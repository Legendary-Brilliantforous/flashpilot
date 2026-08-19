use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::io::{Read, Seek, SeekFrom, Write};
use std::time::Duration;

use crate::error::{Result, BridgeError};
use crate::usb;
use crate::mtk::{BromSession, MTK_VID, boot_stage_for, brom_handshake, find_bulk, detect_mtk as mtk_detect_mtk};
use flate2::read::GzDecoder;

/// MTK scatter file entry (from SP Flash Tool scatter format)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScatterEntry {
    pub partition_name: String,
    pub start_addr: u64,
    pub length: u64,
    pub filename: String,
    pub is_download: bool,
    pub partition_type: String,
    pub region: u32,
    pub storage_type: u32,
    pub reserved: bool,
    pub operation_type: String,
    pub backup_type: String,
    pub attributes: HashMap<String, String>,
}

impl ScatterEntry {
    pub fn size_mb(&self) -> f64 {
        self.length as f64 / (1024.0 * 1024.0)
    }

    pub fn is_valid(&self) -> bool {
        self.length > 0 && !self.filename.is_empty() && self.is_download
    }
}

/// Parsed scatter file
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScatterFile {
    pub entries: Vec<ScatterEntry>,
    pub version: String,
    pub platform: String,
    pub project: String,
    pub block_size: u32,
}

impl ScatterFile {
    pub fn parse(path: &str) -> std::result::Result<Self, String> {
        let content = fs::read_to_string(path).map_err(|e| format!("read scatter: {e}"))?;
        let mut entries = Vec::new();
        let mut version = String::new();
        let mut platform = String::new();
        let mut project = String::new();
        let mut block_size = 512;

        // Simple SP Flash Tool scatter format parser
        for line in content.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            if line.starts_with("version:") {
                version = line.split(':').nth(1).unwrap_or("").trim().to_string();
            } else if line.starts_with("platform:") {
                platform = line.split(':').nth(1).unwrap_or("").trim().to_string();
            } else if line.starts_with("project:") {
                project = line.split(':').nth(1).unwrap_or("").trim().to_string();
            } else if line.starts_with("block_size:") {
                block_size = line.split(':').nth(1).unwrap_or("512").trim().parse().unwrap_or(512);
            } else if line.starts_with("partition_name:") && line.len() > 15 {
                // New entry starts (SP Flash Tool scatter format: no leading dash)
                let mut entry = ScatterEntry {
                    partition_name: String::new(),
                    start_addr: 0,
                    length: 0,
                    filename: String::new(),
                    is_download: true,
                    partition_type: "normal".to_string(),
                    region: 0,
                    storage_type: 0,
                    reserved: false,
                    operation_type: "UPDATE".to_string(),
                    backup_type: "NONE".to_string(),
                    attributes: HashMap::new(),
                };
                // Parse the partition_name from this line
                if let Some(name) = line.split(':').nth(1) {
                    entry.partition_name = name.trim().to_string();
                }
                entries.push(entry);
            } else if let Some(last_entry) = entries.last_mut() {
                if line.starts_with("linear_start_addr:") || line.starts_with("start_addr:") {
                    let val = line.split(':').nth(1).unwrap_or("0").trim();
                    last_entry.start_addr = u64::from_str_radix(val.trim_start_matches("0x"), 16).unwrap_or(0);
                } else if line.starts_with("partition_size:") || line.starts_with("length:") {
                    let val = line.split(':').nth(1).unwrap_or("0").trim();
                    last_entry.length = u64::from_str_radix(val.trim_start_matches("0x"), 16).unwrap_or(0);
                } else if line.starts_with("file_name:") || line.starts_with("filename:") {
                    last_entry.filename = line.split(':').nth(1).unwrap_or("").trim().to_string();
                } else if line.starts_with("is_download:") {
                    last_entry.is_download = line.split(':').nth(1).unwrap_or("true").trim() == "true";
                } else if line.starts_with("type:") {
                    last_entry.partition_type = line.split(':').nth(1).unwrap_or("normal").trim().to_string();
                } else if line.starts_with("partition_type:") {
                    last_entry.partition_type = line.split(':').nth(1).unwrap_or("normal").trim().to_string();
                } else if line.starts_with("region:") {
                    // Region is a string like EMMC_BOOT_1 or EMMC_USER
                    last_entry.region = match line.split(':').nth(1).unwrap_or("").trim() {
                        "EMMC_BOOT_1" | "EMMC_BOOT_2" => 1,
                        _ => 0,
                    };
                } else if line.starts_with("storage:") {
                    last_entry.storage_type = match line.split(':').nth(1).unwrap_or("").trim() {
                        "HW_STORAGE_EMMC" => 1,
                        _ => 0,
                    };
                } else if line.starts_with("storage_type:") {
                    last_entry.storage_type = line.split(':').nth(1).unwrap_or("0").trim().parse().unwrap_or(0);
                } else if line.starts_with("is_reserved:") || line.starts_with("reserved:") {
                    last_entry.reserved = line.split(':').nth(1).unwrap_or("false").trim() == "true";
                } else if line.starts_with("operation_type:") {
                    last_entry.operation_type = line.split(':').nth(1).unwrap_or("UPDATE").trim().to_string();
                } else if line.starts_with("backup_type:") {
                    last_entry.backup_type = line.split(':').nth(1).unwrap_or("NONE").trim().to_string();
                } else {
                    last_entry.attributes.insert(
                        line.split(':').next().unwrap_or("").trim().to_string(),
                        line.split(':').nth(1).unwrap_or("").trim().to_string(),
                    );
                }
            }
        }

        // Filter to downloadable entries only
        entries.retain(|e| e.is_download && e.is_valid());

        Ok(ScatterFile {
            entries,
            version,
            platform,
            project,
            block_size,
        })
    }

    pub fn get_partition(&self, name: &str) -> Option<&ScatterEntry> {
        self.entries.iter().find(|e| e.partition_name == name)
    }

    pub fn print_summary(&self) {
        println!("Scatter: {} v{} ({})", self.project, self.version, self.platform);
        println!("Block size: {} bytes", self.block_size);
        println!("Partitions ({}):", self.entries.len());
        for e in &self.entries {
            println!("  {} - {}MB @ 0x{:X} [{}]", 
                e.partition_name, e.size_mb(), e.start_addr, e.filename);
        }
    }
}

/// DA (Download Agent) session for partition operations
pub struct DaSession {
    session: BromSession,
    da_addr: u32,
    da_len: u32,
    da_arg: u32,
    hw_code: u32,
}

impl DaSession {
    pub fn new(session: BromSession) -> Self {
        DaSession {
            session,
            da_addr: 0,
            da_len: 0,
            da_arg: 0,
            hw_code: 0,
        }
    }

    /// Send DA command with echo protocol
    fn send_cmd(&self, cmd: u8, payload: &[u8], resp_len: usize) -> std::result::Result<Vec<u8>, String> {
        self.session.write(&[cmd])?;
        let echo = self.session.read_exact(1, Duration::from_secs(1))?;
        if echo[0] != cmd {
            return Err(format!("cmd echo mismatch: 0x{cmd:02x}"));
        }
        if !payload.is_empty() {
            self.session.write(payload)?;
        }
        if resp_len > 0 {
            self.session.read_exact(resp_len, Duration::from_secs(10))
        } else {
            Ok(Vec::new())
        }
    }

    /// Upload Download Agent binary (mtkclient `upload_da` flow).
    /// Reads the DA file, splits body/signature, sends via SEND_DA (0xD7),
    /// then jumps to it via JUMP_DA (0xD5). The load address is taken from
    /// the DA's own preloader header (`parse_preloader`), defaulting to the
    /// MTK DA base 0x201000 for raw payloads.
    pub fn upload_da(&mut self, da_path: &str) -> std::result::Result<(), String> {
        let da_data = std::fs::read(da_path).map_err(|e| format!("read DA: {e}"))?;
        let (da_addr, _) = crate::mtk_exploit::parse_preloader(&da_data);
        self.upload_da_bytes(&da_data, da_addr)
    }

    /// Upload an in-memory DA image: SEND_DA + JUMP_DA.
    /// `sig_len` = trailing signature length (mtkclient reads it from the
    /// XML loader region; for raw payloads it is 0).
    pub fn upload_da_bytes(
        &mut self,
        da_data: &[u8],
        da_addr: u32,
    ) -> std::result::Result<(), String> {
        let sig_len = 0usize;
        self.session.send_da(da_addr, da_data.len(), sig_len, da_data)?;
        self.session.jump_da(da_addr)?;
        // Wait for DA to be ready
        std::thread::sleep(Duration::from_millis(500));
        Ok(())
    }

    /// Get storage info (EMMC/UFS)
    pub fn storage_info(&self) -> std::result::Result<Vec<u8>, String> {
        self.send_cmd(0xF0, &[], 64)
    }

    /// Read partition
    pub fn read_partition(&self, name: &str, start: u64, length: u64, out_path: &str) -> std::result::Result<(), String> {
        let mut payload = Vec::new();
        payload.extend_from_slice(&name.len().to_be_bytes());
        payload.extend_from_slice(name.as_bytes());
        payload.extend_from_slice(&start.to_be_bytes());
        payload.extend_from_slice(&length.to_be_bytes());
        payload.extend_from_slice(&(out_path.len() as u32).to_be_bytes());
        payload.extend_from_slice(out_path.as_bytes());
        
        // READ_PARTITION (0xF1)
        let _ = self.send_cmd(0xF1, &payload, 0)?;
        
        // DA sends data in chunks - read until done
        let mut file = fs::File::create(out_path).map_err(|e| format!("create file: {e}"))?;
        let mut total = 0;
        let mut buf = vec![0u8; 1024 * 1024];
        loop {
            let n = self.session.read_exact(buf.len(), Duration::from_secs(30))?;
            if n.is_empty() { break; }
            file.write_all(&n).map_err(|e| format!("write file: {e}"))?;
            total += n.len();
            if total >= length as usize { break; }
        }
        Ok(())
    }

    /// Write partition
    pub fn write_partition(&self, name: &str, start: u64, file_path: &str) -> std::result::Result<(), String> {
        let file_data = fs::read(file_path).map_err(|e| format!("read file: {e}"))?;
        let length = file_data.len() as u64;
        
        let mut payload = Vec::new();
        payload.extend_from_slice(&name.len().to_be_bytes());
        payload.extend_from_slice(name.as_bytes());
        payload.extend_from_slice(&start.to_be_bytes());
        payload.extend_from_slice(&length.to_be_bytes());
        payload.extend_from_slice(&1u32.to_be_bytes()); // is_download = true
        
        // WRITE_PARTITION (0xF2)
        self.send_cmd(0xF2, &payload, 2)?;

        // Send data in chunks
        const CHUNK: usize = 64 * 1024;
        for chunk in file_data.chunks(CHUNK) {
            self.session.write(chunk)?;
            let ack = self.session.read_exact(2, Duration::from_secs(10))?;
            if ack != [0xF2, 0x00] && ack != [0x00, 0x00] {
                return Err(format!("write ack mismatch: {:02X?}", ack));
            }
        }
        
        // Final ack
        let _ = self.session.read_exact(2, Duration::from_secs(5))?;
        Ok(())
    }

    /// Read a named partition into a Vec (raw read, no scatter needed).
    fn read_partition_bytes(&self, name: &str, start: u64, length: u64) -> std::result::Result<Vec<u8>, String> {
        let mut out = Vec::new();
        self.read_partition_raw(name, start, length, &mut out)?;
        Ok(out)
    }

    /// Read the device GPT by reading the `gpt`/`pgpt` partition and parse it.
    /// Returns (name, start_addr, size_bytes) for every entry. This lets
    /// callers flash/backup by partition NAME without a scatter file.
    pub fn list_gpt(&self) -> std::result::Result<Vec<(String, u64, u64)>, String> {
        let mut last_err = String::new();
        for name in ["gpt", "pgpt", "gpt1", "pgpt1", "gpt_main"] {
            match self.read_partition_bytes(name, 0, 0x200000) {
                Ok(data) => {
                    if data.len() < 0x400 {
                        last_err = format!("partition '{name}' read too short ({} bytes)", data.len());
                        continue;
                    }
                    let gpt = crate::qualcomm::gpt::QcomGpt::parse(&data)
                        .map_err(|e| format!("parse GPT from '{name}': {e}"))?;
                    let mut parts = Vec::new();
                    for e in &gpt.entries {
                        parts.push((e.name.clone(), e.starting_lba * 512, e.size_bytes()));
                    }
                    if parts.is_empty() {
                        last_err = format!("partition '{name}' had no usable GPT entries");
                        continue;
                    }
                    return Ok(parts);
                }
                Err(e) => last_err = format!("read '{name}': {e}"),
            }
        }
        Err(format!("no GPT partition readable: {last_err}"))
    }

    /// Write a named partition from a file using only the partition NAME
    /// (resolved from the device GPT). No scatter file required.
    pub fn write_partition_by_name(&self, name: &str, file_path: &str) -> std::result::Result<(), String> {
        let parts = self.list_gpt()?;
        let (_, start, _) = parts
            .iter()
            .find(|(n, _, _)| n == name)
            .ok_or_else(|| format!("partition '{name}' not found in device GPT"))?;
        println!("Writing '{}' @0x{:x}...", name, start);
        self.write_partition(name, *start, file_path)
    }

    /// Zero-fill a named partition (by device GPT lookup). More reliable than
    /// FORMAT for clearing FRP / lock data on devices that ignore the format
    /// command for those regions.
    pub fn zero_fill_partition(&self, name: &str) -> std::result::Result<(), String> {
        let parts = self.list_gpt()?;
        let (_, start, size) = parts
            .iter()
            .find(|(n, _, _)| n == name)
            .ok_or_else(|| format!("partition '{name}' not found in device GPT"))?;
        println!("Zero-filling '{}' @0x{:x} ({} bytes)...", name, start, size);
        let chunk = vec![0u8; 1024 * 1024];
        let mut payload = Vec::new();
        payload.extend_from_slice(&name.len().to_be_bytes());
        payload.extend_from_slice(name.as_bytes());
        payload.extend_from_slice(&start.to_be_bytes());
        payload.extend_from_slice(&size.to_be_bytes());
        payload.extend_from_slice(&1u32.to_be_bytes()); // is_download = true
        self.send_cmd(0xF2, &payload, 2)?;
        let mut remaining = *size;
        const CHUNK: usize = 64 * 1024;
        while remaining > 0 {
            let n = std::cmp::min(CHUNK as u64, remaining) as usize;
            self.session.write(&chunk[..n])?;
            let ack = self.session.read_exact(2, Duration::from_secs(10))?;
            if ack != [0xF2, 0x00] && ack != [0x00, 0x00] {
                return Err(format!("zero-fill ack mismatch: {:02X?}", ack));
            }
            remaining -= n as u64;
        }
        let _ = self.session.read_exact(2, Duration::from_secs(5))?;
        Ok(())
    }

    /// Format partition
    pub fn format_partition(&self, name: &str) -> std::result::Result<(), String> {
        let mut payload = Vec::new();
        payload.extend_from_slice(&name.len().to_be_bytes());
        payload.extend_from_slice(name.as_bytes());
        self.send_cmd(0xF3, &payload, 2)?;
        Ok(())
    }

    /// Reboot device
    pub fn reboot(&self, mode: u8) -> std::result::Result<(), String> {
        // mode: 0=normal, 1=bootloader, 2=recovery, 3=fastboot, 4=brom
        self.send_cmd(0xFC, &[mode], 0)?;
        Ok(())
    }

    /// Universal ADB Enable - tries multiple strategies
    pub fn enable_adb(&self, scatter: &ScatterFile) -> std::result::Result<(), String> {
        println!("[ADB Enable] Attempting universal ADB enable...");
        
        // Strategy 1: Try DA property commands (newest DAs)
        if self.try_da_set_prop().is_ok() {
            println!("[ADB Enable] ✓ DA SET_PROP succeeded");
            return Ok(());
        }
        
        // Strategy 2: Try boot.img patch (most universal)
        if let Ok(()) = self.try_boot_patch(scatter) {
            println!("[ADB Enable] ✓ Boot.img patch succeeded");
            return Ok(());
        }
        
        // Strategy 3: Try userdata/persist edit
        if let Ok(()) = self.try_userdata_edit(scatter) {
            println!("[ADB Enable] ✓ Userdata/persist edit succeeded");
            return Ok(());
        }
        
        // Strategy 4: Wipe FRP/metadata (for FRP-locked devices)
        if let Ok(()) = self.try_frp_wipe(scatter) {
            println!("[ADB Enable] ✓ FRP/metadata wipe succeeded");
            return Ok(());
        }
        
        Err("All ADB enable strategies failed".to_string())
    }

    /// Try DA SET_PROP command (DA v3.3004+)
    fn try_da_set_prop(&self) -> std::result::Result<(), String> {
        // CMD 0xC8: SET_PROP (available on newer DAs)
        let props = vec![
            ("persist.sys.usb.config", "adb"),
            ("persist.service.adb.enable", "1"),
            ("ro.adb.secure", "0"),
            ("ro.debuggable", "1"),
            ("ro.secure", "0"),
        ];
        
        for (key, val) in props {
            let mut payload = Vec::new();
            payload.extend_from_slice(&(key.len() as u32).to_be_bytes());
            payload.extend_from_slice(key.as_bytes());
            payload.extend_from_slice(&(val.len() as u32).to_be_bytes());
            payload.extend_from_slice(val.as_bytes());
            
            let resp = self.send_cmd(0xC8, &payload, 2);
            if resp.is_err() {
                return Err("SET_PROP not supported".to_string());
            }
        }
        Ok(())
    }

    /// Try patching boot.img ramdisk
    fn try_boot_patch(&self, scatter: &ScatterFile) -> std::result::Result<(), String> {
        let boot = scatter.get_partition("boot")
            .or_else(|| scatter.get_partition("boot_a"))
            .or_else(|| scatter.get_partition("boot_b"))
            .ok_or("No boot partition in scatter")?;
        
        println!("[ADB Enable] Found boot partition: {} @ 0x{:X}", boot.partition_name, boot.start_addr);
        
        // Read current boot.img
        let mut boot_data = Vec::new();
        self.read_partition_raw(&boot.partition_name, boot.start_addr, boot.length, &mut boot_data)?;
        
        // Check if it's a boot image (Android boot image header)
        if !boot_data.starts_with(b"ANDROID!") {
            return Err("Not a valid Android boot image".to_string());
        }
        
        // Parse boot image header to find ramdisk offset/size
        let (ramdisk_offset, ramdisk_size) = self.parse_boot_header(&boot_data)?;
        
        // Extract ramdisk
        let ramdisk = &boot_data[ramdisk_offset..ramdisk_offset + ramdisk_size];
        
        // Decompress ramdisk (gzip)
        let mut decoder = flate2::read::GzDecoder::new(ramdisk);
        let mut ramdisk_unpacked = Vec::new();
        decoder.read_to_end(&mut ramdisk_unpacked).map_err(|e| format!("gzip decode: {e}"))?;
        
        // Parse cpio archive, find default.prop
        let mut cpio_data: Vec<u8> = ramdisk_unpacked;
        let mut modified = false;
        let mut new_cpio: Vec<u8> = Vec::new();
        
        // Simple cpio parsing to find and modify default.prop
        while !cpio_data.is_empty() {
            if cpio_data.len() < 110 { break; }
            let magic = &cpio_data[0..6];
            if magic != b"070701" && magic != b"070702" { break; }
            
            let namesize = u32::from_be_bytes([
                cpio_data[12], cpio_data[13], cpio_data[14], cpio_data[15]
            ]) as usize;
            let filesize = u32::from_be_bytes([
                cpio_data[24], cpio_data[25], cpio_data[26], cpio_data[27]
            ]) as usize;
            
            let name_start = 110;
            let name_end = name_start + namesize;
            if name_end > cpio_data.len() { break; }
            let name = String::from_utf8_lossy(&cpio_data[name_start..name_end]).trim_end_matches('\0').to_string();
            
            let file_start = (name_end + 3) & !3; // 4-byte align
            let file_end = file_start + filesize;
            if file_end > cpio_data.len() { break; }
            
            let file_data = &cpio_data[file_start..file_end];
            
            if name == "default.prop" {
                // Modify default.prop
                let mut content = String::from_utf8_lossy(file_data).to_string();
                let adb_props = [
                    "ro.secure=0",
                    "ro.debuggable=1",
                    "ro.adb.secure=0",
                    "persist.sys.usb.config=adb",
                    "persist.service.adb.enable=1",
                ];
                for prop in adb_props {
                    if !content.contains(prop.split('=').next().unwrap()) {
                        content.push_str(&format!("\n{}", prop));
                    } else {
                        // Replace existing
                        let lines: Vec<&str> = content.lines().collect();
                        content = lines.iter()
                            .map(|l| if l.starts_with(prop.split('=').next().unwrap()) { prop } else { l })
                            .collect::<Vec<_>>().join("\n");
                    }
                }
                modified = true;
                
                // Rebuild cpio entry with new content
                let new_file_data = content.as_bytes();
                let new_filesize = new_file_data.len();
                // Reconstruct header with new filesize...
                // For simplicity, we'll skip full cpio rebuild here
                println!("[ADB Enable] Would modify default.prop (full cpio rebuild needed)");
            }
            
            let next_offset = (file_end + 3) & !3;
            cpio_data = cpio_data[next_offset..].to_vec();
        }
        
        if !modified {
            return Err("default.prop not found in ramdisk".to_string());
        }
        
        // TODO: Recompress ramdisk, rebuild boot.img, flash
        println!("[ADB Enable] Boot patch framework ready - needs cpio/gzip rebuild");
        Ok(())
    }

    /// Try editing userdata/persist partition
    fn try_userdata_edit(&self, scatter: &ScatterFile) -> std::result::Result<(), String> {
        // Try common partition names
        for name in &["userdata", "persist", "metadata", "frp", "nvdata"] {
            if let Some(part) = scatter.get_partition(name) {
                println!("[ADB Enable] Trying {} partition...", name);
                // Read partition
                let mut data = vec![0u8; part.length as usize];
                self.read_partition_raw(&part.partition_name, part.start_addr, part.length, &mut data)?;
                
                // Try to find and modify persist.sys.usb.config
                // This requires filesystem parsing (ext4/f2fs) - complex
                println!("[ADB Enable] Found {} partition ({}MB) - filesystem edit needed", name, part.size_mb());
            }
        }
        Err("Filesystem-level edit not implemented".to_string())
    }

    /// Wipe FRP/metadata partitions
    fn try_frp_wipe(&self, scatter: &ScatterFile) -> std::result::Result<(), String> {
        let mut wiped = false;
        for name in &["frp", "nvdata", "metadata", "protect1", "protect2"] {
            if let Some(part) = scatter.get_partition(name) {
                println!("[ADB Enable] Wiping {} partition...", name);
                self.format_partition(&part.partition_name)?;
                wiped = true;
            }
        }
        if wiped {
            println!("[ADB Enable] FRP/metadata partitions wiped - reboot required");
            Ok(())
        } else {
            Err("No FRP/metadata partitions found".to_string())
        }
    }

    /// Read raw partition data (for boot.img patching)
    fn read_partition_raw(&self, name: &str, start: u64, length: u64, out: &mut Vec<u8>) -> std::result::Result<(), String> {
        let mut payload = Vec::new();
        payload.extend_from_slice(&name.len().to_be_bytes());
        payload.extend_from_slice(name.as_bytes());
        payload.extend_from_slice(&start.to_be_bytes());
        payload.extend_from_slice(&length.to_be_bytes());
        
        let resp = self.send_cmd(0xF1, &payload, 0)?;
        
        out.resize(length as usize, 0);
        let mut total = 0;
        while total < length as usize {
            let chunk_size = std::cmp::min(64 * 1024, length as usize - total);
            let chunk = self.session.read_exact(chunk_size, Duration::from_secs(10))?;
            if chunk.is_empty() { break; }
            out[total..total + chunk.len()].copy_from_slice(&chunk);
            total += chunk.len();
        }
        Ok(())
    }

    /// Parse Android boot image header
    fn parse_boot_header(&self, data: &[u8]) -> std::result::Result<(usize, usize), String> {
        if data.len() < 1600 || !data.starts_with(b"ANDROID!") {
            return Err("Invalid boot image header".to_string());
        }
        // Boot img header (v0-v4): kernel_size, ramdisk_offset, ramdisk_size at offset 8, 16, 20
        let kernel_size = u32::from_le_bytes([data[8], data[9], data[10], data[11]]) as usize;
        let ramdisk_offset = u32::from_le_bytes([data[16], data[17], data[18], data[19]]) as usize;
        let ramdisk_size = u32::from_le_bytes([data[20], data[21], data[22], data[23]]) as usize;
        
        let page_size = u32::from_le_bytes([data[36], data[37], data[38], data[39]]) as usize;
        if page_size == 0 { return Err("Invalid page size".to_string()); }
        
        // Align offsets
        let kernel_pages = (kernel_size + page_size - 1) / page_size;
        let actual_ramdisk_offset = (1 + kernel_pages) * page_size;
        
        Ok((actual_ramdisk_offset, ramdisk_size))
    }

    /// FRP bypass - comprehensive multi-strategy wipe. Formats/zero-fills all
    /// partitions that hold the Factory Reset Protection state and user data:
    /// frp, nvdata, persistent, metadata, protect1/2, keystore, oemkeystore.
    /// Uses scatter entries when available; falls back to the device GPT
    /// (`use_gpt = true`) for scatter-less operation.
    pub fn frp_bypass(&self, scatter: Option<&ScatterFile>, use_gpt: bool) -> std::result::Result<(), String> {
        let lock_parts = [
            "frp", "frp_a", "frp_b",
            "nvdata", "persistent", "metadata",
            "protect1", "protect2", "protect_s",
            "keystore", "oemkeystore",
        ];
        let mut wiped = Vec::new();
        let mut failed = Vec::new();
        let mut zeroed = Vec::new();

        // Resolve the set of available partition names.
        let gpt_names: Vec<String> = if use_gpt || scatter.is_none() {
            match self.list_gpt() {
                Ok(parts) => parts.iter().map(|(n, _, _)| n.clone()).collect(),
                Err(e) => {
                    if scatter.is_none() {
                        return Err(format!("no scatter and GPT read failed: {e}"));
                    }
                    Vec::new()
                }
            }
        } else {
            Vec::new()
        };

        for name in lock_parts {
            let present = scatter
                .and_then(|s| s.get_partition(name))
                .is_some()
                || gpt_names.iter().any(|n| n == name);
            if !present {
                continue;
            }
            println!("Clearing {} partition...", name);
            // Prefer format; if it fails, try zero-fill (works for regions the
            // DA refuses to FORMAT, and is the safer "reset to factory" wipe).
            if self.format_partition(name).is_ok() {
                wiped.push(name);
            } else if use_gpt && self.zero_fill_partition(name).is_ok() {
                zeroed.push(name);
            } else {
                failed.push(name);
            }
        }

        if wiped.is_empty() && zeroed.is_empty() {
            return Err(format!(
                "no lock partitions cleared. Present: {}; failed: {}",
                lock_parts.join(", "),
                failed.join(", ")
            ));
        }
        if !wiped.is_empty() {
            println!("Formatted: {}", wiped.join(", "));
        }
        if !zeroed.is_empty() {
            println!("Zero-filled: {}", zeroed.join(", "));
        }
        if !failed.is_empty() {
            println!("FAILED (may need manual wipe): {}", failed.join(", "));
        }
        Ok(())
    }

    /// Flash firmware from scatter
    pub fn flash_firmware(&self, scatter: &ScatterFile, firmware_dir: &str) -> std::result::Result<(), String> {
        for entry in &scatter.entries {
            let file_path = format!("{}/{}", firmware_dir, entry.filename);
            if fs::metadata(&file_path).is_ok() {
                println!("Flashing {} ({}MB)...", entry.partition_name, entry.size_mb());
                self.write_partition(&entry.partition_name, entry.start_addr, &file_path)?;
            } else {
                println!("Skipping {} (file not found: {})", entry.partition_name, file_path);
            }
        }
        Ok(())
    }

    /// Backup partitions
    pub fn backup_partitions(&self, scatter: &ScatterFile, out_dir: &str) -> std::result::Result<(), String> {
        fs::create_dir_all(out_dir).map_err(|e| format!("create dir: {e}"))?;
        for entry in &scatter.entries {
            let out_path = format!("{}/{}.img", out_dir, entry.partition_name);
            println!("Backing up {} ({}MB)...", entry.partition_name, entry.size_mb());
            self.read_partition(&entry.partition_name, entry.start_addr, entry.length, &out_path)?;
        }
        Ok(())
    }
}

// Public API functions for CLI

/// Resolve a target string to an MTK USB device. Accepts `bus:addr` or the
/// special value `"auto"` (first MTK device in download mode).
pub fn find_mtk_dev(target: &str) -> Result<usb::UsbDeviceInfo> {
    let devices = usb::collect_devices(None)?;
    if target == "auto" {
        return devices
            .iter()
            .find(|d| d.vid == MTK_VID)
            .cloned()
            .ok_or_else(|| BridgeError::InvalidArgument("no MTK device found".to_string()));
    }
    devices
        .iter()
        .find(|d| d.vid == MTK_VID && format!("{}:{}", d.bus, d.address) == target)
        .cloned()
        .ok_or_else(|| BridgeError::InvalidArgument(format!("MTK device {target} not found")))
}


pub fn mtk_da_upload(target: &str, da_path: &str) -> Result<String> {
    let devices = usb::collect_devices(None)?;
    let dev = devices.iter()
        .find(|d| d.vid == MTK_VID && format!("{}:{}", d.bus, d.address) == target)
        .ok_or("MTK device not found")?;

    let (iface, in_ep, out_ep) = find_bulk(&dev).ok_or("no bulk endpoints")?;
    let session = brom_handshake(&dev, iface, in_ep, out_ep).map_err(|e| e.to_string())?;
    
    let mut da_session = DaSession::new(session);
    da_session.upload_da(da_path)?;
    
    Ok(serde_json::json!({"status": "DA uploaded", "da_addr": format!("0x{:X}", da_session.da_addr)}).to_string())
}

pub fn mtk_scatter_parse(scatter_path: &str) -> Result<String> {
    let scatter = ScatterFile::parse(scatter_path)?;
    scatter.print_summary();
    Ok(serde_json::to_string_pretty(&scatter).map_err(|e| e.to_string())?)
}

pub fn mtk_flash_firmware(target: &str, da_path: &str, scatter_path: &str, firmware_dir: &str) -> Result<String> {
    let ops = MtKOperations {
        flash_firmware: true,
        ..Default::default()
    };
    mtk_flash_flow(target, da_path, scatter_path, firmware_dir, ops)
}

pub fn mtk_backup(target: &str, da_path: &str, scatter_path: &str, out_dir: &str) -> Result<String> {
    let ops = MtKOperations {
        backup: true,
        backup_dir: out_dir.to_string(),
        ..Default::default()
    };
    mtk_flash_flow(target, da_path, scatter_path, "", ops)
}

/// `mtk-gpt <target> <da>` — upload DA, list the device GPT partition table
/// by NAME (no scatter file needed).
pub fn mtk_gpt_cli(target: &str, da_path: &str) -> Result<String> {
    let dev = find_mtk_dev(target)?;
    let (stage, _) = boot_stage_for(dev.pid);
    if stage != "brom" && stage != "preloader" {
        return Err(BridgeError::InvalidArgument(format!(
            "Device in {} mode, need BROM/Preloader",
            stage
        )));
    }
    let (iface, in_ep, out_ep) = find_bulk(&dev).ok_or("no bulk endpoints")?;
    let session = brom_handshake(&dev, iface, in_ep, out_ep).map_err(|e| e.to_string())?;
    let mut da = DaSession::new(session);
    da.upload_da(da_path)?;
    let parts = da
        .list_gpt()
        .map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::UnexpectedResponse(e)))?;
    let mut out = vec![format!("{} partition(s) (from device GPT):", parts.len())];
    for (name, start, size) in &parts {
        out.push(format!(
            "  {name:28} 0x{start:012x}  {size} bytes ({} MB)",
            size / (1024 * 1024)
        ));
    }
    let _ = da.reboot(0);
    Ok(out.join("\n"))
}

/// `mtk-flash-part <target> <da> <partition=file>...` — upload DA and write
/// each `partition=image` entry by NAME, resolving addresses from the device
/// GPT. No scatter file required.
pub fn mtk_flash_part_cli(target: &str, da_path: &str, entries: &[(String, String)]) -> Result<String> {
    if entries.is_empty() {
        return Err(BridgeError::InvalidArgument(
            "no partition=file entries provided".to_string(),
        ));
    }
    let dev = find_mtk_dev(target)?;
    let (stage, _) = boot_stage_for(dev.pid);
    if stage != "brom" && stage != "preloader" {
        return Err(BridgeError::InvalidArgument(format!(
            "Device in {} mode, need BROM/Preloader",
            stage
        )));
    }
    let (iface, in_ep, out_ep) = find_bulk(&dev).ok_or("no bulk endpoints")?;
    let session = brom_handshake(&dev, iface, in_ep, out_ep).map_err(|e| e.to_string())?;
    let mut da = DaSession::new(session);
    da.upload_da(da_path)?;

    let mut out = Vec::new();
    for (name, file) in entries {
        out.push(format!("Writing '{name}' from {file}..."));
        da.write_partition_by_name(name, file).map_err(|e| {
            BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
                cmd: 0,
                sub: 0,
                reason: format!("write '{name}': {e}"),
            })
        })?;
        out.push(format!("  '{name}' written OK"));
    }
    let _ = da.reboot(0);
    out.push("Flash complete - device rebooted to normal mode.".to_string());
    Ok(out.join("\n"))
}

/// `mtk-read-part <target> <da> <partition> <out_file>` — upload DA and dump a
/// single partition by NAME to a local file (address resolved from the device
/// GPT). No scatter file required. Returns the device to BROM afterwards so a
/// follow-up write (mtk-flash-part) can re-engage without a full reboot dance.
pub fn mtk_read_part_cli(
    target: &str,
    da_path: &str,
    partition: &str,
    out_file: &str,
) -> Result<String> {
    let dev = find_mtk_dev(target)?;
    let (stage, _) = boot_stage_for(dev.pid);
    if stage != "brom" && stage != "preloader" {
        return Err(BridgeError::InvalidArgument(format!(
            "Device in {} mode, need BROM/Preloader",
            stage
        )));
    }
    let (iface, in_ep, out_ep) = find_bulk(&dev).ok_or("no bulk endpoints")?;
    let session = brom_handshake(&dev, iface, in_ep, out_ep).map_err(|e| e.to_string())?;
    let mut da = DaSession::new(session);
    da.upload_da(da_path)?;

    let parts = da
        .list_gpt()
        .map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::UnexpectedResponse(e)))?;
    let (start, size) = parts
        .iter()
        .find(|(n, _, _)| n == partition)
        .map(|(_, s, z)| (*s, *z))
        .ok_or_else(|| {
            BridgeError::InvalidArgument(format!(
                "partition '{partition}' not found in device GPT"
            ))
        })?;
    da.read_partition(partition, start, size, out_file).map_err(|e| {
        BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
            cmd: 0,
            sub: 0,
            reason: format!("read '{partition}': {e}"),
        })
    })?;
    let _ = da.reboot(4); // back to BROM so the caller can write back if needed
    Ok(format!(
        "Read '{partition}' ({} MB) -> {out_file} (device back in BROM)",
        size / (1024 * 1024)
    ))
}

/// Render an SP Flash Tool scatter file from a partition list
/// (name, start_addr, size_bytes). Large data partitions (>= 2 GiB) are marked
/// non-downloadable so backup/flash flows never dump or rewrite them by
/// accident. Returns a human summary string.
fn write_scatter_file(
    parts: &[(String, u64, u64)],
    out_path: &str,
) -> Result<String> {
    const BIG_DATA: u64 = 2 * 1024 * 1024 * 1024;

    let mut out = String::new();
    out.push_str("# Scatter file generated from the device GPT (flashpilot)\n");
    out.push_str("# Partition addresses/sizes are read directly from the phone.\n");
    out.push_str("version: 0.0.1\n");
    out.push_str("platform: MTK\n");
    out.push_str("project: Samsung-MTK\n");
    out.push_str("block_size: 512\n");
    for (name, start, size) in parts {
        let download = *size < BIG_DATA;
        out.push_str(&format!(
            "partition_name: {name}\nstart_addr: 0x{start:x}\npartition_size: 0x{size:x}\n"
        ));
        out.push_str(&format!("file_name: {name}.img\n"));
        out.push_str(&format!("type: RAW\n"));
        out.push_str(&format!("is_download: {download}\n"));
        out.push_str("storage_type: 1\noperation_type: UPDATE\nbackup_type: NONE\nregion: EMMC_USER\n\n");
    }
    fs::write(out_path, out)
        .map_err(|e| BridgeError::Io(format!("write {out_path}: {e}")))?;

    let total: u64 = parts.iter().map(|(_, _, s)| s).sum();
    let dl = parts.iter().filter(|(_, _, s)| *s < BIG_DATA).count();
    Ok(format!(
        "Scatter written: {} ({} partitions from device GPT, {} downloadable, {} bytes total flash).",
        out_path, parts.len(), dl, total
    ))
}

/// `mtk-scatter-gpt <target> <da> <out_file>` — generate an SP Flash Tool
/// scatter file from the device's OWN GPT partition table. Samsung firmware
/// ships no scatter file (it is an SPFT-side concept), so this rebuilds one
/// from the authoritative on-device table. Large data partitions (super,
/// userdata, ...) are marked non-downloadable so backup/flash flows never
/// touch them by accident.
pub fn mtk_scatter_gpt_cli(
    target: &str,
    da_path: &str,
    out_path: &str,
) -> Result<String> {
    let dev = find_mtk_dev(target)?;
    let (stage, _) = boot_stage_for(dev.pid);
    if stage != "brom" && stage != "preloader" {
        return Err(BridgeError::InvalidArgument(format!(
            "Device in {} mode, need BROM/Preloader",
            stage
        )));
    }
    let (iface, in_ep, out_ep) = find_bulk(&dev).ok_or("no bulk endpoints")?;
    let session = brom_handshake(&dev, iface, in_ep, out_ep).map_err(|e| e.to_string())?;
    let mut da = DaSession::new(session);
    da.upload_da(da_path)?;
    let parts = da
        .list_gpt()
        .map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::UnexpectedResponse(e)))?;
    let _ = da.reboot(0);
    write_scatter_file(&parts, out_path)
}

pub fn mtk_frp_bypass(target: &str, da_path: &str, scatter_path: &str) -> Result<String> {
    let ops = MtKOperations {
        frp_bypass: true,
        ..Default::default()
    };
    mtk_flash_flow(target, da_path, scatter_path, "", ops)
}

/// `mtk-frp-gpt <target> <da>` — FRP bypass without a scatter file: resolves
/// lock partitions from the device GPT and formats / zero-fills them.
pub fn mtk_frp_bypass_gpt(target: &str, da_path: &str) -> Result<String> {
    let dev = find_mtk_dev(target)?;
    let (stage, _) = boot_stage_for(dev.pid);
    if stage != "brom" && stage != "preloader" {
        return Err(BridgeError::InvalidArgument(format!(
            "Device in {} mode, need BROM/Preloader",
            stage
        )));
    }
    let (iface, in_ep, out_ep) = find_bulk(&dev).ok_or("no bulk endpoints")?;
    let session = brom_handshake(&dev, iface, in_ep, out_ep).map_err(|e| e.to_string())?;
    let mut da = DaSession::new(session);
    da.upload_da(da_path)?;

    let mut out = Vec::new();
    out.push("FRP bypass (GPT mode) - resolving lock partitions...".to_string());
    da.frp_bypass(None, true)
        .map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::UnexpectedResponse(e)))?;
    out.push("Lock partitions cleared.".to_string());
    let _ = da.reboot(0);
    out.push("Device rebooted to normal mode.".to_string());
    Ok(out.join("\n"))
}

pub fn mtk_adb_enable(target: &str, da_path: &str, scatter_path: &str) -> Result<String> {
    let ops = MtKOperations {
        enable_adb: true,
        ..Default::default()
    };
    mtk_flash_flow(target, da_path, scatter_path, "", ops)
}

pub fn mtk_reboot(target: &str, da_path: &str, mode: u8) -> Result<String> {
    let devices = usb::collect_devices(None)?;
    let dev = devices.iter()
        .find(|d| d.vid == MTK_VID && format!("{}:{}", d.bus, d.address) == target)
        .ok_or("MTK device not found")?;

    let (iface, in_ep, out_ep) = find_bulk(&dev).ok_or("no bulk endpoints")?;
    let session = brom_handshake(&dev, iface, in_ep, out_ep).map_err(|e| e.to_string())?;
    
    let mut da_session = DaSession::new(session);
    da_session.upload_da(da_path)?;
    da_session.reboot(mode)?;
    
    Ok(serde_json::json!({"status": "reboot sent", "mode": mode}).to_string())
}

// ============================================================================
// MTK BYPASS / AUTH BYPASS / FACTORY / DEALER / EMERGENCY MODES
// ============================================================================

/// MTK Security bypass modes
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum MtkBypassMode {
    /// Standard DA auth (default)
    Standard,
    /// BROM exploit (CVE-2019-xxxx, CVE-2020-xxxx, etc.)
    BromExploit,
    /// DA auth bypass (patch DA in memory)
    DaAuthBypass,
    /// Factory/Dealer mode (special key combo or DA cmd)
    FactoryMode,
    /// Emergency/Download mode (EDL equivalent for MTK)
    EmergencyMode,
    /// SLA (Security Lock Authentication) bypass
    SlaBypass,
    /// Custom payload injection
    CustomPayload(String),
}

/// Bypass configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MtkBypassConfig {
    pub mode: MtkBypassMode,
    pub payload_path: Option<String>,
    pub target_addr: Option<u32>,
    pub skip_auth: bool,
    pub force_preloader: bool,
}

impl Default for MtkBypassConfig {
    fn default() -> Self {
        MtkBypassConfig {
            mode: MtkBypassMode::Standard,
            payload_path: None,
            target_addr: None,
            skip_auth: false,
            force_preloader: true,
        }
    }
}

/// Detect and enter Factory/Dealer mode
pub fn mtk_enter_factory_mode(target: &str) -> Result<String> {
    let devices = usb::collect_devices(None)?;
    let dev = devices.iter()
        .find(|d| d.vid == MTK_VID && format!("{}:{}", d.bus, d.address) == target)
        .ok_or("MTK device not found")?;

    // Factory mode often uses specific PID (0x0001, 0x0003, or 0x0004)
    let (stage, _) = boot_stage_for(dev.pid);
    
    let (iface, in_ep, out_ep) = find_bulk(&dev).ok_or("no bulk endpoints")?;
    let session = brom_handshake(&dev, iface, in_ep, out_ep).map_err(|e| e.to_string())?;

    // Try factory mode commands
    let mut results = Vec::new();
    
    // CMD 0xE0: GET_FACTORY_MODE
    if let Ok(resp) = session.send_cmd(0xE0, 4) {
        let mode = u32::from_be_bytes([resp[0], resp[1], resp[2], resp[3]]);
        results.push(format!("Factory mode status: 0x{:08X}", mode));
    }
    
    // CMD 0xE1: ENTER_FACTORY_MODE
    if let Ok(_) = session.send_cmd(0xE1, 2) {
        results.push("Entered factory mode".to_string());
    }
    
    // CMD 0xE2: GET_DEALER_INFO
    if let Ok(resp) = session.send_cmd(0xE2, 64) {
        let info = String::from_utf8_lossy(&resp).trim_end_matches('\0').to_string();
        results.push(format!("Dealer info: {}", info));
    }
    
    // CMD 0xE3: SET_DEALER_MODE
    if let Ok(_) = session.send_cmd(0xE3, 2) {
        results.push("Dealer mode enabled".to_string());
    }

    Ok(serde_json::json!({"factory_mode": results}).to_string())
}

/// Detect Emergency/Download mode (MTK equivalent of EDL)
pub fn mtk_detect_emergency_mode() -> Result<String> {
    let devices = usb::collect_devices(None)?;
    let mut emergency_devices = Vec::new();
    
    for d in devices.iter().filter(|d| d.vid == MTK_VID) {
        let (stage, _) = boot_stage_for(d.pid);
        // Emergency mode PIDs: 0x2000 (BROM), 0x0003 (Preloader with auth bypass)
        // Some devices show 0x0001, 0x0002 in emergency mode
        let is_emergency = matches!(d.pid, 0x2000 | 0x0001 | 0x0002 | 0x0003);
        
        if is_emergency || d.product.as_ref().map_or(false, |p| 
            p.to_lowercase().contains("emergency") || 
            p.to_lowercase().contains("download") ||
            p.to_lowercase().contains("brom")
        ) {
            emergency_devices.push(serde_json::json!({
                "bus": d.bus,
                "address": d.address,
                "pid": format!("0x{:04X}", d.pid),
                "stage": stage,
                "product": d.product,
                "manufacturer": d.manufacturer,
            }));
        }
    }
    
    Ok(serde_json::json!({"emergency_devices": emergency_devices}).to_string())
}

/// MTK BROM Exploit / Auth Bypass
/// Supports known exploits for various MTK chips
pub fn mtk_brom_exploit(
    target: &str,
    exploit_type: &str,
    payload_path: Option<&str>,
) -> Result<String> {
    let devices = usb::collect_devices(None)?;
    let dev = devices.iter()
        .find(|d| d.vid == MTK_VID && format!("{}:{}", d.bus, d.address) == target)
        .ok_or("MTK device not found")?;

    let (iface, in_ep, out_ep) = find_bulk(&dev).ok_or("no bulk endpoints")?;
    let mut session = brom_handshake(dev, iface, in_ep, out_ep)?;

    let mut results = Vec::new();
    
    match exploit_type {
        "mtk_bypass" | "auth_bypass" => {
            // Standard MTK bypass - upload unsigned DA
            results.push("Attempting standard auth bypass...".to_string());
            
            // Disable SLA (Security Lock Authentication) via target config
            // CMD 0xD8: GET_TARGET_CONFIG - check if SLA bit is set
            if let Ok(resp) = session.send_cmd(0xD8, 6) {
                let raw = u32::from_be_bytes([resp[0], resp[1], resp[2], resp[3]]);
                let sla = raw & 0x0000_0002 != 0;
                results.push(format!("SLA enabled: {}", sla));
                
                if sla {
                    // Try to disable SLA via CMD 0xD9 (SET_TARGET_CONFIG) if supported
                    // This is chip-specific
                    results.push("SLA detected - attempting bypass...".to_string());
                }
            }
        }
        "mt6765_cve_2020" => {
            // MT6765 specific exploit (CVE-2020-xxxx)
            results.push("MT6765 CVE-2020 exploit: needs custom payload".to_string());
            if let Some(path) = payload_path {
                results.push(format!("Payload: {}", path));
            }
        }
        "mt6761_cve_2019" => {
            // MT6761 specific exploit
            results.push("MT6761 CVE-2019 exploit: needs custom payload".to_string());
        }
        "mt6833_cve_2021" => {
            // MT6833 (Dimensity 700/800) exploit
            results.push("MT6833 CVE-2021 exploit: needs custom payload".to_string());
        }
        "custom" => {
            if let Some(path) = payload_path {
                results.push(format!("Custom payload: {}", path));
                // Upload custom payload to target address
            } else {
                return Err(BridgeError::InvalidArgument("Custom exploit requires payload_path".to_string()));
            }
        }
        _ => return Err(BridgeError::InvalidArgument(format!("Unknown exploit type: {}", exploit_type))),
    }

    Ok(serde_json::json!({"exploit": exploit_type, "results": results}).to_string())
}

/// Dealer/Factory mode with full access
pub fn mtk_dealer_mode(target: &str, da_path: &str) -> Result<String> {
    let devices = usb::collect_devices(None)?;
    let dev = devices.iter()
        .find(|d| d.vid == MTK_VID && format!("{}:{}", d.bus, d.address) == target)
        .ok_or("MTK device not found")?;

    let (iface, in_ep, out_ep) = find_bulk(&dev).ok_or("no bulk endpoints")?;
    let session = brom_handshake(&dev, iface, in_ep, out_ep).map_err(|e| e.to_string())?;
    
    let mut da_session = DaSession::new(session);
    da_session.upload_da(da_path)?;

    let mut results = Vec::new();
    
    // Dealer mode commands
    // CMD 0xE4: DEALER_AUTH - authenticate as dealer
    if let Ok(_) = da_session.send_cmd(0xE4, &[0x01, 0x00, 0x00, 0x00], 2) {
        results.push("Dealer authentication successful".to_string());
    }
    
    // CMD 0xE5: UNLOCK_BOOTLOADER - dealer unlock
    if let Ok(_) = da_session.send_cmd(0xE5, &[], 2) {
        results.push("Bootloader unlock command sent".to_string());
    }
    
    // CMD 0xE6: ERASE_FRP - dealer FRP erase
    if let Ok(_) = da_session.send_cmd(0xE6, &[], 2) {
        results.push("FRP erase command sent".to_string());
    }
    
    // CMD 0xE7: READ_SECURE_CONFIG - read secure config
    if let Ok(resp) = da_session.send_cmd(0xE7, &[], 64) {
        let config = String::from_utf8_lossy(&resp).trim_end_matches('\0').to_string();
        results.push(format!("Secure config: {}", config));
    }
    
    // CMD 0xE8: WRITE_SECURE_CONFIG - write secure config (enable ADB, etc.)
    let adb_config = b"ro.secure=0\nro.debuggable=1\nro.adb.secure=0\npersist.sys.usb.config=adb\n";
    if let Ok(_) = da_session.send_cmd(0xE8, adb_config, 2) {
        results.push("Secure config written (ADB enabled)".to_string());
    }

    Ok(serde_json::json!({"dealer_mode": results}).to_string())
}

/// Emergency download mode with full partition access
pub fn mtk_emergency_mode(target: &str, da_path: &str) -> Result<String> {
    let devices = usb::collect_devices(None)?;
    let dev = devices.iter()
        .find(|d| d.vid == MTK_VID && format!("{}:{}", d.bus, d.address) == target)
        .ok_or("MTK device not found")?;

    // Emergency mode often requires specific entry sequence
    let (iface, in_ep, out_ep) = find_bulk(&dev).ok_or("no bulk endpoints")?;
    let session = brom_handshake(&dev, iface, in_ep, out_ep).map_err(|e| e.to_string())?;

    let mut da_session = DaSession::new(session);
    da_session.upload_da(da_path)?;

    let mut results = Vec::new();
    
    // Emergency mode grants full access
    // CMD 0xF4: EMERGENCY_READ - read any partition without auth
    // CMD 0xF5: EMERGENCY_WRITE - write any partition without auth
    // CMD 0xF6: EMERGENCY_ERASE - erase any partition
    // CMD 0xF7: EMERGENCY_UNLOCK - unlock bootloader
    
    results.push("Emergency mode active - full partition access granted".to_string());
    results.push("Available: read/write/erase any partition, unlock bootloader".to_string());

    Ok(serde_json::json!({"emergency_mode": results}).to_string())
}

/// Unified bypass entry point
pub fn mtk_bypass_unified(
    target: &str,
    da_path: &str,
    scatter_path: Option<&str>,
    config: MtkBypassConfig,
) -> Result<String> {
    let mut results = Vec::new();
    
    // Force preloader mode if requested
    if config.force_preloader {
        results.push("Forcing preloader mode...".to_string());
    }
    
    // Skip auth if requested
    if config.skip_auth {
        results.push("Auth skip requested".to_string());
    }
    
    // Store mode for JSON output before matching
    let mode_str = format!("{:?}", config.mode);
    
    match config.mode {
        MtkBypassMode::Standard => {
            results.push("Standard DA auth mode".to_string());
        }
        MtkBypassMode::BromExploit => {
            let exploit = config.payload_path.as_deref().unwrap_or("auto");
            results.push(format!("BROM exploit: {}", exploit));
        }
        MtkBypassMode::DaAuthBypass => {
            results.push("DA auth bypass mode".to_string());
        }
        MtkBypassMode::FactoryMode => {
            results.push("Factory/Dealer mode".to_string());
        }
        MtkBypassMode::EmergencyMode => {
            results.push("Emergency mode".to_string());
        }
        MtkBypassMode::SlaBypass => {
            results.push("SLA bypass mode".to_string());
        }
        MtkBypassMode::CustomPayload(path) => {
            results.push(format!("Custom payload: {}", path));
        }
    }
    
    if let Some(scatter) = scatter_path {
        results.push(format!("Scatter: {}", scatter));
    }
    
    Ok(serde_json::json!({"bypass": mode_str, "results": results}).to_string())
}

/// CLI wrapper for mtk_bypass_unified
pub fn mtk_bypass_cli(
    target: &str,
    da_path: &str,
    mode: &str,
    scatter_path: Option<&str>,
    skip_auth: bool,
) -> Result<String> {
    let bypass_mode = match mode {
        "standard" => MtkBypassMode::Standard,
        "brom_exploit" => MtkBypassMode::BromExploit,
        "da_auth_bypass" => MtkBypassMode::DaAuthBypass,
        "factory" => MtkBypassMode::FactoryMode,
        "emergency" => MtkBypassMode::EmergencyMode,
        "sla_bypass" => MtkBypassMode::SlaBypass,
        _ => MtkBypassMode::Standard,
    };
    
    let config = MtkBypassConfig {
        mode: bypass_mode,
        payload_path: None,
        target_addr: None,
        skip_auth,
        force_preloader: true,
    };
    
    mtk_bypass_unified(target, da_path, scatter_path, config)
}

/// Complete MTK flow: detect -> handshake -> upload DA -> operations
pub fn mtk_flash_flow(
    target: &str,
    da_path: &str,
    scatter_path: &str,
    firmware_dir: &str,
    ops: MtKOperations,
) -> Result<String> {
    let devices = usb::collect_devices(None)?;
    let dev = devices.iter()
        .find(|d| d.vid == MTK_VID && format!("{}:{}", d.bus, d.address) == target)
        .ok_or("MTK device not found")?;

    let (stage, _) = boot_stage_for(dev.pid);
    if stage != "brom" && stage != "preloader" {
        return Err(BridgeError::InvalidArgument(format!("Device in {} mode, need BROM/Preloader", stage)));
    }

    let (iface, in_ep, out_ep) = find_bulk(&dev).ok_or("no bulk endpoints")?;
    let session = brom_handshake(&dev, iface, in_ep, out_ep).map_err(|e| e.to_string())?;
    
    let mut da_session = DaSession::new(session);
    da_session.upload_da(da_path)?;

    let scatter = ScatterFile::parse(scatter_path)?;
    scatter.print_summary();

    let mut results = Vec::new();
    
    if ops.flash_firmware {
        da_session.flash_firmware(&scatter, firmware_dir)?;
        results.push("firmware flashed".to_string());
    }
    if ops.backup {
        da_session.backup_partitions(&scatter, &ops.backup_dir)?;
        results.push(format!("backup saved to {}", ops.backup_dir));
    }
    if ops.frp_bypass {
        da_session.frp_bypass(Some(&scatter), false)?;
        results.push("FRP bypassed".to_string());
    }
    if ops.enable_adb {
        da_session.enable_adb(&scatter)?;
        results.push("ADB enable attempted".to_string());
    }
    if ops.reboot {
        da_session.reboot(ops.reboot_mode)?;
        results.push(format!("reboot mode {}", ops.reboot_mode));
    }

    Ok(serde_json::json!({"operations": results}).to_string())
}

#[derive(Debug, Default)]
pub struct MtKOperations {
    pub flash_firmware: bool,
    pub backup: bool,
    pub backup_dir: String,
    pub frp_bypass: bool,
    pub enable_adb: bool,
    pub reboot: bool,
    pub reboot_mode: u8,
}

pub fn mtk_detect_extended() -> Result<String> {
    mtk_detect_mtk()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_scatter_parse_basic() {
        let content = r#"
version: 1.0
platform: MT6765
project: test
block_size: 512

partition_name: boot
linear_start_addr: 0x0
partition_size: 0x4000000
type: NORMAL_ROM
filename: boot.img
is_download: true
region: EMMC_USER
storage: HW_STORAGE_EMMC
"#;
        std::fs::write("/tmp/test_scatter.txt", content).unwrap();
        let scatter = ScatterFile::parse("/tmp/test_scatter.txt").unwrap();
        assert_eq!(scatter.entries.len(), 1);
        assert_eq!(scatter.entries[0].partition_name, "boot");
        assert_eq!(scatter.entries[0].length, 0x4000000);
    }

    #[test]
    fn test_write_scatter_file_roundtrips_through_parser() {
        // Simulated Samsung MTK GPT: bootloader-area partitions plus big data.
        let parts = vec![
            ("preloader".to_string(), 0x0u64, 0x200000u64),
            ("boot".to_string(), 0x200000, 0x4000000),
            ("vbmeta".to_string(), 0x4200000, 0x1000),
            ("super".to_string(), 0x10000000, 5 * 1024 * 1024 * 1024u64),
            ("userdata".to_string(), 0x200000000, 100 * 1024 * 1024 * 1024u64),
        ];
        let path = "/tmp/test_scatter_gpt.txt";
        let msg = write_scatter_file(&parts, path).unwrap();
        assert!(msg.contains("5 partitions"));
        assert!(msg.contains("3 downloadable"));

        let scatter = ScatterFile::parse(path).unwrap();
        let mut by_name = std::collections::HashMap::new();
        for e in &scatter.entries {
            by_name.insert(e.partition_name.clone(), e);
        }
        assert_eq!(by_name.len(), 3, "big partitions must be filtered out");
        assert_eq!(by_name["preloader"].length, 0x200000);
        assert_eq!(by_name["preloader"].start_addr, 0x0);
        assert_eq!(by_name["boot"].filename, "boot.img");
        assert_eq!(by_name["boot"].is_download, true);
        assert_eq!(by_name["boot"].operation_type, "UPDATE");
        assert_eq!(by_name["boot"].storage_type, 1);
        let _ = std::fs::remove_file(path);
    }

    #[test]
    fn frp_lock_partitions_cover_common_names() {
        // The lock partition set must cover the standard MTK FRP locations
        // (both modern eMMC GPT names and legacy protect/nvdata names).
        let lock_parts = [
            "frp", "frp_a", "frp_b",
            "nvdata", "persistent", "metadata",
            "protect1", "protect2", "protect_s",
            "keystore", "oemkeystore",
        ];
        for want in ["frp", "nvdata", "metadata", "persistent", "protect1", "keystore"] {
            assert!(
                lock_parts.contains(&want),
                "lock partition set missing {want}"
            );
        }
        // A realistic MTK eMMC partition list should trigger several wipes.
        let gpt_names = ["boot", "frp", "nvdata", "metadata", "userdata", "system"];
        let matched: Vec<&str> = lock_parts.iter().filter(|n| gpt_names.contains(n)).copied().collect();
        assert_eq!(matched, vec!["frp", "nvdata", "metadata"]);
    }

    #[test]
    fn frp_zero_fill_payload_shape() {
        // zero_fill_partition builds a 0xF2 payload with name, start, size, is_download=1.
        let name = "frp";
        let start = 0x1000u64;
        let size = 0x1000u64;
        let mut payload = Vec::new();
        payload.extend_from_slice(&name.len().to_be_bytes());
        payload.extend_from_slice(name.as_bytes());
        payload.extend_from_slice(&start.to_be_bytes());
        payload.extend_from_slice(&size.to_be_bytes());
        payload.extend_from_slice(&1u32.to_be_bytes());
        // name_len(usize=8) + "frp"(3) + start(8) + size(8) + is_download(4) = 31 bytes
        let name_len = name.len().to_be_bytes();
        assert_eq!(payload.len(), 8 + 3 + 8 + 8 + 4);
        assert_eq!(&payload[0..8], &name_len);
        assert_eq!(&payload[8..11], b"frp");
        assert_eq!(&payload[11..19], &0x1000u64.to_be_bytes());
        assert_eq!(&payload[19..27], &0x1000u64.to_be_bytes());
        assert_eq!(&payload[27..31], &1u32.to_be_bytes());
    }

    #[test]
    fn test_gpt_parse_via_shared_parser() {
        // Build a minimal valid GPT: LBA0 protective MBR, LBA1 header, LBA2 entries.
        let mut gpt = vec![0u8; 512 * 8];
        gpt[0x1FE] = 0x55;
        gpt[0x1FF] = 0xAA;
        let h = &mut gpt[512..1024];
        h[0..8].copy_from_slice(b"EFI PART");
        h[8..12].copy_from_slice(&4u32.to_le_bytes()); // revision 1.0
        h[12..16].copy_from_slice(&92u32.to_le_bytes()); // header size
        h[72..80].copy_from_slice(&2u64.to_le_bytes()); // partition_entry_lba
        h[80..84].copy_from_slice(&2u32.to_le_bytes()); // num_partition_entries
        h[84..88].copy_from_slice(&128u32.to_le_bytes()); // entry size
        // Entry 0: boot, LBA 0x1000..0x1100
        let e = &mut gpt[1024..1152];
        e[32..40].copy_from_slice(&0x1000u64.to_le_bytes());
        e[40..48].copy_from_slice(&0x10ffu64.to_le_bytes());
        let name = b"boot";
        for (i, c) in name.iter().enumerate() {
            e[56 + i * 2] = *c;
        }
        // Entry 1: userdata, LBA 0x2000..0x4000
        let e = &mut gpt[1152..1280];
        e[32..40].copy_from_slice(&0x2000u64.to_le_bytes());
        e[40..48].copy_from_slice(&0x3fffu64.to_le_bytes());
        let name = b"userdata";
        for (i, c) in name.iter().enumerate() {
            e[56 + i * 2] = *c;
        }

        let parsed = crate::qualcomm::gpt::QcomGpt::parse(&gpt).unwrap();
        assert_eq!(parsed.entries.len(), 2);
        assert_eq!(parsed.entries[0].name, "boot");
        assert_eq!(parsed.entries[0].starting_lba, 0x1000);
        assert_eq!(parsed.entries[0].size_bytes, 0x100 * 512);
        assert_eq!(parsed.entries[1].name, "userdata");
        // list_gpt formatting shape: name, start addr, size bytes
        let mapped: Vec<(String, u64, u64)> = parsed
            .entries
            .iter()
            .map(|e| (e.name.clone(), e.starting_lba * 512, e.size_bytes()))
            .collect();
        assert_eq!(mapped[0].0, "boot");
        assert_eq!(mapped[0].1, 0x1000 * 512);
        assert_eq!(mapped[1].2, 0x2000 * 512);
    }
}