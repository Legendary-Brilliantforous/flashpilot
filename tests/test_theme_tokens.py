"""Theme foundation (S1a): design tokens + live-accent QSS.

Guards the bugs fixed in the theme foundation slice:
* `_get_base_qss()` was a frozen import-time f-string, so switching accent
  (`C.update(ACCENT_THEMES[...])`) recolored only the accent strip, not the
  whole app.
* `_btn_danger()` hardcoded its focus colour instead of the `err_hi` token.
* `_BASE_QSS` declared `QScrollBar` twice with conflicting radius/width.

Pure/PyQt-free: only `python.gui.theme` is imported, so no QApplication is
needed and the tests stay headless.
"""
import re

from python.gui import theme


def test_get_base_qss_reflects_current_accent():
    """A mutated accent must show up in freshly generated QSS (pre-fix: stale)."""
    saved = theme.C["accent"]
    try:
        theme.C["accent"] = "#123456"
        assert "#123456" in theme._get_base_qss()
    finally:
        theme.C["accent"] = saved


def test_btn_danger_uses_err_hi_token():
    """The danger focus colour must come from the `err_hi` token, not a literal."""
    saved = theme.C["err_hi"]
    try:
        before = theme._btn_danger()
        theme.C["err_hi"] = "#010203"
        after = theme._btn_danger()
        assert before != after
        assert "#010203" in after
        assert "QPushButton:focus { border-color: #010203; }" in after
    finally:
        theme.C["err_hi"] = saved


def test_design_tokens_match_design_md():
    """Tokens exist and match the design.md scales exactly."""
    assert theme.SPACE == {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24}
    assert theme.RADIUS == {"sm": 8, "md": 10, "lg": 12, "xl": 14, "xxl": 16}
    assert theme.FONT_FAMILY == (
        '"Inter", "Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif'
    )
    assert theme.FONT_MONO == '"JetBrains Mono", "Consolas", "Menlo", monospace'
    assert theme.FONT_SIZE == {"caption": 8, "small": 11, "base": 13, "title": 16}
    assert theme.ELEV["card"] == (0, 8, 24)
    assert theme.ELEV["popup"] == (0, 18, 64)
    assert {"experimental", "experimental_hi", "err_hi"} <= set(theme.C)


def test_base_qss_is_str_and_get_matches_prefix():
    """`_BASE_QSS` stays a str (some call sites concatenate) and agrees in head."""
    assert isinstance(theme._BASE_QSS, str)
    fresh = theme._get_base_qss()
    assert isinstance(fresh, str)
    # `_BASE_QSS` is a frozen import-time snapshot; compare only the
    # accent-independent head so this holds even if another test left a
    # different accent selected in the shared `C` dict.
    assert fresh.startswith(theme._BASE_QSS[:80])


def test_base_qss_declares_scrollbar_once():
    """Dedupe guard: one QScrollBar width declaration per orientation.

    Robustness choice: rather than diffing block bodies (brittle to whitespace),
    count the selector *declarations* that carry the geometry (`QScrollBar:vertical`
    / `QScrollBar:horizontal`) with a tolerant regex. Pre-fix each appeared twice
    with conflicting width (8 vs 7) and radius (4 vs 3).
    """
    qss = theme._get_base_qss()
    assert len(re.findall(r"QScrollBar:vertical\s*\{", qss)) == 1
    assert len(re.findall(r"QScrollBar:horizontal\s*\{", qss)) == 1
    # The surviving values are the intended (later) ones.
    assert "width: 7px" in qss
    assert "height: 7px" in qss
