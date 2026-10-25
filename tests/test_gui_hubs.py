"""Headless GUI regression tests: the QR Provision entry, the Easy Login hub,
and the model-page action board.

Guards the fixes for:
* the model action board rendering blank (page opacity effect stuck at 0.0
  before the event loop ran) and later mis-rendering offset over the
  console panel,
* QR provisioning scattering three separate DPC tiles: every MDM-via-QR
  surface now exposes ONE "QR Provision" entry that opens a single window.
  That window shows the TestDPC QR large by default and its bottom-left
  dropdown lists only the two optional DPCs (Google Device Policy,
  FlashPilot).

The page builders are exercised with a stub window: they only touch `win`
inside click closures. The real window (which wires every section at
construction, including "easylogin") is covered by test_gates_display.
"""
import inspect
import os
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

# The three per-DPC Easy Login flows (still offered on the Easy Login page).
QR_ACTS = {"frp_fake_login", "frp_fake_login_testdpc", "frp_fake_login_adp"}
# The single router act that opens the shared QR window everywhere else.
QR_ENTRY = "_qr_generator"


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    assert app is not None
    return app


@pytest.fixture()
def win():
    # Only click closures use the window; a stub keeps the tests hermetic
    # (no bridge subprocess threads to race the assertions/teardown).
    return types.SimpleNamespace()


def _panel_acts(widget):
    """The `flow_act` tags carried by QFrame tiles/rows under `widget`."""
    from PyQt6.QtWidgets import QFrame

    got = set()
    for fr in widget.findChildren(QFrame):
        act = fr.property("flow_act")
        if act:
            got.add(act)
    return got


def _motorola_model():
    from python.gui import devices as dp

    models = dp.BRAND_BY_KEY["motorola"]["models"]
    for m in models:
        if "g6" in (m.get("model") or "").lower():
            return m
    return models[0]


class TestQrProvision:
    def test_easylogin_hub_keeps_three_dpcs_and_adds_a_qr_entry(self, qapp, win):
        from python.gui import devices as dp

        # The Easy Login page is deliberately left where it is; it keeps the
        # three per-DPC tiles and also carries the shared QR window entry.
        page = dp.build_easylogin_hub_page(win)
        acts = _panel_acts(page)
        assert QR_ACTS <= acts
        assert QR_ENTRY in acts

    def test_adb_hub_has_a_single_qr_provision_entry(self, qapp, win):
        from python.gui import devices as dp

        page = dp.build_adb_hub_page(win)
        acts = _panel_acts(page)
        assert QR_ENTRY in acts
        assert not (QR_ACTS & acts), "ADB hub still scatters three DPC tiles"

    def test_device_board_has_a_single_qr_provision_row(self, qapp, win, monkeypatch):
        from python.gui import devices as dp

        # Keep it hermetic: the adaptive FRP label probes the live bridge.
        monkeypatch.setattr(dp, "_moto_frp_label", lambda: "FRP Remove")
        page = dp._build_model_page(win, dp.BRAND_BY_KEY["motorola"],
                                    _motorola_model(), back=None)
        acts = _panel_acts(page)
        assert QR_ENTRY in acts
        assert not (QR_ACTS & acts), "device board still scatters three DPC rows"

    def test_qr_window_defaults_to_testdpc_with_two_optional_dpcs(self):
        # The window shows the TestDPC QR large by default; its bottom-left
        # dropdown lists ONLY the two optional DPCs.
        from python.gui.qt_app import FlashPilotWindow

        src = inspect.getsource(FlashPilotWindow._open_qr_generator)
        assert 'setPlaceholderText("TestDPC (default)")' in src
        assert 'addItem("Google Device Policy", "adp")' in src
        assert 'addItem("FlashPilot DPC", "ours")' in src
        # TestDPC is the default shown QR, never a dropdown entry.
        assert 'addItem("TestDPC' not in src
        # Selecting an option re-renders the shown QR.
        assert "activated.connect" in src

    def test_mdm_tab_qr_provisioning_is_one_button(self, qapp):
        from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget
        from python.gui.qt_app import FlashPilotWindow

        host = QWidget()
        lay = QVBoxLayout(host)
        stub = types.SimpleNamespace(_open_qr_generator=lambda: None)
        FlashPilotWindow._add_qr_provisioning(stub, lay)
        btns = [b for b in host.findChildren(QPushButton)
                if "QR Provision" in b.text()]
        assert len(btns) == 1, "MDM tab should expose exactly one QR entry"
        assert btns[0].property("flow_act") == QR_ENTRY

    def test_qr_entry_is_exempt_from_the_transport_gate(self):
        # QR provisioning *creates* the ADB session, so the pre-flight gate
        # must never refuse it for a phone that isn't on ADB yet.
        from python.gui import devices as dp

        for act in QR_ACTS | {QR_ENTRY}:
            assert dp.required_transports(act) is None


class TestModelPage:
    def test_board_renders_rows_and_is_scrollable(self, qapp, win, monkeypatch):
        from PyQt6.QtWidgets import QScrollArea
        from python.gui import devices as dp

        monkeypatch.setattr(dp, "_moto_frp_label", lambda: "FRP Remove")
        page = dp._build_model_page(win, dp.BRAND_BY_KEY["motorola"],
                                    _motorola_model(), back=None)
        assert page.findChildren(QScrollArea), "model board is not scrollable"
        acts = _panel_acts(page)
        assert {"moto_frp", "moto_fb_frp"} <= acts
        # The single QR Provision entry belongs on the device board too.
        assert QR_ENTRY in acts

    def test_no_page_level_opacity_effect(self, qapp, win, monkeypatch):
        # A QGraphicsOpacityEffect on the page hid the whole board (opacity
        # stuck at 0.0) and rendered it offset. It must not come back.
        from python.gui import devices as dp

        monkeypatch.setattr(dp, "_moto_frp_label", lambda: "FRP Remove")
        page = dp._build_model_page(win, dp.BRAND_BY_KEY["motorola"],
                                    _motorola_model(), back=None)
        assert page.graphicsEffect() is None
