"""Live device identity resolver — real serial / Android ver / build from device, no fake.

Priority for Android (ADB authorized → real getprop, no USB placeholder):
  1. ADB getprop ro.serialno || ro.boot.serialno → serial (filter 012345... fake)
     ADB serial from `adb devices` is only fallback if getprop empty.
  2. ADB getprop ro.build.version.release + sdk → android, ro.build.display.id → build
  3. MTP GetDeviceInfo serial_number / device_version (when ADB not authorized)
  4. USB target device product/serial (filtered, last resort)

Priority for Apple (05ac):
  1. Lockdown via ideviceinfo -k SerialNumber/UniqueDeviceID/ProductVersion/BuildVersion
  2. pymobiledevice3 usbmux list
  3. USB descriptor product/serial filtered

Fake filter: placeholder serials never emitted as real — show "--" instead so user knows to authorize / replug.
Works for many devices: Samsung/MTK/QC/SPD/Android generic + Apple A9-A15.
"""

import re
import shutil
import subprocess

FAKE_SERIALS = {
    "0123456789abcdef",
    "0123456789abcde",
    "0123456789abc",
    "0123456789ab",
    "0123456789",
    "1234567890abcdef",
    "1234567890abcde",
    "0000000000000000",
    "000000000000000",
    "111111111111111",
    "abcdef0123456789",
    "unknown",
    "n/a",
    "",
}

FAKE_SERIAL_RE = re.compile(r"^(0+|1+|a+b+c+d+e+f+|01234567.*|12345678.*)$", re.I)


def _is_fake_serial(s: str) -> bool:
    if not s:
        return True
    t = s.strip().lower()
    if t in FAKE_SERIALS:
        return True
    # All hex same char? e.g. 0000 or FFF
    if len(t) >= 8 and len(set(t)) == 1:
        return True
    # Sequential placeholder
    if t.startswith("012345") or t.startswith("123456"):
        return True
    # Short serial like "abc" etc
    if len(t) <= 4:
        return True
    return False


def _adb_getprop(name: str, timeout=6) -> str:
    try:
        from . import bridge

        out = bridge.adb_shell(f"getprop {name}", timeout=timeout)
        return (out or "").strip()
    except Exception:
        return ""


def _adb_devices_serial() -> str:
    try:
        from . import bridge

        devs = bridge.adb_status()
        auth = [d for d in devs if d.get("state") == "device"]
        if auth:
            cand = (auth[0].get("serial") or "").strip()
            if cand and not _is_fake_serial(cand):
                return cand
        # fallback even unauthorized extra? not real, skip
        return ""
    except Exception:
        return ""


def _usb_target_serial() -> str:
    try:
        from .mtp import find_samsung  # noqa
        from python.gui.qt_app import _find_target_device  # type: ignore

        dev = _find_target_device()
        if dev:
            s = (dev.get("serial") or "").strip()
            if s and not _is_fake_serial(s) and s.lower() != "adb":
                return s
    except Exception:
        pass
    return ""


def _mtp_serial_and_build() -> tuple:
    """MTP GetDeviceInfo serial_number + device_version (build hint), no ADB needed."""
    try:
        from . import bridge
        from python.gui.qt_app import _find_mtp_device  # type: ignore

        dev = _find_mtp_device()
        if not dev:
            return "", ""
        tgt = f"{dev['vid']:04x}:{dev['pid']:04x}@{dev['bus']}:{dev['address']}"
        info = bridge.mtp_info(tgt, timeout_ms=4000)
        if isinstance(info, dict):
            ser = (info.get("serial_number") or "").strip()
            if _is_fake_serial(ser):
                ser = ""
            bld = (info.get("device_version") or "").strip()
            if bld.lower() == "adb":
                bld = ""
            return ser, bld
    except Exception:
        pass
    return "", ""


def _apple_lockdown_info() -> dict:
    """Apple UDID / Serial / iOS ver / Build via lockdown, no fake."""
    info = {}
    # ideviceinfo -k per key (fast, per-key)
    idev = shutil.which("ideviceinfo")
    if idev:
        for k in ("SerialNumber", "UniqueDeviceID", "ProductVersion", "BuildVersion", "ProductType", "DeviceName"):
            try:
                out = subprocess.run([idev, "-k", k], capture_output=True, text=True, timeout=5).stdout.strip()
                if out and "ERROR" not in out and len(out) < 128:
                    info[k] = out
            except Exception:
                continue
        # If we got at least one, parse full dump for cross-check
        if info:
            return info
    # pymobiledevice3 fallback via usbmux list json
    if shutil.which("pymobiledevice3"):
        try:
            out = subprocess.run(["pymobiledevice3", "usbmux", "list", "-o", "json"], capture_output=True, text=True, timeout=6).stdout
            if out:
                import json

                data = json.loads(out)
                # list may be array of devices
                devs = data if isinstance(data, list) else [data]
                if devs and isinstance(devs[0], dict):
                    d = devs[0]
                    if d.get("SerialNumber") and "SerialNumber" not in info:
                        info["SerialNumber"] = d["SerialNumber"]
                    if d.get("UniqueDeviceID") and "UniqueDeviceID" not in info:
                        info["UniqueDeviceID"] = d["UniqueDeviceID"]
                    if d.get("ProductVersion") and "ProductVersion" not in info:
                        info["ProductVersion"] = d["ProductVersion"]
        except Exception:
            pass
    return info


def get_live_identity() -> dict:
    """Return real {serial, android_ver, build, model, mfr, brand} or empty strings if unavailable.

    Never returns fake 01234... placeholders — caller should show "--" instead.
    """
    out = {"serial": "", "android_ver": "", "build": "", "model": "", "mfr": "", "brand": "", "sdk": ""}
    # Detect Apple first (05ac) — treat separately
    apple = {}
    try:
        from . import bridge

        usb = bridge.detect_all()
        has_apple = any(isinstance(d, dict) and d.get("vid") == 0x05AC for d in usb)
        if has_apple:
            apple = _apple_lockdown_info()
            if apple.get("SerialNumber") and not _is_fake_serial(apple["SerialNumber"]):
                out["serial"] = apple["SerialNumber"]
            elif apple.get("UniqueDeviceID") and not _is_fake_serial(apple["UniqueDeviceID"]):
                out["serial"] = apple["UniqueDeviceID"]
            if apple.get("ProductVersion"):
                out["android_ver"] = apple["ProductVersion"]
                if apple.get("BuildVersion"):
                    out["android_ver"] = f"{apple['ProductVersion']} ({apple['BuildVersion']})"
                out["build"] = apple.get("BuildVersion", "")
            if apple.get("ProductType"):
                out["model"] = apple["ProductType"]
            # Apple device present → return Apple identity even if Android adb also present (dual bus)
            # Only return if we got something real
            if any(out[k] for k in ("serial", "android_ver", "model")):
                return out
    except Exception:
        pass

    # Android path — ADB getprop is truth, not USB descriptor
    has_adb_device = False
    try:
        from . import bridge

        devs = bridge.adb_status()
        has_adb_device = any(d.get("state") == "device" for d in devs)
    except Exception:
        pass

    if has_adb_device:
        serial_prop = _adb_getprop("ro.serialno") or _adb_getprop("ro.boot.serialno") or _adb_getprop("sys.serialnumber") or ""
        if _is_fake_serial(serial_prop):
            serial_prop = ""
        adb_serial = _adb_devices_serial()
        serial = serial_prop or adb_serial
        if serial and not _is_fake_serial(serial):
            out["serial"] = serial

        # Model / brand
        model = _adb_getprop("ro.product.model")
        mfr = _adb_getprop("ro.product.manufacturer")
        brand = _adb_getprop("ro.product.brand")
        if model and model.lower() != "adb":
            out["model"] = model
        if mfr and mfr.lower() != "adb":
            out["mfr"] = mfr
        if brand and brand.lower() != "adb":
            out["brand"] = brand

        # Android ver + sdk
        rel = _adb_getprop("ro.build.version.release")
        sdk = _adb_getprop("ro.build.version.sdk")
        if rel:
            out["android_ver"] = f"{rel} (API {sdk})" if sdk else rel
            out["sdk"] = sdk
        # Build
        bld = _adb_getprop("ro.build.display.id") or _adb_getprop("ro.build.version.incremental") or _adb_getprop("ro.build.version.security_patch") or ""
        if bld and bld.lower() not in ("adb", "unknown"):
            out["build"] = bld
        # Never leak fake — if we got real serial/model/build, return
        if any([out["serial"], out["model"], out["build"], out["android_ver"]]):
            return out

    # Fallback without ADB: MTP serial/build
    ser_mtp, bld_mtp = _mtp_serial_and_build()
    if ser_mtp and not _is_fake_serial(ser_mtp):
        out["serial"] = ser_mtp
    if bld_mtp and bld_mtp.lower() != "adb":
        out["build"] = bld_mtp

    # Last resort USB target (filtered)
    if not out["serial"]:
        us = _usb_target_serial()
        if us and not _is_fake_serial(us):
            out["serial"] = us
    # Model via USB target product if still empty
    if not out["model"]:
        try:
            from python.gui.qt_app import _find_target_device

            dev = _find_target_device()
            if dev:
                prod = (dev.get("product") or "").strip()
                if prod and prod.lower() not in ("adb", "samsung_android", "") and not _is_fake_serial(prod):
                    out["model"] = prod
        except Exception:
            pass
    return out
