//! Device row composition for GUI: USB + ADB merged rows (filtering lives in usb::filtering)
#![allow(dead_code)] // list_devices_filtered is Python-facing API surface

use crate::error::Result;
use crate::usb::filtering::{
    adb_extra_field, brand_from_vid, brand_hint, classify_mode, compute_transports, device_key,
    device_label, normalize_serial, parse_adb_rows, AdbDevice,
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
    /// Real model from `adb devices -l` (`model:` extra) when the phone is
    /// authorized. No probe is opened for this — the server row is free.
    pub model: Option<String>,
    /// Best-effort brand family from USB/ADB strings (SAMSUNG/TECNO/ITEL/…).
    pub brand: Option<String>,
    /// Form factor (phone/tablet/watch/tv/…). Only a live ADB
    /// `ro.build.characteristics` probe can fill this, so the zero-touch
    /// USB poll leaves it `None` rather than guessing.
    pub device_type: Option<String>,
    /// Rust mode classification (`classify_mode`): the single source of
    /// truth Python groups on (mtp.py/mtk.py/device_info.py/GUI buckets).
    /// `android-adb` for ADB-only rows (no USB leg to classify).
    pub mode: String,
}

/// Identity fields shared by USB and ADB-only rows: model from the ADB
/// `model:` extra, brand from every available string.
fn row_identity(
    usb: Option<&crate::config::DeviceInfo>,
    adb: Option<&AdbDevice>,
) -> (Option<String>, Option<String>) {
    let model = adb.and_then(|a| adb_extra_field(&a.extra, "model"));
    let mut text = String::new();
    // ADB extras also carry `product:`/`device:` — include them so a brand
    // spelled into the product string (common for OEM VID stages) is found.
    if let Some(a) = adb {
        for key in ["product", "device"] {
            if let Some(v) = adb_extra_field(&a.extra, key) {
                text.push_str(&v);
                text.push(' ');
            }
        }
    }
    if let Some(u) = usb {
        if let Some(m) = &u.manufacturer {
            text.push_str(m);
            text.push(' ');
        }
        if let Some(p) = &u.product {
            text.push_str(p);
            text.push(' ');
        }
    }
    if let Some(m) = &model {
        text.push_str(m);
        text.push(' ');
    }
    // Strings first, then the vendor ID (a bare Samsung Odin stage has no
    // product string but the VID is still Samsung).
    let brand = brand_hint(text.trim())
        .or_else(|| usb.and_then(|u| brand_from_vid(u.vid)));
    (model, brand)
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
        let (model, brand) = row_identity(Some(&usb), adb_match.as_ref());
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
            adb_state: adb_match.as_ref().map(|a| a.state.clone()),
            usb_product: usb.product.clone(),
            usb_manufacturer: usb.manufacturer.clone(),
            model,
            brand,
            // No live probe in the zero-touch poll: never guess a form factor.
            device_type: None,
            mode: classify_mode(usb.vid, usb.pid, &usb.interfaces),
        });
    }

    for adb in adb_devices {
        let serial = normalize_serial(Some(&adb.serial));
        if serial.is_empty() || claimed.contains(&serial) {
            continue;
        }
        let (model, brand) = row_identity(None, Some(&adb));
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
            model,
            brand,
            device_type: None,
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
            model: None,
            brand: Some("SAMSUNG".into()),
            device_type: None,
            mode: "samsung-odin".into(),
        };
        let json = serde_json::to_string(&row).unwrap();
        assert!(
            json.contains(r#""mode":"samsung-odin""#),
            "row JSON: {json}"
        );
    }

    #[test]
    fn adb_extra_field_reads_model_and_skips_unknown() {
        let extra = "product:beyond1 model:SM_G973F device:beyond1 transport_id:1";
        assert_eq!(
            adb_extra_field(extra, "model").as_deref(),
            Some("SM_G973F")
        );
        assert_eq!(
            adb_extra_field(extra, "product").as_deref(),
            Some("beyond1")
        );
        assert_eq!(adb_extra_field("model:unknown device:x", "model"), None);
        assert_eq!(adb_extra_field("model: device:x", "model"), None);
        assert_eq!(adb_extra_field(extra, "missing"), None);
    }

    #[test]
    fn row_identity_prefers_the_adb_model_and_finds_the_brand() {
        // ADB strings carry the brand in `product:` even when the model code
        // itself (SM_G973F / KG6-GL) has no family word.
        let adb = AdbDevice {
            serial: "R58M123456A".into(),
            state: "device".into(),
            extra: "product:SAMSUNG Galaxy S23 model:SM_G973F device:SM_G973F".into(),
        };
        let (model, brand) = row_identity(None, Some(&adb));
        assert_eq!(model.as_deref(), Some("SM_G973F"));
        assert_eq!(brand.as_deref(), Some("SAMSUNG"));

        let tecno = AdbDevice {
            serial: "T123456789".into(),
            state: "device".into(),
            extra: "product:TECNO KG6 model:KG6-GL".into(),
        };
        let (model, brand) = row_identity(None, Some(&tecno));
        assert_eq!(model.as_deref(), Some("KG6-GL"));
        assert_eq!(brand.as_deref(), Some("TECNO"));

        // USB strings alone still give the brand, but never invent a model.
        let usb = crate::config::DeviceInfo {
            vid: 0x0E8D,
            pid: 0x2000,
            bus: 1,
            address: 2,
            product: Some("TECNO Mobile".into()),
            manufacturer: Some("TECNO".into()),
            serial: None,
            interfaces: Vec::new(),
            is_samsung: false,
            configs: 1,
            active_config: 1,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 3,
            port_numbers: "1-2".into(),
            max_packet_size0: 64,
            mode: "mediatek".into(),
        };
        let (model, brand) = row_identity(Some(&usb), None);
        assert_eq!(model, None);
        assert_eq!(brand.as_deref(), Some("TECNO"));

        // A stringless Samsung stage still names its brand through the VID.
        let mut samsung = usb.clone();
        samsung.vid = 0x04E8;
        samsung.product = None;
        samsung.manufacturer = None;
        let (model, brand) = row_identity(Some(&samsung), None);
        assert_eq!(model, None);
        assert_eq!(brand.as_deref(), Some("SAMSUNG"));
    }
}
