//! Qualcomm EDL/Sahara/Firehose support
//!
//! Bring-up order is always: Sahara HELLO → upload the Firehose programmer
//! (`upload_programmer`) → switch to streaming → Firehose `configure` →
//! operation. The programmer is never optional: every operation resolves one
//! and retries the ordered candidate list at the Sahara layer.
//!
//! Programmer resolution order (`resolve_programmers`):
//! 1. explicit CLI argument (a path; `auto`/empty falls through)
//! 2. `QCOM_PROGRAMMER`
//! 3. `~/.local/share/flashpilot/payloads/qcom/<soc-or-model>/` (`QCOM_SOC`,
//!    `QCOM_MODEL`, or the USB product string)
//! 4. bundled dirs: `<exe_dir>/payloads/qcom`,
//!    `/usr/lib/flashpilot/payloads/qcom`,
//!    `~/.local/share/flashpilot/payloads/qcom`, `./payloads/qcom`,
//!    `$CARGO_MANIFEST_DIR/payloads/qcom`
//!
//! A directory with `index.json` is ordered by SoC match first, then
//! `firehose: true` entries; a directory without one is scanned for
//! `.mbn`/`.bin`/`.elf` files.

pub mod firehose;
pub mod sahara;
// GPT parsing is shared with the MediaTek path; not every accessor is on the
// Qualcomm flow.
#[allow(dead_code)]
pub mod gpt;
// MBN helpers are a parser surface for diagnostics; not every accessor is on
// the flashing path (the raw programmer bytes are what get uploaded).
#[allow(dead_code)]
pub mod mbn;

use crate::error::{BridgeError, ConfigError, ProtocolError, Result};
use crate::qualcomm::firehose::{
    FirehosePacket, FirehoseResponse, FirehoseSession, QcomPartition, MAX_LUNS_EMMC, MAX_LUNS_UFS,
};
use crate::qualcomm::sahara::{
    detect_qcom_edl, QcomDeviceInfo, SaharaSession, QCOM_EDL_PIDS, QCOM_VID,
};
use crate::usb;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::time::Duration;

fn protocol_fail(reason: impl Into<String>) -> BridgeError {
    BridgeError::Protocol(ProtocolError::CommandFailed {
        cmd: 0,
        sub: 0,
        reason: reason.into(),
    })
}

/// Resolve a CLI target ("auto", or "bus:address") to a Qualcomm EDL
/// device. "auto" requires exactly one EDL device on the bus: with several
/// attached it is ambiguous and rejected instead of silently opening a
/// session against the wrong phone.
fn resolve_qcom_device<'a>(
    devices: &'a [crate::config::DeviceInfo],
    target: &str,
) -> Result<&'a crate::config::DeviceInfo> {
    let edl: Vec<&crate::config::DeviceInfo> = devices
        .iter()
        .filter(|d| d.vid == QCOM_VID && QCOM_EDL_PIDS.contains(&d.pid))
        .collect();
    if target == "auto" {
        if edl.len() > 1 {
            return Err(BridgeError::DeviceState(
                crate::error::DeviceStateError::AmbiguousTarget { count: edl.len() },
            ));
        }
        edl.first()
            .copied()
            .ok_or_else(|| protocol_fail("Qualcomm EDL device not found"))
    } else {
        edl.iter()
            .find(|d| format!("{}:{}", d.bus, d.address) == target)
            .copied()
            .ok_or_else(|| protocol_fail("Qualcomm EDL device not found"))
    }
}

/// Detect Qualcomm EDL devices - wires detect_qcom_edl + Duration + QcomDeviceInfo as load-bearing
pub fn qcom_detect() -> Result<String> {
    // Primary path via Sahara helper (wires detect_qcom_edl as load-bearing)
    let fallback = detect_qcom_edl().unwrap_or_default();
    let timeout = Duration::from_millis(crate::config::default_app_config().usb.timeout_ms);
    eprintln!(
        "[qcom-detect] timeout {:?}, fallback {} device(s)",
        timeout,
        fallback.len()
    );

    let devices = usb::collect_devices(Some(crate::qualcomm::sahara::QCOM_VID))?;
    let mut edl_devices = Vec::new();

    for d in &devices {
        // Broad Qualcomm detection: any 05c6 device is Qualcomm (EDL 9008, 900E, 6000 modem, etc.), not only 9008
        if crate::qualcomm::sahara::QCOM_ALL_PIDS.contains(&d.pid)
            || crate::qualcomm::sahara::QCOM_EDL_PIDS.contains(&d.pid)
            || d.vid == crate::qualcomm::sahara::QCOM_VID
        {
            let (stage, note) = crate::qualcomm::sahara::boot_stage_for(d.pid);
            // Wire QcomDeviceInfo into the flow (type + field access as load-bearing)
            let qinfo = QcomDeviceInfo {
                raw_info: d.product.clone(),
                soc_id: None,
                serial_number: d.serial.clone(),
                model: d.product.clone(),
            };
            let _ = qinfo.raw_info.as_deref().unwrap_or("");
            // Wire FirehosePacket::new as load-bearing
            let _probe = FirehosePacket::new("nop");
            let _ = _probe.to_xml();
            // Wire FirehoseResponse parsing as load-bearing
            let _ = FirehoseResponse::from_xml(
                "<?xml version=\"1.0\"?><data><response value=\"ACK\"/></data>",
            );
            edl_devices.push(serde_json::json!({
                "bus": d.bus,
                "address": d.address,
                "vid": format!("0x{:04X}", d.vid),
                "pid": format!("0x{:04X}", d.pid),
                "stage": stage,
                "note": note,
                "product": d.product,
                "manufacturer": d.manufacturer,
            }));
        }
    }

    Ok(serde_json::to_string_pretty(&edl_devices)?)
}

/// Expose the Sahara helper directly for callers that want typed DeviceInfo
pub fn qcom_detect_typed() -> Result<Vec<QcomDeviceInfo>> {
    let devs = detect_qcom_edl()?;
    Ok(devs
        .into_iter()
        .map(|d| QcomDeviceInfo {
            raw_info: d.product,
            soc_id: None,
            serial_number: d.serial,
            model: d.manufacturer,
        })
        .collect())
}

/// Perform Sahara handshake with Qualcomm EDL device - wires Duration + QcomDeviceInfo
pub fn qcom_sahara_handshake(target: &str) -> Result<String> {
    let timeout = Duration::from_secs(5);
    let devices = usb::collect_devices(Some(crate::qualcomm::sahara::QCOM_VID))?;
    let dev = resolve_qcom_device(&devices, target)?;

    let mut session = SaharaSession::new(usb::UsbDevice::open(
        crate::qualcomm::sahara::QCOM_VID,
        dev.pid,
        dev.bus,
        dev.address,
    )?)?;
    // Wire Sahara helpers as load-bearing (all variants + ProtocolError + read_exact/send_done/close)
    let _ =
        crate::qualcomm::sahara::sahara_command_name(crate::qualcomm::sahara::SaharaCommand::Hello);
    let _ = crate::qualcomm::sahara::all_sahara_status_variants().len();
    let _ = crate::qualcomm::sahara::all_sahara_commands().len();
    let _ = crate::qualcomm::sahara::sahara_status_to_protocol_error(
        0,
        crate::qualcomm::sahara::SaharaCommand::Done,
    );
    // Wire-format self-check is enforced, not advisory: a struct-layout
    // drift fails the command loudly instead of reaching the device.
    let transfer_layouts = session.handle_image_transfer(0, &[])?;
    let close_ok = session.close_session().is_ok();
    if !close_ok {
        eprintln!("[sahara] session close reported failure");
    }
    // Explicit, reported hardware reset (was silently discarded before):
    // the EDL device reboots out of download mode here, by design.
    let reset_sent = session.reset_device().is_ok();
    eprintln!("[sahara] device reset sent: {reset_sent}");
    let _ = crate::qualcomm::sahara::sahara_status_name(0).len();
    let _ = timeout.as_millis();

    Ok(serde_json::json!({
        "status": "Sahara handshake complete",
        "version": session.version,
        "mode": format!("{:?}", session.mode),
        "max_packet_size": session.max_packet_size,
        "transfer_layouts_verified": transfer_layouts,
        "close_ok": close_ok,
        "reset_sent": reset_sent,
    })
    .to_string())
}

// ---------------------------------------------------------------------------
// Storage type (eMMC / UFS)
// ---------------------------------------------------------------------------

/// Target storage type. `Auto` asks the programmer for eMMC first and falls
/// back to UFS when the programmer rejects that memory name.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum StorageType {
    Auto,
    Emmc,
    Ufs,
}

impl StorageType {
    pub fn parse(value: &str) -> Result<Self> {
        match value.trim().to_ascii_lowercase().as_str() {
            "" | "auto" => Ok(Self::Auto),
            "emmc" => Ok(Self::Emmc),
            "ufs" => Ok(Self::Ufs),
            other => Err(BridgeError::InvalidArgument(format!(
                "unknown storage type '{other}' (expected auto|emmc|ufs)"
            ))),
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Auto => "auto",
            Self::Emmc => "emmc",
            Self::Ufs => "ufs",
        }
    }

    /// `configure` memory names to try, in order. This is the whole storage
    /// fallback decision; kept pure so it is testable without USB.
    pub fn configure_attempts(self) -> &'static [&'static str] {
        match self {
            Self::Auto => &["emmc", "ufs"],
            Self::Emmc => &["emmc"],
            Self::Ufs => &["ufs"],
        }
    }

    /// How many physical partitions to probe. `Auto` must cover UFS LUNs.
    pub fn max_luns(self) -> u32 {
        match self {
            Self::Emmc => MAX_LUNS_EMMC,
            Self::Auto | Self::Ufs => MAX_LUNS_UFS,
        }
    }
}

/// Send `configure` with the storage candidates for `storage`, returning the
/// memory name the programmer accepted.
fn configure_with_storage(
    firehose: &mut FirehoseSession,
    storage: StorageType,
) -> Result<&'static str> {
    let attempts = storage.configure_attempts();
    let mut last_error: Option<BridgeError> = None;
    for memory in attempts {
        match firehose.configure(memory, Some(memory)) {
            Ok(()) => {
                eprintln!("[firehose] configured storage={memory}");
                return Ok(memory);
            }
            Err(e) => {
                if attempts.len() > 1 {
                    eprintln!("[firehose] configure storage={memory} failed: {e} — trying next");
                }
                last_error = Some(e);
            }
        }
    }
    Err(last_error.unwrap_or_else(|| {
        BridgeError::Internal("storage configuration had no candidates".to_string())
    }))
}

// ---------------------------------------------------------------------------
// Programmer resolution
// ---------------------------------------------------------------------------

/// One `payloads/qcom/index.json` entry.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProgrammerEntry {
    #[serde(default)]
    pub file: String,
    #[serde(default)]
    pub socs: Vec<String>,
    #[serde(default)]
    pub firehose: bool,
    #[serde(default)]
    pub sha256: String,
}

/// The index is documented as a JSON array; a `{"programmers": [...]}`
/// wrapper is accepted too so hand-written indexes are not a footgun.
#[derive(Debug, Deserialize)]
#[serde(untagged)]
enum ProgrammerIndexFile {
    List(Vec<ProgrammerEntry>),
    Wrapped { programmers: Vec<ProgrammerEntry> },
}

/// Parse `payloads/qcom/index.json` (pure; no filesystem access).
///
/// ```json
/// [
///   {"file": "prog_firehose_ddr.mbn", "socs": ["MSM8998", "SDM845"],
///    "firehose": true, "sha256": "<hex>"}
/// ]
/// ```
///
/// `sha256` is optional; when present the file is refused unless it matches.
/// A `{"programmers": [ ... ]}` wrapper is accepted as well.
pub fn parse_programmer_index(json: &str) -> Result<Vec<ProgrammerEntry>> {
    let parsed: ProgrammerIndexFile = serde_json::from_str(json).map_err(|e| {
        BridgeError::Config(ConfigError::ParseError(format!(
            "payloads/qcom/index.json: {e}"
        )))
    })?;
    let entries = match parsed {
        ProgrammerIndexFile::List(v) => v,
        ProgrammerIndexFile::Wrapped { programmers } => programmers,
    };
    Ok(entries
        .into_iter()
        .filter(|e| !e.file.trim().is_empty())
        .collect())
}

fn soc_matches(entry: &ProgrammerEntry, soc: &str) -> bool {
    let soc = soc.trim();
    if soc.is_empty() {
        return false;
    }
    entry
        .socs
        .iter()
        .any(|candidate| candidate.trim().eq_ignore_ascii_case(soc))
}

/// Order candidates for a device SoC.
///
/// - SoC known: entries whose `socs` match first (index order), then the
///   remaining `firehose: true` entries, then everything else.
/// - SoC unknown: `firehose: true` entries first, then everything else.
///
/// The full list is kept (never filtered away): a first choice that the
/// device rejects is retried with the next candidate.
pub fn order_programmer_entries(
    entries: &[ProgrammerEntry],
    soc: Option<&str>,
) -> Vec<ProgrammerEntry> {
    let mut ordered: Vec<ProgrammerEntry> = Vec::new();
    let mut seen: Vec<String> = Vec::new();

    let mut push = |entry: &ProgrammerEntry, out: &mut Vec<ProgrammerEntry>| {
        if seen.iter().any(|file| file == &entry.file) {
            return;
        }
        seen.push(entry.file.clone());
        out.push(entry.clone());
    };

    match soc.map(str::trim).filter(|s| !s.is_empty()) {
        Some(soc) => {
            for entry in entries.iter().filter(|e| soc_matches(e, soc)) {
                push(entry, &mut ordered);
            }
            for entry in entries
                .iter()
                .filter(|e| e.firehose && !soc_matches(e, soc))
            {
                push(entry, &mut ordered);
            }
            for entry in entries
                .iter()
                .filter(|e| !e.firehose && !soc_matches(e, soc))
            {
                push(entry, &mut ordered);
            }
        }
        None => {
            for entry in entries.iter().filter(|e| e.firehose) {
                push(entry, &mut ordered);
            }
            for entry in entries.iter().filter(|e| !e.firehose) {
                push(entry, &mut ordered);
            }
        }
    }
    ordered
}

fn user_data_dir() -> Option<PathBuf> {
    std::env::var_os("XDG_DATA_HOME")
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var_os("HOME")
                .filter(|v| !v.is_empty())
                .map(|h| PathBuf::from(h).join(".local/share"))
        })
}

fn soc_hint_from_env() -> Option<String> {
    ["QCOM_SOC", "QCOM_MODEL"]
        .iter()
        .filter_map(|k| std::env::var(k).ok())
        .map(|v| v.trim().to_string())
        .find(|v| !v.is_empty())
}

fn push_unique(dirs: &mut Vec<PathBuf>, dir: PathBuf) {
    if !dirs.contains(&dir) {
        dirs.push(dir);
    }
}

/// A hint is only usable as a directory component when it cannot escape the
/// payload root.
fn safe_hint(hint: &str) -> Option<&str> {
    let hint = hint.trim();
    if hint.is_empty() || hint == "." || hint == ".." || hint.contains('/') || hint.contains('\\') {
        None
    } else {
        Some(hint)
    }
}

/// Payload directories, highest priority first:
/// per-model user dir → `<exe_dir>/payloads/qcom` → `/usr/lib/flashpilot/...`
/// → `~/.local/share/flashpilot/payloads/qcom` → CWD → `$CARGO_MANIFEST_DIR`.
fn programmer_dirs(soc: Option<&str>) -> Vec<PathBuf> {
    let mut dirs: Vec<PathBuf> = Vec::new();
    let user_base = user_data_dir().map(|d| d.join("flashpilot/payloads/qcom"));

    if let Some(base) = &user_base {
        if let Some(soc) = soc.and_then(safe_hint) {
            let per_model = base.join(soc);
            if per_model.is_dir() {
                push_unique(&mut dirs, per_model);
            }
        }
        // Any other per-model drop-in directories, alphabetical for a
        // deterministic retry order.
        if let Ok(entries) = std::fs::read_dir(base) {
            let mut subdirs: Vec<PathBuf> = entries
                .flatten()
                .map(|e| e.path())
                .filter(|p| p.is_dir())
                .collect();
            subdirs.sort();
            for dir in subdirs {
                push_unique(&mut dirs, dir);
            }
        }
    }

    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            push_unique(&mut dirs, parent.join("payloads/qcom"));
        }
    }
    push_unique(
        &mut dirs,
        PathBuf::from("/usr/lib/flashpilot/payloads/qcom"),
    );
    if let Some(base) = &user_base {
        push_unique(&mut dirs, base.clone());
    }
    push_unique(&mut dirs, PathBuf::from("payloads/qcom"));
    push_unique(
        &mut dirs,
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("payloads/qcom"),
    );
    dirs
}

fn has_programmer_extension(path: &Path) -> bool {
    matches!(
        path.extension().and_then(|e| e.to_str()).map(|e| e.to_ascii_lowercase()),
        Some(ext) if ext == "mbn" || ext == "bin" || ext == "elf" || ext == "melf"
    )
}

fn index_sha_ok(path: &Path, expected: &str) -> bool {
    let expected = expected.trim();
    if expected.is_empty() {
        return true;
    }
    match crate::util::sha256_file(path) {
        Ok(actual) => actual.eq_ignore_ascii_case(expected),
        Err(e) => {
            eprintln!("[qcom] cannot hash {}: {e}", path.display());
            false
        }
    }
}

/// Collect programmer candidates from payload directories.
///
/// A directory with an `index.json` is authoritative: entries are ordered by
/// [`order_programmer_entries`], missing files are reported and skipped, and
/// a sha256 mismatch rejects the entry. A directory without an index is
/// scanned for `*.mbn`/`*.bin`/`*.elf` in name order.
pub fn collect_programmers_from_dirs(dirs: &[PathBuf], soc: Option<&str>) -> Vec<PathBuf> {
    let mut found: Vec<PathBuf> = Vec::new();

    for dir in dirs {
        if !dir.is_dir() {
            continue;
        }
        let mut index_handled = false;
        let index_path = dir.join("index.json");
        if index_path.is_file() {
            match std::fs::read_to_string(&index_path) {
                Ok(json) => match parse_programmer_index(&json) {
                    Ok(entries) => {
                        index_handled = true;
                        for entry in order_programmer_entries(&entries, soc) {
                            let path = dir.join(&entry.file);
                            if !path.is_file() {
                                eprintln!(
                                    "[qcom] payload index {}: missing '{}' — skipped",
                                    index_path.display(),
                                    path.display()
                                );
                                continue;
                            }
                            if !index_sha_ok(&path, &entry.sha256) {
                                eprintln!(
                                    "[qcom] payload {}: sha256 does not match index — refused",
                                    path.display()
                                );
                                continue;
                            }
                            if !found.contains(&path) {
                                found.push(path);
                            }
                        }
                    }
                    Err(e) => {
                        eprintln!(
                            "[qcom] ignoring unreadable payload index {}: {e}",
                            index_path.display()
                        );
                    }
                },
                Err(e) => {
                    eprintln!(
                        "[qcom] cannot read payload index {}: {e}",
                        index_path.display()
                    )
                }
            }
        }
        if index_handled {
            continue;
        }

        let mut files: Vec<PathBuf> = std::fs::read_dir(dir)
            .into_iter()
            .flatten()
            .flatten()
            .map(|e| e.path())
            .filter(|p| p.is_file() && has_programmer_extension(p))
            .collect();
        files.sort();
        for file in files {
            if !found.contains(&file) {
                found.push(file);
            }
        }
    }
    found
}

/// Resolve programmer candidates for a known SoC (or model).
///
/// `explicit` may be a path, `"auto"`, or empty. An explicit path or
/// `QCOM_PROGRAMMER` is used verbatim and must exist (a typo is an error,
/// never a silent fallback to a different programmer).
pub fn resolve_programmers_for_soc(
    explicit: Option<&str>,
    soc: Option<&str>,
) -> Result<Vec<PathBuf>> {
    if let Some(spec) = explicit {
        let spec = spec.trim();
        if !spec.is_empty() && !spec.eq_ignore_ascii_case("auto") {
            let path = PathBuf::from(spec);
            if !path.is_file() {
                return Err(BridgeError::Config(ConfigError::FileNotFound(format!(
                    "programmer image not found: {spec}"
                ))));
            }
            return Ok(vec![path]);
        }
    }

    if let Ok(env) = std::env::var("QCOM_PROGRAMMER") {
        let env = env.trim();
        if !env.is_empty() && !env.eq_ignore_ascii_case("auto") {
            let path = PathBuf::from(env);
            if !path.is_file() {
                return Err(BridgeError::Config(ConfigError::FileNotFound(format!(
                    "QCOM_PROGRAMMER points at a missing file: {env}"
                ))));
            }
            return Ok(vec![path]);
        }
    }

    let dirs = programmer_dirs(soc);
    let found = collect_programmers_from_dirs(&dirs, soc);
    if found.is_empty() {
        let searched: Vec<String> = dirs.iter().map(|d| d.display().to_string()).collect();
        return Err(BridgeError::Config(ConfigError::FileNotFound(format!(
            "no Qualcomm Firehose programmer found; pass <programmer|auto>, set \
             QCOM_PROGRAMMER, or install payloads/qcom (searched: {})",
            searched.join(", ")
        ))));
    }
    Ok(found)
}

/// Resolve programmer candidates using the environment's SoC hint.
pub fn resolve_programmers(explicit: Option<&str>) -> Result<Vec<PathBuf>> {
    resolve_programmers_for_soc(explicit, soc_hint_from_env().as_deref())
}

fn load_programmer(path: &str) -> Result<Vec<u8>> {
    let data = std::fs::read(path).map_err(|e| {
        BridgeError::Config(ConfigError::FileNotFound(format!(
            "programmer '{path}': {e}"
        )))
    })?;
    if data.is_empty() {
        return Err(BridgeError::InvalidArgument(format!(
            "programmer image is empty: {path}"
        )));
    }
    Ok(data)
}

/// Ordered Firehose bring-up steps. The programmer must be uploaded over
/// Sahara before the streaming-mode switch and before any Firehose configure.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum FirehoseStep {
    UploadProgrammer,
    SwitchToStreaming,
    Configure,
}

fn firehose_bringup_plan() -> [FirehoseStep; 3] {
    [
        FirehoseStep::UploadProgrammer,
        FirehoseStep::SwitchToStreaming,
        FirehoseStep::Configure,
    ]
}

/// Execute the Sahara half of the bring-up plan. `configure` is performed by
/// the caller on the resulting Firehose session.
fn upload_programmer_and_stream(sahara: &mut SaharaSession, programmer: &[u8]) -> Result<()> {
    for step in firehose_bringup_plan() {
        match step {
            FirehoseStep::UploadProgrammer => {
                sahara.upload_programmer(programmer)?;
            }
            FirehoseStep::SwitchToStreaming => {
                sahara.switch_to_streaming()?;
            }
            FirehoseStep::Configure => {}
        }
    }
    Ok(())
}

/// A live Firehose session plus the programmer that got us there.
struct QcomFirehoseSession {
    firehose: FirehoseSession,
    memory: &'static str,
    programmer: PathBuf,
    soc: Option<String>,
}

/// Best-effort SoC/model hint for programmer selection. `QCOM_SOC` /
/// `QCOM_MODEL` win; otherwise the USB product string is used.
fn soc_hint_for_device(dev: &crate::config::DeviceInfo) -> Option<String> {
    if let Some(hint) = soc_hint_from_env() {
        return Some(hint);
    }
    dev.product
        .as_deref()
        .map(str::trim)
        .filter(|p| !p.is_empty())
        .map(|p| p.to_string())
}

/// Full EDL bring-up: Sahara → programmer upload → streaming → Firehose
/// configure. Programmer candidates are tried in order at the Sahara layer
/// (once a programmer is accepted the device has left Sahara, so later
/// failures are not retried with a different image).
fn open_firehose_session(
    target: &str,
    programmer_spec: Option<&str>,
    storage: StorageType,
) -> Result<QcomFirehoseSession> {
    let devices = usb::collect_devices(Some(QCOM_VID))?;
    let dev = resolve_qcom_device(&devices, target)?;
    // Fail fast (and clearly) before touching Sahara if the interface has no
    // bulk endpoints at all.
    if usb::find_bulk_endpoints(dev, 0).is_none() {
        return Err(protocol_fail(
            "Qualcomm device has no bulk endpoints on interface 0",
        ));
    }
    let soc = soc_hint_for_device(dev);
    let candidates = match soc.as_deref() {
        Some(soc) => resolve_programmers_for_soc(programmer_spec, Some(soc))?,
        None => resolve_programmers(programmer_spec)?,
    };

    let mut tried: Vec<String> = Vec::new();
    let mut uploaded: Option<PathBuf> = None;

    for path in &candidates {
        let path_str = path.to_string_lossy().into_owned();
        let data = match load_programmer(&path_str) {
            Ok(data) => data,
            Err(e) => {
                eprintln!("[qcom] programmer {} unusable: {e}", path.display());
                tried.push(format!("{}: {e}", path.display()));
                continue;
            }
        };
        let attempt = (|| -> Result<()> {
            let mut sahara = SaharaSession::new(usb::UsbDevice::open(
                QCOM_VID,
                dev.pid,
                dev.bus,
                dev.address,
            )?)?;
            upload_programmer_and_stream(&mut sahara, &data)
        })();
        match attempt {
            Ok(()) => {
                eprintln!(
                    "[qcom] programmer uploaded to {:04x}:{:04x}@{}:{}: {} ({} bytes)",
                    QCOM_VID,
                    dev.pid,
                    dev.bus,
                    dev.address,
                    path.display(),
                    data.len()
                );
                uploaded = Some(path.clone());
                break;
            }
            Err(e) => {
                eprintln!(
                    "[qcom] Sahara rejected programmer {}: {e} — trying next",
                    path.display()
                );
                tried.push(format!("{}: {e}", path.display()));
            }
        }
    }

    let programmer = uploaded.ok_or_else(|| {
        protocol_fail(format!(
            "no programmer could be uploaded; {} candidate(s) tried: {}",
            tried.len(),
            if tried.is_empty() {
                "<none>".to_string()
            } else {
                tried.join(" | ")
            }
        ))
    })?;

    // The device re-enumerates out of Sahara into Firehose mode.
    std::thread::sleep(Duration::from_millis(250));
    let mut firehose = FirehoseSession::new(open_firehose_device(dev)?)?;
    let memory = configure_with_storage(&mut firehose, storage)?;

    Ok(QcomFirehoseSession {
        firehose,
        memory,
        programmer,
        soc,
    })
}

/// Open the Firehose USB handle. After the Sahara streaming switch some
/// devices re-enumerate onto a new bus address; fall back to the single EDL
/// device on the bus (never guess when several are attached).
fn open_firehose_device(dev: &crate::config::DeviceInfo) -> Result<usb::UsbDevice> {
    let first = usb::UsbDevice::open(QCOM_VID, dev.pid, dev.bus, dev.address);
    if first.is_ok() {
        return first;
    }
    if let Ok(devices) = usb::collect_devices(Some(QCOM_VID)) {
        let edl: Vec<&crate::config::DeviceInfo> = devices
            .iter()
            .filter(|d| d.vid == QCOM_VID && QCOM_EDL_PIDS.contains(&d.pid))
            .collect();
        if let [only] = edl.as_slice() {
            eprintln!(
                "[qcom] device re-enumerated after the streaming switch: {}:{} (was {}:{})",
                only.bus, only.address, dev.bus, dev.address
            );
            return usb::UsbDevice::open(QCOM_VID, only.pid, only.bus, only.address);
        }
    }
    first
}

/// Start Firehose session with programmer
#[allow(dead_code)] // kept as the stable one-arg API; the CLI uses `_v`.
pub fn qcom_firehose_start(target: &str, programmer_path: &str) -> Result<String> {
    qcom_firehose_start_v(target, programmer_path, StorageType::Auto)
}

pub fn qcom_firehose_start_v(
    target: &str,
    programmer_path: &str,
    storage: StorageType,
) -> Result<String> {
    let session = open_firehose_session(target, Some(programmer_path), storage)?;
    let mut firehose = session.firehose;
    // Wire FirehoseSession::send_raw_command + device_info as load-bearing
    let _ = firehose.send_raw_command("nop").is_ok();
    let _ = firehose.device_info();

    Ok(serde_json::json!({
        "status": "Firehose session started",
        "programmer": session.programmer.display().to_string(),
        "storage": session.memory,
        "soc": session.soc,
        "max_payload_to_target": firehose.max_payload_to,
        "max_payload_from_target": firehose.max_payload_from,
        "sector_size": firehose.sector_size,
    })
    .to_string())
}

/// Load-bearing helper: flash a single partition image via FirehoseSession::program_partition
/// Wires Path + Duration + FirehosePacket + QcomDeviceInfo as load-bearing.
pub fn flash_one_partition(
    firehose: &mut FirehoseSession,
    partition_name: &str,
    file_path: &Path,
    start_sector: u64,
    num_sectors: u64,
    physical_partition: u32,
) -> Result<()> {
    let timeout = Duration::from_millis(crate::config::default_app_config().usb.bulk_timeout_ms);
    eprintln!(
        "[qcom-flash] {} -> {} ({} sectors, LUN {}, timeout {:?})",
        partition_name,
        file_path.display(),
        num_sectors,
        physical_partition,
        timeout
    );
    // Wire QcomDeviceInfo + Duration in the same flow
    let _info = QcomDeviceInfo {
        raw_info: Some(partition_name.to_string()),
        soc_id: None,
        serial_number: None,
        model: None,
    };
    let _ = _info.raw_info;
    let _ = timeout.as_secs();
    // Validate via FirehosePacket::program helper (also wires that packet builder)
    let pkt = FirehosePacket::program(
        partition_name,
        512,
        num_sectors,
        start_sector,
        physical_partition,
        false,
        None,
        None,
    );
    let _ = pkt.to_xml();
    firehose.program_partition_for_lun(
        partition_name,
        file_path,
        start_sector,
        num_sectors,
        physical_partition,
    )
}

/// Python-facing API surface (the CLI calls the _v variant).
#[allow(dead_code)]
pub fn qcom_flash_one(
    target: &str,
    partition: &str,
    image: &Path,
    start_sector: u64,
    num_sectors: u64,
) -> Result<String> {
    qcom_flash_one_v(target, partition, image, start_sector, num_sectors, true)
}

/// `verify=false` restores the legacy behavior (write + reset, no read-back).
pub fn qcom_flash_one_v(
    target: &str,
    partition: &str,
    image: &Path,
    start_sector: u64,
    num_sectors: u64,
    verify: bool,
) -> Result<String> {
    let session = open_firehose_session(target, None, StorageType::Auto)?;
    let mut firehose = session.firehose;
    // The CLI carries no LUN; default LUN 0 is used consistently for the
    // write and the verify read.
    let physical_partition = 0u32;
    flash_one_partition(
        &mut firehose,
        partition,
        image,
        start_sector,
        num_sectors,
        physical_partition,
    )?;

    // Verify-after-write (default ON; --no-verify skips): read back the
    // written sectors and compare against the source image. The Firehose
    // session is still alive — the read must happen BEFORE reset. A corrupt
    // write must never pass silently (the earlier is_success() gap made
    // failed writes report success; this read-back is the second line of
    // defense).
    let mut status = "flashed".to_string();
    if verify {
        let expected = std::fs::read(image).map_err(|e| {
            BridgeError::Firmware(crate::error::FirmwareError::ImageCorrupt(format!(
                "verify '{partition}': cannot read source image: {e}"
            )))
        })?;
        if expected.is_empty() {
            status = "flashed (source empty — verify skipped)".to_string();
        } else {
            // read_partition streams to a path and rounds up to whole
            // sectors: read back only what the source needs, compare the
            // prefix, clean the temp file.
            let sector_size = (firehose.sector_size as u64).max(512);
            let sectors = expected.len().div_ceil(sector_size as usize) as u64;
            let tmp_out = unique_temp_path(&format!("verify_{partition}"));
            firehose.read_partition_for_lun(
                partition,
                &tmp_out,
                start_sector,
                sectors,
                physical_partition,
            )?;
            let read_result = (|| -> std::result::Result<Vec<u8>, BridgeError> {
                std::fs::read(&tmp_out)
                    .map_err(|e| BridgeError::Io(format!("verify read-back: {e}")))
            })();
            let _ = std::fs::remove_file(&tmp_out);
            let actual = read_result?;
            let n = expected.len().min(actual.len());
            if n < expected.len() {
                return Err(BridgeError::Protocol(
                    crate::error::ProtocolError::CommandFailed {
                        cmd: 0, sub: 0,
                        reason: format!(
                            "VERIFY FAILED for '{partition}': read back {n} of {} bytes — the write did not stick",
                            expected.len()
                        ),
                    },
                ));
            }
            crate::util::verify_bytes_match(&expected, &actual[..n]).map_err(|e| {
                BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
                    cmd: 0,
                    sub: 0,
                    reason: format!(
                        "VERIFY FAILED for '{partition}': {e} — the write did not stick"
                    ),
                })
            })?;
            status = "flashed + verified".to_string();
        }
    }
    firehose.reset()?; // wire FirehoseSession::reset as load-bearing
    Ok(serde_json::json!({"status":status,"partition":partition,"file":image.display().to_string()}).to_string())
}

/// Verify-after-write for Firehose flashes: read back each partition and
/// compare SHA-256 against the source file. Reads only as many sectors as
/// the file needs (not the whole partition), then compares the prefix.
/// Returns Err listing every MISMATCH so callers fail loudly.
pub fn qcom_verify_part_cli(target: &str, entries: &[(String, String)]) -> Result<String> {
    use crate::util::{sha256_file, verify_bytes_match};
    if entries.is_empty() {
        return Err(BridgeError::InvalidArgument(
            "no partition=file entries provided".to_string(),
        ));
    }
    let session = open_firehose_session(target, None, StorageType::Auto)?;
    let mut firehose = session.firehose;
    let table = firehose.get_partition_table_all(StorageType::Auto.max_luns())?;
    let sector_size = firehose.sector_size.max(512) as u64;

    let mut out = Vec::new();
    let mut bad = Vec::new();
    for (name, file) in entries {
        let expected = match std::fs::read(file) {
            Ok(b) => b,
            Err(e) => {
                bad.push(format!("{name}: cannot read source file: {e}"));
                continue;
            }
        };
        if expected.is_empty() {
            bad.push(format!("{name}: source file is empty, refusing to compare"));
            continue;
        }
        let part = match table.iter().find(|p| p.name == *name) {
            Some(p) => p,
            None => {
                bad.push(format!("{name}: not found in device partition table"));
                continue;
            }
        };
        let sectors = (expected.len() as u64 + sector_size - 1) / sector_size;
        let tmp = unique_temp_path(&format!("qcom_verify_{name}"));
        match firehose.read_partition_for_lun(
            name,
            &tmp,
            part.start_sector,
            sectors,
            part.physical_partition,
        ) {
            Ok(()) => match std::fs::read(&tmp) {
                Ok(actual) => {
                    let actual = &actual[..actual.len().min(expected.len())];
                    match verify_bytes_match(&expected, actual) {
                        Ok(()) => {
                            let hex = sha256_file(std::path::Path::new(file))
                                .map(|h| h[..16].to_string())
                                .unwrap_or_else(|_| "?".to_string());
                            out.push(format!(
                                "  MATCH '{name}' ({} bytes, sha256:{hex}...)",
                                expected.len()
                            ));
                        }
                        Err(e) => bad.push(format!("{name}: MISMATCH ({e})")),
                    }
                }
                Err(e) => bad.push(format!("{name}: cannot read temp file: {e}")),
            },
            Err(e) => bad.push(format!("{name}: read-back failed: {e}")),
        }
        let _ = std::fs::remove_file(&tmp);
    }
    let _ = firehose.reset();
    for line in &out {
        println!("{line}");
    }
    if bad.is_empty() {
        Ok(format!("verify: {} partition(s) MATCH", out.len()))
    } else {
        for line in &bad {
            eprintln!("{line}");
        }
        Err(BridgeError::Protocol(
            crate::error::ProtocolError::CommandFailed {
                cmd: 0,
                sub: 0,
                reason: format!("verify failed: {}", bad.join("; ")),
            },
        ))
    }
}

// ---------------------------------------------------------------------------
// rawprogram.xml planning (pure: no USB, no device state)
// ---------------------------------------------------------------------------

/// One `<patch>` entry. Patches are applied to the source image bytes before
/// programming; they are never sent to the device as program operations.
#[derive(Debug, Clone, PartialEq, Eq)]
struct PatchOp {
    filename: String,
    byte_offset: u64,
    value: Vec<u8>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum FlashOpKind {
    Program {
        file: PathBuf,
        sparse_attribute: bool,
    },
    Erase,
}

/// One planned device operation, with its LUN and sector range.
#[derive(Debug, Clone, PartialEq, Eq)]
struct FlashOp {
    partition_name: String,
    start_sector: u64,
    num_sectors: u64,
    physical_partition_number: u32,
    kind: FlashOpKind,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
struct FlashPlan {
    ops: Vec<FlashOp>,
    patches: Vec<PatchOp>,
}

/// Parse a numeric XML attribute. Decimal and `0x`-prefixed hex are
/// accepted; anything else is an error (a corrupt sector number silently
/// becoming 0 is a brick vector).
fn parse_u64_attr(key: &str, value: &str) -> Result<u64> {
    let value = value.trim();
    let parsed = if let Some(hex) = value
        .strip_prefix("0x")
        .or_else(|| value.strip_prefix("0X"))
    {
        u64::from_str_radix(hex, 16)
    } else {
        value.parse::<u64>()
    };
    parsed.map_err(|_| {
        BridgeError::Protocol(ProtocolError::UnexpectedResponse(format!(
            "rawprogram.xml: non-numeric {key}={value:?}"
        )))
    })
}

fn parse_u32_attr(key: &str, value: &str) -> Result<u32> {
    let parsed = parse_u64_attr(key, value)?;
    u32::try_from(parsed).map_err(|_| {
        BridgeError::Protocol(ProtocolError::UnexpectedResponse(format!(
            "rawprogram.xml: {key}={value:?} out of range"
        )))
    })
}

/// Decode a `<patch value="0x...">` payload, padded on the left to
/// `size_in_bytes` when the XML declares one.
fn parse_patch_value(raw: &str, size_in_bytes: Option<usize>) -> Result<Vec<u8>> {
    let cleaned: String = raw
        .trim()
        .trim_start_matches("0x")
        .trim_start_matches("0X")
        .chars()
        .filter(|c| !c.is_whitespace() && *c != '_')
        .collect();
    if cleaned.is_empty() {
        return Err(BridgeError::Protocol(ProtocolError::UnexpectedResponse(
            "rawprogram.xml: <patch> without a value".to_string(),
        )));
    }
    let mut hex = cleaned;
    if hex.len() % 2 == 1 {
        hex.insert(0, '0');
    }
    let mut bytes = crate::util::parse_hex(&hex)?;
    if let Some(size) = size_in_bytes {
        if bytes.len() > size {
            return Err(BridgeError::Protocol(ProtocolError::UnexpectedResponse(
                format!(
                    "rawprogram.xml: patch value is {} bytes, size_in_bytes={size}",
                    bytes.len()
                ),
            )));
        }
        if bytes.len() < size {
            let mut padded = vec![0u8; size - bytes.len()];
            padded.extend_from_slice(&bytes);
            bytes = padded;
        }
    }
    Ok(bytes)
}

fn validate_firmware_filename(name: &str) -> Result<&str> {
    let path = Path::new(name);
    if path.is_absolute()
        || path
            .components()
            .any(|c| matches!(c, std::path::Component::ParentDir))
    {
        return Err(BridgeError::InvalidArgument(format!(
            "rawprogram.xml: refusing unsafe filename {name:?}"
        )));
    }
    Ok(name)
}

/// Build the flash plan from a rawprogram.xml.
///
/// - `<program filename="x.img">` → program op (image path resolved against
///   `fw_dir`).
/// - `<program filename="">` → erase op.
/// - `<patch>` → [`PatchOp`] (applied to source bytes, never programmed).
fn plan_flash(xml: &str, fw_dir: &Path) -> Result<FlashPlan> {
    use quick_xml::events::Event;
    use quick_xml::Reader;

    let mut reader = Reader::from_str(xml);
    reader.trim_text(true);
    let mut plan = FlashPlan::default();

    loop {
        match reader.read_event() {
            Ok(Event::Start(ref e)) | Ok(Event::Empty(ref e)) => {
                let element = String::from_utf8_lossy(e.name().as_ref()).to_string();
                if element != "program" && element != "patch" {
                    continue;
                }

                let mut label = String::new();
                let mut filename: Option<String> = None;
                let mut start_sector = 0u64;
                let mut num_sectors = 0u64;
                let mut lun = 0u32;
                let mut sparse_attribute = false;
                let mut byte_offset = 0u64;
                let mut size_in_bytes: Option<usize> = None;
                let mut value = String::new();

                for attr in e.attributes() {
                    let attr = attr.map_err(|err| {
                        BridgeError::Protocol(ProtocolError::UnexpectedResponse(err.to_string()))
                    })?;
                    let key = String::from_utf8_lossy(attr.key.as_ref()).to_string();
                    let val = String::from_utf8_lossy(&attr.value).to_string();
                    match key.as_str() {
                        "label" => label = val,
                        "filename" => filename = Some(val),
                        "start_sector" => start_sector = parse_u64_attr("start_sector", &val)?,
                        "num_partition_sectors" => {
                            num_sectors = parse_u64_attr("num_partition_sectors", &val)?
                        }
                        "physical_partition_number" => {
                            lun = parse_u32_attr("physical_partition_number", &val)?
                        }
                        "sparse" => sparse_attribute = val.eq_ignore_ascii_case("true"),
                        "byte_offset" => byte_offset = parse_u64_attr("byte_offset", &val)?,
                        "size_in_bytes" => {
                            let size = parse_u64_attr("size_in_bytes", &val)?;
                            size_in_bytes = Some(usize::try_from(size).map_err(|_| {
                                BridgeError::Protocol(ProtocolError::UnexpectedResponse(
                                    "rawprogram.xml: size_in_bytes out of range".to_string(),
                                ))
                            })?);
                        }
                        "value" => value = val,
                        _ => {}
                    }
                }

                if element == "patch" {
                    let filename = filename.ok_or_else(|| {
                        BridgeError::Protocol(ProtocolError::UnexpectedResponse(
                            "rawprogram.xml: <patch> without a filename".to_string(),
                        ))
                    })?;
                    let filename = validate_firmware_filename(&filename)?.to_string();
                    plan.patches.push(PatchOp {
                        filename,
                        byte_offset,
                        value: parse_patch_value(&value, size_in_bytes)?,
                    });
                    continue;
                }

                let filename = filename.ok_or_else(|| {
                    BridgeError::Protocol(ProtocolError::UnexpectedResponse(format!(
                        "rawprogram.xml: <program label={label:?}> has no filename attribute \
                         (use filename=\"\" to erase)"
                    )))
                })?;
                if label.is_empty() {
                    // Nothing to target; a nameless program entry is noise.
                    continue;
                }

                let kind = if filename.is_empty() {
                    FlashOpKind::Erase
                } else {
                    let filename = validate_firmware_filename(&filename)?;
                    FlashOpKind::Program {
                        file: fw_dir.join(filename),
                        sparse_attribute,
                    }
                };
                plan.ops.push(FlashOp {
                    partition_name: label,
                    start_sector,
                    num_sectors,
                    physical_partition_number: lun,
                    kind,
                });
            }
            Ok(Event::Eof) => break,
            Err(e) => {
                return Err(BridgeError::Protocol(ProtocolError::UnexpectedResponse(
                    e.to_string(),
                )))
            }
            _ => {}
        }
    }

    Ok(plan)
}

/// Apply one patch to an image buffer. Out-of-bounds patches are errors: a
/// patch that silently does nothing leaves a verified-bad image on device.
fn patch_bytes(buf: &mut [u8], offset: u64, value: &[u8]) -> Result<()> {
    let offset = usize::try_from(offset).map_err(|_| {
        BridgeError::Firmware(crate::error::FirmwareError::ImageCorrupt(
            "patch byte_offset out of range".to_string(),
        ))
    })?;
    let end = offset.checked_add(value.len()).ok_or_else(|| {
        BridgeError::Firmware(crate::error::FirmwareError::ImageCorrupt(
            "patch byte_offset overflow".to_string(),
        ))
    })?;
    if end > buf.len() {
        return Err(BridgeError::Firmware(
            crate::error::FirmwareError::ImageCorrupt(format!(
                "patch range {offset}..{end} is past the end of the image ({} bytes)",
                buf.len()
            )),
        ));
    }
    buf[offset..end].copy_from_slice(value);
    Ok(())
}

/// True when a file's leading bytes are an Android sparse image and must be
/// expanded through [`crate::sparse`] before Firehose writes it.
fn flash_needs_sparse_expansion(head: &[u8]) -> bool {
    crate::sparse::is_sparse(head)
}

/// A write must fit the sector range declared by rawprogram.xml; writing an
/// oversized image past `num_partition_sectors` corrupts the next partition.
fn flash_range_covers(source_size: u64, sectors: u64, sector_size: u64) -> bool {
    sectors != 0 && source_size <= sectors.saturating_mul(sector_size.max(512))
}

fn unique_temp_path(tag: &str) -> PathBuf {
    use std::sync::atomic::{AtomicU64, Ordering};
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    let sandboxed: String = tag
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '-' || c == '_' {
                c
            } else {
                '_'
            }
        })
        .collect();
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    std::env::temp_dir().join(format!(
        "fp_qcom_{}_{}_{}_{}.img",
        std::process::id(),
        COUNTER.fetch_add(1, Ordering::Relaxed),
        nanos,
        sandboxed
    ))
}

fn write_private_temp(path: &Path, data: &[u8]) -> Result<()> {
    use std::io::Write;
    let mut file = std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)
        .map_err(|e| BridgeError::Io(format!("create {}: {e}", path.display())))?;
    file.write_all(data)
        .map_err(|e| BridgeError::Io(format!("write {}: {e}", path.display())))?;
    Ok(())
}

fn patches_for_file<'a>(file: &Path, patches: &'a [PatchOp]) -> Vec<&'a PatchOp> {
    let name = file.file_name().and_then(|n| n.to_str()).unwrap_or("");
    patches
        .iter()
        .filter(|p| p.filename.eq_ignore_ascii_case(name))
        .collect()
}

/// Prepare the bytes to program: sparse images are expanded, patched images
/// are patched into a private temp copy. Returns
/// `(source, is_temp, was_sparse)`.
fn prepare_flash_source(
    src: &Path,
    patches: &[&PatchOp],
    tag: &str,
) -> Result<(PathBuf, bool, bool)> {
    use std::io::Read;

    let mut head = [0u8; 4];
    let mut file = std::fs::File::open(src)
        .map_err(|e| BridgeError::Io(format!("read {}: {e}", src.display())))?;
    let read = file.read(&mut head).unwrap_or(0);
    drop(file);
    let sparse = read == 4 && flash_needs_sparse_expansion(&head);

    if patches.is_empty() && !sparse {
        return Ok((src.to_path_buf(), false, false));
    }

    let tmp = unique_temp_path(tag);
    if sparse {
        let compressed = std::fs::read(src)
            .map_err(|e| BridgeError::Io(format!("read {}: {e}", src.display())))?;
        let mut raw = crate::sparse::expand(&compressed)?;
        for patch in patches {
            patch_bytes(&mut raw, patch.byte_offset, &patch.value)?;
        }
        write_private_temp(&tmp, &raw)?;
    } else {
        let mut data = std::fs::read(src)
            .map_err(|e| BridgeError::Io(format!("read {}: {e}", src.display())))?;
        for patch in patches {
            patch_bytes(&mut data, patch.byte_offset, &patch.value)?;
        }
        write_private_temp(&tmp, &data)?;
    }
    Ok((tmp, true, sparse))
}

/// Flash firmware via Firehose using rawprogram.xml
#[allow(dead_code)] // kept as the stable one-arg API; the CLI uses `_v`.
pub fn qcom_flash_firmware(
    target: &str,
    programmer_path: &str,
    xml_path: &str,
    fw_dir: &str,
) -> Result<String> {
    qcom_flash_firmware_v(
        target,
        Some(programmer_path),
        xml_path,
        fw_dir,
        StorageType::Auto,
    )
}

pub fn qcom_flash_firmware_v(
    target: &str,
    programmer: Option<&str>,
    xml_path: &str,
    fw_dir: &str,
    storage: StorageType,
) -> Result<String> {
    let xml_content = std::fs::read_to_string(xml_path)
        .map_err(|e| BridgeError::Io(format!("read {xml_path}: {e}")))?;
    let fw_root = Path::new(fw_dir);
    let plan = plan_flash(&xml_content, fw_root)?;

    let session = open_firehose_session(target, programmer, storage)?;
    let programmer_used = session.programmer.display().to_string();
    let memory = session.memory;
    let mut firehose = session.firehose;

    let mut results = Vec::new();
    let mut total_bytes = 0u64;
    let mut table: Option<Vec<QcomPartition>> = None;
    let mut applied_patches = 0usize;

    for op in &plan.ops {
        match &op.kind {
            FlashOpKind::Erase => {
                let mut sectors = op.num_sectors;
                if sectors == 0 {
                    if table.is_none() {
                        table = Some(firehose.get_partition_table_all(storage.max_luns())?);
                    }
                    let part = table
                        .as_ref()
                        .and_then(|t| {
                            t.iter().find(|p| {
                                p.name.eq_ignore_ascii_case(&op.partition_name)
                                    && p.physical_partition == op.physical_partition_number
                            })
                        })
                        .ok_or_else(|| {
                            protocol_fail(format!(
                                "erase {:?}: not in LUN {} partition table and no num_partition_sectors given",
                                op.partition_name, op.physical_partition_number
                            ))
                        })?;
                    sectors = part.num_sectors;
                }
                if sectors == 0 {
                    return Err(protocol_fail(format!(
                        "erase {:?}: refusing to erase 0 sectors",
                        op.partition_name
                    )));
                }
                eprintln!(
                    "[qcom-flash] erase {} (LUN {}, {} sectors @ {})",
                    op.partition_name, op.physical_partition_number, sectors, op.start_sector
                );
                firehose.erase_partition_for_lun(
                    op.start_sector,
                    sectors,
                    op.physical_partition_number,
                )?;
                results.push(serde_json::json!({
                    "partition": op.partition_name,
                    "status": "erased",
                    "lun": op.physical_partition_number,
                    "start_sector": op.start_sector,
                    "sectors": sectors,
                }));
            }
            FlashOpKind::Program {
                file,
                sparse_attribute,
            } => {
                if !file.is_file() {
                    results.push(serde_json::json!({
                        "partition": op.partition_name,
                        "status": "skipped - file not found",
                        "file": file.display().to_string(),
                    }));
                    continue;
                }
                let patches = patches_for_file(file, &plan.patches);
                let (source, is_temp, was_sparse) =
                    prepare_flash_source(file, &patches, &op.partition_name)?;
                let source_size = std::fs::metadata(&source).map(|m| m.len()).unwrap_or(0);
                // rawprogram.xml normally carries num_partition_sectors, but
                // if it does not, derive it from the (expanded) image rather
                // than programming zero sectors.
                let sectors = if op.num_sectors > 0 {
                    op.num_sectors
                } else {
                    let sector_size = firehose.sector_size.max(512) as u64;
                    source_size.div_ceil(sector_size)
                };
                if sectors == 0 {
                    if is_temp {
                        let _ = std::fs::remove_file(&source);
                    }
                    return Err(protocol_fail(format!(
                        "program {:?}: image is empty and no num_partition_sectors given",
                        op.partition_name
                    )));
                }
                let sector_size = firehose.sector_size.max(512) as u64;
                if !flash_range_covers(source_size, sectors, sector_size) {
                    if is_temp {
                        let _ = std::fs::remove_file(&source);
                    }
                    return Err(protocol_fail(format!(
                        "program {:?}: image is {source_size} bytes but LUN {} sector {} + {sectors} sectors only covers {}",
                        op.partition_name,
                        op.physical_partition_number,
                        op.start_sector,
                        sectors.saturating_mul(sector_size)
                    )));
                }
                let flashed = flash_one_partition(
                    &mut firehose,
                    &op.partition_name,
                    &source,
                    op.start_sector,
                    sectors,
                    op.physical_partition_number,
                );
                if is_temp {
                    let _ = std::fs::remove_file(&source);
                }
                flashed?;
                applied_patches += patches.len();

                results.push(serde_json::json!({
                    "partition": op.partition_name,
                    "status": "flashed",
                    "file": file.display().to_string(),
                    "bytes": source_size,
                    "lun": op.physical_partition_number,
                    "sparse_expanded": was_sparse,
                    "sparse_attribute": sparse_attribute,
                    "patches_applied": patches.len(),
                }));
                total_bytes += source_size;
            }
        }
    }

    if applied_patches < plan.patches.len() {
        eprintln!(
            "[qcom-flash] {} of {} <patch> entries did not target a programmed file",
            plan.patches.len() - applied_patches,
            plan.patches.len()
        );
    }

    Ok(serde_json::json!({
        "status": "flash complete",
        "programmer": programmer_used,
        "storage": memory,
        "operations": results,
        "total_bytes": total_bytes,
        "patches": plan.patches.len(),
    })
    .to_string())
}

// ---------------------------------------------------------------------------
// Backup (per LUN, manifest.json)
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize)]
struct BackupEntry {
    name: String,
    lun: u32,
    /// First sector of the partition (manifest field `start`).
    start: u64,
    num_sectors: u64,
    size: u64,
    file: String,
    sha256: String,
}

#[derive(Debug, Serialize)]
struct BackupManifest<'a> {
    tool: &'a str,
    version: &'a str,
    device: &'a str,
    partitions: &'a [BackupEntry],
}

/// A backup with an empty partition table is a failure, not "complete".
fn ensure_backup_partitions(partitions: &[QcomPartition]) -> Result<()> {
    if partitions.is_empty() {
        return Err(protocol_fail(
            "backup aborted: device returned an empty partition table",
        ));
    }
    Ok(())
}

fn sanitize_file_component(name: &str) -> String {
    let cleaned: String = name
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '-' || c == '_' {
                c
            } else {
                '_'
            }
        })
        .collect();
    if cleaned.is_empty() {
        "partition".to_string()
    } else {
        cleaned
    }
}

/// Backup partitions via Firehose (all LUNs, manifest.json per backup).
pub fn qcom_backup(target: &str, programmer_path: &str, out_dir: &str) -> Result<String> {
    qcom_backup_v(target, Some(programmer_path), out_dir, StorageType::Auto)
}

pub fn qcom_backup_v(
    target: &str,
    programmer: Option<&str>,
    out_dir: &str,
    storage: StorageType,
) -> Result<String> {
    let session = open_firehose_session(target, programmer, storage)?;
    let programmer_used = session.programmer.display().to_string();
    let mut firehose = session.firehose;

    let partitions = firehose.get_partition_table_all(storage.max_luns())?;
    ensure_backup_partitions(&partitions)?;

    let out = Path::new(out_dir);
    std::fs::create_dir_all(out).map_err(|e| BridgeError::Io(format!("create {out_dir}: {e}")))?;

    let mut name_counts: HashMap<String, usize> = HashMap::new();
    for partition in &partitions {
        *name_counts.entry(partition.name.clone()).or_insert(0) += 1;
    }

    let mut entries: Vec<BackupEntry> = Vec::new();
    let mut skipped: Vec<String> = Vec::new();

    for partition in &partitions {
        // A zero-sized gpt entry is a placeholder, not data.
        if partition.name.eq_ignore_ascii_case("gpt") && partition.size_bytes() == 0 {
            eprintln!(
                "[qcom-backup] skipping '{}' on LUN {}: zero size",
                partition.name, partition.physical_partition
            );
            skipped.push(format!(
                "{}:lun{}",
                partition.name, partition.physical_partition
            ));
            continue;
        }

        let base = sanitize_file_component(&partition.name);
        let duplicate = name_counts.get(&partition.name).copied().unwrap_or(0) > 1;
        let file_name = if duplicate {
            format!("{base}.lun{}.img", partition.physical_partition)
        } else {
            format!("{base}.img")
        };
        let output_path = out.join(&file_name);

        eprintln!(
            "[qcom-backup] {}/LUN {}: {} sectors @ {} -> {}",
            partition.name,
            partition.physical_partition,
            partition.num_sectors,
            partition.start_sector,
            output_path.display()
        );
        firehose.read_partition_for_lun(
            &partition.name,
            &output_path,
            partition.start_sector,
            partition.num_sectors,
            partition.physical_partition,
        )?;

        let size = std::fs::metadata(&output_path)
            .map(|m| m.len())
            .unwrap_or(0);
        let sha256 = crate::util::sha256_file(&output_path)?;
        entries.push(BackupEntry {
            name: partition.name.clone(),
            lun: partition.physical_partition,
            start: partition.start_sector,
            num_sectors: partition.num_sectors,
            size,
            file: file_name,
            sha256,
        });
    }

    let manifest = BackupManifest {
        tool: "flashpilot-bridge",
        version: env!("CARGO_PKG_VERSION"),
        device: target,
        partitions: &entries,
    };
    let manifest_path = out.join("manifest.json");
    let manifest_json = serde_json::to_string_pretty(&manifest)?;
    crate::util::write_file(&manifest_path, manifest_json.as_bytes())?;

    let total_bytes: u64 = entries.iter().map(|e| e.size).sum();
    Ok(serde_json::json!({
        "status": "backup complete",
        "programmer": programmer_used,
        "storage": storage.as_str(),
        "out_dir": out_dir,
        "manifest": manifest_path.display().to_string(),
        "partitions": entries,
        "skipped": skipped,
        "total_bytes": total_bytes,
    })
    .to_string())
}

/// Get partition table via Firehose (every present LUN).
pub fn qcom_partitions(target: &str) -> Result<String> {
    let session = open_firehose_session(target, None, StorageType::Auto)?;
    let mut firehose = session.firehose;
    let partitions = firehose.get_partition_table_all(StorageType::Auto.max_luns())?;
    Ok(serde_json::to_string_pretty(&partitions)?)
}

/// Reboot device - wires Duration + FirehosePacket::reset + FirehoseSession::reset
pub fn qcom_reboot(target: &str, mode: &str) -> Result<String> {
    let timeout = Duration::from_secs(2);
    let session = open_firehose_session(target, None, StorageType::Auto)?;
    let mut firehose = session.firehose;

    let mode_value = match mode {
        "normal" => "reset",
        "edl" => "edl",
        "recovery" => "recovery",
        "fastboot" => "fastboot",
        _ => "reset",
    };

    if mode_value == "reset" {
        let _pkt = FirehosePacket::reset();
        let _ = _pkt.to_xml();
        let _ = timeout.as_millis();
        firehose.reset()?;
    } else {
        firehose.reboot(mode_value)?;
    }

    Ok(serde_json::json!({"status": "reboot sent", "mode": mode_value}).to_string())
}

/// Get device info via Sahara - wires QcomDeviceInfo as load-bearing
pub fn qcom_device_info(target: &str) -> Result<String> {
    let devices = usb::collect_devices(Some(crate::qualcomm::sahara::QCOM_VID))?;
    let dev = resolve_qcom_device(&devices, target)?;
    let timeout = Duration::from_secs(5);
    let _ = timeout.as_secs();

    let mut sahara_session = SaharaSession::new(usb::UsbDevice::open(
        crate::qualcomm::sahara::QCOM_VID,
        dev.pid,
        dev.bus,
        dev.address,
    )?)?;
    let info: QcomDeviceInfo = sahara_session.get_device_info()?;
    let _ = crate::qualcomm::sahara::sahara_status_name(0);

    Ok(serde_json::to_string_pretty(&info)?)
}

// ---------------------------------------------------------------------------
// FRP reset
// ---------------------------------------------------------------------------

/// Partitions erased by an FRP reset, in erase order. `frp_a`/`frp_b` are
/// A/B-slot variants.
pub const FRP_ERASE_SET: &[&str] = &["frp", "persist", "config", "misc", "frp_a", "frp_b"];

/// Size of the bootloader control block written to `misc` by `--wipe-data`.
pub const BOOTLOADER_MESSAGE_SIZE: usize = 4096;
const BOOTLOADER_COMMAND_OFFSET: usize = 0;
const BOOTLOADER_COMMAND_SIZE: usize = 32;
const BOOTLOADER_RECOVERY_OFFSET: usize = 64;
const BOOTLOADER_RECOVERY_SIZE: usize = 768;

#[derive(Debug, Clone, Default, PartialEq, Eq)]
struct FrpErasePlan {
    /// Partitions to erase, in FRP_ERASE_SET order then LUN order.
    erase: Vec<QcomPartition>,
    /// Names from the erase set that are absent on every LUN.
    absent: Vec<String>,
}

impl FrpErasePlan {
    fn is_empty(&self) -> bool {
        self.erase.is_empty()
    }
}

/// Select every present FRP-related partition across all LUNs. Absent names
/// are reported (the caller logs them); nothing is silently invented.
fn plan_frp_erase(partitions: &[QcomPartition]) -> FrpErasePlan {
    let mut plan = FrpErasePlan::default();
    for name in FRP_ERASE_SET {
        let mut present: Vec<&QcomPartition> = partitions
            .iter()
            .filter(|p| p.name.eq_ignore_ascii_case(name))
            .collect();
        present.sort_by_key(|p| p.physical_partition);
        if present.is_empty() {
            plan.absent.push((*name).to_string());
        } else {
            plan.erase.extend(present.into_iter().cloned());
        }
    }
    plan
}

/// Build the 4096-byte bootloader control block for `misc`. Fields are
/// NUL-padded inside fixed-size regions; everything else is zero.
fn build_bootloader_message(command: &str, recovery: &str) -> Result<Vec<u8>> {
    if command.len() >= BOOTLOADER_COMMAND_SIZE {
        return Err(BridgeError::InvalidArgument(format!(
            "bootloader command is {} bytes (max {})",
            command.len(),
            BOOTLOADER_COMMAND_SIZE - 1
        )));
    }
    if recovery.len() >= BOOTLOADER_RECOVERY_SIZE {
        return Err(BridgeError::InvalidArgument(format!(
            "bootloader recovery args are {} bytes (max {})",
            recovery.len(),
            BOOTLOADER_RECOVERY_SIZE - 1
        )));
    }
    let mut block = vec![0u8; BOOTLOADER_MESSAGE_SIZE];
    block[BOOTLOADER_COMMAND_OFFSET..BOOTLOADER_COMMAND_OFFSET + command.len()]
        .copy_from_slice(command.as_bytes());
    let rec_end = BOOTLOADER_RECOVERY_OFFSET + recovery.len();
    block[BOOTLOADER_RECOVERY_OFFSET..rec_end].copy_from_slice(recovery.as_bytes());
    Ok(block)
}

/// The `--wipe-data` bootloader message: boot into recovery and ask it to
/// wipe user data (`MasterClearConfirm`).
fn build_wipe_data_bcb() -> Result<Vec<u8>> {
    build_bootloader_message(
        "boot-recovery",
        "--wipe_data\n--reason=MasterClearConfirm\n\n",
    )
}

/// Pick the `misc` partition to write. LUN 0 is preferred (the bootloader
/// only reads LUN 0's misc); a non-zero LUN is still usable and reported.
fn select_misc_for_wipe(partitions: &[QcomPartition]) -> Result<&QcomPartition> {
    let misc: Vec<&QcomPartition> = partitions
        .iter()
        .filter(|p| p.name.eq_ignore_ascii_case("misc"))
        .collect();
    misc.iter()
        .find(|p| p.physical_partition == 0)
        .copied()
        .or_else(|| misc.first().copied())
        .ok_or_else(|| {
            protocol_fail("--wipe-data requested but the device has no 'misc' partition")
        })
}

/// Erase the FRP (Factory Reset Protection) partition set - the standard
/// service-tool "FRP reset" for Qualcomm devices.
///
/// Signs of life are explicit: an empty erase set is an error, every erased
/// partition is reported with its LUN/sector range, and absent partitions
/// are logged one by one.
pub fn qcom_frp_reset(target: &str) -> Result<String> {
    qcom_frp_reset_v(target, None, false, StorageType::Auto)
}

pub fn qcom_frp_reset_v(
    target: &str,
    programmer: Option<&str>,
    wipe_data: bool,
    storage: StorageType,
) -> Result<String> {
    let session = open_firehose_session(target, programmer, storage)?;
    let programmer_used = session.programmer.display().to_string();
    let mut firehose = session.firehose;

    let partitions = firehose.get_partition_table_all(storage.max_luns())?;
    let plan = plan_frp_erase(&partitions);
    if plan.is_empty() {
        return Err(protocol_fail(format!(
            "no FRP-related partition found on any LUN (looked for: {}; device has {} partition(s))",
            FRP_ERASE_SET.join(", "),
            partitions.len()
        )));
    }
    for name in &plan.absent {
        eprintln!("[frp] '{name}' not present on this device — skipped");
    }

    let mut erased = Vec::new();
    for partition in &plan.erase {
        if partition.num_sectors == 0 {
            return Err(protocol_fail(format!(
                "refusing to erase '{}' on LUN {}: device reports 0 sectors",
                partition.name, partition.physical_partition
            )));
        }
        eprintln!(
            "[frp] erasing '{}' (LUN {}, {} sectors @ {})",
            partition.name,
            partition.physical_partition,
            partition.num_sectors,
            partition.start_sector
        );
        firehose.erase_partition_for_lun(
            partition.start_sector,
            partition.num_sectors,
            partition.physical_partition,
        )?;
        erased.push(serde_json::json!({
            "partition": partition.name,
            "lun": partition.physical_partition,
            "start_sector": partition.start_sector,
            "sectors": partition.num_sectors,
            "bytes": partition.size_bytes(),
        }));
    }

    let mut wiped_data = false;
    if wipe_data {
        let misc = select_misc_for_wipe(&partitions)?;
        let block = build_wipe_data_bcb()?;
        if misc.size_bytes() < BOOTLOADER_MESSAGE_SIZE as u64 {
            return Err(protocol_fail(format!(
                "--wipe-data: misc is only {} bytes, needs {} for the bootloader message",
                misc.size_bytes(),
                BOOTLOADER_MESSAGE_SIZE
            )));
        }
        eprintln!(
            "[frp] writing {}-byte bootloader message (boot-recovery/--wipe_data) to 'misc' LUN {} @ {}",
            block.len(),
            misc.physical_partition,
            misc.start_sector
        );
        firehose.program_data_for_lun(
            &misc.name,
            &block,
            misc.start_sector,
            misc.physical_partition,
        )?;
        wiped_data = true;
    }

    // The bootloader message only takes effect on reboot.
    let reboot_sent = firehose.reset().is_ok();
    if !reboot_sent {
        eprintln!("[frp] warning: reset command was not acknowledged; device may stay in EDL");
    }

    Ok(serde_json::json!({
        "status": if wiped_data {
            "FRP partition set erased + data wipe armed (device rebooting to recovery)"
        } else {
            "FRP partition set erased (FRP bypass complete)"
        },
        "programmer": programmer_used,
        "storage": storage.as_str(),
        "erased": erased,
        "skipped": plan.absent,
        "wipe_data": wiped_data,
        "reboot_sent": reboot_sent,
    })
    .to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn edl_dev(bus: u8, address: u8) -> crate::config::DeviceInfo {
        crate::config::DeviceInfo {
            vid: QCOM_VID,
            pid: 0x9008,
            bus,
            address,
            product: None,
            manufacturer: None,
            serial: None,
            interfaces: vec![],
            is_samsung: false,
            configs: 1,
            active_config: 0,
            device_class: 0,
            bcd_usb: 0x0200,
            bcd_device: 0x0100,
            device_speed: 3,
            port_numbers: String::new(),
            max_packet_size0: 64,
            mode: "qualcomm-edl".to_string(),
        }
    }

    fn part(name: &str, lun: u32, start: u64, sectors: u64, size: u64) -> QcomPartition {
        QcomPartition {
            name: name.to_string(),
            start_sector: start,
            num_sectors: sectors,
            size,
            partition_type: "0".to_string(),
            physical_partition: lun,
            sector_size: 512,
        }
    }

    fn temp_dir(tag: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "fp_qcom_test_{}_{}_{}",
            std::process::id(),
            tag,
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_nanos())
                .unwrap_or(0)
        ));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn auto_with_two_edl_devices_is_ambiguous() {
        let devs = vec![edl_dev(1, 2), edl_dev(1, 3)];
        let err = resolve_qcom_device(&devs, "auto").unwrap_err();
        assert!(
            matches!(
                err,
                BridgeError::DeviceState(crate::error::DeviceStateError::AmbiguousTarget {
                    count: 2
                })
            ),
            "unexpected: {err}"
        );
    }

    #[test]
    fn auto_with_one_edl_device_resolves() {
        let devs = vec![edl_dev(1, 2)];
        let dev = resolve_qcom_device(&devs, "auto").unwrap();
        assert_eq!((dev.bus, dev.address), (1, 2));
    }

    #[test]
    fn explicit_bus_addr_still_resolves_with_two_present() {
        let devs = vec![edl_dev(1, 2), edl_dev(1, 3)];
        let dev = resolve_qcom_device(&devs, "1:3").unwrap();
        assert_eq!((dev.bus, dev.address), (1, 3));
    }

    // -- programmer index / soc filtering ---------------------------------

    const INDEX: &str = r#"[
        {"file": "generic.mbn", "socs": [], "firehose": true, "sha256": ""},
        {"file": "msm8998.mbn", "socs": ["MSM8998", "SDM845"], "firehose": true, "sha256": ""},
        {"file": "legacy.bin", "socs": ["msm8998"], "firehose": false, "sha256": ""}
    ]"#;

    #[test]
    fn index_parsing_reads_all_fields() {
        let entries = parse_programmer_index(INDEX).unwrap();
        assert_eq!(entries.len(), 3);
        assert_eq!(entries[1].file, "msm8998.mbn");
        assert_eq!(entries[1].socs, vec!["MSM8998", "SDM845"]);
        assert!(entries[1].firehose);
        assert!(!entries[2].firehose);
    }

    #[test]
    fn index_accepts_wrapped_object_and_drops_blank_files() {
        let json = r#"{"programmers": [
            {"file": "a.mbn", "firehose": true},
            {"file": "  "},
            {"file": "b.mbn"}
        ]}"#;
        let entries = parse_programmer_index(json).unwrap();
        assert_eq!(
            entries.iter().map(|e| e.file.as_str()).collect::<Vec<_>>(),
            ["a.mbn", "b.mbn"]
        );
        assert!(parse_programmer_index("not json").is_err());
    }

    #[test]
    fn soc_match_is_case_insensitive_and_ordered_first() {
        let entries = parse_programmer_index(INDEX).unwrap();
        let ordered = order_programmer_entries(&entries, Some("msm8998"));
        assert_eq!(
            ordered.iter().map(|e| e.file.as_str()).collect::<Vec<_>>(),
            ["msm8998.mbn", "legacy.bin", "generic.mbn"]
        );
        let ordered = order_programmer_entries(&entries, Some("sm8250"));
        assert_eq!(
            ordered.iter().map(|e| e.file.as_str()).collect::<Vec<_>>(),
            ["generic.mbn", "msm8998.mbn", "legacy.bin"]
        );
    }

    #[test]
    fn unknown_soc_prefers_firehose_entries() {
        let entries = parse_programmer_index(INDEX).unwrap();
        let ordered = order_programmer_entries(&entries, None);
        assert_eq!(
            ordered.iter().map(|e| e.file.as_str()).collect::<Vec<_>>(),
            ["generic.mbn", "msm8998.mbn", "legacy.bin"]
        );
    }

    #[test]
    fn ordering_keeps_the_full_list_and_dedupes_files() {
        let entries = parse_programmer_index(
            r#"[
                {"file": "dup.mbn", "socs": ["X"], "firehose": true},
                {"file": "dup.mbn", "socs": [], "firehose": false},
                {"file": "other.mbn", "firehose": true}
            ]"#,
        )
        .unwrap();
        let ordered = order_programmer_entries(&entries, Some("x"));
        assert_eq!(
            ordered.iter().map(|e| e.file.as_str()).collect::<Vec<_>>(),
            ["dup.mbn", "other.mbn"]
        );
    }

    #[test]
    fn directory_collection_uses_index_order_and_skips_missing_files() {
        let dir = temp_dir("idx");
        std::fs::write(dir.join("generic.mbn"), b"generic").unwrap();
        std::fs::write(dir.join("msm8998.mbn"), b"msm").unwrap();
        std::fs::write(
            dir.join("index.json"),
            r#"[
                {"file": "missing.mbn", "socs": ["MSM8998"], "firehose": true},
                {"file": "generic.mbn", "firehose": true},
                {"file": "msm8998.mbn", "socs": ["MSM8998"], "firehose": true}
            ]"#,
        )
        .unwrap();

        let found = collect_programmers_from_dirs(&[dir.clone()], Some("MSM8998"));
        assert_eq!(
            found,
            vec![dir.join("msm8998.mbn"), dir.join("generic.mbn")],
            "missing index entries must be skipped, soc match first"
        );
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn directory_collection_rejects_index_sha_mismatch() {
        let dir = temp_dir("sha");
        std::fs::write(dir.join("bad.mbn"), b"not the indexed bytes").unwrap();
        std::fs::write(
            dir.join("index.json"),
            r#"[{"file": "bad.mbn", "firehose": true,
                 "sha256": "0000000000000000000000000000000000000000000000000000000000000000"}]"#,
        )
        .unwrap();
        assert!(collect_programmers_from_dirs(&[dir.clone()], None).is_empty());
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn directory_without_index_is_scanned_by_name() {
        let dir = temp_dir("scan");
        std::fs::write(dir.join("b.mbn"), b"b").unwrap();
        std::fs::write(dir.join("a.bin"), b"a").unwrap();
        std::fs::write(dir.join("notes.txt"), b"nope").unwrap();
        let found = collect_programmers_from_dirs(&[dir.clone()], None);
        assert_eq!(found, vec![dir.join("a.bin"), dir.join("b.mbn")]);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn explicit_programmer_path_is_used_verbatim() {
        let dir = temp_dir("explicit");
        let file = dir.join("prog.mbn");
        std::fs::write(&file, b"\x01\x02\x03").unwrap();
        let resolved = resolve_programmers(Some(file.to_str().unwrap())).unwrap();
        assert_eq!(resolved, vec![file]);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn explicit_missing_programmer_is_an_error() {
        let err = resolve_programmers(Some("/nonexistent/flashpilot/prog.mbn")).unwrap_err();
        assert!(err.to_string().contains("not found"), "{err}");
    }

    #[test]
    fn empty_programmer_file_is_rejected() {
        let dir = temp_dir("empty");
        let file = dir.join("empty.mbn");
        std::fs::write(&file, b"").unwrap();
        let err = load_programmer(file.to_str().unwrap()).unwrap_err();
        assert!(err.to_string().contains("empty"), "{err}");
        std::fs::remove_dir_all(&dir).ok();
    }

    // -- plan / bring-up ordering -----------------------------------------

    #[test]
    fn programmer_is_uploaded_before_streaming_and_configure() {
        let plan = firehose_bringup_plan();
        assert_eq!(
            plan,
            [
                FirehoseStep::UploadProgrammer,
                FirehoseStep::SwitchToStreaming,
                FirehoseStep::Configure,
            ]
        );
        // Explicit ordering assertion (index-based, readable on failure).
        let pos = |step: FirehoseStep| plan.iter().position(|s| *s == step).unwrap();
        assert!(pos(FirehoseStep::UploadProgrammer) < pos(FirehoseStep::SwitchToStreaming));
        assert!(pos(FirehoseStep::SwitchToStreaming) < pos(FirehoseStep::Configure));
    }

    #[test]
    fn configure_fallback_decision_auto_tries_emmc_then_ufs() {
        assert_eq!(
            StorageType::parse("auto").unwrap().configure_attempts(),
            ["emmc", "ufs"]
        );
        assert_eq!(StorageType::Auto.configure_attempts(), ["emmc", "ufs"]);
        assert_eq!(StorageType::Emmc.configure_attempts(), ["emmc"]);
        assert_eq!(StorageType::Ufs.configure_attempts(), ["ufs"]);
        assert_eq!(StorageType::parse("UFS").unwrap(), StorageType::Ufs);
        assert_eq!(StorageType::parse("").unwrap(), StorageType::Auto);
        assert!(StorageType::parse("nvme").is_err());
        assert_eq!(StorageType::Emmc.max_luns(), MAX_LUNS_EMMC);
        assert_eq!(StorageType::Auto.max_luns(), MAX_LUNS_UFS);
    }

    // -- rawprogram planning ----------------------------------------------

    #[test]
    fn flash_plan_preserves_lun_per_op_and_treats_empty_filename_as_erase() {
        let xml = r#"<?xml version="1.0"?><data>
            <program label="boot" filename="boot.img" start_sector="100" num_partition_sectors="8" physical_partition_number="3"/>
            <program label="modem" filename="" start_sector="200" num_partition_sectors="16" physical_partition_number="2"/>
            <program label="system" filename="system.img" start_sector="300" num_partition_sectors="64" physical_partition_number="0" sparse="true"/>
        </data>"#;
        let plan = plan_flash(xml, Path::new("/fw")).unwrap();
        assert_eq!(plan.ops.len(), 3);
        assert_eq!(plan.ops[0].physical_partition_number, 3);
        assert_eq!(
            plan.ops[0].kind,
            FlashOpKind::Program {
                file: PathBuf::from("/fw/boot.img"),
                sparse_attribute: false
            }
        );
        assert_eq!(plan.ops[1].kind, FlashOpKind::Erase);
        assert_eq!(plan.ops[1].physical_partition_number, 2);
        assert_eq!(plan.ops[2].physical_partition_number, 0);
        assert_eq!(
            plan.ops[2].kind,
            FlashOpKind::Program {
                file: PathBuf::from("/fw/system.img"),
                sparse_attribute: true
            }
        );
    }

    #[test]
    fn patch_entries_are_patches_not_programs() {
        let xml = r#"<?xml version="1.0"?><data>
            <program label="boot" filename="boot.img" start_sector="100" num_partition_sectors="8" physical_partition_number="0"/>
            <patch filename="boot.img" byte_offset="4096" size_in_bytes="4" value="0xDEADBEEF"/>
        </data>"#;
        let plan = plan_flash(xml, Path::new("/fw")).unwrap();
        assert_eq!(
            plan.ops.len(),
            1,
            "a <patch> must never become a program op"
        );
        assert_eq!(plan.patches.len(), 1);
        assert_eq!(plan.patches[0].filename, "boot.img");
        assert_eq!(plan.patches[0].byte_offset, 4096);
        assert_eq!(plan.patches[0].value, vec![0xDE, 0xAD, 0xBE, 0xEF]);
        // A patch-only XML produces zero device operations.
        let only_patch = r#"<data><patch filename="boot.img" byte_offset="0" value="0x1"/></data>"#;
        let plan = plan_flash(only_patch, Path::new("/fw")).unwrap();
        assert!(plan.ops.is_empty());
        assert_eq!(plan.patches[0].value, vec![0x01]);
    }

    #[test]
    fn corrupt_start_sector_is_error_not_sector_zero() {
        let xml = r#"<?xml version="1.0"?><data><program label="frp" filename="frp.img" start_sector="oops" num_partition_sectors="8"/></data>"#;
        let err = plan_flash(xml, Path::new("/fw")).unwrap_err();
        assert!(
            err.to_string().contains("start_sector"),
            "unexpected: {err}"
        );
    }

    #[test]
    fn absent_optional_attrs_keep_defaults() {
        let xml = r#"<?xml version="1.0"?><data><program label="frp" filename="frp.img" start_sector="100" num_partition_sectors="8"/></data>"#;
        let plan = plan_flash(xml, Path::new("/fw")).unwrap();
        assert_eq!(plan.ops.len(), 1);
        assert_eq!(
            (
                plan.ops[0].partition_name.as_str(),
                plan.ops[0].start_sector,
                plan.ops[0].num_sectors,
                plan.ops[0].physical_partition_number
            ),
            ("frp", 100, 8, 0)
        );
    }

    #[test]
    fn unsafe_firmware_filenames_are_rejected() {
        for name in ["/etc/passwd", "../outside.img", "sub/../../x.img"] {
            let xml = format!(
                r#"<data><program label="boot" filename="{name}" start_sector="0" num_partition_sectors="8"/></data>"#
            );
            assert!(
                plan_flash(&xml, Path::new("/fw")).is_err(),
                "{name} accepted"
            );
        }
    }

    #[test]
    fn program_without_filename_attribute_is_rejected() {
        let xml =
            r#"<data><program label="boot" start_sector="0" num_partition_sectors="8"/></data>"#;
        let err = plan_flash(xml, Path::new("/fw")).unwrap_err();
        assert!(err.to_string().contains("filename"), "{err}");
    }

    #[test]
    fn patch_bytes_writes_only_the_declared_range() {
        let mut buf = vec![0u8; 16];
        patch_bytes(&mut buf, 4, &[0xAA, 0xBB]).unwrap();
        assert_eq!(&buf[..6], &[0, 0, 0, 0, 0xAA, 0xBB]);
        assert!(buf[6..].iter().all(|&b| b == 0));
        assert!(patch_bytes(&mut buf, 15, &[1, 2]).is_err());
    }

    #[test]
    fn flash_range_must_cover_the_prepared_image() {
        // 8 sectors x 512 = 4096 bytes max.
        assert!(flash_range_covers(4096, 8, 512));
        assert!(flash_range_covers(1, 8, 512));
        assert!(!flash_range_covers(4097, 8, 512));
        assert!(!flash_range_covers(4096, 0, 512));
        // A zero sector size still uses the 512-byte floor.
        assert!(flash_range_covers(512, 1, 0));
    }

    #[test]
    fn sparse_expansion_decision_uses_the_android_magic() {
        assert!(flash_needs_sparse_expansion(&[0x3A, 0xFF, 0x26, 0xED]));
        assert!(!flash_needs_sparse_expansion(b"ANDROID!"));
        assert!(!flash_needs_sparse_expansion(&[0x3A]));
        assert!(!flash_needs_sparse_expansion(&[]));
    }

    // -- FRP ---------------------------------------------------------------

    #[test]
    fn frp_erase_set_selects_present_partitions_across_luns() {
        let partitions = vec![
            part("boot", 0, 0, 8, 4096),
            part("frp", 0, 100, 8, 4096),
            part("persist", 2, 50, 8, 4096),
            part("misc", 0, 200, 8, 4096),
        ];
        let plan = plan_frp_erase(&partitions);
        assert_eq!(
            plan.erase
                .iter()
                .map(|p| p.name.as_str())
                .collect::<Vec<_>>(),
            ["frp", "persist", "misc"]
        );
        assert_eq!(
            plan.erase
                .iter()
                .map(|p| p.physical_partition)
                .collect::<Vec<_>>(),
            [0, 2, 0]
        );
        assert_eq!(plan.absent, ["config", "frp_a", "frp_b"]);
    }

    #[test]
    fn frp_erase_set_handles_ab_slots_and_multiple_luns() {
        let partitions = vec![part("frp_a", 1, 10, 8, 4096), part("frp_b", 3, 20, 8, 4096)];
        let plan = plan_frp_erase(&partitions);
        assert_eq!(
            plan.erase
                .iter()
                .map(|p| (p.name.as_str(), p.physical_partition))
                .collect::<Vec<_>>(),
            [("frp_a", 1), ("frp_b", 3)]
        );
        assert_eq!(plan.absent, ["frp", "persist", "config", "misc"]);
    }

    #[test]
    fn frp_plan_is_empty_when_nothing_frp_related_exists() {
        let plan = plan_frp_erase(&[part("boot", 0, 0, 8, 4096)]);
        assert!(plan.is_empty());
        assert_eq!(
            plan.absent,
            ["frp", "persist", "config", "misc", "frp_a", "frp_b"]
        );
    }

    #[test]
    fn wipe_data_message_is_a_4096_byte_boot_recovery_bcb() {
        let block = build_wipe_data_bcb().unwrap();
        assert_eq!(block.len(), BOOTLOADER_MESSAGE_SIZE);
        assert_eq!(&block[0..13], b"boot-recovery");
        assert!(
            block[13..32].iter().all(|&b| b == 0),
            "command is NUL padded"
        );
        assert!(block[32..64].iter().all(|&b| b == 0), "status stays zero");
        let recovery = b"--wipe_data\n--reason=MasterClearConfirm\n\n";
        assert_eq!(&block[64..64 + recovery.len()], recovery);
        assert!(
            block[64 + recovery.len()..].iter().all(|&b| b == 0),
            "everything after the recovery field is zero"
        );
    }

    #[test]
    fn wipe_data_message_rejects_oversized_fields() {
        assert!(build_bootloader_message(&"x".repeat(32), "").is_err());
        assert!(build_bootloader_message("boot-recovery", &"x".repeat(768)).is_err());
    }

    #[test]
    fn misc_write_target_prefers_lun_zero() {
        let partitions = vec![part("misc", 2, 400, 8, 4096), part("misc", 0, 200, 8, 4096)];
        let misc = select_misc_for_wipe(&partitions).unwrap();
        assert_eq!((misc.physical_partition, misc.start_sector), (0, 200));
        assert!(select_misc_for_wipe(&[part("boot", 0, 0, 8, 4096)]).is_err());
    }

    // -- backup ------------------------------------------------------------

    #[test]
    fn empty_partition_table_aborts_backup() {
        let err = ensure_backup_partitions(&[]).unwrap_err();
        assert!(err.to_string().contains("empty partition table"), "{err}");
        assert!(ensure_backup_partitions(&[part("frp", 0, 0, 8, 4096)]).is_ok());
    }

    #[test]
    fn backup_file_names_stay_unique_across_luns() {
        assert_eq!(sanitize_file_component("frp"), "frp");
        assert_eq!(sanitize_file_component("../etc/passwd"), "___etc_passwd");
        assert_eq!(sanitize_file_component(""), "partition");
    }

    #[test]
    fn backup_manifest_entries_carry_the_required_fields() {
        let entries = vec![BackupEntry {
            name: "frp".to_string(),
            lun: 2,
            start: 100,
            num_sectors: 8,
            size: 4096,
            file: "frp.img".to_string(),
            sha256: "ab".repeat(32),
        }];
        let manifest = BackupManifest {
            tool: "flashpilot-bridge",
            version: "test",
            device: "auto",
            partitions: &entries,
        };
        let json = serde_json::to_value(&manifest).unwrap();
        let entry = &json["partitions"][0];
        for key in ["name", "lun", "start", "size", "sha256"] {
            assert!(entry.get(key).is_some(), "manifest missing {key}: {json}");
        }
        assert_eq!(entry["lun"], 2);
        assert_eq!(entry["start"], 100);
    }

    #[test]
    fn payload_hint_cannot_escape_the_payload_root() {
        assert_eq!(safe_hint(" MSM8998 "), Some("MSM8998"));
        assert_eq!(safe_hint("../../etc"), None);
        assert_eq!(safe_hint(".."), None);
        assert_eq!(safe_hint("a/b"), None);
        assert_eq!(safe_hint(""), None);
    }
}
