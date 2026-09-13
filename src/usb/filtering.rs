//! USB device filtering and USB↔ADB merging.
//!
//! Moves the Python device filtering/merging logic (from `python/core/devices.py`)
//! into Rust for deterministic, efficient classification of phones vs. peripherals
//! and stable device identity generation.

use crate::config::{DeviceInfo, InterfaceInfo};
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
    0x18D1, // Google (duplicate but OK)
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
    pub state: String,  // "device", "offline", "unauthorized", "recovery", etc.
    #[serde(default)]
    pub extra: String,  // Additional info (e.g., "transport_id:1")
}

/// Merged USB + ADB device entry with stable key and transports
#[derive(Debug, Clone, Serialize)]
pub struct MergedDeviceInfo {
    pub key: String,                           // Stable identity: adb:<serial> or usb:<ports> or usb:vid:pid@bus:addr
    pub label: String,                         // Short display label for UI
    pub transports: Vec<String>,               // Job modes: ["ADB", "Download mode", "MTK BROM", ...]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub usb: Option<DeviceInfo>,               // USB device info (if on USB)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub adb: Option<AdbDevice>,                // ADB device info (if reachable via ADB)
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
///
/// Rejects:
/// - Hubs (generic_hub vendor IDs, hub class codes)
/// - HID keyboards/mice (class 3)
/// - Webcams
/// - Smartcard readers
/// - Printers
///
/// Accepts:
/// - Known phone VIDs (Samsung, Qualcomm, MediaTek, Google, Apple, UNISOC)
/// - ADB interfaces (255/66/*)
/// - MTP interfaces (class 6)
/// - Products with phone keywords in name
pub fn is_phone(d: &DeviceInfo) -> bool {
    // Check known phone vendor IDs
    if KNOWN_PHONE_VIDS.contains(&d.vid) {
        return true;
    }

    // Check for ADB interface (class 255, subclass 66, protocol 1)
    if d.interfaces
        .iter()
        .any(|i| i.class == 255 && i.subclass == 66)
    {
        return true;
    }

    // Check for MTP/PTP image interface (class 6)
    if d.interfaces.iter().any(|i| i.class == 6) {
        return true;
    }

    // Check generic Android vendor IDs
    if ANDROID_GENERIC_VIDS.contains(&d.vid) {
        return true;
    }

    // Check product/manufacturer keywords
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
/// Priority:
/// 1. ADB serial (most stable, user-facing)
/// 2. USB serial (maps to ADB on same phone)
/// 3. USB port numbers (stable across re-enumeration, not volatile bus:addr)
/// 4. USB vid:pid@bus:addr (volatile, last resort)
/// 5. Standalone ADB (TCP, emulator)
pub fn device_key(usb: Option<&DeviceInfo>, adb: Option<&AdbDevice>) -> String {
    // Prefer ADB serial
    if let Some(adb) = adb {
        let serial = normalize_serial(Some(&adb.serial));
        if !serial.is_empty() {
            return format!("adb:{}", serial);
        }
    }

    // Prefer USB serial (merges with ADB)
    if let Some(usb) = usb {
        if let Some(serial) = &usb.serial {
            let normalized = normalize_serial(Some(serial));
            if !normalized.is_empty() {
                return format!("adb:{}", normalized);
            }
        }

        // Fallback to port numbers (stable across re-enumeration)
        if !usb.port_numbers.is_empty() {
            return format!("usb:{}", usb.port_numbers);
        }

        // Last resort: volatile VID:PID@BUS:ADDR
        return format!(
            "usb:{:04x}:{:04x}@{}:{}",
            usb.vid, usb.pid, usb.bus, usb.address
        );
    }

    // Standalone ADB (no USB)
    if let Some(adb) = adb {
        let serial = normalize_serial(Some(&adb.serial));
        if !serial.is_empty() {
            return format!("adb:{}", serial);
        }
    }

    String::new()
}

/// Compute transport modes for a device (job modes the UI can use)
///
/// Returns ["ADB", "Download mode", "MTK BROM", "EDL", "FASTBOOT", "SPD", "MTP", ...]
pub fn compute_transports(usb: &DeviceInfo, adb_serials: &HashSet<String>) -> Vec<String> {
    let mut transports = Vec::new();
    let vid = usb.vid;
    let pid = usb.pid;

    // Check for ADB composite
    let has_adb_iface = usb.interfaces.iter().any(|i| i.class == 255 && i.subclass == 66);
    if has_adb_iface {
        transports.push("ADB".to_string());
    }

    // Samsung-specific modes
    if vid == 0x04E8 {
        // Samsung BROM
        if pid == 0x685C {
            transports.push("Samsung BROM".to_string());
        }
        // Download mode (Odin PIDs)
        else if is_samsung_odin_pid(pid) && !has_adb_iface {
            transports.push("Download mode".to_string());
        }
        // MTP or default
        else if pid == 0x6860 || transports.is_empty() {
            transports.push("MTP".to_string());
        }

        // Samsung may expose ADB via serial
        if let Some(serial) = &usb.serial {
            let normalized = normalize_serial(Some(serial));
            if !normalized.is_empty() && adb_serials.contains(&normalized) && !has_adb_iface {
                transports.push("ADB".to_string());
            }
        }
    }
    // MediaTek modes
    else if vid == 0x0E8D {
        match pid {
            0x0003 => transports.push("MTK BROM".to_string()),
            0x2000 => transports.push("MTK BROM".to_string()),  // Preloader
            0x0004 | 0x1004 => transports.push("MTK".to_string()),  // DA
            _ => {}
        }
    }
    // Qualcomm EDL
    else if vid == 0x05C6 && pid == 0x9008 {
        transports.push("EDL".to_string());
    }
    // Google Fastboot
    else if vid == 0x18D1 {
        transports.push("FASTBOOT".to_string());
    }
    // UNISOC/Spreadtrum
    else if vid == 0x1782 {
        transports.push("SPD".to_string());
    }

    // Default to MTP if nothing else matched
    if transports.is_empty() {
        transports.push("MTP".to_string());
    }

    // De-duplicate and preserve order
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
fn compute_label(usb: &DeviceInfo, adb_state_by_serial: &HashSet<String>) -> String {
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
    let name = if !prod.is_empty() { prod } else if !mfr.is_empty() } { mfr } else { "USB device" };

    let mut bits = vec![name.to_string()];

    // Add serial if present
    if let Some(serial) = &usb.serial {
        let normalized = normalize_serial(Some(serial));
        if !normalized.is_empty() {
            bits.push(normalized);
        }
    }

    // Add VID:PID
    bits.push(format!("{:04x}:{:04x}", usb.vid, usb.pid));

    bits.join(" · ")
}

/// Merge USB device list and ADB device list into unified rows
///
/// Algorithm:
/// 1. Iterate USB devices, filter to phones only
/// 2. For each USB phone, look for matching ADB entry by serial
/// 3. Merge and output as single row
/// 4. Iterate ADB devices, output standalone entries (not already merged)
pub fn merge_devices(
    usb_devices: &[DeviceInfo],
    adb_devices: &[AdbDevice],
) -> Vec<MergedDeviceInfo> {
    let mut rows = Vec::new();
    let mut claimed_adb = HashSet::new();

    // Build ADB serial → state map
    let mut adb_by_serial = std::collections::HashMap::new();
    for adb in adb_devices {
        let serial = normalize_serial(Some(&adb.serial));
        if !serial.is_empty() {
            adb_by_serial.insert(serial, adb.clone());
        }
    }

    let adb_serials: HashSet<String> = adb_by_serial.keys().cloned().collect();

    // First pass: USB devices, merged with matching ADB
    for usb in usb_devices {
        if !is_phone(usb) {
            continue;  // Hub, keyboard, etc. — skip
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

    // Second pass: Standalone ADB entries (TCP, emulator, not on USB)
    for adb in adb_devices {
        let serial = normalize_serial(Some(&adb.serial));
        if serial.is_empty() || claimed_adb.contains(&serial) {
            continue;  // Empty or already merged
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normalize_serial_empty() {
        assert_eq!(normalize_serial(None), "");
        assert_eq!(normalize_serial(Some("")), "");
        assert_eq!(normalize_serial(Some("  ")), "");
    }

    #[test]
    fn test_normalize_serial_noise() {
        assert_eq!(normalize_serial(Some("null")), "");
        assert_eq!(normalize_serial(Some("NULL")), "");
        assert_eq!(normalize_serial(Some("none")), "");
        assert_eq!(normalize_serial(Some("unknown")), "");
        assert_eq!(normalize_serial(Some("?")), "");
    }

    #[test]
    fn test_normalize_serial_valid() {
        assert_eq!(normalize_serial(Some("R9X")), "R9X");
        assert_eq!(normalize_serial(Some("  ABC123  ")), "ABC123");
    }

    #[test]
    fn test_is_phone_known_vid_samsung() {
        let device = DeviceInfo {
            vid: 0x04E8,
            pid: 0x685D,
            bus: 1,
            address: 3,
            product: None,
            manufacturer: None,
            serial: None,
            interfaces: vec![],
            is_samsung: true,
            configs: 1,
            active_config: 0,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 3,
            port_numbers: "1-2".to_string(),
            max_packet_size0: 64,
            mode: "samsung-odin".to_string(),
        };

        assert!(is_phone(&device));
    }

    #[test]
    fn test_is_phone_adb_interface() {
        let device = DeviceInfo {
            vid: 0x1234,  // Unknown VID
            pid: 0x5678,
            bus: 1,
            address: 3,
            product: None,
            manufacturer: None,
            serial: None,
            interfaces: vec![InterfaceInfo {
                number: 0,
                class: 255,  // Vendor-specific
                subclass: 66,  // ADB subclass
                protocol: 1,
                endpoints: vec![],
            }],
            is_samsung: false,
            configs: 1,
            active_config: 1,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 3,
            port_numbers: "1-3".to_string(),
            max_packet_size0: 64,
            mode: "android-adb".to_string(),
        };

        assert!(is_phone(&device));
    }

    #[test]
    fn test_is_phone_mtp_interface() {
        let device = DeviceInfo {
            vid: 0x9999,  // Unknown VID
            pid: 0x9999,
            bus: 1,
            address: 3,
            product: Some("Camera".to_string()),
            manufacturer: None,
            serial: None,
            interfaces: vec![InterfaceInfo {
                number: 0,
                class: 6,  // MTP/PTP
                subclass: 1,
                protocol: 1,
                endpoints: vec![],
            }],
            is_samsung: false,
            configs: 1,
            active_config: 1,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 3,
            port_numbers: "1-4".to_string(),
            max_packet_size0: 64,
            mode: "other".to_string(),
        };

        assert!(is_phone(&device));
    }

    #[test]
    fn test_is_phone_keyword() {
        let device = DeviceInfo {
            vid: 0x9999,
            pid: 0x9999,
            bus: 1,
            address: 3,
            product: Some("MyPhone Android Device".to_string()),
            manufacturer: None,
            serial: None,
            interfaces: vec![],
            is_samsung: false,
            configs: 1,
            active_config: 1,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 3,
            port_numbers: "1-5".to_string(),
            max_packet_size0: 64,
            mode: "other".to_string(),
        };

        assert!(is_phone(&device));
    }

    #[test]
    fn test_is_phone_rejects_unknown_no_keyword() {
        let device = DeviceInfo {
            vid: 0x9999,
            pid: 0x9999,
            bus: 1,
            address: 3,
            product: Some("USB Hub".to_string()),
            manufacturer: None,
            serial: None,
            interfaces: vec![],
            is_samsung: false,
            configs: 1,
            active_config: 1,
            device_class: 0x09,  // Hub class
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 3,
            port_numbers: "1-6".to_string(),
            max_packet_size0: 64,
            mode: "other".to_string(),
        };

        assert!(!is_phone(&device));
    }

    #[test]
    fn test_device_key_prefers_serial() {
        let usb = DeviceInfo {
            vid: 0x04E8,
            pid: 0x685D,
            bus: 1,
            address: 3,
            product: None,
            manufacturer: None,
            serial: Some("ABC123".to_string()),
            interfaces: vec![],
            is_samsung: true,
            configs: 1,
            active_config: 0,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 3,
            port_numbers: "1-2".to_string(),
            max_packet_size0: 64,
            mode: "samsung-odin".to_string(),
        };

        assert_eq!(device_key(Some(&usb), None), "adb:ABC123");
    }

    #[test]
    fn test_device_key_fallback_to_ports() {
        let usb = DeviceInfo {
            vid: 0x04E8,
            pid: 0x685D,
            bus: 1,
            address: 3,
            product: None,
            manufacturer: None,
            serial: None,
            interfaces: vec![],
            is_samsung: true,
            configs: 1,
            active_config: 0,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 3,
            port_numbers: "1-2-3".to_string(),
            max_packet_size0: 64,
            mode: "samsung-odin".to_string(),
        };

        assert_eq!(device_key(Some(&usb), None), "usb:1-2-3");
    }

    #[test]
    fn test_device_key_fallback_to_volatile() {
        let usb = DeviceInfo {
            vid: 0x04E8,
            pid: 0x685D,
            bus: 1,
            address: 3,
            product: None,
            manufacturer: None,
            serial: None,
            interfaces: vec![],
            is_samsung: true,
            configs: 1,
            active_config: 0,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 3,
            port_numbers: String::new(),  // No port numbers
            max_packet_size0: 64,
            mode: "samsung-odin".to_string(),
        };

        assert_eq!(device_key(Some(&usb), None), "usb:04e8:685d@1:3");
    }

    #[test]
    fn test_merge_devices_usb_adb_by_serial() {
        let usb = vec![DeviceInfo {
            vid: 0x04E8,
            pid: 0x685D,
            bus: 1,
            address: 3,
            product: Some("Samsung Galaxy".to_string()),
            manufacturer: Some("SAMSUNG".to_string()),
            serial: Some("R9X".to_string()),
            interfaces: vec![],
            is_samsung: true,
            configs: 1,
            active_config: 0,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 3,
            port_numbers: "1-2".to_string(),
            max_packet_size0: 64,
            mode: "samsung-odin".to_string(),
        }];

        let adb = vec![AdbDevice {
            serial: "R9X".to_string(),
            state: "device".to_string(),
            extra: String::new(),
        }];

        let merged = merge_devices(&usb, &adb);

        assert_eq!(merged.len(), 1);
        assert_eq!(merged[0].key, "adb:R9X");
        assert!(merged[0].usb.is_some());
        assert!(merged[0].adb.is_some());
    }

    #[test]
    fn test_merge_devices_standalone_adb() {
        let usb = vec![];

        let adb = vec![
            AdbDevice {
                serial: "R9X".to_string(),
                state: "device".to_string(),
                extra: String::new(),
            },
            AdbDevice {
                serial: "emulator-5554".to_string(),
                state: "device".to_string(),
                extra: String::new(),
            },
        ];

        let merged = merge_devices(&usb, &adb);

        assert_eq!(merged.len(), 2);
        assert_eq!(merged[0].key, "adb:R9X");
        assert_eq!(merged[1].key, "adb:emulator-5554");
        assert!(merged[0].usb.is_none());
        assert!(merged[1].usb.is_none());
    }

    #[test]
    fn test_filter_phones() {
        let devices = vec![
            DeviceInfo {
                vid: 0x04E8,
                pid: 0x685D,
                bus: 1,
                address: 3,
                product: None,
                manufacturer: None,
                serial: None,
                interfaces: vec![],
                is_samsung: true,
                configs: 1,
                active_config: 0,
                device_class: 0,
                bcd_usb: 0x0200,
                bcd_device: 0x0100,
                device_speed: 3,
                port_numbers: "1-2".to_string(),
                max_packet_size0: 64,
                mode: "samsung-odin".to_string(),
            },
            DeviceInfo {
                vid: 0x9999,
                pid: 0x9999,
                bus: 1,
                address: 4,
                product: Some("USB Hub".to_string()),
                manufacturer: None,
                serial: None,
                interfaces: vec![],
                is_samsung: false,
                configs: 1,
                active_config: 1,
                device_class: 0x09,
                bcd_usb: 0x0200,
                bcd_device: 0x0100,
                device_speed: 3,
                port_numbers: "1-3".to_string(),
                max_packet_size0: 64,
                mode: "other".to_string(),
            },
        ];

        let phones = filter_phones(&devices);
        assert_eq!(phones.len(), 1);
        assert_eq!(phones[0].vid, 0x04E8);
    }
}
