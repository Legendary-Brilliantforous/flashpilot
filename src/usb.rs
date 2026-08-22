//! USB device abstraction

use crate::error::{Result, BridgeError, UsbError};
use crate::config::{DeviceInfo, InterfaceInfo, EndpointInfo};

// Re-export types for backward compatibility
pub type UsbDeviceInfo = DeviceInfo;
pub type UsbInterface = InterfaceInfo;
use rusb::{Context, DeviceHandle, UsbContext, Direction, TransferType};
use std::time::Duration;
use std::collections::HashMap;

/// Samsung download-mode PIDs (mirrors python/core/frp.py `_ODIN_PIDS`).
pub const SAMSUNG_ODIN_PIDS: &[u16] = &[0x6601, 0x685d, 0x68c3, 0x68ef, 0x4eee, 0x4eef];

/// Coarse protocol/mode hint so the GUI can label a device without keeping a
/// VID/PID table in Python. Kept conservative: a PID that is also used by a
/// normal-boot ADB composite (e.g. 0x685d) still reports "samsung-odin" here;
/// the Python layer re-checks the ADB signature to disambiguate.
pub fn mode_hint(vid: u16, pid: u16, interfaces: &[InterfaceInfo]) -> String {
    let has_adb = interfaces.iter().any(|i| i.class == 255 && i.subclass == 66 && i.protocol == 1);
    let has_mtp = interfaces.iter().any(|i| i.class == 6);
    let has_hid = interfaces.iter().any(|i| i.class == 3);

    match vid {
        0x05c6 if pid == 0x9008 => "qualcomm-edl".to_string(),
        0x0e8d => "mediatek".to_string(),
        0x04e8 => {
            if SAMSUNG_ODIN_PIDS.contains(&pid) {
                "samsung-odin".to_string()
            } else if has_adb {
                "android-adb".to_string()
            } else if has_mtp {
                "android-mtp".to_string()
            } else if has_hid {
                "samsung-hid".to_string()
            } else {
                "samsung".to_string()
            }
        }
        _ => {
            if has_adb {
                "android-adb".to_string()
            } else if has_mtp {
                "android-mtp".to_string()
            } else if has_hid {
                "hid".to_string()
            } else {
                "other".to_string()
            }
        }
    }
}

/// USB device wrapper
pub struct UsbDevice {
    handle: DeviceHandle<Context>,
    info: DeviceInfo,
    claimed_interfaces: Vec<u8>,
    endpoints: HashMap<u8, EndpointConfig>,
}

#[derive(Debug, Clone)]
pub struct EndpointConfig {
    pub address: u8,
    pub direction: Direction,
    pub transfer_type: TransferType,
    pub max_packet_size: u16,
    pub interval: u8,
}

impl UsbDevice {
    /// Open device by VID/PID and bus/address
    pub fn open(vid: u16, pid: u16, bus: u8, address: u8) -> Result<Self> {
        let context = Context::new()?;
        let device = context
            .devices()?
            .iter()
            .find(|d| {
                let desc = d.device_descriptor().ok();
                desc.as_ref().map_or(false, |desc| {
                    desc.vendor_id() == vid && desc.product_id() == pid
                }) && d.bus_number() == bus && d.address() == address
            })
            .ok_or(BridgeError::Usb(UsbError::DeviceNotFound))?;

        let handle = device.open()?;
        
        let device_desc = device.device_descriptor()?;
        let config_desc = device.active_config_descriptor().ok()
            .or_else(|| device.config_descriptor(0).ok());
        
        let mut interfaces = Vec::new();
        let mut endpoints = HashMap::new();
        
        if let Some(config_desc) = config_desc {
            for interface in config_desc.interfaces() {
                let mut iface_endpoints = Vec::new();
                for interface_desc in interface.descriptors() {
                    for endpoint_desc in interface_desc.endpoint_descriptors() {
                        let ep_config = EndpointConfig {
                            address: endpoint_desc.address(),
                            direction: endpoint_desc.direction(),
                            transfer_type: endpoint_desc.transfer_type(),
                            max_packet_size: endpoint_desc.max_packet_size(),
                            interval: endpoint_desc.interval(),
                        };
                        endpoints.insert(endpoint_desc.address(), ep_config.clone());
                        iface_endpoints.push(EndpointInfo {
                            address: endpoint_desc.address(),
                            direction: match endpoint_desc.direction() {
                                Direction::In => "in".to_string(),
                                Direction::Out => "out".to_string(),
                            },
                            transfer_type: match endpoint_desc.transfer_type() {
                                TransferType::Control => "control".to_string(),
                                TransferType::Bulk => "bulk".to_string(),
                                TransferType::Interrupt => "interrupt".to_string(),
                                TransferType::Isochronous => "isochronous".to_string(),
                            },
                            max_packet_size: endpoint_desc.max_packet_size(),
                        });
                    }
                }
                interfaces.push(InterfaceInfo {
                    number: interface.number(),
                    class: interface.descriptors().next().map(|d| d.class_code()).unwrap_or(0),
                    subclass: interface.descriptors().next().map(|d| d.sub_class_code()).unwrap_or(0),
                    protocol: interface.descriptors().next().map(|d| d.protocol_code()).unwrap_or(0),
                    endpoints: iface_endpoints,
                });
            }
        }

        let info = {
            // Read string descriptors (best effort) so callers get the same
            // rich info collect_devices() provides.
            let mut product = None;
            let mut manufacturer = None;
            let mut serial = None;
            if device_desc.manufacturer_string_index().is_some() {
                manufacturer = handle
                    .read_manufacturer_string_ascii(&device_desc)
                    .ok()
                    .filter(|s| !s.is_empty());
            }
            if device_desc.product_string_index().is_some() {
                product = handle
                    .read_product_string_ascii(&device_desc)
                    .ok()
                    .filter(|s| !s.is_empty());
            }
            if device_desc.serial_number_string_index().is_some() {
                serial = handle
                    .read_serial_number_string_ascii(&device_desc)
                    .ok()
                    .filter(|s| !s.is_empty());
            }

            DeviceInfo {
                vid,
                pid,
                bus,
                address,
                product,
                manufacturer,
                serial,
                is_samsung: vid == 0x04e8,
                configs: device_desc.num_configurations() as u32,
                active_config: device
                    .active_config_descriptor()
                    .ok()
                    .map(|c| c.number())
                    .unwrap_or(0),
                device_class: device_desc.class_code(),
                bcd_usb: bcd_version_u16(device_desc.usb_version()),
                bcd_device: bcd_version_u16(device_desc.device_version()),
                device_speed: device.speed() as u8,
                port_numbers: device
                    .port_numbers()
                    .unwrap_or_default()
                    .iter()
                    .map(|p| p.to_string())
                    .collect::<Vec<_>>()
                    .join("-"),
                max_packet_size0: device_desc.max_packet_size(),
                mode: mode_hint(vid, pid, &interfaces),
                interfaces,
            }
        };

        Ok(Self {
            handle,
            info,
            claimed_interfaces: Vec::new(),
            endpoints,
        })
    }

    /// Open by target string "bus:address"
    pub fn open_target(vid: u16, pid: u16, target: &str) -> Result<Self> {
        let parts: Vec<&str> = target.split(':').collect();
        if parts.len() != 2 {
            return Err(BridgeError::InvalidArgument("target must be 'bus:address'".to_string()));
        }
        let bus = parts[0].parse().map_err(|_| BridgeError::InvalidArgument("invalid bus".to_string()))?;
        let address = parts[1].parse().map_err(|_| BridgeError::InvalidArgument("invalid address".to_string()))?;
        Self::open(vid, pid, bus, address)
    }

    /// Claim interface
    pub fn claim_interface(&mut self, interface_num: u8) -> Result<()> {
        if self.claimed_interfaces.contains(&interface_num) {
            return Ok(());
        }
        self.handle.claim_interface(interface_num)
            .map_err(|e| BridgeError::Usb(UsbError::ClaimInterfaceFailed))?;
        self.claimed_interfaces.push(interface_num);
        Ok(())
    }

    /// Release interface
    pub fn release_interface(&mut self, interface_num: u8) -> Result<()> {
        if let Some(pos) = self.claimed_interfaces.iter().position(|&x| x == interface_num) {
            self.handle.release_interface(interface_num)?;
            self.claimed_interfaces.remove(pos);
        }
        Ok(())
    }

    /// Set auto detach kernel driver
    pub fn set_auto_detach_kernel_driver(&mut self, auto: bool) -> Result<()> {
        self.handle.set_auto_detach_kernel_driver(auto)?;
        Ok(())
    }

    /// Bulk write
    pub fn write_bulk(&self, endpoint: u8, data: &[u8], timeout: Duration) -> Result<usize> {
        self.handle.write_bulk(endpoint, data, timeout)
            .map_err(|e| BridgeError::Usb(UsbError::TransferFailed(e.to_string())))
    }

    /// Bulk read
    pub fn read_bulk(&self, endpoint: u8, buf: &mut [u8], timeout: Duration) -> Result<usize> {
        self.handle.read_bulk(endpoint, buf, timeout)
            .map_err(|e| BridgeError::Usb(UsbError::TransferFailed(e.to_string())))
    }

    /// Control transfer
    pub fn control_transfer(
        &self,
        request_type: u8,
        request: u8,
        value: u16,
        index: u16,
        data: &mut [u8],
        timeout: Duration,
    ) -> Result<usize> {
        self.handle
            .write_control(request_type, request, value, index, data, timeout)
            .map_err(|e| BridgeError::Usb(UsbError::TransferFailed(e.to_string())))
    }

    /// Read exact bytes
    pub fn read_exact(&self, endpoint: u8, mut buf: &mut [u8], timeout: Duration) -> Result<()> {
        let mut total = 0;
        while total < buf.len() {
            let n = self.read_bulk(endpoint, &mut buf[total..], timeout)?;
            if n == 0 {
                return Err(BridgeError::Usb(UsbError::TransferFailed("EOF".to_string())));
            }
            total += n;
        }
        Ok(())
    }

    /// Find bulk endpoints
    pub fn find_bulk_endpoints(&self, interface: u8) -> Option<(u8, u8)> {
        let mut in_ep = None;
        let mut out_ep = None;
        
        for iface in &self.info.interfaces {
            if iface.number == interface {
                for ep in &iface.endpoints {
                    if ep.transfer_type == "bulk" {
                        match ep.direction.as_str() {
                            "in" => in_ep = Some(ep.address),
                            "out" => out_ep = Some(ep.address),
                            _ => {}
                        }
                    }
                }
            }
        }
        
        match (in_ep, out_ep) {
            (Some(in_ep), Some(out_ep)) => Some((in_ep, out_ep)),
            _ => None,
        }
    }

    /// Get device info
    pub fn info(&self) -> &DeviceInfo {
        &self.info
    }

    /// Get endpoint config
    pub fn endpoint_config(&self, address: u8) -> Option<&EndpointConfig> {
        self.endpoints.get(&address)
    }
}

/// Collect all USB devices matching criteria
pub fn collect_devices(vid_filter: Option<u16>) -> Result<Vec<DeviceInfo>> {
    let context = Context::new()?;
    let mut devices = Vec::new();
    
    for device in context.devices()?.iter() {
        let desc = match device.device_descriptor() {
            Ok(d) => d,
            Err(e) => {
                eprintln!(
                    "[usb] skip dev bus={} addr={}: device_descriptor: {e}",
                    device.bus_number(),
                    device.address()
                );
                continue;
            }
        };
        
        if let Some(vid) = vid_filter {
            if desc.vendor_id() != vid {
                continue;
            }
        }

        // Download-mode / EDL / preloader devices often have NO active
        // configuration (config value 0), which makes active_config_descriptor
        // fail. Falling back to the first available config descriptor (and
        // finally to an empty interface list) keeps such devices visible to
        // detection instead of silently dropping them.
        let config_desc = device.active_config_descriptor().ok()
            .or_else(|| device.config_descriptor(0).ok());
        
        let mut interfaces = Vec::new();
        if let Some(config_desc) = config_desc {
            for interface in config_desc.interfaces() {
                for interface_desc in interface.descriptors() {
                    let mut iface_endpoints = Vec::new();
                    for endpoint_desc in interface_desc.endpoint_descriptors() {
                        iface_endpoints.push(EndpointInfo {
                            address: endpoint_desc.address(),
                            direction: match endpoint_desc.direction() {
                                Direction::In => "in".to_string(),
                                Direction::Out => "out".to_string(),
                            },
                            transfer_type: match endpoint_desc.transfer_type() {
                                TransferType::Control => "control".to_string(),
                                TransferType::Bulk => "bulk".to_string(),
                                TransferType::Interrupt => "interrupt".to_string(),
                                TransferType::Isochronous => "isochronous".to_string(),
                            },
                            max_packet_size: endpoint_desc.max_packet_size(),
                        });
                    }
                    interfaces.push(InterfaceInfo {
                        number: interface.number(),
                        class: interface_desc.class_code(),
                        subclass: interface_desc.sub_class_code(),
                        protocol: interface_desc.protocol_code(),
                        endpoints: iface_endpoints,
                    });
                }
            }
        }
        
        // Read string descriptors (manufacturer / product / serial) so the GUI
        // can show full device info instead of just VID:PID.
        let mut product = None;
        let mut manufacturer = None;
        let mut serial = None;
        if let Ok(handle) = device.open() {
            if desc.manufacturer_string_index().is_some() {
                manufacturer = handle
                    .read_manufacturer_string_ascii(&desc)
                    .ok()
                    .filter(|s| !s.is_empty());
            }
            if desc.product_string_index().is_some() {
                product = handle
                    .read_product_string_ascii(&desc)
                    .ok()
                    .filter(|s| !s.is_empty());
            }
            if desc.serial_number_string_index().is_some() {
                serial = handle
                    .read_serial_number_string_ascii(&desc)
                    .ok()
                    .filter(|s| !s.is_empty());
            }
        }

        let vid = desc.vendor_id();
        let pid = desc.product_id();
        devices.push(DeviceInfo {
            vid,
            pid,
            bus: device.bus_number(),
            address: device.address(),
            product,
            manufacturer,
            serial,
            is_samsung: vid == 0x04e8,
            configs: desc.num_configurations() as u32,
            active_config: device
                .active_config_descriptor()
                .ok()
                .map(|c| c.number())
                .unwrap_or(0),
            device_class: desc.class_code(),
            bcd_usb: bcd_version_u16(desc.usb_version()),
            bcd_device: bcd_version_u16(desc.device_version()),
            device_speed: device.speed() as u8,
            port_numbers: device
                .port_numbers()
                .unwrap_or_default()
                .iter()
                .map(|p| p.to_string())
                .collect::<Vec<_>>()
                .join("-"),
            max_packet_size0: desc.max_packet_size(),
            mode: mode_hint(vid, pid, &interfaces),
            interfaces,
        });
    }

    Ok(devices)
}

/// Find bulk endpoints for a device
pub fn find_bulk_endpoints(device: &DeviceInfo, interface_num: u8) -> Option<(u8, u8)> {
    for iface in &device.interfaces {
        if iface.number == interface_num {
            let mut in_ep = None;
            let mut out_ep = None;
            for ep in &iface.endpoints {
                if ep.transfer_type == "bulk" {
                    match ep.direction.as_str() {
                        "in" => in_ep = Some(ep.address),
                        "out" => out_ep = Some(ep.address),
                        _ => {}
                    }
                }
            }
            if let (Some(in_ep), Some(out_ep)) = (in_ep, out_ep) {
                return Some((in_ep, out_ep));
            }
        }
    }
    None
}

/// Detect USB devices with optional VID filter
pub fn detect(vid_filter: Option<u16>) -> Result<String> {
    let devices = collect_devices(vid_filter)?;
    serde_json::to_string_pretty(&devices).map_err(|e| crate::error::BridgeError::Io(e.to_string()))
}

/// Convert a rusb BCD version back to its raw 0xJJMN encoding (e.g. 2.0 ->
/// 0x0200) so the JSON contract stays a plain number.
fn bcd_version_u16(v: rusb::Version) -> u16 {
    let (major, minor, sub_minor) = (v.0 as u16, v.1 as u16, v.2 as u16);
    ((major / 10) << 12) | ((major % 10) << 8) | (minor << 4) | sub_minor
}

/// Set USB configuration on a device
pub fn set_config(target: &str, config_idx: usize) -> Result<String> {
    let parts: Vec<&str> = target.split(':').collect();
    if parts.len() != 2 {
        return Err(crate::error::BridgeError::InvalidArgument("target must be 'bus:address'".into()));
    }
    let bus: u8 = parts[0].parse().map_err(|_| crate::error::BridgeError::InvalidArgument("invalid bus".into()))?;
    let address: u8 = parts[1].parse().map_err(|_| crate::error::BridgeError::InvalidArgument("invalid address".into()))?;
    
    let devices = collect_devices(None)?;
    let dev = devices.iter()
        .find(|d| d.bus == bus && d.address == address)
        .ok_or(crate::error::BridgeError::Usb(crate::error::UsbError::DeviceNotFound))?;
    
    let context = rusb::Context::new()?;
    let device = context
        .devices()?
        .iter()
        .find(|d| {
            let desc = d.device_descriptor().ok();
            desc.as_ref().map_or(false, |desc| {
                desc.vendor_id() == dev.vid && desc.product_id() == dev.pid
            }) && d.bus_number() == bus && d.address() == address
        })
        .ok_or(crate::error::BridgeError::Usb(crate::error::UsbError::DeviceNotFound))?;
    
    let handle = device.open()?;
    handle.set_active_configuration(config_idx as u8)
        .map_err(|e| crate::error::BridgeError::Usb(crate::error::UsbError::TransferFailed(e.to_string())))?;
    
    Ok(serde_json::json!({"status": "configuration set", "config": config_idx}).to_string())
}

/// Detach kernel drivers from all interfaces of a device
pub fn detach_kernel_drivers(target: &str) -> Result<String> {
    let parts: Vec<&str> = target.split(':').collect();
    if parts.len() != 2 {
        return Err(crate::error::BridgeError::InvalidArgument("target must be 'bus:address'".into()));
    }
    let bus: u8 = parts[0].parse().map_err(|_| crate::error::BridgeError::InvalidArgument("invalid bus".into()))?;
    let address: u8 = parts[1].parse().map_err(|_| crate::error::BridgeError::InvalidArgument("invalid address".into()))?;
    
    let devices = collect_devices(None)?;
    let dev = devices.iter()
        .find(|d| d.bus == bus && d.address == address)
        .ok_or(crate::error::BridgeError::Usb(crate::error::UsbError::DeviceNotFound))?;
    
    let context = rusb::Context::new()?;
    let device = context
        .devices()?
        .iter()
        .find(|d| {
            let desc = d.device_descriptor().ok();
            desc.as_ref().map_or(false, |desc| {
                desc.vendor_id() == dev.vid && desc.product_id() == dev.pid
            }) && d.bus_number() == bus && d.address() == address
        })
        .ok_or(crate::error::BridgeError::Usb(crate::error::UsbError::DeviceNotFound))?;
    
let handle = device.open()?;
    let _ = handle.set_auto_detach_kernel_driver(true);

    // Detach the *matched* device's interfaces (not devices[0] - with several
    // phones plugged in that would release the wrong device).
    for iface in &dev.interfaces {
        let _ = handle.release_interface(iface.number);
    }
    
    Ok(serde_json::json!({"status": "kernel drivers detached"}).to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Regression: download-mode / EDL / preloader devices have no active
    /// configuration, so collect_devices must still report them (with an empty
    /// interface list) instead of dropping them. This exercises the exact JSON
    /// contract the Python layer parses from `detect` / `detect-all`.
    #[test]
    fn download_mode_device_without_active_config_is_reported() {
        let info = DeviceInfo {
            vid: 0x04e8,
            pid: 0x685d,
            bus: 1,
            address: 3,
            product: Some("SAMSUNG USB".into()),
            manufacturer: Some("SAMSUNG".into()),
            serial: None,
            interfaces: Vec::new(),
            is_samsung: true,
            configs: 1,
            active_config: 0,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 3,
            port_numbers: "1-2".into(),
            max_packet_size0: 64,
            mode: mode_hint(0x04e8, 0x685d, &[]),
        };

        let json = serde_json::to_string(&info).unwrap();
        let parsed: DeviceInfo = serde_json::from_str(&json).unwrap();

        assert!(parsed.is_samsung);
        assert!(parsed.interfaces.is_empty());
        assert_eq!(parsed.vid, 0x04e8);
        assert_eq!(parsed.pid, 0x685d);
        assert_eq!(parsed.bus, 1);
        assert_eq!(parsed.address, 3);
        // New detection fields survive the JSON round-trip.
        assert_eq!(parsed.configs, 1);
        assert_eq!(parsed.active_config, 0);
        assert_eq!(parsed.device_speed, 3);
        assert_eq!(parsed.port_numbers, "1-2");
        assert_eq!(parsed.mode, "samsung-odin");
    }

    /// mode_hint must classify the common flashing stages so the GUI can
    /// label a device without its own VID/PID tables.
    #[test]
    fn mode_hint_classifies_flashing_stages() {
        let adb_iface = |class: u8| InterfaceInfo {
            number: 0,
            class,
            subclass: if class == 255 { 66 } else { 0 },
            protocol: if class == 255 { 1 } else { 0 },
            endpoints: Vec::new(),
        };

        // Qualcomm EDL (Sahara / Firehose)
        assert_eq!(mode_hint(0x05c6, 0x9008, &[]), "qualcomm-edl");
        // MediaTek BROM / preloader / DA
        assert_eq!(mode_hint(0x0e8d, 0x2000, &[]), "mediatek");
        // Samsung download-mode PIDs
        for pid in SAMSUNG_ODIN_PIDS {
            assert_eq!(mode_hint(0x04e8, *pid, &[]), "samsung-odin");
        }
        // Normal-boot Samsung composite with ADB wins over generic labels
        // only when the PID is not an Odin PID (Python disambiguates further).
        assert_eq!(mode_hint(0x04e8, 0x6860, &[adb_iface(255)]), "android-adb");
        assert_eq!(mode_hint(0x04e8, 0x6860, &[adb_iface(6)]), "android-mtp");
        assert_eq!(mode_hint(0x04e8, 0x6860, &[adb_iface(3)]), "samsung-hid");
        assert_eq!(mode_hint(0x04e8, 0x6860, &[]), "samsung");
        // Non-Samsung ADB/MTP
        assert_eq!(mode_hint(0x18d1, 0x4ee7, &[adb_iface(255)]), "android-adb");
        assert_eq!(mode_hint(0x1234, 0x5678, &[]), "other");
    }
}