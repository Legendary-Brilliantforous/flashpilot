//! Configuration types

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;

/// USB device information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceInfo {
    pub vid: u16,
    pub pid: u16,
    pub bus: u8,
    pub address: u8,
    pub product: Option<String>,
    pub manufacturer: Option<String>,
    pub serial: Option<String>,
    pub interfaces: Vec<InterfaceInfo>,
    pub is_samsung: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InterfaceInfo {
    pub number: u8,
    pub class: u8,
    pub subclass: u8,
    pub protocol: u8,
    pub endpoints: Vec<EndpointInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EndpointInfo {
    pub address: u8,
    pub direction: String,
    pub transfer_type: String,
    pub max_packet_size: u16,
}

/// Global application configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    pub usb: UsbConfig,
    pub logging: LoggingConfig,
    pub defaults: DefaultsConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UsbConfig {
    pub timeout_ms: u64,
    pub bulk_timeout_ms: u64,
    pub control_timeout_ms: u64,
    pub retry_count: u32,
    pub auto_detach_kernel: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoggingConfig {
    pub level: String,
    pub json_output: bool,
    pub log_usb_traffic: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DefaultsConfig {
    pub samsung_packet_size: u32,
    pub mtk_packet_size: u32,
    pub flash_timeout_secs: u64,
}

/// Samsung/Odin specific configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SamsungConfig {
    pub pit_path: Option<std::path::PathBuf>,
    pub use_csc_pit: bool,
    pub packet_size: u32,
    pub session_timeout_ms: u64,
    pub allow_progress_codes: bool,
    pub reboot_after_flash: bool,
}

/// MediaTek specific configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MtkConfig {
    pub da_path: Option<std::path::PathBuf>,
    pub scatter_path: Option<std::path::PathBuf>,
    pub firmware_dir: Option<std::path::PathBuf>,
    pub bypass_mode: String,
    pub skip_auth: bool,
    pub force_preloader: bool,
    pub packet_size: u32,
    pub da_timeout_ms: u64,
}

/// Operation context passed through the call chain
#[derive(Debug, Clone)]
pub struct OperationContext {
    pub config: AppConfig,
    pub samsung: SamsungConfig,
    pub mtk: MtkConfig,
    pub device_info: Option<DeviceInfo>,
    pub extras: std::collections::HashMap<String, String>,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            usb: UsbConfig {
                timeout_ms: 5000,
                bulk_timeout_ms: 30000,
                control_timeout_ms: 5000,
                retry_count: 3,
                auto_detach_kernel: true,
            },
            logging: LoggingConfig {
                level: "info".to_string(),
                json_output: false,
                log_usb_traffic: false,
            },
            defaults: DefaultsConfig {
                samsung_packet_size: 1048576,
                mtk_packet_size: 1048576,
                flash_timeout_secs: 300,
            },
        }
    }
}

impl Default for SamsungConfig {
    fn default() -> Self {
        Self {
            pit_path: None,
            use_csc_pit: true,
            packet_size: 1048576,
            session_timeout_ms: 120000,
            allow_progress_codes: true,
            reboot_after_flash: true,
        }
    }
}

impl Default for MtkConfig {
    fn default() -> Self {
        Self {
            da_path: None,
            scatter_path: None,
            firmware_dir: None,
            bypass_mode: "standard".to_string(),
            skip_auth: false,
            force_preloader: true,
            packet_size: 1048576,
            da_timeout_ms: 10000,
        }
    }
}

impl OperationContext {
    pub fn new() -> Self {
        Self {
            config: AppConfig::default(),
            samsung: SamsungConfig::default(),
            mtk: MtkConfig::default(),
            device_info: None,
            extras: std::collections::HashMap::new(),
        }
    }

    pub fn with_device(mut self, info: DeviceInfo) -> Self {
        self.device_info = Some(info);
        self
    }

    pub fn with_extra(mut self, key: &str, value: &str) -> Self {
        self.extras.insert(key.to_string(), value.to_string());
        self
    }
}