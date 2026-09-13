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
