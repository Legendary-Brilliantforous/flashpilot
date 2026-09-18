//! Actionable error explanations for Samsung download-mode protocol errors.
//!
//! Raw protocol errors ("BOOTLOADER_FAIL ack=-5", "bulk read: timeout",
//! "Resource busy") are meaningless to ordinary users. This module converts
//! every known failure class into (why, fix) pairs and is wired into the
//! CLI error output and the flash flows' stderr hints.

/// One actionable error explanation.
pub struct Explanation {
    /// Why this error happened (protocol-level cause, plain language).
    pub why: String,
    /// What the user should do about it (concrete steps).
    pub fix: String,
}

/// Match a raw error string against the known Samsung download-mode failure
/// classes. Returns None for unknown errors (caller keeps the raw message).
pub fn explain_error(err: &str) -> Option<Explanation> {
    let lower = err.to_lowercase();

    // ---- USB transport classes ----
    if lower.contains("resource busy") || lower.contains("claim iface") {
        let adb_holder = lower.contains("adb server") || lower.contains("adb");
        let why = if adb_holder {
            "The system adb server (running from your adb command or another tool) is holding the phone's ADB interface claimed - FlashPilot's native ADB cannot coexist with an exclusive claim.".to_string()
        } else {
            "Another driver (cdc_acm, ModemManager) or process is holding the phone's USB port, so FlashPilot cannot claim it.".to_string()
        };
        let fix = if adb_holder {
            "FlashPilot kills the system adb server automatically and retries (`adb kill-server` is a host-side operation - your phone stays connected). If it persists, replug and retry.".to_string()
        } else {
            "Replug the phone; if it persists run `sudo systemctl stop ModemManager`, then retry. The latest .deb installs udev rules that keep ModemManager away.".to_string()
        };
        return Some(Explanation { why, fix });
    }
    if lower.contains("bulk read: operation timed out") || lower.contains("bulk write: operation timed out") || lower.contains("timed out") {
        return Some(Explanation {
            why: "The bootloader did not answer in time - either the phone is on the Warning screen (not yet in Download mode), a bad cable/hub dropped frames, or the cdc_acm kernel module is interfering with bulk transfers.".into(),
            fix: "Press Volume Up on the phone to enter the blue 'Downloading...' screen, use a direct motherboard USB port (no hub), and retry. If it still times out: `sudo rmmod cdc_acm` and retry.".into(),
        });
    }
    if lower.contains("no device") || lower.contains("device not found") {
        return Some(Explanation {
            why: "No Samsung phone in Download mode is visible on the USB bus right now (the phone may have rebooted out of Download mode or re-enumerated with a new address).".into(),
            fix: "Power off, hold Volume Down + Power, press Volume Up to the 'Downloading...' screen, keep it plugged, and retry.".into(),
        });
    }
    if lower.contains("overflow") {
        return Some(Explanation {
            why: "The bootloader sent a full max-packet-size bulk packet that a smaller read buffer could not hold (a known Samsung Download-mode quirk).".into(),
            fix: "Update to the latest FlashPilot - reads are always 512-byte buffered. If it persists, report the device model.".into(),
        });
    }
    if lower.contains("pipe") || lower.contains("stall") {
        return Some(Explanation {
            why: "The USB endpoint stalled - the bootloader rejected or wedged on the last transfer (often a session left half-open by an earlier failed attempt).".into(),
            fix: "Replug the phone to force re-enumeration and retry; FlashPilot also auto-rescues with a blind EndSession first.".into(),
        });
    }

    // ---- Bootloader protocol classes ----
    if lower.contains("-5") || lower.contains("bootloader fail") {
        if lower.contains("endsequence") || lower.contains("end sequence") || lower.contains("commit") {
            return Some(Explanation {
                why: "The bootloader is still validating previously written partitions (async md5hdr/secure-check) and reported 'busy' (-5) for the commit - the data itself is already written.".into(),
                fix: "Wait a few seconds and retry the same step - FlashPilot retries with backoff automatically. Do not unplug during validation.".into(),
            });
        }
        return Some(Explanation {
            why: "The bootloader rejected the command (BOOTLOADER_FAIL). Common causes: firmware not built for this exact model, Anti-Rollback (SWREV) refusing an older revision, or a corrupted archive.".into(),
            fix: "Verify the firmware matches your exact model (dial *#1234#), use a firmware with equal or higher binary version (SVN), and re-verify the archive checksum.".into(),
        });
    }
    if lower.contains("secure check fail") || lower.contains("swrev") || lower.contains("anti-rollback") {
        return Some(Explanation {
            why: "Samsung Anti-Rollback protection blocked the write: the device bootloader refuses software older than its current security revision.".into(),
            fix: "Flash firmware with an equal or higher binary version (SVN/revision). Downgrades are only possible up to the device's allowed rollback floor.".into(),
        });
    }
    if lower.contains("md5") || lower.contains("trailer") {
        return Some(Explanation {
            why: "The firmware archive's embedded checksum does not match its contents - the .tar.md5 file is corrupt or was modified after download.".into(),
            fix: "Re-download the firmware and do not rename the archive before flashing.".into(),
        });
    }
    if lower.contains("pit") && (lower.contains("match") || lower.contains("not found") || lower.contains("unknown")) {
        return Some(Explanation {
            why: "An archive partition has no matching partition in the device's PIT - the firmware is probably for a different model or variant.".into(),
            fix: "Check your exact model (dial *#1234#) and use matching firmware, or pass --allow-unknown to skip unmatched entries deliberately.".into(),
        });
    }
    if lower.contains("permission") || lower.contains("access") && lower.contains("denied") {
        return Some(Explanation {
            why: "Your Linux user has no permission to open the phone's USB device node (udev rules missing or the plugdev group membership is stale).".into(),
            fix: "Run `sudo bash root/setup-usb.sh` (or reinstall the latest .deb), then replug. Run `flashpilot-bridge setup-check` to diagnose the exact problem.".into(),
        });
    }
    None
}

/// Render an explanation (or the raw error) as a user-facing hint block.
pub fn render(err: &str) -> String {
    match explain_error(err) {
        Some(e) => format!(
            "\n[why] {}\n[fix] {}",
            e.why,
            e.fix
        ),
        None => String::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn usb_classes_map_to_explanations() {
        for err in [
            "claim iface: Resource busy",
            "bulk read: Operation timed out",
            "device not found (attempt 0)",
            "LIBUSB_ERROR_OVERFLOW",
            "pipe: stall",
        ] {
            let e = explain_error(err).unwrap_or_else(|| panic!("no explanation for {err}"));
            assert!(!e.why.is_empty());
            assert!(!e.fix.is_empty());
        }
    }

    #[test]
    fn bootloader_classes_map_to_explanations() {
        for err in [
            "EndSequenceFlash: ack -5 (busy)",
            "bootloader fail during file part",
            "Secure check fail :boot",
            "md5 trailer mismatch",
            "PIT: partition 'foo' not found in PIT",
            "no permissions (USB claim failed)",
        ] {
            let e = explain_error(err).unwrap_or_else(|| panic!("no explanation for {err}"));
            assert!(!e.why.is_empty());
            assert!(!e.fix.is_empty());
        }
    }

    #[test]
    fn unknown_errors_return_none() {
        assert!(explain_error("some totally unrelated error").is_none());
    }

    #[test]
    fn render_includes_why_and_fix() {
        let out = render("claim iface: Resource busy");
        assert!(out.contains("[why]"));
        assert!(out.contains("[fix]"));
        assert!(render("unrelated").is_empty());
    }
}
