"""Qt message filtering: drop only the benign font-fallback notice.

Qt logs ``qt.text.font.db: OpenType support missing for "Inter", script 11``
when a label uses a script the UI font cannot shape (the language picker's
native names, or a Hindi/Arabic/CJK interface). Qt then falls back per glyph
and the text renders fine, so the notice is startup noise — but every other
Qt message must still reach the console.
"""
import types

import pytest

from python.gui import qt_logging


def _ctx(category=""):
    return types.SimpleNamespace(category=category)


def test_detects_the_real_notice():
    assert qt_logging.is_font_fallback_notice(
        'OpenType support missing for "Inter", script 11'
    )
    assert qt_logging.is_font_fallback_notice(
        'OpenType support missing for "Roboto", script 11'
    )
    assert not qt_logging.is_font_fallback_notice("Failed to load platform plugin")
    assert not qt_logging.is_font_fallback_notice("")
    assert not qt_logging.is_font_fallback_notice(None)


def test_format_message_matches_qt_default_shape():
    assert (
        qt_logging.format_message(
            _ctx("qt.text.font.db"), 'OpenType support missing for "Inter", script 11'
        )
        == 'qt.text.font.db: OpenType support missing for "Inter", script 11'
    )
    # Default-category messages are printed bare.
    assert qt_logging.format_message(_ctx(""), "plain warning") == "plain warning"
    assert qt_logging.format_message(None, "no context") == "no context"


def test_handler_drops_the_notice_and_keeps_everything_else(capsys):
    qt_logging.handler(
        None, _ctx("qt.text.font.db"), 'OpenType support missing for "Inter", script 11'
    )
    assert capsys.readouterr().err == ""

    qt_logging.handler(None, _ctx("qt.qpa.plugin"), "cound not find plugin")
    assert "qt.qpa.plugin: cound not find plugin" in capsys.readouterr().err


def test_install_honours_the_show_override(monkeypatch):
    monkeypatch.setenv(qt_logging.SHOW_ENV, "1")
    assert qt_logging.install() is False
    monkeypatch.delenv(qt_logging.SHOW_ENV, raising=False)


def test_main_installs_the_filter():
    """Without the install, the app's startup noise comes back."""
    import inspect

    from python.gui import qt_app

    source = inspect.getsource(qt_app.main)
    assert "qt_logging" in source
    assert "_install_qt_logging()" in source


@pytest.fixture
def devanagari_font():
    from tests.conftest import ensure_qapp

    ensure_qapp()
    from PyQt6.QtGui import QFontDatabase

    if "Noto Sans Devanagari" not in QFontDatabase.families():
        pytest.skip("no Devanagari font installed")
    return "Noto Sans Devanagari"


_PICKER_SCRIPT = r"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, {root!r})

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QComboBox

if sys.argv[1] == "filter":
    from python.gui.qt_logging import install

    install()

app = QApplication([])
app.setFont(QFont("Inter", 10))  # what the app uses for Latin-script UIs
combo = QComboBox()
combo.addItem("English")
combo.addItem("\u0939\u093f\u0928\u094d\u0926\u0940")
combo.show()
app.processEvents()
"""


def test_real_qt_warning_is_suppressed_end_to_end(devanagari_font):
    """Prove it in a fresh interpreter, where Qt's font cache is cold.

    A Devanagari row under the app's Inter stack makes Qt log the notice; the
    unfiltered run (control) must show it, the filtered run must not. Both run
    in subprocesses because Qt resolves each family/script pair once per
    process — in-process counts depend on what earlier tests already shaped.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = str(Path(__file__).resolve().parents[1])
    script = _PICKER_SCRIPT.format(root=root)

    def run(mode):
        return subprocess.run(
            [sys.executable, "-c", script, mode],
            capture_output=True,
            text=True,
            timeout=180,
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        )

    control = run("plain")
    assert control.returncode == 0, control.stderr
    assert "OpenType support missing" in control.stderr, control.stderr

    filtered = run("filter")
    assert filtered.returncode == 0, filtered.stderr
    assert "OpenType support missing" not in filtered.stderr, filtered.stderr
