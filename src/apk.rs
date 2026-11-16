//! Minimal, dependency-free reader for an APK's v1 (JAR) signing block.
//!
//! The fake-login provisioning flow puts the DPC's signing-certificate
//! checksum into the QR payload (`PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM`).
//! That value used to be produced by shelling out to `unzip` + `openssl`, which
//! made a user-visible feature (and its unit test) depend on host tooling that
//! is absent on minimal installs and whose output varies between images. Both
//! formats are small and well-specified, so parse them here instead:
//!
//! * zip: End Of Central Directory -> central directory -> first `META-INF/*.RSA`
//!   entry (stored or deflated);
//! * PKCS#7: `ContentInfo { OID signedData, [0] SignedData }`, whose
//!   `certificates [0]` field holds the DER certificates.
//!
//! Anything unexpected (zip64, encryption, unsupported compression, indefinite
//! DER lengths) yields `None`; callers fall back or emit no checksum rather
//! than guessing.

const EOCD_SIG: u32 = 0x0605_4b50;
const CENTRAL_SIG: u32 = 0x0201_4b50;
const LOCAL_SIG: u32 = 0x0403_4b50;

/// `1.2.840.113549.1.7.2` — PKCS#7 `signedData`.
const SIGNED_DATA_OID: &[u8] = &[0x2A, 0x86, 0x48, 0x86, 0xF7, 0x0D, 0x01, 0x07, 0x02];

fn le16(buf: &[u8], off: usize) -> Option<u16> {
    let b = buf.get(off..off.checked_add(2)?)?;
    Some(u16::from_le_bytes([b[0], b[1]]))
}

fn le32(buf: &[u8], off: usize) -> Option<u32> {
    let b = buf.get(off..off.checked_add(4)?)?;
    Some(u32::from_le_bytes([b[0], b[1], b[2], b[3]]))
}

/// Find the End Of Central Directory record. It sits in the last 22 bytes plus
/// up to 64 KiB of archive comment.
fn find_eocd(zip: &[u8]) -> Option<usize> {
    if zip.len() < 22 {
        return None;
    }
    let stop = zip.len().saturating_sub(22 + 0xFFFF);
    let mut i = zip.len() - 22;
    loop {
        if le32(zip, i) == Some(EOCD_SIG) {
            return Some(i);
        }
        if i == stop {
            return None;
        }
        i -= 1;
    }
}

/// Decompress one local-file entry.
fn read_entry(zip: &[u8], local_off: usize, comp_size: usize, method: u16) -> Option<Vec<u8>> {
    if le32(zip, local_off)? != LOCAL_SIG {
        return None;
    }
    let name_len = le16(zip, local_off.checked_add(26)?)? as usize;
    let extra_len = le16(zip, local_off.checked_add(28)?)? as usize;
    let data_off = local_off
        .checked_add(30)?
        .checked_add(name_len)?
        .checked_add(extra_len)?;
    let data = zip.get(data_off..data_off.checked_add(comp_size)?)?;
    match method {
        0 => Some(data.to_vec()),
        8 => {
            use std::io::Read;
            let mut out = Vec::new();
            flate2::read::DeflateDecoder::new(data)
                .read_to_end(&mut out)
                .ok()?;
            Some(out)
        }
        _ => None,
    }
}

/// Read the first zip entry whose name matches `want`, decompressed.
pub fn zip_read_entry(zip: &[u8], want: &dyn Fn(&str) -> bool) -> Option<Vec<u8>> {
    let eocd = find_eocd(zip)?;
    let entries = le16(zip, eocd.checked_add(10)?)? as usize;
    let mut p = le32(zip, eocd.checked_add(16)?)? as usize;
    for _ in 0..entries {
        if le32(zip, p)? != CENTRAL_SIG {
            return None;
        }
        let method = le16(zip, p.checked_add(10)?)?;
        let comp_size = le32(zip, p.checked_add(20)?)? as usize;
        let name_len = le16(zip, p.checked_add(28)?)? as usize;
        let extra_len = le16(zip, p.checked_add(30)?)? as usize;
        let comment_len = le16(zip, p.checked_add(32)?)? as usize;
        let local_off = le32(zip, p.checked_add(42)?)? as usize;
        let name_start = p.checked_add(46)?;
        let name =
            std::str::from_utf8(zip.get(name_start..name_start.checked_add(name_len)?)?).ok()?;
        if want(name) {
            return read_entry(zip, local_off, comp_size, method);
        }
        p = name_start.checked_add(name_len)?;
        p = p.checked_add(extra_len)?.checked_add(comment_len)?;
    }
    None
}

/// Cursor over DER TLVs. Only definite short/long lengths are supported, which
/// is what X.509 and PKCS#7 use.
struct DerReader<'a> {
    buf: &'a [u8],
    pos: usize,
}

impl<'a> DerReader<'a> {
    fn new(buf: &'a [u8]) -> Self {
        Self { buf, pos: 0 }
    }

    /// Read one TLV: returns `(tag, content, full_tlv_including_header)`.
    fn read_tlv(&mut self) -> Option<(u8, &'a [u8], &'a [u8])> {
        let start = self.pos;
        let tag = *self.buf.get(self.pos)?;
        // High-tag-number form (tag & 0x1F == 0x1F) does not occur in these
        // structures; treat it as unsupported instead of misparsing.
        if tag & 0x1F == 0x1F {
            return None;
        }
        self.pos += 1;
        let first = *self.buf.get(self.pos)?;
        self.pos += 1;
        let len = if first & 0x80 == 0 {
            first as usize
        } else {
            let n = (first & 0x7F) as usize;
            if n == 0 || n > 4 {
                return None; // indefinite length or unreasonably large
            }
            let mut len = 0usize;
            for _ in 0..n {
                len = (len << 8) | *self.buf.get(self.pos)? as usize;
                self.pos += 1;
            }
            len
        };
        let end = self.pos.checked_add(len)?;
        let content = self.buf.get(self.pos..end)?;
        self.pos = end;
        Some((tag, content, &self.buf[start..end]))
    }
}

/// Extract the first certificate (its full DER TLV) from a PKCS#7 SignedData.
pub fn pkcs7_first_cert_der(pkcs7: &[u8]) -> Option<&[u8]> {
    let mut outer = DerReader::new(pkcs7);
    let (tag, content, _) = outer.read_tlv()?;
    if tag != 0x30 {
        return None;
    }

    let mut content_info = DerReader::new(content);
    let (oid_tag, oid, _) = content_info.read_tlv()?;
    if oid_tag != 0x06 || oid != SIGNED_DATA_OID {
        return None;
    }
    let (explicit_tag, signed_data, _) = content_info.read_tlv()?;
    if explicit_tag != 0xA0 {
        return None;
    }

    let mut wrapper = DerReader::new(signed_data);
    let (seq_tag, seq_content, _) = wrapper.read_tlv()?;
    if seq_tag != 0x30 {
        return None;
    }

    let mut fields = DerReader::new(seq_content);
    while let Some((tag, certs, _)) = fields.read_tlv() {
        if tag == 0xA0 {
            // certificates [0] IMPLICIT SET OF Certificate — first child wins.
            let mut set = DerReader::new(certs);
            let (cert_tag, _, full) = set.read_tlv()?;
            return if cert_tag == 0x30 { Some(full) } else { None };
        }
    }
    None
}

/// The v1 signing certificate DER of an APK, if it has one.
pub fn v1_cert_der(apk: &[u8]) -> Option<Vec<u8>> {
    let pkcs7 = zip_read_entry(apk, &|name| {
        name.starts_with("META-INF/") && name.ends_with(".RSA")
    })?;
    pkcs7_first_cert_der(&pkcs7).map(<[u8]>::to_vec)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn der_lengths_short_and_long_forms() {
        // 0x04 0x03 "abc"
        let short = [0x04, 0x03, b'a', b'b', b'c'];
        let r = DerReader::new(&short).read_tlv().unwrap();
        assert_eq!(r.0, 0x04);
        assert_eq!(r.1, b"abc");
        assert_eq!(r.2, &short[..]);

        // 0x04 0x81 0x80 <128 bytes> — long form, one length byte
        let mut long = vec![0x04, 0x81, 0x80];
        long.extend(std::iter::repeat(0x41).take(128));
        let r = DerReader::new(&long).read_tlv().unwrap();
        assert_eq!(r.1.len(), 128);

        // Truncated content must be rejected, never panic.
        assert!(DerReader::new(&[0x04, 0x05, b'a']).read_tlv().is_none());
        // Indefinite / oversized lengths are unsupported.
        assert!(DerReader::new(&[0x04, 0x80, 0x00, 0x00])
            .read_tlv()
            .is_none());
        assert!(DerReader::new(&[0x04, 0x85]).read_tlv().is_none());
    }

    #[test]
    fn pkcs7_requires_signed_data_and_a_certificate() {
        // Empty / junk inputs must be None rather than a panic.
        assert!(pkcs7_first_cert_der(&[]).is_none());
        assert!(pkcs7_first_cert_der(&[0x30, 0x00]).is_none());
        assert!(pkcs7_first_cert_der(&[0x31, 0x02, 0x06, 0x00]).is_none());

        // Well-formed envelope with the wrong OID (data, not signedData).
        let mut not_signed = vec![0x30, 0x0C, 0x06, 0x09];
        not_signed.extend_from_slice(&[0x2A, 0x86, 0x48, 0x86, 0xF7, 0x0D, 0x01, 0x07, 0x01]);
        assert!(pkcs7_first_cert_der(&not_signed).is_none());
    }

    #[test]
    fn zip_entry_reader_rejects_junk_without_panicking() {
        assert!(zip_read_entry(&[], &|_| true).is_none());
        assert!(zip_read_entry(b"not a zip at all", &|_| true).is_none());
        // EOCD signature but truncated fields.
        let mut fake = vec![0u8; 22];
        fake[0..4].copy_from_slice(&EOCD_SIG.to_le_bytes());
        assert!(zip_read_entry(&fake, &|_| true).is_none());
    }

    #[test]
    fn extracts_the_bundled_testdpc_v1_cert() {
        // Real APK fixture: the checksum is pinned in flows' fake-login test,
        // this checks the native reader finds the same certificate DER there.
        let path = "mdm_qr/serve/testdpc.apk";
        let Ok(apk) = std::fs::read(path) else {
            return; // fixture absent (source tarball) — nothing to assert
        };
        let cert = v1_cert_der(&apk).expect("v1 cert present");
        assert!(cert.starts_with(&[0x30, 0x82]), "DER SEQUENCE expected");
        assert!(cert.len() > 512, "certificate DER looks too small");
        // The exact value the QR provisioning payload needs. Pinning it here
        // proves the native zip/PKCS#7 path alone produces it (no unzip/openssl)
        // — and that it hashes the certificate DER, which is what
        // PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM is defined as.
        use sha2::Digest;
        let mut h = sha2::Sha256::new();
        h.update(&cert);
        let got = base64::engine::Engine::encode(
            &base64::engine::general_purpose::URL_SAFE_NO_PAD,
            h.finalize(),
        );
        assert_eq!(got, "gJD2YwtOiWJHkSMkkIfLRlj-quNqG1fb6v100QmzM9w");
    }
}
