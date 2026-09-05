//! Utility functions

use crate::error::Result;
use std::path::Path;
use std::fs;

/// Read file to bytes
pub fn read_file(path: &Path) -> Result<Vec<u8>> {
    fs::read(path).map_err(|e| crate::error::BridgeError::Io(e.to_string()))
}

/// Write bytes to file
pub fn write_file(path: &Path, data: &[u8]) -> Result<()> {
    fs::write(path, data).map_err(|e| crate::error::BridgeError::Io(e.to_string()))
}

/// Ensure directory exists
pub fn ensure_dir(path: &Path) -> Result<()> {
    if !path.exists() {
        fs::create_dir_all(path).map_err(|e| crate::error::BridgeError::Io(e.to_string()))?;
    }
    Ok(())
}

/// Parse hex string to bytes
pub fn parse_hex(hex: &str) -> Result<Vec<u8>> {
    let hex = hex.trim().trim_start_matches("0x");
    if hex.len() % 2 != 0 {
        return Err(crate::error::BridgeError::InvalidArgument("Hex string must have even length".to_string()));
    }
    let mut bytes = Vec::with_capacity(hex.len() / 2);
    for i in (0..hex.len()).step_by(2) {
        let byte = u8::from_str_radix(&hex[i..i+2], 16)
            .map_err(|_| crate::error::BridgeError::InvalidArgument("Invalid hex".to_string()))?;
        bytes.push(byte);
    }
    Ok(bytes)
}

/// Format bytes as hex
pub fn format_hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{:02X}", b)).collect::<Vec<_>>().join(" ")
}

/// Format bytes as hex with spaces
pub fn format_hex_spaced(bytes: &[u8], group: usize) -> String {
    let hex = format_hex(bytes);
    hex.as_bytes()
        .chunks(group * 2)
        .map(|chunk| String::from_utf8_lossy(chunk).to_string())
        .collect::<Vec<_>>()
        .join(" ")
}

/// Parse size string (e.g., "10MB", "1GB", "512KB")
pub fn parse_size(size_str: &str) -> Result<u64> {
    let size_str = size_str.trim().to_uppercase();
    let (num_str, unit) = if size_str.ends_with("KB") {
        (&size_str[..size_str.len()-2], 1024)
    } else if size_str.ends_with("MB") {
        (&size_str[..size_str.len()-2], 1024 * 1024)
    } else if size_str.ends_with("GB") {
        (&size_str[..size_str.len()-2], 1024 * 1024 * 1024)
    } else if size_str.ends_with("B") {
        (&size_str[..size_str.len()-1], 1)
    } else {
        (size_str.as_str(), 1)
    };
    
    let num: f64 = num_str.trim().parse()
        .map_err(|_| crate::error::BridgeError::InvalidArgument("Invalid size".to_string()))?;
    
    Ok((num * unit as f64) as u64)
}

/// Format size as human readable
pub fn format_size(bytes: u64) -> String {
    const UNITS: &[&str] = &["B", "KB", "MB", "GB", "TB"];
    let mut size = bytes as f64;
    let mut unit = 0;
    while size >= 1024.0 && unit < UNITS.len() - 1 {
        size /= 1024.0;
        unit += 1;
    }
    if unit == 0 {
        format!("{} {}", bytes, UNITS[unit])
    } else {
        format!("{:.2} {}", size, UNITS[unit])
    }
}

/// Progress reporter
pub struct ProgressReporter {
    total: u64,
    current: u64,
    last_report: std::time::Instant,
    interval: std::time::Duration,
}

impl ProgressReporter {
    pub fn new(total: u64, interval_ms: u64) -> Self {
        Self {
            total,
            current: 0,
            last_report: std::time::Instant::now(),
            interval: std::time::Duration::from_millis(interval_ms),
        }
    }

    pub fn update(&mut self, current: u64) {
        self.current = current;
        if self.last_report.elapsed() >= self.interval {
            self.report();
        }
    }

    pub fn finish(&mut self) {
        self.current = self.total;
        self.report();
    }

    fn report(&mut self) {
        if self.total > 0 {
            let pct = (self.current as f64 / self.total as f64) * 100.0;
            eprint!("\rProgress: {:.1}% ({}/{})", pct, crate::util::format_size(self.current), crate::util::format_size(self.total));
        } else {
            eprint!("\rTransferred: {}", crate::util::format_size(self.current));
        }
        use std::io::{stdout, Write};
        stdout().flush().ok();
        self.last_report = std::time::Instant::now();
    }
}

impl Drop for ProgressReporter {
    fn drop(&mut self) {
        self.finish();
        eprintln!();
    }
}

/// Streaming SHA-256 of a file (never loads the whole file into RAM).
pub fn sha256_file(path: &Path) -> Result<String> {
    use sha2::{Digest, Sha256};
    use std::io::Read;
    let f = fs::File::open(path).map_err(|e| crate::error::BridgeError::Io(e.to_string()))?;
    let mut h = Sha256::new();
    let mut buf = [0u8; 1 << 20];
    let mut reader = std::io::BufReader::new(f);
    loop {
        let n = reader
            .read(&mut buf)
            .map_err(|e| crate::error::BridgeError::Io(e.to_string()))?;
        if n == 0 {
            break;
        }
        h.update(&buf[..n]);
    }
    let digest: [u8; 32] = h.finalize().into();
    Ok(digest.iter().map(|b| format!("{b:02x}")).collect())
}

/// Compare two byte slices for verify-after-write. Returns Ok(()) on exact
/// match, Err with sizes + first-diff offset otherwise (no giant dumps).
pub fn verify_bytes_match(expected: &[u8], actual: &[u8]) -> std::result::Result<(), String> {
    if expected.len() != actual.len() {
        return Err(format!(
            "length mismatch: expected {} bytes, read back {} bytes",
            expected.len(),
            actual.len()
        ));
    }
    if let Some(i) = expected.iter().zip(actual.iter()).position(|(a, b)| a != b) {
        return Err(format!(
            "content mismatch at offset 0x{i:x} (expected {:02x}, got {:02x})",
            expected[i], actual[i]
        ));
    }
    Ok(())
}

/// Write SHA256SUMS + manifest.json into a backup directory by scanning the
/// files already written there. Idempotent: skips its own outputs, sorts
/// entries, overwrites both files. Returns a human summary string.
pub fn write_backup_manifest(out_dir: &Path) -> Result<String> {
    use std::io::Write;
    ensure_dir(out_dir)?;
    let mut entries: Vec<(String, u64, String)> = Vec::new();
    let dir = fs::read_dir(out_dir).map_err(|e| crate::error::BridgeError::Io(e.to_string()))?;
    for ent in dir.flatten() {
        let p = ent.path();
        if !p.is_file() {
            continue;
        }
        let name = match p.file_name().and_then(|n| n.to_str()) {
            Some(n) => n.to_string(),
            None => continue,
        };
        if name == "SHA256SUMS" || name == "manifest.json" {
            continue;
        }
        let size = fs::metadata(&p)
            .map(|m| m.len())
            .map_err(|e| crate::error::BridgeError::Io(e.to_string()))?;
        let sha = sha256_file(&p)?;
        entries.push((name, size, sha));
    }
    entries.sort_by(|a, b| a.0.cmp(&b.0));
    let mut sums = String::new();
    for (name, _, sha) in &entries {
        sums.push_str(&format!("{sha}  {name}\n"));
    }
    let sums_path = out_dir.join("SHA256SUMS");
    let mut f = fs::File::create(&sums_path).map_err(|e| crate::error::BridgeError::Io(e.to_string()))?;
    f.write_all(sums.as_bytes())
        .map_err(|e| crate::error::BridgeError::Io(e.to_string()))?;
    let files_json: Vec<String> = entries
        .iter()
        .map(|(name, size, sha)| {
            format!("    {{\"name\": \"{name}\", \"size\": {size}, \"sha256\": \"{sha}\"}}")
        })
        .collect();
    let manifest = format!(
        "{{\n  \"tool\": \"flashpilot-bridge\",\n  \"version\": \"{}\",\n  \"files\": [\n{}\n  ]\n}}\n",
        env!("CARGO_PKG_VERSION"),
        files_json.join(",\n")
    );
    fs::write(out_dir.join("manifest.json"), manifest)
        .map_err(|e| crate::error::BridgeError::Io(e.to_string()))?;
    Ok(format!(
        "manifest: {} file(s) hashed -> SHA256SUMS + manifest.json in {}",
        entries.len(),
        out_dir.display()
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    fn tmp_dir(name: &str) -> std::path::PathBuf {
        let d = std::env::temp_dir().join(format!("fp_util_test_{name}"));
        let _ = fs::remove_dir_all(&d);
        fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn sha256_file_matches_known_vector() {
        let d = tmp_dir("sha");
        let p = d.join("a.bin");
        fs::write(&p, b"abc").unwrap();
        assert_eq!(
            sha256_file(&p).unwrap(),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
    }

    #[test]
    fn verify_bytes_match_reports_first_diff() {
        assert!(verify_bytes_match(b"hello", b"hello").is_ok());
        let e = verify_bytes_match(b"hello", b"hallo").unwrap_err();
        assert!(e.contains("0x1"), "unexpected: {e}");
        let e2 = verify_bytes_match(b"ab", b"abc").unwrap_err();
        assert!(e2.contains("length mismatch"), "unexpected: {e2}");
    }

    #[test]
    fn backup_manifest_roundtrip() {
        let d = tmp_dir("manifest");
        let mut f = fs::File::create(d.join("modemst1.img")).unwrap();
        f.write_all(b"test-data-123").unwrap();
        let out = write_backup_manifest(&d).unwrap();
        assert!(out.contains("1 file(s)"), "unexpected: {out}");
        let sums = fs::read_to_string(d.join("SHA256SUMS")).unwrap();
        assert!(sums.ends_with("  modemst1.img\n"), "unexpected: {sums}");
        let manifest = fs::read_to_string(d.join("manifest.json")).unwrap();
        assert!(manifest.contains("\"tool\": \"flashpilot-bridge\""));
        assert!(manifest.contains("modemst1.img"));
        // Idempotent: second run skips its own outputs, same file set.
        let out2 = write_backup_manifest(&d).unwrap();
        assert!(out2.contains("1 file(s)"), "unexpected: {out2}");
    }
}