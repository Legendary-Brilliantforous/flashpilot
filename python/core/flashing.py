"""FlashPilot flashing - Odin/Samsung firmware flashing.

Canonical location for all Odin/flashing flows. Previously these lived in
``frp.py`` (god-file). New code should::

    from .flashing import flow_odin_advanced_flash, flow_odin_flash_tar, ...

``frp.py`` re-exports the same symbols for backwards-compat but is
deprecated for flashing - it will be trimmed to FRP/lock-only in a
future release.

This module is currently a shim over ``frp`` to avoid a risky 2k-line
move in one commit. The next step is to move the implementations here
and make ``frp`` import from this module instead (requires extracting
shared helpers into ``flow.py``).
"""

# Re-export flashing symbols from the legacy location.
# Keep the list explicit so import cost stays low and linters see it.
from .core import (  # noqa: F401
    _find_odin4, _find_slot_tar, _tar_md5_valid, _strip_odin4_md5_trailer,
)
from .core import (  # noqa: F401
    flow_efs_backup, flow_efs_restore, flow_change_sales_code,
    flow_odin_enable_adb, flow_odin_flash_tar, flow_odin_check, flow_odin_list,
    flow_odin_pit_tools, flow_odin_flash_partition_gui, flow_odin_vbmeta,
    flow_odin_flash_multi, flow_odin_send_pit, flow_odin_advanced_flash,
    flow_preflight, _run_odin4_streaming,
    _enforce_flash_gates, _enforce_bl_downgrade_gate,
    _require_preflight, _require_recent_efs_backup,
)

__all__ = [
    "ODIN4_SHA256",
    "ODIN4_SHA256_MTK",
    "ODIN4_SHA256S",
    "flow_odin_enable_adb",
    "flow_odin_flash_tar",
    "flow_odin_check",
    "flow_odin_list",
    "flow_odin_advanced_flash",
    "flow_odin_pit_tools",
    "flow_odin_flash_partition_gui",
    "flow_odin_vbmeta",
    "flow_odin_flash_multi",
    "flow_odin_send_pit",
    "flow_efs_backup",
    "flow_efs_restore",
    "flow_mtk_samsung_gpt",
]

# ---------------------------------------------------------------------------
# MTK Samsung (A145P etc): Samsung firmware has NO scatter. Flash via GPT.
# Rust does the actual writes (mtk-flash-samsung); Python extracts tar.md5 +
# decompresses lz4 first, then calls bridge.mtk_flash_samsung.
# ---------------------------------------------------------------------------
def flow_mtk_samsung_gpt():
    """Flash Samsung MTK firmware (A145P/A05/A06) via MTK DA + GPT.

    No scatter file needed. Caller sets MTK_DA (DA binary) and selects
    firmware dir containing AP/BL/CP/CSC tar.md5 or already-extracted .img.
    The flow extracts tar.md5, decompresses .img.lz4, then flashes each
    partition by name via device GPT (Rust mtk-flash-samsung).
    """
    from .flow import Flow, Step
    from . import bridge
    import os, tarfile, tempfile, glob

    def _run(ctx, log):
        da = os.environ.get("MTK_DA", "").strip() or ctx.get("mtk_da", "")
        if da and not os.path.isfile(da):
            raise RuntimeError(f"MTK_DA not found: {da}")
        if not da:
            # try auto-find
            from .core import _find_mtk_da
            da = _find_mtk_da()
            if not da:
                raise RuntimeError("No MTK DA binary found. Place one in ~/Downloads or set MTK_DA=/path/to/da.bin")

        fw_dir = os.environ.get("MTK_FW_DIR", "").strip() or ctx.get("mtk_fw_dir", "") or os.path.expanduser("~/Downloads")
        # if fw_dir is a tar file, extract it
        work = tempfile.mkdtemp(prefix="flashpilot_mtk_samsung_")
        had_tar = False
        for tar in glob.glob(os.path.join(fw_dir, "*.tar.md5")) + glob.glob(os.path.join(fw_dir, "*.tar")):
            had_tar = True
            log(f"Extracting {os.path.basename(tar)}...")
            try:
                with tarfile.open(tar, "r") as tf:
                    tf.extractall(work)
            except Exception as e:
                log(f"  warn: extract {tar}: {e}")

        src_dir = work if had_tar else fw_dir
        # decompress .lz4 (legacy) + .zst/.zstd (zstd preferred) — dual support
        for ext, strip_len in [(".lz4", 4), (".zst", 4), (".zstd", 5)]:
            for comp in glob.glob(os.path.join(src_dir, f"*{ext}")):
                out = comp[:-strip_len]
                if os.path.exists(out):
                    continue
                log(f"Decompressing {os.path.basename(comp)}...")
                if ext == ".lz4":
                    try:
                        import lz4.frame as _lz4
                        open(out, "wb").write(_lz4.decompress(open(comp, "rb").read()))
                    except Exception:
                        import subprocess
                        subprocess.run(["lz4", "-d", "-f", comp, out], check=True)
                else:
                    try:
                        import zstandard as _zstd
                        dctx = _zstd.ZstdDecompressor()
                        data = open(comp, "rb").read()
                        dec = dctx.decompress(data, max_output_size=8*1024*1024*1024)
                        open(out, "wb").write(dec)
                    except Exception:
                        import subprocess
                        subprocess.run(["zstd", "-d", "-f", comp, out], check=True)

        # count images
        imgs = glob.glob(os.path.join(src_dir, "*.img")) + glob.glob(os.path.join(src_dir, "*.bin"))
        if not imgs:
            raise RuntimeError(f"No partition images found in {src_dir} (extract Samsung tar.md5 first)")

        log(f"MTK Samsung flash: {len(imgs)} images from {src_dir} via DA {os.path.basename(da)}")
        log("Device must be in BROM/Preloader (0e8d:0003/2000) - power off, hold Vol Up+Down, plug USB")
        res = bridge.mtk_flash_samsung(da, src_dir, timeout=1800)
        log(res)
        return True

    return Flow("MTK Samsung flash (GPT, no scatter)", [Step("mtk_samsung_gpt", _run)])
