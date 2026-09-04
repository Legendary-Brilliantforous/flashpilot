"""Apple iCloud add/remove — DFU / usbmuxd / ramdisk (EXPERIMENTAL).

1.2.1-beta ships read-only discovery (info, activation state via usbmuxd when
available) and EXPERIMENTAL-gated bypass stubs. Full ramdisk bypass requires
HIL with checkm8 DFU samples.

Dep: optional `pymobiledevice3` or `libimobiledevice` tools (ideviceinfo).
Falls back to usbmuxd socket / lsusb detection when deps absent.
"""

import os
import re
import shutil
import subprocess

from .flow import Flow, Step


def _lsusb_apple() -> str:
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


def _idevice_info(log, timeout=12) -> dict:
    info = {}
    # Try pymobiledevice3
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
        apple = _lsusb_apple()
        if apple:
            log("  lsusb Apple devices:")
            for line in apple.splitlines():
                log(f"    {line}")
                # DFU 05ac:1227, Recovery 05ac:1281, Normal 05ac:12a8
                if "1227" in line:
                    log("    -> DFU mode (05ac:1227) — checkm8 candidate if A5-A11")
                elif "1281" in line:
                    log("    -> Recovery mode (05ac:1281)")
                elif "12a8" in line:
                    log("    -> Normal mode (05ac:12a8) — needs usbmuxd")
        else:
            log("  No Apple 05ac device on lsusb. Plug iPhone/iPad via USB.")
        log(f"  usbmuxd: {'present' if _usbmuxd_present() else 'not found (install libimobiledevice / pymobiledevice3)'}")
        info = _idevice_info(log)
        if not info:
            log("  No lockdown info — device may be in DFU/Recovery or not trusted")
        log("  Tip: Trust this computer on device when prompted, then re-run.")
        log("  Apple info complete (read-only).")

    return Flow("Apple info (EXPERIMENTAL — read-only)", [Step("apple_info", _run)])


def flow_apple_icloud_remove():
    def _run(ctx, log):
        from .experimental import check_gate, audit_log

        if not check_gate("apple_icloud_remove", log):
            raise RuntimeError("Apple iCloud Remove is EXPERIMENTAL — ack required in GUI")
        audit_log("apple_icloud_remove", "remove_attempt")
        log("[EXPERIMENTAL] Apple iCloud Remove — educational purpose only. You certify you own this device.")
        # Check for DFU or usbmuxd path
        apple = _lsusb_apple()
        if "1227" not in apple and not _usbmuxd_present():
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
        from .experimental import check_gate, audit_log

        if not check_gate("apple_icloud_add", log):
            raise RuntimeError("Apple iCloud Add is EXPERIMENTAL — ack required")
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
