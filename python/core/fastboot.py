"""Google Pixel Fastboot support — unlock, factory images, slot A/B, vbmeta.

All fastboot device communication runs on the native Rust transport
(target-pinned `vid:pid@bus:addr`, kernel-driver detach) via
``bridge.fastboot_cmd`` — the protocol lives in the Rust core
(`src/fastboot.rs`), not in Python and not in an external binary.
All high-risk ops are EXPERIMENTAL behind the experimental gate
(fastboot_pixel).

Factory images: extracts Pixel factory zip (contains bootloader/radio/*.img +
flash-all.sh) and flashes slot-aware over the native transport.
`flash-all.sh` itself always runs as a vendor script through bash
(never reimplemented) — the only path that still reaches for the system
fastboot binary, and it is skipped when the native per-image path can do
the job.
"""

import glob
import os
import re
import shutil
import subprocess
import tempfile
import zipfile

from . import bridge
from .flow import Flow, Step


def _native_target() -> str:
    """Resolve a native fastboot target (``vid:pid@bus:addr``).

    Prefers the ambient device scope (GUI device picker); otherwise the
    first device exposing a fastboot interface. Returns '' when none —
    callers raise with the native-mode instructions."""
    try:
        from . import devices as _dev

        key = _dev.current_key()
        devs = bridge.fastboot_devices(timeout=10) or []
        devs = [d for d in devs if isinstance(d, dict)]
        if key and key.startswith("adb:"):
            want = key[4:]
            for d in devs:
                if (d.get("serial") or "") == want:
                    return _target_str(d)
        if devs:
            return _target_str(devs[0])
    except Exception:
        pass
    return ""


def _target_str(d) -> str:
    try:
        return f"{d['vid']}:{d['pid']}@{d['bus']}:{d['address']}"
    except (KeyError, TypeError):
        return ""


def _run_fastboot(args, timeout=120, log=None):
    """Run one fastboot command over the native Rust transport.

    Device communication is Rust-only (`src/fastboot.rs`): no external
    fastboot binary is invoked from Python."""
    if isinstance(args, str):
        args = [args]
    target = _native_target()
    if not target:
        raise RuntimeError(
            "No fastboot device detected by the native transport. "
            "Boot the device to fastboot mode (VID 18d1 PID 4ee0), "
            "replug, and retry."
        )
    if log:
        log(f"$ fastboot {' '.join(args)}  [native → {target}]")
    try:
        out = bridge.fastboot_cmd(
            target, list(args),
            timeout_ms=max(5000, timeout * 1000),
            timeout=timeout + 15,
        )
    except Exception as e:  # noqa: BLE001 - BridgeError subclasses + BinaryNotFound
        raise RuntimeError(f"native fastboot failed: {e}")
    if log:
        for line in out.splitlines():
            log(f"  {line}")
    if "FAILED" in (out or ""):
        raise RuntimeError(f"fastboot {' '.join(args)} failed:\n{out}")
    return out or ""


def _is_fastboot_device() -> bool:
    try:
        devs = bridge.fastboot_devices(timeout=10) or []
        if any(isinstance(d, dict) for d in devs):
            return True
    except Exception:
        pass
    try:
        devs = bridge.detect_all()
        for d in devs:
            if d.get("vid") == 0x18D1 and d.get("pid") in (0x4EE0, 0xD00D):
                return True
            for iface in d.get("interfaces", []):
                if iface.get("class") == 255 and iface.get("subclass") == 66 and iface.get("protocol") == 3:
                    return True
    except Exception:
        pass
    return False


def _vbmeta_patch_flags(data: bytes, disable: bool = True) -> bytes:
    # Reuse frp._patch_vbmeta_flags if available
    try:
        from .core import _patch_vbmeta_flags
        patched = _patch_vbmeta_flags(data)
        return patched if patched else data
    except Exception:
        return data


def flow_fastboot_info():
    def _run(ctx, log):
        log("Fastboot info — listing devices and vars")
        if not _native_target() and not _is_fastboot_device():
            log("  No fastboot devices detected by the native transport.")
        try:
            out = _run_fastboot(["devices", "-l"], log=log)
            if not out.strip():
                log("  No fastboot devices. Boot Pixel to fastboot: Vol Down + Power → fastboot")
        except Exception as e:
            log(f"  {e}")
        for var in ["product", "version-bootloader", "current-slot", "slot-count", "unlocked"]:
            try:
                _run_fastboot(["getvar", var], log=log)
            except Exception:
                pass

    return Flow("Pixel fastboot info", [Step("fastboot_info", _run)])


def flow_fastboot_unlock():
    def _run(ctx, log):
        from .experimental import check_gate_strict, per_run_acked_from_ctx, audit_log

        if not check_gate_strict("fastboot_pixel", per_run_acked_from_ctx(ctx), log):
            raise RuntimeError("Fastboot unlock is EXPERIMENTAL — per-run ack required")
        audit_log("fastboot_pixel", "unlock_attempt")
        log("[EXPERIMENTAL] Fastboot bootloader unlock — THIS WIPES ALL DATA")
        if not _is_fastboot_device():
            raise RuntimeError("No fastboot device. Pixel must be in fastboot mode (bootloader).")
        _run_fastboot(["flashing", "unlock"], log=log)
        log("Unlock sent — confirm on device screen with Volume/Power, then reboot.")

    return Flow("Pixel bootloader unlock (EXPERIMENTAL)", [Step("fastboot_unlock", _run)])


def flow_fastboot_flash_factory():
    def _run(ctx, log):
        from .experimental import check_gate_strict, per_run_acked_from_ctx, audit_log

        if not check_gate_strict("fastboot_pixel", per_run_acked_from_ctx(ctx), log):
            raise RuntimeError("Factory flash is EXPERIMENTAL — per-run ack required")
        audit_log("fastboot_pixel", "factory_flash")
        zip_path = os.environ.get("PIXEL_FACTORY_ZIP", "").strip() or ctx.get("factory_zip", "")
        if not zip_path or not os.path.isfile(zip_path):
            raise RuntimeError("Set PIXEL_FACTORY_ZIP=/path/to/pixel_factory.zip or place zip in ~/Downloads")
        log(f"Factory zip: {zip_path}")
        work = tempfile.mkdtemp(prefix="fp_pixel_")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(work)
            names = zf.namelist()
            log(f"  Zip contains {len(names)} files, e.g. {names[:5]}")
        # Handle vbmeta patch if env set
        if os.environ.get("PIXEL_PATCH_VBMETA") == "1":
            for vb in glob.glob(os.path.join(work, "**/vbmeta*.img"), recursive=True):
                try:
                    data = open(vb, "rb").read()
                    patched = _vbmeta_patch_flags(data)
                    if patched != data:
                        open(vb, "wb").write(patched)
                        log(f"  Patched {os.path.basename(vb)} AVB -> 0x03")
                except Exception as e:
                    log(f"  vbmeta patch skip {vb}: {e}")
        # Prefer the vendor script if present (the one documented exception
        # that shells out to the system fastboot binary inside bash — never
        # reimplemented). Everything else flashes over the native transport.
        flash_sh = glob.glob(os.path.join(work, "flash-all.sh"))
        if flash_sh and os.path.isfile(flash_sh[0]) and shutil.which("fastboot"):
            log(f"Running {flash_sh[0]}")
            # ensure fastboot in PATH for the script
            env = os.environ.copy()
            proc = subprocess.run(["bash", flash_sh[0]], cwd=work, env=env, capture_output=True, text=True, timeout=1800)
            for line in (proc.stdout + proc.stderr).splitlines():
                log(f"  {line}")
            if proc.returncode != 0:
                raise RuntimeError(f"flash-all.sh failed with {proc.returncode}")
            log("Factory flash complete — device will reboot to system.")
            return True
        # Fallback: fastboot flash each img individually
        imgs = glob.glob(os.path.join(work, "*.img")) + glob.glob(os.path.join(work, "**/*.img"), recursive=True)
        if not imgs:
            raise RuntimeError(f"No .img found in {work}")
        for img_path in sorted(imgs):
            part = os.path.splitext(os.path.basename(img_path))[0]
            # Skip hidden or nested duplicates?
            log(f"Flashing {part} <- {os.path.basename(img_path)}")
            _run_fastboot(["flash", part, img_path], timeout=600, log=log)
        _run_fastboot(["reboot"], log=log)
        log("Flash complete — rebooting.")

    return Flow("Pixel factory flash (EXPERIMENTAL)", [Step("pixel_factory", _run)])


def flow_fastboot_flash_single():
    def _run(ctx, log):
        from .experimental import check_gate_strict, per_run_acked_from_ctx

        if not check_gate_strict("fastboot_pixel", per_run_acked_from_ctx(ctx), log):
            raise RuntimeError("Fastboot flash is EXPERIMENTAL — per-run ack required")
        part = os.environ.get("FASTBOOT_PARTITION", "").strip() or ctx.get("partition", "")
        img = os.environ.get("FASTBOOT_IMAGE", "").strip() or ctx.get("image", "")
        if not part or not img:
            raise RuntimeError("Set FASTBOOT_PARTITION and FASTBOOT_IMAGE env (or GUI picker)")
        if not os.path.isfile(img):
            raise RuntimeError(f"Image not found: {img}")
        if not _is_fastboot_device():
            raise RuntimeError("No fastboot device")
        # Slot handling: allow --slot all or _a/_b suffix
        slot = os.environ.get("FASTBOOT_SLOT", "").strip()
        args = ["flash"]
        if slot in ("a", "b", "all"):
            args += ["--slot", slot]
        args += [part, img]
        _run_fastboot(args, timeout=600, log=log)
        log(f"Flashed {part} from {os.path.basename(img)}")

    return Flow("Pixel flash single partition (EXPERIMENTAL)", [Step("fastboot_single", _run)])
