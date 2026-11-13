"""SPD/UNISOC "Enable ADB (boot patch)" — honest refusal, safe import.

The Qt button imports :func:`enable_adb_via_boot_patch` from this module.
The module did not exist, so every press died with ImportError and the user
saw a generic error. This module exists so the import is always safe and the
GUI reports a truthful, actionable message instead of a fake success.

Why the one-shot boot-ramdisk patch is refused
----------------------------------------------
1. The only sanctioned dump path for ``boot`` is ``spd-readback``, and it
   ends with a BSL normal reset (``src/spd.rs``): the phone leaves
   BROM/download mode. The same invocation therefore cannot flash the
   patched image back — a second write needs the user to re-enter download
   mode first, which this button does not model.
2. On AVB-enforcing Android builds, changing the boot ramdisk invalidates
   the verified-boot hash. Flashing it without a matching vbmeta/AVB update
   can leave the phone unbootable, and the SPD path has no AVB stage today.

Nothing is written by this module: it raises before touching the device.

Safe alternatives
-----------------
* On-phone: Settings ▸ Developer options ▸ USB debugging (or the Transsion
  secret code ``*#*#49#*#*`` on UMS9230-class devices), then reconnect and
  use the normal ADB tools.
* Factory-reset / FRP-locked phone: use the SPD FRP action (or the MTK/ADB
  flow for the matching chip), then enable ADB from the phone's settings.
* Offline image work: patch and flash ``boot`` yourself with FDL1/FDL2
  (review the avb/vbmeta pairing first), then re-enter download mode for
  the write.
"""

from __future__ import annotations

#: False until a safe one-shot read→patch→flash path exists. The Qt page
#: reads this to refuse the button up front, before asking for FDL files.
SUPPORTED = False

UNAVAILABLE_REASON = (
    "SPD ADB enable via boot.img patch cannot be done in one step: "
    "dumping 'boot' (spd-readback) resets the phone out of download mode, "
    "and a patched ramdisk breaks AVB on verified-boot devices. Nothing "
    "was written to the phone. Use the on-phone route (Settings > "
    "Developer options > USB debugging, or the Transsion secret code "
    "*#*#49#*#*), then reconnect and use the ADB tools; or clear FRP with "
    "the SPD FRP action first. Offline, patch/flash boot yourself with "
    "FDL1/FDL2 (including the vbmeta pairing) and re-enter download mode "
    "for the write."
)


def enable_adb_via_boot_patch(bridge, target, fdl1, fdl1_addr, fdl2=None,
                              a2=None, part="boot", backup_dir=None,
                              log=None, **kwargs):
    """Refuse the one-shot SPD boot patch with an explanation (see module doc).

    Signature mirrors the Qt call site so the import path and keyword
    arguments are stable. ``**kwargs`` tolerates future callers; no argument
    combination makes this write to the device.
    """
    if callable(log):
        try:
            log("[spd-adb] boot-patch ADB enable is not available as a "
                "one-shot operation; nothing was read or written")
        except Exception:
            pass
    raise NotImplementedError(UNAVAILABLE_REASON)
