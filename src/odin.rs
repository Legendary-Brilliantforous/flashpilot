use std::time::Duration;

use serde::Serialize;
use serde_json::json;

use crate::error::{Result, BridgeError};
use crate::usb;

// Protocol constants from the Heimdall project (MIT) - the reverse-engineered
// Samsung "Odin 3" download protocol.
const CTRL_SESSION: u32 = 0x64;
const CTRL_PIT_FILE: u32 = 0x65;
#[allow(dead_code)]
const CTRL_FILE_TRANSFER: u32 = 0x66;
const CTRL_END_SESSION: u32 = 0x67;

const RESP_SESSION: u32 = 0x64;
const RESP_PIT_FILE: u32 = 0x65;

#[allow(dead_code)]
const PIT_REQUEST_FLASH: u32 = 0x00;
const PIT_REQUEST_DUMP: u32 = 0x01;
const PIT_REQUEST_PART: u32 = 0x02;
const PIT_REQUEST_END: u32 = 0x03;

#[allow(dead_code)]
const FILE_REQUEST_FLASH: u32 = 0x00;

const PACKET_SIZE: usize = 1024;
const RECV_PART_SIZE: usize = 512;

#[derive(Debug)]
struct OdinError(String);

impl std::fmt::Display for OdinError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl From<std::io::Error> for OdinError {
    fn from(e: std::io::Error) -> Self {
        OdinError(e.to_string())
    }
}

impl From<String> for OdinError {
    fn from(e: String) -> Self {
        OdinError(e)
    }
}

impl From<crate::error::BridgeError> for OdinError {
    fn from(e: crate::error::BridgeError) -> Self {
        OdinError(e.to_string())
    }
}

impl From<rusb::Error> for OdinError {
    fn from(e: rusb::Error) -> Self {
        OdinError(e.to_string())
    }
}

type OdinResult<T> = std::result::Result<T, OdinError>;

fn err<T>(msg: impl Into<String>) -> OdinResult<T> {
    Err(OdinError(msg.into()))
}

struct Device {
    handle: rusb::DeviceHandle<rusb::Context>,
    in_ep: u8,
    out_ep: u8,
}

fn open_device(target: &str) -> OdinResult<Device> {
    let devices = usb::collect_devices(Some(0x04e8))?;
    let wanted: Vec<&str> = target.split('@').collect();
    if wanted.len() != 2 {
        return err("target must be vid:pid@bus:addr");
    }
    let vid = u16::from_str_radix(wanted[0].split(':').next().unwrap_or(""), 16)
        .map_err(|_| OdinError("bad vid".into()))?;
    let loc: Vec<&str> = wanted[1].split(':').collect();
    let bus: u8 = loc[0].parse().map_err(|_| OdinError("bad bus".into()))?;
    let addr: u8 = loc[1].parse().map_err(|_| OdinError("bad addr".into()))?;

    let target_dev = devices
        .iter()
        .find(|d| d.vid == vid && d.bus == bus && d.address == addr)
        .ok_or(OdinError("device not found (is it in download mode?)".into()))?;

    let iface = target_dev
        .interfaces
        .iter()
        .find(|i| i.class == 10)
        .or_else(|| {
            target_dev.interfaces.iter().find(|i| {
                i.endpoints
                    .iter()
                    .any(|e| e.transfer_type == "bulk" && e.direction == "out")
                    && i.endpoints
                        .iter()
                        .any(|e| e.transfer_type == "bulk" && e.direction == "in")
            })
        })
        .ok_or(OdinError("no CDC data interface".into()))?;
    let in_ep = iface
        .endpoints
        .iter()
        .find(|e| e.direction == "in" && e.transfer_type == "bulk")
        .map(|e| e.address)
        .ok_or(OdinError("no bulk IN".into()))?;
    let out_ep = iface
        .endpoints
        .iter()
        .find(|e| e.direction == "out" && e.transfer_type == "bulk")
        .map(|e| e.address)
        .ok_or(OdinError("no bulk OUT".into()))?;

    let context = rusb::Context::new().map_err(|e| OdinError(format!("libusb: {e}")))?;
    use rusb::UsbContext;
    let handle = context
        .devices()?
        .iter()
        .find(|d| {
            let desc = d.device_descriptor().ok();
            desc.as_ref().map_or(false, |desc| {
                desc.vendor_id() == vid && desc.product_id() == target_dev.pid
            }) && d.bus_number() == target_dev.bus && d.address() == target_dev.address
        })
        .ok_or(OdinError("device not found".into()))?
        .open()?;

    handle
        .set_auto_detach_kernel_driver(true)
        .map_err(|e| OdinError(format!("auto detach: {e}")))?;
    handle
        .claim_interface(iface.number)
        .map_err(|e| OdinError(format!("claim iface: {e}")))?;

    Ok(Device { handle, in_ep, out_ep })
}

impl Device {
    fn send_raw(&self, data: &[u8]) -> OdinResult<()> {
        self.handle
            .write_bulk(self.out_ep, data, Duration::from_secs(10))
            .map_err(|e| OdinError(format!("bulk write: {e}")))?;
        Ok(())
    }

    fn recv_raw(&self, len: usize, timeout: u64) -> OdinResult<Vec<u8>> {
        // Always read into at least a 512-byte buffer: Samsung download mode
        // (and MediaTek variants like the A14/A06) send full max-packet-size
        // bulk packets. Reading a smaller buffer makes libusb return
        // LIBUSB_ERROR_OVERFLOW even though the transfer succeeded.
        let buflen = len.max(512);
        let mut buf = vec![0u8; buflen];
        let n = self
            .handle
            .read_bulk(self.in_ep, &mut buf, Duration::from_secs(timeout))
            .map_err(|e| OdinError(format!("bulk read: {e}")))?;
        buf.truncate(n);
        Ok(buf)
    }

    /// Handshake: send "ODIN", expect "LOKE".
    fn handshake(&self) -> OdinResult<()> {
        // Drain any leftover frames from a previous session before sending ODIN.
        for _ in 0..4 {
            let r = self.recv_raw(512, 1);
            match r {
                Ok(_) => continue,
                Err(_) => break, // no pending data
            }
        }
        for attempt in 0..4 {
            self.send_raw(b"ODIN")?;
            let resp = self.recv_raw(7, 5)?;
            if resp.get(..4) == Some(b"LOKE") {
                return Ok(());
            }
            eprintln!(
                "[handshake] attempt {attempt}: got {:?}, retrying",
                resp.iter().map(|b| format!("{:02x}", b)).collect::<Vec<_>>().join(" ")
            );
        }
        err("handshake failed after retries")
    }

    /// Pack a little-endian u32 control frame of the given type + payload.
    fn control_frame(control_type: u32, payload: &[u8]) -> Vec<u8> {
        let mut frame = vec![0u8; PACKET_SIZE];
        frame[0..4].copy_from_slice(&control_type.to_le_bytes());
        for (i, chunk) in payload.chunks(4).enumerate() {
            let mut u = [0u8; 4];
            u.copy_from_slice(chunk);
            frame[4 + i * 4..8 + i * 4].copy_from_slice(&u);
        }
        frame
    }

    fn send_control(&self, control_type: u32, payload: &[u8]) -> OdinResult<()> {
        let frame = Self::control_frame(control_type, payload);
        self.send_raw(&frame)
    }

    fn recv_response(&self, expected_type: u32, timeout: u64) -> OdinResult<Vec<u8>> {
        let resp = self.recv_raw(8, timeout)?;
        if resp.len() < 4 {
            return err("short response");
        }
        let rtype = u32::from_le_bytes([resp[0], resp[1], resp[2], resp[3]]);
        if rtype != expected_type {
            return err(format!("unexpected response type 0x{:x}", rtype));
        }
        Ok(resp)
    }

    fn begin_session(&self) -> OdinResult<u32> {
        self.send_control(CTRL_SESSION, &0u32.to_le_bytes())?;
        let resp = self.recv_response(RESP_SESSION, 15)?;
        Ok(u32::from_le_bytes([resp[4], resp[5], resp[6], resp[7]]))
    }

    fn end_session(&self) -> OdinResult<()> {
        // kRequestEndSession = 0 (EndSessionPacket) - send end session control
        self.send_control(CTRL_END_SESSION, &0u32.to_le_bytes())?;
        Ok(())
    }

    fn request_pit_dump(&self) -> OdinResult<u32> {
        self.send_control(CTRL_PIT_FILE, &PIT_REQUEST_DUMP.to_le_bytes())?;
        let resp = self.recv_response(RESP_PIT_FILE, 15)?;
        let size = u32::from_le_bytes([resp[4], resp[5], resp[6], resp[7]]);
        Ok(size)
    }

    fn request_pit_part(&self, index: u32) -> OdinResult<Vec<u8>> {
        let mut payload = Vec::new();
        payload.extend_from_slice(&PIT_REQUEST_PART.to_le_bytes());
        payload.extend_from_slice(&index.to_le_bytes());
        self.send_control(CTRL_PIT_FILE, &payload)?;
        self.recv_raw(RECV_PART_SIZE, 15)
    }

    fn end_pit_transfer(&self) -> OdinResult<()> {
        self.send_control(CTRL_PIT_FILE, &PIT_REQUEST_END.to_le_bytes())?;
        Ok(())
    }

    fn dump_pit(&self) -> OdinResult<Vec<u8>> {
        let size = self.request_pit_dump()? as usize;
        if size == 0 {
            return err("PIT dump refused (size 0)");
        }
        let mut pit = Vec::with_capacity(size);
        let transfer_count = size.div_ceil(RECV_PART_SIZE);
        for i in 0..transfer_count {
            let part = self.request_pit_part(i as u32)?;
            pit.extend_from_slice(&part);
            if pit.len() >= size {
                break;
            }
        }
        pit.truncate(size);
        self.end_pit_transfer()?;
        Ok(pit)
    }

    /// Device info extraction (cmd 0x69): dump model/serial/region/carrier.
    /// 0x69/0x00 -> size, 0x69/0x01 + index -> 500-byte block, 0x69/0x02 -> end.
    fn dump_device_info(&self) -> OdinResult<Vec<u8>> {
        self.send_control(0x69, &0u32.to_le_bytes())?;
        let resp = self.recv_raw(8, 15)?;
        if resp.len() < 8 {
            return err("short device-info response");
        }
        let rtype = u32::from_le_bytes([resp[0], resp[1], resp[2], resp[3]]);
        let size = u32::from_le_bytes([resp[4], resp[5], resp[6], resp[7]]);
        if rtype != 0x69 {
            return err(format!("unexpected 0x69 response type 0x{:x}", rtype));
        }
        let size = size as usize;
        if size == 0 || size > 0x100000 {
            return err(format!("unexpected device-info size {size}"));
        }
        let mut data = Vec::with_capacity(size);
        let transfer_count = size.div_ceil(RECV_PART_SIZE);
        for i in 0..transfer_count {
            let mut payload = Vec::new();
            payload.extend_from_slice(&1u32.to_le_bytes());
            payload.extend_from_slice(&(i as u32).to_le_bytes());
            self.send_control(0x69, &payload)?;
            let part = self.recv_raw(RECV_PART_SIZE, 15)?;
            data.extend_from_slice(&part);
            if data.len() >= size {
                break;
            }
        }
        data.truncate(size);
        self.send_control(0x69, &2u32.to_le_bytes())?;
        Ok(data)
    }

    /// Device type query (0x64/0x01): returns the model string.
    fn request_device_type(&self) -> OdinResult<Vec<u8>> {
        let mut payload = Vec::new();
        payload.extend_from_slice(&1u32.to_le_bytes());
        self.send_control(CTRL_SESSION, &payload)?;
        self.recv_raw(1024, 15)
    }
}

/// Keep only printable ASCII, then pick the token that looks like a Samsung
/// model (SM-/GT-/SC-... or a compact alphanumeric string with a digit).
fn pick_model(clean: &str) -> String {
    for tok in clean.split_whitespace() {
        let t = tok.trim_matches(|c: char| c == '\0' || c.is_whitespace());
        if t.starts_with("SM-") || t.starts_with("GT-") || t.starts_with("SC-") {
            return t.to_string();
        }
    }
    for tok in clean.split_whitespace() {
        let t = tok.trim_matches(|c: char| c == '\0');
        let n = t.chars().count();
        if n >= 4
            && t.chars().any(|c| c.is_ascii_digit())
            && t.chars().all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
        {
            return t.to_string();
        }
    }
    clean.trim().to_string()
}

/// Read the device model string over the Odin protocol the same way the
/// desktop Odin shows it (session probe 0x64/0x01), falling back to the
/// 0x69 device-info dump. Runs in its own session so a probe that desyncs
/// one session (e.g. on old J3 firmware) does not affect other commands.
pub fn odin_model(target: &str) -> Result<String> {
    let dev = open_device(target).map_err(|e| e.to_string())?;
    dev.handshake().map_err(|e| e.to_string())?;
    dev.begin_session().map_err(|e| e.to_string())?;

    let mut model = String::new();
    let mut info_bytes: Option<usize> = None;
    if let Ok(data) = dev.request_device_type() {
        let ascii: String = data
            .iter()
            .map(|&b| if (0x20..0x7f).contains(&b) { b as char } else { ' ' })
            .collect();
        model = pick_model(&ascii);
    }
    if model.is_empty() {
        match dev.dump_device_info() {
            Ok(data) => {
                info_bytes = Some(data.len());
                let ascii: String = data
                    .iter()
                    .map(|&b| if (0x20..0x7f).contains(&b) { b as char } else { ' ' })
                    .collect();
                model = pick_model(&ascii);
            }
            Err(e) => model = format!("(device info probe failed: {e})"),
        }
    }
    dev.end_session().ok();

    Ok(serde_json::json!({
        "model": model,
        "info_bytes": info_bytes,
    })
    .to_string())
}

#[derive(Serialize)]
pub struct OdinSessionInfo {
    pub handshake: bool,
    pub session: bool,
    pub packet_size: u32,
}

pub fn odin_connect(target: &str) -> Result<String> {
    let dev = open_device(target).map_err(|e| e.to_string())?;
    dev.handshake().map_err(|e| e.to_string())?;
    let packet_size = dev.begin_session().map_err(|e| e.to_string())?;
    let info = OdinSessionInfo {
        handshake: true,
        session: true,
        packet_size,
    };
    let json = serde_json::to_string(&info).map_err(|e| e.to_string())?;
    Ok(json)
}

pub fn odin_pit(target: &str, out_file: Option<&str>) -> Result<String> {
    let dev = open_device(target).map_err(|e| e.to_string())?;
    dev.handshake().map_err(|e| e.to_string())?;
    dev.begin_session().map_err(|e| e.to_string())?;
    let pit = dev.dump_pit().map_err(|e| e.to_string())?;
    dev.end_session().ok();

    if let Some(path) = out_file {
        std::fs::write(path, &pit).map_err(|e| e.to_string())?;
        return Ok(format!("{{\"size\": {}, \"file\": \"{}\"}}", pit.len(), path));
    }

    let full = pit.iter().map(|b| format!("{:02x}", b)).collect::<Vec<_>>().join("");
    Ok(format!(
        "{{\"size\": {}, \"hex\": \"{}\"}}",
        pit.len(),
        full
    ))
}

/// MediaTek download-agent PIT dump. Samsung MTK devices (A14/A06 class)
/// answer the "ODIN" probe with the raw PIT bytes instead of "LOKE" - no
/// session control, no LOKE handshake. Stream the response until we have the
/// full PIT (32-byte header + count*132 bytes).
pub fn odin_pit_mtk(target: &str, out_file: Option<&str>) -> Result<String> {
    let dev = open_device(target).map_err(|e| e.to_string())?;
    dev.send_raw(b"ODIN").map_err(|e| e.to_string())?;

    let mut pit = Vec::new();
    let mut buf = vec![0u8; 512];
    let mut cap = 0u32;
    let mut idle = 0u32;
    // Read until we have the full PIT or the DA goes quiet for a few packets.
    while idle < 3 && pit.len() < (32 + cap as usize * 132).min(64 * 1024) {
        match dev.handle.read_bulk(dev.in_ep, &mut buf, Duration::from_secs(2)) {
            Ok(n) => {
                if n == 0 {
                    idle += 1;
                    continue;
                }
                idle = 0;
                pit.extend_from_slice(&buf[..n]);
                if cap == 0 && pit.len() >= 8 {
                    cap = u32::from_le_bytes([pit[4], pit[5], pit[6], pit[7]]);
                }
            }
            Err(_) => idle += 1,
        }
    }

    if pit.len() < 8 || u32::from_le_bytes([pit[0], pit[1], pit[2], pit[3]]) != 0x12349876 {
        let preview = pit
            .iter()
            .take(32)
            .map(|b| format!("{:02x}", b))
            .collect::<Vec<_>>()
            .join(" ");
        return Err(BridgeError::InvalidArgument(format!(
            "MTK PIT dump: bad response ({} bytes, no PIT magic: {preview}",
            pit.len()
        )));
    }

    let count = u32::from_le_bytes([pit[4], pit[5], pit[6], pit[7]]);
    let need = 32 + count as usize * 132;
    if pit.len() > need {
        pit.truncate(need);
    }

    if let Some(path) = out_file {
        std::fs::write(path, &pit).map_err(|e| e.to_string())?;
        return Ok(format!(
            "{{\"size\": {}, \"entries\": {}, \"model\": \"{}\", \"file\": \"{}\"}}",
            pit.len(),
            count,
            String::from_utf8_lossy(&pit[8..28]).trim_matches('\0'),
            path
        ));
    }

    let full = pit.iter().map(|b| format!("{:02x}", b)).collect::<Vec<_>>().join("");
    Ok(format!(
        "{{\"size\": {}, \"entries\": {}, \"hex\": \"{}\"}}",
        pit.len(),
        count,
        full
    ))
}

/// Full recon in a single session: handshake, session, PIT dump.
/// The 0x64/0x01 and 0x69 probes are intentionally skipped - they desync
/// the session stream on older devices like the J3.
pub fn odin_info(target: &str, pit_file: &str) -> Result<String> {
    let dev = open_device(target).map_err(|e| e.to_string())?;
    dev.handshake().map_err(|e| e.to_string())?;
    let packet_size = dev.begin_session().map_err(|e| e.to_string())?;
    let pit = dev.dump_pit().map_err(|e| e.to_string())?;
    std::fs::write(pit_file, &pit).map_err(|e| e.to_string())?;
    dev.end_session().ok();

    let json = serde_json::json!({
        "device_type": "unknown (probes skipped, J3 is old-protocol)",
        "packet_size": packet_size,
        "pit_size": pit.len(),
        "pit_file": pit_file,
    });
    Ok(serde_json::to_string_pretty(&json).map_err(|e| e.to_string())?)
}

/// Odin command: send a 1024-byte request frame with type/subtype/payload,
/// read a response (at least 8 bytes: id + ack), and validate the id.
fn odin_command(
    dev: &Device,
    cmd: u32,
    sub: u32,
    payload: &[u8],
    timeout: u64,
) -> OdinResult<Vec<u8>> {
    let mut buf = vec![0u8; PACKET_SIZE];
    buf[0..4].copy_from_slice(&cmd.to_le_bytes());
    buf[4..8].copy_from_slice(&sub.to_le_bytes());
    if payload.len() + 8 > PACKET_SIZE {
        return err("odin command payload too large");
    }
    buf[8..8 + payload.len()].copy_from_slice(payload);
    dev.send_raw(&buf)?;

    let rsp = dev.recv_raw(512, timeout)?;
    if rsp.len() < 8 {
        return err(format!("odin response too short: {} bytes", rsp.len()));
    }
    Ok(rsp)
}

/// True when the user asked for strict error handling (ODIN_STRICT=1).
/// In strict mode, progress-like ack codes and end-session failures are
/// treated as fatal instead of being tolerated, so a partially written
/// bootloader is never reported as a success.
fn strict_mode() -> bool {
    std::env::var("ODIN_STRICT")
        .map(|v| matches!(v.trim().to_lowercase().as_str(), "1" | "true" | "yes" | "on"))
        .unwrap_or(false)
}

/// Check response like odin4's odin_fail_check.
/// If allow_progress is true, codes -2..-7 are treated as progress (success) -
/// unless ODIN_STRICT=1, in which case they are treated as failures.
fn odin_fail_check(rsp: &[u8], context: &str, allow_progress: bool) -> OdinResult<()> {
    let rid = u32::from_le_bytes([rsp[0], rsp[1], rsp[2], rsp[3]]);
    let ack = u32::from_le_bytes([rsp[4], rsp[5], rsp[6], rsp[7]]);
    let rid_i32 = rid as i32;
    let ack_i32 = ack as i32;

    if rid_i32 == -1 {
        // BOOTLOADER_FAIL (0xFFFFFFFF) - check if it's actually a progress code
        if allow_progress && ack_i32 >= -7 && ack_i32 <= -2 && !strict_mode() {
            // Progress codes: -2 WP, -3 Erase, -4 Write, -5 Auth, -6 Size, -7 Ext4
            // These are treated as success in odin4 for certain commands.
            eprintln!("[debug] {context}: progress code {ack_i32}");
            return Ok(());
        }
        if allow_progress && ack_i32 >= -7 && ack_i32 <= -2 {
            eprintln!("[warn] {context}: progress code {ack_i32} treated as FAILURE (ODIN_STRICT=1)");
        }
        eprintln!("[debug] cmd: BOOTLOADER_FAIL rid=0x{:08x} ack=0x{:08x}", rid, ack);
        return err(format!("{context}: bootloader fail response"));
    }
    if ack_i32 == -1 {
        eprintln!("[debug] cmd: BOOTLOADER_FAIL ack=0x{:08x} rid=0x{:08x}", ack, rid);
        return err(format!("{context}: bootloader fail in ack"));
    }
    Ok(())
}

/// Begin session with protocol negotiation (0x64/0x00), returns packet size.
fn begin_session_v2(dev: &Device) -> OdinResult<u32> {
    let rsp = odin_command(dev, 0x64, 0x00, &0x7FFFFFFFu32.to_le_bytes(), 15)?;
    odin_fail_check(&rsp, "BeginSession", false)?;
    let ack = u32::from_le_bytes([rsp[4], rsp[5], rsp[6], rsp[7]]);
    let ack_upper = ((ack >> 16) & 0xFFFF) as u16;
    let version = ack_upper & 0x7FFF;
    let compressed = (ack_upper & 0x8000) != 0;
    eprintln!(
        "[flash] begin_session ack=0x{ack:08x} version={version} compressed={compressed}"
    );

    if version <= 1 {
        // Legacy protocol: 128KiB packets, no packet-size negotiation.
        let rsp = odin_command(dev, 0x64, 0x05, &131072u32.to_le_bytes(), 15)?;
        odin_fail_check(&rsp, "SendFilePartSize", false)?;
        Ok(131072)
    } else {
        // Modern protocol: 1MiB packets negotiated via 0x64/0x05.
        let rsp = odin_command(dev, 0x64, 0x05, &1048576u32.to_le_bytes(), 15)?;
        odin_fail_check(&rsp, "SendFilePartSize", false)?;
        Ok(1048576)
    }
}

/// Set the total number of bytes about to be flashed (0x64/0x02).
fn set_total_bytes(dev: &Device, total: u64) -> OdinResult<()> {
    let rsp = odin_command(dev, 0x64, 0x02, &total.to_le_bytes(), 15)?;
    odin_fail_check(&rsp, "SetTotalBytes", false)
}

/// Request file flash (0x66/0x00) - begin a partition write.
fn request_file_flash(dev: &Device) -> OdinResult<()> {
    let rsp = odin_command(dev, 0x66, 0x00, &[], 15)?;
    odin_fail_check(&rsp, "RequestFileFlash", false)
}

/// Request a sequence flash (0x66/0x02) with an aligned size.
fn request_sequence_flash(dev: &Device, aligned_size: u32) -> OdinResult<()> {
    let rsp = odin_command(dev, 0x66, 0x02, &aligned_size.to_le_bytes(), 15)?;
    odin_fail_check(&rsp, "RequestSequenceFlash", false)
}

/// Send one file chunk and wait for the ack with the expected index (0x66 data).
fn send_file_part(dev: &Device, data: &[u8], expected_index: u32, timeout: u64) -> OdinResult<()> {
    dev.send_raw(data)?;
    let rsp = dev.recv_raw(512, timeout)?;
    if rsp.len() < 8 {
        return err("short file-part ack");
    }
    let rid = u32::from_le_bytes([rsp[0], rsp[1], rsp[2], rsp[3]]);
    let ack = u32::from_le_bytes([rsp[4], rsp[5], rsp[6], rsp[7]]);
    if rid == 0xFFFFFFFF || ack == 0xFFFFFFFF {
        return err("bootloader fail during file part");
    }
    if ack != expected_index {
        return err(format!(
            "file part index mismatch: expected {expected_index}, got {ack}"
        ));
    }
    Ok(())
}

/// End a sequence flash (0x66/0x03) with the partition metadata payload.
///
/// The payload carries two extra flags odin4 sends in bytes 24-31 that the
/// docs omit: `efs_clear` and `boot_update`. `boot_update` tells LK this is a
/// bootloader/firmware update, which triggers regeneration of the `md5hdr`
/// secure-check hash table. Without it the partitions get written but LK keeps
/// failing them at boot with "Secure check fail :<partition>".
fn end_sequence_flash(
    dev: &Device,
    binary_type: u32,
    device_type: u32,
    identifier: u32,
    real_size: u32,
    is_last: u32,
    efs_clear: u32,
    boot_update: u32,
) -> OdinResult<()> {
    let mut payload = vec![0u8; 32];
    if binary_type == 1 {
        payload[0..4].copy_from_slice(&1u32.to_le_bytes());
        payload[4..8].copy_from_slice(&real_size.to_le_bytes());
        payload[8..12].copy_from_slice(&binary_type.to_le_bytes());
        payload[12..16].copy_from_slice(&device_type.to_le_bytes());
        payload[16..20].copy_from_slice(&0u32.to_le_bytes());
        payload[20..24].copy_from_slice(&is_last.to_le_bytes());
    } else {
        payload[0..4].copy_from_slice(&0u32.to_le_bytes());
        payload[4..8].copy_from_slice(&real_size.to_le_bytes());
        payload[8..12].copy_from_slice(&binary_type.to_le_bytes());
        payload[12..16].copy_from_slice(&device_type.to_le_bytes());
        payload[16..20].copy_from_slice(&identifier.to_le_bytes());
        payload[20..24].copy_from_slice(&is_last.to_le_bytes());
        payload[24..28].copy_from_slice(&efs_clear.to_le_bytes());
        payload[28..32].copy_from_slice(&boot_update.to_le_bytes());
    }
    dev.send_raw(&[0u8; 0])?;
    let rsp = odin_command(dev, 0x66, 0x03, &payload, 120)?;
    odin_fail_check(&rsp, "EndSequenceFlash", true)?;
    // Drain any unexpected bytes after the empty transfer.
    let _ = dev.recv_raw(512, 1);
    Ok(())
}

/// Reset flash count (0x64/0x01).
fn reset_flash_count(dev: &Device) -> OdinResult<()> {
    let rsp = odin_command(dev, 0x64, 0x01, &[], 15)?;
    odin_fail_check(&rsp, "ResetFlashCount", false)
}

/// Send the PIT to the device in its own session (for testing).
pub fn odin_send_pit(target: &str, pit_file: &str) -> Result<String> {
    let pit = std::fs::read(pit_file).map_err(|e| format!("read pit: {e}"))?;
    let dev = open_device(target).map_err(|e| e.to_string())?;
    dev.handshake().map_err(|e| e.to_string())?;
    eprintln!("[pit] handshake ok");
    begin_session_v2(&dev).map_err(|e| e.to_string())?;
    eprintln!("[pit] session ok");
    send_pit(&dev, &pit, 15).map_err(|e| e.to_string())?;
    eprintln!("[pit] pit send ok, {} bytes", pit.len());
    if let Err(e) = end_session_v2(&dev) {
        eprintln!("[pit] end_session warning (non-fatal): {e}");
    }
    Ok(format!("{{\"sent\": {}}}", pit.len()))
}

/// Send the PIT to the device (RQT_PIT_SET flow) matching odin4:
/// 0x65/0x00 PIT_SET -> ack; 0x65/0x02 PIT_START(size) -> ack;
/// bulk-write PIT data -> 8-byte ack; 0x65/0x03 PIT_COMPLETE -> ack.
fn send_pit(dev: &Device, pit: &[u8], timeout: u64) -> OdinResult<()> {
    let rsp = odin_command(dev, 0x65, 0x00, &[], timeout)?;
    odin_fail_check(&rsp, "PitSet", false)?;
    let rsp = odin_command(dev, 0x65, 0x02, &(pit.len() as u32).to_le_bytes(), timeout)?;
    odin_fail_check(&rsp, "PitStart", false)?;
    dev.send_raw(pit)?;
    let rsp = dev.recv_raw(512, timeout)?;
    odin_fail_check(&rsp, "PitData", false)?;
    let rsp = odin_command(dev, 0x65, 0x03, &[], timeout)?;
    odin_fail_check(&rsp, "PitComplete", false)
}

/// End the session (0x67/0x00).
fn end_session_v2(dev: &Device) -> OdinResult<()> {
    let rsp = odin_command(dev, 0x67, 0x00, &[], 15)?;
    odin_fail_check(&rsp, "EndSession", false)
}

/// Reboot the device after a completed flash (0x67/0x01).
fn reboot_v2(dev: &Device) -> OdinResult<()> {
    let rsp = odin_command(dev, 0x67, 0x01, &[], 15)?;
    odin_fail_check(&rsp, "Reboot", false)
}

/// Find a PIT entry by partition name and return (binary_type, device_type, identifier).
fn find_pit_entry(
    pit: &[u8],
    name: &str,
) -> std::result::Result<(u32, u32, u32, u32, u32), String> {
    if pit.len() < 32 {
        return Err("PIT too small".into());
    }
    let entry_count = u32::from_le_bytes([pit[4], pit[5], pit[6], pit[7]]) as usize;
    // PIT layout (matches python/core/pit.py and the real A14M PIT):
    // 32-byte header (magic @0, count @4, model @8), then 132-byte entries.
    // Within an entry: binary_type@0, device_type@4, identifier@8, block_size@20,
    // block_count@24, partition name@32, flash_filename@64.
    for i in 0..entry_count {
        let off = 32 + i * 132;
        if off + 132 > pit.len() {
            break;
        }
        let entry = &pit[off..off + 132];
        let pname_bytes = &entry[32..64];
        let pname_end = pname_bytes.iter().position(|&b| b == 0).unwrap_or(32);
        let pname = String::from_utf8_lossy(&pname_bytes[..pname_end]).to_string();
        // Also match by the PIT flash_filename field (e.g. preloader.img
        // maps to the bootloader partition, lk-verified.img to lk).
        let fname_bytes = &entry[64..96];
        let fname_end = fname_bytes.iter().position(|&b| b == 0).unwrap_or(32);
        let fname = String::from_utf8_lossy(&fname_bytes[..fname_end]).to_string();
        if pname == name || fname == name {
            let binary_type = u32::from_le_bytes([entry[0], entry[1], entry[2], entry[3]]);
            let device_type = u32::from_le_bytes([entry[4], entry[5], entry[6], entry[7]]);
            let identifier = u32::from_le_bytes([entry[8], entry[9], entry[10], entry[11]]);
            let block_size = u32::from_le_bytes([entry[20], entry[21], entry[22], entry[23]]);
            let block_count = u32::from_le_bytes([entry[24], entry[25], entry[26], entry[27]]);
            return Ok((binary_type, device_type, identifier, block_size, block_count));
        }
    }
    Err(format!("partition '{name}' not found in PIT"))
}

/// Flash one raw image to a partition. Assumes an active session (begin already
/// done); does request_file_flash + sequences + reset_flash_count, matching
/// odin4's per-partition behavior. Returns number of sequences sent.
fn flash_one_partition(
    dev: &Device,
    pit: &[u8],
    partition: &str,
    image_file: &str,
    packet_size: u32,
    large: bool,
) -> std::result::Result<u32, String> {
    let (binary_type, device_type, identifier, _block_size, _block_count) =
        find_pit_entry(pit, partition).map_err(|e| e.to_string())?;

    let total = std::fs::metadata(image_file)
        .map_err(|e| format!("stat image: {e}"))?
        .len() as usize;
    eprintln!("[flash] {partition}: {total} bytes, binary_type={binary_type} ident={identifier}");

    request_file_flash(dev).map_err(|e| e.to_string())?;

    let mut file = std::fs::File::open(image_file).map_err(|e| format!("open image: {e}"))?;
    let mut buf = vec![0u8; packet_size as usize];

    // Sequence geometry matching odin4: up to 30 sequences of packet_size
    // (modern) or 240 (legacy); each sequence is a set of packet_size chunks,
    // and each chunk is acknowledged individually by the bootloader.
    let mut sent = 0usize;
    let mut sequence = 0u32;

    let sequence_count = 30;
    let max_seq_bytes = packet_size as usize * sequence_count;
    while sent < total {
        let remaining = total - sent;
        let real_size = remaining.min(max_seq_bytes);
        let aligned =
            (real_size + packet_size as usize - 1) / packet_size as usize * packet_size as usize;
        eprintln!("[flash]   seq {sequence}: real={real_size} aligned={aligned} ({sent}/{total})");
        request_sequence_flash(dev, aligned as u32).map_err(|e| e.to_string())?;

        let mut index = 0u32;
        let parts = aligned / packet_size as usize;
        for _p in 0..parts {
            buf[..packet_size as usize].fill(0);
            use std::io::Read;
            let mut got = 0usize;
            while got < packet_size as usize {
                let n = file
                    .read(&mut buf[got..packet_size as usize])
                    .map_err(|e| format!("read image: {e}"))?;
                if n == 0 {
                    break;
                }
                got += n;
            }
            send_file_part(dev, &buf, index, 120).map_err(|e| e.to_string())?;
            index += 1;
        }

        let is_last = if sent + real_size >= total { 1 } else { 0 };
        let mut final_size = real_size;
        if is_last == 1 && large {
            // Large partitions (super/system/userdata) get the last real_size
            // padded to a 512-byte boundary, matching odin4.
            let rem = final_size % 512;
            if rem != 0 {
                final_size += 512 - rem;
            }
        }
        end_sequence_flash(
            dev,
            binary_type,
            device_type,
            identifier,
            final_size as u32,
            is_last,
            0,
            1,
        )
        .map_err(|e| e.to_string())?;
        sent += real_size;
        sequence += 1;
    }

    reset_flash_count(dev).map_err(|e| e.to_string())?;
    eprintln!("[flash] {partition}: done, {sequence} sequences, {sent} bytes");
    Ok(sequence)
}

/// Flash a single raw image to a named partition in its own session.
pub fn odin_flash_partition(
    target: &str,
    pit_file: &str,
    partition: &str,
    image_file: &str,
) -> Result<String> {
    let pit = std::fs::read(pit_file).map_err(|e| format!("read pit: {e}"))?;
    let total = std::fs::metadata(image_file)
        .map_err(|e| format!("stat image: {e}"))?
        .len() as usize;

    let dev = open_device(target).map_err(|e| e.to_string())?;
    dev.handshake().map_err(|e| e.to_string())?;
    eprintln!("[flash] handshake ok");
    let packet_size = begin_session_v2(&dev).map_err(|e| e.to_string())?;
    eprintln!("[flash] session ok, packet_size={packet_size}");

    set_total_bytes(&dev, total as u64).map_err(|e| e.to_string())?;
    let is_large = matches!(partition, "super" | "system" | "userdata");
    let sequences =
        flash_one_partition(&dev, &pit, partition, image_file, packet_size, is_large)
            .map_err(|e| e.to_string())?;

    if let Err(e) = end_session_v2(&dev) {
        // EndSession (0x67/0x00) can return BOOTLOADER_FAIL on some devices
        // after the partition data was fully written and acknowledged. It is
        // teardown only; treat as non-fatal unless ODIN_STRICT=1.
        if strict_mode() {
            return Err(format!("end_session failed under ODIN_STRICT=1: {e}").into());
        }
        eprintln!("[flash] end_session warning (non-fatal): {e}");
    }
    eprintln!("[flash] end_session ok");

    Ok(serde_json::json!({
        "partition": partition,
        "bytes": total,
        "sequences": sequences,
        "packet_size": packet_size,
    })
    .to_string())
}

/// Flash multiple raw images (partition=file pairs) in ONE session, then
/// end the session and reboot. Mirrors odin4's multi-archive flow:
/// begin -> send_pit (optional) -> total_bytes(sum of all) -> flash each -> end -> reboot.
pub fn odin_flash_multi(
    target: &str,
    pit_file: &str,
    files: &[(&str, &str)],
    reboot: bool,
) -> Result<String> {
    let pit = std::fs::read(pit_file).map_err(|e| format!("read pit: {e}"))?;

    let mut total_bytes = 0u64;
    for (partition, image_file) in files {
        let sz = std::fs::metadata(image_file)
            .map_err(|e| format!("stat {partition} ({image_file}): {e}"))?
            .len();
        total_bytes += sz;
    }

    let dev = open_device(target).map_err(|e| e.to_string())?;
    dev.handshake().map_err(|e| e.to_string())?;
    eprintln!("[flash] handshake ok");
    let packet_size = begin_session_v2(&dev).map_err(|e| e.to_string())?;
    eprintln!("[flash] session ok, packet_size={packet_size}");

    // NOTE: the reference odin4 never sends a PIT to the device during a
    // firmware flash - it only *reads* the device's own PIT to learn partition
    // geometry. Pushing an external PIT here makes the DA flag the session
    // ("PitComplete: bootloader fail"), which prevents a clean hash-table
    // rebuild. The local PIT is used only for partition lookups below.

    set_total_bytes(&dev, total_bytes).map_err(|e| e.to_string())?;
    eprintln!("[flash] set_total_bytes ok ({total_bytes} bytes total)");

    let mut results = Vec::new();
    for (partition, image_file) in files {
        let is_large = matches!(*partition, "super" | "system" | "userdata");
        let sequences =
            flash_one_partition(&dev, &pit, partition, image_file, packet_size, is_large)
                .map_err(|e| e.to_string())?;
        results.push((partition.to_string(), sequences));
    }

    if let Err(e) = end_session_v2(&dev) {
        // On some devices end_session (0x67/0x00) returns BOOTLOADER_FAIL even
        // after all partition data was written and acknowledged. It is session
        // teardown only; the data is already committed. Under ODIN_STRICT this
        // is treated as fatal rather than silently tolerated.
        if strict_mode() {
            return Err(format!("end_session failed under ODIN_STRICT=1: {e}").into());
        }
        eprintln!("[flash] end_session warning (non-fatal): {e}");
    }
    if reboot {
        if let Err(e) = reboot_v2(&dev) {
            if strict_mode() {
                return Err(format!("reboot command failed under ODIN_STRICT=1: {e}").into());
            }
            eprintln!("[flash] reboot command warning: {e}");
        } else {
            eprintln!("[flash] reboot command sent");
        }
    }

    Ok(serde_json::json!({
        "partitions": results.iter().map(|(p, s)| json!({"partition": p, "sequences": s})).collect::<Vec<_>>(),
        "total_bytes": total_bytes,
        "reboot": reboot,
    })
    .to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_pit(entries: usize) -> Vec<u8> {
        let mut pit = vec![0u8; 32];
        pit[0..4].copy_from_slice(&0x12349876u32.to_le_bytes());
        pit[4..8].copy_from_slice(&(entries as u32).to_le_bytes());
        for i in 0..entries {
            let mut e = vec![0u8; 132];
            e[0..4].copy_from_slice(&1u32.to_le_bytes()); // binary_type
            e[4..8].copy_from_slice(&0x50u32.to_le_bytes()); // device_type
            e[8..12].copy_from_slice(&(i as u32).to_le_bytes()); // identifier
            e[20..24].copy_from_slice(&512u32.to_le_bytes()); // block_size
            e[24..28].copy_from_slice(&8u32.to_le_bytes()); // block_count
            let name = format!("partition{i}");
            e[32..32 + name.len()].copy_from_slice(name.as_bytes());
            let fname = format!("{i}.img");
            e[64..64 + fname.len()].copy_from_slice(fname.as_bytes());
            pit.extend_from_slice(&e);
        }
        pit
    }

    #[test]
    fn find_pit_entry_matches_by_name() {
        let pit = make_pit(4);
        let (bt, dt, id, bs, bc) = find_pit_entry(&pit, "partition2").unwrap();
        assert_eq!((bt, dt, id, bs, bc), (1, 0x50, 2, 512, 8));
    }

    #[test]
    fn find_pit_entry_matches_by_flash_filename() {
        let pit = make_pit(2);
        let (_, _, id, _, _) = find_pit_entry(&pit, "1.img").unwrap();
        assert_eq!(id, 1);
    }

    #[test]
    fn find_pit_entry_missing_partition_errors() {
        let pit = make_pit(2);
        assert!(find_pit_entry(&pit, "nope").is_err());
        assert!(find_pit_entry(&pit, "").is_err());
    }

    #[test]
    fn find_pit_entry_rejects_truncated_pit() {
        let pit = make_pit(2);
        assert!(find_pit_entry(&pit[..20], "partition0").is_err());
    }

    #[test]
    fn find_pit_entry_real_a14m_pit() {
        // Regression test against the real firmware PIT in the repo: the first
        // entry must resolve to binary_type=2, device_type=0x50, identifier=2
        // (the old offset code read these 4 bytes early and got zeros).
        let path = concat!(env!("CARGO_MANIFEST_DIR"), "/pit/A14M_MEA_OPEN.pit");
        let pit = std::fs::read(path).expect("real PIT present");
        let (bt, dt, id, _, _) = find_pit_entry(&pit, "bootloader").unwrap();
        assert_eq!((bt, dt, id), (2, 0x50, 2));
        // flash_filename fallback lookup also resolves.
        let (bt2, _, id2, _, _) = find_pit_entry(&pit, "preloader.img").unwrap();
        assert_eq!((bt2, id2), (2, 2));
    }

    #[test]
    fn fail_check_accepts_clean_ack() {
        let rsp = [0x64u8, 0, 0, 0, 0, 0, 0, 0];
        assert!(odin_fail_check(&rsp, "test", false).is_ok());
    }

    #[test]
    fn fail_check_rejects_bootloader_fail() {
        let rsp = [0xffu8, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff];
        assert!(odin_fail_check(&rsp, "test", false).is_err());
    }

    #[test]
    fn fail_check_progress_tolerated_only_in_lenient_mode() {
        let rsp = [0xffu8, 0xff, 0xff, 0xff, 0xfb, 0xff, 0xff, 0xff]; // ack = -5 (Auth)
        std::env::remove_var("ODIN_STRICT");
        assert!(odin_fail_check(&rsp, "test", true).is_ok());
        std::env::set_var("ODIN_STRICT", "1");
        assert!(odin_fail_check(&rsp, "test", true).is_err());
        std::env::remove_var("ODIN_STRICT");
    }
}
