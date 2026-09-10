"""Native ADB wiring: serial resolution, bridge delegates, EFS pinning."""

from python.core import bridge
from python.core import adb as adb_mod
from python.core import core
from python.core import devices as _dev
from python.core import flow as _flow


def _logs():
    logs = []
    return logs, logs.append


def test_shell_prefers_explicit_serial(monkeypatch):
    seen = {}

    def fake_run(args, timeout=15):
        seen["args"] = args
        return "ok"
    monkeypatch.setattr(bridge, "_run", fake_run)

    bridge.adb_shell("getprop foo", timeout=20, serial="ABC123")
    assert seen["args"][:3] == ["adb-shell", "ABC123", "20000"]


def test_shell_uses_ambient_scope(monkeypatch):
    seen = {}

    def fake_run(args, timeout=15):
        seen["args"] = args
        return "ok"
    monkeypatch.setattr(bridge, "_run", fake_run)

    with _dev.device_scope("adb:XYZ999"):
        bridge.adb_shell("getprop foo")
    assert seen["args"][1] == "XYZ999"


def test_shell_falls_back_to_first_authorized(monkeypatch):
    def fake_status():
        return [
            {"serial": "AAA", "state": "unauthorized", "extra": ""},
            {"serial": "BBB", "state": "device", "extra": ""},
        ]
    monkeypatch.setattr(bridge, "adb_status", fake_status)

    seen = {}

    def fake_run(args, timeout=15):
        seen["args"] = args
        return "ok"
    monkeypatch.setattr(bridge, "_run", fake_run)

    bridge.adb_shell("getprop foo")
    assert seen["args"][1] == "BBB"


def test_shell_no_device_uses_first_device_legacy(monkeypatch):
    monkeypatch.setattr(bridge, "adb_status", lambda: [])

    seen = {}

    def fake_run(args, timeout=15):
        seen["args"] = args
        return "ok"
    monkeypatch.setattr(bridge, "_run", fake_run)

    bridge.adb_shell("getprop foo")
    assert seen["args"][1] == "-"


def test_pull_requires_authorized(monkeypatch):
    monkeypatch.setattr(bridge, "adb_status", lambda: [])
    try:
        bridge.adb_pull(None, "/sdcard/x", "/tmp/x", timeout=10)
    except bridge.BridgeError as e:
        assert "no authorized" in str(e)
    else:
        raise AssertionError("expected BridgeError")


def test_pull_passes_serial_through(monkeypatch):
    seen = {}

    def fake_run(args, timeout=15):
        seen["args"] = args
        return "pulled 1/1 bytes"
    monkeypatch.setattr(bridge, "_run", fake_run)

    out = bridge.adb_pull("SER1", "/sdcard/x", "/tmp/x", timeout=60)
    assert seen["args"][:4] == ["adb-pull", "SER1", "60000", "/sdcard/x"]
    assert "pulled" in out


def test_adb_module_delegates(monkeypatch):
    monkeypatch.setattr(
        bridge, "adb_status",
        lambda: [{"serial": "Q1", "state": "device", "extra": ""}],
    )
    assert adb_mod.connected_serial() == "Q1"

    monkeypatch.setattr(bridge, "adb_shell", lambda cmd, timeout=20: "  ali\n")
    assert adb_mod.shell("getprop x") == "ali"
    assert adb_mod.getprop("ro.x") == "ali"


def test_has_adb_means_bridge_built():
    assert bridge.has_adb() is True


def test_efs_backup_uses_pinned_pull(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    _flow.clear_cancel()

    def fake_wait(ctx, log, timeout=30):
        ctx["serial"] = "EFS1"
        return True
    monkeypatch.setattr(core, "_wait_for_adb", fake_wait)
    monkeypatch.setattr(bridge, "adb_shell", lambda cmd, timeout=20: "")

    seen = {}

    def fake_pull(serial, remote, local, timeout=300):
        seen.update(serial=serial, remote=remote, local=local)
        open(local, "w").write("efs")
        return "pulled"
    monkeypatch.setattr(bridge, "adb_pull", fake_pull)

    logs, log = _logs()
    assert core.flow_efs_backup().run({"serial": "EFS1"}, log) == [True]
    assert seen["serial"] == "EFS1"
    assert seen["remote"] == "/sdcard/efs_backup.tar"
    assert seen["local"].endswith(".tar")
