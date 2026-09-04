"""MediaTek + SPD/UNISOC IMEI repair / change (EXPERIMENTAL).

Mirrors ``qcn.py`` for Qualcomm: the MediaTek path targets the modem NVRAM
(``nvdata``/``nvram`` MP0B001_* records) and the SPD path targets the modem
NV via BSL. Both are read/validate/restore oriented in this release — the
autonomous write is gated behind an EXPLICIT env + an every-run ack in the GUI,
and full partition roadmaps land after HIL on real samples.

TIM inject safety invariants shared with qcn.py:
  * IMEI must be 15 digits and Luhn-valid (warn-only, never auto-correct).
  * ``IMEI Repaired`` = restore the IMEI you previously backed up from THIS
    device; ``IMEI Change`` requires an explicit ``IMEI_CHANGE_CONFIRM`` env
    equal to the typed IMEI before any attempt.
"""

import os
import re
import struct

from . import bridge
from .flow import Flow, Step


def _luhn_ok(imei: str) -> bool:
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


def _bcd(imei: str) -> bytes:
    b = bytearray(9)
    for i in range(7):
        a = int(imei[i * 2]) if i * 2 < len(imei) else 0xF
        c = int(imei[i * 2 + 1]) if i * 2 + 1 < len(imei) else 0xF
        b[i] = (c << 4) | a
    if len(imei) == 15:
        b[7] = (0xF << 4) | int(imei[14])
        b[8] = 0
    return bytes(b)


def _read_imei_env(ctx):
    imei = (os.environ.get("TARGET_IMEI", "").strip() or ctx.get("imei", "") or "").replace(" ", "")
    if not imei or not re.fullmatch(r"\d{15}", imei):
        raise RuntimeError("Set TARGET_IMEI=15-digit IMEI (or pass imei= in ctx)")
    if not _luhn_ok(imei):
        # raise is intentional for change, warn for repair is handled by caller
        pass
    return imei


def _mtk_nv_targets():
    """MediaTek modem-NVRAM partitions, probed in order."""
    return ("nvdata", "nvram", "protect1", "protect2")


def flow_imei_repair_mtk():
    """MediaTek IMEI repair (restore from backup / re-write nvdata)."""

    def _run(ctx, log):
        from .experimental import check_gate_strict, per_run_acked_from_ctx, audit_log

        if not check_gate_strict("imei_repair_mtk", per_run_acked_from_ctx(ctx), log):
            raise RuntimeError("MTK IMEI repair is EXPERIMENTAL — per-run ownership ack required (GUI checkbox or EXPERIMENTAL_ACK=1)")
        audit_log("imei_repair_mtk", "repair_attempt")
        log("[EXPERIMENTAL] MediaTek IMEI repair — restore your backed-up IMEI")
        imei = _read_imei_env(ctx)
        log(f"  IMEI {imei} — Luhn {'OK' if _luhn_ok(imei) else 'FAIL (will still attempt, verify by hand)'}")
        log(f"  NV BCD (9 bytes): {_bcd(imei).hex()}")
        log("  Targets (probed): " + ", ".join(_mtk_nv_targets()))
        da = os.environ.get("MTK_DA", "").strip()
        log(f"  DA: {da or '(auto-detect via ~/Downloads / BROM)'}")
        # Best-effort: read back the nvdata record to locate the MP0B001_* IMEI slot.
        tgt = ctx.get("target") or ""
        if not tgt:
            log("  No BROM target yet — power off, hold Vol Up+Down, plug USB (0e8d:0003 BROM, or 0e8d:2000 preloader).")
        log("  [EXPERIMENTAL] Autonomous nvdata rewrite not HIL-validated yet — prepared BCD only.")
        log("  After HIL: patch MP0B001_003 IMEI + checksum, then flash nvdata via mtk-flash.")
        log("  Done — re-read with 'Read Device Info -> MTK BROM' to verify.")

    return Flow("MTK IMEI repair (EXPERIMENTAL — restore-only)", [Step("imei_repair_mtk", _run)])


def flow_imei_change_mtk():
    """MediaTek IMEI change (double-gated, higher legal exposure)."""

    def _run(ctx, log):
        from .experimental import check_gate_strict, per_run_acked_from_ctx, audit_log

        if not check_gate_strict("imei_change_mtk", per_run_acked_from_ctx(ctx), log):
            raise RuntimeError("MTK IMEI change is EXPERIMENTAL — per-run ownership ack required (GUI checkbox or EXPERIMENTAL_ACK=1)")
        audit_log("imei_change_mtk", "change_attempt")
        log("[EXPERIMENTAL] MediaTek IMEI change — usually ILLEGAL on a foreign device")
        imei = _read_imei_env(ctx)
        if not _luhn_ok(imei):
            raise RuntimeError(f"IMEI {imei} fails Luhn — refusing to write an invalid IMEI")
        # Double-confirm env, mirroring qcn.py: IMEI_CHANGE_CONFIRM must equal IMEI.
        confirm = os.environ.get("IMEI_CHANGE_CONFIRM", "").strip()
        if confirm != imei:
            raise RuntimeError(
                f"Set IMEI_CHANGE_CONFIRM={imei} to double-confirm before attempting IMEI change."
            )
        log(f"  Confirmed change to {imei}. BCD {_bcd(imei).hex()}")
        log("  [EXPERIMENTAL] Change write is HIL-gated — prepared only, no autonomous nvdata write yet.")
        log("  Set MTK_IMEI_DO_WRITE=1 after HIL to enable the nvdata flash.")

    return Flow("MTK IMEI change (EXPERIMENTAL — double-gated)", [Step("imei_change_mtk", _run)])


def flow_imei_repair_spd():
    """SPD/UNISOC IMEI repair (restore via BSL modem-NV)."""

    def _run(ctx, log):
        from .experimental import check_gate_strict, per_run_acked_from_ctx, audit_log

        if not check_gate_strict("imei_repair_spd", per_run_acked_from_ctx(ctx), log):
            raise RuntimeError("SPD IMEI repair is EXPERIMENTAL — per-run ownership ack required (GUI checkbox or EXPERIMENTAL_ACK=1)")
        audit_log("imei_repair_spd", "repair_attempt")
        log("[EXPERIMENTAL] SPD/UNISOC IMEI repair — restore your backed-up IMEI")
        imei = _read_imei_env(ctx)
        log(f"  IMEI {imei} — Luhn {'OK' if _luhn_ok(imei) else 'FAIL'}")
        log(f"  NV BCD: {_bcd(imei).hex()}")
        log("  [EXPERIMENTAL] BSL modem-NV write not HIL-validated — prepared BCD only.")
        log("  Connect in SPD download mode and provide FDL1/FDL2 to proceed post-HIL.")

    return Flow("SPD IMEI repair (EXPERIMENTAL — restore-only)", [Step("imei_repair_spd", _run)])


def flow_imei_change_spd():
    """SPD/UNISOC IMEI change (double-gated, higher legal exposure)."""

    def _run(ctx, log):
        from .experimental import check_gate_strict, per_run_acked_from_ctx, audit_log

        if not check_gate_strict("imei_change_spd", per_run_acked_from_ctx(ctx), log):
            raise RuntimeError("SPD IMEI change is EXPERIMENTAL — per-run ownership ack required (GUI checkbox or EXPERIMENTAL_ACK=1)")
        audit_log("imei_change_spd", "change_attempt")
        log("[EXPERIMENTAL] SPD/UNISOC IMEI change — usually ILLEGAL on a foreign device")
        imei = _read_imei_env(ctx)
        if not _luhn_ok(imei):
            raise RuntimeError(f"IMEI {imei} fails Luhn — refusing invalid write")
        confirm = os.environ.get("IMEI_CHANGE_CONFIRM", "").strip()
        if confirm != imei:
            raise RuntimeError(f"Set IMEI_CHANGE_CONFIRM={imei} to double-confirm before attempting IMEI change.")
        log(f"  Confirmed change to {imei}. BCD {_bcd(imei).hex()}")
        log("  [EXPERIMENTAL] Change write is HIL-gated — prepared only. Set SPD_IMEI_DO_WRITE=1 after HIL.")

    return Flow("SPD IMEI change (EXPERIMENTAL — double-gated)", [Step("imei_change_spd", _run)])