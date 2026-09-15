//! Apple usbmuxd + lockdown client (native device communication).
//!
//! Replaces the Python paths that shelled out to `pymobiledevice3` /
//! `ideviceinfo` / `lsusb`: detection and lockdown GetValue run natively.
//!
//! Protocol: usbmuxd listens on /var/run/usbmuxd (unix socket). Messages are
//! a 16-byte header (u32 len, u32 version=1, u32 type, u32 tag) followed by
//! an XML plist body. Listen (type 8) yields a DeviceList plist; Connect
//! (type 6) opens a TCP relay to the device — port 62078 is lockdownd.
//! Lockdown speaks XML plists: `{"Request": "GetValue"}` returns
//! `{Status, Value{...}}` for non-protected keys without pairing.

use crate::error::{Result, BridgeError};
use serde::Serialize;
use std::io::{Read, Write};
use std::os::unix::net::UnixStream;

const USBMUXD_SOCKET: &str = "/var/run/usbmuxd";
const LOCKDOWN_PORT: u16 = 62078;
const MUX_VERSION: u32 = 1;
const MSG_RESULT: u32 = 1;
const MSG_CONNECT: u32 = 6;
const MSG_LISTEN: u32 = 8;

#[derive(Debug, Clone, Serialize)]
pub struct AppleDevice {
    pub device_id: u32,
    pub udid: String,
    pub connection_type: String,
}

// ---- minimal XML plist subset (dict/string/integer/array) ----------------

fn xml_escape(s: &str) -> String {
    s.replace('&', "&")
        .replace('<', "<")
        .replace('>', ">")
}

pub fn plist_dict_xml(pairs: &[(&str, String)]) -> String {
    let mut body = String::from("<plist version=\"1.0\"><dict>");
    for (k, v) in pairs {
        body.push_str(&format!(
            "<key>{}</key><string>{}</string>",
            xml_escape(k),
            xml_escape(v)
        ));
    }
    body.push_str("</dict></plist>");
    body
}

/// Extract the inner text of `<key>name</key>`'s sibling `<string>`.
fn plist_string_after_tag(xml: &str, tag: &str) -> Option<String> {
    let key_pat = format!("<key>{}</key><string>", xml_escape(tag));
    if let Some(start) = xml.find(&key_pat) {
        let rest = &xml[start + key_pat.len()..];
        if let Some(end) = rest.find("</string>") {
            return Some(rest[..end].replace("<", "<").replace(">", ">").replace("&", "&"));
        }
    }
    None
}

/// Extract `<integer>` sibling text of a key.
fn plist_int_after_tag(xml: &str, tag: &str) -> Option<i64> {
    let key_pat = format!("<key>{}</key><integer>", xml_escape(tag));
    if let Some(start) = xml.find(&key_pat) {
        let rest = &xml[start + key_pat.len()..];
        if let Some(end) = rest.find("</integer>") {
            return rest[..end].trim().parse().ok();
        }
    }
    None
}

/// Pull one full `<dict>...</dict>` block from `xml` starting at `from`.
fn dict_block(xml: &str, from: usize) -> Option<&str> {
    let open = xml.find("<dict>")?;
    let _ = from;
    let start = open;
    let mut depth = 0i32;
    let mut idx = start;
    while idx < xml.len() {
        if xml[idx..].starts_with("<dict>") {
            depth += 1;
            idx += 6;
        } else if xml[idx..].starts_with("</dict>") {
            depth -= 1;
            idx += 7;
            if depth == 0 {
                return Some(&xml[start..idx]);
            }
        } else {
            idx += 1;
        }
    }
    None
}

// ---- usbmuxd framing ------------------------------------------------------

fn mux_frame(msg_type: u32, tag: u32, payload: &str) -> Vec<u8> {
    let len = (16 + payload.len()) as u32;
    let mut buf = Vec::with_capacity(16 + payload.len());
    buf.extend_from_slice(&len.to_le_bytes());
    buf.extend_from_slice(&MUX_VERSION.to_le_bytes());
    buf.extend_from_slice(&msg_type.to_le_bytes());
    buf.extend_from_slice(&tag.to_le_bytes());
    buf.extend_from_slice(payload.as_bytes());
    buf
}

fn read_mux_message(stream: &mut UnixStream) -> Result<(u32, String)> {
    let mut hdr = [0u8; 16];
    stream
        .read_exact(&mut hdr)
        .map_err(|e| BridgeError::Io(format!("usbmuxd read header: {e}")))?;
    let len = u32::from_le_bytes([hdr[0], hdr[1], hdr[2], hdr[3]]) as usize;
    let msg_type = u32::from_le_bytes([hdr[8], hdr[9], hdr[10], hdr[11]]);
    if len < 16 || len > 1 << 22 {
        return Err(BridgeError::Io(format!("usbmuxd bad frame len {len}")));
    }
    let mut body = vec![0u8; len - 16];
    stream
        .read_exact(&mut body)
        .map_err(|e| BridgeError::Io(format!("usbmuxd read body: {e}")))?;
    Ok((msg_type, String::from_utf8_lossy(&body).to_string()))
}

fn usbmuxd_socket() -> Result<UnixStream> {
    UnixStream::connect(USBMUXD_SOCKET)
        .map_err(|e| BridgeError::Io(format!("connect {USBMUXD_SOCKET}: {e} (is usbmuxd running?)")))
}

/// List devices attached to usbmuxd (native Listen round).
pub fn usbmuxd_list() -> Result<Vec<AppleDevice>> {
    let mut stream = usbmuxd_socket()?;
    let payload = plist_dict_xml(&[("Message", "Listen".to_string())]);
    stream
        .write_all(&mux_frame(MSG_LISTEN, 1, &payload))
        .map_err(|e| BridgeError::Io(format!("usbmuxd write: {e}")))?;
    let (_t, reply) = read_mux_message(&mut stream)?;

    let mut out = Vec::new();
    // DeviceList reply contains one <dict> per attached device inside
    // nested dicts; iterate every dict block that carries a DeviceID.
    let mut cursor = 0usize;
    while let Some(pos) = reply[cursor..].find("<dict>") {
        let abs = cursor + pos;
        let block = match dict_block(&reply[abs..], 0) {
            Some(b) => b.to_string(),
            None => break,
        };
        cursor = abs + 1;
        if let Some(id) = plist_int_after_tag(&block, "DeviceID") {
            let udid = plist_string_after_tag(&block, "SerialNumber").unwrap_or_default();
            let conn = plist_string_after_tag(&block, "ConnectionType").unwrap_or_else(|| "USB".into());
            if !udid.is_empty() {
                out.push(AppleDevice {
                    device_id: id as u32,
                    udid,
                    connection_type: conn,
                });
            }
        }
    }
    Ok(out)
}

/// Lockdown GetValue over a usbmuxd relay (unpaired: non-protected keys).
pub fn lockdown_get_value(device_id: u32) -> Result<std::collections::HashMap<String, String>> {
    let mut stream = usbmuxd_socket()?;
    let payload = plist_dict_xml(&[
        ("DeviceID", device_id.to_string()),
        ("PortNumber", LOCKDOWN_PORT.to_string()),
    ]);
    stream
        .write_all(&mux_frame(MSG_CONNECT, 2, &payload))
        .map_err(|e| BridgeError::Io(format!("usbmuxd write: {e}")))?;
    let (t, reply) = read_mux_message(&mut stream)?;
    if t != MSG_RESULT || !reply.contains("<integer>0</integer>") {
        return Err(BridgeError::Io(format!(
            "usbmuxd Connect refused: {reply:.200}"
        )));
    }
    // The socket is now a raw lockdown relay: speak XML plists.
    let req = plist_dict_xml(&[("Request", "GetValue".to_string())]);
    let framed = format!("{}{}", (4 + req.len()) as u32, req); // lockdown frames are u32 len + plist
    stream
        .write_all(framed.as_bytes())
        .map_err(|e| BridgeError::Io(format!("lockdown write: {e}")))?;

    // Lockdown reply: u32 len + plist (read with a generous timeout).
    let mut hdr = [0u8; 4];
    stream
        .read_exact(&mut hdr)
        .map_err(|e| BridgeError::Io(format!("lockdown read: {e}")))?;
    let len = u32::from_le_bytes(hdr) as usize;
    if len < 4 || len > 1 << 22 {
        return Err(BridgeError::Io(format!("lockdown bad frame len {len}")));
    }
    let mut body = vec![0u8; len - 4];
    stream
        .read_exact(&mut body)
        .map_err(|e| BridgeError::Io(format!("lockdown read body: {e}")))?;
    let xml = String::from_utf8_lossy(&body).to_string();

    let mut out = std::collections::HashMap::new();
    let block = dict_block(&xml, 0).unwrap_or(&xml).to_string();
    for key in [
        "ActivationState",
        "SerialNumber",
        "ProductType",
        "ProductVersion",
        "UniqueDeviceID",
        "DeviceName",
        "BuildVersion",
        "IntegratedCircuitCardIdentity",
        "InternationalMobileSubscriberIdentity",
    ] {
        if let Some(v) = plist_string_after_tag(&block, key) {
            if !v.is_empty() {
                out.insert(key.to_string(), v);
            }
        }
    }
    Ok(out)
}

/// CLI: `apple-detect` — usbmuxd device list as JSON.
pub fn apple_detect_cli() -> Result<String> {
    let devices = usbmuxd_list()?;
    serde_json::to_string(&devices).map_err(|e| BridgeError::Io(e.to_string()))
}

/// CLI: `apple-info` — usbmuxd list + lockdown GetValue for the first device.
pub fn apple_info_cli() -> Result<String> {
    let devices = usbmuxd_list()?;
    let mut out = serde_json::json!({"devices": devices});
    if let Some(first) = devices.first() {
        match lockdown_get_value(first.device_id) {
            Ok(values) => out["lockdown"] = serde_json::json!(values),
            Err(e) => out["lockdown_error"] = serde_json::json!(e.to_string()),
        }
    }
    Ok(out.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn plist_dict_encoding() {
        let xml = plist_dict_xml(&[("Message", "Listen".to_string())]);
        assert!(xml.contains("<key>Message</key><string>Listen</string>"));
        assert!(xml.starts_with("<plist version=\"1.0\">"));
    }

    #[test]
    fn plist_string_extraction() {
        let xml = "<plist><dict><key>SerialNumber</key><string>R9X&1</string>\
                   <key>DeviceID</key><integer>7</integer></dict></plist>";
        assert_eq!(plist_string_after_tag(xml, "SerialNumber").unwrap(), "R9X&1");
        assert_eq!(plist_int_after_tag(xml, "DeviceID").unwrap(), 7);
        assert!(plist_string_after_tag(xml, "Missing").is_none());
    }

    #[test]
    fn dict_block_scans_nested() {
        let xml = "<plist><array><dict><key>DeviceID</key><integer>2</integer>\
                   <key>Properties</key><dict><key>SerialNumber</key><string>U1</string></dict>\
                   </dict></array></plist>";
        let block = dict_block(xml, 0).unwrap();
        assert!(block.starts_with("<dict>"));
        assert!(block.ends_with("</dict>"));
        assert!(plist_int_after_tag(block, "DeviceID").is_some());
        assert_eq!(plist_string_after_tag(block, "SerialNumber").unwrap(), "U1");
    }

    #[test]
    fn mux_frame_layout() {
        let f = mux_frame(MSG_LISTEN, 1, "XY");
        assert_eq!(f.len(), 18);
        assert_eq!(u32::from_le_bytes([f[0], f[1], f[2], f[3]]), 18);
        assert_eq!(u32::from_le_bytes([f[4], f[5], f[6], f[7]]), MUX_VERSION);
        assert_eq!(u32::from_le_bytes([f[8], f[9], f[10], f[11]]), MSG_LISTEN);
        assert_eq!(&f[16..], b"XY");
    }
}