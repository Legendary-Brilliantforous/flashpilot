//! Qualcomm GPT (GUID Partition Table) parsing

use crate::error::{Result, BridgeError, FirmwareError};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GptHeader {
    pub signature: [u8; 8],
    pub revision: u32,
    pub header_size: u32,
    pub header_crc32: u32,
    pub reserved: u32,
    pub current_lba: u64,
    pub backup_lba: u64,
    pub first_usable_lba: u64,
    pub last_usable_lba: u64,
    pub disk_guid: [u8; 16],
    pub partition_entry_lba: u64,
    pub num_partition_entries: u32,
    pub partition_entry_size: u32,
    pub partition_entry_array_crc32: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GptPartition {
    pub partition_type_guid: String,
    pub unique_partition_guid: String,
    pub starting_lba: u64,
    pub ending_lba: u64,
    pub attributes: u64,
    pub name: String,
    pub size_bytes: u64,
}

impl GptPartition {
    pub fn size_bytes(&self) -> u64 {
        self.size_bytes
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QcomGpt {
    pub header: GptHeader,
    pub entries: Vec<GptPartition>,
}

impl QcomGpt {
    pub fn parse(data: &[u8]) -> Result<Self> {
        if data.len() < 512 {
            return Err(BridgeError::Firmware(FirmwareError::ScatterParseError(
                "GPT data too small".to_string()
            )));
        }
        
        let header = Self::parse_header(&data[512..1024])?;
        let entry_size = header.partition_entry_size as usize;
        let num_entries = header.num_partition_entries as usize;
        let entries_offset = (header.partition_entry_lba * 512) as usize;
        
        let entries_data = if entries_offset + num_entries * entry_size <= data.len() {
            &data[entries_offset..]
        } else {
            return Err(BridgeError::Firmware(FirmwareError::ScatterParseError(
                "GPT entries exceed data".to_string()
            )));
        };
        
        let mut entries = Vec::new();
        for i in 0..num_entries {
            let entry_start = i * entry_size;
            let entry_end = entry_start + 128;
            if entry_end <= entries_data.len() {
                if let Ok(entry) = Self::parse_entry(&entries_data[entry_start..entry_end]) {
                    if entry.size_bytes() > 0 {
                        entries.push(entry);
                    }
                }
            }
        }
        
        Ok(QcomGpt { header, entries })
    }
    
    fn parse_header(data: &[u8]) -> Result<GptHeader> {
        if data.len() < 92 {
            return Err(BridgeError::Firmware(FirmwareError::ScatterParseError(
                "GPT header too small".to_string()
            )));
        }
        
        if &data[0..8] != b"EFI PART" {
            return Err(BridgeError::Firmware(FirmwareError::ScatterParseError(
                "Invalid GPT signature".to_string()
            )));
        }
        
        Ok(GptHeader {
            signature: data[0..8].try_into().unwrap(),
            revision: u32::from_le_bytes([data[8], data[9], data[10], data[11]]),
            header_size: u32::from_le_bytes([data[12], data[13], data[14], data[15]]),
            header_crc32: u32::from_le_bytes([data[16], data[17], data[18], data[19]]),
            reserved: u32::from_le_bytes([data[20], data[21], data[22], data[23]]),
            current_lba: u64::from_le_bytes(data[24..32].try_into().unwrap()),
            backup_lba: u64::from_le_bytes(data[32..40].try_into().unwrap()),
            first_usable_lba: u64::from_le_bytes(data[40..48].try_into().unwrap()),
            last_usable_lba: u64::from_le_bytes(data[48..56].try_into().unwrap()),
            disk_guid: data[56..72].try_into().unwrap(),
            partition_entry_lba: u64::from_le_bytes(data[72..80].try_into().unwrap()),
            num_partition_entries: u32::from_le_bytes([data[80], data[81], data[82], data[83]]),
            partition_entry_size: u32::from_le_bytes([data[84], data[85], data[86], data[87]]),
            partition_entry_array_crc32: u32::from_le_bytes([data[88], data[89], data[90], data[91]]),
        })
    }
    
    fn parse_entry(data: &[u8]) -> Result<GptPartition> {
        if data.len() < 128 {
            return Err(BridgeError::Firmware(FirmwareError::ScatterParseError(
                "GPT entry too small".to_string()
            )));
        }
        
        let starting_lba = u64::from_le_bytes(data[32..40].try_into().unwrap());
        let ending_lba = u64::from_le_bytes(data[40..48].try_into().unwrap());
        let attributes = u64::from_le_bytes(data[48..56].try_into().unwrap());
        
        // UTF-16 name
        let name = String::from_utf16_lossy(
            &data[56..128].chunks(2)
                .map(|c| u16::from_le_bytes([c[0], c[1]]))
                .collect::<Vec<_>>()
        ).trim_end_matches('\0').to_string();
        
        let size_bytes = (ending_lba.saturating_sub(starting_lba) + 1) * 512;
        
        Ok(GptPartition {
            partition_type_guid: Self::guid_to_string(&data[0..16]),
            unique_partition_guid: Self::guid_to_string(&data[16..32]),
            starting_lba,
            ending_lba,
            attributes,
            name,
            size_bytes,
        })
    }
    
    fn guid_to_string(bytes: &[u8]) -> String {
        if bytes.len() != 16 { return String::new(); }
        let mut s = String::with_capacity(36);
        // Standard GUID format: 8-4-4-4-12
        let groups = [(0, 4), (4, 2), (6, 2), (8, 2), (10, 6)];
        for (idx, &(start, len)) in groups.iter().enumerate() {
            if idx > 0 { s.push('-'); }
            for j in 0..len {
                let idx = start + len - 1 - j;
                s.push_str(&format!("{:02x}", bytes[idx]));
            }
        }
        s
    }
    
    pub fn find_partition(&self, name: &str) -> Option<&GptPartition> {
        self.entries.iter().find(|e| e.name == name)
    }
}