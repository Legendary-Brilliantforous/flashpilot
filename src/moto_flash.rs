//! Motorola fastboot staged FRP (Moto G6 `ali` and friends).
//!
//! Strategy (Moto-M shape, all local, no server): flash signed stock
//! firmware in flashfile.xml order -> reboot -> up to 3 cycles, each
//! acting per the mode actually seen (ADB authorized -> wipe; ADB
//! unauthorized -> prompt the on-phone tap, then wipe; fastboot ->
//! state check + cache clear + reboot again; dark -> cable guidance).
//!
//! Honest scope, stated up front: every command below is a documented
//! local fastboot/ADB command. Moto-M's per-boot payload bytes come from
//! their server and were never visible client-side, so they are NOT
//! replicated here — and a clean signed flash plus reboots does not
//! itself enable ADB. If no ADB session appears in 3 cycles, the flow
//! stops and names the realistic route (Easy Login QR, `frp_fake_login*`,
//! which needs no exploit at all). Nothing here pretends otherwise.

use crate::error::{BridgeError, Result};
use std::path::Path;
use std::time::Duration;

// ---------------------------------------------------------------------------
// flashfile.xml runner (signed stock flash over fastboot).
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Default)]
pub struct FlashStep {
    pub op: String,
    pub partition: String,
    pub filename: String,
    pub var: String,
    pub md5: String,
}

fn parse_attr(tag: &str, key: &str) -> String {
    let needle = format!("{key}=\"");
    let Some(s) = tag.find(&needle) else {
        return String::new();
    };
    let rest = &tag[s + needle.len()..];
    let Some(e) = rest.find('"') else {
        return String::new();
    };
    rest[..e].to_string()
}

/// Parse `<step .../>` tags (machine-generated Motorola XML; a small
/// attribute scanner beats a full XML parser here and fails loudly on
/// anything unexpected).
pub fn parse_flashfile_xml(text: &str) -> Result<Vec<FlashStep>> {
    let mut steps = Vec::new();
    let mut rest = text;
    while let Some(s) = rest.find("<step") {
        // `<steps` (plural container) is not a step.
        let after = rest[s + 5..].chars().next().unwrap_or('>');
        if after != ' '
            && after != '\t'
            && after != '\n'
            && after != '\r'
            && after != '/'
            && after != '>'
        {
            rest = &rest[s + 5..];
            continue;
        }
        let tail = &rest[s..];
        let end = tail
            .find("/>")
            .map(|i| i + 2)
            .or_else(|| tail.find('>').map(|i| i + 1))
            .ok_or_else(|| {
                BridgeError::InvalidArgument("flashfile.xml: truncated <step>".to_string())
            })?;
        let tag = &tail[..end];
        let op = parse_attr(tag, "operation").to_lowercase();
        if op.is_empty() {
            return Err(BridgeError::InvalidArgument(
                "flashfile.xml: <step> without operation".to_string(),
            ));
        }
        steps.push(FlashStep {
            op,
            partition: parse_attr(tag, "partition"),
            filename: parse_attr(tag, "filename"),
            var: parse_attr(tag, "var"),
            md5: parse_attr(tag, "MD5").to_lowercase(),
        });
        rest = &tail[end..];
    }
    if steps.is_empty() {
        return Err(BridgeError::InvalidArgument(
            "flashfile.xml: no <step> entries".to_string(),
        ));
    }
    Ok(steps)
}

fn md5_hex(data: &[u8]) -> String {
    use md5::Digest;
    let mut h = md5::Md5::new();
    h.update(data);
    h.finalize().iter().map(|b| format!("{b:02x}")).collect()
}

/// Flash the stock firmware dir in flashfile.xml order. Every image is
/// MD5-verified first (a corrupt flash on a locked phone is a brick risk);
/// every step is printed Moto-M style before it runs.
pub fn flash_stock_fw(dir: &Path, target: &str, out: &mut Vec<String>) -> Result<()> {
    let text = std::fs::read_to_string(dir.join("flashfile.xml"))
        .map_err(|e| BridgeError::Io(format!("read flashfile.xml: {e}")))?;
    let steps = parse_flashfile_xml(&text)?;
    out.push(format!(
        "  flashfile.xml: {} steps from {}",
        steps.len(),
        dir.display()
    ));
    out.push("  NOTE: erase steps below WILL wipe userdata/modemst/cache.".to_string());
    let mut flash_failed = false;
    for (i, s) in steps.iter().enumerate() {
        let tag = format!("[{}/{}]", i + 1, steps.len());
        match s.op.as_str() {
            "getvar" => {
                out.push(format!("  {tag} getvar {}", s.var));
                crate::flows::fb_run(
                    target,
                    &format!("getvar {}", s.var),
                    Duration::from_secs(30),
                    out,
                );
            }
            "oem" => {
                out.push(format!("  {tag} oem {}", s.var));
                let t = crate::flows::fb_run(
                    target,
                    &format!("oem {}", s.var),
                    Duration::from_secs(60),
                    out,
                );
                if t.contains("FAILED") || t.starts_with("ERROR") {
                    return Err(BridgeError::DeviceState(
                        crate::error::DeviceStateError::WrongMode {
                            expected: format!("oem {} accepted", s.var),
                            actual: "bootloader refused".to_string(),
                        },
                    ));
                }
            }
            "flash" => {
                let path = dir.join(&s.filename);
                out.push(format!("  {tag} flash {} <- {}", s.partition, s.filename));
                let bytes = std::fs::read(&path)
                    .map_err(|e| BridgeError::Io(format!("read {}: {e}", path.display())))?;
                if !s.md5.is_empty() {
                    let got = md5_hex(&bytes);
                    if got != s.md5 {
                        return Err(BridgeError::Firmware(
                            crate::error::FirmwareError::ImageCorrupt(format!(
                                "{} MD5 mismatch (want {}, got {got}) — refusing to flash",
                                s.filename, s.md5
                            )),
                        ));
                    }
                    out.push("  md5 OK".to_string());
                }
                match crate::fastboot::flash_partition(
                    target,
                    &s.partition,
                    path.to_str().unwrap_or_default(),
                    Duration::from_secs(900),
                ) {
                    Ok(t) => {
                        for line in t.lines() {
                            out.push(format!("      {line}"));
                        }
                        if t.contains("FAILED") {
                            out.push(format!(
                                "  device refused flash {} — erase steps will be skipped (no wipe without gain)",
                                s.partition
                            ));
                            flash_failed = true;
                        }
                    }
                    Err(e) => {
                        return Err(BridgeError::DeviceState(
                            crate::error::DeviceStateError::WrongMode {
                                expected: format!("flash {} accepted", s.partition),
                                actual: format!("flash failed: {e}"),
                            },
                        ));
                    }
                }
            }
            "erase" => {
                if flash_failed {
                    out.push(format!(
                        "  {tag} erase {} — SKIPPED (earlier flash refused; wiping would destroy data for nothing)",
                        s.partition
                    ));
                    continue;
                }
                out.push(format!("  {tag} erase {}", s.partition));
                crate::flows::fb_run(
                    target,
                    &format!("erase {}", s.partition),
                    Duration::from_secs(120),
                    out,
                );
            }
            other => {
                return Err(BridgeError::InvalidArgument(format!(
                    "flashfile.xml: unsupported operation '{other}' — stopping before any guess"
                )));
            }
        }
    }
    out.push("  stock flash complete".to_string());
    Ok(())
}

// ---------------------------------------------------------------------------
// Staged flow.
// ---------------------------------------------------------------------------

pub struct MotoFbArgs {
    pub target: String,
    pub firmware_dir: String,
}

/// `moto_fb_factory_adb` — the Moto-M style reboot-payload cycle, all
/// local: `oem fb_mode_set` (factory bootmode flag) → reboot → wait for
/// the mode the phone actually comes up in → ADB authorized = wipe;
/// ADB unauthorized = tap prompt then wipe; fastboot = re-flag + reboot
/// again; nothing = report honestly. Ends with `fb_mode_clear` so the
/// phone doesn't stay stuck in factory bootmode. A clean flag cycle does
/// NOT itself enable ADB on devices whose factory mode ships no adbd —
/// the flow reports that honestly instead of pretending.
pub fn flow_moto_fb_factory_adb(target: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("MOTOROLA - FACTORY-BOOTMODE ADB CYCLE (Moto-M shape, all local)".to_string());
    out.push("  oem fb_mode_set -> reboot -> act per the mode seen (x3) ->".to_string());
    out.push("  wipe over authorized ADB -> fb_mode_clear restore.".to_string());
    let fb = match crate::flows::resolve_fastboot_target(target, Duration::from_secs(60), out) {
        Some(t) => t,
        None => {
            return Err(crate::error::BridgeError::DeviceState(
                crate::error::DeviceStateError::NotInDownloadMode,
            ));
        }
    };
    // The Moto-M decompile captures exactly this pair around the wipe.
    let set = crate::flows::fb_run(&fb, "oem fb_mode_set", Duration::from_secs(30), out);
    if set.contains("FAILED") || set.contains("ERROR") {
        out.push("  `oem fb_mode_set` refused — this bootloader does not".to_string());
        out.push("  expose the factory bootmode flag; the cycle cannot start.".to_string());
        return Ok(());
    }
    let mut wiped = false;
    for cycle in 1..=3 {
        out.push(format!(
            "CYCLE {cycle}/3 - reboot, then act per the mode seen"
        ));
        if let Some(f) = crate::flows::resolve_fastboot_target(target, Duration::from_secs(30), out)
        {
            crate::flows::fb_run(&f, "reboot", Duration::from_secs(30), out);
        } else {
            out.push("  no fastboot device right now — waiting".to_string());
        }
        match factory_cycle_wait(target, out) {
            FactorySee::Authorized(serial) => {
                out.push(format!("  ADB authorized ({serial}) - wiping FRP ..."));
                crate::flows::moto_adb_frp_wipe(&serial, out);
                crate::flows::adb_step(&serial, "reboot", Duration::from_secs(30), out);
                wiped = true;
                break;
            }
            FactorySee::Unauthorized => {
                out.push("  ADB present but NOT authorized - TAP 'Allow USB".to_string());
                out.push("  debugging' on the phone now (check 'always allow').".to_string());
                if let Some(serial) =
                    crate::flows::wait_authorized_adb(target, Duration::from_secs(120), out)
                {
                    out.push(format!("  authorized ({serial}) - wiping FRP ..."));
                    crate::flows::moto_adb_frp_wipe(&serial, out);
                    crate::flows::adb_step(&serial, "reboot", Duration::from_secs(30), out);
                    wiped = true;
                    break;
                }
                out.push("  still unauthorized - next cycle".to_string());
            }
            FactorySee::Fastboot(f) => {
                out.push("  fastboot is back - re-arming the factory flag".to_string());
                let s = crate::flows::fb_run(&f, "oem fb_mode_set", Duration::from_secs(30), out);
                if s.contains("FAILED") {
                    out.push("  flag refused - ending the cycle early".to_string());
                    break;
                }
            }
            FactorySee::Nothing => {
                out.push("  nothing on USB (cable? manual fastboot re-entry)".to_string());
            }
        }
    }
    // Restore the bootmode so the phone boots Android normally afterwards.
    if let Some(f) = crate::flows::resolve_fastboot_target(target, Duration::from_secs(20), out) {
        out.push("RESTORE - oem fb_mode_clear".to_string());
        crate::flows::fb_run(&f, "oem fb_mode_clear", Duration::from_secs(30), out);
    } else {
        out.push("  NOTE: fb_mode_clear NOT sent (no fastboot device) - if the".to_string());
        out.push("  phone loops in factory mode: Vol Down+Power -> fastboot ->".to_string());
        out.push("  re-run this flow (the clear runs even when no cycle succeeds).".to_string());
    }
    if wiped {
        out.push("Done. The phone should boot past FRP as a fresh device.".to_string());
        Ok(())
    } else {
        out.push("3 cycles done, no authorized ADB session appeared. A flag".to_string());
        out.push("cycle does not itself enable ADB when factory mode ships no".to_string());
        out.push(
            "adbd - the realistic route is the Easy Login QR (QR Provision window),".to_string(),
        );
        out.push("which needs no exploit at all.".to_string());
        Err(crate::error::BridgeError::DeviceState(
            crate::error::DeviceStateError::WrongMode {
                expected: "adb (authorized)".to_string(),
                actual: "no ADB session in 3 factory cycles".to_string(),
            },
        ))
    }
}

enum FactorySee {
    Authorized(String),
    Unauthorized,
    Fastboot(String),
    Nothing,
}

/// Wait up to ~150 s for whatever the rebooted phone enumerates as.
fn factory_cycle_wait(target: &str, out: &mut Vec<String>) -> FactorySee {
    if let Some(serial) = crate::flows::wait_authorized_adb(target, Duration::from_secs(150), out) {
        return FactorySee::Authorized(serial);
    }
    if crate::flows::adb_unauthorized_present() {
        return FactorySee::Unauthorized;
    }
    if let Some(f) = crate::flows::resolve_fastboot_target(target, Duration::from_secs(20), out) {
        return FactorySee::Fastboot(f);
    }
    FactorySee::Nothing
}

/// `moto_fb_frp` — Motorola fastboot staged FRP (Moto-M shape, all local):
/// MD5-verified signed stock flash -> reboot -> up to 3 cycles acting per
/// the mode actually seen -> ADB wipe when (and only when) a session is
/// authorized. See the module docs for the honest scope.
pub fn flow_moto_fb_frp(a: &MotoFbArgs, out: &mut Vec<String>) -> Result<()> {
    out.push("MOTOROLA - FASTBOOT STAGED FRP (flash + reboot cycles)".to_string());
    out.push("  Stage 0: MD5-verified signed stock flash (locked-OK when".to_string());
    out.push("           versions match; refusals abort with device lines).".to_string());
    out.push("  Stage 1 (x3 cycles): reboot, then act per the mode seen —".to_string());
    out.push("           ADB authorized -> wipe; ADB unauthorized -> tap".to_string());
    out.push("           prompt; fastboot -> state check + cache clear.".to_string());

    let firmware_dir = if !a.firmware_dir.is_empty() {
        a.firmware_dir.clone()
    } else {
        std::env::var("MOTO_FW_DIR")
            .unwrap_or_default()
            .trim()
            .to_string()
    };
    if firmware_dir.is_empty() {
        return Err(BridgeError::InvalidArgument(
            "need --firmware-dir <signed stock firmware> (or MOTO_FW_DIR)".to_string(),
        ));
    }

    // ---- Stage 0: signed stock flash.
    out.push("STAGE 0 - flash signed stock firmware (fastboot)".to_string());
    let fbt = crate::flows::resolve_fastboot_target(&a.target, Duration::from_secs(60), out)
        .ok_or_else(|| {
            BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
                expected: "fastboot".to_string(),
                actual: "no fastboot device for the stock flash".to_string(),
            })
        })?;
    flash_stock_fw(Path::new(&firmware_dir), &fbt, out)?;

    // ---- Stage 1: up to 3 reboot cycles.
    for cycle in 1..=3 {
        out.push(format!(
            "CYCLE {cycle}/3 - reboot (if in fastboot), then act per the mode seen"
        ));
        // Resolve fresh every cycle: bus:addr goes stale across reboots.
        if let Some(fb_now) =
            crate::flows::resolve_fastboot_target(&a.target, Duration::from_secs(30), out)
        {
            crate::flows::fb_run(&fb_now, "reboot", Duration::from_secs(30), out);
        } else {
            out.push("  no fastboot device right now — waiting for re-enumeration".to_string());
        }
        match cycle_wait(&a.target, out) {
            CycleSee::Authorized(serial) => {
                return wipe_and_done(&serial, out);
            }
            CycleSee::Unauthorized => {
                if tap_and_wipe(&a.target, out)? {
                    return Ok(());
                }
            }
            CycleSee::Fastboot(fb) => {
                cycle_payload(&fb, out);
            }
            CycleSee::Nothing => {
                out.push("  nothing on USB (cable? Vol Down + Power for fastboot)".to_string());
            }
        }
    }
    out.push("3 cycles done, no authorized ADB session appeared.".to_string());
    out.push("A clean flash + reboots does not itself enable ADB — the".to_string());
    out.push("realistic route is Easy Login QR (frp_fake_login*), which needs".to_string());
    out.push("no exploit at all.".to_string());
    Err(BridgeError::DeviceState(
        crate::error::DeviceStateError::WrongMode {
            expected: "adb (authorized)".to_string(),
            actual: "no ADB session in 3 cycles".to_string(),
        },
    ))
}

enum CycleSee {
    Authorized(String),
    Unauthorized,
    Fastboot(String),
    Nothing,
}

/// Wait up to ~150 s for whatever the rebooted phone enumerates as.
fn cycle_wait(target: &str, out: &mut Vec<String>) -> CycleSee {
    if let Some(serial) = crate::flows::wait_authorized_adb(target, Duration::from_secs(150), out) {
        return CycleSee::Authorized(serial);
    }
    if crate::flows::adb_unauthorized_present() {
        return CycleSee::Unauthorized;
    }
    if let Some(fb) = crate::flows::resolve_fastboot_target(target, Duration::from_secs(20), out) {
        return CycleSee::Fastboot(fb);
    }
    CycleSee::Nothing
}

/// Fastboot reappeared: state check + cache clear (both allowed ops),
/// then the next cycle reboots again.
fn cycle_payload(fb: &str, out: &mut Vec<String>) {
    out.push("  fastboot is back — stage payload: state check + cache clear".to_string());
    crate::flows::fb_run(fb, "getvar securestate", Duration::from_secs(20), out);
    crate::flows::fb_run(fb, "erase cache", Duration::from_secs(120), out);
}

/// ADB unauthorized: prompt the on-phone tap (Moto-M style), then wipe on
/// success. Returns Ok(true) when the wipe ran.
fn tap_and_wipe(target: &str, out: &mut Vec<String>) -> Result<bool> {
    out.push("  ADB present but NOT authorized — TAP 'Allow USB debugging'".to_string());
    out.push("  on the phone screen now (check 'always allow' if offered).".to_string());
    match crate::flows::wait_authorized_adb(target, Duration::from_secs(120), out) {
        Some(serial) => wipe_and_done(&serial, out).map(|_| true),
        None => {
            out.push("  still unauthorized — next cycle".to_string());
            Ok(false)
        }
    }
}

fn wipe_and_done(serial: &str, out: &mut Vec<String>) -> Result<()> {
    out.push(format!("  ADB authorized ({serial}) — wiping FRP ..."));
    crate::flows::moto_adb_frp_wipe(serial, out);
    crate::flows::adb_step(serial, "reboot", Duration::from_secs(30), out);
    out.push("Done. The phone should boot past FRP as a fresh device.".to_string());
    Ok(())
}

// ---------------------------------------------------------------------------
// Tests (synthetic inputs only — no hardware).
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn flashfile_parses_all_step_kinds() {
        let xml = r#"<?xml version="1.0" ?>
<flashing><header><phone_model model="ali"/></header>
<steps interface="AP">
<step operation="getvar" var="max-sparse-size"/>
<step operation="oem" var="fb_mode_set"/>
<step MD5="d091175147568e4f235978be7b299ef1" filename="gpt.bin" operation="flash" partition="partition"/>
<step operation="erase" partition="cache"/>
<step operation="oem" var="fb_mode_clear"/>
</steps>
</flashing>"#;
        let steps = parse_flashfile_xml(xml).unwrap();
        assert_eq!(steps.len(), 5);
        assert_eq!(steps[0].op, "getvar");
        assert_eq!(steps[0].var, "max-sparse-size");
        assert_eq!(steps[2].op, "flash");
        assert_eq!(steps[2].partition, "partition");
        assert_eq!(steps[2].filename, "gpt.bin");
        assert_eq!(steps[2].md5, "d091175147568e4f235978be7b299ef1");
        assert_eq!(steps[3].op, "erase");
        assert!(parse_flashfile_xml("<flashing></flashing>").is_err());
    }
}
