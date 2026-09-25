import json
import os
import shutil
import subprocess
import threading
import time
import signal
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


# ---- cooperative cancel (single registry: core/cancel.py) ----------------
# Per-device scopes plus a broadcast bus: request_cancel() with no key stops
# everything (global STOP); request_cancel(key) stops one device. Checks
# consult the scope event OR the broadcast bus. flow.py delegates to the
# same registry, so a GUI Stop trips flow-level checks AND the _run poll
# loop together (previously two desynchronized event sets).
from . import cancel as _cancel_registry


def _cancel_scope_key(key):
    return _cancel_registry._scope_key(key)


def _cancel_event(key):
    return _cancel_registry._event(key)

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
        except OSError:  # noqa: BLE001 - logging must never break a flash
            pass


def request_cancel(key=None):
    return _cancel_registry.request_cancel(key)


def clear_cancel(key=None):
    return _cancel_registry.clear_cancel(key)


def cancel_requested(key=None):
    return _cancel_registry.cancel_requested(key)


def _graceful_terminate(proc, timeout=3.0):
    """Gracefully terminate a process: SIGTERM, wait, then SIGKILL if needed.
    
    This gives the Rust bridge time to cleanly close USB connections and
    disconnect the phone before hard-killing the process.
    """
    if proc.poll() is not None:
        return  # Already terminated
    
    try:
        # Send SIGTERM (graceful shutdown)
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
            return  # Process terminated gracefully
        except subprocess.TimeoutExpired:
            # Process didn't respond to SIGTERM, force kill
            proc.kill()
            proc.wait()
    except OSError:
        # Ignore errors during termination
        pass


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

    cancel_grace = False
    try:
        while True:
            if cancel_requested():
                # Don't burn the one Loke session or yank the USB port.
                # Let the bridge exit its current bulk op with a TERM;
                # a short linger lets its Drop close the handle cleanly and
                # the device stays plugged without re-enumerating.
                cancel_grace = True
                _graceful_terminate(proc, timeout=1.2)
                raise BridgeCancelled("cancelled by user")
            rc = proc.poll()
            if rc is not None:
                break
            if time.monotonic() > deadline:
                _graceful_terminate(proc, timeout=2.0)
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
            _graceful_terminate(proc, timeout=2.0)
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
                except OSError:
                    pass
            try:
                if self._proc.poll() is None:
                    self._proc.kill()
                    self._proc.wait(timeout=5)
            except OSError:
                pass
        except OSError:
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


def list_merged(vid_filter=None, timeout=30):
    """Unified, phone-filtered USB + ADB device rows (Rust core).

    Returns a list of dicts, each: {key, label, transports, vid, pid, bus,
    address, serial, is_adb, adb_state}. Phones and ADB entries are merged by
    serial; classes/modes are classified by the Rust bridge (single source of
    truth under the "Rust core, Python GUI" split).
    """
    args = ["detect-merged"]
    if vid_filter is not None:
        args.append(f"--vid={vid_filter:04x}")
    return json.loads(_run(args, timeout=timeout))


def actions_for(device_key, timeout=30):
    """Backend-authoritative valid action set for one device right now.

    Resolves ``device_key`` (adb:<serial> | usb:<ports> |
    usb:<vid>:<pid>@<bus>:<addr>) to its current transport, builds the
    device profile, runs capability detection and returns
    ``{key, profile, actions}`` where ``actions`` is [{id, display_name,
    description}]. The GUI must offer exactly this set — never decide
    compatibility itself. Raises BridgeError when the device is gone or
    the key is ambiguous.
    """
    if not device_key or not isinstance(device_key, str):
        raise BridgeError("actions_for needs a device key", code="BAD_DEVICE_KEY")
    out = _run(["actions-for", device_key], timeout=timeout)
    try:
        return json.loads(out)
    except ValueError:
        raise BridgeError(f"actions-for returned non-JSON: {out[:200]}")


def validate_action(device_key, action_id, timeout=30):
    """Backend enforcement: is ``action_id`` valid for ``device_key`` now?

    Returns the ``{"allowed": true, ...}`` dict when valid; raises
    BridgeError(code="ACTION_NOT_SUPPORTED") when the backend rejects the
    action — even when the caller is a hand-driven GUI path. Identity
    failures (device gone, ambiguous, bad key) propagate with their own
    codes: those are resolution problems, not capability rejections.
    Runners must call this before executing any destructive flow.
    """
    if not device_key or not isinstance(device_key, str):
        raise BridgeError("validate_action needs a device key", code="BAD_DEVICE_KEY")
    if not action_id or not isinstance(action_id, str):
        raise BridgeError("validate_action needs an action id", code="BAD_ACTION_ID")
    try:
        out = _run(["validate-action", device_key, action_id], timeout=timeout)
    except BridgeError as e:
        low = str(e).lower()
        if any(k in low for k in (
            "not found", "no device", "disconnected", "unparseable",
            "ambiguous target",
        )):
            raise
        raise BridgeError(
            str(e),
            code="ACTION_NOT_SUPPORTED",
            details={"device_key": device_key, "action": action_id},
        )
    try:
        data = json.loads(out)
    except ValueError:
        raise BridgeError(f"validate-action returned non-JSON: {out[:200]}")
    if not isinstance(data, dict) or not data.get("allowed"):
        raise BridgeError(
            f"action {action_id!r} not supported for device {device_key}",
            code="ACTION_NOT_SUPPORTED",
            details={"device_key": device_key, "action": action_id},
        )
    return data


def detect_mtk():
    """MediaTek low-level USB devices (BROM/preloader/DA) - VID 0x0e8d."""
    return json.loads(_run(["mtk-detect"]))


def mtk_scatter_gpt(da, out_file, timeout=600):
    """Generate an SP Flash Tool scatter file from the device's own GPT
    partition table (no scatter file in Samsung firmware needed). Returns the
    bridge's summary string."""
    return _run(["mtk-scatter-gpt", "auto", da, out_file], timeout=timeout)


def mtk_flash_samsung(da, fw_dir, timeout=1800):
    """Flash a Samsung firmware directory (extracted AP/BL/CP/CSC, no scatter)
    via MTK GPT. Caller must extract tar.md5 and decompress .lz4 first."""
    return _run(["mtk-flash-samsung", "auto", da, fw_dir], timeout=timeout)


def mtk_verify_part(target, da, entries, timeout=900):
    """Verify-after-write: read back each partition and SHA-256 compare
    against the source file. ``entries`` is [(partition, file), ...].
    Raises BridgeError listing every MISMATCH."""
    args = ["mtk-verify-part", target, da]
    args += [f"{part}={path}" for part, path in entries]
    return _run(args, timeout=timeout)


def qcom_verify_part(target, entries, timeout=900):
    """Verify-after-write over Firehose: read back each partition and
    SHA-256 compare. ``entries`` is [(partition, file), ...]."""
    args = ["qcom-verify-part", target]
    args += [f"{part}={path}" for part, path in entries]
    return _run(args, timeout=timeout)


def qcom_flash_one(target, partition, image, start_sector, num_sectors, timeout=900):
    """Flash one partition over Firehose (mirrors the qcom-flash-one CLI)."""
    return _run(["qcom-flash-one", target, partition, image,
                 str(start_sector), str(num_sectors)], timeout=timeout)


def mtk_crash_brom(bus_addr, timeout=25):
    """Crash a preloader (0e8d:2000) into the held BootROM (0e8d:0003).

    `bus_addr` is 'bus:address' (e.g. '1:42'), NOT a vid:pid@ target — the
    device re-enumerates with a new address after the crash."""
    return _run(["mtk-crash-brom", bus_addr], timeout=timeout)


def mtk_reset(target, timeout=30):
    """Reset an MTK device in BROM via the reset command."""
    return _run(["mtk-reset", target], timeout=timeout)


def mtk_mem_probe(target, timeout=60):
    """Probe BROM readable memory windows (read16/write16/write32/reset)."""
    return _run(["mtk-mem-probe", target], timeout=timeout)


def mtk_detect_extended(timeout=60):
    """Extended MTK detect (hw/sub codes, operation context)."""
    return json.loads(_run(["mtk-detect-extended"], timeout=timeout))


def mtk_brom_exploit(target, exploit_type, payload=None, timeout=120):
    """Direct BROM exploit dispatch (wires mtk_brom_exploit)."""
    args = ["mtk-brom-exploit", target, exploit_type]
    if payload:
        args.append(payload)
    return _run(args, timeout=timeout)


def mtk_exploit(target, exploit_type, payload=None, timeout=120):
    """BROM exploit (mtk_bypass|kamakiri2|dump_preloader|patch_da|custom)."""
    args = ["mtk-exploit", target, exploit_type]
    if payload:
        args.append(payload)
    return _run(args, timeout=timeout)


def mtk_factory(target, timeout=60):
    """Enter factory/dealer mode on an MTK device."""
    return _run(["mtk-factory", target], timeout=timeout)


def mtk_emergency(timeout=60):
    """Detect MTK emergency/download mode devices."""
    return _run(["mtk-emergency"], timeout=timeout)


def mtk_dealer(target, da_file, timeout=120):
    """Dealer mode (auth, unlock, FRP erase, secure config)."""
    return _run(["mtk-dealer", target, da_file], timeout=timeout)


def mtk_emergency_mode(target, da_file, timeout=300):
    """Emergency mode (full partition access) with a DA file."""
    return _run(["mtk-emergency-mode", target, da_file], timeout=timeout)


def qcom_detect(timeout=30):
    """Detect Qualcomm EDL devices (05c6:9008)."""
    return _run(["qcom-detect"], timeout=timeout)


def qcom_sahara(target, timeout=60):
    """Sahara handshake with a Qualcomm EDL device."""
    return _run(["qcom-sahara", target], timeout=timeout)


def qcom_info(target, timeout=60):
    """Device info via Sahara."""
    return _run(["qcom-info", target], timeout=timeout)


def qcom_partitions(target, timeout=120):
    """Partition table via Firehose."""
    return _run(["qcom-partitions", target], timeout=timeout)


def qcom_backup(target, programmer, out_dir, timeout=900):
    """Backup partitions via Firehose."""
    return _run(["qcom-backup", target, programmer, out_dir], timeout=timeout)


def qcom_reboot(target, mode, timeout=60):
    """Reboot a Qualcomm device (normal|edl|recovery|fastboot)."""
    return _run(["qcom-reboot", target, mode], timeout=timeout)


def qcom_frp_reset(target, timeout=300):
    """FRP reset on a Qualcomm EDL device."""
    return _run(["qcom-frp-reset", target], timeout=timeout)


def spd_detect(timeout=30):
    """Detect Spreadtrum/UNISOC download devices."""
    return _run(["spd-detect"], timeout=timeout)


def spd_info(target, timeout=60):
    """Full SPD device info (read-only, safe)."""
    return _run(["spd-info", target], timeout=timeout)


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


def fastboot_devices(timeout=15):
    """List USB devices exposing a native fastboot interface.

    Returns [{vid, pid, bus, address, serial, product, interface}] with
    vid/pid as lowercase hex strings. Powers the target-pinned native
    fastboot path (multi-device safe, no system fastboot binary needed)."""
    return json.loads(_run(["fastboot-devices"], timeout=timeout))


def fastboot_cmd(target, args, timeout_ms=20000, timeout=30):
    """Run one raw fastboot command (getvar/oem/erase/reboot) on an explicit
    ``vid:pid@bus:addr`` target via the native Rust transport.

    Returns the system-fastboot-style transcript (``(bootloader) ...`` lines
    + ``OKAY [...]`` / ``FAILED (remote: ...)``). A device-side FAIL is
    rendered in-output with exit 0 (like the system binary); transport
    failures raise BridgeError."""
    if isinstance(args, str):
        args = [args]
    return _run(
        ["fastboot-cmd", target, str(timeout_ms), *args],
        timeout=timeout,
    )


def pit_parse(pit_file, timeout=30):
    """Parse a Samsung PIT file via the native Rust engine.

    Returns {model, unknown, project, reserved, style, entries[{index,
    binary_type, device_type, identifier, attributes, update_attributes,
    block_size, block_count, file_offset, file_size, name, flash_filename,
    delta_filename}]}. Raises BridgeError on bad magic/truncation."""
    return json.loads(_run(["pit-parse", pit_file], timeout=timeout))


def pit_health(pit_file, timeout=30):
    """PIT forensic verdict via the native Rust engine. Always returns
    {verdict, summary, findings[{severity, code, message}], stats} —
    a corrupt table is a `fail` verdict, never an error."""
    return json.loads(_run(["pit-health", pit_file], timeout=timeout))


def pit_find(pit_file, name, timeout=30):
    """One PIT entry dict by name (or None). Never errors on a missing
    name; bad magic still raises like parse."""
    return json.loads(_run(["pit-find", pit_file, name], timeout=timeout))


def pit_model(pit_file, timeout=30):
    """PIT header strings {model, unknown, project, reserved} with no
    magic validation (mirrors parse_model)."""
    return json.loads(_run(["pit-model", pit_file], timeout=timeout))


def pit_overlaps(pit_file, timeout=30):
    """Overlap pairs {all: [[a, b, blocks]], significant: [...]}."""
    return json.loads(_run(["pit-overlaps", pit_file], timeout=timeout))


def pac_parse(pac_file, timeout=60):
    """Parse an SPD PAC container via the native Rust engine.

    Returns {path, count, flash_size, entries[{index, name, size, is_nv,
    checksum, data_offset}], total_payload}. Raises BridgeError on bad
    magic/truncation."""
    return json.loads(_run(["pac-parse", pac_file], timeout=timeout))


def pac_extract(pac_file, out_dir, timeout=300):
    """Extract PAC payloads via the native Rust engine. Returns [paths]."""
    return json.loads(_run(["pac-extract", pac_file, out_dir], timeout=timeout))


def pac_pack(in_dir, out_pac, product="", timeout=300):
    """Pack a folder into a PAC via the native Rust engine. Returns path."""
    args = ["pac-pack", in_dir, out_pac]
    if product:
        args.append(product)
    return _run(args, timeout=timeout).strip()


def boot_info(image_path, timeout=60):
    """Android boot image header + prop-file list via the native engine."""
    return json.loads(_run(["boot-info", image_path], timeout=timeout))


def boot_patch_adb(in_img, out_img, timeout=300):
    """Patch a boot image ramdisk for ADB via the native engine.

    Returns {kernel_size, ramdisk_size, page_size, ramdisk_offset,
    ramdisk_old, ramdisk_new, grew_by, patched_files, recompressed}."""
    return json.loads(_run(["boot-patch-adb", in_img, out_img], timeout=timeout))


def vbmeta_patch(in_img, out_img, flags=0x03, timeout=60):
    """Set AVB flags via the native engine. Returns {patched, size[, flags]}."""
    return json.loads(
        _run(["vbmeta-patch", in_img, out_img, f"0x{flags:x}"], timeout=timeout)
    )


def _free_adb_interface(err_str: str) -> bool:
    """When the native ADB claim fails with "Resource busy", the system adb
    server (or another process) is holding the phone's interface - our
    native bridge cannot coexist with an exclusive claim. Kill the system
    adb server (a HOST-side op, not device I/O) so the native transport can
    claim it. Returns True when a kill was attempted.

    Callers must be deliberate user-initiated operations ONLY. This must
    never run from the passive GUI poll: the dying adb server makes the
    phone's adbd reset its USB function (re-enumeration at a new address)
    every time, which is the exact address-churn + "never shows connected"
    flap users report."""
    import subprocess as _sp
    low = (err_str or "").lower()
    if "busy" not in low:
        return False
    try:
        _sp.run(["adb", "kill-server"], capture_output=True, timeout=10)
        # The dying adb process releases its usbfs claim asynchronously -
        # a retry issued instantly hits "Input/Output Error" (the kernel
        # hasn't finished teardown). Let it settle first.
        import time as _t
        _t.sleep(1.5)
        # NO usb-reset here: after kill-server the phone's adbd resets its
        # USB function itself (known adb behavior on client disconnect) and
        # re-enumerates - a forced reset during that window triggers another
        # reset (crash loop). Wait for the adbd reset + fresh enumeration to
        # settle instead; the serial-pinned retry re-resolves the address.
        _t.sleep(3.0)
        return True
    except Exception:
        return False


def adb_devices():
    """Native `adb-devices` row list (the busy-holder rescue lives on the
    Rust side and in `adb_shell` for user-initiated operations only).

    The busy state is returned as an honest state LINE (not an error) so
    the GUI surfaces it. NO kill-server here: this runs on every GUI poll,
    and killing the system adb server made phones re-enumerate at a new
    address on every cycle."""
    return json.loads(_run(["adb-devices"]))


def adb_presence():
    """Zero-touch ADB presence for poll/monitor/display paths.

    Same row contract as `adb_devices` but the Rust side never opens,
    claims or handshakes USB (`adb-devices --no-probe`): system-server rows
    plus `unknown`-state rows for descriptor-triple devices. Native
    claim/CNXN cycles from a poll loop reset fragile hardware (USB modems
    re-enumerate every cycle and never stabilize) — presence must not
    touch. Flows and explicit operations keep verified `adb_status()` and
    per-command native verification.
    """
    return json.loads(_run(["adb-devices", "--no-probe"]))


def _parse_adb_lines(lines):
    """Parse `SERIAL state extras` rows into {serial, state, extra} dicts."""
    devs = []
    for line in (lines or []):
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        devs.append({
            "serial": parts[0],
            "state": parts[1],
            "extra": parts[2] if len(parts) > 2 else "",
        })
    return devs


def adb_status():
    """Parsed `adb devices -l`: list of {serial, state, extra}.
    state is 'device' (authorized), 'unauthorized', 'offline', 'recovery', ...

    Verified listing (native probe for server-unknown serials): for flows
    and explicit operations. Poll/monitor/display paths must use
    `adb_presence_status()` instead — verification claims interfaces and
    handshakes, which re-enumerates fragile hardware every cycle."""
    import time as _t
    devs = []
    lines = None
    last = None
    for attempt in range(3):
        try:
            lines = adb_devices()
            break
        except BridgeError as e:
            last = e
            _t.sleep(1.5)
    if lines is None:
        if last is not None:
            raise last
        return devs
    return _parse_adb_lines(lines)


def adb_presence_status():
    """Parsed zero-touch presence: list of {serial, state, extra} where
    state may be 'unknown' (triple present on USB, server has no row, never
    probed natively). For poll/monitor/display paths ONLY — never for
    authorization decisions or flow gating (use verified `adb_status`)."""
    return _parse_adb_lines(adb_presence())


def _ambient_adb_serial():
    """Serial from the ambient device scope (GUI device picker), else ''."""
    try:
        from . import devices as _dev

        key = _dev.current_key()
    except (ImportError, AttributeError):
        return ""
    if isinstance(key, str) and key.startswith("adb:"):
        return key[4:]
    return ""


def _resolve_adb_serial(serial=None, need_authorized=False):
    """Explicit serial > ambient scope > single authorized device.

    Pull/push set need_authorized=True and raise BridgeError when no
    authorized device exists (fail before touching the filesystem). Shell
    falls back to '-' (first device) ONLY when exactly one authorized
    device is present; with several authorized devices and no scope, the
    target is ambiguous and this raises instead of silently commanding
    the wrong phone."""
    if serial:
        return serial
    ambient = _ambient_adb_serial()
    if ambient:
        return ambient
    try:
        authorized = [d for d in adb_status() if d.get("state") == "device"]
    except BridgeError:
        authorized = []
    if len(authorized) > 1:
        serials = ", ".join(d.get("serial", "?") for d in authorized)
        raise BridgeError(
            f"multiple authorized ADB devices ({serials}): specify a serial",
            code="ADB_AMBIGUOUS_TARGET",
        )
    if authorized:
        return authorized[0]["serial"]
    if need_authorized:
        raise BridgeError("no authorized ADB device", code="ADB_NO_DEVICE")
    return "-"


_host_adb_cache = {"checked": False, "path": None}

# Server-side device states the native backend must judge
# authoritatively (auth/offline/presence): fall through to native so the
# backend — not a stderr sniff — reports them.
_HOST_DEVICE_ERRORS = (
    "not found", "offline", "unauthorized", "no device", "device empty",
    "no emulator", "no devices", "device still connecting",
)


def _host_adb_binary():
    """platform-tools `adb` when present (fallback transport only).

    The native Rust transport stays primary (no platform-tools dependency);
    the host binary is used only to route through the system server when it
    already owns the device's interface.
    """
    if not _host_adb_cache["checked"]:
        _host_adb_cache.update(checked=True, path=shutil.which("adb"))
    return _host_adb_cache["path"]


def _run_host_adb_raw(args, timeout):
    """Run platform-tools adb, polling for cooperative cancel.

    Returns (returncode, stdout, stderr). Raises BridgeTimeout on expiry
    and BridgeCancelled on user stop; spawn failures raise BridgeError
    (caller falls through to native). Remote command failure is NOT an
    exception here — the caller decides by returncode/stderr.
    """
    adb_bin = _host_adb_binary()
    try:
        proc = subprocess.Popen(
            [adb_bin, *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
    except (OSError, ValueError) as e:
        raise BridgeError(f"host adb spawn failed: {e}")
    deadline = time.monotonic() + timeout
    try:
        while True:
            if cancel_requested():
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
                raise BridgeCancelled()
            if proc.poll() is not None:
                out, err = proc.communicate()
                return proc.returncode, out or "", err or ""
            if time.monotonic() > deadline:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
                raise BridgeTimeout(
                    f"host adb {' '.join(args)} timed out after {timeout}s",
                    timeout=int(timeout),
                )
            time.sleep(0.05)
    finally:
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass


def _host_owned_error(stderr):
    """True when the server disclaims the device (native must decide)."""
    low = (stderr or "").lower()
    return any(k in low for k in _HOST_DEVICE_ERRORS)


def _server_shell_for(serial, cmd, timeout):
    """Try one shell via the Rust server transport (zero USB, no binary).

    Returns (True, stdout) on success — verbatim, even on remote nonzero
    exit (native parity). Returns (False, None) when native must decide:
    unpinned serial, daemon down/refused, or any bridge error (including
    the daemon disclaiming the device — our key may differ from the
    server's, so native auth stays authoritative). Timeout/cancel
    propagate.
    """
    if not serial or serial == "-":
        return False, None
    try:
        out = _run(["adb-shell-server", serial, str(int(timeout * 1000)), cmd],
                   timeout=timeout + 10)
    except (BridgeTimeout, BridgeCancelled):
        raise
    except BridgeError:
        return False, None
    return True, out


def _host_shell_for(serial, cmd, timeout):
    """Try one shell command via the system server transport.

    Returns (True, stdout) when the host adb handled it - stdout verbatim,
    even on remote nonzero exit (native-compatible: remote failure text is
    data, not an exception). Returns (False, None) when the caller should
    proceed natively: no binary, unpinned serial, transport failure, or the
    server disclaiming the device.
    """
    if not serial or serial == "-" or _host_adb_binary() is None:
        return False, None
    try:
        rc, out, err = _run_host_adb_raw(["-s", serial, "shell", cmd], timeout)
    except (BridgeTimeout, BridgeCancelled):
        raise
    except BridgeError:
        return False, None
    if rc != 0 and _host_owned_error(err):
        return False, None
    return True, out


def _host_transfer_for(serial, direction, local, remote, timeout):
    """Try one pull/push via the system server transport.

    Returns (True, stdout) only on rc == 0; any nonzero exit (missing
    file, disclaimed device, ...) falls through to native so the backend
    reports authoritatively.
    """
    if direction not in ("pull", "push"):
        return False, None
    if not serial or serial == "-" or _host_adb_binary() is None:
        return False, None
    argv = (["-s", serial, "pull", remote, local] if direction == "pull"
            else ["-s", serial, "push", local, remote])
    try:
        rc, out, err = _run_host_adb_raw(argv, timeout)
    except (BridgeTimeout, BridgeCancelled):
        raise
    except BridgeError:
        return False, None
    if rc != 0:
        return False, None
    return True, out


def adb_shell(cmd, timeout=20, serial=None, rescue=True):
    """Run `adb shell <cmd>` over the native Rust transport.

    Serial pinning (explicit > ambient scope > first authorized) makes
    multi-device ADB safe; previously the system binary picked (or
    errored on) whatever was plugged in.

    Transport order for an explicitly-pinned serial: native Rust transport
    first; on an exclusive-claim fight ("Resource busy" — the system adb
    server or a sibling process holds the interface), delegate to the
    server transport instead of evicting it. Killing the server to force a
    claim resets fragile hardware (USB modems re-enumerate every cycle),
    so the kill only remains as a last resort for deliberate operations.
    ``rescue`` gates that busy-holder kill: leave it True for deliberate
    user-initiated operations; passive GUI polls must pass rescue=False —
    killing the server from the poll loop made phones re-enumerate at a
    new address every cycle."""
    ser = _resolve_adb_serial(serial)
    last = None
    rescued = False
    host_tried = False
    for attempt in range(4):
        try:
            return _run(["adb-shell", ser, str(int(timeout * 1000)), cmd],
                        timeout=timeout + 10)
        except BridgeError as e:
            last = e
            err_l = str(e).lower()
            transient = any(k in err_l for k in (
                "busy", "timed out", "timeout", "input/output error",
                "io error", "no device", "device not found", "pipe", "stall",
            ))
            if not transient:
                raise
            # Busy = an exclusive-claim fight. Delegate once, least-touch
            # first: Rust server transport (daemon, no binary, zero USB),
            # then the host binary (starts the daemon if needed). Evicting
            # the holder (kill-server) resets fragile hardware (USB modems
            # re-enumerate every cycle), so it stays last resort below.
            # Delegate failure falls through to the logic below unchanged.
            if not host_tried and "busy" in err_l and ser != "-":
                host_tried = True
                for _delegate in (_server_shell_for, _host_shell_for):
                    try:
                        handled, out = _delegate(ser, cmd, timeout)
                        if handled:
                            return out
                    except (BridgeTimeout, BridgeCancelled):
                        raise
                    except BridgeError:
                        pass
            # Busy while another holder owns the interface is deterministic
            # for this attempt - without a kill (rescue=False) retrying is
            # pointless churn; fail fast so the caller can fall back.
            if not rescue and "busy" in err_l:
                raise
            # Rescue 1 (once): "Resource busy" = the system adb server holds
            # the interface - kill it (host-side) so the native transport
            # can claim; the usb-reset unwedges the kernel state.
            if not rescued and _free_adb_interface(str(e)):
                rescued = True
                import time as _t
                _t.sleep(1.0)
                continue
            # Transient backoff: right after enumeration the phone's adbd
            # has not re-attached to the USB function yet (EIO on the first
            # bulk) - the system adb server survives this because it polls;
            # we retry with backoff for the same effect.
            import time as _t
            _t.sleep(2.0 * (attempt + 1))
    raise last


def adb_pull(serial, remote, local, timeout=300):
    """Native `adb pull` via the sync service (serial-pinned).

    On an exclusive-claim fight, delegates once to the server transport
    (see `adb_shell`); anything else propagates natively."""
    ser = _resolve_adb_serial(serial, need_authorized=True)
    try:
        return _run(["adb-pull", ser, str(int(timeout * 1000)), remote, local],
                    timeout=timeout + 15)
    except BridgeError as e:
        if "busy" not in str(e).lower() or ser == "-":
            raise
        try:
            handled, out = _host_transfer_for(ser, "pull", local, remote, timeout)
            if handled:
                return out
        except (BridgeTimeout, BridgeCancelled):
            raise
        except BridgeError:
            pass
        raise


def adb_push(serial, local, remote, timeout=300):
    """Native `adb push` via the sync service (serial-pinned).

    On an exclusive-claim fight, delegates once to the server transport
    (see `adb_shell`); anything else propagates natively."""
    ser = _resolve_adb_serial(serial, need_authorized=True)
    try:
        return _run(["adb-push", ser, str(int(timeout * 1000)), local, remote],
                    timeout=timeout + 15)
    except BridgeError as e:
        if "busy" not in str(e).lower() or ser == "-":
            raise
        try:
            handled, out = _host_transfer_for(ser, "push", local, remote, timeout)
            if handled:
                return out
        except (BridgeTimeout, BridgeCancelled):
            raise
        except BridgeError:
            pass
        raise


def bundled_mtk_da_dir():
    """The bundled mtkclient DA containers (V5/V6): repo root/tools/mtk (dev
    tree) or /usr/share/flashpilot/root/tools/mtk (.deb install). Returns ''
    when neither exists."""
    here = Path(__file__).resolve().parent.parent.parent
    for p in (here / "root" / "tools" / "mtk",
              Path("/usr/share/flashpilot/root/tools/mtk")):
        try:
            if (p / "MTK_DA_V5.bin").exists() or (p / "MTK_DA_V6.bin").exists():
                return str(p)
        except OSError:
            continue
    return ""


def mtk_frp_brom(target="auto", timeout=900):
    """FRP bypass for ANY MediaTek device via BROM with NO user-supplied DA:
    the bundled mtkclient DA containers are parsed natively (per-chip DA
    picked by dacode), uploaded (kamakiri2 first on SBC/SLA/DAA-protected
    BROMs) and the lock partitions are erased from the device GPT."""
    da_dir = bundled_mtk_da_dir()
    if not da_dir:
        raise BridgeError(
            "bundled MTK DA containers missing (root/tools/mtk/MTK_DA_V5.bin)",
            code="MTK_NO_BUNDLED_DA",
        )
    return _run(["mtk-frp-brom", target, da_dir], timeout=timeout)


def odin_connect(target, timeout=30):
    return _run(["odin-connect", target], timeout=timeout)


def odin_pit(target, outfile=None, timeout=90):
    args = ["odin-pit", target]
    if outfile:
        args.append(outfile)
    return _run(args, timeout=timeout)


def odin_info(target, pit_file, timeout=90):
    return _run(["odin-info", target, pit_file], timeout=timeout)


# Serializes Odin model probes across threads. Concurrent `odin-model`
# processes contend the same bulk interface and every contender fails with
# "claim iface: Resource busy" - including our own background monitor firing
# while the user clicks Detect. The wait scales with the probe timeout so a
# wedged holder (killed at its own deadline) can never deadlock waiters.
_odin_probe_lock = threading.Lock()


def odin_model(target, timeout=40):
    """Read the device model string over the Odin session probe (0x64/0x01),
    falling back to the 0x69 device-info dump. Returns dict."""
    acquired = _odin_probe_lock.acquire(timeout=timeout + 15)
    try:
        return json.loads(_run(["odin-model", target], timeout=timeout))
    finally:
        if acquired:
            _odin_probe_lock.release()


def with_usb_retry(func, retries=3, delay=2.0):
    """Execute a function with transient USB error retry logic."""
    import time
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            return func()
        except OSError as e:
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


def odin_send_pit(target, pit_file, timeout=120):
    """Send a PIT to the device (repartition / re-map partitions)."""
    return _run(["odin-send-pit", target, pit_file], timeout=timeout)


def has_adb():
    """Native ADB needs only the bridge binary (no platform-tools on PATH)."""
    return BRIDGE.exists()


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
