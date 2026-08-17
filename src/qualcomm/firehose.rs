//! Qualcomm Firehose Protocol - Flashing Protocol

use crate::error::{Result, BridgeError, ProtocolError};
use crate::usb::UsbDevice;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::Path;
use std::time::Duration;

/// Firehose packet helper
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FirehosePacket {
    pub data: HashMap<String, String>,
}

impl FirehosePacket {
    pub fn new(command: &str) -> Self {
        let mut data = HashMap::new();
        data.insert("command".to_string(), command.to_string());
        data.insert("version".to_string(), "1".to_string());
        Self { data }
    }

    pub fn configure(target: &str, max_payload_from: u32, max_payload_to: u32,
                     memory_name: Option<&str>, physical_partition: u32, verbose: bool) -> Self {
        let mut data = HashMap::new();
        data.insert("command".to_string(), "configure".to_string());
        data.insert("version".to_string(), "1".to_string());
        data.insert("target".to_string(), target.to_string());
        data.insert("MaxPayloadSizeToTargetInBytes".to_string(), max_payload_to.to_string());
        data.insert("MaxPayloadSizeFromTargetInBytes".to_string(), max_payload_from.to_string());
        data.insert("MemoryName".to_string(), memory_name.unwrap_or("emmc").to_string());
        data.insert("PhysicalPartitionNumber".to_string(), physical_partition.to_string());
        data.insert("verbose".to_string(), if verbose { "1" } else { "0" }.to_string());
        Self { data }
    }

    pub fn program(filename: &str, sector_size: u32, num_sectors: u64,
                   start_sector: u64, physical_partition: u32,
                   sparse: bool, sparse_size: Option<u64>, md5: Option<&str>) -> Self {
        let mut data = HashMap::new();
        data.insert("command".to_string(), "program".to_string());
        data.insert("version".to_string(), "1".to_string());
        data.insert("filename".to_string(), filename.to_string());
        data.insert("SECTOR_SIZE_IN_BYTES".to_string(), sector_size.to_string());
        data.insert("num_partition_sectors".to_string(), num_sectors.to_string());
        data.insert("start_sector".to_string(), start_sector.to_string());
        data.insert("physical_partition_number".to_string(), physical_partition.to_string());
        data.insert("sparse".to_string(), if sparse { "true" } else { "false" }.to_string());
        if let Some(s) = sparse_size { data.insert("sparse_size".to_string(), s.to_string()); }
        if let Some(m) = md5 { data.insert("md5".to_string(), m.to_string()); }
        Self { data }
    }

    pub fn read(start_sector: u64, num_sectors: u64, physical_partition: u32, filename: &str) -> Self {
        let mut data = HashMap::new();
        data.insert("command".to_string(), "read".to_string());
        data.insert("version".to_string(), "1".to_string());
        data.insert("start_sector".to_string(), start_sector.to_string());
        data.insert("num_partition_sectors".to_string(), num_sectors.to_string());
        data.insert("physical_partition_number".to_string(), physical_partition.to_string());
        data.insert("filename".to_string(), filename.to_string());
        Self { data }
    }

    pub fn erase(start_sector: u64, num_sectors: u64, physical_partition: u32) -> Self {
        let mut data = HashMap::new();
        data.insert("command".to_string(), "erase".to_string());
        data.insert("version".to_string(), "1".to_string());
        data.insert("start_sector".to_string(), start_sector.to_string());
        data.insert("num_partition_sectors".to_string(), num_sectors.to_string());
        data.insert("physical_partition_number".to_string(), physical_partition.to_string());
        Self { data }
    }

    pub fn get_partition_table(physical_partition: u32) -> Self {
        let mut data = HashMap::new();
        data.insert("command".to_string(), "get_partition_table".to_string());
        data.insert("version".to_string(), "1".to_string());
        data.insert("physical_partition_number".to_string(), physical_partition.to_string());
        Self { data }
    }

    pub fn power(value: &str, delay: Option<u32>) -> Self {
        let mut data = HashMap::new();
        data.insert("command".to_string(), "power".to_string());
        data.insert("version".to_string(), "1".to_string());
        data.insert("value".to_string(), value.to_string());
        if let Some(d) = delay { data.insert("delay".to_string(), d.to_string()); }
        Self { data }
    }

    pub fn reset() -> Self {
        let mut data = HashMap::new();
        data.insert("command".to_string(), "reset".to_string());
        data.insert("version".to_string(), "1".to_string());
        Self { data }
    }

    pub fn to_xml(&self) -> String {
        let mut xml = String::new();
        xml.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
        xml.push_str("<data>\n");
        for (k, v) in &self.data {
            xml.push_str(&format!("  <{} value=\"{}\"/>\n", k, v));
        }
        xml.push_str("</data>\n");
        xml
    }
}

/// Firehose response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FirehoseResponse {
    pub command: String,
    pub version: String,
    pub response: Option<HashMap<String, String>>,
    pub log: Option<String>,
    pub value: Option<String>,
    pub more: Option<String>,
    pub error: Option<String>,
}

impl FirehoseResponse {
    pub fn from_xml(xml: &str) -> Result<Self> {
        use quick_xml::events::Event;
        use quick_xml::Reader;
        
        let mut reader = Reader::from_str(xml);
        reader.trim_text(true);
        let mut data = HashMap::new();
        let mut log = None;
        
        loop {
            match reader.read_event() {
                Ok(Event::Start(ref e)) | Ok(Event::Empty(ref e)) => {
                    let name = String::from_utf8_lossy(e.name().as_ref()).to_string();
                    for attr in e.attributes() {
                        let attr = attr.map_err(|e| crate::error::BridgeError::Protocol(crate::error::ProtocolError::UnexpectedResponse(e.to_string())))?;
                        let key = String::from_utf8_lossy(attr.key.as_ref()).to_string();
                        let value = String::from_utf8_lossy(&attr.value).to_string();
                        data.insert(key, value);
                    }
                }
                Ok(Event::Text(e)) => {
                    let text = e.unescape().map_err(|e| crate::error::BridgeError::Protocol(crate::error::ProtocolError::UnexpectedResponse(e.to_string())))?;
                    if text.trim().starts_with("<log>") {
                        log = Some(text.to_string());
                    }
                }
                Ok(Event::Eof) => break,
                Err(e) => return Err(crate::error::BridgeError::Protocol(crate::error::ProtocolError::UnexpectedResponse(e.to_string()))),
                _ => {}
            }
        }
        
        Ok(Self {
            command: data.remove("command").unwrap_or_default(),
            version: data.remove("version").unwrap_or_default(),
            response: Some(data),
            log,
            value: None,
            more: None,
            error: None,
        })
    }

    pub fn is_success(&self) -> bool {
        self.error.is_none() && self.value.as_deref() != Some("FAIL")
    }

    pub fn get_value(&self, key: &str) -> Option<&String> {
        self.response.as_ref().and_then(|r| r.get(key))
    }
}

/// Firehose session
pub struct FirehoseSession {
    pub device: crate::usb::UsbDevice,
    pub in_ep: u8,
    pub out_ep: u8,
    pub max_payload_from: u32,
    pub max_payload_to: u32,
    pub configured: bool,
    pub sector_size: u32,
    pub physical_partition: u32,
}

impl FirehoseSession {
    pub fn new(mut device: crate::usb::UsbDevice) -> Result<Self> {
        let (in_ep, out_ep) = device.find_bulk_endpoints(0)
            .ok_or_else(|| crate::error::BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
                cmd: 0, sub: 0, reason: "No bulk endpoints".to_string(),
            }))?;

        device.claim_interface(0)?;
        device.set_auto_detach_kernel_driver(true)?;

        Ok(Self {
            device,
            in_ep,
            out_ep,
            max_payload_from: 1024 * 1024,
            max_payload_to: 1024 * 1024,
            configured: false,
            sector_size: 512,
            physical_partition: 0,
        })
    }

    pub fn send_command(&mut self, packet: &FirehosePacket) -> Result<FirehoseResponse> {
        let xml = packet.to_xml();
        self.device.write_bulk(self.out_ep, xml.as_bytes(), std::time::Duration::from_secs(30))?;
        
        let mut buf = vec![0u8; 64 * 1024];
        let n = self.device.read_bulk(self.in_ep, &mut buf, std::time::Duration::from_secs(30))?;
        buf.truncate(n);
        
        let xml_str = String::from_utf8_lossy(&buf).to_string();
        FirehoseResponse::from_xml(&xml_str)
    }

    pub fn configure(&mut self, target: &str, memory_name: Option<&str>) -> Result<()> {
        let packet = FirehosePacket::configure(
            target, self.max_payload_from, self.max_payload_to,
            memory_name, self.physical_partition, true);
        
        let resp = self.send_command(&packet)?;
        if !resp.is_success() {
            return Err(crate::error::BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
                cmd: 0, sub: 0, reason: format!("Configure failed: {:?}", resp.error),
            }));
        }
        
        self.configured = true;
        if let Some(val) = resp.get_value("MaxPayloadSizeToTargetInBytes") {
            self.max_payload_to = val.parse().unwrap_or(self.max_payload_to);
        }
        if let Some(val) = resp.get_value("MaxPayloadSizeFromTargetInBytes") {
            self.max_payload_from = val.parse().unwrap_or(self.max_payload_from);
        }
        if let Some(val) = resp.get_value("SectorSizeInBytes") {
            self.sector_size = val.parse().unwrap_or(self.sector_size);
        }
        Ok(())
    }

    pub fn get_partition_table(&mut self) -> Result<Vec<QcomPartition>> {
        let packet = FirehosePacket::get_partition_table(self.physical_partition);
        let resp = self.send_command(&packet)?;
        
        if !resp.is_success() {
            return Err(crate::error::BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
                cmd: 0, sub: 0, reason: format!("Get partition table failed: {:?}", resp.error),
            }));
        }
        
        self.parse_partition_table(&resp)
    }

    fn parse_partition_table(&self, resp: &FirehoseResponse) -> Result<Vec<QcomPartition>> {
        let mut partitions = Vec::new();
        
        if let Some(log) = &resp.log {
            for line in log.lines() {
                if line.contains("<partition") {
                    if let Some(p) = self.parse_partition_xml(line) {
                        partitions.push(p);
                    }
                }
            }
        }
        
        Ok(partitions)
    }

    fn parse_partition_xml(&self, xml: &str) -> Option<QcomPartition> {
        let mut name = String::new();
        let mut start_sector = 0u64;
        let mut num_sectors = 0u64;
        let mut size = 0u64;
        let mut partition_type = String::new();
        let mut physical_partition = 0u32;
        
        for part in xml.split_whitespace() {
            if let Some((k, v)) = part.split_once('=') {
                let v = v.trim_matches('"');
                match k {
                    "name" => name = v.to_string(),
                    "start_sector" => start_sector = v.parse().unwrap_or(0),
                    "num_partition_sectors" => num_sectors = v.parse().unwrap_or(0),
                    "size_in_bytes" => size = v.parse().unwrap_or(0),
                    "type" => partition_type = v.to_string(),
                    "physical_partition_number" => physical_partition = v.parse().unwrap_or(0),
                    _ => {}
                }
            }
        }
        
        if !name.is_empty() {
            Some(QcomPartition {
                name,
                start_sector,
                num_sectors,
                size,
                partition_type,
                physical_partition,
                sector_size: 512,
            })
        } else {
            None
        }
    }

    pub fn program_partition(&mut self, partition_name: &str, file_path: &std::path::Path, 
                             start_sector: u64, num_sectors: u64) -> Result<()> {
        let file = std::fs::File::open(file_path)?;
        let file_size = file.metadata()?.len();
        
        let packet = crate::qualcomm::firehose::FirehosePacket::program(
            partition_name, 512, num_sectors, start_sector,
            self.physical_partition, false, None, None);
        
        self.send_command(&packet)?;
        self.send_file_data(file, file_size)?;
        Ok(())
    }

    pub fn send_file_data(&mut self, mut file: std::fs::File, file_size: u64) -> Result<()> {
        let mut buffer = vec![0u8; self.max_payload_to as usize];
        let mut total_sent = 0u64;
        
        use std::io::Read;
        
        while total_sent < file_size {
            let chunk_size = std::cmp::min(self.max_payload_to as usize, (file_size - total_sent) as usize);
            let n = file.read(&mut buffer[..chunk_size])?;
            if n == 0 { break; }
            
            self.device.write_bulk(self.out_ep, &buffer[..n], std::time::Duration::from_secs(30))?;
            total_sent += n as u64;
        }
        
        // Read final response
        let mut buf = vec![0u8; 4096];
        let n = self.device.read_bulk(self.in_ep, &mut buf, std::time::Duration::from_secs(30))?;
        buf.truncate(n);
        
        let xml_str = String::from_utf8_lossy(&buf).to_string();
        let resp = FirehoseResponse::from_xml(&xml_str)?;
        
        if !resp.is_success() {
            return Err(crate::error::BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
                cmd: 0, sub: 0, reason: format!("File data transfer failed: {:?}", resp.error),
            }));
        }
        
        Ok(())
    }

    pub fn read_partition(&mut self, partition_name: &str, output_path: &std::path::Path, 
                          start_sector: u64, num_sectors: u64) -> Result<()> {
        let packet = crate::qualcomm::firehose::FirehosePacket::read(
            start_sector, num_sectors, self.physical_partition, partition_name);
        let resp = self.send_command(&packet)?;
        
        if !resp.is_success() {
            return Err(crate::error::BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
                cmd: 0, sub: 0, reason: format!("Read command failed: {:?}", resp.error),
            }));
        }
        
        let mut file = std::fs::File::create(output_path)?;
        let expected_size = num_sectors * self.sector_size as u64;
        let mut total_received = 0u64;
        let mut buffer = vec![0u8; self.max_payload_from as usize];
        
        while total_received < expected_size {
            let chunk_size = std::cmp::min(self.max_payload_from as usize, (expected_size - total_received) as usize);
            let n = self.device.read_bulk(self.in_ep, &mut buffer[..chunk_size], std::time::Duration::from_secs(30))?;
            if n == 0 { break; }
            
            use std::io::Write;
            file.write_all(&buffer[..n])?;
            total_received += n as u64;
        }
        
        Ok(())
    }

    pub fn erase_partition(&mut self, start_sector: u64, num_sectors: u64) -> Result<()> {
        let packet = FirehosePacket::erase(start_sector, num_sectors, self.physical_partition);
        let resp = self.send_command(&packet)?;
        
        if !resp.is_success() {
            return Err(crate::error::BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
                cmd: 0, sub: 0, reason: format!("Erase failed: {:?}", resp.error),
            }));
        }
        Ok(())
    }

    pub fn reboot(&mut self, mode: &str) -> Result<()> {
        let packet = FirehosePacket::power(mode, Some(100));
        let resp = self.send_command(&packet)?;
        
        if !resp.is_success() {
            return Err(crate::error::BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
                cmd: 0, sub: 0, reason: format!("Power command failed: {:?}", resp.error),
            }));
        }
        Ok(())
    }

    pub fn reset(&mut self) -> Result<()> {
        let packet = FirehosePacket::reset();
        let resp = self.send_command(&packet)?;
        
        if !resp.is_success() {
            return Err(crate::error::BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
                cmd: 0, sub: 0, reason: format!("Reset failed: {:?}", resp.error),
            }));
        }
        Ok(())
    }
}

/// Qualcomm partition information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QcomPartition {
    pub name: String,
    pub start_sector: u64,
    pub num_sectors: u64,
    pub size: u64,
    pub partition_type: String,
    pub physical_partition: u32,
    pub sector_size: u32,
}

impl QcomPartition {
    pub fn size_bytes(&self) -> u64 {
        if self.size > 0 { self.size } else { self.num_sectors * self.sector_size as u64 }
    }
}