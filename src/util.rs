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