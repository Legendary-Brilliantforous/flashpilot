"""FlashPilot core — thin Python shim over the Rust engine.

ALL flows, transports and engines live in Rust (src/flows.rs).
This module provides:
  - The FLOWS/JOBS/MODES registry (mirrors the Rust flow-list)
  - A thin Flow wrapper that delegates execution to bridge.flow_run()
  - The cancellation framework (from flow.py)
  - Helpers the GUI needs
"""

import json
import os
import threading
import time

from . import bridge
from .flow import Flow, Step, FlowCancelled, request_cancel, clear_cancel, cancel_requested  # noqa: F401
from . import flow as _flow_mod
from . import actions as _actions
from . import jobs as _jobs
from . import experimental as _experimental
from . import device_info as _device_info
from . import devices as _devices

__version__ = "1.2.0"
APP_VERSION = __version__

MODES = ["ADB", "MTP", "Download mode", "Samsung BROM", "MTK", "MTK BROM", "FASTBOOT", "EDL", "SPD"]

_registry = None
_registry_lock = threading.Lock()


def _load_registry():
    """Load the flow registry from the Rust bridge (cached)."""
    global _registry
    with _registry_lock:
        if _registry is not None:
            return _registry
        try:
            rows = bridge.flow_list()
            if rows:
                _registry = rows
                return _registry
        except Exception:
            pass
        _registry = []
        return _registry


class _RustFlow:
    """Thin wrapper that delegates execution to the Rust engine.

    GUI integration:
      - The flow-run subprocess is registered in ctx['_proc'] so the STOP
        button kills it (previously cancel only set a Python flag and the
        Rust subprocess kept running to completion).
      - Progress lines from the Rust transcript ('> cmd' steps, OKAY/FAILED,
        'Flashing: <part>') update the progress callback when the runner
        provides one.
      - QR files the flow generates (mdm_qr / frp_qr_provision) are surfaced
        via ctx['mdm_qr_pngs'] so the GUI shows the QR dialog.
    """

    def __init__(self, key, label):
        self.key = key
        self.name = label

    def __call__(self):
        # Factory-compatible: the old FLOWS registry held factories
        # (FLOWS[key]() -> Flow); this wrapper IS the flow instance, so
        # calling it returns itself. Both call shapes keep working:
        #   flow = core.FLOWS[key](); flow.run(ctx, log)
        #   core.flow_for(job, mode, key).run(ctx, log)
        return self

    def run(self, ctx, log):
        """Execute via bridge flow-run. The transcript streams to stdout."""
        key = self.key
        serial = ""
        if isinstance(ctx, dict):
            serial = ctx.get("serial", "") or ""
        import subprocess
        import queue as _queue
        args = ["flow-run", key]
        if serial:
            args.append(serial)
        # Optional provisions the runner supplies: the unlock code (the
        # Motorola token), a partition and a file-path override.
        if isinstance(ctx, dict):
            code = (ctx.get("unlock_code") or ctx.get("code") or "").strip()
            if code:
                args += ["--code", code]
            partition = (ctx.get("partition") or "").strip()
            if partition:
                args += ["--partition", partition]
            file_path = (ctx.get("file") or "").strip()
            if file_path:
                args += ["--file", file_path]
        proc = subprocess.Popen(
            [bridge.BRIDGE] + args,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        if isinstance(ctx, dict):
            ctx["_proc"] = proc
        steps_done = 0
        steps_total = 0
        qr_dir_hint = {"mdm_qr": "mdm_qr", "frp_qr_provision": "frp_qr", "frp_fake_login": "mdm_qr", "frp_fake_login_testdpc": "mdm_qr", "frp_fake_login_adp": "mdm_qr"}.get(key)
        qr_files = []
        # Reader thread + queue: the Rust side can be silent for long
        # stretches (waiting for a device), and a blocking
        # `for line in stdout` loop would never reach the cancel check.
        # The queue poll keeps the loop responsive to the STOP button.
        lines_q = _queue.Queue()

        def _reader():
            try:
                for line in proc.stdout:
                    lines_q.put(line)
            except Exception:
                pass
            lines_q.put(None)

        threading.Thread(target=_reader, daemon=True).start()
        try:
            while True:
                if cancel_requested():
                    proc.kill()
                    raise FlowCancelled("cancelled by user")
                try:
                    line = lines_q.get(timeout=0.2)
                except _queue.Empty:
                    continue
                if line is None:
                    break
                text = line.rstrip("\n")
                progress_cb = ctx.get("progress_cb") if isinstance(ctx, dict) else None
                if callable(progress_cb):
                    try:
                        if text.lstrip().startswith("> "):
                            steps_total += 1
                        elif "OKAY [" in text or text.strip().startswith("FAILED"):
                            if steps_total:
                                steps_done += 1
                        pct = None
                        if steps_total and steps_done:
                            pct = min(99, int(steps_done * 100 / steps_total))
                        progress_cb(pct)
                    except Exception:
                        pass
                if qr_dir_hint and "qr (svg):" in text:
                    path = text.split("qr (svg):", 1)[1].strip()
                    if path:
                        qr_files.append(path)
                log(text)
            proc.wait()
        finally:
            if proc.poll() is None:
                proc.kill()
            if isinstance(ctx, dict):
                ctx.pop("_proc", None)
        if qr_files and isinstance(ctx, dict):
            ctx["mdm_qr_pngs"] = qr_files
        if proc.returncode != 0 and cancel_requested():
            raise FlowCancelled("cancelled")


# Build FLOWS from the Rust registry
_flow_objs = {}
_flow_objs["odin_preflight"] = _RustFlow("odin_preflight", "Pre-flight validation")
_flow_objs["odin_advanced_flash"] = _RustFlow("odin_advanced_flash", "Advanced flash (AP/BL/CP/CSC + Unofficial)")
_flow_objs["odin_flash_tar"] = _RustFlow("odin_flash_tar", "Flash firmware tar (native)")
_flow_objs["odin_check_tar"] = _RustFlow("odin_check_tar", "Check firmware archive (native)")
_flow_objs["odin_efs_backup"] = _RustFlow("odin_efs_backup", "EFS backup")
_flow_objs["odin_efs_restore"] = _RustFlow("odin_efs_restore", "EFS restore")
_flow_objs["odin_sales_code"] = _RustFlow("odin_sales_code", "Change sales code (CSC)")
_flow_objs["odin_list_devices"] = _RustFlow("odin_list_devices", "List download devices (native)")
_flow_objs["odin_pit_tools"] = _RustFlow("odin_pit_tools", "PIT tools (dump/compare/repartition)")
_flow_objs["odin_flash_partition"] = _RustFlow("odin_flash_partition", "Flash single partition (raw)")
_flow_objs["odin_flash_multi"] = _RustFlow("odin_flash_multi", "Flash multiple partitions (native Odin)")
_flow_objs["odin_send_pit"] = _RustFlow("odin_send_pit", "Send PIT to device (repartition)")
_flow_objs["odin_vbmeta"] = _RustFlow("odin_vbmeta", "VBMETA / AVB signature control")
_flow_objs["drk_repair"] = _RustFlow("drk_repair", "DRK repair (BL+CP reflash guide)")
_flow_objs["reboot_normal"] = _RustFlow("reboot_normal", "reboot normally")
_flow_objs["mtk_auth_flash"] = _RustFlow("mtk_auth_flash", "MTK auth-bypass flash (signed devices)")
_flow_objs["adb_frp"] = _RustFlow("adb_frp", "ADB FRP clear")
_flow_objs["frp_qr_provision"] = _RustFlow("frp_qr_provision", "FRP bypass (QR provisioning, Android 10-14)")
_flow_objs["frp_fake_login"] = _RustFlow("frp_fake_login", "FRP fake-login (own DPC + QR provisioning)")
_flow_objs["frp_fake_login_testdpc"] = _RustFlow("frp_fake_login_testdpc", "FRP fake-login (TestDPC + QR)")
_flow_objs["frp_fake_login_adp"] = _RustFlow("frp_fake_login_adp", "FRP fake-login (Device Policy + QR)")
_flow_objs["frp_alliance"] = _RustFlow("frp_alliance", "FRP bypass (Alliance Shield, Knox admin)")
_flow_objs["frp_browser"] = _RustFlow("frp_browser", "frp bypass (browser)")
_flow_objs["frp_emergency"] = _RustFlow("frp_emergency", "frp bypass (emergency call)")
_flow_objs["frp_settings"] = _RustFlow("frp_settings", "frp bypass (settings)")
_flow_objs["huawei_frp_guide"] = _RustFlow("huawei_frp_guide", "Huawei FRP guide (honest scope)")
_flow_objs["moto_frp_adb"] = _RustFlow("moto_frp_adb", "Motorola FRP reset (ADB)")
_flow_objs["at_method"] = _RustFlow("at_method", "bypass FRP (MTP/AT, commercial)")
_flow_objs["enable_adb"] = _RustFlow("enable_adb", "enable usb debugging (adb) — strong")
_flow_objs["test_mode"] = _RustFlow("test_mode", "Test mode (*#0*#) ADB bypass")
_flow_objs["download_frp"] = _RustFlow("download_frp", "FRP clear (download mode - combo firmware + ADB)")
_flow_objs["odin_enable_adb"] = _RustFlow("odin_enable_adb", "Enable ADB (download mode - combo firmware)")
_flow_objs["mtk_combo_flash"] = _RustFlow("mtk_combo_flash", "flash combination firmware (MediaTek)")
_flow_objs["fastboot_frp"] = _RustFlow("fastboot_frp", "fastboot FRP bypass")
_flow_objs["fastboot_unlock"] = _RustFlow("fastboot_unlock", "fastboot unlock bootloader")
_flow_objs["fastboot_wipe"] = _RustFlow("fastboot_wipe", "fastboot wipe userdata")
_flow_objs["moto_frp_fastboot"] = _RustFlow("moto_frp_fastboot", "Motorola FRP remove (fastboot · CVE-2016-10277)")
_flow_objs["edl_auto"] = _RustFlow("edl_auto", "edl_auto")
_flow_objs["edl_frp"] = _RustFlow("edl_frp", "edl_frp")
_flow_objs["edl_enable_adb"] = _RustFlow("edl_enable_adb", "edl_enable_adb")
_flow_objs["edl_detect"] = _RustFlow("edl_detect", "edl_detect")
_flow_objs["qcom_verify"] = _RustFlow("qcom_verify", "Qualcomm verify-after-write (SHA-256)")
_flow_objs["screen_lock_remove"] = _RustFlow("screen_lock_remove", "screen lock remove (ADB)")
_flow_objs["screen_lock_locksettings"] = _RustFlow("screen_lock_locksettings", "screen lock remove (ADB locksettings, Android 8/9)")
_flow_objs["screen_lock_csc"] = _RustFlow("screen_lock_csc", "screen lock remove (adb or CSC flash - factory reset)")
_flow_objs["screen_lock_recovery"] = _RustFlow("screen_lock_recovery", "screen lock remove (Recovery)")
_flow_objs["screen_lock_comprehensive"] = _RustFlow("screen_lock_comprehensive", "screen lock remove (Comprehensive)")
_flow_objs["screen_lock_download"] = _RustFlow("screen_lock_download", "Remove Screen Lock (download mode - combo firmware + ADB)")
_flow_objs["mtk_recovery_reset"] = _RustFlow("mtk_recovery_reset", "recovery factory reset (MediaTek)")
_flow_objs["fastboot_erase"] = _RustFlow("fastboot_erase", "fastboot erase partition")
_flow_objs["screen_lock_edl"] = _RustFlow("screen_lock_edl", "screen lock remove (EDL)")
_flow_objs["adb_info"] = _RustFlow("adb_info", "adb read info")
_flow_objs["kg_state_check"] = _RustFlow("kg_state_check", "KG state check")
_flow_objs["oem_unlock_guide"] = _RustFlow("oem_unlock_guide", "bootloader unlock guide (checks + steps)")
_flow_objs["recovery"] = _RustFlow("recovery", "recovery mode")
_flow_objs["at_info"] = _RustFlow("at_info", "at read info (MTP/AT)")
_flow_objs["download_mode_info"] = _RustFlow("download_mode_info", "download mode info (real Odin read)")
_flow_objs["mtk_download_info"] = _RustFlow("mtk_download_info", "MediaTek download info")
_flow_objs["mtk_brom_info"] = _RustFlow("mtk_brom_info", "MediaTek BROM / preloader detection")
_flow_objs["mtk_brom_backup"] = _RustFlow("mtk_brom_backup", "MTK BROM read & backup (bootloader + security area)")
_flow_objs["mtk_crash_brom"] = _RustFlow("mtk_crash_brom", "MTK crash preloader into BROM")
_flow_objs["mtk_verify"] = _RustFlow("mtk_verify", "MTK verify-after-write (SHA-256)")
_flow_objs["fastboot_devices"] = _RustFlow("fastboot_devices", "fastboot list devices")
_flow_objs["fastboot_getvar"] = _RustFlow("fastboot_getvar", "fastboot getvar all")
_flow_objs["fastboot"] = _RustFlow("fastboot", "fastboot device overview")
_flow_objs["qcom_detect_info"] = _RustFlow("qcom_detect_info", "Qualcomm detect + info (read-only)")
_flow_objs["spd_detect_info"] = _RustFlow("spd_detect_info", "SPD detect + info (read-only)")
_flow_objs["detect"] = _RustFlow("detect", "detect")
_flow_objs["reboot_recovery"] = _RustFlow("reboot_recovery", "reboot to recovery")
_flow_objs["reboot_download"] = _RustFlow("reboot_download", "reboot to download mode")
_flow_objs["reboot_edl"] = _RustFlow("reboot_edl", "reboot to EDL (Qualcomm)")
_flow_objs["reboot_bootloader"] = _RustFlow("reboot_bootloader", "reboot to fastboot/bootloader")
_flow_objs["fastboot_reboot"] = _RustFlow("fastboot_reboot", "fastboot reboot")
_flow_objs["fastboot_reboot_bootloader"] = _RustFlow("fastboot_reboot_bootloader", "fastboot reboot to bootloader")
_flow_objs["fastboot_recovery"] = _RustFlow("fastboot_recovery", "fastboot reboot to recovery")
_flow_objs["fastboot_continue"] = _RustFlow("fastboot_continue", "fastboot continue boot")
_flow_objs["repair_settings"] = _RustFlow("repair_settings", "repair settings app crash (A14 / A145P etc.)")
_flow_objs["fix_adb_auth"] = _RustFlow("fix_adb_auth", "Fix ADB authorization (unauthorized, no dialog)")
_flow_objs["carrier_lock_status"] = _RustFlow("carrier_lock_status", "carrier lock status (read-only)")
_flow_objs["carrier_lock_mtk"] = _RustFlow("carrier_lock_mtk", "MTK nvram simlock read/backup/analyze (A05/A06)")
_flow_objs["mdm_diagnostics"] = _RustFlow("mdm_diagnostics", "mdm diagnostics / analysis")
_flow_objs["mdm_unlock"] = _RustFlow("mdm_unlock", "mdm / device-owner unlock - smart")
_flow_objs["mdm_unlock_comprehensive"] = _RustFlow("mdm_unlock_comprehensive", "mdm / device-owner unlock - comprehensive / deep")
_flow_objs["mdm_unlock_recovery"] = _RustFlow("mdm_unlock_recovery", "mdm / device-owner unlock - recovery (no wipe)")
_flow_objs["mdm_unlock_recovery_wipe"] = _RustFlow("mdm_unlock_recovery_wipe", "mdm / device-owner unlock - recovery (with user-data wipe)")
_flow_objs["mdm_qr"] = _RustFlow("mdm_qr", "mdm qr code generator (Android Enterprise)")
_flow_objs["knox_check"] = _RustFlow("knox_check", "Knox warranty check (EXPERIMENTAL)")
_flow_objs["kg_remove"] = _RustFlow("kg_remove", "KG remove (patch vbmeta)")
_flow_objs["knox_bypass"] = _RustFlow("knox_bypass", "Knox bypass (EXPERIMENTAL — irreversible)")
_flow_objs["qcn_backup"] = _RustFlow("qcn_backup", "QCN backup (EXPERIMENTAL)")
_flow_objs["qcn_nv_browser"] = _RustFlow("qcn_nv_browser", "QCN NV browser (backup inspector)")
_flow_objs["qcn_efs_explorer"] = _RustFlow("qcn_efs_explorer", "QCN EFS explorer (backup inspector)")
_flow_objs["qcn_restore"] = _RustFlow("qcn_restore", "QCN restore (EXPERIMENTAL)")
_flow_objs["qcn_imei_repair"] = _RustFlow("qcn_imei_repair", "QCN IMEI repair (EXPERIMENTAL — restore-only)")
_flow_objs["imei_repair_mtk"] = _RustFlow("imei_repair_mtk", "MTK IMEI repair (EXPERIMENTAL — restore-only)")
_flow_objs["imei_repair_spd"] = _RustFlow("imei_repair_spd", "SPD IMEI repair (EXPERIMENTAL — restore-only)")
_flow_objs["imei_change_spd"] = _RustFlow("imei_change_spd", "SPD IMEI change (EXPERIMENTAL — double-gated)")
_flow_objs["imei_change_mtk"] = _RustFlow("imei_change_mtk", "MTK IMEI change (EXPERIMENTAL — double-gated)")
_flow_objs["emmc_health"] = _RustFlow("emmc_health", "eMMC/UFS health (read-only)")
_flow_objs["emmc_raw"] = _RustFlow("emmc_raw", "eMMC/UFS raw NAND (EXPERIMENTAL — brick risk)")
_flow_objs["factory_reset"] = _RustFlow("factory_reset", "factory reset")
_flow_objs["setup_wizard"] = _RustFlow("setup_wizard", "Setup Wizard ADB bypass")
_flow_objs["fastboot_flash"] = _RustFlow("fastboot_flash", "fastboot flash partition")
_flow_objs["fastboot_format"] = _RustFlow("fastboot_format", "fastboot format partition")
_flow_objs["fastboot_lock"] = _RustFlow("fastboot_lock", "fastboot relock bootloader")
_flow_objs["fastboot_set_active"] = _RustFlow("fastboot_set_active", "fastboot set active slot")
_flow_objs["fastboot_oem"] = _RustFlow("fastboot_oem", "fastboot oem command")
_flow_objs["apple_info"] = _RustFlow("apple_info", "Apple info (EXPERIMENTAL — read-only)")
_flow_objs["apple_passcode_guide"] = _RustFlow("apple_passcode_guide", "iPhone passcode scope guide (honest)")
_flow_objs["apple_icloud_remove"] = _RustFlow("apple_icloud_remove", "Apple iCloud Remove (EXPERIMENTAL — edu only)")
_flow_objs["apple_icloud_add"] = _RustFlow("apple_icloud_add", "Apple iCloud Add (EXPERIMENTAL — edu only)")
_flow_objs["ofp_extract"] = _RustFlow("ofp_extract", "Oppo OFP prepare (extract / guidance)")
_flow_objs["pac_extract"] = _RustFlow("pac_extract", "SPD PAC extract (file to folder)")
_flow_objs["pac_pack"] = _RustFlow("pac_pack", "SPD PAC pack (folder to file)")

FLOWS = _flow_objs

JOBS = {
    "Flash Firmware": {
        "ADB": ["odin_preflight", "odin_advanced_flash", "odin_flash_tar", "odin_check_tar", "odin_efs_backup", "odin_efs_restore", "odin_sales_code", "odin_flash_tar", "odin_check_tar", "odin_sales_code", "odin_efs_backup", "odin_efs_restore"],
        "MTP": ["odin_preflight", "odin_advanced_flash", "odin_flash_tar", "odin_check_tar", "odin_list_devices", "odin_list_devices"],
        "Download mode": ["odin_preflight", "odin_advanced_flash", "odin_flash_tar", "odin_check_tar", "odin_list_devices", "odin_pit_tools", "odin_flash_partition", "odin_flash_multi", "odin_send_pit", "odin_vbmeta", "drk_repair", "reboot_normal", "drk_repair", "odin_pit_tools", "odin_flash_partition", "odin_flash_multi", "odin_send_pit", "odin_preflight"],
        "Samsung BROM": ["odin_preflight", "odin_advanced_flash", "odin_flash_tar", "odin_check_tar", "odin_list_devices", "odin_pit_tools", "odin_flash_partition", "odin_flash_multi", "odin_send_pit", "odin_vbmeta"],
        "MTK": ["mtk_auth_flash", "mtk_auth_flash"],
        "MTK BROM": ["mtk_auth_flash"],
        "FASTBOOT": ["fastboot_flash", "fastboot_format", "fastboot_lock", "fastboot_set_active", "fastboot_oem", "fastboot_set_active", "fastboot_lock"],
        "SPD": ["ofp_extract", "pac_extract", "pac_pack", "pac_extract", "pac_pack"],
    },
    "Remove FRP": {
        "ADB": ["adb_frp", "frp_qr_provision", "frp_fake_login", "frp_fake_login_testdpc", "frp_fake_login_adp", "frp_alliance", "frp_browser", "frp_emergency", "frp_settings", "huawei_frp_guide", "moto_frp_adb", "factory_reset", "setup_wizard", "moto_frp_adb", "frp_browser", "frp_emergency", "frp_settings", "huawei_frp_guide", "frp_qr_provision", "frp_alliance"],
        "MTP": ["at_method", "enable_adb", "test_mode", "test_mode"],
        "Download mode": ["download_frp", "odin_enable_adb", "download_frp", "odin_enable_adb"],
        "Samsung BROM": ["download_frp", "odin_enable_adb"],
        "MTK": ["mtk_combo_flash", "mtk_combo_flash"],
        "FASTBOOT": ["fastboot_frp", "fastboot_unlock", "fastboot_wipe", "moto_frp_fastboot"],
        "EDL": ["edl_auto", "edl_frp", "edl_enable_adb", "edl_detect", "qcom_verify", "edl_auto", "edl_frp", "edl_enable_adb"],
    },
    "Remove Screen Lock": {
        "ADB": ["screen_lock_remove", "screen_lock_locksettings", "screen_lock_csc", "screen_lock_recovery", "screen_lock_comprehensive", "screen_lock_locksettings", "screen_lock_csc", "screen_lock_comprehensive", "screen_lock_recovery"],
        "MTP": ["enable_adb", "test_mode"],
        "Download mode": ["screen_lock_download", "screen_lock_csc", "odin_enable_adb", "screen_lock_download"],
        "Samsung BROM": ["screen_lock_download", "screen_lock_csc", "odin_enable_adb"],
        "MTK": ["mtk_recovery_reset", "mtk_combo_flash", "mtk_recovery_reset"],
        "FASTBOOT": ["fastboot_wipe", "fastboot_erase", "fastboot_frp"],
        "EDL": ["screen_lock_edl", "screen_lock_edl"],
    },
    "Read Device Info": {
        "ADB": ["adb_info", "kg_state_check", "oem_unlock_guide", "recovery", "apple_info", "apple_passcode_guide", "apple_icloud_remove", "apple_icloud_add", "recovery", "adb_info", "kg_state_check", "oem_unlock_guide", "apple_info", "apple_passcode_guide"],
        "MTP": ["at_info", "enable_adb", "test_mode", "at_info"],
        "Download mode": ["download_mode_info", "kg_state_check", "download_mode_info"],
        "Samsung BROM": ["download_mode_info"],
        "MTK": ["mtk_download_info", "mtk_brom_info", "mtk_brom_backup", "mtk_download_info"],
        "MTK BROM": ["mtk_crash_brom", "mtk_brom_info", "mtk_brom_backup", "mtk_verify", "mtk_verify", "mtk_brom_info", "mtk_crash_brom", "mtk_brom_backup"],
        "FASTBOOT": ["fastboot_devices", "fastboot_getvar", "fastboot", "oem_unlock_guide"],
        "EDL": ["edl_detect", "qcom_detect_info", "qcom_verify", "qcom_detect_info", "qcom_verify"],
        "SPD": ["spd_detect_info", "spd_detect_info"],
    },
    "Detect Devices": {
        "ADB": ["detect", "detect"],
        "MTP": ["detect"],
        "Download mode": ["detect"],
        "Samsung BROM": ["detect"],
        "MTK": ["mtk_download_info", "mtk_brom_info", "mtk_brom_backup"],
        "MTK BROM": ["mtk_crash_brom", "mtk_brom_info", "mtk_brom_backup"],
        "FASTBOOT": ["fastboot_devices", "fastboot_getvar", "fastboot", "fastboot_devices", "fastboot_getvar", "fastboot"],
        "EDL": ["detect", "qcom_detect_info", "edl_detect"],
        "SPD": ["spd_detect_info"],
    },
    "Reboot": {
        "ADB": ["reboot_recovery", "reboot_download", "reboot_normal", "reboot_edl", "reboot_bootloader", "reboot_normal", "reboot_recovery", "reboot_download", "reboot_edl", "reboot_bootloader"],
        "MTP": ["reboot_recovery", "reboot_download", "reboot_normal"],
        "Download mode": ["reboot_normal"],
        "Samsung BROM": ["reboot_normal"],
        "MTK": ["reboot_normal"],
        "FASTBOOT": ["fastboot_reboot", "fastboot_reboot_bootloader", "fastboot_recovery", "fastboot_continue", "fastboot_reboot_bootloader", "fastboot_recovery", "fastboot_continue"],
        "EDL": ["reboot_normal"],
    },
    "Repair Settings": {
        "ADB": ["repair_settings", "fix_adb_auth", "fix_adb_auth"],
        "MTP": ["enable_adb", "test_mode"],
    },
    "Unlock Carrier": {
        "ADB": ["carrier_lock_status", "carrier_lock_status"],
        "MTK BROM": ["carrier_lock_mtk", "carrier_lock_mtk"],
    },
    "Remove MDM": {
        "ADB": ["mdm_diagnostics", "mdm_unlock", "mdm_unlock_comprehensive", "mdm_unlock_recovery", "mdm_unlock_recovery_wipe", "mdm_qr", "mdm_qr", "mdm_diagnostics", "mdm_unlock", "mdm_unlock_comprehensive"],
        "MTP": ["enable_adb", "test_mode"],
        "FASTBOOT": ["fastboot_wipe", "fastboot_frp"],
        "Download mode": ["mdm_unlock_recovery", "mdm_unlock_recovery_wipe"],
    },
    "Knox / Warranty": {
        "ADB": ["knox_check", "kg_remove", "knox_check", "knox_bypass", "kg_remove"],
        "Download mode": ["knox_check", "knox_bypass"],
        "Samsung BROM": ["knox_check", "knox_bypass"],
    },
    "QCN / Modem": {
        "ADB": ["qcn_backup", "qcn_nv_browser", "qcn_efs_explorer"],
        "EDL": ["qcn_backup", "qcn_restore", "qcn_imei_repair", "qcn_nv_browser", "qcn_efs_explorer", "qcn_backup"],
    },
    "IMEI Repair / Change": {
        "ADB": ["imei_repair_mtk", "imei_repair_spd", "imei_change_spd"],
        "MTK BROM": ["imei_repair_mtk", "imei_change_mtk"],
        "EDL": ["qcn_imei_repair"],
    },
    "eMMC / UFS": {
        "ADB": ["emmc_health", "emmc_raw", "emmc_health"],
    },
}


def list_jobs():
    return list(JOBS.keys())


def modes_for(job):
    reg = _load_registry()
    if reg:
        modes = []
        for row in reg:
            if row["job"] == job and row["mode"] not in modes:
                modes.append(row["mode"])
        if modes:
            return modes
    return list(MODES)


def methods_for(job, mode):
    reg = _load_registry()
    if reg:
        keys = []
        for row in reg:
            if row["job"] == job and row["mode"] == mode and row["key"] not in keys:
                keys.append(row["key"])
        if keys:
            return keys
    return list(JOBS.get(job, {}).get(mode, []))


def flow_for(job, mode, method):
    return FLOWS[method]()


def list_methods():
    return sorted(FLOWS.keys())


# Re-exports from the sub-modules the GUI uses
from .cancel import request_cancel as _rc, clear_cancel as _cc, cancel_requested as _cr
request_cancel = _rc
clear_cancel = _cc
cancel_requested = _cr
