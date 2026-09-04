"""eMMC/UFS deep tools — health, bad block, raw NAND (EXPERIMENTAL).

Linux host-side: reads /sys/block/mmcblk*/device/*, sg / ioctl helpers.
Device-side (when rooted): /sys/class/mmc_host/*, /sys/block/sda/device
for UFS. All raw-write paths are EXPERIMENTAL with audit log.
"""

import os
import re
import subprocess

from .flow import Flow, Step


def _host_emmc_health(log=None) -> dict:
    info = {}
    # Host eMMC/UFS (useful for embedded lab boards)
    for base in ["/sys/block", "/sys/class/block"]:
        if not os.path.isdir(base):
            continue
        for ent in os.listdir(base):
            if not ent.startswith(("mmcblk", "sda", "sdb")):
                continue
            dev_path = os.path.join(base, ent, "device")
            if not os.path.isdir(dev_path):
                continue
            # Collect known files
            for key in ["name", "type", "cid", "csd", "date", "fwrev", "hwrev", "oemid", "manfid", "serial", "life_time", "pre_eol_info"]:
                fp = os.path.join(dev_path, key)
                if os.path.isfile(fp):
                    try:
                        info[f"{ent}_{key}"] = open(fp).read().strip()
                    except Exception:
                        pass
    # mmc extcsd via mmc-utils if present
    mmc = next((p for p in ["/usr/bin/mmc", "/usr/local/bin/mmc"] if os.path.isfile(p)), "")
    if mmc:
        try:
            out = subprocess.run([mmc, "extcsd", "read", "/dev/mmcblk0"], capture_output=True, text=True, timeout=8).stdout
            for line in out.splitlines()[:80]:
                if "Life Time" in line or "Pre EOL" in line or "EXT_CSD" in line:
                    if log:
                        log(f"  [mmc extcsd] {line.strip()}")
                    info["extcsd_line"] = line.strip()
        except Exception:
            pass
    return info


def _adb_emmc_health(log=None) -> dict:
    from . import bridge

    info = {}
    try:
        out = bridge.adb_shell("cat /sys/class/mmc_host/mmc0/mmc0:0001/life_time 2>/dev/null; cat /sys/class/mmc_host/mmc0/mmc0:0001/pre_eol_info 2>&1 | head", timeout=8)
        if out.strip():
            info["adb_life_time"] = out.strip()
            if log:
                log(f"  adb life_time: {out.strip()}")
    except Exception:
        pass
    try:
        out = bridge.adb_shell("ls -l /sys/block/mmcblk0/device/ 2>&1 | head -n 20", timeout=8)
        if out.strip():
            for line in out.splitlines()[:20]:
                if log:
                    log(f"  adb emmc sysfs: {line}")
    except Exception:
        pass
    # UFS: /sys/block/sda/device model/rev
    try:
        out = bridge.adb_shell("cat /sys/block/sda/device/model 2>/dev/null; cat /sys/block/sda/device/rev 2>&1 | head", timeout=8)
        if out.strip():
            info["ufs_model"] = out.strip()
    except Exception:
        pass
    return info


def flow_emmc_health():
    def _run(ctx, log):
        log("=" * 60)
        log("eMMC/UFS health — host + device (read-only)")
        log("=" * 60)
        h = _host_emmc_health(log)
        if h:
            for k, v in list(h.items())[:30]:
                log(f"  host {k} = {v}")
        else:
            log("  Host: no mmcblk/sda in /sys/block — not an eMMC host")
        a = _adb_emmc_health(log)
        if not h and not a:
            log("  No health data — connect device with USB debugging or run on eMMC host")
        log("  Health read complete (read-only). Raw programming is EXPERIMENTAL.")

    return Flow("eMMC/UFS health (read-only)", [Step("emmc_health", _run)])


def flow_emmc_raw():
    def _run(ctx, log):
        from .experimental import check_gate_strict, per_run_acked_from_ctx, audit_log

        if not check_gate_strict("emmc_ufs_raw", per_run_acked_from_ctx(ctx), log):
            raise RuntimeError("Raw NAND access is EXPERIMENTAL — ack required")
        audit_log("emmc_ufs_raw", "raw_access")
        log("[EXPERIMENTAL] eMMC/UFS raw NAND — you accept brick risk")
        log("  Provide EMMC_RAW_TARGET, EMMC_RAW_OFFSET, EMMC_RAW_FILE env")
        target = os.environ.get("EMMC_RAW_TARGET", "").strip() or ctx.get("target", "")
        offset = os.environ.get("EMMC_RAW_OFFSET", "").strip() or ctx.get("offset", "")
        fpath = os.environ.get("EMMC_RAW_FILE", "").strip() or ctx.get("file", "")
        mode = os.environ.get("EMMC_RAW_MODE", "read")  # read|write
        if not target or not fpath:
            raise RuntimeError("Set EMMC_RAW_TARGET (/dev/mmcblk0 or /dev/mmcblk0pX or adb:/dev/block/mmcblk0) and EMMC_RAW_FILE")
        off = 0
        if offset:
            off = int(offset, 0)
        log(f"  Target={target} offset=0x{off:x} mode={mode} file={fpath}")
        if mode == "read":
            # Host read via dd, device read via adb
            if target.startswith("adb:"):
                dev = target[4:]
                from . import bridge
                # adb pull raw via dd to tmp
                tmp = f"/tmp/emmc_raw_{os.getpid()}.bin"
                cmd = f"dd if={dev} of={tmp} bs=4096 skip={off//4096} count=256 2>&1 | head"
                out = bridge.adb_shell(cmd, timeout=30)
                log(f"  adb dd: {out[:400]}")
                bridge.adb_shell(f"ls -l {tmp} 2>&1 | head", timeout=5)
                log(f"  (adb read placeholder — HIL required for full readback)")
            else:
                if not os.path.exists(target):
                    raise RuntimeError(f"Host target not found: {target}")
                # Example placeholder — real would need ioctl for reliable raw
                log(f"  Host dd if={target} of={fpath} skip=... (placeholder)")
                log("  [EXPERIMENTAL] Raw write gate passed — streaming via dd not yet HIL-validated, prepared only.")
        else:
            if not os.path.isfile(fpath):
                raise RuntimeError(f"File not found: {fpath}")
            log(f"  Write file {os.path.getsize(fpath)} bytes -> {target} @0x{off:x} (placeholder, no autonomous write until HIL)")
            log("  Set EMMC_RAW_DO_WRITE=1 after HIL to enable")

    return Flow("eMMC/UFS raw NAND (EXPERIMENTAL — brick risk)", [Step("emmc_raw", _run)])
