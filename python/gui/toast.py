"""Toast notification system - sliding dark notifications with optional progress.

A single `ToastHost` overlay lives on top of the main window's top-right corner.
Toasts animate in from the right, auto-dismiss after a duration, and can carry a
transient progress bar (used for live flash/scan operations). Colors mirror the
main theme tokens so the module stays dependency-free (no circular import).
"""

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QTimer,
    Qt,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

# Mirrors the design tokens in qt_app.C
_PANEL = "#0a111a"
_CARD = "#0d1622"
_INSET = "#070d15"
_BORDER_HI = "#2c405e"
_TEXT = "#e7eef8"
_DIM = "#8fa4bd"
_GRAD_A = "#0ea5e9"
_GRAD_B = "#22d3ee"
_OK = "#2dd4bf"
_WARN = "#fbbf24"
_ERR = "#fb7185"
_ACCENT_HI = "#7dd3fc"

_ICON = {
    "ok": _OK,
    "warn": _WARN,
    "err": _ERR,
    "info": _ACCENT_HI,
}


class _SlideFrame(QFrame):
    """A single toast card that slides in from the right."""

    def __init__(self, host, kind, title, detail, duration):
        super().__init__(host)
        self._kind = kind
        self._offset = 1.0
        accent = _ICON.get(kind, _ACCENT_HI)

        self.setFixedWidth(320)
        self.setStyleSheet(
            f"QFrame#toast {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f" stop:0 {_PANEL}, stop:1 {_CARD});"
            f" border:1px solid {_BORDER_HI}; border-left:3px solid {accent};"
            f" border-radius:9px; }}"
        )
        self.setObjectName("toast")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.setGraphicsEffect(shadow)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)

        dot = QLabel("●")
        dot.setStyleSheet(f"color:{accent}; font-size:16px;")
        dot.setFixedWidth(14)
        lay.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        self._title = QLabel(title)
        self._title.setStyleSheet(
            f"color:{_TEXT}; font-size:12px; font-weight:700;"
            f" font-family:'JetBrains Mono','Consolas',monospace;"
        )
        self._title.setWordWrap(True)
        text_box.addWidget(self._title)

        self._detail = None
        if detail:
            self._detail = QLabel(detail)
            # High-contrast detail text so warnings don't look "out of focus"
            self._detail.setStyleSheet(
                f"color:#e2e8f0; font-size:11.5px; font-weight:500; line-height:135%;"
            )
            self._detail.setWordWrap(True)
            self._detail.setTextFormat(Qt.TextFormat.PlainText)
            text_box.addWidget(self._detail)
        lay.addLayout(text_box, 1)

        self._bar = None
        if kind == "progress":
            self._bar = QProgressBar()
            self._bar.setRange(0, 1000)
            self._bar.setValue(0)
            self._bar.setTextVisible(False)
            self._bar.setFixedHeight(6)
            self._bar.setStyleSheet(
                f"QProgressBar {{ background:{_INSET}; border:none; border-radius:3px; }}"
                f" QProgressBar::chunk {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                f" stop:0 {_GRAD_A}, stop:1 {_GRAD_B}); border-radius:3px; }}"
            )
            lay.addWidget(self._bar)

        if duration > 0:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(lambda: host.dismiss(self))
            self._timer.start(duration)

        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(240)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

        self.show()

    # offset: 1.0 = fully off-screen right, 0.0 = resting position.
    def get_offset(self):
        return self._offset

    def set_offset(self, v):
        self._offset = v
        self.update()

    offset = pyqtProperty(float, get_offset, set_offset)

    def set_progress(self, value01):
        if self._bar is not None:
            self._bar.setValue(int(max(0.0, min(1.0, value01)) * 1000))

    def set_title(self, title):
        self._title.setText(title)

    def set_detail(self, detail):
        if self._detail is not None:
            self._detail.setText(detail)

    def paintEvent(self, event):
        # Slide via painter transform so the widget geometry stays put for layout
        # bookkeeping.
        p = QPainter(self)
        if self._offset > 0:
            w = self.width()
            p.translate(w * self._offset, 0)
            p.setOpacity(max(0.0, 1.0 - self._offset))
        super().paintEvent(event)
        p.end()


class ToastHost(QWidget):
    """Transparent overlay pinned to the top-right of a parent window.

    Usage:
        host = ToastHost(parent_window)
        host.show_info("Connected", "Galaxy A14 · ADB online")
        toast = host.show_progress("Flashing", "super ...")
        toast.set_progress(0.42)
    """

    _MARGIN = 16
    _GAP = 10

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._toasts = []
        self._progress = None
        self._progress_slot = None

    def _relayout(self):
        parent = self.parentWidget()
        if parent is None:
            return
        self.setGeometry(0, 0, parent.width(), parent.height())
        self.raise_()
        y = self._MARGIN
        x = parent.width() - self._MARGIN
        for toast in self._toasts:
            toast.adjustSize()
            tw = toast.width()
            toast.setGeometry(x - tw, y, tw, toast.height())
            y += toast.height() + self._GAP

    def _ensure_visible(self):
        parent = self.parentWidget()
        if parent is None or self.isVisible():
            return
        self.setGeometry(0, 0, parent.width(), parent.height())
        self.show()

    def _spawn(self, kind, title, detail, duration):
        self._ensure_visible()
        self._relayout()
        toast = _SlideFrame(self, kind, title, detail, duration)
        self._toasts.append(toast)
        self._relayout()
        return toast

    def show_info(self, title, detail="", duration=4000):
        return self._spawn("info", title, detail, duration)

    def show_ok(self, title, detail="", duration=4000):
        return self._spawn("ok", title, detail, duration)

    def show_warn(self, title, detail="", duration=6000):
        return self._spawn("warn", title, detail, duration)

    def show_error(self, title, detail="", duration=7000):
        return self._spawn("err", title, detail, duration)

    def show_progress(self, title, detail=""):
        """Returns a progress toast; update via set_progress/set_title/set_detail."""
        self.dismiss_progress()
        self._progress = self._spawn("progress", title, detail, 0)
        return self._progress

    def update_progress(self, value01, title=None, detail=None):
        if self._progress is not None:
            if title:
                self._progress.set_title(title)
            if detail:
                self._progress.set_detail(detail)
            self._progress.set_progress(value01)

    def dismiss(self, toast):
        if toast in self._toasts:
            self._toasts.remove(toast)
            toast.hide()
            toast.deleteLater()
            if self._progress is toast:
                self._progress = None
            self._relayout()

    def dismiss_progress(self):
        if self._progress is not None:
            self.dismiss(self._progress)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()