"""Stable multi-device identity for FlashPilot.

Problem: every resolver historically grabbed the *first* matching device
(`find_samsung`, `good[0]`, `samsung[0]`...), and bridge targets are
`vid:pid@bus:addr`, which goes stale on every USB re-enumeration (the exact
cause of odin `usb device Fail`).

This module provides:

* :func:`device_key` — a stable identity string for a USB dict or ADB entry.
  Serial-first (`adb:<serial>`), else stable USB port path
  (`usb:<port_numbers>`), else volatile `vid:pid@bus:addr` as last resort.
* :func:`list_devices` — one unified, de-duplicated list across USB +
  ADB (+MTK/EDL/SPD detail where the bridge reports it), each entry with
  ``key``, ``label``, ``transports`` (job-mode names) and the raw dicts.
* :func:`resolve_usb_target` — turn a stored key back into a *fresh*
  `vid:pid@bus:addr` target by re-scanning. Call this right before opening
  any USB session.
* :func:`device_scope` / :func:`current_key` — a thread-local (ContextVar)
  ambient device selector. Flow runners set it around ``flow.run()``; the
  ``key=None`` default of every resolver below reads it. Zero call-site
  changes, fully backward compatible, and headless callers can scope
  explicitly without a GUI.

Threading: each flow runs in its own daemon thread, so the ContextVar is
naturally per-operation. Parallel ops on different devices are isolated.
"""

from __future__ import annotations

import contextvars

# Ambient device key for the current thread. None = legacy first-match.
_current_key: contextvars.ContextVar = contextvars.ContextVar(
    "flashpilot_device_key", default=None
)


def current_key():
    """Return the ambient device key for this thread, or None."""
    try:
        return _current_key.get()
    except LookupError:
        return None


class device_scope:
    """Context manager pinning the ambient device key for this thread.

    Usage::

        with devices.device_scope(key):
            flow.run(ctx, log)
    """

    def __init__(self, key):
        self.key = key
        self._token = None

    def __enter__(self):
        self._token = _current_key.set(self.key)
        return self.key

    def __exit__(self, *exc):
        try:
            _current_key.reset(self._token)
        except Exception:
            _current_key.set(None)
        return False


def _norm_serial(value):
    s = (value or "")
    if not isinstance(s, str):
        s = str(s)
    s = s.strip()
    if not s or s.lower() in ("null", "none", "unknown", "?"):
        return ""
    return s


# Vendor VIDs that always count as phones/tablets (mirrors the GUI's
# DeviceMonitor classification: Samsung/MTK/Qualcomm/UNISOC/Google/Apple).
KNOWN_PHONE_VIDS = frozenset({0x04E8, 0x05C6, 0x0E8D, 0x1782, 0x18D1, 0x05AC})

# Other Android vendor VIDs (same set as the GUI's _ANDROID_GENERIC_VIDS).
ANDROID_GENERIC_VIDS = frozenset({0x18D1, 0x0BB4, 0x2717, 0x2A70, 0x12D1, 0x22D9, 0x2AE5})

# Product/manufacturer keywords that mark a non-vendor VID as a phone.
_PHONE_NAME_KEYWORDS = (
    "android", "phone", "tecno", "infinix", "itel", "xiaomi", "redmi",
    "oppo", "vivo", "oneplus", "realme", "pixel", "nexus", "motorola",
    "lenovo", "huawei", "honor", "asus", "transsion", "spark", "smartphone",
)


def is_phone(d):
    """True if a USB device dict plausibly is a phone/tablet.

    Hubs, HID keyboards/mice, webcams, smartcard readers (e.g. the Broadcom
    BCM5880 with its bogus 0123456789ABCD serial) and similar peripherals
    must never appear as device rows — otherwise one plugged-in modem shows
    up as a dozen "devices".
    """
    if not isinstance(d, dict):
        return False
    vid = d.get("vid", 0)
    if vid in KNOWN_PHONE_VIDS:
        return True
    ifaces = d.get("interfaces") or []
    if any(isinstance(i, dict) and i.get("class") == 255
           and i.get("subclass") == 66 for i in ifaces):
        return True  # ADB gadget (255/66/*)
    if any(isinstance(i, dict) and i.get("class") == 6 for i in ifaces):
        return True  # MTP/PTP image interface
    if vid in ANDROID_GENERIC_VIDS:
        return True
    prod = (d.get("product") or "").lower() if isinstance(d.get("product"), str) else ""
    mfr = (d.get("manufacturer") or "").lower() if isinstance(d.get("manufacturer"), str) else ""
    for kw in _PHONE_NAME_KEYWORDS:
        if kw in prod or kw in mfr:
            return True
    return False


def device_key(d):
    """Stable identity string for a USB device dict or ADB entry dict.

    * ADB entries (``serial`` + ``state`` keys) → ``adb:<serial>``.
    * USB dicts with a usable ``serial`` → ``adb:<serial>`` (same phone as
      its ADB entry — this is what merges the two views).
    * USB dicts with ``port_numbers`` → ``usb:<port_numbers>`` (stable
      across re-enumeration; bus/address are not).
    * Otherwise → ``usb:<vid:pid>@<bus>:<addr>`` (volatile fallback).
    """
    if not isinstance(d, dict):
        return ""
    serial = _norm_serial(d.get("serial"))
    if serial and ("state" in d or "extra" in d):
        return f"adb:{serial}"
    if serial:
        return f"adb:{serial}"
    ports = (d.get("port_numbers") or "").strip() if isinstance(d.get("port_numbers"), str) else ""
    if ports:
        return f"usb:{ports}"
    try:
        vid = int(d.get("vid") or 0)
        pid = int(d.get("pid") or 0)
        bus = d.get("bus")
        addr = d.get("address")
    except (TypeError, ValueError):
        return ""
    return f"usb:{vid:04x}:{pid:04x}@{bus}:{addr}"


def match_key(d, key):
    """True if device dict ``d`` is the device identified by ``key``."""
    if not key:
        return True
    return device_key(d) == key


def _usb_transports(d, adb_serials):
    """Job-mode transport names for one USB device dict."""
    from . import mtp as _mtp

    transports = []
    vid = d.get("vid")
    pid = d.get("pid")
    if _mtp.is_adb_composite(d):
        transports.append("ADB")
    if vid == 0x04E8:
        from .core import _ODIN_PIDS as _odin_pids

        if pid == 0x685C:
            transports.append("Samsung BROM")
        elif pid in _odin_pids and not _mtp.is_adb_composite(d):
            transports.append("Download mode")
        elif pid == 0x6860 or not transports:
            transports.append("MTP")
        # A Samsung in any USB mode may also expose ADB via its serial.
        serial = _norm_serial(d.get("serial"))
        if serial and serial in adb_serials and "ADB" not in transports:
            transports.append("ADB")
    elif vid == 0x0E8D:
        from . import mtk as _mtk

        stage = _mtk.pid_stage(pid or 0)
        if stage in ("brom", "preloader"):
            transports.append("MTK BROM")
        elif stage == "da":
            transports.append("MTK")
    elif vid == 0x05C6 and pid == 0x9008:
        transports.append("EDL")
    elif vid == 0x18D1:
        transports.append("FASTBOOT")
    elif vid == 0x1782:
        transports.append("SPD")
    if not transports:
        transports.append("MTP")
    # De-duplicate, preserve order.
    seen = set()
    out = []
    for t in transports:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _usb_label(d, adb_state_by_serial):
    """Short human label: model/product + serial + pid."""
    mfr = (d.get("manufacturer") or "").strip()
    prod = (d.get("product") or "").strip()
    serial = _norm_serial(d.get("serial"))
    name = prod or mfr or "USB device"
    bits = [name]
    if serial:
        state = adb_state_by_serial.get(serial, "")
        bits.append(f"{serial}" + (f" [{state}]" if state else ""))
    try:
        bits.append(f"{int(d.get('vid') or 0):04x}:{int(d.get('pid') or 0):04x}")
    except (TypeError, ValueError):
        pass
    return " · ".join(bits)


def list_devices():
    """Unified device list across USB + ADB.

    Returns a list of ``{"key", "label", "transports", "usb", "adb"}`` dicts.
    USB entries carrying an ADB-listed serial are merged into a single row
    (key ``adb:<serial>``); standalone ADB entries (e.g. TCP/emulator) and
    USB entries without serials each get their own row.
    """
    from . import bridge as _bridge

    try:
        usb_devs = _bridge.detect_all()
    except _bridge.BridgeError:
        usb_devs = []
    if not isinstance(usb_devs, list):
        usb_devs = []
    try:
        adb_devs = _bridge.adb_status()
    except _bridge.BridgeError:
        adb_devs = []
    if not isinstance(adb_devs, list):
        adb_devs = []

    adb_by_serial = {}
    for a in adb_devs:
        if isinstance(a, dict):
            s = _norm_serial(a.get("serial"))
            if s:
                adb_by_serial[s] = a.get("state", "")

    rows = []
    claimed_adb = set()
    for d in usb_devs:
        if not isinstance(d, dict):
            continue
        if not is_phone(d):
            continue  # hub / HID / webcam / card reader — not a phone
        serial = _norm_serial(d.get("serial"))
        key = device_key(d)
        if not key:
            continue
        adb_entry = adb_by_serial.get(serial) and next(
            (a for a in adb_devs if _norm_serial(a.get("serial")) == serial), None
        )
        if serial and serial in adb_by_serial:
            claimed_adb.add(serial)
        rows.append(
            {
                "key": key,
                "label": _usb_label(d, adb_by_serial),
                "transports": _usb_transports(d, set(adb_by_serial)),
                "usb": d,
                "adb": adb_entry,
            }
        )
    for a in adb_devs:
        if not isinstance(a, dict):
            continue
        s = _norm_serial(a.get("serial"))
        if not s or s in claimed_adb:
            continue
        rows.append(
            {
                "key": f"adb:{s}",
                "label": f"{s} [{a.get('state', '')}]",
                "transports": ["ADB"],
                "usb": None,
                "adb": a,
            }
        )
    return rows


def candidates_for_modes(modes):
    """Subset of :func:`list_devices` whose transports intersect ``modes``."""
    want = set(modes or [])
    return [r for r in list_devices() if want & set(r.get("transports", []))]


def resolve_usb_target(key):
    """Fresh ``vid:pid@bus:addr`` target string for a stored device ``key``.

    Returns None when the device is not currently on USB (e.g. an ADB-only
    row, or the phone re-enumerated away). ADB-keyed rows resolve via the
    merged USB dict when the same phone exposes both.
    """
    if not key:
        return None
    from . import bridge as _bridge

    try:
        usb_devs = _bridge.detect_all()
    except Exception:
        return None
    if not isinstance(usb_devs, list):
        return None
    for d in usb_devs:
        if isinstance(d, dict) and device_key(d) == key:
            try:
                return f"{int(d['vid']):04x}:{int(d['pid']):04x}@{d['bus']}:{d['address']}"
            except (KeyError, TypeError, ValueError):
                return None
    return None


def find_usb(key=None):
    """First USB dict matching ``key`` (ambient scope key when None)."""
    from . import bridge as _bridge

    key = key if key is not None else current_key()
    try:
        devs = _bridge.detect_all()
    except _bridge.BridgeError:
        return None
    if not isinstance(devs, list):
        return None
    for d in devs:
        if isinstance(d, dict) and (key is None or match_key(d, key)):
            return d
    return None
