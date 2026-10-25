"""Reusable GUI widgets extracted from :mod:`python.gui.qt_app`.

Mechanically moved (verbatim) — no behaviour change.
"""

from PyQt6.QtCore import Qt, QPointF, QRectF, QSize
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from ..theme import C


class CollapsibleSection(QFrame):
    """Circuit-deck collapsible panel: a clickable header with a chevron +
    terminal title that toggles the body. Keeps dense pages (like the FLASH
    tab) to one screen - advanced panels collapse by default."""

    def __init__(self, title, body, accent=None, collapsed=False,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("colsec")
        self._title = title
        self._accent = accent or C["accent"]
        self._collapsed = collapsed
        self.setStyleSheet(
            f"QFrame#colsec {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border']}; border-left: 2px solid {accent};"
            f" border-top: 1px solid {C['border_hi']}; border-radius: 9px; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 6, 14, 8)
        lay.setSpacing(8)

        self._header = QPushButton()
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setStyleSheet("QPushButton { border: none; background: transparent; }")
        self._header.clicked.connect(self.toggle)
        lay.addWidget(self._header)

        self._body = body
        self._body.setParent(self)
        lay.addWidget(self._body)
        self._body.setVisible(not collapsed)

    def toggle(self):
        self._collapsed = not self._collapsed
        self._body.setVisible(not self._collapsed)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # chevron rendered on the header strip
        if self._collapsed:
            pts = [QPointF(14, 12), QPointF(21, 17), QPointF(14, 22)]
        else:
            pts = [QPointF(14, 16), QPointF(20, 10), QPointF(26, 16)]
        p.setBrush(QColor(self._accent))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF(pts))
        # ">>" prefix
        p.setPen(QPen(QColor(self._accent)))
        p.setFont(QFont("JetBrains Mono", 8, QFont.Weight.Bold))
        p.drawText(34, 16, ">>")
        # title
        p.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        p.setPen(QPen(QColor(C["text"])))
        p.drawText(66, 16, self._title)
        p.end()

class SectionTitle(QLabel):
    def __init__(self, text, accent=C["accent"]):
        super().__init__(text)
        self._accent = accent
        self.setStyleSheet(
            f"color:{C['dim']}; font-size:11px; font-weight:700; letter-spacing:1.5px;"
        )
        self.setContentsMargins(0, 0, 0, 0)

    def minimumSizeHint(self):
        """Reserve room for the painted ">> " prefix.

        ``paintEvent`` draws a monospace ">>" before the text, but the inherited
        label hint only covers the text itself: when a layout gives this widget
        exactly its hint (e.g. the narrow console header) the painter clips the
        last characters ("CONSOLE" -> "CONSO"). Keep the prefix in the floor so
        the label is never truncated; the dashed decoration after the text stays
        optional and may still be clipped when space is tight.
        """
        hint = QLabel.minimumSizeHint(self)
        return QSize(hint.width() + 18, hint.height())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pm = p.fontMetrics()
        x = 0
        y = pm.ascent() + 1

        # mono ">>" terminal prefix
        mono = QFont("JetBrains Mono", 8, QFont.Weight.Bold)
        p.setFont(mono)
        p.setPen(QPen(QColor(self._accent)))
        p.drawText(x, y, ">>")
        prefix_w = p.fontMetrics().horizontalAdvance(">>") + 4

        p.setFont(self.font())
        p.setPen(QPen(QColor(C["dim"])))
        p.drawText(x + prefix_w, y, self.text())

        # dashed trace line + node dot (circuit-run style)
        tw = pm.horizontalAdvance(self.text())
        lx = x + prefix_w + tw + 10
        dash = QPen(QColor(self._accent), 1.2, Qt.PenStyle.DashLine)
        p.setPen(dash)
        p.drawLine(QPointF(lx, y - 2), QPointF(lx + 56, y - 2))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._accent))
        p.drawEllipse(QRectF(lx + 58, y - 4.5, 5, 5))
        p.end()
