"""Shared, Qt-light helpers used by both :mod:`python.gui.qt_app` and the
:mod:`python.gui.widgets` package. Kept import-cycle free.
"""
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from .theme import C


def _mode_chip(mode):
    if not mode:
        return "NOT CONNECTED", C["card"], C["mute"], C["mute"]
    m = mode.upper()
    if "RECOVERY" in m:
        return "RECOVERY", C["warn_dim"], C["warn"], C["warn"]
    if "ADB" in m:
        return "ADB", C["chip_blue"], C["chip_text"], C["accent"]
    if "BROM" in m:
        return "BROM", C["err_dim"], C["err"], C["err"]
    if "MTK" in m or "MEDIATEK" in m:
        # "MEDIATEK" does not contain the substring "MTK" — a generic
        # MTK-mode label ("MEDIATEK MODE (VID 0x0E8D PID 0x2008)") used to
        # fall all the way through to OTHER.
        return "MTK", C["warn_dim"], C["warn"], C["warn"]
    if "EDL" in m:
        # Most specific first: "EDL MODE (Qualcomm Emergency Download)"
        # contains the substring "Download" and used to fall through to
        # the DOWNLOAD chip (a Samsung download-mode label).
        return "EDL", C["err_dim"], C["err"], C["err"]
    if "DIAG" in m:
        return "DIAG/AT", C["warn_dim"], C["warn"], C["warn"]
    if "DOWNLOAD" in m:
        return "DOWNLOAD", C["err_dim"], C["err"], C["err"]
    if "FASTBOOT" in m:
        return "FASTBOOT", C["warn_dim"], C["warn"], C["warn"]
    if "BOOTLOADER" in m:
        return "BOOTLOADER", C["warn_dim"], C["warn"], C["warn"]
    if "QUALCOMM" in m:
        # Whole-bus Qualcomm-normal mode: "QUALCOMM DEVICE (modem / normal
        # mode)" — NOT MTP (the substring "normal" used to fall through to
        # the MTP chip and mislabeled every Qualcomm-normal setup).
        return "QUALCOMM", C["warn_dim"], C["warn"], C["warn"]
    if "TETHERING" in m or "RNDIS" in m:
        return "RNDIS", C["ok_dim"], C["ok"], C["ok"]
    if "STORAGE" in m:
        return "STORAGE", C["ok_dim"], C["ok"], C["ok"]
    if "PTP" in m:
        return "PTP", C["ok_dim"], C["ok"], C["ok"]
    if "NORMAL" in m or "SETUP" in m:
        return "MTP", C["ok_dim"], C["ok"], C["ok"]
    if "MTP" in m:
        return "MTP", C["ok_dim"], C["ok"], C["ok"]
    return "OTHER", C["card"], C["dim"], C["dim"]

# Flows that wipe device data / clear security state. These must always ask
# for confirmation, even when launched from the generic job-flow buttons.
_DESTRUCTIVE_CONFIRM = {
    "factory_reset": (
        "Factory Reset",
        "This WIPES ALL DATA on the connected device:\n\n"
        "  - Apps, accounts, photos, messages, files\n"
        "  - Phone / modem settings are kept\n\n"
        "It tries an ADB /data wipe first, and falls back to a guided "
        "recovery-mode reset if the device is not authorized.\n\n"
        "There is NO undo. Continue?",
    ),
    "mdm_unlock": (
        "MDM Unlock",
        "Removes the mobile-device-management (MDM / device-owner) app and "
        "clears its control over the phone.\n\n"
        "On some builds this also WIPES USER DATA (--wipe_data) so the "
        "device can be set up fresh.\n\n"
        "There is NO undo for the wiped data. Continue?",
    ),
    "mdm_unlock_comprehensive": (
        "MDM Unlock (Comprehensive)",
        "Removes the MDM / device-owner app AND clears related account and "
        "system state across all users.\n\n"
        "This is the deepest MDM removal and may also wipe user data. "
        "Continue?",
    ),
    "mdm_unlock_recovery_wipe": (
        "MDM Unlock (with data wipe)",
        "Removes the MDM / device-owner app and WIPES USER DATA via "
        "recovery so the device can be set up as new.\n\n"
        "There is NO undo for the wiped data. Continue?",
    ),
    "screen_lock_locksettings": (
        "Screen Lock Remove",
        "Removes the screen lock (PIN / password / pattern / face) via the "
        "locksettings command.\n\n"
        "This may log out signed-in accounts and reset security settings. "
        "Continue?",
    ),
    "screen_lock_csc": (
        "Screen Lock Remove (CSC flash)",
        "Removes the screen lock by flashing a combination/CSC build, which "
        "FACTORY RESETS the device and wipes all user data.\n\n"
        "There is NO undo. Continue?",
    ),
    "screen_lock_recovery": (
        "Screen Lock Remove (Recovery)",
        "Removes the screen lock and FRP records from recovery, which "
        "resets security state and may log out accounts.\n\n"
        "Continue?",
    ),
    "screen_lock_comprehensive": (
        "Screen Lock Remove (Comprehensive)",
        "Removes the screen lock / FRP / account lock records by the most "
        "thorough method available on the device.\n\n"
        "This may wipe data and log out accounts. Continue?",
    ),
    "screen_lock_download": (
        "Screen Lock Remove (Combo flash)",
        "Flashes a combination firmware in Download mode to remove the "
        "screen lock - this REPLACES the firmware and wipes the device.\n\n"
        "There is NO undo. Continue?",
    ),
    "adb_frp": (
        "FRP Bypass (ADB)",
        "Clears the Factory Reset Protection flag so the device can be set "
        "up with a new account.\n\n"
        "Continue?",
    ),
    "frp_browser": (
        "FRP Bypass (Browser)",
        "Clears the Factory Reset Protection flag via the browser workaround.\n\n"
        "Continue?",
    ),
    "frp_settings": (
        "FRP Bypass (Settings)",
        "Clears the Factory Reset Protection flag via the settings workaround.\n\n"
        "Continue?",
    ),
}


def _risk_banner(text):
    """A compact red-striped warning bar used near destructive operations
    (flash / wipe). Keeps beginners aware of the consequence before they click."""
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    icon = QLabel("⚠")
    icon.setStyleSheet(f"color: {C['err']}; font-size: 14px; font-weight: 800;")
    icon.setFixedWidth(18)
    lay.addWidget(icon)
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: #ffb4b4; font-size: 11px; font-weight: 600;"
        f" background: rgba(220, 38, 38, 22);"
        f" border: 1px solid rgba(239, 68, 68, 140);"
        f" border-left: 3px solid {C['err']}; border-radius: 6px;"
        f" padding: 6px 10px;"
    )
    lay.addWidget(lbl, 1)
    return w


# ---------------------------------------------------------------------------
# Experimental feature mapping — Knox / QCN / IMEI / eMMC ship as EXPERIMENTAL
# behind a per-run ownership ack (Q2-B gate). Maps a flow key to an
# ``experimental.EXPERIMENTAL_FEATURES`` feature id so the GUI knows to show
# the amber pill + mandatory checkbox before running.
# ---------------------------------------------------------------------------
_EXPERIMENTAL_FLOW_MAP = {
    "knox_check": "knox_warranty",
    "knox_bypass": "knox_bypass",
    "qcn_backup": "qcn_backup",
    "qcn_restore": "qcn_imei_repair",
    "qcn_imei_repair": "qcn_imei_repair",
    "imei_repair_mtk": "imei_repair_mtk",
    "imei_change_mtk": "imei_change_mtk",
    "imei_repair_spd": "imei_repair_spd",
    "imei_change_spd": "imei_change_spd",
    "emmc_health": "emmc_ufs_raw",
    "emmc_raw": "emmc_ufs_raw",
}


def _experimental_banner(text):
    """Amber-striped EXPERIMENTAL warning bar for per-chip experimental
    collapsibles. Mirrors _risk_banner but amber."""
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    icon = QLabel("🧪")
    icon.setStyleSheet(f"color: {C['warn']}; font-size: 14px; font-weight: 800;")
    icon.setFixedWidth(18)
    lay.addWidget(icon)
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: #fde68a; font-size: 11px; font-weight: 600;"
        f" background: rgba(251, 191, 36, 18);"
        f" border: 1px solid rgba(251, 191, 36, 110);"
        f" border-left: 3px solid {C['warn']}; border-radius: 6px;"
        f" padding: 6px 10px;"
    )
    lay.addWidget(lbl, 1)
    return w


__all__ = [
    "_DESTRUCTIVE_CONFIRM",
    "_EXPERIMENTAL_FLOW_MAP",
    "_experimental_banner",
    "_mode_chip",
    "_risk_banner",
]

