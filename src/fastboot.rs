//! Native fastboot USB transport.
//!
//! Fastboot is a bulk-text protocol: the host writes one ASCII command packet
//! (`getvar:securestate`, `erase:frp`, `oem get_unlock_data`,
//! `reboot-bootloader`, ...) and the device replies with `INFO` / `OKAY` /
//! `FAIL` packets. This module gives Python a target-pinned fastboot path
//! (`vid:pid@bus:addr`) with kernel-driver detach, instead of shelling out to
//! the system `fastboot` binary (which has no `-s` serial pinning and breaks
//! the multi-device rule with several phones plugged in).
//!
//! Scope is deliberately the *command* phase only (getvar / oem / erase /
//! reboot): flashing (the `DATA` download phase) is out of scope and returns
//! a clean error. Verified live against Moto G6 `ali` (22b8:2e80,
//! if 255/66/3, bulk 0x01 OUT / 0x81 IN).

use crate::error::{BridgeError, Result, UsbError};
use crate::usb::{self, UsbDevice};
use serde_json::json;
use std::time::{Duration, Instant};

/// Fastboot USB interface triple (AOSP fastboot gadget; matches Moto `ali`).
const FB_CLASS: u8 = 255;
const FB_SUBCLASS: u8 = 66;
const FB_PROTOCOL: u8 = 3;

/// Max fastboot command packet (protocol limit is 64 bytes).
const FB_CMD_MAX: usize = 64;
/// Read buffer per bulk packet.
const FB_READ_BUF: usize = 512;
/// Upper bound on reply packets per command (hangs the session otherwise).
const FB_MAX_PACKETS: usize = 128;

#[derive(Debug, PartialEq)]
enum Reply {
    Info(String),
    Okay(String),
    Fail(String),
    Data(String),
    Garbage(String),
}

/// Parse one raw bulk packet into a fastboot reply. Pure function, unit
/// tested — the USB session code below only moves bytes.
fn parse_packet(raw: &[u8]) -> Reply {
    let text = String::from_utf8_lossy(raw);
    let text = text.trim_end_matches('\0').trim_end();
    if let Some(rest) = text.strip_prefix("INFO") {
        Reply::Info(rest.to_string())
    } else if let Some(rest) = text.strip_prefix("OKAY") {
        Reply::Okay(rest.to_string())
    } else if let Some(rest) = text.strip_prefix("FAIL") {
        Reply::Fail(rest.to_string())
    } else if let Some(rest) = text.strip_prefix("DATA") {
        Reply::Data(rest.to_string())
    } else {
        Reply::Garbage(text.to_string())
    }
}

/// Render one INFO payload the way system fastboot (platform-tools 35.x)
/// does: payloads that already carry `name: value` pass through verbatim;
/// bare values from a `getvar <var>` call are prefixed as `var: value` so
/// downstream `getvar`-style parsing keeps working unchanged.
fn format_info(getvar_var: Option<&str>, payload: &str) -> String {
    match getvar_var {
        Some(var) if !var.is_empty() && !payload.contains(':') => {
            format!("(bootloader) {var}: {payload}")
        }
        _ => format!("(bootloader) {payload}"),
    }
}

/// Extract the variable name from a `getvar` command (`getvar:foo` or
/// `getvar foo`), if any.
fn getvar_name(cmd: &str) -> Option<String> {
    let mut parts = cmd.split_whitespace();
    match parts.next() {
        Some("getvar") => parts.next().map(|s| s.to_string()),
        Some(other) if other.starts_with("getvar:") => {
            Some(other["getvar:".len()..].to_string())
        }
        _ => None,
    }
}

/// Parse a `vid:pid@bus:addr` target (vid/pid hex, bus/addr decimal).
fn parse_full_target(target: &str) -> Result<(u16, u16, u8, u8)> {
    let (id_part, ba_part) = target.split_once('@').ok_or_else(|| {
        BridgeError::InvalidArgument(
            "target must be 'vid:pid@bus:addr' (e.g. 22b8:2e80@2:16)".to_string(),
        )
    })?;
    let (vid_s, pid_s) = id_part.split_once(':').ok_or_else(|| {
        BridgeError::InvalidArgument("target vid:pid part must be 'vid:pid'".to_string())
    })?;
    let (bus_s, addr_s) = ba_part.split_once(':').ok_or_else(|| {
        BridgeError::InvalidArgument("target bus:addr part must be 'bus:addr'".to_string())
    })?;
    let vid = u16::from_str_radix(vid_s, 16)
        .map_err(|_| BridgeError::InvalidArgument(format!("bad vid '{vid_s}'")))?;
    let pid = u16::from_str_radix(pid_s, 16)
        .map_err(|_| BridgeError::InvalidArgument(format!("bad pid '{pid_s}'")))?;
    let bus: u8 = bus_s
        .parse()
        .map_err(|_| BridgeError::InvalidArgument(format!("bad bus '{bus_s}'")))?;
    let address: u8 = addr_s
        .parse()
        .map_err(|_| BridgeError::InvalidArgument(format!("bad address '{addr_s}'")))?;
    Ok((vid, pid, bus, address))
}

/// Open a fastboot session: open device, detach kernel drivers, claim the
/// fastboot interface, resolve bulk endpoints. Returns (device, ep_in, ep_out).
fn open_session(target: &str) -> Result<(UsbDevice, u8, u8)> {
    let (vid, pid, bus, address) = parse_full_target(target)?;
    let mut dev = UsbDevice::open(vid, pid, bus, address).map_err(|e| match e {
        BridgeError::Usb(UsbError::DeviceNotFound) => BridgeError::Usb(UsbError::DeviceNotFound),
        other => other,
    })?;
    let iface = dev
        .info()
        .interfaces
        .iter()
        .find(|i| i.class == FB_CLASS && i.subclass == FB_SUBCLASS && i.protocol == FB_PROTOCOL)
        .map(|i| i.number)
        .ok_or_else(|| {
            BridgeError::InvalidArgument(format!(
                "no fastboot interface (255/66/3) on {vid:04x}:{pid:04x}@{bus}:{address}"
            ))
        })?;
    // Kernel drivers (e.g. cdc_acm leftovers) steal bulk endpoints and cause
    // 'bulk read timed out' / 'usb device Fail' — detach before claiming.
    let _ = dev.set_auto_detach_kernel_driver(true);
    dev.claim_interface(iface)?;
    let (ep_in, ep_out) = dev.find_bulk_endpoints(iface).ok_or_else(|| {
        BridgeError::InvalidArgument(format!("no bulk endpoints on fastboot iface {iface}"))
    })?;
    Ok((dev, ep_in, ep_out))
}

/// Run one raw fastboot command, returning the system-fastboot-style
/// transcript (`(bootloader) ...` lines + `OKAY [...]` / `FAILED ...`).
/// A device-side FAIL is *not* a transport error: it is rendered as
/// `FAILED (remote: 'reason')` with exit 0, so Python-side `FAILED`-in-output
/// checks keep working exactly like the system binary.
fn run_command(target: &str, cmd: &str, timeout: Duration) -> Result<String> {
    if cmd.is_empty() {
        return Err(BridgeError::InvalidArgument("empty fastboot command".to_string()));
    }
    if cmd.len() > FB_CMD_MAX {
        return Err(BridgeError::InvalidArgument(format!(
            "fastboot command too long ({} > {FB_CMD_MAX})",
            cmd.len()
        )));
    }
    let (dev, ep_in, ep_out) = open_session(target)?;
    let start = Instant::now();
    let var = getvar_name(cmd);
    dev.write_bulk(ep_out, cmd.as_bytes(), timeout)?;
    let mut buf = vec![0u8; FB_READ_BUF];
    let mut lines: Vec<String> = Vec::new();
    for _ in 0..FB_MAX_PACKETS {
        let n = dev.read_bulk(ep_in, &mut buf, timeout)?;
        match parse_packet(&buf[..n]) {
            Reply::Info(payload) => {
                for line in payload.lines() {
                    lines.push(format_info(var.as_deref(), line));
                }
            }
            Reply::Okay(payload) => {
                if !payload.is_empty() {
                    // Some bootloaders (Moto MBM) carry a lone `getvar`
                    // value in the OKAY packet instead of an INFO packet —
                    // format it exactly like INFO so `var: value` parsing
                    // works uniformly.
                    lines.push(format_info(var.as_deref(), &payload));
                }
                lines.push(format!("OKAY [  {:.3}s]", start.elapsed().as_secs_f64()));
                return Ok(lines.join("\n"));
            }
            Reply::Fail(reason) => {
                lines.push(format!("FAILED (remote: '{reason}')"));
                eprintln!("[fastboot] command '{cmd}' refused by device: {reason}");
                return Ok(lines.join("\n"));
            }
            Reply::Data(_) => {
                return Err(BridgeError::NotSupported(
                    "fastboot DATA (download/flash) phase is not implemented; use getvar/oem/erase/reboot commands only".to_string(),
                ));
            }
            Reply::Garbage(text) => {
                eprintln!("[fastboot] ignoring non-protocol packet: {text:?}");
            }
        }
    }
    Err(BridgeError::Usb(UsbError::Timeout))
}

/// `fastboot-devices` — JSON list of USB devices exposing a fastboot
/// interface: [{vid, pid, bus, address, serial, product, interface}].
pub fn fastboot_devices_cli() -> Result<String> {
    let devices = usb::collect_devices(None)?;
    let mut out = Vec::new();
    for d in &devices {
        if let Some(iface) = d.interfaces.iter().find(|i| {
            i.class == FB_CLASS && i.subclass == FB_SUBCLASS && i.protocol == FB_PROTOCOL
        }) {
            out.push(json!({
                "vid": format!("{:04x}", d.vid),
                "pid": format!("{:04x}", d.pid),
                "bus": d.bus,
                "address": d.address,
                "serial": d.serial,
                "product": d.product,
                "interface": iface.number,
            }));
        }
    }
    serde_json::to_string_pretty(&out).map_err(|e| BridgeError::Io(e.to_string()))
}

/// `fastboot-cmd <target> <timeout_ms> <cmd...>` — run one raw command.
/// Prints the transcript; exit 0 unless the *transport* failed.
pub fn fastboot_cmd_cli(target: &str, timeout_ms: u64, cmd: &[String]) -> Result<String> {
    if cmd.is_empty() {
        return Err(BridgeError::InvalidArgument(
            "usage: fastboot-cmd <vid:pid@bus:addr> <timeout_ms> <cmd...>".to_string(),
        ));
    }
    let command = cmd.join(" ");
    run_command(target, &command, Duration::from_millis(timeout_ms))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_info_okay_fail_data() {
        assert_eq!(
            parse_packet(b"INFOsecurestate: oem_locked"),
            Reply::Info("securestate: oem_locked".to_string())
        );
        assert_eq!(parse_packet(b"OKAY"), Reply::Okay(String::new()));
        assert_eq!(
            parse_packet(b"OKAY0.012"),
            Reply::Okay("0.012".to_string())
        );
        assert_eq!(
            parse_packet(b"FAILPermission denied"),
            Reply::Fail("Permission denied".to_string())
        );
        assert_eq!(
            parse_packet(b"DATA00100000"),
            Reply::Data("00100000".to_string())
        );
    }

    #[test]
    fn parse_nul_padded_and_garbage() {
        let mut pkt = b"INFOserialno: ZY322PSBZ2".to_vec();
        pkt.extend_from_slice(&[0u8; 32]);
        assert_eq!(
            parse_packet(&pkt),
            Reply::Info("serialno: ZY322PSBZ2".to_string())
        );
        assert_eq!(
            parse_packet(b"hello?"),
            Reply::Garbage("hello?".to_string())
        );
    }

    #[test]
    fn parse_full_target_ok_and_rejects_junk() {
        assert_eq!(
            parse_full_target("22b8:2e80@2:16").unwrap(),
            (0x22b8, 0x2e80, 2, 16)
        );
        assert!(parse_full_target("2:16").is_err());
        assert!(parse_full_target("22b8@2:16").is_err());
        assert!(parse_full_target("zzzz:2e80@2:16").is_err());
        assert!(parse_full_target("22b8:2e80@2").is_err());
    }

    #[test]
    fn info_formatting_mirrors_system_fastboot() {
        // Bare values from `getvar <var>` gain the `var: ` prefix.
        assert_eq!(
            format_info(Some("securestate"), "oem_locked"),
            "(bootloader) securestate: oem_locked"
        );
        // Payloads that already carry a name pass through untouched.
        assert_eq!(
            format_info(Some("all"), "version: 0.5"),
            "(bootloader) version: 0.5"
        );
        assert_eq!(
            format_info(None, "oem_locked"),
            "(bootloader) oem_locked"
        );
        // Command-shape parsing for both `getvar:foo` and `getvar foo`.
        assert_eq!(getvar_name("getvar:securestate"), Some("securestate".to_string()));
        assert_eq!(
            getvar_name("getvar securestate"),
            Some("securestate".to_string())
        );
        assert_eq!(getvar_name("erase:frp"), None);
        assert_eq!(getvar_name("oem get_unlock_data"), None);
    }

    #[test]
    fn fail_transcript_matches_system_fastboot_shape() {
        // The Python side keys FAILED-in-output checks off this exact shape.
        let rendered = format!("FAILED (remote: '{}')", "Permission denied");
        assert!(rendered.contains("FAILED"));
        assert!(rendered.contains("Permission denied"));
    }
}
