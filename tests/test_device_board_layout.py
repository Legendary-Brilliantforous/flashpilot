"""Layout regression tests for the device->model board (brand page).

The brand page (`devices.build_brand_page`) splits the page into a LEFT
"supported devices" list and a RIGHT per-model action board. It used to add a
competing trailing stretch under the split row, so the two panes were handed
only ~50% of the page height and a large dead band was left below them.

These tests pin the fixed behaviour:
* the split row reaches the bottom of the page (no dead band),
* both panes receive the real available height (not half of it),
* the right board scrolls its own taller content,
* adding more supported devices grows the LEFT list's scroll range only — the
  panes keep their height and both scroll independently.

The standalone-page pattern is the reliable one here (see
`test_gui_hubs.py::TestModelPage`): build the page, resize it, show it, and
pump the event loop so Qt lays it out.
"""
import types

import pytest

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QScrollArea

from python.gui import devices as dp


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    assert app is not None
    return app


@pytest.fixture()
def win(monkeypatch):
    # build_brand_page stores the page under win._device_stacks[key]; click
    # closures would need the real window but we never click. The motorola
    # FRP label reads live device state, so pin it to stay hermetic.
    monkeypatch.setattr(dp, "_moto_frp_label", lambda: "FRP Remove")
    return types.SimpleNamespace(_device_stacks={})


def _pump(qapp, n=8):
    for _ in range(n):
        qapp.processEvents()


def _build(qapp, win, key="motorola", width=878, height=640):
    page = dp.build_brand_page(win, key)
    page.resize(width, height)
    page.show()
    _pump(qapp)
    return page


def _panes(page):
    """(left list, right board) QScrollAreas by their column widths."""
    areas = page.findChildren(QScrollArea)
    assert len(areas) >= 2, f"expected both panes, got {len(areas)} scroll areas"
    left = min(areas, key=lambda a: a.width())
    right = max(areas, key=lambda a: a.width())
    return left, right


def _bottom_in_page(page, widget):
    """Bottom edge of `widget` in `page` coordinates (geometry is parent-relative)."""
    top = widget.mapTo(page, QPoint(0, 0)).y()
    return top + widget.height() - 1


class TestBrandPageFillsHeight:
    def test_no_dead_band_below_split(self, qapp, win):
        # Tolerance: `outer` has 10/8/10/8 contents margins, so the split row's
        # bottom edge legitimately sits ~8px above the widget bottom; 16px
        # absorbs that margin plus offscreen font-metric rounding.
        H = 640
        page = _build(qapp, win, height=H)
        _left, right = _panes(page)
        outer_bottom = page.layout().contentsMargins().bottom()
        dead_band = (H - outer_bottom) - _bottom_in_page(page, right)
        assert dead_band <= 16, (
            f"dead band of {dead_band}px below the split row "
            f"(right pane bottom={_bottom_in_page(page, right)}, "
            f"page bottom={H}, bottom margin={outer_bottom})"
        )

    def test_both_panes_get_the_real_height(self, qapp, win):
        H = 640
        page = _build(qapp, win, height=H)
        left, right = _panes(page)
        # Available height for the split row = page height minus the chips row
        # above it and the layout's bottom margin.
        split_top = right.mapTo(page, QPoint(0, 0)).y()
        available = H - split_top - page.layout().contentsMargins().bottom()
        floor_ = 0.7 * available
        assert left.height() >= floor_, (
            f"left pane {left.height()}px < 0.7 * {available}px ({floor_:.0f}) "
            "— it is being given roughly half the page again"
        )
        assert right.height() >= floor_, (
            f"right pane {right.height()}px < 0.7 * {available}px ({floor_:.0f}) "
            "— it is being given roughly half the page again"
        )

    def test_right_board_scrolls_its_own_content(self, qapp, win):
        H = 640
        page = _build(qapp, win, height=H)
        _left, right = _panes(page)
        assert right.verticalScrollBar().maximum() > 0, (
            "the action board's content is taller than its pane yet it is not "
            "scrollable — the pane is not owning its scrollbar"
        )
        # The shell shows its outer page scrollbar only when the page's own
        # minimum hint exceeds the viewport; the fix must not inflate it.
        assert page.minimumSizeHint().height() <= H, (
            f"page minimumSizeHint height {page.minimumSizeHint().height()} > {H} "
            "— the page now needs the shell's outer scrollbar"
        )

    def test_more_devices_scroll_left_without_growing_the_panes(self, qapp, win):
        H = 640
        base = _build(qapp, win, height=H)
        base_left, base_right = _panes(base)
        base_left_h = base_left.height()
        base_right_h = base_right.height()

        # Extra models for the future: appended in-memory only (never written
        # to supported_devices.json) and removed in `finally`.
        models = dp.BRAND_BY_KEY["motorola"]["models"]
        original_len = len(models)
        extra = [
            {
                "model": f"Future Device {i}",
                "chip": "Snapdragon 8 Gen 1",
                "engine": "qcom",
                "status": "planned",
                "notes": "",
            }
            for i in range(40)
        ]
        models.extend(extra)
        try:
            grown = _build(qapp, win, height=H)
            grown_left, grown_right = _panes(grown)
            assert grown_left.verticalScrollBar().maximum() > 0, (
                "with 40 more supported devices the left list still cannot "
                "scroll — future devices would have nowhere to go"
            )
            # The extra devices are reached by scrolling, not by growing the page.
            assert grown_left.height() == base_left_h, (
                f"left pane grew from {base_left_h} to {grown_left.height()} "
                "to fit the extra devices instead of scrolling"
            )
            assert grown_right.height() == base_right_h, (
                f"right pane changed from {base_right_h} to {grown_right.height()} "
                "when the left list grew"
            )
            grown.deleteLater()
            _pump(qapp)
        finally:
            del models[original_len:]
        assert len(dp.BRAND_BY_KEY["motorola"]["models"]) == original_len
