"""Left navigation rail - the signature element of commercial flashing tools.

A slim vertical strip of icon+label buttons. The active section is highlighted
with a left accent bar and a gradient fill. Emits `section_selected(str)`.
"""

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QButtonGroup, QFrame, QPushButton, QVBoxLayout

_PANEL = "#10161f"
_INSET = "#0c111a"
_BORDER = "#1f2a38"
_BORDER_HI = "#31415a"
_TEXT = "#e8ebf1"
_DIM = "#98a3b4"
_MUTE = "#5c6a7e"
_ACCENT = "#3b82f6"
_GRAD_A = "#2563eb"
_GRAD_B = "#06b6d4"


class _NavButton(QPushButton):
    """Painted nav item with a left accent indicator when selected."""

    def __init__(self, label, glyph):
        super().__init__(f"{glyph}  {label}")
        self._label = label
        self._glyph = glyph
        self._active = False
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

    def set_active(self, active):
        self._active = active
        self.setChecked(active)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if self._active:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0, QColor(_ACCENT).darker(160))
            grad.setColorAt(1, QColor(_PANEL))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(6, 3, w - 12, h - 6), 9, 9)
            # left accent bar
            bar = QLinearGradient(0, 0, 4, 0)
            bar.setColorAt(0, QColor(_GRAD_A))
            bar.setColorAt(1, QColor(_GRAD_B))
            p.setBrush(bar)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(6, 8, 4, h - 16), 2, 2)

        # text
        color = QColor(_TEXT) if self._active else QColor(_DIM)
        if not self._active and self.underMouse():
            color = QColor(_TEXT)
        p.setPen(QPen(color))
        p.setFont(self.font())
        fm = p.fontMetrics()
        p.drawText(18, (h - fm.height()) // 2 + fm.ascent(), self.text())
        p.end()


class NavRail(QFrame):
    """Vertical navigation rail with section buttons."""

    section_selected = pyqtSignal(str)

    def __init__(self, sections, parent=None):
        super().__init__(parent)
        self.setObjectName("navrail")
        self.setStyleSheet(
            f"QFrame#navrail {{ background: {_PANEL};"
            f" border-right: 1px solid {_BORDER}; }}"
        )
        self.setFixedWidth(168)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(4)

        brand = QPushButton("BRILLIANT FLASHING")
        brand.setEnabled(False)
        brand.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none;"
            f" color: {_MUTE}; font-size: 11px; font-weight: 800;"
            f" letter-spacing: 2px; text-align: left; padding: 2px 12px; }}"
        )
        lay.addWidget(brand)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {_BORDER};")
        lay.addWidget(sep)
        lay.addSpacing(4)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = {}
        self._sections = list(sections)

        for key, glyph, label in self._sections:
            btn = _NavButton(label, glyph)
            btn.clicked.connect(lambda _=False, k=key: self.section_selected.emit(k))
            self._group.addButton(btn)
            lay.addWidget(btn)
            self._buttons[key] = btn

        lay.addStretch(1)

        foot = QFrame()
        foot.setFixedHeight(1)
        foot.setStyleSheet(f"background: {_BORDER};")
        lay.addWidget(foot)
        lay.addSpacing(2)

        v = QPushButton("v1.3  ·  Rust core")
        v.setEnabled(False)
        v.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none;"
            f" color: {_MUTE}; font-size: 9px; letter-spacing: 1px;"
            f" text-align: left; padding: 2px 12px; }}"
        )
        lay.addWidget(v)

    def select(self, key):
        if key in self._buttons:
            for k, b in self._buttons.items():
                b.set_active(k == key)

    def keys(self):
        return list(self._buttons.keys())