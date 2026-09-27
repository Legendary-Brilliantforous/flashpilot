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
    # Tests drive _on_device_state with synthetic states directly: the live
    # monitor thread would race them (its next poll emits over the corner
    # mid-assertion — flaky full-suite ordering).
    w._monitor.stop()
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


def test_qcom_corner_shows_adb_overlay(win, monkeypatch):
    """Regression: the top-right corner for a non-EDL Qualcomm device with
    authorized ADB must name the ADB transport (it previously showed only
    the VID:PID line, and stale builds showed MTP)."""
    from python.core import devices as _dev
    from python.core import bridge as _bridge

    # Hermetic: the rebuild's live scan must see exactly this device set
    # (the real bus may hold other hardware whose rows overwrite the
    # synthetic corner).
    _LAST_TEST_STATE["state"] = _dongle_state()
    monkeypatch.setattr(_dev, "list_devices", _fake_list_for_state)
    monkeypatch.setattr(_bridge, "list_merged", _fake_list_for_state)
    win._on_device_state(_dongle_state())
    text = win.conn_state.text()
    assert "05c6:90b4" in text
    assert "ADB" in text and "3588b020" in text, f"corner missing ADB line: {text!r}"
    assert "MTP" not in text


def test_adb_begin_retries_transient_validation_once(win, monkeypatch):
    """_adb_begin: a transient backend refusal (device mid re-enumeration)
    retries once after settling instead of telling the user 'no adb'
    while the monitor shows the device connected."""
    from python.core import bridge as _bridge
    from python.core import devices as _dev
    from python.core import jobs as _jobs
    from python.gui.qt_app import _flow_end

    row = {"key": "adb:FAKE1234", "label": "Fake", "transports": ["ADB"],
           "serial": "FAKE1234",
           "usb": {"vid": 0x18D1, "serial": "FAKE1234"},
           "adb": {"serial": "FAKE1234", "state": "device", "extra": ""}}
    monkeypatch.setattr(_dev, "candidates_for_modes", lambda modes: [row])
    calls = {"n": 0}

    def fake_validate(key, aid):
        calls["n"] += 1
        assert (key, aid) == ("adb:FAKE1234", "adb_shell")
        if calls["n"] == 1:
            raise _bridge.BridgeError("USB error: Device not found")
        return {"allowed": True}

    monkeypatch.setattr(_bridge, "validate_action", fake_validate)
    try:
        serial, key, flux = win._adb_begin("Battery report", "battery_report")
        assert (serial, key) == ("FAKE1234", "adb:FAKE1234")
        assert flux is not None and flux.state == "VALIDATED"
        assert calls["n"] == 2
        _jobs.finish_job(flux.job_id, "CANCELLED", "test", "TEST")
    finally:
        _flow_end(key="adb:FAKE1234")


def test_adb_begin_no_retry_on_settled_refusal(win, monkeypatch):
    """Unsupported-action refusals fail fast (no pointless settle wait)."""
    from python.core import bridge as _bridge
    from python.core import devices as _dev
    from python.gui.qt_app import _flow_end

    row = {"key": "adb:FAKE1234", "label": "Fake", "transports": ["ADB"],
           "serial": "FAKE1234",
           "usb": {"vid": 0x18D1, "serial": "FAKE1234"},
           "adb": {"serial": "FAKE1234", "state": "device", "extra": ""}}
    monkeypatch.setattr(_dev, "candidates_for_modes", lambda modes: [row])
    calls = {"n": 0}

    def fake_validate(key, aid):
        calls["n"] += 1
        raise _bridge.BridgeError("action not supported",
                                  code="ACTION_NOT_SUPPORTED")

    monkeypatch.setattr(_bridge, "validate_action", fake_validate)
    import time as _t

    start = _t.monotonic()
    try:
        assert win._adb_begin("Battery report", "battery_report") == (None, None, None)
    finally:
        _flow_end(key="adb:FAKE1234")
    assert calls["n"] == 1
    assert _t.monotonic() - start < 2.0, "settled refusal must not sleep"


def test_pick_device_retries_empty_once(win, monkeypatch):
    """A scan that misses a re-enumerating device retries once and picks
    it up — tools stop refusing with 'no device' mid-flap."""
    calls = {"n": 0}

    def fake_choose(label, modes):
        calls["n"] += 1
        return None if calls["n"] == 1 else "adb:X"

    monkeypatch.setattr(win, "_choose_device", fake_choose)
    assert win._pick_device("Battery report", "ADB") == "adb:X"
    assert calls["n"] == 2


def test_pick_device_empty_twice_gives_up(win, monkeypatch):
    calls = {"n": 0}

    def fake_choose(label, modes):
        calls["n"] += 1
        return None

    monkeypatch.setattr(win, "_choose_device", fake_choose)
    import time as _t

    start = _t.monotonic()
    assert win._pick_device("Battery report", "ADB") is None
    assert calls["n"] == 2
    assert _t.monotonic() - start >= 2.4


def test_pick_device_cancel_never_retried(win, monkeypatch):
    calls = {"n": 0}

    def fake_choose(label, modes):
        calls["n"] += 1
        return "__cancelled__"

    monkeypatch.setattr(win, "_choose_device", fake_choose)
    assert win._pick_device("Battery report", "ADB") == "__cancelled__"
    assert calls["n"] == 1


def _mtk_composite_state():
    """MediaTek 0e8d:201c with an ADB interface, server-authorized — the
    user's exact device shape."""
    usb_dev = {
        "vid": 0x0E8D, "pid": 0x201C, "bus": 2, "address": 50,
        "product": "TECNO SPARK 8", "manufacturer": "TECNO MOBILE LIMITED",
        "serial": "06977371AD102074", "is_samsung": False,
        "interfaces": [{"class": 255, "subclass": 66, "protocol": 1,
                        "endpoints": []}],
    }
    adb_dev = {"serial": "06977371AD102074", "state": "device", "extra": "transport:usb"}
    return {
        "samsung": [], "mtk": [usb_dev], "hid": [], "adb": [adb_dev],
        "fastboot": [], "edl": [], "qcom": [], "spd": [],
        "apple": [], "other_android": [],
        "mode": "ADB ENABLED (debug composite) - normal boot",
    }


def test_mtk_corner_shows_adb_overlay(win, monkeypatch):
    """Regression: the mtk_devs corner branch never called _adb_overlay —
    a Tecno with authorized ADB showed only 'MediaTek low-level' in the
    top-right corner while ADB Status showed connected."""
    from python.core import devices as _dev
    from python.core import bridge as _bridge

    _LAST_TEST_STATE["state"] = _mtk_composite_state()
    monkeypatch.setattr(_dev, "list_devices", _fake_list_for_state)
    monkeypatch.setattr(_bridge, "list_merged", _fake_list_for_state)
    win._on_device_state(_mtk_composite_state())
    text = win.conn_state.text()
    assert "0e8d:201c" in text
    assert "ADB" in text and "06977371AD102074" in text, f"corner missing ADB line: {text!r}"


def test_adb_begin_server_row_fallback(win, monkeypatch):
    """The exact 'shows connected but actions say no adb' gap: the merged
    pick misses (USB descriptor flap) while the ADB daemon still reports
    the device — the daemon row must be used instead of refusing."""
    from python.core import bridge as _bridge
    from python.core import devices as _dev
    from python.core import jobs as _jobs
    from python.gui.qt_app import _flow_end

    # Both scans miss (flap): candidates empty twice.
    monkeypatch.setattr(_dev, "candidates_for_modes", lambda modes: [])
    # But the daemon reports exactly one authorized device.
    monkeypatch.setattr(_bridge, "adb_status",
                        lambda: [{"serial": "R9XFLAP1", "state": "device",
                                  "extra": ""}])

    def fake_validate(key, aid):
        assert (key, aid) == ("adb:R9XFLAP1", "adb_shell")
        return {"allowed": True}

    monkeypatch.setattr(_bridge, "validate_action", fake_validate)
    try:
        serial, key, flux = win._adb_begin("Battery report", "battery_report")
        assert (serial, key) == ("R9XFLAP1", "adb:R9XFLAP1")
        assert flux is not None
        _jobs.finish_job(flux.job_id, "CANCELLED", "test", "TEST")
    finally:
        _flow_end(key="adb:R9XFLAP1")


def test_adb_begin_server_fallback_multiple_picks(win, monkeypatch):
    """Pick misses + several authorized daemon rows: the daemon-row picker
    appears (never a bare refuse), and dismissing it stops nothing."""
    from python.core import bridge as _bridge
    from python.core import devices as _dev
    from python.core import jobs as _jobs
    from python.gui.qt_app import _flow_end

    monkeypatch.setattr(_dev, "candidates_for_modes", lambda modes: [])
    monkeypatch.setattr(_bridge, "adb_status",
                        lambda: [{"serial": "A1", "state": "device", "extra": ""},
                                 {"serial": "B1", "state": "device", "extra": ""}])
    monkeypatch.setattr(win, "_pick_stop_target",
                        lambda keys: "__cancelled__")

    def boom(key, aid):  # pragma: no cover
        raise AssertionError("must not validate after dismissal")

    monkeypatch.setattr(_bridge, "validate_action", boom)
    try:
        assert win._adb_begin("Battery report", "battery_report") == (None, None, None)
    finally:
        _flow_end(key=None)


def test_adb_begin_server_fallback_zero_warns(win, monkeypatch):
    from python.core import bridge as _bridge
    from python.core import devices as _dev
    from python.gui.qt_app import _flow_end

    monkeypatch.setattr(_dev, "candidates_for_modes", lambda modes: [])
    monkeypatch.setattr(_bridge, "adb_status", lambda: [])

    try:
        assert win._adb_begin("Battery report", "battery_report") == (None, None, None)
    finally:
        _flow_end(key=None)


def _fake_list_for_state(_unused=None):
    """Merged rows for whatever synthetic state the test drives: the
    monitor's per-category devices become rows (hermetic list_devices /
    list_merged stand-in — the real bridge sees only the physical bus)."""
    try:
        st = _LAST_TEST_STATE["state"]
    except (NameError, KeyError):
        return []
    rows = []
    seen = set()
    for cat in ("samsung", "mtk", "qcom", "spd", "apple", "other_android"):
        for d in (st.get(cat) or []):
            if not isinstance(d, dict):
                continue
            key = f"adb:{d['serial']}" if d.get("serial") else (
                f"usb:{d.get('vid', 0):04x}:{d.get('pid', 0):04x}"
                f"@{d.get('bus')}:{d.get('address')}")
            if key in seen:
                continue
            seen.add(key)
            adb = next((a for a in (st.get("adb") or [])
                        if isinstance(a, dict) and a.get("serial") == d.get("serial")), None)
            rows.append({
                "key": key,
                "label": f"{d.get('product', 'USB')} · {d.get('serial', '')} · "
                         f"{d.get('vid', 0):04x}:{d.get('pid', 0):04x}",
                "transports": ["ADB"] if adb else ["USB"],
                "serial": d.get("serial"),
                "usb": d,
                "adb": adb,
            })
    return rows


_LAST_TEST_STATE = {"state": {}}


def _two_device_state():
    """Tecno (MTK+ADB) + dongle (QCOM+ADB), both server-authorized."""
    tecno = {
        "vid": 0x0E8D, "pid": 0x201C, "bus": 2, "address": 50,
        "product": "TECNO SPARK 8", "manufacturer": "TECNO MOBILE LIMITED",
        "serial": "06977371AD102074", "is_samsung": False,
        "interfaces": [{"class": 255, "subclass": 66, "protocol": 1,
                        "endpoints": []}],
    }
    dongle = {
        "vid": 0x05C6, "pid": 0x90B4, "bus": 1, "address": 57,
        "product": "Android", "manufacturer": "Android",
        "serial": "3588b020", "is_samsung": False,
        "interfaces": [{"class": 255, "subclass": 66, "protocol": 1,
                        "endpoints": []}],
    }
    adb = [
        {"serial": "06977371AD102074", "state": "device", "extra": ""},
        {"serial": "3588b020", "state": "device", "extra": ""},
    ]
    return {
        "samsung": [], "mtk": [tecno], "hid": [], "adb": adb,
        "fastboot": [], "edl": [], "qcom": [dongle], "spd": [],
        "apple": [], "other_android": [],
        "mode": "ADB ENABLED (debug composite) - normal boot",
    }


def test_two_device_switching_display(win, monkeypatch):
    """Both phones render distinct rows; clicking switches the display."""
    from python.core import devices as _dev
    from python.core import bridge as _bridge

    # Hermetic: the rebuild's list_devices must see BOTH devices (the
    # real bridge only sees what is physically on the bus).
    def fake_list():
        st = _two_device_state()
        rows = []
        for d in st["mtk"] + st["qcom"]:
            key = f"adb:{d['serial']}"
            rows.append({
                "key": key,
                "label": f"{d['product']} · {d['serial']} · "
                         f"{d['vid']:04x}:{d['pid']:04x}",
                "transports": ["ADB"],
                "serial": d["serial"],
                "usb": d,
                "adb": {"serial": d["serial"], "state": "device", "extra": ""},
            })
        return rows

    monkeypatch.setattr(_dev, "list_devices", fake_list)
    monkeypatch.setattr(_bridge, "list_merged", fake_list)
    win._on_device_state(_two_device_state())
    # Both rows present with the ADB overlay on each.
    rows = [win.device_list.item(i) for i in range(win.device_list.count())]
    texts = [r.text() for r in rows]
    assert len(texts) == 2, f"expected 2 rows, got {texts}"
    assert any("TECNO" in t for t in texts), texts
    assert any("3588b020" in t for t in texts), texts
    # Click row 0 → display key switches to its key; click row 1 → other.
    for i in (0, 1):
        win._on_device_picked(rows[i])
        key = win._display_key
        assert key, "no display key after pick"
        # The corner reflects the picked device.
        text = win.conn_state.text()
        assert (key in text) or ("TECNO" in text) or ("3588b020" in text), \
            f"row {i} pick did not switch display: {text!r}"


def test_refresh_retries_when_scan_drops_a_device(win, monkeypatch):
    """The rebuild's second live scan can hit a flap window and drop a
    device the monitor just saw: settle-retry once, then render."""
    from python.core import devices as _dev

    calls = {"n": 0}

    def flaky_list():
        calls["n"] += 1
        rows = fake_two_rows()
        # First scan drops the Tecno (mid re-enumeration); second sees both.
        return rows if calls["n"] >= 2 else rows[:1]

    def fake_two_rows():
        st = _two_device_state()
        return [
            {"key": f"adb:{d['serial']}",
             "label": f"{d['product']} · {d['serial']}",
             "transports": ["ADB"], "serial": d["serial"], "usb": d,
             "adb": {"serial": d["serial"], "state": "device", "extra": ""}}
            for d in st["mtk"] + st["qcom"]
        ]

    monkeypatch.setattr(_dev, "list_devices", flaky_list)
    win._monitor._last_state = _two_device_state()
    win._refresh_device_list()
    assert calls["n"] >= 2, "retry should have fired"
    texts = [win.device_list.item(i).text()
             for i in range(win.device_list.count())]
    assert len(texts) == 2, f"both rows must render after retry: {texts}"


def test_adb_begin_multi_daemon_shows_picker(win, monkeypatch):
    """Pick misses + several authorized daemon rows: the picker appears
    over the daemon rows instead of refusing ('Pick a device' toast)."""
    from python.core import bridge as _bridge
    from python.core import devices as _dev
    from python.core import jobs as _jobs
    from python.gui.qt_app import _flow_end

    monkeypatch.setattr(_dev, "candidates_for_modes", lambda modes: [])
    monkeypatch.setattr(_bridge, "adb_status",
                        lambda: [{"serial": "A1", "state": "device", "extra": ""},
                                 {"serial": "B1", "state": "device", "extra": ""}])
    picked = {}

    def fake_pick_stop(keys):
        picked["keys"] = keys
        return "adb:B1"

    monkeypatch.setattr(win, "_pick_stop_target", fake_pick_stop)

    def fake_validate(key, aid):
        assert (key, aid) == ("adb:B1", "adb_shell")
        return {"allowed": True}

    monkeypatch.setattr(_bridge, "validate_action", fake_validate)
    try:
        serial, key, flux = win._adb_begin("Battery report", "battery_report")
        assert picked["keys"] == ["adb:A1", "adb:B1"]
        assert (serial, key) == ("B1", "adb:B1")
        _jobs.finish_job(flux.job_id, "CANCELLED", "test", "TEST")
    finally:
        _flow_end(key="adb:B1")
