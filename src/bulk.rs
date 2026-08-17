use serde::Serialize;
use std::time::Duration;

use crate::config::{DeviceInfo, InterfaceInfo, EndpointInfo};
use crate::error::{Result, BridgeError};
use crate::usb;
use rusb::{Context, UsbContext};

#[derive(Serialize)]
pub struct BulkTarget {
    pub bus: u8,
    pub address: u8,
    pub vid: u16,
    pub pid: u16,
    pub product: Option<String>,
    pub interface: u8,
    pub in_ep: u8,
    pub out_ep: u8,
    pub label: String,
}

pub fn list_bulk_targets() -> Result<String> {
    let devices = usb::collect_devices(Some(0x04e8))?;
    let mut targets = Vec::new();

    for d in &devices {
        for iface in &d.interfaces {
            let in_ep = iface.endpoints.iter().find(|e| e.direction == "in" && e.transfer_type == "bulk");
            let out_ep = iface.endpoints.iter().find(|e| e.direction == "out" && e.transfer_type == "bulk");
            if in_ep.is_none() || out_ep.is_none() {
                continue;
            }
            targets.push(BulkTarget {
                bus: d.bus,
                address: d.address,
                vid: d.vid,
                pid: d.pid,
                product: d.product.clone(),
                interface: iface.number,
                in_ep: in_ep.unwrap().address,
                out_ep: out_ep.unwrap().address,
                label: format!("{:04x}:{:04x}@{}:{}", d.vid, d.pid, d.bus, d.address),
            });
        }
    }

    let json = serde_json::to_string_pretty(&targets).map_err(|e| crate::error::BridgeError::Io(e.to_string()))?;
    Ok(json)
}

/// Open a persistent bulk session: connect, claim, then process commands
/// given as hex args. Commands: "w<hex>" write, "r<n>" read n bytes (timeout 5s).
/// Returns a JSON list of per-command results, then releases the interface.
pub fn bulk_session(target: &str, cmds: &[String]) -> Result<String> {
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
        .find(|d| d.vid == vid && d.bus == bus && d.address == addr)
        .ok_or_else(|| BridgeError::Usb(crate::error::UsbError::DeviceNotFound))?;

    let iface = find_bulk_iface(target_dev).ok_or_else(|| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
        cmd: 0, sub: 0, reason: "no bulk interface found".into(),
    }))?;
    let in_ep = iface
        .endpoints
        .iter()
        .find(|e| e.direction == "in" && e.transfer_type == "bulk")
        .map(|e| e.address)
        .ok_or_else(|| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
            cmd: 0, sub: 0, reason: "no bulk IN endpoint".into(),
        }))?;
    let out_ep = iface
        .endpoints
        .iter()
        .find(|e| e.direction == "out" && e.transfer_type == "bulk")
        .map(|e| e.address)
        .ok_or_else(|| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
            cmd: 0, sub: 0, reason: "no bulk OUT endpoint".into(),
        }))?;

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

    handle.set_auto_detach_kernel_driver(true)?;
    handle.claim_interface(iface.number)?;

    let mut results = Vec::new();
    for cmd in cmds {
        if let Some(hex) = cmd.strip_prefix('w') {
            let bytes = hex_decode(hex)?;
            let n = handle.write_bulk(out_ep, &bytes, std::time::Duration::from_secs(5))
                .map_err(|e| crate::error::BridgeError::Usb(crate::error::UsbError::TransferFailed(e.to_string())))?;
            results.push(format!("w[{n}]"));
        } else if let Some(nstr) = cmd.strip_prefix('r') {
            let n: usize = nstr.parse().map_err(|e| BridgeError::InvalidArgument(format!("bad read size: {e}")))?;
            let mut buf = vec![0u8; n.max(1)];
            match handle.read_bulk(in_ep, &mut buf, std::time::Duration::from_secs(5)) {
                Ok(got) => {
                    let hex_out = buf[..got]
                        .iter()
                        .map(|b| format!("{b:02x}"))
                        .collect::<Vec<_>>()
                        .join(" ");
                    results.push(format!("r[{got}]: {hex_out}"));
                }
                Err(e) => results.push(format!("r[ERR]: {e}")),
            }
        } else {
            return Err(BridgeError::InvalidArgument(format!("unknown session command: {cmd}")));
        }
    }

    handle.release_interface(iface.number)?;

    let json = serde_json::to_string(&results).map_err(|e| crate::error::BridgeError::Io(e.to_string()))?;
    Ok(json)
}

fn hex_decode(s: &str) -> Result<Vec<u8>> {
    let joined: String = s.chars().filter(|c| c.is_ascii_hexdigit()).collect();
    if joined.len() % 2 != 0 {
        return Err(BridgeError::InvalidArgument("hex string must have even length".into()));
    }
    (0..joined.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&joined[i..i + 2], 16).map_err(|e| BridgeError::InvalidArgument(format!("bad hex: {e}"))))
        .collect()
}

/// Locate the download-mode (Odin) interface on a Samsung device: the CDC
/// data interface (class 10) or the first bulk interface.
fn find_bulk_iface<'a>(dev: &'a DeviceInfo) -> Option<&'a InterfaceInfo> {
    dev.interfaces.iter().find(|i| i.class == 10).or_else(|| {
        dev.interfaces.iter().find(|i| {
            i.endpoints
                .iter()
                .any(|e| e.transfer_type == "bulk" && e.direction == "out")
            && i.endpoints
                .iter()
                .any(|e| e.transfer_type == "bulk" && e.direction == "in")
        })
    })
}

pub fn bulk_send(target: &str, hex: &str, read_len: usize) -> Result<String> {
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
        .find(|d| d.vid == vid && d.bus == bus && d.address == addr)
        .ok_or_else(|| BridgeError::Usb(crate::error::UsbError::DeviceNotFound))?;

    let iface = find_bulk_iface(target_dev).ok_or_else(|| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
        cmd: 0, sub: 0, reason: "no bulk interface found".into(),
    }))?;
    let in_ep = iface
        .endpoints
        .iter()
        .find(|e| e.direction == "in" && e.transfer_type == "bulk")
        .map(|e| e.address)
        .ok_or_else(|| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
            cmd: 0, sub: 0, reason: "no bulk IN endpoint".into(),
        }))?;
    let out_ep = iface
        .endpoints
        .iter()
        .find(|e| e.direction == "out" && e.transfer_type == "bulk")
        .map(|e| e.address)
        .ok_or_else(|| BridgeError::Protocol(crate::error::ProtocolError::CommandFailed {
            cmd: 0, sub: 0, reason: "no bulk OUT endpoint".into(),
        }))?;

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

    handle.set_auto_detach_kernel_driver(true)?;
    handle.claim_interface(iface.number)?;

    if !bytes.is_empty() {
        handle.write_bulk(out_ep, &bytes, std::time::Duration::from_secs(5))?;
    }

    let mut buf = vec![0u8; read_len.max(1)];
    let n = handle.read_bulk(in_ep, &mut buf, std::time::Duration::from_secs(5))?;

    handle.release_interface(iface.number)?;

    let hex_out = buf[..n]
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect::<Vec<_>>()
        .join(" ");

    let sent_hex = bytes
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect::<Vec<_>>()
        .join(" ");

    Ok(format!(
        "{{\"sent\": \"{}\", \"len\": {}, \"reply\": \"{}\"}}",
        sent_hex, n, hex_out
    ))
}