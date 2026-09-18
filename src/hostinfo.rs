//! Host-side eMMC/UFS health — native Rust.
//!
//! Replaces the Python path that shelled out to the system `mmc` binary
//! (`mmc extcsd read /dev/mmcblk0`): device health attributes are read
//! directly from sysfs (life_time, pre_eol_info) and block-device identity
//! (model, rev, cid) without an external tool.

use crate::error::{BridgeError, Result};
use serde::Serialize;

#[derive(Debug, Clone, Serialize, Default)]
pub struct HostEmmcHealth {
    /// eMMC life time estimate (device-reported A/B values, e.g. "0x01 0x01").
    pub life_time: String,
    /// eMMC pre-EOL info (0x01=normal .. 0x03=urgent).
    pub pre_eol_info: String,
    /// Block device model string (e.g. "SDW64G").
    pub model: String,
    /// Firmware revision.
    pub rev: String,
    /// Device CID (hex) when present.
    pub cid: String,
    /// The mmc_host device path these attributes came from.
    pub device: String,
}

fn read_trim(path: &str) -> String {
    std::fs::read_to_string(path)
        .map(|s| s.trim().to_string())
        .unwrap_or_default()
}

/// Discover the first mmc_host device dir (e.g. /sys/class/mmc_host/mmc0/mmc0:0001).
fn mmc_device_dir() -> Option<String> {
    for base in ["/sys/class/mmc_host"] {
        let entries = std::fs::read_dir(base).ok()?;
        for host in entries.flatten() {
            let host_path = host.path();
            let subs = match std::fs::read_dir(&host_path) {
                Ok(s) => s,
                Err(_) => continue,
            };
            for sub in subs.flatten() {
                let name = sub.file_name().to_string_lossy().to_string();
                // The card device dir looks like "mmc0:0001".
                if name.starts_with("mmc") && name.contains(':') {
                    return Some(sub.path().to_string_lossy().to_string());
                }
            }
        }
    }
    None
}

/// Read the host's eMMC health from sysfs (no external tool).
pub fn host_emmc_health() -> Result<HostEmmcHealth> {
    let dev = mmc_device_dir().ok_or_else(|| {
        BridgeError::Io(
            "no mmc_host device in /sys - this host has no eMMC (SD-only or NVMe system?)"
                .into(),
        )
    })?;
    let mut out = HostEmmcHealth {
        device: dev.clone(),
        ..Default::default()
    };
    out.life_time = read_trim(&format!("{dev}/life_time"));
    out.pre_eol_info = read_trim(&format!("{dev}/pre_eol_info"));
    // Block-device identity (the block node mirrors the card: mmcblk0).
    if let Some(blk) = std::fs::read_dir("/sys/block")
        .ok()
        .and_then(|ents| {
            ents.flatten()
                .map(|e| e.file_name().to_string_lossy().to_string())
                .find(|n| n.starts_with("mmcblk") && !n.contains('p'))
        })
    {
        out.model = read_trim(&format!("/sys/block/{blk}/device/model"));
        out.rev = read_trim(&format!("/sys/block/{blk}/device/rev"));
        out.cid = read_trim(&format!("/sys/block/{blk}/device/cid"));
    }
    Ok(out)
}

/// CLI: `emmc-host` — host eMMC health as JSON.
pub fn emmc_host_cli() -> Result<String> {
    let h = host_emmc_health()?;
    serde_json::to_string(&h).map_err(|e| BridgeError::Io(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_mmc_is_clean_error() {
        // A host without /sys/class/mmc_host must error cleanly, not crash.
        match host_emmc_health() {
            Ok(h) => assert!(!h.device.is_empty()),
            Err(e) => assert!(e.to_string().contains("no mmc_host")),
        }
    }

    #[test]
    fn mmc_discovery_handles_absent_sysfs() {
        // Sandbox/headless: no crash either way.
        let _ = mmc_device_dir();
    }
}
