//! Samsung PIT (Partition Information Table) engine — the single
//! implementation of parse/validate/health/find used for flash gating.
//!
//! Layout (the single true format, cross-verified between Heimdall
//! libpit.h/cpp, Thor's extended parser and real device dumps):
//! header 28B: magic u32@0 (=0x12349876), count u32@4, Unknown[8]@8,
//! Project[8]@16, Reserved u32@24. Entry 132B from offset 28:
//! binType@+0 devType@+4 ident@+8 attr@+12 updAttr@+16 blkOff@+20
//! blkCnt@+24 fileOff@+28 fileSize@+32 name[32]@+36 flash[32]@+68
//! delta[32]@+100. SECTOR_SIZE = 512.
//!
//! Python (`python/core/pit.py`) delegates every raw-bytes decision path
//! (parse/health/find/model/overlaps) to this module through the
//! `pit-parse` / `pit-health` / `pit-find` / `pit-overlaps` commands.
//! In-memory display helpers stay Python-side but operate on entries this
//! engine produced. Shared rules (suffix table, meta sets, messages) are
//! pinned by cross-implementation equivalence tests.

use crate::error::{BridgeError, Result};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

pub const PIT_MAGIC: u32 = 0x1234_9876;
pub const HEADER_SIZE: usize = 28;
pub const ENTRY_SIZE: usize = 132;
pub const SECTOR_SIZE: u64 = 512;
pub const MAX_SANE_ENTRIES: u32 = 512;

const HDR_MAGIC_OFF: usize = 0;
const HDR_COUNT_OFF: usize = 4;
const HDR_UNKNOWN_OFF: usize = 8;
const HDR_PROJECT_OFF: usize = 16;
const HDR_RESERVED_OFF: usize = 24;

const NAME_OFF: usize = 36;
const FLASH_OFF: usize = 68;
const DELTA_OFF: usize = 100;

// Suffixes stripped for partition-name matching (order matters: loop until
// stable, same table as Python `_IMG_SUFFIXES`).
const IMG_SUFFIXES: &[&str] = &[
    ".img", ".bin", ".mbn", ".elf", ".lz4", ".zst", ".zstd", ".ext4", ".raw",
];

fn read_u32_le(data: &[u8], off: usize) -> Result<u32> {
    if off + 4 > data.len() {
        return Err(BridgeError::InvalidArgument("PIT truncated field".to_string()));
    }
    Ok(u32::from_le_bytes([
        data[off],
        data[off + 1],
        data[off + 2],
        data[off + 3],
    ]))
}

/// NUL-terminated ASCII string search from `off`, clamped to off+32 —
/// mirrors Python `_str_at` (global NUL search, not window-limited first).
fn str_at(data: &[u8], off: usize) -> String {
    if off >= data.len() {
        return String::new();
    }
    let mut end = data.len();
    for (i, &b) in data.iter().enumerate().skip(off) {
        if b == 0 {
            end = i;
            break;
        }
    }
    if end > off + 32 {
        end = (off + 32).min(data.len());
    }
    String::from_utf8_lossy(&data[off..end]).to_string()
}

/// Strict printable-ASCII 32-byte field for validation (mirrors
/// `_clean_str_at`).
fn clean_str_at(data: &[u8], off: usize) -> String {
    if off + 32 > data.len() {
        return String::new();
    }
    let raw = &data[off..off + 32];
    let end = raw.iter().position(|&b| b == 0).unwrap_or(32);
    if end == 0 {
        return String::new();
    }
    let text = &raw[..end];
    if text.iter().all(|&b| (0x20..0x7f).contains(&b)) {
        String::from_utf8_lossy(text).to_string()
    } else {
        String::new()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PitEntry {
    pub index: usize,
    pub binary_type: u32,
    pub device_type: u32,
    pub identifier: u32,
    pub attributes: u32,
    pub update_attributes: u32,
    pub block_size: u32,
    pub block_count: u32,
    pub file_offset: u32,
    pub file_size: u32,
    pub name: String,
    pub flash_filename: String,
    pub delta_filename: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PitHeader {
    pub model: String,
    pub unknown: String,
    pub project: String,
    pub reserved: u32,
}

fn parse_one(data: &[u8], index: usize) -> Result<PitEntry> {
    if data.len() < ENTRY_SIZE {
        return Err(BridgeError::InvalidArgument("PIT entry truncated".to_string()));
    }
    let u = |off: usize| read_u32_le(data, off);
    Ok(PitEntry {
        index,
        binary_type: u(0)?,
        device_type: u(4)?,
        identifier: u(8)?,
        attributes: u(12)?,
        update_attributes: u(16)?,
        block_size: u(20)?,
        block_count: u(24)?,
        file_offset: u(28)?,
        file_size: u(32)?,
        name: str_at(data, NAME_OFF),
        flash_filename: str_at(data, FLASH_OFF),
        delta_filename: str_at(data, DELTA_OFF),
    })
}

fn is_flashable_name(name: &str) -> bool {
    let n = name.trim();
    !n.is_empty() && !n.starts_with('.')
}

pub fn parse_header(raw: &[u8]) -> PitHeader {
    if raw.len() < HEADER_SIZE {
        return PitHeader {
            model: String::new(),
            unknown: String::new(),
            project: String::new(),
            reserved: 0,
        };
    }
    let unknown_full = str_at(&raw[..HEADER_SIZE], HDR_UNKNOWN_OFF);
    let project_full = str_at(&raw[..HEADER_SIZE], HDR_PROJECT_OFF);
    let unknown: String = unknown_full.chars().take(8).collect();
    let project: String = project_full.chars().take(8).collect();
    let reserved = read_u32_le(raw, HDR_RESERVED_OFF).unwrap_or(0);
    let model = format!("{unknown}{project}")
        .trim_matches('\0')
        .trim()
        .to_string();
    PitHeader {
        model,
        unknown: unknown.trim_matches('\0').to_string(),
        project: project.trim_matches('\0').to_string(),
        reserved,
    }
}

/// Parse all flashable entries (whitespace/dot-only names filtered, like
/// Odin). Errors mirror Python ValueError texts.
pub fn parse_pit(raw: &[u8]) -> Result<Vec<PitEntry>> {
    if raw.len() < HEADER_SIZE {
        return Err(BridgeError::InvalidArgument("PIT too short".to_string()));
    }
    let magic = read_u32_le(raw, HDR_MAGIC_OFF)?;
    if magic != PIT_MAGIC {
        return Err(BridgeError::InvalidArgument(format!("bad PIT magic: {magic:#x}")));
    }
    let count = read_u32_le(raw, HDR_COUNT_OFF)? as usize;
    let mut out = Vec::new();
    for i in 0..count {
        let off = HEADER_SIZE + i * ENTRY_SIZE;
        if off + ENTRY_SIZE > raw.len() {
            break;
        }
        let e = parse_one(&raw[off..off + ENTRY_SIZE], i)?;
        if is_flashable_name(&e.name) {
            out.push(e);
        }
    }
    Ok(out)
}

pub fn normalize_part_name(name: &str) -> String {
    let mut n = name.trim().to_lowercase();
    loop {
        let mut changed = false;
        for suf in IMG_SUFFIXES {
            if !n.is_empty() && n.ends_with(suf) {
                n.truncate(n.len() - suf.len());
                changed = true;
            }
        }
        if !changed || n.is_empty() {
            break;
        }
    }
    n
}

pub fn is_meta_entry_name(name: &str, identifier: u32) -> bool {
    matches!(
        name.trim().to_lowercase().as_str(),
        "pgpt" | "gpt" | "pit" | "md5hdr"
    ) || matches!(identifier, 70..=72)
}

pub fn find_in(entries: &[PitEntry], name: &str) -> Option<PitEntry> {
    let want = normalize_part_name(name);
    for e in entries {
        if normalize_part_name(&e.name) == want {
            return Some(e.clone());
        }
    }
    for e in entries {
        if !e.flash_filename.is_empty() && normalize_part_name(&e.flash_filename) == want {
            return Some(e.clone());
        }
    }
    None
}

/// Adjacent-pair overlap scan over start-sorted ranges (stable sort, like
/// Python). Returns (name_a, name_b, overlap_blocks), meta containment
/// included — use `significant_overlaps` for corruption.
pub fn find_overlaps(entries: &[PitEntry]) -> Vec<(String, String, u64)> {
    let mut ranges: Vec<(&PitEntry, u64, u64)> = entries
        .iter()
        .filter(|e| e.block_count != 0)
        .map(|e| {
            let s = e.block_size as u64;
            (e, s, s + e.block_count as u64)
        })
        .collect();
    ranges.sort_by_key(|r| r.1);
    let mut out = Vec::new();
    for w in ranges.windows(2) {
        let (pe, _ps, pe_end) = w[0];
        let (ce, s, e) = w[1];
        if s < pe_end {
            out.push((pe.name.clone(), ce.name.clone(), pe_end.min(e) - s));
        }
    }
    out
}

pub fn significant_overlaps(entries: &[PitEntry]) -> Vec<(String, String, u64)> {
    let by_name: HashMap<&str, &PitEntry> = entries.iter().map(|e| (e.name.as_str(), e)).collect();
    let mut out = Vec::new();
    for (a, b, blocks) in find_overlaps(entries) {
        match (by_name.get(a.as_str()), by_name.get(b.as_str())) {
            (Some(ea), Some(eb)) => {
                if !(is_meta_entry_name(&ea.name, ea.identifier)
                    || is_meta_entry_name(&eb.name, eb.identifier))
                {
                    out.push((a, b, blocks));
                }
            }
            _ => out.push((a, b, blocks)),
        }
    }
    out
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Finding {
    pub severity: String,
    pub code: String,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthStats {
    pub declared_count: u32,
    pub parsed_count: usize,
    pub model: String,
    pub style: String,
    pub total_bytes: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Health {
    pub verdict: String,
    pub summary: String,
    pub findings: Vec<Finding>,
    pub stats: HealthStats,
}

/// Python `repr()` for decoded names (single quotes, backslash/n/r/t and
/// \\xNN escapes) — only used inside the INVALID_NAME message so
/// byte-identical verdicts survive unusual dumps.
///
/// Escape rule mirrors CPython `str.isprintable()`: C0 controls + DEL are
/// escaped; U+FFFD (what `errors="replace"` decoding produces, and the only
/// non-ASCII char that can actually occur here) is printable and stays raw.
/// Anything else non-ASCII falls back to \\uXXXX (matches Python for format/
/// private-use/unassigned chars; printable scripts like CJK cannot occur
/// from ascii/replace decoding so the divergence is unreachable).
fn py_repr(s: &str) -> String {
    let use_double = s.contains('\'') && !s.contains('"');
    let mut out = String::new();
    out.push(if use_double { '"' } else { '\'' });
    for c in s.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\'' if !use_double => out.push_str("\\'"),
            '"' if use_double => out.push_str("\\\""),
            c if (c < '\u{20}' || c == '\u{7f}') => {
                out.push_str(&format!("\\x{:02x}", c as u32))
            }
            '\u{fffd}' => out.push('\u{fffd}'),
            c if (c as u32) > 0x7e => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push(if use_double { '"' } else { '\'' });
    out
}

pub fn pit_style_entries(entries: &[PitEntry]) -> String {
    let mut prev: Option<u32> = None;
    for e in entries {
        if e.block_size == 0 && e.block_count == 0 {
            continue;
        }
        if let Some(p) = prev {
            if e.block_size != p {
                return "new".to_string();
            }
        }
        prev = Some(e.block_size);
    }
    "old".to_string()
}

fn verdict_of(findings: &[Finding]) -> String {
    if findings.iter().any(|f| f.severity == "fail") {
        "fail".to_string()
    } else if findings.iter().any(|f| f.severity == "warn") {
        "warn".to_string()
    } else {
        "ok".to_string()
    }
}

pub fn human_size(n: u64) -> String {
    // Mirrors Python human_size: B exact, else one decimal, 1024 steps.
    let mut v = n as f64;
    for unit in ["B", "KB", "MB", "GB", "TB"] {
        if v.abs() < 1024.0 || unit == "TB" {
            if unit == "B" {
                return format!("{n} B");
            }
            return format!("{v:.1} {unit}");
        }
        v /= 1024.0;
    }
    format!("{n} B")
}

pub fn validate_pit(raw: &[u8]) -> Health {
    let mut findings: Vec<Finding> = Vec::new();
    let mut stats = HealthStats {
        declared_count: 0,
        parsed_count: 0,
        model: String::new(),
        style: "unknown".to_string(),
        total_bytes: 0,
    };
    let mut add = |severity: &str, code: &str, message: String| {
        findings.push(Finding {
            severity: severity.to_string(),
            code: code.to_string(),
            message,
        });
    };
    let finish = |findings: Vec<Finding>, stats: HealthStats| Health {
        verdict: verdict_of(&findings),
        summary: String::new(), // filled by health()
        findings,
        stats,
    };
    if raw.len() < HEADER_SIZE {
        add(
            "fail",
            "PIT_TOO_SHORT",
            format!("PIT too small ({} bytes)", raw.len()),
        );
        return finish(findings, stats);
    }
    let magic = read_u32_le(raw, HDR_MAGIC_OFF).unwrap_or(0);
    if magic != PIT_MAGIC {
        add(
            "fail",
            "BAD_MAGIC",
            format!("PIT file identifier mismatch: 0x{magic:08x}"),
        );
        return finish(findings, stats);
    }
    let header = parse_header(raw);
    let declared = read_u32_le(raw, HDR_COUNT_OFF).unwrap_or(0);
    stats.declared_count = declared;
    stats.model = header.model;
    if declared == 0 {
        add("warn", "NO_ENTRIES", "PIT declares zero entries".to_string());
    } else if declared > MAX_SANE_ENTRIES {
        add(
            "fail",
            "COUNT_INSANE",
            format!("Invalid PIT entry count: {declared} (>{MAX_SANE_ENTRIES})"),
        );
    }
    let needed = HEADER_SIZE + declared as usize * ENTRY_SIZE;
    if raw.len() < needed {
        add(
            "fail",
            "TRUNCATED",
            format!(
                "PIT truncated: expected at least {needed} bytes, got {}",
                raw.len()
            ),
        );
    }
    let mut all_entries = Vec::new();
    for i in 0..(declared.min(MAX_SANE_ENTRIES) as usize) {
        let off = HEADER_SIZE + i * ENTRY_SIZE;
        if off + ENTRY_SIZE > raw.len() {
            break;
        }
        match parse_one(&raw[off..off + ENTRY_SIZE], i) {
            Ok(e) => all_entries.push(e),
            Err(e) => {
                add("fail", "PARSE_ERROR", format!("PIT parse error: {e}"));
                return finish(findings, stats);
            }
        }
    }
    stats.parsed_count = all_entries.len();
    let flashable: Vec<&PitEntry> = all_entries
        .iter()
        .filter(|e| is_flashable_name(&e.name))
        .collect();
    let mut seen_ids: HashMap<u32, String> = HashMap::new();
    // Consistency: duplicate partition NAMES (two entries claiming the same
    // name makes a PIT-mapped flash land both images on one partition) and
    // zero-size flashable entries (a flash that would silently write nothing).
    let mut seen_names: HashMap<&str, usize> = HashMap::new();
    let mut zero_size: Vec<String> = Vec::new();
    for e in &flashable {
        match seen_names.get(e.name.as_str()) {
            Some(first) => add(
                "fail",
                "DUPLICATE_NAME",
                format!(
                    "PIT entries {} and {} both claim partition name '{}' - a flash would write both images to one partition",
                    first,
                    e.index,
                    e.name
                ),
            ),
            None => {
                seen_names.insert(e.name.as_str(), e.index);
            }
        }
        if e.block_count == 0 {
            zero_size.push(e.name.clone());
        }
        if e.name.trim().is_empty() {
            add(
                "fail",
                "EMPTY_NAME",
                format!("PIT entry {} has an empty partition name", e.index),
            );
        } else {
            let entry_off = HEADER_SIZE + e.index * ENTRY_SIZE + NAME_OFF;
            if clean_str_at(raw, entry_off) != e.name {
                add(
                    "fail",
                    "INVALID_NAME",
                    format!(
                        "PIT entry {} has an invalid partition name: {}",
                        e.index,
                        py_repr(&e.name)
                    ),
                );
            }
        }
        if e.identifier == 0 {
            add(
                "fail",
                "IDENTIFIER_ZERO",
                format!("PIT entry '{}' has an invalid identifier (0)", e.name),
            );
        }
        if let Some(first) = seen_ids.get(&e.identifier) {
            add(
                "fail",
                "DUPLICATE_IDENTIFIER",
                format!(
                    "PIT contains duplicate partition identifier {}: '{first}' and '{}'",
                    e.identifier, e.name
                ),
            );
        } else {
            seen_ids.insert(e.identifier, e.name.clone());
        }
    }
    let flash_owned: Vec<PitEntry> = flashable.into_iter().cloned().collect();
    if !zero_size.is_empty() {
        add(
            "warn",
            "ZERO_SIZE_FLASHABLE",
            format!(
                "Flashable partition(s) with zero block count: {} - flashing them is a no-op",
                zero_size.join(", ")
            ),
        );
    }
    let sig = significant_overlaps(&flash_owned);
    for (a, b, blocks) in sig.iter().take(8) {
        add(
            "fail",
            "OVERLAP",
            format!(
                "partitions '{a}' and '{b}' overlap by {blocks} blocks ({} bytes) - corrupt or foreign table",
                blocks * SECTOR_SIZE
            ),
        );
    }
    let sig_set: HashSet<(String, String, u64)> =
        sig.iter().cloned().collect();
    let mut meta_pairs = 0;
    for (a, b, blocks) in find_overlaps(&flash_owned) {
        if sig_set.contains(&(a.clone(), b.clone(), blocks)) {
            continue;
        }
        if meta_pairs >= 4 {
            break;
        }
        meta_pairs += 1;
        add(
            "info",
            "META_CONTAINMENT",
            format!(
                "'{b}' is contained in '{a}' ({blocks} blocks) - normal for platform tables"
            ),
        );
    }
    stats.total_bytes = flash_owned
        .iter()
        .map(|e| e.block_count as u64 * SECTOR_SIZE)
        .sum();
    // Style is computed over the flashable set (parse_pit semantics).
    stats.style = pit_style_entries(&flash_owned);
    finish(findings, stats)
}

pub fn health(raw: &[u8]) -> Health {
    let mut h = validate_pit(raw);
    let s = &h.stats;
    h.summary = format!(
        "PIT {}: {}/{} entries, style={}, {} accounted{}",
        h.verdict.to_uppercase(),
        s.parsed_count,
        s.declared_count,
        s.style,
        human_size(s.total_bytes),
        if s.model.is_empty() {
            String::new()
        } else {
            format!(", model={}", s.model)
        }
    );
    h
}

// ---------------------------------------------------------------------------
// CLI entry points (file-path based; PITs are tiny, callers use temp files
// for in-memory dumps).
// ---------------------------------------------------------------------------

fn read_pit_file(path: &str) -> Result<Vec<u8>> {
    std::fs::read(path).map_err(|e| BridgeError::Io(format!("read {path}: {e}")))
}

/// `pit-parse <file>` — header + flashable entries JSON.
pub fn parse_cli(path: &str) -> Result<String> {
    let raw = read_pit_file(path)?;
    let header = parse_header(&raw);
    let entries = parse_pit(&raw)?;
    let style_entries = entries.clone();
    let out = serde_json::json!({
        "model": header.model,
        "unknown": header.unknown,
        "project": header.project,
        "reserved": header.reserved,
        "style": pit_style_entries(&style_entries),
        "entries": entries,
    });
    serde_json::to_string_pretty(&out).map_err(|e| BridgeError::Io(e.to_string()))
}

/// `pit-health <file>` — validate_pit verdict JSON (always exit 0, even for
/// garbage input: a corrupt table is a `fail` verdict, not a transport error).
pub fn health_cli(path: &str) -> Result<String> {
    let raw = read_pit_file(path).unwrap_or_default();
    let h = health(&raw);
    serde_json::to_string_pretty(&h).map_err(|e| BridgeError::Io(e.to_string()))
}

/// `pit-model <file>` — header strings JSON. Never validates magic (mirrors
/// Python `parse_model`, which reads the string area unconditionally);
/// short input yields empty strings. Missing files still error.
pub fn model_cli(path: &str) -> Result<String> {
    let raw = read_pit_file(path)?;
    let h = parse_header(&raw);
    let out = serde_json::json!({
        "model": h.model,
        "unknown": h.unknown,
        "project": h.project,
        "reserved": h.reserved,
    });
    serde_json::to_string(&out).map_err(|e| BridgeError::Io(e.to_string()))
}

/// `pit-find <file> <name>` — one entry JSON or null. A missing name (or an
/// unparseable table) is `null`, never an error; only unreadable files
/// error. Mirrors Python `find_partition`, which returns None instead of
/// raising on invalid input.
pub fn find_cli(path: &str, name: &str) -> Result<String> {
    let raw = read_pit_file(path)?;
    let found = parse_pit(&raw).ok().and_then(|e| find_in(&e, name));
    serde_json::to_string(&found).map_err(|e| BridgeError::Io(e.to_string()))
}

/// `pit-overlaps <file>` — all + significant overlap pairs.
pub fn overlaps_cli(path: &str) -> Result<String> {
    let raw = read_pit_file(path)?;
    let entries = parse_pit(&raw)?;
    let all = find_overlaps(&entries);
    let sig = significant_overlaps(&entries);
    let out = serde_json::json!({"all": all, "significant": sig});
    serde_json::to_string_pretty(&out).map_err(|e| BridgeError::Io(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn entry_bytes(name: &str, ident: u32, start: u32, count: u32) -> Vec<u8> {
        let mut e = vec![0u8; ENTRY_SIZE];
        let w = |b: &mut Vec<u8>, off: usize, v: u32| {
            b[off..off + 4].copy_from_slice(&v.to_le_bytes());
        };
        w(&mut e, 0, 1);
        w(&mut e, 4, 2);
        w(&mut e, 8, ident);
        w(&mut e, 12, 1);
        w(&mut e, 16, 0);
        w(&mut e, 20, start);
        w(&mut e, 24, count);
        e[36..36 + name.len()].copy_from_slice(name.as_bytes());
        e
    }

    fn pit_bytes(specs: &[(&str, u32, u32, u32)]) -> Vec<u8> {
        let mut p = vec![0u8; HEADER_SIZE];
        p[0..4].copy_from_slice(&PIT_MAGIC.to_le_bytes());
        p[4..8].copy_from_slice(&(specs.len() as u32).to_le_bytes());
        p[8..16].copy_from_slice(b"COM_TAR2");
        p[16..24].copy_from_slice(b"MTK6765\x00");
        for (name, ident, start, count) in specs {
            p.extend_from_slice(&entry_bytes(name, *ident, *start, *count));
        }
        p
    }

    #[test]
    fn layout_positions_match_single_true_format() {
        let raw = pit_bytes(&[("boot", 10, 100, 50)]);
        let entries = parse_pit(&raw).unwrap();
        assert_eq!(entries.len(), 1);
        let e = &entries[0];
        assert_eq!((e.binary_type, e.device_type, e.identifier), (1, 2, 10));
        assert_eq!((e.block_size, e.block_count), (100, 50));
        assert_eq!(e.name, "boot");
        assert_eq!(parse_header(&raw).model, "COM_TAR2MTK6765");
    }

    #[test]
    fn bad_magic_and_truncation_rejected_like_python() {
        let mut raw = pit_bytes(&[("boot", 10, 100, 50)]);
        raw[0] ^= 0xff;
        assert!(parse_pit(&raw).unwrap_err().to_string().contains("bad PIT magic"));
        assert!(parse_pit(&[][..]).unwrap_err().to_string().contains("too short"));
    }

    #[test]
    fn normalize_matches_python_table() {
        for (inp, want) in [
            ("Boot.IMG", "boot"),
            (" modem.bin ", "modem"),
            ("vbmeta", "vbmeta"),
            ("radio.img.lz4", "radio"),
            ("system.ext4", "system"),
            ("recovery.zst", "recovery"),
            ("abl.elf", "abl"),
            ("x.mbn", "x"),
            ("persist.raw", "persist"),
            ("cache.zstd", "cache"),
        ] {
            assert_eq!(normalize_part_name(inp), want, "input {inp}");
        }
    }

    #[test]
    fn overlaps_detect_and_classify_meta() {
        // bootloader contains pgpt (meta) -> all-pair only; two data
        // partitions colliding -> significant.
        let raw = pit_bytes(&[
            ("bootloader", 1, 0, 1000),
            ("pgpt", 70, 0, 34),
            ("system", 20, 2000, 500),
            ("vendor", 21, 2200, 500),
        ]);
        let entries = parse_pit(&raw).unwrap();
        let all = find_overlaps(&entries);
        assert!(all.iter().any(|(a, b, _)| a == "bootloader" && b == "pgpt"));
        let sig = significant_overlaps(&entries);
        assert_eq!(sig.len(), 1);
        assert_eq!(&sig[0].0, "system");
        assert_eq!(&sig[0].1, "vendor");
        assert_eq!(sig[0].2, 300);
        // Health flags the corruption, keeps meta containment as info.
        let h = health(&raw);
        assert_eq!(h.verdict, "fail");
        assert!(h.findings.iter().any(|f| f.code == "OVERLAP"));
        assert!(h.findings.iter().any(|f| f.code == "META_CONTAINMENT"));
    }

    #[test]
    fn health_summary_shape_matches_python() {
        let raw = pit_bytes(&[("boot", 10, 100, 50)]);
        let h = health(&raw);
        assert!(h.summary.starts_with("PIT OK: 1/1 entries, style="));
        assert!(h.summary.contains("model=COM_TAR2MTK6765"));
        assert!(h.summary.contains("accounted"));
    }

    #[test]
    fn human_size_matches_python_buckets() {
        assert_eq!(human_size(0), "0 B");
        assert_eq!(human_size(512), "512 B");
        assert_eq!(human_size(1023), "1023 B");
        assert_eq!(human_size(1024), "1.0 KB");
        assert_eq!(human_size(1536), "1.5 KB");
        assert_eq!(human_size(1024 * 1024), "1.0 MB");
    }

    #[test]
    fn find_prefers_name_then_flash_file() {
        let mut raw = pit_bytes(&[("boot", 10, 100, 50)]);
        // flash filename on the entry
        let off = HEADER_SIZE + FLASH_OFF;
        raw[off..off + 8].copy_from_slice(b"boot.img");
        let entries = parse_pit(&raw).unwrap();
        assert_eq!(find_in(&entries, "BOOT").unwrap().identifier, 10);
        assert_eq!(find_in(&entries, "boot.img").unwrap().identifier, 10);
        assert!(find_in(&entries, "nope").is_none());
    }

    #[test]
    fn py_repr_covers_junk_names() {
        assert_eq!(py_repr("boot"), "'boot'");
        assert_eq!(py_repr("a'b"), "\"a'b\"");
        assert_eq!(py_repr("a\nb"), "'a\\nb'");
        assert_eq!(py_repr("a\x01b"), "'a\\x01b'");
        // U+FFFD is printable per CPython str.isprintable: stays raw.
        assert_eq!(py_repr("\u{fffd}\u{fffd}AB"), "'\u{fffd}\u{fffd}AB'");
    }
    /// Consistency: duplicate partition names are a FAIL (a PIT-mapped flash
    /// would write two images onto one partition).
    #[test]
    fn duplicate_partition_names_fail() {
        let mut pit = vec![0u8; 28];
        pit[0..4].copy_from_slice(&super::PIT_MAGIC.to_le_bytes());
        pit[4..8].copy_from_slice(&2u32.to_le_bytes());
        for i in 0..2 {
            let mut e = vec![0u8; super::ENTRY_SIZE];
            e[0..4].copy_from_slice(&1u32.to_le_bytes());
            e[8..12].copy_from_slice(&(i as u32).to_le_bytes());
            e[20..24].copy_from_slice(&512u32.to_le_bytes());
            e[24..28].copy_from_slice(&8u32.to_le_bytes());
            e[36..36 + 4].copy_from_slice(b"boot");
            pit.extend_from_slice(&e);
        }
        let h = health(&pit);
        assert!(h.findings.iter().any(|f| f.code == "DUPLICATE_NAME"), "{:?}", h.findings.iter().map(|f| f.code.clone()).collect::<Vec<_>>());
    }

    /// Consistency: zero-size flashable entries are a WARN (flashing them
    /// would silently write nothing).
    #[test]
    fn zero_size_flashable_warns() {
        let mut pit = vec![0u8; 28];
        pit[0..4].copy_from_slice(&super::PIT_MAGIC.to_le_bytes());
        pit[4..8].copy_from_slice(&1u32.to_le_bytes());
        let mut e = vec![0u8; super::ENTRY_SIZE];
        e[0..4].copy_from_slice(&1u32.to_le_bytes());
        e[8..12].copy_from_slice(&0u32.to_le_bytes());
        e[20..24].copy_from_slice(&512u32.to_le_bytes());
        e[24..28].copy_from_slice(&0u32.to_le_bytes());
        e[36..36 + 4].copy_from_slice(b"boot");
        pit.extend_from_slice(&e);
        let h = health(&pit);
        assert!(h.findings.iter().any(|f| f.code == "ZERO_SIZE_FLASHABLE"));
    }

}
