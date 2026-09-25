"""Display gating: buttons enable/disable from backend actions-for.

Runs the real window headless (QT_QPA_PLATFORM=offscreen): registers are
populated at construction, then `bridge.actions_for` is stubbed per test
and `_refresh_gates()` applied. Asserts the enforcement direction —
unsupported actions hidden/disabled, fail-open on backend errors.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def win():
    from PyQt6.QtWidgets import QApplication

    global _qapp
    try:
        _qapp
    except NameError:
        _qapp = QApplication([])
    from python.gui import qt_app as _qt

    w = _qt.FlashPilotWindow()
    assert len(w._gated_buttons) > 100, "gated registry unexpectedly small"
    return w


def _button(win, job=None, mode=None, command=None):
    for ref, j, m, c, _base in win._gated_buttons:
        if job is not None and j != job:
            continue
        if mode is not None and m != mode:
            continue
        if command is not None and c != command:
            continue
        btn = ref()
        if btn is not None:
            return btn
    raise AssertionError(f"no live button job={job} mode={mode} command={command}")


def _drive(win, monkeypatch, key, action_ids=None, error=None):
    from python.core import bridge as _bridge

    def fake_actions_for(k, timeout=30):
        assert k == key
        if error is not None:
            raise error
        return {"key": k, "actions": [{"id": a} for a in (action_ids or [])]}

    monkeypatch.setattr(_bridge, "actions_for", fake_actions_for)
    win._display_key = key
    win._last_device_list_sig = ("test-sig",)
    win._gate_cache = {}
    win._refresh_gates()


def test_frp_hidden_for_edl_without_workflow(win, monkeypatch):
    _drive(win, monkeypatch, "usb:9-9",
           ["qualcomm_edl_flash", "read_device_info", "reboot_device"])
    btn = _button(win, job="Remove FRP", mode="ADB")
    assert btn.isEnabled() is False
    assert "BACKEND" in btn.toolTip()


def test_frp_shown_for_download_with_workflow(win, monkeypatch):
    _drive(win, monkeypatch, "usb:9-9",
           ["samsung_odin_flash", "frp_workflow", "read_device_info"])
    assert _button(win, job="Remove FRP", mode="ADB").isEnabled() is True
    # MDM needs the ADB mechanism: absent here, so hidden.
    assert _button(win, job="Remove MDM", mode="ADB").isEnabled() is False


def test_direct_buttons_follow_protocol(win, monkeypatch):
    _drive(win, monkeypatch, "usb:9-9",
           ["qualcomm_edl_flash", "frp_workflow", "read_device_info"])
    assert _button(win, command="qcom-flash").isEnabled() is True
    assert _button(win, command="mtk-flash").isEnabled() is False
    assert _button(win, command="spd-flash").isEnabled() is False
    assert _button(win, command="qcom-frp-reset").isEnabled() is True


def test_fail_open_on_backend_error(win, monkeypatch):
    from python.core.bridge import BridgeError

    _drive(win, monkeypatch, "usb:9-9", error=BridgeError("no bridge"))
    assert _button(win, job="Remove FRP", mode="ADB").isEnabled() is True
    assert _button(win, command="mtk-flash").isEnabled() is True


def test_fail_open_without_selection(win, monkeypatch):
    from python.core import bridge as _bridge

    called = []

    def fake_actions_for(k, timeout=30):  # pragma: no cover
        called.append(k)
        return {"key": k, "actions": []}

    monkeypatch.setattr(_bridge, "actions_for", fake_actions_for)
    win._display_key = None
    win._gate_cache = {}
    win._refresh_gates()
    assert called == []
    assert _button(win, job="Remove FRP", mode="ADB").isEnabled() is True


def _dongle_state():
    """Synthetic DeviceMonitor state for a Qualcomm Android modem/dongle
    (05c6:90b4, RNDIS + ADB 255/66/1), ADB authorized via the server."""
    usb_dev = {
        "vid": 0x05C6, "pid": 0x90B4, "bus": 1, "address": 57,
        "product": "Android", "manufacturer": "Android",
        "serial": "3588b020", "is_samsung": False,
        "interfaces": [
            {"class": 224, "subclass": 1, "protocol": 3, "endpoints": []},
            {"class": 10, "subclass": 0, "protocol": 0, "endpoints": []},
            {"class": 255, "subclass": 0, "protocol": 0, "endpoints": []},
            {"class": 255, "subclass": 66, "protocol": 1, "endpoints": []},
        ],
    }
    adb_dev = {"serial": "3588b020", "state": "device", "extra": "transport:usb"}
    return {
        "samsung": [], "mtk": [], "hid": [], "adb": [adb_dev],
        "fastboot": [], "edl": [], "qcom": [usb_dev], "spd": [],
        "apple": [], "other_android": [],
        "mode": "QUALCOMM DEVICE (modem / normal mode)",
    }


def test_qcom_corner_shows_adb_overlay(win):
    """Regression: the top-right corner for a non-EDL Qualcomm device with
    authorized ADB must name the ADB transport (it previously showed only
    the VID:PID line, and stale builds showed MTP)."""
    win._on_device_state(_dongle_state())
    text = win.conn_state.text()
    assert "05c6:90b4" in text
    assert "ADB" in text and "3588b020" in text, f"corner missing ADB line: {text!r}"
    assert "MTP" not in text
