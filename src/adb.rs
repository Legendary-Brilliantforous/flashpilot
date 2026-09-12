//! Native ADB client over USB (no platform-tools dependency).
//!
//! Implements the ADB wire protocol directly on bulk endpoints (interface
//! 255/66/1) with kernel-driver detach: 24-byte message framing
//! (command/arg0/arg1/len/checksum/magic), CNXN handshake, RSA-SHA256/SHA-1
//! AUTH (reusing `~/.android/adbkey`, generated when missing), the `shell:`
//! service, and the `sync:` service (STAT/RECV/SEND for pull/push).
//!
//! One CLI invocation opens one USB session and runs one service — no
//! multiplexing, no daemon. Device states mirror `adb devices`: `device`
//! (authorized), `unauthorized` (key rejected / user hasn't tapped Allow),
//! `no permissions` (USB claim failed).
//!
//! Key layout notes (AOSP adb_auth_host / transport_usb):
//! * AUTH TOKEN is 20 bytes; SIGNATURE is PKCS#1 v1.5 over the token.
//! * adbkey.pub is base64 of the 524-byte RSAPublicKey struct (64 LE words).

use crate::config::{get_read_chunk_secs, OperationContext};
use crate::error::{BridgeError, Result, UsbError};
use crate::usb::{self, UsbDevice};
use num_bigint::BigUint;
use num_traits::One;
use rsa::traits::{PrivateKeyParts, PublicKeyParts};
use std::collections::HashMap;
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::time::{Duration, Instant};

// ADB USB interface triple.
const ADB_CLASS: u8 = 255;
const ADB_SUBCLASS: u8 = 66;
const ADB_PROTO: u8 = 1;

// Message commands (ASCII LE).
const A_CNXN: u32 = 0x4e58_4e43;
const A_AUTH: u32 = 0x4854_5541;
const A_OPEN: u32 = 0x4e45_504f;
const A_OKAY: u32 = 0x5941_4b4f;
const A_CLSE: u32 = 0x4553_4c43;
const A_WRTE: u32 = 0x4552_5457;

// AUTH subtypes.
const AUTH_TOKEN: u32 = 1;
const AUTH_SIGNATURE: u32 = 2;
const AUTH_RSAPUBLICKEY: u32 = 3;

const A_VERSION: u32 = 0x0100_0000;
const MAXDATA: usize = 4096;
const TOKEN_LEN: usize = 20;
/// ADB read chunk timeout (overridable via config)
// const DEFAULT_READ_CHUNK_SECS: u64 = 2;

// RSA-2048 adb key layout.
const RSA_WORDS: usize = 64;
const RSA_BYTES: usize = 256;

// PKCS#1 v1.5 DigestInfo prefixes.
const SHA256_PREFIX: &[u8] = &[
    0x30, 0x31, 0x30, 0x0d, 0x06, 0x09, 0x60, 0x86, 0x48, 0x01, 0x65, 0x03, 0x04, 0x02,
    0x01, 0x05, 0x00, 0x04, 0x20,
];
const SHA1_PREFIX: &[u8] = &[
    0x30, 0x21, 0x30, 0x09, 0x06, 0x05, 0x2b, 0x0e, 0x03, 0x02, 0x1a, 0x05, 0x00, 0x04,
    0x14,
];

#[derive(Debug)]
struct Msg {
    cmd: u32,
    arg0: u32,
    arg1: u32,
    payload: Vec<u8>,
}

/// ADB checksum: wrapping sum of payload bytes.
fn checksum(data: &[u8]) -> u32 {
    data.iter().fold(0u32, |a, &b| a.wrapping_add(b as u32))
}

fn encode_msg(cmd: u32, arg0: u32, arg1: u32, payload: &[u8]) -> Vec<u8> {
    let mut v = Vec::with_capacity(24 + payload.len());
    v.extend_from_slice(&cmd.to_le_bytes());
    v.extend_from_slice(&arg0.to_le_bytes());
    v.extend_from_slice(&arg1.to_le_bytes());
    v.extend_from_slice(&(payload.len() as u32).to_le_bytes());
    v.extend_from_slice(&checksum(payload).to_le_bytes());
    v.extend_from_slice(&(cmd ^ 0xFFFF_FFFF).to_le_bytes());
    v.extend_from_slice(payload);
    v
}

fn decode_header(raw: &[u8; 24]) -> Result<(u32, u32, u32, u32)> {
    let cmd = u32::from_le_bytes(raw[0..4].try_into().unwrap());
    let a0 = u32::from_le_bytes(raw[4..8].try_into().unwrap());
    let a1 = u32::from_le_bytes(raw[8..12].try_into().unwrap());
    let len = u32::from_le_bytes(raw[12..16].try_into().unwrap());
    let sum = u32::from_le_bytes(raw[16..20].try_into().unwrap());
    let magic = u32::from_le_bytes(raw[20..24].try_into().unwrap());
    if magic != cmd ^ 0xFFFF_FFFF {
        return Err(BridgeError::Protocol(
            crate::error::ProtocolError::UnexpectedResponse(format!(
                "adb magic mismatch for cmd 0x{cmd:08x}"
            )),
        ));
    }
    if len > 1024 * 1024 {
        return Err(BridgeError::Protocol(
            crate::error::ProtocolError::UnexpectedResponse(format!("adb absurd length {len}")),
        ));
    }
    let _ = sum;
    Ok((cmd, a0, a1, len))
}

// ---------------------------------------------------------------------------
// Minimal DER reader/writer (PKCS#8 <-> RSA components, no new crates).
// ---------------------------------------------------------------------------

struct Der<'a> {
    b: &'a [u8],
    pos: usize,
}

impl<'a> Der<'a> {
    fn new(b: &'a [u8]) -> Self {
        Der { b, pos: 0 }
    }
    fn rest_len(&self) -> usize {
        self.b.len().saturating_sub(self.pos)
    }
    fn read_byte(&mut self) -> Result<u8> {
        if self.pos >= self.b.len() {
            return Err(BridgeError::InvalidArgument("DER truncated".to_string()));
        }
        let v = self.b[self.pos];
        self.pos += 1;
        Ok(v)
    }
    fn read_len(&mut self) -> Result<usize> {
        let first = self.read_byte()? as usize;
        if first < 0x80 {
            return Ok(first);
        }
        let n = first & 0x7f;
        if n == 0 || n > 4 {
            return Err(BridgeError::InvalidArgument("DER bad length".to_string()));
        }
        let mut len = 0usize;
        for _ in 0..n {
            len = (len << 8) | (self.read_byte()? as usize);
        }
        Ok(len)
    }
    fn read_tlv(&mut self) -> Result<(u8, &'a [u8])> {
        let tag = self.read_byte()?;
        let len = self.read_len()?;
        if len > self.rest_len() {
            return Err(BridgeError::InvalidArgument("DER overrun".to_string()));
        }
        let s = &self.b[self.pos..self.pos + len];
        self.pos += len;
        Ok((tag, s))
    }
    fn expect_seq(&mut self) -> Result<Der<'a>> {
        let (tag, body) = self.read_tlv()?;
        if tag != 0x30 {
            return Err(BridgeError::InvalidArgument("DER expected SEQUENCE".to_string()));
        }
        Ok(Der::new(body))
    }
    fn expect_int(&mut self) -> Result<Vec<u8>> {
        let (tag, body) = self.read_tlv()?;
        if tag != 0x02 {
            return Err(BridgeError::InvalidArgument("DER expected INTEGER".to_string()));
        }
        Ok(body.to_vec())
    }
}

fn der_len(len: usize) -> Vec<u8> {
    if len < 0x80 {
        vec![len as u8]
    } else {
        let mut b = Vec::new();
        let mut v = len;
        let mut tmp = Vec::new();
        while v > 0 {
            tmp.push((v & 0xff) as u8);
            v >>= 8;
        }
        b.push(0x80 | (tmp.len() as u8));
        tmp.reverse();
        b.extend_from_slice(&tmp);
        b
    }
}

fn der_tlv(tag: u8, content: &[u8]) -> Vec<u8> {
    let mut v = vec![tag];
    v.extend_from_slice(&der_len(content.len()));
    v.extend_from_slice(content);
    v
}

fn der_int(bytes: &[u8]) -> Vec<u8> {
    let mut b: &[u8] = bytes;
    while b.len() > 1 && b[0] == 0x00 {
        b = &b[1..];
    }
    let mut content = Vec::new();
    if b.is_empty() || b[0] & 0x80 != 0 {
        content.push(0x00);
    }
    content.extend_from_slice(b);
    der_tlv(0x02, &content)
}

/// Decode an adbkey file: PEM-armored (modern platform-tools) or raw DER
/// (older ones). Returns the PKCS#8 DER bytes either way.
fn decode_key_file(raw: &[u8]) -> Result<Vec<u8>> {
    if !raw.starts_with(b"-----BEGIN") {
        return Ok(raw.to_vec());
    }
    let text = String::from_utf8_lossy(raw);
    let mut b64 = String::new();
    let mut in_body = false;
    for line in text.lines() {
        let l = line.trim();
        if l.starts_with("-----BEGIN") {
            in_body = true;
            continue;
        }
        if l.starts_with("-----END") {
            break;
        }
        if in_body {
            b64.push_str(l);
        }
    }
    base64::Engine::decode(&base64::engine::general_purpose::STANDARD, &b64)
        .map_err(|e| BridgeError::InvalidArgument(format!("adbkey base64: {e}")))
}

/// Parse PKCS#8 DER adbkey -> (n, e, d, p, q) as BigUint.
fn parse_pkcs8(der: &[u8]) -> Result<(BigUint, BigUint, BigUint, BigUint, BigUint)> {
    let mut top = Der::new(der);
    let mut outer = top.expect_seq()?;
    let _version = outer.expect_int()?;
    let mut alg = outer.expect_seq()?;
    let (oid_tag, oid) = alg.read_tlv()?;
    const RSA_OID: &[u8] = &[0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01, 0x01];
    if oid_tag != 0x06 || oid != RSA_OID {
        return Err(BridgeError::InvalidArgument("adbkey is not an RSA key".to_string()));
    }
    let (null_tag, _) = alg.read_tlv()?;
    if null_tag != 0x05 {
        return Err(BridgeError::InvalidArgument("adbkey alg params not NULL".to_string()));
    }
    let (oct_tag, inner) = outer.read_tlv()?;
    if oct_tag != 0x04 {
        return Err(BridgeError::InvalidArgument("adbkey missing private key octets".to_string()));
    }
    let mut pkcs1 = Der::new(inner);
    let mut seq = pkcs1.expect_seq()?;
    let _v = seq.expect_int()?;
    let ints: Vec<BigUint> = (0..8)
        .map(|_| seq.expect_int().map(|b| BigUint::from_bytes_be(&b)))
        .collect::<Result<Vec<_>>>()?;
    Ok((ints[0].clone(), ints[1].clone(), ints[2].clone(), ints[3].clone(), ints[4].clone()))
}

/// RSA components for PKCS#8 encoding.
struct RsaParts<'a> {
    n: &'a BigUint,
    e: &'a BigUint,
    d: &'a BigUint,
    p: &'a BigUint,
    q: &'a BigUint,
    dp: &'a BigUint,
    dq: &'a BigUint,
    qinv: &'a BigUint,
}

/// Encode key parts as PKCS#8 DER.
fn encode_pkcs8(k: &RsaParts) -> Vec<u8> {
    let bi = |x: &BigUint| der_int(&x.to_bytes_be());
    let mut inner = Vec::new();
    inner.extend_from_slice(&der_int(&[0x00])); // version
    for x in [k.n, k.e, k.d, k.p, k.q, k.dp, k.dq, k.qinv] {
        inner.extend_from_slice(&bi(x));
    }
    let inner_seq = der_tlv(0x30, &inner);
    let mut oid = vec![0x06, 0x09, 0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01, 0x01];
    oid.extend_from_slice(&[0x05, 0x00]);
    let alg = der_tlv(0x30, &oid);
    let mut outer = Vec::new();
    outer.extend_from_slice(&der_int(&[0x00]));
    outer.extend_from_slice(&alg);
    outer.extend_from_slice(&der_tlv(0x04, &inner_seq));
    der_tlv(0x30, &outer)
}

// ---------------------------------------------------------------------------
// RSA key: load ~/.android/adbkey or generate; sign; adb pubkey blob.
// ---------------------------------------------------------------------------

fn adb_key_path() -> std::path::PathBuf {
    let home = std::env::var("HOME").unwrap_or_else(|_| "/root".to_string());
    std::path::Path::new(&home).join(".android").join("adbkey")
}

struct AdbKey {
    n: BigUint,
    e: BigUint,
    d: BigUint,
}

/// rsa::BigUint is num-bigint-dig (a fork), not our num-bigint: bridge
/// through big-endian bytes (both sides have stable byte APIs).
fn rsa_to_nbi(x: &rsa::BigUint) -> BigUint {
    BigUint::from_bytes_be(&x.to_bytes_be())
}

impl AdbKey {
    fn k_bytes(&self) -> usize {
        self.n.bits().div_ceil(8) as usize
    }

    /// EMSA-PKCS1-v1_5 sign (manual modpow; avoids signing-trait API).
    fn sign(&self, token: &[u8], use_sha256: bool) -> Vec<u8> {
        let digest: Vec<u8> = if use_sha256 {
            use sha2::{Digest, Sha256};
            Sha256::digest(token).to_vec()
        } else {
            use sha1::{Digest, Sha1};
            Sha1::digest(token).to_vec()
        };
        let prefix = if use_sha256 { SHA256_PREFIX } else { SHA1_PREFIX };
        let k = self.k_bytes();
        let mut t = Vec::with_capacity(prefix.len() + digest.len());
        t.extend_from_slice(prefix);
        t.extend_from_slice(&digest);
        let mut em = vec![0xffu8; k];
        em[0] = 0x00;
        em[1] = 0x01;
        let t_off = k - t.len();
        em[t_off - 1] = 0x00;
        em[t_off..].copy_from_slice(&t);
        let m = BigUint::from_bytes_be(&em);
        let s = m.modpow(&self.d, &self.n);
        let mut sig = s.to_bytes_be();
        if sig.len() < k {
            let mut padded = vec![0u8; k - sig.len()];
            padded.extend_from_slice(&sig);
            sig = padded;
        }
        sig
    }

    /// adb RSAPublicKey blob: base64(524-byte struct) + " user@host".
    fn pubkey_string(&self) -> Result<String> {
        if self.k_bytes() != RSA_BYTES {
            return Err(BridgeError::InvalidArgument(format!(
                "adb needs a 2048-bit key, have {} bits",
                self.n.bits()
            )));
        }
        let n0 = (self.n.clone() % BigUint::from(0x1_0000_0000u64))
            .to_u32_digits()
            .first()
            .copied()
            .unwrap_or(0);
        // n0inv = -1/n0 mod 2^32 via Newton iteration.
        let mut inv = 1u32;
        for _ in 0..5 {
            inv = inv.wrapping_mul(2u32.wrapping_sub(n0.wrapping_mul(inv)));
        }
        let n0inv = inv.wrapping_neg();
        // rr = R^2 mod n with R = 2^2048.
        let r = BigUint::from(2u32).modpow(&BigUint::from(4096u32), &self.n);
        let n_be = {
            let mut b = self.n.to_bytes_be();
            if b.len() < RSA_BYTES {
                let mut p = vec![0u8; RSA_BYTES - b.len()];
                p.extend_from_slice(&b);
                b = p;
            }
            b
        };
        let word = |bytes: &[u8], i: usize| -> u32 {
            // i-th little-endian 32-bit word of the 256-byte big-endian int.
            let o = RSA_BYTES - (i + 1) * 4;
            u32::from_be_bytes([bytes[o], bytes[o + 1], bytes[o + 2], bytes[o + 3]])
        };
        let mut blob = Vec::with_capacity(4 * (2 + 2 * RSA_WORDS) + 4);
        blob.extend_from_slice(&(RSA_WORDS as u32).to_le_bytes());
        blob.extend_from_slice(&n0inv.to_le_bytes());
        for i in 0..RSA_WORDS {
            blob.extend_from_slice(&word(&n_be, i).to_le_bytes());
        }
        let mut rr_be = r.to_bytes_be();
        if rr_be.len() < RSA_BYTES {
            let mut p = vec![0u8; RSA_BYTES - rr_be.len()];
            p.extend_from_slice(&rr_be);
            rr_be = p;
        }
        for i in 0..RSA_WORDS {
            blob.extend_from_slice(&word(&rr_be, i).to_le_bytes());
        }
        let exp = self.e.to_bytes_be();
        let exp_u32 = if exp.len() <= 4 {
            let mut p = vec![0u8; 4 - exp.len()];
            p.extend_from_slice(&exp);
            u32::from_be_bytes([p[0], p[1], p[2], p[3]])
        } else {
            return Err(BridgeError::InvalidArgument("adb RSA exponent too large".to_string()));
        };
        blob.extend_from_slice(&exp_u32.to_le_bytes());
        Ok(format!(
            "{} user@host",
            base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &blob)
        ))
    }
}

/// Backoff between AUTH token rounds: 100ms doubling, capped at 2s.
/// Pure function so the schedule is unit-tested, not hoped-for.
fn auth_backoff_ms(round: u32) -> u64 {
    100u64.saturating_mul(1u64 << round.min(5)).min(2000)
}

fn load_or_create_key() -> Result<AdbKey> {
    let path = adb_key_path();
    if path.exists() {
        let raw = fs::read(&path).map_err(|e| BridgeError::Io(e.to_string()))?;
        let der = decode_key_file(&raw)?;
        let (n, e, d, _p, _q) = parse_pkcs8(&der)?;
        return Ok(AdbKey { n, e, d });
    }
    // Generate fresh 2048-bit key (first run / CI machines). rsa::BigUint
    // IS num_bigint::BigUint (re-exported), so no conversion is needed.
    // One-time cost (~1s prime search), persisted forever — announced so
    // the pause is never mistaken for a hang.
    eprintln!("[adb] generating fresh ADB keypair (one-time, ~1s)...");
    let mut rng = rand::thread_rng();
    let privk = rsa::RsaPrivateKey::new(&mut rng, 2048)
        .map_err(|e| BridgeError::Internal(format!("rsa keygen: {e}")))?;
    let one = BigUint::one();
    let n = rsa_to_nbi(privk.n());
    let e = rsa_to_nbi(privk.e());
    let d = rsa_to_nbi(privk.d());
    let primes = privk.primes();
    if primes.len() < 2 {
        return Err(BridgeError::Internal("rsa keygen gave <2 primes".to_string()));
    }
    let (p, q) = (rsa_to_nbi(&primes[0]), rsa_to_nbi(&primes[1]));
    let dp = &d % (&p - &one);
    let dq = &d % (&q - &one);
    let qinv = {
        // q^-1 mod p via Fermat (p prime): q^(p-2) mod p.
        let two = BigUint::from(2u32);
        q.modpow(&(&p - &two), &p)
    };
    let der = encode_pkcs8(&RsaParts {
        n: &n,
        e: &e,
        d: &d,
        p: &p,
        q: &q,
        dp: &dp,
        dq: &dq,
        qinv: &qinv,
    });
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    fs::write(&path, &der).map_err(|e| BridgeError::Io(e.to_string()))?;
    let _ = fs::set_permissions(&path, fs::Permissions::from_mode(0o600));
    let pubkey = AdbKey { n: n.clone(), e: e.clone(), d: d.clone() }.pubkey_string()?;
    let _ = fs::write(path.with_extension("pub"), format!("{pubkey}\n"));
    Ok(AdbKey { n, e, d })
}

// ---------------------------------------------------------------------------
// USB session.
// ---------------------------------------------------------------------------

struct Session {
    dev: UsbDevice,
    ep_in: u8,
    ep_out: u8,
    next_id: u32,
    deadline: Instant,
    ctx: Option<OperationContext>,
}

impl Session {
    fn check_deadline(&self) -> Result<()> {
        if Instant::now() > self.deadline {
            return Err(BridgeError::Usb(UsbError::Timeout));
        }
        Ok(())
    }

    fn write_msg(&self, cmd: u32, a0: u32, a1: u32, payload: &[u8]) -> Result<()> {
        let pkt = encode_msg(cmd, a0, a1, payload);
        // ADB payloads never exceed MAXDATA here; chunk by endpoint MPS.
        let _timeout = Duration::from_secs(get_read_chunk_secs(self.ctx.as_ref()));
        self.dev
            .write_bulk(self.ep_out, &pkt, Duration::from_secs(get_read_chunk_secs(self.ctx.as_ref())))
            .map(|_| ())
    }

    fn read_msg(&self) -> Result<Msg> {
        self.check_deadline()?;
        let mut hdr = [0u8; 24];
        self.dev.read_exact(self.ep_in, &mut hdr, Duration::from_secs(get_read_chunk_secs(self.ctx.as_ref())))?;
        let (cmd, a0, a1, len) = decode_header(&hdr)?;
        let mut payload = vec![0u8; len as usize];
        if len > 0 {
            self.dev.read_exact(self.ep_in, &mut payload, Duration::from_secs(get_read_chunk_secs(self.ctx.as_ref())))?;
            let (_, _, _, _) = decode_header(&hdr)?; // re-validated; checksum below
            let (_, got) = (len, checksum(&payload));
            let expected = u32::from_le_bytes(hdr[16..20].try_into().unwrap());
            if got != expected {
                return Err(BridgeError::Protocol(
                    crate::error::ProtocolError::ChecksumMismatch,
                ));
            }
        }
        Ok(Msg { cmd, arg0: a0, arg1: a1, payload })
    }

    /// CNXN handshake with AUTH. Returns device banner props on success.
    fn connect(&self, banner: &mut HashMap<String, String>) -> Result<()> {
        let host = b"host::features=shell_v2,cmd,stat_v2,ls_v2";
        self.write_msg(A_CNXN, A_VERSION, MAXDATA as u32, host)?;
        let key = load_or_create_key()?;
        let mut pubkey_sent = false;
        let mut token_rounds = 0u32;
        let mut use_sha256 = true;
        loop {
            self.check_deadline()?;
            let m = self.read_msg()?;
            match m.cmd {
                A_CNXN => {
                    parse_banner(&m.payload, banner);
                    return Ok(());
                }
                A_AUTH if m.arg0 == AUTH_TOKEN => {
                    if m.payload.len() < TOKEN_LEN {
                        return Err(BridgeError::Protocol(
                            crate::error::ProtocolError::UnexpectedResponse(
                                "short AUTH token".to_string(),
                            ),
                        ));
                    }
                    token_rounds += 1;
                    if token_rounds > 6 {
                        return Err(BridgeError::Auth(crate::error::AuthError::Unauthorized(
                            "device keeps rejecting the key — tap 'Allow USB debugging' on the phone, then retry".to_string(),
                        )));
                    }
                    if token_rounds == 3 && !pubkey_sent {
                        let pubkey = key.pubkey_string()?;
                        self.write_msg(A_AUTH, AUTH_RSAPUBLICKEY, 0, pubkey.as_bytes())?;
                        pubkey_sent = true;
                        continue;
                    }
                    // Back off between rounds (capped exponential): hammering
                    // TOKEN replies back-to-back desyncs slow/noisy links and
                    // burns the whole deadline on transport retries.
                    if token_rounds >= 2 {
                        std::thread::sleep(Duration::from_millis(auth_backoff_ms(
                            token_rounds,
                        )));
                    }
                    // Alternate hashes across rounds: new adbd wants
                    // SHA-256, old (pre-10-era) wants SHA-1.
                    if token_rounds == 2 {
                        use_sha256 = false;
                    }
                    let sig = key.sign(&m.payload[..TOKEN_LEN.min(m.payload.len())], use_sha256);
                    self.write_msg(A_AUTH, AUTH_SIGNATURE, 0, &sig)?;
                }
                _ => {
                    return Err(BridgeError::Protocol(
                        crate::error::ProtocolError::HandshakeFailed(format!(
                            "unexpected 0x{:08x} during CNXN",
                            m.cmd
                        )),
                    ));
                }
            }
        }
    }

    /// OPEN a service; returns remote stream id.
    fn open(&mut self, service: &str) -> Result<u32> {
        let local = self.next_id;
        self.next_id += 1;
        let mut dest = service.as_bytes().to_vec();
        dest.push(0);
        self.write_msg(A_OPEN, local, 0, &dest)?;
        // Single reply expected (OKAY with the remote id, or CLSE refusal);
        // anything else desyncs the stream, so it is fatal, not retried.
        self.check_deadline()?;
        let m = self.read_msg()?;
        match m.cmd {
            A_OKAY if m.arg0 == local => Ok(m.arg1),
            A_CLSE if m.arg0 == local => Err(BridgeError::Protocol(
                crate::error::ProtocolError::HandshakeFailed(format!(
                    "open {service} refused (CLSE)"
                )),
            )),
            _ => Err(BridgeError::Protocol(
                crate::error::ProtocolError::UnexpectedResponse(format!(
                    "open {service}: unexpected 0x{:08x}",
                    m.cmd
                )),
            )),
        }
    }

    fn close(&self, local: u32, remote: u32) {
        let _ = self.write_msg(A_CLSE, local, remote, &[]);
    }

    /// Run `shell:CMD` (v1), collecting stdout+stderr text.
    fn shell(&mut self, cmd: &str) -> Result<String> {
        let remote = self.open(&format!("shell:{cmd}"))?;
        let local = self.next_id - 1;
        let mut out = Vec::new();
        loop {
            self.check_deadline()?;
            let m = self.read_msg()?;
            match m.cmd {
                A_WRTE if m.arg0 == remote => {
                    self.write_msg(A_OKAY, local, remote, &[])?;
                    out.extend_from_slice(&m.payload);
                }
                A_CLSE => {
                    self.close(local, remote);
                    break;
                }
                _ => {}
            }
        }
        Ok(String::from_utf8_lossy(&out).to_string())
    }

    /// Low-level sync request/response (caller owns framing).
    fn sync_write(&mut self, local: u32, remote: u32, payload: &[u8]) -> Result<()> {
        self.write_msg(A_WRTE, local, remote, payload)?;
        // Every sync WRTE is acked with OKAY before the reply arrives.
        loop {
            self.check_deadline()?;
            let m = self.read_msg()?;
            match m.cmd {
                A_OKAY => return Ok(()),
                A_CLSE => {
                    return Err(BridgeError::Protocol(
                        crate::error::ProtocolError::SessionEnded,
                    ));
                }
                _ => {}
            }
        }
    }

    fn sync_read(&mut self, local: u32, remote: u32) -> Result<(String, Vec<u8>)> {
        loop {
            self.check_deadline()?;
            let m = self.read_msg()?;
            match m.cmd {
                A_WRTE if m.arg0 == remote => {
                    self.write_msg(A_OKAY, local, remote, &[])?;
                    if m.payload.len() < 4 {
                        continue;
                    }
                    let id = String::from_utf8_lossy(&m.payload[..4]).to_string();
                    let data = m.payload[4..].to_vec();
                    return Ok((id, data));
                }
                A_CLSE => {
                    return Err(BridgeError::Protocol(
                        crate::error::ProtocolError::SessionEnded,
                    ));
                }
                _ => {}
            }
        }
    }

    /// One sync request/response pair on a throwaway stream (STAT and other
    /// single-shot requests; payloads here never exceed MAXDATA).
    fn sync_transact(&mut self, payload: &[u8]) -> Result<(String, Vec<u8>)> {
        assert!(payload.len() <= MAXDATA);
        let remote = self.open("sync:")?;
        let local = self.next_id - 1;
        self.sync_write(local, remote, payload)?;
        let out = self.sync_read(local, remote)?;
        self.close(local, remote);
        Ok(out)
    }

    /// Raw WRTE with no ack wait (for QUIT: adbd closes instead of acking,
    /// so waiting would misreport success as SessionEnded).
    fn sync_write_noreply(&self, local: u32, remote: u32, payload: &[u8]) {
        let raw = encode_msg(A_WRTE, local, remote, payload);
        let _timeout = Duration::from_secs(get_read_chunk_secs(self.ctx.as_ref()));
            let _ = self.dev.write_bulk(self.ep_out, &raw, Duration::from_secs(get_read_chunk_secs(self.ctx.as_ref())));
    }

    /// `adb pull`: STAT then RECV, streaming DATA to `local_path`.
    fn pull(&mut self, remote: &str, local_path: &str) -> Result<String> {
        let mut req = b"STAT".to_vec();
        req.extend_from_slice(&(remote.len() as u32).to_le_bytes());
        req.extend_from_slice(remote.as_bytes());
        let (id, data) = self.sync_transact(&req)?;
        if id == "FAIL" {
            return Err(BridgeError::Io(format!(
                "pull: remote stat failed: {}",
                String::from_utf8_lossy(&data)
            )));
        }
        if id != "STAT" || data.len() < 12 {
            return Err(BridgeError::Protocol(
                crate::error::ProtocolError::UnexpectedResponse(format!("pull: bad STAT reply {id}")),
            ));
        }
        let size = u32::from_le_bytes(data[4..8].try_into().unwrap()) as u64;
        let mut req = b"RECV".to_vec();
        req.extend_from_slice(&(remote.len() as u32).to_le_bytes());
        req.extend_from_slice(remote.as_bytes());
        let remote_id = self.open("sync:")?;
        let local = self.next_id - 1;
        // RECV has no transport-level ack peculiarity beyond the standard
        // OKAY; reuse sync_write. (QUIT below intentionally skips the ack.)
        self.sync_write(local, remote_id, &req)?;
        if let Some(parent) = std::path::Path::new(local_path).parent() {
            if !parent.as_os_str().is_empty() {
                fs::create_dir_all(parent).map_err(|e| BridgeError::Io(e.to_string()))?;
            }
        }
        let mut f = fs::File::create(local_path).map_err(|e| BridgeError::Io(e.to_string()))?;
        use std::io::Write;
        let mut got = 0u64;
        loop {
            let (id, data) = self.sync_read(local, remote_id)?;
            match id.as_str() {
                "DATA" => {
                    f.write_all(&data).map_err(|e| BridgeError::Io(e.to_string()))?;
                    got += data.len() as u64;
                }
                "DONE" => break,
                "FAIL" => {
                    let _ = fs::remove_file(local_path);
                    return Err(BridgeError::Io(format!(
                        "pull failed: {}",
                        String::from_utf8_lossy(&data)
                    )));
                }
                _ => {}
            }
        }
        self.sync_write_noreply(local, remote_id, b"QUIT");
        self.close(local, remote_id);
        Ok(format!("pulled {got}/{size} bytes -> {local_path}"))
    }

    /// `adb push`: SEND then DATA chunks then DONE, expect OKAY.
    fn push(&mut self, local_path: &str, remote: &str) -> Result<String> {
        let bytes =
            fs::read(local_path).map_err(|e| BridgeError::Io(format!("push: read {local_path}: {e}")))?;
        let remote_id = self.open("sync:")?;
        let local = self.next_id - 1;
        let spec = format!("{remote},420");
        let mut req = b"SEND".to_vec();
        req.extend_from_slice(&(spec.len() as u32).to_le_bytes());
        req.extend_from_slice(spec.as_bytes());
        self.sync_write(local, remote_id, &req)?;
        for chunk in bytes.chunks(MAXDATA) {
            let mut pkt = b"DATA".to_vec();
            pkt.extend_from_slice(&(chunk.len() as u32).to_le_bytes());
            pkt.extend_from_slice(chunk);
            // DATA request gets no reply of its own; send back-to-back then
            // read acks lazily would desync — instead write raw and drain.
            let raw = encode_msg(A_WRTE, local, remote_id, &pkt);
            self.dev
                .write_bulk(self.ep_out, &raw, Duration::from_secs(get_read_chunk_secs(self.ctx.as_ref())))
                .map(|_| ())?;
            // Drain the OKAY ack for each DATA chunk.
            loop {
                self.check_deadline()?;
                let m = self.read_msg()?;
                if m.cmd == A_OKAY {
                    break;
                }
                if m.cmd == A_CLSE {
                    return Err(BridgeError::Protocol(
                        crate::error::ProtocolError::SessionEnded,
                    ));
                }
            }
        }
        let mut done = b"DONE".to_vec();
        done.extend_from_slice(&0u32.to_le_bytes());
        self.sync_write(local, remote_id, &done)?;
        let (id, data) = self.sync_read(local, remote_id)?;
        self.sync_write_noreply(local, remote_id, b"QUIT");
        self.close(local, remote_id);
        if id == "FAIL" {
            return Err(BridgeError::Io(format!(
                "push failed: {}",
                String::from_utf8_lossy(&data)
            )));
        }
        Ok(format!("pushed {} bytes -> {remote}", bytes.len()))
    }
}

fn parse_banner(payload: &[u8], out: &mut HashMap<String, String>) {
    let text = String::from_utf8_lossy(payload);
    // "device::ro.product.name=X;ro.product.model=Y;..." — the leading
    // token before "::" is the connection state word.
    for part in text.split(';') {
        if let Some((k, v)) = part.split_once('=') {
            let k = k.trim();
            if k.contains("::") {
                if let Some((_, real)) = k.split_once("::") {
                    out.insert(real.trim().to_string(), v.trim().to_string());
                }
                continue;
            }
            if !k.is_empty() {
                out.insert(k.to_string(), v.trim().to_string());
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Device open + scan.
// ---------------------------------------------------------------------------

struct AdbTarget {
    vid: u16,
    pid: u16,
    bus: u8,
    address: u8,
    serial: String,
}

fn collect_adb() -> Result<Vec<AdbTarget>> {
    let devices = usb::collect_devices(None)?;
    let mut out = Vec::new();
    for d in &devices {
        let has_adb = d.interfaces.iter().any(|i| {
            i.class == ADB_CLASS && i.subclass == ADB_SUBCLASS && i.protocol == ADB_PROTO
        });
        if !has_adb {
            continue;
        }
        out.push(AdbTarget {
            vid: d.vid,
            pid: d.pid,
            bus: d.bus,
            address: d.address,
            serial: d.serial.clone().unwrap_or_else(|| "unknown".to_string()),
        });
    }
    Ok(out)
}

fn open_session(t: &AdbTarget, deadline: Instant) -> Result<Session> {
    let mut dev = UsbDevice::open(t.vid, t.pid, t.bus, t.address)?;
    let iface = dev
        .info()
        .interfaces
        .iter()
        .find(|i| i.class == ADB_CLASS && i.subclass == ADB_SUBCLASS && i.protocol == ADB_PROTO)
        .map(|i| i.number)
        .ok_or_else(|| {
            BridgeError::InvalidArgument(format!(
                "no ADB interface on {:04x}:{:04x}@{}:{}",
                t.vid, t.pid, t.bus, t.address
            ))
        })?;
    let _ = dev.set_auto_detach_kernel_driver(true);
    dev.claim_interface(iface).map_err(|e| match e {
        BridgeError::Usb(UsbError::TransferFailed(_)) => {
            BridgeError::Usb(UsbError::PermissionDenied)
        }
        other => other,
    })?;
    let (ep_in, ep_out) = dev.find_bulk_endpoints(iface).ok_or_else(|| {
        BridgeError::InvalidArgument("no bulk endpoints on ADB iface".to_string())
    })?;
    Ok(Session { dev, ep_in, ep_out, next_id: 1, deadline, ctx: None })
}

fn extras(banner: &HashMap<String, String>) -> String {
    // Mirror `adb devices -l` extra fields the GUI parses (model, ...).
    let mut parts = Vec::new();
    for key in ["product", "model", "device"] {
        if let Some(v) = banner.get(&format!("ro.product.{key}")) {
            if !v.is_empty() {
                parts.push(format!("{key}:{v}"));
            }
        }
    }
    parts.push("transport:usb".to_string());
    parts.join(" ")
}

/// `adb-devices` — JSON list of `SERIAL\tstate extras` strings (same line
/// contract as `adb devices -l`, so Python parsing is unchanged).
pub fn devices_json() -> Result<String> {
    let targets = collect_adb()?;
    let mut lines = Vec::new();
    for t in &targets {
        let deadline = Instant::now() + Duration::from_secs(6);
        let probe = (|| -> Result<HashMap<String, String>> {
            let sess = open_session(t, deadline)?;
            let mut props = HashMap::new();
            match sess.connect(&mut props) {
                Ok(()) => Ok(props),
                Err(BridgeError::Auth(_)) => Err(BridgeError::Auth(
                    crate::error::AuthError::Unauthorized("unauthorized".to_string()),
                )),
                Err(e) => Err(e),
            }
        })();
        match probe {
            Ok(props) => {
                let ex = extras(&props);
                lines.push(format!("{}\tdevice {}", t.serial, ex));
            }
            Err(BridgeError::Auth(_)) => {
                lines.push(format!("{}\tunauthorized transport:usb", t.serial));
            }
            Err(BridgeError::Usb(UsbError::PermissionDenied)) => {
                lines.push(format!("{}\tno permissions transport:usb", t.serial));
            }
            Err(_) => {} // transient GONE device — skip like adb does
        }
    }
    serde_json::to_string(&lines).map_err(|e| BridgeError::Io(e.to_string()))
}

fn pick_target(serial: &str) -> Result<AdbTarget> {
    let mut targets = collect_adb()?;
    if targets.is_empty() {
        return Err(BridgeError::Usb(UsbError::DeviceNotFound));
    }
    if serial.is_empty() || serial == "-" {
        // First device, legacy single-device behaviour.
        return Ok(targets.remove(0));
    }
    if let Some(i) = targets.iter().position(|t| t.serial == serial) {
        return Ok(targets.remove(i));
    }
    Err(BridgeError::Usb(UsbError::DeviceNotFound))
}

/// `adb-shell <serial|-> <timeout_ms> <cmd...>` — run a shell command.
pub fn shell_cli(serial: &str, timeout_ms: u64, cmd: &[String]) -> Result<String> {
    if cmd.is_empty() {
        return Err(BridgeError::InvalidArgument(
            "usage: adb-shell <serial|-> <timeout_ms> <cmd...>".to_string(),
        ));
    }
    let t = pick_target(serial)?;
    let deadline = Instant::now() + Duration::from_millis(timeout_ms);
    let sess = &mut open_session(&t, deadline)?;
    let mut props = HashMap::new();
    sess.connect(&mut props).map_err(|e| match e {
        BridgeError::Auth(_) => BridgeError::Auth(crate::error::AuthError::Unauthorized(format!(
            "{}: not authorized — tap 'Allow USB debugging' on the phone (Always allow), then retry",
            t.serial
        ))),
        other => other,
    })?;
    sess.shell(&cmd.join(" "))
}

/// `adb-pull <serial|-> <timeout_ms> <remote> <local>`.
pub fn pull_cli(serial: &str, timeout_ms: u64, remote: &str, local: &str) -> Result<String> {
    let t = pick_target(serial)?;
    let deadline = Instant::now() + Duration::from_millis(timeout_ms);
    let sess = &mut open_session(&t, deadline)?;
    let mut props = HashMap::new();
    sess.connect(&mut props)?;
    sess.pull(remote, local)
}

/// `adb-push <serial|-> <timeout_ms> <local> <remote>`.
pub fn push_cli(serial: &str, timeout_ms: u64, local: &str, remote: &str) -> Result<String> {
    let t = pick_target(serial)?;
    let deadline = Instant::now() + Duration::from_millis(timeout_ms);
    let sess = &mut open_session(&t, deadline)?;
    let mut props = HashMap::new();
    sess.connect(&mut props)?;
    sess.push(local, remote)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn msg_roundtrip_and_checksum() {
        let payload = b"shell:getprop ro.serialno";
        let pkt = encode_msg(A_OPEN, 1, 0, payload);
        assert_eq!(pkt.len(), 24 + payload.len());
        let mut hdr = [0u8; 24];
        hdr.copy_from_slice(&pkt[..24]);
        let (cmd, a0, a1, len) = decode_header(&hdr).unwrap();
        assert_eq!((cmd, a0, a1, len as usize), (A_OPEN, 1, 0, payload.len()));
        assert_eq!(&pkt[24..], payload);
        // Corrupt magic -> rejected.
        let mut bad = hdr;
        bad[20] ^= 0xff;
        assert!(decode_header(&bad).is_err());
        // Checksum is a plain byte sum.
        assert_eq!(checksum(b"ABC"), 65 + 66 + 67);
        assert_eq!(checksum(&[]), 0);
    }

    #[test]
    fn banner_parses_ro_props() {
        let mut m = HashMap::new();
        parse_banner(
            b"device::ro.product.name=ali_n;ro.product.model=Moto G (6);ro.product.device=ali;features=shell_v2,cmd",
            &mut m,
        );
        assert_eq!(m.get("ro.product.model").unwrap(), "Moto G (6)");
        assert_eq!(m.get("ro.product.device").unwrap(), "ali");
        assert_eq!(m.get("features").unwrap(), "shell_v2,cmd");
        let ex = extras(&m);
        assert!(ex.contains("model:Moto G (6)"));
        assert!(ex.contains("transport:usb"));
    }

    #[test]
    fn der_pkcs8_roundtrip() {
        let n = BigUint::from(0xdeadbeefu64) << 2000u32 | BigUint::from(0x12345u32);
        let e = BigUint::from(65537u32);
        let d = BigUint::from(0xabcdefu64) << 1990u32 | BigUint::from(7u32);
        let p = BigUint::from(0xffffff61u64) << 900u32 | BigUint::from(3u32);
        let q = BigUint::from(0xffffff6fu64) << 900u32 | BigUint::from(5u32);
        let one = BigUint::from(1u32);
        let dp = &d % (&p - &one);
        let dq = &d % (&q - &one);
        let two = BigUint::from(2u32);
        let qinv = q.modpow(&(&p - &two), &p);
    let der = encode_pkcs8(&RsaParts {
        n: &n,
        e: &e,
        d: &d,
        p: &p,
        q: &q,
        dp: &dp,
        dq: &dq,
        qinv: &qinv,
    });
        let (n2, e2, d2, p2, q2) = parse_pkcs8(&der).unwrap();
        assert_eq!((n, e, d, p, q), (n2, e2, d2, p2, q2));
    }

    #[test]
    fn pkcs1_sign_verify_roundtrip() {
        // Fixed 256-bit primes (secp256k1 + Curve25519 field primes, both
        // famously prime): n is ~511 bits so k=64 fits the DigestInfo.
        // A toy 40-bit key cannot hold EMSA-PKCS#1-v1_5 (51-byte SHA-256 T).
        let p = BigUint::parse_bytes(
            b"FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F", 16)
            .unwrap();
        let q = BigUint::parse_bytes(
            b"7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFED", 16)
            .unwrap();
        let n = &p * &q;
        let e = BigUint::from(65537u32);
        let phi = (&p - BigUint::from(1u32)) * (&q - BigUint::from(1u32));
        // d = e^-1 mod phi via Fermat-style extended Euclid on BigInt.
        use num_bigint::BigInt;
        use num_traits::{One, Zero};
        fn egcd(a: BigInt, b: BigInt) -> (BigInt, BigInt, BigInt) {
            if b.is_zero() {
                (a.clone(), BigInt::one(), BigInt::zero())
            } else {
                let (g, x1, y1) = egcd(b.clone(), a.clone() % b.clone());
                (g, y1.clone(), x1 - (a / b) * y1)
            }
        }
        let phi_i = BigInt::from(phi.clone());
        let e_i = BigInt::from(e.clone());
        let (g, x, _) = egcd(e_i, phi_i.clone());
        assert_eq!(g, BigInt::one());
        let mut d_i = x % &phi_i;
        if d_i < BigInt::zero() {
            d_i += &phi_i;
        }
        let d = BigUint::try_from(d_i).unwrap();
        let key = AdbKey { n: n.clone(), e: e.clone(), d };
        let token = b"0123456789abcdefghij";
        for sha256 in [true, false] {
            let sig = key.sign(token, sha256);
            // Manual verify: s^e mod n must equal the EMSA encoding.
            let m = BigUint::from_bytes_be(&sig).modpow(&e, &n);
            let k = ((n.bits() + 7) / 8) as usize;
            let mut em = m.to_bytes_be();
            if em.len() < k {
                let mut p = vec![0u8; k - em.len()];
                p.extend_from_slice(&em);
                em = p;
            }
            assert_eq!(em[0], 0x00);
            assert_eq!(em[1], 0x01);
            // Full EMSA structure: 00 01 FF..FF 00 || prefix || hash.
            let (prefix, digest): (&[u8], Vec<u8>) = if sha256 {
                use sha2::{Digest, Sha256};
                (SHA256_PREFIX, Sha256::digest(token).to_vec())
            } else {
                use sha1::{Digest, Sha1};
                (SHA1_PREFIX, Sha1::digest(token).to_vec())
            };
            let t_len = prefix.len() + digest.len();
            assert_eq!(&em[k - t_len..k - digest.len()], prefix);
            assert_eq!(&em[k - digest.len()..], digest.as_slice());
        }
    }

    #[test]
    fn system_adbkey_interop_when_present() {
        // Bit-for-bit interop with system adb: parse the real ~/.android
        // key, re-derive the .pub blob, and require byte equality. Skipped
        // where no system key exists (CI); keygen path covered above.
        let home = match std::env::var("HOME") {
            Ok(h) => h,
            Err(_) => return,
        };
        let priv_path = format!("{home}/.android/adbkey");
        let pub_path = format!("{home}/.android/adbkey.pub");
        if !std::path::Path::new(&priv_path).exists()
            || !std::path::Path::new(&pub_path).exists()
        {
            return;
        }
        let raw = std::fs::read(&priv_path).unwrap();
        let der = decode_key_file(&raw).unwrap();
        let (n, e, d, _, _) = parse_pkcs8(&der).unwrap();
        assert!(n.bits() >= 2000, "unexpected key size {}", n.bits());
        let key = AdbKey { n, e, d };
        let sig = key.sign(b"interop-probe-token!!", true);
        assert_eq!(sig.len(), key.k_bytes());
        let mine = key.pubkey_string().unwrap();
        let (mine_b64, _) = mine.split_once(' ').unwrap();
        let pubfile = std::fs::read_to_string(&pub_path).unwrap();
        let (file_b64, _) = pubfile.trim().split_once(' ').unwrap();
        let mine_raw =
            base64::Engine::decode(&base64::engine::general_purpose::STANDARD, mine_b64).unwrap();
        let file_raw =
            base64::Engine::decode(&base64::engine::general_purpose::STANDARD, file_b64).unwrap();
        assert_eq!(mine_raw, file_raw, "pubkey blob differs from system adb's");
    }

    #[test]
    fn auth_backoff_rises_then_caps() {
        assert_eq!(auth_backoff_ms(1), 200);
        assert_eq!(auth_backoff_ms(2), 400);
        assert_eq!(auth_backoff_ms(3), 800);
        assert_eq!(auth_backoff_ms(4), 1600);
        assert_eq!(auth_backoff_ms(5), 2000);
        assert_eq!(auth_backoff_ms(6), 2000);
        assert_eq!(auth_backoff_ms(100), 2000);
    }

    #[test]
    fn pubkey_blob_is_524_bytes() {
        // rsa::BigUint IS num_bigint::BigUint (re-exported): clone directly.
        use rsa::traits::{PrivateKeyParts, PublicKeyParts};
        let mut rng = rand::thread_rng();
        let privk = rsa::RsaPrivateKey::new(&mut rng, 2048).unwrap();
        let key = AdbKey {
            n: rsa_to_nbi(privk.n()),
            e: rsa_to_nbi(privk.e()),
            d: rsa_to_nbi(privk.d()),
        };
        let s = key.pubkey_string().unwrap();
        let (b64, user) = s.split_once(' ').unwrap();
        assert_eq!(user, "user@host");
        let raw = base64::Engine::decode(&base64::engine::general_purpose::STANDARD, b64).unwrap();
        assert_eq!(raw.len(), 524);
        assert_eq!(u32::from_le_bytes(raw[0..4].try_into().unwrap()), 64);
        // n0inv invariant: n0 * n0inv == 2^32 - 1.
        let n0 = u32::from_le_bytes(raw[8..12].try_into().unwrap());
        let n0inv = u32::from_le_bytes(raw[4..8].try_into().unwrap());
        assert_eq!(n0.wrapping_mul(n0inv), 0xFFFF_FFFF);
        // exponent round-trips.
        assert_eq!(u32::from_le_bytes(raw[520..524].try_into().unwrap()), 65537);
    }
}
