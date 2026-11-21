"""Keep Qt's benign font-fallback notice out of the console.

When a label uses a script the requested font family cannot shape, Qt's font
database logs one warning per fallback candidate:

    qt.text.font.db: OpenType support missing for "Inter", script 11
    qt.text.font.db: OpenType support missing for "Roboto", script 11

`script 11` is Devanagari, and Inter — the UI typeface — covers Latin, Greek
and Cyrillic only, so the language picker's native names (`हिन्दी`, `العربية`,
`日本語`) trigger it at startup in *every* UI language, and an Arabic, Hindi or
CJK interface triggers it again for its own labels.

The text still renders correctly: Qt falls back per glyph and uses a font that
does have the script. The message is a diagnostic about that fallback, not an
error or a defect the operator can act on. We drop exactly that message and
forward every other Qt message unchanged, so real warnings (missing bridge,
plugin failures, ...) still reach the console.

Set ``FLASHPILOT_SHOW_FONT_WARNINGS=1`` to keep the notices for debugging.
"""
from __future__ import annotations

import os
import sys

#: Prefix of the notice to drop — the family and script number vary.
FONT_FALLBACK_PREFIX = "OpenType support missing for "

#: Enable the notices again, e.g. when checking which font actually renders.
SHOW_ENV = "FLASHPILOT_SHOW_FONT_WARNINGS"


def is_font_fallback_notice(message) -> bool:
    """True for Qt's per-candidate font fallback notice."""
    return str(message or "").startswith(FONT_FALLBACK_PREFIX)


def format_message(context, message) -> str:
    """Render a Qt message the way Qt's default handler does.

    Qt prefixes messages from a named logging category with the category
    (``qt.text.font.db: ...``) and prints default-category messages bare.
    """
    category = getattr(context, "category", None) or ""
    text = str(message or "")
    return f"{category}: {text}" if category else text


def handler(mode, context, message):
    """Qt message handler: drop the fallback notice, forward the rest."""
    if is_font_fallback_notice(message):
        return
    try:
        print(format_message(context, message), file=sys.stderr, flush=True)
    except Exception:
        pass


def install() -> bool:
    """Install :func:`handler` process-wide. Returns True when installed.

    Honours ``FLASHPILOT_SHOW_FONT_WARNINGS`` so the notices can be re-enabled
    without a code change.
    """
    if str(os.environ.get(SHOW_ENV, "") or "").strip() not in ("", "0", "false", "False"):
        return False
    try:
        from PyQt6.QtCore import qInstallMessageHandler

        qInstallMessageHandler(handler)
    except Exception:
        return False
    return True
