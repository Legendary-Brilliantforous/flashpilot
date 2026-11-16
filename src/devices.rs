//! Device row composition for GUI: USB + ADB merged rows (filtering lives in usb::filtering)
#![allow(dead_code)] // list_devices_filtered is Python-facing API surface

use crate::error::Result;
use crate::usb::filtering::{
    classify_mode, compute_transports, device_key, device_label, normalize_serial, parse_adb_rows,
    AdbDevice,
};
use serde::Serialize;

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
    /// USB string descriptors so the GUI can show model/manufacturer without
    /// re-enumerating from Python (Rust core owns enumeration).
    pub usb_product: Option<String>,
    pub usb_manufacturer: Option<String>,
    /// Rust mode classification (`classify_mode`): the single source of
    /// truth Python groups on (mtp.py/mtk.py/device_info.py/GUI buckets).
    /// `android-adb` for ADB-only rows (no USB leg to classify).
    pub mode: String,
}

/// Merge USB + ADB into GUI rows.
pub fn list_devices_filtered() -> Result<String> {
    list_devices_filtered_vid(None)
}

/// Merge USB + ADB into GUI rows, optionally restricted to a vendor ID.
///
/// Uses the zero-touch presence listing (`devices_json_no_probe`): row
/// rebuilds fire on change-detection — i.e. precisely during USB
/// re-enumeration — which is the worst moment to claim interfaces and
/// handshake. States come from the system server when it runs; otherwise
/// rows report presence with `unknown` state (honest, never guessed).
pub fn list_devices_filtered_vid(vid_filter: Option<u16>) -> Result<String> {
    let usb_devices = crate::usb::collect_devices(vid_filter)?;
    let phones = crate::usb::filtering::filter_phones(&usb_devices);

    let adb_json = crate::adb::devices_json_no_probe().unwrap_or_else(|_| "[]".to_string());
    let adb_devices: Vec<AdbDevice> = parse_adb_rows(&adb_json);

    let adb_serials: std::collections::HashSet<String> = adb_devices
        .iter()
        .map(|a| normalize_serial(Some(&a.serial)))
        .filter(|s| !s.is_empty())
        .collect();

    let mut claimed: std::collections::HashSet<String> = std::collections::HashSet::new();
    let mut rows = Vec::new();

    for usb in phones {
        let serial = normalize_serial(usb.serial.as_deref());
        let adb_match = if serial.is_empty() {
            None
        } else {
            adb_devices
                .iter()
                .find(|a| normalize_serial(Some(&a.serial)) == serial)
                .cloned()
        };
        if let Some(a) = &adb_match {
            claimed.insert(normalize_serial(Some(&a.serial)));
        }
        rows.push(DeviceRow {
            key: device_key(Some(&usb), adb_match.as_ref()),
            label: device_label(&usb, &adb_serials),
            transports: compute_transports(&usb, &adb_serials),
            vid: usb.vid,
            pid: usb.pid,
            bus: usb.bus,
            address: usb.address,
            serial: usb.serial.clone(),
            is_adb: false,
            adb_state: adb_match.map(|a| a.state.clone()),
            usb_product: usb.product.clone(),
            usb_manufacturer: usb.manufacturer.clone(),
            mode: classify_mode(usb.vid, usb.pid, &usb.interfaces),
        });
    }

    for adb in adb_devices {
        let serial = normalize_serial(Some(&adb.serial));
        if serial.is_empty() || claimed.contains(&serial) {
            continue;
        }
        rows.push(DeviceRow {
            key: format!("adb:{}", serial),
            label: format!("{} [{}]", adb.serial, adb.state),
            transports: vec!["ADB".to_string()],
            vid: 0,
            pid: 0,
            bus: 0,
            address: 0,
            serial: Some(adb.serial.clone()),
            is_adb: true,
            adb_state: Some(adb.state.clone()),
            usb_product: None,
            usb_manufacturer: None,
            mode: "android-adb".to_string(),
        });
    }

    serde_json::to_string_pretty(&rows).map_err(|e| crate::error::BridgeError::Io(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn classify_samsung_odin() {
        assert_eq!(classify_mode(0x04E8, 0x685D, &[]), "samsung-odin");
    }

    #[test]
    fn device_row_carries_mode_for_python() {
        // Regression: detect-merged rows previously had no `mode` field, so
        // every Python consumer keying on it (mtp.py, mtk.py, device_info.py,
        // GUI buckets) silently saw "" and mis-bucketed every device.
        let row = DeviceRow {
            key: "usb:04e8:685d@1:3".into(),
            label: "SAMSUNG Mobile USB".into(),
            transports: vec!["Download mode".into()],
            vid: 0x04E8,
            pid: 0x685D,
            bus: 1,
            address: 3,
            serial: None,
            is_adb: false,
            adb_state: None,
            usb_product: Some("SAMSUNG Mobile USB".into()),
            usb_manufacturer: Some("SAMSUNG".into()),
            mode: "samsung-odin".into(),
        };
        let json = serde_json::to_string(&row).unwrap();
        assert!(
            json.contains(r#""mode":"samsung-odin""#),
            "row JSON: {json}"
        );
    }
}
