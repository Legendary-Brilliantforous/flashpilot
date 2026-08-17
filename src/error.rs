//! Unified error handling for the project

use std::fmt;
use serde::Serialize;

/// Main error type for all operations
#[derive(Debug, Serialize)]
pub enum BridgeError {
    /// USB communication errors
    Usb(UsbError),
    /// Protocol-specific errors
    Protocol(ProtocolError),
    /// Configuration errors
    Config(ConfigError),
    /// Firmware/partition errors
    Firmware(FirmwareError),
    /// Authentication/authorization errors
    Auth(AuthError),
    /// Device state errors
    DeviceState(DeviceStateError),
    /// I/O errors
    Io(String),
    /// Invalid argument/usage
    InvalidArgument(String),
    /// Not implemented/unsupported
    NotSupported(String),
    /// Internal/unknown error
    Internal(String),
}

#[derive(Debug, Serialize)]
pub enum UsbError {
    DeviceNotFound,
    PermissionDenied,
    EndpointNotFound,
    TransferFailed(String),
    Timeout,
    DeviceDisconnected,
    KernelDriverActive,
    ClaimInterfaceFailed,
}

#[derive(Debug, Serialize)]
pub enum ProtocolError {
    HandshakeFailed(String),
    CommandFailed { cmd: u8, sub: u8, reason: String },
    UnexpectedResponse(String),
    ChecksumMismatch,
    SequenceError(String),
    SessionEnded,
    UnsupportedCommand,
}

#[derive(Debug, Serialize)]
pub enum ConfigError {
    FileNotFound(String),
    ParseError(String),
    ValidationError(String),
    MissingRequired(String),
}

#[derive(Debug, Serialize)]
pub enum FirmwareError {
    PartitionNotFound(String),
    ImageTooLarge,
    ImageCorrupt(String),
    ScatterParseError(String),
    MismatchedVbmeta,
    VerificationFailed,
}

#[derive(Debug, Serialize)]
pub enum AuthError {
    DAAuthFailed,
    SLAEnabled,
    BootloaderLocked,
    InvalidCredentials,
    ExploitFailed(String),
}

#[derive(Debug, Serialize)]
pub enum DeviceStateError {
    WrongMode { expected: String, actual: String },
    NotInDownloadMode,
    NotInBromMode,
    NotInPreloaderMode,
    DeviceBusy,
    RebootRequired,
}

impl fmt::Display for BridgeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            BridgeError::Usb(e) => write!(f, "USB error: {}", e),
            BridgeError::Protocol(e) => write!(f, "Protocol error: {}", e),
            BridgeError::Config(e) => write!(f, "Config error: {}", e),
            BridgeError::Firmware(e) => write!(f, "Firmware error: {}", e),
            BridgeError::Auth(e) => write!(f, "Auth error: {}", e),
            BridgeError::DeviceState(e) => write!(f, "Device state error: {}", e),
            BridgeError::Io(e) => write!(f, "I/O error: {}", e),
            BridgeError::InvalidArgument(e) => write!(f, "Invalid argument: {}", e),
            BridgeError::NotSupported(e) => write!(f, "Not supported: {}", e),
            BridgeError::Internal(e) => write!(f, "Internal error: {}", e),
        }
    }
}

impl fmt::Display for UsbError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            UsbError::DeviceNotFound => write!(f, "Device not found"),
            UsbError::PermissionDenied => write!(f, "Permission denied"),
            UsbError::EndpointNotFound => write!(f, "Endpoint not found"),
            UsbError::TransferFailed(s) => write!(f, "Transfer failed: {}", s),
            UsbError::Timeout => write!(f, "Timeout"),
            UsbError::DeviceDisconnected => write!(f, "Device disconnected"),
            UsbError::KernelDriverActive => write!(f, "Kernel driver active"),
            UsbError::ClaimInterfaceFailed => write!(f, "Claim interface failed"),
        }
    }
}

impl fmt::Display for ProtocolError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ProtocolError::HandshakeFailed(s) => write!(f, "Handshake failed: {}", s),
            ProtocolError::CommandFailed { cmd, sub, reason } => write!(f, "Command 0x{:02X}/0x{:02X} failed: {}", cmd, sub, reason),
            ProtocolError::UnexpectedResponse(s) => write!(f, "Unexpected response: {}", s),
            ProtocolError::ChecksumMismatch => write!(f, "Checksum mismatch"),
            ProtocolError::SequenceError(s) => write!(f, "Sequence error: {}", s),
            ProtocolError::SessionEnded => write!(f, "Session ended"),
            ProtocolError::UnsupportedCommand => write!(f, "Unsupported command"),
        }
    }
}

impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ConfigError::FileNotFound(s) => write!(f, "File not found: {}", s),
            ConfigError::ParseError(s) => write!(f, "Parse error: {}", s),
            ConfigError::ValidationError(s) => write!(f, "Validation error: {}", s),
            ConfigError::MissingRequired(s) => write!(f, "Missing required: {}", s),
        }
    }
}

impl fmt::Display for FirmwareError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            FirmwareError::PartitionNotFound(s) => write!(f, "Partition not found: {}", s),
            FirmwareError::ImageTooLarge => write!(f, "Image too large"),
            FirmwareError::ImageCorrupt(s) => write!(f, "Image corrupt: {}", s),
            FirmwareError::ScatterParseError(s) => write!(f, "Scatter parse error: {}", s),
            FirmwareError::MismatchedVbmeta => write!(f, "Mismatched vbmeta"),
            FirmwareError::VerificationFailed => write!(f, "Verification failed"),
        }
    }
}

impl fmt::Display for AuthError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AuthError::DAAuthFailed => write!(f, "DA auth failed"),
            AuthError::SLAEnabled => write!(f, "SLA enabled"),
            AuthError::BootloaderLocked => write!(f, "Bootloader locked"),
            AuthError::InvalidCredentials => write!(f, "Invalid credentials"),
            AuthError::ExploitFailed(s) => write!(f, "Exploit failed: {}", s),
        }
    }
}

impl fmt::Display for DeviceStateError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            DeviceStateError::WrongMode { expected, actual } => write!(f, "Wrong mode: expected {}, got {}", expected, actual),
            DeviceStateError::NotInDownloadMode => write!(f, "Not in download mode"),
            DeviceStateError::NotInBromMode => write!(f, "Not in BROM mode"),
            DeviceStateError::NotInPreloaderMode => write!(f, "Not in preloader mode"),
            DeviceStateError::DeviceBusy => write!(f, "Device busy"),
            DeviceStateError::RebootRequired => write!(f, "Reboot required"),
        }
    }
}

impl std::error::Error for BridgeError {}

/// Result type alias
pub type Result<T> = std::result::Result<T, BridgeError>;

// Conversion helpers
impl From<rusb::Error> for BridgeError {
    fn from(e: rusb::Error) -> Self {
        BridgeError::Usb(match e {
            rusb::Error::NotFound => UsbError::DeviceNotFound,
            rusb::Error::Access => UsbError::PermissionDenied,
            rusb::Error::Timeout => UsbError::Timeout,
            rusb::Error::NoDevice => UsbError::DeviceDisconnected,
            rusb::Error::Busy => UsbError::ClaimInterfaceFailed,
            _ => UsbError::TransferFailed(e.to_string()),
        })
    }
}

impl From<std::io::Error> for BridgeError {
    fn from(e: std::io::Error) -> Self {
        BridgeError::Io(e.to_string())
    }
}

impl From<serde_json::Error> for BridgeError {
    fn from(e: serde_json::Error) -> Self {
        BridgeError::Config(ConfigError::ParseError(e.to_string()))
    }
}

impl From<&str> for BridgeError {
    fn from(s: &str) -> Self {
        BridgeError::InvalidArgument(s.to_string())
    }
}

impl From<String> for BridgeError {
    fn from(s: String) -> Self {
        BridgeError::InvalidArgument(s)
    }
}

impl From<BridgeError> for String {
    fn from(e: BridgeError) -> Self {
        e.to_string()
    }
}