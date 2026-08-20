import json
import os
import subprocess
import shutil
import threading
import time
from pathlib import Path


def _resolve_bridge():
    """Locate the compiled Rust bridge binary.

    Priority: flashpilot_BRIDGE env override -> in-source `target/release` path
    (dev) -> installed system paths (packaged .deb layout)."""
    env = os.environ.get("flashpilot_BRIDGE")
    if env:
        return Path(env)
    dev = Path(__file__).resolve().parent.parent.parent / "target" / "release" / "flashpilot-bridge"
    if dev.exists():
        return dev
    for cand in (
        "/usr/lib/flashpilot/flashpilot-bridge",
        "/usr/libexec/flashpilot/flashpilot-bridge",
        "/opt/flashpilot/flashpilot-bridge",
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

# Optional live-log callback: the GUI wires this to its console so Rust
# eprintln! progress lines reach the screen in real time.
_log_hook = None
_lock = threading.Lock()


def set_log_hook(fn):
    """Set a callable(line) that receives every line the bridge writes to
    stderr as it runs (flash progress, handshake retries, ...)."""
    global _log_hook
    with _lock:
        _log_hook = fn


def _forward_log(line):
    fn = None
    with _lock:
        fn = _log_hook
    if fn is not None:
        try:
            fn(line)
        except Exception:  # noqa: BLE001 - logging must never break a flash
            pass


def request_cancel():
    _cancel.set()


def clear_cancel():
    _cancel.clear()


def cancel_requested():
    return _cancel.is_set()


def _run(args, timeout=15):
    bridge_path = Path(BRIDGE)
    if not bridge_path.exists():
        raise BridgeError(
            f"rust bridge not built at {BRIDGE}. Run `cargo build --release` first."
        )
    proc = subprocess.Popen(
        [str(bridge_path), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    deadline = time.monotonic() + timeout

    # Background threads drain stdout and stderr independently. stderr lines
    # are forwarded live to the GUI; reading both pipes without double-reading
    # avoids the race where communicate() and a manual drainer split the pipe
    # nondeterministically and drop log lines.
    stdout_lines = []
    stderr_lines = []
    stopped = threading.Event()

    def _drain():
        assert proc.stderr is not None
        for raw in proc.stderr:
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            stderr_lines.append(line)
            _forward_log(line)
        stopped.set()

    def _drain_stdout():
        assert proc.stdout is not None
        for raw in proc.stdout:
            stdout_lines.append(raw)

    drainer = threading.Thread(target=_drain, daemon=True)
    drainer.start()
    out_drainer = threading.Thread(target=_drain_stdout, daemon=True)
    out_drainer.start()

    try:
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
        out_drainer.join(timeout=2)
        stopped.wait(timeout=2)
        drainer.join(timeout=2)
        out = "".join(stdout_lines)
        tail = "\n".join(stderr_lines[-25:])
        if proc.returncode != 0:
            detail = tail.strip() or out.strip() or "bridge exited with error"
            raise BridgeError(detail + (f"\n[bridge log tail]\n{tail}" if tail else ""))
        return out.strip()
    finally:
        if not stopped.is_set():
            proc.kill()
            proc.wait()
            stopped.set()


def detect_usb():
    return json.loads(_run(["detect"]))


def detect_all():
    """All USB devices (any VID) - lets the GUI see non-Samsung targets like
    Qualcomm modems that are not in EDL mode."""
    return json.loads(_run(["detect-all"]))


def detect_mtk():
    """MediaTek low-level USB devices (BROM/preloader/DA) - VID 0x0e8d."""
    return json.loads(_run(["mtk-detect"]))


def mtk_scatter_gpt(da, out_file, timeout=600):
    """Generate an SP Flash Tool scatter file from the device's own GPT
    partition table (no scatter file in Samsung firmware needed). Returns the
    bridge's summary string."""
    return _run(["mtk-scatter-gpt", "auto", da, out_file], timeout=timeout)


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


def odin_flash_multi(target, pit_file, specs, reboot=False, timeout=1800):
    """Flash several partition=image pairs in ONE native Odin session using the
    Rust protocol implementation - no odin4 binary needed. specs is a list of
    (partition, image_file) tuples. Returns the parsed bridge JSON."""
    args = ["odin-flash-multi", target, pit_file, "1" if reboot else "0"]
    for part, img in specs:
        args.append(f"{part}={img}")
    return json.loads(_run(args, timeout=timeout))


def odin_send_pit(target, pit_file, timeout=120):
    """Send a PIT to the device (repartition / re-map partitions)."""
    return _run(["odin-send-pit", target, pit_file], timeout=timeout)


def has_adb():
    return shutil.which("adb") is not None
