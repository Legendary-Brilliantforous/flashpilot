"""Apple iCloud add/remove — DFU / usbmuxd / ramdisk (EXPERIMENTAL).

1.2.1-beta ships read-only discovery (info, activation state via usbmuxd when
available) and EXPERIMENTAL-gated bypass stubs. Full ramdisk bypass requires
HIL with checkm8 DFU samples.

Device detection runs on the native Rust bridge (`detect-all`: VID 0x05AC
classified with PID, so DFU 1227 / Recovery 1281 / Normal 12a8 are told
apart without shelling out to lsusb).

Lockdown-level detail (ActivationState, SerialNumber, ProductType) needs the
usbmuxd + lockdown plist protocol — no Rust implementation yet, so the
optional `pymobiledevice3` / `libimobiledevice` tools remain the only source
for that tier (flagged as the pending Rust usbmuxd migration).
"""

import os
import re
import shutil
import subprocess

from . import bridge
from .flow import Flow, Step


def _detect_apple_native() -> list:
    """Apple devices from the native Rust enumeration (no lsusb).

    Returns [{vid, pid, bus, address, mode, bcd_device}] for VID 0x05AC."""
    try:
        devs = bridge.detect_all() or []
    except Exception:
        return []
    return [
        d for d in devs
        if isinstance(d, dict) and d.get("vid") == 0x05AC
    ]


def _lsusb_apple() -> str:
    """Legacy lsusb text (kept for callers; primary path is _detect_apple_native)."""
    try:
        out = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5).stdout
        apple = [l for l in out.splitlines() if "05ac" in l.lower()]
        return "\n".join(apple) if apple else ""
    except Exception:
        return ""


def _usbmuxd_present() -> bool:
    for p in ["/var/run/usbmuxd", "/var/run/usbmuxd.socket"]:
        if os.path.exists(p):
            return True
    return shutil.which("ideviceinfo") is not None or shutil.which("pymobiledevice3") is not None


def _native_lockdown_info(log) -> dict:
    """Native Rust usbmuxd + lockdown info (no external tools).

    device_id = -1 -> use the first attached device. Returns the lockdown
    GetValue dict (unpaired: non-protected keys) or {} when usbmuxd is not
    running / no device attached."""
    from . import bridge as _bridge

    try:
        out = _bridge._run(["apple-info"], timeout=15)
        import json as _json
        data = _json.loads(out or "{}") if isinstance(out, str) else {}
    except Exception as e:
        log(f"  native usbmuxd: {e}")
        return {}
    vals = data.get("lockdown") or {}
    if vals:
        for k in ("DeviceName", "ProductType", "ProductVersion", "ActivationState",
                  "SerialNumber", "BuildVersion", "UniqueDeviceID"):
            if vals.get(k):
                log(f"  native: {k}: {vals[k]}")
    return {k: str(v) for k, v in vals.items()} if isinstance(vals, dict) else {}


def _idevice_info(log, timeout=12) -> dict:
    info = {}
    # Native first: Rust usbmuxd + lockdown GetValue (no external tools).
    try:
        info = _native_lockdown_info(log)
        if info:
            return info
    except Exception as e:
        log(f"  native usbmuxd: {e}")
    # Fallback: external tools (pymobiledevice3 / ideviceinfo)
    if shutil.which("pymobiledevice3"):
        try:
            out = subprocess.run(["pymobiledevice3", "usbmux", "list"], capture_output=True, text=True, timeout=timeout).stdout
            log(f"  pymobiledevice3 usbmux list: {out[:400]}")
        except Exception as e:
            log(f"  pymobiledevice3: {e}")
    # Try libimobiledevice ideviceinfo
    idev = shutil.which("ideviceinfo")
    if idev:
        try:
            out = subprocess.run([idev, "-s"], capture_output=True, text=True, timeout=timeout).stdout
            for line in out.splitlines()[:60]:
                if any(k in line for k in ["ActivationState", "ProductVersion", "ProductType", "UniqueDeviceID", "SerialNumber", "DeviceName"]):
                    log(f"  {line.strip()}")
                    # parse k: v
                    if ":" in line:
                        k, v = line.split(":", 1)
                        info[k.strip()] = v.strip()
        except Exception as e:
            log(f"  ideviceinfo: {e}")
    return info


def flow_apple_info():
    def _run(ctx, log):
        log("=" * 60)
        log("Apple device info (read-only, EXPERIMENTAL)")
        log("=" * 60)
        apples = _detect_apple_native()
        if apples:
            log("  Native (Rust) Apple devices:")
            for d in apples:
                pid = d.get("pid", 0)
                log(f"    05ac:{pid:04x} bus={d.get('bus')} addr={d.get('address')} mode={d.get('mode')}")
                # DFU 05ac:1227, Recovery 05ac:1281, Normal 05ac:12a8
                if pid == 0x1227:
                    log("    -> DFU mode (05ac:1227) — checkm8 candidate if A5-A11")
                elif pid == 0x1281:
                    log("    -> Recovery mode (05ac:1281)")
                elif pid == 0x12a8 or d.get("mode") == "apple":
                    log("    -> Normal/Recovery mode — needs usbmuxd for lockdown")
        else:
            log("  No Apple 05ac device detected (native USB scan). Plug iPhone/iPad via USB.")
        log(f"  usbmuxd: {'present' if _usbmuxd_present() else 'not found (install libimobiledevice / pymobiledevice3)'}")
        info = _idevice_info(log)
        if not info:
            log("  No lockdown info — device may be in DFU/Recovery or not trusted")
        log("  Tip: Trust this computer on device when prompted, then re-run.")
        log("  Apple info complete (read-only).")

    return Flow("Apple info (EXPERIMENTAL — read-only)", [Step("apple_info", _run)])


def flow_apple_icloud_remove():
    def _run(ctx, log):
        from .experimental import check_gate_strict, per_run_acked_from_ctx, audit_log

        if not check_gate_strict("apple_icloud_remove", per_run_acked_from_ctx(ctx), log):
            raise RuntimeError("Apple iCloud Remove is EXPERIMENTAL — per-run ack required")
        audit_log("apple_icloud_remove", "remove_attempt")
        log("[EXPERIMENTAL] Apple iCloud Remove — educational purpose only. You certify you own this device.")
        # Check for DFU or usbmuxd path (native Rust detection)
        apples = _detect_apple_native()
        pids = {d.get("pid") for d in apples}
        if 0x1227 not in pids and not _usbmuxd_present():
            log("  No DFU (05ac:1227) and no usbmuxd — plug device in DFU (checkm8) or Recovery/Normal with trust")
            log("  DFU enter: vary by model — e.g. iPhone X: Vol Down + Side, hold Power sequence")
        log("  In beta: ramdisk SSH path not yet HIL-validated — preparing placeholder flow only")
        ramdisk = os.environ.get("APPLE_RAMDISK", "").strip()
        if ramdisk and os.path.isfile(ramdisk):
            log(f"  Found custom ramdisk {ramdisk} ({os.path.getsize(ramdisk)} bytes) — would boot via iRecovery / checkm8 payload")
            log("  [EXPERIMENTAL] Ramdisk boot stub — set APPLE_DO_RAMDISK=1 after HIL")
            if os.environ.get("APPLE_DO_RAMDISK") == "1":
                log("  Would execute: ipwnDFU + iRecovery -f ramdisk.im4p + boot")
            else:
                log("  Prepared only. Provide activation_records patch via APPLE_ACTIVATION_PLIST.")
        else:
            log("  No APPLE_RAMDISK provided. Set APPLE_RAMDISK=/path/to/ramdisk.im4p to attempt ramdisk boot (after HIL).")
        log("  Flow finished (EXPERIMENTAL placeholder). HIL with DFU sample required for autonomous bypass.")

    return Flow("Apple iCloud Remove (EXPERIMENTAL — edu only)", [Step("apple_icloud_remove", _run)])


def flow_apple_icloud_add():
    def _run(ctx, log):
        from .experimental import check_gate_strict, per_run_acked_from_ctx, audit_log

        if not check_gate_strict("apple_icloud_add", per_run_acked_from_ctx(ctx), log):
            raise RuntimeError("Apple iCloud Add is EXPERIMENTAL — per-run ack required")
        audit_log("apple_icloud_add", "add_attempt")
        log("[EXPERIMENTAL] Apple iCloud Add — educational, own device only")
        plist = os.environ.get("APPLE_ACTIVATION_PLIST", "").strip()
        if plist and os.path.isfile(plist):
            log(f"  Found activation plist {plist} — would push via lockdown AFC")
        else:
            log("  No APPLE_ACTIVATION_PLIST — set path to activation_record.plist to attempt push")
        if not _usbmuxd_present():
            raise RuntimeError("usbmuxd / libimobiledevice not available — install and trust device first")
        _idevice_info(log)
        log("  Add flow placeholder — HIL required.")

    return Flow("Apple iCloud Add (EXPERIMENTAL — edu only)", [Step("apple_icloud_add", _run)])


def flow_apple_passcode_guide():
    """iPhone passcode / Screen Time scope guide (honest, backup-based).

    Read-only checks + guidance. States plainly what no free tool can do:
    Activation Lock (iCloud) is Apple-server-side and cannot be bypassed
    offline; a lost-mode/erased device with FMI ON stays locked without the
    Apple ID. What IS real: (a) Screen Time passcode removal from an
    ENCRYPTED iTunes/Finder backup you own, (b) passcode retry/wait guidance,
    (c) DFU/restore path that keeps the device usable but NOT activated.
    Never writes to the device.
    """

    def _run(ctx, log):
        log("=" * 60)
        log("IPHONE PASSCODE / SCREEN TIME SCOPE (honest, backup-based)")
        log("=" * 60)
        tools = {t: shutil.which(t) for t in
                 ("ideviceinfo", "idevicebackup2", "pymobiledevice3", "iproxy")}
        for t, p in tools.items():
            log(f"  {t:<16}: {p or '(not installed)'}")
        if not any(tools.values()):
            log("")
            log("  Install libimobiledevice for USB access:")
            log("    sudo apt install libimobiledevice-utils usbmuxd")
        log("")
        info = _idevice_info(log)
        act = (info.get("ActivationState") or "").lower()
        if act:
            log(f"  ActivationState: {act}")
            if "unactivated" in act or "activation" in act and "activat" in act:
                log("  NOTE: an unactivated device with Find My ON cannot be")
                log("  activated without the Apple ID - no offline tool changes this.")
        log("")
        log("  Honest options:")
        log("  1. Screen Time passcode (iOS 12+): make an ENCRYPTED backup")
        log("     (Finder/iTunes, 'Encrypt local backup' ON), then remove the")
        log("     Screen Time passcode from that backup you own. Needs the")
        log("     backup password if one was set - there is no way around it.")
        log("  2. Device passcode, FMI OFF, trusted PC: 'Erase All Content and")
        log("     Settings' on-device, or Finder restore - then set up as NEW")
        log("     (not from backup) to avoid re-locking to the old passcode.")
        log("  3. Device passcode, FMI ON: DFU restore makes the phone boot,")
        log("     but Activation Lock remains. Only the Apple ID (or Apple")
        log("     with proof of purchase) removes it.")
        log("  4. Retry delays ('try again in X minutes') are enforced on-device;")
        log("     waiting them out is the only free path - do not wipe blindly.")
        log("")
        log("  Anyone promising offline Activation Lock removal is selling")
        log("  the DFU restore in (3) with the lock still on.")

    return Flow("iPhone passcode scope guide (honest)", [Step("apple_passcode_guide", _run)])
