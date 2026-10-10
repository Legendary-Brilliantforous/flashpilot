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


def _merged_row_to_legacy(row):
    """Adapt a Rust `detect-merged` DeviceRow to the legacy list_devices()
    row shape ({key, label, transports, usb, adb}) so GUI consumers are
    unchanged while filtering/merge runs in the Rust core."""
    adb_state = row.get("adb_state")
    adb = None
    if row.get("is_adb") or adb_state:
        adb = {
            "serial": row.get("serial") or "",
            "state": adb_state or "device",
            "extra": "",
        }
    usb = None
    if not row.get("is_adb"):
        usb = {
            "vid": row.get("vid", 0),
            "pid": row.get("pid", 0),
            "bus": row.get("bus", 0),
            "address": row.get("address", 0),
            "serial": row.get("serial"),
            "product": row.get("usb_product"),
            "manufacturer": row.get("usb_manufacturer"),
        }
    return {
        "key": row.get("key", ""),
        "label": row.get("label", ""),
        "transports": row.get("transports", []),
        "usb": usb,
        "adb": adb,
    }


def list_devices():
    """Unified device list across USB + ADB.

    Filtering/merge now runs in the Rust core (`detect-merged`): one atomic,
    deterministic call instead of per-poll Python re-computation. Rows are
    adapted back to the legacy shape so GUI consumers are unchanged. On any
    bridge failure the legacy Python path below remains the rollback.
    """
    from . import bridge as _bridge

    # Rust-only: filtering/merge/classification live in the bridge
    # (detect-merged). No Python fallback - a bridge failure propagates so
    # callers surface it instead of silently degrading.
    merged = _bridge.list_merged()
    return [
        _merged_row_to_legacy(r) for r in merged
        if isinstance(r, dict) and r.get("key")
    ]


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
