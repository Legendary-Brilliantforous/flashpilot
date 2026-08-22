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
    """Base class for all bridge errors."""
    def __init__(self, message: str, code: str = "BRIDGE_ERROR", details: dict = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class BridgeCancelled(BridgeError):
    """Raised when the user hits Stop while a bridge subprocess is running."""
    def __init__(self, message: str = "Operation cancelled by user"):
        super().__init__(message, code="CANCELLED")


class BridgeTimeout(BridgeError):
    """Raised when the bridge operation exceeds the timeout."""
    def __init__(self, message: str, timeout: int):
        super().__init__(message, code="TIMEOUT", details={"timeout_seconds": timeout})


class USBError(BridgeError):
    """USB communication errors (device disconnect, permission, claim failed)."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, code="USB_ERROR", details=details)


class ProtocolError(BridgeError):
    """Protocol-level errors (handshake failed, unexpected response, checksum mismatch)."""
    def __init__(self, message: str, stage: str = None, details: dict = None):
        d = details or {}
        if stage:
            d["stage"] = stage
        super().__init__(message, code="PROTOCOL_ERROR", details=d)


class FirmwareMismatchError(BridgeError):
    """Firmware/model mismatch errors (wrong PIT, wrong scatter, BL downgrade)."""
    def __init__(self, message: str, expected: str = None, actual: str = None, details: dict = None):
        d = details or {}
        if expected:
            d["expected"] = expected
        if actual:
            d["actual"] = actual
        super().__init__(message, code="FIRMWARE_MISMATCH", details=d)


class BinaryNotFoundError(BridgeError):
    """Required binary not found (odin4, DA, firehose, etc.)."""
    def __init__(self, message: str, binary: str = None, paths: list = None):
        d = {}
        if binary:
            d["binary"] = binary
        if paths:
            d["searched_paths"] = paths
        super().__init__(message, code="BINARY_NOT_FOUND", details=d)


class DAError(BridgeError):
    """Download Agent specific errors (auth failed, checksum zero, version mismatch)."""
    def __init__(self, message: str, chip: str = None, hw_code: int = None, details: dict = None):
        d = details or {}
        if chip:
            d["chip"] = chip
        if hw_code:
            d["hw_code"] = f"0x{hw_code:04X}"
        super().__init__(message, code="DA_ERROR", details=d)


class PartitionError(BridgeError):
    """Partition operation errors (not found, read/write failed, size mismatch)."""
    def __init__(self, message: str, partition: str = None, details: dict = None):
        d = details or {}
        if partition:
            d["partition"] = partition
        super().__init__(message, code="PARTITION_ERROR", details=d)


def _classify_bridge_error(stderr: str, args: list) -> BridgeError:
    """Classify bridge stderr output into specific error types."""
    s = stderr.lower()
    # USB errors
    if any(kw in s for kw in ("usb", "libusb", "permission denied", "could not claim", "device not found", "disconnected", "no device")):
        return USBError(stderr.strip())
    # Timeout
    if "timeout" in s or "timed out" in s:
        return BridgeTimeout(stderr.strip(), timeout=0)
    # DA errors
    if "da" in s and any(kw in s for kw in ("checksum", "auth", "download agent", "preloader", "brom")):
        return DAError(stderr.strip())
    # Protocol errors
    if any(kw in s for kw in ("handshake", "ack", "checksum mismatch", "unexpected", "protocol", "invalid response")):
        return ProtocolError(stderr.strip())
    # Firmware mismatch
    if any(kw in s for kw in ("mismatch", "wrong model", "pit", "bl revision", "downgrade", "not match")):
        return FirmwareMismatchError(stderr.strip())
    # Partition errors (check before binary not found to avoid "not found" collision)
    if any(kw in s for kw in ("partition", "gpt", "scatter", "size mismatch")):
        return PartitionError(stderr.strip())
    # Binary not found
    if any(kw in s for kw in ("not found", "no such file", "binary missing", "odin4 not found", "firehose not found")):
        return BinaryNotFoundError(stderr.strip())
    # Generic
    return BridgeError(stderr.strip())


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
        raise BinaryNotFoundError(
            f"rust bridge not built at {BRIDGE}. Run `cargo build --release` first.",
            binary="flashpilot-bridge",
            paths=[str(bridge_path)]
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
                raise BridgeTimeout(f"timed out after {timeout}s", timeout=timeout)
            time.sleep(0.05)
        out_drainer.join()
        stopped.wait(timeout=30)
        drainer.join(timeout=30)
        out = "".join(stdout_lines)
        tail = "\n".join(stderr_lines[-25:])
        if proc.returncode != 0:
            detail = tail.strip() or out.strip() or "bridge exited with error"
            err = _classify_bridge_error(tail, args)
            if isinstance(err, BridgeError) and err.code == "BRIDGE_ERROR":
                # Add log tail for generic errors
                err = BridgeError(detail + (f"\n[bridge log tail]\n{tail}" if tail else ""), code=err.code, details=err.details)
            raise err
        return out.strip()
    finally:
        if not stopped.is_set():
            proc.kill()
            proc.wait()
            stopped.set()


def detect_usb():
    return json.loads(_run(["detect"]))


class OdinSession:
    """Long-lived Odin session multiplexer.

    Some Loke firmwares allow exactly ONE Odin session per download-mode
    entry: after one complete session the bootloader goes deaf until the USB
    device re-enumerates. Spawning a fresh bridge process per command burns
    that budget. The agent (odin-agent) opens the device ONCE and serves
    multiple requests over stdin/stdout JSON lines - matching how real Odin
    works (single process, single session).

    Usage:
        with bridge.OdinSession(target) as s:
            pit = s.cmd("pit-dump", out="/tmp/x.pit")
            model = s.cmd("model")
    """

    def __init__(self, target, timeout=30):
        import subprocess as _sp
        self._proc = _sp.Popen(
            [str(BRIDGE), "odin-agent", str(target)],
            stdin=_sp.PIPE, stdout=_sp.PIPE, stderr=_sp.DEVNULL,
            text=True, bufsize=1,
        )
        ready = self._readline()
        if not ready or ready.get("status") != "ready":
            err = (ready or {}).get("error", "agent did not become ready")
            self.close(kill=True)
            raise BridgeError(f"odin-agent: {err}", details=ready or {})
        self.packet_size = ready.get("packet_size")

    def _readline(self):
        line = self._proc.stdout.readline()
        if not line:
            return None
        try:
            return json.loads(line)
        except ValueError:
            return {"error": f"unparseable agent output: {line!r}"}

    def cmd(self, command, **kw):
        if self._proc.poll() is not None:
            raise BridgeError("odin-agent exited unexpectedly")
        payload = {"cmd": command, **kw}
        try:
            self._proc.stdin.write(json.dumps(payload) + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, ValueError) as e:
            raise BridgeError(f"odin-agent pipe broken: {e}")
        resp = self._readline()
        if resp is None:
            raise BridgeError("odin-agent closed output without response")
        if "error" in resp:
            raise BridgeError(f"odin-agent {command}: {resp['error']}",
                              details=resp)
        return resp

    def close(self, kill=False):
        try:
            if not kill and self._proc.poll() is None:
                try:
                    self._proc.stdin.write('{"cmd":"end"}\n')
                    self._proc.stdin.flush()
                    self._proc.wait(timeout=10)
                    return
                except Exception:
                    pass
            if self._proc.poll() is None:
                self._proc.kill()
                self._proc.wait(timeout=5)
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


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


def with_usb_retry(func, retries=3, delay=2.0):
    """Execute a function with transient USB error retry logic."""
    import time
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            return func()
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if any(k in msg for k in ("timeout", "busy", "transfer", "pipe", "reset", "resource", "bulk")):
                if attempt < retries:
                    time.sleep(delay * attempt)
                    continue
            raise
    raise last_err


def select_flash_engine(has_pit=False, is_samsung=True):
    """Smart selection logic: determine whether native Rust protocol or odin4 is optimal."""
    if is_samsung and has_pit:
        return "native"  # Native Odin protocol preferred (fast, no external binary needed)
    return "odin4"       # Fallback to odin4 for complex tar multi-archive parsing

    return json.loads(_run(args, timeout=timeout))


def odin_send_pit(target, pit_file, timeout=120):
    """Send a PIT to the device (repartition / re-map partitions)."""
    return _run(["odin-send-pit", target, pit_file], timeout=timeout)


def has_adb():
    return shutil.which("adb") is not None


# ---- USB re-enumeration helpers ----------------------------------------

def wait_for_usb_reenumeration(vid: int, pid: int = None, timeout: float = 15.0,
                                interval: float = 0.5) -> dict:
    """
    Wait for a USB device with the given VID (and optional PID) to appear.
    Returns the device dict from detect_all() when found.
    Raises BridgeTimeout if not found within timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for dev in detect_all():
            if dev.get("vid") == vid:
                if pid is None or dev.get("pid") == pid:
                    return dev
        time.sleep(interval)
    raise BridgeTimeout(f"USB device VID={vid:04x}" + (f" PID={pid:04x}" if pid else "") + " not found after re-enumeration", timeout=int(timeout))


def wait_for_mode_switch(from_vid: int, to_vid: int, to_pid: int = None,
                          timeout: float = 30.0) -> dict:
    """
    Wait for a device to switch from one USB mode to another (e.g., Download -> BROM,
    or normal -> EDL). Polls detect_all() until a device with to_vid appears.
    Returns the new device dict.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for dev in detect_all():
            if dev.get("vid") == to_vid:
                if to_pid is None or dev.get("pid") == to_pid:
                    return dev
        time.sleep(0.5)
    raise BridgeTimeout(
        f"Device did not switch from VID={from_vid:04x} to VID={to_vid:04x}"
        + (f" PID={to_pid:04x}" if to_pid else ""),
        timeout=int(timeout)
    )
