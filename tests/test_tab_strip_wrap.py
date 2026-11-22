"""Samsung sub-tab strip wrapping regressions.

The Samsung hub used to put every tab in one ``QHBoxLayout``.  Its natural
width was therefore the sum of all tab widths, which made the middle page
wider than its viewport at the minimum window size.  ``SamsungSubTabs`` now
uses the shared wrapping flow layout: its minimum width is the widest single
tab, while narrow pages grow the strip vertically and keep every chip visible.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from python.gui.widgets.controls import SamsungSubTabs


_SAMSUNG_TABS = [
    ("supported", "SUPPORTED DEVICES"),
    ("flash", "ODIN FLASH"),
    ("unlock", "UNLOCK"),
    ("adv", "ADVANCED FLASH"),
    ("tools", "INFO & TOOLS"),
]


@pytest.fixture(scope="module")
def qapp():
    """Provide the shared headless application and tear down its test window."""
    from tests.conftest import build_test_window, destroy_test_window, ensure_qapp

    app = ensure_qapp()
    window = build_test_window()
    try:
        yield app
    finally:
        destroy_test_window(window)


def _settle(app, rounds=12):
    for _ in range(rounds):
        app.processEvents()


def _make_strip():
    return SamsungSubTabs(_SAMSUNG_TABS)


def test_sub_tabs_minimum_width_is_the_widest_tab_not_the_sum(qapp):
    """The strip asks for one tab's width, not the sum of every tab."""
    strip = _make_strip()
    try:
        widths = [button.minimumSizeHint().width()
                  for button in strip._buttons.values()]
        widest = max(widths)
        total = sum(widths)
        minimum = strip.minimumSizeHint().width()

        assert minimum <= widest + 12, (
            f"strip minimum is {minimum}px; widest tab is only {widest}px"
        )
        assert minimum < total / 2, (
            f"strip minimum is {minimum}px; tabs still total {total}px"
        )
    finally:
        strip.deleteLater()


def test_sub_tabs_wrap_onto_a_second_row_when_narrow(qapp):
    """A narrow strip grows vertically and keeps every tab visible."""
    host = QWidget()
    host.setFixedWidth(260)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    strip = _make_strip()
    layout.addWidget(strip)
    host.show()
    _settle(qapp)

    try:
        one_row_height = max(button.height() for button in strip._buttons.values())
        assert strip.height() > one_row_height + 4, (
            f"strip did not wrap: height={strip.height()}px, "
            f"one-row height={one_row_height}px"
        )

        for key, button in strip._buttons.items():
            assert button.isVisible(), f"{key} tab is not visible"
            assert button.geometry().top() >= 0
            assert button.geometry().bottom() < strip.height(), (
                f"{key} tab is clipped below the strip: "
                f"{button.geometry().getRect()} in {strip.height()}px"
            )
    finally:
        host.close()
        host.deleteLater()
        _settle(qapp)


def test_sub_tabs_keep_their_behaviour(qapp):
    """Selection, activation, exclusivity, and the button map are unchanged."""
    strip = _make_strip()
    selected = []
    strip.tab_selected.connect(selected.append)

    try:
        assert set(strip._buttons) == {key for key, _ in _SAMSUNG_TABS}
        assert strip._buttons["supported"].isChecked()
        assert strip._group.exclusive()

        strip._buttons["flash"].click()
        assert selected == ["flash"]

        strip.set_active("flash")
        assert strip._buttons["flash"].isChecked()
        assert not strip._buttons["supported"].isChecked()
    finally:
        strip.deleteLater()
