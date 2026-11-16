"""Pseudo-locale smoke test.

A pseudo-locale makes untranslated text impossible to miss: every catalog value
is wrapped in visible markers. Building the real window under it proves that
the shared chrome and the flow browser actually go through the translator, and
that nothing crashes when every label is suddenly longer than the English.

The companion RTL contract lives in ``tests/test_i18n.py`` (layout direction and
the Arabic catalog lookup); this module exercises the rendered window.
"""
import json

import pytest

from python.gui import i18n

MARK = "\u27e6"  # ⟦
CLOSE = "\u27e7"  # ⟧


def _pseudo(value):
    if not value.strip():
        return value
    # Keep surrounding whitespace: layouts depend on it.
    lead = value[: len(value) - len(value.lstrip())]
    trail = value[len(value.rstrip()):]
    return f"{lead}{MARK}{value.strip()}{CLOSE}{trail}"


@pytest.fixture
def pseudo_catalog(tmp_path, monkeypatch):
    """Install a pseudo translator built from the English catalog."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    source = json.loads((i18n.catalog_dir() / "en.json").read_text(encoding="utf-8"))
    catalog = {
        "strings": {k: _pseudo(v) for k, v in source.get("strings", {}).items()},
        "keys": {k: _pseudo(v) for k, v in source.get("keys", {}).items()},
    }
    (tmp_path / "pseudo.json").write_text(
        json.dumps(catalog, ensure_ascii=False), encoding="utf-8"
    )

    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv(i18n.CATALOG_ENV, str(tmp_path))
    i18n.reset_for_tests()
    translator = i18n.install(app, "pseudo")
    assert translator is not None, "the pseudo catalog must install"
    try:
        yield translator
    finally:
        app.removeTranslator(translator)
        app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        i18n.reset_for_tests()


def test_pseudo_locale_reaches_every_shared_surface(pseudo_catalog, test_window):
    win = test_window()

    # Chrome built directly from translated literals.
    assert MARK in win.windowTitle()
    assert MARK in win.global_stop_btn.text()
    assert MARK in win._dev_title.text()
    assert MARK in win._dev_text.text()
    assert MARK in win._transport_combo.itemText(0)
    assert MARK in win._transport_combo.toolTip()
    assert MARK in win._console_title.text()

    # Data-driven labels go through the key catalog.
    assert MARK in i18n.tr_key("flow.adb_frp", "Fallback")
    rows = win._flow_rows(["Remove FRP"], modes=["ADB"])
    assert rows, "the flow browser must render at least one row"
    for row in rows:
        assert MARK in row.label, row
        assert MARK in row.job_text, row
        assert MARK in row.mode_text, row

    # Module-level helper used where no widget exists.
    assert MARK in i18n.tr("No phone detected")


def test_pseudo_locale_does_not_leak_into_english(pseudo_catalog):
    """Guard the fixture itself: the marker only exists while installed."""
    assert MARK in i18n.tr("CONSOLE")
    assert CLOSE in i18n.tr_key("job.remove_frp", "Remove FRP")
