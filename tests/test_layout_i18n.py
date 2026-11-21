"""Long-translation layout regressions (French / German / Russian ...).

Reported bug: after selecting a language whose labels are longer than English,
rows grew past their container. The shared console was the visible casualty —
``Save`` becomes ``Enregistrer`` (74 px instead of 43), ``Warnings`` becomes
``Avertissements`` (91 px instead of 61), ``auto-clear`` becomes
``effacement auto`` — yet every one of those controls had a hard
``setFixedWidth``, so the label was silently truncated ("Enregistr",
"›arcourir..") and the dock's content overflowed its own frame. On whole pages
the effect was worse: a row of buttons demanded more width than the page
viewport, so the page grew horizontally and the right-hand controls (Browse
buttons, switches, dropdowns) ended up outside the visible area.

Contracts guarded here:

* console toolbar chips and filter chips are never narrower than their own
  translated label, and their rows wrap instead of overflowing;
* ``flow_row`` is a real wrapping row (``FlowHost`` + ``FlowLayout``) that
  keeps every child at its full ``sizeHint`` width and grows in height;
* whole pages (settings, MTK, FUS, general) still fit the viewport in French,
  so no scroll area needs a horizontal scrollbar;
* controls that used to be pinned (settings row buttons, MTK/Qualcomm/SPD
  browse buttons) keep their baseline as a minimum and grow with the label.

Run:  QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_layout_i18n.py -q
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

# Console dock keys cleared before construction so the default split is stable.
_DOCK_KEYS = ("console/collapsed", "console/maximised", "console/dock_width")


@pytest.fixture(scope="module")
def fr_win(test_window):
    """The real window, built while the French catalog is installed.

    Labels are resolved in ``tr()`` at construction time, so the translator has
    to be installed *before* the window is built — installing it afterwards
    would leave every widget with its English text and the test would pass
    vacuously. (The runtime language switch in the GUI is a different path:
    it swaps the translator *and* rebuilds the widget tree, see
    ``FlashPilotWindow._switch_ui_language``.) Qt does not own the translator,
    so it is removed explicitly at teardown; otherwise every later test in the
    session would see French.
    """
    from python.gui import i18n

    app = QApplication.instance() or QApplication([])
    translator = i18n.install(app, "fr")
    assert translator is not None, "the French catalog must ship"
    w = test_window(_DOCK_KEYS)
    w.resize(1366, 736)
    w.show()
    for _ in range(15):
        QApplication.processEvents()
    try:
        yield w
    finally:
        app.removeTranslator(translator)
        i18n.reset_for_tests()


def _settle(window, rounds=10):
    for _ in range(rounds):
        QApplication.processEvents()


def _assert_not_truncated(widget):
    assert isinstance(widget, QPushButton)
    assert widget.width() >= widget.minimumSizeHint().width(), (
        f"{widget.text()!r} is clipped: "
        f"width {widget.width()} < needed {widget.minimumSizeHint().width()}"
    )


def test_console_toolbar_shows_translated_labels_in_full(fr_win):
    """Every console toolbar chip is at least as wide as its own label."""
    _settle(fr_win)
    assert fr_win.save_btn.text() == "Enregistrer"
    for btn in (fr_win.wrap_btn, fr_win.clear_btn, fr_win.copy_btn,
                fr_win.save_btn, fr_win.time_btn):
        _assert_not_truncated(btn)
    # English baseline is 52 px; the French label genuinely needs more.
    assert fr_win.save_btn.width() > 52


def test_console_filter_chips_and_autoclear_show_in_full(fr_win):
    """The filter chips and the auto-clear checkbox are not squeezed."""
    _settle(fr_win)
    for btn in fr_win._filter_btns.values():
        _assert_not_truncated(btn)
    assert fr_win._filter_btns["warn"].text() == "Avertissements"
    assert fr_win._filter_btns["warn"].width() >= 90
    assert (fr_win.clear_on_run.width()
            >= fr_win.clear_on_run.minimumSizeHint().width())
    assert fr_win.clear_on_run.text() == "effacement auto"


def test_console_rows_are_wrapping_hosts(fr_win):
    """Toolbar + filter rows live in FlowLayout hosts, so they can wrap."""
    from python.gui.widgets import FlowHost, FlowLayout

    _settle(fr_win)
    hosts = [h for h in fr_win._console_body.findChildren(FlowHost)
             if isinstance(h.layout(), FlowLayout)]
    assert len(hosts) >= 2, "console toolbar/filter rows must be wrapping rows"
    for btn in (fr_win.wrap_btn, fr_win.save_btn, fr_win.time_btn,
                *fr_win._filter_btns.values(), fr_win.clear_on_run):
        assert any(btn.parentWidget() is h for h in hosts), (
            f"{getattr(btn, 'text', lambda: btn)()!r} is not in a wrapping row"
        )


def test_narrow_dock_wraps_instead_of_clipping(fr_win):
    """Below the row's natural width the row wraps instead of clipping."""
    from python.gui.widgets import FlowHost

    _settle(fr_win)
    hosts = [h for h in fr_win._console_body.findChildren(FlowHost)
             if h.layout() is not None]
    toolbar = next(h for h in hosts if fr_win.save_btn.parentWidget() is h)
    single_row = max(b.sizeHint().height() for b in
                     (fr_win.wrap_btn, fr_win.clear_btn, fr_win.copy_btn,
                      fr_win.save_btn, fr_win.time_btn))
    assert toolbar.heightForWidth(150) > single_row, "row should wrap when narrow"
    # Wrapping never squeezes a label.
    for btn in (fr_win.wrap_btn, fr_win.clear_btn, fr_win.copy_btn,
                fr_win.save_btn, fr_win.time_btn):
        _assert_not_truncated(btn)


def test_console_rows_fit_the_narrowest_dock(fr_win):
    """No console row demands more width than the narrowest allowed dock.

    When a row's layout minimum exceeds the dock width, Qt squeezes *every*
    child of that row — that is how Spanish "Siguiente" lost its last pixel.
    """
    from PyQt6.QtWidgets import QLayout

    _settle(fr_win)
    limit = fr_win._DOCK_MIN_CONSOLE
    rows = []
    for widget in fr_win._console_body.findChildren(QWidget):
        lay = widget.layout()
        if isinstance(lay, QLayout) and lay.count():
            rows.append((widget, lay.minimumSize().width()))
    assert rows, "console body has no laid-out rows"
    too_wide = [(lay.minimumSize().width(), widget.objectName())
                for widget, lay in [(w, w.layout()) for w, _ in rows]
                if lay.minimumSize().width() > limit]
    assert not too_wide, f"console rows wider than {limit}px: {too_wide}"


def test_spanish_nav_chips_are_not_clipped(test_window):
    """A long translation in another language ('Siguiente') stays whole."""
    from python.gui import i18n

    app = QApplication.instance()
    translator = i18n.install(app, "es")
    assert translator is not None
    try:
        w = test_window(_DOCK_KEYS)
        w.resize(1366, 736)
        w.show()
        _settle(w, 15)
        assert w.find_next_btn.text() == "Siguiente"
        for btn in (w.find_next_btn, w.find_prev_btn, w.regex_btn,
                    w.search_clear_btn):
            _assert_not_truncated(btn)
    finally:
        app.removeTranslator(translator)
        i18n.reset_for_tests()


def test_flow_row_helper_wraps_and_keeps_full_widths():
    """``flow_row`` returns a wrapping host: 4 wide buttons need 2+ rows at 200px."""
    from python.gui.widgets import FlowHost, FlowLayout, flow_row

    host, row = flow_row(spacing=8)
    assert isinstance(host, FlowHost)
    assert isinstance(row, FlowLayout)
    buttons = []
    for _ in range(4):
        b = QPushButton("Avertissements")
        buttons.append(b)
        row.addWidget(b)
    host.resize(200, 200)
    host.show()
    QApplication.processEvents()
    needed = host.heightForWidth(200)
    assert needed > max(b.sizeHint().height() for b in buttons) * 1.5, (
        "four 'Avertissements' buttons did not wrap inside 200px "
        f"(height={needed})"
    )
    for b in buttons:
        assert b.width() >= b.sizeHint().width()


@pytest.mark.parametrize("section", ["settings", "mtk", "fus", "general"])
def test_pages_fit_viewport_in_french(fr_win, section):
    """No page needs a horizontal scrollbar just because the UI is French."""
    fr_win.resize(1366, 736)
    fr_win._on_section(section)
    _settle(fr_win, 12)
    page = fr_win._stack.currentWidget()
    viewport = fr_win._page_scroll.viewport().width()

    overflowing = [
        (w.minimumSizeHint().width(), type(w).__name__,
         getattr(w, "text", lambda: "")())
        for w in page.findChildren(QWidget)
        if w.minimumSizeHint().width() > viewport
    ]
    assert not overflowing, (
        f"{section}: widgets wider than the {viewport}px viewport in French: "
        f"{overflowing[:5]}"
    )

    # Inner ops scroll areas must not need a horizontal bar either.
    from PyQt6.QtWidgets import QScrollArea

    for area in page.findChildren(QScrollArea):
        assert area.horizontalScrollBar().maximum() == 0, (
            f"{section}: inner scroll area overflows in French"
        )


def test_settings_action_buttons_grow_with_their_label(fr_win):
    """Settings row buttons keep their baseline as a minimum, not a maximum."""
    fr_win._on_section("settings")
    _settle(fr_win, 12)
    for btn in (fr_win._check_updates_btn, fr_win._apply_patch_btn):
        _assert_not_truncated(btn)
    # "Check for Updates Now" needs well over the 200 px English baseline.
    assert fr_win._check_updates_btn.width() > 200


def test_browse_button_grows_for_french_label(fr_win):
    """MTK's Browse button is 'Parcourir...' wide in French — not clipped."""
    fr_win._on_section("mtk")
    _settle(fr_win, 12)
    browse = [b for b in fr_win.findChildren(QPushButton)
              if b.text() == "Parcourir..."]
    assert browse, "expected the translated MTK browse buttons"
    for btn in browse:
        _assert_not_truncated(btn)


def _caption_of(card):
    """The uppercase caption label inside a :class:`MetricCard`."""
    from PyQt6.QtWidgets import QLabel

    caps = [lab for lab in card.findChildren(QLabel)
            if lab.wordWrap() and lab.text().isupper()]
    assert len(caps) == 1, f"expected one caption label, got {len(caps)}"
    return caps[0]


def test_device_metric_captions_are_translated_and_wrap(fr_win):
    """Tile captions follow the language and wrap instead of widening the panel."""
    _settle(fr_win)
    card = fr_win.info["Device Model"]
    cap = _caption_of(card)
    assert cap.text() == "MODÈLE DE L'APPAREIL"
    # Wrapping is what keeps the panel at its design width.
    assert cap.width() >= min(cap.minimumSizeHint().width(), card.width() - 30)
    assert cap.height() >= cap.fontMetrics().height()


def test_device_panel_does_not_squeeze_the_page_in_french(fr_win):
    """A longer translated caption must not widen the panel.

    The page keeps whatever width the splitter gives it: the panel's minimum is
    what used to grow from 228 to 303 px in Russian and drag the page behind a
    horizontal scrollbar.
    """
    fr_win.resize(1366, 736)
    fr_win._on_section("general")
    _settle(fr_win, 12)
    panel = fr_win._conn
    assert panel.minimumSizeHint().width() <= 240, (
        "the device panel grew with French labels: "
        f"{panel.minimumSizeHint().width()}px"
    )
    assert fr_win.info_copy_btn.width() <= panel.width(), (
        "the copy-info button is wider than the panel it sits in"
    )

def test_settings_category_labels_are_translated(fr_win):
    """The five settings categories are looked up in the catalog, not hard-coded."""
    fr_win._on_section("settings")
    _settle(fr_win, 12)
    labels = {key: btn._label for key, btn in fr_win._settings_cats.items()}
    assert labels == {
        "general": "Général",
        "updates": "Mises à jour",
        "appearance": "Apparence",
        "tools": "Outils",
        "about": "À propos",
    }


def test_elided_button_never_widens_its_parent():
    """``ElidedButton`` reports no minimum width, so a column cannot grow."""
    from PyQt6.QtWidgets import QFrame, QHBoxLayout

    from python.gui.widgets import ElidedButton

    frame = QFrame()
    frame.setFixedWidth(140)
    lay = QHBoxLayout(frame)
    lay.setContentsMargins(0, 0, 0, 0)
    btn = ElidedButton("Копировать информацию об устройстве")
    lay.addWidget(btn)
    frame.show()
    QApplication.processEvents()
    assert btn.minimumSizeHint().width() == 0
    assert btn.sizeHint().width() <= btn._MAX_HINT
    assert btn.width() <= 140
    assert frame.width() == 140



def test_settings_row_titles_wrap(fr_win):
    """A long translated row title wraps instead of raising the page minimum."""
    from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

    host = QWidget()
    lay = QVBoxLayout(host)
    fr_win._settings_row(
        lay,
        "Автоматическая проверка обновлений",
        "Автоматически проверять новые версии при запуске.",
    )
    title = next(lab for lab in host.findChildren(QLabel)
                 if lab.text().startswith("Автоматическая"))
    assert title.wordWrap(), "settings row titles must wrap when translated"
    assert title.heightForWidth(title.width()) >= title.fontMetrics().height()
