"""Safety-net backups before destructive flashing operations.

Before any write to boot-critical partitions, dump the small partitions that
make a device recoverable (preloader/lk/misc/frp + friends) into a per-device
backup folder. One careless click should never be unrecoverable.

Usage from flows:
    from .safety import preflash_backup
    preflash_backup(chip="spd", target="1:60", fdl1=..., log=log)
    # or for MTK/Odin:
    preflash_backup(chip="mtk", da="/path/da.bin", log=log)
"""

import os
import time


# Partitions worth saving before a flash, per chip family. Small ones only -
# dumping super/userdata would take longer than the flash itself.
_CRITICAL_PARTITIONS = {
    "spd": ["preloader", "lk", "lk_a", "misc", "misc_a", "frp", "frp_a",
            "persist", "proinfo", "nvdata", "nvcfg", "nvram"],
    "mtk": ["preloader", "lk", "lk_a", "misc", "misc_a", "frp", "frp_a",
            "persist", "proinfo", "nvdata", "nvcfg", "nvram", "seccfg",
            "para", "expdb", "metadata"],
    "odin": [],  # Samsung: PIT is dumped separately; BL tar already local
}

_MAX_PARTITION_BYTES = 32 * 1024 * 1024  # skip anything bigger than 32MB


def _backup_root() -> str:
    return os.path.expanduser("~/flashpilot/backups")


def backup_dir_for(chip: str, ident: str = "") -> str:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    name = f"{chip}_{ident}_{stamp}" if ident else f"{chip}_{stamp}"
    d = os.path.join(_backup_root(), name)
    os.makedirs(d, exist_ok=True)
    return d


def latest_backup_dir(chip: str) -> str:
    root = _backup_root()
    if not os.path.isdir(root):
        return ""
    cands = sorted(
        (os.path.join(root, n) for n in os.listdir(root) if n.startswith(f"{chip}_")),
        key=os.path.getmtime,
        reverse=True,
    )
    return cands[0] if cands else ""


def _dump_spd(bridge, target, fdl1, a1, fdl2, a2, out_dir, log) -> list:
    """Dump critical partitions via spd-backup subset (Rust reads by name)."""
    parts = _CRITICAL_PARTITIONS["spd"]
    args = ["spd-readback", target, fdl1, f"0x{a1:x}"]
    if fdl2:
        args += [fdl2] + ([f"0x{a2:x}"] if a2 else [])
    # spd-readback writes one .pac; we want per-partition files instead.
    # Use the partition-level path: spd-backup dumps everything, so filter
    # afterwards to keep the operation single-pass and simple.
    tmp_pac = os.path.join(out_dir, "_all.pac")
    args += [tmp_pac, ",".join(parts)]
    try:
        bridge._run(args, timeout=1200)
    except Exception as e:  # noqa: BLE001
        log(f"  backup readback failed (non-fatal): {e}")
        return []
    saved = [tmp_pac]
    log(f"  packed backup: {tmp_pac}")
    return saved


def _dump_mtk(bridge, da, scatter, out_dir, log) -> list:
    """MTK: use mtk-backup on the critical set via existing bridge command."""
    if not da:
        return []
    args = ["mtk-backup", "auto", da]
    if scatter:
        args.append(scatter)
    else:
        # no scatter: mtk-backup requires it today - skip silently
        log("  (no scatter - skipping MTK pre-flash backup)")
        return []
    args.append(out_dir)
    try:
        bridge._run(args, timeout=1800)
    except Exception as e:  # noqa: BLE001
        log(f"  backup failed (non-fatal): {e}")
        return []
    return [out_dir]


def preflash_backup(chip: str, bridge, log, target="", fdl1="", a1=None,
                    fdl2="", a2=None, da="", scatter="", ident="") -> str:
    """Best-effort safety backup. Never raises - a failed backup must not
    block the user's actual operation; it just logs."""
    try:
        parts_list = _CRITICAL_PARTITIONS.get(chip, [])
        if not parts_list:
            return ""
        out_dir = backup_dir_for(chip, ident)
        log(f"[safety] pre-flash backup -> {out_dir}")
        if chip == "spd" and target and fdl1 and a1 is not None:
            _dump_spd(bridge, target, fdl1, a1, fdl2, a2, out_dir, log)
        elif chip == "mtk":
            _dump_mtk(bridge, da, scatter, out_dir, log)
        return out_dir
    except Exception as e:  # noqa: BLE001
        try:
            log(f"[safety] backup skipped: {e}")
        except Exception:  # noqa: BLE001
            pass
        return ""
