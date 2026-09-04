"""Left navigation rail - the signature element of commercial flashing tools.

A slim vertical strip of icon+label buttons styled as a backlit circuit-deck
switchboard. The active section is highlighted with a cyan left accent bar and
a gradient fill. Emits `section_selected(str)`.
"""

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QButtonGroup, QFrame, QPushButton, QHBoxLayout, QVBoxLayout

from .theme import C as _C
_PANEL = _C["panel"]
_INSET = _C["inset"]
_BORDER = _C["border"]
_BORDER_HI = _C["border_hi"]
_TEXT = _C["text"]
_DIM = _C["dim"]
_MUTE = _C["mute"]
_ACCENT = _C["accent"]
_GRAD_A = _C["grad_a"]
_GRAD_B = _C["grad_b"]


class _NavButton(QPushButton):
    """Painted nav item with a cyan left accent indicator when selected."""

    def __init__(self, label, glyph):
        super().__init__(f"{glyph}  {label}")
        self._label = label
        self._glyph = glyph
        self._active = False
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        f = self.font(); f.setPixelSize(11); self.setFont(f)
        self.setFixedHeight(30)
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
            grad.setColorAt(0, QColor(_ACCENT).darker(140))
            grad.setColorAt(0.55, QColor(_PANEL))
            grad.setColorAt(1, QColor(_PANEL))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(6, 3, w - 12, h - 6), 6, 6)
            # cyan left accent bar
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
        lay.setContentsMargins(4, 4, 4, 2)
        lay.setSpacing(0)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {_BORDER};")
        lay.addWidget(sep)

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


    def select(self, key):
        if key in self._buttons:
            for k, b in self._buttons.items():
                b.set_active(k == key)

    def keys(self):
        return list(self._buttons.keys())

class OemChipBar(QFrame):
    """Top OEM brand selector — bordered chips in rows (~10/row), then a slim
    tools row. Emits section_selected(str). Keeps the scene/content clean:
    OEMs on top, animation left, page fills the middle."""

    section_selected = pyqtSignal(str)

    def __init__(self, oem_items, tools=None, parent=None):
        super().__init__(parent)
        self.setObjectName("oemchipbar")
        self.setStyleSheet("QFrame#oemchipbar { background: transparent; }")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 4)
        outer.setSpacing(4)
        self._buttons = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        row = None
        for i, (key, glyph, label) in enumerate(oem_items):
            if i % 10 == 0:
                row = QHBoxLayout()
                row.setSpacing(4)
                outer.addLayout(row)
            btn = self._chip(f"{glyph}  {label}", key, accent=True)
            row.addWidget(btn)
        if row is not None:
            row.addStretch(1)

        if tools:
            trow = QHBoxLayout()
            trow.setSpacing(4)
            for key, glyph, label in tools:
                btn = self._chip(f"{glyph}  {label}", key, accent=False)
                trow.addWidget(btn)
            trow.addStretch(1)
            outer.addLayout(trow)

        outer.addStretch(1)

    def _chip(self, text, key, accent):
        b = QPushButton(text)
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        f = b.font(); f.setPixelSize(11); b.setFont(f)
        b.setFixedHeight(26)
        if accent:
            b.setStyleSheet(
                "QPushButton { color:#dbe6f2; background:rgba(24,36,55,0.72);"
                " border:1px solid rgba(255,255,255,0.09); border-radius:13px; padding:0 12px; }"
                "QPushButton:hover { border:1px solid rgba(34,211,238,0.75); color:#fff;"
                                   " background:rgba(30,45,68,0.85); }"
                "QPushButton:checked { background:#22d3ee; color:#04121a;"
                " border:1px solid #22d3ee; }"
                "QPushButton:focus { border:1px solid rgba(255,255,255,0.09); outline:none; }"
                "QPushButton:checked:focus { border:1px solid #22d3ee; outline:none; }"
            )
        else:
            b.setStyleSheet(
                "QPushButton { color:#8fa4bd; background:transparent;"
                " border:1px dashed #334155; border-radius:13px; padding:0 12px; }"
                "QPushButton:hover { border:1px solid #94a3b8; color:#e2e8f0; }"
                "QPushButton:checked { background:#94a3b8; color:#0b0f14;"
                " border:1px solid #94a3b8; }"
                "QPushButton:focus { border:1px dashed #334155; outline:none; }"
                "QPushButton:checked:focus { border:1px solid #94a3b8; outline:none; }"
            )
        b.clicked.connect(lambda _=False, k=key: self.section_selected.emit(k))
        self._group.addButton(b)
        self._buttons[key] = b
        return b

    def select(self, key):
        for k, b in self._buttons.items():
            b.setChecked(k == key)

    def keys(self):
        return list(self._buttons.keys())
