//! mtkclient DA container parsing (Loader/MTK_DA_V5.bin / MTK_DA_V6.bin).
//!
//! Format (mtkclient `Library/DA/daconfig.py` `parse_da_loader` / `DA`,
//! B. Kerler, GPLv3 — the SLA keys in `mtk_sla_keys.rs` carry the same
//! attribution):
//!   0x68-byte header ("MTK_DA_v6" marker -> XML mode)
//!   count_da u32 @0x68
//!   entry size: 0xD8 when the two bytes @0x6C+0xD8 are "DADA", else 0xDC
//!   entries at 0x6C + i*off, each:
//!     magic u16, hw_code u16, hw_sub_code u16, hw_version u16,
//!     [sw_version u16, reserved u16 (non-old layout)],
//!     pagesize u16, reserved u16, entry_region_index u16,
//!     entry_region_count u16, then count x 20-byte regions:
//!     m_buf/m_len/m_start_addr/m_start_offset/m_sig_len (u32 each)
//!
//! Upload (mtkclient `dalegacy_lib.py` `upload_da1`): region[1] is the DA
//! binary — `file[m_buf..m_buf+m_len]` sent via SEND_DA at `m_start_addr`,
//! jumped via JUMP_DA, then a 0xC0 sync byte arrives on the SAME connection
//! (no USB re-enumeration — the app's DaSession keeps talking on it).
//!
//! Keying: V5 (LEGACY) containers key entries by the marketing dacode
//! (MT6765 -> 0x6765); V6 (XML) containers key by the raw hw_code
//! (MT6855 -> 0x1129). This engine speaks the LEGACY protocol, so V5 is
//! preferred and V6 is only a fallback for chips with no V5 entry.

use crate::error::{BridgeError, Result};

pub struct EntryRegion {
    pub m_buf: u32,
    pub m_len: u32,
    pub m_start_addr: u32,
    pub m_start_offset: u32,
    pub m_sig_len: u32,
}

pub struct DaEntry {
    pub hw_code: u16,
    pub hw_sub_code: u16,
    pub hw_version: u16,
    pub sw_version: u16,
    pub v6: bool,
    pub regions: Vec<EntryRegion>,
}

pub struct DaContainer {
    pub v6: bool,
    pub entries: Vec<DaEntry>,
}

/// Marketing dacode for a hw_code (mtkclient brom_config `dacode`): the
/// 67xx/65xx family uses the chip number in hex (hw 0x766 -> 0x6765);
/// newer 0x1xxx-class SoCs use their hw code directly (MT6855 -> 0x1129).
pub fn marketing_dacode(hw_code: u32) -> Option<u32> {
    if hw_code >= 0x1000 {
        return Some(hw_code);
    }
    Some(match hw_code {
        0x699 => 0x6739,
        0x766 => 0x6765,
        0x707 => 0x6768,
        0x788 => 0x6771,
        0x725 => 0x6779,
        0x813 => 0x6785,
        0x989 => 0x6833,
        0x996 => 0x6853,
        0x886 => 0x6873,
        0x816 => 0x6885,
        0x950 => 0x6893,
        0x959 => 0x6877,
        0x1066 | 0x6781 => 0x6781,
        _ => return None,
    })
}

pub fn parse_container(data: &[u8]) -> Result<DaContainer> {
    if data.len() < 0x6C + 0xDA {
        return Err(BridgeError::InvalidArgument(
            "DA container truncated (no entry table)".to_string(),
        ));
    }
    let v6 = data[..0x68].windows(9).any(|w| w == b"MTK_DA_v6");
    let count = u32::from_le_bytes(data[0x68..0x6C].try_into().unwrap()) as usize;
    let old = data[0x6C + 0xD8..0x6C + 0xDA] == *b"\xDA\xDA";
    let off = if old { 0xD8 } else { 0xDC };

    let mut entries = Vec::new();
    for i in 0..count {
        let start = 0x6C + i * off;
        if start + off > data.len() {
            break; // truncated tail — keep whatever parsed
        }
        let e = &data[start..start + off];
        let hw_code = u16::from_le_bytes(e[2..4].try_into().unwrap());
        let hw_sub_code = u16::from_le_bytes(e[4..6].try_into().unwrap());
        let hw_version = u16::from_le_bytes(e[6..8].try_into().unwrap());
        let (sw_version, regions_base) = if old {
            (0u16, 16usize)
        } else {
            (u16::from_le_bytes(e[8..10].try_into().unwrap()), 20usize)
        };
        if regions_base + 2 > e.len() {
            continue;
        }
        let region_count =
            u16::from_le_bytes(e[regions_base - 2..regions_base].try_into().unwrap()) as usize;
        let mut regions = Vec::new();
        for r in 0..region_count {
            let pos = regions_base + r * 20;
            if pos + 20 > e.len() {
                break;
            }
            let g = |p: usize| u32::from_le_bytes(e[p..p + 4].try_into().unwrap());
            regions.push(EntryRegion {
                m_buf: g(pos),
                m_len: g(pos + 4),
                m_start_addr: g(pos + 8),
                m_start_offset: g(pos + 12),
                m_sig_len: g(pos + 16),
            });
        }
        if hw_code == 0 && regions.is_empty() {
            continue;
        }
        entries.push(DaEntry {
            hw_code,
            hw_sub_code,
            hw_version,
            sw_version,
            v6,
            regions,
        });
    }
    Ok(DaContainer { v6, entries })
}

impl DaContainer {
    /// First entry matching hw_code or its marketing dacode.
    pub fn pick(&self, hw_code: u32) -> Option<&DaEntry> {
        self.entries
            .iter()
            .find(|e| e.hw_code as u32 == hw_code)
            .or_else(|| {
                let mkt = marketing_dacode(hw_code)?;
                self.entries.iter().find(|e| e.hw_code as u32 == mkt)
            })
    }

    /// The DA binary: region[1] (mtkclient `upload_da1`'s stage 1).
    /// Returns (bytes, load address, signature length).
    pub fn stage1<'a>(&self, entry: &'a DaEntry, data: &'a [u8]) -> Result<(&'a [u8], u32, usize)> {
        let r = entry.regions.get(1).ok_or_else(|| {
            BridgeError::InvalidArgument("DA entry has no stage-1 region".to_string())
        })?;
        let start = r.m_buf as usize;
        let end = start
            .checked_add(r.m_len as usize)
            .filter(|&end| end <= data.len())
            .ok_or_else(|| {
                BridgeError::InvalidArgument(format!(
                    "DA stage-1 region {start}..{} exceeds container size {}",
                    start + r.m_len as usize,
                    data.len()
                ))
            })?;
        Ok((&data[start..end], r.m_start_addr, r.m_sig_len as usize))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Build a minimal V5-style container: header + 1 entry with 3 regions.
    fn v5_container() -> Vec<u8> {
        let mut d = vec![0u8; 0x68];
        d[..9].copy_from_slice(b"MTK_DA_V5");
        d.extend_from_slice(&1u32.to_le_bytes()); // count_da @0x68
        // entry (0xDC bytes) at 0x6C
        let mut e = vec![0u8; 0xDC];
        e[2..4].copy_from_slice(&0x6765u16.to_le_bytes()); // hw_code (dacode)
        e[6..8].copy_from_slice(&0xca00u16.to_le_bytes()); // hw_version
        e[8..10].copy_from_slice(&0xca01u16.to_le_bytes()); // sw_version
        // entry_region_count @18 = 3
        e[18..20].copy_from_slice(&3u16.to_le_bytes());
        // regions @20: 3 x 20 bytes; m_bufs point inside the container
        // (region[1] data is appended after the entry below)
        let r = |buf: u32, len: u32, addr: u32, sig: u32| {
            let mut b = vec![0u8; 20];
            b[0..4].copy_from_slice(&buf.to_le_bytes());
            b[4..8].copy_from_slice(&len.to_le_bytes());
            b[8..12].copy_from_slice(&addr.to_le_bytes());
            b[16..20].copy_from_slice(&sig.to_le_bytes());
            b
        };
        let regs = r(0x148, 0x10, 0x80000100, 0)
            .into_iter()
            .chain(r(0x160, 0x20, 0x200000, 256))
            .chain(r(0x190, 0x10, 0x40000000, 256))
            .collect::<Vec<u8>>();
        e[20..20 + regs.len()].copy_from_slice(&regs);
        // old_ldr marker check reads @0x6C+0xD8; we are non-old (not DADA)
        // so leave zeros there.
        d.extend_from_slice(&e);
        // region payload bytes the stage1 slice reads from
        d.extend(std::iter::repeat_n(0xA5u8, 0x60));
        d
    }

    #[test]
    fn container_parses_and_picks_by_dacode() {
        let data = v5_container();
        let c = parse_container(&data).unwrap();
        assert!(!c.v6);
        assert_eq!(c.entries.len(), 1);
        let e = c.pick(0x766).expect("hw 0x766 must pick via dacode 0x6765");
        assert_eq!(e.hw_code, 0x6765);
        assert_eq!(e.hw_sub_code, 0);
        let (da1, addr, sig) = c.stage1(e, &data).unwrap();
        // region[1]: m_buf 0x160, m_len 0x20, m_start_addr 0x200000, sig 256
        assert_eq!(da1.len(), 0x20);
        assert_eq!(addr, 0x200000);
        assert_eq!(sig, 256);
    }

    #[test]
    fn pick_matches_hw_code_first_then_marketing() {
        let data = v5_container();
        let c = parse_container(&data).unwrap();
        // Direct dacode hit.
        assert!(c.pick(0x6765).is_some());
        // Unknown chip with no entry and no marketing form -> None
        // (a small hw code below 0x1000 that is not in the dacode table).
        assert!(c.pick(0x123).is_none());
        // Marketing fallback for a known hw code with no entry.
        assert_eq!(marketing_dacode(0x766), Some(0x6765));
        assert_eq!(marketing_dacode(0x707), Some(0x6768));
        assert_eq!(marketing_dacode(0x1129), Some(0x1129));
        // >=0x1000 hw codes map to themselves (MT6855 -> 0x1129).
        assert_eq!(marketing_dacode(0x9999), Some(0x9999));
    }

    #[test]
    fn stage1_rejects_overflow() {
        let mut data = v5_container();
        data.truncate(0x170); // cut inside region[1] (0x160..0x180)
        let c = parse_container(&data).unwrap();
        let e = c.pick(0x766).unwrap();
        assert!(c.stage1(e, &data).is_err());
    }
}
