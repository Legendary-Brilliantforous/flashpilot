"""Brand-page chip-row width regression tests.

The eight engine chips used to live in a plain ``QHBoxLayout``. Their widths
were therefore additive (about 747px), which made every ``build_brand_page``
page wider than the shell's page viewport and pushed its content under the
console dock. The chips now live in the shared wrapping ``FlowLayout`` host,
so a narrow page wraps them onto additional rows while a wide page keeps the
original single row.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QFrame, QPushButton


_DOCK_KEYS = ("console/collapsed", "console/maximised", "console/dock_width")
_EXPECTED_CHIP_TEXT = (
    "▣  MTK",
    "✦  UNISOC",
    "◈  Qualcomm",
    "Ⓢ  Samsung",
    "🍎  Apple",
    "📱  Motorola",
    "🐉  Kirin",
    "🌐  Rockchip",
)


def _settle(window, rounds=12):
    from PyQt6.QtWidgets import QApplication

    for _ in range(rounds):
        QApplication.processEvents()


@pytest.fixture(scope="module")
def brand_window():
    """A real window with every deferred page materialised."""
    from tests.conftest import build_test_window, destroy_test_window, ensure_qapp

    ensure_qapp()
    window = build_test_window(settings_clear=_DOCK_KEYS)
    window.resize(1180, 768)
    window.show()
    _settle(window, 15)
    try:
        yield window
    finally:
        destroy_test_window(window)


def _open_samsung_brand_page(window):
    """Open the Samsung hub's SUPPORTED DEVICES brand page."""
    window._on_section("samsung")
    window._on_samsung_tab("supported")
    _settle(window)
    page = window.samsung_stack.currentWidget()
    assert page is window._device_stacks["samsung"]
    return page


def _chip_row(page):
    """Return the brand page's wrapping host and its eight chip buttons."""
    from python.gui.widgets.flow_layout import FlowHost, FlowLayout

    for host in page.findChildren(FlowHost):
        layout = host.layout()
        if not isinstance(layout, FlowLayout):
            continue
        chips = [
            layout.itemAt(index).widget()
            for index in range(layout.count())
            if isinstance(layout.itemAt(index).widget(), QPushButton)
        ]
        if tuple(chip.text() for chip in chips) == _EXPECTED_CHIP_TEXT:
            return host, chips
    raise AssertionError("the brand page has no wrapping row with its eight chips")


def _adb_tiles(page):
    """Return the ADB hub's wrapping host and its three fixed-width tiles."""
    from python.gui.widgets.flow_layout import FlowHost, FlowLayout

    for host in page.findChildren(FlowHost):
        layout = host.layout()
        if not isinstance(layout, FlowLayout):
            continue
        tiles = [
            layout.itemAt(index).widget()
            for index in range(layout.count())
            if isinstance(layout.itemAt(index).widget(), QFrame)
            and layout.itemAt(index).widget().width() == 170
        ]
        if len(tiles) == 3:
            return host, tiles
    raise AssertionError("the ADB hub has no wrapping row with its three tiles")


def test_brand_page_chip_row_minimum_width_is_one_chip_not_eight(brand_window):
    """The chip row's minimum is the widest chip, not the sum of all eight."""
    page = _open_samsung_brand_page(brand_window)
    host, chips = _chip_row(page)

    page_width = page.minimumSizeHint().width()
    assert page_width < 400, (
        f"brand page still needs {page_width}px; the chip row is forcing "
        "the page wider than its viewport"
    )
    assert len(chips) == 8

    chip_widths = [chip.minimumSizeHint().width() for chip in chips]
    row_width = host.minimumSizeHint().width()
    assert row_width == max(chip_widths), (
        f"wrapping row minimum is {row_width}px; expected the widest chip "
        f"({max(chip_widths)}px), not the sum ({sum(chip_widths)}px)"
    )
    assert row_width < sum(chip_widths)

    # The host owns the extra height when the available width cannot hold
    # all eight chips on one row.
    single_row_height = max(chip.sizeHint().height() for chip in chips)
    assert host.heightForWidth(300) > single_row_height


def test_brand_page_chips_keep_their_behaviour(brand_window, monkeypatch):
    """Wrapping changes only the layout, not chip state, tips, or routing."""
    from python.gui import devices
    from python.gui.i18n import tr

    page = _open_samsung_brand_page(brand_window)
    _host, chips = _chip_row(page)
    by_text = {chip.text(): chip for chip in chips}

    brand = devices.BRAND_BY_KEY["samsung"]
    engines = {(model.get("engine") or "").lower() for model in brand["models"]}
    for engine, label, glyph, section in devices._ENGINE_CHIPS:
        chip = by_text[f"{glyph}  {label}"]
        expected_enabled = engine in engines and bool(section)
        assert chip.isEnabled() is expected_enabled

        if not expected_enabled:
            reason = (
                tr("no tool section yet")
                if engine in engines
                else tr("{brand} doesn't use {engine}").format(
                    brand=brand["label"], engine=label
                )
            )
            assert chip.toolTip() == f"{glyph}  {label} — {reason}"

    enabled = [chip for chip in chips if chip.isEnabled()]
    assert enabled
    target = enabled[0]
    expected_section = next(
        section
        for engine, label, glyph, section in devices._ENGINE_CHIPS
        if f"{glyph}  {label}" == target.text()
    )

    calls = []
    original_on_section = brand_window._on_section

    def spy(section):
        calls.append(section)
        return original_on_section(section)

    monkeypatch.setattr(brand_window, "_on_section", spy)
    target.click()
    assert calls == [expected_section]


def test_adb_hub_tiles_wrap_instead_of_forcing_width(brand_window):
    """The ADB hub's fixed cards wrap instead of widening the whole page."""
    brand_window._on_section("adb")
    _settle(brand_window)
    page = brand_window._stack.currentWidget()

    page_width = page.minimumSizeHint().width()
    assert page_width < 260, (
        f"ADB hub still needs {page_width}px; its tile row is forcing the "
        "page wider than its viewport"
    )

    host, tiles = _adb_tiles(page)
    assert len(tiles) == 3
    for tile in tiles:
        assert tile.width() == 170
        assert tile.minimumWidth() == 170
        assert tile.maximumWidth() == 170
    assert host.minimumSizeHint().width() == 170
    assert host.heightForWidth(300) > 150
