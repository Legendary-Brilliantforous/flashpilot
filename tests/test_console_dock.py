"""Console dock (S2a) regression tests.

Builds the real window headless and asserts the shared console lives in a
collapsible RIGHT-hand dock inside a horizontal ``QSplitter`` (pages left,
console right): default panel width, collapse/expand, F11 maximised mode,
unchanged logging, and QSettings persistence.

    QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_console_dock.py -q
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

# The real window is built through the shared harness in tests/conftest.py
# (`test_window`), which joins the monitor poll thread, stops the periodic
# timers and fully tears the window down at module end.

# Everything the dock touches via QSettings — cleared before construction so the
# default split is deterministic regardless of prior runs.
_DOCK_KEYS = ("console/collapsed", "console/maximised", "console/dock_width")


@pytest.fixture(scope="module")
def win(test_window):
    # Build + quiesce a real window through the shared harness; the dock keys
    # are cleared before construction so the default split is deterministic.
    w = test_window(_DOCK_KEYS)
    from PyQt6.QtWidgets import QSplitter

    assert isinstance(w._splitter, QSplitter)
    return w


def test_console_panel_is_dock_right_of_pages(win):
    """(a) the console sits on the RIGHT; the other child holds the pages."""
    from PyQt6.QtWidgets import QSplitter

    assert isinstance(win._splitter, QSplitter)
    assert win._splitter.orientation().name == "Horizontal"
    # Console must be the *last* child: the dock is on the right-hand side.
    assert win._splitter.indexOf(win._console_dock) == win._splitter.count() - 1
    other = next(win._splitter.widget(i) for i in range(win._splitter.count())
                 if win._splitter.widget(i) is not win._console_dock)
    assert other is win._top_area
    assert win._top_area.isAncestorOf(win._stack)
    # Not a clamped fixed column: the user can drag the splitter handle.
    assert win._console_dock.maximumWidth() > 10000


def test_default_console_width_is_the_panel_default(win):
    """(b) after show() the console is the default panel width (not a share)."""
    from PyQt6.QtWidgets import QApplication

    win.show()
    QApplication.processEvents()
    sizes = win._splitter.sizes()
    total = sum(sizes)
    assert total > 0, f"splitter has no width: {sizes}"
    assert sizes[1] >= win._DOCK_MIN_CONSOLE, f"console too narrow: {sizes}"
    assert sizes[0] >= win._DOCK_MIN_TOP, f"page area too narrow: {sizes}"
    assert abs(sizes[1] - win._DOCK_DEFAULT_WIDTH) <= 120, (
        f"console width {sizes[1]} not near the default {win._DOCK_DEFAULT_WIDTH} ({sizes})")


def test_collapse_hides_transcript_and_expand_restores(win):
    """(c) collapsing hides the transcript; expanding brings it back."""
    from PyQt6.QtWidgets import QApplication

    assert win.log.isVisible() is True
    win._toggle_console_collapse()
    QApplication.processEvents()
    assert win._console_collapsed is True
    assert win._console_body.isVisible() is False
    assert win.log.isVisible() is False
    # The toggle stays reachable in the thin bar; title/count hide to fit.
    assert win.console_toggle_btn.isVisible() is True
    assert win.console_count.isVisible() is False
    assert win._splitter.sizes()[1] <= win._DOCK_COLLAPSED_W + 12, (
        f"collapsed bar not thin: {win._splitter.sizes()}")

    win._toggle_console_collapse()
    QApplication.processEvents()
    assert win._console_collapsed is False
    assert win.log.isVisible() is True
    assert win.console_count.isVisible() is True
    assert win._splitter.sizes()[1] >= win._DOCK_MIN_CONSOLE


def test_f11_maximised_toggle_is_reversible(win):
    """(d) F11 maximisation flag flips and fully restores the page area."""
    from PyQt6.QtGui import QShortcut
    from PyQt6.QtWidgets import QApplication

    keys = {s.key().toString() for s in win.findChildren(QShortcut)}
    assert "F11" in keys, f"no F11 shortcut registered: {keys}"

    assert win._console_maximised is False
    win._toggle_console_maximised()
    QApplication.processEvents()
    assert win._console_maximised is True
    assert win._top_area.isVisible() is False

    win._toggle_console_maximised()
    QApplication.processEvents()
    assert win._console_maximised is False
    assert win._top_area.isVisible() is True
    assert win.log.isVisible() is True


def test_log_line_still_appends_and_counts(win):
    """(e) logging behaviour is unchanged."""
    before = win.console_count.text()
    win.log_line("hello")
    assert "hello" in win.log.toPlainText()
    assert win.console_count.text() != before
    assert len(win._log_buffer) >= 1


def test_dock_persistence_round_trips(win):
    """(f) dock width / collapsed / maximised persist through QSettings."""
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication

    w = win
    w._set_console_collapsed(True)
    assert w.settings.value("console/collapsed", type=bool) is True
    w._set_console_maximised(True)
    assert w.settings.value("console/maximised", type=bool) is True

    w._set_console_maximised(False)
    w._set_console_collapsed(False)
    # A dock width is only persisted once the user actually chose it — a
    # programmatic/transient width must not become the saved preference.
    w.show()
    QApplication.processEvents()
    w._dock_user_moved = True
    w._splitter.setSizes([max(w._DOCK_MIN_TOP, w._splitter.width() - 400), 400])
    QApplication.processEvents()
    w._on_dock_splitter_moved()
    chosen = w._splitter.sizes()[1]
    w._save_console_state()
    fresh = QSettings("FlashPilot", "FlashingTool")
    assert fresh.value("console/collapsed", type=bool) is False
    assert fresh.value("console/maximised", type=bool) is False
    width = fresh.value("console/dock_width")
    assert width is not None and int(width) == chosen >= w._DOCK_MIN_CONSOLE
    w._dock_user_moved = False

    # Invalid persisted values are tolerated (fall back to the default width,
    # clamped so the page area keeps its minimum).
    w._console_dock_width = "nonsense"
    assert w._desired_dock_console_width(400) == w._DOCK_MIN_CONSOLE
    # A stale/transiently-narrow persisted width is clamped up to the floor,
    # so an old value can never reopen the dock too narrow for its controls.
    w._console_dock_width = 314
    assert w._desired_dock_console_width(940) == w._DOCK_MIN_CONSOLE


def test_no_console_control_is_clipped_at_the_minimum_width(win):
    """(g) At the dock's minimum width every control renders in full.

    Guards two real defects: the toolbar buttons were pinned to 52px while the
    "compact" padding override never matched ``_btn_ghost()``'s actual
    ``7px 14px`` (so each button clipped its own label), and ``SectionTitle``
    painted a ``">> "`` prefix it reserved no width for ("CONSOLE" -> "CONSO").
    """
    from PyQt6.QtWidgets import QApplication

    win.show()
    # Behave like a user drag, otherwise the dock re-applies its default width.
    win._dock_user_moved = True
    win._splitter.setSizes(
        [win._splitter.width() - win._DOCK_MIN_CONSOLE, win._DOCK_MIN_CONSOLE])
    QApplication.processEvents()

    dock = win._console_dock
    assert dock.width() >= win._DOCK_MIN_CONSOLE, f"dock floor not honoured: {dock.width()}"
    controls = [win.console_toggle_btn, win._console_title, win.console_count,
                win.wrap_btn, win.clear_btn, win.copy_btn, win.save_btn, win.time_btn,
                win.find_edit, win.regex_btn, win.find_next_btn, win.find_prev_btn,
                win.search_clear_btn, win.clear_on_run]
    controls += list(win._filter_btns.values())
    for c in controls:
        pos = c.mapTo(dock, c.rect().topLeft())
        assert pos.x() + c.width() <= dock.width(), (
            f"{c.objectName() or type(c).__name__} overflows the dock")
        assert c.width() >= c.minimumSizeHint().width(), (
            f"{c.text() if hasattr(c, 'text') else c} is clipped")
    win._dock_user_moved = False


def test_transient_narrow_layout_does_not_pin_the_dock(win):
    """(h) The dock holds its desired width across resizes until the user drags.

    Regression: the default split used to be applied exactly once, so if the
    very first layout pass happened before the window geometry was restored
    (a narrow splitter) the console was pinned to that transient width for the
    whole session — and that width was then persisted on close.
    """
    from PyQt6.QtWidgets import QApplication

    win._dock_user_moved = False
    win._console_dock_width = None          # no saved preference: use the default
    win.show()
    QApplication.processEvents()

    # Simulate a narrow, pre-geometry-restore pass, then the real window size.
    win._splitter.setSizes([100, 314])
    QApplication.processEvents()
    win.resize(1400, 800)
    QApplication.processEvents()
    assert win._splitter.sizes()[1] == win._desired_dock_console_width(
        win._splitter.width()), "the transient narrow width was kept"
    assert win._splitter.sizes()[1] >= win._DOCK_MIN_CONSOLE

    # Once the user drags, that width is what survives a resize.
    win._dock_user_moved = True
    win._splitter.setSizes([win._splitter.width() - 400, 400])
    QApplication.processEvents()
    win.resize(1200, 800)
    QApplication.processEvents()
    assert win._splitter.sizes()[1] == 400, "a user-chosen width was overwritten"
    win._dock_user_moved = False


def test_collapsed_bar_keeps_the_chevron_anchored(win):
    """(j) Collapsing never moves the chevron vertically.

    Regression: with the body hidden the header became the only item left in the
    dock's column, so Qt handed it the leftover height and centred the chevron in
    the full-height bar — it jumped to the middle on collapse and back on expand.
    """
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QApplication

    win._set_console_collapsed(False)
    QApplication.processEvents()
    expanded = win.console_toggle_btn.mapTo(win._console_dock, QPoint(0, 0))

    win._set_console_collapsed(True)
    QApplication.processEvents()
    collapsed = win.console_toggle_btn.mapTo(win._console_dock, QPoint(0, 0))
    assert collapsed.y() == expanded.y(), (
        f"chevron moved vertically on collapse: {expanded.y()} -> {collapsed.y()}")
    # Anchored at the top of the bar, not centred in it.
    assert collapsed.y() <= 20, f"chevron not anchored: y={collapsed.y()}"
    assert (collapsed.y() + win.console_toggle_btn.height()
            <= win._console_dock.height())

    # Expanding puts it back exactly where it was.
    win._set_console_collapsed(False)
    QApplication.processEvents()
    back = win.console_toggle_btn.mapTo(win._console_dock, QPoint(0, 0))
    assert back.y() == expanded.y(), f"chevron did not return: {back.y()}"


def test_collapsed_bar_centres_the_toggle_chevron(win):
    """(i) Collapsed: the reopen chevron is centred in the thin bar.

    Regression: the collapsed bar kept the expanded 12px side margins, so the
    24px button had no room in the 44px bar and drifted to one side — the
    reopen affordance appeared to jump around between the two states.
    """
    from PyQt6.QtWidgets import QApplication

    win._set_console_collapsed(False)
    QApplication.processEvents()
    win._set_console_collapsed(True)
    QApplication.processEvents()

    dock, btn = win._console_dock, win.console_toggle_btn
    assert dock.width() == win._DOCK_COLLAPSED_W, f"bar not thin: {dock.width()}"
    assert btn.isVisible() is True
    assert btn.text() == "▸" and "Expand" in btn.toolTip()
    pos = btn.mapTo(dock, btn.rect().topLeft())
    left_gap = pos.x()
    right_gap = dock.width() - (pos.x() + btn.width())
    assert pos.x() >= 0 and pos.x() + btn.width() <= dock.width(), (
        f"chevron outside the bar: x={pos.x()} w={btn.width()} bar={dock.width()}")
    assert abs(left_gap - right_gap) <= 2, (
        f"chevron not centred in the collapsed bar: left={left_gap} right={right_gap}")

    # Expanding restores the title/count and the left-aligned header.
    win._set_console_collapsed(False)
    QApplication.processEvents()
    assert win._console_title.isVisible() and win.console_count.isVisible()
    assert btn.text() == "▾" and "Collapse" in btn.toolTip()
    pos = btn.mapTo(dock, btn.rect().topLeft())
    assert pos.x() <= 20, f"expanded header no longer starts at the left: x={pos.x()}"
