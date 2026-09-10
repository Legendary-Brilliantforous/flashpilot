//! SPD/UNISOC PAC container engine — the single implementation of
//! parse/extract/pack (Python `python/core/pac.py` delegates here).
//!
//! Layout (YGDP, reverse-engineered from public parsers):
//! header 2124B: magic u32@0 (=0xD3), version u16@4 (=1), hdrlen u16@6
//! (=2116), "MCT_DOWNLOAD_HEADER"@8, product utf16le@0x20 (64B),
//! count u32@0x60, flash-size u32@0x848.
//! entries: one 2560B slot per file: name[512] utf16le@0, size u32@0x30C,
//! is_nv u32@0x310, checksum u16@0x318 (=0x5433). Then concatenated
//! payloads, then a 3076-byte zero footer.
//!
//! Notes on fidelity:
//! * Entry names decode utf16le with lone surrogates DROPPED (Python
//!   `errors="ignore"`), cut at the first NUL, whitespace-stripped.
//! * The slot-name writer caps at 510 bytes and may split a surrogate pair
//!   exactly like the Python writer (byte truncation, not char truncation).
//! * `spd-readback` (spd.rs) historically writes doubled slot names
//!   (`{name}_{name}.img`); that quirk is preserved verbatim in the
//!   readback path via the `slot_name` parameter — pack-from-folder uses
//!   plain basenames, matching real YGDP tools.

use crate::error::{BridgeError, Result};
use serde::{Deserialize, Serialize};
use std::io::{Read, Seek, Write};

pub const PAC_HEADER_SIZE: usize = 2124;
pub const PAC_ENTRY_SIZE: usize = 2560;
pub const PAC_FOOTER_SIZE: usize = 3076;
pub const PAC_MAGIC: u32 = 0xD3;
pub const PAC_COUNT_OFF: usize = 0x60;
pub const PAC_FLASH_SIZE_OFF: usize = 0x848;
pub const PAC_ENTRY_SIZE_OFF: usize = 0x30C;
pub const PAC_ENTRY_IS_NV_OFF: usize = 0x310;
pub const PAC_ENTRY_CHECKSUM_OFF: usize = 0x318;
pub const PAC_ENTRY_CHECKSUM: u16 = 0x5433;
pub const PAC_PRODUCT_OFF: usize = 0x20;
pub const PAC_PRODUCT_LEN: usize = 64;

fn read_u32_le(data: &[u8], off: usize) -> Result<u32> {
    if off + 4 > data.len() {
        return Err(BridgeError::InvalidArgument("PAC truncated field".to_string()));
    }
    Ok(u32::from_le_bytes([
        data[off],
        data[off + 1],
        data[off + 2],
        data[off + 3],
    ]))
}

fn read_u16_le(data: &[u8], off: usize) -> Result<u16> {
    if off + 2 > data.len() {
        return Err(BridgeError::InvalidArgument("PAC truncated field".to_string()));
    }
    Ok(u16::from_le_bytes([data[off], data[off + 1]]))
}

/// Decode a 512-byte utf16le name field: drop lone surrogates (Python
/// `errors="ignore"`), cut at first NUL, strip whitespace.
pub(crate) fn decode_name(buf: &[u8]) -> String {
    let units: Vec<u16> = buf
        .chunks_exact(2)
        .map(|c| u16::from_le_bytes([c[0], c[1]]))
        .collect();
    let text: String = char::decode_utf16(units)
        .filter_map(|r| r.ok())
        .collect();
    text.split('\0').next().unwrap_or("").trim().to_string()
}

/// Encode a name into a fixed region, truncating to `max_bytes - 2` BYTES
/// (may split a surrogate pair — byte-identical to the Python writer).
fn encode_name_capped(buf: &mut [u8], s: &str, max_bytes: usize) {
    let mut bytes = Vec::new();
    for unit in s.encode_utf16() {
        bytes.extend_from_slice(&unit.to_le_bytes());
    }
    let n = bytes.len().min(max_bytes.saturating_sub(2));
    let n = n.min(buf.len());
    buf[..n].copy_from_slice(&bytes[..n]);
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PacEntry {
    pub index: usize,
    pub name: String,
    pub size: u32,
    pub is_nv: bool,
    pub checksum: u16,
    pub data_offset: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PacInfo {
    pub path: String,
    pub count: u32,
    pub flash_size: u32,
    pub entries: Vec<PacEntry>,
    pub total_payload: u64,
}

fn parse_header(buf: &[u8]) -> Result<(u32, u32)> {
    if buf.len() < PAC_HEADER_SIZE {
        return Err(BridgeError::InvalidArgument(format!(
            "PAC too short: {} < {}",
            buf.len(),
            PAC_HEADER_SIZE
        )));
    }
    let magic = read_u32_le(buf, 0)?;
    if magic != PAC_MAGIC {
        return Err(BridgeError::InvalidArgument(format!(
            "Bad PAC magic 0x{magic:x} expected 0x{:x}",
            PAC_MAGIC
        )));
    }
    let count = read_u32_le(buf, PAC_COUNT_OFF)?;
    if count == 0 || count > 500 {
        return Err(BridgeError::InvalidArgument(format!(
            "Suspicious PAC count {count}"
        )));
    }
    let flash_size = read_u32_le(buf, PAC_FLASH_SIZE_OFF)?;
    Ok((count, flash_size))
}

/// Parse header + entry table. `data_len` bounds entry reads (file size).
fn parse_entries(buf: &[u8], data_len: u64) -> Result<Vec<PacEntry>> {
    let (count, _flash) = parse_header(buf)?;
    let mut entries = Vec::new();
    let mut data_offset = (PAC_HEADER_SIZE + count as usize * PAC_ENTRY_SIZE) as u64;
    for i in 0..count as usize {
        let off = PAC_HEADER_SIZE + i * PAC_ENTRY_SIZE;
        if off + PAC_ENTRY_SIZE > buf.len().min(data_len as usize) {
            return Err(BridgeError::InvalidArgument(format!(
                "Truncated PAC entry {i}"
            )));
        }
        let slot = &buf[off..off + PAC_ENTRY_SIZE];
        let raw_name = decode_name(&slot[0..512]);
        let name = if raw_name.is_empty() {
            format!("part_{i}")
        } else {
            raw_name
        };
        let size = read_u32_le(slot, PAC_ENTRY_SIZE_OFF)?;
        let is_nv = read_u32_le(slot, PAC_ENTRY_IS_NV_OFF)? != 0;
        let chk = read_u16_le(slot, PAC_ENTRY_CHECKSUM_OFF)?;
        entries.push(PacEntry {
            index: i,
            name,
            size,
            is_nv,
            checksum: chk,
            data_offset,
        });
        data_offset += size as u64;
    }
    Ok(entries)
}

pub fn parse_pac(path: &str) -> Result<PacInfo> {
    let buf = std::fs::read(path).map_err(|e| BridgeError::Io(format!("read {path}: {e}")))?;
    let (count, flash_size) = parse_header(&buf)?;
    let entries = parse_entries(&buf, buf.len() as u64)?;
    let total_payload: u64 = entries.iter().map(|e| e.size as u64).sum();
    Ok(PacInfo {
        path: path.to_string(),
        count,
        flash_size,
        entries,
        total_payload,
    })
}

/// Shared 2124-byte header builder (readback + pack emit identical bytes).
pub(crate) fn build_header(count: u32, total_bytes: u64, product: &str) -> Result<Vec<u8>> {
    if total_bytes > u32::MAX as u64 {
        return Err(BridgeError::InvalidArgument(format!(
            "PAC payload too large: {total_bytes} bytes exceeds u32 flash-size"
        )));
    }
    let mut hdr = vec![0u8; PAC_HEADER_SIZE];
    hdr[0..4].copy_from_slice(&PAC_MAGIC.to_le_bytes());
    hdr[4..6].copy_from_slice(&1u16.to_le_bytes());
    hdr[6..8].copy_from_slice(&2116u16.to_le_bytes());
    let mct = b"MCT_DOWNLOAD_HEADER";
    hdr[8..8 + mct.len()].copy_from_slice(mct);
    if !product.is_empty() {
        encode_name_capped(
            &mut hdr[PAC_PRODUCT_OFF..PAC_PRODUCT_OFF + PAC_PRODUCT_LEN],
            product,
            PAC_PRODUCT_LEN,
        );
    }
    hdr[PAC_COUNT_OFF..PAC_COUNT_OFF + 4].copy_from_slice(&count.to_le_bytes());
    hdr[PAC_FLASH_SIZE_OFF..PAC_FLASH_SIZE_OFF + 4]
        .copy_from_slice(&(total_bytes as u32).to_le_bytes());
    Ok(hdr)
}

/// Shared 2560-byte entry-slot builder.
pub(crate) fn build_slot(name: &str, size: u32, is_nv: bool) -> Vec<u8> {
    let mut slot = vec![0u8; PAC_ENTRY_SIZE];
    encode_name_capped(&mut slot[..512], name, 512);
    slot[PAC_ENTRY_SIZE_OFF..PAC_ENTRY_SIZE_OFF + 4].copy_from_slice(&size.to_le_bytes());
    slot[PAC_ENTRY_IS_NV_OFF..PAC_ENTRY_IS_NV_OFF + 4]
        .copy_from_slice(&(is_nv as u32).to_le_bytes());
    slot[PAC_ENTRY_CHECKSUM_OFF..PAC_ENTRY_CHECKSUM_OFF + 2]
        .copy_from_slice(&PAC_ENTRY_CHECKSUM.to_le_bytes());
    slot
}

fn check_u32(name: &str, size: u64) -> Result<u32> {
    if size > u32::MAX as u64 {
        return Err(BridgeError::InvalidArgument(format!(
            "file too large for PAC: {name} ({size} bytes exceeds u32)"
        )));
    }
    Ok(size as u32)
}

/// Sanitize an entry name for extraction (mirrors Python: separators to
/// underscore, strip, `part_{index}` fallback; dir collision gets .img).
fn sanitize_extract(name: &str, index: usize, out_dir: &std::path::Path) -> std::path::PathBuf {
    let mut safe = name.replace(['/', '\\'], "_").trim().to_string();
    if safe.is_empty() {
        safe = format!("part_{index}");
    }
    let mut path = out_dir.join(&safe);
    if path.is_dir() {
        path.set_extension("img");
        if path.file_name().is_none() {
            path = out_dir.join(format!("part_{index}.img"));
        }
    }
    path
}

fn read_up_to(f: &mut std::fs::File, mut len: u64) -> Result<Vec<u8>> {
    // Tolerate short reads (sparse footers): return what the file has.
    let mut out = Vec::new();
    let mut buf = [0u8; 1 << 20];
    while len > 0 {
        let want = (len as usize).min(buf.len());
        let n = f.read(&mut buf[..want]).map_err(|e| BridgeError::Io(e.to_string()))?;
        if n == 0 {
            break;
        }
        out.extend_from_slice(&buf[..n]);
        len -= n as u64;
    }
    Ok(out)
}

/// `pac-extract <file> <out_dir>` — write payloads, return written paths.
pub fn extract_cli(pac_path: &str, out_dir: &str) -> Result<String> {
    let info = parse_pac(pac_path)?;
    std::fs::create_dir_all(out_dir).map_err(|e| BridgeError::Io(e.to_string()))?;
    let out_path = std::path::Path::new(out_dir);
    let mut f = std::fs::File::open(pac_path).map_err(|e| BridgeError::Io(e.to_string()))?;
    let mut written = Vec::new();
    for e in &info.entries {
        if e.size == 0 {
            continue;
        }
        let dest = sanitize_extract(&e.name, e.index, out_path);
        f.seek(std::io::SeekFrom::Start(e.data_offset))
            .map_err(|e| BridgeError::Io(e.to_string()))?;
        let data = read_up_to(&mut f, e.size as u64)?;
        std::fs::write(&dest, &data).map_err(|e| BridgeError::Io(e.to_string()))?;
        written.push(dest.to_string_lossy().to_string());
    }
    serde_json::to_string(&written).map_err(|e| BridgeError::Io(e.to_string()))
}

/// `pac-pack <in_dir> <out_pac> [product]` — pack sorted regular files.
pub fn pack_cli(in_dir: &str, out_pac: &str, product: &str) -> Result<String> {
    let mut files: Vec<std::path::PathBuf> = std::fs::read_dir(in_dir)
        .map_err(|e| BridgeError::Io(format!("read {in_dir}: {e}")))?
        .filter_map(|e| e.ok().map(|x| x.path()))
        .filter(|p| p.is_file())
        .collect();
    files.sort();
    if files.is_empty() {
        return Err(BridgeError::InvalidArgument(format!("No files in {in_dir}")));
    }
    let mut entries: Vec<(String, u64)> = Vec::new();
    let mut total: u64 = 0;
    for p in &files {
        let name = p
            .file_name()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_default();
        let size = p
            .metadata()
            .map_err(|e| BridgeError::Io(e.to_string()))?
            .len();
        check_u32(&name, size)?;
        entries.push((name, size));
        total += size;
    }
    if total > u32::MAX as u64 {
        return Err(BridgeError::InvalidArgument(format!(
            "PAC payload too large: {total} bytes exceeds u32 flash-size"
        )));
    }
    let mut out = std::fs::File::create(out_pac).map_err(|e| BridgeError::Io(e.to_string()))?;
    out.write_all(&build_header(entries.len() as u32, total, product)?)
        .map_err(|e| BridgeError::Io(e.to_string()))?;
    for (name, size) in &entries {
        out.write_all(&build_slot(name, *size as u32, false))
            .map_err(|e| BridgeError::Io(e.to_string()))?;
    }
    for p in &files {
        let mut f =
            std::fs::File::open(p).map_err(|e| BridgeError::Io(e.to_string()))?;
        std::io::copy(&mut f, &mut out).map_err(|e| BridgeError::Io(e.to_string()))?;
    }
    out.write_all(&vec![0u8; PAC_FOOTER_SIZE])
        .map_err(|e| BridgeError::Io(e.to_string()))?;
    Ok(out_pac.to_string())
}

/// `pac-parse <file>` — header + entry table JSON.
pub fn parse_cli(path: &str) -> Result<String> {
    let info = parse_pac(path)?;
    serde_json::to_string_pretty(&info).map_err(|e| BridgeError::Io(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn synthetic_pac(names: &[(&str, u32)]) -> Vec<u8> {
        // Build via the shared writers (what pack_cli emits).
        let total: u64 = names.iter().map(|(_, s)| *s as u64).sum();
        let mut buf = build_header(names.len() as u32, total, "TestProduct").unwrap();
        for (name, size) in names {
            buf.extend_from_slice(&build_slot(name, *size, false));
        }
        for (_, size) in names {
            buf.extend(std::iter::repeat(0xAB).take(*size as usize));
        }
        buf.extend(vec![0u8; PAC_FOOTER_SIZE]);
        buf
    }

    #[test]
    fn header_and_entries_parse() {
        let buf = synthetic_pac(&[("boot.img", 16), ("system.img", 32)]);
        let dir = std::env::temp_dir().join(format!("fp_pac_test_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("t.pac");
        std::fs::write(&path, &buf).unwrap();
        let info = parse_pac(path.to_str().unwrap()).unwrap();
        assert_eq!(info.count, 2);
        assert_eq!(info.total_payload, 48);
        assert_eq!(info.entries[0].name, "boot.img");
        assert_eq!(info.entries[0].size, 16);
        assert_eq!(info.entries[1].data_offset as usize, PAC_HEADER_SIZE + 2 * PAC_ENTRY_SIZE + 16);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn bad_magic_short_and_count_rejected_like_python() {
        let dir = std::env::temp_dir().join(format!("fp_pac_err_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let w = |n: &str, b: &[u8]| {
            let p = dir.join(n);
            std::fs::write(&p, b).unwrap();
            p
        };
        let short = w("short.pac", &[0u8; 100]);
        assert!(parse_pac(short.to_str().unwrap())
            .unwrap_err()
            .to_string()
            .contains("PAC too short"));
        let mut bad = synthetic_pac(&[("a", 1)]);
        bad[0] = 0x00;
        let badp = w("bad.pac", &bad);
        assert!(parse_pac(badp.to_str().unwrap())
            .unwrap_err()
            .to_string()
            .contains("Bad PAC magic"));
        // count = 0 and count > 500 rejected
        let mut zc = synthetic_pac(&[("a", 1)]);
        zc[PAC_COUNT_OFF..PAC_COUNT_OFF + 4].copy_from_slice(&0u32.to_le_bytes());
        let zcp = w("zero.pac", &zc);
        assert!(parse_pac(zcp.to_str().unwrap())
            .unwrap_err()
            .to_string()
            .contains("Suspicious PAC count"));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn utf16_names_drop_lone_surrogates_like_python() {
        // Lone surrogate must be dropped (errors="ignore"), not replaced.
        let mut slot = vec![0u8; 512];
        slot[0..2].copy_from_slice(&0x0041u16.to_le_bytes()); // 'A'
        slot[2..4].copy_from_slice(&0xD800u16.to_le_bytes()); // lone high
        slot[4..6].copy_from_slice(&0x0042u16.to_le_bytes()); // 'B'
        assert_eq!(decode_name(&slot), "AB");
        assert_eq!(decode_name(&[0u8; 512]), "");
    }

    #[test]
    fn writer_caps_match_python_truncation() {
        // 510-byte cap (max_bytes - 2). UTF-16LE: 'x' is [0x78, 0x00], so
        // the tail straddles a unit boundary — byte-exact by construction.
        let mut buf = vec![0u8; 512];
        encode_name_capped(&mut buf, &"x".repeat(1000), 512);
        assert_eq!(buf[506..512], [b'x', 0, b'x', 0, 0, 0]);
        let mut hdr = vec![0u8; PAC_PRODUCT_LEN];
        encode_name_capped(&mut hdr, &"y".repeat(100), PAC_PRODUCT_LEN);
        assert_eq!(hdr[60..64], [b'y', 0, 0, 0]);
    }

    #[test]
    fn sanitize_extract_parity() {
        let dir = std::env::temp_dir();
        let p = sanitize_extract("a/b\\c", 3, &dir);
        assert!(p.ends_with("a_b_c"));
        let p2 = sanitize_extract("   ", 7, &dir);
        assert!(p2.ends_with("part_7"));
    }
}
