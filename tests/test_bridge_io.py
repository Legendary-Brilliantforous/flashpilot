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
