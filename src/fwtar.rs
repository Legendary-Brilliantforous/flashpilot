//! Samsung firmware tar (.tar/.tar.md5) pipeline — native Rust.
//!
//! Replaces Python's tarfile/lz4/simg2img orchestration: member listing,
//! md5 trailer validation + strip, LZ4/zstd decompression, Android sparse
//! expansion, and staging of flash-ready raw images.

use crate::error::{BridgeError, Result};
use md5::{Digest, Md5};
use std::fs::{self, File};
use std::io::{self, BufReader, BufWriter, Read, Write};
use std::path::{Path, PathBuf};
use tar::Archive;

/// Hex-encode a byte slice (lowercase).
fn to_hex(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push_str(&format!("{b:02x}"));
    }
    s
}

/// Streaming MD5 of `len` bytes read from `r` (stops at EOF or limit).
fn md5_of_stream<R: Read>(r: &mut R, take: u64) -> String {
    let mut h = Md5::new();
    let mut remaining = take;
    let mut buf = [0u8; 65536];
    loop {
        if remaining == 0 {
            break;
        }
        let want = remaining.min(buf.len() as u64) as usize;
        match r.read(&mut buf[..want]) {
            Ok(0) | Err(_) => break,
            Ok(n) => {
                h.update(&buf[..n]);
                remaining -= n as u64;
            }
        }
    }
    to_hex(&h.finalize())
}

/// Validate the `.tar.md5` trailer: 32-hex md5 of the tar body, followed by
/// ` *<filename>\n` (66 bytes total). Returns the expected md5 hex.
pub fn verify_md5_trailer(path: &str) -> Result<String> {
    let meta = fs::metadata(path).map_err(|e| BridgeError::Io(format!("{path}: {e}")))?;
    let body_len = meta.len().saturating_sub(66);
    if body_len == 0 {
        return Err(BridgeError::InvalidArgument(format!(
            "{path} too small for a .tar.md5 trailer"
        )));
    }
    let mut f = BufReader::new(
        File::open(path).map_err(|e| BridgeError::Io(format!("{path}: {e}")))?,
    );
    let body_md5 = md5_of_stream(&mut f, body_len);

    let mut tail = vec![0u8; 66];
    {
        use std::io::Seek;
        let mut f2 = File::open(path).map_err(|e| BridgeError::Io(e.to_string()))?;
        f2.seek(io::SeekFrom::Start(body_len))
            .and_then(|_| f2.read_exact(&mut tail))
            .map_err(|e| BridgeError::Io(e.to_string()))?;
    }
    let tail_txt = String::from_utf8_lossy(&tail);
    let trailer_md5: String = tail_txt.chars().take(32).collect();
    if trailer_md5 != body_md5 {
        return Err(BridgeError::InvalidArgument(format!(
            "md5 trailer mismatch: embedded {trailer_md5} != computed {body_md5}"
        )));
    }
    Ok(body_md5)
}

/// True when the file name ends with `.md5` (i.e. it is `*.tar.md5` or the
/// archive was signed with a trailer).
pub fn has_md5_trailer(path: &str) -> bool {
    Path::new(path)
        .extension()
        .and_then(|e| e.to_str())
        .map(|ext| ext.eq_ignore_ascii_case("md5"))
        .unwrap_or(false)
}

/// Strip the 66-byte md5 trailer and write the pure tar payload to a
/// cache file under the system temp dir. Returns `(out_path, md5_hex)`.
pub fn strip_md5_trailer(path: &str) -> Result<(String, String)> {
    let len = fs::metadata(path)
        .map_err(|e| BridgeError::Io(format!("{path}: {e}")))?
        .len()
        .saturating_sub(66);
    if len == 0 {
        return Err(BridgeError::InvalidArgument(format!(
            "{path} too small for a trailer"
        )));
    }
    let mut r = BufReader::new(File::open(path).map_err(|e| BridgeError::Io(e.to_string()))?);
    let name = Path::new(path)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("firmware");
    let out_path = std::env::temp_dir()
        .join(format!("{name}.tar"))
        .to_string_lossy()
        .to_string();
    let mut w = BufWriter::new(File::create(&out_path).map_err(|e| BridgeError::Io(e.to_string()))?);
    // Stream-copy only the `len`-byte payload.
    let mut remaining = len;
    let mut buf = [0u8; 65536];
    let mut h = Md5::new();
    loop {
        if remaining == 0 {
            break;
        }
        let want = remaining.min(buf.len() as u64) as usize;
        let n = r.read(&mut buf[..want]).map_err(|e| BridgeError::Io(e.to_string()))?;
        if n == 0 {
            break;
        }
        w.write_all(&buf[..n]).map_err(|e| BridgeError::Io(e.to_string()))?;
        h.update(&buf[..n]);
        remaining -= n as u64;
    }
    w.flush().map_err(|e| BridgeError::Io(e.to_string()))?;
    Ok((out_path, to_hex(&h.finalize())))
}

/// List member names of a tar archive (skips directory entries).
pub fn tar_member_names(path: &str) -> Result<Vec<String>> {
    let f = File::open(path).map_err(|e| BridgeError::Io(format!("{path}: {e}")))?;
    let mut ar = Archive::new(f);
    let mut names = Vec::new();
    for e in ar
        .entries()
        .map_err(|e| BridgeError::Io(format!("tar entries {path}: {e}")))?
    {
        let e = e.map_err(|e| BridgeError::Io(e.to_string()))?;
        let name = e
            .path()
            .map_err(|e| BridgeError::Io(e.to_string()))?
            .to_string_lossy()
            .to_string();
        if !name.ends_with('/') {
            names.push(name);
        }
    }
    Ok(names)
}

/// Extract a tar archive into `out_dir` (creating directories as needed) and
/// return extracted file paths in tar order.
pub fn extract_tar(path: &str, out_dir: &Path) -> Result<Vec<PathBuf>> {
    let f = File::open(path).map_err(|e| BridgeError::Io(format!("{path}: {e}")))?;
    let mut ar = Archive::new(f);
    let mut out = Vec::new();
    for e in ar
        .entries()
        .map_err(|e| BridgeError::Io(format!("tar entries {path}: {e}")))?
    {
        let mut e = e.map_err(|e| BridgeError::Io(e.to_string()))?;
        let name = e
            .path()
            .map_err(|e| BridgeError::Io(e.to_string()))?
            .to_string_lossy()
            .to_string();
        if name.ends_with('/') {
            continue;
        }
        // Path traversal guard: a malicious firmware tarball must not escape
        // the staging directory via `..` components or absolute members
        // (Path::join does not sanitize either). Reject the whole archive.
        let member = std::path::Path::new(&name);
        if member.is_absolute()
            || member
                .components()
                .any(|c| matches!(c, std::path::Component::ParentDir))
        {
            return Err(BridgeError::Firmware(
                crate::error::FirmwareError::ArchiveError(format!(
                    "tar member escapes staging dir: {name}"
                )),
            ));
        }
        let dest = out_dir.join(&name);
        if let Some(parent) = dest.parent() {
            fs::create_dir_all(parent).map_err(|e| BridgeError::Io(e.to_string()))?;
        }
        let mut w = File::create(&dest).map_err(|e| BridgeError::Io(e.to_string()))?;
        io::copy(&mut e, &mut w).map_err(|e| BridgeError::Io(e.to_string()))?;
        out.push(dest);
    }
    Ok(out)
}

/// Decompress an LZ4 frame file to `out_path`.
fn decompress_lz4(src: &Path, out_path: &Path) -> Result<()> {
    use lz4_flex::frame::FrameDecoder;
    let mut r = FrameDecoder::new(BufReader::new(
        File::open(src).map_err(|e| BridgeError::Io(format!("{src:?}: {e}")))?,
    ));
    let mut w = BufWriter::new(
        File::create(out_path).map_err(|e| BridgeError::Io(format!("{out_path:?}: {e}")))?,
    );
    io::copy(&mut r, &mut w)
        .map_err(|e| BridgeError::Io(format!("lz4 dec {}: {e}", src.display())))?;
    Ok(())
}

/// Decompress a zstd stream file to `out_path`.
fn decompress_zstd(src: &Path, out_path: &Path) -> Result<()> {
    let data = fs::read(src).map_err(|e| BridgeError::Io(format!("{src:?}: {e}")))?;
    let dec = zstd::decode_all(io::Cursor::new(&data[..]))
        .map_err(|e| BridgeError::InvalidArgument(format!("zstd: {e}")))?;
    fs::write(out_path, &dec).map_err(|e| BridgeError::Io(e.to_string()))?;
    Ok(())
}

/// Prepare one extracted member: decompress (LZ4/zstd) then expand sparse.
/// Returns the final raw image path.
pub fn prepare_member(path: &Path) -> Result<PathBuf> {
    let mut current = path.to_path_buf();
    let name = current
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("")
        .to_string();
    if name.ends_with(".lz4") {
        let out = current.with_extension("");
        decompress_lz4(&current, &out)?;
        current = out;
    } else if name.ends_with(".zst") || name.ends_with(".zstd") {
        let out = current.with_extension("");
        decompress_zstd(&current, &out)?;
        current = out;
    }
    // Sparse: expand if the magic is present.
    if let Ok(mut f) = File::open(&current) {
        let mut magic = [0u8; 4];
        if f.read_exact(&mut magic).is_ok()
            && u32::from_le_bytes(magic) == crate::sparse::SPARSE_MAGIC
        {
            let raw = current.with_extension("raw");
            crate::sparse::expand_file(
                &current.to_string_lossy(),
                &raw.to_string_lossy(),
            )?;
            current = raw;
        }
    }
    Ok(current)
}

/// Stage a full firmware archive: md5 check + strip trailer, extract tar,
/// decompress members, expand sparse. Returns ordered (member_name, path).
pub fn prepare_archive(tar_path: &str, out_dir: &Path) -> Result<Vec<(String, PathBuf)>> {
    fs::create_dir_all(out_dir).map_err(|e| BridgeError::Io(e.to_string()))?;
    let work = if has_md5_trailer(tar_path) {
        let md5 = verify_md5_trailer(tar_path)?;
        eprintln!("[archive] tar.md5 trailer verified: {md5}");
        let (plain, _) = strip_md5_trailer(tar_path)?;
        plain
    } else {
        tar_path.to_string()
    };
    let paths = extract_tar(&work, out_dir)?;
    // Parallel member preparation: every member is decompressed (LZ4/zstd)
    // and sparse-expanded independently - preparing them on threads gives
    // the same result in a fraction of the wall time on multi-core hosts
    // (Samsung super.img members are multi-GB each).
    let results: Vec<std::result::Result<(String, PathBuf), BridgeError>> =
        std::thread::scope(|scope| {
            let handles: Vec<_> = paths
                .iter()
                .map(|p| {
                    let p = p.clone();
                    scope.spawn(move || {
                        let name = p
                            .file_name()
                            .and_then(|n| n.to_str())
                            .unwrap_or("")
                            .to_string();
                        let prepared = prepare_member(&p)?;
                        Ok((name, prepared))
                    })
                })
                .collect();
            handles.into_iter().map(|h| h.join().unwrap()).collect()
        });
    let mut staged = Vec::new();
    // Preserve tar order: results are collected in spawn order.
    for r in results {
        staged.push(r?);
    }
    Ok(staged)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::error::FirmwareError;

    /// Build a real tar member and append a valid 66-byte `.tar.md5` trailer.
    fn make_tar_md5(tmp: &tempfile::TempDir) -> (String, String) {
        let body = b"hello firmware".to_vec();
        let mut b = tar::Builder::new(Vec::new());
        let mut h = tar::Header::new_ustar();
        h.set_path("test.img").unwrap();
        h.set_size(body.len() as u64);
        h.set_mode(0o644);
        h.set_cksum();  // MUST be called last (computes checksum over the header)
        b.append(&h, body.as_slice()).unwrap();
        let tar_bytes = b.into_inner().unwrap();
        let md5 = to_hex(&Md5::digest(&tar_bytes));

        let mut full = tar_bytes.clone();
        let fname = "fw.tar";
        let mut trailer = format!("{md5}  {fname}\n").into_bytes();
        trailer.resize(66, 0);
        full.extend_from_slice(&trailer);

        let path = tmp.path().join("fw.tar.md5");
        fs::write(&path, &full).unwrap();
        (path.to_string_lossy().to_string(), md5)
    }

    #[test]
    fn trailer_validates_and_strips() {
        let tmp = tempfile::tempdir().unwrap();
        let (p, expected) = make_tar_md5(&tmp);
        let md5 = verify_md5_trailer(&p).unwrap();
        assert_eq!(md5, expected);
        let (plain, again) = strip_md5_trailer(&p).unwrap();
        assert_eq!(again, expected);
        assert_eq!(tar_member_names(&plain).unwrap(), vec!["test.img"]);
        let member = extract_tar(&plain, tmp.path()).unwrap().pop().unwrap();
        assert_eq!(fs::read(&member).unwrap(), b"hello firmware");
    }

    #[test]
    fn trailer_rejects_tampered() {
        let tmp = tempfile::tempdir().unwrap();
        let (p, _) = make_tar_md5(&tmp);
        let mut data = fs::read(&p).unwrap();
        // Flip a byte inside the tar body (first byte of member content).
        let mut data = data;
        data[0] ^= 0xFF;
        // but keep the trailer intact (last 66 bytes untouched)
        fs::write(&p, &data).unwrap();
        assert!(verify_md5_trailer(&p).is_err());
    }

    #[test]
    fn prepare_archive_stages_plain_tar_in_order() {
        // Exercises the parallel member-preparation path end-to-end with a
        // multi-member plain tar: staging must preserve tar order.
        let tmp = tempfile::tempdir().unwrap();
        let mut b = tar::Builder::new(Vec::new());
        for (i, name) in ["boot.img", "recovery.img", "vbmeta.img"].iter().enumerate() {
            let body = vec![b'A' + i as u8; 1024];
            let mut h = tar::Header::new_ustar();
            h.set_path(name).unwrap();
            h.set_size(body.len() as u64);
            h.set_mode(0o644);
            h.set_cksum();
            b.append(&h, body.as_slice()).unwrap();
        }
        let tar_bytes = b.into_inner().unwrap();
        let path = tmp.path().join("fw.tar");
        fs::write(&path, &tar_bytes).unwrap();
        let out_dir = tmp.path().join("stage");
        let staged = prepare_archive(&path.to_string_lossy(), &out_dir).unwrap();
        let names: Vec<&str> = staged.iter().map(|(n, _)| n.as_str()).collect();
        assert_eq!(names, vec!["boot.img", "recovery.img", "vbmeta.img"]);
        for (name, p) in &staged {
            assert!(p.exists(), "{name} not staged");
            assert_eq!(fs::metadata(p).unwrap().len(), 1024);
        }
    }

    #[test]
    fn plain_tar_passes_through_without_trailer() {
        let tmp = tempfile::tempdir().unwrap();
        let body = b"firmware payload".to_vec();
        let path = tmp.path().join("fw.tar");
        fs::write(&path, &body).unwrap();
        assert!(!has_md5_trailer(&path.to_string_lossy()));
    }

    /// Build a tar with an arbitrary (possibly hostile) member name by
    /// hand-crafting the ustar header: the `tar` crate's safe builder
    /// refuses `..`/absolute paths, but real malicious archives are raw
    /// bytes — which is exactly what extract_tar must reject.
    fn make_raw_tar(tmp: &tempfile::TempDir, member: &str, filename: &str) -> String {
        let body = b"evil";
        let mut hdr = [0u8; 512];
        let name = member.as_bytes();
        assert!(name.len() < 100, "member name too long for ustar");
        hdr[..name.len()].copy_from_slice(name);
        hdr[100..108].copy_from_slice(b"0000644\0");
        let size = format!("{:011o}\0", body.len());
        hdr[124..136].copy_from_slice(size.as_bytes());
        hdr[156] = b'0';
        hdr[257..263].copy_from_slice(b"ustar\0");
        hdr[148..156].copy_from_slice(b"        ");
        let sum: u32 = hdr.iter().map(|b| *b as u32).sum();
        let cks = format!("{sum:06o}\0 ");
        hdr[148..156].copy_from_slice(cks.as_bytes());
        let mut tar_bytes = hdr.to_vec();
        let mut content = [0u8; 512];
        content[..body.len()].copy_from_slice(body);
        tar_bytes.extend_from_slice(&content);
        tar_bytes.extend_from_slice(&[0u8; 1024]); // end-of-archive
        let path = tmp.path().join(filename);
        fs::write(&path, &tar_bytes).unwrap();
        path.to_string_lossy().to_string()
    }

    #[test]
    fn traversal_member_is_rejected() {
        let tmp = tempfile::tempdir().unwrap();
        let stage = tmp.path().join("stage");
        for (i, evil) in ["../escape.img", "../../escape.img", "sub/../../escape.img"]
            .iter()
            .enumerate()
        {
            let p = make_raw_tar(&tmp, evil, &format!("evil{i}.tar"));
            let err = extract_tar(&p, &stage).unwrap_err();
            assert!(
                matches!(err, BridgeError::Firmware(FirmwareError::ArchiveError(_))),
                "member {evil}: unexpected {err}"
            );
        }
        assert!(
            !tmp.path().join("escape.img").exists(),
            "traversal member escaped the staging dir"
        );
    }

    #[test]
    fn absolute_member_is_rejected() {
        let tmp = tempfile::tempdir().unwrap();
        let stage = tmp.path().join("stage");
        let p = make_raw_tar(&tmp, "/tmp/absolute.img", "abs.tar");
        let err = extract_tar(&p, &stage).unwrap_err();
        assert!(
            matches!(err, BridgeError::Firmware(FirmwareError::ArchiveError(_))),
            "unexpected {err}"
        );
    }
}
