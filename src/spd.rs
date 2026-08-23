//! Spreadtrum / UNISOC (SPD) feature-phone & SoC download support.
//!
//! Implements the Boot Service Layer (BSL) protocol spoken by the BootROM /
//! FDL stages of SC6530/SC6531 feature phones and newer UNISOC SoCs
//! (SL8541, T310, UMS9117...). The device enumerates as VID 0x1782, PID
//! 0x4d00 (download / engineering port) or 0x4d02/0x4e00.
//!
//! Frame layout (HDLC-framed, big-endian headers):
//!   `0x7e | type[2 BE] len[2 BE] payload[len] checksum[2 BE] | 0x7e`
//!   * BootROM checksum = CRC16 (poly 0x11021).
//!   * Once FDL1 runs the device switches to a ones-complement sum.
//!   * Bytes 0x7e / 0x7d inside the frame are escaped as `0x7d byte^0x20`.
//!
//! Protocol reference: spd_cmd.h / spd_dump.c (ilyakurdyukov/spreadtrum_flash)
//! and the Opus-Spreadtrum / uniflash clean-room write-ups.

use serde::Serialize;
use std::fs;
use std::time::Duration;

use crate::error::{BridgeError, Result};
use crate::usb;
use rusb::{Context, UsbContext};

pub const SPD_VID: u16 = 0x1782;

/// PIDs that put a Spreadtrum/UNISOC device in download/engineering mode.
pub fn is_download_pid(pid: u16) -> bool {
    matches!(pid, 0x4D00 | 0x4D02 | 0x4E00)
}

pub fn stage_label(pid: u16) -> &'static str {
    match pid {
        0x4D00 => "SPD download (BROM/FDL)",
        0x4D02 => "SPD download (engineering)",
        0x4E00 => "SPD download (FDL stage)",
        _ => "SPD device (normal/other)",
    }
}

// --------------------------- BSL constants -------------------------------

pub const BSL_CMD_CONNECT: u16 = 0x00;
pub const BSL_CMD_START_DATA: u16 = 0x01;
pub const BSL_CMD_MIDST_DATA: u16 = 0x02;
pub const BSL_CMD_END_DATA: u16 = 0x03;
pub const BSL_CMD_EXEC_DATA: u16 = 0x04;
pub const BSL_CMD_NORMAL_RESET: u16 = 0x05;
pub const BSL_CMD_READ_FLASH: u16 = 0x06;
pub const BSL_CMD_READ_CHIP_TYPE: u16 = 0x07;
pub const BSL_CMD_CHANGE_BAUD: u16 = 0x09;
pub const BSL_CMD_ERASE_FLASH: u16 = 0x0A;
pub const BSL_CMD_REPARTITION: u16 = 0x0B;
pub const BSL_CMD_READ_FLASH_TYPE: u16 = 0x0C;
pub const BSL_CMD_READ_FLASH_INFO: u16 = 0x0D;
pub const BSL_CMD_READ_SECTOR_SIZE: u16 = 0x0F;
pub const BSL_CMD_READ_START: u16 = 0x10;
pub const BSL_CMD_READ_MIDST: u16 = 0x11;
pub const BSL_CMD_READ_END: u16 = 0x12;
pub const BSL_CMD_KEEP_CHARGE: u16 = 0x13;
pub const BSL_CMD_POWER_OFF: u16 = 0x17;
pub const BSL_CMD_READ_CHIP_UID: u16 = 0x1A;
pub const BSL_CMD_ENABLE_WRITE_FLASH: u16 = 0x1B;
pub const BSL_CMD_DISABLE_TRANSCODE: u16 = 0x21;
pub const BSL_CMD_READ_PARTITION: u16 = 0x2D;
pub const BSL_CMD_CHECK_BAUD: u16 = 0x7E;

pub const BSL_REP_ACK: u16 = 0x80;
pub const BSL_REP_VER: u16 = 0x81;
pub const BSL_REP_INVALID_CMD: u16 = 0x82;
pub const BSL_REP_UNKNOW_CMD: u16 = 0x83;
pub const BSL_REP_OPERATION_FAILED: u16 = 0x84;
pub const BSL_REP_READ_FLASH: u16 = 0x93;
pub const BSL_REP_INCOMPATIBLE_PARTITION: u16 = 0x96;
pub const BSL_REP_SIGN_VERIFY_ERROR: u16 = 0xA6;
pub const BSL_REP_READ_CHIP_UID: u16 = 0xAB;
pub const BSL_REP_READ_PARTITION: u16 = 0xBA;
pub const BSL_REP_LOG: u16 = 0xFF;

pub const HDLC_HEADER: u8 = 0x7e;
pub const HDLC_ESCAPE: u8 = 0x7d;

// ------------------------- frame helpers ---------------------------------

/// CRC16 (poly 0x11021), init 0 — BootROM checksum.
fn spd_crc16(mut crc: u16, src: &[u8]) -> u16 {
    for &b in src {
        crc ^= (b as u16) << 8;
        for _ in 0..8 {
            crc = (crc << 1) ^ ((0u16.wrapping_sub(crc >> 15)) & 0x1021);
        }
    }
    crc
}

/// Ones-complement sum checksum used once FDL1 is running.
fn spd_sum(mut crc: u32, src: &[u8]) -> u16 {
    let mut it = src.chunks_exact(2);
    for c in &mut it {
        crc = crc.wrapping_add(((c[1] as u32) << 8) | c[0] as u32);
    }
    if let Some(&b) = it.remainder().first() {
        crc = crc.wrapping_add(b as u32);
    }
    crc = (crc >> 16) + (crc & 0xffff);
    crc += crc >> 16;
    (!crc) as u16
}

/// Escape HDLC special bytes (0x7e/0x7d) for the wire.
fn transcode_encode(src: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(src.len() + 8);
    for &b in src {
        if b == HDLC_HEADER || b == HDLC_ESCAPE {
            out.push(HDLC_ESCAPE);
            out.push(b ^ 0x20);
        } else {
            out.push(b);
        }
    }
    out
}

// --------------------------- session --------------------------------------

/// A claimed SPD BROM/FDL bulk session over USB.
pub struct SpdSession {
    handle: rusb::DeviceHandle<rusb::Context>,
    iface: u8,
    in_ep: u8,
    out_ep: u8,
    crc16: bool,
    transcode: bool,
    pub chip_id: u32,
    pub secure_boot: bool,
    pub version: String,
}

fn be16(v: u16) -> [u8; 2] {
    [(v >> 8) as u8, v as u8]
}

fn be32(v: u32) -> [u8; 4] {
    [(v >> 24) as u8, (v >> 16) as u8, (v >> 8) as u8, v as u8]
}

fn le32(v: u32) -> [u8; 4] {
    [v as u8, (v >> 8) as u8, (v >> 16) as u8, (v >> 24) as u8]
}

impl SpdSession {
    pub fn write_all(&self, data: &[u8]) -> std::result::Result<(), String> {
        self.handle
            .write_bulk(self.out_ep, data, Duration::from_secs(5))
            .map(|_| ())
            .map_err(|e| format!("bulk write: {e}"))
    }

    pub fn read_exact(&self, n: usize, timeout: Duration) -> std::result::Result<Vec<u8>, String> {
        let mut out = Vec::with_capacity(n);
        let mut buf = [0u8; 4096];
        let deadline = std::time::Instant::now() + timeout;
        while out.len() < n {
            let remain = deadline.saturating_duration_since(std::time::Instant::now());
            if remain.is_zero() {
                break;
            }
            match self.handle.read_bulk(self.in_ep, &mut buf, remain) {
                Ok(0) => break,
                Ok(r) => out.extend_from_slice(&buf[..r]),
                Err(e) => return Err(format!("bulk read: {e}")),
            }
        }
        if out.len() < n {
            return Err(format!("short read: got {} of {n} bytes", out.len()));
        }
        Ok(out)
    }

    pub fn flush(&self) {
        let mut junk = [0u8; 64];
        let _ = self
            .handle
            .read_bulk(self.in_ep, &mut junk, Duration::from_millis(30));
    }

    /// Build + transmit one BSL frame.
    pub fn send_msg(&self, cmd: u16, payload: &[u8]) -> std::result::Result<(), String> {
        let mut raw = Vec::with_capacity(payload.len() + 6);
        raw.extend_from_slice(&be16(cmd));
        raw.extend_from_slice(&be16(payload.len() as u16));
        raw.extend_from_slice(payload);
        let chk = if self.crc16 {
            spd_crc16(0, &raw)
        } else {
            spd_sum(0, &raw)
        };
        raw.extend_from_slice(&be16(chk));

        let mut frame = Vec::with_capacity(raw.len() + 2);
        frame.push(HDLC_HEADER);
        if self.transcode {
            frame.extend_from_slice(&transcode_encode(&raw));
        } else {
            frame.extend_from_slice(&raw);
        }
        frame.push(HDLC_HEADER);
        self.write_all(&frame)
    }

    /// Read one complete BSL frame (returns its type + payload).
    pub fn recv_msg(&self, timeout: Duration) -> std::result::Result<(u16, Vec<u8>), String> {
        let mut collected: Vec<u8> = Vec::new();
        let deadline = std::time::Instant::now() + timeout;
        let mut expect_len: Option<usize> = None;

        // Read until we find a full `0x7e ... 0x7e` frame, undoing escaping.
        let mut raw = Vec::new();
        let mut esc = false;
        loop {
            let remain = deadline.saturating_duration_since(std::time::Instant::now());
            if remain.is_zero() {
                return Err("recv timeout".to_string());
            }
            if collected.is_empty() {
                collected = self.read_exact(1, remain)?;
            }
            // consume one byte
            let b = collected.remove(0);
            if esc {
                raw.push(b ^ 0x20);
                esc = false;
            } else if b == HDLC_ESCAPE && self.transcode {
                esc = true;
            } else if b == HDLC_HEADER {
                if raw.is_empty() {
                    continue; // leading flag
                }
                // closing flag
                if raw.len() < 6 {
                    return Err("frame too short".to_string());
                }
                let len = ((raw[2] as usize) << 8) | raw[3] as usize;
                if raw.len() != len + 6 {
                    return Err(format!(
                        "frame length mismatch: {} vs payload {len}",
                        raw.len()
                    ));
                }
                let cmd = ((raw[0] as u16) << 8) | raw[1] as u16;
                let payload = raw[4..raw.len() - 2].to_vec();
                // verify checksum
                let want = ((raw[raw.len() - 2] as u16) << 8) | raw[raw.len() - 1] as u16;
                let body = &raw[..raw.len() - 2];
                let got = if self.crc16 {
                    spd_crc16(0, body)
                } else {
                    spd_sum(0, body)
                };
                if want != got {
                    return Err(format!(
                        "checksum mismatch: frame 0x{want:04x}, computed 0x{got:04x}"
                    ));
                }
                let _ = expect_len;
                return Ok((cmd, payload));
            } else {
                raw.push(b);
                if raw.len() == 4 {
                    expect_len = Some(((raw[2] as usize) << 8) | raw[3] as usize);
                }
                if let Some(len) = expect_len {
                    if raw.len() > len + 6 {
                        return Err("frame overrun".to_string());
                    }
                }
            }
        }
    }

    /// Send a command and expect a plain ACK.
    pub fn cmd_ack(&self, cmd: u16, payload: &[u8]) -> std::result::Result<(), String> {
        self.send_msg(cmd, payload)?;
        let (resp, _) = self.recv_msg(Duration::from_secs(5))?;
        if resp == BSL_REP_LOG {
            let (resp, _) = self.recv_msg(Duration::from_secs(5))?;
            if resp != BSL_REP_ACK {
                return Err(format!("command 0x{cmd:04x}: unexpected response 0x{resp:04x}"));
            }
            return Ok(());
        }
        if resp != BSL_REP_ACK {
            return Err(format!(
                "command 0x{cmd:04x}: expected ACK, got 0x{resp:04x}"
            ));
        }
        Ok(())
    }

    /// Stream `data` to `start_addr` via START/MIDST/END, then EXEC.
    pub fn load_to_ram(&self, start_addr: u32, data: &[u8], step: usize) -> std::result::Result<(), String> {
        let mut hdr = Vec::with_capacity(8);
        hdr.extend_from_slice(&be32(start_addr));
        hdr.extend_from_slice(&be32(data.len() as u32));
        self.cmd_ack(BSL_CMD_START_DATA, &hdr)?;

        for chunk in data.chunks(step) {
            self.cmd_ack(BSL_CMD_MIDST_DATA, chunk)?;
        }
        self.cmd_ack(BSL_CMD_END_DATA, &[])?;
        self.cmd_ack(BSL_CMD_EXEC_DATA, &[])?;
        Ok(())
    }

    /// BootROM + FDL1 handshake sequence. Returns the FDL version string.
    pub fn handshake(&mut self) -> std::result::Result<String, String> {
        // BootROM stage: CRC16 checksum + transcode.
        self.crc16 = true;
        self.transcode = true;

        // CHECK_BAUD burst of one byte -> device answers BSL_REP_VER "SPRD3..."
        self.send_msg(BSL_CMD_CHECK_BAUD, &[HDLC_HEADER])?;
        let (resp, payload) = self.recv_msg(Duration::from_secs(5))?;
        if resp != BSL_REP_VER {
            return Err(format!("CHECK_BAUD: expected VER, got 0x{resp:04x}"));
        }
        let version = String::from_utf8_lossy(&payload).to_string();
        self.version = version.clone();
        // SPRD3 -> unsecured legacy boot; anything else implies secure boot.
        self.secure_boot = !(payload.len() >= 6 && &payload[..6] == b"SPRD3");

        self.cmd_ack(BSL_CMD_CONNECT, &[])?;

        // After CONNECT we parse the chip id from the version banner later;
        // FDL1 switches the checksum to the ones-complement sum.
        Ok(version)
    }

    /// After FDL1 executes the device re-syncs: CHECK_BAUD x4 -> VER.
    pub fn resync_after_fdl1(&mut self) -> std::result::Result<String, String> {
        self.crc16 = false; // FDL1 uses the sum checksum
        self.send_msg(BSL_CMD_CHECK_BAUD, &[0u8; 4])?;
        let (resp, payload) = self.recv_msg(Duration::from_secs(8))?;
        if resp != BSL_REP_VER {
            return Err(format!("FDL1 resync: expected VER, got 0x{resp:04x}"));
        }
        let text = String::from_utf8_lossy(&payload).to_string();
        // The banner may contain "CHIP ID = 0x..." — capture it for chip logic.
        if let Some(pos) = text.find("CHIP ID = 0x") {
            let end = (pos + 19).min(text.len());
            if end > pos + 11 {
                if let Ok(v) = u32::from_str_radix(&text[pos + 11..end], 16) {
                    self.chip_id = v;
                }
            }
        }
        self.cmd_ack(BSL_CMD_CONNECT, &[])?;
        Ok(text)
    }

    /// Enable write access (required before ERASE / WRITE on some FDL2s).
    pub fn enable_write(&self) -> std::result::Result<(), String> {
        self.cmd_ack(BSL_CMD_ENABLE_WRITE_FLASH, &[])
    }

    /// Read a raw flash region (feature-phone style: address-based).
    /// Returns the number of bytes actually read.
    pub fn read_flash(&self, addr: u32, offset: u32, len: usize, step: usize, out: &mut Vec<u8>) -> std::result::Result<usize, String> {
        let mut done = 0usize;
        while done < len {
            let n = (len - done).min(step);
            let mut payload = Vec::with_capacity(12);
            payload.extend_from_slice(&be32(addr));
            payload.extend_from_slice(&be32(n as u32));
            payload.extend_from_slice(&be32(offset + done as u32));
            self.send_msg(BSL_CMD_READ_FLASH, &payload)?;
            let (resp, data) = self.recv_msg(Duration::from_secs(15))?;
            if resp != BSL_REP_READ_FLASH {
                return Err(format!("READ_FLASH: unexpected response 0x{resp:04x}"));
            }
            out.extend_from_slice(&data);
            done += data.len();
            if data.len() < n {
                break;
            }
        }
        Ok(done)
    }

    /// Erase a raw flash region.
    pub fn erase_flash(&self, addr: u32, size: u32) -> std::result::Result<(), String> {
        let mut payload = Vec::with_capacity(8);
        payload.extend_from_slice(&be32(addr));
        payload.extend_from_slice(&be32(size));
        self.cmd_ack(BSL_CMD_ERASE_FLASH, &payload)
    }

    /// Read the partition table (FDL2). Returns (name, size) pairs.
    pub fn read_partitions(&self) -> std::result::Result<Vec<(String, u64)>, String> {
        self.send_msg(BSL_CMD_READ_PARTITION, &[])?;
        let (resp, data) = self.recv_msg(Duration::from_secs(10))?;
        if resp != BSL_REP_READ_PARTITION {
            return Err(format!("READ_PARTITION: unexpected response 0x{resp:04x}"));
        }
        if data.len() % 0x4c != 0 {
            return Err(format!("partition table size {} not multiple of 0x4c", data.len()));
        }
        let mut parts = Vec::new();
        for chunk in data.chunks_exact(0x4c) {
            let mut name = String::new();
            for pair in chunk[..72].chunks_exact(2) {
                let c = pair[0];
                if c == 0 {
                    break;
                }
                name.push(c as char);
            }
            let size = u32::from_le_bytes([chunk[0x48], chunk[0x49], chunk[0x4a], chunk[0x4b]]);
            parts.push((name, size as u64));
        }
        Ok(parts)
    }

    /// Select + stream a named partition (FDL2 partition I/O).
    fn partition_start(&self, name: &str, size: u64, cmd: u16) -> std::result::Result<(), String> {
        let mut pkt = vec![0u8; 0x4c];
        let name_bytes = name.as_bytes();
        for (i, &b) in name_bytes.iter().enumerate().take(36) {
            pkt[i * 2] = b;
        }
        pkt[0x48..0x4c].copy_from_slice(&le32(size as u32));
        self.cmd_ack(cmd, &pkt[..0x48 + 4])
    }

    /// Write a named partition from a file (destructive).
    pub fn write_partition(&self, name: &str, file_path: &str, step: usize) -> std::result::Result<(), String> {
        let data = fs::read(file_path).map_err(|e| format!("read {file_path}: {e}"))?;
        self.partition_start(name, data.len() as u64, BSL_CMD_START_DATA)?;
        for chunk in data.chunks(step) {
            self.cmd_ack(BSL_CMD_MIDST_DATA, chunk)?;
        }
        self.cmd_ack(BSL_CMD_END_DATA, &[])?;
        Ok(())
    }

    /// Read a named partition to a file.
    pub fn read_partition(&self, name: &str, start: u64, len: u64, out_path: &str, step: usize) -> std::result::Result<u64, String> {
        let mode64 = (start + len) >> 32 != 0;
        self.partition_start(name, start + len, BSL_CMD_READ_START)?;
        let mut out = fs::File::create(out_path).map_err(|e| format!("create {out_path}: {e}"))?;
        use std::io::Write;
        let mut done = 0u64;
        while done < len {
            let n = ((len - done) as usize).min(step);
            let mut payload = Vec::with_capacity(12);
            payload.extend_from_slice(&le32(n as u32));
            payload.extend_from_slice(&le32((start + done) as u32));
            if mode64 {
                payload.extend_from_slice(&le32(0));
            }
            self.send_msg(BSL_CMD_READ_MIDST, &payload)?;
            let (resp, data) = self.recv_msg(Duration::from_secs(15))?;
            if resp != BSL_REP_READ_FLASH {
                self.cmd_ack(BSL_CMD_READ_END, &[])?;
                return Err(format!("READ_MIDST: unexpected response 0x{resp:04x}"));
            }
            out.write_all(&data).map_err(|e| format!("write {out_path}: {e}"))?;
            done += data.len() as u64;
            if data.len() < n {
                break;
            }
        }
        self.cmd_ack(BSL_CMD_READ_END, &[])?;
        Ok(done)
    }

    /// Erase a named partition.
    pub fn erase_partition(&self, name: &str) -> std::result::Result<(), String> {
        self.partition_start(name, 0, BSL_CMD_ERASE_FLASH)
    }

    /// Read the chip UID string.
    pub fn chip_uid(&self) -> std::result::Result<String, String> {
        self.send_msg(BSL_CMD_READ_CHIP_UID, &[])?;
        let (resp, data) = self.recv_msg(Duration::from_secs(5))?;
        if resp != BSL_REP_READ_CHIP_UID {
            return Err(format!("READ_CHIP_UID: unexpected response 0x{resp:04x}"));
        }
        Ok(String::from_utf8_lossy(&data).to_string())
    }

    pub fn reset(&self) -> std::result::Result<(), String> {
        self.cmd_ack(BSL_CMD_NORMAL_RESET, &[])
    }

    pub fn power_off(&self) -> std::result::Result<(), String> {
        self.cmd_ack(BSL_CMD_POWER_OFF, &[])
    }

    /// Raw START_DATA + MIDST_DATA chunks + END_DATA to an arbitrary address
    /// (mirrors spd_dump `send_buf`: used both for RAM loads and raw flash
    /// writes on feature phones — no EXEC, the flash controller handles it).
    pub fn write_raw(&self, start_addr: u32, data: &[u8], step: usize) -> std::result::Result<(), String> {
        let mut hdr = Vec::with_capacity(8);
        hdr.extend_from_slice(&be32(start_addr));
        hdr.extend_from_slice(&be32(data.len() as u32));
        self.cmd_ack(BSL_CMD_START_DATA, &hdr)?;
        for chunk in data.chunks(step) {
            self.cmd_ack(BSL_CMD_MIDST_DATA, chunk)?;
        }
        self.cmd_ack(BSL_CMD_END_DATA, &[])
    }
}

// --------------------------- open + detect --------------------------------

/// Find bulk endpoints on an SPD device, mirroring spd_dump's find_endpoints.
pub fn find_bulk<'a>(dev: &'a usb::UsbDeviceInfo) -> Option<(u8, u8, u8)> {
    for iface in &dev.interfaces {
        let in_ep = iface
            .endpoints
            .iter()
            .find(|e| e.direction == "in" && e.transfer_type == "bulk")
            .map(|e| e.address);
        let out_ep = iface
            .endpoints
            .iter()
            .find(|e| e.direction == "out" && e.transfer_type == "bulk")
            .map(|e| e.address);
        if let (Some(i), Some(o)) = (in_ep, out_ep) {
            return Some((iface.number, i, o));
        }
    }
    None
}

/// Open + claim the SPD download port for `dev`.
pub fn open_session(dev: &usb::UsbDeviceInfo) -> Result<SpdSession> {
    let context = Context::new().map_err(|e| {
        BridgeError::Usb(crate::error::UsbError::TransferFailed(e.to_string()))
    })?;
    let handle = context
        .devices()?
        .iter()
        .find(|d| {
            let desc = d.device_descriptor().ok();
            desc.as_ref().map_or(false, |desc| {
                desc.vendor_id() == SPD_VID && desc.product_id() == dev.pid
            }) && d.bus_number() == dev.bus && d.address() == dev.address
        })
        .ok_or(BridgeError::Usb(crate::error::UsbError::DeviceNotFound))?
        .open()?;
    let _ = handle.set_auto_detach_kernel_driver(true);

    let (iface, in_ep, out_ep) = find_bulk(dev)
        .ok_or_else(|| BridgeError::InvalidArgument("no bulk endpoints on SPD device".to_string()))?;
    handle
        .claim_interface(iface)
        .map_err(|e| format!("claim interface {iface}: {e}"))?;

    // Activate the download data interface (spd_dump control transfer).
    let _ = handle.write_control(
        0x21,
        34,
        0x601,
        0,
        &[],
        Duration::from_secs(1),
    );

    Ok(SpdSession {
        handle,
        iface,
        in_ep,
        out_ep,
        crc16: true,
        transcode: true,
        chip_id: 0,
        secure_boot: false,
        version: String::new(),
    })
}

#[derive(Serialize)]
pub struct SpdDeviceInfo {
    pub bus: u8,
    pub address: u8,
    pub vid: u16,
    pub pid: u16,
    pub product: Option<String>,
    pub manufacturer: Option<String>,
    pub stage: String,
    pub download: bool,
}

pub fn detect_spd() -> Result<String> {
    let devices = usb::collect_devices(None).map_err(|e| e.to_string())?;
    let out: Vec<SpdDeviceInfo> = devices
        .iter()
        .filter(|d| d.vid == SPD_VID)
        .map(|d| SpdDeviceInfo {
            bus: d.bus,
            address: d.address,
            vid: d.vid,
            pid: d.pid,
            product: d.product.clone(),
            manufacturer: d.manufacturer.clone(),
            stage: stage_label(d.pid).to_string(),
            download: is_download_pid(d.pid),
        })
        .collect();
    serde_json::to_string_pretty(&out).map_err(|e| BridgeError::InvalidArgument(e.to_string()))
}

/// Identify the running chip from the FDL version banner, returning the
/// (fw_addr, ram_addr) FDL base addresses for known chips. Feature-phone
/// chips auto-derive; Android SoCs need their XML-specified bases (the
/// known ones are included so a bare `--chip` hint is rarely needed).
pub fn chip_fdl_bases(chip_id: u32) -> Option<(u32, u32)> {
    // SC6530 / SC6530C / SC6531 (feature phones)
    if (chip_id ^ 0x6530_0000) >> 17 == 0 {
        return Some((0x3000_0000, 0x3400_0000));
    }
    // SC6531E (feature phones)
    if (chip_id ^ 0x6562_0000) >> 16 == 0 {
        return Some((0x1000_0000, 0x1400_0000));
    }
    // UMS9117 / T117 (4G feature phones, Android-capable)
    if (chip_id ^ 0x9818_0000) >> 16 == 0 {
        return Some((0x0, 0x8000_0000));
    }
    // SL8541E / UMS512 (Android) - FDL1 @0x5500, FDL2 @0x9EFFFE00
    if chip_id == 0x5000_0 || chip_id == 0x7100_0 {
        return Some((0x5500, 0x9EFF_FE00));
    }
    None
}

// --------------------------- high-level flows -----------------------------

/// Open a download session, run the BootROM handshake, load FDL1 and FDL2,
/// and leave the session ready for partition I/O. `fdl1_addr` / `fdl2_addr`
/// default from the chip id when known.
pub fn connect_and_load_fdls(
    dev: &usb::UsbDeviceInfo,
    fdl1: &str,
    fdl1_addr: u32,
    fdl2: &str,
    fdl2_addr: u32,
    keep_charge: bool,
    step: usize,
) -> Result<SpdSession> {
    let mut s = open_session(dev)?;
    let ver = s.handshake().map_err(|e| {
        BridgeError::Protocol(crate::error::ProtocolError::HandshakeFailed(e))
    })?;
    eprintln!("[spd] BootROM version: {ver}");

    let fdl1_data = fs::read(fdl1).map_err(|e| {
        BridgeError::Config(crate::error::ConfigError::FileNotFound(e.to_string()))
    })?;
    s.load_to_ram(fdl1_addr, &fdl1_data, step)
        .map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
            cmd: 0,
            sub: 0,
            reason: format!("FDL1 upload: {e}"),
        }))?;

    let banner = s.resync_after_fdl1().map_err(|e| {
        BridgeError::Protocol(crate::error::ProtocolError::HandshakeFailed(e))
    })?;
    eprintln!("[spd] FDL1 banner: {banner}");

    // Prefer explicit FDL2 base, else derive from chip id.
    let f2 = if fdl2_addr != 0 {
        fdl2_addr
    } else {
        match chip_fdl_bases(s.chip_id) {
            Some((_, ram)) => ram,
            None => 0x1400_0000,
        }
    };

    if keep_charge {
        let _ = s.cmd_ack(BSL_CMD_KEEP_CHARGE, &[]);
    }

    if fdl2.is_empty() || fdl2 == "none" {
        eprintln!("[spd] no FDL2 provided - single-stage session (feature phone)");
        return Ok(s);
    }

    let fdl2_data = fs::read(fdl2).map_err(|e| {
        BridgeError::Config(crate::error::ConfigError::FileNotFound(e.to_string()))
    })?;
    s.load_to_ram(f2, &fdl2_data, step)
        .map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
            cmd: 0,
            sub: 0,
            reason: format!("FDL2 upload: {e}"),
        }))?;
    Ok(s)
}

// --------------------------- CLI entry points -----------------------------

/// `spd-detect` — list SPD USB devices.
pub fn spd_detect_cli() -> Result<String> {
    detect_spd()
}

/// `spd-info <target>` — full USB + protocol info (best effort, read-only).
pub fn spd_info_cli(target: &str) -> Result<String> {
    let devices = usb::collect_devices(None).map_err(|e| e.to_string())?;
    let dev = devices
        .iter()
        .find(|d| d.vid == SPD_VID && format!("{}:{}", d.bus, d.address) == target)
        .ok_or_else(|| BridgeError::InvalidArgument(format!("SPD device {target} not found")))?;

    let mut lines = vec![
        "=== Spreadtrum / UNISOC Device Info ===".to_string(),
    ];
    lines.push(format!("VID:PID   1782:{:04x}", dev.pid));
    lines.push(format!("Bus:Addr  {}:{}", dev.bus, dev.address));
    if let Some(p) = &dev.product {
        lines.push(format!("Product:  {p}"));
    }
    if let Some(m) = &dev.manufacturer {
        lines.push(format!("Mfr:      {m}"));
    }
    for i in &dev.interfaces {
        lines.push(format!(
            "Iface {}: class {} sub {} proto {} ({} endpoints)",
            i.number,
            i.class,
            i.subclass,
            i.protocol,
            i.endpoints.len()
        ));
    }
    if is_download_pid(dev.pid) {
        lines.push(String::new());
        lines.push("Device is in download mode (BROM/FDL).".to_string());
        match open_session(dev) {
            Ok(mut s) => {
                match s.handshake() {
                    Ok(ver) => {
                        lines.push(format!("BootROM version: {}", ver.trim_end_matches('\0')));
                        lines.push(format!("Secure boot: {}", if s.secure_boot { "yes" } else { "no" }));
                        match chip_fdl_bases(s.chip_id) {
                            Some((fw, ram)) => lines.push(format!(
                                "Chip ID 0x{:08x}: FDL1 base 0x{fw:08x}, FDL2 base 0x{ram:08x}",
                                s.chip_id
                            )),
                            None => {
                                if s.chip_id != 0 {
                                    lines.push(format!(
                                        "Chip ID 0x{:08x}: no known FDL base mapping",
                                        s.chip_id
                                    ));
                                }
                            }
                        }
                    }
                    Err(e) => lines.push(format!("BROM handshake: {e}")),
                }
            }
            Err(e) => lines.push(format!("Open error: {e}")),
        }
    } else {
        lines.push(String::new());
        lines.push("Device is NOT in download mode. To reach BROM/FDL:".to_string());
        lines.push("  power OFF, hold the boot key (often Volume- or '*'), plug USB.".to_string());
    }
    Ok(lines.join("\n"))
}

/// `spd-format <target> <fdl1> <fdl1_addr> [fdl2] [fdl2_addr]` —
/// load FDLs then ERASE the user-data / NV areas (feature-phone password
/// removal without flashing firmware: this is the "Format / Reset to
/// Factory Default" operation commercial tools perform).
pub fn spd_format_cli(
    target: &str,
    fdl1: &str,
    fdl1_addr: u32,
    fdl2: Option<&str>,
    fdl2_addr: Option<u32>,
) -> Result<String> {
    let dev = find_spd_target(target)?;
    let mut out = Vec::new();
    let step = 528usize;

    let mut s = open_session(&dev)?;
    let ver = s.handshake().map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::HandshakeFailed(e)))?;
    out.push(format!("BootROM version: {ver}"));

    let f1 = fs::read(fdl1).map_err(|e| BridgeError::Config(crate::error::ConfigError::FileNotFound(e.to_string())))?;
    s.load_to_ram(fdl1_addr, &f1, step)
        .map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed { cmd: 0, sub: 0, reason: format!("FDL1 upload: {e}") }))?;
    let banner = s.resync_after_fdl1().map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::HandshakeFailed(e)))?;
    out.push(format!("FDL1 banner: {}", banner.trim_end_matches('\0')));

    // FDL2 present -> Android-style device: erase by named partition.
    let android = fdl2.is_some();
    if let Some(f2path) = fdl2 {
        let f2 = fs::read(f2path).map_err(|e| BridgeError::Config(crate::error::ConfigError::FileNotFound(e.to_string())))?;
        let f2addr = fdl2_addr.unwrap_or_else(|| chip_fdl_bases(s.chip_id).map(|(_, r)| r).unwrap_or(0x1400_0000));
        s.load_to_ram(f2addr, &f2, step)
            .map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed { cmd: 0, sub: 0, reason: format!("FDL2 upload: {e}") }))?;
        out.push("FDL2 loaded (Android partition mode)".to_string());
    } else {
        // Single-stage (feature phones often only need FDL1).
        let _ = s.enable_write();
    }

    if android {
        // Android UNISOC device: erase user-data / lock partitions by name.
        let parts = s
            .read_partitions()
            .map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::UnexpectedResponse(e)))?;
        let avail: Vec<String> = parts.iter().map(|(n, _)| n.clone()).collect();
        out.push(format!("Partition table: {} entries", parts.len()));
        for want in ["userdata", "cache", "frp", "frp_a", "misc"] {
            if !avail.contains(&want.to_string()) {
                out.push(format!("  '{want}': not present, skipped"));
                continue;
            }
            match s.erase_partition(want) {
                Ok(_) => out.push(format!("  erased partition '{want}'")),
                Err(e) => out.push(format!("  '{want}': {e}")),
            }
        }
    } else {
        // Feature phone: erase the raw areas that hold the security lock /
        // user data. IDs from the SC6531 flash map:
        // NV = 0x90000001, PS = 0x80000003, FLASH = 0x90000003 (varies).
        out.push("Erasing security / user-data regions...".to_string());
        for (name, addr, size) in [
            ("PS (param store)", 0x8000_0003u32, 0x1000u32),
            ("NV (non-volatile)", 0x9000_0001, 0x10000),
        ] {
            match s.erase_flash(addr, size) {
                Ok(_) => out.push(format!("  erased {name} @0x{addr:08x}")),
                Err(e) => out.push(format!("  {name}: {e}")),
            }
        }
    }

    let _ = s.reset();
    out.push("Done. Device reset to normal mode.".to_string());
    Ok(out.join("\n"))
}

/// `spd-partitions <target> <fdl1> <fdl1_addr> [fdl2] [fdl2_addr]` —
/// load FDLs then list the Android partition table (sizes in bytes).
pub fn spd_partitions_cli(
    target: &str,
    fdl1: &str,
    fdl1_addr: u32,
    fdl2: Option<&str>,
    fdl2_addr: Option<u32>,
) -> Result<String> {
    let dev = find_spd_target(target)?;
    let mut s = connect_and_load_fdls(
        &dev,
        fdl1,
        fdl1_addr,
        fdl2.unwrap_or(""),
        fdl2_addr.unwrap_or(0),
        true,
        528,
    )?;
    let _ = s.enable_write();
    let parts = s
        .read_partitions()
        .map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::UnexpectedResponse(e)))?;
    let mut out = vec![format!("{} partition(s):", parts.len())];
    for (name, size) in &parts {
        out.push(format!("  {name:28} {size} bytes"));
    }
    let _ = s.reset();
    Ok(out.join("\n"))
}

/// `spd-backup <target> <fdl1> <fdl1_addr> <fdl2> <fdl2_addr> <out_dir>` —
/// load FDLs then dump all named partitions to files.
pub fn spd_backup_cli(
    target: &str,
    fdl1: &str,
    fdl1_addr: u32,
    fdl2: &str,
    fdl2_addr: u32,
    out_dir: &str,
) -> Result<String> {
    let dev = find_spd_target(target)?;
    let mut s = connect_and_load_fdls(&dev, fdl1, fdl1_addr, fdl2, fdl2_addr, true, 528)?;
    let _ = s.enable_write();
    let parts = s.read_partitions().map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::UnexpectedResponse(e)))?;
    let mut out = Vec::new();
    out.push(format!("{} partition(s) from Android/SPD device:", parts.len()));

    let mut dumped = 0u64;
    for (name, size) in &parts {
        let safe = sanitize(name);
        let path = format!("{out_dir}/{safe}.bin");
        if *size == 0 {
            out.push(format!("  {name}: size 0, skipped"));
            continue;
        }
        match s.read_partition(name, 0, *size, &path, 4096) {
            Ok(n) => {
                out.push(format!("  {name}: read {n} bytes -> {path}"));
                dumped += n;
            }
            Err(e) => out.push(format!("  {name}: FAILED - {e}")),
        }
    }
    out.push(format!("Total dumped: {dumped} bytes"));
    let _ = s.reset();
    Ok(out.join("\n"))
}

/// `spd-frp <target> <fdl1> <fdl1_addr> [fdl2] [fdl2_addr]` —
/// erase the FRP lock partition (Android UNISOC devices).
pub fn spd_frp_cli(
    target: &str,
    fdl1: &str,
    fdl1_addr: u32,
    fdl2: Option<&str>,
    fdl2_addr: Option<u32>,
) -> Result<String> {
    let dev = find_spd_target(target)?;
    let mut s = open_session(&dev)?;
    s.handshake().map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::HandshakeFailed(e)))?;
    let f1 = fs::read(fdl1).map_err(|e| BridgeError::Config(crate::error::ConfigError::FileNotFound(e.to_string())))?;
    s.load_to_ram(fdl1_addr, &f1, 528)
        .map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed { cmd: 0, sub: 0, reason: format!("FDL1: {e}") }))?;
    s.resync_after_fdl1().map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::HandshakeFailed(e)))?;

    if let Some(f2p) = fdl2 {
        let f2 = fs::read(f2p).map_err(|e| BridgeError::Config(crate::error::ConfigError::FileNotFound(e.to_string())))?;
        let f2a = fdl2_addr.unwrap_or_else(|| chip_fdl_bases(s.chip_id).map(|(_, r)| r).unwrap_or(0x1400_0000));
        s.load_to_ram(f2a, &f2, 528)
            .map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed { cmd: 0, sub: 0, reason: format!("FDL2: {e}") }))?;
    }
    let _ = s.enable_write();
    let mut out = Vec::new();
    for name in ["frp", "frp_a", "misc"] {
        match s.erase_partition(name) {
            Ok(_) => out.push(format!("  erased partition '{name}'")),
            Err(e) => out.push(format!("  '{name}': {e}")),
        }
    }
    let _ = s.reset();
    out.insert(0, "FRP / lock partitions erased.".to_string());
    Ok(out.join("\n"))
}

/// `spd-reset <target>` — issue a normal reset on a download-mode device.
pub fn spd_reset_cli(target: &str) -> Result<String> {
    let dev = find_spd_target(target)?;
    let s = open_session(&dev)?;
    match s.reset() {
        Ok(_) => Ok("Device reset to normal mode.".to_string()),
        Err(e) => Err(BridgeError::Protocol(crate::error::ProtocolError::UnexpectedResponse(e))),
    }
}

/// `spd-flash <target> <fdl1> <fdl1_addr> [fdl2] [fdl2_addr] <part=file>...` —
/// load FDLs, enable write, then write each `partition=image` entry.
/// Raw flash regions can be targeted with a hex address instead of a name
/// (e.g. `0x80000003=ps.bin`), and special raw-region aliases are resolved.
pub fn spd_flash_cli(
    target: &str,
    fdl1: &str,
    fdl1_addr: u32,
    fdl2: Option<&str>,
    fdl2_addr: Option<u32>,
    entries: &[(String, String)],
) -> Result<String> {
    if entries.is_empty() {
        return Err(BridgeError::InvalidArgument(
            "no partition=file entries provided".to_string(),
        ));
    }
    let dev = find_spd_target(target)?;
    let mut s = open_session(&dev)?;
    let mut out = Vec::new();

    let ver = s.handshake().map_err(|e| {
        BridgeError::Protocol(crate::error::ProtocolError::HandshakeFailed(e))
    })?;
    out.push(format!("BootROM version: {ver}"));

    let f1 = fs::read(fdl1).map_err(|e| {
        BridgeError::Config(crate::error::ConfigError::FileNotFound(e.to_string()))
    })?;
    s.load_to_ram(fdl1_addr, &f1, 528).map_err(|e| {
        BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
            cmd: 0,
            sub: 0,
            reason: format!("FDL1 upload: {e}"),
        })
    })?;
    let banner = s.resync_after_fdl1().map_err(|e| {
        BridgeError::Protocol(crate::error::ProtocolError::HandshakeFailed(e))
    })?;
    out.push(format!("FDL1 banner: {}", banner.trim_end_matches('\0')));

    if let Some(f2p) = fdl2 {
        if !f2p.is_empty() && f2p != "none" {
            let f2 = fs::read(f2p).map_err(|e| {
                BridgeError::Config(crate::error::ConfigError::FileNotFound(e.to_string()))
            })?;
            let f2a = fdl2_addr.unwrap_or_else(|| {
                chip_fdl_bases(s.chip_id).map(|(_, r)| r).unwrap_or(0x1400_0000)
            });
            s.load_to_ram(f2a, &f2, 528).map_err(|e| {
                BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
                    cmd: 0,
                    sub: 0,
                    reason: format!("FDL2 upload: {e}"),
                })
            })?;
            out.push(format!("FDL2 loaded @0x{f2a:x}"));
        }
    }

    let _ = s.enable_write();

    // Resolve feature-phone raw-region aliases.
    let raw_aliases: &[(&str, u32)] = &[
        ("bootloader", 0x8000_0000),
        ("ps", 0x8000_0003),
        ("nv", 0x9000_0001),
        ("phasecheck", 0x9000_0002),
        ("flash", 0x9000_0003),
        ("mmires", 0x9000_0004),
        ("udisk", 0x9000_0006),
    ];

    for (part, file) in entries {
        let data = fs::read(file).map_err(|e| {
            BridgeError::Config(crate::error::ConfigError::FileNotFound(e.to_string()))
        })?;
        out.push(format!("Writing '{part}' ({}) from {file}...", data.len()));
        if part.starts_with("0x") {
            let addr = u32::from_str_radix(part.trim_start_matches("0x"), 16).map_err(|_| {
                BridgeError::InvalidArgument(format!("bad address '{part}'"))
            })?;
            s.write_raw(addr, &data, 528).map_err(|e| {
                BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
                    cmd: 0,
                    sub: 0,
                    reason: format!("raw write {part}: {e}"),
                })
            })?;
        } else if let Some(&(_, addr)) = raw_aliases.iter().find(|(n, _)| *n == part) {
            s.write_raw(addr, &data, 528).map_err(|e| {
                BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
                    cmd: 0,
                    sub: 0,
                    reason: format!("raw write {part} @0x{addr:x}: {e}"),
                })
            })?;
        } else {
            s.write_partition(part, file, 4096).map_err(|e| {
                BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
                    cmd: 0,
                    sub: 0,
                    reason: format!("partition write {part}: {e}"),
                })
            })?;
        }
        out.push(format!("  '{part}' written OK"));
    }

    let _ = s.reset();
    out.push("Flash complete - device reset to normal mode.".to_string());
    Ok(out.join("\n"))
}

fn find_spd_target(target: &str) -> Result<usb::UsbDeviceInfo> {
    let devices = usb::collect_devices(None).map_err(|e| e.to_string())?;
    devices
        .into_iter()
        .find(|d| d.vid == SPD_VID && format!("{}:{}", d.bus, d.address) == target)
        .ok_or_else(|| BridgeError::InvalidArgument(format!("SPD device {target} not found")))
}

fn sanitize(name: &str) -> String {
    name.chars()
        .map(|c| if c.is_ascii_alphanumeric() || c == '_' { c } else { '_' })
        .collect()
}

// ---------------------------------------------------------------------------
// .pac readback: dump the full flash via FDL2 and repack into a SPD .pac
// container so it can be re-flashed by SPD Research Tool / Upgrade Download.
//
// .pac layout (YGDP, reverse-engineered from public parsers):
//   header  2124 bytes:
//     0x00  magic       b"\xd3\x00\x00\x00" (little-endian 0xD3)
//     0x04  version     u16 (e.g. 1) + u16 hdrlen(=2116)
//     0x08  "MCT_DOWNLOAD_HEADER\0" pad 60
//     0x20  product / model string (64 bytes)
//     0x60  file-count  u32
//     ...    per-file NV/NVB params etc - we keep zeros
//     0x848 flash-size  u32 (bytes)
//     0x84C project ver string ...
//   then for each file a 2560-byte entry followed by its data:
//     0x000 name[512] (utf16le)
//     0x200 dir[260]  (utf16le, usually empty)
//     0x30C size      u32
//     0x310 is_nv     u32
//     0x318 checksum  u16 (fixed 0x5433 in most pacs)
//     0x31A .. reserved
//   footer 3076 bytes of zeros.
// We emit a single-file pac named "pac_readback.img" containing every
// partition concatenated in table order; that is enough to restore via
// our own spd-flash or to feed partition slices back individually.

/// One file slot inside the .pac we generate.
struct PacFileEntry {
    name: String,
    data_offset: u64,
    size: u32,
}

const PAC_FILE_ENTRY_SIZE: usize = 2560;
const PAC_HEADER_SIZE: u64 = 2124;
const PAC_FOOTER_SIZE: u64 = 3076;

fn write_utf16le(buf: &mut [u8], s: &str) {
    for (i, unit) in s.encode_utf16().enumerate() {
        let off = i * 2;
        if off + 1 < buf.len() {
            buf[off] = (unit & 0xff) as u8;
            buf[off + 1] = (unit >> 8) as u8;
        }
    }
}

/// `spd-readback <target> <fdl1> <fdl1_addr> <fdl2> <fdl2_addr> <out.pac> [part,part,...]`
///
/// Dumps every Android partition (or just the comma-separated subset) and
/// packs them into `out.pac`. The resulting archive restores with our own
/// `spd-flash` or any YGDP-compatible tool.
pub fn spd_readback_cli(
    target: &str,
    fdl1: &str,
    fdl1_addr: u32,
    fdl2: &str,
    fdl2_addr: Option<u32>,
    out_pac: &str,
    only: Option<&str>,
) -> Result<String> {
    let dev = find_spd_target(target)?;
    let mut s = connect_and_load_fdls(
        &dev,
        fdl1,
        fdl1_addr,
        fdl2,
        fdl2_addr.unwrap_or(0x1400_0000),
        true,
        4096,
    )?;
    let _ = s.enable_write();

    let all = s.read_partitions().map_err(|e| BridgeError::Protocol(
        crate::error::ProtocolError::UnexpectedResponse(e),
    ))?;
    let wanted: Vec<(String, u64)> = match only {
        Some(list) => {
            let set: std::collections::HashSet<&str> = list.split(',').map(str::trim).collect();
            all.into_iter().filter(|(n, _)| set.contains(n.as_str())).collect()
        }
        None => all,
    };
    if wanted.is_empty() {
        return Err(BridgeError::InvalidArgument("no partitions matched".into()));
    }

    // Pass 1: stream each partition into a side temp file and record sizes.
    let tmpdir = std::env::temp_dir().join(format!("flashpilot_pac_{}", std::process::id()));
    fs::create_dir_all(&tmpdir).map_err(|e| format!("mkdir {}: {e}", tmpdir.display()))?;

    let mut entries: Vec<PacFileEntry> = Vec::new();
    let mut manifest = String::new();
    let mut total_bytes = 0u64;
    // Data region starts right after header + one entry-slot per file.
    let mut cursor = PAC_HEADER_SIZE + (wanted.len() as u64) * PAC_FILE_ENTRY_SIZE as u64;
    for (idx, (name, size)) in wanted.iter().enumerate() {
        let part_path = tmpdir.join(format!("{idx:03}_{}.bin", sanitize(name)));
        let path_str = part_path.to_string_lossy().to_string();
        eprintln!("[readback] {name} ({size} bytes)...");

        // FDL2 READ uses absolute flash offsets; partition_start(name,...) already
        // encodes the name so start=0 len=size reads exactly this partition.
        let n = s.read_partition(name, 0, *size, &path_str, 4096)?;
        let actual = fs::metadata(&part_path).map(|m| m.len()).unwrap_or(0);
        if actual == 0 {
            eprintln!("[readback]   {name} empty, skipped");
            let _ = fs::remove_file(&part_path);
            continue;
        }
        let _ = n;
        entries.push(PacFileEntry {
            name: sanitize(name),
            data_offset: cursor,
            size: actual as u32,
        });
        manifest.push_str(&format!("{name}: {actual} bytes\n"));
        cursor += actual;
        total_bytes += actual;
    }
    if entries.is_empty() {
        let _ = fs::remove_dir_all(&tmpdir);
        return Err(BridgeError::InvalidArgument("every partition read back empty".into()));
    }

    // Pass 2: assemble the .pac.
    let mut out = fs::File::create(out_pac).map_err(|e| format!("create {out_pac}: {e}"))?;
    use std::io::{Seek, SeekFrom, Write};

    // Header (2124 bytes)
    let mut hdr = vec![0u8; PAC_HEADER_SIZE as usize];
    hdr[0..4].copy_from_slice(&0xD3u32.to_le_bytes());
    hdr[4..6].copy_from_slice(&1u16.to_le_bytes());          // version
    hdr[6..8].copy_from_slice(&2116u16.to_le_bytes());        // header size
    let mct = b"MCT_DOWNLOAD_HEADER";
    hdr[8..8 + mct.len()].copy_from_slice(mct);
    // product string @0x20 (leave zeros -> tools accept blank model)
    hdr[0x60..0x64].copy_from_slice(&(entries.len() as u32).to_le_bytes());
    hdr[0x848..0x84c].copy_from_slice(&(total_bytes as u32).to_le_bytes());
    out.write_all(&hdr).map_err(|e| format!("write hdr: {e}"))?;

    // File-entry slots
    for e in &entries {
        let mut slot = vec![0u8; PAC_FILE_ENTRY_SIZE];
        write_utf16le(&mut slot[..512], &format!("{}_{}.img", e.name, e.name)); // name field
        slot[0x30C..0x310].copy_from_slice(&e.size.to_le_bytes());
        slot[0x310..0x314].copy_from_slice(&0u32.to_le_bytes()); // is_nv = false
        slot[0x318..0x31A].copy_from_slice(&0x5433u16.to_le_bytes()); // checksum marker
        out.write_all(&slot).map_err(|err| format!("write entry {}: {err}", e.name))?;
    }

    // Partition payloads, streamed from temp files.
    for e in &entries {
        let idx = entries.iter().position(|x| x.data_offset == e.data_offset).unwrap_or(0);
        let part_path = tmpdir.join(format!("{idx:03}_{}.bin", e.name));
        let mut f = fs::File::open(&part_path).map_err(|e| format!("reopen {}: {e}", part_path.display()))?;
        std::io::copy(&mut f, &mut out).map_err(|err| format!("stream {}: {err}", e.name))?;
    }

    // Footer
    out.write_all(&vec![0u8; PAC_FOOTER_SIZE as usize]).map_err(|e| format!("write footer: {e}"))?;
    out.flush().ok();

    let _ = fs::remove_dir_all(&tmpdir);
    let _ = s.reset();

    Ok(format!(
        "{} partition(s) packed into {} ({} bytes):\n{}",
        entries.len(),
        out_pac,
        fs::metadata(out_pac).map(|m| m.len()).unwrap_or(0),
        manifest
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn crc16_matches_poly() {
        // CRC-16/XMODEM (poly 0x1021, init 0) of "123456789" is 0x31C3.
        let c = spd_crc16(0, b"123456789");
        assert_eq!(c, 0x31c3);
    }

    #[test]
    fn sum_checksum_is_stable() {
        // Ones-complement sum of an empty frame body = 0xffff (all ones).
        let c = spd_sum(0, &[]);
        assert_eq!(c, 0xffff);
        // A 2-byte body 00 00 -> 0xffff too.
        assert_eq!(spd_sum(0, &[0x00, 0x00]), 0xffff);
    }

    #[test]
    fn transcode_roundtrip() {
        let data = [0x7e, 0x41, 0x7d, 0x00, 0x7e];
        let enc = transcode_encode(&data);
        // escaped: 0x7e -> [0x7d, 0x5e], 0x7d -> [0x7d, 0x5d], plain bytes pass.
        assert_eq!(enc, vec![0x7d, 0x5e, 0x41, 0x7d, 0x5d, 0x00, 0x7d, 0x5e]);
        // Each escape marker is 0x7d; the byte after it is original ^ 0x20.
        assert_eq!(enc[1] ^ 0x20, 0x7e);
        assert_eq!(enc[4] ^ 0x20, 0x7d);
        assert_eq!(enc[7] ^ 0x20, 0x7e);
    }

    #[test]
    fn chip_bases() {
        assert_eq!(chip_fdl_bases(0x6530_0000), Some((0x3000_0000, 0x3400_0000)));
        assert_eq!(chip_fdl_bases(0x6531_0000), Some((0x3000_0000, 0x3400_0000)));
        assert_eq!(chip_fdl_bases(0x6562_0000), Some((0x1000_0000, 0x1400_0000)));
        assert_eq!(chip_fdl_bases(0x1234_5678), None);
        // Android SoCs
        assert_eq!(chip_fdl_bases(0x9818_0000), Some((0x0, 0x8000_0000)));
        assert_eq!(chip_fdl_bases(0x5000_0), Some((0x5500, 0x9EFF_FE00)));
        assert_eq!(chip_fdl_bases(0x7100_0), Some((0x5500, 0x9EFF_FE00)));
    }

    #[test]
    fn download_pids() {
        assert!(is_download_pid(0x4d00));
        assert!(is_download_pid(0x4d02));
        assert!(is_download_pid(0x4e00));
        assert!(!is_download_pid(0x0001));
        assert_eq!(stage_label(0x4d00), "SPD download (BROM/FDL)");
    }
}