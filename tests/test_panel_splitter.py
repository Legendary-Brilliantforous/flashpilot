"""Device panel | page splitter regression tests.

The device/connection panel is no longer a hard ``setFixedWidth(232)``: it and
the page stack live in a horizontal ``QSplitter`` so the divider can be dragged
front or back. The page keeps its own natural width (it scrolls sideways when
squeezed rather than reflowing its tabs/firmware grid) and stretch factors keep
the panel steady across window resizes while the page absorbs them.

    QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_panel_splitter.py -q
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

# The real window is built through the shared harness in tests/conftest.py
# (`test_window`), which joins the monitor poll thread, stops the periodic
# timers and fully tears the window down at module end.

# Everything the body split touches via QSettings — cleared before construction
# so the default panel width is deterministic regardless of prior runs.
_BODY_KEYS = ("layout/device_panel_width",)

# A *fresh* first show must not inherit geometry saved by an earlier module, so
# the regression test below clears these too before building its window. The
# console-dock keys matter as well: an earlier module can persist a dock width,
# which changes the top area (and therefore the body splitter) at first show.
_FRESH_KEYS = ("layout/device_panel_width", "win_geometry", "win_maximized",
               "console/collapsed", "console/maximised", "console/dock_width")

# A window wide enough that the page fits at its natural width without a
# scrollbar, so "the default panel width" is unambiguous.
_WIDE = (1500, 800)


def _pump():
    from PyQt6.QtWidgets import QApplication

    for _ in range(3):
        QApplication.processEvents()


def _settle(win, geometry=_WIDE):
    """Show at a known geometry (resize must precede show: the open animation
    would otherwise override a later resize)."""
    win._body_user_moved = False
    win._device_panel_width = None
    if geometry is not None:
        win.resize(*geometry)
    win.show()
    _pump()


@pytest.fixture(scope="module")
def win(test_window):
    from PyQt6.QtWidgets import QSplitter

    w = test_window(_BODY_KEYS)
    assert isinstance(w._body_splitter, QSplitter)
    _settle(w)
    return w


def test_device_panel_and_page_live_in_a_horizontal_splitter(win):
    """Panel and page are the two children of a draggable horizontal splitter."""
    splitter = win._body_splitter
    assert splitter.orientation().name == "Horizontal"
    assert splitter.count() == 2
    # Panel first (left), page second (right).
    assert splitter.widget(0) is win._conn
    assert splitter.widget(1) is win._page_scroll
    # The page stack is inside the scroll area, not a sibling of the panel.
    assert win._page_scroll.widget() is win._stack
    assert win._page_scroll.isAncestorOf(win._stack)
    # Neither side may be collapsed away by a drag.
    assert splitter.isCollapsible(0) is False
    assert splitter.isCollapsible(1) is False
    # Not a clamped fixed column any more: the panel can actually move.
    assert win._conn.minimumWidth() < win._conn.maximumWidth()


def test_default_panel_width_is_the_panel_default(win):
    """After show() the panel is its default width and the page still fits."""
    sizes = win._body_splitter.sizes()
    assert sum(sizes) > 800, f"window did not reach its geometry: {sizes}"
    assert abs(sizes[0] - win._BODY_PANEL_DEFAULT_W) <= 12, (
        f"panel {sizes[0]} not near the default {win._BODY_PANEL_DEFAULT_W} ({sizes})")
    assert sizes[1] >= win._PAGE_VIEW_MIN_W, f"page viewport too narrow: {sizes}"
    # Nothing is squeezed yet: the page fits, so no scrollbar is shown.
    assert win._page_scroll.viewport().width() >= win._stack.minimumSizeHint().width()
    assert win._page_scroll.horizontalScrollBar().isVisible() is False


def test_first_show_without_resize_still_applies_default_panel_width(test_window):
    """Pins the first-show split when the window is never resized.

    Regression for the slice-B2 review defect: ``_apply_default_body_split`` ran
    from ``showEvent`` *before* the splitter's first layout pass, saw
    ``width() <= 0`` and returned early. Because no ``resizeEvent`` followed, the
    panel never got the width the window's own formula computes for it and kept
    the splitter's stale 50/50 (``[225, 225]``; the page viewport ~233px while
    the page's natural width is ~699, so it scrolled sideways). A fresh window
    (config cleared) is shown *without* a resize — the shared fixture's usual
    ``_settle`` resizes, which is why the other tests here never caught it. The
    fix schedules one apply after the first real layout pass, and lets that apply
    stick even when the window is at its minimum width (where the panel and page
    floors together exceed the splitter, making ``QSplitter`` ignore
    ``setSizes``).
    """
    win = test_window(_FRESH_KEYS)
    win._body_user_moved = False
    win._device_panel_width = None
    win.show()          # deliberately no resize: the defect fires without one
    _pump()

    splitter = win._body_splitter
    sizes = splitter.sizes()
    # The panel gets exactly the width the window's formula computes for it.
    # (Pre-fix this stale split was [225, 225].)
    assert sizes[0] == win._desired_device_panel_width(splitter.width()), (
        f"panel did not get its computed width: {sizes}")
    assert sizes[0] >= win._BODY_PANEL_MIN_W, f"panel below its floor: {sizes}"
    # The page takes the remainder (it scrolls: the window is at its minimum).
    assert sizes[1] > 0 and win._page_scroll.viewport().width() > 0


def test_dragging_the_panel_resizes_the_page_and_persists(win):
    """Dragging front/back moves the boundary; a user width is remembered."""
    from PyQt6.QtCore import QSettings

    _settle(win)
    splitter = win._body_splitter
    before = splitter.sizes()
    assert before[1] > 0

    # Drag the divider to the right: panel wider, page viewport narrower.
    win._body_user_moved = True
    target = min(win._BODY_PANEL_MAX_W, win._BODY_PANEL_DEFAULT_W + 120)
    splitter.setSizes([target, splitter.width() - target])
    _pump()
    after = splitter.sizes()
    assert after[0] > before[0], f"panel did not widen: {before} -> {after}"
    assert after[1] < before[1], f"page did not give up room: {before} -> {after}"

    win._on_body_splitter_moved()
    chosen = splitter.sizes()[0]
    win.settings.sync()
    fresh = QSettings("FlashPilot", "FlashingTool")
    assert int(fresh.value("layout/device_panel_width")) == chosen
    assert win._body_user_moved is True

    # Drag back past the floor: the panel stops at its content minimum.
    splitter.setSizes([2, splitter.width() - 2])
    _pump()
    assert splitter.sizes()[0] >= win._BODY_PANEL_MIN_W, (
        f"panel collapsed past its floor: {splitter.sizes()}")
    # ...and the panel's own controls still fit at that width.
    assert win._conn.width() >= win._conn.minimumSizeHint().width()

    win._body_user_moved = False
    win._device_panel_width = None


def test_panel_width_preference_is_clamped(win):
    """A saved or dragged width is clamped so neither side is ever squeezed out."""
    page_floor = win._PAGE_VIEW_MIN_W
    total = 1000

    win._device_panel_width = None                     # no preference
    assert win._desired_device_panel_width(total) == win._BODY_PANEL_DEFAULT_W
    win._device_panel_width = "nonsense"               # invalid saved value
    assert win._desired_device_panel_width(total) == win._BODY_PANEL_DEFAULT_W
    win._device_panel_width = 10                       # below the panel floor
    assert win._desired_device_panel_width(total) == win._BODY_PANEL_MIN_W
    win._device_panel_width = 9999                     # above the panel cap
    assert win._desired_device_panel_width(total) == win._BODY_PANEL_MAX_W
    # A narrow splitter must still leave the page its viewport floor.
    narrow = win._BODY_PANEL_MIN_W + page_floor + 6
    assert win._desired_device_panel_width(narrow) == win._BODY_PANEL_MIN_W
    assert win._desired_device_panel_width(narrow) + page_floor + 6 <= narrow + 1
    win._device_panel_width = None


def test_transient_narrow_layout_does_not_pin_the_panel(win):
    """The panel holds its desired width across resizes until the user drags.

    Regression guard for the same defect class the console dock had: a one-shot
    default applied during a narrow pre-geometry-restore layout pass pinned the
    panel to a transient width (its floor) for the whole session.
    """
    _settle(win)
    win._body_splitter.setSizes([win._BODY_PANEL_MIN_W, 120])   # transient pass
    _pump()
    win.resize(1400, 800)
    _pump()
    assert win._body_splitter.sizes()[0] == win._desired_device_panel_width(
        win._body_splitter.width()), "the transient narrow panel width was kept"

    # Once the user drags, that width is what survives a resize.
    win._body_user_moved = True
    win._body_splitter.setSizes([300, win._body_splitter.width() - 300])
    _pump()
    win.resize(1250, 800)
    _pump()
    assert win._body_splitter.sizes()[0] == 300, "a user-chosen width was overwritten"
    win._body_user_moved = False


def test_squeezed_page_scrolls_instead_of_clipping(win):
    """Squeezing the page scrolls it sideways; its layout is never reflowed."""
    _settle(win)
    win._body_user_moved = True
    splitter = win._body_splitter
    splitter.setSizes([win._BODY_PANEL_MAX_W, splitter.width() - win._BODY_PANEL_MAX_W])
    _pump()

    viewport = win._page_scroll.viewport()
    natural = win._stack.minimumSizeHint().width()
    assert splitter.sizes()[0] == win._BODY_PANEL_MAX_W, (
        f"panel did not reach its cap: {splitter.sizes()}")
    assert viewport.width() < natural, "the probe needs a squeezed viewport"
    # The page keeps its own natural width (no reflow, no clipped controls) and
    # the scroll area exposes it instead.
    assert win._stack.width() >= natural, (
        f"page reflowed: stack {win._stack.width()} < natural {natural}")
    assert win._page_scroll.horizontalScrollBar().isVisible() is True
    win._body_user_moved = False
