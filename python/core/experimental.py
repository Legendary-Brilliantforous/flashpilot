"""Experimental feature gating — tag high-intensity operations as EXPERIMENTAL.

All high-intensity features (Knox bypass, Apple iCloud, QCN/IMEI write,
eMMC/UFS raw access, etc.) ship in 1.2.1-beta as EXPERIMENTAL behind an
explicit educational/legal ack. After proven working on HIL, the same code
flips to stable by removing the EXPR tag — no fork.

Storage: QSettings("FlashPilot","FlashingTool") per-feature per-version ack
plus file-based audit log. Mirrors beta gate pattern: qt_app.py:5435
"""

import json
import os
import time
from typing import Dict, Tuple

from . import APP_VERSION

# (title, warning_text, requires_backup)
EXPERIMENTAL_FEATURES: Dict[str, Tuple[str, str, bool]] = {
    "knox_bypass": (
        "Samsung Knox Bypass (EXPERIMENTAL)",
        "Bypasses Knox warranty / KG / RMM checks. This may PERMANENTLY TRIP "
        "the Knox eFuse (0x1) and void warranty. Knox trip is IRREVERSIBLE — "
        "Samsung Pay / Secure Folder / Knox attestation will never return.\n\n"
        "Educational purpose only. You certify you OWN this device and accept "
        "all brick/warranty risk. There is NO undo after eFuse blow.\n\n"
        "A pre-flash backup (param/efs) will be taken first. Continue?",
    ),
    "knox_warranty": (
        "Samsung Knox Warranty Detection (EXPERIMENTAL)",
        "Reads Knox counter / warranty bit via Odin/AT. Read-only but the "
        "subsequent bypass is EXPERIMENTAL and irreversible.\n\n"
        "Educational purpose only. Continue?",
    ),
    "apple_icloud_remove": (
        "Apple iCloud Remove (EXPERIMENTAL)",
        "Removes Apple Activation Lock / iCloud account via DFU/ramdisk. "
        "Activation Lock is a theft-deterrent. Bypass on a device you do NOT "
        "own or without proof of ownership may be ILLEGAL in your jurisdiction "
        "and may violate Apple's terms.\n\n"
        "Educational purpose only. You certify you OWN this device and have "
        "legal proof of ownership. Continue?",
    ),
    "apple_icloud_add": (
        "Apple iCloud Add / Setup (EXPERIMENTAL)",
        "Adds or re-adds iCloud/Apple ID association via usbmuxd/activation. "
        "Use only on devices you own with legal entitlement.\n\n"
        "Educational purpose only. Continue?",
    ),
    "qcn_imei_repair": (
        "Qualcomm QCN / IMEI Repair (EXPERIMENTAL)",
        "Rewrites modem NV — IMEI (NV 550/682), MEID, RF calibration, sec.dat. "
        "Writing a FOREIGN IMEI or to a device you do NOT own may be ILLEGAL "
        "(e.g., US 18 USC 1029, UK Mobile Telephones Act 2002, India) and can "
        "permanently kill cellular (no service / emergency only) or cause "
        "carrier blacklist.\n\n"
        "Educational purpose only. You certify you OWN this device and will "
        "only RESTORE an IMEI you previously backed up FROM THIS SAME DEVICE.\n\n"
        "A modemst1/2 + EFS backup will be taken first. Continue?",
    ),
    "qcn_backup": (
        "Qualcomm QCN Backup (EXPERIMENTAL)",
        "Dumps modem partitions (modemst1/2, fsg, fsc) + EFS via Firehose/DIAG "
        "for later restore. Keep the backup safe — it contains device-specific "
        "calibration.\n\n"
        "Educational purpose only. Continue?",
    ),
    "emmc_ufs_raw": (
        "eMMC/UFS Deep Tools — Raw NAND (EXPERIMENTAL)",
        "Low-level chip programming: raw NAND access, bad-block management, "
        "RPMB, UFS health. A wrong offset or bad-block mishandle will BRICK "
        "the device beyond software recovery.\n\n"
        "Educational purpose only. You certify you understand raw flash "
        "programming and accept brick risk. Continue?",
    ),
    "fastboot_pixel": (
        "Google Pixel Fastboot (EXPERIMENTAL)",
        "Fastboot flashing for Pixel devices — bootloader unlock, factory "
        "images, slot A/B, vbmeta/AVB. Unlock WIPES ALL DATA and may void "
        "warranty.\n\n"
        "Educational purpose only. Continue?",
    ),
    "pac_flash": (
        "SPD/UNISOC PAC Flash (EXPERIMENTAL)",
        "Flashes UNISOC PAC archives via BSL. A mismatched PAC will brick "
        "the device. PAC repack writes full partition tables.\n\n"
        "Educational purpose only. Continue?",
    ),
    "mtk_sla_bypass": (
        "MTK Secure Boot Bypass / SLA (EXPERIMENTAL)",
        "Uses SLA key auth + kamakiri2 BROM exploit to bypass secure boot. "
        "May be device-specific and can brick if DA is wrong.\n\n"
        "Educational purpose only. Continue?",
    ),
    "imei_repair_mtk": (
        "MediaTek IMEI Repair (EXPERIMENTAL)",
        "Rewrites the modem NVRAM IMEI record (MP0B001_*). Restore ONLY the "
        "IMEI you previously backed up from THIS SAME device. Writing a foreign "
        "IMEI may be ILLEGAL and can kill cellular or cause carrier blacklist.\n\n"
        "Educational purpose only. You certify you OWN this device. Continue?",
    ),
    "imei_change_mtk": (
        "MediaTek IMEI Change (EXPERIMENTAL, DOUBLE-GATED)",
        "Changes the IMEI to a new value. On a device you do not own, or a "
        "value not backed up from this device, this is ILLEGAL in most "
        "jurisdictions (US 18 USC 1029, UK, India) and can permanently kill "
        "cellular service.\n\n"
        "Educational purpose only. You certify ownership and legal entitlement. Continue?",
    ),
    "imei_repair_spd": (
        "SPD/UNISOC IMEI Repair (EXPERIMENTAL)",
        "Restores the modem-NV IMEI via BSL. Restore ONLY a backed-up IMEI "
        "from THIS SAME device.\n\n"
        "Educational purpose only. You certify you OWN this device. Continue?",
    ),
    "imei_change_spd": (
        "SPD/UNISOC IMEI Change (EXPERIMENTAL, DOUBLE-GATED)",
        "Changes the IMEI to a new value via BSL. On a device you do not own, "
        "or a value not backed up from this device, this is ILLEGAL and can "
        "permanently kill cellular.\n\n"
        "Educational purpose only. You certify ownership and legal entitlement. Continue?",
    ),
}

# Generic fallback for any experimental flow not explicitly listed
_GENERIC_WARN = (
    "Experimental Operation",
    "This is an EXPERIMENTAL feature. It may brick the device, trip "
    "security counters, or be restricted by law.\n\n"
    "Educational purpose only. You certify you own this device and accept "
    "all risk. Continue?",
)


def _settings():
    try:
        from PyQt6.QtCore import QSettings

        return QSettings("FlashPilot", "FlashingTool")
    except Exception:
        return None


def _ack_key(feature: str) -> str:
    return f"experimental_ack_{feature}_{APP_VERSION}"


def is_acknowledged(feature: str) -> bool:
    s = _settings()
    if s is None:
        return False
    return bool(s.value(_ack_key(feature), False, type=bool))


def set_acknowledged(feature: str, value: bool = True) -> None:
    s = _settings()
    if s is not None:
        s.setValue(_ack_key(feature), bool(value))


def get_warning(feature: str) -> Tuple[str, str]:
    return EXPERIMENTAL_FEATURES.get(feature, _GENERIC_WARN)[:2]


def feature_title(feature: str) -> str:
    return EXPERIMENTAL_FEATURES.get(feature, _GENERIC_WARN)[0]


def audit_log_path() -> str:
    # XDG state: ~/.local/share/flashpilot/audit.jsonl
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    d = os.path.join(base, "flashpilot")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return os.path.join(d, "audit.jsonl")


def audit_log(feature: str, action: str, detail: str = "") -> None:
    path = audit_log_path()
    entry = {
        "ts": time.time(),
        "ts_human": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "version": APP_VERSION,
        "feature": feature,
        "action": action,
        "detail": detail,
        "experimental": True,
    }
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def check_gate(feature: str, log_fn=None) -> bool:
    """Legacy persisted-ack gate (kept for API compat only).

    Returns True if a per-version ack was stored via set_acknowledged().
    Audit is always written. No in-tree flow uses this anymore — every
    experimental flow goes through check_gate_strict(), so a stored ack
    can never auto-pass a high-risk operation. Kept so external/headless
    scripts importing it don't break.
    """
    if is_acknowledged(feature):
        audit_log(feature, "gate_pass")
        return True
    if log_fn:
        try:
            log_fn(f"[EXPERIMENTAL] blocked: {feature} requires ack — see dialog")
        except Exception:
            pass
    audit_log(feature, "gate_blocked")
    return False


def check_gate_strict(feature: str, per_run_acked: bool = False, log_fn=None) -> bool:
    """Strict per-run gate for high-risk operations (Q2-B).

    A persisted ack NEVER passes this gate — the caller must supply
    per_run_acked=True from the current run's ownership checkbox (GUI) or
    an explicit env/ctx flag (headless). Audit is always written, separately
    from the pass/block decision.
    """
    if per_run_acked:
        audit_log(feature, "gate_strict_pass")
        return True
    if log_fn:
        try:
            log_fn(f"[EXPERIMENTAL] blocked: {feature} requires a per-run ownership ack")
        except Exception:
            pass
    audit_log(feature, "gate_strict_blocked")
    return False


def per_run_acked_from_ctx(ctx=None) -> bool:
    """Read an explicit per-run ack from ctx or env (headless runs).

    Accepted: ctx['experimental_ack'] is True, or env EXPERIMENTAL_ACK=1.
    Persisted QSettings ack is deliberately NOT consulted here.
    """
    try:
        if isinstance(ctx, dict) and ctx.get("experimental_ack") is True:
            return True
    except Exception:
        pass
    try:
        import os as _os
        if _os.environ.get("EXPERIMENTAL_ACK", "").strip().lower() in ("1", "true", "yes", "on"):
            return True
    except Exception:
        pass
    return False


# Action/flow key -> experimental feature id. Single source: the GUI
# drill-down router (devices._dispatch) and the flow runners resolve through
# this instead of carrying private copies that can drift.
FLOW_FEATURE_IDS: Dict[str, str] = {
    "apple_icloud_remove": "apple_icloud_remove",
    "apple_icloud_add": "apple_icloud_add",
    "knox_check": "knox_warranty",
    "knox_bypass": "knox_bypass",
    "qcn_backup": "qcn_backup",
    "qcn_imei_repair": "qcn_imei_repair",
    "emmc_health": "emmc_ufs_raw",
    "health": "qcn_backup",  # health uses generic health gate still EXPERIMENTAL-ish
    "pac_extract": "pac_flash",
    "pac_pack": "pac_flash",
    "pixel_fastboot": "fastboot_pixel",
}

# How long a GUI checkbox confirm authorizes a run. Bounds the blast radius
# of a confirm: even if token bookkeeping races, a stale confirm cannot
# authorize a run started much later.
ACK_TOKEN_TTL = 600.0


def token_note(store: dict, feature: str, now: float = None) -> dict:
    """Record one GUI ownership-checkbox confirm (append-only, counted).

    Counted, not boolean: two confirms authorize two runs, so rapid
    sequential confirms on parallel devices can never starve each other.
    Returns the store for convenience.
    """
    if not isinstance(store, dict):
        return {}
    try:
        store.setdefault(feature, []).append(
            time.monotonic() if now is None else now)
    except Exception:
        pass
    return store


def token_consume(store: dict, feature: str, now: float = None) -> bool:
    """Consume one fresh confirm token for `feature`, if any.

    Drops expired tokens (>ACK_TOKEN_TTL old) instead of honouring them, so
    a confirm can never authorize a run started much later. Returns True
    exactly when a fresh token existed (single-use: it is removed).
    """
    if not isinstance(store, dict) or not feature:
        return False
    try:
        ts = now if now is not None else time.monotonic()
        kept = [t for t in store.get(feature, []) if ts - t <= ACK_TOKEN_TTL]
        if not kept:
            store.pop(feature, None)
            return False
        kept.pop(0)
        if kept:
            store[feature] = kept
        else:
            store.pop(feature, None)
        return True
    except Exception:
        return False
