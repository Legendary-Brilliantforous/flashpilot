"""Reusable GUI widgets extracted from :mod:`python.gui.qt_app`.

Mechanically moved (verbatim) — no behaviour change.
"""

from PyQt6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from ..common import _mode_chip
from ..theme import C


class BeautifulToggle(QCheckBox):
    """Standard iOS-style animated toggle — 48×26, thumb slides with OutCubic."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thumb_pos = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(48, 26)
        self.setChecked(False)
        self._anim = None
        self.toggled.connect(self._on_toggled)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def _on_toggled(self, checked: bool):
        # If not yet visible (startup), snap without anim so toggle isn't stuck at 0
        if not self.isVisible():
            self._thumb_pos = 1.0 if checked else 0.0
            self.update()
            return
        try:
            if self._anim and self._anim.state() == QPropertyAnimation.State.Running:
                self._anim.stop()
        except Exception:
            pass
        self._anim = QPropertyAnimation(self, b"thumbPos")
        self._anim.setDuration(220)
        self._anim.setStartValue(self._thumb_pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def getThumbPos(self):
        return self._thumb_pos

    def setThumbPos(self, v: float):
        self._thumb_pos = float(v)
        self.update()

    thumbPos = pyqtProperty(float, getThumbPos, setThumbPos)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.toggle()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # Prevent double-toggle from QCheckBox base
        event.accept()

    def hitButton(self, pos):
        # Whole widget is hit area (not just indicator)
        return self.rect().contains(pos)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Disabled → muted track, no glow
        if not self.isEnabled():
            p.setBrush(QColor("#1e293b"))
            p.setPen(QPen(QColor("#334155"), 1.2))
            p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), h / 2, h / 2)
            thumb_d = h - 6
            x0 = 3
            x1 = w - thumb_d - 3
            x = x0 + (x1 - x0) * self._thumb_pos
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 35))
            p.drawEllipse(QRectF(x + 0.5, 3.5, thumb_d, thumb_d))
            p.setBrush(QColor("#94a3b8"))
            p.setPen(QPen(QColor(0, 0, 0, 25), 1))
            p.drawEllipse(QRectF(x, 2, thumb_d, thumb_d))
            p.end()
            return
        # Track
        track = QRectF(1, 1, w - 2, h - 2)
        if self.isChecked():
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0, QColor(C["grad_a"]))
            grad.setColorAt(1, QColor(C["grad_b"]))
            p.setBrush(grad)
            p.setPen(QPen(QColor(C["accent_hi"]), 1.2))
        else:
            p.setBrush(QColor(C["border"]))
            p.setPen(QPen(QColor(C["border_hi"]), 1.2))
        p.drawRoundedRect(track, h / 2, h / 2)
        # Thumb
        thumb_d = h - 6
        # Interpolate x from 3 → w - thumb_d - 3
        x0 = 3
        x1 = w - thumb_d - 3
        x = x0 + (x1 - x0) * self._thumb_pos
        # Shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 45))
        p.drawEllipse(QRectF(x + 0.5, 3.5, thumb_d, thumb_d))
        # Thumb fill
        p.setBrush(QColor("#ffffff"))
        p.setPen(QPen(QColor(0, 0, 0, 30), 1))
        p.drawEllipse(QRectF(x, 2, thumb_d, thumb_d))
        # Inner dot when on (eloquent)
        if self.isChecked():
            p.setBrush(QColor(C["accent"]))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(x + thumb_d * 0.35, 2 + thumb_d * 0.35, thumb_d * 0.30, thumb_d * 0.30))
        p.end()

    def sizeHint(self):
        return QSize(48, 26)

class SamsungSubTabs(QFrame):
    """Pill sub-tab strip: hairline chips, gradient fill when active."""
    tab_selected = pyqtSignal(str)

    def __init__(self, tabs):
        super().__init__()
        self.setObjectName("subtabs")
        self.setStyleSheet("QFrame#subtabs { background: transparent; }")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = {}
        for i, (key, label) in enumerate(tabs):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            f = b.font(); f.setPixelSize(10); f.setBold(True); b.setFont(f)
            b.setFixedHeight(26)
            b.setStyleSheet(
                "QPushButton { color:#8fa4bd; background:rgba(255,255,255,9);"
                " border:1px solid rgba(255,255,255,0.08); border-radius:13px;"
                " padding:0 14px; letter-spacing:0.6px; }"
                "QPushButton:hover { color:#e2e8f0;"
                " border-color:rgba(255,255,255,0.22); background:rgba(255,255,255,20); }"
                f"QPushButton:checked {{ color:#04121a;"
                f" background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                f" stop:0 {C['grad_b']}, stop:1 {C['grad_a']});"
                f" border: 1px solid {C['sel_border']}; }}"
                f"QPushButton:focus {{ border: 1px solid {C['focus_ring']}; outline: none; }}"
                f"QPushButton:checked:focus {{ border: 1px solid {C['sel_border']}; outline: none; }}"
            )
            if i == 0:
                b.setChecked(True)
            b.clicked.connect(lambda _=False, k=key: self.tab_selected.emit(k))
            self._group.addButton(b)
            lay.addWidget(b)
            self._buttons[key] = b
        lay.addStretch(1)

    def set_active(self, key):
        if hasattr(self, "_buttons"):
            for k, b in self._buttons.items():
                b.setChecked(k == key)

class ModeBadge(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("modebadge")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 5, 12, 5)
        lay.setSpacing(7)
        self._dot = QLabel()
        self._dot.setFixedSize(8, 8)
        lay.addWidget(self._dot)
        self._label = QLabel("NOT CONNECTED")
        self._label.setStyleSheet(
            f"color:{C['mute']}; font-size:11px; font-weight:700; letter-spacing:1px;"
        )
        lay.addWidget(self._label)
        self.set_state(None)

    def set_state(self, mode):
        label, bg, fg, dot = _mode_chip(mode)
        self._label.setText(label)
        self._label.setStyleSheet(
            f"color:{fg}; font-size:10px; font-weight:700; letter-spacing:1.5px;"
            f" font-family:'JetBrains Mono','Consolas',monospace;"
        )
        self._dot.setStyleSheet(f"background:{dot}; border-radius:4px;")
        self.setStyleSheet(
            f"QFrame#modebadge {{ background:{bg}; border:1px solid {C['border']};"
            f" border-left: 2px solid {dot}; border-radius:7px; }}"
        )

class WindowButton(QWidget):
    """Painted minimize / maximize / close button for the custom title bar."""

    clicked = pyqtSignal()

    def __init__(self, kind):
        super().__init__()
        self._kind = kind  # 'min' | 'max' | 'close'
        self._hover = False
        self._down = False
        self.setFixedSize(38, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._down = True
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._down:
            self._down = False
            if self.rect().contains(e.position().toPoint()):
                self.clicked.emit()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        if self._hover or self._down:
            bg = QColor(C["err"]) if self._kind == "close" else QColor(C["card_hover"])
            if self._down:
                bg = bg.darker(115)
            p.fillRect(r, bg)
        p.setPen(QPen(QColor(C["dim"]), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx = r.width() / 2
        cy = r.height() / 2
        if self._kind == "min":
            p.drawLine(QPoint(int(cx - 6), int(cy)), QPoint(int(cx + 6), int(cy)))
        elif self._kind == "max":
            x, y = int(cx - 6), int(cy - 5)
            p.drawRect(x, y, 12, 10)
        elif self._kind == "close":
            for d in (-5, 5):
                p.drawLine(QPoint(int(cx - d), int(cy - d)), QPoint(int(cx + d), int(cy + d)))
        p.end()

class DragBar(QWidget):
    """Mouse-drag region that moves the frameless window."""

    def __init__(self, win):
        super().__init__()
        self._win = win
        self._offset = None

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._offset = e.globalPosition().toPoint() - self._win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._offset is not None and (e.buttons() & Qt.MouseButton.LeftButton):
            self._win.move(e.globalPosition().toPoint() - self._offset)

    def mouseReleaseEvent(self, e):
        self._offset = None

class _SettingsCatButton(QPushButton):
    """Premium Windows-11 style settings category button with enhanced gradients and effects."""

    def __init__(self, glyph, label):
        super().__init__(f"{glyph}  {label}")
        self._label = label
        self._active = False
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self.setStyleSheet(
            "QPushButton { border: none; background: transparent;"
            " text-align: left; padding-left: 14px; }"
        )

    def set_active(self, a):
        self._active = a
        self.setChecked(a)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        
        # Hover effect
        is_hovered = self.underMouse()
        
        if self._active:
            # Premium active state with rich gradient
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0, QColor("#6366f1"))
            grad.setColorAt(0.5, QColor("#8b5cf6"))
            grad.setColorAt(1, QColor(C["panel"]))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(4, 2, w - 8, h - 4), 8, 8)
            
            # Premium accent bar
            bar = QLinearGradient(0, 0, 4, 0)
            bar.setColorAt(0, QColor("#6366f1"))
            bar.setColorAt(0.5, QColor("#8b5cf6"))
            bar.setColorAt(1, QColor("#22d3ee"))
            p.setBrush(bar)
            p.drawRoundedRect(QRectF(4, 10, 4, h - 20), 2, 2)
            
            # Subtle glow effect
            glow = QRadialGradient(w/2, h/2, w)
            glow.setColorAt(0, QColor(99, 102, 241, 20))
            glow.setColorAt(1, QColor(99, 102, 241, 0))
            p.setBrush(glow)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(4, 2, w - 8, h - 4), 8, 8)
        elif is_hovered:
            # Premium hover state
            hover_grad = QLinearGradient(0, 0, w, 0)
            hover_grad.setColorAt(0, QColor(255, 255, 255, 8))
            hover_grad.setColorAt(1, QColor(255, 255, 255, 4))
            p.setBrush(hover_grad)
            p.setPen(QPen(QColor(C["border_hi"]), 1))
            p.drawRoundedRect(QRectF(4, 2, w - 8, h - 4), 8, 8)
        
        # Premium text styling
        if self._active:
            color = QColor("#f8fafc")
            font_weight = QFont.Weight.Bold
        elif is_hovered:
            color = QColor(C["accent_hi"])
            font_weight = QFont.Weight.DemiBold
        else:
            color = QColor(C["dim"])
            font_weight = QFont.Weight.Medium
        
        p.setPen(QPen(color))
        font = self.font()
        font.setWeight(font_weight)
        p.setFont(font)
        fm = p.fontMetrics()
        p.drawText(20, (h - fm.height()) // 2 + fm.ascent(), self.text())
        p.end()

class _ComboItemDelegate(QStyledItemDelegate):
    """Paints dropdown items with premium dark rounded hover/selection."""

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        painter.setClipRect(opt.rect)
        r = QRectF(opt.rect).adjusted(5, 3, -5, -3)
        if opt.state & QStyle.StateFlag.State_Selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(C["accent_dim"]))
            painter.drawRoundedRect(r, 8, 8)
            text_color = QColor(C["accent_hi"])
        elif opt.state & QStyle.StateFlag.State_MouseOver:
            painter.setBrush(QColor(C["card_hover"]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(r, 8, 8)
            text_color = QColor(C["text"])
        else:
            text_color = QColor(C["dim"])
        painter.setPen(QPen(text_color))
        painter.setFont(opt.font)
        painter.drawText(
            r.adjusted(12, 0, -10, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            opt.text,
        )
        painter.restore()

    def sizeHint(self, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        fm = QFontMetricsF(opt.font)
        return QSize(int(fm.horizontalAdvance(opt.text) + 34), int(fm.height() + 22))
