"""ActionRow — the tall, full-width action card on the device model board.

Phase 7 · slice B2. The model board used to draw every action as a short
(50px) hand-rolled ``QFrame`` whose title *and* subtitle both wrapped: a long
flow label could force the board wider than its pane and read as a ragged
multi-line block. ``ActionRow`` is the same click/tag surface — the board
still sets the ``flow_act`` / ``flow_tip`` properties on it — drawn as a
deliberate card:

* a 3px semantic **left edge** (``err`` for wipe/destructive actions, else
  ``accent_hi``) — the same risk-edge language ``MethodCard.set_risk`` paints
  in the flow browser,
* a 40x40 inset **icon tile**,
* a 13px/800 title and a **one-line elided** description that never wraps,
* an optional engine/mode **chip** and a dim ``›`` chevron.

Hover / pressed / focus are owned by this widget (QSS attribute selectors on
the ``pressed`` dynamic property), and activation is the :attr:`activated`
signal — a real class instead of a monkeypatched ``mousePressEvent``. The row
is keyboard reachable (``StrongFocus`` + Enter / Return / Space) and adds no
widgets of its own beyond the labels it draws.

It never imports the top-level application module and never routes anything.
"""
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from ..theme import C, FONT_SIZE, RADIUS, SPACE


def _alpha(color, alpha):
    """A theme token colour at a translucent ``alpha`` (0-255).

    Qt's stylesheet parser reads an 8-digit hex as ``#AARRGGBB`` (alpha
    *first*), so the CSS ``#RRGGBBAA`` form — ``f"{color}1f"`` — would be
    parsed as an opaque, different hue. The colour stays exactly the token the
    caller passed; only its alpha is derived here.
    """
    return f"#{alpha:02x}{color.lstrip('#')}"


class _ElidedLabel(QLabel):
    """A single-line label that ellipsises instead of wrapping.

    A plain ``QLabel`` reports its full text width as ``minimumSizeHint``, so
    a long description pushed the whole board wider than its pane (and, with
    wrapping on, broke into a ragged block). This label reports a zero-width
    minimum and paints the ellipsised text, so the row stays full-width and
    the text is always exactly one line. The full string is kept in
    :meth:`fullText` and in the label's ``text()``.
    """

    _MAX_HINT = 320  # never let the natural hint approach the board width

    def __init__(self, text, color, size, bold=False, parent=None):
        super().__init__(text, parent)
        self.setWordWrap(False)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self._color = QColor(color)
        font = QFont(self.font())
        font.setPixelSize(size)
        font.setBold(bold)
        self.setFont(font)

    def fullText(self):
        """The whole string, before elision."""
        return super().text()

    def sizeHint(self):
        metrics = QFontMetrics(self.font())
        return QSize(min(metrics.horizontalAdvance(self.fullText()),
                         self._MAX_HINT), metrics.height())

    def minimumSizeHint(self):
        # Zero width: the row (and the board) must never be widened by text.
        return QSize(0, QFontMetrics(self.font()).height())

    def paintEvent(self, event):  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setPen(self._color)
        metrics = QFontMetrics(self.font())
        text = metrics.elidedText(self.fullText(), Qt.TextElideMode.ElideRight,
                                  self.width())
        painter.drawText(0, 0, self.width(), self.height(),
                         int(Qt.AlignmentFlag.AlignLeft
                             | Qt.AlignmentFlag.AlignVCenter), text)


class ActionRow(QFrame):
    """One action on the model board: icon tile, title, description, chevron.

    ``accent`` is the semantic colour of the 3px left edge; ``chip`` is an
    optional ``(label, background, foreground, border)`` tuple — the board
    builds it from :func:`python.gui.common._mode_chip`, whose third colour
    (the badge's accent/border) is reused here as a single-hue pill so every
    engine badge shares one look.
    """

    activated = pyqtSignal()

    def __init__(self, title, icon, description="", accent=None, tooltip="",
                 chip=None, parent=None):
        super().__init__(parent)
        self.setObjectName("actionrow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Preferred)
        # Keyboard reachable: focus ring below, Enter / Space activates.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Needed for the `#actionrow:hover` rule to receive hover events.
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setProperty("pressed", False)
        self.setToolTip(tooltip or description)

        accent = accent or C["accent_hi"]
        self.setStyleSheet(
            f"QFrame#actionrow {{"
            f" background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border:1px solid {C['border']};"
            f" border-left:3px solid {accent};"
            f" border-radius:{RADIUS['md']}px; }}"
            f"QFrame#actionrow:hover {{ background:{C['card_hover']};"
            f" border:1px solid {C['border_hi']};"
            f" border-left:3px solid {accent}; }}"
            f"QFrame#actionrow[pressed=\"true\"] {{ background:{C['inset']};"
            f" border:1px solid {C['border_hi']};"
            f" border-left:3px solid {accent}; }}"
            f"QFrame#actionrow:focus {{ border:1px solid {C['focus_ring']};"
            f" border-left:3px solid {accent}; }}"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(SPACE["md"], SPACE["sm"], SPACE["md"], SPACE["sm"])
        lay.setSpacing(SPACE["md"])

        # Icon tile — inset fill, hairline border, 20px glyph.
        tile = QLabel(icon or "•")
        tile.setFixedSize(40, 40)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        tile.setStyleSheet(
            f"color:{C['text_hi']}; background:{C['inset']};"
            f" border:1px solid {C['border']};"
            f" border-radius:{RADIUS['md']}px; font-size:20px;"
        )
        lay.addWidget(tile)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(SPACE["xs"])
        heading = _ElidedLabel(title, C["text_hi"], FONT_SIZE["base"], bold=True)
        heading.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_col.addWidget(heading)
        desc = _ElidedLabel(description, C["dim"], FONT_SIZE["small"])
        desc.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_col.addWidget(desc)
        lay.addLayout(text_col, 1)

        if chip:
            # The 4-tuple from ``common._mode_chip`` was designed for the
            # *status* chips: a dim background + a strong foreground + a
            # third "accent" colour. Painting it verbatim made each badge a
            # different recipe (``ADB`` was a murky ``chip_blue`` pill with a
            # contrasting border; ``FASTBOOT`` a flat amber one). Here the
            # badge is instead a single-hue pill built from that third accent
            # colour alone: the accent tints the fill (low alpha), colours the
            # text, and draws the hairline border (higher alpha). The label
            # element is ignored, so every badge reads as one family while the
            # public signature stays a ``(label, bg, fg, border)`` tuple.
            chip_text, _chip_bg, _chip_fg, chip_accent = chip
            badge = QLabel(chip_text)
            badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            badge.setStyleSheet(
                f"color:{chip_accent};"
                f" background:{_alpha(chip_accent, 0x1f)};"
                f" border:1px solid {_alpha(chip_accent, 0x40)};"
                f" border-radius:{RADIUS['sm']}px; padding:2px 8px;"
                f" font-size:{FONT_SIZE['caption']}px; font-weight:800;"
                " letter-spacing:1px;"
            )
            lay.addWidget(badge)

        chevron = QLabel("›")
        chevron.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        chevron.setStyleSheet(
            f"color:{C['mute']}; background:transparent; border:none;"
            f" font-size:{FONT_SIZE['title']}px; font-weight:800;"
        )
        lay.addWidget(chevron)

    # -- interaction -------------------------------------------------------
    def _set_pressed(self, on):
        """Flip the ``pressed`` dynamic property and repolish the QSS."""
        if bool(self.property("pressed")) == bool(on):
            return
        self.setProperty("pressed", bool(on))
        style = self.style()
        style.unpolish(self)
        style.polish(self)

    def mousePressEvent(self, event):  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self._set_pressed(True)
        super().mousePressEvent(event)
        # Activation happens on press, exactly like the hand-rolled row did.
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()

    def mouseReleaseEvent(self, event):  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self._set_pressed(False)
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):  # noqa: N802 (Qt override)
        self._set_pressed(False)
        super().leaveEvent(event)

    def keyPressEvent(self, event):  # noqa: N802 (Qt override)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter,
                           Qt.Key.Key_Space):
            self.activated.emit()
            event.accept()
            return
        super().keyPressEvent(event)


__all__ = ["ActionRow"]
