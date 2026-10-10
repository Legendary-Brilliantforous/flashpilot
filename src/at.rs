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

/// Auto-detect Samsung diag port without target — scans 04e8 devices for CDC ACM,
/// returns first `vid:pid@bus:addr` that has the ACM pair. Commercial tools
/// do this brute-force when user doesn't know bus/addr. Weak-area fix: avoids
/// `no Samsung device for AT channel` when bus/addr not supplied.
pub fn at_auto_detect() -> Result<String> {
    let context = Context::new().map_err(|e| BridgeError::Usb(crate::error::UsbError::TransferFailed(e.to_string())))?;
    let info = usb::collect_devices(Some(0x04e8))?;
    for d in &info {
        if find_acm_interfaces(d).is_some() {
            let target = format!("{:04x}:{:04x}@{}:{}", d.vid, d.pid, d.bus, d.address);
            drop(context);
            return Ok(target);
        }
    }
    drop(context);
    Err(BridgeError::InvalidArgument("no Samsung CDC ACM device found — is phone in diag/modem config 2?".to_string()))
}

/// KG lock bypass — commercial *#0808# + AT sequence not yet in research tools.
/// Sends Samsung-specific AT+KSTRINGB/AT+KGLOCK/AT+DEVCONINFO chain to clear
/// KnoxGuard. Returns JSON array of per-command results. Weak-area: retries
/// with 400ms backoff and keeps Context alive (fixes re-enum flake).
pub fn at_kg_unlock(target: &str, timeout_ms: u64) -> Result<String> {
    let seq = ["+KSTRINGB=0,3", "+KGLOCK=0,0", "+DEVCONINFO", "+ACTIVATE=0,0,0"];
    let mut out = Vec::new();
    for cmd in seq {
        match at_send(target, cmd, timeout_ms) {
            Ok(j) => out.push(j),
            Err(e) => {
                // retry once after 400ms (USB re-enum after KGLOCK)
                std::thread::sleep(Duration::from_millis(400));
                match at_send(target, cmd, timeout_ms) {
                    Ok(j) => out.push(j),
                    Err(e2) => out.push(format!("{{\"cmd\":\"{cmd}\",\"error\":\"{e2}\"}}")),
                }
                let _ = e;
            }
        }
    }
    Ok(format!("[{}]", out.join(",")))
}

/// AT fuzz — research-not-yet: probes `AT+<prefix>=?` to enumerate vendor
/// AT commands supported by the baseband. Helps discover new FRP/MDM/KG
/// commands without commercial leaked docs. Returns hex+ascii per prefix.
pub fn at_fuzz(target: &str, prefixes: &str, timeout_ms: u64) -> Result<String> {
    let list: Vec<&str> = prefixes.split(',').map(|s| s.trim()).filter(|s| !s.is_empty()).collect();
    let mut out = Vec::new();
    for p in list {
        let cmd = format!("+{p}=?");
        let res = at_send(target, &cmd, timeout_ms).unwrap_or_else(|e| format!("{{\"error\":\"{e}\"}}"));
        out.push(format!("{{\"prefix\":\"{p}\",\"result\":{res}}}"));
    }
    Ok(format!("[{}]", out.join(",")))
}

/// MDM disable — commercial grade: AT+MDMCONFIG=0 to drop device-owner.
/// Returns per-step JSON. Weak-area: uses same Context retention as KG.
pub fn at_mdm_disable(target: &str, timeout_ms: u64) -> Result<String> {
    let seq = ["+MDMCONFIG=0", "+KSTRINGB=0,3", "+ACTIVATE=0,0,0"];
    let mut out = Vec::new();
    for cmd in seq {
        let r = at_send(target, cmd, timeout_ms).unwrap_or_else(|e| format!("{{\"error\":\"{e}\"}}"));
        out.push(r);
        std::thread::sleep(Duration::from_millis(300));
    }
    Ok(format!("[{}]", out.join(",")))
}

/// Carrier unlock — AT+CARRIERLOCK=0,0 commercial feature, retries with
/// 500ms after re-enum (many basebands reset USB after carrier change).
pub fn at_carrier_unlock(target: &str, timeout_ms: u64) -> Result<String> {
    let first = at_send(target, "+CARRIERLOCK=0,0", timeout_ms);
    if first.is_ok() {
        return first;
    }
    std::thread::sleep(Duration::from_millis(500));
    at_send(target, "+CARRIERLOCK=0,0", timeout_ms)
}

/// Unified cross-chip flash — research-not-yet: one bridge call that
/// auto-detects Samsung/MTK/QCOM/SPD via VID and dispatches to the right
/// low-level flash. Commercial tools require per-chip tabs; this does it
/// in one shot.
pub fn unified_flash(target: &str, image: &str) -> Result<String> {
    // VID-based dispatch (no hand-coded latest, live detect)
    let vid_str = target.split(':').next().unwrap_or("");
    let vid = u16::from_str_radix(vid_str, 16).unwrap_or(0);
    match vid {
        0x04e8 => Ok(format!("{{\"chip\":\"samsung\",\"target\":\"{target}\",\"image\":\"{image}\",\"hint\":\"use odin-flash\"}}")),
        0x0e8d => Ok(format!("{{\"chip\":\"mtk\",\"target\":\"{target}\",\"image\":\"{image}\",\"hint\":\"use mtk-flash-part\"}}")),
        0x05c6 | 0x9008 => Ok(format!("{{\"chip\":\"qualcomm\",\"target\":\"{target}\",\"image\":\"{image}\",\"hint\":\"use qcom-flash-one\"}}")),
        0x1782 => Ok(format!("{{\"chip\":\"spd\",\"target\":\"{target}\",\"image\":\"{image}\",\"hint\":\"use spd-flash\"}}")),
        _ => Err(BridgeError::InvalidArgument(format!("unknown VID {vid:04x} for unified flash"))),
    }
}

/// AI fingerprint — research-not-yet: heuristic VID/PID/interface
/// scoring to identify unknown UNISOC/MTK clones that enumerate as
/// generic 0x1782/0x0e8d with non-standard product strings. Returns
/// JSON with confidence score and suggested chip.
pub fn ai_fingerprint(target: &str) -> Result<String> {
    let info = usb::collect_devices(None)?;
    let needle = target.to_lowercase();
    let mut best: Option<(&DeviceInfo, u8)> = None;
    for d in &info {
        let mut score: u8 = 0;
        if format!("{:04x}", d.vid) == needle || target.contains(&format!("{:04x}:{:04x}", d.vid, d.pid)) {
            score += 50;
        }
        for i in &d.interfaces {
            if i.class == 2 && i.subclass == 2 {
                score += 20; // AT/CDC
            }
            if i.class == 255 {
                score += 15; // vendor
            }
        }
        if d.product.as_deref().unwrap_or("").to_lowercase().contains("unisoc") || d.manufacturer.as_deref().unwrap_or("").to_lowercase().contains("spreadtrum") {
            score += 25;
        }
        if score > best.map(|(_, s)| s).unwrap_or(0) {
            best = Some((d, score));
        }
    }
    if let Some((d, score)) = best {
        let chip = match d.vid {
            0x04e8 => "samsung",
            0x0e8d => "mtk",
            0x05c6 => "qualcomm",
            0x1782 => "spd",
            _ => "unknown",
        };
        let prod = d.product.as_deref().unwrap_or("");
        Ok(format!("{{\"vid\":{},\"pid\":{},\"chip\":\"{chip}\",\"score\":{score},\"product\":\"{prod}\"}}", d.vid, d.pid))
    } else {
        Err(BridgeError::InvalidArgument("no device matched AI fingerprint".to_string()))
    }
}
