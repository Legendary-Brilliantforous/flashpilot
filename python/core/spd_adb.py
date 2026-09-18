"""Enable ADB on Spreadtrum/UNISOC devices via boot.img patch (Path 1).

Chain:
    BROM -> FDL1+FDL2 -> spd-readback boot_a -> patch default.prop
    (ro.adb.secure=0, ro.debuggable=1, persist.sys.usb.config+=adb)
    -> repack boot.img (headers/sizes preserved) -> spd-flash boot_a
    -> reboot -> unauthorized ADB appears -> user taps Allow (or the
    ro.adb.secure=0 build accepts without prompt on engineering-style builds).

The patch is reversible: stock boot is saved to the backup folder first and
a `restore` entry point writes it back.
"""

import os
import struct
import tempfile
import time

from . import bridge


# Android boot image magic
BOOT_MAGIC = b"ANDROID!"

# Fields we set/patch inside the ramdisk's default prop files.
ADB_PROPS = {
    "ro.adb.secure": "0",
    "ro.debuggable": "1",
    "ro.secure": "0",
    "persist.sys.usb.config": "mtp,adb",
    "sys.usb.configfs": "1",
}


class BootImageError(RuntimeError):
    pass


def _patch_props_in_ramdisk(ramdisk: bytes, log) -> tuple:
    """Decompress gzip ramdisk, patch prop files, recompress.

    Returns (new_ramdisk_bytes, patched_names, was_gzipped). Pure-Python
    path: fallback when the bridge is absent + unit-test oracle for the
    native engine (byte parity on decompressed content)."""
    import gzip
    import io

    try:
        raw = gzip.decompress(ramdisk)
        was_gz = True
    except Exception:
        raw = ramdisk
        was_gz = False

    patched = []
    idx = 0
    buf = bytearray(raw)
    while True:
        idx = buf.find(b"070701", idx)
        if idx < 0:
            break
        hdr = bytes(buf[idx:idx + 110])
        if len(hdr) < 110 or not _is_hex_ascii(hdr):
            idx += 6
            continue
        try:
            namesize = int(hdr[94:102], 16)
            filesize = int(hdr[54:62], 16)
            name_start = idx + 110
            name = bytes(buf[name_start:name_start + namesize - 1]).decode(
                "ascii", errors="ignore")
            data_start = name_start + namesize
            data_start = (data_start + 3) & ~3
        except Exception:
            idx += 6
            continue

        if name.endswith("default.prop") or name.endswith("build.prop") or \
           name in ("default.prop", "prop.default", "build.prop"):
            content = bytes(buf[data_start:data_start + filesize])
            new_content = _patch_prop_text(content.decode(
                "utf-8", errors="ignore"), log, name)
            nb = new_content.encode()
            if len(nb) <= len(content):
                nb = nb + b"\n" * (len(content) - len(nb))  # pad with newlines
                buf[data_start:data_start + filesize] = nb
                patched.append(name)
                log(f"    patched {name} ({filesize}B)")
                idx = data_start + ((filesize + 3) & ~3)
                continue
            # Patched text is larger than the slot: grow the cpio by rewriting
            # this entry's header (new filesize) and splicing the rest after.
            # This is the standard approach used by magiskboot's cpio repack.
            # Data position MUST use the same absolute alignment as the
            # reader (align_up(110 + namesize)); padding the name length
            # alone disagrees with the scan by (110 % 4) bytes and corrupts
            # every entry after the splice.
            growth = ((len(nb) + 3) & ~3) - ((filesize + 3) & ~3)
            new_namesize = namesize  # name unchanged
            fields_new = bytearray(hdr)
            fields_new[54:62] = f"{len(nb):08X}".encode()
            # keep namesize as-is
            data_pos = (110 + namesize + 3) & ~3
            new_entry = bytes(fields_new) + bytes(buf[name_start:name_start + namesize])
            pad1 = b"\x00" * (data_pos - 110 - namesize)
            pad2 = b"\x00" * (((-len(nb)) % 4))
            new_entry += pad1 + nb + pad2
            old_entry_len = data_pos + ((filesize + 3) & ~3)
            buf[idx:idx + old_entry_len] = new_entry
            patched.append(name)
            log(f"    patched+grew {name} ({filesize} -> {len(nb)}B, +{growth})")
            idx += len(new_entry)
            continue
        idx = data_start + ((filesize + 3) & ~3)

    if not patched:
        raise BootImageError("no prop file found/patched in ramdisk")

    new_raw = bytes(buf)
    if was_gz:
        bio = io.BytesIO()
        with gzip.GzipFile(fileobj=bio, mode="wb", mtime=0) as g:
            g.write(new_raw)
        return bio.getvalue(), patched, True
    return new_raw, patched, False


def _patch_prop_text(text: str, log, name: str) -> str:
    """Set/replace ADB-related keys; append missing ones at end."""
    lines = text.splitlines()
    seen = {}
    out = []
    for ln in lines:
        stripped = ln.strip()
        key = None
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _, v = stripped.partition("=")
            key = k.strip()
        if key in ADB_PROPS:
            seen[key] = True
            new_v = ADB_PROPS[key]
            if v.strip() != new_v:
                log(f"      {key}: {v.strip()} -> {new_v}")
            out.append(f"{key}={new_v}")
        else:
            out.append(ln)
    missing = [k for k in ADB_PROPS if k not in seen]
    if missing:
        out.append("")
        out.append("# added by FlashPilot (adb enable)")
        for k in missing:
            out.append(f"{k}={ADB_PROPS[k]}")
            log(f"      {k}: (absent) -> {ADB_PROPS[k]}")
    return "\n".join(out) + "\n"


def _is_hex_ascii(b) -> bool:
    """True when every byte in the ASCII string is a hex digit (cpio newc)."""
    s = b.decode("ascii", errors="ignore")
    return bool(s) and all(c in "0123456789ABCDEFabcdef" for c in s)


def read_boot(bridge, target, fdl1, a1, fdl2=None, a2=None,
              part="boot", out_path=None, log=print):
    """Read `part` (boot/boot_a/recovery...) via spd-readback subset."""
    out_path = out_path or os.path.join(
        tempfile.gettempdir(), f"spd_{part}_{int(time.time())}.img")
    args = ["spd-readback", target, fdl1, f"0x{a1:x}",
            fdl2 or "none"] + ([f"0x{a2:x}"] if a2 else [])
    args += [out_path, part]
    bridge._run(args, timeout=600)
    if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
        raise BootImageError(f"readback produced no data for {part}")
    return out_path


def write_boot(bridge, target, fdl1, a1, img_path, fdl2=None, a2=None,
               part="boot", log=print):
    """Write patched img back to `part` via spd-flash."""
    args = ["spd-flash", target, fdl1, f"0x{a1:x}"]
    if fdl2:
        args += [fdl2] + ([f"0x{a2:x}"] if a2 else [])
    args.append(f"{part}={img_path}")
    bridge._run(args, timeout=900)


def enable_adb_via_boot_patch(bridge, target, fdl1, a1, fdl2=None, a2=None,
                               part="boot", backup_dir="", log=print) -> dict:
    """Full flow: read -> patch -> write. Returns dict with paths."""
    log(f"[adb-en] reading {part} ...")
    stock = read_boot(bridge, target, fdl1, a1, fdl2, a2, part, log=log)

    if backup_dir:
        os.makedirs(backup_dir, exist_ok=True)
        keep = os.path.join(backup_dir, f"{part}_stock.img")
        with open(stock, "rb") as s, open(keep, "wb") as d:
            d.write(s.read())
        log(f"[adb-en] stock image saved: {keep}")

    with open(stock, "rb") as f:
        img = bytearray(f.read())

    if img[:8] != BOOT_MAGIC:
        raise BootImageError(f"{part} has no ANDROID! magic - not a boot image?")

    patched_path = stock.replace(".img", "_adb.img")
    try:
        summary = bridge.boot_patch_adb(stock, patched_path)
    except bridge.BinaryNotFoundError:
        raise
    except bridge.BridgeError as e:
        raise BootImageError(str(e))
    log(f"[adb-en] kernel={summary['kernel_size']} "
        f"ramdisk={summary['ramdisk_size']} page={summary['page_size']}")
    if summary["grew_by"] > 0:
        log(f"[adb-en] ramdisk grew by {summary['grew_by']}B - header size updated")
    log(f"[adb-en] patched image: {patched_path}")

    log(f"[adb-en] flashing patched {part} ...")
    write_boot(bridge, target, fdl1, a1, patched_path, fdl2, a2, part, log=log)
    log("[adb-en] done - rebooting device will expose ADB "
        "(ro.adb.secure=0). If still unauthorized, accept the dialog once.")

    return {"stock": stock, "stock_backup": keep if backup_dir else None,
            "patched": patched_path}
