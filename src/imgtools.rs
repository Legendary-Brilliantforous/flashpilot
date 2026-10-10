//! Android boot image + AVB vbmeta byte surgery — the single implementation
//! (Python `python/core/spd_adb.py` and `core._patch_vbmeta_flags` delegate
//! here).
//!
//! Boot images (v0–v3 header: magic `ANDROID!`, kernel_size@8,
//! ramdisk_size@24, page_size@36): parse the header, locate the ramdisk
//! (`page_size + align(kernel_size)`), gunzip it (multi-member tolerant),
//! scan cpio newc entries for prop files, set the ADB-enable keys, and
//! repack — padding in place with newlines when the text fits, growing the
//! cpio entry (magiskboot-style header rewrite + splice) when it does not.
//! The header size field is updated on growth; everything else is preserved.
//!
//! Fidelity notes vs the Python implementation:
//! * cpio scan/predicate/advance rules, `%08X` filesize fields, NUL pads,
//!   prop-text rewriting and all log lines are ported verbatim (per-key
//!   detail goes to stderr, which the bridge forwards live to the GUI).
//! * gzip output is deterministic (mtime=0, level 9) but NOT byte-identical
//!   to Python's zlib across implementations — equivalence is defined over
//!   decompressed bytes, sizes and header fields, never raw gz bytes.
//! * CRLF prop files: segments are split on `\n` with trailing `\r`
//!   stripped, matching `splitlines()` for real-world files.
//! * v3+/GKI (`vendor_boot`) layouts are out of scope on both sides.

use crate::error::{BridgeError, Result};
use serde::{Deserialize, Serialize};
use std::io::{Read, Write};

pub const BOOT_MAGIC: &[u8; 8] = b"ANDROID!";
const KERNEL_SIZE_OFF: usize = 8;
const RAMDISK_SIZE_OFF: usize = 24;
const PAGE_SIZE_OFF: usize = 36;
const HEADER_MIN: usize = 40;

// Props forced inside ramdisk prop files (insertion order = append order).
const ADB_PROPS: &[(&str, &str)] = &[
    ("ro.adb.secure", "0"),
    ("ro.debuggable", "1"),
    ("ro.secure", "0"),
    ("persist.sys.usb.config", "mtp,adb"),
    ("sys.usb.configfs", "1"),
];
const PROP_MARKER: &str = "# added by FlashPilot (adb enable)";

fn read_u32_le(data: &[u8], off: usize) -> Result<u32> {
    if off + 4 > data.len() {
        return Err(BridgeError::InvalidArgument(
            "boot image truncated field".to_string(),
        ));
    }
    Ok(u32::from_le_bytes([
        data[off],
        data[off + 1],
        data[off + 2],
        data[off + 3],
    ]))
}

fn parse_boot_header(img: &[u8]) -> Result<(u32, u32, u32)> {
    if img.len() < HEADER_MIN || &img[..8] != BOOT_MAGIC {
        return Err(BridgeError::InvalidArgument(
            "not a boot image (missing ANDROID! magic)".to_string(),
        ));
    }
    let kernel_size = read_u32_le(img, KERNEL_SIZE_OFF)?;
    let ramdisk_size = read_u32_le(img, RAMDISK_SIZE_OFF)?;
    let page_size = read_u32_le(img, PAGE_SIZE_OFF)?;
    if page_size == 0 {
        return Err(BridgeError::InvalidArgument("invalid page size 0".to_string()));
    }
    Ok((kernel_size, ramdisk_size, page_size))
}

fn page_align(n: u64, page: u64) -> u64 {
    n.div_ceil(page) * page
}

fn is_hex_ascii(b: &[u8]) -> bool {
    !b.is_empty() && b.iter().all(|c| c.is_ascii_hexdigit())
}

fn ascii_name(raw: &[u8]) -> String {
    raw.iter()
        .take_while(|&&b| b != 0)
        .filter(|&&b| b < 0x80)
        .map(|&b| b as char)
        .collect()
}

/// cpio newc scan yielding (entry_offset, name, data_start, filesize).
/// Mirrors the Python scan exactly: 110-byte ASCII-hex headers, namesize @
/// [94:102], filesize @ [54:62], 4-byte alignment, idx+=6 on rejects.
fn scan_cpio(raw: &[u8]) -> Vec<(usize, String, usize, usize)> {
    let mut out = Vec::new();
    let mut idx = 0usize;
    while idx + 6 <= raw.len() {
        let rel = raw[idx..].windows(b"070701".len()).position(|w| w == b"070701");
        let at = match rel {
            Some(r) => idx + r,
            None => break,
        };
        idx = at;
        if at + 110 > raw.len() || !is_hex_ascii(&raw[at..at + 110]) {
            idx += 6;
            continue;
        }
        let parse_hex = |s: &[u8]| -> Option<usize> {
            std::str::from_utf8(s)
                .ok()
                .and_then(|t| usize::from_str_radix(t.trim(), 16).ok())
        };
        let (namesize, filesize) = match (
            parse_hex(&raw[at + 94..at + 102]),
            parse_hex(&raw[at + 54..at + 62]),
        ) {
            (Some(n), Some(f)) => (n, f),
            _ => {
                idx += 6;
                continue;
            }
        };
        let name_start = at + 110;
        if name_start > raw.len() {
            idx += 6;
            continue;
        }
        let name_end = name_start.saturating_add(namesize.saturating_sub(1)).min(raw.len());
        let name = ascii_name(&raw[name_start..name_end]);
        let mut data_start = name_start + namesize;
        data_start = (data_start + 3) & !3;
        out.push((at, name, data_start, filesize));
        // Advance past data (callers that splice recompute; see below).
        let next = data_start.saturating_add((filesize + 3) & !3);
        idx = if next > at { next } else { at + 6 };
    }
    out
}

fn is_prop_target(name: &str) -> bool {
    name.ends_with("default.prop")
        || name.ends_with("build.prop")
        || matches!(name, "default.prop" | "prop.default" | "build.prop")
}

/// Rewrite one prop file's text, forcing ADB_PROPS. Returns (new_text,
/// per-key log lines). Mirrors `_patch_prop_text` verbatim.
fn patch_prop_text(text: &str, name: &str) -> (String, Vec<String>) {
    let mut logs = Vec::new();
    let mut seen = std::collections::HashSet::new();
    let mut out: Vec<String> = Vec::new();
    // Mirror Python splitlines(): a final newline terminates the last line,
    // it does not add an empty one (otherwise every re-patch grows by \n).
    let mut segs: Vec<&str> = text.split('\n').collect();
    if text.ends_with('\n') {
        segs.pop();
    }
    for seg in segs {
        let ln = seg.strip_suffix('\r').unwrap_or(seg);
        let stripped = ln.trim();
        let mut matched: Option<(&str, &str)> = None;
        if !stripped.is_empty() && !stripped.starts_with('#') {
            if let Some((k, _)) = stripped.split_once('=') {
                let kk = k.trim();
                matched = ADB_PROPS.iter().find(|(ak, _)| *ak == kk).copied();
            }
        }
        if let Some((ak, av)) = matched {
            seen.insert(ak.to_string());
            let old_v = stripped.split_once('=').map(|(_, v)| v.trim()).unwrap_or("");
            if old_v != av {
                logs.push(format!("      {ak}: {old_v} -> {av}"));
            }
            out.push(format!("{ak}={av}"));
        } else {
            out.push(ln.to_string());
        }
    }
    let missing: Vec<(&str, &str)> = ADB_PROPS
        .iter()
        .filter(|(k, _)| !seen.contains(*k))
        .copied()
        .collect();
    if !missing.is_empty() {
        out.push(String::new());
        out.push(PROP_MARKER.to_string());
        for (k, v) in &missing {
            out.push(format!("{k}={v}"));
            logs.push(format!("      {k}: (absent) -> {v}"));
        }
    }
    let _ = name;
    (out.join("\n") + "\n", logs)
}

fn gunzip_maybe(blob: &[u8]) -> (Vec<u8>, bool) {
    use flate2::read::MultiGzDecoder;
    let mut dec = MultiGzDecoder::new(blob);
    let mut raw = Vec::new();
    match dec.read_to_end(&mut raw) {
        Ok(_) if !raw.is_empty() => (raw, true),
        _ => (blob.to_vec(), false),
    }
}

fn gzip_mtime0(data: &[u8]) -> Result<Vec<u8>> {
    use flate2::Compression;
    let mut enc = flate2::GzBuilder::new()
        .mtime(0)
        .write(Vec::new(), Compression::best());
    enc.write_all(data)
        .map_err(|e| BridgeError::Io(format!("gzip: {e}")))?;
    enc.finish()
        .map_err(|e| BridgeError::Io(format!("gzip finish: {e}")))
}

/// Patch prop files inside a (possibly gzipped) ramdisk blob. Returns
/// (new_blob, patched_names). Errors when nothing matched.
fn patch_ramdisk(ramdisk: &[u8]) -> Result<(Vec<u8>, Vec<String>)> {
    let (raw, was_gz) = gunzip_maybe(ramdisk);
    let mut buf = raw;
    let mut patched_names: Vec<String> = Vec::new();
    let mut idx = 0usize;
    loop {
        let rel = buf[idx..]
            .windows(b"070701".len())
            .position(|w| w == b"070701");
        let at = match rel {
            Some(r) => idx + r,
            None => break,
        };
        idx = at;
        if at + 110 > buf.len() || !is_hex_ascii(&buf[at..at + 110]) {
            idx += 6;
            continue;
        }
        let parse_hex = |s: &[u8]| -> Option<usize> {
            std::str::from_utf8(s)
                .ok()
                .and_then(|t| usize::from_str_radix(t.trim(), 16).ok())
        };
        let (namesize, filesize) = match (
            parse_hex(&buf[at + 94..at + 102]),
            parse_hex(&buf[at + 54..at + 62]),
        ) {
            (Some(n), Some(f)) => (n, f),
            _ => {
                idx += 6;
                continue;
            }
        };
        let name_start = at + 110;
        if name_start > buf.len() {
            idx += 6;
            continue;
        }
        let name_end = name_start
            .saturating_add(namesize.saturating_sub(1))
            .min(buf.len());
        let name = ascii_name(&buf[name_start..name_end]);
        let mut data_start = name_start.saturating_add(namesize);
        data_start = data_start.saturating_add(3) & !3;
        if !is_prop_target(&name) {
            idx = data_start.saturating_add((filesize + 3) & !3).max(at + 6);
            continue;
        }
        let data_end = data_start.saturating_add(filesize).min(buf.len());
        // Clamp like Python slicing (never panic on corrupt entries). Note:
        // on valid inputs content.len() == filesize, so padding matches
        // Python exactly; on truncated inputs we pad to available bytes
        // instead of splicing in extra ones.
        let content_len = data_end.saturating_sub(data_start);
        let nb: Vec<u8> = {
            let content = &buf[data_start..data_start + content_len];
            let text = String::from_utf8_lossy(content);
            let (new_text, mut logs) = patch_prop_text(&text, &name);
            for l in logs.drain(..) {
                eprintln!("{l}");
            }
            new_text.into_bytes()
        };
        if nb.len() <= content_len {
            // Pad in place with newlines (offsets after us never move).
            let mut filled = nb;
            filled.extend(std::iter::repeat_n(b'\n', content_len - filled.len()));
            buf[data_start..data_start + content_len].copy_from_slice(&filled);
            patched_names.push(name.clone());
            eprintln!("    patched {name} ({filesize}B)");
            idx = data_start + ((filesize + 3) & !3);
            continue;
        }
        // Grow: rewrite this entry's header (new filesize, %08X) and splice.
        // Data position uses the SAME absolute alignment as the reader
        // (align_up(name_start + namesize)); padding the name length
        // alone would disagree with the scan by (110 % 4) bytes.
        if nb.len() > u32::MAX as usize {
            return Err(BridgeError::InvalidArgument(
                "patched prop file exceeds 4GB".to_string(),
            ));
        }
        let growth = ((nb.len() + 3) & !3) - ((filesize + 3) & !3);
        let mut fields = buf[at..at + 110].to_vec();
        let fs = format!("{:08X}", nb.len());
        fields[54..62].copy_from_slice(fs.as_bytes());
        let data_pos = (110 + namesize + 3) & !3;
        let pad1_len = data_pos - 110 - namesize;
        let pad2_len = (4 - (nb.len() % 4)) % 4;
        let mut new_entry = fields;
        let name_avail = buf.len().saturating_sub(name_start).min(namesize);
        new_entry.extend_from_slice(&buf[name_start..name_start + name_avail]);
        new_entry.extend(std::iter::repeat_n(0u8, pad1_len + namesize - name_avail));
        new_entry.extend_from_slice(&nb);
        new_entry.extend(std::iter::repeat_n(0u8, pad2_len));
        let old_entry_len = data_pos + ((filesize + 3) & !3);
        let splice_end = (at + old_entry_len).min(buf.len());
        buf.splice(at..splice_end, new_entry.iter().cloned());
        patched_names.push(name.clone());
        eprintln!(
            "    patched+grew {name} ({filesize} -> {}B, +{growth})",
            nb.len()
        );
        idx = at + new_entry.len();
    }
    if patched_names.is_empty() {
        return Err(BridgeError::InvalidArgument(
            "no prop file found/patched in ramdisk".to_string(),
        ));
    }
    let out = if was_gz { gzip_mtime0(&buf)? } else { buf };
    Ok((out, patched_names))
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BootPatchSummary {
    pub kernel_size: u32,
    pub ramdisk_size: u32,
    pub page_size: u32,
    pub ramdisk_offset: u64,
    pub ramdisk_old: usize,
    pub ramdisk_new: usize,
    pub grew_by: i64,
    pub patched_files: Vec<String>,
    pub recompressed: bool,
}

/// `boot-patch-adb <in.img> <out.img>` — patch ramdisk props for ADB.
pub fn boot_patch_adb_cli(in_path: &str, out_path: &str) -> Result<String> {
    let img = std::fs::read(in_path).map_err(|e| BridgeError::Io(format!("read {in_path}: {e}")))?;
    let (kernel_size, ramdisk_size, page_size) = parse_boot_header(&img)?;
    let rd_off = page_size as u64 + page_align(kernel_size as u64, page_size as u64);
    let rd_end = rd_off
        .checked_add(ramdisk_size as u64)
        .ok_or_else(|| BridgeError::InvalidArgument("ramdisk range overflow".to_string()))?;
    if rd_end > img.len() as u64 {
        return Err(BridgeError::InvalidArgument(
            "ramdisk extends beyond image".to_string(),
        ));
    }
    let ramdisk = &img[rd_off as usize..rd_end as usize];
    let was_gz = {
        let (raw, gz) = gunzip_maybe(ramdisk);
        let _ = raw;
        gz
    };
    let (new_rd, patched_files) = patch_ramdisk(ramdisk)?;
    let grew_by = new_rd.len() as i64 - ramdisk_size as i64;
    let mut out_img = img;
    if new_rd.len() as u64 > ramdisk_size as u64 {
        // Grow: splice tail after the ramdisk and fix the header size.
        let tail = out_img[rd_end as usize..].to_vec();
        out_img.truncate(rd_off as usize);
        out_img.extend_from_slice(&new_rd);
        out_img.extend_from_slice(&tail);
        let n = new_rd.len() as u32;
        out_img[RAMDISK_SIZE_OFF..RAMDISK_SIZE_OFF + 4].copy_from_slice(&n.to_le_bytes());
    } else {
        let mut padded = new_rd.clone();
        padded.resize(ramdisk_size as usize, 0);
        out_img[rd_off as usize..rd_end as usize].copy_from_slice(&padded);
    }
    std::fs::write(out_path, &out_img).map_err(|e| BridgeError::Io(format!("write {out_path}: {e}")))?;
    let summary = BootPatchSummary {
        kernel_size,
        ramdisk_size,
        page_size,
        ramdisk_offset: rd_off,
        ramdisk_old: ramdisk_size as usize,
        ramdisk_new: new_rd.len(),
        grew_by,
        patched_files,
        recompressed: was_gz,
    };
    serde_json::to_string_pretty(&summary).map_err(|e| BridgeError::Io(e.to_string()))
}

/// `boot-info <img>` — header sizes + prop file list JSON.
pub fn boot_info_cli(path: &str) -> Result<String> {
    let img = std::fs::read(path).map_err(|e| BridgeError::Io(format!("read {path}: {e}")))?;
    let (kernel_size, ramdisk_size, page_size) = parse_boot_header(&img)?;
    let rd_off = page_size as u64 + page_align(kernel_size as u64, page_size as u64);
    let rd_end = rd_off.saturating_add(ramdisk_size as u64).min(img.len() as u64);
    let prop_files = if rd_end > rd_off {
        let (raw, _) = gunzip_maybe(&img[rd_off as usize..rd_end as usize]);
        scan_cpio(&raw)
            .into_iter()
            .filter(|(_, name, _, _)| is_prop_target(name))
            .map(|(_, name, _, _)| name)
            .collect()
    } else {
        Vec::new()
    };
    let out = serde_json::json!({
        "kernel_size": kernel_size,
        "ramdisk_size": ramdisk_size,
        "page_size": page_size,
        "ramdisk_offset": rd_off,
        "prop_files": prop_files,
    });
    serde_json::to_string_pretty(&out).map_err(|e| BridgeError::Io(e.to_string()))
}

// ---------------------------------------------------------------------------
// AVB vbmeta flags.
// ---------------------------------------------------------------------------

pub const AVB_MAGIC: &[u8; 4] = b"AVB0";
pub const AVB_FLAGS_OFF: usize = 80;
pub const AVB_MIN: usize = 96;

/// `vbmeta-patch <in> <out> [flags]` — set AVB flags (default 0x03:
/// HASHTREE_DISABLED | VERIFICATION_DISABLED). Exit 0 + {"patched": true}
/// on success; exit 0 + {"patched": false} when the input is not an AVB
/// image (mirrors Python returning None instead of raising).
pub fn vbmeta_patch_cli(in_path: &str, out_path: &str, flags: u32) -> Result<String> {
    let data = std::fs::read(in_path).map_err(|e| BridgeError::Io(format!("read {in_path}: {e}")))?;
    if data.len() < AVB_MIN || &data[..4] != AVB_MAGIC || data.len() < AVB_FLAGS_OFF + 4 {
        let out = serde_json::json!({"patched": false, "size": data.len()});
        return serde_json::to_string(&out).map_err(|e| BridgeError::Io(e.to_string()));
    }
    let mut patched = data;
    patched[AVB_FLAGS_OFF..AVB_FLAGS_OFF + 4].copy_from_slice(&flags.to_le_bytes());
    std::fs::write(out_path, &patched).map_err(|e| BridgeError::Io(format!("write {out_path}: {e}")))?;
    let out = serde_json::json!({"patched": true, "size": patched.len(), "flags": flags});
    serde_json::to_string(&out).map_err(|e| BridgeError::Io(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cpio_entry(name: &str, data: &[u8]) -> Vec<u8> {
        // newc 110-byte ASCII-hex header.
        let mut hdr = vec![b'0'; 110];
        hdr[0..6].copy_from_slice(b"070701");
        let finfo = format!("{:08X}", data.len());
        hdr[54..62].copy_from_slice(finfo.as_bytes());
        let ns = format!("{:08X}", name.len() + 1);
        hdr[94..102].copy_from_slice(ns.as_bytes());
        let mut e = hdr;
        e.extend_from_slice(name.as_bytes());
        e.push(0);
        while e.len() % 4 != 0 {
            e.push(0);
        }
        e.extend_from_slice(data);
        while e.len() % 4 != 0 {
            e.push(0);
        }
        e
    }

    fn gzip_bytes(data: &[u8]) -> Vec<u8> {
        use flate2::Compression;
        let mut enc = flate2::GzBuilder::new()
            .mtime(0)
            .write(Vec::new(), Compression::best());
        enc.write_all(data).unwrap();
        enc.finish().unwrap()
    }

    fn boot_img(prop_text: &str, gzipped: bool) -> Vec<u8> {
        let page = 2048u32;
        let kernel = vec![0xAAu8; 100];
        let mut rd_raw = Vec::new();
        rd_raw.extend_from_slice(&cpio_entry("default.prop", prop_text.as_bytes()));
        rd_raw.extend_from_slice(&cpio_entry("first_stage_ramdisk/fstab", b"ro xxx\n"));
        let rd_blob = if gzipped { gzip_bytes(&rd_raw) } else { rd_raw };
        let mut img = vec![0u8; page as usize];
        img[..8].copy_from_slice(BOOT_MAGIC);
        img[8..12].copy_from_slice(&(kernel.len() as u32).to_le_bytes());
        img[24..28].copy_from_slice(&(rd_blob.len() as u32).to_le_bytes());
        img[36..40].copy_from_slice(&page.to_le_bytes());
        let mut aligned_kernel = kernel.clone();
        while aligned_kernel.len() % page as usize != 0 {
            aligned_kernel.push(0);
        }
        img.extend_from_slice(&aligned_kernel);
        img.extend_from_slice(&rd_blob);
        img
    }

    #[test]
    fn prop_patch_sets_keys_and_appends_missing() {
        let img = boot_img("ro.adb.secure=1\nro.debuggable=0\n", true);
        let dir = std::env::temp_dir().join(format!("fp_img_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let inp = dir.join("boot.img");
        let outp = dir.join("boot_adb.img");
        std::fs::write(&inp, &img).unwrap();
        let summary: BootPatchSummary =
            serde_json::from_str(&boot_patch_adb_cli(inp.to_str().unwrap(), outp.to_str().unwrap()).unwrap())
                .unwrap();
        assert_eq!(summary.patched_files, vec!["default.prop".to_string()]);
        assert!(summary.recompressed);
        // Patched content visible after gunzip.
        let patched = std::fs::read(&outp).unwrap();
        let rd_off = summary.ramdisk_offset as usize;
        let new_size = u32::from_le_bytes(patched[24..28].try_into().unwrap()) as usize;
        let (raw, was_gz) = gunzip_maybe(&patched[rd_off..rd_off + new_size]);
        assert!(was_gz);
        let text = String::from_utf8_lossy(&raw);
        assert!(text.contains("ro.adb.secure=0"));
        assert!(text.contains("ro.debuggable=1"));
        assert!(text.contains("persist.sys.usb.config=mtp,adb"));
        assert!(text.contains("# added by FlashPilot (adb enable)"));
        // Idempotent: patching twice does not grow the image.
        let out2 = dir.join("boot_adb2.img");
        let s2: BootPatchSummary = serde_json::from_str(
            &boot_patch_adb_cli(outp.to_str().unwrap(), out2.to_str().unwrap()).unwrap(),
        )
        .unwrap();
        assert_eq!(s2.grew_by, 0);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn growth_updates_header_and_stays_parseable() {
        // Slot exactly full: existing content + missing keys must grow.
        let filler = "x".repeat(200);
        let img = boot_img(&format!("ro.adb.secure=1\n#filler {filler}\n"), false);
        let dir = std::env::temp_dir().join(format!("fp_grow_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let inp = dir.join("b.img");
        let outp = dir.join("b2.img");
        std::fs::write(&inp, &img).unwrap();
        let s: BootPatchSummary =
            serde_json::from_str(&boot_patch_adb_cli(inp.to_str().unwrap(), outp.to_str().unwrap()).unwrap())
                .unwrap();
        assert!(s.grew_by > 0, "expected growth, got {}", s.grew_by);
        assert!(!s.recompressed);
        // Header size field tracks the new ramdisk.
        let patched = std::fs::read(&outp).unwrap();
        assert_eq!(
            u32::from_le_bytes(patched[24..28].try_into().unwrap()) as usize,
            s.ramdisk_new
        );
        // Patched image re-parses: values present.
        let (raw, _) = gunzip_maybe(&patched[s.ramdisk_offset as usize..][..s.ramdisk_new]);
        let text = String::from_utf8_lossy(&raw);
        assert!(text.contains("ro.adb.secure=0"));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn no_prop_files_is_a_clean_error() {
        let mut rd_raw = Vec::new();
        rd_raw.extend_from_slice(&cpio_entry("first_stage_ramdisk/fstab", b"ro xxx\n"));
        let img = {
            let page = 2048u32;
            let mut img = vec![0u8; page as usize];
            img[..8].copy_from_slice(BOOT_MAGIC);
            img[8..12].copy_from_slice(&100u32.to_le_bytes());
            img[24..28].copy_from_slice(&(rd_raw.len() as u32).to_le_bytes());
            img[36..40].copy_from_slice(&page.to_le_bytes());
            let mut k = vec![0xAAu8; 100];
            while k.len() % page as usize != 0 {
                k.push(0);
            }
            img.extend_from_slice(&k);
            img.extend_from_slice(&rd_raw);
            img
        };
        let dir = std::env::temp_dir().join(format!("fp_noprop_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let inp = dir.join("b.img");
        let outp = dir.join("b2.img");
        std::fs::write(&inp, &img).unwrap();
        let err = boot_patch_adb_cli(inp.to_str().unwrap(), outp.to_str().unwrap()).unwrap_err();
        assert!(err.to_string().contains("no prop file found/patched"));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn bad_magic_short_and_zero_page_rejected() {
        let dir = std::env::temp_dir().join(format!("fp_bad_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let inp = dir.join("b.img");
        let outp = dir.join("b2.img");
        std::fs::write(&inp, b"NOPE").unwrap();
        assert!(boot_patch_adb_cli(inp.to_str().unwrap(), outp.to_str().unwrap())
            .unwrap_err()
            .to_string()
            .contains("ANDROID"));
        // Zero page size is a clean error, not a divide-by-zero.
        let mut z = vec![0u8; 64];
        z[..8].copy_from_slice(BOOT_MAGIC);
        std::fs::write(&inp, &z).unwrap();
        assert!(boot_patch_adb_cli(inp.to_str().unwrap(), outp.to_str().unwrap())
            .unwrap_err()
            .to_string()
            .contains("page size"));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn gzip_header_is_deterministic_mtime0() {
        let gz = gzip_mtime0(b"hello hello hello hello").unwrap();
        assert_eq!(&gz[..3], &[0x1f, 0x8b, 0x08]);
        assert_eq!(&gz[4..8], &[0, 0, 0, 0], "mtime must be 0");
    }

    #[test]
    fn vbmeta_patch_sets_flags_and_refuses_junk() {
        let dir = std::env::temp_dir().join(format!("fp_vb_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let inp = dir.join("vbmeta.img");
        let outp = dir.join("vbmeta2.img");
        let mut vb = vec![0u8; 128];
        vb[..4].copy_from_slice(b"AVB0");
        vb[80..84].copy_from_slice(&0u32.to_le_bytes());
        std::fs::write(&inp, &vb).unwrap();
        let r: serde_json::Value =
            serde_json::from_str(&vbmeta_patch_cli(inp.to_str().unwrap(), outp.to_str().unwrap(), 0x03).unwrap())
                .unwrap();
        assert_eq!(r["patched"], true);
        let back = std::fs::read(&outp).unwrap();
        assert_eq!(u32::from_le_bytes(back[80..84].try_into().unwrap()), 0x03);
        std::fs::write(&inp, b"junkjunkjunk").unwrap();
        let r2: serde_json::Value =
            serde_json::from_str(&vbmeta_patch_cli(inp.to_str().unwrap(), outp.to_str().unwrap(), 0x03).unwrap())
                .unwrap();
        assert_eq!(r2["patched"], false);
        let _ = std::fs::remove_dir_all(&dir);
    }
}
