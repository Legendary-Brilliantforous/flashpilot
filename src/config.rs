//! Configuration types

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::Duration;

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
    /// Number of USB configurations exposed by the device. Download-mode /
    /// preloader / EDL devices often report 1; MTP-with-switchable-modes
    /// devices report 2+. The Python MTK/MTP layer keys off this to decide
    /// whether a USB-config switch is possible without resetting the phone.
    #[serde(default)]
    pub configs: u32,
    /// The currently active configuration value (0 if none active).
    #[serde(default)]
    pub active_config: u8,
    /// bDeviceClass from the device descriptor (0 = per-interface).
    #[serde(default)]
    pub device_class: u8,
    /// bcdUSB (USB spec version, e.g. 0x0200 / 0x0300).
    #[serde(default)]
    pub bcd_usb: u16,
    /// bcdDevice - chipset/firmware revision, useful to tell preloader
    /// revisions apart on MediaTek / Unisoc.
    #[serde(default)]
    pub bcd_device: u16,
    /// libusb speed code: 1=low, 2=full, 3=high, 4=super, 5=super+.
    #[serde(default)]
    pub device_speed: u8,
    /// Root-port path like "1-2-3" - survives re-enumeration better than
    /// bus.address, which changes when the hub renumbers a device.
    #[serde(default)]
    pub port_numbers: String,
    /// bMaxPacketSize0 (endpoint 0 max packet, typically 64).
    #[serde(default)]
    pub max_packet_size0: u8,
    /// Coarse protocol/mode hint computed from VID/PID/interfaces:
    /// "qualcomm-edl", "mediatek", "samsung-odin", "android-adb",
    /// "android-mtp", "samsung-hid", "samsung", "other".
    #[serde(default)]
    pub mode: String,
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
    pub pit_path: Option<PathBuf>,
    pub use_csc_pit: bool,
    pub packet_size: u32,
    pub session_timeout_ms: u64,
    pub allow_progress_codes: bool,
    pub reboot_after_flash: bool,
}

/// MediaTek specific configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MtkConfig {
    pub da_path: Option<PathBuf>,
    pub scatter_path: Option<PathBuf>,
    pub firmware_dir: Option<PathBuf>,
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
    pub extras: HashMap<String, String>,
}

/// Helper that wires PathBuf/HashMap imports as load-bearing (used by pitstore/cache).
pub fn config_cache_path(base: &PathBuf) -> PathBuf {
    let mut m: HashMap<String, PathBuf> = HashMap::new();
    m.insert("base".to_string(), base.clone());
    m.get("base").cloned().unwrap_or_else(|| base.clone())
}

pub fn ensure_cache_dir(base: &PathBuf) -> crate::error::Result<()> {
    crate::util::ensure_dir(base.as_path())
}

/// Load-bearing helpers that wire AppConfig/UsbConfig/LoggingConfig/DefaultConfig/SamsungConfig/MtkConfig/OperationContext
/// into real timeouts and packet-size decisions. Called from `mtk`/`qcom` flows and `main::config-show`.

pub fn app_config_for_operation(device: Option<DeviceInfo>) -> OperationContext {
    let mut ctx = OperationContext::new();
    if let Some(d) = device {
        ctx = ctx.with_device(d);
    }
    ctx.with_extra("source", "default")
}

pub fn usb_bulk_timeout(cfg: &AppConfig) -> Duration {
    Duration::from_millis(cfg.usb.bulk_timeout_ms)
}

pub fn usb_control_timeout(cfg: &AppConfig) -> Duration {
    Duration::from_millis(cfg.usb.control_timeout_ms)
}

pub fn samsung_packet_size(cfg: &SamsungConfig) -> usize {
    cfg.packet_size as usize
}

pub fn mtk_packet_size(cfg: &MtkConfig) -> usize {
    cfg.packet_size as usize
}

pub fn mtk_da_timeout(cfg: &MtkConfig) -> Duration {
    Duration::from_millis(cfg.da_timeout_ms)
}

pub fn config_summary(ctx: &OperationContext) -> serde_json::Value {
    serde_json::json!({
        "usb_timeout_ms": ctx.config.usb.timeout_ms,
        "bulk_timeout_ms": ctx.config.usb.bulk_timeout_ms,
        "control_timeout_ms": ctx.config.usb.control_timeout_ms,
        "samsung_packet_size": ctx.samsung.packet_size,
        "mtk_packet_size": ctx.mtk.packet_size,
        "device": ctx.device_info,
        "extras": ctx.extras,
        "logging_level": ctx.config.logging.level,
        "defaults_flash_timeout": ctx.config.defaults.flash_timeout_secs,
    })
}

pub fn default_app_config() -> AppConfig { AppConfig::default() }
pub fn default_usb_config() -> UsbConfig { UsbConfig { timeout_ms: 5000, bulk_timeout_ms: 30000, control_timeout_ms: 5000, retry_count: 3, auto_detach_kernel: true } }
pub fn default_logging_config() -> LoggingConfig { LoggingConfig { level: "info".to_string(), json_output: false, log_usb_traffic: false } }
pub fn default_defaults_config() -> DefaultsConfig { DefaultsConfig { samsung_packet_size: 1048576, mtk_packet_size: 1048576, flash_timeout_secs: 300 } }
pub fn default_samsung_config() -> SamsungConfig { SamsungConfig::default() }
pub fn default_mtk_config() -> MtkConfig { MtkConfig::default() }

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