"""Partition integrity verification — SHA-256/MD5 before/after flash.

Before write: archive MD5 trailer (frp:_tar_md5_valid) + per-image SHA-256.
After write: best-effort readback via bridge (when protocol supports it) and
compare hashes. Failures are logged as warnings — they never silently pass.
"""

import hashlib
import os
from typing import Dict, List, Tuple

from . import bridge


def sha256_file(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk_data in iter(lambda: f.read(chunk), b""):
            h.update(chunk_data)
    return h.hexdigest()


def md5_file(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk_data in iter(lambda: f.read(chunk), b""):
            h.update(chunk_data)
    return h.hexdigest()


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def before_flight_hashes(images: List[Tuple[str, str]]) -> Dict[str, str]:
    """Per-image SHA-256 for the flashed set. images = [(part, file_path)]."""
    out: Dict[str, str] = {}
    for part, fpath in images:
        try:
            out[part] = sha256_file(fpath)
        except Exception as e:
            out[part] = f"error: {e}"
    return out


def verify_tar_md5(tar_path: str) -> Tuple[bool, str]:
    """Check Samsung .tar.md5 trailer (first 32 hex + two spaces + name)."""
    # Reuse frp logic without importing full frp to avoid cycle
    try:
        from .core import _tar_md5_valid  # type: ignore

        return _tar_md5_valid(tar_path)
    except Exception as e:
        return (False, str(e))


def after_flash_verify(
    partition: str,
    expected_sha256: str,
    readback_bytes: bytes = b"",
    readback_file: str = "",
) -> Tuple[bool, str]:
    """Compare expected SHA vs readback (bytes or file)."""
    got = ""
    if readback_bytes:
        got = hash_bytes(readback_bytes)
    elif readback_file and os.path.isfile(readback_file):
        try:
            got = sha256_file(readback_file)
        except Exception as e:
            return (False, f"readback hash failed: {e}")
    else:
        return (False, "no readback data — verification skipped (protocol may not support readback)")
    if got.lower() == expected_sha256.lower():
        return (True, f"SHA-256 ok {got[:16]}...")
    return (False, f"SHA-256 mismatch expected {expected_sha256[:16]}... got {got[:16]}...")


def log_before_hashes(log, images: List[Tuple[str, str]]) -> Dict[str, str]:
    hashes = before_flight_hashes(images)
    for part, h in hashes.items():
        try:
            log(f"  [integrity] {part}: sha256 {h[:16]}... ({h})")
        except Exception:
            pass
    return hashes
