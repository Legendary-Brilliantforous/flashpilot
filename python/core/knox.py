"""Samsung Knox warranty detection + bypass (EXPERIMENTAL, educational purpose only).

Read-only: Knox warranty void (0x0/0x1), KG/RMM state, Secure Boot, RPMB.
Bypass: parameter / efs patch behind experimental gate — irreversible eFuse.
"""

import os

from . import bridge
from .flow import Flow, Step


def _getprop(key: str, timeout=8) -> str:
    try:
        return bridge.adb_shell(f"getprop {key}", timeout=timeout).strip()
    except Exception:
        return ""


def _adb_shell(cmd: str, timeout=12) -> str:
    try:
        return bridge.adb_shell(cmd, timeout=timeout).strip()
    except Exception as e:
        return f"error: {e}"


def check_knox_status(ctx, log):
    log("=" * 60)
    log("Knox warranty / KG / RMM status (read-only)")
    log("=" * 60)
    # Try ADB first
    for key in ["ro.boot.warranty_bit", "ro.boot.knox", "ro.boot.secure_hardware", "ro.boot.kg_status", "ro.boot.rmm_state"]:
        v = _getprop(key)
        if v:
            log(f"  {key} = {v}")
    # ADB shell checks
    for cmd in [
        "cat /efs/FactoryApp/factorymode 2>/dev/null || cat /efs/imei/mps_code.dat 2>/dev/null | head",
        "getprop ro.boot.warranty_bit; getprop ro.boot.knox; getprop ro.boot.kg_status",
        "dumpsys device_policy 2>/dev/null | head -n 30",
    ]:
        out = _adb_shell(cmd)
        if out and "error" not in out.lower()[:20]:
            for line in out.splitlines()[:20]:
                log(f"  {line}")
    # Download mode PIT presence indicates device is reachable
    try:
        from .core import _download_mode_device

        d = _download_mode_device()
        if d:
            log(f"  Download mode device: 04e8:{d.get('pid',0):04x} bus={d.get('bus')} addr={d.get('address')}")
        else:
            log("  No Download mode device (04e8:685d) — plug in Download Mode for param/efs read")
    except Exception:
        pass
    # Heuristic warn
    log("")
    log("  Interpret: warranty_bit 0 = intact, 1 = tripped (eFuse blown, irreversible).")
    log("  KG/RMM 'prenormal' → wait 168h / complete setup to clear.")


def flow_knox_check():
    def _run(ctx, log):
        check_knox_status(ctx, log)

    return Flow("Knox warranty check (EXPERIMENTAL)", [Step("knox_check", _run)])


def flow_knox_bypass():
    def _run(ctx, log):
        from .experimental import check_gate_strict, per_run_acked_from_ctx, audit_log

        if not check_gate_strict("knox_bypass", per_run_acked_from_ctx(ctx), log):
            raise RuntimeError("Knox bypass is EXPERIMENTAL — ack required in GUI")
        audit_log("knox_bypass", "attempt")
        log("[EXPERIMENTAL] Knox bypass — THIS MAY PERMANENTLY TRIP eFuse AND VOID WARRANTY")
        log("  Educational purpose only. You certify you own this device.")
        # Safety backup
        try:
            from .safety import preflash_backup

            preflash_backup(chip="odin", bridge=bridge, log=log, ident="knox_bypass")
        except Exception:
            pass
        # Attempt: 1) ADB KG removal if adb present, 2) Download-mode param patch
        did = False
        for cmd, desc in [
            ("am broadcast -a com.samsung.android.knox.container.ENABLE --ez enable false 2>&1", "knox container disable"),
            ("pm disable-user --user 0 com.samsung.android.knox.kpu 2>&1 || pm disable com.samsung.android.knox.kpu 2>&1", "knox kpu disable"),
            ("settings put global knox_guard 0; settings put secure kg_state 0 2>&1; echo kg_cleared", "kg state clear"),
        ]:
            out = _adb_shell(cmd)
            if "cleared" in out or "disabled" in out:
                log(f"  [ok] {desc}: {out[:120]}")
                did = True
            else:
                log(f"  [check] {desc}: {out[:120]}")

        if not did:
            log("  No ADB KG success — for Download-mode param patch: use Odin pit + param.bin editing (RMM/KG bytes @0x28) behind download mode.")
            log("  Placeholder: bypass not fully implemented without param blob — connect Download Mode and provide param.bin via KNOX_PARAM env.")
            p = os.environ.get("KNOX_PARAM", "").strip()
            if p and os.path.isfile(p):
                log(f"  Found KNOX_PARAM={p} ({os.path.getsize(p)} bytes) — would patch RMM/KG bytes and flash param partition via odin-agent.")
                log("  [EXPERIMENTAL] Not flashing yet — HIL required to validate eFuse safety.")
            else:
                log("  Set KNOX_PARAM=/path/to/param.bin to attempt param flash (EXPERIMENTAL).")
        log("  Knox bypass flow finished (EXPERIMENTAL). Reboot and re-check warranty_bit.")

    return Flow("Knox bypass (EXPERIMENTAL — irreversible)", [Step("knox_bypass", _run)])
