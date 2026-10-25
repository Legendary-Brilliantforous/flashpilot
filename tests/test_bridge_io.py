"""Tests for the bridge subprocess I/O layer (bridge.py).

Covers the robustness behavior added for the "bridge must not swallow
errors" work: live stderr streaming to the log hook and error messages
that carry the last lines of bridge output.
"""
import os
import subprocess
import sys

import pytest

from python.core import bridge
from python.core import core


def _fake_bridge(tmp_path):
    """A fake bridge executable that emits progress to stderr then exits with
    a chosen code."""
    script = (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "for line in ('[flash] handshake ok', '[flash] super: 10 bytes', 'boom'):\n"
        "    print(line, file=sys.stderr, flush=True)\n"
        "sys.stderr.flush()\n"
        "sys.exit(int(sys.argv[1]) if len(sys.argv) > 1 else 0)\n"
    )
    path = tmp_path / "fake_bridge.py"
    path.write_text(script)
    path.chmod(0o755)
    return str(path)


def test_stderr_is_streamed_to_log_hook(monkeypatch, tmp_path):
    path = _fake_bridge(tmp_path)
    monkeypatch.setattr(bridge, "BRIDGE", path)
    lines = []
    bridge.set_log_hook(lines.append)
    try:
        bridge._run(["0"])
    finally:
        bridge.set_log_hook(None)
    assert "[flash] handshake ok" in lines
    assert "boom" in lines


def test_error_carries_bridge_log_tail(monkeypatch, tmp_path):
    path = _fake_bridge(tmp_path)
    monkeypatch.setattr(bridge, "BRIDGE", path)
    try:
        with pytest.raises(bridge.BridgeError) as exc:
            bridge._run(["1"])
    finally:
        bridge.set_log_hook(None)
    assert "boom" in str(exc.value) or "[flash] handshake ok" in str(exc.value)


def test_success_returns_stdout(monkeypatch, tmp_path):
    script = "#!/usr/bin/env python3\nprint('{\"ok\": true}')\n"
    path = tmp_path / "fake_bridge2.py"
    path.write_text(script)
    path.chmod(0o755)
    monkeypatch.setattr(bridge, "BRIDGE", path)
    assert bridge._run(["0"]) == '{"ok": true}'


def _flow_bridge(tmp_path, code, lines):
    """Fake bridge for flow-run: prints `lines`, then exits with `code`."""
    body = "".join(f"print({line!r})\n" for line in lines)
    script = "#!/usr/bin/env python3\nimport sys\n" + body + f"sys.exit({code})\n"
    path = tmp_path / f"flow_bridge_{code}.py"
    path.write_text(script)
    path.chmod(0o755)
    return str(path)


def test_flow_nonzero_exit_raises_flow_failed(monkeypatch, tmp_path):
    """A non-zero bridge exit is a failure: run() must raise, not return
    quietly (the GUI used to announce success for these)."""
    path = _flow_bridge(
        tmp_path, 7, ["[step] trying", "failed to open /dev/bus/003"])
    monkeypatch.setattr(bridge, "BRIDGE", path)
    core.clear_cancel()
    seen = []
    try:
        with pytest.raises(core.FlowFailed) as exc:
            core._RustFlow("detect", "detect").run({}, seen.append)
    finally:
        core.clear_cancel()
    assert exc.value.exit_code == 7
    assert "exit code 7" in str(exc.value)
    assert "failed to open /dev/bus/003" in str(exc.value)
    assert any("failed to open" in line for line in seen)


def test_flow_clean_exit_returns(monkeypatch, tmp_path):
    path = _flow_bridge(tmp_path, 0, ["[step] ok", "OKAY [ 0.1s]"])
    monkeypatch.setattr(bridge, "BRIDGE", path)
    core.clear_cancel()
    try:
        assert core._RustFlow("detect", "detect").run({}, lambda m: None) is None
    finally:
        core.clear_cancel()


def test_flow_cancellation_still_reports_cancelled(monkeypatch, tmp_path):
    """STOP is not a failure: cancellation keeps raising FlowCancelled even
    when the killed bridge exits non-zero."""
    path = _flow_bridge(tmp_path, 1, ["[error] would fail"])
    monkeypatch.setattr(bridge, "BRIDGE", path)
    core.clear_cancel()
    core.request_cancel()
    try:
        with pytest.raises(core.FlowCancelled):
            core._RustFlow("detect", "detect").run({}, lambda m: None)
    finally:
        core.clear_cancel()


def test_flow_success_gating_rejects_failed_transcript():
    """GUI success gating: only a transcript without failure markers may
    show the green 'completed' toast."""
    from python.gui.qt_app import _flow_failure_markers

    assert _flow_failure_markers(["[step] x", "OKAY [ 0.1s]", "done"]) == []
    # Mid-line mentions are not markers; prefix lines are.
    assert _flow_failure_markers(["hint: it failed before, retry"]) == []
    bad = _flow_failure_markers([
        "  [error] nope",
        "FAILED (remote: nope)",
        "refused: wrong device",
    ])
    assert len(bad) == 3


def test_spd_adb_import_is_safe_and_refuses():
    """The GUI's SPD ADB button imports this module; it must never raise
    ImportError and must never pretend a boot patch was written."""
    import importlib

    mod = importlib.import_module("python.core.spd_adb")
    assert mod.SUPPORTED is False
    assert "Nothing was written" in mod.UNAVAILABLE_REASON
    with pytest.raises(NotImplementedError) as exc:
        mod.enable_adb_via_boot_patch(
            object(), "1:2", "/tmp/fdl1", 0x40004000,
            fdl2=None, part="boot", log=lambda m: None)
    assert "Nothing was written" in str(exc.value)
    assert "USB debugging" in str(exc.value)


def test_missing_bridge_raises_clear_error(monkeypatch):
    monkeypatch.setattr(bridge, "BRIDGE", "/nonexistent/flashpilot-bridge")
    with pytest.raises(bridge.BridgeError) as exc:
        bridge._run(["detect"])
    assert "rust bridge not built" in str(exc.value)


def test_odin_model_probes_are_serialized(monkeypatch):
    """Concurrent odin_model calls must not overlap: overlapping probes
    contend the same bulk interface and all fail EBUSY (regression test
    for FUS Detect colliding with the background monitor probe)."""
    import threading
    import time

    in_flight = 0
    max_in_flight = 0
    guard = threading.Lock()

    def fake_run(args, timeout=40):
        nonlocal in_flight, max_in_flight
        assert args[0] == "odin-model"
        with guard:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        time.sleep(0.2)
        with guard:
            in_flight -= 1
        return '{"model": "SM-A145M"}'

    monkeypatch.setattr(bridge, "_run", fake_run)
    threads = [
        threading.Thread(target=bridge.odin_model, args=("t", 5))
        for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert all(not t.is_alive() for t in threads)
    assert max_in_flight == 1


def test_odin_model_waits_for_inflight_probe(monkeypatch):
    """A second probe must wait for (not barge into) an in-flight one:
    hold the lock, start a probe, assert its `_run` is not entered while
    held, then release and assert it completes."""
    import threading
    import time

    entered = threading.Event()

    def fake_run(args, timeout=40):
        entered.set()
        return '{"model": "SM-A145M"}'

    monkeypatch.setattr(bridge, "_run", fake_run)
    assert bridge._odin_probe_lock.acquire(blocking=False)
    try:
        done = []
        t = threading.Thread(
            target=lambda: done.append(bridge.odin_model("t", 30)))
        t.start()
        time.sleep(1.0)
        assert not entered.is_set(), "probe barged into a held lock"
        assert t.is_alive()
    finally:
        bridge._odin_probe_lock.release()
    t.join(timeout=30)
    assert done == [{"model": "SM-A145M"}]


def test_list_merged_wraps_detect_merged(monkeypatch):
    """list_merged() shells out to `detect-merged` and parses merged rows."""
    calls = []

    def fake_run(args, timeout=30):
        calls.append(list(args))
        return '[{"key":"adb:R9X","label":"Samsung Galaxy · R9X","transports":["ADB"],"vid":1256,"pid":26717,"bus":1,"address":2,"serial":"R9X","is_adb":true,"adb_state":"device"}]'

    monkeypatch.setattr(bridge, "_run", fake_run)
    rows = bridge.list_merged()
    assert rows[0]["key"] == "adb:R9X"
    assert rows[0]["transports"] == ["ADB"]
    assert calls == [["detect-merged"]]


def test_list_merged_passes_vid_filter(monkeypatch):
    captured = []

    def fake_run(args, timeout=30):
        captured.append(list(args))
        return "[]"

    monkeypatch.setattr(bridge, "_run", fake_run)
    bridge.list_merged(vid_filter=0x04E8)
    assert captured[-1] == ["detect-merged", "--vid=04e8"]
