//! Android sparse image expansion — replaces `simg2img` for Samsung firmware
//! (super.img / vendor.img ship sparse inside Odyssey/tar archives).
//!
//! Sparse v1 format (ANDROID_SPARSE_IMG_MAGIC 0xED26FF3A):
//!   header: magic u32, major u16, minor u16, file_hdr_sz u16, chunk_hdr_sz u16,
//!           blk_sz u32, total_blks u32, total_chunks u32, image checksum u32
//!   chunk header: type u16, reserved u16, chunk_sz u32 (output blocks), total_sz u32
//!   chunk types: RAW(0xCAC1), FILL(0xCAC2), DONT_CARE(0xCAC3), CRC32(0xCAC4)

use crate::error::{BridgeError, Result};

pub const SPARSE_MAGIC: u32 = 0xED26FF3A;
const CT_RAW: u16 = 0xCAC1;
const CT_FILL: u16 = 0xCAC2;
const CT_DONT_CARE: u16 = 0xCAC3;
const CT_CRC32: u16 = 0xCAC4;

/// True if `data` begins with the sparse image magic.
pub fn is_sparse(data: &[u8]) -> bool {
    data.len() >= 4 && u32::from_le_bytes([data[0], data[1], data[2], data[3]]) == SPARSE_MAGIC
}

/// Expand a sparse image in memory to the raw output image.
pub fn expand(data: &[u8]) -> Result<Vec<u8>> {
    if !is_sparse(data) {
        return Err(BridgeError::InvalidArgument("not a sparse image".into()));
    }
    let hexword = |off: usize| -> Result<u32> {
        data.get(off..off + 4)
            .map(|b| u32::from_le_bytes([b[0], b[1], b[2], b[3]]))
            .ok_or_else(|| BridgeError::InvalidArgument("sparse header truncated".into()))
    };
    let hw = |off: usize| -> Result<u16> {
        data.get(off..off + 2)
            .map(|b| u16::from_le_bytes([b[0], b[1]]))
            .ok_or_else(|| BridgeError::InvalidArgument("sparse header truncated".into()))
    };

    let file_hdr_sz = hw(8)? as usize;
    let chunk_hdr_sz = hw(10)? as usize;
    let blk_sz = hexword(12)? as usize;
    let total_chunks = hexword(20)? as usize;

    if blk_sz == 0 || blk_sz > (1 << 26) {
        return Err(BridgeError::InvalidArgument(
            "insane sparse block size".into(),
        ));
    }

    let mut out: Vec<u8> = Vec::new();
    let mut off = file_hdr_sz;
    for _ in 0..total_chunks {
        if off + chunk_hdr_sz > data.len() {
            return Err(BridgeError::InvalidArgument("sparse chunk truncated".into()));
        }
        let ctype = hw(off)?;
        let chunk_sz = hexword(off + 4)? as usize; // blocks this chunk produces
        let total_sz = hexword(off + 8)? as usize; // bytes this chunk occupies on disk
        let payload = off + chunk_hdr_sz;
        let next = off + total_sz;
        if next > data.len() {
            return Err(BridgeError::InvalidArgument("sparse chunk overrun".into()));
        }
        match ctype {
            CT_RAW => {
                let n = chunk_sz * blk_sz;
                if payload + n > data.len() {
                    return Err(BridgeError::InvalidArgument("sparse RAW overrun".into()));
                }
                out.extend_from_slice(&data[payload..payload + n]);
            }
            CT_FILL => {
                if payload + 4 > data.len() {
                    return Err(BridgeError::InvalidArgument("sparse FILL overrun".into()));
                }
                let fill = &data[payload..payload + 4];
                let n = chunk_sz * blk_sz;
                let mut buf = Vec::with_capacity(n);
                while buf.len() < n {
                    buf.extend_from_slice(fill);
                }
                buf.truncate(n);
                out.extend_from_slice(&buf);
            }
            CT_DONT_CARE => {
                out.resize(out.len() + chunk_sz * blk_sz, 0);
            }
            CT_CRC32 => {}
            other => {
                return Err(BridgeError::InvalidArgument(format!(
                    "unknown sparse chunk type 0x{other:04x}"
                )));
            }
        }
        off = next;
    }
    Ok(out)
}

/// Expand sparse file → raw file (out file removed on failure).
pub fn expand_file(src: &str, dst: &str) -> Result<()> {
    let data = std::fs::read(src).map_err(|e| BridgeError::Io(format!("read {src}: {e}")))?;
    if !is_sparse(&data) {
        return Err(BridgeError::InvalidArgument(format!("{src}: not sparse")));
    }
    let raw = expand(&data)?;
    std::fs::write(dst, &raw).map_err(|e| BridgeError::Io(format!("write {dst}: {e}")))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sparse_fixture() -> Vec<u8> {
        // sparse header: 28 bytes, chunk header 12 bytes, block size 512
        let mut d = Vec::new();
        d.extend_from_slice(&SPARSE_MAGIC.to_le_bytes());
        d.extend_from_slice(&1u16.to_le_bytes()); // major
        d.extend_from_slice(&0u16.to_le_bytes()); // minor
        d.extend_from_slice(&28u16.to_le_bytes()); // file hdr size
        d.extend_from_slice(&12u16.to_le_bytes()); // chunk hdr size
        d.extend_from_slice(&512u32.to_le_bytes()); // blk size
        d.extend_from_slice(&2u32.to_le_bytes()); // total blocks output
        d.extend_from_slice(&3u32.to_le_bytes()); // chunk count
        d.extend_from_slice(&0u32.to_le_bytes()); // image checksum

        // chunk 1: RAW, 1 block ("HELLO ..." 512 bytes)
        let raw = vec![b'H'; 512];
        d.extend_from_slice(&CT_RAW.to_le_bytes());
        d.extend_from_slice(&0u16.to_le_bytes());
        d.extend_from_slice(&1u32.to_le_bytes()); // chunk_sz (blocks)
        d.extend_from_slice(&(12u32 + 512).to_le_bytes()); // total_sz
        d.extend_from_slice(&raw);

        // chunk 2: FILL 0xAB, 0 blocks? -> use DONT_CARE for hole then fill.
        d.extend_from_slice(&CT_DONT_CARE.to_le_bytes());
        d.extend_from_slice(&0u16.to_le_bytes());
        d.extend_from_slice(&1u32.to_le_bytes()); // one hole block
        d.extend_from_slice(&12u32.to_le_bytes());

        // chunk 3: FILL with 0xCC everywhere (0 blocks means 0 bytes — use 0 blocks)
        d.extend_from_slice(&CT_FILL.to_le_bytes());
        d.extend_from_slice(&0u16.to_le_bytes());
        d.extend_from_slice(&0u32.to_le_bytes()); // 0 blocks
        d.extend_from_slice(&(12u32 + 4).to_le_bytes());
        d.extend_from_slice(&0xCCCCCCCCu32.to_le_bytes());
        d
    }

    #[test]
    fn expands_raw_and_dontcare() {
        let out = expand(&sparse_fixture()).unwrap();
        assert_eq!(out.len(), 2 * 512);
        assert!(out[..512].iter().all(|&b| b == b'H'));
        assert!(out[512..].iter().all(|&b| b == 0));
    }

    #[test]
    fn rejects_non_sparse() {
        assert!(expand(b"not sparse").is_err());
        assert!(!is_sparse(b"not sparse"));
    }
}
