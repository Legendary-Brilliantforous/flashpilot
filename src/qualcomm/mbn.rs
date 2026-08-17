//! Qualcomm MBN (Multi Boot Image) parsing

use crate::error::{Result, BridgeError, FirmwareError};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MbnHeader {
    pub magic: [u8; 4],
    pub version: u32,
    pub header_size: u32,
    pub image_src: u32,
    pub image_dest_ptr: u32,
    pub image_size: u32,
    pub code_size: u32,
    pub signature_size: u32,
    pub cert_chain_size: u32,
    pub reserved: [u32; 4],
    pub hash: [u8; 32],
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MbnImage {
    pub header: MbnHeader,
    pub image_data: Vec<u8>,
    pub signature: Vec<u8>,
    pub cert_chain: Vec<u8>,
    pub image_type: MbnImageType,
    pub device_model: Option<String>,
    pub version: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MbnImageType {
    Unknown,
    Xbl, ABl, Tz, Hyp, Devcfg, Keymaster, Cmnlib, Cmnlib64, Keymaster64,
    Dsp, Modem, Boot, Recovery, Dtbo, Vbmeta, VbmetaSystem, VbmetaVendor,
    Super, Logo, Mdtp, Featenabler, Multiimgoem, Multiimgqti,
}

impl MbnImageType {
    pub fn from_name(name: &str) -> Self {
        match name.to_lowercase().as_str() {
            "xbl" => Self::Xbl, "abl" => Self::ABl, "tz" => Self::Tz,
            "hyp" => Self::Hyp, "devcfg" => Self::Devcfg, "keymaster" => Self::Keymaster,
            "cmnlib" => Self::Cmnlib, "cmnlib64" => Self::Cmnlib64, "keymaster64" => Self::Keymaster64,
            "dsp" => Self::Dsp, "modem" => Self::Modem, "boot" => Self::Boot,
            "recovery" => Self::Recovery, "dtbo" => Self::Dtbo, "vbmeta" => Self::Vbmeta,
            "vbmeta_system" => Self::VbmetaSystem, "vbmeta_vendor" => Self::VbmetaVendor,
            "super" => Self::Super, "logo" => Self::Logo, "mdtp" => Self::Mdtp,
            "featenabler" => Self::Featenabler, "multiimgoem" => Self::Multiimgoem,
            "multiimgqti" => Self::Multiimgqti, _ => Self::Unknown,
        }
    }
    
    pub fn to_str(&self) -> &'static str {
        match self {
            Self::Xbl => "xbl", Self::ABl => "abl", Self::Tz => "tz",
            Self::Hyp => "hyp", Self::Devcfg => "devcfg", Self::Keymaster => "keymaster",
            Self::Cmnlib => "cmnlib", Self::Cmnlib64 => "cmnlib64", Self::Keymaster64 => "keymaster64",
            Self::Dsp => "dsp", Self::Modem => "modem", Self::Boot => "boot",
            Self::Recovery => "recovery", Self::Dtbo => "dtbo", Self::Vbmeta => "vbmeta",
            Self::VbmetaSystem => "vbmeta_system", Self::VbmetaVendor => "vbmeta_vendor",
            Self::Super => "super", Self::Logo => "logo", Self::Mdtp => "mdtp",
            Self::Featenabler => "featenabler", Self::Multiimgoem => "multiimgoem",
            Self::Multiimgqti => "multiimgqti", _ => "unknown",
        }
    }
    
    pub fn detect_type_from_filename(filename: &str) -> Self {
        let name = std::path::Path::new(filename)
            .file_stem().and_then(|s| s.to_str()).unwrap_or("");
        Self::from_name(name)
    }
}

impl std::fmt::Display for MbnImageType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.to_str())
    }
}

impl MbnImage {
    pub fn parse(data: &[u8]) -> Result<Self> {
        if data.len() < 64 {
            return Err(BridgeError::Firmware(crate::error::FirmwareError::ScatterParseError(
                "MBN too small".to_string()
            )));
        }
        
        let header = Self::parse_header(data)?;
        let header_size = header.header_size as usize;
        let image_size = header.image_size as usize;
        let signature_size = header.signature_size as usize;
        let cert_chain_size = header.cert_chain_size as usize;
        
        let expected_total = header_size + image_size + signature_size + cert_chain_size;
        if data.len() < expected_total {
            return Err(BridgeError::Firmware(FirmwareError::ScatterParseError(
                format!("MBN data too small: {} < {}", data.len(), expected_total)
            )));
        }
        
        let image_data = data[header_size..header_size + image_size].to_vec();
        let signature = data[header_size + image_size..header_size + image_size + signature_size].to_vec();
        let cert_chain = data[header_size + image_size + signature_size..expected_total].to_vec();
        
        Ok(MbnImage {
            header, image_data, signature, cert_chain,
            image_type: MbnImageType::Unknown,
            device_model: None, version: None,
        })
    }
    
    fn parse_header(data: &[u8]) -> Result<MbnHeader> {
        if data.len() < 84 {
            return Err(BridgeError::Firmware(FirmwareError::ScatterParseError(
                "MBN header too small".to_string()
            )));
        }
        
        Ok(MbnHeader {
            magic: data[0..4].try_into().unwrap(),
            version: u32::from_le_bytes([data[4], data[5], data[6], data[7]]),
            header_size: u32::from_le_bytes([data[8], data[9], data[10], data[11]]),
            image_src: u32::from_le_bytes([data[12], data[13], data[14], data[15]]),
            image_dest_ptr: u32::from_le_bytes([data[16], data[17], data[18], data[19]]),
            image_size: u32::from_le_bytes([data[20], data[21], data[22], data[23]]),
            code_size: u32::from_le_bytes([data[24], data[25], data[26], data[27]]),
            signature_size: u32::from_le_bytes([data[28], data[29], data[30], data[31]]),
            cert_chain_size: u32::from_le_bytes([data[32], data[33], data[34], data[35]]),
            reserved: [
                u32::from_le_bytes([data[36], data[37], data[38], data[39]]),
                u32::from_le_bytes([data[40], data[41], data[42], data[43]]),
                u32::from_le_bytes([data[44], data[45], data[46], data[47]]),
                u32::from_le_bytes([data[48], data[49], data[50], data[51]]),
            ],
            hash: data[52..84].try_into().unwrap_or([0; 32]),
        })
    }
    
    pub fn parse_multi(data: &[u8]) -> Result<Vec<MbnImage>> {
        let mut images = Vec::new();
        let mut offset = 0;
        
        while offset + 64 <= data.len() {
            if let Ok(img) = Self::parse(&data[offset..]) {
                let header_size = img.header.header_size as usize;
                let image_size = img.header.image_size as usize;
                let signature_size = img.header.signature_size as usize;
                let cert_chain_size = img.header.cert_chain_size as usize;
                let total = header_size + image_size + signature_size + cert_chain_size;
                
                images.push(img);
                offset += total;
                offset = (offset + 4095) & !4095;
            } else { break; }
        }
        
        Ok(images)
    }
    
    pub fn detect_type_from_filename(filename: &str) -> MbnImageType {
        let name = std::path::Path::new(filename)
            .file_stem().and_then(|s| s.to_str()).unwrap_or("");
        MbnImageType::from_name(name)
    }
}

#[derive(Debug, Default, Clone, Serialize, Deserialize)]
pub struct QcomFirmwarePackage {
    pub images: HashMap<String, MbnImage>,
    pub gpt: Option<crate::qualcomm::gpt::QcomGpt>,
    pub raw_program_xml: Option<String>,
    pub patch_xml: Option<String>,
}

impl QcomFirmwarePackage {
    pub fn parse_directory(dir: &std::path::Path) -> Result<Self> {
        let mut package = Self::default();
        
        for entry in std::fs::read_dir(dir)? {
            let entry = entry?;
            let path = entry.path();
            
            if path.is_file() {
                let filename = path.file_name()
                    .and_then(|s| s.to_str()).unwrap_or("");
                
                if filename.ends_with(".mbn") || filename.ends_with(".elf") || filename.ends_with(".img") {
                    if let Ok(data) = std::fs::read(&path) {
                        if let Ok(images) = MbnImage::parse_multi(&data) {
                            for img in images {
                                let img_type = MbnImageType::detect_type_from_filename(filename);
                                package.images.insert(img_type.to_string(), img);
                            }
                        }
                    }
                }
                
                if filename == "rawprogram.xml" || filename == "rawprogram0.xml" {
                    package.raw_program_xml = std::fs::read_to_string(&path).ok();
                }
                if filename == "patch.xml" || filename == "patch0.xml" {
                    package.patch_xml = std::fs::read_to_string(&path).ok();
                }
            }
        }
        
        Ok(package)
    }
    
    pub fn get_image(&self, img_type: MbnImageType) -> Option<&MbnImage> {
        self.images.get(img_type.to_str())
    }
    
    pub fn list_images(&self) -> Vec<(&str, &MbnImage)> {
        self.images.iter().map(|(k, v)| (k.as_str(), v)).collect()
    }
}