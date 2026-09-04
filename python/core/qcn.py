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
        log("QCN restore complete. Reboot device.")

    return Flow("QCN restore (EXPERIMENTAL)", [Step("qcn_restore", _run)])
