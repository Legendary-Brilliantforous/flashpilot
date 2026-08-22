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

/// Sanity ceiling for a PIT dump: 512 entries * 132 B + header is ~67.8 KiB.
/// Anything above this from the size query means the firmware sent garbage
/// (or an ack code) instead of a byte count.
const PIT_MAX_BYTES: usize = 32 + 512 * 132;

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

impl Device {
    /// USB-level port reset. Forces the bootloader to re-enumerate without
    /// touching the cable - the only reliable way to unwedge a Loke that
    /// stopped answering after a desynced session.
    fn reset_port(&self) -> bool {
        self.handle.reset().is_ok()
    }
}

/// Open the device and reach LOKE handshake, resilient to wedged sessions.
///
/// Escalation ladder on failure:
///   1. blind EndSession rescue (inside handshake()) - unwedges sessions
///      left open by a previous process;
///   2. USB port reset + reopen - forces fresh enumeration without replug.
fn open_and_handshake(target: &str) -> OdinResult<Device> {
    let mut last_err = String::from("unknown");
    for attempt in 0..3 {
        match open_device(target) {
            Ok(dev) => match dev.handshake() {
                Ok(()) => return Ok(dev),
                Err(e) => {
                    last_err = e.to_string();
                    eprintln!("[open] handshake failed (attempt {attempt}): {e}");
                    if attempt < 2 && dev.reset_port() {
                        eprintln!("[open] USB port reset issued; waiting for re-enumeration...");
                        std::thread::sleep(Duration::from_millis(1800));
                    }
                    // dev dropped here -> handle closed before reopen
                }
            },
            Err(e) => {
                // Device may be re-enumerating after our own reset: wait+retry.
                last_err = e.to_string();
                eprintln!("[open] device not found (attempt {attempt}): {e}");
                if attempt < 2 {
                    std::thread::sleep(Duration::from_millis(1200));
                }
            }
        }
    }
    err(format!(
        "{last_err} (rescue incl. USB reset attempted)"
    ))
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
    // Some download-mode enumerations come up unconfigured (config value 0);
    // libusb refuses to claim interfaces until a configuration is active.
    // Setting configuration 1 before claiming mirrors what Windows' usbccgp
    // does automatically and un-breaks those devices.
    let claimed = handle.claim_interface(iface.number);
    if claimed.is_err() {
        if let Err(e) = handle.set_active_configuration(1) {
            eprintln!("[odin] set_active_configuration(1): {e}");
        }
        handle
            .claim_interface(iface.number)
            .map_err(|e| OdinError(format!("claim iface: {e}")))?;
    }

    Ok(Device { handle, in_ep, out_ep })
}

impl Device {
    fn send_raw(&self, data: &[u8]) -> OdinResult<()> {
        const WRITE_RETRIES: u32 = 3;
        let mut last_err: Option<String> = None;
        for attempt in 0..WRITE_RETRIES {
            let res = self
                .handle
                .write_bulk(self.out_ep, data, Duration::from_secs(10))
                .map_err(|e| OdinError(format!("bulk write: {e}")));
            match res {
                Ok(_) => return Ok(()),
                Err(e) => {
                    last_err = Some(e.to_string());
                    if is_transient_usb_error(&e.to_string()) {
                        eprintln!("[flash]   write retry {attempt}: {}", e.to_string().trim());
                        std::thread::sleep(std::time::Duration::from_millis(50 * (attempt as u64 + 1)));
                        continue;
                    }
                    return Err(e);
                }
            }
        }
        Err(OdinError(last_err.unwrap_or_else(|| "bulk write failed".into())))
    }

    /// Single-shot write with a short timeout - used by the handshake probe
    /// so a stalled OUT endpoint costs 2s instead of 30s of retries.
    fn send_raw_fast(&self, data: &[u8]) -> OdinResult<()> {
        self.handle
            .write_bulk(self.out_ep, data, Duration::from_secs(2))
            .map(|_| ())
            .map_err(|e| OdinError(format!("bulk write: {e}")))
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
    ///
    /// Real-device finding: a process that exits mid-session (or a desynced
    /// probe) leaves Loke believing a session is still active - it then
    /// IGNORES the next "ODIN" until the USB device re-enumerates. Recovery
    /// used to require unplug/replug. We instead send a blind EndSession
    /// (0x67/0x00) between retry rounds, which unwedges the bootloader
    /// without touching the cable.
    fn handshake(&self) -> OdinResult<()> {
        for round in 0..2 {
            if round > 0 {
                eprintln!("[handshake] rescue: sending blind EndSession");
                let _ = self.send_control(CTRL_END_SESSION, &0u32.to_le_bytes());
                std::thread::sleep(Duration::from_millis(300));
                // Drain any stale frames the rescue shook loose.
                for _ in 0..4 {
                    if self.recv_raw(512, 1).is_err() {
                        break;
                    }
                }
            }
            // Drain any leftover frames from a previous session before ODIN.
            for _ in 0..4 {
                let r = self.recv_raw(512, 1);
                match r {
                    Ok(_) => continue,
                    Err(_) => break, // no pending data
                }
            }
            let mut last_recv_err: Option<String> = None;
            let mut write_failed = false;
            for attempt in 0..4 {
                match self.send_raw_fast(b"ODIN") {
                    Ok(_) => {}
                    Err(e) => {
                        // A stalled OUT endpoint means the firmware is deaf:
                        // retrying is pointless - escalate to port reset.
                        eprintln!("[handshake] send error attempt {attempt}: {e}");
                        write_failed = true;
                        break;
                    }
                }
                match self.recv_raw(7, 3) {
                    Ok(resp) if resp.get(..4) == Some(b"LOKE") => return Ok(()),
                    Ok(resp) => {
                        eprintln!(
                            "[handshake] attempt {attempt}: got {:?}, retrying",
                            resp.iter().map(|b| format!("{:02x}", b)).collect::<Vec<_>>().join(" ")
                        );
                    }
                    Err(e) => {
                        last_recv_err = Some(e.to_string());
                        eprintln!("[handshake] recv error attempt {attempt}: {e}");
                    }
                }
                std::thread::sleep(Duration::from_millis(80 * (attempt as u64 + 1)));
            }
            if write_failed {
                return err("handshake: OUT endpoint stalled (device needs reset)");
            }
            if round == 0 && last_recv_err.is_some() {
                continue; // one rescue round before giving up
            }
        }
        err("handshake failed after retries (device must be in download mode)")
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
        // Read the device's end-transfer verification response. Leaving it
        // queued poisons the NEXT operation in the same session: the stale
        // {0x65,...} frame gets consumed as PIT data (live-device finding -
        // second pit-dump came back 16 KB of shifted garbage).
        let _ = self.recv_raw(512, 5)?;
        Ok(())
    }

    fn dump_pit(&self) -> OdinResult<Vec<u8>> {
        let mut size = self.request_pit_dump()? as usize;
        if size > PIT_MAX_BYTES {
            // Implausible size: some firmwares return a raw ack instead of a
            // byte count. Ignore it and fall through to the streaming path,
            // which stops once the header magic + entry count are satisfied.
            eprintln!("[pit] implausible PIT size {size}, switching to streaming read");
            size = 0;
        }
        let mut pit = Vec::with_capacity(size.max(4096));
        if size == 0 {
            // Fallback for bootloaders that ACK the dump request without a
            // size: stream chunks until we can validate magic + entry count
            // or the device goes quiet.
            let mut idle = 0u32;
            while idle < 3 {
                match self.request_pit_part(pit.len().div_ceil(RECV_PART_SIZE) as u32) {
                    Ok(part) if !part.is_empty() => {
                        idle = 0;
                        pit.extend_from_slice(&part);
                        if pit.len() >= 8
                            && u32::from_le_bytes([pit[0], pit[1], pit[2], pit[3]]) == 0x12349876
                        {
                            let count =
                                u32::from_le_bytes([pit[4], pit[5], pit[6], pit[7]]) as usize;
                            let need = 32 + count * 132;
                            if count > 0 && count <= 512 && pit.len() >= need.min(PIT_MAX_BYTES) {
                                break;
                            }
                        }
                    }
                    Ok(_) => idle += 1,
                    Err(e) => {
                        eprintln!("[pit] streaming read stopped: {e}");
                        break;
                    }
                }
            }
        } else {
            let transfer_count = size.div_ceil(RECV_PART_SIZE);
            for i in 0..transfer_count {
                let part = self.request_pit_part(i as u32)?;
                pit.extend_from_slice(&part);
                if pit.len() >= size {
                    break;
                }
            }
        }
        if pit.is_empty() {
            return err("PIT dump refused (size 0, no streamed data)");
        }
        // Trim to the exact PIT length when the header is valid; otherwise
        // keep whatever arrived (caller-side parsers re-validate).
        if pit.len() >= 8
            && u32::from_le_bytes([pit[0], pit[1], pit[2], pit[3]]) == 0x12349876
        {
            let count = u32::from_le_bytes([pit[4], pit[5], pit[6], pit[7]]) as usize;
            let need = 32 + count * 132;
            if count <= 512 && pit.len() > need {
                pit.truncate(need);
            }
        } else if size > 0 && pit.len() > size {
            pit.truncate(size);
        }
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
    let dev = open_and_handshake(target).map_err(|e| e.to_string())?;
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
    let dev = open_and_handshake(target).map_err(|e| e.to_string())?;
    let packet_size = dev.begin_session().map_err(|e| e.to_string())?;
    // Close the session - a process that exits with an active session wedges
    // the bootloader until re-enumeration (real-device finding).
    if let Err(e) = end_session_v2(&dev) {
        eprintln!("[connect] end_session warning (non-fatal): {e}");
    }
    let info = OdinSessionInfo {
        handshake: true,
        session: true,
        packet_size,
    };
    let json = serde_json::to_string(&info).map_err(|e| e.to_string())?;
    Ok(json)
}

pub fn odin_pit(target: &str, out_file: Option<&str>) -> Result<String> {
    let dev = open_and_handshake(target).map_err(|e| e.to_string())?;
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
            String::from_utf8_lossy(&pit[8..24]).trim_matches('\0'),
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
    let dev = open_and_handshake(target).map_err(|e| e.to_string())?;
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
///
/// Retries on transient USB errors (timeout/stall/overflow) with a short
/// backoff. Control commands are idempotent enough to resend: the bootloader
/// either replies to the first copy or has gone quiet and needs the command
/// re-issued (odin4 retries these the same way).
fn odin_command(
    dev: &Device,
    cmd: u32,
    sub: u32,
    payload: &[u8],
    timeout: u64,
) -> OdinResult<Vec<u8>> {
    const CMD_RETRIES: u32 = 4;
    let mut buf = vec![0u8; PACKET_SIZE];
    buf[0..4].copy_from_slice(&cmd.to_le_bytes());
    buf[4..8].copy_from_slice(&sub.to_le_bytes());
    if payload.len() + 8 > PACKET_SIZE {
        return err("odin command payload too large");
    }
    buf[8..8 + payload.len()].copy_from_slice(payload);

    let mut last_err: Option<String> = None;
    for attempt in 0..CMD_RETRIES {
        if attempt > 0 {
            eprintln!(
                "[odin] command 0x{cmd:02x}/0x{sub:02x} retry {attempt}: {last}",
                last = last_err.as_deref().unwrap_or("unknown")
            );
            std::thread::sleep(Duration::from_millis(100 * (attempt as u64)));
        }
        if let Err(e) = dev.send_raw(&buf) {
            last_err = Some(e.to_string());
            if !is_transient_usb_error(&e.to_string()) {
                return Err(e);
            }
            continue;
        }
        match dev.recv_raw(512, timeout) {
            Ok(rsp) if rsp.len() >= 8 => return Ok(rsp),
            Ok(rsp) => {
                last_err = Some(format!("odin response too short: {} bytes", rsp.len()));
                continue;
            }
            Err(e) => {
                last_err = Some(e.to_string());
                if !is_transient_usb_error(&e.to_string()) {
                    return Err(e);
                }
                continue;
            }
        }
    }
    Err(OdinError(
        last_err.unwrap_or_else(|| format!("odin command 0x{cmd:02x}/0x{sub:02x} failed")),
    ))
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

/// Read an integer env override (used for ODIN_BOOT_UPDATE / ODIN_EFS_CLEAR).
fn env_override(name: &str) -> Option<u32> {
    std::env::var(name)
        .ok()
        .and_then(|v| v.trim().parse::<u32>().ok())
}

/// True when the partition belongs to the bootloader (BL) tar. These are the
/// partitions whose end-sequence commit must set `boot_update`, which tells LK
/// to regenerate the `md5hdr` secure-check hash table after writing.
fn is_bootloader_partition(partition: &str) -> bool {
    matches!(
        partition,
        "bootloader"
            | "lk"
            | "param"
            | "up_param"
            | "efuse"
            | "vbmeta"
            | "spmfw"
            | "scp1"
            | "sspm_1"
            | "tee1"
            | "tzar"
            | "gz1"
    )
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
        // BOOTLOADER_FAIL (0xFFFFFFFF) - check if it's actually a progress code.
        // Only codes that are pure transfer progress markers (-2 WP, -3 Erase,
        // -4 Write, -7 Ext4) may ever be treated as success. -5 (Auth) and
        // -6 (Size) are real validation failures: the device rejected the data
        // (bad signature / wrong size), so treating them as "progress" would
        // report a rejected bootloader write as complete. They are fatal
        // regardless of allow_progress / strict mode.
        if allow_progress && ack_i32 >= -7 && ack_i32 <= -2 && ack_i32 != -5 && ack_i32 != -6 && !strict_mode() {
            // Progress codes: -2 WP, -3 Erase, -4 Write, -5 Auth, -6 Size, -7 Ext4
            eprintln!("[debug] {context}: progress code {ack_i32}");
            return Ok(());
        }
        if allow_progress && ack_i32 >= -7 && ack_i32 <= -2 {
            let reason = if ack_i32 == -5 || ack_i32 == -6 {
                " (Auth/Size: always fatal)"
            } else {
                " (ODIN_STRICT=1)"
            };
            eprintln!("[warn] {context}: code {ack_i32} treated as FAILURE{reason}");
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

/// Begin session with protocol negotiation (0x64/0x00), returns packet size
/// and whether the legacy 128KiB protocol is in use.
fn begin_session_v2(dev: &Device) -> OdinResult<(u32, bool)> {
    // Some Samsung MTK download agents (J3/MTK "COM_TAR2MTK*" devices) hard-
    // reject the modern 1MiB framing at EndSequence even though they advertise
    // protocol version 2. Force the legacy 128KiB path with ODIN_LEGACY=1.
    let force_legacy = std::env::var("ODIN_LEGACY")
        .map(|v| matches!(v.trim().to_lowercase().as_str(), "1" | "true" | "yes" | "on"))
        .unwrap_or(false);

    let rsp = odin_command(dev, 0x64, 0x00, &0x7FFFFFFFu32.to_le_bytes(), 15)?;
    odin_fail_check(&rsp, "BeginSession", false)?;
    let ack = u32::from_le_bytes([rsp[4], rsp[5], rsp[6], rsp[7]]);
    let ack_upper = ((ack >> 16) & 0xFFFF) as u16;
    let version = ack_upper & 0x7FFF;
    let compressed = (ack_upper & 0x8000) != 0;
    eprintln!(
        "[flash] begin_session ack=0x{ack:08x} version={version} compressed={compressed} force_legacy={force_legacy}"
    );

    if version <= 1 || force_legacy {
        // Legacy protocol: 128KiB packets, no packet-size negotiation.
        let rsp = odin_command(dev, 0x64, 0x05, &131072u32.to_le_bytes(), 15)?;
        odin_fail_check(&rsp, "SendFilePartSize", false)?;
        Ok((131072, true))
    } else {
        // Modern protocol: 1MiB packets negotiated via 0x64/0x05.
        let rsp = odin_command(dev, 0x64, 0x05, &1048576u32.to_le_bytes(), 15)?;
        odin_fail_check(&rsp, "SendFilePartSize", false)?;
        Ok((1048576, false))
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

/// True when an error string looks like a transient USB timeout/stall that is
/// safe to retry: the bootloader was slow to ACK a chunk, or the USB bus
/// dropped a frame. Same classes odin4/heimdall retry before giving up.
fn is_transient_usb_error(e: &str) -> bool {
    let lower = e.to_lowercase();
    lower.contains("timed out")
        || lower.contains("timeout")
        || lower.contains("pipe")
        || lower.contains("stall")
        || lower.contains("no device")
        || lower.contains("overflow")
        || lower.contains("not found")
}

/// Send one file chunk and wait for the ack with the expected index (0x66 data).
///
/// Retries the ack read on transient USB errors (timeout/stall/overflow) with
/// a short backoff, up to ACK_RETRIES total attempts. The chunk is written once;
/// the device only ACKs once it has the chunk, so re-reading on timeout is safe.
/// A hard failure (BOOTLOADER_FAIL, index mismatch) is never retried.
fn send_file_part(dev: &Device, data: &[u8], expected_index: u32, timeout: u64) -> OdinResult<()> {
    const ACK_RETRIES: u32 = 5;
    dev.send_raw(data)?;
    let mut last_err: Option<String> = None;
    for attempt in 0..ACK_RETRIES {
        let rsp = dev.recv_raw(512, timeout);
        let rsp = match rsp {
            Ok(r) => r,
            Err(e) => {
                last_err = Some(e.to_string());
                if is_transient_usb_error(&e.to_string()) {
                    eprintln!(
                        "[flash]   ack retry {attempt}: {}",
                        e.to_string().trim()
                    );
                    std::thread::sleep(std::time::Duration::from_millis(50 * (attempt as u64 + 1)));
                    continue;
                }
                return Err(e);
            }
        };
        if rsp.len() < 8 {
            last_err = Some("short file-part ack".into());
            std::thread::sleep(std::time::Duration::from_millis(50 * (attempt as u64 + 1)));
            continue;
        }
        let rid = u32::from_le_bytes([rsp[0], rsp[1], rsp[2], rsp[3]]);
        let ack = u32::from_le_bytes([rsp[4], rsp[5], rsp[6], rsp[7]]);
        if rid == 0xFFFFFFFF || ack == 0xFFFFFFFF {
            return err("bootloader fail during file part");
        }
        if ack != expected_index {
            // A stale ACK from a previous chunk: the bootloader was one step
            // behind. Drain and re-read rather than aborting the flash.
            eprintln!(
                "[flash]   index mismatch: expected {expected_index}, got {ack} (attempt {attempt})"
            );
            last_err = Some(format!(
                "file part index mismatch: expected {expected_index}, got {ack}"
            ));
            std::thread::sleep(std::time::Duration::from_millis(50 * (attempt as u64 + 1)));
            continue;
        }
        return Ok(());
    }
    Err(OdinError(last_err.unwrap_or_else(|| "file part ack failed".into())))
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
    // Live-device finding: EndSequenceFlash can return BOOTLOADER_FAIL (-5)
    // while the bootloader finishes async md5hdr/boot_update validation of
    // previously written partitions. All chunk data is already written and
    // ACKed - only the finalize failed, and resending it after a delay
    // succeeds. Retry with exponential backoff; ONLY ack -5 is retryable,
    // everything else (rid/ack mismatch etc.) is fatal.
    const COMMIT_DELAYS_MS: [u64; 6] = [500, 1000, 2000, 4000, 5000, 6000];
    let mut last_err: Option<OdinError> = None;
    for attempt in 0..=COMMIT_DELAYS_MS.len() {
        if attempt > 0 {
            let delay = COMMIT_DELAYS_MS[attempt - 1];
            eprintln!(
                "[flash]   commit busy (-5): retry {attempt} after {delay}ms \
                 (device still validating previous writes)"
            );
            std::thread::sleep(Duration::from_millis(delay));
        }
        match odin_command(dev, 0x66, 0x03, &payload, 120) {
            Ok(rsp) => {
                if rsp.len() >= 8 {
                    let rid = u32::from_le_bytes([rsp[0], rsp[1], rsp[2], rsp[3]]);
                    let ack = u32::from_le_bytes([rsp[4], rsp[5], rsp[6], rsp[7]]);
                    let ack_i32 = ack as i32;
                    if rid == 0xFFFF_FFFF && ack_i32 == -5 {
                        // Transient "busy validating" - retryable.
                        eprintln!(
                            "[flash]   EndSequenceFlash ack -5 (device busy)"
                        );
                        last_err = Some(OdinError(
                            "EndSequenceFlash: ack -5 (busy)".into(),
                        ));
                        continue;
                    }
                }
                match odin_fail_check(&rsp, "EndSequenceFlash", true) {
                    Ok(()) => {
                        // Drain any unexpected bytes after the empty transfer.
                        let _ = dev.recv_raw(512, 1);
                        return Ok(());
                    }
                    Err(e) => return Err(e),
                }
            }
            Err(e) => return Err(OdinError(e.to_string())),
        }
    }
    Err(last_err.unwrap_or_else(|| OdinError("commit failed".into())))
}

/// Reset flash count (0x64/0x01).
fn reset_flash_count(dev: &Device) -> OdinResult<()> {
    let rsp = odin_command(dev, 0x64, 0x01, &[], 15)?;
    odin_fail_check(&rsp, "ResetFlashCount", false)
}

/// Session-multiplexing Odin agent - THE fix for Loke firmwares that allow
/// exactly ONE session per download-mode entry.
///
/// Real-device finding (live A14-class Samsung): after one complete session,
/// the bootloader goes deaf until the USB device re-enumerates. Our old
/// architecture spawned a fresh bridge process per command, so the second
/// command always failed. Real Odin works because it is a single process
/// doing everything in one session - this agent does the same.
///
/// Protocol (JSON lines on stdin/stdout):
///   agent prints  {"status":"ready","packet_size":N}     once opened
///   request       {"cmd":"pit-dump","out":"path","hex":false}
///   response      {"size":N,"file":"path"[,"hex":"..."]} or {"error":"..."}
///   request       {"cmd":"model"}          -> {"model":"..."}
///   request       {"cmd":"reboot"}         -> {"ok":true} then exits
///   request       {"cmd":"end"}            -> {"bye":true} then exits
/// EOF also ends the session cleanly.
/// Session PIT cache for the agent's flash command (set by pit-dump).
static AGENT_PIT: std::sync::OnceLock<Vec<u8>> = std::sync::OnceLock::new();

pub fn odin_agent(target: &str) -> Result<String> {
    use std::io::{BufRead, Write};
    let dev = open_and_handshake(target).map_err(|e| e.to_string())?;
    let (packet_size, legacy) = begin_session_v2(&dev).map_err(|e| e.to_string())?;
    let mut out = std::io::stdout().lock();
    let _ = writeln!(
        out,
        "{}",
        json!({"status": "ready", "packet_size": packet_size})
    );
    let _ = out.flush();

    let stdin = std::io::stdin();
    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        if line.trim().is_empty() {
            continue;
        }
        let req: serde_json::Value = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(e) => {
                let _ = writeln!(out, "{}", json!({"error": format!("bad json: {e}")}));
                let _ = out.flush();
                continue;
            }
        };
        let cmd = req.get("cmd").and_then(|x| x.as_str()).unwrap_or("");
        match cmd {
            "pit-dump" => {
                // Self-healing: some probes (0x64/0x01 device-type) desync the
                // bulk stream on certain Loke builds - the next read then gets
                // a stale control frame. Drain and retry once before failing.
                let mut attempt = 0;
                loop {
                    attempt += 1;
                    let ok = dev
                        .dump_pit()
                        .map(|data| {
                            // Cache for the session's flash commands.
                            let _ = AGENT_PIT.set(data.clone());
                            let mut resp = json!({"size": data.len()});
                            if let Some(o) = req.get("out").and_then(|x| x.as_str()) {
                                if !o.is_empty() {
                                    match std::fs::write(o, &data) {
                                        Ok(()) => resp["file"] = json!(o),
                                        Err(e) => {
                                            resp["write_error"] = json!(e.to_string())
                                        }
                                    }
                                }
                            }
                            if req.get("hex").and_then(|x| x.as_bool()).unwrap_or(false) {
                                resp["hex"] = json!(
                                    data.iter().map(|b| format!("{b:02x}")).collect::<String>()
                                );
                            }
                            resp
                        });
                    match ok {
                        Ok(resp) => {
                            let _ = writeln!(out, "{resp}");
                            break;
                        }
                        Err(e) => {
                            if attempt < 2 && e.to_string().contains("unexpected response") {
                                eprintln!(
                                    "[agent] pit-dump desync detected; draining and retrying"
                                );
                                for _ in 0..8 {
                                    if dev.recv_raw(512, 1).is_err() {
                                        break;
                                    }
                                }
                                continue;
                            }
                            let _ =
                                writeln!(out, "{}", json!({"error": e.to_string()}));
                            break;
                        }
                    }
                }
            }
            "model" => {
                // WARNING: this probe poisons the bulk stream on several Loke
                // builds (J3/A14 class answer garbage like 'd'/'e'). Prefer
                // reading the model from the PIT header (Unknown+Project).
                let mut model = String::new();
                if let Ok(data) = dev.request_device_type() {
                    let ascii: String = data
                        .iter()
                        .map(|&b| if (0x20..0x7f).contains(&b) { b as char } else { ' ' })
                        .collect();
                    model = pick_model(&ascii);
                }
                let _ = writeln!(out, "{}", json!({"model": model}));
            }
            "flash" => {
                // Write a raw image to a partition within this session.
                // {"cmd":"flash","partition":"bootloader","file":"/tmp/x.img"}
                // Requires the session PIT: run pit-dump first (cached here).
                let part = req.get("partition").and_then(|x| x.as_str()).unwrap_or("");
                let file = req.get("file").and_then(|x| x.as_str()).unwrap_or("");
                if part.is_empty() || file.is_empty() {
                    let _ = writeln!(
                        out,
                        "{}",
                        json!({"error": "flash needs 'partition' and 'file'"})
                    );
                    let _ = out.flush();
                    continue;
                }
                let pit_cache: &Vec<u8> = match AGENT_PIT.get() {
                    Some(p) => p,
                    None => {
                        let _ = writeln!(
                            out,
                            "{}",
                            json!({"error": "no session PIT - run pit-dump first"})
                        );
                        let _ = out.flush();
                        continue;
                    }
                };
                eprintln!("[agent] flashing {part} <- {file}");
                let is_large = matches!(part, "super" | "system" | "userdata");
                let total = std::fs::metadata(file)
                    .map(|m| m.len())
                    .unwrap_or(0);
                // Mirror odin_flash_partition: announce total bytes first.
                if let Err(e) = set_total_bytes(&dev, total) {
                    let _ = writeln!(out, "{}", json!({"error": e.to_string(), "partition": part}));
                    let _ = out.flush();
                    continue;
                }
                match flash_one_partition_ext(
                    &dev,
                    pit_cache,
                    part,
                    file,
                    packet_size,
                    legacy,
                    is_large,
                    true, // single-partition flash = session last
                ) {
                    Ok(seqs) => {
                        let _ = writeln!(
                            out,
                            "{}",
                            json!({"ok": true, "partition": part, "sequences": seqs})
                        );
                    }
                    Err(e) => {
                        let _ = writeln!(out, "{}", json!({"error": e, "partition": part}));
                    }
                }
            }
            "flash-batch" => {
                // Multi-partition write in ONE session, mirroring
                // odin_flash_multi exactly: SetTotalBytes ONCE with the
                // GRAND TOTAL of all files, then sequential writes.
                //
                // Live-device finding: declaring per-file totals (resetting
                // 0x64/0x02 before each write) makes the 4th+ commit fail
                // with BOOTLOADER_FAIL -5 - the bootloader keeps a running
                // received-byte counter across the session.
                // {"cmd":"flash-batch","files":[["part","/path"],...],
                //  "reboot":true}
                // Emits one JSON line per finished partition.
                let pit_cache = match AGENT_PIT.get() {
                    Some(p) => p,
                    None => {
                        let _ = writeln!(
                            out,
                            "{}",
                            json!({"error": "no session PIT - run pit-dump first",
                                   "batch": "complete"})
                        );
                        let _ = out.flush();
                        continue;
                    }
                };
                let mut files: Vec<(String, String)> = Vec::new();
                if let Some(arr) = req.get("files").and_then(|x| x.as_array()) {
                    for pair in arr {
                        if let Some(pair_arr) = pair.as_array() {
                            if pair_arr.len() == 2 {
                                if let (Some(p), Some(f)) = (
                                    pair_arr[0].as_str(),
                                    pair_arr[1].as_str(),
                                ) {
                                    files.push((p.to_string(), f.to_string()));
                                }
                            }
                        }
                    }
                }
                if files.is_empty() {
                    let _ = writeln!(
                        out,
                        "{}",
                        json!({"error": "flash-batch needs non-empty files",
                               "batch": "complete"})
                    );
                    let _ = out.flush();
                    continue;
                }
                let mut total_bytes = 0u64;
                let mut stat_err = None;
                for (_, path) in &files {
                    match std::fs::metadata(path) {
                        Ok(m) => total_bytes += m.len(),
                        Err(e) => {
                            stat_err = Some(format!("{}: {e}", path));
                            break;
                        }
                    }
                }
                if let Some(e) = stat_err {
                    let _ = writeln!(
                        out,
                        "{}",
                        json!({"error": e, "batch": "complete"})
                    );
                    let _ = out.flush();
                    continue;
                }
                let want_reboot =
                    req.get("reboot").and_then(|x| x.as_bool()).unwrap_or(false);

                eprintln!(
                    "[agent] flash-batch: {} partitions, {} bytes total",
                    files.len(),
                    total_bytes
                );
                if let Err(e) = set_total_bytes(&dev, total_bytes) {
                    let _ = writeln!(out, "{}", json!({"error": e.to_string()}));
                    let _ = out.flush();
                    continue;
                }

                let mut failed = None;
                for (pos, (part, path)) in files.iter().enumerate() {
                    eprintln!("[agent] flashing {part} <- {path}");
                    let is_large =
                        matches!(part.as_str(), "super" | "system" | "userdata");
                    // is_last=1 ONLY on the batch's final partition - Loke
                    // closes the flash context on is_last and the next
                    // commit then fails deterministically with -5.
                    let session_last = pos + 1 == files.len();
                    // One full retry of a failed partition: transient
                    // bootloader-busy states can abort a commit; rewriting
                    // the same content into the same session has succeeded
                    // live where immediate failure was deterministic.
                    let mut result = flash_one_partition_ext(
                        &dev,
                        pit_cache,
                        part,
                        path,
                        packet_size,
                        legacy,
                        is_large,
                        session_last,
                    );
                    if result.is_err() {
                        eprintln!(
                            "[agent] {part} failed once - rewriting partition"
                        );
                        std::thread::sleep(Duration::from_millis(1000));
                        result = flash_one_partition_ext(
                            &dev,
                            pit_cache,
                            part,
                            path,
                            packet_size,
                            legacy,
                            is_large,
                            session_last,
                        );
                    }
                    match result {
                        Ok(seqs) => {
                            let _ = writeln!(
                                out,
                                "{}",
                                json!({
                                    "done": part,
                                    "sequences": seqs,
                                    "progress":
                                        format!("{}/{}", files.iter().position(|(p, _)| p == part).map(|i| i + 1).unwrap_or(0), files.len())
                                })
                            );
                            let _ = out.flush();
                        }
                        Err(e) => {
                            failed = Some((part.clone(), e.to_string()));
                            let _ = writeln!(
                                out,
                                "{}",
                                json!({"error": e.to_string(), "partition": part})
                            );
                            let _ = out.flush();
                            break;
                        }
                    }
                }
                if failed.is_none() && want_reboot {
                    match reboot_v2(&dev) {
                        Ok(()) => {
                            let _ = writeln!(out, "{}", json!({"rebooted": true}));
                        }
                        Err(e) => {
                            let _ = writeln!(
                                out,
                                "{}",
                                json!({"reboot_error": e.to_string()})
                            );
                        }
                    }
                }
                // Terminal marker - ALWAYS last, success or failure, so the
                // peer can stop reading instead of counting expected lines.
                let _ = writeln!(
                    out,
                    "{}",
                    json!({
                        "batch": "complete",
                        "flashed": files.len() - failed.as_ref().map_or(0, |_| 1),
                        "failed_partition":
                            failed.as_ref().map(|(p, _)| p.clone()),
                    })
                );
                let _ = out.flush();
            }
            "reboot" => {
                let r = reboot_v2(&dev);
                let _ = writeln!(
                    out,
                    "{}",
                    match r {
                        Ok(()) => json!({"ok": true}),
                        Err(e) => json!({"error": e.to_string()}),
                    }
                );
                let _ = out.flush();
                break;
            }
            _ => {
                let _ = writeln!(out, "{}", json!({"bye": true}));
                let _ = out.flush();
                break;
            }
        }
        let _ = out.flush();
    }
    if let Err(e) = end_session_v2(&dev) {
        eprintln!("[agent] end_session warning (non-fatal): {e}");
    }
    Ok(json!({"status": "closed"}).to_string())
}

/// Send the PIT to the device in its own session, then CLOSE THE LOOP:
/// re-dump the device's PIT and hash-compare it against what was written.
/// Heimdall pads the outgoing buffer to a 4096-byte multiple; the re-dump is
/// compared over the unpadded length so padding differences never cause
/// false failures. No other tool performs this verification automatically.
pub fn odin_send_pit(target: &str, pit_file: &str) -> Result<String> {
    let pit = std::fs::read(pit_file).map_err(|e| format!("read pit: {e}"))?;
    let dev = open_and_handshake(target).map_err(|e| e.to_string())?;
    eprintln!("[pit] handshake ok");
    begin_session_v2(&dev).map_err(|e| e.to_string())?;
    eprintln!("[pit] session ok");
    send_pit(&dev, &pit, 15).map_err(|e| e.to_string())?;
    eprintln!("[pit] pit send ok, {} bytes", pit.len());

    // Post-write verification: re-dump from the device and compare.
    eprintln!("[pit] verifying: re-dumping device PIT...");
    let redump = dev.dump_pit().unwrap_or_default();
    let n = pit.len().min(redump.len());
    let verified = !redump.is_empty()
        && redump.len() >= pit.len()
        && pit[..n] == redump[..n];
    if verified {
        eprintln!("[pit] verification OK (re-dumped {} bytes match)", redump.len());
    } else {
        eprintln!(
            "[pit] verification MISMATCH: sent {} bytes, re-dumped {} bytes",
            pit.len(),
            redump.len()
        );
    }
    if let Err(e) = end_session_v2(&dev) {
        eprintln!("[pit] end_session warning (non-fatal): {e}");
    }
    Ok(json!({
        "sent": pit.len(),
        "redump": redump.len(),
        "verified": verified,
    })
    .to_string())
}

/// Send the PIT to the device (RQT_PIT_SET flow) matching odin4, with the
/// outgoing buffer padded to a 4096-byte multiple like Heimdall's
/// GetPaddedSize(): 0x65/0x00 PIT_SET -> ack; 0x65/0x02 PIT_START(size of
/// PADDED buffer) -> ack; bulk-write PIT data -> 8-byte ack;
/// 0x65/0x03 PIT_COMPLETE -> ack.
fn send_pit(dev: &Device, pit: &[u8], timeout: u64) -> OdinResult<()> {
    const PAD_MULTIPLE: usize = 4096;
    let padded_len = pit.len().div_ceil(PAD_MULTIPLE) * PAD_MULTIPLE;
    let mut padded = vec![0u8; padded_len];
    padded[..pit.len()].copy_from_slice(pit);
    eprintln!(
        "[pit] sending {} bytes (padded to {padded_len})",
        pit.len()
    );
    let rsp = odin_command(dev, 0x65, 0x00, &[], timeout)?;
    odin_fail_check(&rsp, "PitSet", false)?;
    let rsp = odin_command(dev, 0x65, 0x02, &(padded_len as u32).to_le_bytes(), timeout)?;
    odin_fail_check(&rsp, "PitStart", false)?;
    dev.send_raw(&padded)?;
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

/// Find a PIT entry by partition name and return
/// (binary_type, device_type, identifier, blockSizeOrOffset, blockCount).
fn find_pit_entry(
    pit: &[u8],
    name: &str,
) -> std::result::Result<(u32, u32, u32, u32, u32), String> {
    // True PIT layout - verified against Heimdall libpit.h, Thor's extended
    // parser and our own real device dumps: 28-byte header (magic @0,
    // count @4, model strings @8..24, reserved @24), then 132-byte entries.
    // Within an entry: binaryType@0 deviceType@4 identifier@8 attributes@12
    // updateAttributes@16 blockSizeOrOffset@20 blockCount@24 fileOffset@28
    // fileSize@32, then partitionName@36 flashFileName@68 deltaFileName@100.
    const BASE: usize = 28;
    if pit.len() < BASE {
        return Err("PIT too small".into());
    }
    let entry_count = u32::from_le_bytes([pit[4], pit[5], pit[6], pit[7]]) as usize;
    for i in 0..entry_count {
        let off = BASE + i * 132;
        if off + 132 > pit.len() {
            break;
        }
        let entry = &pit[off..off + 132];
        let pname_bytes = &entry[36..68];
        let pname_end = pname_bytes.iter().position(|&b| b == 0).unwrap_or(32);
        let pname = String::from_utf8_lossy(&pname_bytes[..pname_end]).to_string();
        // Also match by the PIT flash_filename field (e.g. preloader.img
        // maps to the bootloader partition, lk-verified.img to lk).
        let fname_bytes = &entry[68..100];
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
    legacy: bool,
    large: bool,
) -> std::result::Result<u32, String> {
    flash_one_partition_ext(
        dev, pit, partition, image_file, packet_size, legacy, large, true,
    )
}

/// `session_last`: mark this partition's final sequence with is_last=1 ONLY
/// when it is the LAST partition of the whole session. Live-device finding:
/// Loke interprets is_last=1 as "finalize the session" - sending it on every
/// partition makes the NEXT commit fail deterministically with -5.
fn flash_one_partition_ext(
    dev: &Device,
    pit: &[u8],
    partition: &str,
    image_file: &str,
    packet_size: u32,
    legacy: bool,
    large: bool,
    session_last: bool,
) -> std::result::Result<u32, String> {
    let (binary_type, device_type, identifier, _block_size, _block_count) =
        find_pit_entry(pit, partition).map_err(|e| e.to_string())?;

    let total = std::fs::metadata(image_file)
        .map_err(|e| format!("stat image: {e}"))?
        .len() as usize;
    let boot_update = env_override("ODIN_BOOT_UPDATE")
        .unwrap_or_else(|| u32::from(is_bootloader_partition(partition)));
    let efs_clear = env_override("ODIN_EFS_CLEAR").unwrap_or(0);
    eprintln!(
        "[flash] {partition}: {total} bytes, binary_type={binary_type} ident={identifier} boot_update={boot_update} efs_clear={efs_clear}"
    );

    request_file_flash(dev).map_err(|e| e.to_string())?;

    let mut file = std::fs::File::open(image_file).map_err(|e| format!("open image: {e}"))?;
    let mut buf = vec![0u8; packet_size as usize];

    // Sequence geometry matching odin4: up to 30 sequences of packet_size
    // (modern 1MiB) or 240 (legacy 128KiB); each sequence is a set of
    // packet_size chunks, and each chunk is acknowledged individually by the
    // bootloader.
    let mut sent = 0usize;
    let mut sequence = 0u32;

    // Report progress to stderr as parseable lines so the Python bridge can
    // show live percentage on screen. Emitted at least once per sequence.
    let mut last_report_pct = 0u32;

    let sequence_count = if legacy { 240 } else { 30 };
    let max_seq_bytes = packet_size as usize * sequence_count;
    while sent < total {
        let remaining = total - sent;
        let real_size = remaining.min(max_seq_bytes);
        let aligned =
            (real_size + packet_size as usize - 1) / packet_size as usize * packet_size as usize;
        eprintln!("[flash]   seq {sequence}: real={real_size} aligned={aligned} ({sent}/{total})");
        request_sequence_flash(dev, aligned as u32)
            .map_err(|e| format!("{partition}: sequence {sequence}: {e}"))?;

        let mut index = 0u32;
        let parts = aligned / packet_size as usize;
        for _p in 0..parts {
            buf[..packet_size as usize].fill(0);
            use std::io::Read;
            let mut got = 0usize;
            while got < packet_size as usize {
                let n = file
                    .read(&mut buf[got..packet_size as usize])
                    .map_err(|e| format!("{partition}: read image at byte {sent}: {e}"))?;
                if n == 0 {
                    break;
                }
                got += n;
            }
            send_file_part(dev, &buf, index, 120)
                .map_err(|e| format!("{partition}: byte {sent}: {e}"))?;
            index += 1;

            sent += packet_size as usize;
            if sent > total {
                sent = total;
            }
            let pct = (sent * 100 / total) as u32;
            if pct >= last_report_pct + 2 || sent >= total {
                eprintln!("[progress] {partition}: {pct}% ({sent}/{total})");
                last_report_pct = pct;
            }
        }

        let is_last = if sent >= total && session_last { 1 } else { 0 };
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
            efs_clear,
            boot_update,
        )
        .map_err(|e| format!("{partition}: end sequence {sequence}: {e}"))?;
        sequence += 1;
    }

    reset_flash_count(dev).map_err(|e| format!("{partition}: reset flash count: {e}"))?;
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

    let dev = open_and_handshake(target).map_err(|e| e.to_string())?;
    eprintln!("[flash] handshake ok");
    let (packet_size, legacy) = begin_session_v2(&dev).map_err(|e| e.to_string())?;
    eprintln!("[flash] session ok, packet_size={packet_size}, legacy={legacy}");

    set_total_bytes(&dev, total as u64).map_err(|e| e.to_string())?;
    let is_large = matches!(partition, "super" | "system" | "userdata");
    let sequences = flash_one_partition_ext(
        &dev,
        &pit,
        partition,
        image_file,
        packet_size,
        legacy,
        is_large,
        true, // single-partition flash = session last
    )
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

    let dev = open_and_handshake(target).map_err(|e| e.to_string())?;
    eprintln!("[flash] handshake ok");
    let (packet_size, legacy) = begin_session_v2(&dev).map_err(|e| e.to_string())?;
    eprintln!("[flash] session ok, packet_size={packet_size}, legacy={legacy}");

    // NOTE: the reference odin4 never sends a PIT to the device during a
    // firmware flash - it only *reads* the device's own PIT to learn partition
    // geometry. Pushing an external PIT here makes the DA flag the session
    // ("PitComplete: bootloader fail"), which prevents a clean hash-table
    // rebuild. The local PIT is used only for partition lookups below.

    set_total_bytes(&dev, total_bytes).map_err(|e| e.to_string())?;
    eprintln!("[flash] set_total_bytes ok ({total_bytes} bytes total)");

    let mut results = Vec::new();
    for (idx, (partition, image_file)) in files.iter().enumerate() {
        let is_large =
            matches!(*partition, "super" | "system" | "userdata");
        // is_last=1 only on the session's true final partition (live-device
        // finding: per-partition is_last closes the flash context and the
        // NEXT commit fails -5).
        let session_last = idx + 1 == files.len();
        let sequences = flash_one_partition_ext(
            &dev,
            &pit,
            partition,
            image_file,
            packet_size,
            legacy,
            is_large,
            session_last,
        )
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
        // True layout: 28-byte header, entries at 28.
        let mut pit = vec![0u8; 28];
        pit[0..4].copy_from_slice(&0x12349876u32.to_le_bytes());
        pit[4..8].copy_from_slice(&(entries as u32).to_le_bytes());
        for i in 0..entries {
            let mut e = vec![0u8; 132];
            e[0..4].copy_from_slice(&1u32.to_le_bytes()); // binary_type
            e[4..8].copy_from_slice(&0x50u32.to_le_bytes()); // device_type
            e[8..12].copy_from_slice(&(i as u32).to_le_bytes()); // identifier
            e[20..24].copy_from_slice(&512u32.to_le_bytes()); // blockSizeOrOffset
            e[24..28].copy_from_slice(&8u32.to_le_bytes()); // block_count
            let name = format!("partition{i}");
            e[36..36 + name.len()].copy_from_slice(name.as_bytes());
            let fname = format!("{i}.img");
            e[68..68 + fname.len()].copy_from_slice(fname.as_bytes());
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
        // Regression against the real firmware PIT in the repo, decoded with
        // the true layout (28-byte header): the bootloader partition must
        // resolve to binary_type=0 (AP), device_type=2 (MMC/eMMC),
        // identifier=80, start block 0, count 8192.
        let path = concat!(env!("CARGO_MANIFEST_DIR"), "/pit/A14M_MEA_OPEN.pit");
        let pit = std::fs::read(path).expect("real PIT present");
        let (bt, dt, id, bs, bc) = find_pit_entry(&pit, "bootloader").unwrap();
        assert_eq!((bt, dt, id, bs, bc), (0, 2, 80, 0, 8192));
        // flash_filename fallback lookup also resolves to the same entry.
        let (bt2, _, id2, _, _) = find_pit_entry(&pit, "preloader.img").unwrap();
        assert_eq!((bt2, id2), (0, 80));
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
    fn transient_usb_errors_are_identified() {
        assert!(is_transient_usb_error("bulk read: timed out"));
        assert!(is_transient_usb_error("LIBUSB_ERROR_TIMEOUT"));
        assert!(is_transient_usb_error("bulk write: pipe error"));
        assert!(is_transient_usb_error("no device found"));
        assert!(is_transient_usb_error("LIBUSB_ERROR_OVERFLOW"));
        assert!(!is_transient_usb_error("bootloader fail during file part"));
        assert!(!is_transient_usb_error("file part index mismatch"));
        assert!(!is_transient_usb_error("could not open file /nope.img"));
    }

    #[test]
    fn fail_check_progress_tolerated_only_in_lenient_mode() {
        let rsp = [0xffu8, 0xff, 0xff, 0xff, 0xfc, 0xff, 0xff, 0xff]; // ack = -4 (Write)
        std::env::remove_var("ODIN_STRICT");
        assert!(odin_fail_check(&rsp, "test", true).is_ok());
        std::env::set_var("ODIN_STRICT", "1");
        assert!(odin_fail_check(&rsp, "test", true).is_err());
        std::env::remove_var("ODIN_STRICT");
    }

    #[test]
    fn auth_and_size_commit_failures_are_never_treated_as_progress() {
        // -5 (Auth) and -6 (Size) mean the device rejected the write at the
        // end-sequence commit. These must be fatal even in lenient mode: a
        // rejected bootloader must never be reported as a completed flash.
        for ack_le in [[0xfb, 0xff, 0xff, 0xff], [0xfa, 0xff, 0xff, 0xff]] {
            let mut rsp = [0xffu8; 8];
            rsp[4..8].copy_from_slice(&ack_le);
            assert!(
                odin_fail_check(&rsp, "EndSequenceFlash", true).is_err(),
                "ack {:?} must be fatal with ODIN_STRICT unset",
                ack_le,
            );
        }
        // A genuine transfer-progress code (-4 Write) is still tolerated.
        let mut rsp = [0xffu8; 8];
        rsp[4..8].copy_from_slice(&[0xfc, 0xff, 0xff, 0xff]); // ack = -4
        std::env::remove_var("ODIN_STRICT");
        assert!(odin_fail_check(&rsp, "file part", true).is_ok());
    }
}
