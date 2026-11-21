"""Live UI-language switching regression tests.

The translator alone cannot update labels that were translated when their
widgets were constructed. These tests exercise the in-place UI rebuild and
verify that it preserves the window, transcript, active section, and the
run-time safety guard around flashing operations.
"""
import json

import pytest

from python.gui import i18n, qt_app
from python.gui.i18n import current_language, set_language


@pytest.fixture
def language_window():
    """Build one real window and restore English after every test."""
    # Import after pytest's session-level QSettings isolation check so the
    # helper module is not loaded a second time before that check runs.
    from tests.conftest import build_test_window, destroy_test_window, ensure_qapp

    app = ensure_qapp()
    set_language(app, "en")
    window = build_test_window()
    try:
        yield app, window
    finally:
        set_language(app, "en")
        destroy_test_window(window)


def _tr_catalog():
    return json.loads(
        (i18n.catalog_dir() / "tr.json").read_text(encoding="utf-8")
    )


def test_language_switch_updates_visible_strings_without_restart(language_window):
    from PyQt6.QtWidgets import QLabel

    _app, window = language_window
    catalog = _tr_catalog()
    expected = catalog["strings"]["No phone detected"]
    original_window = window

    assert window._switch_ui_language("tr") is True
    assert window is original_window
    assert window._dev_title.text() == expected

    window._on_section("settings")
    labels = [
        label.text()
        for label in window._settings_pages.findChildren(QLabel)
    ]
    new_source = "Display language for menus and buttons. Applies immediately."
    old_source = "Display language for menus and buttons. Requires a restart."
    expected_description = catalog["strings"].get(new_source, new_source)
    old_description = catalog["strings"].get(old_source, old_source)

    assert expected_description in labels
    assert old_description not in labels
    assert "restart" not in expected_description.lower()


def test_language_switch_preserves_the_console_transcript(language_window):
    _app, window = language_window
    window.log_line("[info] hello")

    assert window._switch_ui_language("tr") is True
    assert "[info] hello" in window.log.toPlainText()


def test_language_switch_keeps_the_current_section(language_window):
    from PyQt6.QtWidgets import QFrame

    _app, window = language_window
    window._on_section("settings")
    old_page = window._stack.currentWidget()
    assert isinstance(old_page, QFrame)

    assert window._switch_ui_language("tr") is True
    assert window._current_section == "settings"
    current_page = window._stack.currentWidget()
    assert current_page is window._stack.widget(window._section_index["settings"])
    assert current_page is not old_page
    assert isinstance(current_page, QFrame)
    assert current_page.isAncestorOf(window._settings_pages)


def test_language_switch_is_deferred_while_an_operation_runs(
    language_window, monkeypatch
):
    _app, window = language_window
    running = qt_app._flows_running
    monkeypatch.setattr(qt_app, "_flows_running", lambda: 1)

    assert window._switch_ui_language("tr") is False
    assert current_language() == "en"
    assert window._pending_ui_language == "tr"

    monkeypatch.setattr(qt_app, "_flows_running", running)
    assert window._apply_pending_ui_language() is True
    assert current_language() == "tr"
    assert window._pending_ui_language is None


def test_language_switch_keeps_the_console_dock_width(language_window):
    from PyQt6.QtWidgets import QApplication

    app, window = language_window
    window.show()
    for _ in range(5):
        QApplication.processEvents()

    before = list(window._splitter.sizes())
    assert before[1] > 0

    assert window._switch_ui_language("tr") is True
    # The rebuilt splitter gets its real width on the next layout pass; let
    # the deferred restore run before checking the resulting distribution.
    for _ in range(6):
        QApplication.processEvents()

    after = list(window._splitter.sizes())
    assert abs(after[1] - before[1]) <= 2
    assert before[0] - after[0] <= 2


def test_language_switch_keeps_the_panels_side_by_side(language_window):
    """The three shell panels must stay edge to edge, never overlapping.

    The console dock is a sibling of the page area in the horizontal
    splitter: when the rebuilt splitter lost its sizes the console grew
    over the middle page. Map every panel into window coordinates and
    assert the edges only touch — the console may not cover the page.
    """
    from PyQt6.QtWidgets import QApplication

    app, window = language_window
    window.show()
    for _ in range(5):
        QApplication.processEvents()

    def panel_edges():
        def rect_of(widget):
            top_left = widget.mapTo(window, widget.rect().topLeft())
            return top_left.x(), top_left.x() + widget.width()

        device_left, device_right = rect_of(window._conn)
        page_left, page_right = rect_of(window._page_scroll)
        console_left, console_right = rect_of(window._console_dock)
        return device_left, device_right, page_left, page_right, console_left, console_right

    def assert_side_by_side():
        (
            device_left,
            device_right,
            page_left,
            page_right,
            console_left,
            console_right,
        ) = panel_edges()
        assert device_right <= page_left, "device panel overlaps the page"
        assert page_right <= console_left, "console dock overlaps the page"
        assert console_right > console_left, "console dock has no width"

    assert_side_by_side()

    assert window._switch_ui_language("tr") is True
    for _ in range(6):
        QApplication.processEvents()

    assert_side_by_side()


def test_language_switch_does_not_replay_the_connection_animation(language_window):
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication

    app, window = language_window
    # The harness stops the monitor, but its first queued poll can still be
    # delivered while the test settles the scene. Disconnect it so the test
    # exercises only the language-switch rebuild.
    try:
        window._monitor.state.disconnect()
    except (TypeError, RuntimeError):
        pass
    window.scene.set_connected(True)
    QTest.qWait(120)
    for _ in range(3):
        QApplication.processEvents()

    plug_t = window.scene._plug_t
    bubbles = list(window.scene._bubbles)
    bubble_ids = {id(bubble) for bubble in bubbles}
    assert window.scene._connected is True

    assert window._switch_ui_language("tr") is True
    for _ in range(6):
        QApplication.processEvents()

    assert window.scene._connected is True
    assert window.scene._plug_t >= plug_t
    assert len(window.scene._bubbles) <= len(bubbles)
    assert all(id(bubble) in bubble_ids for bubble in window.scene._bubbles)


def test_language_switch_keeps_the_shimmer_hidden(language_window):
    from PyQt6.QtWidgets import QApplication

    app, window = language_window
    # The harness leaves the window hidden, so isHidden() is the reliable
    # check for the shimmer's explicit visibility state.
    assert window.shimmer.isVisible() is False
    assert window.shimmer.isHidden() is True

    assert window._switch_ui_language("tr") is True
    for _ in range(6):
        QApplication.processEvents()

    assert window.shimmer.isVisible() is False
    assert window.shimmer.isHidden() is True


def test_language_switch_keeps_the_granular_animation_preferences(language_window):
    app, window = language_window
    settings = window.settings
    saved = {
        key: (settings.contains(key), settings.value(key))
        for key in ("animations", "anim_orb")
    }
    try:
        settings.setValue("animations", True)
        settings.setValue("anim_orb", False)
        window._apply_animation_prefs()
        assert window.orb._anim is False

        assert window._switch_ui_language("tr") is True
        assert window.orb._anim is False
    finally:
        for key, (present, value) in saved.items():
            if present:
                settings.setValue(key, value)
            else:
                settings.remove(key)
