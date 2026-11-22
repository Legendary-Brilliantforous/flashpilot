"""The middle page must fit its viewport — no content under the console dock.

The shell is `device panel | middle page | console dock`. The page lives in a
scroll area that does not clip its content: the page keeps its natural
minimum width and scrolls sideways instead. When a page's natural width grew
past the viewport, the page content was cut off at the console edge and
looked like it ran under the console panel.

These tests pin both halves of the fix:
* the pages themselves stay narrow enough (their rows wrap instead of
  forcing a width),
* the console dock gives the middle panel room instead of squeezing it.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

# The app's minimum window width (qt_app.py: `fit_w = min(1180, ...)`).
MIN_WINDOW_W = 1180
# The page area the shell keeps at that width: the console dock shrinks to
# its own 360px floor so the page still gets ~515px.
PAGE_BUDGET = 500


@pytest.fixture(scope="module")
def page_window():
    """One real window, every deferred section materialised."""
    from tests.conftest import build_test_window, destroy_test_window, ensure_qapp

    app = ensure_qapp()
    window = build_test_window()
    try:
        yield app, window
    finally:
        destroy_test_window(window)


def _settle(window, rounds=8):
    from PyQt6.QtWidgets import QApplication

    for _ in range(rounds):
        QApplication.processEvents()


@pytest.fixture
def narrow_page_window(page_window):
    """The window at its minimum width with a normal (expanded) console."""
    _app, window = page_window
    saved_width = getattr(window, "_console_dock_width", None)
    saved_collapsed = bool(getattr(window, "_console_collapsed", False))
    saved_panel = getattr(window, "_device_panel_width", None)
    try:
        # Resize before showing: the offscreen platform clamps a visible
        # window to the (small) virtual screen, the hidden one keeps the
        # requested size.
        window.resize(MIN_WINDOW_W, 720)
        window.show()
        window._console_dock_width = 420
        # An earlier module may have persisted a dragged device-panel width;
        # the default split is what this test measures.
        window._device_panel_width = None
        window._set_console_collapsed(False, persist=False)
        window._dock_user_moved = False
        window._body_user_moved = False
        window._apply_default_dock_split()
        window._apply_default_body_split()
        _settle(window, 15)
        if window.width() < MIN_WINDOW_W:
            pytest.skip(
                "the platform clamped the window below the app's minimum "
                f"width ({window.width()}px < {MIN_WINDOW_W}px)"
            )
        yield window
    finally:
        if saved_width is not None:
            window._console_dock_width = saved_width
        window._device_panel_width = saved_panel
        window._set_console_collapsed(saved_collapsed, persist=False)
        _settle(window, 5)


def test_every_section_page_fits_the_middle_panel(narrow_page_window):
    window = narrow_page_window
    viewport = window._page_scroll.viewport().width()
    assert viewport >= PAGE_BUDGET, (
        f"the page area is only {viewport}px wide at the minimum window width"
    )

    overflowing = []
    for key in list(window._section_index.keys()):
        window._on_section(key)
        _settle(window, 4)
        page = window._stack.currentWidget()
        min_width = page.minimumSizeHint().width()
        if min_width > viewport:
            overflowing.append((key, min_width))

    assert not overflowing, (
        "pages wider than the middle panel (they are clipped at the console "
        f"edge): {overflowing}"
    )


def test_the_middle_page_does_not_scroll_sideways(narrow_page_window):
    """The page scroll area must not need horizontal scrolling."""
    window = narrow_page_window
    for key in list(window._section_index.keys()):
        window._on_section(key)
        _settle(window, 4)
        bar = window._page_scroll.horizontalScrollBar()
        assert bar.maximum() == 0, (
            f"section {key!r} scrolls sideways by {bar.maximum()} px — its "
            "content is wider than the page area"
        )


def test_the_console_dock_never_covers_the_page(narrow_page_window):
    """The three panels stay side by side, edge to edge."""
    window = narrow_page_window

    def edges():
        def right_edge(widget):
            return widget.mapTo(window, widget.rect().topLeft()).x() + widget.width()

        def left_edge(widget):
            return widget.mapTo(window, widget.rect().topLeft()).x()

        return (
            right_edge(window._conn),
            left_edge(window._page_scroll),
            right_edge(window._page_scroll),
            left_edge(window._console_dock),
        )

    device_right, page_left, page_right, console_left = edges()
    assert device_right <= page_left, "device panel overlaps the page"
    assert page_right <= console_left, "console dock overlaps the page"


def test_the_console_dock_does_not_squeeze_the_middle_page(narrow_page_window):
    """At the minimum window width the console gives room to the page."""
    window = narrow_page_window
    dock, body = window._splitter.sizes(), window._body_splitter.sizes()
    assert body[1] >= PAGE_BUDGET, (
        f"the middle page is only {body[1]}px wide (dock {dock}, body {body})"
    )
    assert window._page_scroll.viewport().width() >= PAGE_BUDGET
