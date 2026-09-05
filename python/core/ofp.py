"""Oppo/Realme OFP firmware containers — detect + best-effort extract.

Honest scope, stated up front: shipping OFP images are AES-encrypted with
device-family keys that are provisioned via Oppo's auth infrastructure.
There is no offline key database in this project and we will not ship a
fake decryptor that mangles firmware. What this module DOES do:

* detect whether a file is an OFP container (magic + size sanity),
* extract it when it is actually a plain zip/tar wrapper (many mirrors
  mislabel plain archives as .ofp),
* otherwise refuse loudly with the exact requirement (model-specific key /
  auth) instead of producing a corrupt image that would brick the phone.
"""

import os
import struct
import tarfile
import tempfile
import zipfile

OFP_MAGICS = (b"OFP", b"OPPO")


def detect_ofp(path):
    """Return (is_ofp, detail). `is_ofp` True when the header looks like an
    Oppo OFP container (magic at offset 0). Never raises."""
    try:
        if not os.path.isfile(path) or os.path.getsize(path) < 8:
            return False, "not a file / too small"
        with open(path, "rb") as fh:
            head = fh.read(16)
        for magic in OFP_MAGICS:
            if head.startswith(magic):
                return True, f"OFP magic {magic!r} at offset 0"
        # Zip-wrapped OFP (mislabeled mirrors): real zip header.
        if head[:2] == b"PK":
            return False, "plain zip archive (mislabeled .ofp?) - extractable"
        return False, "no OFP magic - not an OFP container"
    except OSError as e:
        return False, f"unreadable: {e}"


def extract_plain_ofp(path, out_dir):
    """Extract `path` when it is a plain zip/tar wrapper. Returns file list.

    Raises RuntimeError for genuinely encrypted OFP containers (with the
    requirement spelled out) instead of writing corrupt output.
    """
    is_ofp, detail = detect_ofp(path)
    if is_ofp:
        raise RuntimeError(
            f"encrypted OFP container ({detail}). Decryption needs the "
            "model-specific key from Oppo auth infrastructure, which this "
            "tool does not ship and will not guess. Options: flash the OFP "
            "with the official MSM Download Tool, or use an unencrypted "
            "scatter/firmware for this model with 'Flash Firmware -> MTK'."
        )
    os.makedirs(out_dir, exist_ok=True)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            zf.extractall(out_dir)
            return [os.path.join(out_dir, n) for n in zf.namelist() if n and not n.endswith("/")]
    try:
        with tarfile.open(path, "r:*") as tf:
            tf.extractall(out_dir)
            return [os.path.join(out_dir, m.name) for m in tf.getmembers() if m.isfile()]
    except Exception as e:
        raise RuntimeError(f"not an extractable archive ({detail}): {e}")


def flow_ofp_extract():
    """Oppo OFP prepare: detect + extract plain wrappers, refuse encrypted."""
    from .flow import Flow, Step

    def _run(ctx, log):
        from . import bridge as _bridge

        log("=" * 60)
        log("OPPO OFP PREPARE (detect + plain-extract, honest scope)")
        log("=" * 60)
        src = (os.environ.get("OFP_FILE", "").strip() or ctx.get("ofp_file", ""))
        if not src or not os.path.isfile(src):
            raise RuntimeError("Set OFP_FILE=/path/to/firmware.ofp (or pass ofp_file=)")
        log(f"  File: {src} ({os.path.getsize(src) >> 20} MB)")
        is_ofp, detail = detect_ofp(src)
        log(f"  Detect: {detail}")
        out_dir = (os.environ.get("OFP_OUT_DIR", "").strip()
                   or os.path.join(tempfile.gettempdir(), "ofp_out"))
        try:
            files = extract_plain_ofp(src, out_dir)
        except RuntimeError:
            raise
        log(f"  Extracted {len(files)} file(s) -> {out_dir}")
        for f in files[:20]:
            log(f"    {os.path.basename(f)}")
        if len(files) > 20:
            log(f"    ... and {len(files) - 20} more")
        ctx["ofp_out_dir"] = out_dir
        log("  Next: point MTK_FW_DIR at the extracted dir for MTK flashing.")
        return True

    return Flow("Oppo OFP prepare (extract / guidance)", [Step("ofp_extract", _run)])
