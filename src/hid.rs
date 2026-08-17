use serde::Serialize;
use std::time::Duration;

use crate::config::{DeviceInfo, InterfaceInfo};
use crate::error::{Result, BridgeError};
use crate::usb;
use rusb::{Context, UsbContext};

#[derive(Serialize)]
pub struct HidTarget {
    pub bus: u8,
    pub address: u8,
    pub vid: u16,
    pub pid: u16,
    pub product: Option<String>,
    pub interface: u8,
    pub in_ep: Option<u8>,
    pub out_ep: Option<u8>,
    pub label: String,
}

fn hex_decode(s: &str) -> Result<Vec<u8>> {
    let clean: String = s
        .chars()
        .filter(|c| c.is_ascii_hexdigit() || *c == ' ' || *c == ',')
        .collect();
    let joined: String = clean.chars().filter(|c| c.is_ascii_hexdigit()).collect();
    if joined.len() % 2 != 0 {
        return Err(BridgeError::InvalidArgument("hex string must have even length".into()));
    }
    (0..joined.len())
        .step_by(2)
        .map(|i| {
            u8::from_str_radix(&joined[i..i + 2], 16)
                .map_err(|e| BridgeError::InvalidArgument(format!("bad hex: {e}")))
        })
        .collect()
}

pub fn list_samsung_hid() -> Result<String> {
    let devices = usb::collect_devices(Some(0x04e8))?;
    let mut targets = Vec::new();

    for d in &devices {
        for iface in &d.interfaces {
            if iface.class != 0x03 {
                continue;
            }
            let in_ep = iface
                .endpoints
                .iter()
                .find(|e| e.direction == "in" && e.transfer_type == "interrupt")
                .map(|e| e.address);
            let out_ep = iface
                .endpoints
                .iter()
                .find(|e| e.direction == "out" && e.transfer_type == "interrupt")
                .map(|e| e.address);
            targets.push(HidTarget {
                bus: d.bus,
                address: d.address,
                vid: d.vid,
                pid: d.pid,
                product: d.product.clone(),
                interface: iface.number,
                in_ep,
                out_ep,
                label: format!(
                    "{:04x}:{:04x}@{}:{}",
                    d.vid, d.pid, d.bus, d.address
                ),
            });
        }
    }

    let json = serde_json::to_string_pretty(&targets).map_err(|e| crate::error::BridgeError::Io(e.to_string()))?;
    Ok(json)
}

pub fn open_and_send(target: &str, hex: &str) -> Result<String> {
    let bytes = hex_decode(hex)?;

    let devices = usb::collect_devices(Some(0x04e8))?;
    let wanted: Vec<&str> = target.split('@').collect();
    if wanted.len() != 2 {
        return Err(BridgeError::InvalidArgument("target must be vid:pid@bus:addr".into()));
    }
    let vid = u16::from_str_radix(wanted[0].split(':').next().unwrap_or(""), 16)
        .map_err(|e| BridgeError::InvalidArgument(format!("bad vid: {e}")))?;
    let loc: Vec<&str> = wanted[1].split(':').collect();
    let bus: u8 = loc[0].parse().map_err(|e| BridgeError::InvalidArgument(format!("bad bus: {e}")))?;
    let addr: u8 = loc[1].parse().map_err(|e| BridgeError::InvalidArgument(format!("bad addr: {e}")))?;

    let devices = usb::collect_devices(Some(0x04e8))?;
    let target_dev = devices
        .iter()
        .find(|d| {
            d.vid == vid && d.bus == bus && d.address == addr
        })
        .ok_or_else(|| BridgeError::Usb(crate::error::UsbError::DeviceNotFound))?;

    let context = Context::new().map_err(|e| crate::error::BridgeError::Usb(crate::error::UsbError::TransferFailed(e.to_string())))?;
    let handle = context
        .devices()?
        .iter()
        .find(|d| {
            let desc = d.device_descriptor().ok();
            desc.as_ref().map_or(false, |desc| {
                desc.vendor_id() == vid && desc.product_id() == target_dev.pid
            }) && d.bus_number() == target_dev.bus && d.address() == target_dev.address
        })
        .ok_or_else(|| BridgeError::Usb(crate::error::UsbError::DeviceNotFound))?
        .open()?;

    let interface = target_dev
        .interfaces
        .iter()
        .find(|i| i.class == 0x03)
        .ok_or_else(|| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
            cmd: 0, sub: 0, reason: "no HID interface on this device".into(),
        }))?;

    handle.claim_interface(interface.number)?;

    let in_ep = interface
        .endpoints
        .iter()
        .find(|e| e.direction == "in" && e.transfer_type == "interrupt")
        .map(|e| e.address)
        .ok_or_else(|| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
            cmd: 0, sub: 0, reason: "no interrupt IN endpoint".into(),
        }))?;
    let out_ep = interface
        .endpoints
        .iter()
        .find(|e| e.direction == "out" && e.transfer_type == "interrupt")
        .map(|e| e.address);

    let mut packet = bytes.clone();
    if packet.first() != Some(&0x00) {
        packet.insert(0, 0x00); // prepend report ID
    }

    match out_ep {
        Some(ep) => {
            handle.write_interrupt(ep, &packet, std::time::Duration::from_secs(5))
                .map_err(|e| crate::error::BridgeError::Usb(crate::error::UsbError::TransferFailed(e.to_string())))?;
        }
        None => {
            handle.write_control(
                0x21,
                0x09, // SET_REPORT
                0x0200,
                interface.number as u16,
                &packet,
                std::time::Duration::from_secs(5),
            ).map_err(|e| crate::error::BridgeError::Usb(crate::error::UsbError::TransferFailed(e.to_string())))?;
        }
    }

    let mut buf = vec![0u8; 64 + 1];
    let n = handle
        .read_interrupt(in_ep, &mut buf, std::time::Duration::from_secs(5))
        .map_err(|e| crate::error::BridgeError::Usb(crate::error::UsbError::TransferFailed(e.to_string())))?;

    handle.release_interface(interface.number)?;

    let hex_out = buf[..n]
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect::<Vec<_>>()
        .join(" ");

    Ok(format!(
        "{{\"sent\": \"{}\", \"len\": {}, \"reply\": \"{}\"}}",
        bytes
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect::<Vec<_>>()
            .join(" "),
        n,
        hex_out
    ))
}