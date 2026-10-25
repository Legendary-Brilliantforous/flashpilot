"""Toast notification system - sliding dark notifications with optional progress.

A single `ToastHost` overlay lives on top of the main window's top-right (or
bottom-right) corner. Toasts animate in from the right, auto-dismiss after a
duration, and can carry a transient progress bar (used for live flash/scan
operations). Colors mirror the main theme tokens so the module stays
dependency-free (no circular import).

Features beyond the original host:

* At most ``_MAX_VISIBLE`` toasts on screen; the rest are queued and surfaced
  through a compact "+N more" overflow chip that shrinks as toasts dismiss.
* Auto-dismissing toasts get a thin countdown bar. Hovering a toast pauses the
  timer *and* the bar; leaving resumes with the remaining time (never restarts
  from full).
* An optional single action button on a toast.
* ``toast/position`` (top-right default, or bottom-right) is honoured.
* Reduced motion (master ``animations`` or granular ``anim_toast`` off) skips
  the slide animation, so toasts appear instantly.
"""

import time as _time

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSettings,
    QTimer,
    Qt,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter, QRegion
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .theme import C as _C
# Unified — single source, no mirror drift
_PANEL = _C["panel"]
_CARD = _C["card"]
_INSET = _C["inset"]
_BORDER_HI = _C["border_hi"]
_TEXT = _C["text"]
_DIM = _C["dim"]
_GRAD_A = _C["grad_a"]
_GRAD_B = _C["grad_b"]
_OK = _C["ok"]
_WARN = _C["warn"]
_ERR = _C["err"]
_ACCENT_HI = _C["accent_hi"]

_ICON = {
    "ok": _OK,
    "warn": _WARN,
    "err": _ERR,
    "info": _ACCENT_HI,
}

_POSITIONS = ("top-right", "bottom-right")


def _motion_enabled():
    """Honour the master ``animations`` bool and the granular ``anim_toast``.

    Mirrors how ``anim_window`` is read elsewhere (``QSettings`` + ``type=bool``
    with a safe default); a missing key means "on", exactly like the rest of the
    animation toggles.
    """
    try:
        s = QSettings("FlashPilot", "FlashingTool")
        if not s.value("animations", "true", type=bool):
            return False
        if not s.value("anim_toast", "true", type=bool):
            return False
    except Exception:
        return True
    return True


class _SlideFrame(QFrame):
    """A single toast card that slides in from the right."""

    def __init__(self, host, kind, title, detail, duration,
                 action_label=None, action_cb=None):
        super().__init__(host)
        self._host = host
        self._kind = kind
        self._animated = _motion_enabled()
        self._offset = 1.0 if self._animated else 0.0
        accent = _ICON.get(kind, _ACCENT_HI)

        # --- auto-dismiss bookkeeping (kept even for instant toasts) --------
        self._duration = max(0, int(duration))
        self._remaining = self._duration
        self._paused = False
        self._deadline = None
        self._dismiss_timer = None
        self._tick_timer = None
        self._countdown = None

        self.setFixedWidth(340)
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

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(12)

        dot = QLabel("●")
        dot.setStyleSheet(f"color:{accent}; font-size:16px;")
        dot.setFixedWidth(14)
        row.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)

        text_box = QVBoxLayout()
        text_box.setSpacing(3)
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
                f"color:#e2e8f0; font-size:11.5px; font-weight:500; line-height:145%;"
            )
            self._detail.setWordWrap(True)
            self._detail.setTextFormat(Qt.TextFormat.PlainText)
            text_box.addWidget(self._detail)

        # Optional single action button (runs the callback, then dismisses).
        self._action_btn = None
        if action_label and callable(action_cb):
            self._action_btn = QPushButton(str(action_label))
            self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._action_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._action_btn.setStyleSheet(
                f"QPushButton {{ background:transparent; color:{accent};"
                f" border:1px solid {accent}; border-radius:6px;"
                f" padding:3px 10px; font-size:10.5px; font-weight:800; }}"
                f" QPushButton:hover {{ background:{_INSET};"
                f" border-color:{_ACCENT_HI}; color:{_ACCENT_HI}; }}"
            )
            self._action_btn.clicked.connect(
                lambda _=False, cb=action_cb: self._run_action(cb))
            text_box.addWidget(self._action_btn, 0, Qt.AlignmentFlag.AlignLeft)

        row.addLayout(text_box, 1)
        outer.addLayout(row)

        # Determinate progress bar — only for ``kind == "progress"`` toasts.
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
            outer.addWidget(self._bar)

        # Thin auto-dismiss countdown bar (separate from the determinate bar).
        if self._duration > 0:
            self._countdown = QProgressBar()
            self._countdown.setRange(0, 1000)
            self._countdown.setValue(1000)
            self._countdown.setTextVisible(False)
            self._countdown.setFixedHeight(3)
            self._countdown.setStyleSheet(
                f"QProgressBar {{ background:{_INSET}; border:none; border-radius:2px; }}"
                f" QProgressBar::chunk {{ background:{accent}; border-radius:2px; }}"
            )
            outer.addWidget(self._countdown)
            self._dismiss_timer = QTimer(self)
            self._dismiss_timer.setSingleShot(True)
            self._dismiss_timer.timeout.connect(self._on_auto_dismiss)
            self._tick_timer = QTimer(self)
            self._tick_timer.setInterval(50)
            self._tick_timer.timeout.connect(self._update_countdown)
            self._start_countdown(self._duration)

        if self._animated:
            self._anim = QPropertyAnimation(self, b"offset", self)
            self._anim.setDuration(240)
            self._anim.setStartValue(1.0)
            self._anim.setEndValue(0.0)
            self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim.start()
        else:
            # Reduced motion: appear instantly, no slide.
            self._anim = None

        self.show()

    # -- animation offset (1.0 = off-screen right, 0.0 = resting) -----------
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

    # -- auto-dismiss + hover pause ----------------------------------------
    def remaining_ms(self):
        """Milliseconds left before auto-dismiss (0 for persistent toasts)."""
        if self._duration <= 0:
            return 0
        if self._paused or self._deadline is None:
            return max(0, int(self._remaining))
        return max(0, int((self._deadline - _time.monotonic()) * 1000))

    def _start_countdown(self, ms):
        ms = int(ms)
        self._remaining = ms
        if ms <= 0:
            if self._dismiss_timer is not None:
                self._dismiss_timer.start(0)
            return
        self._deadline = _time.monotonic() + ms / 1000.0
        if self._countdown is not None:
            frac = ms / float(self._duration) if self._duration > 0 else 0.0
            self._countdown.setValue(int(max(0.0, min(1.0, frac)) * 1000))
        if self._dismiss_timer is not None:
            self._dismiss_timer.start(ms)
        if self._tick_timer is not None:
            self._tick_timer.start()

    def _update_countdown(self):
        if self._countdown is None:
            return
        if self._duration <= 0:
            return
        frac = self.remaining_ms() / float(self._duration)
        self._countdown.setValue(int(max(0.0, min(1.0, frac)) * 1000))

    def pause(self):
        """Freeze the auto-dismiss timer/bar (hover). Safe when idle."""
        if self._duration <= 0 or self._paused:
            return
        self._remaining = self.remaining_ms()
        self._paused = True
        if self._dismiss_timer is not None:
            self._dismiss_timer.stop()
        if self._tick_timer is not None:
            self._tick_timer.stop()
        self._update_countdown()

    def resume(self):
        """Resume from the remaining time (never reset to the full duration)."""
        if self._duration <= 0 or not self._paused:
            return
        self._paused = False
        remaining = max(0, int(self._remaining))
        if remaining <= 0:
            self._on_auto_dismiss()
            return
        self._start_countdown(remaining)

    def enterEvent(self, event):  # noqa: N802 (Qt override)
        self.pause()

    def leaveEvent(self, event):  # noqa: N802 (Qt override)
        # Moving onto a child (e.g. the action button) keeps the toast hovered;
        # only resume once the pointer has actually left the card.
        try:
            if self.underMouse():
                return
        except Exception:
            pass
        self.resume()

    def stop_timers(self):
        for timer in (self._dismiss_timer, self._tick_timer):
            if timer is not None:
                try:
                    timer.stop()
                except Exception:
                    pass

    def _run_action(self, cb):
        try:
            cb()
        except Exception:
            pass
        try:
            self._host.dismiss(self)
        except Exception:
            pass

    def _on_auto_dismiss(self):
        if self._paused:
            return
        try:
            self._host.dismiss(self)
        except Exception:
            pass

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
    """Transparent overlay pinned to a corner of a parent window.

    Usage:
        host = ToastHost(parent_window)
        host.show_info("Connected", "Galaxy A14 · ADB online")
        toast = host.show_progress("Flashing", "super ...")
        toast.set_progress(0.42)
    """

    _MARGIN = 18
    _GAP = 12
    _MAX_VISIBLE = 3          # toasts on screen at once
    _MAX_STACK = _MAX_VISIBLE  # back-compat alias
    _SHADOW_PAD = 30          # mask padding so drop shadows are not clipped

    def __init__(self, parent, position="top-right"):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Click-through until a toast actually needs to be interactive; the
        # exact toast regions are exposed through setMask() in _relayout().
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._position = position if position in _POSITIONS else "top-right"
        self._toasts = []
        self._queue = []          # pending (kind, title, detail, duration, label, cb)
        self._progress = None
        self._progress_slot = None
        self._overflow = None

    # -- position -----------------------------------------------------------
    def position(self):
        return self._position

    def set_position(self, position):
        self._position = position if position in _POSITIONS else "top-right"
        self._relayout()

    # -- stack bookkeeping --------------------------------------------------
    def _ensure_visible(self):
        parent = self.parentWidget()
        if not self.isVisible():
            self.show()
        if parent is not None and parent.width() > 0 and parent.height() > 0:
            self.setGeometry(0, 0, parent.width(), parent.height())
        self.raise_()

    def _ensure_overflow(self):
        if self._overflow is None:
            lab = QLabel(self)
            lab.setObjectName("toast_overflow")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setStyleSheet(
                f"QLabel#toast_overflow {{ background:{_INSET};"
                f" color:{_DIM}; border:1px solid {_BORDER_HI};"
                f" border-radius:9px; padding:5px 14px; font-size:11px;"
                f" font-weight:700;"
                f" font-family:'JetBrains Mono','Consolas',monospace; }}"
            )
            self._overflow = lab
        return self._overflow

    def _update_overflow(self):
        n = len(self._queue)
        if n <= 0:
            if self._overflow is not None:
                self._overflow.hide()
            return
        lab = self._ensure_overflow()
        lab.setText(f"+{n} more")
        lab.adjustSize()
        lab.show()

    def _stack_widgets(self):
        widgets = list(self._toasts)
        if self._overflow is not None and not self._overflow.isHidden():
            widgets.append(self._overflow)
        return widgets

    def _relayout(self):
        parent = self.parentWidget()
        if parent is None:
            return
        w, h = parent.width(), parent.height()
        # A host shown before the parent has a size: keep it click-through and
        # defer geometry until a real resize arrives.
        if w <= 0 or h <= 0:
            return
        self.setGeometry(0, 0, w, h)
        self.raise_()

        widgets = self._stack_widgets()
        if not widgets:
            self.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.clearMask()
            return

        for wid in widgets:
            wid.adjustSize()
        total = sum(wid.height() for wid in widgets) + self._GAP * (len(widgets) - 1)
        if self._position == "bottom-right":
            y = h - self._MARGIN - total
            if y < self._MARGIN:
                y = self._MARGIN
        else:
            y = self._MARGIN
        right = w - self._MARGIN

        region = QRegion()
        for wid in widgets:
            tw = wid.width()
            wid.setGeometry(right - tw, y, tw, wid.height())
            # Extend the interactive region to the right edge so the slide-in
            # animation is never clipped, and pad for the drop shadow.
            rect = QRectF(
                right - tw - self._SHADOW_PAD,
                y - self._SHADOW_PAD,
                tw + self._SHADOW_PAD + self._MARGIN,
                wid.height() + self._SHADOW_PAD * 2,
            )
            region = region.united(QRegion(rect.toRect()))
            y += wid.height() + self._GAP

        # Interactive only where the toasts are; the rest of the overlay stays
        # click-through so the underlying UI keeps working.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMask(region)

    def _add_card(self, kind, title, detail, duration, action_label, action_cb):
        toast = _SlideFrame(self, kind, title, detail, duration,
                            action_label, action_cb)
        self._toasts.append(toast)
        self._update_overflow()
        self._relayout()
        return toast

    def _promote(self):
        while self._queue and len(self._toasts) < self._MAX_VISIBLE:
            spec = self._queue.pop(0)
            self._add_card(*spec)

    def _spawn(self, kind, title, detail, duration, *,
               action_label=None, action_cb=None):
        self._ensure_visible()
        if len(self._toasts) >= self._MAX_VISIBLE:
            # Deterministic cap: queue it and surface the overflow chip.
            self._queue.append((kind, title, detail, duration,
                                action_label, action_cb))
            self._update_overflow()
            self._relayout()
            return None
        return self._add_card(kind, title, detail, duration,
                              action_label, action_cb)

    # -- public API ---------------------------------------------------------
    def show_info(self, title, detail="", duration=4000, *,
                  action_label=None, action_cb=None):
        return self._spawn("info", title, detail, duration,
                           action_label=action_label, action_cb=action_cb)

    def show_ok(self, title, detail="", duration=4000, *,
                action_label=None, action_cb=None):
        return self._spawn("ok", title, detail, duration,
                           action_label=action_label, action_cb=action_cb)

    def show_warn(self, title, detail="", duration=6000, *,
                  action_label=None, action_cb=None):
        return self._spawn("warn", title, detail, duration,
                           action_label=action_label, action_cb=action_cb)

    def show_error(self, title, detail="", duration=7000, *,
                   action_label=None, action_cb=None):
        return self._spawn("err", title, detail, duration,
                           action_label=action_label, action_cb=action_cb)

    def show_progress(self, title, detail=""):
        """Returns a progress toast; update via set_progress/set_title/set_detail.

        A live flash must stay visible, so when the stack is full the oldest
        toast is retired to make room (the strict 3-slot visible cap is still
        honoured — progress never queues silently behind it).
        """
        self.dismiss_progress()
        while len(self._toasts) >= self._MAX_VISIBLE and self._toasts:
            self._retire(self._toasts[0])
        self._progress = self._spawn("progress", title, detail, 0)
        return self._progress

    def _retire(self, toast):
        """Drop a toast without promoting the queue (used to make room)."""
        if toast not in self._toasts:
            return
        self._toasts.remove(toast)
        try:
            toast.stop_timers()
        except Exception:
            pass
        toast.hide()
        toast.deleteLater()
        if self._progress is toast:
            self._progress = None

    def update_progress(self, value01, title=None, detail=None):
        if self._progress is not None:
            if title:
                self._progress.set_title(title)
            if detail:
                self._progress.set_detail(detail)
            self._progress.set_progress(value01)

    def dismiss(self, toast):
        if toast not in self._toasts:
            return
        self._toasts.remove(toast)
        try:
            toast.stop_timers()
        except Exception:
            pass
        toast.hide()
        toast.deleteLater()
        if self._progress is toast:
            self._progress = None
        # A queued toast takes the freed slot; the "+N more" chip follows.
        self._promote()
        self._update_overflow()
        self._relayout()

    def dismiss_progress(self):
        if self._progress is not None:
            self.dismiss(self._progress)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()
