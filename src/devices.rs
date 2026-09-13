//! Device filtering and merging for USB + ADB

use crate::config::DeviceInfo;
use crate::error::{Result, BridgeError};
use serde::Serialize;

/// Vendor IDs that always count as phones/tablets
const KNOWN_PHONE_VIDS: &[u16] = &[0x04E8, 0x05C6, 0x0E8D, 0x1782, 0x18D1, 0x05AC];

/// Other Android vendor IDs
const ANDROID_GENERIC_VIDS: &[u16] = &[0x18D1, 0x0BB4, 0x2717, 0x2A70, 0x12D1, 0x22D9, 0x2AE5];

/// Product/manufacturer keywords that mark a non-vendor VID as a phone
const PHONE_NAME_KEYWORDS: &[&str] = &[
    "android", "phone", "tecno", "infinix", "itel", "xiaomi", "redmi",
    "oppo", "vivo", "oneplus", "realme", "pixel", "nexus", "motorola",
    "lenovo", "huawei", "honor", "asus", "transsion", "spark", "smartphone",
    "fus",  // Add FUS detection
];

/// Unified device row for GUI: USB + ADB merged
#[derive(Debug, Clone, Serialize)]
pub struct DeviceRow {
    pub key: String,
    pub label: String,
    pub transports: Vec<String>,
    pub vid: u16,
    pub pid: u16,
    pub bus: u8,
    pub address: u8,
    pub serial: Option<String>,
    pub is_adb: bool,
    pub adb_state: Option<String>,
}

/// Normalize serial string: handle null/none/unknown, whitespace
fn norm_serial(value: Option<&str>) -> String {
    let s = value.unwrap_or("").trim();
    if s.is_empty() || matches!(s.to_lowercase().as_str(), "null" | "none" | "unknown" | "?") {
        return String::new();
    }
    s.to_string()
}

/// True if a USB device dict plausibly is a phone/tablet
pub fn is_phone_device(d: &DeviceInfo) -> bool {
    // Check vendor ID
    if KNOWN_PHONE_VIDS.contains(&d.vid) {
        return true;
    }

    // Check interfaces: ADB (255/66/*) or MTP/PTP (class 6)
    for iface in &d.interfaces {
        if iface.class == 255 && iface.subclass == 66 {
            return true; // ADB gadget
        }
        if iface.class == 6 {
            return true; // MTP/PTP image interface
        }
    }

    // Generic Android vendor IDs
    if ANDROID_GENERIC_VIDS.contains(&d.vid) {
        return true;
    }

    // Check product/manufacturer name keywords
    let prod = d.product.as_deref().unwrap_or("").to_lowercase();
    let mfr = d.manufacturer.as_deref().unwrap_or("").to_lowercase();
    for kw in PHONE_NAME_KEYWORDS {
        if prod.contains(kw) || mfr.contains(kw) {
            return true;
        }
    }

    false
}

/// Get transport names (ADB, MTK, EDL, etc.) for a device
pub fn device_transports(d: &DeviceInfo) -> Vec<String> {
    let mut transports = Vec::new();

    // Check for ADB composite
    let has_adb = d.interfaces
        .iter()
        .any(|i| i.class == 255 && i.subclass == 66 && i.protocol == 1);

    if has_adb {
        transports.push("ADB".to_string());
    }

    // Samsung-specific modes
    if d.vid == 0x04E8 {
        if d.pid == 0x685C {
            transports.push("Samsung BROM".to_string());
        } else if crate::usb::SAMSUNG_ODIN_PIDS.contains(&d.pid) && !has_adb {
            transports.push("Download mode".to_string());
        } else if d.pid == 0x6860 || transports.is_empty() {
            transports.push("MTP".to_string());
        }
    }
    // MediaTek modes
    else if d.vid == 0x0E8D {
        let mode_hint = &d.mode;
        if mode_hint.contains("brom") || mode_hint.contains("preloader") {
            transports.push("MTK BROM".to_string());
        } else if mode_hint.contains("da") {
            transports.push("MTK".to_string());
        }
    }
    // Qualcomm EDL
    else if d.vid == 0x05C6 && d.pid == 0x9008 {
        transports.push("EDL".to_string());
    }
    // Google Fastboot
    else if d.vid == 0x18D1 {
        transports.push("FASTBOOT".to_string());
    }
    // Spreadtrum/UNISOC
    else if d.vid == 0x1782 {
        transports.push("SPD".to_string());
    }

    // Default fallback
    if transports.is_empty() {
        transports.push("MTP".to_string());
    }

    // De-duplicate while preserving order
    let mut seen = std::collections::HashSet::new();
    let mut out = Vec::new();
    for t in transports {
        if !seen.contains(&t) {
            seen.insert(t.clone());
            out.push(t);
        }
    }

    out
}

/// Generate a short human label: model/product + serial + pid
pub fn device_label(d: &DeviceInfo) -> String {
    let mfr = d.manufacturer.as_deref().unwrap_or("").trim();
    let prod = d.product.as_deref().unwrap_or("").trim();
    let name = if !prod.is_empty() {
        prod
    } else if !mfr.is_empty() {
        mfr
    } else {
        "USB device"
    };

    let mut bits = vec![name.to_string()];

    let serial = norm_serial(d.serial.as_deref());
    if !serial.is_empty() {
        bits.push(serial);
    }

    bits.push(format!("{:04x}:{:04x}", d.vid, d.pid));

    bits.join(" · ")
}

/// Generate stable device key: adb:<serial> or usb:<port_numbers> or usb:vid:pid@bus:addr
pub fn device_key(d: &DeviceInfo) -> String {
    let serial = norm_serial(d.serial.as_deref());
    if !serial.is_empty() {
        return format!("adb:{}", serial);
    }

    let port_numbers = d.port_numbers.trim();
    if !port_numbers.is_empty() {
        return format!("usb:{}", port_numbers);
    }

    format!("usb:{:04x}:{:04x}@{}:{}", d.vid, d.pid, d.bus, d.address)
}

/// ADB device info from bridge
#[derive(Debug, Clone, Serialize)]
pub struct AdbDevice {
    pub serial: String,
    pub state: String,
}

/// List filtered USB devices (phones only, no hubs/HID/webcams)
pub fn list_devices_filtered() -> Result<String> {
    let usb_devs = crate::usb::collect_devices(None)?;

    let rows: Vec<DeviceRow> = usb_devs
        .into_iter()
        .filter(|d| is_phone_device(d))
        .map(|d| DeviceRow {
            key: device_key(&d),
            label: device_label(&d),
            transports: device_transports(&d),
            vid: d.vid,
            pid: d.pid,
            bus: d.bus,
            address: d.address,
            serial: d.serial.clone(),
            is_adb: false,
            adb_state: None,
        })
        .collect();

    serde_json::to_string_pretty(&rows)
        .map_err(|e| BridgeError::Io(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::InterfaceInfo;

    #[test]
    fn is_phone_device_known_vid() {
        let dev = DeviceInfo {
            vid: 0x04E8, // Samsung
            pid: 0x6860,
            bus: 1,
            address: 2,
            product: None,
            manufacturer: None,
            serial: None,
            is_samsung: true,
            configs: 1,
            active_config: 1,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 2,
            port_numbers: "1-2".to_string(),
            max_packet_size0: 64,
            mode: "android-mtp".to_string(),
            interfaces: vec![],
        };
        assert!(is_phone_device(&dev));
    }

    #[test]
    fn is_phone_device_adb_interface() {
        let dev = DeviceInfo {
            vid: 0x1234, // Unknown VID
            pid: 0x5678,
            bus: 1,
            address: 2,
            product: None,
            manufacturer: None,
            serial: None,
            is_samsung: false,
            configs: 1,
            active_config: 1,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 2,
            port_numbers: "1-2".to_string(),
            max_packet_size0: 64,
            mode: "other".to_string(),
            interfaces: vec![InterfaceInfo {
                number: 0,
                class: 255,
                subclass: 66,
                protocol: 1,
                endpoints: vec![],
            }],
        };
        assert!(is_phone_device(&dev));
    }

    #[test]
    fn is_phone_device_keyword_match() {
        let dev = DeviceInfo {
            vid: 0x1234,
            pid: 0x5678,
            bus: 1,
            address: 2,
            product: Some("My Android Phone".to_string()),
            manufacturer: None,
            serial: None,
            is_samsung: false,
            configs: 1,
            active_config: 1,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 2,
            port_numbers: "1-2".to_string(),
            max_packet_size0: 64,
            mode: "other".to_string(),
            interfaces: vec![],
        };
        assert!(is_phone_device(&dev));
    }

    #[test]
    fn is_phone_device_fus_keyword() {
        let dev = DeviceInfo {
            vid: 0x1234,
            pid: 0x5678,
            bus: 1,
            address: 2,
            product: Some("FUS Device".to_string()),
            manufacturer: None,
            serial: None,
            is_samsung: false,
            configs: 1,
            active_config: 1,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 2,
            port_numbers: "1-2".to_string(),
            max_packet_size0: 64,
            mode: "other".to_string(),
            interfaces: vec![],
        };
        assert!(is_phone_device(&dev));
    }

    #[test]
    fn is_phone_device_not_hub() {
        let dev = DeviceInfo {
            vid: 0x0424, // SMSC (typical hub vendor)
            pid: 0x2514,
            bus: 1,
            address: 2,
            product: Some("USB 2.0 Hub".to_string()),
            manufacturer: None,
            serial: None,
            is_samsung: false,
            configs: 1,
            active_config: 1,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 2,
            port_numbers: "1-2".to_string(),
            max_packet_size0: 64,
            mode: "other".to_string(),
            interfaces: vec![],
        };
        assert!(!is_phone_device(&dev));
    }

    #[test]
    fn device_key_uses_serial() {
        let dev = DeviceInfo {
            vid: 0x04E8,
            pid: 0x6860,
            bus: 1,
            address: 2,
            product: None,
            manufacturer: None,
            serial: Some("ABC123".to_string()),
            is_samsung: true,
            configs: 1,
            active_config: 1,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 2,
            port_numbers: "1-2".to_string(),
            max_packet_size0: 64,
            mode: "android-mtp".to_string(),
            interfaces: vec![],
        };
        assert_eq!(device_key(&dev), "adb:ABC123");
    }

    #[test]
    fn device_key_uses_port_numbers() {
        let dev = DeviceInfo {
            vid: 0x04E8,
            pid: 0x6860,
            bus: 1,
            address: 2,
            product: None,
            manufacturer: None,
            serial: None,
            is_samsung: true,
            configs: 1,
            active_config: 1,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 2,
            port_numbers: "1-2-3".to_string(),
            max_packet_size0: 64,
            mode: "android-mtp".to_string(),
            interfaces: vec![],
        };
        assert_eq!(device_key(&dev), "usb:1-2-3");
    }

    #[test]
    fn device_label_format() {
        let dev = DeviceInfo {
            vid: 0x04E8,
            pid: 0x6860,
            bus: 1,
            address: 2,
            product: Some("Samsung Galaxy".to_string()),
            manufacturer: Some("Samsung".to_string()),
            serial: Some("ABC123".to_string()),
            is_samsung: true,
            configs: 1,
            active_config: 1,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 2,
            port_numbers: "1-2".to_string(),
            max_packet_size0: 64,
            mode: "android-mtp".to_string(),
            interfaces: vec![],
        };
        let label = device_label(&dev);
        assert!(label.contains("Samsung Galaxy"));
        assert!(label.contains("ABC123"));
        assert!(label.contains("04e8:6860"));
    }
}
