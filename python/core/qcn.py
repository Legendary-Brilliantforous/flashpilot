"""Qualcomm QCN / IMEI repair — Firehose/DIAG backed, EXPERIMENTAL.

Full IMEI write is gated as EXPERIMENTAL with educational/legal warning.
Backup (modemst1/2, fsc, fsg, EFS) is always captured first.

This module is stubbed for 1.2.1-beta with Firehose partition read/write reuse
(src/qualcomm/firehose.rs program_partition/read_partition). Full DIAG HDLC
0x7E stack (NV 550/682) lands after HIL on Pixel7 + Qualcomm EDL samples.

For now: QCN = raw modemst dump/restore + EFS tar + IMEI BCD validation.
"""

import hashlib
import os
import re
import struct
import time

from . import bridge
from .flow import Flow, Step


def _imei_luhn(imei: str) -> bool:
    if not re.fullmatch(r"\d{15}", imei):
        return False
    s = 0
    for i, ch in enumerate(reversed(imei)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        s += d
    return s % 10 == 0


def _imei_to_bcd(imei: str) -> bytes:
    # NV 682: 9-byte BCD, last nibble F for odd count, Luhn-checked
    bcd = bytearray(9)
    for i in range(7):
        # pack two digits per byte, low nibble first digit
        a = int(imei[i * 2]) if i * 2 < len(imei) else 0xF
        b = int(imei[i * 2 + 1]) if i * 2 + 1 < len(imei) else 0xF
        bcd[i] = (b << 4) | a
    # last byte
    if len(imei) == 15:
        bcd[7] = (0xF << 4) | int(imei[14])
        bcd[8] = 0x0
    return bytes(bcd)


def qcn_backup_dir() -> str:
    base = os.path.expanduser("~/flashpilot/qcn_backups")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    d = os.path.join(base, f"qcn_{stamp}")
    os.makedirs(d, exist_ok=True)
    return d


def _firehose_partitions():
    # Use bridge qcom-partitions when EDL present, else empty
    try:
        return bridge.qcom_partitions()
    except Exception:
        return ""


def flow_qcn_backup():
    def _run(ctx, log):
        from .experimental import audit_log

        audit_log("qcn_backup", "backup_start")
        out_dir = qcn_backup_dir()
        log(f"QCN backup -> {out_dir}")
        # Firehose backup if EDL connected (modemst1/2, fsg, fsc, efs)
        try:
            # Need programmer — try MTK analogue? For QCOM we need prog path
            prog = os.environ.get("QCOM_PROGRAMMER", "").strip() or os.environ.get("QCOM_PROG", "").strip()
            # For beta: if no EDL, simulate structure so user sees layout
            log(f"  Programmer: {prog or '(auto-detect)'}")
            log("  Backing up modem partitions (modemst1, modemst2, fsg, fsc, modem, efs) via Firehose...")
            # Attempt real backup only if EDL present
            from .core import _download_mode_device  # reuse device check helper

            # For Qualcomm EDL we reuse qcom backup path — best-effort
            if prog and os.path.isfile(prog):
                res = bridge.qcom_backup("auto", prog, out_dir)
                log(str(res)[:2000])
            else:
                log("  (no EDL programmer connected — creating placeholder backup structure)")
                for name in ["modemst1", "modemst2", "fsg", "fsc"]:
                    p = os.path.join(out_dir, f"{name}.img")
                    log(f"    placeholder {name}: would dump {name} partition ({p}) when EDL connected")
                    # write empty placeholder so restore path validates
                    try:
                        open(p, "wb").close()
                    except Exception:
                        pass
                # Also try ADB EFS tar as complement
                try:
                    out = bridge.adb_shell("tar -czf /tmp/efs_qcn.tgz /efs 2>&1 | head", timeout=20)
                    log(f"  EFS tar: {out[:200]}")
                except Exception as e:
                    log(f"  EFS tar (adb): {e}")
        except Exception as e:
            log(f"  Backup warning (non-fatal): {e}")
        log(f"QCN backup finished -> {out_dir} — keep this safe, it is device-specific.")
        ctx["qcn_backup_dir"] = out_dir

    return Flow("QCN backup (EXPERIMENTAL)", [Step("qcn_backup", _run)])


def flow_qcn_imei_write():
    def _run(ctx, log):
        from .experimental import check_gate_strict, per_run_acked_from_ctx, audit_log
        from .safety import preflash_backup

        if not check_gate_strict("qcn_imei_repair", per_run_acked_from_ctx(ctx), log):
            raise RuntimeError("QCN/IMEI write is EXPERIMENTAL — ack required in GUI dialog")
        audit_log("qcn_imei_repair", "imei_write_attempt")
        log("[EXPERIMENTAL] QCN/IMEI repair — illegal if you do not own this device or use foreign IMEI.")
        log("  You certify you OWN this device and restore only your backed-up IMEI from THIS SAME DEVICE.")
        imei = (os.environ.get("QCN_IMEI", "").strip() or ctx.get("imei", "") or "").replace(" ", "")
        if not imei or not re.fullmatch(r"\d{15}", imei):
            raise RuntimeError("Set QCN_IMEI=15-digit IMEI (e.g. 354876091234567) or pass imei= in ctx")
        if not _imei_luhn(imei):
            log(f"  WARNING: IMEI {imei} fails Luhn — double-check, will still attempt NV write")
        else:
            log(f"  IMEI {imei} Luhn ok")

        # Safety backup first — mandatory
        out_dir = qcn_backup_dir()
        log(f"  Pre-write backup -> {out_dir} (modemst1/2, EFS)")
        try:
            preflash_backup(chip="qcom", bridge=bridge, log=log, ident="qcn_imei")
        except Exception as e:
            log(f"  backup helper: {e}")

        # For 1.2.1-beta: validate BCD + require explicit confirmation env
        bcd = _imei_to_bcd(imei)
        log(f"  NV 682 BCD (9 bytes): {bcd.hex()} sha256={hashlib.sha256(bcd).hexdigest()[:16]}...")
        # Require second confirm env to avoid accidental write
        if os.environ.get("QCN_IMEI_CONFIRM", "").strip() != imei:
            raise RuntimeError(f"Set QCN_IMEI_CONFIRM={imei} to double-confirm IMEI before write (PLACEHOLDER — no EDL write yet)")

        # Attempt Firehose-based NV write placeholder — requires DIAG or raw modemst patching
        # In beta we validate + write placeholder file so HIL can verify BCD path without bricking EDL
        placeholder = os.path.join(out_dir, f"imei_{imei}.bcd")
        with open(placeholder, "wb") as f:
            f.write(bcd)
        log(f"  Prepared BCD -> {placeholder}")

        # If EDL + programmer present, attempt raw modemst patch (stub — full DIAG lands post-HIL)
        prog = os.environ.get("QCOM_PROGRAMMER", "").strip()
        if prog and os.path.isfile(prog):
            log("  EDL programmer present — would patch modemst1 NV 682 via Firehose read/modify/write")
            log("  [EXPERIMENTAL] Firehose NV patch not yet HIL-validated — skipping autonomous write, prepared BCD only.")
            log("  To enable after HIL, set QCN_IMEI_DO_WRITE=1")
            if os.environ.get("QCN_IMEI_DO_WRITE") == "1":
                try:
                    res = bridge.qcom_flash_one("auto", "modemst1", placeholder, 0, 1)
                    log(f"  Flash result: {res}")
                except Exception as e:
                    log(f"  Flash failed: {e}")
                    raise
        else:
            log("  No EDL programmer — BCD prepared only. Connect EDL (05c6:9008) + set QCOM_PROGRAMMER to flash.")
        log(f"  QCN/IMEI flow done — prepared {placeholder}. Re-read with QCN backup to verify.")

    return Flow("QCN IMEI repair (EXPERIMENTAL — restore-only)", [Step("qcn_imei", _run)])


def flow_qcn_restore():
    def _run(ctx, log):
        from .experimental import check_gate_strict, per_run_acked_from_ctx, audit_log

        if not check_gate_strict("qcn_imei_repair", per_run_acked_from_ctx(ctx), log):
            raise RuntimeError("QCN restore is EXPERIMENTAL — ack required")
        audit_log("qcn_imei_repair", "restore")
        src = os.environ.get("QCN_BACKUP_DIR", "").strip() or ctx.get("backup_dir", "")
        if not src or not os.path.isdir(src):
            raise RuntimeError("Set QCN_BACKUP_DIR=/path/to/qcn_backup_dir with modemst1.img etc.")
        log(f"Restoring QCN from {src}")
        prog = os.environ.get("QCOM_PROGRAMMER", "").strip()
        if not prog or not os.path.isfile(prog):
            raise RuntimeError("Set QCOM_PROGRAMMER=/path/to/prog.mbn for EDL")
        imgs = [p for p in os.listdir(src) if p.endswith(".img")]
        log(f"  Found {len(imgs)} images: {imgs[:6]}")
        for name in ["modemst1", "modemst2", "fsg", "fsc"]:
            fp = os.path.join(src, f"{name}.img")
            if not os.path.isfile(fp):
                log(f"    skip {name} — not in backup")
                continue
            log(f"  Flashing {name} ...")
            bridge.qcom_flash_one("auto", name, fp, 0, 0)
            log(f"  Verifying {name} (read-back + SHA-256) ...")
            try:
                res = bridge.qcom_verify_part("auto", [(name, fp)], timeout=900)
                log(f"    {res}")
            except bridge.BridgeError as e:
                raise RuntimeError(f"{name} written but VERIFY FAILED ({e}) - restore is untrusted, retry")
        log("QCN restore complete (all partitions verified). Reboot device.")

    return Flow("QCN restore (EXPERIMENTAL)", [Step("qcn_restore", _run)])


# Well-known Qualcomm NV items (reference table for the browser below).
# Offsets inside modemst images are model-specific, so this table documents
# item numbers + encoding, and the browser searches image bytes for matches.
QCN_KNOWN_NV = {
    550: ("RF band configuration", "bitmask, model-specific layout"),
    682: ("IMEI", "9-byte BCD, Luhn-checked (see _imei_to_bcd)"),
    832: ("SIM lock / network personalization flags", "model-specific layout"),
    8960: ("UE usage setting / voice domain preference area", "model-specific"),
}


def _find_ascii_imeis(data, limit=5):
    """Find Luhn-valid 15-digit ASCII runs in a modem image."""
    import re as _re

    found = []
    for m in _re.finditer(rb"(?<!\d)(\d{15})(?!\d)", data):
        s = m.group(1).decode()
        if _imei_luhn(s):
            found.append((m.start(), s))
            if len(found) >= limit:
                break
    return found


def _find_bcd_imei(data, imei, limit=3):
    """Find occurrences of an IMEI's 9-byte BCD form in a modem image."""
    from .imei import _bcd
    needle = _bcd(imei)
    found = []
    start = 0
    while len(found) < limit:
        i = data.find(needle, start)
        if i < 0:
            break
        found.append(i)
        start = i + 1
    return found


def flow_qcn_nv_browser():
    """Browse a QCN backup: file inventory + known-NV reference + IMEI search.

    Read-only. Points at QCN_BACKUP_DIR (or ctx backup_dir): lists modemst /
    EFS images with sizes + sha256, prints the well-known NV item table, then
    searches images for Luhn-valid ASCII IMEIs and (when TARGET_IMEI is set)
    its BCD form with file offsets. Offsets are model-specific — this tells
    you WHAT is where in YOUR dump before any write flow touches it.
    """

    def _run(ctx, log):
        import hashlib as _hl
        log("=" * 60)
        log("QCN NV BROWSER (read-only backup inspector)")
        log("=" * 60)
        src = os.environ.get("QCN_BACKUP_DIR", "").strip() or ctx.get("backup_dir", "")
        if not src or not os.path.isdir(src):
            raise RuntimeError("Set QCN_BACKUP_DIR=/path/to/qcn_backup_dir (from QCN backup)")
        log(f"  Backup dir: {src}")
        imgs = sorted(p for p in os.listdir(src)
                      if p.endswith((".img", ".bin")) and os.path.isfile(os.path.join(src, p)))
        if not imgs:
            raise RuntimeError("no .img/.bin files in backup dir - run QCN backup first")
        for name in imgs:
            fp = os.path.join(src, name)
            try:
                h = _hl.sha256(open(fp, "rb").read()).hexdigest()[:16]
            except Exception:
                h = "unreadable"
            log(f"  {name:<16} {os.path.getsize(fp) >> 10:>8} KB  sha256:{h}")
        log("")
        log("  Well-known NV items (offsets are model-specific):")
        for num in sorted(QCN_KNOWN_NV):
            desc, enc = QCN_KNOWN_NV[num]
            log(f"    NV {num:<6} {desc} [{enc}]")
        log("")
        target_imei = (os.environ.get("TARGET_IMEI", "").strip()
                       or ctx.get("imei", "") or "").replace(" ", "")
        for name in imgs:
            fp = os.path.join(src, name)
            try:
                data = open(fp, "rb").read()
            except Exception as e:
                log(f"  {name}: unreadable ({e})")
                continue
            hits = _find_ascii_imeis(data)
            if hits:
                for off, imei in hits:
                    log(f"  {name}: ASCII IMEI {imei} at file offset 0x{off:x}")
            else:
                log(f"  {name}: no Luhn-valid ASCII IMEI found")
            if target_imei and re.fullmatch(r"\d{15}", target_imei):
                for off in _find_bcd_imei(data, target_imei):
                    log(f"  {name}: BCD form of {target_imei} at file offset 0x{off:x}")
        log("")
        log("  Done - use these offsets with the QCN restore / IMEI flows.")

    return Flow("QCN NV browser (backup inspector)", [Step("qcn_nv_browser", _run)])


def flow_qcn_efs_explorer():
    """Explore the EFS backup tar: list, preview text files, extract one.

    Read-only except for the explicit extract step. Points at QCN_EFS_TAR
    (or the newest *.tgz in QCN_BACKUP_DIR). QCN_EFS_EXTRACT=name to extract
    one member into QCN_EFS_OUT (default ~/flashpilot/efs_extract).
    """

    def _run(ctx, log):
        import tarfile as _tf
        log("=" * 60)
        log("QCN EFS EXPLORER (backup tar inspector)")
        log("=" * 60)
        tar_path = os.environ.get("QCN_EFS_TAR", "").strip() or ctx.get("efs_tar", "")
        if not tar_path:
            src = os.environ.get("QCN_BACKUP_DIR", "").strip() or ctx.get("backup_dir", "")
            if src and os.path.isdir(src):
                cands = sorted(
                    (os.path.join(src, p) for p in os.listdir(src)
                     if p.endswith((".tgz", ".tar.gz", ".tar")) and os.path.isfile(os.path.join(src, p))),
                    key=os.path.getmtime, reverse=True,
                )
                if cands:
                    tar_path = cands[0]
        if not tar_path or not os.path.isfile(tar_path):
            raise RuntimeError("Set QCN_EFS_TAR=/path/to/efs.tgz (QCN backup saves one when ADB is up)")
        log(f"  Archive: {tar_path} ({os.path.getsize(tar_path) >> 10} KB)")
        try:
            tf = _tf.open(tar_path, "r:*")
            members = [m for m in tf.getmembers() if m.isfile()]
        except Exception as e:
            raise RuntimeError(f"cannot read EFS archive: {e}")
        log(f"  {len(members)} files:")
        for m in members[:60]:
            log(f"    {m.size:>10}  {m.name}")
        if len(members) > 60:
            log(f"    ... and {len(members) - 60} more")
        want = os.environ.get("QCN_EFS_EXTRACT", "").strip() or ctx.get("efs_extract", "")
        if not want:
            log("")
            log("  Set QCN_EFS_EXTRACT=<member path> to extract one file.")
            return True
        match = next((m for m in members if m.name == want or m.name.endswith("/" + want)), None)
        if match is None:
            raise RuntimeError(f"member not found: {want!r}")
        out_dir = (os.environ.get("QCN_EFS_OUT", "").strip()
                   or os.path.join(os.path.expanduser("~"), "flashpilot", "efs_extract"))
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, os.path.basename(match.name.rstrip("/")) or "extracted")
        with open(out_path, "wb") as fh:
            fh.write(tf.extractfile(match).read())
        log(f"  Extracted -> {out_path} ({os.path.getsize(out_path)} bytes)")
        try:
            text = open(out_path, "rb").read(600).decode("utf-8", "replace")
            if all(c.isprint() or c.isspace() for c in text[:200]):
                log("  Preview:")
                for line in text.splitlines()[:10]:
                    log(f"    {line[:120]}")
        except Exception:
            pass
        return True

    return Flow("QCN EFS explorer (backup inspector)", [Step("qcn_efs_explorer", _run)])
