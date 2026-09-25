"""Native ADB wiring: serial resolution, bridge delegates, EFS pinning."""

import pytest

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


def test_shell_multiple_authorized_without_scope_raises(monkeypatch):
    """Two authorized ADB phones and no explicit/ambient serial must NOT
    silently command the first one (wrong-device operation)."""
    from python.core.bridge import BridgeError

    def fake_status():
        return [
            {"serial": "AAA", "state": "device", "extra": ""},
            {"serial": "BBB", "state": "device", "extra": ""},
        ]
    monkeypatch.setattr(bridge, "adb_status", fake_status)

    def fail_run(args, timeout=15):  # pragma: no cover
        raise AssertionError("bridge must not be called for ambiguous target")

    monkeypatch.setattr(bridge, "_run", fail_run)

    try:
        bridge.adb_shell("getprop foo")
    except BridgeError as e:
        assert getattr(e, "code", "") == "ADB_AMBIGUOUS_TARGET"
    else:  # pragma: no cover
        raise AssertionError("expected ADB_AMBIGUOUS_TARGET")


def test_shell_multiple_authorized_with_scope_still_works(monkeypatch):
    """The same two phones are fine once the ambient scope pins one."""

    def fake_status():
        return [
            {"serial": "AAA", "state": "device", "extra": ""},
            {"serial": "BBB", "state": "device", "extra": ""},
        ]
    monkeypatch.setattr(bridge, "adb_status", fake_status)

    seen = {}

    def fake_run(args, timeout=15):
        seen["args"] = args
        return "ok"
    monkeypatch.setattr(bridge, "_run", fake_run)

    with _dev.device_scope("adb:BBB"):
        bridge.adb_shell("getprop foo")
    assert seen["args"][1] == "BBB"


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


def test_adb_devices_never_kills_server_on_busy(monkeypatch):
    """adb_devices() is the passive GUI poll path: a busy line (system adb
    server holds the interface) must be surfaced honestly, NOT rescued with
    kill-server - the dying server makes phones re-enumerate at a new
    address on every poll."""
    monkeypatch.setattr(
        bridge, "_run",
        lambda args, timeout=15:
            '["SER1\\tbusy (system adb server holds this interface) transport:usb"]',
    )

    def _no_kill(err_str):
        raise AssertionError("adb_devices must not kill-server on the poll path")

    monkeypatch.setattr(bridge, "_free_adb_interface", _no_kill)
    lines = bridge.adb_devices()
    assert any("busy" in l for l in lines)


def test_adb_status_never_kills_server_on_busy(monkeypatch):
    """adb_status() retries transient failures but must never rescue with
    kill-server (passive poll path - re-enumeration churn)."""
    calls = {"n": 0}

    def fake_run(args, timeout=15):
        calls["n"] += 1
        raise bridge.BridgeError("claim_interface: Resource busy - held")

    monkeypatch.setattr(bridge, "_run", fake_run)

    def _no_kill(err_str):
        raise AssertionError("adb_status must not kill-server on the poll path")

    monkeypatch.setattr(bridge, "_free_adb_interface", _no_kill)
    import time as _t
    monkeypatch.setattr(_t, "sleep", lambda s: None)
    try:
        bridge.adb_status()
    except bridge.BridgeError:
        pass
    assert calls["n"] >= 1


def test_adb_shell_busy_rescue_gated(monkeypatch):
    """rescue=False (passive poll timers): busy is deterministic while the
    system adb server holds the interface - must fail fast (one attempt,
    no kill, no retry churn)."""
    calls = {"n": 0}

    def fake_run(args, timeout=15):
        assert args[0] == "adb-shell", "only the shell op should run"
        calls["n"] += 1
        raise bridge.BridgeError("claim_interface: Resource busy - held")

    monkeypatch.setattr(bridge, "_run", fake_run)
    monkeypatch.setattr(
        bridge, "adb_status",
        lambda: [{"serial": "SER1", "state": "device", "extra": ""}],
    )

    def _no_kill(err_str):
        raise AssertionError("rescue=False must not kill-server")

    monkeypatch.setattr(bridge, "_free_adb_interface", _no_kill)
    try:
        bridge.adb_shell("getprop ro.product.model", timeout=8, rescue=False)
    except bridge.BridgeError as e:
        assert "busy" in str(e).lower()
    else:
        raise AssertionError("expected BridgeError")
    assert calls["n"] == 1


def test_adb_shell_busy_rescue_kills_once_when_enabled(monkeypatch):
    """rescue=True (user-initiated operations): the busy-holder kill runs
    exactly once, then the retry succeeds over the native transport."""
    import time as _t

    calls = {"n": 0}
    kills = {"n": 0}

    def fake_run(args, timeout=15):
        assert args[0] == "adb-shell", "only the shell op should run"
        calls["n"] += 1
        if calls["n"] == 1:
            raise bridge.BridgeError("claim_interface: Resource busy - held")
        return "ok"

    monkeypatch.setattr(bridge, "_run", fake_run)
    monkeypatch.setattr(
        bridge, "adb_status",
        lambda: [{"serial": "SER1", "state": "device", "extra": ""}],
    )

    def fake_kill(err_str):
        assert "busy" in (err_str or "").lower()
        kills["n"] += 1
        return True

    monkeypatch.setattr(bridge, "_free_adb_interface", fake_kill)
    monkeypatch.setattr(_t, "sleep", lambda s: None)
    assert bridge.adb_shell("getprop ro.product.model", timeout=8) == "ok"
    assert kills["n"] == 1
    assert calls["n"] == 2


def test_monitor_backs_off_after_dry_native_probes(monkeypatch):
    """DeviceMonitor: when the native handshake keeps coming up dry while
    the USB bus still sees ADB-capable hardware, every re-probe is another
    CNXN - on adbd-reset-on-CNXN devices each retry causes another USB
    re-enumeration (the address storm). The monitor must stop probing for
    a backoff window instead of hammering every poll."""
    import time

    from python.gui.qt_app import DeviceMonitor

    calls = {"n": 0}
    fake_dev = {
        "vid": 0x18D1, "pid": 0x4EE7, "bus": 1, "address": 2,
        "interfaces": [{"class": 255, "subclass": 66, "protocol": 1,
                        "endpoints": []}],
        "is_samsung": False, "product": "Pixel", "manufacturer": "Google",
        "serial": "SER1", "mode": "android-adb",
    }
    monkeypatch.setattr(bridge, "detect_all", lambda: [fake_dev])
    monkeypatch.setattr(bridge, "list_samsung_hid", lambda: "[]")

    def fake_status():
        calls["n"] += 1
        return []  # dry probe (device resets on our CNXN)

    # The monitor probes presence (zero-touch), not verified status.
    monkeypatch.setattr(bridge, "adb_presence_status", fake_status)

    m = DeviceMonitor(interval=0.05)
    m.start()
    try:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and calls["n"] < 2:
            time.sleep(0.05)
        assert calls["n"] >= 2, "two dry probes should have happened"
        window = calls["n"]
        time.sleep(1.0)  # well within the 45s backoff
        assert calls["n"] == window, "probes must stop during the backoff"
    finally:
        m.stop()


def test_bundled_mtk_da_dir_resolves(monkeypatch, tmp_path):
    """bundled_mtk_da_dir(): repo root/tools/mtk when the containers exist,
    else '' — the mtk-frp-brom flow refuses to run without them."""
    from python.core import bridge as _b
    from pathlib import Path as _Path

    real_root = _Path(__file__).resolve().parent.parent / "root" / "tools" / "mtk"
    if (real_root / "MTK_DA_V5.bin").exists():
        assert _b.bundled_mtk_da_dir() == str(real_root)
    else:
        # Repo without the bundled containers: empty dir is reported honestly
        # (never a fabricated path).
        assert _b.bundled_mtk_da_dir() == "" or "tools/mtk" in _b.bundled_mtk_da_dir()


def test_bundled_mtk_da_dir_empty_when_missing(monkeypatch, tmp_path):
    """No containers anywhere -> '' (mtk_frp_brom raises a clear error)."""
    from python.core import bridge as _b
    import python.core.bridge as bridge_mod

    # Point the resolver at an empty tmp tree via monkeypatched Path lookups:
    # simplest is to verify mtk_frp_brom's error path with a stubbed resolver.
    monkeypatch.setattr(bridge_mod, "bundled_mtk_da_dir", lambda: "")
    try:
        _b.mtk_frp_brom("auto")
    except Exception as e:
        assert "bundled" in str(e).lower() or "missing" in str(e).lower()
    else:
        raise AssertionError("expected an error when the bundled DA is missing")


def test_mtk_frp_brom_uses_bundled_dir(monkeypatch):
    """mtk_frp_brom() passes the bundled da_dir through to the bridge."""
    from python.core import bridge as _b
    import python.core.bridge as bridge_mod

    calls = {}

    def fake_run(args, timeout=900):
        calls["args"] = list(args)
        return "ok"

    monkeypatch.setattr(bridge_mod, "_run", fake_run)
    monkeypatch.setattr(bridge_mod, "bundled_mtk_da_dir",
                        lambda: "/opt/mtk-containers")
    _b.mtk_frp_brom("auto")
    assert calls["args"][:3] == ["mtk-frp-brom", "auto", "/opt/mtk-containers"]


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


_FAKE_ADB = """#!/bin/sh
# Fake platform-tools adb for transport-fallback tests.
# FAKE_ADB_MODE=fail makes pull/push exit nonzero (native must decide).
if [ "$1" = "-s" ]; then
  SER="$2"; shift 2
  case "$1" in
    shell)
      shift
      if [ "$SER" = "KNOWNSER" ]; then echo "fake-out:$*"; exit 0; fi
      echo "error: device '$SER' not found" >&2; exit 1;;
    pull|push)
      if [ "$FAKE_ADB_MODE" = "fail" ]; then
        echo "fake-$1: remote object missing" >&2; exit 1
      fi
      echo "fake-$1-ok"; exit 0;;
  esac
fi
echo "error: unknown invocation" >&2; exit 1
"""


class TestHostTransportFallback:
    """Server transport: route through host adb when it owns the device."""

    def _fake_bin(self, tmp_path, monkeypatch):
        import os as _os

        p = tmp_path / "adb"
        p.write_text(_FAKE_ADB)
        _os.chmod(p, 0o755)
        monkeypatch.setenv("PATH", f"{tmp_path}{_os.pathsep}{_os.environ.get('PATH', '')}")
        bridge._host_adb_cache.update(checked=False, path=None)
        return p

    def test_shell_delegates_to_host_on_busy(self, tmp_path, monkeypatch):
        from python.core.bridge import USBError

        self._fake_bin(tmp_path, monkeypatch)
        calls = {"n": 0}

        def busy_once(args, timeout=15):
            calls["n"] += 1
            raise USBError("USB error: Transfer failed: claim_interface: Resource busy")

        monkeypatch.setattr(bridge, "_run", busy_once)
        out = bridge.adb_shell("getprop foo", serial="KNOWNSER")
        assert out == "fake-out:getprop foo\n"
        assert calls["n"] == 1

    def test_shell_native_success_never_touches_host(self, tmp_path, monkeypatch):
        import os as _os

        # No host binary on PATH at all: native success must not need it.
        empty = tmp_path / "emptybin"
        empty.mkdir()
        monkeypatch.setenv("PATH", str(empty))
        bridge._host_adb_cache.update(checked=False, path=None)

        def fake_run(args, timeout=15):
            return "native-ok"

        monkeypatch.setattr(bridge, "_run", fake_run)
        assert bridge.adb_shell("getprop foo", serial="KNOWNSER") == "native-ok"

    def test_shell_falls_through_when_server_disclaims(self, tmp_path, monkeypatch):
        self._fake_bin(tmp_path, monkeypatch)

        seen = {}

        def fake_run(args, timeout=15):
            seen["args"] = args
            return "native-ok"

        monkeypatch.setattr(bridge, "_run", fake_run)
        assert bridge.adb_shell("getprop foo", serial="GHOSTSER") == "native-ok"
        assert seen["args"][:2] == ["adb-shell", "GHOSTSER"]

    def test_shell_remote_failure_text_passes_through(self, tmp_path, monkeypatch):
        # Remote nonzero exit is data, not an exception (native parity).
        # Native goes busy first so the host transport engages.
        from python.core.bridge import USBError

        dest = tmp_path / "adb"
        import os as _os

        dest.write_text(
            "#!/bin/sh\necho 'remote failed hard'\n"
            "echo 'error: closed' >&2\nexit 1\n")
        _os.chmod(dest, 0o755)
        monkeypatch.setenv("PATH", f"{tmp_path}{_os.pathsep}{_os.environ.get('PATH', '')}")
        bridge._host_adb_cache.update(checked=False, path=None)

        def busy_once(args, timeout=15):
            raise USBError("USB error: Transfer failed: claim_interface: Resource busy")

        monkeypatch.setattr(bridge, "_run", busy_once)
        assert bridge.adb_shell("false", serial="KNOWNSER") == "remote failed hard\n"

    def test_host_skipped_without_binary(self, tmp_path, monkeypatch):
        import os as _os

        empty = tmp_path / "emptybin"
        empty.mkdir()
        monkeypatch.setenv("PATH", str(empty))
        bridge._host_adb_cache.update(checked=False, path=None)

        seen = {}

        def fake_run(args, timeout=15):
            seen["args"] = args
            return "native-ok"

        monkeypatch.setattr(bridge, "_run", fake_run)
        assert bridge.adb_shell("getprop foo", serial="KNOWNSER") == "native-ok"
        assert seen["args"][:2] == ["adb-shell", "KNOWNSER"]

    def test_host_skipped_for_unpinned_dash(self, tmp_path, monkeypatch):
        self._fake_bin(tmp_path, monkeypatch)
        monkeypatch.setattr(bridge, "adb_status", lambda: [])

        seen = {}

        def fake_run(args, timeout=15):
            seen["args"] = args
            return "native-ok"

        monkeypatch.setattr(bridge, "_run", fake_run)
        assert bridge.adb_shell("getprop foo") == "native-ok"
        assert seen["args"][1] == "-"

    def test_pull_push_handled_and_fallback(self, tmp_path, monkeypatch):
        from python.core.bridge import USBError

        self._fake_bin(tmp_path, monkeypatch)

        def busy_native(args, timeout=15):
            raise USBError("USB error: Transfer failed: claim_interface: Resource busy")

        monkeypatch.setattr(bridge, "_run", busy_native)
        assert bridge.adb_pull("KNOWNSER", "/r", "/tmp/x_l") == "fake-pull-ok\n"
        assert bridge.adb_push("KNOWNSER", "/tmp/x_l", "/r") == "fake-push-ok\n"

        monkeypatch.setenv("FAKE_ADB_MODE", "fail")

        def busy_native(args, timeout=15):
            raise USBError("USB error: Transfer failed: claim_interface: Resource busy")

        monkeypatch.setattr(bridge, "_run", busy_native)
        # Host nonzero exit falls through; the original busy error propagates
        # (no silent success, no kill-server from here).
        with pytest.raises(USBError, match="[Bb]usy"):
            bridge.adb_pull("KNOWNSER", "/r", "/tmp/x_l")
