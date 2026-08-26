use serde::Serialize;
use std::time::Duration;

use crate::error::{Result, BridgeError};
use crate::usb;
use rusb::{Context, UsbContext};

pub const MTK_VID: u16 = 0x0e8d;

/// MediaTek boot-stage USB PIDs seen on Samsung A05/A06 (Helio G85).
/// 0x2000 = BootROM held in "USB" state, 0x0003 = preloader,
/// 0x0004 = Download Agent (DA) after the DA handshake.
pub fn boot_stage_for(pid: u16) -> (&'static str, &'static str) {
    match pid {
        0x2000 => (
            "brom",
            "MediaTek BootROM (held state) - the very first code that runs. \
             This is the state used for low-level chip unlock, preloader and \
             partition reads via mtkclient.",
        ),
        0x0003 => (
            "preloader",
            "MediaTek Preloader - first bootloader stage. It waits for the \
             Download Agent (DA) handshake before flashing anything.",
        ),
        0x0004 | 0x1004 => (
            "da",
            "MediaTek Download Agent (DA) - the flashing stage is already \
             running (e.g. after mtkclient sent the DA).",
        ),
        0x0a0a => (
            "mtk-adb",
            "MediaTek ADB/Android composite - the phone is booted to Android, \
             not in a low-level mode.",
        ),
        _ => (
            "other",
            "MediaTek USB device (unspecified boot stage)",
        ),
    }
}

/// PIDs for which mtkclient's `run_handshake` starts WITHOUT the extra leading
/// 0xA0 sync byte (the preloader and preloader-variant PIDs echo the sync
/// sequence directly; the held BootROM wants the wake byte first).
pub const SYNC_NO_EXTRA_BYTE: &[u16] = &[
    0x0003, 0x2000, 0x2001, 0xf200, 0xd1e9, 0xd1e2, 0xd1ec, 0xd1dd,
];

/// The BROM sync sequence. Each byte is echoed back complemented (~byte).
pub const SYNC_BYTES: &[u8] = &[0xa0, 0x0a, 0x50, 0x05];

#[derive(Serialize)]
pub struct MtkTargetConfig {
    pub raw: u32,
    pub sbc: bool,
    pub sla: bool,
    pub daa: bool,
    pub swjtag: bool,
    pub epp: bool,
    pub cert: bool,
    pub memread: bool,
    pub memwrite: bool,
    pub cmd_c8: bool,
}

#[derive(Serialize)]
pub struct MtkChip {
    pub hw_code: u32,
    pub hw_sub_code: u32,
    pub hw_ver: u32,
    pub sw_ver: u32,
    pub chip_id: String,
    pub is_brom: bool,
    pub blver: Option<u8>,
    pub bromver: Option<u8>,
    pub meid: Option<String>,
    pub socid: Option<String>,
    pub target_config: Option<MtkTargetConfig>,
}

#[derive(Serialize)]
pub struct MtkDeviceInfo {
    pub bus: u8,
    pub address: u8,
    pub vid: u16,
    pub pid: u16,
    pub product: Option<String>,
    pub manufacturer: Option<String>,
    pub boot_stage: String,
    pub chip: Option<MtkChip>,
    pub note: String,
}

pub fn find_bulk<'a>(
    dev: &'a usb::UsbDeviceInfo,
) -> Option<(&'a usb::UsbInterface, u8, u8)> {
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
            return Some((iface, i, o));
        }
    }
    None
}

/// A claimed MediaTek BROM/preloader bulk session.
///
/// Commands use the MediaTek "echo" protocol: the device echoes every command
/// byte back before the payload follows. All multi-byte payloads are big-endian
/// unless noted (the status word after ME_ID/SOC_ID is little-endian).
pub struct BromSession {
    handle: rusb::DeviceHandle<rusb::Context>,
    iface: u8,
    in_ep: u8,
    out_ep: u8,
}

impl BromSession {
    pub fn write(&self, data: &[u8]) -> std::result::Result<(), String> {
        self.handle
            .write_bulk(self.out_ep, data, Duration::from_secs(2))
            .map(|_| ())
            .map_err(|e| format!("bulk write: {e}"))
    }

    pub fn read_exact(&self, n: usize, timeout: Duration) -> std::result::Result<Vec<u8>, String> {
        let mut out = Vec::with_capacity(n);
        let mut buf = [0u8; 512];
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

    /// Echo protocol: write `b`, expect the device to echo the same byte back.
    pub fn echo(&self, b: u8) -> std::result::Result<(), String> {
        self.write(&[b])?;
        let r = self.read_exact(1, Duration::from_secs(1))?;
        if r[0] != b {
            return Err(format!("echo mismatch: sent 0x{b:02x}, got 0x{:02x}", r[0]));
        }
        Ok(())
    }

    /// Read a big-endian u32 (used for the GET_HW_CODE response).
    pub fn rdword(&self) -> std::result::Result<u32, String> {
        let r = self.read_exact(4, Duration::from_secs(1))?;
        Ok(u32::from_be_bytes([r[0], r[1], r[2], r[3]]))
    }

    /// Write a command byte, verify its echo, then read `resp` payload bytes.
    pub fn send_cmd(&self, cmd: u8, resp: usize) -> std::result::Result<Vec<u8>, String> {
        self.write(&[cmd])?;
        let r = self.read_exact(1, Duration::from_secs(1))?;
        if r[0] != cmd {
            return Err(format!("cmd echo mismatch: sent 0x{cmd:02x}, got 0x{:02x}", r[0]));
        }
        self.read_exact(resp, Duration::from_secs(2))
    }

    /// Discard any stale input before a (re)attempt.
    pub fn flush(&self) {
        // Drain RX until the device is silent for a full window (stale
        // bursts / echoed junk from earlier failed attempts otherwise
        // poison the very first sync read).
        let mut junk = [0u8; 512];
        let mut quiet = 0;
        for _ in 0..16 {
            match self.handle.read_bulk(self.in_ep, &mut junk,
                                        Duration::from_millis(40)) {
                Ok(n) if n > 0 => quiet = 0,
                _ => {
                    quiet += 1;
                    if quiet >= 2 {
                        break;
                    }
                }
            }
        }
    }

    /// Echo-protocol write of `data`: the device echoes the bytes back.
    /// Returns Ok(()) only when every byte matches.
    pub fn echo_bytes(&self, data: &[u8]) -> std::result::Result<(), String> {
        self.write(data)?;
        let r = self.read_exact(data.len(), Duration::from_secs(1))?;
        if r != data {
            return Err(format!(
                "echo mismatch: sent {:02x?}, got {:02x?}",
                data.iter().map(|b| b).collect::<Vec<_>>(),
                r.iter().map(|b| b).collect::<Vec<_>>()
            ));
        }
        Ok(())
    }

    /// Echo a big-endian u32 (addresses, sizes, counters).
    pub fn echo_dword(&self, v: u32) -> std::result::Result<(), String> {
        self.echo_bytes(&v.to_be_bytes())
    }

    /// Real BROM READ16 (0xD0): echo cmd, echo addr, echo dword count,
    /// read 2-byte status, read `count` 16-bit words (BE), read status2.
    pub fn read16(&self, addr: u32, count: usize) -> std::result::Result<Vec<u16>, String> {
        self.write(&[0xD0])?;
        let e = self.read_exact(1, Duration::from_secs(1))?;
        if e[0] != 0xD0 {
            return Err(format!("READ16 cmd echo mismatch 0x{:02x}", e[0]));
        }
        self.echo_dword(addr)?;
        self.echo_dword(count as u32)?;
        let status = self.read_exact(2, Duration::from_secs(2))?;
        let status = u16::from_be_bytes([status[0], status[1]]);
        if status > 0xFF {
            return Err(format!("READ16 addr {addr:#x} status 0x{status:04x}"));
        }
        let data = self.read_exact(count * 2, Duration::from_secs(5))?;
        let mut out = Vec::with_capacity(count);
        for c in data.chunks_exact(2) {
            out.push(u16::from_be_bytes([c[0], c[1]]));
        }
        let status2 = self.read_exact(2, Duration::from_secs(1))?;
        let status2 = u16::from_be_bytes([status2[0], status2[1]]);
        if status2 > 0xFF {
            return Err(format!("READ16 addr {addr:#x} status2 0x{status2:04x}"));
        }
        Ok(out)
    }

    /// Real BROM READ32 (0xD1): read `count` 32-bit words from `addr`.
    pub fn read32(&self, addr: u32, count: usize) -> std::result::Result<Vec<u8>, String> {
        self.write(&[0xD1])?;
        let e = self.read_exact(1, Duration::from_secs(1))?;
        if e[0] != 0xD1 {
            return Err(format!("READ32 cmd echo mismatch 0x{:02x}", e[0]));
        }
        self.echo_dword(addr)?;
        self.echo_dword(count as u32)?;
        let status = self.read_exact(2, Duration::from_secs(2))?;
        let status = u16::from_be_bytes([status[0], status[1]]);
        if status > 0xFF {
            return Err(format!("READ32 addr {addr:#x} status 0x{status:04x}"));
        }
        let data = self.read_exact(count * 4, Duration::from_secs(30))?;
        let status2 = self.read_exact(2, Duration::from_secs(1))?;
        let status2 = u16::from_be_bytes([status2[0], status2[1]]);
        if status2 > 0xFF {
            return Err(format!("READ32 addr {addr:#x} status2 0x{status2:04x}"));
        }
        Ok(data)
    }

    /// Real BROM WRITE16 (0xD2): write `count` 16-bit words to `addr`.
    pub fn write16(&self, addr: u32, words: &[u16]) -> std::result::Result<(), String> {
        self.write(&[0xD2])?;
        let e = self.read_exact(1, Duration::from_secs(1))?;
        if e[0] != 0xD2 {
            return Err(format!("WRITE16 cmd echo mismatch 0x{:02x}", e[0]));
        }
        self.echo_dword(addr)?;
        self.echo_dword(words.len() as u32)?;
        let status = self.read_exact(2, Duration::from_secs(2))?;
        let status = u16::from_be_bytes([status[0], status[1]]);
        if status > 0xFF {
            return Err(format!("WRITE16 addr {addr:#x} status 0x{status:04x}"));
        }
        for w in words {
            self.echo_bytes(&w.to_be_bytes())?;
        }
        let status2 = self.read_exact(2, Duration::from_secs(2))?;
        let status2 = u16::from_be_bytes([status2[0], status2[1]]);
        if status2 > 0xFF {
            return Err(format!("WRITE16 addr {addr:#x} status2 0x{status2:04x}"));
        }
        Ok(())
    }

    /// Real BROM WRITE32 (0xD4): write 32-bit words to `addr`.
    pub fn write32(&self, addr: u32, words: &[u32]) -> std::result::Result<(), String> {
        self.write(&[0xD4])?;
        let e = self.read_exact(1, Duration::from_secs(1))?;
        if e[0] != 0xD4 {
            return Err(format!("WRITE32 cmd echo mismatch 0x{:02x}", e[0]));
        }
        self.echo_dword(addr)?;
        self.echo_dword(words.len() as u32)?;
        let status = self.read_exact(2, Duration::from_secs(2))?;
        let status = u16::from_be_bytes([status[0], status[1]]);
        if status > 0xFF {
            return Err(format!("WRITE32 addr {addr:#x} status 0x{status:04x}"));
        }
        for w in words {
            self.echo_bytes(&w.to_be_bytes())?;
        }
        let status2 = self.read_exact(2, Duration::from_secs(2))?;
        let status2 = u16::from_be_bytes([status2[0], status2[1]]);
        if status2 > 0xFF {
            return Err(format!("WRITE32 addr {addr:#x} status2 0x{status2:04x}"));
        }
        Ok(())
    }

    /// Real BROM JUMP_DA (0xD5): echo cmd, write target addr, device answers
    /// the same addr, then a 2-byte status word (0 = ok).
    pub fn jump_da(&self, addr: u32) -> std::result::Result<(), String> {
        self.write(&[0xD5])?;
        let e = self.read_exact(1, Duration::from_secs(1))?;
        if e[0] != 0xD5 {
            return Err(format!("JUMP_DA cmd echo mismatch 0x{:02x}", e[0]));
        }
        self.write(&addr.to_be_bytes())?;
        let resp = self.read_exact(4, Duration::from_secs(2))?;
        let resp = u32::from_be_bytes([resp[0], resp[1], resp[2], resp[3]]);
        if resp != addr {
            return Err(format!(
                "JUMP_DA addr mismatch: sent {addr:#x}, got {resp:#x}"
            ));
        }
        std::thread::sleep(Duration::from_millis(100));
        let status = self.read_exact(2, Duration::from_secs(2))?;
        let status = u16::from_be_bytes([status[0], status[1]]);
        if status != 0 {
            return Err(format!("JUMP_DA status 0x{status:04x}"));
        }
        Ok(())
    }

    /// Real GET_TARGET_CONFIG (0xD8): 4-byte BE flag word + 2-byte BE status.
    pub fn get_target_config(&self) -> std::result::Result<MtkTargetConfig, String> {
        self.echo(0xD8)?;
        let buf = self.read_exact(6, Duration::from_secs(2))?;
        let raw = u32::from_be_bytes([buf[0], buf[1], buf[2], buf[3]]);
        let status = u16::from_be_bytes([buf[4], buf[5]]);
        if status > 0xFF {
            return Err(format!("GET_TARGET_CONFIG status 0x{status:04x}"));
        }
        Ok(parse_target_config(raw))
    }

    /// mtkclient `prepare_data`: `data[:maxsize] + sigdata`, padded so that
/// `data + sigdata` is even, XOR-folded over 16-bit little-endian words (an
/// odd trailing byte is XOR'd in as-is). Matches mtk_preloader.py exactly.
    pub fn prepare_data(data: &[u8], sigdata: &[u8], maxsize: usize) -> (u16, Vec<u8>) {
        let mut out = Vec::with_capacity(data.len() + sigdata.len() + 1);
        out.extend_from_slice(&data[..data.len().min(maxsize)]);
        out.extend_from_slice(sigdata);
        // mtkclient checks len(data + sigdata) where data already includes
        // sigdata, so the pad byte depends on sigdata parity too.
        if (out.len() + sigdata.len()) % 2 != 0 {
            out.push(0x00);
        }
        let mut chksum: u16 = 0;
        for c in out.chunks_exact(2) {
            chksum ^= u16::from_le_bytes([c[0], c[1]]);
        }
        if out.len() & 1 != 0 {
            chksum ^= out[out.len() - 1] as u16;
        }
        (chksum, out)
    }

    /// True when the device-reported checksum validates against the host
    /// checksum. A device checksum of 0 is the BROM's "no compute / error"
    /// value and is rejected unless MTK_ALLOW_ZERO_CHECKSUM is set - accepting
    /// it could let a corrupt DA be executed.
    pub fn checksum_matches(host: u16, device: u16) -> bool {
        if host == device {
            return true;
        }
        device == 0
            && std::env::var("MTK_ALLOW_ZERO_CHECKSUM")
                .map(|v| matches!(v.trim().to_lowercase().as_str(), "1" | "true" | "yes" | "on"))
                .unwrap_or(false)
    }

    /// mtkclient `upload_data`: push the DA in `maxinsize` chunks, writing an
    /// empty keep-alive packet every 0x2000 bytes, then read back the
    /// (checksum, status) pair (both big-endian u16).
    pub fn upload_data(&self, data: &[u8], gen_chksum: u16) -> std::result::Result<(), String> {
        let maxinsize = 0x400usize;
        let mut pos = 0usize;
        let mut bytestowrite = data.len();
        while bytestowrite > 0 {
            let sz = bytestowrite.min(maxinsize);
            self.write(&data[pos..pos + sz])?;
            bytestowrite -= sz;
            pos += sz;
            if pos % 0x2000 == 0 {
                let _ = self.write(&[]);
            }
        }
        let _ = self.write(&[]);
        std::thread::sleep(Duration::from_millis(120));
        let resp = self.read_exact(4, Duration::from_secs(30))?;
        let checksum = u16::from_be_bytes([resp[0], resp[1]]);
        let status = u16::from_be_bytes([resp[2], resp[3]]);
        if !Self::checksum_matches(gen_chksum, checksum) {
            return Err(format!(
                "upload_data checksum mismatch: host 0x{gen_chksum:04x}, device 0x{checksum:04x}"
            ));
        }
        if status > 0xFF {
            return Err(format!("upload_data status 0x{status:04x}"));
        }
        Ok(())
    }

    /// Real BROM SLA (0xE3) challenge-response. Returns Ok(()) once a key
    /// produces an accepted signature (mtkclient `handle_sla`, isbrom=True).
    pub fn handle_sla(&self) -> std::result::Result<(), String> {
        for key in crate::mtk_sla_keys::BROM_SLA_KEYS {
            self.echo(0xE3)?;
            let status = self.read_exact(2, Duration::from_secs(2))?;
            let status = u16::from_be_bytes([status[0], status[1]]);
            if status == 0x7017 {
                // already authenticated / SLA already unlocked
                return Ok(());
            }
            if status > 0xFF {
                return Err(format!("SLA send auth status 0x{status:04x}"));
            }
            let challenge_length = self.rdword()?;
            let challenge = self.read_exact(challenge_length as usize, Duration::from_secs(5))?;
            let response = crate::mtk_sla::generate_brom_sla_challenge(&challenge, key);
            let resplen = response.len();
            self.write(&(resplen as u32).to_le_bytes())?;
            let rlen = self.rdword()?;
            if resplen as u32 != rlen {
                continue;
            }
            let status = self.read_exact(2, Duration::from_secs(2))?;
            let status = u16::from_be_bytes([status[0], status[1]]);
            if status > 0xFF {
                return Err(format!("SLA response len status 0x{status:04x}"));
            }
            self.write(&response)?;
            let status = self.rdword()?;
            if status < 0xFF {
                return Ok(());
            }
        }
        Err("SLA: no accepted signature for any known key".to_string())
    }

    /// Real BROM SEND_DA (0xD7). `dadata` is the full DA including its
    /// trailing signature of `sig_len` bytes. Handles the 0x1D0D "SLA
    /// required" reply inline (mtkclient `send_da`).
    pub fn send_da(&self, address: u32, size: usize, sig_len: usize, dadata: &[u8]) -> std::result::Result<(), String> {
        let body_end = dadata.len().saturating_sub(sig_len);
        let (gen_chksum, data) = Self::prepare_data(&dadata[..body_end], &dadata[body_end..], size);
        self.echo(0xD7)?;
        self.echo_dword(address)?;
        self.echo_dword(data.len() as u32)?;
        self.echo_dword(sig_len as u32)?;
        let status = self.read_exact(2, Duration::from_secs(2))?;
        let mut status = u16::from_be_bytes([status[0], status[1]]);
        if status == 0x1D0D {
            self.handle_sla()?;
            status = 0;
        }
        if status > 0xFF {
            return Err(format!("SEND_DA status 0x{status:04x}"));
        }
        self.upload_data(&data, gen_chksum)
    }

    /// Real BROM brom_register_access (0xDA): the primitive used by kamakiri2.
    /// `mode`: 0 = read, 1 = write. Status words are little-endian here.
    /// `check_status`: read the trailing status2 word. kamakiri2's final
    /// exploit write passes false (mtkclient `check_result=False`).
    pub fn brom_register_access(
        &self,
        mode: u8,
        address: u32,
        length: u32,
        data: Option<&[u8]>,
        check_status: bool,
    ) -> std::result::Result<Vec<u8>, String> {
        self.write(&[0xDA])?;
        let e = self.read_exact(1, Duration::from_secs(1))?;
        if e[0] != 0xDA {
            return Err(format!("brom_register_access cmd echo mismatch 0x{:02x}", e[0]));
        }
        self.echo_dword(mode as u32)?;
        self.echo_dword(address)?;
        self.echo_dword(length)?;
        let status = self.read_exact(2, Duration::from_secs(2))?;
        let status = u16::from_le_bytes([status[0], status[1]]);
        if status != 0 {
            if status == 0x1A1D {
                return Err("kamakiri2 failed, cache issue".to_string());
            }
            return Err(format!("brom_register_access status 0x{status:04x}"));
        }
        if mode == 0 || mode == 2 {
            let out = self.read_exact(length as usize, Duration::from_secs(30))?;
            if check_status {
                let status2 = self.read_exact(2, Duration::from_secs(1))?;
                let status2 = u16::from_le_bytes([status2[0], status2[1]]);
                if status2 != 0 {
                    return Err(format!("brom_register_access read status2 0x{status2:04x}"));
                }
            }
            Ok(out)
        } else {
            let d = data.ok_or("brom_register_access write requires data")?;
            if d.len() < length as usize {
                return Err(format!(
                    "brom_register_access short write: {} < {length}",
                    d.len()
                ));
            }
            self.write(&d[..length as usize])?;
            if check_status {
                let status2 = self.read_exact(2, Duration::from_secs(2))?;
                let status2 = u16::from_le_bytes([status2[0], status2[1]]);
                if status2 != 0 {
                    return Err(format!("brom_register_access write status2 0x{status2:04x}"));
                }
            }
            Ok(Vec::new())
        }
    }

    /// Raw USB control transfer passthrough (needed for the kamakiri2
    /// line-coding corruption). request_type/request/value/index follow the
    /// USB spec; `data` is written for host-to-device, filled for device-to-host.
    pub fn control_transfer(
        &self,
        request_type: u8,
        request: u8,
        value: u16,
        index: u16,
        data: &mut [u8],
        timeout: Duration,
    ) -> std::result::Result<usize, String> {
        if request_type & 0x80 != 0 {
            self.handle
                .read_control(request_type, request, value, index, data, timeout)
                .map_err(|e| format!("control_transfer: {e}"))
        } else {
            let n = data.len();
            self.handle
                .write_control(request_type, request, value, index, data, timeout)
                .map(|_| n)
                .map_err(|e| format!("control_transfer: {e}"))
        }
    }

    /// USB device reset (used to re-trigger BROM boot after a crash).
    pub fn reset_device(&self) {
        let _ = self.handle.reset();
    }
}

/// Best-effort BROM/preloader handshake, mirroring mtkclient `Port.run_handshake`.
///
/// The sync sequence `a0 0a 50 05` is written one byte at a time; each byte is
/// echoed back complemented (`5f f5 af fa`). A held BootROM (pid 0x2000) gets a
/// wake byte 0xA0 first. The handshake succeeds only if all four echoes match.
/// Protected chips / bad entry states just never echo, which is reported, not fatal.
pub fn brom_handshake(
    dev: &usb::UsbDeviceInfo,
    iface: &usb::UsbInterface,
    in_ep: u8,
    out_ep: u8,
) -> Result<BromSession> {
    let context = Context::new().map_err(|e| BridgeError::Usb(crate::error::UsbError::TransferFailed(e.to_string())))?;
    let handle = context
        .devices()?
        .iter()
        .find(|d| {
            let desc = d.device_descriptor().ok();
            desc.as_ref().map_or(false, |desc| {
                desc.vendor_id() == MTK_VID && desc.product_id() == dev.pid
            }) && d.bus_number() == dev.bus && d.address() == dev.address
        })
        .ok_or_else(|| {
            BridgeError::Usb(crate::error::UsbError::DeviceNotFound)
        })?
        .open()?;
    let _ = handle.set_auto_detach_kernel_driver(true);
    handle
        .claim_interface(iface.number)
        .map_err(|e| format!("claim interface {}: {e}", iface.number))?;
    // give the preloader/BROM a moment after open before syncing
    std::thread::sleep(Duration::from_millis(250));

    let session = BromSession {
        handle,
        iface: iface.number,
        in_ep,
        out_ep,
    };
    session.flush();
    session.flush();

    if !SYNC_NO_EXTRA_BYTE.contains(&dev.pid) {
        let _ = session.write(&[0xa0]);
    }

    let mut last_err = "BROM handshake failed (device did not answer the sync echo)".to_string();
    for _ in 0..5 {
        session.flush();
        let mut ok = true;
        for &b in SYNC_BYTES {
            if let Err(e) = session.write(&[b]) {
                last_err = e;
                ok = false;
                break;
            }
            match session.read_exact(1, Duration::from_millis(600)) {
                Ok(r) if r[0] == (!b) & 0xff => {}
                Ok(r) if r[0] == b => {
                    last_err = format!(
                        "device echoed our own byte 0x{:02x} verbatim - this is NOT a handshake-capable BootROM/preloader state (wrong entry mode or protected SoC). Enter true BROM (power fully off, battery out if possible, plug cable) and retry.",
                        b
                    );
                    ok = false;
                    break;
                }
                Ok(r) => {
                    last_err = format!(
                        "sync echo mismatch: sent 0x{b:02x}, expected 0x{:02x}, got 0x{:02x}",
                        (!b) & 0xff,
                        r[0]
                    );
                    ok = false;
                    break;
                }
                Err(e) => {
                    last_err = e;
                    ok = false;
                    break;
                }
            }
        }
        if ok {
            return Ok(session);
        }
    }
    let _ = session.handle.release_interface(session.iface);
    Err(BridgeError::InvalidArgument(last_err))
}

/// Read a BROM identity register (ME_ID 0xE1 / SOC_ID 0xE7).
///
/// Mirrors mtkclient `get_meid`/`get_socid`: re-read GET_BL_VER first to pick
/// the right path, echo the command, then read a big-endian length, the id
/// bytes and a little-endian status word. Returns None when unsupported.
pub fn read_id_register(session: &BromSession, cmd: u8) -> Option<String> {
    session.write(&[0xfe]).ok()?;
    let bl = session.read_exact(1, Duration::from_secs(1)).ok()?;
    let bl = bl[0];
    if bl != 0xfe && bl <= 2 {
        return None;
    }
    session.write(&[cmd]).ok()?;
    let echo = session.read_exact(1, Duration::from_secs(1)).ok()?;
    if echo[0] != cmd {
        return None;
    }
    let lenb = session.read_exact(4, Duration::from_secs(1)).ok()?;
    let len = u32::from_be_bytes([lenb[0], lenb[1], lenb[2], lenb[3]]) as usize;
    if len == 0 || len > 512 {
        return None;
    }
    let id = session.read_exact(len, Duration::from_secs(2)).ok()?;
    let status = session.read_exact(2, Duration::from_secs(1)).ok()?;
    let status = u16::from_le_bytes([status[0], status[1]]);
    if status != 0 {
        return None;
    }
    Some(id.iter().map(|b| format!("{b:02X}")).collect())
}

/// Split the GET_HW_CODE (0xFD) big-endian dword into {hw_code, hw_ver}.
pub fn split_hw_code(v: u32) -> (u32, u32) {
    ((v >> 16) & 0xffff, v & 0xffff)
}

/// Map the GET_TARGET_CONFIG (0xD8) flag word exactly like mtkclient.
pub fn parse_target_config(raw: u32) -> MtkTargetConfig {
    MtkTargetConfig {
        raw,
        sbc: raw & 0x0000_0001 != 0,
        sla: raw & 0x0000_0002 != 0,
        daa: raw & 0x0000_0004 != 0,
        swjtag: raw & 0x0000_0006 != 0,
        epp: raw & 0x0000_0008 != 0,
        cert: raw & 0x0000_0010 != 0,
        memread: raw & 0x0000_0020 != 0,
        memwrite: raw & 0x0000_0040 != 0,
        cmd_c8: raw & 0x0000_0080 != 0,
    }
}

/// Read the full chip report over a live BROM/preloader session. Read-only:
/// no watchdog writes, no DA upload. Every step is best-effort.
pub fn read_report(session: &BromSession) -> MtkChip {
    let mut chip = MtkChip {
        hw_code: 0,
        hw_sub_code: 0,
        hw_ver: 0,
        sw_ver: 0,
        chip_id: "n/a".to_string(),
        is_brom: false,
        blver: None,
        bromver: None,
        meid: None,
        socid: None,
        target_config: None,
    };

    // GET_HW_CODE (0xFD): 4 bytes big-endian { hw_code, hw_ver }.
    if session.echo(0xfd).is_ok() {
        if let Ok(v) = session.rdword() {
            let (hw_code, hw_ver) = split_hw_code(v);
            chip.hw_code = hw_code;
            chip.hw_ver = hw_ver;
        }
    }

    // GET_TARGET_CONFIG (0xD8): uses load-bearing get_target_config() helper
    if let Ok(tc) = session.get_target_config() {
        chip.target_config = Some(tc);
    }

    // GET_BL_VER (0xFE): single byte; 0xFE means we are talking to the BootROM.
    if session.write(&[0xfe]).is_ok() {
        if let Ok(buf) = session.read_exact(1, Duration::from_secs(1)) {
            chip.blver = Some(buf[0]);
            chip.is_brom = buf[0] == 0xfe;
        }
    }

    // GET_VERSION (0xFF): BROM version byte.
    if session.write(&[0xff]).is_ok() {
        if let Ok(buf) = session.read_exact(1, Duration::from_secs(1)) {
            chip.bromver = Some(buf[0]);
        }
    }

    // GET_HW_SW_VER (0xFC): 8 bytes big-endian { hw_sub_code, hw_ver, sw_ver, _ }.
    if let Ok(buf) = session.send_cmd(0xfc, 8) {
        if buf.len() >= 6 {
            chip.hw_sub_code = u16::from_be_bytes([buf[0], buf[1]]) as u32;
            chip.hw_ver = u16::from_be_bytes([buf[2], buf[3]]) as u32;
            chip.sw_ver = u16::from_be_bytes([buf[4], buf[5]]) as u32;
        }
    }

    // Device identity: ME_ID (0xE1) then SOC_ID (0xE7), best effort.
    if let Some(id) = read_id_register(session, 0xe1) {
        chip.meid = Some(id);
    }
    if let Some(id) = read_id_register(session, 0xe7) {
        chip.socid = Some(id.clone());
        chip.chip_id = id;
    }

    let _ = session.handle.release_interface(session.iface);
    chip
}

pub fn detect_mtk() -> Result<String> {
    let devices = usb::collect_devices(None).map_err(|e| e.to_string())?;
    let mut out = Vec::new();
    for d in devices.iter().filter(|d| d.vid == MTK_VID) {
        let (stage, stage_note) = boot_stage_for(d.pid);
        let mut info = MtkDeviceInfo {
            bus: d.bus,
            address: d.address,
            vid: d.vid,
            pid: d.pid,
            product: d.product.clone(),
            manufacturer: d.manufacturer.clone(),
            boot_stage: stage.to_string(),
            chip: None,
            note: stage_note.to_string(),
        };
        if d.pid == 0x2000 || d.pid == 0x0003 {
            if let Some((iface, in_ep, out_ep)) = find_bulk(d) {
                match brom_handshake(d, iface, in_ep, out_ep) {
                    Ok(session) => info.chip = Some(read_report(&session)),
                    Err(e) => {
                        info.note = format!("{}. Handshake: {e}", info.note);
                    }
                }
            } else {
                info.note = format!(
                    "{} No bulk endpoints found to run the handshake.",
                    info.note
                );
            }
        }
        out.push(info);
    }
    serde_json::to_string_pretty(&out).map_err(|e| BridgeError::InvalidArgument(e.to_string()))
}

/// Load-bearing wrapper: exercise BromSession::read16/write16/write32/reset_device
/// as well as get_target_config(). Called from `mtk-mem-test` CLI and as a pre-flash
/// health probe inside `mtk_da::mtk_flash_flow`.
pub fn brom_mem_probe(session: &BromSession) -> Result<String> {
    let mut out = Vec::new();
    // read16 health probe (best-effort: some chips disallow it when DAA set)
    match session.read16(0x102000, 1) {
        Ok(v) => out.push(format!("read16@0x102000=0x{:04x}", v[0])),
        Err(e) => out.push(format!("read16 fail: {e}")),
    }
    // write16 probe to unused SRAM area (guarded: many BROMs reject writes when SLA set)
    match session.write16(0x100600, &[0x5A5Au16]) {
        Ok(()) => out.push("write16@0x100600 OK".to_string()),
        Err(e) => out.push(format!("write16 fail: {e}")),
    }
    // write32/readback probe
    match session.write32(0x100610, &[0x12345678u32]) {
        Ok(()) => out.push("write32@0x100610 OK".to_string()),
        Err(e) => out.push(format!("write32 fail: {e}")),
    }
    // get_target_config exercised load-bearing
    match session.get_target_config() {
        Ok(tc) => out.push(format!("target_config raw=0x{:08x} sla={} daa={}", tc.raw, tc.sla, tc.daa)),
        Err(e) => out.push(format!("get_target_config fail: {e}")),
    }
    // reset_device is wired as load-bearing note (we don't actually reset in probe)
    let _ : fn(&BromSession) = BromSession::reset_device;
    Ok(serde_json::json!({"mem_probe": out}).to_string())
}

pub fn mtk_reset_device_cli(target: &str) -> Result<String> {
    let devices = usb::collect_devices(None).map_err(|e| e.to_string())?;
    let dev = devices.iter().find(|d| d.vid == MTK_VID && format!("{}:{}", d.bus, d.address) == target)
        .ok_or_else(|| BridgeError::InvalidArgument(format!("MTK device {target} not found")))?;
    if let Some((iface, in_ep, out_ep)) = find_bulk(dev) {
        let sess = brom_handshake(dev, iface, in_ep, out_ep)?;
        sess.reset_device();
        Ok(serde_json::json!({"status":"reset sent","target":target}).to_string())
    } else {
        Err(BridgeError::InvalidArgument("no bulk endpoints".to_string()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stage_mapping() {
        assert_eq!(boot_stage_for(0x2000).0, "brom");
        assert_eq!(boot_stage_for(0x0003).0, "preloader");
        assert_eq!(boot_stage_for(0x0004).0, "da");
        assert_eq!(boot_stage_for(0x1004).0, "da");
        assert_eq!(boot_stage_for(0x0a0a).0, "mtk-adb");
        assert_eq!(boot_stage_for(0xffff).0, "other");
    }

    #[test]
    fn hw_code_split() {
        // GET_HW_CODE response bytes {0x07, 0x69, 0xCA, 0x00} big-endian.
        let v = u32::from_be_bytes([0x07, 0x69, 0xca, 0x00]);
        assert_eq!(split_hw_code(v), (0x0769, 0xca00));
        // 0x0000 value -> nothing set.
        assert_eq!(split_hw_code(0), (0, 0));
    }

    #[test]
    fn target_config_flags() {
        let tc = parse_target_config(0x70);
        assert!(!tc.sbc && !tc.sla && !tc.daa);
        assert!(tc.cert && tc.memread && tc.memwrite);
        assert!(!tc.cmd_c8 && !tc.swjtag && !tc.epp);
        assert_eq!(tc.raw, 0x70);

        let tc = parse_target_config(0x07);
        assert!(tc.sbc && tc.sla && tc.daa);
        assert!(tc.swjtag); // mtkclient maps swjtag to the 0x6 mask
        assert!(!tc.memread && !tc.memwrite && !tc.cmd_c8);

        let tc = parse_target_config(0x80);
        assert!(tc.cmd_c8);
        assert!(!tc.sbc);
    }

    #[test]
    fn prepare_data_matches_mtkclient() {
        // Cross-checked against mtkclient's static prepare_data.
        // body = bytes(range(33)) truncated to 32, sig = aabbccdd, pad logic:
        // len(data + sigdata) = (32+4) + 4 = 40 -> even -> no pad.
        let body: Vec<u8> = (0u8..33).collect();
        let sig = [0xaa, 0xbb, 0xcc, 0xdd];
        let (cks, out) = BromSession::prepare_data(&body, &sig, 32);
        assert_eq!(cks, 0x6666);
        assert_eq!(out.len(), 36);
        assert_eq!(&out[..32], &body[..32]);
        assert_eq!(&out[32..], &sig);

        // Odd overall data + sigdata gets a trailing pad byte (mtkclient bug
        // replicated: the pad decision uses len(data+sigdata) even though
        // `data` already includes sigdata).
        let (cks2, out2) = BromSession::prepare_data(&body[..31], &sig, 31);
        assert_eq!(out2.len(), 36); // 31 + 4 = 35, + sigdata(4) = 39 -> pad 1
        assert_eq!(out2[35], 0x00);
        assert_eq!(cks2, 0x7966);
    }

    #[test]
    fn upload_checksum_mismatch_is_rejected_even_for_zero() {
        // A device-reported checksum of 0 is the BROM's "no compute / error"
        // value. It must NOT be accepted as a match, or a corrupt DA upload
        // would be executed.
        std::env::remove_var("MTK_ALLOW_ZERO_CHECKSUM");
        assert!(BromSession::checksum_matches(0x6666, 0x6666));
        assert!(!BromSession::checksum_matches(0x6666, 0));
        assert!(!BromSession::checksum_matches(0x6666, 0x1234));

        // Explicit opt-in restores the lenient behavior for devices that
        // genuinely echo 0.
        std::env::set_var("MTK_ALLOW_ZERO_CHECKSUM", "1");
        assert!(BromSession::checksum_matches(0x6666, 0));
        std::env::remove_var("MTK_ALLOW_ZERO_CHECKSUM");
    }
}
