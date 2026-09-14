//! Device row composition for GUI: USB + ADB merged rows (filtering lives in usb::filtering)
#![allow(dead_code)] // list_devices_filtered is Python-facing API surface

use crate::error::Result;
use crate::usb::filtering::{
    compute_transports, device_key, device_label, normalize_serial,
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
}

/// Merge USB + ADB into GUI rows.
pub fn list_devices_filtered() -> Result<String> {
    list_devices_filtered_vid(None)
}

/// Merge USB + ADB into GUI rows, optionally restricted to a vendor ID.
pub fn list_devices_filtered_vid(vid_filter: Option<u16>) -> Result<String> {
    let usb_devices = crate::usb::collect_devices(vid_filter)?;
    let phones = crate::usb::filtering::filter_phones(&usb_devices);

    let adb_json = crate::adb::devices_json().unwrap_or_else(|_| "[]".to_string());
    let adb_devices: Vec<AdbDevice> = serde_json::from_str(&adb_json).unwrap_or_default();

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
            adb_devices.iter().find(|a| normalize_serial(Some(&a.serial)) == serial).cloned()
        };
        if let Some(a) = &adb_match {
            claimed.insert(a.serial.clone());
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
        });
    }

    serde_json::to_string_pretty(&rows).map_err(|e| crate::error::BridgeError::Io(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::usb::filtering::classify_mode;

    #[test]
    fn classify_samsung_odin() {
        assert_eq!(classify_mode(0x04E8, 0x685D, &[]), "samsung-odin");
    }
}