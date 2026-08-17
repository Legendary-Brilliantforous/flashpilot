//! Qualcomm EDL/Sahara/Firehose support

pub mod sahara;
pub mod firehose;
pub mod gpt;
pub mod mbn;

use crate::error::{Result, BridgeError};
use crate::usb;
use crate::qualcomm::sahara::{SaharaSession, QcomDeviceInfo, QCOM_VID, QCOM_EDL_PIDS};
use crate::qualcomm::firehose::{FirehoseSession, FirehosePacket, FirehoseResponse, QcomPartition};
use std::path::Path;
use std::time::Duration;

/// Resolve a CLI target ("auto", or "bus:address") to the first matching
/// Qualcomm EDL device. "auto" picks the first EDL device on the bus.
fn resolve_qcom_device<'a>(devices: &'a [crate::config::DeviceInfo],
                           target: &str) -> Result<&'a crate::config::DeviceInfo> {
    let edl: Vec<&crate::config::DeviceInfo> = devices.iter()
        .filter(|d| d.vid == QCOM_VID && QCOM_EDL_PIDS.contains(&d.pid))
        .collect();
    if target == "auto" {
        edl.first()
            .copied()
            .ok_or_else(|| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
    cmd: 0, sub: 0, reason: "Qualcomm EDL device not found".into(),
}))
    } else {
        edl.iter()
            .find(|d| format!("{}:{}", d.bus, d.address) == target)
            .copied()
            .ok_or_else(|| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
    cmd: 0, sub: 0, reason: "Qualcomm EDL device not found".into(),
}))
    }
}

/// Detect Qualcomm EDL devices
pub fn qcom_detect() -> Result<String> {
    let devices = usb::collect_devices(Some(crate::qualcomm::sahara::QCOM_VID))?;
    let mut edl_devices = Vec::new();
    
    for d in devices {
        if crate::qualcomm::sahara::QCOM_EDL_PIDS.contains(&d.pid) {
            let (stage, note) = crate::qualcomm::sahara::boot_stage_for(d.pid);
            edl_devices.push(serde_json::json!({
                "bus": d.bus,
                "address": d.address,
                "vid": format!("0x{:04X}", d.vid),
                "pid": format!("0x{:04X}", d.pid),
                "stage": stage,
                "note": note,
                "product": d.product,
                "manufacturer": d.manufacturer,
            }));
        }
    }
    
    Ok(serde_json::to_string_pretty(&edl_devices)?)
}

/// Perform Sahara handshake with Qualcomm EDL device
pub fn qcom_sahara_handshake(target: &str) -> Result<String> {
    let devices = usb::collect_devices(Some(crate::qualcomm::sahara::QCOM_VID))?;
    let dev = resolve_qcom_device(&devices, target)?;

    let mut session = SaharaSession::new(usb::UsbDevice::open(crate::qualcomm::sahara::QCOM_VID, dev.pid, dev.bus, dev.address)?)?;

    Ok(serde_json::json!({
        "status": "Sahara handshake complete",
        "version": session.version,
        "mode": format!("{:?}", session.mode),
        "max_packet_size": session.max_packet_size,
    }).to_string())
}

/// Start Firehose session with programmer
pub fn qcom_firehose_start(target: &str, programmer_path: &str) -> Result<String> {
    let devices = usb::collect_devices(Some(crate::qualcomm::sahara::QCOM_VID))?;
    let dev = resolve_qcom_device(&devices, target)?;

    let (in_ep, out_ep) = match usb::find_bulk_endpoints(dev, 0) {
    Some(eps) => eps,
    None => return Err(BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
        cmd: 0, sub: 0, reason: "no bulk endpoints".into(),
    })),
};
let iface = 0; // default interface
    
    // First do Sahara handshake
    let sahara_session = SaharaSession::new(usb::UsbDevice::open(crate::qualcomm::sahara::QCOM_VID, dev.pid, dev.bus, dev.address)?)?;
    
    // Switch to streaming mode (Firehose)
    let mut sahara_session = sahara_session;
    sahara_session.switch_to_streaming()?;
    
    // Now create Firehose session using the same USB device
    let mut firehose = FirehoseSession::new(usb::UsbDevice::open(crate::qualcomm::sahara::QCOM_VID, dev.pid, dev.bus, dev.address)?)?;
    
    // Load programmer (ELF/MBN)
    let programmer_data = std::fs::read(programmer_path)
        .map_err(|e| BridgeError::Io(e.to_string()))?;
    
    // Configure Firehose
    firehose.configure("emmc", Some("emmc"))?;
    
    Ok(serde_json::json!({
        "status": "Firehose session started",
        "programmer": programmer_path,
        "max_payload_to_target": firehose.max_payload_to,
        "max_payload_from_target": firehose.max_payload_from,
        "sector_size": firehose.sector_size,
    }).to_string())
}

/// Flash firmware via Firehose using rawprogram.xml
pub fn qcom_flash_firmware(target: &str, programmer_path: &str, xml_path: &str, fw_dir: &str) -> Result<String> {
    // Parse rawprogram.xml
    let xml_content = std::fs::read_to_string(xml_path)
        .map_err(|e| BridgeError::Io(e.to_string()))?;
    
    // Parse XML for partition operations
    let operations = parse_rawprogram_xml(&xml_content)?;
    
    let devices = usb::collect_devices(Some(crate::qualcomm::sahara::QCOM_VID))?;
    let dev = resolve_qcom_device(&devices, target)?;

    // Full flow: Sahara -> Firehose -> Flash
    let sahara_session = SaharaSession::new(usb::UsbDevice::open(crate::qualcomm::sahara::QCOM_VID, dev.pid, dev.bus, dev.address)?)?;
    let mut sahara_session = sahara_session;
    sahara_session.switch_to_streaming()?;
    
    let mut firehose = FirehoseSession::new(usb::UsbDevice::open(crate::qualcomm::sahara::QCOM_VID, dev.pid, dev.bus, dev.address)?)?;
    firehose.configure("emmc", Some("emmc"))?;
    
    let mut results = Vec::new();
    let mut total_bytes = 0u64;
    
    for op in operations {
        let file_path = format!("{}/{}", fw_dir, op.filename);
        if !Path::new(&file_path).exists() {
            results.push(serde_json::json!({
                "partition": op.partition_name,
                "status": "skipped - file not found",
                "file": file_path,
            }));
            continue;
        }
        
        let packet = crate::qualcomm::firehose::FirehosePacket::program(
            &op.partition_name,
            512, // sector size
            op.num_sectors,
            op.start_sector,
            op.physical_partition_number,
            op.sparse,
            None,
            None,
        );
        
        let mut firehose_session = FirehoseSession::new(usb::UsbDevice::open(crate::qualcomm::sahara::QCOM_VID, dev.pid, dev.bus, dev.address)?)?;
        firehose_session.configure("emmc", Some("emmc"))?;
        
        firehose_session.send_command(&packet)?;
        
        // Send file data
        let file = std::fs::File::open(&file_path)?;
        let file_size = std::fs::metadata(&file_path)?.len();
        firehose_session.send_file_data(file, file_size)?;
        
        results.push(serde_json::json!({
            "partition": op.partition_name,
            "status": "flashed",
            "file": op.filename,
            "bytes": file_size,
        }));
        total_bytes += file_size;
    }
    
    Ok(serde_json::json!({
        "status": "flash complete",
        "operations": results,
        "total_bytes": total_bytes,
    }).to_string())
}

#[derive(Debug)]
struct PartitionOp {
    partition_name: String,
    filename: String,
    start_sector: u64,
    num_sectors: u64,
    physical_partition_number: u32,
    sparse: bool,
}

fn parse_rawprogram_xml(xml: &str) -> Result<Vec<PartitionOp>> {
    use quick_xml::events::Event;
    use quick_xml::Reader;
    
    let mut reader = Reader::from_str(xml);
    reader.trim_text(true);
    let mut operations = Vec::new();
    
    loop {
        match reader.read_event() {
            Ok(Event::Start(ref e)) | Ok(Event::Empty(ref e)) => {
                let name = String::from_utf8_lossy(e.name().as_ref()).to_string();
                if name == "program" || name == "patch" {
                    let mut op = PartitionOp {
                        partition_name: String::new(),
                        filename: String::new(),
                        start_sector: 0,
                        num_sectors: 0,
                        physical_partition_number: 0,
                        sparse: false,
                    };
                    
                    for attr in e.attributes() {
                        let attr = attr.map_err(|e| BridgeError::Protocol(crate::error::ProtocolError::UnexpectedResponse(e.to_string())))?;
                        let key = String::from_utf8_lossy(attr.key.as_ref()).to_string();
                        let value = String::from_utf8_lossy(&attr.value).to_string();
                        
                        match key.as_str() {
                            "label" => op.partition_name = value,
                            "filename" => op.filename = value,
                            "start_sector" => op.start_sector = value.parse().unwrap_or(0),
                            "num_partition_sectors" => op.num_sectors = value.parse().unwrap_or(0),
                            "physical_partition_number" => op.physical_partition_number = value.parse().unwrap_or(0),
                            "sparse" => op.sparse = value == "true",
                            _ => {}
                        }
                    }
                    
                    if !op.partition_name.is_empty() {
                        operations.push(op);
                    }
                }
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(BridgeError::Protocol(crate::error::ProtocolError::UnexpectedResponse(e.to_string()))),
            _ => {}
        }
    }
    
    Ok(operations)
}

/// Backup partitions via Firehose
pub fn qcom_backup(target: &str, programmer_path: &str, out_dir: &str) -> Result<String> {
    let devices = usb::collect_devices(Some(crate::qualcomm::sahara::QCOM_VID))?;
    let dev = resolve_qcom_device(&devices, target)?;

    let sahara_session = SaharaSession::new(usb::UsbDevice::open(crate::qualcomm::sahara::QCOM_VID, dev.pid, dev.bus, dev.address)?)?;
    let mut sahara_session = sahara_session;
    sahara_session.switch_to_streaming()?;
    
    let mut firehose = FirehoseSession::new(usb::UsbDevice::open(crate::qualcomm::sahara::QCOM_VID, dev.pid, dev.bus, dev.address)?)?;
    firehose.configure("emmc", Some("emmc"))?;
    
    let partitions = firehose.get_partition_table()?;
    let mut results = Vec::new();
    
    std::fs::create_dir_all(out_dir)?;
    
    for partition in partitions {
        let output_path = format!("{}/{}.img", out_dir, partition.name);
        firehose.read_partition(&partition.name, Path::new(&output_path), partition.start_sector, partition.num_sectors)?;
        results.push(serde_json::json!({
            "partition": partition.name,
            "status": "backed_up",
            "file": output_path,
            "size": partition.size_bytes(),
        }));
    }
    
    Ok(serde_json::json!({
        "status": "backup complete",
        "partitions": results,
    }).to_string())
}

/// Get partition table via Firehose
pub fn qcom_partitions(target: &str) -> Result<String> {
    let devices = usb::collect_devices(Some(crate::qualcomm::sahara::QCOM_VID))?;
    let dev = resolve_qcom_device(&devices, target)?;

    let sahara_session = SaharaSession::new(usb::UsbDevice::open(crate::qualcomm::sahara::QCOM_VID, dev.pid, dev.bus, dev.address)?)?;
    let mut sahara_session = sahara_session;
    sahara_session.switch_to_streaming()?;
    
    let mut firehose = FirehoseSession::new(usb::UsbDevice::open(crate::qualcomm::sahara::QCOM_VID, dev.pid, dev.bus, dev.address)?)?;
    firehose.configure("emmc", Some("emmc"))?;
    
    let partitions = firehose.get_partition_table()?;
    
    Ok(serde_json::to_string_pretty(&partitions)?)
}

/// Reboot device
pub fn qcom_reboot(target: &str, mode: &str) -> Result<String> {
    let devices = usb::collect_devices(Some(crate::qualcomm::sahara::QCOM_VID))?;
    let dev = resolve_qcom_device(&devices, target)?;

    let sahara_session = SaharaSession::new(usb::UsbDevice::open(crate::qualcomm::sahara::QCOM_VID, dev.pid, dev.bus, dev.address)?)?;
    let mut sahara_session = sahara_session;
    sahara_session.switch_to_streaming()?;
    
    let mut firehose = FirehoseSession::new(usb::UsbDevice::open(crate::qualcomm::sahara::QCOM_VID, dev.pid, dev.bus, dev.address)?)?;
    firehose.configure("emmc", Some("emmc"))?;
    
    let mode_value = match mode {
        "normal" => "reset",
        "edl" => "edl",
        "recovery" => "recovery",
        "fastboot" => "fastboot",
        _ => "reset",
    };
    
    firehose.reboot(mode_value)?;
    
    Ok(serde_json::json!({"status": "reboot sent", "mode": mode_value}).to_string())
}
/// Get device info via Sahara
pub fn qcom_device_info(target: &str) -> Result<String> {
    let devices = usb::collect_devices(Some(crate::qualcomm::sahara::QCOM_VID))?;
    let dev = resolve_qcom_device(&devices, target)?;

    let mut sahara_session = SaharaSession::new(usb::UsbDevice::open(crate::qualcomm::sahara::QCOM_VID, dev.pid, dev.bus, dev.address)?)?;
    let info = sahara_session.get_device_info()?;
    
    Ok(serde_json::to_string_pretty(&info)?)
}

/// Erase the FRP (Factory Reset Protection) partition - the standard
/// service-tool "FRP reset" for FRP bypass on Qualcomm devices.
pub fn qcom_frp_reset(target: &str) -> Result<String> {
    let devices = usb::collect_devices(Some(crate::qualcomm::sahara::QCOM_VID))?;
    let dev = resolve_qcom_device(&devices, target)?;

    let sahara_session = SaharaSession::new(usb::UsbDevice::open(crate::qualcomm::sahara::QCOM_VID, dev.pid, dev.bus, dev.address)?)?;
    let mut sahara_session = sahara_session;
    sahara_session.switch_to_streaming()?;

    let mut firehose = FirehoseSession::new(usb::UsbDevice::open(crate::qualcomm::sahara::QCOM_VID, dev.pid, dev.bus, dev.address)?)?;
    firehose.configure("emmc", Some("emmc"))?;

    let partitions = firehose.get_partition_table()?;
    let frp = partitions.iter()
        .find(|p| p.name.eq_ignore_ascii_case("frp"))
        .ok_or_else(|| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
    cmd: 0, sub: 0, reason: "FRP partition not found in the device partition table".into(),
}))?;

    firehose.erase_partition(frp.start_sector, frp.num_sectors)?;

    Ok(serde_json::json!({
        "status": "FRP partition erased (FRP bypass complete)",
        "partition": frp.name,
        "start_sector": frp.start_sector,
        "sectors": frp.num_sectors,
        "size": frp.size_bytes(),
    }).to_string())
}