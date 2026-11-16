//! SPD/UNISOC PAC container engine — the single implementation of
//! parse/extract/pack (Python `python/core/pac.py` delegates here).
//!
//! Layout (YGDP, reverse-engineered from public parsers):
//! header 2124B: magic u32@0 (=0xD3), version u16@4 (=1), hdrlen u16@6
//! (=2116), "MCT_DOWNLOAD_HEADER"@8, product utf16le@0x20 (64B),
//! count u32@0x60, flash-size u32@0x848.
//! entries: one 2560B slot per file: name[512] utf16le@0, size u32@0x30C,
//! is_nv u32@0x310, checksum u16@0x318 (additive byte sum; legacy packers
//! write the 0x5433 sentinel, which is still accepted on read). Then
//! concatenated payloads, then a 3076-byte zero footer.
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
/// Legacy sentinel written by older SPD/YGDP packers at `0x318`. It is not a
/// data checksum; readers must keep accepting it for compatibility.
pub const PAC_ENTRY_LEGACY_CHECKSUM: u16 = 0x5433;
pub const PAC_PRODUCT_OFF: usize = 0x20;
pub const PAC_PRODUCT_LEN: usize = 64;

fn read_u32_le(data: &[u8], off: usize) -> Result<u32> {
    if off + 4 > data.len() {
        return Err(BridgeError::InvalidArgument(
            "PAC truncated field".to_string(),
        ));
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
        return Err(BridgeError::InvalidArgument(
            "PAC truncated field".to_string(),
        ));
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
    let text: String = char::decode_utf16(units).filter_map(|r| r.ok()).collect();
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

/// Per-entry payload checksum: additive 16-bit sum of every byte in the
/// image (mod 2^16). This is the value `pack` writes and `extract` verifies.
pub fn entry_checksum(data: &[u8]) -> u16 {
    data.iter().fold(0u16, |acc, &b| acc.wrapping_add(b as u16))
}

pub(crate) fn checksum_file(path: &std::path::Path) -> Result<u16> {
    let mut f = std::fs::File::open(path).map_err(|e| BridgeError::Io(e.to_string()))?;
    let mut buf = vec![0u8; 1 << 20];
    let mut sum = 0u16;
    loop {
        let n = f
            .read(&mut buf)
            .map_err(|e| BridgeError::Io(e.to_string()))?;
        if n == 0 {
            break;
        }
        sum = buf[..n]
            .iter()
            .fold(sum, |acc, &b| acc.wrapping_add(b as u16));
    }
    Ok(sum)
}

/// Payload kinds that decide what `spd-flash-pac` does with a PAC entry.
///
/// `Flash` is the only kind that is written to the device. Everything else is
/// metadata (loaders / partition XML / NV calibration) and must be skipped —
/// never flashed as if it were a partition.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PacEntryKind {
    /// Zero-size slot: an operation marker or a truncated payload.
    Empty,
    Fdl1,
    Fdl2,
    /// Partition-layout / configuration metadata (`*.xml`).
    Xml,
    /// NV / IMEI / RF-calibration payload (must never be flashed implicitly).
    Nv,
    /// A real partition image.
    Partition,
}

/// Lower-case basename of a PAC entry (entries may carry a Windows path).
fn entry_basename_lower(name: &str) -> String {
    name.rsplit(['/', '\\'])
        .next()
        .unwrap_or(name)
        .trim()
        .to_ascii_lowercase()
}

/// FDL1 loader spellings seen in PACs: `fdl1-sign.bin`, `fdl1.bin`,
/// `fdl1-dl.bin`, and the legacy vendor FILE_T id `FDLA`. FDL2 mirrors it
/// (`fdl2*`, `FDLB`).
fn is_fdl1_name(name: &str) -> bool {
    let n = entry_basename_lower(name);
    n.starts_with("fdl1") || n.starts_with("fdla")
}

fn is_fdl2_name(name: &str) -> bool {
    let n = entry_basename_lower(name);
    n.starts_with("fdl2") || n.starts_with("fdlb")
}

/// Classify one PAC entry for the one-file pipeline. Order matters: a
/// zero-size entry is a marker even if its name says `fdl1`, and NV beats a
/// `.bin` partition image (an NV payload must never be written implicitly).
pub fn classify_pac_entry(entry: &PacEntry) -> PacEntryKind {
    if entry.size == 0 {
        return PacEntryKind::Empty;
    }
    if is_fdl1_name(&entry.name) {
        return PacEntryKind::Fdl1;
    }
    if is_fdl2_name(&entry.name) {
        return PacEntryKind::Fdl2;
    }
    let base = entry_basename_lower(&entry.name);
    if base.ends_with(".xml") || base == "xml" {
        return PacEntryKind::Xml;
    }
    if entry.is_nv || is_nv_name(&entry.name) {
        return PacEntryKind::Nv;
    }
    PacEntryKind::Partition
}

/// Device partition name for a PAC payload: PAC entries are image file names
/// (`boot.img`, `system.bin`), the FDL2 table is keyed by partition
/// (`boot`, `system`). Only well-known image extensions are stripped; any
/// other name is kept verbatim (existing spd-flash naming rule).
pub fn entry_partition_name(name: &str) -> String {
    let base = name.rsplit(['/', '\\']).next().unwrap_or(name).trim();
    let lower = base.to_ascii_lowercase();
    for ext in [".img", ".bin", ".image", ".mbn"] {
        if lower.ends_with(ext) {
            return base[..base.len() - ext.len()].to_string();
        }
    }
    base.to_string()
}

/// Locate the FDL1 and FDL2 payloads in a parsed PAC.
///
/// Matching is case-insensitive on the basename (`FDL1-SIGN.BIN` works) and
/// covers the known PAC spellings (`fdl1*`/`fdla*`, `fdl2*`/`fdlb*`). When a
/// loader is missing the error lists every entry name in the PAC and documents
/// the `--fdl1-addr` / `--fdl2-addr` address overrides (plus the explicit
/// `spd-*` commands that take extracted FDL files).
pub fn find_fdl_entries(info: &PacInfo) -> Result<(PacEntry, PacEntry)> {
    let fdl1 = info.entries.iter().find(|e| is_fdl1_name(&e.name));
    let fdl2 = info.entries.iter().find(|e| is_fdl2_name(&e.name));
    let (fdl1, fdl2) = match (fdl1, fdl2) {
        (Some(a), Some(b)) => (a, b),
        (a, b) => {
            let missing = match (a.is_some(), b.is_some()) {
                (false, false) => "FDL1 and FDL2",
                (false, true) => "FDL1",
                (true, false) => "FDL2",
                (true, true) => unreachable!(),
            };
            let names: Vec<&str> = info.entries.iter().map(|e| e.name.as_str()).collect();
            return Err(BridgeError::InvalidArgument(format!(
                "PAC '{}' has no {missing} loader entry (expected a name starting with \
                 'fdl1'/'fdla' and 'fdl2'/'fdlb', case-insensitive, e.g. fdl1-sign.bin \
                 and fdl2-sign.bin).\nEntries in this PAC: {}\n\
                 If the loaders are not in the PAC, use the explicit spd-flash/spd-frp \
                 commands with the extracted FDL files. FDL load addresses can be \
                 overridden with --fdl1-addr 0x... / --fdl2-addr 0x... (needed when \
                 the chip has no entry in the built-in chip->address table).",
                info.path,
                if names.is_empty() {
                    "(none)".to_string()
                } else {
                    names.join(", ")
                }
            )));
        }
    };
    for (which, e) in [("FDL1", fdl1), ("FDL2", fdl2)] {
        if e.size == 0 {
            return Err(BridgeError::InvalidArgument(format!(
                "PAC entry '{}' is the {which} loader but carries 0 bytes; the PAC is \
                 truncated or uses an operation marker instead of a loader",
                e.name
            )));
        }
    }
    Ok((fdl1.clone(), fdl2.clone()))
}

/// Read one entry's payload, enforcing the declared size and the PAC checksum
/// (the legacy 0x5433 sentinel is accepted). The one-file pipeline reads FDLs
/// and images straight from the archive, so this is the single checked reader.
pub fn read_entry_data(pac_path: &str, entry: &PacEntry) -> Result<Vec<u8>> {
    use std::io::SeekFrom;
    let mut f = std::fs::File::open(pac_path)
        .map_err(|e| BridgeError::Io(format!("read {pac_path}: {e}")))?;
    f.seek(SeekFrom::Start(entry.data_offset))
        .map_err(|e| BridgeError::Io(e.to_string()))?;
    let data = read_up_to(&mut f, entry.size as u64)?;
    if data.len() != entry.size as usize {
        return Err(BridgeError::InvalidArgument(format!(
            "PAC entry '{}' truncated: expected {} bytes, found {}",
            entry.name,
            entry.size,
            data.len()
        )));
    }
    let actual = entry_checksum(&data);
    if entry.checksum != actual && entry.checksum != PAC_ENTRY_LEGACY_CHECKSUM {
        return Err(BridgeError::InvalidArgument(format!(
            "PAC entry '{}' checksum mismatch: stored 0x{:04x}, computed 0x{:04x}",
            entry.name, entry.checksum, actual
        )));
    }
    Ok(data)
}

/// Derive the PAC NV flag from an image/partition name. NV payloads are the
/// RF calibration / IMEI images (`nv`, `nvdata`, `nvitem`, `nvram`, ...).
pub(crate) fn is_nv_name(name: &str) -> bool {
    name.to_ascii_lowercase()
        .split(|c: char| !c.is_ascii_alphanumeric())
        .any(|token| token == "nv" || token.starts_with("nv"))
}

/// Reject names that cannot be represented in the fixed 512-byte UTF-16LE
/// slot (the writer caps at 510 bytes, so a longer name would be silently
/// truncated into a different partition name).
pub(crate) fn check_entry_name(name: &str) -> Result<()> {
    if name.trim().is_empty() {
        return Err(BridgeError::InvalidArgument(
            "PAC entry name is empty".to_string(),
        ));
    }
    let bytes = name.encode_utf16().count() * 2;
    if bytes > 512 - 2 {
        return Err(BridgeError::InvalidArgument(format!(
            "PAC entry name too long: '{name}' needs {bytes} UTF-16LE bytes (max 510)"
        )));
    }
    Ok(())
}

/// Shared 2560-byte entry-slot builder.
pub(crate) fn build_slot(name: &str, size: u32, is_nv: bool, checksum: u16) -> Vec<u8> {
    let mut slot = vec![0u8; PAC_ENTRY_SIZE];
    encode_name_capped(&mut slot[..512], name, 512);
    slot[PAC_ENTRY_SIZE_OFF..PAC_ENTRY_SIZE_OFF + 4].copy_from_slice(&size.to_le_bytes());
    slot[PAC_ENTRY_IS_NV_OFF..PAC_ENTRY_IS_NV_OFF + 4]
        .copy_from_slice(&(is_nv as u32).to_le_bytes());
    slot[PAC_ENTRY_CHECKSUM_OFF..PAC_ENTRY_CHECKSUM_OFF + 2]
        .copy_from_slice(&checksum.to_le_bytes());
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
    let mut buf = vec![0u8; 1 << 20];
    while len > 0 {
        let want = (len as usize).min(buf.len());
        let n = f
            .read(&mut buf[..want])
            .map_err(|e| BridgeError::Io(e.to_string()))?;
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
        if data.len() != e.size as usize {
            return Err(BridgeError::InvalidArgument(format!(
                "PAC entry '{}' truncated: expected {} bytes, found {}",
                e.name,
                e.size,
                data.len()
            )));
        }
        let actual = entry_checksum(&data);
        if e.checksum != actual && e.checksum != PAC_ENTRY_LEGACY_CHECKSUM {
            return Err(BridgeError::InvalidArgument(format!(
                "PAC entry '{}' checksum mismatch: stored 0x{:04x}, computed 0x{:04x}",
                e.name, e.checksum, actual
            )));
        }
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
        return Err(BridgeError::InvalidArgument(format!(
            "No files in {in_dir}"
        )));
    }
    if files.len() > 500 {
        return Err(BridgeError::InvalidArgument(format!(
            "Too many files for a PAC: {} (max 500)",
            files.len()
        )));
    }
    let mut entries: Vec<(String, u64, u16, bool)> = Vec::new();
    let mut total: u64 = 0;
    for p in &files {
        let name = p
            .file_name()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_default();
        check_entry_name(&name)?;
        let size = p
            .metadata()
            .map_err(|e| BridgeError::Io(e.to_string()))?
            .len();
        check_u32(&name, size)?;
        let checksum = checksum_file(p)?;
        let is_nv = is_nv_name(&name);
        entries.push((name, size, checksum, is_nv));
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
    for (name, size, checksum, is_nv) in &entries {
        out.write_all(&build_slot(name, *size as u32, *is_nv, *checksum))
            .map_err(|e| BridgeError::Io(e.to_string()))?;
    }
    for p in &files {
        let mut f = std::fs::File::open(p).map_err(|e| BridgeError::Io(e.to_string()))?;
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
            let data = vec![0xABu8; *size as usize];
            buf.extend_from_slice(&build_slot(name, *size, false, entry_checksum(&data)));
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
        assert_eq!(
            info.entries[1].data_offset as usize,
            PAC_HEADER_SIZE + 2 * PAC_ENTRY_SIZE + 16
        );
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

    #[test]
    fn checksum_is_additive_payload_sum() {
        assert_eq!(entry_checksum(&[]), 0);
        assert_eq!(entry_checksum(&[1, 2, 3]), 6);
        assert_eq!(entry_checksum(&[0xff, 0x02]), 0x0101);
    }

    #[test]
    fn nv_flag_is_derived_from_name() {
        assert!(is_nv_name("nv.bin"));
        assert!(is_nv_name("nvdata.img"));
        assert!(is_nv_name("modem_nv.img"));
        assert!(is_nv_name("NVITEM.bin"));
        assert!(!is_nv_name("boot.img"));
        assert!(!is_nv_name("inventory.img"));
    }

    #[test]
    fn oversized_entry_name_is_rejected() {
        assert!(check_entry_name("boot.img").is_ok());
        let err = check_entry_name(&"x".repeat(256)).unwrap_err();
        assert!(err.to_string().contains("too long"), "{err}");
        assert!(check_entry_name("   ").is_err());
    }

    #[test]
    fn pack_extract_roundtrip_verifies_checksum_and_nv() {
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root = std::env::temp_dir().join(format!("fp_pac_rt_{}_{stamp}", std::process::id()));
        let in_dir = root.join("in");
        let out_dir = root.join("out");
        std::fs::create_dir_all(&in_dir).unwrap();
        let boot = b"BOOT-IMAGE-DATA".to_vec();
        let nv = vec![0x11u8; 64];
        std::fs::write(in_dir.join("boot.img"), &boot).unwrap();
        std::fs::write(in_dir.join("nvdata.bin"), &nv).unwrap();
        let pac = root.join("out.pac");
        pack_cli(
            in_dir.to_str().unwrap(),
            pac.to_str().unwrap(),
            "TestProduct",
        )
        .unwrap();

        let info = parse_pac(pac.to_str().unwrap()).unwrap();
        assert_eq!(info.count, 2);
        let boot_entry = info.entries.iter().find(|e| e.name == "boot.img").unwrap();
        let nv_entry = info
            .entries
            .iter()
            .find(|e| e.name == "nvdata.bin")
            .unwrap();
        assert_eq!(boot_entry.checksum, entry_checksum(&boot));
        assert_eq!(nv_entry.checksum, entry_checksum(&nv));
        assert!(!boot_entry.is_nv);
        assert!(nv_entry.is_nv);

        extract_cli(pac.to_str().unwrap(), out_dir.to_str().unwrap()).unwrap();
        assert_eq!(std::fs::read(out_dir.join("boot.img")).unwrap(), boot);
        assert_eq!(std::fs::read(out_dir.join("nvdata.bin")).unwrap(), nv);
        let _ = std::fs::remove_dir_all(&root);
    }

    // ---- one-file PAC pipeline: loader discovery + entry classification ----

    fn entry(index: usize, name: &str, size: u32, is_nv: bool) -> PacEntry {
        PacEntry {
            index,
            name: name.to_string(),
            size,
            is_nv,
            checksum: 0,
            data_offset: 0,
        }
    }

    fn info_with(names: &[(&str, u32, bool)]) -> PacInfo {
        PacInfo {
            path: "test.pac".to_string(),
            count: names.len() as u32,
            flash_size: 0,
            entries: names
                .iter()
                .enumerate()
                .map(|(i, (n, s, nv))| entry(i, n, *s, *nv))
                .collect(),
            total_payload: names.iter().map(|(_, s, _)| *s as u64).sum(),
        }
    }

    #[test]
    fn fdl_discovery_accepts_case_known_and_legacy_names() {
        for (n1, n2) in [
            ("fdl1-sign.bin", "fdl2-sign.bin"),
            ("FDL1.BIN", "FDL2.BIN"),
            ("Fdl1", "Fdl2"),
            ("fdl1-dl.bin", "fdl2-dl.bin"),
            ("FDLA", "FDLB"),
            ("path/to/fdl1-sign.bin", "fdl2.bin"),
        ] {
            let info = info_with(&[("boot.img", 10, false), (n1, 4, false), (n2, 8, false)]);
            let (a, b) = find_fdl_entries(&info).unwrap();
            assert_eq!(a.name, n1, "FDL1 discovery failed for {n1}");
            assert_eq!(b.name, n2, "FDL2 discovery failed for {n2}");
        }
    }

    #[test]
    fn fdl_missing_error_lists_names_and_escape_hatch() {
        let info = info_with(&[("boot.img", 10, false), ("settings.xml", 4, false)]);
        let err = find_fdl_entries(&info).unwrap_err().to_string();
        assert!(err.contains("no FDL1 and FDL2"), "{err}");
        assert!(err.contains("boot.img, settings.xml"), "{err}");
        assert!(err.contains("--fdl1-addr"), "{err}");
        assert!(err.contains("--fdl2-addr"), "{err}");

        // Only FDL1 present: the message must name the missing one.
        let only1 = info_with(&[("fdl1.bin", 4, false), ("boot.img", 10, false)]);
        let err = find_fdl_entries(&only1).unwrap_err().to_string();
        assert!(err.contains("no FDL2 loader"), "{err}");
        assert!(!err.contains("no FDL1 and FDL2"), "{err}");

        // A zero-size loader slot is unusable, not silently accepted.
        let empty_loader = info_with(&[("fdl1.bin", 0, false), ("fdl2.bin", 8, false)]);
        let err = find_fdl_entries(&empty_loader).unwrap_err().to_string();
        assert!(err.contains("0 bytes"), "{err}");
    }

    #[test]
    fn entry_classification_flash_vs_skip() {
        assert_eq!(
            classify_pac_entry(&entry(0, "boot.img", 16, false)),
            PacEntryKind::Partition
        );
        assert_eq!(
            classify_pac_entry(&entry(0, "system.img", 16, false)),
            PacEntryKind::Partition
        );
        assert_eq!(
            classify_pac_entry(&entry(0, "FDL1-SIGN.BIN", 16, false)),
            PacEntryKind::Fdl1
        );
        assert_eq!(
            classify_pac_entry(&entry(0, "fdla.bin", 16, false)),
            PacEntryKind::Fdl1
        );
        assert_eq!(
            classify_pac_entry(&entry(0, "fdl2-sign.bin", 16, false)),
            PacEntryKind::Fdl2
        );
        assert_eq!(
            classify_pac_entry(&entry(0, "FDLB", 16, false)),
            PacEntryKind::Fdl2
        );
        assert_eq!(
            classify_pac_entry(&entry(0, "partition.xml", 16, false)),
            PacEntryKind::Xml
        );
        assert_eq!(
            classify_pac_entry(&entry(0, "settings.XML", 16, false)),
            PacEntryKind::Xml
        );
        assert_eq!(
            classify_pac_entry(&entry(0, "nvitem.bin", 16, true)),
            PacEntryKind::Nv
        );
        assert_eq!(
            classify_pac_entry(&entry(0, "NVDATA.img", 16, false)),
            PacEntryKind::Nv
        );
        // NV flag wins over a partition-looking name.
        assert_eq!(
            classify_pac_entry(&entry(0, "modem.bin", 16, true)),
            PacEntryKind::Nv
        );
        // Zero-size markers are skipped even when the name looks flashable.
        assert_eq!(
            classify_pac_entry(&entry(0, "boot.img", 0, false)),
            PacEntryKind::Empty
        );
        assert_eq!(
            classify_pac_entry(&entry(0, "fdl1.bin", 0, false)),
            PacEntryKind::Empty
        );
        // NV token matching is whole-token (inventory is not NV).
        assert_eq!(
            classify_pac_entry(&entry(0, "inventory.img", 16, false)),
            PacEntryKind::Partition
        );
    }

    #[test]
    fn entry_partition_name_strips_image_extensions_only() {
        assert_eq!(entry_partition_name("boot.img"), "boot");
        assert_eq!(entry_partition_name("system.bin"), "system");
        assert_eq!(entry_partition_name("UPPER.IMG"), "UPPER");
        assert_eq!(entry_partition_name("super.image"), "super");
        assert_eq!(entry_partition_name("dir/vendor.img"), "vendor");
        assert_eq!(entry_partition_name("persist"), "persist");
        assert_eq!(entry_partition_name("weird.dat"), "weird.dat");
    }

    #[test]
    fn read_entry_data_verifies_checksum_and_size() {
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("fp_pac_entry_{}_{stamp}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        // synthetic_pac fills payloads with 0xAB and writes the matching sum.
        let payload = vec![0xABu8; 9];
        let buf = synthetic_pac(&[("boot.img", payload.len() as u32)]);
        let path = dir.join("t.pac");
        std::fs::write(&path, &buf).unwrap();
        let info = parse_pac(path.to_str().unwrap()).unwrap();
        let data = read_entry_data(path.to_str().unwrap(), &info.entries[0]).unwrap();
        assert_eq!(data, payload);

        // Corrupt the entry table checksum: the reader must refuse the payload.
        let mut bad = buf.clone();
        bad[PAC_HEADER_SIZE + PAC_ENTRY_CHECKSUM_OFF..PAC_HEADER_SIZE + PAC_ENTRY_CHECKSUM_OFF + 2]
            .copy_from_slice(&0x1234u16.to_le_bytes());
        let bad_path = dir.join("bad.pac");
        std::fs::write(&bad_path, &bad).unwrap();
        let bad_info = parse_pac(bad_path.to_str().unwrap()).unwrap();
        let err = read_entry_data(bad_path.to_str().unwrap(), &bad_info.entries[0])
            .unwrap_err()
            .to_string();
        assert!(err.contains("checksum mismatch"), "{err}");
        let _ = std::fs::remove_dir_all(&dir);
    }
}
