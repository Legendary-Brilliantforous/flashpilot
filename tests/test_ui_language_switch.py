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
