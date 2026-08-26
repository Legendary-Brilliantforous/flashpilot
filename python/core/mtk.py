"""MediaTek (MTK) detection for Samsung A05/A06-class phones.

The Samsung A05/A06 family is powered by MediaTek SoCs. Those boot a
proprietary MediaTek download agent that open-source Odin tools cannot talk
to, but they also expose the classic MediaTek low-level USB modes:

  BROM      (PID 0x2000)  - the first code that runs; held state
  Preloader (PID 0x0003)  - first bootloader stage, waits for the DA
  DA        (PID 0x0004)  - Download Agent running (flashing active)

The rust bridge's `mtk-detect` command enumerates MediaTek USB devices
(VID 0x0e8d), classifies the boot stage, and - for a held BootROM or the
preloader - runs the real MediaTek sync handshake (echo of a0 0a 50 05) to
report the SoC, the security config and the device identity. This module wraps
that for the Python flows and maps MediaTek hw codes to chip names.
"""

import json

from . import bridge

MTK_VID = 0x0E8D

# MediaTek hw code -> SoC / marketing name (mtkclient hw codes).
CHIP_NAMES = {
    0x0708: "MT6762 (Helio P22 / G25 family)",
    0x0709: "MT6761 (Helio A22)",
    0x0766: "MT6765 (Helio G25 / G35 / G36 / G37)",
    0x0769: "MT6768/MT6769 (Helio G80 / G85 - used in Galaxy A05/A06)",
    0x0783: "MT6763 (Helio P23)",
    0x0786: "MT6781 (Helio G96)",
    0x0788: "MT6785 (Helio G90T)",
    0x0685: "MT6853 (Dimensity 720)",
    0x0687: "MT6877 (Dimensity 1200)",
    0x0818: "MT6873 (Dimensity 1000)",
    0x0833: "MT6833 (Dimensity 700 / 810)",
}

BOOT_STAGE = {
    "brom": ("MediaTek BootROM (held state)",
             "the very first code that runs - the state used for low-level "
             "chip unlock / preloader / partition reads via mtkclient"),
    "preloader": ("MediaTek Preloader",
                  "first bootloader stage; waits for the Download Agent handshake"),
    "da": ("MediaTek Download Agent (DA)",
           "the flashing stage is already running"),
    "mtk-adb": ("MediaTek ADB composite",
                "phone is booted to Android, not in a low-level mode"),
}

# pid -> boot stage (for USB-detect entries that lack mtk-detect data).
_PID_STAGE = {
    0x2000: "brom",
    0x0003: "preloader",
    0x0004: "da",
    0x1004: "da",
    0x0a0a: "mtk-adb",
    0x201C: "mtk-adb",
    0x2010: "mtk-adb",
    0x2008: "mtk-adb",
}


def pid_stage(pid):
    return _PID_STAGE.get(pid, "other")


def find_mtk():
    """Return the list of MediaTek USB device dicts (VID 0x0e8d).

    Scans the UNFILTERED bus list — bridge.detect_usb() is Samsung-filtered
    (04e8) and would never yield MTK devices, which is why BROM/preloader
    polling used to see '0 devices' even with a phone in BROM mode."""
    try:
        return [d for d in bridge.detect_all() if d.get("vid") == MTK_VID]
    except bridge.BridgeError:
        return []


def detect_mtk():
    """Run the bridge's mtk-detect command; returns a list of dicts.

    Returns [] when the bridge is too old to know the command or no MediaTek
    device is present.
    """
    try:
        return json.loads(bridge._run(["mtk-detect"]))
    except bridge.BridgeError:
        return []


def chip_name(hw_code):
    return CHIP_NAMES.get(hw_code, f"MediaTek SoC (hw code 0x{hw_code:04X})")


def stage_label(stage):
    name, note = BOOT_STAGE.get(stage, (stage.title(), ""))
    return name, note
