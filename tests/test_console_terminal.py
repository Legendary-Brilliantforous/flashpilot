"""Console terminal features (S2b) regression tests.

Covers the terminal slice layered onto the S2a console dock:

* ANSI SGR sequences are stripped from ``_log_buffer`` (so search / copy /
  save stay clean) and mapped onto theme-token transcript colours.
* The ``[HH:MM:SS]`` timestamp prefix is a render-only toggle, persisted as
  ``console/timestamps`` and reflowed through ``_rebuild_console``.
* Regex find mode (``console/regex``) drives both the highlight and the line
  filter; an invalid regex never raises and matches nothing.
* Batched flushing coalesces widget appends: the first line of a burst renders
  synchronously, the rest flush in order without loss (10k lines).
* The transcript right-click menu exposes the documented actions and its
  checkable toggles stay in sync with the toolbar chips.

    QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \\
        tests/test_console_terminal.py -q
"""
import os
from contextlib import contextmanager

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@contextmanager
def _qt_messages():
    """Capture every Qt message emitted inside the block.

    Qt renders ``QTextCursor::setPosition: Position 'N' out of range`` (and
    other qWarning/qCritical output) through the installed message handler; a
    regression here used to surface as a warning on stderr — and, at
    interpreter exit, occasionally as a SIGSEGV.
    """
    from PyQt6.QtCore import qInstallMessageHandler

    messages = []

    def _handler(_mode, _ctx, msg):
        messages.append(msg)

    previous = qInstallMessageHandler(_handler)
    try:
        yield messages
    finally:
        qInstallMessageHandler(previous)


@pytest.fixture(scope="module")
def win(test_window):
    # Defaults for the two persisted terminal prefs so construction is
    # deterministic regardless of a previous run's settings.
    return test_window(("console/timestamps", "console/regex"))


def _reset(win, timestamps=True):
    """Return the console to a known state (no search, all filters on)."""
    win._clear_console()
    win.find_edit.clear()
    win._set_regex_mode(False, persist=False)
    win._set_timestamps(timestamps, persist=False)
    for level in ("err", "warn", "ok", "info"):
        win._filter[level] = True
        win._filter_btns[level].setChecked(True)


def _fmt_at(doc, start, length=1):
    from PyQt6.QtGui import QTextCursor

    cur = QTextCursor(doc)
    cur.setPosition(start)
    cur.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
    return cur.charFormat()


# --------------------------------------------------------------------------
# 1. ANSI support
# --------------------------------------------------------------------------
def test_ansi_stripped_from_buffer_and_mapped_to_colour(win):
    from PyQt6.QtGui import QColor, QFont

    from python.gui.theme import C

    _reset(win, timestamps=False)
    win.log_line("\x1b[31mred\x1b[0m and \x1b[1;32mbold green\x1b[0m tail")

    # Stored (and rendered) text is ANSI-free.
    assert win._log_buffer[-1] == ("info", "red and bold green tail")
    assert "\x1b" not in win._log_buffer[-1][1]
    text = win.log.toPlainText()
    assert "\x1b" not in text
    assert "red and bold green tail" in text

    # ...and the runs carry the mapped theme colours / weight.
    doc = win.log.document()
    red_pos = text.index("red")
    assert _fmt_at(doc, red_pos, 3).foreground().color().name() == \
        QColor(C["err"]).name()
    green_pos = text.index("bold green")
    fmt = _fmt_at(doc, green_pos, len("bold green"))
    assert fmt.foreground().color().name() == QColor(C["ok"]).name()
    assert fmt.fontWeight() >= QFont.Weight.Bold.value


def test_ansi_absent_line_is_unchanged(win):
    _reset(win, timestamps=False)
    win.log_line("plain ascii line")
    assert win._log_buffer[-1] == ("info", "plain ascii line")
    assert "plain ascii line" in win.log.toPlainText()


def test_parse_ansi_tolerates_malformed_and_partial():
    from python.gui.widgets import parse_ansi

    plain, spans = parse_ansi("\x1b[1;36mhead\x1b[0m body")
    assert plain == "head body"
    assert spans and spans[0][0] == 0 and spans[0][1] == 4
    assert spans[0][2]["bold"] is True
    assert spans[0][2]["fg"] == "accent"

    # Partial / malformed / unknown sequences must never raise.
    for junk in ("\x1b", "\x1b[", "\x1b[3", "\x1b[999;abc_m", "ok\x1b[mmore",
                 "\x1b[2K", "\x1b[?25h", "\x1b[38;5;9mx"):
        parse_ansi(junk)
    assert parse_ansi("\x1b[38;5;9mx")[0] == "x"
    assert parse_ansi("\x1b[?25hkeep")[0] == "keep"


# --------------------------------------------------------------------------
# 2. Timestamps toggle
# --------------------------------------------------------------------------
def test_timestamps_toggle_persists_and_reflows(win):
    import re

    _reset(win, timestamps=True)
    win._set_timestamps(True)
    win.log_line("stamp me")
    assert re.search(r"\[\d\d:\d\d:\d\d\] stamp me", win.log.toPlainText())
    assert win.settings.value("console/timestamps", type=bool) is True
    # The stored buffer stays timestamp-free (render concern only).
    assert ("info", "stamp me") in win._log_buffer

    # Toggling off hides the prefix and persists the change.
    win._set_timestamps(False)
    assert win.settings.value("console/timestamps", type=bool) is False
    text = win.log.toPlainText()
    assert "stamp me" in text
    assert re.search(r"\[\d\d:\d\d:\d\d\]", text) is None

    # Reflow back on via the buffer (no duplicated/th stamped text).
    win._set_timestamps(True)
    assert re.search(r"\[\d\d:\d\d:\d\d\] stamp me", win.log.toPlainText())


def test_timestamps_applied_on_construction(test_window, win):
    """A persisted ``console/timestamps=False`` is honoured at build time."""
    from PyQt6.QtCore import QSettings

    _ = win  # build the module window first so this extra build is isolated
    settings = QSettings("FlashPilot", "FlashingTool")
    settings.setValue("console/timestamps", False)
    settings.setValue("console/regex", True)
    try:
        fresh = test_window()
        assert fresh._show_timestamps is False
        assert fresh.time_btn.isChecked() is False
        assert fresh._console_regex is True
        assert fresh.regex_btn.isChecked() is True
    finally:
        settings.setValue("console/timestamps", True)
        settings.setValue("console/regex", False)


# --------------------------------------------------------------------------
# 3. Regex find
# --------------------------------------------------------------------------
def test_regex_mode_filters_and_highlights(win):
    _reset(win, timestamps=False)
    for msg in ("alpha 123", "beta 456", "no digits here"):
        win.log_line(msg)
    win._flush_console()

    win._set_regex_mode(True)
    assert win.settings.value("console/regex", type=bool) is True
    win.find_edit.setText(r"\d{3}")

    assert win._console_search_matches("gamma 789") is True
    assert win._console_search_matches("no digits") is False

    visible = win.log.toPlainText()
    assert "alpha 123" in visible and "beta 456" in visible
    assert "no digits here" not in visible

    # Highlight selections are produced for regex matches too.
    selections = win.log.extraSelections()
    assert len(selections) >= 2
    for sel in selections:
        assert sel.cursor.selectedText().isdigit()

    # Next/Prev still navigate in regex mode.
    from PyQt6.QtGui import QTextCursor

    win.log.moveCursor(QTextCursor.MoveOperation.Start)
    win._find_nav(1)
    assert win.log.textCursor().selectedText().isdigit()


def test_plain_mode_is_unchanged_substring(win):
    _reset(win, timestamps=False)
    win.log_line("Hello World")
    win.find_edit.setText("hello")  # case-insensitive substring
    assert win._console_search_matches("HELLO there") is True
    assert "Hello World" in win.log.toPlainText()
    assert win._console_regex is False


def test_invalid_regex_does_not_raise(win):
    _reset(win, timestamps=False)
    win.log_line("alpha 123")
    win._set_regex_mode(True)
    win.find_edit.setText("([unclosed")  # invalid

    # Must not raise and must match nothing (console empties).
    assert win._console_search_matches("anything") is False
    assert win.log.toPlainText().strip() == ""
    assert "Invalid" in win.find_edit.toolTip()
    win._find_nav(1)
    win._find_nav(-1)

    # Recovering to a valid pattern restores matching.
    win.find_edit.setText(r"\d+")
    assert win._console_search_matches("alpha 123") is True
    assert win.find_edit.toolTip() == ""

    # ...and turning regex mode back off returns to substring semantics.
    win._set_regex_mode(False)
    win.find_edit.setText("alpha")
    assert win._console_search_matches("alpha") is True
    assert win.settings.value("console/regex", type=bool) is False


# --------------------------------------------------------------------------
# 4. Batched flush
# --------------------------------------------------------------------------
def test_first_line_is_synchronous_then_batches(win):
    _reset(win, timestamps=False)
    win.log_line("sync-line")
    assert "sync-line" in win.log.toPlainText()

    win.log_line("queued-line")
    assert win._pending_console, "second line of a burst should be queued"
    assert "queued-line" not in win.log.toPlainText()

    win._flush_console()
    assert "queued-line" in win.log.toPlainText()
    assert not win._pending_console


def test_batching_preserves_order_without_loss_10k(win):
    _reset(win, timestamps=False)
    n = 10000
    win.log_line("L0")
    assert "L0" in win.log.toPlainText()  # first line, no timer wait

    for i in range(1, n):
        win.log_line(f"L{i}")
    win._flush_console()

    # Widget caps at 4000 blocks: the trailing lines, in exact order, remain.
    rendered = win.log.toPlainText().splitlines()
    assert rendered == [f"L{i}" for i in range(n - 4000, n)]

    # Buffer/parallel-list stay aligned and honour the 6000/2000 cap.
    assert len(win._log_buffer) == len(win._log_ansi)
    assert 2000 <= len(win._log_buffer) <= 6000
    assert win.console_count.text() == f"{len(win._log_buffer)} lines"
    assert not win._pending_console


def test_flush_appends_once_per_batch_not_per_line(win):
    """Regression guard for the O(n^2) per-line append cost.

    ``appendPlainText`` is O(document length) because ``maxBlockCount`` trims
    the front on every call, so appending one call per line made a burst
    quadratic. The flush must coalesce a batch into a single call, so the
    append-call count tracks the number of *flushes* (~n / _CONSOLE_FLUSH_MAX),
    not the number of lines. Counting calls is deterministic — no wall-clock
    assertion here on purpose (those are flake-prone).
    """
    _reset(win, timestamps=False)
    calls = []
    original = win.log.appendPlainText

    def spy(text):
        calls.append(text)
        return original(text)

    win.log.appendPlainText = spy
    try:
        n = 3000
        win.log_line("L0")
        for i in range(1, n):
            win.log_line(f"L{i}")
        win._flush_console()
    finally:
        del win.log.appendPlainText

    # 1 synchronous first line + n / 200 batches, comfortably under 30.
    assert len(calls) <= 30, (
        f"{len(calls)} appendPlainText calls for {n} lines — the flush is "
        "appending per line again (O(n^2)) instead of per batch")
    # Nothing dropped, order exact (3000 < the 4000-block widget cap).
    assert win.log.toPlainText().splitlines() == [f"L{i}" for i in range(n)]


def test_base_level_runs_keep_level_and_accent_colours(win):
    """The grouped merge must preserve the exact per-level/prefix colours.

    The base format is now merged once per consecutive run of same-key lines;
    this pins that the run grouping did not flatten a mixed transcript (each
    level, and the accent flow-marker prefix, keeps its own colour).
    """
    from PyQt6.QtGui import QColor, QFont

    from python.gui.theme import C

    _reset(win, timestamps=False)
    win.log_line("plain info")
    win.log_line("[step] caution")
    win.log_line("Done ok")
    win.log_line("[error] broken")
    win.log_line(">>> flow heading")
    win.log_line("== running flow: z")
    win._flush_console()

    text = win.log.toPlainText()
    doc = win.log.document()
    expected = {
        "plain info": C["text"],
        "[step] caution": C["warn"],
        "Done ok": C["ok"],
        "[error] broken": C["err"],
        ">>> flow heading": C["accent_hi"],
        "== running flow: z": C["accent_hi"],
    }
    for line, colour in expected.items():
        pos = text.index(line)
        assert _fmt_at(doc, pos, 1).foreground().color().name() == \
            QColor(colour).name(), f"{line!r} lost its colour"
    # The accent run also carries the heavier weight on its first line.
    first = text.index(">>> flow heading")
    assert _fmt_at(doc, first, 1).fontWeight() >= QFont.Weight.DemiBold.value


# --------------------------------------------------------------------------
# 5. Right-click context menu
# --------------------------------------------------------------------------
def _menu_actions(win):
    menu = win._build_console_menu()
    return menu, {a.text(): a for a in menu.actions() if not a.isSeparator()}


def test_context_menu_exposes_documented_actions(win):
    _reset(win, timestamps=False)
    menu, actions = _menu_actions(win)
    for label in ("Copy selection", "Copy all", "Save…", "Clear", "Find…",
                  "Wrap lines", "Timestamps", "Regex search"):
        assert label in actions, f"missing context-menu action: {label}"


def test_context_menu_copy_and_clear_invoke_handlers(win):
    from PyQt6.QtWidgets import QApplication

    _reset(win, timestamps=False)
    win.log_line("menu target line")
    win._flush_console()
    _menu, actions = _menu_actions(win)

    actions["Copy all"].trigger()
    assert "menu target line" in QApplication.clipboard().text()

    actions["Clear"].trigger()
    assert win._log_buffer == []
    assert win.log.toPlainText().strip() == ""


def test_context_menu_toggles_keep_chips_in_sync(win):
    _reset(win, timestamps=True)
    win._set_regex_mode(True)
    _menu, actions = _menu_actions(win)

    assert actions["Timestamps"].isChecked() is True
    assert actions["Regex search"].isChecked() is True
    assert actions["Wrap lines"].isChecked() is win._console_wrap_enabled()

    actions["Timestamps"].trigger()
    assert win._show_timestamps is False
    assert win.time_btn.isChecked() is False

    actions["Regex search"].trigger()
    assert win._console_regex is False
    assert win.regex_btn.isChecked() is False

    before = win.log.lineWrapMode()
    actions["Wrap lines"].trigger()
    assert win.log.lineWrapMode() is not before
    assert win.wrap_btn.text() in ("Wrap", "NoWrap")
    _reset(win, timestamps=True)


# --------------------------------------------------------------------------
# 6. Chip <-> state regression (S2c)
#
# The chips are checkable QPushButtons. They used to be wired
# ``clicked -> _toggle_*``, so a programmatic ``setChecked`` (which does not
# emit ``clicked``) silently desynced the button from the render mode. They are
# now wired ``toggled -> _set_*``: the button state *is* the source of truth.
# --------------------------------------------------------------------------
def test_time_chip_setchecked_drives_timestamp_render(win):
    import re

    _reset(win, timestamps=True)
    win.log_line("chip-stamp")
    assert re.search(r"\[\d\d:\d\d:\d\d\] chip-stamp", win.log.toPlainText())

    # Programmatic uncheck must hide the prefix (old bug kept rendering it).
    win.time_btn.setChecked(False)
    assert win._show_timestamps is False
    win._rebuild_console()
    text = win.log.toPlainText()
    assert "chip-stamp" in text
    assert re.search(r"\[\d\d:\d\d:\d\d\]", text) is None

    # Re-check restores it — still via the button state.
    win.time_btn.setChecked(True)
    assert win._show_timestamps is True
    win._rebuild_console()
    assert re.search(r"\[\d\d:\d\d:\d\d\] chip-stamp", win.log.toPlainText())
    _reset(win, timestamps=True)


def test_regex_chip_setchecked_drives_search_mode(win):
    _reset(win, timestamps=False)
    win.log_line("alpha 123")
    win.log_line("no digits here")
    win._flush_console()

    win.regex_btn.setChecked(True)
    assert win._console_regex is True
    win.find_edit.setText(r"\d{3}")
    visible = win.log.toPlainText()
    assert "alpha 123" in visible
    assert "no digits here" not in visible

    win.regex_btn.setChecked(False)
    assert win._console_regex is False
    assert win.find_edit.toolTip() == ""
    win.find_edit.clear()
    _reset(win, timestamps=True)


# --------------------------------------------------------------------------
# 7. Multi-line messages (S2d regression)
#
# ``appendPlainText`` opens a new paragraph, so a message containing ``\n``
# spans several blocks. The old code derived the merge range from
# ``document().lastBlock()`` and added ``msg.count("\n")`` extra characters,
# overshooting the document end and emitting
# ``QTextCursor::setPosition: Position 'N' out of range`` for every
# multi-line line. These tests capture Qt's message handler and assert the
# warning (or any other Qt message) never fires again.
# --------------------------------------------------------------------------
def test_multiline_message_renders_without_qt_warning(win):
    _reset(win, timestamps=False)
    with _qt_messages() as msgs:
        win.log_line("line one\nline two\nline three")
        win._flush_console()
    assert msgs == [], f"unexpected Qt messages: {msgs}"

    text = win.log.toPlainText()
    for line in ("line one", "line two", "line three"):
        assert line in text


def test_multiline_keeps_buffer_and_ansi_alignment(win):
    _reset(win, timestamps=False)
    win.log_line("one\ntwo")
    win.log_line("single")

    # One buffer entry (and one parallel ANSI entry) per log_line call,
    # regardless of how many lines the message spans.
    assert len(win._log_buffer) == len(win._log_ansi)
    assert win._log_buffer[-2] == ("info", "one\ntwo")
    assert "\x1b" not in win._log_buffer[-2][1]
    assert win._log_ansi[-2] == "one\ntwo"
    assert win._log_buffer[-1] == ("info", "single")


def test_ansi_span_crossing_newline_colours_each_line(win):
    from PyQt6.QtGui import QColor

    from python.gui.theme import C

    _reset(win, timestamps=False)
    with _qt_messages() as msgs:
        win.log_line("\x1b[31mred line\nstill red\x1b[0m plain tail")
        win._flush_console()
    assert msgs == [], f"unexpected Qt messages: {msgs}"

    text = win.log.toPlainText()
    assert "red line" in text and "still red" in text and "plain tail" in text

    doc = win.log.document()
    err = QColor(C["err"]).name()
    for word in ("red line", "still red"):
        pos = text.index(word)
        assert _fmt_at(doc, pos, len(word)).foreground().color().name() == err, \
            f"{word!r} lost its colour across the newline"
    # The un-coloured tail keeps the base colour, not the span colour.
    ppos = text.index("plain tail")
    assert _fmt_at(doc, ppos, len("plain tail")).foreground().color().name() != err


def test_multiline_base_level_and_timestamp_span_lines(win):
    from PyQt6.QtGui import QColor

    from python.gui.theme import C

    _reset(win, timestamps=True)
    with _qt_messages() as msgs:
        win.log_line("[error] boom\n[error] again")
        win._flush_console()
    assert msgs == [], f"unexpected Qt messages: {msgs}"

    text = win.log.toPlainText()
    assert "boom" in text and "again" in text

    doc = win.log.document()
    err = QColor(C["err"]).name()
    # The err level format covers every line of the message.
    for word in ("boom", "again"):
        pos = text.index(word)
        assert _fmt_at(doc, pos, len(word)).foreground().color().name() == err
    # The timestamp prefix is dim and only on the first line.
    assert _fmt_at(doc, 0, 1).foreground().color().name() == QColor(C["dim"]).name()
    second = text.index("[error] again")
    assert _fmt_at(doc, second, 1).foreground().color().name() == err


def test_multiline_message_at_max_block_count(win):
    _reset(win, timestamps=False)
    # Overfill the widget so ``maxBlockCount(4000)`` trims the document on
    # every subsequent append (the case that shifted block positions).
    for i in range(4100):
        win.log_line(f"filler-{i}")
    win._flush_console()
    assert win.log.document().blockCount() == 4000

    with _qt_messages() as msgs:
        win.log_line("multi at cap\nsecond cap line\nthird cap line")
        win._flush_console()
    assert msgs == [], f"unexpected Qt messages: {msgs}"

    tail = win.log.toPlainText().splitlines()[-3:]
    assert tail == ["multi at cap", "second cap line", "third cap line"]
    assert win.log.document().blockCount() == 4000


def test_multiline_message_after_rebuild(win):
    _reset(win, timestamps=False)
    with _qt_messages() as msgs:
        win.log_line("pre rebuild\nsecond pre")
        win._flush_console()
        win._rebuild_console()
        win.log_line("post rebuild\nsecond post")
        win._flush_console()
    assert msgs == [], f"unexpected Qt messages: {msgs}"

    text = win.log.toPlainText()
    for line in ("pre rebuild", "second pre", "post rebuild", "second post"):
        assert line in text

    # The rebuild re-rendered the multi-line buffer entry without duplication.
    assert text.count("second pre") == 1
    assert len(win._log_buffer) == len(win._log_ansi)
