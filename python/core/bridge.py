import json
import os
import subprocess
import shutil
import threading
import time
from pathlib import Path


def _resolve_bridge():
    """Locate the compiled Rust bridge binary.

    Priority: BRILLIANT_BRIDGE env override -> in-source `target/release` path
    (dev) -> installed system paths (packaged .deb layout)."""
    env = os.environ.get("BRILLIANT_BRIDGE")
    if env:
        return Path(env)
    dev = Path(__file__).resolve().parent.parent.parent / "target" / "release" / "brilliant-bridge"
    if dev.exists():
        return dev
    for cand in (
        "/usr/lib/brilliant/brilliant-bridge",
        "/usr/libexec/brilliant/brilliant-bridge",
        "/opt/brilliant/brilliant-bridge",
    ):
        if Path(cand).exists():
            return Path(cand)
    return dev


BRIDGE = _resolve_bridge()


class BridgeError(RuntimeError):
    pass


class BridgeCancelled(BridgeError):
    """Raised when the user hits Stop while a bridge subprocess is running."""


# ---- cooperative cancel (mirrors frp.py) ------------------------------
_cancel = threading.Event()


def request_cancel():
    _cancel.set()


def clear_cancel():
    _cancel.clear()


def cancel_requested():
    return _cancel.is_set()


def _run(args, timeout=15):
    if not BRIDGE.exists():
        raise BridgeError(
            f"rust bridge not built at {BRIDGE}. Run `cargo build --release` first."
        )
    proc = subprocess.Popen(
        [str(BRIDGE), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + timeout
    while True:
        if cancel_requested():
            proc.kill()
            proc.wait()
            raise BridgeCancelled("cancelled by user")
        rc = proc.poll()
        if rc is not None:
            break
        if time.monotonic() > deadline:
            proc.kill()
            proc.wait()
            raise BridgeError(f"timed out after {timeout}s")
        time.sleep(0.05)
    out, err = proc.communicate()
    if proc.returncode != 0:
        raise BridgeError(err.strip() or out.strip())
    return out.strip()


def detect_usb():
    return json.loads(_run(["detect"]))


def detect_all():
    """All USB devices (any VID) - lets the GUI see non-Samsung targets like
    Qualcomm modems that are not in EDL mode."""
    return json.loads(_run(["detect-all"]))


def detect_mtk():
    """MediaTek low-level USB devices (BROM/preloader/DA) - VID 0x0e8d."""
    return json.loads(_run(["mtk-detect"]))


def list_samsung_hid():
    return json.loads(_run(["hid-list"]))


def hid_send(target, hex_payload, timeout=15):
    return json.loads(_run(["hid-open", target, hex_payload], timeout=timeout))


def usb_config(target, config_index, timeout=30):
    """Switch a Samsung device's active USB configuration (index), retrying
    with USB resets like the commercial tools (galaxy-at-tool recipe)."""
    return json.loads(_run(["usb-config", target, str(config_index)], timeout=timeout))


def usb_detach_kernel(target, timeout=30):
    """Detach kernel drivers (cdc_acm, etc.) from every interface on a device
    so libusb bulk transfers can claim them - fixes 'bulk read timed out'."""
    return json.loads(_run(["usb-detach-kernel", target], timeout=timeout))


def at_send(target, cmd, timeout_ms=4000, timeout=15):
    """Send an AT command (text after 'AT', or '' for a bare ping) over the
    device's CDC ACM diag port. Returns dict with reply/ok."""
    return json.loads(
        _run(["at-send", target, cmd, str(timeout_ms)], timeout=timeout)
    )


def mtp_info(target, timeout_ms=8000, timeout=20):
    """MTP GetDeviceInfo: reports which MTP operations the device supports
    (including any vendor ops) and whether an MTP session can be opened.
    Returns a dict, or raises BridgeError if the session is refused."""
    return json.loads(
        _run(["mtp-info", target, str(timeout_ms)], timeout=timeout)
    )


def adb_devices():
    return json.loads(_run(["adb-devices"]))


def adb_status():
    """Parsed `adb devices -l`: list of {serial, state, extra}.
    state is 'device' (authorized), 'unauthorized', 'offline', 'recovery', ..."""
    devs = []
    for line in adb_devices():
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        devs.append({
            "serial": parts[0],
            "state": parts[1],
            "extra": parts[2] if len(parts) > 2 else "",
        })
    return devs


def adb_shell(cmd, timeout=20):
    return _run(["adb-shell", cmd], timeout=timeout)


def odin_connect(target, timeout=30):
    return _run(["odin-connect", target], timeout=timeout)


def odin_pit(target, outfile=None, timeout=90):
    args = ["odin-pit", target]
    if outfile:
        args.append(outfile)
    return _run(args, timeout=timeout)


def odin_info(target, pit_file, timeout=90):
    return _run(["odin-info", target, pit_file], timeout=timeout)


def odin_model(target, timeout=40):
    """Read the device model string over the Odin session probe (0x64/0x01),
    falling back to the 0x69 device-info dump. Returns dict."""
    return json.loads(_run(["odin-model", target], timeout=timeout))


def has_adb():
    return shutil.which("adb") is not None
