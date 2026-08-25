use std::time::{Duration, Instant};

use serde::Serialize;

use crate::config::{DeviceInfo, InterfaceInfo};
use crate::error::{Result, BridgeError};
use crate::usb;
use rusb::Context;

#[derive(Serialize)]
struct AtResult {
    sent: String,
    reply_hex: String,
    reply: String,
    ok: bool,
}

/// Locate the CDC ACM interface pair on a Samsung device:
/// the comm interface (class 2 / subclass 2) and the data interface (class 10).
fn find_acm_interfaces(dev: &DeviceInfo) -> Option<(&InterfaceInfo, &InterfaceInfo)> {
    let comm = dev.interfaces.iter().find(|i| i.class == 2 && i.subclass == 2);
    let data = dev.interfaces.iter().find(|i| {
        i.class == 10
            && i.endpoints
                .iter()
                .any(|e| e.transfer_type == "bulk" && e.direction == "in")
            && i.endpoints
                .iter()
                .any(|e| e.transfer_type == "bulk" && e.direction == "out")
    });
    match (comm, data) {
        (Some(c), Some(d)) => Some((c, d)),
        (_, Some(d)) => Some((d, d)),
        _ => None,
    }
}

fn hex_dump(bytes: &[u8]) -> String {
    bytes
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect::<Vec<_>>()
        .join(" ")
}

/// Send an AT command to a Samsung device's CDC ACM port over libusb bulk
/// transfers (target = vid:pid[@bus:addr], cmd = text after "AT", or "" for a
/// bare AT ping). Works in the diag/modem USB configuration (config 2), which
/// is how commercial tools prompt "Allow USB debugging" on FRP-locked phones.
pub fn at_send(target: &str, cmd: &str, timeout_ms: u64) -> Result<String> {
    let mut parts = target.split('@');
    let id = parts.next().unwrap_or("");
    let vid = u16::from_str_radix(id.split(':').next().unwrap_or(""), 16)
        .map_err(|_| BridgeError::InvalidArgument("bad vid".to_string()))?;
    let pid = u16::from_str_radix(id.split(':').nth(1).unwrap_or(""), 16)
        .map_err(|_| BridgeError::InvalidArgument("bad pid".to_string()))?;
    if vid != 0x04e8 {
        return Err(BridgeError::InvalidArgument(format!("vid {vid:04x} is not Samsung 04e8")));
    }
    let prefer = match parts.next() {
        Some(loc) => {
            let loc: Vec<&str> = loc.split(':').collect();
            let bus: u8 = loc[0].parse().map_err(|_| BridgeError::InvalidArgument("bad bus".to_string()))?;
            let addr: u8 = loc[1].parse().map_err(|_| BridgeError::InvalidArgument("bad addr".to_string()))?;
            Some((bus, addr))
        }
        None => None,
    };

    // Build the AT line, appending CRLF if the caller didn't include it.
    let mut line = String::from("AT");
    if !cmd.is_empty() {
        line.push_str(cmd);
    }
    if !line.ends_with('\n') {
        line.push_str("\r\n");
    }

    // Keep rusb Context alive for the whole operation - libusb requires the
    // context to outlive any DeviceHandle. Using the same context for
    // enumeration and handle open avoids a race where the device disappears
    // between two independent Context::new() calls.
    let context = Context::new().map_err(|e| BridgeError::Usb(crate::error::UsbError::TransferFailed(e.to_string())))?;
    // Use vid/pid to validate against enumerated DeviceInfo, then open a
    // claimed handle that stays alive through the bulk session.
    let info = usb::collect_devices(Some(vid))?;
    let target_dev = info
        .iter()
        .find(|d| {
            d.vid == vid
                && d.pid == pid
                && prefer
                    .map(|(bus, addr)| d.bus == bus && d.address == addr)
                    .unwrap_or(true)
        })
        .ok_or("device disappeared during enumeration")?;

    let (comm, data) = find_acm_interfaces(target_dev).ok_or(
        "no CDC ACM interface found - is the phone in diag/modem config (usb-config 2)?",
    )?;

    let in_ep = data
        .endpoints
        .iter()
        .find(|e| e.transfer_type == "bulk" && e.direction == "in")
        .map(|e| e.address)
        .ok_or("no bulk IN endpoint")?;
    let out_ep = data
        .endpoints
        .iter()
        .find(|e| e.transfer_type == "bulk" && e.direction == "out")
        .map(|e| e.address)
        .ok_or("no bulk OUT endpoint")?;

    // Open via validated vid/pid/bus/address and keep handle alive.
    let mut handle = usb::UsbDevice::open(vid, pid, target_dev.bus, target_dev.address)?;

    handle.set_auto_detach_kernel_driver(true)?;

    // Configure the ACM line (115200 8N1) and assert DTR on the comm interface
    // so the modem/daemon on the phone accepts data.
    if comm.number != data.number {
        let mut line_coding = [0x00u8, 0xc2, 0x01, 0x00, 0x00, 0x00, 0x08];
        let _ = handle.control_transfer(
            0x21,                       // class, host->device, interface
            0x20,                       // SET_LINE_CODING
            0,
            comm.number as u16,
            &mut line_coding,
            Duration::from_secs(2),
        );
        let _ = handle.control_transfer(
            0x21,                    // class, host->device, interface
            0x22,                    // SET_CONTROL_LINE_STATE (DTR+RTS)
            0x0003,
            comm.number as u16,
            &mut [],
            Duration::from_secs(2),
        );
    }

    handle.claim_interface(data.number)?;

    handle.write_bulk(out_ep, line.as_bytes(), Duration::from_secs(5))?;

    // Read until OK/ERROR (accumulated across chunks) or timeout.
    let deadline = Instant::now() + Duration::from_millis(timeout_ms);
    let mut reply = Vec::new();
    let mut buf = vec![0u8; 512];
    loop {
        match handle.read_bulk(in_ep, &mut buf, Duration::from_millis(400)) {
            Ok(n) => reply.extend_from_slice(&buf[..n]),
            Err(crate::error::BridgeError::Usb(crate::error::UsbError::Timeout)) => {}
            Err(e) => {
                if reply.is_empty() {
                    let _ = handle.release_interface(data.number);
                    return Err(BridgeError::InvalidArgument(format!("bulk read: {e}")));
                }
            }
        }
        let ascii = String::from_utf8_lossy(&reply);
        if ascii.contains("OK\r\n") || ascii.contains("ERROR\r\n") {
            break;
        }
        if Instant::now() >= deadline {
            break;
        }
    }
    let _ = handle.release_interface(data.number);
    // Keep context alive until after handle is released.
    drop(context);

    let ascii = String::from_utf8_lossy(&reply).to_string();
    let ok = ascii.contains("OK");
    let result = AtResult {
        sent: hex_dump(line.as_bytes()),
        reply_hex: hex_dump(&reply),
        reply: ascii.trim().to_string(),
        ok,
    };
    serde_json::to_string(&result).map_err(|e| crate::error::BridgeError::Io(e.to_string()))
}
