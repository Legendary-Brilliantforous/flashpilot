use serde::Serialize;
use std::time::{Duration, Instant};

use crate::error::{Result, BridgeError, UsbError};
use crate::usb;
use rusb::Context;

const OP_GET_DEVICE_INFO: u16 = 0x1001;
const OP_OPEN_SESSION: u16 = 0x1002;
const RSP_OK: u16 = 0x2001;
const TYPE_CMD: u16 = 0x0001;
const TYPE_DATA: u16 = 0x0002;
const TYPE_RSP: u16 = 0x0003;
#[allow(dead_code)]
const TYPE_EVENT: u16 = 0x0004;

#[derive(Serialize)]
struct MtpDeviceInfo {
    standard_version: u16,
    vendor_extension_id: u32,
    mtp_version: u16,
    mtp_extensions: String,
    functional_mode: u16,
    operations_supported: Vec<u32>,
    vendor_operations: Vec<u32>,
    events_supported: Vec<u32>,
    device_properties_supported: Vec<u16>,
    manufacturer: String,
    model: String,
    device_version: String,
    serial_number: String,
    session_response: u16,
    raw_hex: String,
}

fn u16_at(d: &[u8], off: usize) -> u16 {
    u16::from_le_bytes([d[off], d[off + 1]])
}

fn u32_at(d: &[u8], off: usize) -> u32 {
    u32::from_le_bytes([d[off], d[off + 1], d[off + 2], d[off + 3]])
}

/// MTP string: 1-byte length (in bytes) followed by UTF-8 chars.
fn read_string(d: &[u8], off: &mut usize) -> String {
    if *off >= d.len() {
        return String::new();
    }
    let len = d[*off] as usize;
    *off += 1;
    let end = (*off + len).min(d.len());
    let raw = &d[*off..end];
    *off = end;
    String::from_utf8_lossy(raw).trim_matches('\0').trim().to_string()
}

fn read_u32_array(d: &[u8], off: &mut usize) -> Vec<u32> {
    if *off + 4 > d.len() {
        return Vec::new();
    }
    let count = u32_at(d, *off) as usize;
    *off += 4;
    let mut out = Vec::new();
    for _ in 0..count {
        if *off + 4 > d.len() {
            break;
        }
        out.push(u32_at(d, *off));
        *off += 4;
    }
    out
}

fn read_u16_array(d: &[u8], off: &mut usize) -> Vec<u16> {
    if *off + 4 > d.len() {
        return Vec::new();
    }
    let count = u32_at(d, *off) as usize;
    *off += 4;
    let mut out = Vec::new();
    for _ in 0..count {
        if *off + 2 > d.len() {
            break;
        }
        out.push(u16_at(d, *off));
        *off += 2;
    }
    out
}

fn hex_dump(bytes: &[u8]) -> String {
    bytes
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect::<Vec<_>>()
        .join(" ")
}

/// Send an MTP GetDeviceInfo over the device's MTP bulk interface and parse
/// the DeviceInfo dataset (operations/events/properties supported).
///
/// This is read-only and safe. The OperationsSupported array is the ground
/// truth for whether this firmware has any Samsung vendor operations that
/// could, e.g., launch a browser without ADB.
pub fn mtp_info(target: &str, timeout_ms: u64) -> Result<String> {
    let mut parts = target.split('@');
    let id = parts.next().unwrap_or("");
    let vid = u16::from_str_radix(id.split(':').next().unwrap_or(""), 16)
        .map_err(|_| "bad vid".to_string())?;
    let pid = u16::from_str_radix(id.split(':').nth(1).unwrap_or(""), 16)
        .map_err(|_| "bad pid".to_string())?;
    let prefer = match parts.next() {
        Some(loc) => {
            let loc: Vec<&str> = loc.split(':').collect();
            let bus: u8 = loc[0].parse().map_err(|_| "bad bus".to_string())?;
            let addr: u8 = loc[1].parse().map_err(|_| "bad addr".to_string())?;
            Some((bus, addr))
        }
        None => None,
    };

    let _context = Context::new().map_err(|e| crate::error::BridgeError::Usb(crate::error::UsbError::TransferFailed(e.to_string())))?;
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

    let mtp_iface = target_dev
        .interfaces
        .iter()
        .find(|i| i.class == 6)
        .ok_or("no MTP interface found (class 6)")?;
    let in_ep = mtp_iface
        .endpoints
        .iter()
        .find(|e| e.transfer_type == "bulk" && e.direction == "in")
        .map(|e| e.address)
        .ok_or("no bulk IN endpoint on MTP interface")?;
    let out_ep = mtp_iface
        .endpoints
        .iter()
        .find(|e| e.transfer_type == "bulk" && e.direction == "out")
        .map(|e| e.address)
        .ok_or("no bulk OUT endpoint on MTP interface")?;

    let mut handle = usb::UsbDevice::open(0x04e8, pid, target_dev.bus, target_dev.address)?;
    handle
        .set_auto_detach_kernel_driver(true)
        .map_err(|e| format!("set auto detach: {e}"))?;
    handle
        .claim_interface(mtp_iface.number)
        .map_err(|e| format!("claim iface {}: {e}", mtp_iface.number))?;

    let mut buf = vec![0u8; 4096];
    let mut raw: Vec<u8> = Vec::new();

    // OpenSession (0x1002) with session id 1 - Samsung MTP stacks reject
    // GetDeviceInfo until a session is open.
    let mut session = [0u8; 16];
    session[0..4].copy_from_slice(&16u32.to_le_bytes());
    session[4..6].copy_from_slice(&TYPE_CMD.to_le_bytes());
    session[6..8].copy_from_slice(&OP_OPEN_SESSION.to_le_bytes());
    session[8..12].copy_from_slice(&1u32.to_le_bytes());
    session[12..16].copy_from_slice(&1u32.to_le_bytes()); // session id

    handle
        .write_bulk(out_ep, &session, Duration::from_secs(5))
        .map_err(|e| format!("bulk write (session): {e}"))?;

    let deadline = Instant::now() + Duration::from_millis(timeout_ms);
    let mut session_rsp: Option<u16> = None;
    while session_rsp.is_none() && Instant::now() < deadline {
        match handle.read_bulk(in_ep, &mut buf, Duration::from_millis(500)) {
            Ok(n) if n >= 12 => {
                let typ = u16_at(&buf, 4);
                let code = u16_at(&buf, 6);
                if typ == TYPE_RSP {
                    session_rsp = Some(code);
                }
            }
            Ok(_) => {}
            Err(BridgeError::Usb(UsbError::Timeout)) => {}
            Err(e) => {
                let _ = handle.release_interface(mtp_iface.number);
                return Err(BridgeError::InvalidArgument(format!("bulk read (session): {e}")));
            }
        }
    }
    raw.clear();

    // GetDeviceInfo command container: 12-byte header, no parameters.
    let mut cmd = [0u8; 12];
    cmd[0..4].copy_from_slice(&12u32.to_le_bytes());
    cmd[4..6].copy_from_slice(&TYPE_CMD.to_le_bytes());
    cmd[6..8].copy_from_slice(&OP_GET_DEVICE_INFO.to_le_bytes());
    cmd[8..12].copy_from_slice(&2u32.to_le_bytes());

    handle
        .write_bulk(out_ep, &cmd, Duration::from_secs(5))
        .map_err(|e| format!("bulk write: {e}"))?;

    let deadline = Instant::now() + Duration::from_millis(timeout_ms);
    let mut data_payload: Option<Vec<u8>> = None;
    let mut response_code: Option<u16> = None;

    while (data_payload.is_none() || response_code.is_none()) && Instant::now() < deadline {
        match handle.read_bulk(in_ep, &mut buf, Duration::from_millis(500)) {
            Ok(n) => {
                raw.extend_from_slice(&buf[..n]);
                if n < 12 {
                    continue;
                }
                let len = u32_at(&buf, 0) as usize;
                let typ = u16_at(&buf, 4);
                let code = u16_at(&buf, 6);
                if typ == TYPE_DATA && code == OP_GET_DEVICE_INFO {
                    data_payload = Some(buf[12..n.min(len)].to_vec());
                } else if typ == TYPE_RSP {
                    response_code = Some(code);
                }
            }
            Err(BridgeError::Usb(UsbError::Timeout)) => {}
            Err(e) => {
                if data_payload.is_none() && response_code.is_none() {
                    let _ = handle.release_interface(mtp_iface.number);
                    return Err(BridgeError::InvalidArgument(format!("bulk read: {e}")));
                }
            }
        }
    }
    let _ = handle.release_interface(mtp_iface.number);

    let payload = data_payload
        .ok_or("no MTP DeviceInfo data received - is the phone connected in MTP mode?")?;
    let rsp = response_code.unwrap_or(0);
    if rsp != RSP_OK {
        return Err(BridgeError::InvalidArgument(format!(
            "MTP GetDeviceInfo response 0x{{rsp:04x}} (not 0x2001 OK)"
        )));
    }

    let mut off = 0usize;
    let standard_version = if off + 2 <= payload.len() { u16_at(&payload, off) } else { 0 };
    off += 2;
    let vendor_extension_id = if off + 4 <= payload.len() { u32_at(&payload, off) } else { 0 };
    off += 4;
    let mtp_version = if off + 2 <= payload.len() { u16_at(&payload, off) } else { 0 };
    off += 2;
    let mtp_extensions = read_string(&payload, &mut off);
    let functional_mode = if off + 2 <= payload.len() { u16_at(&payload, off) } else { 0 };
    off += 2;
    let operations = read_u32_array(&payload, &mut off);
    let events = read_u32_array(&payload, &mut off);
    let properties = read_u16_array(&payload, &mut off);
    let _capture = read_u16_array(&payload, &mut off);
    let _image = read_u16_array(&payload, &mut off);
    let manufacturer = read_string(&payload, &mut off);
    let model = read_string(&payload, &mut off);
    let device_version = read_string(&payload, &mut off);
    let serial_number = read_string(&payload, &mut off);

    // Vendor operations: PTP/MTP core stops around 0x9FFF; Samsung vendor ops
    // live above 0xA000 (their "MTP vendor extension" block).
    let vendor_ops = operations
        .iter()
        .copied()
        .filter(|&c| c >= 0xA000)
        .collect::<Vec<_>>();

    let result = MtpDeviceInfo {
        standard_version,
        vendor_extension_id,
        mtp_version,
        mtp_extensions,
        functional_mode,
        vendor_operations: vendor_ops,
        operations_supported: operations,
        events_supported: events,
        device_properties_supported: properties,
        manufacturer,
        model,
        device_version,
        serial_number,
        session_response: session_rsp.unwrap_or(0),
        raw_hex: hex_dump(&payload),
    };
    serde_json::to_string(&result).map_err(|e| BridgeError::InvalidArgument(e.to_string()))
}
