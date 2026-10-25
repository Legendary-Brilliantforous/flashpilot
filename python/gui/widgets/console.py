"""Reusable GUI widgets extracted from :mod:`python.gui.qt_app`.

Mechanically moved (verbatim) — no behaviour change, plus the console's ANSI
SGR handling (S2b): bridge/flow output may carry ``\\x1b[...m`` colour codes,
which are stripped from the stored text and mapped onto theme tokens.
"""

from PyQt6.QtGui import QColor, QFont, QTextDocument

from ..theme import C

# ANSI SGR foreground code -> theme token name. Basic 8 (30-37) + bright
# (90-97) are mapped onto existing tokens; the palette is deliberately lossy
# (blue/cyan/magenta collapse onto the accent pair) because no extra theme
# colours may be introduced. Unknown codes are dropped by ``apply_sgr``.
ANSI_FG = {
    30: "bg",         # black
    31: "err",        # red
    32: "ok",         # green
    33: "warn",       # yellow
    34: "accent",     # blue
    35: "accent_hi",  # magenta
    36: "accent",     # cyan
    37: "text",       # white
    90: "mute",       # bright black / grey
    91: "err_hi",     # bright red
    92: "ok",         # bright green
    93: "warn",       # bright yellow
    94: "accent_hi",  # bright blue
    95: "accent_hi",  # bright magenta
    96: "accent_hi",  # bright cyan
    97: "text_hi",    # bright white
}

_ESC = "\x1b"


def apply_sgr(state, raw_params):
    """Mutate ``state`` (dict with ``bold``/``dim``/``fg``) from an SGR payload.

    ``raw_params`` is the text between ``\\x1b[`` and the final ``m`` (e.g.
    ``"1;31"``). Empty parameters mean reset. Unknown codes are ignored.
    """
    params = raw_params.split(";") if raw_params else ["0"]
    for p in params:
        p = p.strip()
        if p == "":
            code = 0
        else:
            try:
                code = int(p)
            except ValueError:
                continue  # malformed parameter — drop, never raise
        if code == 0:
            state["bold"] = False
            state["dim"] = False
            state["fg"] = None
        elif code == 1:
            state["bold"] = True
        elif code == 2:
            state["dim"] = True
        elif code == 22:
            state["bold"] = False
            state["dim"] = False
        elif code == 39:
            state["fg"] = None
        elif code in ANSI_FG:
            state["fg"] = ANSI_FG[code]
        # any other code: unknown -> dropped (no visible effect)


def parse_ansi(text):
    """Split *text* into ``(plain, spans)``.

    ``plain`` is *text* with every escape sequence removed (safe to store,
    search, copy and save). ``spans`` is a list of ``(start, end, attrs)``
    ranges over ``plain`` carrying ``{"fg": token|None, "bold": bool,
    "dim": bool}`` for the runs that were coloured/emphasised. Malformed or
    partial escape sequences are tolerated and dropped, never raised on.
    """
    if not text:
        return "", []
    src = str(text)
    if _ESC not in src:
        return src, []

    out = []
    spans = []
    state = {"bold": False, "dim": False, "fg": None}
    span_start = 0
    i = 0
    n = len(src)

    def _close(end):
        if end > span_start and (state["bold"] or state["dim"] or state["fg"]):
            spans.append((span_start, end, dict(state)))

    while i < n:
        ch = src[i]
        if ch != _ESC:
            out.append(ch)
            i += 1
            continue
        if i + 1 >= n:
            # trailing lone ESC: drop it
            i += 1
            continue
        if src[i + 1] != "[":
            # not a CSI introducer — drop the ESC, keep the next char
            i += 1
            continue
        j = i + 2
        params_start = j
        # ECMA-48 parameter bytes: digits plus ; ? < = > (the latter only for
        # non-SGR sequences, which we drop wholesale).
        while j < n and (src[j].isdigit() or src[j] in ";?<=>"):
            j += 1
        if j >= n:
            # partial/truncated escape: drop the remainder
            break
        final = src[j]
        if not (0x40 <= ord(final) <= 0x7E):
            # malformed sequence: drop ESC + '[' and rescan
            i += 2
            continue
        # a complete sequence ends the current styled run
        _close(len(out))
        span_start = len(out)
        if final == "m":
            apply_sgr(state, src[params_start:j])
        i = j + 1

    _close(len(out))
    spans = [(s, e, a) for (s, e, a) in spans if e > s]
    return "".join(out), spans


class ConsoleHighlighter(QTextDocument):
    pass

class LogHighlighter:
    """Syntax highlight for console logs: odin, errors, success."""
    def __init__(self, doc: QTextDocument):
        from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat
        class _HL(QSyntaxHighlighter):
            def highlightBlock(hself, text):
                fmt_ok = QTextCharFormat(); fmt_ok.setForeground(QColor(C["ok"])); fmt_ok.setFontWeight(QFont.Weight.DemiBold.value if hasattr(QFont.Weight.DemiBold, 'value') else 600)
                fmt_warn = QTextCharFormat(); fmt_warn.setForeground(QColor(C["warn"]))
                fmt_err = QTextCharFormat(); fmt_err.setForeground(QColor(C["err"])); fmt_err.setFontWeight(QFont.Weight.Bold.value if hasattr(QFont.Weight.Bold, 'value') else 700)
                fmt_accent = QTextCharFormat(); fmt_accent.setForeground(QColor(C["accent_hi"]))
                fmt_dim = QTextCharFormat(); fmt_dim.setForeground(QColor(C["dim"]))
                if "[odin4]" in text: hself.setFormat(0, len(text), fmt_accent)
                elif "FAILED" in text or "BOOTLOADER_FAIL" in text: hself.setFormat(0, len(text), fmt_err)
                elif "OKAY [" in text or text.strip().startswith("OKAY"): hself.setFormat(0, len(text), fmt_ok)
                elif text.strip().startswith(">>>"): hself.setFormat(0, len(text), fmt_accent)
                elif "[ok]" in text or "successful" in text.lower(): hself.setFormat(0, len(text), fmt_ok)
                elif "[warn]" in text or "failed" in text.lower(): hself.setFormat(0, len(text), fmt_warn)
                elif "[error]" in text: hself.setFormat(0, len(text), fmt_err)
                elif text.strip().startswith("[check]"): hself.setFormat(0, len(text), fmt_dim)
        self._hl = _HL(doc)
