"""MethodCard — the single flow-action button widget (Phase 7).

A drop-in for the plain ``QPushButton`` the flow renderer used to build: the
same text, the same ``_btn_ghost()`` stylesheet and the same
no-focus / no-auto-default / pointing-hand / tooltip behaviour, so the
rendered widget tree and the page's button text set (``btn_sha``) are
unchanged by its introduction.

``set_risk`` now paints the card's house-style **left edge** in the semantic
risk colour (design.md: "Cards: … accent left edge"; "semantic colors are
never accent-tinted"). It composes on top of ``_btn_ghost()`` so the
hover / pressed / focus / disabled states keep working, and it is also where
the EXPERIMENTAL amber dashed border is applied (risk ``experimental``), so a
single call fully styles the card. It never changes the text or the size.

``set_state`` stays **inert** — it only stores the value. The running spinner
/ last-result tick lands in a later slice, which is why the hook exists now.

Callers must mutate the SAME card instance (never recreate it): the window's
``_gated_buttons`` registry holds weak references to these buttons, so
recreating one would silently shrink the gate registry.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton

from ..theme import C, _btn_ghost

# Risk level -> semantic token that colours the card's left edge. Token names
# (not colours) are stored so an accent switch is picked up at call time; the
# semantic tokens themselves are never accent-tinted. Unknown / ``None`` risks
# get no edge.
_RISK_TOKEN = {
    "read": "ok",
    "medium": "warn",
    "high": "err",
    "experimental": "experimental",
}


class MethodCard(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._risk = None
        self._state = "idle"
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAutoDefault(False)
        self.setDefault(False)
        self.setStyleSheet(_btn_ghost())
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_risk(self, level):
        """Style the card for ``level`` (``read`` / ``medium`` / ``high`` /
        ``experimental``): a semantic left edge, plus the amber dashed border
        for ``experimental``. Composed with ``_btn_ghost()`` so every
        interactive state still resets the edge; the text/size never change.
        """
        self._risk = level
        qss = _btn_ghost()
        if level == "experimental":
            # EXPERIMENTAL: amber dashed border (design.md) — preserved here so
            # the card owns its full risk styling.
            amber = C["experimental"]
            qss += (
                f" QPushButton {{ border: 1px dashed {amber}; }}"
                f" QPushButton:focus {{ border: 1px dashed {amber};"
                f" outline: none; }}"
            )
        token = _RISK_TOKEN.get(level)
        if token is not None:
            edge = C[token]
            # border-left is declared AFTER _btn_ghost()'s `border` shorthand
            # and for every interactive state `_btn_ghost()` re-declares, so
            # the edge survives hover/pressed/focus/disabled.
            qss += (
                f" QPushButton {{ border-left: 3px solid {edge}; }}"
                f" QPushButton:hover {{ border-left: 3px solid {edge}; }}"
                f" QPushButton:pressed {{ border-left: 3px solid {edge}; }}"
                f" QPushButton:focus {{ border-left: 3px solid {edge}; }}"
                f" QPushButton:disabled {{ border-left: 3px solid {edge}; }}"
            )
        self.setStyleSheet(qss)

    def risk(self):
        """The stored risk level (``None`` until :meth:`set_risk` is called)."""
        return self._risk

    def set_state(self, state):
        """Store the run state ("running" / "ok" / "fail" / "idle").

        Inert for now — the spinner / result tick lands in the next slice.
        """
        self._state = state

    def state(self):
        """The stored run state (defaults to ``"idle"``)."""
        return self._state
