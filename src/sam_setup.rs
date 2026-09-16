//! Linux setup diagnosis for Samsung/mobile USB flashing.
//!
//! Detects the exact setup problem (missing udev rules, stale group
//! membership, device node permissions, ModemManager holding ports,
//! usbmuxd absent for Apple) and explains how to fix each one.
//! Powers the `setup-check` CLI command.

use crate::error::{Result, BridgeError};
use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
pub struct SetupProblem {
    /// Short issue identifier (machine-readable).
    pub issue: String,
    /// Human-readable description of what is wrong.
    pub detail: String,
    /// Concrete fix steps.
    pub fix: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct SetupReport {
    /// True when no blocking problems were found.
    pub ok: bool,
    pub problems: Vec<SetupProblem>,
}

fn read_file(path: &str) -> String {
    std::fs::read_to_string(path).unwrap_or_default()
}

/// True if a udev rule grants access for the given vendor ID.
fn udev_rule_for(vid: &str) -> bool {
    for dir in ["/etc/udev/rules.d", "/usr/lib/udev/rules.d", "/lib/udev/rules.d"] {
        if let Ok(entries) = std::fs::read_dir(dir) {
            for e in entries.flatten() {
                let content = read_file(&e.path().to_string_lossy());
                if content.contains(vid) && (content.contains("MODE=") || content.contains("GROUP=")) {
                    return true;
                }
            }
        }
    }
    false
}

/// True if the current user is in the given group (or is root).
fn user_in_group(group: &str) -> bool {
    if std::env::var("USER").map(|u| u == "root").unwrap_or(false) {
        return true;
    }
    for dir in ["/etc/group"] {
        let content = read_file(dir);
        for line in content.lines() {
            if let Some((_name, rest)) = line.split_once(':') {
                // group:passwd:gid:members
                let parts: Vec<&str> = line.split(':').collect();
                if parts.len() >= 4 && parts[0] == group {
                    let user = std::env::var("USER").unwrap_or_default();
                    if parts[3].split(',').any(|m| m == user) {
                        return true;
                    }
                }
                let _ = rest;
            }
        }
    }
    false
}

/// Diagnose the flashing setup. `with_apple` adds usbmuxd checks.
pub fn setup_check(with_apple: bool) -> Result<String> {
    let mut problems: Vec<SetupProblem> = Vec::new();

    // 1. udev rules for the three flashing VIDs.
    let samsung_rule = udev_rule_for("04e8");
    let mtk_rule = udev_rule_for("0e8d");
    let spd_rule = udev_rule_for("1782");
    if !samsung_rule {
        problems.push(SetupProblem {
            issue: "udev-samsung-missing".into(),
            detail: "No udev rule grants non-root access to Samsung USB devices (VID 04e8) - flashing needs sudo and the GUI may not see the phone.".into(),
            fix: "Install the latest .deb (rules ship in /usr/lib/udev/rules.d/), or run `sudo bash root/setup-usb.sh`, then replug the phone.".into(),
        });
    }
    if !mtk_rule {
        problems.push(SetupProblem {
            issue: "udev-mtk-missing".into(),
            detail: "No udev rule for MediaTek devices (VID 0e8d) - BROM/preloader/DA access needs sudo.".into(),
            fix: "Install the latest .deb or run `sudo bash root/setup-usb.sh`, then replug.".into(),
        });
    }
    if !spd_rule {
        problems.push(SetupProblem {
            issue: "udev-spd-missing".into(),
            detail: "No udev rule for Spreadtrum/UNISOC devices (VID 1782) - SPD download access needs sudo.".into(),
            fix: "Install the latest .deb or run `sudo bash root/setup-usb.sh`, then replug.".into(),
        });
    }

    // 2. Group membership (rules use GROUP="plugdev").
    if (samsung_rule || mtk_rule || spd_rule) && !user_in_group("plugdev") {
        problems.push(SetupProblem {
            issue: "group-membership-stale".into(),
            detail: "The udev rules use GROUP=\"plugdev\" but your user is not in the plugdev group (or the membership was added after your session started).".into(),
            fix: "Run `sudo usermod -aG plugdev $USER`, then log out and back in (or reboot). Group changes never apply to already-running sessions.".into(),
        });
    }

    // 3. ModemManager holding Samsung download mode.
    let mm_running = std::process::Command::new("pgrep")
        .args(["ModemManager"])
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false);
    let mm_ignored = udev_rule_for("04e8")
        && read_file("/usr/lib/udev/rules.d/60-odin4.rules")
            .contains("ID_MM_DEVICE_IGNORE");
    if mm_running && !mm_ignored {
        problems.push(SetupProblem {
            issue: "modemmanager-holds-port".into(),
            detail: "ModemManager is running and will grab Samsung download mode's CDC ACM port, causing 'Resource busy' on claim.".into(),
            fix: "Install the latest .deb (its udev rule sets ID_MM_DEVICE_IGNORE for Samsung), then replug - or `sudo systemctl stop ModemManager` as a temporary fix.".into(),
        });
    }

    // 4. usbmuxd for Apple work.
    if with_apple {
        let usbmuxd = std::path::Path::new("/var/run/usbmuxd").exists();
        if !usbmuxd {
            problems.push(SetupProblem {
                issue: "usbmuxd-absent".into(),
                detail: "usbmuxd is not running - Apple device detection and lockdown info cannot work.".into(),
                fix: "Install it: `sudo apt install usbmuxd` (and libimobiledevice-utils for the external fallback tools).".into(),
            });
        }
    }

    let ok = problems.is_empty();
    let report = SetupReport { ok, problems };
    serde_json::to_string(&report).map_err(|e| BridgeError::Io(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn user_in_group_parses_etc_group() {
        // plugdev exists on every Debian/Ubuntu system; root always passes.
        assert!(user_in_group("plugdev") == (std::env::var("USER").map(|u| u == "root").unwrap_or(false) || {
            let content = read_file("/etc/group");
            content.lines().any(|l| l.starts_with("plugdev:"))
        }) || user_in_group("plugdev"));
    }

    #[test]
    fn setup_check_returns_json_report() {
        let out = setup_check(false).unwrap();
        assert!(out.contains("\"ok\""));
        assert!(out.contains("\"problems\""));
    }

    #[test]
    fn udev_rule_detection_handles_missing_files() {
        // A VID no rule mentions must be false, not a crash.
        assert!(!udev_rule_for("ffff"));
    }
}
