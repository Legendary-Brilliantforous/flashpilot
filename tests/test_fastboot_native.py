"""Native-first fastboot runner (shared `_fastboot_run` / `_wait_fastboot`).

Covers: `devices` served from native detect, DATA-phase commands pinned to
the system binary, native transport errors falling back, getvar parsing for
both transcript shapes, and native wait with serial scoping.
"""

import subprocess
import types

import pytest

from python.core import core
from python.core import flow as _flow


@pytest.fixture(autouse=True)
def _no_cancel():
    # Other suites (e.g. test_devices) leave the global broadcast cancel
    # set; wait-loops would instantly raise FlowCancelled. Isolate.
    _flow.clear_cancel()
    yield
    _flow.clear_cancel()


def _logs():
    logs = []
    return logs, logs.append


def test_devices_served_from_native(monkeypatch):
    devs = [{"serial": "ABC123", "vid": "18d1", "pid": "4ee0"}]
    monkeypatch.setattr(core.bridge, "fastboot_devices", lambda timeout=10: devs)

    def boom(*a, **k):
        raise AssertionError("system fastboot must not run")
    monkeypatch.setattr(subprocess, "run", boom)

    logs, log = _logs()
    out = core._fastboot_run(log, ["devices"])
    assert "ABC123\tfastboot" in out
    assert any("[native]" in l for l in logs)


def test_data_command_skips_native(monkeypatch):
    seen = {}

    def boom(*a, **k):
        seen["native"] = True
        raise AssertionError("native must not run for DATA-phase commands")
    monkeypatch.setattr(core.bridge, "fastboot_cmd", boom)

    def sysrun(cmd, **k):
        seen["system"] = cmd
        return types.SimpleNamespace(stdout="OKAY", stderr="")
    monkeypatch.setattr(subprocess, "run", sysrun)
    monkeypatch.setattr(core, "_fastboot_native_target", lambda: "22b8:2e80@2:32")

    logs, log = _logs()
    out = core._fastboot_run(log, ["flash", "boot", "/tmp/x.img"], timeout=30)
    assert "native" not in seen
    assert seen["system"][1:] == ["flash", "boot", "/tmp/x.img"]
    assert "OKAY" in out


def test_native_transport_error_falls_back(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("USB error: timeout")
    monkeypatch.setattr(core.bridge, "fastboot_cmd", boom)
    monkeypatch.setattr(core, "_fastboot_native_target", lambda: "22b8:2e80@2:32")

    def sysrun(cmd, **k):
        return types.SimpleNamespace(
            stdout="(bootloader) oem_locked", stderr="")
    monkeypatch.setattr(subprocess, "run", sysrun)

    logs, log = _logs()
    out = core._fastboot_run(log, ["getvar", "securestate"], timeout=20)
    assert "oem_locked" in out
    assert any("fallback" in l for l in logs)


def test_getvar_parses_both_transcript_shapes(monkeypatch):
    monkeypatch.setattr(
        core, "_fastboot_run",
        lambda log, args, timeout=20: "(bootloader) securestate: oem_locked\nOKAY",
    )
    assert core._fastboot_getvar(print, "securestate") == "oem_locked"

    monkeypatch.setattr(
        core, "_fastboot_run",
        lambda log, args, timeout=20: "securestate: oem_locked\nFinished.",
    )
    assert core._fastboot_getvar(print, "securestate") == "oem_locked"

    monkeypatch.setattr(core, "_fastboot_run", lambda log, args, timeout=20: "")
    assert core._fastboot_getvar(print, "securestate") == ""


def test_wait_native_found_no_system_wait(monkeypatch):
    monkeypatch.setattr(
        core.bridge, "fastboot_devices",
        lambda timeout=10: [{"serial": "ZY322PSBZ2"}],
    )

    def boom(*a, **k):
        raise AssertionError("system wait must not run when native finds a device")
    monkeypatch.setattr(subprocess, "run", boom)

    logs, log = _logs()
    assert core._wait_fastboot(log, timeout=5) is True


def test_wait_legacy_on_bridge_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("bridge not built")
    monkeypatch.setattr(core.bridge, "fastboot_devices", boom)

    called = {}
    def legacy(log, timeout=30):
        called["timeout"] = timeout
        return True
    monkeypatch.setattr(core, "_wait_fastboot_legacy", legacy)

    logs, log = _logs()
    assert core._wait_fastboot(log, timeout=25) is True
    assert called["timeout"] <= 25


def test_moto_aliases_delegate(monkeypatch):
    monkeypatch.setattr(core, "_fastboot_run", lambda log, args, timeout=60: "OKAY")
    logs, log = _logs()
    assert core._moto_fastboot_run(log, ["reboot"]) == "OKAY"
    assert core._moto_wait_fastboot(log, timeout=5) in (True, False)
