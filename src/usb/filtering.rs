//! USB device filtering and USB↔ADB merging.
//!
//! Moves the Python device filtering/merging logic (from `python/core/devices.py`)
//! into Rust for deterministic, efficient classification of phones vs. peripherals
//! and stable device identity generation.
//!
//! This is a library-style API module: several `pub` items (`classify_mode`,
//! `detect_merged`, `merge_devices`, `FilterCriteria`, ...) are the Python-facing
//! surface and are not all referenced from the bridge binary's CLI path yet.
#![allow(dead_code)]

use crate::config::{DeviceInfo, InterfaceInfo};
use crate::error::{Result, BridgeError};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;

/// Known phone vendor IDs (mirrors python/core/devices.py `KNOWN_PHONE_VIDS`)
const KNOWN_PHONE_VIDS: &[u16] = &[
    0x04E8, // Samsung
    0x05C6, // Qualcomm
    0x0E8D, // MediaTek
    0x1782, // Spreadtrum/UNISOC
    0x18D1, // Google
    0x05AC, // Apple
];

/// Generic Android vendor IDs (mirrors `ANDROID_GENERIC_VIDS`)
const ANDROID_GENERIC_VIDS: &[u16] = &[
    0x18D1, // Google
    0x0BB4, // HTC
    0x2717, // Xiaomi
    0x2A70, // Xiaomi
    0x12D1, // Huawei
    0x22D9, // ZTE
    0x2AE5, // OnePlus
];

/// Keywords in product/manufacturer that indicate a phone
const PHONE_NAME_KEYWORDS: &[&str] = &[
    "android", "phone", "tecno", "infinix", "itel", "xiaomi", "redmi",
    "oppo", "vivo", "oneplus", "realme", "pixel", "nexus", "motorola",
    "lenovo", "huawei", "honor", "asus", "transsion", "spark", "smartphone",
];

/// ADB device info (from `adb devices -l` output)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AdbDevice {
    pub serial: String,
    pub state: String,
    #[serde(default)]
    pub extra: String,
}

/// Parse one `SERIAL\tstate extras` row (the `adb-devices` line contract)
/// into an `AdbDevice`. Returns None for blank/malformed rows.
///
/// NOTE: `devices_json` emits a JSON array of these STRINGS, not objects —
/// deserializing that array as `Vec<AdbDevice>` fails and silently yields
/// an empty vec (killing the USB↔ADB merge, row `adb_state`, and standalone
/// ADB rows). Always parse through here.
pub fn parse_adb_line(line: &str) -> Option<AdbDevice> {
    let mut parts = line.split_whitespace();
    let serial = parts.next()?;
    let state = parts.next()?;
    if serial.is_empty() || state.is_empty() {
        return None;
    }
    let extra: Vec<&str> = parts.collect();
    Some(AdbDevice {
        serial: serial.to_string(),
        state: state.to_string(),
        extra: extra.join(" "),
    })
}

/// Parse a JSON array of `adb-devices` row strings (tolerates a JSON array
/// of objects too, for forward compatibility).
pub fn parse_adb_rows(json: &str) -> Vec<AdbDevice> {
    let value: serde_json::Value = match serde_json::from_str(json) {
        Ok(v) => v,
        Err(_) => return Vec::new(),
    };
    match value {
        serde_json::Value::Array(items) => items
            .iter()
            .filter_map(|item| match item {
                serde_json::Value::String(s) => parse_adb_line(s),
                serde_json::Value::Object(_) => serde_json::from_value(item.clone()).ok(),
                _ => None,
            })
            .collect(),
        _ => Vec::new(),
    }
}

/// Merged USB + ADB device entry with stable key and transports
#[derive(Debug, Clone, Serialize)]
pub struct MergedDeviceInfo {
    pub key: String,
    pub label: String,
    pub transports: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub usb: Option<DeviceInfo>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub adb: Option<AdbDevice>,
}

/// Normalize a serial number string (filter noise like "null", "?", etc.)
pub fn normalize_serial(s: Option<&str>) -> String {
    let s = (s.unwrap_or("")).trim();
    if s.is_empty() || matches!(s.to_lowercase().as_str(), "null" | "none" | "unknown" | "?") {
        return String::new();
    }
    s.to_string()
}

/// Test if a USB device is plausibly a phone/tablet (not a hub, keyboard, etc.)
pub fn is_phone(d: &DeviceInfo) -> bool {
    if KNOWN_PHONE_VIDS.contains(&d.vid) {
        return true;
    }

    if d.interfaces
        .iter()
        .any(|i| i.class == 255 && i.subclass == 66)
    {
        return true;
    }

    if d.interfaces.iter().any(|i| i.class == 6) {
        return true;
    }

    if ANDROID_GENERIC_VIDS.contains(&d.vid) {
        return true;
    }

    let prod_lower = d
        .product
        .as_ref()
        .map(|s| s.to_lowercase())
        .unwrap_or_default();
    let mfr_lower = d
        .manufacturer
        .as_ref()
        .map(|s| s.to_lowercase())
        .unwrap_or_default();

    for keyword in PHONE_NAME_KEYWORDS {
        if prod_lower.contains(keyword) || mfr_lower.contains(keyword) {
            return true;
        }
    }

    false
}

/// Generate a stable device key from USB and/or ADB info
///
/// Priority: ADB serial > USB serial > USB port numbers > volatile bus:addr.
pub fn device_key(usb: Option<&DeviceInfo>, adb: Option<&AdbDevice>) -> String {
    if let Some(adb) = adb {
        let serial = normalize_serial(Some(&adb.serial));
        if !serial.is_empty() {
            return format!("adb:{}", serial);
        }
    }

    if let Some(usb) = usb {
        if let Some(serial) = &usb.serial {
            let normalized = normalize_serial(Some(serial));
            if !normalized.is_empty() {
                return format!("adb:{}", normalized);
            }
        }

        if !usb.port_numbers.is_empty() {
            return format!("usb:{}", usb.port_numbers);
        }

        return format!(
            "usb:{:04x}:{:04x}@{}:{}",
            usb.vid, usb.pid, usb.bus, usb.address
        );
    }

    String::new()
}

/// Compute transport modes for a device (job modes the UI can use)
pub fn compute_transports(usb: &DeviceInfo, adb_serials: &HashSet<String>) -> Vec<String> {
    let mut transports = Vec::new();
    let vid = usb.vid;
    let pid = usb.pid;

    let has_adb_iface = usb.interfaces.iter().any(|i| i.class == 255 && i.subclass == 66);
    if has_adb_iface {
        transports.push("ADB".to_string());
    }

    if vid == 0x04E8 {
        if pid == 0x685C {
            transports.push("Samsung BROM".to_string());
        } else if crate::usb::SAMSUNG_ODIN_PIDS.contains(&pid) && !has_adb_iface {
            transports.push("Download mode".to_string());
        } else if pid == 0x6860 || transports.is_empty() {
            transports.push("MTP".to_string());
        }

        if let Some(serial) = &usb.serial {
            let normalized = normalize_serial(Some(serial));
            if !normalized.is_empty() && adb_serials.contains(&normalized) && !has_adb_iface {
                transports.push("ADB".to_string());
            }
        }
    } else if vid == 0x0E8D {
        match pid {
            0x0003 => transports.push("MTK BROM".to_string()),
            0x2000 => transports.push("MTK BROM".to_string()),
            0x0004 | 0x1004 => transports.push("MTK".to_string()),
            _ => {}
        }
    } else if vid == 0x05C6 && pid == 0x9008 {
        transports.push("EDL".to_string());
    } else if vid == 0x18D1 {
        transports.push("FASTBOOT".to_string());
    } else if vid == 0x1782 {
        transports.push("SPD".to_string());
    }

    if transports.is_empty() {
        transports.push("MTP".to_string());
    }

    let mut seen = HashSet::new();
    let mut out = Vec::new();
    for t in transports {
        if !seen.contains(&t) {
            seen.insert(t.clone());
            out.push(t);
        }
    }

    out
}

/// Compute a short human-readable label: product + serial + VID:PID
pub fn compute_label(usb: &DeviceInfo, _adb_state_by_serial: &HashSet<String>) -> String {
    let mfr = usb
        .manufacturer
        .as_ref()
        .map(|s| s.trim())
        .unwrap_or("");
    let prod = usb
        .product
        .as_ref()
        .map(|s| s.trim())
        .unwrap_or("");
    let name = if !prod.is_empty() { prod } else if !mfr.is_empty() { mfr } else { "USB device" };

    let mut bits = vec![name.to_string()];

    if let Some(serial) = &usb.serial {
        let normalized = normalize_serial(Some(serial));
        if !normalized.is_empty() {
            bits.push(normalized);
        }
    }

    bits.push(format!("{:04x}:{:04x}", usb.vid, usb.pid));

    bits.join(" · ")
}

/// Alias kept for callers that used `device_label` naming.
pub fn device_label(usb: &DeviceInfo, adb_state_by_serial: &HashSet<String>) -> String {
    compute_label(usb, adb_state_by_serial)
}

/// Check if a PID is in the Samsung Odin download-mode list
fn is_samsung_odin_pid(pid: u16) -> bool {
    matches!(
        pid,
        0x6601 | 0x685d | 0x68c3 | 0x68ef | 0x4eee | 0x4eef
    )
}

/// Filter USB devices to only phones (rejects hubs, keyboards, etc.)
pub fn filter_phones(devices: &[DeviceInfo]) -> Vec<DeviceInfo> {
    devices.iter().filter(|d| is_phone(d)).cloned().collect()
}

/// Merge USB device list and ADB device list into unified rows
pub fn merge_devices(
    usb_devices: &[DeviceInfo],
    adb_devices: &[AdbDevice],
) -> Vec<MergedDeviceInfo> {
    let mut rows = Vec::new();
    let mut claimed_adb = HashSet::new();

    let mut adb_by_serial = std::collections::HashMap::new();
    for adb in adb_devices {
        let serial = normalize_serial(Some(&adb.serial));
        if !serial.is_empty() {
            adb_by_serial.insert(serial, adb.clone());
        }
    }

    let adb_serials: HashSet<String> = adb_by_serial.keys().cloned().collect();

    for usb in usb_devices {
        if !is_phone(usb) {
            continue;
        }

        let usb_serial = usb.serial.as_ref().and_then(|s| {
            let norm = normalize_serial(Some(s));
            if norm.is_empty() { None } else { Some(norm) }
        });

        let adb_match = usb_serial
            .as_ref()
            .and_then(|s| adb_by_serial.get(s).cloned());

        if let Some(ref serial) = usb_serial {
            if adb_by_serial.contains_key(serial) {
                claimed_adb.insert(serial.clone());
            }
        }

        let key = device_key(Some(usb), adb_match.as_ref());
        let transports = compute_transports(usb, &adb_serials);
        let label = compute_label(usb, &adb_serials);

        rows.push(MergedDeviceInfo {
            key,
            label,
            transports,
            usb: Some(usb.clone()),
            adb: adb_match,
        });
    }

    for adb in adb_devices {
        let serial = normalize_serial(Some(&adb.serial));
        if serial.is_empty() || claimed_adb.contains(&serial) {
            continue;
        }

        let key = format!("adb:{}", serial);
        rows.push(MergedDeviceInfo {
            key,
            label: format!("{} [{}]", serial, adb.state),
            transports: vec!["ADB".to_string()],
            usb: None,
            adb: Some(adb.clone()),
        });
    }

    rows
}

/// Filter criteria for device detection
#[derive(Debug, Clone, Default, Deserialize)]
pub struct FilterCriteria {
    pub require_serial: bool,
    pub min_interfaces: usize,
    pub vendor_ids: Option<Vec<u16>>,
}

/// Classify device mode from VID/PID and interfaces (Python-compatible mode strings)
pub fn classify_mode(vid: u16, pid: u16, interfaces: &[InterfaceInfo]) -> String {
    let has_adb_iface = interfaces.iter().any(|i| i.class == 255 && i.subclass == 66);

    match vid {
        0x04E8 => {
            if crate::usb::SAMSUNG_ODIN_PIDS.contains(&pid) && !has_adb_iface {
                return "samsung-odin".to_string();
            }
            if pid == 0x685C {
                return "samsung-brom".to_string();
            }
            if pid == 0x6860 {
                return "android-mtp".to_string();
            }
            if has_adb_iface {
                return "android-adb".to_string();
            }
            if interfaces.iter().any(|i| i.class == 3) {
                return "samsung-hid".to_string();
            }
            "samsung".to_string()
        }
        0x0E8D => match pid {
            0x0003 => "mediatek-brom".to_string(),
            0x2000 => "mediatek-preloader".to_string(),
            0x0004 | 0x1004 => "mediatek-da".to_string(),
            _ => "mediatek".to_string(),
        },
        0x05C6 if pid == 0x9008 => "qualcomm-edl".to_string(),
        0x18D1 => "fastboot".to_string(),
        0x1782 => "spd".to_string(),
        0x05AC => "apple".to_string(),
        _ if has_adb_iface => "android-adb".to_string(),
        _ if interfaces.iter().any(|i| i.class == 6) => "android-mtp".to_string(),
        _ => "other".to_string(),
    }
}

/// Detect and merge USB + ADB devices in one call, emitting JSON rows.
pub fn detect_merged(criteria: Option<&FilterCriteria>) -> Result<String> {
    let vid_filter = criteria
        .and_then(|c| c.vendor_ids.as_ref())
        .and_then(|v| v.first().copied());

    let usb_devices = crate::usb::collect_devices(vid_filter)?;
    let phones = filter_phones(&usb_devices);

    let adb_json = crate::adb::devices_json_no_probe().unwrap_or_else(|_| "[]".to_string());
    let adb_devices: Vec<AdbDevice> = parse_adb_rows(&adb_json);

    let rows = merge_devices(&phones, &adb_devices);

    serde_json::to_string_pretty(&rows).map_err(|e| BridgeError::Io(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dev(vid: u16, pid: u16, product: Option<&str>, interfaces: Vec<InterfaceInfo>) -> DeviceInfo {
        DeviceInfo {
            vid,
            pid,
            bus: 1,
            address: 3,
            product: product.map(|s| s.to_string()),
            manufacturer: None,
            serial: None,
            interfaces,
            is_samsung: vid == 0x04E8,
            configs: 1,
            active_config: 0,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 3,
            port_numbers: String::new(),
            max_packet_size0: 64,
            mode: "other".to_string(),
        }
    }

    #[test]
    fn normalize_serial_noise_and_valid() {
        assert_eq!(normalize_serial(None), "");
        assert_eq!(normalize_serial(Some("null")), "");
        assert_eq!(normalize_serial(Some("  ABC123  ")), "ABC123");
    }

    #[test]
    fn is_phone_rejects_hub_accepts_samsung() {
        assert!(is_phone(&dev(0x04E8, 0x685D, None, vec![])));
        assert!(!is_phone(&dev(0x9999, 0x9999, Some("USB Hub"), vec![])));
    }

    #[test]
    fn device_key_prefers_serial_then_ports() {
        let mut d = dev(0x04E8, 0x685D, None, vec![]);
        d.serial = Some("ABC123".to_string());
        assert_eq!(device_key(Some(&d), None), "adb:ABC123");

        let mut d2 = dev(0x04E8, 0x685D, None, vec![]);
        d2.port_numbers = "1-2-3".to_string();
        assert_eq!(device_key(Some(&d2), None), "usb:1-2-3");
    }

    #[test]
    fn classify_mode_samsung_odin_and_mtk_brom() {
        assert_eq!(classify_mode(0x04E8, 0x685D, &[]), "samsung-odin");
        assert_eq!(classify_mode(0x0E8D, 0x0003, &[]), "mediatek-brom");
        assert_eq!(classify_mode(0x0E8D, 0x2000, &[]), "mediatek-preloader");
        assert_eq!(classify_mode(0x05C6, 0x9008, &[]), "qualcomm-edl");
    }

    #[test]
    fn merge_usb_adb_by_serial() {
        let mut usb = dev(0x04E8, 0x685D, Some("Samsung Galaxy"), vec![]);
        usb.serial = Some("R9X".to_string());

        let adb = vec![AdbDevice { serial: "R9X".to_string(), state: "device".to_string(), extra: String::new() }];

        let merged = merge_devices(&[usb], &adb);
        assert_eq!(merged.len(), 1);
        assert_eq!(merged[0].key, "adb:R9X");
        assert!(merged[0].usb.is_some());
        assert!(merged[0].adb.is_some());
    }
}
#[cfg(test)]
mod presence_parse_tests {
    use super::{parse_adb_line, parse_adb_rows};

    #[test]
    fn line_contract_parses() {
        let d = parse_adb_line("06977371AD102074\tdevice 2-1.2 product:KG6").unwrap();
        assert_eq!(d.serial, "06977371AD102074");
        assert_eq!(d.state, "device");
        assert!(d.extra.contains("product:KG6"));
        assert!(parse_adb_line("").is_none());
        assert!(parse_adb_line("onlyserial").is_none());
    }

    #[test]
    fn string_arrays_parse_objects_too() {
        // devices_json emits an array of STRINGS: this must not silently
        // become an empty vec (that killed the USB-ADB merge outright).
        let rows = parse_adb_rows("[\"AAA\\tdevice x\", \"BBB\\tunknown transport:usb\"]");
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0].serial, "AAA");
        assert_eq!(rows[1].state, "unknown");
        assert!(parse_adb_rows("not json").is_empty());
        assert!(parse_adb_rows("{}").is_empty());
    }
}
