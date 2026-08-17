//! MediaTek SLA (Security Lock Authentication) challenge-response, ported from
//! mtkclient `mtkclient/Library/Auth/sla.py` (B. Kerler, GPLv3).
//!
//! The BROM issues a random challenge; the host signs it with a known RSA
//! private key (one of the leaked BROM SLA keys) and returns the signature.
//! The signature scheme is a "customized" PKCS#1 v1.5: `00 01 FF..FF 00 || msg`
//! raised to the private exponent, with each 16-bit word byte-swapped.

use num_bigint::BigUint;
use num_traits::One;

use crate::mtk_sla_keys::{BROM_SLA_KEYS, SlaKey};

/// PKCS#1 v1.5-style block with `00 01` header, 0xFF padding and the message,
/// then `em^e mod n`, serialized to exactly `k` bytes (mtkclient
/// `customized_sign`).
fn customized_sign(n: &BigUint, e: &BigUint, msg: &[u8]) -> Vec<u8> {
    let k = n.bits().div_ceil(8) as usize;
    let mut em = Vec::with_capacity(k);
    em.push(0x00);
    em.push(0x01);
    em.extend(std::iter::repeat(0xFF).take(k.saturating_sub(msg.len() + 3)));
    em.push(0x00);
    em.extend_from_slice(msg);
    em.truncate(k);

    let em_int = BigUint::from_bytes_be(&em);
    let m_int = em_int.modpow(e, n);
    let mut out = m_int.to_bytes_be();
    // Left-pad to exactly k bytes (mtkclient long_to_bytes(m_int, k)).
    while out.len() < k {
        out.insert(0, 0);
    }
    out
}

/// Swap each 16-bit word of `data` (mtkclient `generate_brom_sla_challenge`).
fn swap_words(data: &[u8]) -> Vec<u8> {
    let mut out = data.to_vec();
    for c in out.chunks_exact_mut(2) {
        c.swap(0, 1);
    }
    out
}

/// Sign the BROM challenge with the given key (d, n, e).
pub fn generate_brom_sla_challenge(challenge: &[u8], key: &SlaKey) -> Vec<u8> {
    let d = BigUint::parse_bytes(key.d.as_bytes(), 16).expect("sla key d");
    let n = BigUint::parse_bytes(key.n.as_bytes(), 16).expect("sla key n");
    let e = BigUint::parse_bytes(key.e.as_bytes(), 16).expect("sla key e");

    let swapped = swap_words(challenge);
    // mtkclient: customized_sign(d, e, data) called with (d=n, e=d) swapped
    // from generate_brom_sla_challenge. So modulus = n, exponent = d.
    let sig = customized_sign(&n, &d, &swapped);
    swap_words(&sig)
}

/// `brom_sla_keys[0]` = the most commonly used generic key (IMG_AUTH_KEY.ini).
pub fn primary_sla_key() -> &'static SlaKey {
    &BROM_SLA_KEYS[0]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn challenge_matches_python_reference() {
        // Cross-checked against mtkclient's sla.py generate_brom_sla_challenge
        // for challenge [1..=8] with brom_sla_keys[0].
        let sig = generate_brom_sla_challenge(&[1, 2, 3, 4, 5, 6, 7, 8], primary_sla_key());
        let hex: String = sig.iter().map(|b| format!("{:02x}", b)).collect();
        assert_eq!(
            hex,
            "de0f430b4353d444952504698cff73b0d3591dce99eb7f80150736bda34bba95a3e29baed2e103994cfee853314d4e43d102dbc55f7bc4882724608417f5e4c6babdd5f59697d984ec170201675a66618008c33d5be8f702286dadab53262218067f25f086d407f77550e327f4a71c3a91b6fc8f4d7bbc405f73812b6e844dfe"
        );
    }

    #[test]
    fn keys_parse() {
        assert!(BROM_SLA_KEYS.len() >= 20);
        for k in BROM_SLA_KEYS {
            let d = BigUint::parse_bytes(k.d.as_bytes(), 16).expect("d");
            let n = BigUint::parse_bytes(k.n.as_bytes(), 16).expect("n");
            assert!(d > BigUint::one());
            assert!(n > BigUint::one());
        }
    }

    #[test]
    fn swap_words_swaps_pairs() {
        assert_eq!(swap_words(&[0xAB, 0xCD, 0x01, 0x02]), vec![0xCD, 0xAB, 0x02, 0x01]);
        // odd trailing byte is left as-is (matches mtkclient range(0,len,2))
        assert_eq!(swap_words(&[0xAB, 0xCD, 0xEF]), vec![0xCD, 0xAB, 0xEF]);
    }

    #[test]
    fn challenge_is_swapped_pkcs1_sig() {
        // Deterministic: signing a fixed challenge with the generic key must
        // be reproducible across runs (validates modpow + padding).
        let a = generate_brom_sla_challenge(&[1, 2, 3, 4, 5, 6, 7, 8], primary_sla_key());
        let b = generate_brom_sla_challenge(&[1, 2, 3, 4, 5, 6, 7, 8], primary_sla_key());
        assert_eq!(a, b);
        // 1024-bit key -> 128-byte signature.
        assert_eq!(a.len(), 128);
        // Different challenge -> different signature.
        let c = generate_brom_sla_challenge(&[8, 7, 6, 5, 4, 3, 2, 1], primary_sla_key());
        assert_ne!(a, c);
    }
}