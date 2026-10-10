//! Backend-authoritative device capability layer (Phase 1).
//!
//! Establishes the chain the GUI must never decide itself:
//!
//! ```text
//! StableDeviceIdentity (key: adb:<serial> | usb:<ports> | usb:vid:pid@bus:addr)
//!       ↓  resolve_transport() — fresh re-scan, every call
//! CurrentTransport (vid/pid/bus/addr + serial + port path + interfaces)
//!       ↓  detect_capabilities()
//! DeviceProfile (platform, boot mode, protocol, capabilities)
//!       ↓  ActionRegistry
//! Allowed actions — the ONLY set the GUI may offer for this device now.
//! ```
//!
//! Identity notes:
//! * A key is stable; a transport is a point-in-time snapshot. Resolution
//!   re-scans USB on every call and fails loudly (DeviceNotFound,
//!   AmbiguousTarget) instead of guessing.
//! * `chipset`/`model` are `None` until a live per-protocol probe fills them
//!   (future): no capability is ever granted on a guessed chipset.
//! * Workflow capabilities (FRP/MDM/screen-lock) are granted on
//!   platform + protocol mechanism only. Model/Android-version specifics
//!   resolve at runtime inside the workflow; Apple NEVER receives Android
//!   workflow capabilities.

use crate::config::{DeviceInfo, InterfaceInfo};
use crate::error::{BridgeError, DeviceStateError, Result, UsbError};
use crate::usb::filtering::normalize_serial;
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Stable identity
// ---------------------------------------------------------------------------

/// Identity that survives USB re-enumeration. Distinct from the transport
/// (bus/address, which the kernel reassigns) and from any protocol session.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum StableDeviceIdentity {
    /// Serial-based: ADB serial or USB iSerial string.
    Serial(String),
    /// Stable USB port path (no usable serial on the device).
    PortPath(String),
    /// Volatile last resort: exact VID/PID/bus/addr snapshot.
    Volatile { vid: u16, pid: u16, bus: u8, addr: u8 },
}

impl StableDeviceIdentity {
    /// Canonical key — identical to `filtering::device_key` / Python
    /// `device_key`, so keys round-trip between GUI, Python and Rust.
    pub fn key(&self) -> String {
        match self {
            StableDeviceIdentity::Serial(s) => format!("adb:{s}"),
            StableDeviceIdentity::PortPath(p) => format!("usb:{p}"),
            StableDeviceIdentity::Volatile { vid, pid, bus, addr } => {
                format!("usb:{vid:04x}:{pid:04x}@{bus}:{addr}")
            }
        }
    }

    /// Parse a GUI/Python key (or a raw transport target) back into an
    /// identity. Accepts `adb:<serial>`, `usb:<ports>`,
    /// `usb:<vid>:<pid>@<bus>:<addr>`, `<vid>:<pid>@<bus>:<addr>` and
    /// `bus:addr` (transport-only fallback used by some chip-page runners).
    pub fn parse(key: &str) -> Option<Self> {
        let key = key.trim();
        if key.is_empty() || key == "-" {
            return None;
        }
        if let Some(serial) = key.strip_prefix("adb:") {
            let s = normalize_serial(Some(serial));
            if s.is_empty() {
                return None;
            }
            return Some(StableDeviceIdentity::Serial(s));
        }
        if let Some(rest) = key.strip_prefix("usb:") {
            if rest.contains('@') {
                return parse_volatile(rest);
            }
            // A colon without '@' is a malformed volatile key, not a port
            // path (port paths are dotted/dashed numbers, never contain ':').
            if rest.contains(':') {
                return None;
            }
            let p = rest.trim();
            if p.is_empty() {
                return None;
            }
            return Some(StableDeviceIdentity::PortPath(p.to_string()));
        }
        if key.contains('@') {
            return parse_volatile(key);
        }
        // Bare "bus:addr" (SPD/MTK-style target).
        let mut it = key.split(':');
        match (it.next(), it.next(), it.next()) {
            (Some(b), Some(a), None) => match (b.parse::<u8>(), a.parse::<u8>()) {
                (Ok(bus), Ok(addr)) => Some(StableDeviceIdentity::Volatile {
                    vid: 0,
                    pid: 0,
                    bus,
                    addr,
                }),
                _ => None,
            },
            _ => None,
        }
    }
}

fn parse_volatile(s: &str) -> Option<StableDeviceIdentity> {
    let (vidpid, busaddr) = s.split_once('@')?;
    let (vid, pid) = vidpid.split_once(':')?;
    let (bus, addr) = busaddr.split_once(':')?;
    let vid = u16::from_str_radix(vid.trim(), 16).ok()?;
    let pid = u16::from_str_radix(pid.trim(), 16).ok()?;
    let bus: u8 = bus.trim().parse().ok()?;
    let addr: u8 = addr.trim().parse().ok()?;
    Some(StableDeviceIdentity::Volatile { vid, pid, bus, addr })
}

// ---------------------------------------------------------------------------
// Current transport
// ---------------------------------------------------------------------------

/// Point-in-time USB snapshot a session would open. Never stored, never
/// reused across calls — `resolve_transport` rebuilds it from a fresh scan.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CurrentTransport {
    pub vid: u16,
    pub pid: u16,
    pub bus: u8,
    pub addr: u8,
    pub serial: Option<String>,
    pub port_numbers: String,
    pub interfaces: Vec<InterfaceInfo>,
    pub product: Option<String>,
    pub manufacturer: Option<String>,
}

impl CurrentTransport {
    fn from_device_info(d: &DeviceInfo) -> Self {
        CurrentTransport {
            vid: d.vid,
            pid: d.pid,
            bus: d.bus,
            addr: d.address,
            serial: {
                let s = normalize_serial(d.serial.as_deref());
                if s.is_empty() { None } else { Some(s) }
            },
            port_numbers: d.port_numbers.clone(),
            interfaces: d.interfaces.clone(),
            product: d.product.clone(),
            manufacturer: d.manufacturer.clone(),
        }
    }

    /// Fresh `vid:pid@bus:addr` target for the protocol CLIs.
    /// No in-tree caller yet: consumed by the FlashJob session-binding
    /// follow-up (open exactly this transport for the validated action).
    #[allow(dead_code)]
    pub fn target(&self) -> String {
        format!("{:04x}:{:04x}@{}:{}", self.vid, self.pid, self.bus, self.addr)
    }
}

/// Resolve an identity to its CURRENT transport via a fresh USB re-scan.
///
/// * Serial: matches normalized USB serials. >1 match ⇒ AmbiguousTarget
///   (two indistinguishable devices — commanding either is forbidden).
///   Zero matches ⇒ DeviceNotFound (unplugged, re-enumerated away, or an
///   ADB-only row with no USB leg).
/// * PortPath: matches the stable port path (0/1/>1 handled the same way).
/// * Volatile: matches the exact snapshot; a re-enumeration that moved the
///   device yields DeviceNotFound (never silently follows the address).
pub fn resolve_transport(ident: &StableDeviceIdentity) -> Result<CurrentTransport> {
    let devices = crate::usb::collect_devices(None)?;
    match ident {
        StableDeviceIdentity::Serial(s) => {
            let hits: Vec<&DeviceInfo> = devices
                .iter()
                .filter(|d| normalize_serial(d.serial.as_deref()) == *s)
                .collect();
            match hits.len() {
                0 => Err(BridgeError::Usb(UsbError::DeviceNotFound)),
                1 => Ok(CurrentTransport::from_device_info(hits[0])),
                n => Err(BridgeError::DeviceState(DeviceStateError::AmbiguousTarget {
                    count: n,
                })),
            }
        }
        StableDeviceIdentity::PortPath(p) => {
            let hits: Vec<&DeviceInfo> =
                devices.iter().filter(|d| &d.port_numbers == p).collect();
            match hits.len() {
                0 => Err(BridgeError::Usb(UsbError::DeviceNotFound)),
                1 => Ok(CurrentTransport::from_device_info(hits[0])),
                n => Err(BridgeError::DeviceState(DeviceStateError::AmbiguousTarget {
                    count: n,
                })),
            }
        }
        StableDeviceIdentity::Volatile { vid, pid, bus, addr } => {
            // vid/pid 0 = bare "bus:addr" fallback: match transport only.
            devices
                .iter()
                .find(|d| {
                    (*vid == 0 || d.vid == *vid)
                        && (*pid == 0 || d.pid == *pid)
                        && d.bus == *bus
                        && d.address == *addr
                })
                .map(CurrentTransport::from_device_info)
                .ok_or(BridgeError::Usb(UsbError::DeviceNotFound))
        }
    }
}

// ---------------------------------------------------------------------------
// Platform / boot mode / protocol / capabilities
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Platform {
    Android,
    Apple,
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum BootMode {
    AndroidAdb,
    AndroidMtp,
    Fastboot,
    SamsungDownload,
    SamsungBrom,
    MtkBrom,
    MtkPreloader,
    MtkDa,
    QualcommEdl,
    SpdDownload,
    AppleRecovery,
    AppleDfu,
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Protocol {
    Adb,
    Fastboot,
    SamsungOdin,
    MtkBrom,
    QualcommSahara,
    SpdBsl,
    AppleLockdown,
    None,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Capability {
    Adb,
    Fastboot,
    SamsungDownload,
    SamsungBrom,
    MtkBrom,
    MtkPreloader,
    QualcommEdl,
    SpdDownload,
    AppleRecovery,
    AppleDfu,
    PartitionFlash,
    DeviceInfo,
    Backup,
    Reboot,
    BootloaderOperation,
    FrpWorkflow,
    MdmWorkflow,
    ScreenLockWorkflow,
}

/// Apple USB PIDs with distinct boot modes (well-established values).
pub const APPLE_DFU_PID: u16 = 0x1227;
pub const APPLE_RECOVERY_PID: u16 = 0x1281;

fn has_iface(interfaces: &[InterfaceInfo], class: u8, subclass: u8) -> bool {
    interfaces
        .iter()
        .any(|i| i.class == class && i.subclass == subclass)
}

fn push_cap(caps: &mut Vec<Capability>, c: Capability) {
    if !caps.contains(&c) {
        caps.push(c);
    }
}

fn has_cap(caps: &[Capability], c: Capability) -> bool {
    caps.contains(&c)
}

/// Detect platform, boot mode, protocol and capabilities from a transport
/// snapshot. Conservative by design:
/// * No capability is granted on a guessed chipset or model.
/// * Download-mode flash capabilities are granted per exact VID:PID/mode —
///   a Qualcomm VID is never "automatically EDL", a Samsung VID never
///   "automatically Download mode".
/// * Workflow capabilities are platform + protocol-mechanism only; Apple
///   never receives Android workflows and vice versa.
pub fn detect_capabilities(
    t: &CurrentTransport,
) -> (Platform, BootMode, Protocol, Vec<Capability>) {
    let has_adb = has_iface(&t.interfaces, 255, 66);
    let mut caps = Vec::new();

    // Apple first: its own world, never Android capabilities.
    if t.vid == 0x05AC {
        let mode = match t.pid {
            APPLE_DFU_PID => BootMode::AppleDfu,
            APPLE_RECOVERY_PID => BootMode::AppleRecovery,
            _ => BootMode::Unknown,
        };
        match mode {
            BootMode::AppleDfu => {
                push_cap(&mut caps, Capability::AppleDfu);
                push_cap(&mut caps, Capability::DeviceInfo);
            }
            BootMode::AppleRecovery => {
                push_cap(&mut caps, Capability::AppleRecovery);
                push_cap(&mut caps, Capability::DeviceInfo);
            }
            _ => {
                // Normal-boot iOS (lockdown reachable): info only.
                push_cap(&mut caps, Capability::DeviceInfo);
            }
        }
        return (Platform::Apple, mode, Protocol::AppleLockdown, caps);
    }

    let platform = Platform::Android;
    // ADB interface present ⇒ ADB mechanism available (authorized or not;
    // authorization failures surface honestly at runtime).
    if has_adb {
        push_cap(&mut caps, Capability::Adb);
        push_cap(&mut caps, Capability::DeviceInfo);
        push_cap(&mut caps, Capability::Reboot);
    }

    let mut mode = BootMode::Unknown;
    let mut proto = Protocol::None;

    match t.vid {
        0x04E8 => {
            if crate::usb::SAMSUNG_ODIN_PIDS.contains(&t.pid) && !has_adb {
                mode = BootMode::SamsungDownload;
                proto = Protocol::SamsungOdin;
                push_cap(&mut caps, Capability::SamsungDownload);
                push_cap(&mut caps, Capability::PartitionFlash);
                push_cap(&mut caps, Capability::Backup);
                push_cap(&mut caps, Capability::DeviceInfo);
                push_cap(&mut caps, Capability::Reboot);
            } else if t.pid == 0x685C {
                // Samsung BROM: no backend flasher — info only.
                mode = BootMode::SamsungBrom;
                push_cap(&mut caps, Capability::SamsungBrom);
                push_cap(&mut caps, Capability::DeviceInfo);
            } else if has_adb {
                mode = BootMode::AndroidAdb;
                proto = Protocol::Adb;
            } else if has_iface(&t.interfaces, 6, 0)
                || t.interfaces.iter().any(|i| i.class == 6)
            {
                mode = BootMode::AndroidMtp;
                push_cap(&mut caps, Capability::DeviceInfo);
            }
        }
        0x0E8D => match t.pid {
            0x0003 => {
                mode = BootMode::MtkBrom;
                proto = Protocol::MtkBrom;
                push_cap(&mut caps, Capability::MtkBrom);
                push_cap(&mut caps, Capability::PartitionFlash);
                push_cap(&mut caps, Capability::Backup);
                push_cap(&mut caps, Capability::DeviceInfo);
                push_cap(&mut caps, Capability::Reboot);
            }
            0x2000 => {
                // Preloader: BROM ops are NOT available; the crash-to-BROM
                // path is (separate action). Info + reboot only.
                mode = BootMode::MtkPreloader;
                proto = Protocol::MtkBrom;
                push_cap(&mut caps, Capability::MtkPreloader);
                push_cap(&mut caps, Capability::DeviceInfo);
                push_cap(&mut caps, Capability::Reboot);
            }
            0x0004 | 0x1004 => {
                // DA stage: same conservative stance — info + reboot until
                // live stage probing lands.
                mode = BootMode::MtkDa;
                push_cap(&mut caps, Capability::DeviceInfo);
                push_cap(&mut caps, Capability::Reboot);
            }
            _ => {
                push_cap(&mut caps, Capability::DeviceInfo);
            }
        },
        0x05C6 => {
            if crate::qualcomm::sahara::QCOM_EDL_PIDS.contains(&t.pid) {
                mode = BootMode::QualcommEdl;
                proto = Protocol::QualcommSahara;
                push_cap(&mut caps, Capability::QualcommEdl);
                push_cap(&mut caps, Capability::PartitionFlash);
                push_cap(&mut caps, Capability::Backup);
                push_cap(&mut caps, Capability::DeviceInfo);
                push_cap(&mut caps, Capability::Reboot);
            } else {
                push_cap(&mut caps, Capability::DeviceInfo);
            }
        }
        0x18D1 => {
            mode = BootMode::Fastboot;
            proto = Protocol::Fastboot;
            push_cap(&mut caps, Capability::Fastboot);
            push_cap(&mut caps, Capability::BootloaderOperation);
            push_cap(&mut caps, Capability::DeviceInfo);
            push_cap(&mut caps, Capability::Reboot);
            // Deliberately NO PartitionFlash: the native backend does not
            // implement the fastboot DATA phase.
        }
        0x1782 => {
            mode = BootMode::SpdDownload;
            proto = Protocol::SpdBsl;
            push_cap(&mut caps, Capability::SpdDownload);
            push_cap(&mut caps, Capability::PartitionFlash);
            push_cap(&mut caps, Capability::Backup);
            push_cap(&mut caps, Capability::DeviceInfo);
            push_cap(&mut caps, Capability::Reboot);
        }
        _ => {
            if has_adb {
                mode = BootMode::AndroidAdb;
                proto = Protocol::Adb;
            } else if t.interfaces.iter().any(|i| i.class == 6) {
                mode = BootMode::AndroidMtp;
                push_cap(&mut caps, Capability::DeviceInfo);
            }
        }
    }

    // Workflow capabilities: Android platform + protocol mechanism.
    if has_cap(&caps, Capability::Adb)
        || has_cap(&caps, Capability::Fastboot)
        || has_cap(&caps, Capability::SamsungDownload)
        || has_cap(&caps, Capability::MtkBrom)
        || has_cap(&caps, Capability::QualcommEdl)
        || has_cap(&caps, Capability::SpdDownload)
    {
        push_cap(&mut caps, Capability::FrpWorkflow);
    }
    if has_cap(&caps, Capability::Adb) {
        // MDM/QC flows in the registry are ADB-mechanism flows.
        push_cap(&mut caps, Capability::MdmWorkflow);
    }
    if has_cap(&caps, Capability::Adb)
        || has_cap(&caps, Capability::Fastboot)
        || has_cap(&caps, Capability::SamsungDownload)
        || has_cap(&caps, Capability::MtkBrom)
        || has_cap(&caps, Capability::QualcommEdl)
    {
        // SPD has no screen-lock flow in the registry — not granted.
        push_cap(&mut caps, Capability::ScreenLockWorkflow);
    }

    (platform, mode, proto, caps)
}

// ---------------------------------------------------------------------------
// Device profile
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceProfile {
    pub identity: StableDeviceIdentity,
    pub key: String,
    pub transport: CurrentTransport,
    pub manufacturer: Option<String>,
    pub model: Option<String>,
    pub chipset: Option<String>,
    pub platform: Platform,
    pub boot_mode: BootMode,
    pub protocol: Protocol,
    pub capabilities: Vec<Capability>,
    /// ADB authorization state when cheaply known (server rows only —
    /// never a native probe here). None = unknown, not absent.
    pub adb_state: Option<String>,
}

/// Build the full profile for a key: resolve current transport, detect
/// capabilities. Fails loudly when the device is gone or ambiguous.
pub fn profile_for_key(key_str: &str) -> Result<DeviceProfile> {
    let ident = StableDeviceIdentity::parse(key_str).ok_or_else(|| {
        crate::error::BridgeError::InvalidArgument(format!("unparseable device key: {key_str}"))
    })?;
    let transport = resolve_transport(&ident)?;
    let (platform, boot_mode, protocol, capabilities) = detect_capabilities(&transport);
    let adb_state = transport
        .serial
        .as_deref()
        .and_then(crate::adb::server_state_for_serial);
    Ok(DeviceProfile {
        key: ident.key(),
        identity: ident,
        manufacturer: transport.manufacturer.clone(),
        model: None,
        chipset: None,
        platform,
        boot_mode,
        protocol,
        capabilities,
        adb_state,
        transport,
    })
}

// ---------------------------------------------------------------------------
// Action registry
// ---------------------------------------------------------------------------

/// One backend-validated operation. `platforms` empty = any platform;
/// `requires_all` must ALL be present; `requires_any` needs at least one
/// (empty = no any-requirement).
pub struct ActionDef {
    pub id: &'static str,
    pub display_name: &'static str,
    pub description: &'static str,
    pub platforms: &'static [Platform],
    pub requires_all: &'static [Capability],
    pub requires_any: &'static [Capability],
}

pub static ACTION_REGISTRY: &[ActionDef] = &[
    ActionDef {
        id: "read_device_info",
        display_name: "Read device info",
        description: "Read identifiers, mode and partition tables without writing.",
        platforms: &[],
        requires_all: &[Capability::DeviceInfo],
        requires_any: &[],
    },
    ActionDef {
        id: "reboot_device",
        display_name: "Reboot device",
        description: "Reboot to normal mode via the current protocol.",
        platforms: &[],
        requires_all: &[Capability::Reboot],
        requires_any: &[],
    },
    ActionDef {
        id: "adb_shell",
        display_name: "ADB shell",
        description: "Run a shell command over ADB.",
        platforms: &[Platform::Android],
        requires_all: &[Capability::Adb],
        requires_any: &[],
    },
    ActionDef {
        id: "fastboot_command",
        display_name: "Fastboot command",
        description: "Getvar/reboot-class fastboot commands (no DATA phase).",
        platforms: &[Platform::Android],
        requires_all: &[Capability::Fastboot],
        requires_any: &[],
    },
    ActionDef {
        id: "samsung_odin_flash",
        display_name: "Samsung Odin flash",
        description: "Flash partitions in Download mode via the Odin protocol.",
        platforms: &[Platform::Android],
        requires_all: &[Capability::SamsungDownload, Capability::PartitionFlash],
        requires_any: &[],
    },
    ActionDef {
        id: "mtk_brom_flash",
        display_name: "MediaTek BROM flash",
        description: "Flash partitions in BROM via DA.",
        platforms: &[Platform::Android],
        requires_all: &[Capability::MtkBrom, Capability::PartitionFlash],
        requires_any: &[],
    },
    ActionDef {
        id: "mtk_crash_to_brom",
        display_name: "Crash preloader to BROM",
        description: "Crash a held preloader into BROM for subsequent operations.",
        platforms: &[Platform::Android],
        requires_all: &[Capability::MtkPreloader],
        requires_any: &[],
    },
    ActionDef {
        id: "qualcomm_edl_flash",
        display_name: "Qualcomm EDL flash",
        description: "Flash partitions in EDL via Sahara/Firehose.",
        platforms: &[Platform::Android],
        requires_all: &[Capability::QualcommEdl, Capability::PartitionFlash],
        requires_any: &[],
    },
    ActionDef {
        id: "spd_flash",
        display_name: "Unisoc/SPD flash",
        description: "Flash partitions in download mode via BSL.",
        platforms: &[Platform::Android],
        requires_all: &[Capability::SpdDownload, Capability::PartitionFlash],
        requires_any: &[],
    },
    ActionDef {
        id: "backup_partitions",
        display_name: "Backup partitions",
        description: "Read back partitions (EFS/NV/GPT) for safety.",
        platforms: &[Platform::Android],
        requires_all: &[Capability::Backup],
        requires_any: &[],
    },
    ActionDef {
        id: "frp_workflow",
        display_name: "FRP workflow",
        description: "Model-specific FRP removal via an actually-available protocol.",
        platforms: &[Platform::Android],
        requires_all: &[Capability::FrpWorkflow],
        requires_any: &[],
    },
    ActionDef {
        id: "mdm_workflow",
        display_name: "MDM workflow",
        description: "MDM removal via ADB mechanisms.",
        platforms: &[Platform::Android],
        requires_all: &[Capability::MdmWorkflow],
        requires_any: &[],
    },
    ActionDef {
        id: "screen_lock_workflow",
        display_name: "Screen-lock workflow",
        description: "Model-specific screen-lock removal via an available protocol.",
        platforms: &[Platform::Android],
        requires_all: &[Capability::ScreenLockWorkflow],
        requires_any: &[],
    },
    ActionDef {
        id: "apple_recovery_operation",
        display_name: "Apple recovery operation",
        description: "Apple recovery-mode operations (never Android workflows).",
        platforms: &[Platform::Apple],
        requires_all: &[Capability::AppleRecovery],
        requires_any: &[],
    },
    ActionDef {
        id: "apple_dfu_operation",
        display_name: "Apple DFU operation",
        description: "Apple DFU-mode operations (never Android workflows).",
        platforms: &[Platform::Apple],
        requires_all: &[Capability::AppleDfu],
        requires_any: &[],
    },
    ActionDef {
        id: "apple_passcode_guide",
        display_name: "Apple passcode guide",
        description: "Guided, non-invasive passcode options. Never writes.",
        platforms: &[Platform::Apple],
        requires_all: &[Capability::AppleRecovery],
        requires_any: &[],
    },
];

fn action_allowed(profile: &DeviceProfile, a: &ActionDef) -> bool {
    if !a.platforms.is_empty() && !a.platforms.contains(&profile.platform) {
        return false;
    }
    if !a.requires_all.iter().all(|c| profile.capabilities.contains(c)) {
        return false;
    }
    if !a.requires_any.is_empty()
        && !a.requires_any.iter().any(|c| profile.capabilities.contains(c))
    {
        return false;
    }
    true
}

/// The valid action set for this device right now. The GUI must offer
/// exactly this set — nothing more.
pub fn allowed_actions(profile: &DeviceProfile) -> Vec<&'static ActionDef> {
    ACTION_REGISTRY.iter().filter(|a| action_allowed(profile, a)).collect()
}

/// Backend enforcement: is `action_id` valid for this device right now?
/// Unknown action ids and unmet requirements are rejected with a
/// structured error — even if the GUI sends them manually.
pub fn validate_action(
    profile: &DeviceProfile,
    action_id: &str,
) -> Result<&'static ActionDef> {
    let def = ACTION_REGISTRY
        .iter()
        .find(|a| a.id == action_id)
        .ok_or_else(|| {
            crate::error::BridgeError::InvalidArgument(format!(
                "unknown action: {action_id}"
            ))
        })?;
    if action_allowed(profile, def) {
        Ok(def)
    } else {
        Err(BridgeError::DeviceState(DeviceStateError::WrongMode {
            expected: format!("capabilities {def:?}", def = def.requires_all),
            actual: format!(
                "device {} in {:?} with {:?}",
                profile.key, profile.boot_mode, profile.capabilities
            ),
        }))
    }
}

// ---------------------------------------------------------------------------
// CLI surface
// ---------------------------------------------------------------------------

/// Full `actions-for` payload: profile + allowed action ids.
#[derive(Debug, Serialize)]
pub struct ActionsForResult {
    pub key: String,
    pub profile: DeviceProfile,
    pub actions: Vec<ActionSummary>,
}

#[derive(Debug, Serialize)]
pub struct ActionSummary {
    pub id: &'static str,
    pub display_name: &'static str,
    pub description: &'static str,
}

/// Resolve → profile → allowed actions, serialized for the GUI/Python.
pub fn actions_for_key(key_str: &str) -> Result<String> {
    let profile = profile_for_key(key_str)?;
    let actions: Vec<ActionSummary> = allowed_actions(&profile)
        .into_iter()
        .map(|a| ActionSummary {
            id: a.id,
            display_name: a.display_name,
            description: a.description,
        })
        .collect();
    let result = ActionsForResult {
        key: profile.key.clone(),
        profile,
        actions,
    };
    serde_json::to_string_pretty(&result).map_err(|e| crate::error::BridgeError::Io(e.to_string()))
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn transport(vid: u16, pid: u16, ifaces: Vec<InterfaceInfo>) -> CurrentTransport {
        CurrentTransport {
            vid,
            pid,
            bus: 1,
            addr: 5,
            serial: None,
            port_numbers: "1-2".to_string(),
            interfaces: ifaces,
            product: None,
            manufacturer: None,
        }
    }

    fn iface(class: u8, subclass: u8) -> InterfaceInfo {
        InterfaceInfo {
            number: 0,
            class,
            subclass,
            protocol: 1,
            endpoints: vec![],
        }
    }

    fn profile_for(vid: u16, pid: u16, ifaces: Vec<InterfaceInfo>) -> DeviceProfile {
        let t = transport(vid, pid, ifaces);
        let (platform, boot_mode, protocol, capabilities) = detect_capabilities(&t);
        DeviceProfile {
            identity: StableDeviceIdentity::PortPath("1-2".to_string()),
            key: "usb:1-2".to_string(),
            transport: t,
            manufacturer: None,
            model: None,
            chipset: None,
            platform,
            boot_mode,
            protocol,
            capabilities,
            adb_state: None,
        }
    }

    fn action_ids(p: &DeviceProfile) -> Vec<&'static str> {
        allowed_actions(p).iter().map(|a| a.id).collect()
    }

    // -- identity parsing -------------------------------------------------

    #[test]
    fn parse_keys_round_trip() {
        assert_eq!(
            StableDeviceIdentity::parse("adb:R9X123"),
            Some(StableDeviceIdentity::Serial("R9X123".to_string()))
        );
        assert_eq!(
            StableDeviceIdentity::parse("usb:1-2-3"),
            Some(StableDeviceIdentity::PortPath("1-2-3".to_string()))
        );
        assert_eq!(
            StableDeviceIdentity::parse("usb:04e8:685d@1:5"),
            Some(StableDeviceIdentity::Volatile {
                vid: 0x04e8,
                pid: 0x685d,
                bus: 1,
                addr: 5
            })
        );
        assert_eq!(
            StableDeviceIdentity::parse("04e8:685d@1:5"),
            Some(StableDeviceIdentity::Volatile {
                vid: 0x04e8,
                pid: 0x685d,
                bus: 1,
                addr: 5
            })
        );
        assert_eq!(
            StableDeviceIdentity::parse("1:5"),
            Some(StableDeviceIdentity::Volatile { vid: 0, pid: 0, bus: 1, addr: 5 })
        );
        assert_eq!(StableDeviceIdentity::parse(""), None);
        assert_eq!(StableDeviceIdentity::parse("-"), None);
        assert_eq!(StableDeviceIdentity::parse("adb:unknown"), None);
        assert_eq!(StableDeviceIdentity::parse("usb:04e8:685d"), None);
    }

    #[test]
    fn keys_are_canonical() {
        assert_eq!(
            StableDeviceIdentity::Serial("A".to_string()).key(),
            "adb:A"
        );
        assert_eq!(
            StableDeviceIdentity::PortPath("1-2".to_string()).key(),
            "usb:1-2"
        );
        // Serials normalize on parse: surrounding whitespace is dropped.
        assert_eq!(
            StableDeviceIdentity::parse("adb:  A  ").unwrap().key(),
            "adb:A"
        );
    }

    // -- matrix: Samsung Download ------------------------------------------

    #[test]
    fn samsung_download_exposes_samsung_actions_only() {
        let p = profile_for(0x04E8, 0x685D, vec![]);
        let ids = action_ids(&p);
        assert!(ids.contains(&"samsung_odin_flash"));
        assert!(ids.contains(&"frp_workflow"));
        assert!(ids.contains(&"screen_lock_workflow"));
        assert!(ids.contains(&"backup_partitions"));
        assert!(ids.contains(&"read_device_info"));
        // Negatives: no MTK / EDL / Apple / ADB / fastboot / MDM actions.
        for bad in [
            "mtk_brom_flash",
            "mtk_crash_to_brom",
            "qualcomm_edl_flash",
            "spd_flash",
            "adb_shell",
            "fastboot_command",
            "mdm_workflow",
            "apple_recovery_operation",
            "apple_dfu_operation",
            "apple_passcode_guide",
        ] {
            assert!(!ids.contains(&bad), "{bad} must not be offered");
        }
        // Backend rejects hand-sent unsupported actions.
        assert!(validate_action(&p, "qualcomm_edl_flash").is_err());
        assert!(validate_action(&p, "frp_workflow").is_ok());
        assert!(validate_action(&p, "no_such_action").is_err());
    }

    #[test]
    fn samsung_adb_composite_is_not_download_mode() {
        // 0x685D WITH an ADB interface is a normal-boot composite:
        // Odin flash must NOT be offered.
        let p = profile_for(0x04E8, 0x685D, vec![iface(255, 66)]);
        let ids = action_ids(&p);
        assert!(!ids.contains(&"samsung_odin_flash"));
        assert!(ids.contains(&"adb_shell"));
        assert!(ids.contains(&"mdm_workflow"));
        assert!(ids.contains(&"frp_workflow"));
    }

    // -- matrix: MediaTek ----------------------------------------------------

    #[test]
    fn mtk_brom_exposes_mtk_actions_only() {
        let p = profile_for(0x0E8D, 0x0003, vec![]);
        let ids = action_ids(&p);
        assert!(ids.contains(&"mtk_brom_flash"));
        assert!(ids.contains(&"frp_workflow"));
        assert!(ids.contains(&"screen_lock_workflow"));
        for bad in [
            "samsung_odin_flash",
            "qualcomm_edl_flash",
            "spd_flash",
            "apple_recovery_operation",
            "mdm_workflow",
            "adb_shell",
        ] {
            assert!(!ids.contains(&bad), "{bad} must not be offered");
        }
    }

    #[test]
    fn mtk_preloader_exposes_crash_not_flash() {
        let p = profile_for(0x0E8D, 0x2000, vec![]);
        let ids = action_ids(&p);
        assert!(ids.contains(&"mtk_crash_to_brom"));
        assert!(!ids.contains(&"mtk_brom_flash"));
        assert!(!ids.contains(&"frp_workflow"));
    }

    // -- matrix: Qualcomm / SPD / fastboot ------------------------------------

    #[test]
    fn qualcomm_edl_exposes_edl_actions_only() {
        let p = profile_for(0x05C6, 0x9008, vec![]);
        let ids = action_ids(&p);
        assert!(ids.contains(&"qualcomm_edl_flash"));
        assert!(ids.contains(&"frp_workflow"));
        for bad in [
            "mtk_brom_flash",
            "samsung_odin_flash",
            "spd_flash",
            "apple_dfu_operation",
            "mdm_workflow",
        ] {
            assert!(!ids.contains(&bad), "{bad} must not be offered");
        }
    }

    #[test]
    fn qualcomm_non_edl_pid_is_not_edl() {
        // A Qualcomm VID outside the EDL PID list is NOT EDL-capable.
        let p = profile_for(0x05C6, 0x901E, vec![]);
        assert!(!action_ids(&p).contains(&"qualcomm_edl_flash"));
    }

    #[test]
    fn fastboot_has_no_partition_flash() {
        let p = profile_for(0x18D1, 0x4EE0, vec![]);
        let ids = action_ids(&p);
        assert!(ids.contains(&"fastboot_command"));
        assert!(ids.contains(&"frp_workflow"));
        // Native backend has no DATA phase: no flash action.
        for bad in [
            "samsung_odin_flash",
            "mtk_brom_flash",
            "qualcomm_edl_flash",
            "spd_flash",
        ] {
            assert!(!ids.contains(&bad), "{bad} must not be offered");
        }
    }

    // -- matrix: Apple --------------------------------------------------------

    #[test]
    fn apple_recovery_has_no_android_actions() {
        let p = profile_for(0x05AC, APPLE_RECOVERY_PID, vec![]);
        let ids = action_ids(&p);
        assert!(ids.contains(&"apple_recovery_operation"));
        assert!(ids.contains(&"apple_passcode_guide"));
        assert!(ids.contains(&"read_device_info"));
        for bad in [
            "frp_workflow",
            "mdm_workflow",
            "screen_lock_workflow",
            "samsung_odin_flash",
            "mtk_brom_flash",
            "qualcomm_edl_flash",
            "adb_shell",
            "apple_dfu_operation",
        ] {
            assert!(!ids.contains(&bad), "{bad} must not be offered");
        }
        assert_eq!(p.platform, Platform::Apple);
    }

    #[test]
    fn apple_dfu_has_dfu_not_recovery() {
        let p = profile_for(0x05AC, APPLE_DFU_PID, vec![]);
        let ids = action_ids(&p);
        assert!(ids.contains(&"apple_dfu_operation"));
        assert!(!ids.contains(&"apple_recovery_operation"));
        assert!(!ids.contains(&"frp_workflow"));
    }
}
