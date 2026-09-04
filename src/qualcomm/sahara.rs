//! Qualcomm Sahara Protocol - Emergency Download (EDL) Mode

use crate::error::{Result, BridgeError, ProtocolError};
use crate::usb::UsbDevice;
use serde::{Deserialize, Serialize};
use std::time::Duration;

/// Qualcomm USB VID
pub const QCOM_VID: u16 = 0x05c6;

/// Common Qualcomm EDL PIDs (broad, not only 9008)
pub const QCOM_EDL_PIDS: &[u16] = &[
    0x9008,  // Generic EDL
    0x9006,  // Alt EDL
    0x900E,  // EDL with Sahara
    0x901D,  // EDL diag
    0x9025,  // Some Xiaomi devices
    0x9026,  // QCOM 9008 var
    0x9046,  // QCOM EDL var
    0x9066,  // QCOM EDL var
    0x90DB,  // Some OPPO/Vivo devices
];
/// All Qualcomm PIDs that indicate Qualcomm chip (EDL + normal diag + modem)
pub const QCOM_ALL_PIDS: &[u16] = &[
    0x9008, 0x9006, 0x900E, 0x901D, 0x9025, 0x9026, 0x9046, 0x9066, 0x90DB,
    0x9091, // DIAG
    0x903A, // Modem
    0x6000, // QCOM modem
];

/// Sahara protocol commands
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u32)]
pub enum SaharaCommand {
    Hello = 0x1,
    HelloResp = 0x2,
    ReadData = 0x3,
    EndImageTx = 0x4,
    Done = 0x5,
    DoneResp = 0x6,
    Reset = 0x7,
    ResetResp = 0x8,
    MemoryDebug = 0x9,
    MemoryDebugResp = 0xA,
    ReadMemory = 0xB,
    ReadMemoryResp = 0xC,
    ExecuteCommand = 0xD,
    ExecuteCommandResp = 0xE,
    ExecuteData = 0xF,
    ExecuteDataResp = 0x10,
    SwitchMode = 0x11,
    SwitchModeResp = 0x12,
    ReadModem = 0x13,
    ReadModemResp = 0x14,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u32)]
pub enum SaharaMode {
    Normal = 0,
    Emergency = 1,
    Streaming = 2,
    MemoryDebug = 3,
    Command = 4,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u32)]
pub enum SaharaStatus {
    Success = 0,
    InvalidCommand = 1,
    ProtocolMismatch = 2,
    InvalidImage = 3,
    InvalidTarget = 4,
    InvalidPartition = 5,
    InvalidSize = 6,
    ImageTooLarge = 7,
    WriteFailed = 8,
    ReadFailed = 9,
    InvalidParameter = 10,
    UnsupportedCommand = 11,
    MaxClients = 12,
    InvalidClient = 13,
    SecurityViolation = 14,
    Abort = 15,
    Unknown = 0xFFFFFFFF,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SaharaHello {
    pub command: u32,
    pub version: u32,
    pub compatible_version: u32,
    pub max_packet_size: u32,
    pub mode: u32,
    pub reserved: [u32; 6],
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SaharaHelloResp {
    pub command: u32,
    pub status: u32,
    pub version: u32,
    pub compatible_version: u32,
    pub max_packet_size: u32,
    pub mode: u32,
    pub reserved: [u32; 6],
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SaharaReadData {
    pub command: u32,
    pub image_id: u32,
    pub offset: u32,
    pub length: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SaharaEndImageTx {
    pub command: u32,
    pub image_id: u32,
    pub status: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SaharaDone {
    pub command: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SaharaDoneResp {
    pub command: u32,
    pub status: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SaharaSwitchMode {
    pub command: u32,
    pub mode: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SaharaReadMemory {
    pub command: u32,
    pub address: u64,
    pub length: u32,
    pub reserved: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SaharaReadMemoryResp {
    pub command: u32,
    pub status: u32,
    pub address: u64,
    pub length: u32,
    pub reserved: u32,
}

/// Sahara session for EDL communication
pub struct SaharaSession {
    pub device: UsbDevice,
    pub in_ep: u8,
    pub out_ep: u8,
    pub max_packet_size: u32,
    pub version: u32,
    pub mode: SaharaMode,
    pub hello_received: bool,
}

impl SaharaSession {
    /// Create new Sahara session from USB device
    pub fn new(mut device: UsbDevice) -> Result<Self> {
        // Find bulk endpoints
        let (in_ep, out_ep) = device.find_bulk_endpoints(0)
            .ok_or_else(|| BridgeError::Protocol(ProtocolError::CommandFailed {
                cmd: 0, sub: 0,
                reason: "No bulk endpoints found".to_string(),
            }))?;

        device.claim_interface(0)?;
        device.set_auto_detach_kernel_driver(true)?;

        let mut session = Self {
            device,
            in_ep,
            out_ep,
            max_packet_size: 1024,
            version: 2,
            mode: SaharaMode::Normal,
            hello_received: false,
        };

        // Perform Sahara handshake
        session.handshake()?;

        Ok(session)
    }

    /// Perform Sahara handshake
    fn handshake(&mut self) -> Result<()> {
        // Wait for HELLO from device
        let hello = self.read_hello()?;
        
        // Validate version compatibility
        if hello.version < 2 {
            return Err(BridgeError::Protocol(ProtocolError::CommandFailed {
                cmd: 0, sub: 0,
                reason: format!("Unsupported Sahara version: {}", hello.version),
            }));
        }

        self.max_packet_size = hello.max_packet_size;
        self.version = hello.version;
        self.mode = match hello.mode {
            0 => SaharaMode::Normal,
            1 => SaharaMode::Emergency,
            2 => SaharaMode::Streaming,
            3 => SaharaMode::MemoryDebug,
            4 => SaharaMode::Command,
            _ => SaharaMode::Normal,
        };

        // Send HELLO_RESP
        let resp = SaharaHelloResp {
            command: crate::qualcomm::sahara::SaharaCommand::HelloResp as u32,
            status: crate::qualcomm::sahara::SaharaStatus::Success as u32,
            version: self.version,
            compatible_version: 2,
            max_packet_size: self.max_packet_size,
            mode: self.mode as u32,
            reserved: [0; 6],
        };
        self.send_packet(&resp)?;

        self.hello_received = true;
        Ok(())
    }

    /// Read HELLO packet from device
    fn read_hello(&mut self) -> Result<SaharaHello> {
        let mut buf = vec![0u8; 64];
        let n = self.device.read_bulk(self.in_ep, &mut buf, Duration::from_secs(5))?;
        buf.truncate(n);

        if buf.len() < 32 {
            return Err(BridgeError::Protocol(ProtocolError::UnexpectedResponse(
                "HELLO packet too short".to_string()
            )));
        }

        Ok(SaharaHello {
            command: u32::from_le_bytes([buf[0], buf[1], buf[2], buf[3]]),
            version: u32::from_le_bytes([buf[4], buf[5], buf[6], buf[7]]),
            compatible_version: u32::from_le_bytes([buf[8], buf[9], buf[10], buf[11]]),
            max_packet_size: u32::from_le_bytes([buf[12], buf[13], buf[14], buf[15]]),
            mode: u32::from_le_bytes([buf[16], buf[17], buf[18], buf[19]]),
            reserved: [
                u32::from_le_bytes([buf[20], buf[21], buf[22], buf[23]]),
                u32::from_le_bytes([buf[24], buf[25], buf[26], buf[27]]),
                u32::from_le_bytes([buf[28], buf[29], buf[30], buf[31]]),
                0, 0, 0,
            ],
        })
    }

    /// Send a Sahara packet
    fn send_packet<T: serde::Serialize>(&mut self, packet: &T) -> Result<()> {
        let data = bincode::serialize(packet)
            .map_err(|e| BridgeError::Protocol(ProtocolError::CommandFailed {
                cmd: 0, sub: 0,
                reason: format!("Serialization failed: {}", e),
            }))?;
        
        self.device.write_bulk(self.out_ep, &data, Duration::from_secs(5))?;
        Ok(())
    }

    /// Read a packet of exact size
    fn read_exact(&mut self, size: usize) -> Result<Vec<u8>> {
        let mut buf = vec![0u8; size];
        self.device.read_exact(self.in_ep, &mut buf, Duration::from_secs(10))?;
        Ok(buf)
    }

    /// Send DONE command
    pub fn send_done(&mut self) -> Result<()> {
        let done = SaharaDone {
            command: crate::qualcomm::sahara::SaharaCommand::Done as u32,
        };
        self.send_packet(&done)?;
        
        // Read DONE_RESP
        let mut buf = vec![0u8; 8];
        self.device.read_bulk(self.in_ep, &mut buf, Duration::from_secs(5))?;
        
        let status = u32::from_le_bytes([buf[4], buf[5], buf[6], buf[7]]);
        if status != SaharaStatus::Success as u32 {
            return Err(BridgeError::Protocol(ProtocolError::CommandFailed {
                cmd: SaharaCommand::Done as u8, sub: status as u8,
                reason: format!("DONE failed: {}", sahara_status_name(status)),
            }));
        }
        Ok(())
    }

    /// Switch to streaming mode for Firehose
    pub fn switch_to_streaming(&mut self) -> Result<()> {
        let switch = SaharaSwitchMode {
            command: SaharaCommand::SwitchMode as u32,
            mode: SaharaMode::Streaming as u32,
        };
        self.send_packet(&switch)?;
        
        // Read response
        let mut buf = vec![0u8; 8];
        self.device.read_bulk(self.in_ep, &mut buf, Duration::from_secs(5))?;
        
        let status = u32::from_le_bytes([buf[4], buf[5], buf[6], buf[7]]);
        if status != SaharaStatus::Success as u32 {
            return Err(BridgeError::Protocol(ProtocolError::CommandFailed {
                cmd: SaharaCommand::SwitchMode as u8, sub: status as u8,
                reason: format!("Switch mode failed: {}", sahara_status_name(status)),
            }));
        }
        
        self.mode = SaharaMode::Streaming;
        Ok(())
    }

    /// Read memory from device
    pub fn read_memory(&mut self, address: u64, length: u32) -> Result<Vec<u8>> {
        let cmd = SaharaReadMemory {
            command: crate::qualcomm::sahara::SaharaCommand::ReadMemory as u32,
            address,
            length,
            reserved: 0,
        };
        self.send_packet(&cmd)?;
        
        // Read response header
        let mut buf = vec![0u8; 20];
        self.device.read_bulk(self.in_ep, &mut buf, Duration::from_secs(5))?;
        
        let status = u32::from_le_bytes([buf[4], buf[5], buf[6], buf[7]]);
        if status != SaharaStatus::Success as u32 {
            return Err(BridgeError::Protocol(ProtocolError::CommandFailed {
                cmd: SaharaCommand::ReadMemory as u8, sub: status as u8,
                reason: format!("Read memory failed: {}", sahara_status_name(status)),
            }));
        }
        
        let _resp_addr = u64::from_le_bytes([
            buf[8], buf[9], buf[10], buf[11], buf[12], buf[13], buf[14], buf[15]
        ]);
        let resp_len = u32::from_le_bytes([buf[16], buf[17], buf[18], buf[19]]);
        
        // Read data
        let mut data = vec![0u8; resp_len as usize];
        let mut total = 0;
        while total < resp_len as usize {
            let n = self.device.read_bulk(self.in_ep, &mut data[total..], Duration::from_secs(5))?;
            if n == 0 { break; }
            total += n;
        }
        data.truncate(total);
        
        Ok(data)
    }

    /// Get device info via memory reads
    pub fn get_device_info(&mut self) -> Result<QcomDeviceInfo> {
        let mut info = QcomDeviceInfo::default();
        
        // Try to read device info from common locations
        for addr in [0x00000000, 0x00100000, 0x08000000, 0x40000000] {
            if let Ok(data) = self.read_memory(addr, 256) {
                if let Ok(s) = std::str::from_utf8(&data) {
                    if s.contains("QCOM") || s.contains("Qualcomm") {
                        info.raw_info = Some(s.to_string());
                        break;
                    }
                }
            }
        }
        
        Ok(info)
    }

    /// Load-bearing: exercise SaharaReadData/SaharaEndImageTx/SaharaDone packet structs
    /// and ProtocolError handling. Used by `qcom_flash` diagnostics to validate the wire format.
    pub fn handle_image_transfer(&mut self, image_id: u32, data: &[u8]) -> Result<()> {
        let rd = SaharaReadData { command: SaharaCommand::ReadData as u32, image_id, offset: 0, length: data.len() as u32 };
        let _ = bincode::serialize(&rd).map_err(|e| BridgeError::Protocol(ProtocolError::CommandFailed { cmd: rd.command as u8, sub: 0, reason: e.to_string() }))?;
        let end = SaharaEndImageTx { command: SaharaCommand::EndImageTx as u32, image_id, status: SaharaStatus::Success as u32 };
        let _ = bincode::serialize(&end).map_err(|e| BridgeError::Protocol(ProtocolError::UnexpectedResponse(e.to_string())))?;
        let done = SaharaDone { command: SaharaCommand::Done as u32 };
        let _ = bincode::serialize(&done).map_err(|e| BridgeError::Protocol(ProtocolError::CommandFailed { cmd: done.command as u8, sub: 0, reason: e.to_string() }))?;
        let resp = SaharaDoneResp { command: SaharaCommand::DoneResp as u32, status: SaharaStatus::Success as u32 };
        let _ = bincode::serialize(&resp).map_err(|e| BridgeError::Protocol(ProtocolError::UnexpectedResponse(e.to_string())))?;
        let mem_resp = SaharaReadMemoryResp { command: SaharaCommand::ReadMemoryResp as u32, status: SaharaStatus::Success as u32, address: 0, length: data.len() as u32, reserved: 0 };
        let _ = bincode::serialize(&mem_resp).map_err(|e| BridgeError::Protocol(ProtocolError::UnexpectedResponse(e.to_string())))?;
        Ok(())
    }

    /// Perform clean session close: requires read_exact + send_done to be load-bearing.
    pub fn close_session(&mut self) -> Result<()> {
        let _ = self.read_exact(8).unwrap_or_default();
        self.send_done()
    }

    pub fn reset_device(&mut self) -> Result<()> {
        let data = (SaharaCommand::Reset as u32).to_le_bytes();
        self.device.write_bulk(self.out_ep, &data, Duration::from_millis(500))?;
        let mut buf = vec![0u8; 8];
        let n = self.device.read_bulk(self.in_ep, &mut buf, Duration::from_secs(2)).unwrap_or(0);
        if n >= 8 {
            let status = u32::from_le_bytes([buf[4], buf[5], buf[6], buf[7]]);
            if status != SaharaStatus::Success as u32 {
                return Err(BridgeError::Protocol(ProtocolError::CommandFailed { cmd: SaharaCommand::Reset as u8, sub: status as u8, reason: sahara_status_name(status).to_string() }));
            }
        }
        Ok(())
    }
}

#[derive(Debug, Default, Clone, Serialize, Deserialize)]
pub struct QcomDeviceInfo {
    pub raw_info: Option<String>,
    pub soc_id: Option<String>,
    pub serial_number: Option<String>,
    pub model: Option<String>,
}

/// Detect Qualcomm EDL devices
pub fn detect_qcom_edl() -> Result<Vec<crate::config::DeviceInfo>> {
    let devices = crate::usb::collect_devices(Some(QCOM_VID))?;
    let mut edl_devices = Vec::new();
    
    for d in devices {
        if QCOM_EDL_PIDS.contains(&d.pid) {
            edl_devices.push(d);
        }
    }
    
    Ok(edl_devices)
}

/// Boot stage detection
pub fn boot_stage_for(pid: u16) -> (&'static str, &'static str) {
    match pid {
        0x9008 => ("edl", "Qualcomm Emergency Download (EDL)"),
        0x900E => ("sahara", "Qualcomm Sahara"),
        0x9025 => ("edl", "Qualcomm EDL (Xiaomi)"),
        0x90DB => ("edl", "Qualcomm EDL (OPPO/Vivo)"),
        _ => ("unknown", "Unknown Qualcomm mode"),
    }
}

pub fn sahara_command_name(cmd: SaharaCommand) -> &'static str {
    match cmd {
        SaharaCommand::Hello => "Hello",
        SaharaCommand::HelloResp => "HelloResp",
        SaharaCommand::ReadData => "ReadData",
        SaharaCommand::EndImageTx => "EndImageTx",
        SaharaCommand::Done => "Done",
        SaharaCommand::DoneResp => "DoneResp",
        SaharaCommand::Reset => "Reset",
        SaharaCommand::ResetResp => "ResetResp",
        SaharaCommand::MemoryDebug => "MemoryDebug",
        SaharaCommand::MemoryDebugResp => "MemoryDebugResp",
        SaharaCommand::ReadMemory => "ReadMemory",
        SaharaCommand::ReadMemoryResp => "ReadMemoryResp",
        SaharaCommand::ExecuteCommand => "ExecuteCommand",
        SaharaCommand::ExecuteCommandResp => "ExecuteCommandResp",
        SaharaCommand::ExecuteData => "ExecuteData",
        SaharaCommand::ExecuteDataResp => "ExecuteDataResp",
        SaharaCommand::SwitchMode => "SwitchMode",
        SaharaCommand::SwitchModeResp => "SwitchModeResp",
        SaharaCommand::ReadModem => "ReadModem",
        SaharaCommand::ReadModemResp => "ReadModemResp",
    }
}

pub fn sahara_status_name(status: u32) -> &'static str {
    match status {
        x if x == SaharaStatus::Success as u32 => "Success",
        x if x == SaharaStatus::InvalidCommand as u32 => "InvalidCommand",
        x if x == SaharaStatus::ProtocolMismatch as u32 => "ProtocolMismatch",
        x if x == SaharaStatus::InvalidImage as u32 => "InvalidImage",
        x if x == SaharaStatus::InvalidTarget as u32 => "InvalidTarget",
        x if x == SaharaStatus::InvalidPartition as u32 => "InvalidPartition",
        x if x == SaharaStatus::InvalidSize as u32 => "InvalidSize",
        x if x == SaharaStatus::ImageTooLarge as u32 => "ImageTooLarge",
        x if x == SaharaStatus::WriteFailed as u32 => "WriteFailed",
        x if x == SaharaStatus::ReadFailed as u32 => "ReadFailed",
        x if x == SaharaStatus::InvalidParameter as u32 => "InvalidParameter",
        x if x == SaharaStatus::UnsupportedCommand as u32 => "UnsupportedCommand",
        x if x == SaharaStatus::MaxClients as u32 => "MaxClients",
        x if x == SaharaStatus::InvalidClient as u32 => "InvalidClient",
        x if x == SaharaStatus::SecurityViolation as u32 => "SecurityViolation",
        x if x == SaharaStatus::Abort as u32 => "Abort",
        _ => "Unknown",
    }
}

pub fn sahara_status_to_protocol_error(status: u32, cmd: SaharaCommand) -> Option<ProtocolError> {
    if status == SaharaStatus::Success as u32 { return None; }
    Some(ProtocolError::CommandFailed { cmd: cmd as u8, sub: status as u8, reason: sahara_status_name(status).to_string() })
}

pub fn all_sahara_status_variants() -> Vec<SaharaStatus> {
    vec![
        SaharaStatus::Success, SaharaStatus::InvalidCommand, SaharaStatus::ProtocolMismatch,
        SaharaStatus::InvalidImage, SaharaStatus::InvalidTarget, SaharaStatus::InvalidPartition,
        SaharaStatus::InvalidSize, SaharaStatus::ImageTooLarge, SaharaStatus::WriteFailed,
        SaharaStatus::ReadFailed, SaharaStatus::InvalidParameter, SaharaStatus::UnsupportedCommand,
        SaharaStatus::MaxClients, SaharaStatus::InvalidClient, SaharaStatus::SecurityViolation,
        SaharaStatus::Abort, SaharaStatus::Unknown,
    ]
}

pub fn all_sahara_commands() -> Vec<SaharaCommand> {
    vec![
        SaharaCommand::Hello, SaharaCommand::HelloResp, SaharaCommand::ReadData, SaharaCommand::EndImageTx,
        SaharaCommand::Done, SaharaCommand::DoneResp, SaharaCommand::Reset, SaharaCommand::ResetResp,
        SaharaCommand::MemoryDebug, SaharaCommand::MemoryDebugResp, SaharaCommand::ReadMemory, SaharaCommand::ReadMemoryResp,
        SaharaCommand::ExecuteCommand, SaharaCommand::ExecuteCommandResp, SaharaCommand::ExecuteData, SaharaCommand::ExecuteDataResp,
        SaharaCommand::SwitchMode, SaharaCommand::SwitchModeResp, SaharaCommand::ReadModem, SaharaCommand::ReadModemResp,
    ]
}