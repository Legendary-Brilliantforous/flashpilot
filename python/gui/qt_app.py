import threading
import time as _time
import math
import os

from PyQt6.QtCore import (
    QRectF,
    QRect,
    QSize,
    Qt,
    QObject,
    QTimer,
    pyqtSignal,
    QPoint,
    QPointF,
    QEvent,
    QSettings,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QLinearGradient,
    QRadialGradient,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QFontMetrics,
    QFontMetricsF,
    QKeySequence,
    QAction,
    QShortcut,
    QPalette,
)
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QGridLayout,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QLayout,
)

from ..core import bridge, frp, mtk, mtp, fus
from .toast import ToastHost
from .nav import NavRail

# ---------------------------------------------------------------------------
# Flow run-guard: only ONE device operation may run at a time. Without this a
# user can click "Flash" while a flash is in progress - launching a second
# write to the same device - and the second clear_cancel() silently discards
# the in-flight operation's cancel request. The lock is acquired on the GUI
# thread when an operation starts and released from the worker's finally.
# ---------------------------------------------------------------------------
_FLOW_LOCK = threading.Lock()
_FLOW_LABEL = [None]
_FLOW_IS_DESTRUCTIVE = [False]


def _flow_start(label, destructive):
    """Try to begin a device operation. Returns False (and the caller should
    abort) if another operation is already running. Records whether this
    operation can brick/wipe a device so Stop reflects the true severity."""
    if not _FLOW_LOCK.acquire(blocking=False):
        return False
    _FLOW_LABEL[0] = label
    _FLOW_IS_DESTRUCTIVE[0] = bool(destructive)
    return True


def _flow_end():
    _FLOW_LABEL[0] = None
    _FLOW_IS_DESTRUCTIVE[0] = False
    _FLOW_LOCK.release()


def _flow_busy_msg():
    other = _FLOW_LABEL[0]
    if other:
        return f"'{other}' is still running. Wait for it to finish before starting another operation."
    return "Another operation is still running. Wait for it to finish."


# Flows that wipe device data / clear security state. These must always ask
# for confirmation, even when launched from the generic job-flow buttons.
_DESTRUCTIVE_CONFIRM = {
    "factory_reset": (
        "Factory Reset",
        "This WIPES ALL DATA on the connected device:\n\n"
        "  - Apps, accounts, photos, messages, files\n"
        "  - Phone / modem settings are kept\n\n"
        "It tries an ADB /data wipe first, and falls back to a guided "
        "recovery-mode reset if the device is not authorized.\n\n"
        "There is NO undo. Continue?",
    ),
    "mdm_unlock": (
        "MDM Unlock",
        "Removes the mobile-device-management (MDM / device-owner) app and "
        "clears its control over the phone.\n\n"
        "On some builds this also WIPES USER DATA (--wipe_data) so the "
        "device can be set up fresh.\n\n"
        "There is NO undo for the wiped data. Continue?",
    ),
    "mdm_unlock_comprehensive": (
        "MDM Unlock (Comprehensive)",
        "Removes the MDM / device-owner app AND clears related account and "
        "system state across all users.\n\n"
        "This is the deepest MDM removal and may also wipe user data. "
        "Continue?",
    ),
    "mdm_unlock_recovery_wipe": (
        "MDM Unlock (with data wipe)",
        "Removes the MDM / device-owner app and WIPES USER DATA via "
        "recovery so the device can be set up as new.\n\n"
        "There is NO undo for the wiped data. Continue?",
    ),
    "screen_lock_locksettings": (
        "Screen Lock Remove",
        "Removes the screen lock (PIN / password / pattern / face) via the "
        "locksettings command.\n\n"
        "This may log out signed-in accounts and reset security settings. "
        "Continue?",
    ),
    "screen_lock_csc": (
        "Screen Lock Remove (CSC flash)",
        "Removes the screen lock by flashing a combination/CSC build, which "
        "FACTORY RESETS the device and wipes all user data.\n\n"
        "There is NO undo. Continue?",
    ),
    "screen_lock_recovery": (
        "Screen Lock Remove (Recovery)",
        "Removes the screen lock and FRP records from recovery, which "
        "resets security state and may log out accounts.\n\n"
        "Continue?",
    ),
    "screen_lock_comprehensive": (
        "Screen Lock Remove (Comprehensive)",
        "Removes the screen lock / FRP / account lock records by the most "
        "thorough method available on the device.\n\n"
        "This may wipe data and log out accounts. Continue?",
    ),
    "screen_lock_download": (
        "Screen Lock Remove (Combo flash)",
        "Flashes a combination firmware in Download mode to remove the "
        "screen lock - this REPLACES the firmware and wipes the device.\n\n"
        "There is NO undo. Continue?",
    ),
    "adb_frp": (
        "FRP Bypass (ADB)",
        "Clears the Factory Reset Protection flag so the device can be set "
        "up with a new account.\n\n"
        "Continue?",
    ),
    "frp_browser": (
        "FRP Bypass (Browser)",
        "Clears the Factory Reset Protection flag via the browser workaround.\n\n"
        "Continue?",
    ),
    "frp_settings": (
        "FRP Bypass (Settings)",
        "Clears the Factory Reset Protection flag via the settings workaround.\n\n"
        "Continue?",
    ),
}

# ---------------------------------------------------------------------------
# Design tokens - single source for the premium dark theme.
# ---------------------------------------------------------------------------
C = {
    "bg": "#04070c",            # window background (deep carbon)
    "panel": "#0a111a",         # card panel
    "card": "#0d1622",          # inner card
    "card_hover": "#152032",    # card hover state
    "inset": "#070d15",         # console / inputs
    "border": "#16233a",
    "border_hi": "#2c405e",
    "text": "#e7eef8",
    "dim": "#8fa4bd",
    "mute": "#52657d",
    "accent": "#22d3ee",        # circuit-cyan signature
    "accent_hi": "#7dd3fc",
    "grad_a": "#0ea5e9",
    "grad_b": "#22d3ee",
    "ok": "#2dd4bf",
    "ok_dim": "#0c332f",
    "warn": "#fbbf24",
    "warn_dim": "#3a3010",
    "err": "#fb7185",
    "err_dim": "#3d1721",
    "chip_blue": "#0f2a41",
    "chip_text": "#7dd3fc",
    "accent_dim": "#0e3350",     # soft accent fill (dropdown selection, tiles)
    "sheen": "#ffffff",          # highlight on painted glyphs
}

# Accent themes selectable in Settings -> Appearance. Each swaps the accent /
# gradient tokens, mirroring how premium commercial tools ship colour packs.
ACCENT_THEMES = {
    "Neon Circuit": {
        "accent": "#22d3ee", "accent_hi": "#7dd3fc",
        "grad_a": "#0ea5e9", "grad_b": "#22d3ee", "accent_dim": "#0e3350",
    },
    "Cobalt Blue": {
        "accent": "#3b82f6", "accent_hi": "#6ea8ff",
        "grad_a": "#2563eb", "grad_b": "#06b6d4", "accent_dim": "#1d3a66",
    },
    "Violet": {
        "accent": "#8b5cf6", "accent_hi": "#a78bfa",
        "grad_a": "#7c3aed", "grad_b": "#06b6d4", "accent_dim": "#2b2350",
    },
    "Emerald": {
        "accent": "#10b981", "accent_hi": "#34d399",
        "grad_a": "#059669", "grad_b": "#2dd4bf", "accent_dim": "#0f3d31",
    },
    "Amber": {
        "accent": "#f59e0b", "accent_hi": "#fbbf24",
        "grad_a": "#d97706", "grad_b": "#f59e0b", "accent_dim": "#3d3413",
    },
    "Crimson": {
        "accent": "#ef4444", "accent_hi": "#f87171",
        "grad_a": "#dc2626", "grad_b": "#f97316", "accent_dim": "#3d1b1e",
    },
}

_BASE_QSS = f"""
* {{
    font-family: "Inter", "Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}
QToolTip {{
    background-color: {C['card']}; color: {C['text']};
    border: 1px solid {C['border_hi']}; border-radius: 6px; padding: 6px 8px;
}}
QLineEdit {{
    background: {C['inset']};
    border: 1px solid {C['border']};
    border-radius: 7px;
    padding: 6px 10px;
    color: {C['text']};
    selection-background-color: {C['accent']};
    selection-color: #ffffff;
}}
QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }}
QLineEdit:focus {{ border: 1px solid {C['accent']}; }}
QComboBox {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 {C['card_hover']}, stop:1 {C['card']});
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: 8px 34px 8px 12px;
    color: {C['text']};
    min-height: 20px;
    selection-background-color: {C['accent']};
    selection-color: #ffffff;
}}
QComboBox:hover {{ border: 1px solid {C['border_hi']}; background: {C['card_hover']}; }}
QComboBox:focus {{ border: 1px solid {C['accent']}; }}
QComboBox:disabled {{ color: {C['mute']}; }}
QComboBox:on {{ border: 1px solid {C['accent']}; }}
QComboBox::drop-down {{
    border: none; width: 30px;
    subcontrol-origin: padding; subcontrol-position: center right;
    background: transparent;
}}
QComboBox::down-arrow {{
    image: none; width: 0; height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {C['dim']};
}}
QComboBox::down-arrow:on {{ border-top: 6px solid {C['accent']}; }}
QComboBox QAbstractItemView {{
    background-color: {C['panel']};
    border: 1px solid {C['border_hi']};
    border-radius: 10px;
    color: {C['text']};
    selection-background-color: transparent;
    outline: 0;
    padding: 4px;
}}
QScrollBar:vertical {{
    background: transparent; width: 10px; border-radius: 5px; margin: 2px;
}}
QScrollBar::handle:vertical {{ background: {C['border_hi']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {C['accent']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ height: 0; }}
"""


def _btn_primary():
    return f"""
    QPushButton {{
        border: 1px solid {C['accent']};
        border-radius: 6px;
        padding: 7px 16px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.5px;
        color: #04121a;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                    stop:0 {C['grad_a']}, stop:1 {C['grad_b']});
    }}
    QPushButton:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                    stop:0 {C['accent']}, stop:1 #67e8f9);
                         border: 1px solid {C['accent_hi']}; }}
    QPushButton:pressed {{ background: {C['grad_a']};
                          border: 1px solid {C['accent_hi']}; }}
    QPushButton:disabled {{ background: {C['border']}; color: {C['mute']};
                           border: 1px solid {C['border']}; }}
    """


def _card_qss():
    """Circuit-deck card surface: dark carbon slab with a hairline top
    highlight and a thin accent edge on the left, like a backlit instrument
    panel rather than a soft rounded glass card."""
    return (
        f"QFrame#card {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        f" stop:0 rgba(15, 24, 38, 244), stop:1 rgba(7, 12, 19, 244));"
        f" border: 1px solid {C['border']}; border-left: 2px solid {C['accent']};"
        f" border-top: 1px solid {C['border_hi']};"
        f" border-radius: 10px; }}"
    )


def _btn_ghost():
    return f"""
    QPushButton {{
        border: 1px solid {C['border']};
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 600;
        color: {C['text']};
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 {C['card']}, stop:1 {C['inset']});
    }}
    QPushButton:hover {{ border: 1px solid {C['accent']}; color: {C['accent_hi']};
                        background: {C['card_hover']}; }}
    QPushButton:pressed {{ background: {C['accent_dim']}; color: #fff; }}
    QPushButton:disabled {{ color: {C['mute']}; border: 1px solid {C['border']}; background: {C['card']}; }}
    """


def _risk_banner(text):
    """A compact red-striped warning bar used near destructive operations
    (flash / wipe). Keeps beginners aware of the consequence before they click."""
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    icon = QLabel("⚠")
    icon.setStyleSheet(f"color: {C['err']}; font-size: 14px; font-weight: 800;")
    icon.setFixedWidth(18)
    lay.addWidget(icon)
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: #ffb4b4; font-size: 11px; font-weight: 600;"
        f" background: rgba(220, 38, 38, 22);"
        f" border: 1px solid rgba(239, 68, 68, 140);"
        f" border-left: 3px solid {C['err']}; border-radius: 6px;"
        f" padding: 6px 10px;"
    )
    lay.addWidget(lbl, 1)
    return w


def _btn_danger():
    return f"""
    QPushButton {{
        border: 1px solid {C['err']};
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 700;
        color: #ffa3b2;
        background: {C['card']};
    }}
    QPushButton:hover {{ background: {C['err']}; color: #ffffff; }}
    QPushButton:pressed {{ background: #b91c1c; border-color: #b91c1c; }}
    QPushButton:disabled {{ color: {C['mute']}; border: 1px solid {C['border']}; }}
    """


def _console_qss():
    return f"""
    QPlainTextEdit {{
        background-color: {C['inset']};
        border: 1px solid {C['border']};
        border-radius: 8px;
        color: {C['text']};
        font-family: "JetBrains Mono", "Consolas", "Menlo", monospace;
        font-size: 12px;
        padding: 12px;
        selection-background-color: {C['accent']};
    }}
    """


class LogBridge(QObject):
    line = pyqtSignal(str)
    status = pyqtSignal(str)
    metric = pyqtSignal(str, str)
    qr = pyqtSignal(object)
    finished = pyqtSignal()
    toast = pyqtSignal(str, str, str)
    ui = pyqtSignal(object)


class DeviceMonitor(QObject):
    """Polls USB/ADB state in a background thread and emits results."""

    state = pyqtSignal(dict)

    def __init__(self, interval=3.0):
        super().__init__()
        self.interval = interval
        self._stop = threading.Event()
        self._thread = None
        self._last_state = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def set_interval(self, seconds):
        """Update the scan interval without restarting the poll thread."""
        self.interval = max(1.0, float(seconds))

    def stop(self):
        self._stop.set()

    def _poll(self):
        while not self._stop.is_set():
            try:
                usb = bridge.detect_all()
                hid = bridge.list_samsung_hid()
                adb_devs = bridge.adb_status()
            except bridge.BridgeError as e:
                self.state.emit({"error": str(e)})
            else:
                samsung = [d for d in usb if d.get("is_samsung")]
                mtk_devs = [d for d in usb if d.get("vid") == mtk.MTK_VID]
                fastboot = [d for d in usb if _is_fastboot(d)]
                edl_devs = [d for d in usb if _is_edl(d)]
                qcom_devs = [d for d in usb if d.get("vid") == 0x05C6]
                spd_devs = [d for d in usb if d.get("vid") == 0x1782]
                mode = _detect_mode(samsung, mtk_devs, adb_devs, fastboot, edl_devs,
                                    qcom_devs, spd_devs)
                current_state = {
                    "samsung": samsung,
                    "mtk": mtk_devs,
                    "hid": hid,
                    "adb": adb_devs,
                    "fastboot": fastboot,
                    "edl": edl_devs,
                    "qcom": qcom_devs,
                    "spd": spd_devs,
                    "mode": mode,
                }
                if current_state != self._last_state:
                    self.state.emit(current_state)
                    self._last_state = current_state
            self._stop.wait(self.interval)


# ---------------------------------------------------------------------------
# Painted glyphs
# ---------------------------------------------------------------------------
def _draw_computer(size, connected=False):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)

    # ground shadow
    p.setBrush(QColor(0, 0, 0, 70))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(s * 0.28, s * 0.945, s * 0.44, s * 0.05))

    # stand base
    base = QRectF(s * 0.27, s * 0.86, s * 0.46, s * 0.09)
    bgrad = QLinearGradient(0, base.top(), 0, base.bottom())
    bgrad.setColorAt(0, QColor(C["border_hi"]))
    bgrad.setColorAt(1, QColor(C["inset"]))
    p.setBrush(bgrad)
    p.setPen(QPen(QColor(C["border_hi"]), 1))
    p.drawRoundedRect(base, s * 0.05, s * 0.05)
    p.setPen(QPen(QColor(255, 255, 255, 42), 1))
    p.drawLine(QPointF(base.x() + s * 0.05, base.y() + 1.6),
               QPointF(base.x() + base.width() - s * 0.05, base.y() + 1.6))
    # neck
    ngrad = QLinearGradient(0, s * 0.70, 0, s * 0.90)
    ngrad.setColorAt(0, QColor(C["border_hi"]))
    ngrad.setColorAt(1, QColor(C["inset"]))
    p.setBrush(ngrad)
    p.setPen(QPen(QColor(C["border_hi"]), 1))
    p.drawRoundedRect(QRectF(s * 0.455, s * 0.72, s * 0.09, s * 0.16), s * 0.03, s * 0.03)

    # monitor bezel (dark metallic frame)
    bezel = QRectF(s * 0.06, s * 0.03, s * 0.88, s * 0.70)
    fr = QLinearGradient(bezel.left(), bezel.top(), bezel.right(), bezel.bottom())
    fr.setColorAt(0, QColor("#3a4450"))
    fr.setColorAt(0.5, QColor("#232b35"))
    fr.setColorAt(1, QColor("#10151d"))
    p.setBrush(fr)
    p.setPen(QPen(QColor("#4a5563"), 1.2))
    p.drawRoundedRect(bezel, s * 0.09, s * 0.09)
    p.setPen(QPen(QColor(255, 255, 255, 26), 1))
    p.drawLine(QPointF(bezel.x() + s * 0.02, bezel.y() + s * 0.02),
               QPointF(bezel.x() + bezel.width() - s * 0.02, bezel.y() + s * 0.02))

    # screen
    screen = QRectF(bezel.x() + s * 0.055, bezel.y() + s * 0.06,
                    bezel.width() - s * 0.11, bezel.height() - s * 0.12)
    if connected:
        sc = QLinearGradient(screen.left(), screen.top(), screen.right(), screen.bottom())
        sc.setColorAt(0, QColor(C["accent_hi"]))
        sc.setColorAt(0.55, QColor(C["grad_b"]))
        sc.setColorAt(1, QColor(C["grad_a"]))
    else:
        sc = QLinearGradient(screen.left(), screen.top(), screen.left(), screen.bottom())
        sc.setColorAt(0, QColor("#25314a"))
        sc.setColorAt(1, QColor(C["inset"]))
    p.setBrush(sc)
    p.setPen(QPen(QColor(0, 0, 0, 120), 1))
    p.drawRoundedRect(screen, s * 0.04, s * 0.04)

    if connected:
        # desktop: sun glow
        orb = QRadialGradient(screen.x() + screen.width() * 0.72,
                              screen.y() + screen.height() * 0.28, s * 0.22)
        orb.setColorAt(0, QColor(255, 255, 255, 90))
        orb.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(orb)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(screen.x() + screen.width() * 0.55,
                             screen.y() + screen.height() * 0.10,
                             s * 0.36, s * 0.36))
        # desktop window
        wx = screen.x() + screen.width() * 0.16
        wy = screen.y() + screen.height() * 0.15
        ww = screen.width() * 0.52
        wh = screen.height() * 0.5
        p.setBrush(QColor(13, 17, 26, 180))
        p.setPen(QPen(QColor(C["accent"]), 1))
        p.drawRoundedRect(QRectF(wx, wy, ww, wh), s * 0.02, s * 0.02)
        p.setPen(QPen(QColor(C["accent_hi"]), 1))
        p.drawLine(QPointF(wx + s * 0.02, wy + wh * 0.09),
                   QPointF(wx + ww - s * 0.02, wy + wh * 0.09))
        p.setBrush(QColor(C["accent_hi"]))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(wx + s * 0.02, wy + wh * 0.14, ww * 0.45, s * 0.02),
                          s * 0.008, s * 0.008)
        # second window hint
        p.setBrush(QColor(13, 17, 26, 140))
        p.setPen(QPen(QColor(C["border_hi"]), 1))
        p.drawRoundedRect(QRectF(wx + ww * 0.30, wy + wh * 0.58, ww * 0.62, wh * 0.32),
                          s * 0.02, s * 0.02)
    else:
        # dark screen with faint reflection
        sh = QLinearGradient(screen.left(), screen.top(), screen.right(), screen.bottom())
        sh.setColorAt(0, QColor(255, 255, 255, 30))
        sh.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(sh)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(screen.adjusted(s * 0.02, s * 0.02, -s * 0.02, -s * 0.3),
                          s * 0.03, s * 0.03)

    # glass diagonal reflection
    p.setPen(QPen(QColor(255, 255, 255, 26), 1))
    p.drawLine(QPointF(screen.x(), screen.y() + screen.height() * 0.6),
               QPointF(screen.x() + screen.width() * 0.5, screen.y()))

    # webcam dot
    p.setBrush(QColor(C["border_hi"]))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(bezel.x() + bezel.width() / 2 - s * 0.014,
                         bezel.y() + s * 0.006, s * 0.028, s * 0.028))
    p.setBrush(QColor(10, 14, 20))
    p.drawEllipse(QRectF(bezel.x() + bezel.width() / 2 - s * 0.008,
                         bezel.y() + s * 0.012, s * 0.016, s * 0.016))

    # status LED (bottom-right of bezel)
    led = QColor(C["ok"]) if connected else QColor(C["mute"])
    p.setBrush(led)
    p.drawEllipse(QRectF(bezel.x() + bezel.width() - s * 0.06,
                         bezel.y() + bezel.height() - s * 0.045,
                         s * 0.026, s * 0.026))
    p.end()
    return pix


def _draw_phone(size, connected):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)

    # ground shadow
    p.setBrush(QColor(0, 0, 0, 70))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(s * 0.36, s * 0.945, s * 0.28, s * 0.045))

    # ambient glow when connected
    if connected:
        glow = QRadialGradient(s * 0.5, s * 0.45, s * 0.58)
        glow.setColorAt(0, QColor(34, 197, 94, 80))
        glow.setColorAt(1, QColor(34, 197, 94, 0))
        p.setBrush(glow)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(0, 0, s, s))

    # body with metallic frame
    body = QRectF(s * 0.30, s * 0.02, s * 0.40, s * 0.94)
    frame = body.adjusted(-s * 0.006, -s * 0.006, s * 0.006, s * 0.006)
    fr = QLinearGradient(frame.left(), frame.top(), frame.right(), frame.bottom())
    fr.setColorAt(0, QColor("#b9c2cc"))
    fr.setColorAt(0.5, QColor("#7c8a99"))
    fr.setColorAt(1, QColor("#3d4754"))
    p.setBrush(fr)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(frame, s * 0.10, s * 0.10)

    if connected:
        bg = QLinearGradient(0, 0, 0, s)
        bg.setColorAt(0, QColor("#263544"))
        bg.setColorAt(1, QColor("#141b26"))
    else:
        bg = QLinearGradient(0, 0, 0, s)
        bg.setColorAt(0, QColor(C["card_hover"]))
        bg.setColorAt(1, QColor(C["inset"]))
    p.setBrush(bg)
    p.setPen(QPen(QColor("#0a0f15"), 1))
    p.drawRoundedRect(body, s * 0.09, s * 0.09)
    # left edge light reflection
    p.setPen(QPen(QColor(255, 255, 255, 26), 1))
    p.drawLine(QPointF(body.x() + s * 0.012, body.y() + s * 0.06),
               QPointF(body.x() + s * 0.012, body.y() + body.height() - s * 0.06))

    # side buttons
    p.setBrush(QColor("#9aa7b5"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(frame.x() - s * 0.014, s * 0.22, s * 0.018, s * 0.09), 1, 1)
    p.drawRoundedRect(QRectF(frame.x() - s * 0.014, s * 0.34, s * 0.018, s * 0.06), 1, 1)
    p.drawRoundedRect(QRectF(frame.x() + frame.width(), s * 0.20, s * 0.018, s * 0.12), 1, 1)

    # screen
    screen = QRectF(body.x() + s * 0.022, body.y() + s * 0.05,
                    body.width() - s * 0.044, body.height() - s * 0.15)
    if connected:
        sg = QLinearGradient(screen.left(), screen.top(), screen.right(), screen.bottom())
        sg.setColorAt(0, QColor(C["grad_b"]))
        sg.setColorAt(1, QColor(C["grad_a"]))
    else:
        sg = QLinearGradient(screen.left(), screen.top(), screen.left(), screen.bottom())
        sg.setColorAt(0, QColor("#1d2939"))
        sg.setColorAt(1, QColor(C["inset"]))
    p.setBrush(sg)
    p.setPen(QPen(QColor(0, 0, 0, 110), 1))
    p.drawRoundedRect(screen, s * 0.035, s * 0.035)

    if connected:
        # wallpaper glow
        orb = QRadialGradient(screen.x() + screen.width() * 0.5,
                              screen.y() + screen.height() * 0.4, s * 0.28)
        orb.setColorAt(0, QColor(255, 255, 255, 70))
        orb.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(orb)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(screen.x() + screen.width() * 0.25,
                             screen.y() + screen.height() * 0.15,
                             screen.width() * 0.5, screen.width() * 0.5))
        # status bar
        p.setPen(QPen(QColor(255, 255, 255, 150), 1))
        p.drawLine(QPointF(screen.x() + s * 0.03, screen.y() + s * 0.035),
                   QPointF(screen.x() + screen.width() - s * 0.03,
                           screen.y() + s * 0.035))
        # clock
        p.setPen(QPen(QColor(255, 255, 255, 220), 1.4))
        fm = p.font()
        fm.setBold(True)
        p.setFont(fm)
        p.drawText(QRectF(screen.x(), screen.y() + s * 0.055, screen.width(), s * 0.06),
                   Qt.AlignmentFlag.AlignHCenter, "09:41")
        # app icon row
        p.setBrush(QColor(255, 255, 255, 190))
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(4):
            ix = screen.x() + screen.width() * (0.12 + i * 0.24)
            iy = screen.y() + screen.height() * 0.70
            p.drawRoundedRect(QRectF(ix, iy, s * 0.048, s * 0.048), s * 0.012, s * 0.012)
        # status text
        p.setPen(QPen(QColor(255, 255, 255, 120), 1))
        p.drawText(QRectF(screen.x() + s * 0.03, screen.y() + s * 0.14,
                          screen.width() - s * 0.06, s * 0.03),
                   Qt.AlignmentFlag.AlignHCenter, "CONNECTED")
    else:
        # lock screen: faint sheen + label
        sh = QLinearGradient(screen.left(), screen.top(), screen.left(), screen.bottom())
        sh.setColorAt(0, QColor(255, 255, 255, 34))
        sh.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(sh)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(screen.adjusted(s * 0.02, s * 0.02, -s * 0.02, -s * 0.35),
                          s * 0.03, s * 0.03)
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.drawText(QRectF(screen.x(), screen.y() + s * 0.16, screen.width(), s * 0.03),
                   Qt.AlignmentFlag.AlignHCenter, "OFFLINE")

    # glass diagonal reflection
    p.setPen(QPen(QColor(255, 255, 255, 26), 1))
    p.drawLine(QPointF(screen.x(), screen.y() + screen.height() * 0.5),
               QPointF(screen.x() + screen.width() * 0.55, screen.y()))

    # camera punch-hole with lens ring
    ring = QColor(C["ok"]) if connected else QColor(C["border_hi"])
    p.setPen(QPen(ring, 1))
    p.setBrush(QColor(8, 12, 18))
    p.drawEllipse(QRectF(s * 0.463, s * 0.062, s * 0.074, s * 0.074))
    p.setBrush(QColor(20, 28, 40))
    p.drawEllipse(QRectF(s * 0.473, s * 0.072, s * 0.054, s * 0.054))
    p.setBrush(QColor(4, 6, 10))
    p.drawEllipse(QRectF(s * 0.483, s * 0.082, s * 0.034, s * 0.034))
    if connected:
        p.setPen(QPen(QColor(C["ok"]), 0.8))
        p.drawArc(QRectF(s * 0.478, s * 0.077, s * 0.044, s * 0.044), 30 * 16, 200 * 16)

    # home indicator bar
    p.setBrush(QColor(255, 255, 255, 110))
    p.drawRoundedRect(
        QRectF(s * 0.42, screen.y() + screen.height() + s * 0.02,
               s * 0.16, s * 0.012), 1, 1
    )

    # USB-C port on the bottom edge (where the cable plugs in)
    port_w = s * 0.13
    port_h = s * 0.052
    port_x = body.x() + (body.width() - port_w) / 2
    port_y = body.y() + body.height() - port_h
    if connected:
        glow = QRadialGradient(port_x + port_w / 2, port_y + port_h / 2, s * 0.10)
        glow.setColorAt(0, QColor(34, 197, 94, 150))
        glow.setColorAt(1, QColor(34, 197, 94, 0))
        p.setBrush(glow)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(port_x - s * 0.03, port_y - s * 0.01,
                             port_w + s * 0.06, s * 0.10))
        p.setBrush(QColor(10, 14, 20))
        p.setPen(QPen(QColor("#9aa7b5"), 1))
        p.drawRoundedRect(QRectF(port_x, port_y, port_w, port_h), 2, 2)
        p.setBrush(QColor(C["ok"]))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(
            QRectF(port_x + port_w * 0.24, port_y + port_h * 0.3,
                   port_w * 0.52, port_h * 0.4), 1, 1
        )
    else:
        p.setBrush(QColor(8, 11, 16))
        p.setPen(QPen(QColor("#7c8a99"), 1))
        p.drawRoundedRect(QRectF(port_x, port_y, port_w, port_h), 2, 2)
        p.setBrush(QColor(20, 26, 36))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(
            QRectF(port_x + port_w * 0.24, port_y + port_h * 0.3,
                   port_w * 0.52, port_h * 0.4), 1, 1
        )
    p.end()
    return pix


def _draw_logo(size):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)

    # outer hexagonal chip die
    hexpts = []
    for i in range(6):
        ang = math.pi / 180.0 * (60 * i - 30)
        hexpts.append(QPointF(s * 0.5 + s * 0.44 * math.cos(ang),
                              s * 0.5 + s * 0.44 * math.sin(ang)))
    hx = QPolygonF(hexpts)
    g = QLinearGradient(0, 0, s, s)
    g.setColorAt(0, QColor(C["grad_a"]))
    g.setColorAt(1, QColor(C["grad_b"]))
    p.setPen(QPen(QColor(C["accent_hi"]), s * 0.02))
    p.setBrush(g)
    p.drawPolygon(hx)

    # inner core (dark inset with a bright node)
    inner = []
    for i in range(6):
        ang = math.pi / 180.0 * (60 * i - 30)
        inner.append(QPointF(s * 0.5 + s * 0.26 * math.cos(ang),
                             s * 0.5 + s * 0.26 * math.sin(ang)))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#051019"))
    p.drawPolygon(QPolygonF(inner))

    # circuit traces fanning from the core to the die edge
    p.setPen(QPen(QColor(C["accent_hi"]), s * 0.025, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    for i in range(6):
        ang = math.pi / 180.0 * (60 * i - 30)
        x0 = s * 0.5 + s * 0.26 * math.cos(ang)
        y0 = s * 0.5 + s * 0.26 * math.sin(ang)
        x1 = s * 0.5 + s * 0.42 * math.cos(ang)
        y1 = s * 0.5 + s * 0.42 * math.sin(ang)
        p.drawLine(QPointF(x0, y0), QPointF(x1, y1))

    # centre node
    core = QRadialGradient(s * 0.5, s * 0.5, s * 0.16)
    core.setColorAt(0, QColor("#e0f7ff"))
    core.setColorAt(1, QColor(C["accent"]))
    p.setBrush(core)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(s * 0.34, s * 0.34, s * 0.32, s * 0.32))
    p.end()
    return pix


# ---------------------------------------------------------------------------
# Device state helpers
# ---------------------------------------------------------------------------
_SAMSUNG_PIDS = {
    0x685D: "DOWNLOAD MODE (or MediaTek A05/A06) - pid 0x685d",
    0x6860: "NORMAL BOOT / SETUP WIZARD (MTP)",
    0x685E: "ADB ENABLED (debug composite)",
    0x6866: "TETHERING (RNDIS)",
    0x68A2: "NORMAL BOOT (MTP)",
    0x68A3: "ADB ENABLED (debug composite)",
    0x68C0: "NORMAL BOOT (MTP)",
    # Additional Samsung flashing modes
    0x685C: "BROM MODE (BootROM)",
    0x6863: "DIAG/MODEM MODE (AT port)",
    0x6865: "CDC SERIAL (DIAG)",
    0x6867: "NETWORK ADAPTER (RNDIS)",
    0x6868: "MTP + ADB COMPOSITE",
    0x6869: "PTP MODE (Picture Transfer)",
    0x686A: "MIDI MODE",
    0x686B: "AUDIO MODE",
    0x686C: "VIDEO MODE",
    0x686D: "PRINTER MODE",
    0x686E: "STORAGE MODE (Mass Storage)",
    0x686F: "CDC DATA MODE",
    0x6870: "CDC ACM MODE",
    0x6871: "CDC WMC MODE",
    0x6872: "CDC WDM MODE",
    0x6873: "CDC OBEX MODE",
    0x6874: "CDC NCM MODE",
    0x6875: "CDC EEM MODE",
    0x6876: "CDC NCM MODE",
    0x6877: "CDC MBIM MODE",
    0x6878: "CDC QMI WWAN MODE",
    0x6879: "CDC QMI ETHERNET MODE",
    0x687A: "CDC GOBI MODE",
    0x687B: "CDC ACCELEROMETER MODE",
    0x687C: "CDC BATTERY MODE",
    0x687D: "CDC HID MODE",
    0x687E: "CDC TEST MODE",
    0x687F: "CDC VENDOR MODE",
    0x6601: "DOWNLOAD MODE (legacy)",
    0x68C3: "DOWNLOAD MODE (variant)",
    0x68EF: "DOWNLOAD MODE (variant)",
    0x4EEE: "DOWNLOAD MODE (variant)",
    0x4EEF: "DOWNLOAD MODE (variant)",
    0x687D: "HID MODE (Download mode)",
    0x687E: "HID + CDC MODE",
    0x687F: "HID + MTP MODE",
    0x6880: "RECOVERY MODE",
    0x6881: "FASTBOOT MODE (Qualcomm)",
    0x6882: "BOOTLOADER MODE",
    0x6883: "MODEM MODE",
    0x6884: "RNDIS + DIAG MODE",
    0x6885: "RNDIS + ADB MODE",
    0x6886: "MTP + DIAG MODE",
    0x6887: "PTP + DIAG MODE",
    0x6888: "CDC + DIAG MODE",
    0x6889: "HID + DIAG MODE",
    0x688A: "MTP + ADB + DIAG MODE",
    0x688B: "PTP + ADB + DIAG MODE",
    0x688C: "CDC + ADB + DIAG MODE",
    0x688D: "HID + ADB + DIAG MODE",
    0x688E: "MTP + ADB + HID MODE",
    0x688F: "PTP + ADB + HID MODE",
    0x6890: "CDC + ADB + HID MODE",
    0x6891: "DIAG + ADB + HID MODE",
    0x6892: "MTP + PTP MODE",
    0x6893: "MTP + CDC MODE",
    0x6894: "MTP + HID MODE",
    0x6895: "PTP + CDC MODE",
    0x6896: "PTP + HID MODE",
    0x6897: "CDC + HID MODE",
    0x6898: "MTP + PTP + CDC MODE",
    0x6899: "MTP + PTP + HID MODE",
    0x689A: "MTP + CDC + HID MODE",
    0x689B: "PTP + CDC + HID MODE",
    0x689C: "MTP + PTP + CDC + HID MODE",
    0x689D: "MTP + ADB + PTP MODE",
    0x689E: "MTP + ADB + CDC MODE",
    0x689F: "MTP + ADB + HID MODE",
    0x68A0: "PTP + ADB + CDC MODE",
    0x68A1: "PTP + ADB + HID MODE",
    0x68A4: "CDC + ADB MODE",
    0x68A5: "HID + ADB MODE",
    0x68A6: "MTP + PTP + ADB MODE",
    0x68A7: "MTP + CDC + ADB MODE",
    0x68A8: "MTP + HID + ADB MODE",
    0x68A9: "PTP + CDC + ADB MODE",
    0x68AA: "PTP + HID + ADB MODE",
    0x68AB: "CDC + HID + ADB MODE",
    0x68AC: "MTP + PTP + CDC + ADB MODE",
    0x68AD: "MTP + PTP + HID + ADB MODE",
    0x68AE: "MTP + CDC + HID + ADB MODE",
    0x68AF: "PTP + CDC + HID + ADB MODE",
    0x68B0: "MTP + PTP + CDC + HID + ADB MODE",
    0x68B1: "DIAG + ADB MODE",
    0x68B2: "DIAG + MTP MODE",
    0x68B3: "DIAG + PTP MODE",
    0x68B4: "DIAG + CDC MODE",
    0x68B5: "DIAG + HID MODE",
    0x68B6: "DIAG + MTP + ADB MODE",
    0x68B7: "DIAG + PTP + ADB MODE",
    0x68B8: "DIAG + CDC + ADB MODE",
    0x68B9: "DIAG + HID + ADB MODE",
    0x68BA: "DIAG + MTP + PTP MODE",
    0x68BB: "DIAG + MTP + CDC MODE",
    0x68BC: "DIAG + MTP + HID MODE",
    0x68BD: "DIAG + PTP + CDC MODE",
    0x68BE: "DIAG + PTP + HID MODE",
    0x68BF: "DIAG + CDC + HID MODE",
    0x68C1: "MTP + DIAG + ADB MODE",
    0x68C2: "PTP + DIAG + ADB MODE",
    0x68C4: "CDC + DIAG + ADB MODE",
    0x68C5: "HID + DIAG + ADB MODE",
    0x68C6: "MTP + DIAG + PTP MODE",
    0x68C7: "MTP + DIAG + CDC MODE",
    0x68C8: "MTP + DIAG + HID MODE",
    0x68C9: "PTP + DIAG + CDC MODE",
    0x68CA: "PTP + DIAG + HID MODE",
    0x68CB: "CDC + DIAG + HID MODE",
    0x68CC: "MTP + DIAG + PTP + ADB MODE",
    0x68CD: "MTP + DIAG + CDC + ADB MODE",
    0x68CE: "MTP + DIAG + HID + ADB MODE",
    0x68CF: "PTP + DIAG + CDC + ADB MODE",
    0x68D0: "PTP + DIAG + HID + ADB MODE",
    0x68D1: "CDC + DIAG + HID + ADB MODE",
    0x68D2: "MTP + DIAG + PTP + CDC MODE",
    0x68D3: "MTP + DIAG + PTP + HID MODE",
    0x68D4: "MTP + DIAG + CDC + HID MODE",
    0x68D5: "PTP + DIAG + CDC + HID MODE",
    0x68D6: "MTP + DIAG + PTP + CDC + ADB MODE",
    0x68D7: "MTP + DIAG + PTP + HID + ADB MODE",
    0x68D8: "MTP + DIAG + CDC + HID + ADB MODE",
    0x68D9: "PTP + DIAG + CDC + HID + ADB MODE",
    0x68DA: "MTP + DIAG + PTP + CDC + HID + ADB MODE",
    0x68DB: "TETHERING + DIAG MODE",
    0x68DC: "TETHERING + ADB MODE",
    0x68DD: "TETHERING + MTP MODE",
    0x68DE: "TETHERING + PTP MODE",
    0x68DF: "TETHERING + CDC MODE",
    0x68E0: "TETHERING + HID MODE",
    0x68E1: "TETHERING + DIAG + ADB MODE",
    0x68E2: "TETHERING + MTP + ADB MODE",
    0x68E3: "TETHERING + PTP + ADB MODE",
    0x68E4: "TETHERING + CDC + ADB MODE",
    0x68E5: "TETHERING + HID + ADB MODE",
    0x68E6: "TETHERING + DIAG + MTP MODE",
    0x68E7: "TETHERING + DIAG + PTP MODE",
    0x68E8: "TETHERING + DIAG + CDC MODE",
    0x68E9: "TETHERING + DIAG + HID MODE",
    0x68EA: "TETHERING + MTP + PTP MODE",
    0x68EB: "TETHERING + MTP + CDC MODE",
    0x68EC: "TETHERING + MTP + HID MODE",
    0x68ED: "TETHERING + PTP + CDC MODE",
    0x68EE: "TETHERING + PTP + HID MODE",
    0x68F0: "TETHERING + CDC + HID MODE",
    0x68F1: "TETHERING + DIAG + MTP + ADB MODE",
    0x68F2: "TETHERING + DIAG + PTP + ADB MODE",
    0x68F3: "TETHERING + DIAG + CDC + ADB MODE",
    0x68F4: "TETHERING + DIAG + HID + ADB MODE",
    0x68F5: "TETHERING + MTP + PTP + ADB MODE",
    0x68F6: "TETHERING + MTP + CDC + ADB MODE",
    0x68F7: "TETHERING + MTP + HID + ADB MODE",
    0x68F8: "TETHERING + PTP + CDC + ADB MODE",
    0x68F9: "TETHERING + PTP + HID + ADB MODE",
    0x68FA: "TETHERING + CDC + HID + ADB MODE",
    0x68FB: "TETHERING + DIAG + MTP + PTP MODE",
    0x68FC: "TETHERING + DIAG + MTP + CDC MODE",
    0x68FD: "TETHERING + DIAG + MTP + HID MODE",
    0x68FE: "TETHERING + DIAG + PTP + CDC MODE",
    0x68FF: "TETHERING + DIAG + PTP + HID MODE",
}


def _has_adb_iface(ifaces):
    return any(
        i["class"] == 255 and i["subclass"] == 66 and i["protocol"] == 1
        for i in ifaces
    )


def _is_fastboot(d):
    """Fastboot is exposed over USB as the Google fastboot gadget: VID 0x18d1
    PID 0x4ee0 (also 0xd00d on older devices), or any device whose interface
    reports class 255 / subclass 66 / protocol 3 (fastboot's ADB-offshoot
    protocol number). Samsung MediaTek A14s boot fastboot this way."""
    if d.get("vid") == 0x18D1 and d.get("pid") in (0x4EE0, 0xD00D):
        return True
    return any(
        i["class"] == 255 and i["subclass"] == 66 and i["protocol"] == 3
        for i in d.get("interfaces", [])
    )


def _is_edl(d):
    """Qualcomm Emergency Download: VID 0x05c6, PIDs 0x9008 (classic EDL) and
    0x900e (UFS/Emmc 9x45+ Sahara-capable)."""
    return d.get("vid") == 0x05C6 and d.get("pid") in (0x9008, 0x900E)


# Spreadtrum / UNISOC feature-phone download & engineering modes (VID 0x1782).
# 0x4d00 is the classic SC6531-family download (BROM/FDL) port.
_SPD_DOWNLOAD_PIDS = (0x4D00, 0x4D02, 0x4E00)


def _spd_mode(d):
    """Return a human label for a Spreadtrum device state, or None."""
    if d.get("vid") != 0x1782:
        return None
    pid = d.get("pid")
    if pid in _SPD_DOWNLOAD_PIDS:
        return "SPD DOWNLOAD MODE (Spreadtrum FDL / BROM)"
    return "SPREADTRUM DEVICE (normal / other)"


_IFACE_CLASS = {
    0: "vendor",
    1: "audio",
    2: "cdc",
    3: "hid",
    6: "image",
    7: "printer",
    8: "storage",
    9: "hub",
    10: "data",
    11: "smart card",
    12: "content security",
    13: "video",
    14: "personal health",
    224: "diagnostic",
    255: "vendor",
}


def _iface_class(i):
    if i["class"] == 255 and i["subclass"] == 66:
        proto = i.get("protocol", 0)
        tag = "fastboot" if proto == 3 else f"ADB/proto{proto}" if proto else "ADB"
        return f"vendor({tag})"
    name = _IFACE_CLASS.get(i["class"], f"cls{i['class']}")
    if i["class"] == 255:
        return f"{name}/sub{i['subclass']}"
    return name


def _fmt_usb_full(d):
    """Full human-readable USB descriptor dump for a device dict."""
    lines = []
    vid, pid = d.get("vid", 0), d.get("pid", 0)
    bus, addr = d.get("bus", "?"), d.get("address", "?")
    lines.append(
        f"USB: {vid:04X}:{pid:04X}  bus={bus} addr={addr}"
    )
    if d.get("manufacturer"):
        lines.append(f"  Manufacturer : {d['manufacturer']}")
    if d.get("product"):
        lines.append(f"  Product      : {d['product']}")
    if d.get("serial"):
        lines.append(f"  Serial       : {d['serial']}")
    for i in d.get("interfaces", []):
        eps = i.get("endpoints", [])
        ep_str = " ".join(
            f"0x{e['address']:02x}({e['direction']},{e['transfer_type']},{e['max_packet_size']})"
            for e in eps
        )
        lines.append(
            f"  Iface {i['number']}: {_iface_class(i)}  "
            f"class={i['class']} sub={i['subclass']} proto={i.get('protocol', 0)}"
            + (f"  eps=[{ep_str}]" if eps else "")
        )
    return lines


def _detect_mode(samsung, mtk_devs=None, adb_devs=None, fastboot=None, edl_devs=None,
                 qcom_devs=None, spd_devs=None):
    # Fastboot is its own transport - a Google-VID composite. Check it before
    # the Samsung-PID table so it isn't swallowed as 'OTHER MODE'.
    if fastboot:
        return "FASTBOOT MODE (bootloader unlocked / fastboot)"

    # Qualcomm EDL - a 05c6 VID composite, separate from the Samsung table.
    if edl_devs:
        return "EDL MODE (Qualcomm Emergency Download)"

    # Spreadtrum feature-phone download/engineering port (1782:4d00 FDL/BROM).
    for d in (spd_devs or []):
        mode = _spd_mode(d)
        if mode:
            return mode

    # A Qualcomm device that is NOT in EDL (e.g. a modem in normal mode).
    if qcom_devs:
        return "QUALCOMM DEVICE (modem / normal mode)"

    # The adb device STATE is the only reliable way to distinguish stock
    # recovery from normal boot: both enumerate the same MTP+ADB USB
    # composite, but adbd reports 'recovery'/'sideload' while in recovery.
    adb_states = {d["state"] for d in (adb_devs or [])}
    if adb_states & {"recovery", "sideload"}:
        if "sideload" in adb_states:
            return "RECOVERY MODE (adb sideload active)"
        return "RECOVERY MODE (stock recovery - adb shell root)"
    if "unauthorized" in adb_states:
        return "ADB PRESENT - UNAUTHORIZED (allow USB debugging on phone)"
    if "offline" in adb_states:
        return "ADB PRESENT - OFFLINE (unplug + replug, accept dialog)"

    adb = image = hid = diag = storage = ptp = rndis = False
    for d in samsung:
        if _has_adb_iface(d["interfaces"]):
            adb = True
        image = image or any(i["class"] == 6 for i in d["interfaces"])
        hid = hid or any(i["class"] == 3 for i in d["interfaces"])
        diag = diag or any(
            i["class"] == 2 and i["subclass"] == 2 and i["protocol"] == 1
            for i in d["interfaces"]
        )
        storage = storage or any(i["class"] == 8 for i in d["interfaces"])
        ptp = ptp or any(i["class"] == 6 and i["subclass"] == 1 for i in d["interfaces"])
        rndis = rndis or any(
            i["class"] == 0xEF and i["subclass"] == 4 and i["protocol"] == 1
            for i in d["interfaces"]
        )

    # Check for EDL mode (Qualcomm emergency download)
    for d in samsung:
        if d.get("vid") == 0x05C6 and d.get("pid") == 0x9008:
            return "EDL MODE (Qualcomm Emergency Download)"

    # Check for BROM mode (BootROM)
    for d in samsung:
        if d.get("pid") == 0x685C:
            return "BROM MODE (BootROM - low-level flashing)"

    # Check for MTK MediaTek devices (VID 0x0E8D) - the Samsung MTK (A05/A06)
    # low-level modes appear as their own USB vendor, not under 04e8.
    for d in (mtk_devs or []):
        pid = d.get("pid")
        mfr = (d.get("manufacturer") or "").lower()
        prod = (d.get("product") or "").lower()
        is_samsung_mtk = "samsung" in mfr or "samsung" in prod
        prefix = "SAMSUNG MTK" if is_samsung_mtk else "MEDIATEK"
        if pid == 0x2000:
            return f"{prefix} BROM (held state)"
        elif pid == 0x0003:
            return f"{prefix} PRELOADER (first bootloader stage)"
        elif pid == 0x0004:
            return f"{prefix} DA (flashing active)"
        else:
            return f"{prefix} MODE (VID 0x0E8D PID 0x{pid:04X})"
    
    if adb and diag and image:
        return "MTP + DIAG + ADB (combined config)"
    if adb and diag:
        return "DIAG + ADB (debug composite with AT port)"
    if adb:
        return "ADB ENABLED (debug composite) - normal boot"
    if diag and image:
        return "MTP + DIAG (AT port) - combined config"
    if diag and storage:
        return "STORAGE + DIAG (AT port)"
    if diag:
        return "DIAG/MODEM CONFIG (AT port)"
    if rndis:
        return "TETHERING (RNDIS network adapter)"
    if storage:
        return "MASS STORAGE MODE"
    if ptp:
        return "PTP MODE (Picture Transfer)"
    if image:
        return "NORMAL BOOT / SETUP WIZARD (MTP)"
    if hid:
        return "DOWNLOAD MODE - HID interface"
    for d in samsung:
        known = _SAMSUNG_PIDS.get(d["pid"])
        if known:
            return known
    return "OTHER MODE"


def _mode_chip(mode):
    if not mode:
        return "NOT CONNECTED", C["card"], C["mute"], C["mute"]
    m = mode.upper()
    if "RECOVERY" in m:
        return "RECOVERY", C["warn_dim"], C["warn"], C["warn"]
    if "ADB" in m:
        return "ADB", C["chip_blue"], C["chip_text"], C["accent"]
    if "BROM" in m:
        return "BROM", C["err_dim"], C["err"], C["err"]
    if "MTK" in m:
        return "MTK", C["warn_dim"], C["warn"], C["warn"]
    if "DIAG" in m:
        return "DIAG/AT", C["warn_dim"], C["warn"], C["warn"]
    if "DOWNLOAD" in m:
        return "DOWNLOAD", C["err_dim"], C["err"], C["err"]
    if "EDL" in m:
        return "EDL", C["err_dim"], C["err"], C["err"]
    if "FASTBOOT" in m:
        return "FASTBOOT", C["warn_dim"], C["warn"], C["warn"]
    if "BOOTLOADER" in m:
        return "BOOTLOADER", C["warn_dim"], C["warn"], C["warn"]
    if "TETHERING" in m or "RNDIS" in m:
        return "RNDIS", C["ok_dim"], C["ok"], C["ok"]
    if "STORAGE" in m:
        return "STORAGE", C["ok_dim"], C["ok"], C["ok"]
    if "PTP" in m:
        return "PTP", C["ok_dim"], C["ok"], C["ok"]
    if "NORMAL" in m or "SETUP" in m:
        return "MTP", C["ok_dim"], C["ok"], C["ok"]
    if "MTP" in m:
        return "MTP", C["ok_dim"], C["ok"], C["ok"]
    return "OTHER", C["card"], C["dim"], C["dim"]


# ---------------------------------------------------------------------------
# Premium composable widgets
# ---------------------------------------------------------------------------
class FlowLayout(QLayout):
    """Wrapping layout: children flow left-to-right and wrap to the next
    row when they exceed the available width (used for the operations
    button grid so 60+ action buttons never clip vertically)."""

    def __init__(self, parent=None, margin=0, spacing=8):
        super().__init__(parent)
        self._items = []
        self._margin = margin
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self._spacing
        m = self.contentsMargins()
        max_x = rect.right() - m.right()
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > max_x and line_height > 0:
                x = rect.x() + m.left()
                y += line_height + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + spacing
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()


class SamsungSubTabs(QFrame):
    """Horizontal sub-tab bar for the Samsung operations panel - a compact
    terminal-style segmented control (FLASH / UNLOCK & FRP / INFO & TOOLS) so
    the operations are split into focused views instead of one congested column."""

    tab_selected = pyqtSignal(str)

    def __init__(self, tabs, parent=None):
        super().__init__(parent)
        self.setObjectName("subnav")
        self.setStyleSheet(
            f"QFrame#subnav {{ background:{C['inset']};"
            f" border:1px solid {C['border']}; border-radius:7px; }}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(3)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._keys = []
        for i, (key, label) in enumerate(tabs):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.setStyleSheet(
                f"QPushButton {{ border:none; border-radius:4px; padding:0 14px;"
                f" font-family:'JetBrains Mono','Consolas',monospace;"
                f" font-size:10px; font-weight:800; letter-spacing:1.5px;"
                f" color:{C['mute']}; background:transparent; }}"
                f" QPushButton:hover {{ color:{C['text']};"
                f" background:{C['card_hover']}; }}"
                f" QPushButton:checked {{ color:#04121a;"
                f" background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                f" stop:0 {C['grad_a']}, stop:1 {C['grad_b']}); }}"
            )
            btn.clicked.connect(
                lambda _=False, k=key: self.tab_selected.emit(k)
            )
            self._group.addButton(btn, i)
            self._keys.append(key)
            lay.addWidget(btn, 1)
        if self._keys:
            self._group.button(0).setChecked(True)

    def set_tab(self, key):
        if key in self._keys:
            self._group.button(self._keys.index(key)).setChecked(True)


class CollapsibleSection(QFrame):
    """Circuit-deck collapsible panel: a clickable header with a chevron +
    terminal title that toggles the body. Keeps dense pages (like the FLASH
    tab) to one screen - advanced panels collapse by default."""

    def __init__(self, title, body, accent=C["accent"], collapsed=False,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("colsec")
        self._title = title
        self._accent = accent
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


class MetricCard(QFrame):
    def __init__(self, caption, value="--", accent=C["accent"]):
        super().__init__()
        self.setObjectName("metric")
        self._accent_hex = accent
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(8)
        bar = QLabel()
        bar.setFixedSize(3, 24)
        bar.setStyleSheet(f"background:{accent}; border-radius:1.5px;")
        top.addWidget(bar, 0, Qt.AlignmentFlag.AlignVCenter)
        cap = QLabel(caption.upper())
        cap.setStyleSheet(
            f"color:{C['mute']}; font-size:10px; font-weight:700; letter-spacing:1px;"
        )
        top.addWidget(cap)
        lay.addLayout(top)
        self.value = QLabel(value)
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.value.setWordWrap(True)
        self.value.setStyleSheet(
            f"color:{C['text']}; font-size:14px; font-weight:600; background:transparent;"
        )
        lay.addWidget(self.value)
        self.setStyleSheet(
            f"QFrame#metric {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border']}; border-left: 2px solid {self._accent_hex};"
            f" border-top: 1px solid {C['border_hi']};"
            f" border-radius: 8px; }}"
            f" QFrame#metric:hover {{ border: 1px solid {self._accent_hex};"
            f" background: {C['card_hover']}; }}"
        )

    def set(self, text):
        if self.value.text() != text:
            self.value.setText(text)


class _SettingsCatButton(QPushButton):
    """Windows-11 style settings category button."""

    def __init__(self, glyph, label):
        super().__init__(f"{glyph}  {label}")
        self._label = label
        self._active = False
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(40)
        self.setStyleSheet(
            "QPushButton { border: none; background: transparent;"
            " text-align: left; padding-left: 12px; }"
        )

    def set_active(self, a):
        self._active = a
        self.setChecked(a)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if self._active:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0, QColor(C["accent"]).darker(140))
            grad.setColorAt(1, QColor(C["panel"]))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(4, 3, w - 8, h - 6), 5, 5)
            bar = QLinearGradient(0, 0, 4, 0)
            bar.setColorAt(0, QColor(C["grad_a"]))
            bar.setColorAt(1, QColor(C["grad_b"]))
            p.setBrush(bar)
            p.drawRoundedRect(QRectF(4, 8, 4, h - 16), 2, 2)
        color = QColor(C["text"]) if self._active else QColor(C["dim"])
        if not self._active and self.underMouse():
            color = QColor(C["text"])
        p.setPen(QPen(color))
        p.setFont(self.font())
        fm = p.fontMetrics()
        p.drawText(18, (h - fm.height()) // 2 + fm.ascent(), self.text())
        p.end()


class SectionTitle(QLabel):
    def __init__(self, text, accent=C["accent"]):
        super().__init__(text)
        self._accent = accent
        self.setStyleSheet(
            f"color:{C['dim']}; font-size:11px; font-weight:700; letter-spacing:1.5px;"
        )
        self.setContentsMargins(0, 0, 0, 0)

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


class StatusOrb(QWidget):
    """Pulsing connection indicator."""

    def __init__(self):
        super().__init__()
        self._color = QColor(C["mute"])
        self._phase = 0.0
        self._connected = False
        self._anim = True
        self.setFixedSize(22, 22)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(35)

    def set_animations(self, on):
        self._anim = bool(on)
        if not on:
            self._phase = 0.0
            self.update()

    def set_connected(self, c):
        if c != self._connected:
            self._connected = c
            self._phase = 0.0
            if not c:
                self.update()

    def _tick(self):
        if self._connected and self._anim:
            self._phase = (self._phase + 0.05) % 1.0
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = cy = 11.0
        if self._connected:
            r = 4.5 + 5.0 * (1.0 - self._phase)
            halo = QColor(C["ok"])
            halo.setAlpha(int(130 * (1.0 - self._phase)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C["ok"]) if self._connected else QColor(C["mute"]))
        p.drawEllipse(QRectF(cx - 5, cy - 5, 10, 10))
        p.end()


def _metal_gradient(x0, y0, x1, y1):
    g = QLinearGradient(x0, y0, x1, y1)
    g.setColorAt(0.00, QColor("#e8edf2"))
    g.setColorAt(0.18, QColor("#f7f9fb"))
    g.setColorAt(0.45, QColor("#b9c2cc"))
    g.setColorAt(0.55, QColor("#9aa5b1"))
    g.setColorAt(1.00, QColor("#6b7683"))
    return g


class ConnectionScene(QWidget):
    """Computer -- cable -- phone, with the USB cable plugging into the
    BOTTOM of the phone (like a real phone port) instead of its side.

    Connected: the plug is seated in the phone's port, cable taut, data pulse
    running. Disconnected: the plug pulls out and dangles below the empty port
    on a slack cable.
    """

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(176)
        self._connected = False
        self._plug_t = 0.0
        self._vendor = None
        self._vendor_color = None
        self._anim = True
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_animations(self, on):
        self._anim = bool(on)
        if not on:
            self._phase = 0.0
            self._plug_t = 1.0 if self._connected else 0.0
            self.update()

    def set_connected(self, c):
        if self._connected == c:
            return
        self._connected = c
        self.update()

    def set_vendor(self, label, color=None):
        self._vendor = label
        self._vendor_color = color or C["ok"]
        self.update()

    def _tick(self):
        self._phase = (self._phase + 0.02) % 1.0
        # ease the plug between dangling and seated so insertion/removal is smooth
        target = 1.0 if self._connected else 0.0
        if self._anim:
            step = 0.08
        else:
            step = 1.0
        if abs(self._plug_t - target) > 0.001:
            if self._plug_t < target:
                self._plug_t = min(target, self._plug_t + step)
            else:
                self._plug_t = max(target, self._plug_t - step)
        self.update()

    def _cable_path(self, c0, plug_pt, rail):
        path = QPainterPath()
        path.moveTo(c0)
        t = self._plug_t
        if t > 0.5:
            # mostly seated: tight, straight cable
            path.cubicTo(c0.x() + 16, c0.y(), c0.x() + 18, rail,
                         c0.x() + 30, rail)
            path.lineTo(plug_pt.x(), rail)
            path.cubicTo(plug_pt.x(), rail, plug_pt.x(),
                         plug_pt.y() - 5, plug_pt.x(), plug_pt.y())
        else:
            # dangling: deeper sag, then droops down to the loose plug
            sway = math.sin(self._phase * math.tau) * (2.2 if self._anim else 0.0)
            path.cubicTo(c0.x() + 22, c0.y() + 2, c0.x() + 26, rail,
                         c0.x() + 40 + sway, rail)
            path.lineTo(plug_pt.x(), rail)
            path.cubicTo(plug_pt.x(), rail + 2, plug_pt.x() + 3,
                         plug_pt.y() - 14, plug_pt.x(), plug_pt.y())
        return path

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = float(self.width())
        h = float(self.height())

        # circuit-grid backdrop: faint traces + nodes + a vertical scanline
        grid = QColor(C["accent"])
        grid.setAlpha(22)
        p.setPen(QPen(grid, 1))
        step = 26.0
        gx = 0.0
        while gx < w:
            p.drawLine(QPointF(gx, 0), QPointF(gx, h))
            gx += step
        gy = 0.0
        while gy < h:
            p.drawLine(QPointF(0, gy), QPointF(w, gy))
            gy += step
        # junction nodes where traces cross
        node = QColor(C["accent_hi"])
        node.setAlpha(60)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(node)
        for gxx in range(1, int(w / step)):
            for gyy in range(1, int(h / step)):
                if (gxx + gyy) % 3 == 0:
                    p.drawEllipse(QRectF(gxx * step - 1.2, gyy * step - 1.2, 2.4, 2.4))
        # moving vertical scanline sweep
        scan_x = int((self._phase * (w + 80)) - 40)
        sc = QLinearGradient(scan_x - 20, 0, scan_x + 20, 0)
        sc.setColorAt(0, QColor(125, 211, 252, 0))
        sc.setColorAt(0.5, QColor(125, 211, 252, 26))
        sc.setColorAt(1, QColor(125, 211, 252, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(sc)
        p.drawRect(QRect(scan_x - 20, 0, 40, int(h)))

        icon = 80.0
        pc_x = 10.0
        phone_x = w - 10.0 - icon
        top_y = (h - icon) * 0.24
        pc_y = top_y
        phone_y = top_y

        # devices
        p.drawPixmap(int(pc_x), int(pc_y),
                     _draw_computer(int(icon), self._connected))
        p.drawPixmap(int(phone_x), int(phone_y),
                     _draw_phone(int(icon), self._connected))

        # connected: soft radial glow behind the phone + vendor chip
        if self._connected:
            glow = QRadialGradient(phone_x + icon / 2, phone_y + icon / 2,
                                   icon * 0.9)
            vc = QColor(self._vendor_color or C["ok"])
            glow.setColorAt(0.0, QColor(vc.red(), vc.green(), vc.blue(), 70))
            glow.setColorAt(0.6, QColor(vc.red(), vc.green(), vc.blue(), 20))
            glow.setColorAt(1.0, QColor(vc.red(), vc.green(), vc.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(QRectF(phone_x - 4, phone_y - 4,
                                 icon + 8, icon + 8))

            if self._vendor:
                fm = p.fontMetrics()
                bw = fm.horizontalAdvance(self._vendor) + 18
                bh = 20
                bx = phone_x + icon / 2 - bw / 2
                by = max(0.0, phone_y - 26)
                p.setPen(QPen(QColor(vc.red(), vc.green(), vc.blue(), 80), 1))
                p.setBrush(QColor(14, 20, 30, 200))
                p.drawRoundedRect(QRectF(bx, by, bw, bh), 8, 8)
                p.setPen(QPen(vc))
                p.setFont(QFont("JetBrains Mono", 8, QFont.Weight.ExtraBold))
                p.drawText(QRectF(bx, by, bw, bh),
                           Qt.AlignmentFlag.AlignCenter, self._vendor)

        # --- plug geometry (interpolated for smooth insert/remove) ---
        t = self._plug_t
        plug_w = 20.0
        plug_h = 13.0
        px = phone_x + icon * 0.5
        port_bottom = phone_y + icon * 0.95

        # plug travels from dangling (t=0) up into the port (t=1)
        sway = math.sin(self._phase * math.tau) * (2.2 if self._anim else 0.0)
        plug_y = port_bottom - plug_h + 1 + (1.0 - t) * 18.0
        plug_x = px - plug_w / 2 + sway * (1.0 - t)
        plug = QRectF(plug_x, plug_y, plug_w, plug_h)
        plug_pt = QPointF(plug.center().x(), plug.top())
        c0 = QPointF(pc_x + icon * 0.92, pc_y + icon * 0.60)

        # --- cable ---
        rail = h - 24 if t > 0.5 else h - 9
        path = self._cable_path(c0, plug_pt, rail)

        # soft drop shadow under the whole cable
        p.setPen(QPen(QColor(0, 0, 0, 70), 8, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path.translated(0, 1.8))
        # braided body
        p.setPen(QPen(QColor("#2b3441"), 7.0, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)
        p.setPen(QPen(QColor("#44515f"), 3.6, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)
        p.setPen(QPen(QColor("#5c6c7c"), 1.1, Qt.PenStyle.DashLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)
        if self._connected:
            p.setPen(QPen(QColor(C["ok"]), 1.8, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(path)

        # --- computer socket ---
        sock = QRectF(c0.x() - 3, c0.y() - 6, 9, 12)
        p.setPen(QPen(QColor("#7c8a99"), 1))
        p.setBrush(QColor(12, 16, 22))
        p.drawRoundedRect(sock, 1.5, 1.5)
        if self._connected:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(C["ok"]))
            p.drawRoundedRect(QRectF(sock.x() + 2.5, sock.y() + 2.5, 4, 7), 1.5, 1.5)

        # --- plug (premium USB-C connector) ---
        # soft shadow under plug
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 100))
        p.drawRoundedRect(plug.translated(0, 2.5), 4, 4)

        # animated connection glow (breathing) around the connector
        breathe = 0.5 + 0.5 * math.sin(self._phase * math.tau * 2)
        if self._connected:
            vc = QColor(self._vendor_color or C["ok"])
            halo = QRadialGradient(plug.center().x(), plug.center().y(),
                                   plug_w * 1.25)
            halo.setColorAt(0, QColor(vc.red(), vc.green(), vc.blue(),
                                      int(70 + 50 * breathe)))
            halo.setColorAt(0.55, QColor(vc.red(), vc.green(), vc.blue(),
                                         int(26 + 20 * breathe)))
            halo.setColorAt(1, QColor(vc.red(), vc.green(), vc.blue(), 0))
            p.setBrush(halo)
            p.drawRoundedRect(plug.adjusted(-6, -5, 6, 5), 7, 7)

        # connector collar (strain-relief where the sleeve meets the cable)
        collar = QRectF(plug.x() + 1.5, plug.y() - 1.2, plug.width() - 3, 3.5)
        cr = QLinearGradient(collar.left(), collar.top(), collar.right(), collar.bottom())
        cr.setColorAt(0, QColor("#4a525d"))
        cr.setColorAt(0.5, QColor("#6b7683"))
        cr.setColorAt(1, QColor("#39424e"))
        p.setPen(QPen(QColor("#2c343f"), 1))
        p.setBrush(cr)
        p.drawRoundedRect(collar, 1.5, 1.5)

        # metal plug body (brushed, with bevels)
        body_rect = plug
        pg = QLinearGradient(plug.left(), plug.top(), plug.right(), plug.bottom())
        pg.setColorAt(0.00, QColor("#f2f5f8"))
        pg.setColorAt(0.20, QColor("#c7cfd8"))
        pg.setColorAt(0.48, QColor("#9aa5b1"))
        pg.setColorAt(0.52, QColor("#7d8895"))
        pg.setColorAt(1.00, QColor("#58636f"))
        p.setPen(QPen(QColor("#39424e"), 1))
        p.setBrush(pg)
        p.drawRoundedRect(body_rect, 5, 5)

        # top sheen (moving highlight while powered)
        if self._anim and self._connected:
            sweep = self._phase
        else:
            sweep = 0.35
        shw = QRectF(plug.x() + 1.5, plug.y() + 1, plug.width() - 3, plug.height() * 0.36)
        sh = QLinearGradient(shw.left(), shw.top(), shw.right(), shw.top())
        sh.setColorAt(max(0.0, sweep - 0.5), QColor(255, 255, 255, 0))
        sh.setColorAt(sweep, QColor(255, 255, 255, 110))
        sh.setColorAt(min(1.0, sweep + 0.5), QColor(255, 255, 255, 0))
        p.setBrush(sh)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(shw, 2, 2)

        # grip ridges (machined lines)
        p.setPen(QPen(QColor(20, 26, 34, 80), 1))
        for i in range(3):
            gx = plug.x() + 3 + i * (plug.width() - 6) / 2
            p.drawLine(QPointF(gx, plug.y() + plug.height() * 0.40),
                       QPointF(gx, plug.bottom() - 1.2))

        # USB-C tip (recessed metal tongue with gold contacts)
        tip_w = 10.0
        tip_h = 7.0
        tip = QRectF(plug_pt.x() - tip_w / 2, plug.y() - tip_h + 1.2, tip_w, tip_h)
        tg = QLinearGradient(tip.left(), tip.top(), tip.left(), tip.bottom())
        tg.setColorAt(0, QColor("#e8edf2"))
        tg.setColorAt(0.5, QColor("#aeb9c4"))
        tg.setColorAt(1, QColor("#7c8895"))
        p.setPen(QPen(QColor("#3d4754"), 0.8))
        p.setBrush(tg)
        p.drawRoundedRect(tip, 1.5, 1.5)
        # gold pin contacts (2x3)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f0c060"))
        for row in range(2):
            for k in range(3):
                cx = tip.x() + 1.6 + k * 2.3
                cy = tip.y() + 1.5 + row * 2.3
                p.drawRoundedRect(QRectF(cx, cy, 1.2, 0.8), 0.5, 0.5)
        # darker tongue core between the pins
        p.setPen(QPen(QColor("#2c343f"), 1))
        p.drawLine(QPointF(tip.center().x(), tip.y() + 0.6),
                   QPointF(tip.center().x(), tip.bottom() - 0.6))

        # activity LED on the plug: pulses with data while powered
        if self._connected:
            led_on = (math.sin(self._phase * math.tau * 6) > -0.4)
            led_rad = 2.6 + 0.4 * breathe
            led = QRadialGradient(plug.right() - 4.5, plug.y() + 4.5, 5)
            led_col = QColor(self._vendor_color or C["ok"])
            led.setColorAt(0, QColor(led_col.red(), led_col.green(), led_col.blue(), 220))
            led.setColorAt(1, QColor(led_col.red(), led_col.green(), led_col.blue(), 0))
            p.setBrush(led)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(plug.right() - 7.5, plug.y() + 2.5, 7.5, 7.5))
            p.setBrush(led_col if led_on else QColor(led_col.red(), led_col.green(),
                                                     led_col.blue(), 120))
            p.drawEllipse(QRectF(plug.right() - 5.6, plug.y() + 4.2, 3.8, 3.8))

        # --- data pulses travelling along the cable (2 phases) ---
        if self._connected:
            for k in range(2):
                ph = (self._phase + k * 0.5) % 1.0
                pos = path.pointAtPercent(ph)
                glow = QRadialGradient(pos.x(), pos.y(), 9)
                vc = QColor(C["accent_hi"])
                glow.setColorAt(0, QColor(vc.red(), vc.green(), vc.blue(), 200))
                glow.setColorAt(1, QColor(vc.red(), vc.green(), vc.blue(), 0))
                p.setBrush(glow)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(pos.x() - 9, pos.y() - 9, 18, 18))
                p.setPen(QPen(QColor(C["accent_hi"]), 5.0, Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap))
                p.drawLine(pos, QPointF(pos.x() - 14, pos.y()))
                p.setPen(QPen(QColor(255, 255, 255, 130), 2.0, Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap))
                p.drawLine(pos, QPointF(pos.x() - 14, pos.y()))
        p.end()


class AccentStrip(QWidget):
    """Ultra-thin animated gradient sheen pinned to the top of a panel."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(3)
        self._phase = 0.0
        self._active = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def set_active(self, a):
        self._active = a
        if not a:
            self.update()

    def _tick(self):
        if self._active:
            self._phase = (self._phase + 0.012) % 1.0
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, QColor(C["grad_a"]))
        grad.setColorAt(0.5, QColor(C["grad_b"]))
        grad.setColorAt(1, QColor(C["grad_a"]))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
        if self._active:
            sweep = int(w * 0.34)
            x0 = int(self._phase * (w + sweep)) - sweep
            sheen = QLinearGradient(x0, 0, x0 + sweep, 0)
            sheen.setColorAt(0, QColor(255, 255, 255, 0))
            sheen.setColorAt(0.5, QColor(255, 255, 255, 200))
            sheen.setColorAt(1, QColor(255, 255, 255, 0))
            p.setBrush(sheen)
            p.drawRoundedRect(x0, 0, sweep, h, h / 2, h / 2)
        p.end()


class ShimmerBar(QWidget):
    """Animated gradient sweep used as the busy/progress indicator."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(8)
        self._active = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def set_active(self, a):
        self._active = a
        if not a:
            self.update()

    def _tick(self):
        if self._active:
            self._phase = (self._phase + 0.02) % 1.0
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C["inset"]))
        p.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
        if self._active:
            sweep = int(w * 0.42)
            x0 = int((self._phase * (w + sweep)) - sweep)
            grad = QLinearGradient(x0, 0, x0 + sweep, 0)
            grad.setColorAt(0, QColor(C["grad_a"]))
            grad.setColorAt(1, QColor(C["grad_b"]))
            p.setBrush(grad)
            p.drawRoundedRect(x0, 0, sweep, h, h / 2, h / 2)
        else:
            p.setBrush(QColor(C["border"]))
            p.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
        p.end()


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


# ---------------------------------------------------------------------------
# Splash screen
# ---------------------------------------------------------------------------
_SPLASH_MESSAGES = [
    "Loading Rust bridge...",
    "Mounting USB subsystem...",
    "Preparing protocol modules...",
    "Warming the console...",
    "Nearly there...",
]


class SplashScreen(QWidget):
    """Frameless splash with the classic badge logo, an animated progress bar
    and cycling status lines; pulses then fades out before the main window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._alpha = 1.0
        self._pulse = 0.0
        self._progress = 0.0
        self._msg_idx = 0

        logo_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..", "docs", "logo_256.png",
        )
        if os.path.exists(logo_path):
            self._logo = QPixmap(logo_path)
        else:
            self._logo = _draw_logo(256)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(500, 380)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def _tick(self):
        self._pulse += 0.05
        self._progress = min(1.0, self._progress + 0.006)
        self._msg_idx = min(len(_SPLASH_MESSAGES) - 1,
                            int(self._progress * len(_SPLASH_MESSAGES)))
        self.update()
        if self._progress >= 1.0:
            self._alpha = max(0.0, self._alpha - 0.025)
            self.update()
            if self._alpha <= 0.0:
                self._timer.stop()
                self.close()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # carbon deck background
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor("#0a1220"))
        grad.setColorAt(1, QColor("#04070c"))
        p.setBrush(grad)
        p.setPen(QPen(QColor(C["border_hi"]), 1))
        p.drawRoundedRect(QRectF(0, 0, w - 1, h - 1), 14, 14)

        # faint circuit grid
        grid = QColor(C["accent"])
        grid.setAlpha(14)
        p.setPen(QPen(grid, 1))
        step = 24.0
        gx = 0.0
        while gx < w:
            p.drawLine(QPointF(gx, 0), QPointF(gx, h))
            gx += step
        gy = 0.0
        while gy < h:
            p.drawLine(QPointF(0, gy), QPointF(w, gy))
            gy += step

        # soft radial glow behind the logo
        glow = QRadialGradient(w / 2, 150, 220)
        glow.setColorAt(0, QColor(34, 211, 238, 40))
        glow.setColorAt(1, QColor(34, 211, 238, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawRect(QRect(0, 0, w, h))

        # top accent bar (subtle breathing pulse)
        pulse = 0.7 + 0.3 * math.sin(self._pulse)
        ag = QLinearGradient(0, 0, w, 0)
        ag.setColorAt(0, QColor(C["grad_a"]))
        ag.setColorAt(1, QColor(C["grad_b"]))
        p.setBrush(ag)
        p.setOpacity(pulse)
        p.drawRoundedRect(QRectF(26, 20, w - 52, 4), 2, 2)
        p.setOpacity(self._alpha)

        # hex circuit logo
        logo_size = 116
        p.drawPixmap(
            QRect((w - logo_size) // 2, 44, logo_size, logo_size),
            _draw_logo(logo_size),
        )

        # title (terminal style)
        p.setFont(QFont("JetBrains Mono", 19, QFont.Weight.ExtraBold))
        p.setPen(QPen(QColor(C["text"])))
        p.drawText(
            QRectF(0, 166, w, 34),
            Qt.AlignmentFlag.AlignCenter,
            "flashpilot FLASHING TOOL",
        )

        # tagline
        p.setFont(QFont("JetBrains Mono", 9, QFont.Weight.DemiBold))
        p.setPen(QPen(QColor(C["accent_hi"])))
        p.drawText(
            QRectF(0, 202, w, 22),
            Qt.AlignmentFlag.AlignCenter,
            ">>  FRP  ·  FLASHING  ·  MTK  ·  QUALCOMM  ·  SPD  <<",
        )

        # segmented progress bar (ticked, instrument-style)
        bar_w, bar_h = w - 110, 10
        bx = (w - bar_w) / 2
        by = 248
        segs = 40
        seg_w = (bar_w - (segs - 1) * 2) / segs
        filled = int(segs * self._progress)
        for i in range(segs):
            sx = bx + i * (seg_w + 2)
            if i < filled:
                gr = QLinearGradient(sx, 0, sx + seg_w, 0)
                gr.setColorAt(0, QColor(C["grad_a"]))
                gr.setColorAt(1, QColor(C["grad_b"]))
                p.setBrush(gr)
            else:
                p.setBrush(QColor(255, 255, 255, 16))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(sx, by, seg_w, bar_h), 1.5, 1.5)

        # status line (mono, like a boot log)
        p.setFont(QFont("JetBrains Mono", 10))
        p.setPen(QPen(QColor(C["dim"])))
        p.drawText(
            QRectF(0, 274, w, 22),
            Qt.AlignmentFlag.AlignCenter,
            _SPLASH_MESSAGES[self._msg_idx],
        )

        # footer chips
        chips = "SAMSUNG  /  MEDIATEK  /  QUALCOMM  /  UNISOC"
        p.setFont(QFont("JetBrains Mono", 8, QFont.Weight.DemiBold))
        p.setPen(QPen(QColor(C["mute"])))
        p.drawText(
            QRectF(0, 318, w, 20),
            Qt.AlignmentFlag.AlignCenter,
            chips,
        )

        p.end()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class FrpWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlashPilot")

        self._cached_model = None
        self._cached_adb_status = None
        self._update_in_progress = False
        self._last_pid = None
        self._maximized = False
        self._log_buffer = []
        self._filter = {"err": True, "warn": True, "ok": True, "info": True}
        self._combo_styled = False
        self._anim_enabled = True
        self.settings = QSettings("FlashPilot", "FlashingTool")

        # apply persisted accent theme before any widget styles are generated
        theme = self.settings.value("theme", "Neon Circuit")
        if theme in ACCENT_THEMES:
            C.update(ACCENT_THEMES[theme])

        # Fit the window to the available screen so it is never cut off.
        screen = QApplication.primaryScreen().availableGeometry()
        fit_w = min(1180, max(960, screen.width() - 120))
        fit_h = min(760, max(640, screen.height() - 80))
        self.setMinimumSize(fit_w, fit_h)
        self.resize(fit_w, fit_h)

        # Frameless, translucent window with a rounded root card.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        app_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
        app_font.setPointSize(10)
        QApplication.instance().setFont(app_font)

        self.setStyleSheet(_BASE_QSS + _console_qss())

        self._build_ui()
        self.nav.select("samsung")

        # apply persisted effect settings to the freshly-built widgets
        if not self.settings.value("animations", "true", type=bool):
            self.scene.set_animations(False)
            self.orb.set_animations(False)
        if not self.settings.value("blur", "true", type=bool):
            self._root_shadow.setEnabled(False)

        # toast overlay on top of everything (top-right corner)
        self._toasts = ToastHost(self)
        self._toasts.show()

        # thread -> UI bridge
        self._ui = LogBridge()
        self._ui.line.connect(self.log_line)
        self._ui.status.connect(self.set_status)
        self._ui.metric.connect(self._set_metric)
        self._ui.qr.connect(self._show_qr_dialog)
        self._ui.finished.connect(self._on_finished)
        self._ui.toast.connect(self._show_toast)
        self._ui.ui.connect(self._run_on_ui)

        # live connection monitor
        self._monitor = DeviceMonitor(
            interval=max(1, int(self.settings.value("scan_interval", 3)))
        )
        self._monitor.state.connect(self._on_device_state)
        if self.settings.value("autoscan", "true", type=bool):
            self._monitor.start()

        # live ADB/model refresh (phone-side 'Allow USB debugging' is not a
        # USB re-enumeration, so poll for it).
        self._adb_timer = QTimer(self)
        self._adb_timer.timeout.connect(self._poll_adb_metric)
        self._adb_timer.timeout.connect(self._poll_net_live)
        self._adb_timer.start(3000)
        self._update_net_in_progress = False

        self._install_shortcuts()
        self.refresh_device()
        self.log_line(
            f"FlashPilot — console ready "
            f"({_time.strftime('%Y-%m-%d %H:%M:%S')})"
        )

    def showEvent(self, event):
        super().showEvent(event)
        if not self._combo_styled:
            self._combo_styled = True
            self._restyle_combos()

    def _restyle_combos(self):
        if hasattr(self, "_s_theme"):
            self._style_combo(self._s_theme)

    def _install_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self._clear_console)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self).activated.connect(self._copy_console)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._save_console)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(
            lambda: (self.find_edit.setFocus(), self.find_edit.selectAll())
        )
        QShortcut(QKeySequence("F5"), self).activated.connect(self.refresh_device)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self.refresh_device)
        QShortcut(QKeySequence("Ctrl+Escape"), self).activated.connect(self.on_stop)

    # ----------------------------- layout builders -------------------------
    def _build_ui(self):
        central = QWidget()
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)

        root = QFrame()
        root.setObjectName("root")
        root.setStyleSheet(
            f"QFrame#root {{ background: rgba(5, 9, 15, 244);"
            f" border: 1px solid {C['border_hi']}; border-top: 2px solid {C['accent']};"
            f" border-radius: 12px; }}"
        )
        root_shadow = QGraphicsDropShadowEffect(root)
        root_shadow.setBlurRadius(42)
        root_shadow.setOffset(0, 14)
        root_shadow.setColor(QColor(0, 0, 0, 170))
        root.setGraphicsEffect(root_shadow)
        self._root_shadow = root_shadow
        self._root = root

        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        self._accent_strip = AccentStrip()
        strip_wrap = QFrame()
        strip_wrap.setStyleSheet("background: transparent;")
        sw_lay = QHBoxLayout(strip_wrap)
        sw_lay.setContentsMargins(24, 0, 24, 0)
        sw_lay.addWidget(self._accent_strip)
        root_lay.addWidget(strip_wrap)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(30, 18, 30, 26)
        outer.addWidget(root)
        self._outer = outer

        # --- custom title bar ---
        titlebar = DragBar(self)
        titlebar.setFixedHeight(58)
        titlebar.setObjectName("dragbar")
        titlebar.setStyleSheet(
            f"QWidget#dragbar {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f" stop:0 rgba(16, 26, 40, 90), stop:0.55 rgba(10, 15, 23, 0),"
            f" stop:1 rgba(10, 15, 23, 90));"
            f" border-bottom: 1px solid {C['border']}; }}"
        )
        tb = QHBoxLayout(titlebar)
        tb.setContentsMargins(20, 8, 10, 6)
        tb.setSpacing(12)

        logo = QLabel()
        logo.setPixmap(_draw_logo(34))
        tb.addWidget(logo, 0, Qt.AlignmentFlag.AlignVCenter)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("flashpilot FLASHING TOOL")
        title.setStyleSheet(
            f"color:{C['text']}; font-size:16px; font-weight:800; letter-spacing:1.5px;"
        )
        sub = QLabel("FRP bypass · screen lock · download mode & ADB tooling")
        sub.setStyleSheet(
            f"color:{C['mute']}; font-size:10px;"
            f" font-family:'JetBrains Mono','Consolas',monospace;"
        )
        title_box.addWidget(title)
        title_box.addWidget(sub)
        tb.addLayout(title_box)

        tb.addStretch(1)

        self.badge = ModeBadge()
        tb.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)

        for kind, handler in (
            ("min", self.showMinimized),
            ("max", self._toggle_max),
            ("close", self.close),
        ):
            btn = WindowButton(kind)
            btn.clicked.connect(handler)
            tb.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)

        root_lay.addWidget(titlebar)

        # --- content ---
        body = QHBoxLayout()
        body.setContentsMargins(18, 4, 18, 14)
        body.setSpacing(14)

        self.nav = NavRail(
            [
                ("samsung", "◉", "Samsung"),
                ("quick", "⚡", "Quick Actions"),
                ("fus", "⬇", "Firmware Downloader"),
                ("mtk", "▣", "MTK Tools"),
                ("qc", "◈", "Qualcomm"),
                ("spd", "✦", "SPD / Unisoc"),
                ("battery", "⚡", "Battery Repair"),
                ("network", "📶", "Network Repair"),
                ("settings", "⚙", "Settings"),
            ]
        )
        self.nav.section_selected.connect(self._on_section)
        body.addWidget(self.nav)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("QStackedWidget { background: transparent; }")

        # Samsung page = operations/console panel (device scene + metrics live
        # in the shared connection banner above the stack).
        dash = QWidget()
        dash_lay = QHBoxLayout(dash)
        dash_lay.setContentsMargins(0, 0, 0, 0)
        dash_lay.setSpacing(14)
        dash_lay.addWidget(self._build_right(), 1)
        self._stack.addWidget(dash)

        self._stack.addWidget(self._build_quick_page())
        self._stack.addWidget(self._build_fus_page())
        self._stack.addWidget(self._build_mtk_page())
        self._stack.addWidget(self._build_qc_page())
        self._stack.addWidget(self._build_spd_page())
        self._stack.addWidget(self._build_battery_page())
        self._stack.addWidget(self._build_network_page())
        self._stack.addWidget(self._build_settings_page())

        # Connection banner shared by every section so the computer-cable-phone
        # scene (and its live animation) is visible on Samsung / MTK / Qualcomm.
        stack_col = QVBoxLayout()
        stack_col.setContentsMargins(0, 0, 0, 0)
        stack_col.setSpacing(10)
        stack_col.addWidget(self._build_conn_bar())
        stack_col.addWidget(self._stack, 1)

        body.addLayout(stack_col, 1)

        # Shared console/log column on the right side, visible on every section
        # (Samsung / MTK / Qualcomm / Settings) - TFT-unlock-tools style.
        body.addWidget(self._build_console())
        root_lay.addLayout(body, 1)

        self._grip = QSizeGrip(root)
        self._grip.setFixedSize(16, 16)
        root_lay.addWidget(
            self._grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight
        )

    def _set_conn_glow(self, color=None):
        accent = color or C["accent"]
        self._conn.setStyleSheet(
            f"QFrame#connbar {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 rgba(24, 33, 47, 210), stop:1 rgba(15, 21, 31, 215));"
            f" border: 1px solid {C['border_hi']};"
            f" border-top: 2px solid {accent};"
            f" border-radius: 13px; }}"
        )

    def _build_conn_bar(self):
        """Shared connection banner: computer -- cable -- phone scene + orb +
        state + live device metrics. Shown above the page stack so every
        section sees the same connection animation and device info."""
        conn = QFrame()
        conn.setObjectName("connbar")
        self._conn = conn
        conn.setStyleSheet(
            f"QFrame#connbar {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 rgba(15, 24, 38, 225), stop:1 rgba(7, 12, 19, 230));"
            f" border: 1px solid {C['border']}; border-top: 1px solid {C['accent']};"
            f" border-radius: 9px; }}"
            f" QFrame#connbar:hover {{ border: 1px solid {C['border_hi']};"
            f" background: rgba(16, 25, 39, 230); }}"
        )
        conn_lay = QHBoxLayout(conn)
        conn_lay.setContentsMargins(14, 8, 14, 8)
        conn_lay.setSpacing(14)

        # left: animated computer -- cable -- phone scene + orb + state
        left = QVBoxLayout()
        left.setSpacing(4)
        self.scene = ConnectionScene()
        self.scene.setMinimumHeight(108)
        left.addWidget(self.scene, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.orb = StatusOrb()
        row.addWidget(self.orb, 0, Qt.AlignmentFlag.AlignVCenter)
        self.conn_state = QLabel("No device connected")
        self.conn_state.setWordWrap(True)
        self.conn_state.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.conn_state.setStyleSheet(
            f"color:{C['dim']}; font-size:11px; font-weight:500; background:transparent;"
            f" font-family:'JetBrains Mono','Consolas',monospace;"
        )
        row.addWidget(self.conn_state, 1, Qt.AlignmentFlag.AlignVCenter)
        left.addLayout(row)
        conn_lay.addLayout(left, 3)

        # right: live device metric cards (model / mode / interface / adb)
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.info = {}
        tiles = [
            ("Device Model", C["grad_b"]),
            ("USB Mode", C["accent"]),
            ("Interface", C["ok"]),
            ("ADB Status", C["warn"]),
        ]
        for i, (name, accent) in enumerate(tiles):
            card = MetricCard(name, "--", accent)
            self.info[name] = card
            grid.addWidget(card, i // 2, i % 2)
        conn_lay.addLayout(grid, 2)

        return conn

    def _build_right(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(
            _card_qss()
        )
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        lay.addWidget(SectionTitle("OPERATIONS"))

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        self.info_btn = QPushButton("Get Device Info")
        self.info_btn.setStyleSheet(_btn_ghost())
        self.info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.info_btn.clicked.connect(self.refresh_device)
        self.info_btn.setToolTip("Scan the bus and print full device info to the console")
        top_row.addWidget(self.info_btn)
        top_row.addStretch(1)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(_btn_danger())
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.clicked.connect(self.on_stop)
        self.stop_btn.setToolTip("Cancel the running operation")
        top_row.addWidget(self.stop_btn)
        lay.addLayout(top_row)

        # TFT-style sub-tabs so the operations are split into focused views
        # instead of one congested scrollable column.
        self.samsung_tabs = SamsungSubTabs(
            [
                ("flash", "FLASH"),
                ("frp", "FRP"),
                ("lock", "SCREEN LOCK"),
                ("mdm", "MDM"),
                ("carrier", "CARRIER LOCK"),
                ("tools", "INFO & TOOLS"),
            ]
        )
        self.samsung_tabs.tab_selected.connect(self._on_samsung_tab)
        lay.addWidget(self.samsung_tabs)

        self.samsung_stack = QStackedWidget()
        self.samsung_stack.setStyleSheet("QStackedWidget { background: transparent; }")

        self._build_flash_inputs()
        flash_page = QWidget()
        flash_page.setStyleSheet("background: transparent;")
        fp_lay = QVBoxLayout(flash_page)
        fp_lay.setContentsMargins(0, 0, 0, 0)
        fp_lay.setSpacing(0)
        flash_scroll = self._ops_scroll_area()
        flash_host = QWidget()
        flash_host.setStyleSheet("background: transparent;")
        fh_lay = QVBoxLayout(flash_host)
        fh_lay.setContentsMargins(0, 0, 0, 0)
        fh_lay.setSpacing(8)
        self._firmware_sec = CollapsibleSection(
            "FIRMWARE SLOTS", self.firmware_panel, accent=C["accent"],
            collapsed=False
        )
        self._options_sec = CollapsibleSection(
            "FLASH OPTIONS", self.options_panel, accent=C["warn"],
            collapsed=True
        )
        self._adv_sec = CollapsibleSection(
            "ADVANCED FLASH", self.adv_panel, accent=C["ok"],
            collapsed=True
        )
        fh_lay.addWidget(self._firmware_sec)
        fh_lay.addWidget(self._options_sec)
        fh_lay.addWidget(self._adv_sec)
        fh_lay.addStretch(1)
        flash_scroll.setWidget(flash_host)
        fp_lay.addWidget(flash_scroll)
        self.samsung_stack.addWidget(flash_page)

        frp_page = self._build_ops_flow_page(["FRP bypass"])
        self.samsung_stack.addWidget(frp_page)

        lock_page = self._build_ops_flow_page(["Screen lock remove"])
        self.samsung_stack.addWidget(lock_page)

        mdm_page = self._build_ops_flow_page(["MDM unlock"])
        self.samsung_stack.addWidget(mdm_page)

        carrier_page = self._build_ops_flow_page(["Carrier lock"])
        self.samsung_stack.addWidget(carrier_page)

        utils_body = QWidget()
        utils_body.setStyleSheet("background: transparent;")
        u_lay = QVBoxLayout(utils_body)
        u_lay.setContentsMargins(0, 0, 0, 0)
        u_lay.setSpacing(0)
        self._add_job_flows(
            u_lay, ["Odin Flashing (Advanced)"],
            modes=["Download mode", "ADB"],
            methods=[
                "odin_preflight", "odin_efs_backup", "odin_efs_restore",
                "odin_pit_tools", "odin_list_devices", "odin_vbmeta",
                "reboot_normal",
            ],
        )
        tools_combo = QWidget()
        tools_combo.setStyleSheet("background: transparent;")
        tc_lay = QVBoxLayout(tools_combo)
        tc_lay.setContentsMargins(0, 0, 0, 0)
        tc_lay.setSpacing(0)
        scroll = self._ops_scroll_area()
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        hv = QVBoxLayout(host)
        hv.setContentsMargins(0, 0, 0, 0)
        hv.setSpacing(10)
        self._add_job_flows(hv, ["Read device info", "Detect", "Reboot device",
                                 "Fix Settings / UI crash"])
        utils = CollapsibleSection(
            "ODIN UTILITIES", utils_body, accent=C["mute"], collapsed=True
        )
        hv.addWidget(utils)
        hv.addStretch(1)
        scroll.setWidget(host)
        tc_lay.addWidget(scroll)
        self.samsung_stack.addWidget(tools_combo)

        lay.addWidget(self.samsung_stack, 1)

        self.shimmer = ShimmerBar()
        self.shimmer.setVisible(False)
        lay.addWidget(self.shimmer)

        self.status = QLabel("Ready")
        self.status.setStyleSheet(f"color:{C['dim']}; font-size:12px;")
        lay.addWidget(self.status)

        return panel

    def _on_samsung_tab(self, key):
        index = {"flash": 0, "frp": 1, "lock": 2, "mdm": 3,
                 "carrier": 4, "tools": 5}.get(key, 0)
        self.samsung_stack.setCurrentIndex(index)

    def _build_quick_page(self):
        """TFT-style QUICK page: one-tap Factory reset / Reboot / ADB / Fastboot
        actions without hunting through mode dropdowns."""
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(
            _card_qss()
        )
        panel_lay = QVBoxLayout(panel)
        panel_lay.setContentsMargins(0, 0, 0, 0)
        panel_lay.setSpacing(0)
        scroll = self._ops_scroll_area()
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        hv = QVBoxLayout(host)
        hv.setContentsMargins(16, 14, 16, 14)
        hv.setSpacing(12)

        hv.addWidget(SectionTitle("QUICK ACTIONS"))
        info = QLabel(
            "One-tap ADB & Fastboot actions - reboot destinations and factory "
            "reset without hunting through the mode dropdowns."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{C['mute']}; font-size:11px;")
        hv.addWidget(info)

        # --- Factory reset (ADB + recovery fallback) ---
        hv.addWidget(SectionTitle("FACTORY RESET"))
        fr_row = QHBoxLayout()
        fr_row.setSpacing(8)
        fr_btn = QPushButton("Factory reset")
        fr_btn.setStyleSheet(_btn_primary())
        fr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fr_btn.setToolTip("ADB wipe /data when authorized, else guided recovery reset")
        fr_btn.clicked.connect(
            lambda: self._confirm_overlay(
                "Factory Reset",
                "This WIPES ALL DATA on the connected device:\n\n"
                "  - Apps, accounts, photos, messages, files\n"
                "  - Phone / modem settings are kept\n\n"
                "It tries an ADB /data wipe first, and falls back to a guided "
                "recovery-mode reset if the device is not authorized.\n\n"
                "There is NO undo. Continue?",
                confirm_label="Wipe Device",
                on_confirm=lambda: self._run_ops_flow(
                    "FRP bypass", "ADB", "factory_reset",
                    frp.FLOWS["factory_reset"]().name,
                ),
            )
        )
        fr_row.addWidget(fr_btn)
        fr_row.addStretch(1)
        hv.addLayout(fr_row)

        # --- ADB: one-tap reboot destinations ---
        hv.addWidget(SectionTitle("ADB / USB DEBUGGING"))
        self._add_job_flows(hv, ["Reboot device"], modes=["ADB"])
        sw_row = QHBoxLayout()
        sw_row.setSpacing(8)
        sw_btn = QPushButton("Setup wizard bypass")
        sw_btn.setStyleSheet(_btn_ghost())
        sw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sw_btn.setToolTip(
            "Classic ADB bypass for older Android (7-8) stuck on the setup wizard"
        )
        sw_btn.clicked.connect(
            lambda: self._run_ops_flow(
                "FRP bypass", "ADB", "setup_wizard",
                frp.FLOWS["setup_wizard"]().name,
            )
        )
        sw_row.addWidget(sw_btn)
        sw_row.addStretch(1)
        hv.addLayout(sw_row)

        # --- Fastboot: reboot out of / within bootloader mode ---
        hv.addWidget(SectionTitle("FASTBOOT"))
        self._add_job_flows(hv, ["Reboot device"], modes=["FASTBOOT"])

        hv.addStretch(1)
        scroll.setWidget(host)
        panel_lay.addWidget(scroll)
        return panel

    def _ops_scroll_area(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        return scroll

    def _add_job_flows(self, parent_layout, jobs, modes=None, run_cb=None,
                       methods=None):
        """Add one wrapping FlowLayout of action buttons per job, no dropdowns.
        modes: optional iterable of frp modes to restrict which flows show.
        methods: optional iterable of method keys to show (only those).
        run_cb: optional callable(job, mode, key, name); defaults to the
        Samsung operations runner (_run_ops_flow)."""
        if modes is not None:
            modes = set(modes)
        for job in jobs:
            seen = set()
            entries = []
            for mode in frp.modes_for(job):
                if modes is not None and mode not in modes:
                    continue
                for key in frp.methods_for(job, mode):
                    if key in seen:
                        continue
                    if methods is not None and key not in methods:
                        continue
                    seen.add(key)
                    entries.append((key, mode))
            if not entries:
                continue
            header = QLabel(job.upper())
            header.setStyleSheet(
                f"color:{C['mute']}; font-size:11px; font-weight:800;"
                f" letter-spacing:1px; margin-top:4px;"
            )
            parent_layout.addWidget(header)
            flow = FlowLayout(spacing=8)
            for key, mode in entries:
                name = frp.FLOWS[key]().name
                b = QPushButton(name)
                b.setStyleSheet(_btn_ghost())
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setToolTip(f"{job} / {mode} / {key}")
                if run_cb is None:
                    confirm = _DESTRUCTIVE_CONFIRM.get(key)
                    if confirm:
                        b.clicked.connect(
                            lambda _=False, j=job, m=mode, k=key, n=name, t=confirm[0], tx=confirm[1]:
                                self._confirm_overlay(
                                    t, tx, confirm_label="Continue",
                                    on_confirm=lambda _=False, j=j, m=m, k=k, n=n:
                                        self._run_ops_flow(j, m, k, n),
                                )
                        )
                    else:
                        b.clicked.connect(
                            lambda _=False, j=job, m=mode, k=key, n=name: self._run_ops_flow(
                                j, m, k, n
                            )
                        )
                else:
                    confirm = _DESTRUCTIVE_CONFIRM.get(key)
                    if confirm:
                        b.clicked.connect(
                            lambda _=False, j=job, m=mode, k=key, n=name, t=confirm[0], tx=confirm[1]:
                                self._confirm_overlay(
                                    t, tx, confirm_label="Continue",
                                    on_confirm=lambda _=False, j=j, m=m, k=k, n=n:
                                        run_cb(j, m, k, n),
                                )
                        )
                    else:
                        b.clicked.connect(
                            lambda _=False, j=job, m=mode, k=key, n=name: run_cb(
                                j, m, k, n
                            )
                        )
                flow.addWidget(b)
            parent_layout.addLayout(flow)

    def _build_ops_flow_page(self, jobs, modes=None, run_cb=None):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        scroll = self._ops_scroll_area()
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        hv = QVBoxLayout(host)
        hv.setContentsMargins(0, 0, 0, 0)
        hv.setSpacing(10)
        self._add_job_flows(hv, jobs, modes=modes, run_cb=run_cb)
        hv.addStretch(1)
        scroll.setWidget(host)
        v.addWidget(scroll)
        return page

    def _build_chip_ops_section(self, chip, modes, stop_btn, progress, reset_ui,
                                flash_jobs=None):
        """Samsung-style sub-tab operations section for the chip pages - the
        same FLASH / FRP / SCREEN LOCK / MDM / INFO & TOOLS tabs, but only the
        flows that apply to that chipset's modes, run through _run_job_flow so
        they use the chip page's own stop button / progress / reset.
        flash_jobs: job list for the FLASH tab; pass None to skip the FLASH tab
        (chip pages already flash through their native tools, not Odin)."""
        def run_cb(job, mode, method, label):
            self._run_job_flow(job, mode, method, label, stop_btn, progress, reset_ui)

        tab_specs = []
        if flash_jobs:
            tab_specs.append(("flash", "FLASH", flash_jobs))
        tab_specs += [
            ("frp", "FRP", ["FRP bypass"]),
            ("lock", "SCREEN LOCK", ["Screen lock remove"]),
            ("mdm", "MDM", ["MDM unlock"]),
            (
                "tools",
                "INFO & TOOLS",
                ["Read device info", "Detect", "Reboot device",
                 "Fix Settings / UI crash"],
            ),
        ]
        modeset = set(modes)
        tabs = []
        pages = []
        for key, label, jobs in tab_specs:
            count = 0
            for job in jobs:
                for mode in frp.modes_for(job):
                    if mode in modeset:
                        count += len(frp.methods_for(job, mode))
            if not count:
                continue
            tabs.append((key, label))
            pages.append(
                (key, self._build_ops_flow_page(jobs, modes=modeset, run_cb=run_cb))
            )
        if not tabs:
            return None

        section = QWidget()
        section.setStyleSheet("background: transparent;")
        # Guarantee the sub-tab bar + a usable amount of action buttons room so
        # the chip pages never crush this section to ~0px (which made the tab
        # buttons overflow their bar and the flow buttons spill off-screen).
        section.setMinimumHeight(240)
        v = QVBoxLayout(section)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        subnav = SamsungSubTabs(tabs)
        v.addWidget(subnav)
        stack = QStackedWidget()
        stack.setStyleSheet("QStackedWidget { background: transparent; }")
        keys = [k for k, _ in pages]
        for _, page in pages:
            stack.addWidget(page)
        subnav.tab_selected.connect(
            lambda key: stack.setCurrentIndex(keys.index(key) if key in keys else 0)
        )
        v.addWidget(stack, 1)
        return section

    def _build_flash_inputs(self):
        # --- Zone 1: Firmware slots (circuit-deck panel) ---
        self.firmware_panel = QFrame()
        self.firmware_panel.setObjectName("firmware")
        self.firmware_panel.setStyleSheet(
            f"QFrame#firmware {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border']}; border-left: 2px solid {C['accent']};"
            f" border-top: 1px solid {C['border_hi']}; border-radius: 9px; }}"
        )
        f_lay = QVBoxLayout(self.firmware_panel)
        f_lay.setContentsMargins(14, 10, 14, 14)
        f_lay.setSpacing(8)

        self.slot_inputs = {}
        slots_grid = QGridLayout()
        slots_grid.setContentsMargins(0, 0, 0, 0)
        slots_grid.setHorizontalSpacing(10)
        slots_grid.setVerticalSpacing(8)

        slot_row = {"AP": 0, "BL": 0, "CP": 1, "CSC": 1, "USERDATA": 2}
        slot_col = {"AP": 0, "BL": 1, "CP": 0, "CSC": 1, "USERDATA": 0}

        def _slot_row(label, row, col, span):
            cell = QWidget()
            cell.setStyleSheet("background: transparent;")
            c_lay = QVBoxLayout(cell)
            c_lay.setContentsMargins(0, 0, 0, 0)
            c_lay.setSpacing(4)
            hl = QHBoxLayout()
            hl.setSpacing(6)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {C['accent_hi']}; font-weight: 800; font-size: 10px; min-width: 58px;")
            hl.addWidget(lbl)
            edit = QLineEdit()
            edit.setPlaceholderText(f"Select {label} (.tar)")
            edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            edit.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 4px 8px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")
            hl.addWidget(edit, 1)
            btn = QPushButton("Browse")
            btn.setStyleSheet(_btn_ghost())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(66)
            btn.clicked.connect(
                (lambda e=edit, n=label: lambda: self._browse_slot(e, n))()
            )
            hl.addWidget(btn)
            c_lay.addLayout(hl)
            slots_grid.addWidget(cell, row, col, 1, span)
            self.slot_inputs[label] = edit

        _slot_row("AP", 0, 0, 1)
        _slot_row("BL", 0, 1, 1)
        _slot_row("CP", 1, 0, 1)
        _slot_row("CSC", 1, 1, 1)
        _slot_row("USERDATA", 2, 0, 2)
        slots_grid.setColumnStretch(0, 1)
        slots_grid.setColumnStretch(1, 1)
        f_lay.addLayout(slots_grid)

        run_row = QHBoxLayout()
        run_row.setSpacing(8)
        self.flash_btn = QPushButton("Flash Firmware")
        self.flash_btn.setStyleSheet(_btn_primary())
        self.flash_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.flash_btn.setToolTip(
            "Flash the selected AP/BL/CP/CSC/USERDATA firmware (odin4)"
        )
        self.flash_btn.clicked.connect(self._on_flash_slots)
        run_row.addWidget(self.flash_btn)
        self.check_tar_btn = QPushButton("Check archive")
        self.check_tar_btn.setStyleSheet(_btn_ghost())
        self.check_tar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_tar_btn.setToolTip(
            "Validate the firmware archive / PIT with odin4 --check-only (no write)"
        )
        self.check_tar_btn.clicked.connect(
            lambda: self._run_ops_flow(
                "Odin Flashing (Advanced)", "Download mode",
                "odin_check_tar", "Check firmware archive (odin4)"
            )
        )
        run_row.addWidget(self.check_tar_btn)
        run_row.addStretch(1)
        f_lay.addLayout(run_row)
        f_lay.addWidget(
            _risk_banner(
                "Flashing overwrites your device's firmware. Wrong files or a "
                "power cut can brick it - keep it plugged in and charged."
            )
        )

        # --- Zone 2: Flash options (safety switches) ---
        self.options_panel = QFrame()
        self.options_panel.setObjectName("flashopts")
        self.options_panel.setStyleSheet(
            f"QFrame#flashopts {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border']}; border-left: 2px solid {C['warn']};"
            f" border-top: 1px solid {C['border_hi']}; border-radius: 9px; }}"
        )
        opt_lay = QVBoxLayout(self.options_panel)
        opt_lay.setContentsMargins(14, 10, 14, 14)
        opt_lay.setSpacing(6)

        opt_row = FlowLayout(spacing=8)
        self.allow_unknown_cb = QCheckBox("Allow unknown partitions (bypass PIT check, --allow-unknown)")
        self.allow_unknown_cb.setChecked(False)
        self.allow_unknown_cb.setToolTip(
            "OFF by default (safety). Lets odin4 skip archive entries that have no match\n"
            "in the device's PIT. Needed for unofficial/custom firmware or region variants\n"
            "whose partition table differs from the device ('check failure pit' / PIT mismatch).\n"
            "Only enable for firmware you are certain is correct for this device."
        )
        self.allow_unknown_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row.addWidget(self.allow_unknown_cb)
        self.auto_reboot_cb = QCheckBox("Auto-reboot after flash (--reboot)")
        self.auto_reboot_cb.setChecked(False)
        self.auto_reboot_cb.setToolTip(
            "OFF by default (safety). Lets odin4 reboot the phone as soon as the flash\n"
            "finishes. Leave OFF so you can verify the flash completed before rebooting -\n"
            "a failed write otherwise hides behind a phone that no longer answers."
        )
        self.auto_reboot_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row.addWidget(self.auto_reboot_cb)
        opt_lay.addLayout(opt_row)

        # Advanced options row 2 - always-work repair steps
        opt_row2 = FlowLayout(spacing=8)
        self.erase_nv_cb = QCheckBox("Erase NVRAM/NVDATA (zero-fill nv* partitions)")
        self.erase_nv_cb.setChecked(False)
        self.erase_nv_cb.setToolTip(
            "OFF by default (safety - wipes network calibration). After the flash,\n"
            "zero-fills every NVRAM/NVDATA partition from the device's own PIT using\n"
            "the native Odin flash path. Standard fix for IMEI/network issues and a\n"
            "common FRP-adjacent step. Works on Odin-protocol (Exynos/Qualcomm)\n"
            "download mode; MTK download-agent devices use the MediaTek workbench."
        )
        self.erase_nv_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row2.addWidget(self.erase_nv_cb)
        self.check_only_cb = QCheckBox("Validate archives first (--check-only)")
        self.check_only_cb.setChecked(False)
        self.check_only_cb.setToolTip(
            "Run odin4 --check-only over every selected archive BEFORE flashing.\n"
            "Aborts on corrupt/renamed .tar.md5 or PIT mismatches so a bad archive\n"
            "is never written to the phone."
        )
        self.check_only_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row2.addWidget(self.check_only_cb)
        self.redownload_cb = QCheckBox("Re-download after flash (--redownload)")
        self.redownload_cb.setChecked(False)
        self.redownload_cb.setToolTip(
            "After flashing, odin4 sends the Redownload command so the phone re-enters\n"
            "download mode instead of rebooting - the reliable way to chain a second\n"
            "step (like Erase NVRAM) without power-cycling. Mutually exclusive with\n"
            "auto-reboot."
        )
        self.redownload_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row2.addWidget(self.redownload_cb)
        self.verbose_cb = QCheckBox("Verbose logging (--verbose)")
        self.verbose_cb.setChecked(False)
        self.verbose_cb.setToolTip(
            "Pass --verbose to odin4 so the console shows detailed per-partition\n"
            "progress - useful for diagnosing stuck flashes."
        )
        self.verbose_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row2.addWidget(self.verbose_cb)
        opt_lay.addLayout(opt_row2)

        # Auto-reboot and re-download are mutually exclusive.
        self.auto_reboot_cb.toggled.connect(
            lambda on: self.redownload_cb.setChecked(False) if on else None
        )
        self.redownload_cb.toggled.connect(
            lambda on: self.auto_reboot_cb.setChecked(False) if on else None
        )

        # BL downgrade override row (native multi-partition flash gate)
        opt_row3 = FlowLayout(spacing=8)
        self.force_bl_cb = QCheckBox("Allow BL revision downgrade (ODIN4_FORCE_BL=1)")
        self.force_bl_cb.setChecked(False)
        self.force_bl_cb.setToolTip(
            "OFF by default (safety). Lets the native multi-partition flash write a\n"
            "bootloader whose revision is LOWER than the device's current one.\n"
            "Flashing a lower BL revision on a newer device can hard-brick it - only\n"
            "enable when you are certain the older firmware is correct for this device."
        )
        self.force_bl_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row3.addWidget(self.force_bl_cb)
        opt_lay.addLayout(opt_row3)

        # vbmeta auto-patch toggle
        opt_row4 = FlowLayout(spacing=8)
        self.vbmeta_patch_cb = QCheckBox("Auto-patch vbmeta (disable AVB verification)")
        self.vbmeta_patch_cb.setChecked(True)
        self.vbmeta_patch_cb.setToolTip(
            "When ON, extracts vbmeta from AP firmware, patches it to disable\n"
            "AVB verification (flags 0x03), and flashes the patched vbmeta.\n"
            "Required for booting custom kernels / unofficial firmware."
        )
        self.vbmeta_patch_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        opt_row4.addWidget(self.vbmeta_patch_cb)
        opt_lay.addLayout(opt_row4)

        # --- Zone 3: Advanced single-partition + native flash (circuit-deck) ---
        self.adv_panel = QFrame()
        self.adv_panel.setObjectName("adv")
        self.adv_panel.setStyleSheet(
            f"QFrame#adv {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border']}; border-left: 2px solid {C['ok']};"
            f" border-top: 1px solid {C['border_hi']}; border-radius: 9px; }}"
        )
        a_lay = QVBoxLayout(self.adv_panel)
        a_lay.setContentsMargins(14, 10, 14, 14)
        a_lay.setSpacing(8)
        a_lay.addWidget(
            _risk_banner(
                "Advanced: these write directly to partitions. A wrong "
                "partition/image combo can soft-brick the device."
            )
        )

        self.partition_edit = QLineEdit()
        self.partition_edit.setPlaceholderText("e.g. vbmeta, boot, super, system ...")
        self.partition_edit.setMinimumWidth(80)
        self.partition_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.partition_edit.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")

        self.image_edit = QLineEdit()
        self.image_edit.setPlaceholderText("Image file (.img / .lz4 / .tar)")
        self.image_edit.setMinimumWidth(80)
        self.image_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.image_edit.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")

        self.sales_code_edit = QLineEdit()
        self.sales_code_edit.setPlaceholderText("e.g. XSG")
        self.sales_code_edit.setMinimumWidth(80)
        self.sales_code_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.sales_code_edit.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")

        self.flash_specs_edit = QLineEdit()
        self.flash_specs_edit.setPlaceholderText("partition=image;partition=image")
        self.flash_specs_edit.setMinimumWidth(80)
        self.flash_specs_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.flash_specs_edit.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")

        self.pit_file_edit = QLineEdit()
        self.pit_file_edit.setPlaceholderText("Path to .pit")
        self.pit_file_edit.setMinimumWidth(80)
        self.pit_file_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.pit_file_edit.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")

        def _adv_run(method, label, tooltip):
            btn = QPushButton(label)
            btn.setStyleSheet(_btn_ghost())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.clicked.connect(
                lambda _=False, m=method, n=label: self._confirm_flash_action(
                    n, m,
                    "This writes data to your device. DO NOT unplug it until "
                    "the operation finishes.",
                )
            )
            return btn

        # single partition + image -> one row
        p_row = QHBoxLayout()
        p_label = QLabel("Single")
        p_label.setStyleSheet(f"color: {C['accent_hi']}; font-weight: 800; min-width: 52px; font-size: 11px;")
        p_row.addWidget(p_label)
        p_row.addWidget(self.partition_edit, 1)
        p_row.addWidget(self.image_edit, 1)
        img_btn = QPushButton("Browse...")
        img_btn.setStyleSheet(_btn_ghost())
        img_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        img_btn.setFixedWidth(80)
        img_btn.clicked.connect(lambda: self._browse_slot(self.image_edit, "partition image"))
        p_row.addWidget(img_btn)
        p_run = _adv_run(
            "odin_flash_partition", "Flash",
            "Flash one partition (raw) with the partition name + image above"
        )
        p_run.setFixedWidth(64)
        p_row.addWidget(p_run)
        a_lay.addLayout(p_row)

        # sales code -> one row
        sc_row = QHBoxLayout()
        sc_label = QLabel("Sales Code")
        sc_label.setStyleSheet(f"color: {C['accent_hi']}; font-weight: 800; min-width: 70px; font-size: 11px;")
        sc_row.addWidget(sc_label)
        sc_row.addWidget(self.sales_code_edit, 1)
        sc_run = _adv_run(
            "odin_sales_code", "Apply",
            "Change the CSC / sales code on the device (needs a matching CSC archive)"
        )
        sc_run.setFixedWidth(64)
        sc_row.addWidget(sc_run)
        a_lay.addLayout(sc_row)

        # multi-partition specs -> one row
        ms_row = QHBoxLayout()
        ms_label = QLabel("Flash specs")
        ms_label.setStyleSheet(f"color: {C['accent_hi']}; font-weight: 800; min-width: 70px; font-size: 11px;")
        ms_row.addWidget(ms_label)
        ms_row.addWidget(self.flash_specs_edit, 1)
        ms_run = _adv_run(
            "odin_flash_multi", "Flash",
            "Flash multiple partitions from partition=image;partition=image specs"
        )
        ms_run.setFixedWidth(64)
        ms_row.addWidget(ms_run)
        a_lay.addLayout(ms_row)

# pit -> one row
        pit_row = QHBoxLayout()
        pit_label = QLabel("PIT file")
        pit_label.setStyleSheet(f"color: {C['accent_hi']}; font-weight: 800; min-width: 70px; font-size: 11px;")
        pit_row.addWidget(pit_label)
        pit_row.addWidget(self.pit_file_edit, 1)
        pit_btn = QPushButton("Browse...")
        pit_btn.setStyleSheet(_btn_ghost())
        pit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pit_btn.setFixedWidth(80)
        pit_btn.clicked.connect(lambda: self._browse_slot(self.pit_file_edit, "pit"))
        pit_run = _adv_run(
            "odin_send_pit", "Send",
            "Send the PIT to the device (repartition)"
        )
        pit_run.setFixedWidth(64)
        pit_row.addWidget(pit_run)
        a_lay.addLayout(pit_row)

        # vbmeta -> one row
        vb_row = QHBoxLayout()
        vb_label = QLabel("vbmeta")
        vb_label.setStyleSheet(f"color: {C['accent_hi']}; font-weight: 800; min-width: 70px; font-size: 11px;")
        vb_row.addWidget(vb_label)
        self.vbmeta_edit = QLineEdit()
        self.vbmeta_edit.setPlaceholderText("vbmeta image (.img / .img.lz4)")
        self.vbmeta_edit.setMinimumWidth(80)
        self.vbmeta_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.vbmeta_edit.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")
        vb_row.addWidget(self.vbmeta_edit, 1)
        vb_img_btn = QPushButton("Browse...")
        vb_img_btn.setStyleSheet(_btn_ghost())
        vb_img_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        vb_img_btn.setFixedWidth(80)
        vb_img_btn.clicked.connect(lambda: self._browse_slot(self.vbmeta_edit, "vbmeta image"))
        vb_row.addWidget(vb_img_btn)
        vb_run = _adv_run(
            "odin_flash_partition", "Flash vbmeta",
            "Flash vbmeta partition (use pre-modified image to disable verification)"
        )
        vb_run.setFixedWidth(64)
        vb_row.addWidget(vb_run)
        a_lay.addLayout(vb_row)

    def _build_console(self):
        """Shared console/log panel shown on the right side of every section."""
        panel = QFrame()
        panel.setObjectName("console")
        panel.setStyleSheet(
            f"QFrame#console {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 rgba(13, 20, 31, 230), stop:1 rgba(6, 10, 16, 235));"
            f" border: 1px solid {C['border']}; border-left: 2px solid {C['accent']};"
            f" border-radius: 9px; }}"
            f" QFrame#console:hover {{ border: 1px solid {C['border_hi']};"
            f" background: rgba(15, 23, 35, 235); }}"
        )
        panel.setMinimumWidth(360)
        panel.setMaximumWidth(430)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        # ---- advanced console toolbar ----
        console_row = QHBoxLayout()
        console_row.setSpacing(8)
        console_row.addWidget(SectionTitle("CONSOLE"))

        self.console_count = QLabel("0 lines")
        self.console_count.setStyleSheet(
            f"color:{C['mute']}; font-size:10px; font-weight:600; letter-spacing:1px;"
            f" font-family:'JetBrains Mono','Consolas',monospace;"
        )
        console_row.addWidget(self.console_count)
        console_row.addStretch(1)

        self.wrap_btn = self._tool_button("Wrap", self._toggle_wrap)
        console_row.addWidget(self.wrap_btn)
        self.clear_btn = self._tool_button("Clear", self._clear_console)
        self.clear_btn.setToolTip("Clear console (Ctrl+L)")
        console_row.addWidget(self.clear_btn)
        self.copy_btn = self._tool_button("Copy", self._copy_console)
        self.copy_btn.setToolTip("Copy console to clipboard (Ctrl+Shift+C)")
        console_row.addWidget(self.copy_btn)
        self.save_btn = self._tool_button("Save", self._save_console)
        self.save_btn.setToolTip("Save console to a text file (Ctrl+S)")
        console_row.addWidget(self.save_btn)
        lay.addLayout(console_row)

        # find + filter rows (two compact rows to fit the narrow console column)
        find_row = QHBoxLayout()
        find_row.setSpacing(6)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Find in console...  (Ctrl+F)")
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.textChanged.connect(self._apply_find)
        self.find_edit.setStyleSheet(
            f"QLineEdit {{ background:{C['card']}; border:1px solid {C['border']};"
            f" border-radius:6px; padding:5px 10px; color:{C['text']};"
            f" selection-background-color:{C['accent']}; }}"
            f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
            f" QLineEdit:focus {{ border:1px solid {C['accent']}; }}"
        )
        find_row.addWidget(self.find_edit, 1)
        self.find_next_btn = self._tool_button("N", lambda: self._find_nav(1))
        self.find_prev_btn = self._tool_button("P", lambda: self._find_nav(-1))
        find_row.addWidget(self.find_next_btn)
        find_row.addWidget(self.find_prev_btn)

        flt_row = QHBoxLayout()
        flt_row.setSpacing(6)

        self._filter_btns = {}
        for level, label, color in (
            ("err", "Err", C["err"]),
            ("warn", "Warn", C["warn"]),
            ("ok", "OK", C["ok"]),
            ("info", "Info", C["dim"]),
        ):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(46)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border:1px solid {C['border']};"
                f" border-radius:8px; padding:4px 6px; font-size:10px; font-weight:700;"
                f" color:{color}; }}"
                f" QPushButton:checked {{ background: {color}; color: #0b0f14; }}"
            )
            btn.toggled.connect(
                lambda checked, lv=level: self._set_filter(lv, checked)
            )
            self._filter_btns[level] = btn
            flt_row.addWidget(btn)

        self.clear_on_run = QCheckBox("auto-clear on run")
        self.clear_on_run.setChecked(
            self.settings.value("clear_on_run", "false", type=bool)
        )
        self.clear_on_run.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        flt_row.addWidget(self.clear_on_run)
        flt_row.addStretch(1)
        lay.addLayout(find_row)
        lay.addLayout(flt_row)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(4000)
        self.log.setMinimumHeight(120)
        self.log.setPlainText("Ready. Connect a device to begin.")
        self.log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(self.log, 1)

        # footer: shortcut hints (collapsed into a single line for the narrow
        # right-hand console column)
        footer = QFrame()
        footer.setObjectName("footer")
        footer.setStyleSheet(
            f"QFrame#footer {{ background:{C['inset']};"
            f" border:1px solid {C['border']}; border-radius:9px; }}"
        )
        f_lay = QVBoxLayout(footer)
        f_lay.setContentsMargins(10, 6, 10, 6)
        f_lay.setSpacing(6)
        self.version_lbl = QLabel("flashpilot FLASHING TOOL v1.2")
        self.version_lbl.setStyleSheet(
            f"color:{C['mute']}; font-size:9px; font-weight:700; letter-spacing:1px;"
        )
        f_lay.addWidget(self.version_lbl)
        for k in ("F5 refresh", "Ctrl+Enter run", "Ctrl+L clear", "Ctrl+S save"):
            chip = QLabel(k)
            chip.setStyleSheet(
                f"color:{C['dim']}; font-size:9px; font-weight:600;"
                f" background:{C['card_hover']}; border:1px solid {C['border']};"
                f" border-radius:6px; padding:2px 7px;"
            )
            f_lay.addWidget(chip)
        lay.addWidget(footer)

        return panel

    # ----------------------------- section switching ----------------------
    def _on_section(self, key):
        order = {"samsung": 0, "quick": 1, "fus": 2, "mtk": 3, "qc": 4, "spd": 5,
                 "battery": 6, "network": 7, "settings": 8}
        idx = order.get(key, 0)
        self._stack.setCurrentIndex(idx)
        self.nav.select(key)
        self.set_status(f"Section: {key.upper()}")

    # ----------------------------- Firmware Downloader page --------------
    def _build_fus_page(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(_card_qss())
        panel_lay = QVBoxLayout(panel)
        panel_lay.setContentsMargins(0, 0, 0, 0)
        panel_lay.setSpacing(0)
        page_scroll = self._ops_scroll_area()
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(host)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        lay.addWidget(SectionTitle("SAMSUNG OFFICIAL FIRMWARE DOWNLOADER (SAMFIRM / FUS)"))
        info = QLabel(
            "Direct FUS client to query Samsung servers, check latest firmware versions, "
            "download encrypted firmware packages in parallel, and auto-decrypt them into "
            "ready-to-flash .tar.md5 archives."
        )
        info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        form_card = QFrame()
        form_card.setStyleSheet(
            f"QFrame {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 12px; }}"
        )
        form_lay = QVBoxLayout(form_card)
        form_lay.setSpacing(10)

        # Model row
        r1 = QHBoxLayout()
        lbl1 = QLabel("Device Model:")
        lbl1.setStyleSheet(f"color:{C['text']}; font-weight:600;")
        r1.addWidget(lbl1)
        self.fus_model_input = QLineEdit("SM-S918B")
        self.fus_model_input.setStyleSheet(f"background:{C['panel']}; color:{C['text']}; border:1px solid {C['border']}; border-radius:6px; padding:6px;")
        r1.addWidget(self.fus_model_input, 1)

        self.fus_detect_btn = QPushButton("🔍 Detect Connected Device")
        self.fus_detect_btn.setStyleSheet(_btn_ghost())
        self.fus_detect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fus_detect_btn.clicked.connect(self._fus_detect_device)
        r1.addWidget(self.fus_detect_btn)
        
        lbl_reg = QLabel("Region:")
        lbl_reg.setStyleSheet(f"color:{C['text']}; font-weight:600;")
        r1.addWidget(lbl_reg)
        self.fus_region_input = QLineEdit("EUX")
        self.fus_region_input.setStyleSheet(f"background:{C['panel']}; color:{C['text']}; border:1px solid {C['border']}; border-radius:6px; padding:6px;")
        self.fus_region_input.setMaximumWidth(100)
        r1.addWidget(self.fus_region_input)
        form_lay.addLayout(r1)

        # Version row
        r2 = QHBoxLayout()
        lbl2 = QLabel("Firmware Version:")
        lbl2.setStyleSheet(f"color:{C['text']}; font-weight:600;")
        r2.addWidget(lbl2)
        self.fus_version_input = QLineEdit()
        self.fus_version_input.setPlaceholderText("e.g. S918BXXU3BWCV/S918BOXM3BWCV/S918BXXU3BWCV (or click Check Version)")
        self.fus_version_input.setStyleSheet(f"background:{C['panel']}; color:{C['text']}; border:1px solid {C['border']}; border-radius:6px; padding:6px;")
        r2.addWidget(self.fus_version_input, 1)

        self.fus_check_btn = QPushButton("Check Version")
        self.fus_check_btn.setStyleSheet(_btn_primary())
        self.fus_check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fus_check_btn.clicked.connect(self._fus_check_version)
        r2.addWidget(self.fus_check_btn)
        form_lay.addLayout(r2)

        # Output dir row
        r3 = QHBoxLayout()
        lbl3 = QLabel("Output Directory:")
        lbl3.setStyleSheet(f"color:{C['text']}; font-weight:600;")
        r3.addWidget(lbl3)
        self.fus_out_input = QLineEdit(os.path.expanduser("~/brilliant/cache"))
        self.fus_out_input.setStyleSheet(f"background:{C['panel']}; color:{C['text']}; border:1px solid {C['border']}; border-radius:6px; padding:6px;")
        r3.addWidget(self.fus_out_input, 1)
        form_lay.addLayout(r3)

        lay.addWidget(form_card)

        # Actions row
        act_row = QHBoxLayout()
        self.fus_download_btn = QPushButton("⬇ Download & Decrypt Firmware")
        self.fus_download_btn.setStyleSheet(_btn_primary())
        self.fus_download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fus_download_btn.setFixedHeight(38)
        self.fus_download_btn.clicked.connect(self._fus_download)
        act_row.addWidget(self.fus_download_btn)

        self.fus_load_ap_btn = QPushButton("📂 Load into AP Slot")
        self.fus_load_ap_btn.setStyleSheet(_btn_ghost())
        self.fus_load_ap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fus_load_ap_btn.setFixedHeight(38)
        self.fus_load_ap_btn.clicked.connect(self._fus_load_into_ap)
        act_row.addWidget(self.fus_load_ap_btn)
        lay.addLayout(act_row)

        # Progress bar
        self.fus_progress = QProgressBar()
        self.fus_progress.setRange(0, 100)
        self.fus_progress.setValue(0)
        self.fus_progress.setStyleSheet(f"QProgressBar {{ background:{C['inset']}; border:1px solid {C['border']}; border-radius:5px; text-align:center; color:{C['text']}; }} QProgressBar::chunk {{ background:{C['accent']}; border-radius:4px; }}")
        lay.addWidget(self.fus_progress)

        # Status label
        self.fus_status_lbl = QLabel("Ready.")
        self.fus_status_lbl.setStyleSheet(f"color:{C['dim']}; font-size:12px; font-weight:600;")
        lay.addWidget(self.fus_status_lbl)

        # Other brand resources card
        res_card = QFrame()
        res_card.setStyleSheet(
            f"QFrame {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 12px; }}"
        )
        res_lay = QVBoxLayout(res_card)
        res_lay.setSpacing(6)
        
        res_title = QLabel("🌐 Other Brand Firmware & Loader Repositories (Reference)")
        res_title.setStyleSheet(f"color:{C['text']}; font-weight:700; font-size:12px;")
        res_lay.addWidget(res_title)

        res_info = QLabel(
            "• <b>MediaTek (MTK) Scatter / DA:</b> Check Hovatek & Needrom for scatter files and signed Download Agents.<br>"
            "• <b>Qualcomm EDL Firehose:</b> Use <i>bkerler/Firehose</i> on GitHub for open EDL programmer loaders.<br>"
            "• <b>UNISOC / Spreadtrum (SPD):</b> Stock PAC firmwares contain FDL1/FDL2 binaries required for BSL flashing."
        )
        res_info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        res_info.setWordWrap(True)
        res_lay.addWidget(res_info)
        lay.addWidget(res_card)

        host.setLayout(lay)
        page_scroll.setWidget(host)
        panel_lay.addWidget(page_scroll)
        return panel

    def _fus_detect_device(self):
        self.fus_status_lbl.setText("Scanning connected Samsung device...")
        def work():
            try:
                devs = bridge.adb_devices()
                if not devs:
                    raise RuntimeError("No ADB device authorized/connected. Please connect phone in normal/ADB mode.")
                model = bridge.adb_shell("getprop ro.product.model", timeout=5).strip()
                csc = bridge.adb_shell("getprop ro.boot.hardware.ods.csc", timeout=5).strip()
                if not csc:
                    csc = bridge.adb_shell("getprop persist.sys.sales_code", timeout=5).strip()
                if not csc:
                    csc = bridge.adb_shell("getprop ro.csc.sales_code", timeout=5).strip()
                if not model:
                    model = "SM-S918B"
                if not csc:
                    csc = "EUX"

                def ok():
                    self.fus_model_input.setText(model)
                    self.fus_region_input.setText(csc)
                    self.fus_status_lbl.setText(f"Detected connected device: {model} ({csc})")
                    self.show_toast(f"Detected {model} [{csc}]", "success")
                    self._fus_check_version()
                QMetaObject.invokeMethod(self, ok, Qt.ConnectionType.QueuedConnection)
            except Exception as e:
                err = str(e)
                def fail():
                    self.fus_status_lbl.setText(f"Detection failed: {err}")
                    self.show_toast(f"Device detection failed: {err}", "error")
                QMetaObject.invokeMethod(self, fail, Qt.ConnectionType.QueuedConnection)

        threading.Thread(target=work, daemon=True).start()

    def _fus_check_version(self):
        model = self.fus_model_input.text().strip()
        region = self.fus_region_input.text().strip()
        if not model or not region:
            self.show_toast("Enter device model and region first.", "error")
            return
        self.fus_check_btn.setEnabled(False)
        self.fus_status_lbl.setText(f"Checking latest version for {model} ({region})...")

        def work():
            try:
                ver = fus.check_latest_version(model, region)
                def ok():
                    self.fus_version_input.setText(ver)
                    self.fus_status_lbl.setText(f"Latest version found: {ver}")
                    self.fus_check_btn.setEnabled(True)
                    self.show_toast(f"Latest firmware: {ver}", "success")
                QMetaObject.invokeMethod(self, ok, Qt.ConnectionType.QueuedConnection)
            except Exception as e:
                err = str(e)
                def fail():
                    self.fus_status_lbl.setText(f"Check failed: {err}")
                    self.fus_check_btn.setEnabled(True)
                    self.show_toast(f"Check failed: {err}", "error")
                QMetaObject.invokeMethod(self, fail, Qt.ConnectionType.QueuedConnection)

        threading.Thread(target=work, daemon=True).start()

    def _fus_download(self):
        model = self.fus_model_input.text().strip()
        region = self.fus_region_input.text().strip()
        fw_ver = self.fus_version_input.text().strip()
        out_dir = self.fus_out_input.text().strip()
        if not model or not region or not fw_ver:
            self.show_toast("Model, Region, and Firmware Version are required.", "error")
            return
        if not _flow_start("Firmware Downloader", destructive=False):
            self.show_toast(_flow_busy_msg(), "warning")
            return

        self.fus_download_btn.setEnabled(False)
        self.fus_progress.setValue(0)
        self.fus_status_lbl.setText("Starting download and decryption...")
        self._append_console(f"[fus] Starting download for {model} {fw_ver}...")

        def progress_cb(downloaded, total):
            if total > 0:
                pct = int((downloaded * 100) / total)
                def upd():
                    self.fus_progress.setValue(pct)
                    self.fus_status_lbl.setText(f"Downloading... {downloaded/(1024*1024):.1f} MB / {total/(1024*1024):.1f} MB ({pct}%)")
                QMetaObject.invokeMethod(self, upd, Qt.ConnectionType.QueuedConnection)

        def log_cb(msg):
            def l():
                self._append_console(f"[fus] {msg}")
            QMetaObject.invokeMethod(self, l, Qt.ConnectionType.QueuedConnection)

        def work():
            try:
                dec_file = fus.download_and_decrypt_firmware(
                    model, region, fw_ver, out_dir,
                    progress_callback=progress_cb,
                    log_callback=log_cb
                )
                def done():
                    self.fus_download_btn.setEnabled(True)
                    self.fus_progress.setValue(100)
                    self.fus_status_lbl.setText(f"Success! Decrypted file: {dec_file}")
                    self._append_console(f"[fus] Complete! Saved to {dec_file}")
                    self.show_toast("Firmware downloaded & decrypted successfully!", "success")
                    self._last_decrypted_fw = dec_file
                    _flow_end()
                QMetaObject.invokeMethod(self, done, Qt.ConnectionType.QueuedConnection)
            except Exception as e:
                err = str(e)
                def fail():
                    self.fus_download_btn.setEnabled(True)
                    self.fus_status_lbl.setText(f"Download/Decrypt failed: {err}")
                    self._append_console(f"[fus] ERROR: {err}")
                    self.show_toast(f"Download failed: {err}", "error")
                    _flow_end()
                QMetaObject.invokeMethod(self, fail, Qt.ConnectionType.QueuedConnection)

        threading.Thread(target=work, daemon=True).start()

    def _fus_load_into_ap(self):
        fw = getattr(self, "_last_decrypted_fw", None)
        if not fw or not os.path.exists(fw):
            self.show_toast("No downloaded firmware found to load.", "warning")
            return
        # Populate AP path in Samsung tab if available
        if hasattr(self, "ap_input"):
            self.ap_input.setText(fw)
            self.show_toast("Loaded decrypted firmware into AP slot!", "success")
            self._on_section("samsung")
        else:
            self.show_toast(f"Firmware ready at: {fw}", "info")

    # ----------------------------- MTK Tools page -------------------------
    def _build_mtk_page(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(
            _card_qss()
        )
        panel_lay = QVBoxLayout(panel)
        panel_lay.setContentsMargins(0, 0, 0, 0)
        panel_lay.setSpacing(0)
        page_scroll = self._ops_scroll_area()
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(host)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(9)

        lay.addWidget(SectionTitle("MEDIATEK LOW-LEVEL TOOLING"))
        info = QLabel(
            "MediaTek BROM / Preloader / DA tooling (VID 0e8d). Needs a matching "
            "DA + scatter file from the device's firmware."
        )
        info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        detect_row = QHBoxLayout()
        self.mtk_detect_btn = QPushButton("Detect MediaTek")
        self.mtk_detect_btn.setStyleSheet(_btn_primary())
        self.mtk_detect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mtk_detect_btn.clicked.connect(self._mtk_detect)
        detect_row.addWidget(self.mtk_detect_btn)
        self.mtk_status = QLabel("No MediaTek device detected")
        self.mtk_status.setStyleSheet(f"color:{C['dim']}; font-size:12px;")
        detect_row.addWidget(self.mtk_status, 1)
        lay.addLayout(detect_row)

        # file rows: scatter + DA
        self.mtk_files = {}
        for name, lbl, flt in (
            ("scatter", "Scatter file", "Scatter (*.txt);;All files (*)"),
            ("da", "DA binary", "DA (*.bin);;All files (*)"),
        ):
            row = QHBoxLayout()
            lab = QLabel(lbl)
            lab.setStyleSheet(f"color:{C['dim']}; font-weight:600; min-width:90px;")
            edit = QLineEdit()
            edit.setPlaceholderText(f"Select {lbl.lower()}...")
            edit.setStyleSheet(
                f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
                f" border-radius:8px; padding:6px 10px; color:{C['text']};"
                f" selection-background-color:{C['accent']}; }}"
                f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
                f" QLineEdit:focus {{ border:1px solid {C['accent']}; }}"
            )
            btn = QPushButton("Browse...")
            btn.setStyleSheet(_btn_ghost())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(90)
            btn.clicked.connect(
                lambda _=False, e=edit, n=name, f=flt: self._mtk_browse(e, n, f)
            )
            row.addWidget(lab)
            row.addWidget(edit, 1)
            row.addWidget(btn)
            lay.addLayout(row)
            self.mtk_files[name] = edit

        # Auth bypass toggle (da_auth_bypass mode)
        auth_row = QHBoxLayout()
        self.mtk_auth_bypass_cb = QCheckBox("Auth bypass (da_auth_bypass mode)")
        self.mtk_auth_bypass_cb.setChecked(False)
        self.mtk_auth_bypass_cb.setToolTip(
            "When ON, uses 'da_auth_bypass' mode to skip preloader auth checks.\n"
            "Required for some secured devices where standard DA auth fails.\n"
            "WARNING: May not work on all chips; can brick if used incorrectly."
        )
        self.mtk_auth_bypass_cb.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        auth_row.addWidget(self.mtk_auth_bypass_cb)
        auth_row.addStretch(1)
        lay.addLayout(auth_row)

        # Generate a scatter file straight from the device GPT (Samsung
        # firmware ships no scatter; this rebuilds one from the phone).
        gen_row = QHBoxLayout()
        gen_btn = QPushButton("Generate Scatter (from device GPT)")
        gen_btn.setStyleSheet(_btn_ghost())
        gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gen_btn.setToolTip(
            "Read the device's own GPT partition table and write an SP Flash\n"
            "Tool scatter file. Samsung firmware never includes a scatter file,\n"
            "so this rebuilds one from the phone. Large data partitions are\n"
            "marked non-downloadable. Needs the DA binary + BROM/preloader."
        )
        gen_btn.clicked.connect(self._mtk_gen_scatter)
        gen_row.addWidget(gen_btn)
        da_btn = QPushButton("Dump & Patch Preloader (build DA from phone)")
        da_btn.setStyleSheet(_btn_ghost())
        da_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        da_btn.setToolTip(
            "Dump the phone's own preloader and patch its security checks -\n"
            "the result IS a working Download Agent for this device. This is\n"
            "how you get a DA without downloading one: the phone provides it.\n"
            "The patched file is saved to ~/Downloads/preloader_patched.bin\n"
            "and auto-selected as the DA binary. Needs the phone in BROM."
        )
        da_btn.clicked.connect(self._mtk_dump_preloader)
        gen_row.addWidget(da_btn)
        gen_row.addStretch(1)
        lay.addLayout(gen_row)

        # action buttons (two compact rows like the QC page)
        acts = QVBoxLayout()
        acts.setSpacing(8)
        acts_row1 = QHBoxLayout()
        acts_row1.setSpacing(10)
        for label, slot in (
            ("Flash Firmware", self._mtk_flash),
            ("Backup Partitions", self._mtk_backup),
            ("Get Device Info", self._mtk_info),
        ):
            b = QPushButton(label)
            b.setStyleSheet(_btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            acts_row1.addWidget(b)
        acts_row1.addStretch(1)
        acts.addLayout(acts_row1)
        acts_row2 = QHBoxLayout()
        acts_row2.setSpacing(10)
        for label, slot in (
            ("FRP Bypass", self._mtk_frp),
            ("Enable ADB", self._mtk_adb),
            ("List Partitions", self._mtk_list_parts),
        ):
            b = QPushButton(label)
            b.setStyleSheet(_btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            acts_row2.addWidget(b)
        acts_row2.addStretch(1)
        self.mtk_stop_btn = QPushButton("Stop")
        self.mtk_stop_btn.setEnabled(False)
        self.mtk_stop_btn.setStyleSheet(_btn_danger())
        self.mtk_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mtk_stop_btn.clicked.connect(self._mtk_stop)
        self.mtk_stop_btn.setToolTip("Cancel the running MTK operation")
        acts_row2.addWidget(self.mtk_stop_btn)
        acts.addLayout(acts_row2)
        acts_row3 = QHBoxLayout()
        acts_row3.setSpacing(10)
        self.mtk_flash_part_btn = QPushButton("Flash Partition (No Scatter)")
        self.mtk_flash_part_btn.setStyleSheet(_btn_ghost())
        self.mtk_flash_part_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mtk_flash_part_btn.setToolTip(
            "Write one or more partitions by NAME, resolving addresses from "
            "the device GPT. No scatter file required."
        )
        self.mtk_flash_part_btn.clicked.connect(self._mtk_flash_part)
        acts_row3.addWidget(self.mtk_flash_part_btn)
        frp_gpt_btn = QPushButton("FRP Bypass (No Scatter)")
        frp_gpt_btn.setStyleSheet(_btn_ghost())
        frp_gpt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        frp_gpt_btn.setToolTip(
            "Clear lock/FRP partitions by NAME from the device GPT. "
            "No scatter file required."
        )
        frp_gpt_btn.clicked.connect(self._mtk_frp_gpt)
        acts_row3.addWidget(frp_gpt_btn)
        acts_row3.addStretch(1)
        acts.addLayout(acts_row3)
        lay.addLayout(acts)

        self.mtk_fw_dir = QLineEdit()
        self.mtk_fw_dir.setPlaceholderText("Firmware directory (partition images)...")
        self.mtk_fw_dir.setStyleSheet(
            f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:6px 10px; color:{C['text']};"
            f" selection-background-color:{C['accent']}; }}"
            f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
            f" QLineEdit:focus {{ border:1px solid {C['accent']}; }}"
        )
        fw_row = QHBoxLayout()
        fw_row.addWidget(QLabel("Firmware dir"), 0)
        fw_row.addWidget(self.mtk_fw_dir, 1)
        fw_btn = QPushButton("Browse...")
        fw_btn.setStyleSheet(_btn_ghost())
        fw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fw_btn.clicked.connect(self._mtk_browse_dir)
        fw_btn.setFixedWidth(90)
        fw_row.addWidget(fw_btn)
        lay.addLayout(fw_row)
        lay.addWidget(
            _risk_banner(
                "MTK flashing and FRP bypass write directly to the chip. "
                "Ensure the DA and scatter match your exact model - a wrong "
                "DA can hard-brick the device."
            )
        )

        self.mtk_progress = QProgressBar()
        self.mtk_progress.setRange(0, 1000)
        self.mtk_progress.setValue(0)
        self.mtk_progress.setTextVisible(False)
        self.mtk_progress.setFixedHeight(8)
        self.mtk_progress.setStyleSheet(
            f"QProgressBar {{ background:{C['inset']}; border:none; border-radius:4px; }}"
            f" QProgressBar::chunk {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f" stop:0 {C['grad_a']}, stop:1 {C['grad_b']}); border-radius:4px; }}"
        )
        self.mtk_progress.setVisible(False)
        mtk_ops = self._build_chip_ops_section(
            "mtk",
            {"MTK", "MTK BROM", "ADB", "MTP", "FASTBOOT"},
            self.mtk_stop_btn, self.mtk_progress, self._mtk_reset_ui,
        )
        lay.addWidget(mtk_ops, 1)
        lay.addWidget(self.mtk_progress)
        page_scroll.setWidget(host)
        panel_lay.addWidget(page_scroll)
        return panel

    def _mtk_browse(self, edit, name, name_filter):
        path, _ = QFileDialog.getOpenFileName(self, f"Select {name}", os.path.expanduser("~/Downloads"), name_filter)
        if path:
            edit.setText(path)

    def _mtk_browse_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select firmware directory", os.path.expanduser("~/Downloads")
        )
        if d:
            self.mtk_fw_dir.setText(d)

    def _mtk_run(self, args, timeout=600):
        if not _flow_start(f"MTK {args[0]}", destructive=True):
            self._ui.status.emit("Busy: " + _flow_busy_msg())
            self._ui.toast.emit("warn", "Operation already running", _flow_busy_msg())
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg()}")
            return

        def work():
            try:
                out = bridge._run(args, timeout=timeout)
                self._ui.line.emit(out or "(no output)")
                self._ui.status.emit(f"MTK: {args[0]} done")
                self._ui.toast.emit("ok", f"MTK {args[0]}", "Completed successfully")
            except bridge.BridgeCancelled:
                self._ui.line.emit("[cancelled] MTK operation stopped by user")
                self._ui.status.emit("MTK: operation cancelled")
                self._ui.toast.emit("warn", "MTK operation", "Cancelled")
            except bridge.BridgeError as e:
                self._ui.line.emit(f"[error] MTK {args[0]}: {e}")
                self._ui.status.emit(f"MTK: {args[0]} failed")
                self._ui.toast.emit("error", f"MTK {args[0]}", str(e))
            finally:
                _flow_end()
                bridge.clear_cancel()
                self._ui.ui.emit(self._mtk_reset_ui)

        bridge.clear_cancel()
        self.mtk_stop_btn.setEnabled(True)
        self.mtk_progress.setVisible(True)
        self.mtk_progress.setValue(150)
        threading.Thread(target=work, daemon=True).start()

    def _mtk_reset_ui(self):
        self.mtk_stop_btn.setEnabled(False)
        self.mtk_progress.setValue(1000)
        QTimer.singleShot(400, lambda: self.mtk_progress.setVisible(False))

    def _mtk_stop(self):
        bridge.request_cancel()
        frp.request_cancel()
        self._ui.status.emit("MTK: stopping ...")
        self._ui.line.emit("[warn] MTK: stop requested, killing bridge ...")

    def _mtk_detect(self):
        self.mtk_status.setText("Scanning USB...")

        def work():
            try:
                devs = bridge.detect_mtk()
                if not devs:
                    self._ui.ui.emit(lambda: self.mtk_status.setText(
                        "No MediaTek device detected"))
                    self._ui.line.emit("[info] mtk-detect: no MediaTek device found")
                    return
                for d in devs:
                    pid = d.get("pid")
                    stage = mtk.pid_stage(pid)
                    name, note = mtk.stage_label(stage)
                    self._ui.line.emit(
                        f"MTK: 0e8d:{pid:04x} bus={d.get('bus')} addr={d.get('address')} - {name}"
                    )
                self._ui.ui.emit(lambda n=len(devs): self.mtk_status.setText(
                    f"{n} MediaTek device(s) found"))
            except bridge.BridgeError as e:
                self._ui.ui.emit(lambda err=e: self.mtk_status.setText(
                    f"Scan error: {err}"))
            except Exception as e:  # noqa: BLE001
                self._ui.ui.emit(lambda err=e: self.mtk_status.setText(
                    f"Scan error: {err}"))

        threading.Thread(target=work, daemon=True).start()

    def _mtk_dump_preloader(self):
        """Dump + patch the phone's own preloader into a working DA. This is
        how the tool gets a DA without downloading one: the phone provides it.
        Only needs the device in BROM/preloader - no DA, no scatter required
        up front. Handles a boot-looping phone: it WAITS for the preloader
        window and retries across cycles instead of failing instantly. The
        patched file is saved to ~/Downloads/preloader_patched.bin and
        auto-selected as the DA binary."""
        out = os.path.expanduser("~/Downloads/preloader_patched.bin")
        if not _flow_start("MTK preloader dump", destructive=True):
            self._ui.status.emit("Busy: " + _flow_busy_msg())
            self._ui.toast.emit("warn", "Operation already running", _flow_busy_msg())
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg()}")
            return
        self._ui.line.emit(
            "[step] MTK dump + patch preloader - waiting for the "
            "BROM/preloader window ..."
        )
        self._ui.status.emit("MTK: waiting for BROM/preloader ...")
        self.mtk_stop_btn.setEnabled(True)

        def work():
            deadline = _time.monotonic() + 240
            attempt = 0
            os.environ["MTK_PRELOADER_OUT"] = out
            try:
                while _time.monotonic() < deadline:
                    if frp.cancel_requested():
                        self._ui.line.emit("[cancelled] MTK preloader dump stopped")
                        return
                    d = None
                    stage = None
                    for x in mtk.find_mtk():
                        st = mtk.pid_stage(x.get("pid", 0))
                        if st in ("brom", "preloader"):
                            d = x
                            stage = st
                            break
                    if not d:
                        _time.sleep(0.7)
                        continue
                    target = f"{d.get('bus')}:{d.get('address')}"
                    attempt += 1
                    self._ui.line.emit(
                        f"  attempt {attempt}: 0e8d:{d.get('pid', 0):04x} "
                        f"({mtk.stage_label(stage)[0]}) - dumping ..."
                    )
                    try:
                        res = bridge._run(
                            ["mtk-exploit", target, "mtk_bypass"], timeout=120
                        )
                        self._ui.line.emit(res)
                    except bridge.BridgeError as e:
                        self._ui.line.emit(
                            f"  attempt {attempt} lost the device ({e}) - "
                            "waiting for the next window ..."
                        )
                        continue
                    if os.path.isfile(out) and os.path.getsize(out):
                        self._ui.ui.emit(lambda: self.mtk_files["da"].setText(out))
                        self._ui.status.emit("MTK: DA built from phone preloader")
                        self._ui.toast.emit(
                            "ok", "MTK DA", "Patched preloader saved + selected as DA"
                        )
                        return
                    self._ui.line.emit(
                        "  dump ran but produced no file - retrying next window ..."
                    )
                    _time.sleep(1)
                self._ui.line.emit(
                    "[error] MTK preloader: no successful dump within 240s"
                )
                self._ui.status.emit("MTK: preloader dump timed out")
            finally:
                os.environ.pop("MTK_PRELOADER_OUT", None)
                _flow_end()
                self._ui.ui.emit(self._mtk_reset_ui)

        threading.Thread(target=work, daemon=True).start()

    def _mtk_gen_scatter(self):
        """Generate an SP Flash Tool scatter file from the device's own GPT
        (Samsung firmware ships no scatter; this rebuilds one from the phone).
        Read-only, then auto-fills the scatter field so the scatter-based
        buttons (Backup Partitions / Flash Firmware / FRP Bypass / Enable ADB)
        work without hunting for a scatter file."""
        da = self.mtk_files["da"].text().strip()
        if not da:
            self._ui.line.emit("[warn] MTK: DA binary is required")
            self._toasts.show_warn("MTK files missing", "Select a DA binary")
            return
        out = os.path.join(
            os.path.expanduser("~/Downloads"),
            f"mtk_scatter_{_time.strftime('%Y%m%d_%H%M%S')}.txt",
        )
        self._ui.line.emit(f"[step] MTK generate scatter from device GPT: da={da}")
        self._ui.status.emit("MTK: reading device GPT ...")

        def work():
            try:
                res = bridge.mtk_scatter_gpt(da, out)
                self._ui.line.emit(res)
                self._ui.ui.emit(lambda: self.mtk_files["scatter"].setText(out))
                self._ui.status.emit("MTK: scatter generated from device GPT")
                self._ui.toast.emit("ok", "MTK scatter", "Generated from device GPT")
            except bridge.BridgeError as e:
                self._ui.line.emit(f"[error] MTK scatter: {e}")
                self._ui.status.emit("MTK: scatter generation failed")
                self._ui.toast.emit("error", "MTK scatter", str(e))
            except Exception as e:  # noqa: BLE001
                self._ui.line.emit(f"[error] MTK scatter: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _mtk_info(self):
        """Full MediaTek device info: merge the raw USB descriptor (from
        detect-all, which now includes manufacturer / product / serial /
        interfaces / endpoints) with the BROM/preloader chip report (from
        mtk-detect, which requires the device in a low-level boot stage)."""
        self.mtk_status.setText("Reading device info...")

        def work():
            try:
                all_devs = bridge.detect_all()
                mtk_usb = [d for d in all_devs if d.get("vid") == mtk.MTK_VID]
                devs = bridge.detect_mtk()
                if not mtk_usb:
                    self._ui.line.emit("[info] mtk-detect: no MediaTek device found")
                    self._ui.ui.emit(lambda: self.mtk_status.setText(
                        "No MediaTek device detected"))
                    return

                chip_by_bus_addr = {}
                for d in devs:
                    chip_by_bus_addr[(d.get("bus"), d.get("address"))] = d

                for d in mtk_usb:
                    pid = d.get("pid")
                    stage = mtk.pid_stage(pid)
                    name, note = mtk.stage_label(stage)
                    chipdev = chip_by_bus_addr.get((d.get("bus"), d.get("address")))
                    chip = (chipdev or {}).get("chip") if chipdev else d.get("chip")
                    lines = [
                        "=== MediaTek Device Info ===",
                    ]
                    lines.extend(_fmt_usb_full(d))
                    lines.append("")
                    lines.append(f"Stage:    {name} ({stage})")
                    if note:
                        lines.append(f"  {note}")
                    if chip:
                        lines.append("")
                        lines.append("--- Chip report ---")
                        chip_name = mtk.chip_name(chip.get("hw_code", 0))
                        lines.append(
                            f"HW code:  0x{chip.get('hw_code', 0):04X}  "
                            f"sub 0x{chip.get('hw_sub_code', 0):04X}  ({chip_name})"
                        )
                        lines.append(
                            f"HW ver:   {chip.get('hw_ver', 0)}   "
                            f"SW ver:   {chip.get('sw_ver', 0)}"
                        )
                        if chip.get("blver") is not None:
                            lines.append(f"BL ver:   {chip['blver']}")
                        if chip.get("bromver") is not None:
                            lines.append(f"BROM ver: {chip['bromver']}")
                        if chip.get("chip_id"):
                            lines.append(f"Chip ID:  {chip['chip_id']}")
                        if chip.get("socid"):
                            lines.append(f"SoC ID:   {chip['socid']}")
                        if chip.get("meid"):
                            lines.append(f"MEID:     {chip['meid']}")
                        if chip.get("is_brom"):
                            lines.append("Mode:     BootROM (BROM)")
                        else:
                            lines.append("Mode:     Preloader (Lk)")
                        tc = chip.get("target_config")
                        if tc:
                            lines.append("")
                            lines.append("--- Security / target config ---")
                            lines.append(
                                f"  raw 0x{tc.get('raw', 0):08X}   "
                                f"SBC {'on' if tc.get('sbc') else 'off'}   "
                                f"SLA {'on' if tc.get('sla') else 'off'}   "
                                f"DA-Auth {'on' if tc.get('daa') else 'off'}"
                            )
                            lines.append(
                                f"  SWJTAG {'on' if tc.get('swjtag') else 'off'}   "
                                f"EPP {'on' if tc.get('epp') else 'off'}   "
                                f"CERT {'on' if tc.get('cert') else 'off'}"
                            )
                            lines.append(
                                f"  MEM read {'on' if tc.get('memread') else 'off'}   "
                                f"MEM write {'on' if tc.get('memwrite') else 'off'}   "
                                f"CMD-C8 {'on' if tc.get('cmd_c8') else 'off'}"
                            )
                    else:
                        lines.append("")
                        if stage == "mtk-adb":
                            lines.append(
                                "Chip report: not available - phone is booted to "
                                "Android (ADB)."
                            )
                        else:
                            lines.append(
                                "Chip report: no BROM/preloader handshake yet - "
                                "put the phone into BROM/preloader mode."
                            )
                        lines.append(
                            "  How to reach BROM: power OFF, then hold Volume+ "
                            "(some models Volume-) while plugging the USB cable. "
                            "No battery removal needed."
                        )
                    self._ui.line.emit("\n".join(lines))
                self._ui.ui.emit(lambda n=len(mtk_usb): self.mtk_status.setText(
                    f"{n} MediaTek device(s) - info above"))
            except bridge.BridgeError as e:
                self._ui.line.emit(f"[error] MTK device info: {e}")
                self._ui.ui.emit(lambda err=e: self.mtk_status.setText(
                    f"Read error: {err}"))
            except Exception as e:  # noqa: BLE001
                self._ui.line.emit(f"[error] MTK device info: {e}")
                self._ui.ui.emit(lambda err=e: self.mtk_status.setText(
                    f"Read error: {err}"))

        threading.Thread(target=work, daemon=True).start()

    def _mtk_require_files(self):
        scatter = self.mtk_files["scatter"].text().strip()
        da = self.mtk_files["da"].text().strip()
        if not scatter or not da:
            self._ui.line.emit("[warn] MTK: scatter file and DA binary are both required")
            self._toasts.show_warn("MTK files missing", "Select a scatter file and DA binary")
            return None
        return scatter, da

    def _mtk_flash(self):
        files = self._mtk_require_files()
        if not files:
            return
        scatter, da = files
        fw = self.mtk_fw_dir.text().strip()
        if not fw:
            self._toasts.show_warn("Firmware dir missing", "Select the firmware directory")
            return
        self._ui.line.emit(f"[step] MTK flashing: scatter={scatter} da={da} fw={fw}")
        auth_bypass = self.mtk_auth_bypass_cb.isChecked()
        
        def run_flash():
            if auth_bypass:
                self._ui.line.emit("[step] Running auth bypass (da_auth_bypass)...")
                try:
                    self._mtk_run(["mtk-bypass", "auto", da, "da_auth_bypass", scatter, "1"], timeout=300)
                except Exception as e:
                    self._toasts.show_error("Auth bypass failed", str(e))
                    return
            self._mtk_run(["mtk-flash", "auto", da, scatter, fw], timeout=1800)
        
        self._confirm_overlay(
            "Flash Firmware (MTK)",
            "Write ALL firmware images from the selected directory to the "
            "connected MediaTek device, following the scatter file.\n\n"
            "This OVERWRITES the system, boot, vendor and modem partitions.\n"
            "If the firmware is wrong for this model, the device may not boot.\n\n"
            "There is NO undo. Continue?",
            confirm_label="Flash",
            on_confirm=run_flash,
        )

    def _mtk_backup(self):
        files = self._mtk_require_files()
        if not files:
            return
        scatter, da = files
        self._ui.line.emit(f"[step] MTK backup: scatter={scatter} da={da}")
        auth_bypass = self.mtk_auth_bypass_cb.isChecked()
        
        def run_backup():
            if auth_bypass:
                self._ui.line.emit("[step] Running auth bypass (da_auth_bypass)...")
                try:
                    self._mtk_run(["mtk-bypass", "auto", da, "da_auth_bypass", scatter, "1"], timeout=300)
                except Exception as e:
                    self._toasts.show_error("Auth bypass failed", str(e))
                    return
            self._mtk_run(["mtk-backup", "auto", da, scatter, "/tmp/mtk_backup"], timeout=1800)
        
        self._confirm_overlay(
            "Backup Partitions (MTK)",
            "Backup ALL partitions from the connected MediaTek device to /tmp/mtk_backup.\n\n"
            "This reads all partitions defined in the scatter file.\n\n"
            "Continue?",
            confirm_label="Backup",
            on_confirm=run_backup,
        )

    def _mtk_frp(self):
        files = self._mtk_require_files()
        if not files:
            return
        scatter, da = files
        self._ui.line.emit(f"[step] MTK FRP bypass: scatter={scatter} da={da}")
        auth_bypass = self.mtk_auth_bypass_cb.isChecked()
        
        def run_frp():
            if auth_bypass:
                self._ui.line.emit("[step] Running auth bypass (da_auth_bypass)...")
                try:
                    self._mtk_run(["mtk-bypass", "auto", da, "da_auth_bypass", scatter, "1"], timeout=300)
                except Exception as e:
                    self._toasts.show_error("Auth bypass failed", str(e))
                    return
            self._toasts.show_ok("MTK FRP bypass", "Clearing frp/nvdata...")
            self._mtk_run(["mtk-frp", "auto", da, scatter], timeout=1800)
        
        self._confirm_overlay(
            "FRP Bypass (MTK)",
            "Clear lock / FRP partitions by NAME, resolving addresses\n"
            "from the device GPT (no scatter file needed)?\n\n"
            "This formats or zero-fills frp, nvdata, metadata, persistent,\n"
            "protect1/2, and keystore partitions where present.\n"
            "User data may be erased. Continue?",
            confirm_label="Clear FRP",
            on_confirm=run_frp,
        )

    def _mtk_frp_gpt(self):
        da = self.mtk_files["da"].text().strip()
        if not da:
            self._ui.line.emit("[warn] MTK: DA binary is required")
            self._toasts.show_warn("MTK files missing", "Select a DA binary")
            return
        self._ui.line.emit("[step] MTK FRP bypass (GPT mode, no scatter): da={}".format(da))
        self._confirm_overlay(
            "FRP Bypass (No Scatter)",
            "Clear lock / FRP partitions by NAME, resolving addresses\n"
            "from the device GPT (no scatter file needed)?\n\n"
            "This formats or zero-fills frp, nvdata, metadata, persistent,\n"
            "protect1/2, and keystore partitions where present.\n"
            "User data may be erased. Continue?",
            confirm_label="Clear FRP",
            on_confirm=lambda: self._mtk_run(["mtk-frp-gpt", "auto", da], timeout=1800),
        )

    def _mtk_adb(self):
        files = self._mtk_require_files()
        if not files:
            return
        scatter, da = files
        self._ui.line.emit(f"[step] MTK ADB enable: scatter={scatter} da={da}")
        self._mtk_run(["mtk-adb-enable", "auto", da, scatter], timeout=1800)

    def _mtk_list_parts(self):
        da = self.mtk_files["da"].text().strip()
        if not da:
            self._ui.line.emit("[warn] MTK: DA binary is required")
            self._toasts.show_warn("MTK files missing", "Select a DA binary")
            return
        self._ui.line.emit(f"[step] MTK list partitions: da={da}")
        self._mtk_run(["mtk-gpt", "auto", da], timeout=300)

    def _mtk_flash_part(self):
        da = self.mtk_files["da"].text().strip()
        if not da:
            self._ui.line.emit("[warn] MTK: DA binary is required")
            self._toasts.show_warn("MTK files missing", "Select a DA binary")
            return
        fw = self.mtk_fw_dir.text().strip()
        if not fw:
            self._toasts.show_warn("Firmware dir missing", "Select the firmware directory")
            return
        import glob as _glob
        entries = []
        for img in sorted(_glob.glob(os.path.join(fw, "*.img")) +
                          _glob.glob(os.path.join(fw, "*.bin"))):
            name = os.path.splitext(os.path.basename(img))[0].lower()
            if not name:
                continue
            entries.append(f"{name}={img}")
        if not entries:
            self._toasts.show_warn(
                "No images found",
                "Firmware dir needs partition images (boot.img, recovery.img, ...)",
            )
            return
        parts = ", ".join(os.path.basename(e) for e in entries)
        self._ui.line.emit(f"[step] MTK flash partitions (no scatter): {parts}")
        self._confirm_overlay(
            "Flash Partitions (No Scatter)",
            f"Write {len(entries)} partition(s) by NAME, resolving addresses\n"
            f"from the device GPT (no scatter file needed)?\n\n"
            + "\n".join(f"  {e}" for e in entries)
            + "\n\nThis OVERWRITES those partitions. Continue?",
            confirm_label="Flash",
            on_confirm=lambda: self._mtk_run(
                ["mtk-flash-part", "auto", da] + entries, timeout=1800
            ),
        )

    # ----------------------------- Qualcomm page --------------------------
    def _build_qc_page(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(
            _card_qss()
        )
        panel_lay = QVBoxLayout(panel)
        panel_lay.setContentsMargins(0, 0, 0, 0)
        panel_lay.setSpacing(0)
        page_scroll = self._ops_scroll_area()
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(host)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(9)

        lay.addWidget(SectionTitle("QUALCOMM EDL / SAHARA / FIREHOSE"))
        info = QLabel(
            "Qualcomm Emergency Download (EDL) tooling. Requires the device in EDL "
            "mode (VID 05c6) plus a firehose programmer and rawprogram XML."
        )
        info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        det_row = QHBoxLayout()
        self.qc_detect_btn = QPushButton("Detect Qualcomm")
        self.qc_detect_btn.setStyleSheet(_btn_primary())
        self.qc_detect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.qc_detect_btn.clicked.connect(self._qc_detect)
        det_row.addWidget(self.qc_detect_btn)
        self.qc_status = QLabel("No Qualcomm EDL device detected")
        self.qc_status.setStyleSheet(f"color:{C['dim']}; font-size:12px;")
        det_row.addWidget(self.qc_status, 1)
        lay.addLayout(det_row)

        self.qc_files = {}
        for name, lbl, flt in (
            ("prog", "Programmer (.mbn)", "Programmer (*.mbn *.elf);;All files (*)"),
            ("xml", "Rawprogram XML", "XML (*.xml);;All files (*)"),
        ):
            row = QHBoxLayout()
            lab = QLabel(lbl)
            lab.setStyleSheet(f"color:{C['dim']}; font-weight:600; min-width:120px;")
            edit = QLineEdit()
            edit.setPlaceholderText(f"Select {lbl.lower()}...")
            edit.setStyleSheet(
                f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
                f" border-radius:8px; padding:6px 10px; color:{C['text']};"
                f" selection-background-color:{C['accent']}; }}"
                f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
                f" QLineEdit:focus {{ border:1px solid {C['accent']}; }}"
            )
            btn = QPushButton("Browse...")
            btn.setStyleSheet(_btn_ghost())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(90)
            btn.clicked.connect(
                lambda _=False, e=edit, n=name, f=flt: self._qc_browse(e, n, f)
            )
            row.addWidget(lab)
            row.addWidget(edit, 1)
            row.addWidget(btn)
            lay.addLayout(row)
            self.qc_files[name] = edit

        acts = QVBoxLayout()
        acts.setSpacing(8)
        acts_row1 = QHBoxLayout()
        acts_row1.setSpacing(10)
        for label, slot in (
            ("Flash via Firehose", self._qc_flash),
            ("Backup Partitions", self._qc_backup),
            ("Get Device Info", self._qc_info),
        ):
            b = QPushButton(label)
            b.setStyleSheet(_btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            acts_row1.addWidget(b)
        acts_row1.addStretch(1)
        acts.addLayout(acts_row1)
        acts_row2 = QHBoxLayout()
        acts_row2.setSpacing(10)
        for label, slot in (
            ("FRP Reset", self._qc_frp_reset),
            ("Enable ADB", self._qc_adb),
        ):
            b = QPushButton(label)
            b.setStyleSheet(_btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            acts_row2.addWidget(b)
        acts_row2.addStretch(1)
        self.qc_stop_btn = QPushButton("Stop")
        self.qc_stop_btn.setEnabled(False)
        self.qc_stop_btn.setStyleSheet(_btn_danger())
        self.qc_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.qc_stop_btn.clicked.connect(self._qc_stop)
        self.qc_stop_btn.setToolTip("Cancel the running Qualcomm operation")
        acts_row2.addWidget(self.qc_stop_btn)
        acts.addLayout(acts_row2)
        lay.addLayout(acts)

        self.qc_fw_dir = QLineEdit()
        self.qc_fw_dir.setPlaceholderText("Firmware directory (partition images)...")
        self.qc_fw_dir.setStyleSheet(
            f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:6px 10px; color:{C['text']};"
            f" selection-background-color:{C['accent']}; }}"
            f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
            f" QLineEdit:focus {{ border:1px solid {C['accent']}; }}"
        )
        fw_row = QHBoxLayout()
        fw_row.addWidget(QLabel("Firmware dir"), 0)
        fw_row.addWidget(self.qc_fw_dir, 1)
        fw_btn = QPushButton("Browse...")
        fw_btn.setStyleSheet(_btn_ghost())
        fw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fw_btn.clicked.connect(self._qc_browse_dir)
        fw_btn.setFixedWidth(90)
        fw_row.addWidget(fw_btn)
        lay.addLayout(fw_row)
        lay.addWidget(
            _risk_banner(
                "Qualcomm firehose flashing writes the whole device. The "
                "programmer must match your exact SoC - a mismatch can hard-brick."
            )
        )

        self.qc_progress = QProgressBar()
        self.qc_progress.setRange(0, 1000)
        self.qc_progress.setValue(0)
        self.qc_progress.setTextVisible(False)
        self.qc_progress.setFixedHeight(8)
        self.qc_progress.setStyleSheet(
            f"QProgressBar {{ background:{C['inset']}; border:none; border-radius:4px; }}"
            f" QProgressBar::chunk {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f" stop:0 {C['grad_a']}, stop:1 {C['grad_b']}); border-radius:4px; }}"
        )
        self.qc_progress.setVisible(False)

        # --- Fastboot partition tools (not covered by the job/flow maps) ---
        fb_body = QWidget()
        fb_body.setStyleSheet("background: transparent;")
        fb_lay = QVBoxLayout(fb_body)
        fb_lay.setContentsMargins(0, 0, 0, 0)
        fb_lay.setSpacing(8)

        fb_row = QHBoxLayout()
        fb_row.setSpacing(6)
        fb_part = QLineEdit()
        fb_part.setPlaceholderText("Partition (e.g. boot, system, super)")
        fb_part.setMinimumWidth(80)
        fb_part.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        fb_part.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 5px 8px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")
        fb_row.addWidget(fb_part, 1)
        fb_img = QLineEdit()
        fb_img.setPlaceholderText("Image file (.img / .tar)")
        fb_img.setMinimumWidth(80)
        fb_img.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        fb_img.setStyleSheet(f"QLineEdit {{ background: {C['inset']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 5px 8px; color: {C['text']}; selection-background-color: {C['accent']}; }} QLineEdit:hover {{ border: 1px solid {C['border_hi']}; }} QLineEdit:focus {{ border: 1px solid {C['accent']}; }}")
        fb_row.addWidget(fb_img, 1)
        fb_browse = QPushButton("Browse...")
        fb_browse.setStyleSheet(_btn_ghost())
        fb_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        fb_browse.setFixedWidth(80)
        fb_browse.clicked.connect(lambda: self._qc_browse(fb_img, "fastboot image", "Images (*.img *.img.gz *.tar);;All files (*)"))
        fb_row.addWidget(fb_browse)
        fb_lay.addLayout(fb_row)

        def _fb_run(method, label, tooltip):
            btn = QPushButton(label)
            btn.setStyleSheet(_btn_ghost())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.clicked.connect(
                lambda _=False, m=method, n=label: self._qc_fastboot_flow(
                    m, n, fb_part, fb_img
                )
            )
            return btn

        fb_btns = QHBoxLayout()
        fb_btns.setSpacing(6)
        fb_btns.addWidget(_fb_run("fastboot_flash", "Flash", "fastboot flash <partition> <image> (bootloader must be unlocked)"))
        fb_btns.addWidget(_fb_run("fastboot_format", "Format", "fastboot format <partition> (ext4/f2fs)"))
        fb_btns.addWidget(_fb_run("fastboot_lock", "Relock", "fastboot flashing lock / oem lock (re-lock the bootloader)"))
        fb_btns.addWidget(_fb_run("fastboot_set_active", "Set active", "fastboot set_active a/b - choose the boot slot"))
        fb_btns.addStretch(1)
        fb_lay.addLayout(fb_btns)

        fb_btns2 = QHBoxLayout()
        fb_btns2.setSpacing(6)
        fb_btns2.addWidget(_fb_run("fastboot_read", "Getvar", "fastboot getvar all - dump device variables"))
        fb_btns2.addWidget(_fb_run("fastboot_oem", "OEM", "fastboot oem <cmd> (set FASTBOOT_OEM, default device-info)"))
        fb_btns2.addStretch(1)
        fb_lay.addLayout(fb_btns2)

        fb_sec = CollapsibleSection(
            "FASTBOOT TOOLS", fb_body, accent=C["accent"], collapsed=True
        )
        lay.addWidget(fb_sec)

        qc_ops = self._build_chip_ops_section(
            "qc",
            {"EDL", "FASTBOOT", "ADB", "MTP"},
            self.qc_stop_btn, self.qc_progress, self._qc_reset_ui,
        )
        lay.addWidget(qc_ops, 1)
        lay.addWidget(self.qc_progress)
        page_scroll.setWidget(host)
        panel_lay.addWidget(page_scroll)
        return panel

    def _qc_fastboot_flow(self, method, label, part_edit, img_edit):
        """Run a fastboot partition flow with the values typed in the FASTBOOT
        TOOLS section. Sets FASTBOOT_PARTITION / FASTBOOT_IMAGE env so the flow
        flashes / formats exactly the partition+image the user entered."""
        part = part_edit.text().strip()
        img = img_edit.text().strip()
        if part:
            os.environ["FASTBOOT_PARTITION"] = part
        else:
            os.environ.pop("FASTBOOT_PARTITION", None)
        if img:
            os.environ["FASTBOOT_IMAGE"] = img
        else:
            os.environ.pop("FASTBOOT_IMAGE", None)
        self._run_job_flow(
            "Reboot device", "FASTBOOT", method, label,
            self.qc_stop_btn, self.qc_progress, self._qc_reset_ui,
        )

    def _qc_browse(self, edit, name, name_filter):
        path, _ = QFileDialog.getOpenFileName(self, f"Select {name}", os.path.expanduser("~/Downloads"), name_filter)
        if path:
            edit.setText(path)

    def _qc_browse_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select firmware directory", os.path.expanduser("~/Downloads")
        )
        if d:
            self.qc_fw_dir.setText(d)

    def _qc_run(self, args, timeout=600):
        if not _flow_start(f"Qualcomm {args[0]}", destructive=True):
            self._ui.status.emit("Busy: " + _flow_busy_msg())
            self._ui.toast.emit("warn", "Operation already running", _flow_busy_msg())
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg()}")
            return

        def work():
            try:
                out = bridge._run(args, timeout=timeout)
                self._ui.line.emit(out or "(no output)")
                self._ui.status.emit(f"Qualcomm: {args[0]} done")
                self._ui.toast.emit("ok", f"Qualcomm {args[0]}", "Completed successfully")
            except bridge.BridgeCancelled:
                self._ui.line.emit("[cancelled] Qualcomm operation stopped by user")
                self._ui.status.emit("Qualcomm: operation cancelled")
                self._ui.toast.emit("warn", "Qualcomm operation", "Cancelled")
            except bridge.BridgeError as e:
                self._ui.line.emit(f"[error] Qualcomm {args[0]}: {e}")
                self._ui.status.emit(f"Qualcomm: {args[0]} failed")
                self._ui.toast.emit("error", f"Qualcomm {args[0]}", str(e))
            finally:
                _flow_end()
                bridge.clear_cancel()
                self._ui.ui.emit(self._qc_reset_ui)

        bridge.clear_cancel()
        self.qc_stop_btn.setEnabled(True)
        self.qc_progress.setVisible(True)
        self.qc_progress.setValue(150)
        threading.Thread(target=work, daemon=True).start()

    def _qc_reset_ui(self):
        self.qc_stop_btn.setEnabled(False)
        self.qc_progress.setValue(1000)
        QTimer.singleShot(400, lambda: self.qc_progress.setVisible(False))

    def _qc_stop(self):
        bridge.request_cancel()
        frp.request_cancel()
        self._ui.status.emit("Qualcomm: stopping ...")
        self._ui.line.emit("[warn] Qualcomm: stop requested, killing bridge ...")

    def _qc_adb(self):
        """Best-effort ADB enable for a Qualcomm device that is booted to
        Android (or recovery) and reachable over adb. EDL-mode devices can't
        enable ADB directly - tell the user so."""
        def work():
            try:
                devs = bridge.adb_status()
            except bridge.BridgeError:
                devs = []
            if not any(d["state"] == "device" for d in devs):
                self._ui.line.emit(
                    "[warn] No authorized ADB device found. Boot the phone to "
                    "Android/recovery with USB debugging on, then retry."
                )
                self._ui.toast.emit(
                    "warn", "Enable ADB", "No authorized ADB device detected"
                )
                return
            serial = next(d["serial"] for d in devs if d["state"] == "device")
            self._ui.line.emit(f"[step] Enabling ADB on {serial} ...")
            for cmd in (
                "setprop persist.sys.usb.config adb",
                "setprop sys.usb.config adb",
                "settings put global adb_enabled 1",
                "svc usb setFunctions adb",
            ):
                try:
                    out = bridge.adb_shell(cmd, timeout=10)
                    if out:
                        self._ui.line.emit(f"  {cmd} -> {out[:120]}")
                    else:
                        self._ui.line.emit(f"  {cmd} -> ok")
                except bridge.BridgeError as e:
                    self._ui.line.emit(f"[warn] {cmd}: {e}")
            self._ui.line.emit("[ok] ADB enable commands sent")
            self._ui.toast.emit("ok", "Enable ADB", "Commands sent to device")

        threading.Thread(target=work, daemon=True).start()

    def _qc_detect(self):
        self.qc_status.setText("Scanning USB...")

        def work():
            try:
                out = bridge._run(["qcom-detect"])
                self._ui.ui.emit(lambda s=out: self.qc_status.setText(
                    s or "No Qualcomm EDL device detected"))
                self._ui.line.emit(f"[info] {out}")
            except bridge.BridgeError as e:
                self._ui.ui.emit(lambda err=e: self.qc_status.setText(
                    f"Scan error: {err}"))
                self._ui.line.emit(f"[error] qcom-detect: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _qc_flash(self):
        prog = self.qc_files["prog"].text().strip()
        xml = self.qc_files["xml"].text().strip()
        fw = self.qc_fw_dir.text().strip()
        if not prog or not xml or not fw:
            self._toasts.show_warn(
                "Qualcomm files missing",
                "Need programmer (.mbn), rawprogram XML and firmware dir",
            )
            return
        self._ui.line.emit(f"[step] Qualcomm flash: prog={prog} xml={xml} fw={fw}")
        self._qc_run(["qcom-flash", "auto", prog, xml, fw], timeout=1800)

    def _qc_backup(self):
        prog = self.qc_files["prog"].text().strip()
        if not prog:
            self._toasts.show_warn("Programmer missing", "Select the firehose programmer (.mbn)")
            return
        self._qc_run(["qcom-backup", "auto", prog, "/tmp/qcom_backup"], timeout=1800)

    def _qc_info(self):
        self.qc_progress.setVisible(True)
        self.qc_progress.setValue(150)

        def work():
            lines = []
            try:
                all_devs = bridge.detect_all()
                qcom = [d for d in all_devs if d.get("vid") == 0x05C6]
                if qcom:
                    lines.append("=== Qualcomm USB Device(s) ===")
                    for d in qcom:
                        lines.extend(_fmt_usb_full(d))
                        pid = d.get("pid", 0)
                        if pid in (0x9008, 0x900E):
                            lines.append("  -> EDL mode (Sahara/firehose capable)")
                        else:
                            lines.append("  -> normal/modem mode (not in EDL)")
                        lines.append("")
                else:
                    lines.append("No Qualcomm USB device (VID 05c6) found over USB")
                    lines.append("")

                out = bridge._run(["qcom-info", "auto"], timeout=120)
                lines.append("--- Sahara device info ---")
                lines.append(out or "(Sahara handshake not available - device not in EDL)")
                self._ui.line.emit("\n".join(lines))
                self._ui.status.emit("Qualcomm: device info complete")
            except bridge.BridgeCancelled:
                self._ui.line.emit("[cancelled] Qualcomm info stopped by user")
            except bridge.BridgeError as e:
                lines.append("--- Sahara device info ---")
                lines.append(f"(Sahara handshake failed: {e})")
                self._ui.line.emit("\n".join(lines))
                self._ui.status.emit("Qualcomm: info partial")
            finally:
                bridge.clear_cancel()
                self._ui.ui.emit(self._qc_reset_ui)

        bridge.clear_cancel()
        self.qc_stop_btn.setEnabled(True)
        threading.Thread(target=work, daemon=True).start()

    def _qc_frp_reset(self):
        """One-click FRP bypass: erase the frp partition over Firehose.
        Requires the device in EDL mode with Sahara/streaming support."""
        self._confirm_overlay(
            "FRP Reset",
            "Erase the FRP partition on the connected Qualcomm device?\n\n"
            "This wipes Factory Reset Protection so the phone can be "
            "re-flashed / set up as new. The device must be in EDL mode.",
            confirm_label="Erase FRP",
            on_confirm=lambda: self._qc_run(["qcom-frp-reset", "auto"], timeout=300),
        )

    def _confirm_flash_action(self, label, method, extra):
        """Confirm any device-writing operation before it runs, then dispatch
        through the Odin advanced-flow runner."""
        self._confirm_overlay(
            label,
            f"{extra}\n\n"
            "Make sure you selected the correct files. Proceed only if you "
            "are sure this is the right firmware for your model.",
            confirm_label="Continue",
            on_confirm=lambda: self._run_ops_flow(
                "Odin Flashing (Advanced)", "Download mode", method, label
            ),
        )

    def _confirm_overlay(self, title, text, confirm_label, on_confirm):
        """Non-blocking in-window confirmation. The native QMessageBox modal
        can hang on frameless/translucent Wayland windows, so we render our
        own dimmed overlay card (same approach as the toast system)."""
        overlay = QFrame(self._root)
        overlay.setObjectName("confirmOverlay")
        overlay.setStyleSheet(
            f"QFrame#confirmOverlay {{ background: rgba(5, 8, 13, 185);"
            f" border-radius: 18px; }}"
        )
        overlay.setGeometry(0, 0, self._root.width(), self._root.height())

        card = QFrame(overlay)
        card.setObjectName("confirmCard")
        card.setFixedWidth(400)
        card.setStyleSheet(
            f"QFrame#confirmCard {{ background: {C['card']};"
            f" border: 1px solid {C['border_hi']}; border-radius: 14px; }}"
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 180))
        card.setGraphicsEffect(shadow)

        v = QVBoxLayout(card)
        v.setContentsMargins(22, 20, 22, 18)
        v.setSpacing(14)

        t = QLabel(title)
        t.setStyleSheet(
            f"color:{C['text']}; font-size:15px; font-weight:800;"
        )
        v.addWidget(t)

        m = QLabel(text)
        m.setStyleSheet(f"color:{C['dim']}; font-size:12px; line-height:140%;")
        m.setWordWrap(True)
        v.addWidget(m)

        btns = QHBoxLayout()
        btns.setSpacing(10)

        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(_btn_ghost())
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setFixedWidth(110)

        ok = QPushButton(confirm_label)
        ok.setStyleSheet(_btn_danger())
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setFixedWidth(140)
        ok.setFocus()

        def close():
            overlay.hide()
            overlay.deleteLater()

        cancel.clicked.connect(close)
        ok.clicked.connect(lambda: (close(), on_confirm()))
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        v.addLayout(btns)

        # center the card inside the overlay (recomputed on resize)
        def center():
            card.move(
                (overlay.width() - card.width()) // 2,
                (overlay.height() - card.height()) // 2,
            )

        def on_resize(e):
            QFrame.resizeEvent(overlay, e)
            center()

        overlay.resizeEvent = on_resize
        center()
        overlay.show()
        overlay.raise_()
        ok.setFocus()

    # ----------------------------- Battery page ---------------------------
    # ----------------------------- SPD / UNISOC page ----------------------
    def _build_spd_page(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(_card_qss())
        panel_lay = QVBoxLayout(panel)
        panel_lay.setContentsMargins(0, 0, 0, 0)
        panel_lay.setSpacing(0)
        page_scroll = self._ops_scroll_area()
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(host)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(9)

        lay.addWidget(SectionTitle("SPREADTRUM / UNISOC (SPD) DOWNLOAD"))
        info = QLabel(
            "Feature-phone & SoC BSL download tooling. Requires the device in "
            "download mode (1782:4d00) plus FDL1/FDL2 binaries + base addresses."
        )
        info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        det_row = QHBoxLayout()
        self.spd_detect_btn = QPushButton("Detect SPD")
        self.spd_detect_btn.setStyleSheet(_btn_primary())
        self.spd_detect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.spd_detect_btn.clicked.connect(self._spd_detect)
        det_row.addWidget(self.spd_detect_btn)
        self.spd_status = QLabel("No SPD download device detected")
        self.spd_status.setStyleSheet(f"color:{C['dim']}; font-size:12px;")
        det_row.addWidget(self.spd_status, 1)
        lay.addLayout(det_row)

        self.spd_files = {}
        for name, lbl, flt in (
            ("fdl1", "FDL1 binary", "FDL (*.bin);;All files (*)"),
            ("fdl2", "FDL2 binary", "FDL (*.bin);;All files (*)"),
        ):
            row = QHBoxLayout()
            lab = QLabel(lbl)
            lab.setStyleSheet(f"color:{C['dim']}; font-weight:600; min-width:90px;")
            edit = QLineEdit()
            edit.setPlaceholderText(f"Select {lbl.lower()}...")
            edit.setStyleSheet(
                f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
                f" border-radius:8px; padding:6px 10px; color:{C['text']};"
                f" selection-background-color:{C['accent']}; }}"
                f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
                f" QLineEdit:focus {{ border:1px solid {C['accent']}; }}"
            )
            btn = QPushButton("Browse...")
            btn.setStyleSheet(_btn_ghost())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(90)
            btn.clicked.connect(
                lambda _=False, e=edit, n=name, f=flt: self._spd_browse(e, n, f)
            )
            row.addWidget(lab)
            row.addWidget(edit, 1)
            row.addWidget(btn)
            lay.addLayout(row)
            self.spd_files[name] = edit

        # FDL base addresses (hex)
        base_row = QHBoxLayout()
        self.spd_fdl1_addr = QLineEdit("0x40004000")
        self.spd_fdl1_addr.setToolTip("FDL1 base address for your chip")
        self.spd_fdl2_addr = QLineEdit("0x14000000")
        self.spd_fdl2_addr.setToolTip("FDL2 base address for your chip")
        for edit in (self.spd_fdl1_addr, self.spd_fdl2_addr):
            edit.setStyleSheet(
                f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
                f" border-radius:8px; padding:6px 10px; color:{C['text']};"
                f" selection-background-color:{C['accent']}; }}"
                f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
            )
        base_row.addWidget(QLabel("FDL1 base"))
        base_row.addWidget(self.spd_fdl1_addr, 1)
        base_row.addWidget(QLabel("FDL2 base"))
        base_row.addWidget(self.spd_fdl2_addr, 1)
        lay.addLayout(base_row)

        acts = QVBoxLayout()
        acts.setSpacing(8)
        acts_row1 = QHBoxLayout()
        acts_row1.setSpacing(10)
        for label, slot in (
            ("Get Device Info", self._spd_info),
            ("Flash Firmware", self._spd_flash),
            ("Backup Partitions", self._spd_backup),
        ):
            b = QPushButton(label)
            b.setStyleSheet(_btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            acts_row1.addWidget(b)
        acts_row1.addStretch(1)
        acts.addLayout(acts_row1)
        acts_row2 = QHBoxLayout()
        acts_row2.setSpacing(10)
        for label, slot in (
            ("Format / Unlock", self._spd_format),
            ("FRP Reset", self._spd_frp),
        ):
            b = QPushButton(label)
            b.setStyleSheet(_btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            acts_row2.addWidget(b)
        acts_row2.addStretch(1)
        self.spd_stop_btn = QPushButton("Stop")
        self.spd_stop_btn.setEnabled(False)
        self.spd_stop_btn.setStyleSheet(_btn_danger())
        self.spd_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.spd_stop_btn.clicked.connect(self._spd_stop)
        self.spd_stop_btn.setToolTip("Cancel the running SPD operation")
        acts_row2.addWidget(self.spd_stop_btn)
        acts.addLayout(acts_row2)
        lay.addLayout(acts)

        self.spd_fw_dir = QLineEdit()
        self.spd_fw_dir.setPlaceholderText("Firmware directory (partition images)...")
        self.spd_fw_dir.setStyleSheet(
            f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:6px 10px; color:{C['text']};"
            f" selection-background-color:{C['accent']}; }}"
            f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
        )
        fw_row = QHBoxLayout()
        fw_row.addWidget(QLabel("Firmware dir"), 0)
        fw_row.addWidget(self.spd_fw_dir, 1)
        fw_btn = QPushButton("Browse...")
        fw_btn.setStyleSheet(_btn_ghost())
        fw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fw_btn.clicked.connect(self._spd_browse_dir)
        fw_btn.setFixedWidth(90)
        fw_row.addWidget(fw_btn)
        lay.addLayout(fw_row)
        lay.addWidget(
            _risk_banner(
                "SPD flashing and factory format write directly to the chip. "
                "The FDL binaries and base addresses must match your exact "
                "chipset - a wrong FDL can hard-brick the device."
            )
        )

        self.spd_progress = QProgressBar()
        self.spd_progress.setRange(0, 1000)
        self.spd_progress.setValue(0)
        self.spd_progress.setTextVisible(False)
        self.spd_progress.setFixedHeight(8)
        self.spd_progress.setStyleSheet(
            f"QProgressBar {{ background:{C['inset']}; border:none; border-radius:4px; }}"
            f" QProgressBar::chunk {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f" stop:0 {C['grad_a']}, stop:1 {C['grad_b']}); border-radius:4px; }}"
        )
        self.spd_progress.setVisible(False)
        spd_ops = self._build_chip_ops_section(
            "spd",
            {"ADB", "MTP", "FASTBOOT"},
            self.spd_stop_btn, self.spd_progress, self._spd_reset_ui,
        )
        lay.addWidget(spd_ops, 1)
        lay.addWidget(self.spd_progress)
        page_scroll.setWidget(host)
        panel_lay.addWidget(page_scroll)
        return panel

    def _spd_browse(self, edit, name, name_filter):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Select {name}", os.path.expanduser("~/Downloads"), name_filter
        )
        if path:
            edit.setText(path)

    def _spd_browse_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select firmware directory", os.path.expanduser("~/Downloads")
        )
        if d:
            self.spd_fw_dir.setText(d)

    def _spd_target(self):
        """Best-effort current SPD download target from the poll state."""
        return getattr(self, "_last_spd_target", None)

    def _spd_run(self, args, timeout=900):
        if not _flow_start(f"SPD {args[0]}", destructive=True):
            self._ui.status.emit("Busy: " + _flow_busy_msg())
            self._ui.toast.emit("warn", "Operation already running", _flow_busy_msg())
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg()}")
            return

        def work():
            try:
                out = bridge._run(args, timeout=timeout)
                self._ui.line.emit(out or "(no output)")
                self._ui.status.emit(f"SPD: {args[0]} done")
                self._ui.toast.emit("ok", f"SPD {args[0]}", "Completed successfully")
            except bridge.BridgeCancelled:
                self._ui.line.emit("[cancelled] SPD operation stopped by user")
                self._ui.status.emit("SPD: operation cancelled")
                self._ui.toast.emit("warn", "SPD operation", "Cancelled")
            except bridge.BridgeError as e:
                self._ui.line.emit(f"[error] SPD {args[0]}: {e}")
                self._ui.status.emit(f"SPD: {args[0]} failed")
                self._ui.toast.emit("error", f"SPD {args[0]}", str(e))
            finally:
                _flow_end()
                bridge.clear_cancel()
                self._ui.ui.emit(self._spd_reset_ui)

        bridge.clear_cancel()
        self.spd_stop_btn.setEnabled(True)
        self.spd_progress.setVisible(True)
        self.spd_progress.setValue(150)
        threading.Thread(target=work, daemon=True).start()

    def _spd_reset_ui(self):
        self.spd_stop_btn.setEnabled(False)
        self.spd_progress.setValue(1000)
        QTimer.singleShot(400, lambda: self.spd_progress.setVisible(False))

    def _spd_stop(self):
        bridge.request_cancel()
        frp.request_cancel()
        self._ui.status.emit("SPD: stopping ...")
        self._ui.line.emit("[warn] SPD: stop requested, killing bridge ...")

    def _spd_detect(self):
        self.spd_status.setText("Scanning USB...")

        def work():
            try:
                devs = bridge._run(["spd-detect"])
                import json as _json
                parsed = _json.loads(devs or "[]")
                if not parsed:
                    self._ui.ui.emit(lambda: self.spd_status.setText(
                        "No SPD device detected"))
                    self._ui.line.emit("[info] spd-detect: no device found")
                    return
                for d in parsed:
                    self._ui.line.emit(
                        f"SPD: 1782:{d.get('pid', 0):04x} bus={d.get('bus')} "
                        f"addr={d.get('address')} - {d.get('stage', '')}"
                    )
                self._ui.ui.emit(lambda n=len(parsed): self.spd_status.setText(
                    f"{n} SPD device(s) found"))
            except bridge.BridgeError as e:
                self._ui.ui.emit(lambda err=e: self.spd_status.setText(
                    f"Scan error: {err}"))
            except Exception as e:  # noqa: BLE001
                self._ui.ui.emit(lambda err=e: self.spd_status.setText(
                    f"Scan error: {err}"))

        threading.Thread(target=work, daemon=True).start()

    def _spd_resolve_target(self):
        """Resolve 'auto' to the current SPD download device target string."""
        tgt = self._spd_target()
        if tgt:
            return tgt
        try:
            devs = bridge._run(["spd-detect"])
            import json as _json
            parsed = _json.loads(devs or "[]")
            dl = [d for d in parsed if d.get("download")]
            if not dl:
                dl = parsed
            if dl:
                d = dl[0]
                self._last_spd_target = f"{d['bus']}:{d['address']}"
                return self._last_spd_target
        except Exception:  # noqa: BLE001
            pass
        return None

    def _spd_require_files(self):
        fdl1 = self.spd_files["fdl1"].text().strip()
        if not fdl1:
            self._ui.line.emit("[warn] SPD: FDL1 binary is required")
            self._toasts.show_warn("SPD files missing", "Select an FDL1 binary")
            return None
        return fdl1

    def _spd_addr(self, edit):
        try:
            return int(edit.text().strip(), 0)
        except ValueError:
            self._ui.line.emit("[warn] SPD: invalid FDL base address")
            return None

    def _spd_info(self):
        self.spd_status.setText("Reading device info...")

        def work():
            try:
                tgt = self._spd_resolve_target()
                if not tgt:
                    self._ui.line.emit("[info] spd-info: no SPD device in download mode")
                    self._ui.ui.emit(lambda: self.spd_status.setText(
                        "No SPD device detected"))
                    return
                out = bridge._run(["spd-info", tgt], timeout=60)
                self._ui.line.emit(out or "(no output)")
                self._ui.ui.emit(lambda: self.spd_status.setText("Info above"))
            except bridge.BridgeError as e:
                self._ui.line.emit(f"[error] SPD device info: {e}")
                self._ui.ui.emit(lambda err=e: self.spd_status.setText(
                    f"Read error: {err}"))

        threading.Thread(target=work, daemon=True).start()

    def _spd_format(self):
        fdl1 = self._spd_require_files()
        if not fdl1:
            return
        a1 = self._spd_addr(self.spd_fdl1_addr)
        if a1 is None:
            return
        fdl2 = self.spd_files["fdl2"].text().strip()
        tgt = self._spd_resolve_target()
        if not tgt:
            self._ui.line.emit("[warn] SPD: no download device detected")
            self._toasts.show_warn("No SPD device", "Plug the phone into download mode")
            return
        self._confirm_overlay(
            "Format / Unlock",
            "Erase the security lock / user-data regions WITHOUT flashing\n"
            "firmware (SPD 'Reset to Factory Default').\n\n"
            + ("Android: erases userdata, cache, frp, misc partitions.\n"
               if fdl2 else
               "Feature phone: erases PS (param store) + NV regions.\n")
            + "User data on the phone will be erased. Continue?",
            confirm_label="Format & Unlock",
            on_confirm=lambda: self._spd_run(
                ["spd-format", tgt, fdl1, f"0x{a1:x}"]
                + ([fdl2, "0x%x" % self._spd_addr(self.spd_fdl2_addr)] if fdl2 else []),
                timeout=900,
            ),
        )

    def _spd_frp(self):
        fdl1 = self._spd_require_files()
        if not fdl1:
            return
        a1 = self._spd_addr(self.spd_fdl1_addr)
        if a1 is None:
            return
        fdl2 = self.spd_files["fdl2"].text().strip()
        tgt = self._spd_resolve_target()
        if not tgt:
            self._ui.line.emit("[warn] SPD: no download device detected")
            self._toasts.show_warn("No SPD device", "Plug the phone into download mode")
            return
        self._confirm_overlay(
            "FRP Reset",
            "Erase the FRP / lock partitions on the connected SPD device?\n\n"
            "Wipes Factory Reset Protection so the device can be set up as new.",
            confirm_label="Erase FRP",
            on_confirm=lambda: self._spd_run(
                ["spd-frp", tgt, fdl1, f"0x{a1:x}"]
                + ([fdl2, "0x%x" % self._spd_addr(self.spd_fdl2_addr)] if fdl2 else []),
                timeout=900,
            ),
        )

    def _spd_flash(self):
        fdl1 = self._spd_require_files()
        if not fdl1:
            return
        a1 = self._spd_addr(self.spd_fdl1_addr)
        if a1 is None:
            return
        fdl2 = self.spd_files["fdl2"].text().strip()
        fw = self.spd_fw_dir.text().strip()
        if not fw:
            self._toasts.show_warn("Firmware dir missing", "Select the firmware directory")
            return

        entries = self._spd_build_entry_map(fw)
        if not entries:
            self._toasts.show_warn(
                "No images found",
                "Firmware dir needs partition images: feature-phone (ps.bin, "
                "nv.bin, bootloader.bin) or Android (boot.img, system.img, ...)",
            )
            return

        parts = ", ".join(f"{p}->{os.path.basename(f)}" for p, f in entries)
        self._ui.line.emit(f"[step] SPD flash: {parts}")
        self._confirm_overlay(
            "Flash Firmware",
            f"Write {len(entries)} partition image(s) to the connected SPD device?\n\n"
            + "\n".join(f"  {p} <- {os.path.basename(f)}" for p, f in entries)
            + "\n\nThis OVERWRITES those partitions/regions.\n"
            "Firmware is not replaced wholesale - only the listed images.\n"
            "Android devices need FDL1 + FDL2; feature phones need FDL1.\n"
            "Ensure the FDL binaries match your chipset. Continue?",
            confirm_label="Flash",
            on_confirm=lambda: self._spd_flash_run(fdl1, a1, fdl2, entries),
        )

    def _spd_build_entry_map(self, fw_dir):
        """Build a list of (partition, file) from the firmware dir. Names are
        derived from the image filenames so users can drop feature-phone
        images (`ps.bin`, `nv.bin`, `bootloader.bin`, `udisk.bin`,
        `0xADDR.bin`) or Android partition images (`boot.img`, `system.img`,
        `recovery.img`, `userdata.img`, ...). Looks one level into
        subdirectories for Android firmware layouts."""
        import glob as _glob
        entries = []
        roots = [fw_dir] + [
            os.path.join(fw_dir, d) for d in sorted(os.listdir(fw_dir))
            if os.path.isdir(os.path.join(fw_dir, d))
        ]
        for root in roots:
            for img in sorted(_glob.glob(os.path.join(root, "*.bin")) +
                              _glob.glob(os.path.join(root, "*.img"))):
                name = os.path.splitext(os.path.basename(img))[0].lower()
                if not name:
                    continue
                entries.append((name, img))
        return entries

    def _spd_flash_run(self, fdl1, a1, fdl2, entries):
        if not _flow_start("SPD flash", destructive=True):
            self._ui.status.emit("Busy: " + _flow_busy_msg())
            self._ui.toast.emit("warn", "Operation already running", _flow_busy_msg())
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg()}")
            return

        def work():
            try:
                tgt = self._spd_resolve_target()
                if not tgt:
                    self._ui.line.emit("[error] SPD: no download device")
                    self._ui.ui.emit(self._spd_reset_ui)
                    return
                args = ["spd-flash", tgt, fdl1, f"0x{a1:x}"]
                if fdl2:
                    a2 = self._spd_addr(self.spd_fdl2_addr) or 0
                    args += [fdl2, f"0x{a2:x}"]
                for part, file in entries:
                    args.append(f"{part}={file}")
                out = bridge._run(args, timeout=1800)
                self._ui.line.emit(out or "(no output)")
                self._ui.status.emit("SPD: flash complete")
                self._ui.toast.emit("ok", "SPD flash", "Completed")
            except bridge.BridgeError as e:
                self._ui.line.emit(f"[error] SPD flash: {e}")
                self._ui.toast.emit("error", "SPD flash", str(e))
            finally:
                _flow_end()
                bridge.clear_cancel()
                self._ui.ui.emit(self._spd_reset_ui)

        bridge.clear_cancel()
        self.spd_stop_btn.setEnabled(True)
        self.spd_progress.setVisible(True)
        self.spd_progress.setValue(150)
        threading.Thread(target=work, daemon=True).start()

    def _spd_backup(self):
        fdl1 = self._spd_require_files()
        if not fdl1:
            return
        if not _flow_start("SPD backup", destructive=False):
            self._ui.status.emit("Busy: " + _flow_busy_msg())
            self._ui.toast.emit("warn", "Operation already running", _flow_busy_msg())
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg()}")
            return
        a1 = self._spd_addr(self.spd_fdl1_addr)
        if a1 is None:
            _flow_end()
            return
        fdl2 = self.spd_files["fdl2"].text().strip()
        fw = self.spd_fw_dir.text().strip()
        out_dir = fw or "/tmp/spd_backup"
        self._ui.line.emit(f"[step] SPD backup: fdl1={fdl1} fdl2={fdl2} out={out_dir}")
        self._toasts.show_ok("SPD backup queued", "Reading partition table...")

        def work():
            try:
                tgt = self._spd_resolve_target()
                if not tgt:
                    self._ui.line.emit("[error] SPD: no download device")
                    self._ui.ui.emit(self._spd_reset_ui)
                    return
                out = bridge._run(
                    ["spd-backup", tgt, fdl1, f"0x{a1:x}",
                     fdl2 or "none", "0", out_dir],
                    timeout=900,
                )
                self._ui.line.emit(out or "(no output)")
                self._ui.status.emit("SPD: backup complete")
                self._ui.toast.emit("ok", "SPD backup", "Partition table dumped")
            except bridge.BridgeError as e:
                self._ui.line.emit(f"[error] SPD backup: {e}")
                self._ui.toast.emit("error", "SPD backup", str(e))
            finally:
                _flow_end()
                bridge.clear_cancel()
                self._ui.ui.emit(self._spd_reset_ui)

        bridge.clear_cancel()
        self.spd_stop_btn.setEnabled(True)
        self.spd_progress.setVisible(True)
        self.spd_progress.setValue(150)
        threading.Thread(target=work, daemon=True).start()

    # ----------------------------- Battery page --------------------------
    def _build_battery_page(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(_card_qss())
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        lay.addWidget(SectionTitle("BATTERY REPAIR (ADB)"))
        info = QLabel(
            "Diagnose and repair any connected Android device over ADB - no "
            "vendor-specific hardware needed.\n"
            "Works on Samsung, MediaTek (Tecno/Infinix/itel/Redmi...), Qualcomm "
            "and any other phone with USB debugging enabled."
        )
        info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        status_row = QHBoxLayout()
        self.batt_status = QLabel("No device probed yet")
        self.batt_status.setStyleSheet(f"color:{C['dim']}; font-size:12px;")
        status_row.addWidget(self.batt_status, 1)
        lay.addLayout(status_row)

        # three big action cards
        cards = QHBoxLayout()
        cards.setSpacing(12)

        def action_card(title, desc, btn_label, slot, primary=False):
            c = QFrame()
            c.setStyleSheet(
                f"background: {C['inset']}; border: 1px solid {C['border']};"
                f" border-radius: 12px;"
            )
            cv = QVBoxLayout(c)
            cv.setContentsMargins(14, 14, 14, 14)
            cv.setSpacing(10)
            t = QLabel(title)
            t.setStyleSheet(f"color:{C['text']}; font-size:13px; font-weight:800;")
            t.setWordWrap(True)
            cv.addWidget(t)
            d = QLabel(desc)
            d.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
            d.setWordWrap(True)
            cv.addWidget(d)
            cv.addStretch(1)
            b = QPushButton(btn_label)
            b.setStyleSheet(_btn_primary() if primary else _btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            cv.addWidget(b)
            return c

        cards.addWidget(
            action_card(
                "Battery Report",
                "Accurate health % from the fuel gauge, level, temperature, "
                "voltage, current draw and top consumers.",
                "Run Report",
                self._battery_report,
            ),
            1,
        )
        cards.addWidget(
            action_card(
                "Battery Repair",
                "The fixes commercial tools apply: reset battery stats, "
                "Battery Saver, disable scanning, kill background apps, trim "
                "caches, tune screen/animation power.",
                "Repair Battery",
                self._battery_repair,
                primary=True,
            ),
            1,
        )
        cards.addWidget(
            action_card(
                "Load Test",
                "Stress the battery under heavy load and measure voltage sag / "
                "internal resistance to confirm a weak cell.",
                "Start Load Test",
                self._battery_load_test,
            ),
            1,
        )
        lay.addLayout(cards, 1)

        tip = QLabel(
            "Tip: for accurate battery health the device must expose the "
            "fuel-gauge sysfs (charge_full / charge_full_design). Connect the "
            "phone, authorize USB debugging, then run any tool - they work on "
            "any connected device."
        )
        tip.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        return panel

    # ----------------------------- Network page --------------------------
    def _build_network_page(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(_card_qss())
        root_lay = QVBoxLayout(panel)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Scroll wrapper: the page holds a live readout + two action groups, so
        # it must be scrollable rather than crushed into the fixed viewport.
        page_scroll = self._ops_scroll_area()
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(host)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(14)

        lay.addWidget(SectionTitle("NETWORK REPAIR (ADB)"))
        info = QLabel(
            "Diagnose and repair Wi-Fi / mobile data / modem issues on any "
            "connected Android device over ADB.\n"
            "Useful for: no internet, weak signal, stuck on 3G, DNS failures, "
            "SIM not detected after a flash, airplane-mode glitches."
        )
        info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        # --- Live diagnostics readout (updates every 3s while an ADB device
        #     is connected - no need to click anything) ---
        self.net_cards = {}
        net_grid = QGridLayout()
        net_grid.setContentsMargins(0, 0, 0, 0)
        net_grid.setHorizontalSpacing(14)
        net_grid.setVerticalSpacing(12)
        for i, (key, cap) in enumerate(
            (
                ("sim", "SIM STATE"),
                ("net", "NETWORK TYPE"),
                ("mode", "PREFERRED MODE"),
                ("signal", "SIGNAL"),
                ("data", "MOBILE DATA"),
                ("wifi", "WI-FI"),
                ("dns", "PRIVATE DNS"),
                ("airplane", "AIRPLANE MODE"),
            )
        ):
            mc = MetricCard(cap, "--", accent=C["accent"])
            net_grid.addWidget(mc, i // 4, i % 4)
            self.net_cards[key] = mc
        net_grid.setColumnStretch(0, 1)
        net_grid.setColumnStretch(1, 1)
        net_grid.setColumnStretch(2, 1)
        net_grid.setColumnStretch(3, 1)
        lay.addLayout(net_grid)

        status_row = QHBoxLayout()
        self.net_status = QLabel("Live diagnostics update while a device is connected")
        self.net_status.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        status_row.addWidget(self.net_status, 1)
        lay.addLayout(status_row)

        def action_card(title, desc, btn_label, slot, primary=False):
            c = QFrame()
            c.setStyleSheet(
                f"background: {C['inset']}; border: 1px solid {C['border']};"
                f" border-radius: 12px;"
            )
            cv = QVBoxLayout(c)
            cv.setContentsMargins(16, 16, 16, 16)
            cv.setSpacing(10)
            t = QLabel(title)
            t.setStyleSheet(f"color:{C['text']}; font-size:13px; font-weight:800;")
            t.setWordWrap(True)
            cv.addWidget(t)
            d = QLabel(desc)
            d.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
            d.setWordWrap(True)
            cv.addWidget(d)
            cv.addStretch(1)
            b = QPushButton(btn_label)
            b.setStyleSheet(_btn_primary() if primary else _btn_ghost())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            cv.addWidget(b)
            return c

        lay.addWidget(SectionTitle("ACTIONS"))
        cards = QHBoxLayout()
        cards.setSpacing(14)
        cards.addWidget(
            action_card(
                "Network Report",
                "Full report: SIM state, network type, preferred mode, "
                "data/Wi-Fi flags, DNS, IP and radio version - printed to the "
                "console.",
                "Run Report",
                self._network_report,
            ),
            1,
        )
        cards.addWidget(
            action_card(
                "Network Repair",
                "The fixes commercial tools use: reset radios (airplane cycle), "
                "re-enable Wi-Fi/data, restore network mode, clear DNS, flush "
                "phone/telephony caches.",
                "Repair Network",
                self._network_repair,
                primary=True,
            ),
            1,
        )
        cards.addWidget(
            action_card(
                "Mobile Data Reset",
                "Force the modem to re-register: airplane cycle + preferred "
                "network mode + data re-enable. Good for stuck 'No service'.",
                "Reset Modem",
                self._network_modem_reset,
            ),
            1,
        )
        lay.addLayout(cards)

        # --- SIM / carrier lock lives in a collapsible section so the main
        #     view stays open and breathable ---
        lock_body = QWidget()
        lock_body.setStyleSheet("background: transparent;")
        lock_lay = QVBoxLayout(lock_body)
        lock_lay.setContentsMargins(0, 0, 0, 0)
        lock_lay.setSpacing(12)

        lock_info = QLabel(
            "Check the SIM / network lock state on any device (read-only), and "
            "read / back up the modem lock record on MediaTek A05/A06 (BROM).\n"
            "The MTK unlock step never writes without a validated device recipe."
        )
        lock_info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        lock_info.setWordWrap(True)
        lock_lay.addWidget(lock_info)

        lock_cards = QHBoxLayout()
        lock_cards.setSpacing(14)
        lock_cards.addWidget(
            action_card(
                "Carrier Lock Status",
                "Read the SIM / network lock state over ADB on ANY phone "
                "(Samsung, MTK, Qualcomm, UNISOC). Pure read - nothing is "
                "written.",
                "Check Status",
                self._carrier_lock_status,
                primary=True,
            ),
            1,
        )
        lock_cards.addWidget(
            action_card(
                "MTK NVRAM SimLock",
                "A05/A06 (Helio G85): dump the modem NVRAM lock record over the "
                "DA, keep a backup and locate the SimLock record. Recipe-gated "
                "patch.",
                "Read / Backup",
                self._carrier_lock_mtk,
            ),
            1,
        )
        lock_lay.addLayout(lock_cards)

        lay.addWidget(CollapsibleSection(
            "CARRIER / SIM LOCK", lock_body, accent=C["warn"], collapsed=True
        ))

        tip = QLabel(
            "All fixes work over ADB on any connected device (Samsung / MTK / "
            "Qualcomm / any Android). Reversible from the phone's network "
            "settings."
        )
        tip.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        lay.addStretch(1)

        page_scroll.setWidget(host)
        root_lay.addWidget(page_scroll)
        return panel

    # ----------------------------- Settings page --------------------------
    def _build_settings_page(self):
        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(
            _card_qss()
        )
        root_lay = QHBoxLayout(panel)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Left category rail - mirrors the Windows 11 settings sidebar.
        cat = QFrame()
        cat.setStyleSheet(
            f"QFrame {{ background: rgba(12, 17, 25, 170);"
            f" border-right: 1px solid {C['border']}; border-top-left-radius: 14px;"
            f" border-bottom-left-radius: 14px; }}"
        )
        cat.setFixedWidth(172)
        cat_lay = QVBoxLayout(cat)
        cat_lay.setContentsMargins(10, 18, 10, 14)
        cat_lay.setSpacing(4)

        self._settings_pages = QStackedWidget()
        self._settings_pages.setStyleSheet(
            "QStackedWidget { background: transparent; }"
        )
        self._settings_cats = {}

        categories = [
            ("general", "◈", "General",
             self._build_settings_general),
            ("appearance", "✦", "Appearance",
             self._build_settings_appearance),
            ("tools", "▤", "Tools",
             self._build_settings_tools),
            ("about", "ℹ", "About",
             self._build_settings_about),
        ]
        for key, glyph, label, builder in categories:
            page = builder()
            self._settings_pages.addWidget(page)
            btn = _SettingsCatButton(glyph, label)
            btn.clicked.connect(lambda _=False, k=key: self._switch_settings(k))
            cat_lay.addWidget(btn)
            self._settings_cats[key] = btn

        cat_lay.addStretch(1)
        root_lay.addWidget(cat)
        root_lay.addWidget(self._settings_pages, 1)
        self._switch_settings("general")
        return panel

    def _switch_settings(self, key):
        order = {"general": 0, "appearance": 1, "tools": 2, "about": 3}
        idx = order.get(key, 0)
        self._settings_pages.setCurrentIndex(idx)
        for k, btn in self._settings_cats.items():
            btn.set_active(k == key)

    # --- settings helpers -------------------------------------------------
    def _settings_box(self, title, parent_lay):
        box = QFrame()
        box.setObjectName("sbox")
        box.setStyleSheet(
            f"QFrame#sbox {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 {C['card']}, stop:1 {C['inset']});"
            f" border: 1px solid {C['border']}; border-top: 1px solid {C['border_hi']};"
            f" border-radius: 12px; }}"
        )
        bl = QVBoxLayout(box)
        bl.setContentsMargins(14, 12, 14, 12)
        bl.setSpacing(10)
        t = SectionTitle(title)
        bl.addWidget(t)
        parent_lay.addWidget(box)
        return bl

    def _settings_row(self, box_lay, text, detail="", widget=None):
        row = QHBoxLayout()
        row.setSpacing(10)
        col = QVBoxLayout()
        col.setSpacing(1)
        lab = QLabel(text)
        lab.setStyleSheet(f"color:{C['text']}; font-size:12px; font-weight:600;")
        col.addWidget(lab)
        if detail:
            d = QLabel(detail)
            d.setStyleSheet(f"color:{C['mute']}; font-size:10px;")
            d.setWordWrap(True)
            col.addWidget(d)
        row.addLayout(col, 1)
        if widget is not None:
            row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        box_lay.addLayout(row)
        return row

    def _settings_switch(self):
        cb = QCheckBox()
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        cb.setStyleSheet(
            f"QCheckBox::indicator {{ width:36px; height:20px; }}"
            f" QCheckBox::indicator:unchecked {{"
            f"  image: none; background: {C['border']}; border-radius: 10px;"
            f"  border: 1px solid {C['border_hi']}; }}"
            f" QCheckBox::indicator:checked {{"
            f"  image: none; background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"   stop:0 {C['grad_a']}, stop:1 {C['grad_b']}); border-radius: 10px;"
            f"  border: 1px solid {C['accent_hi']}; }}"
        )
        return cb

    # --- General -----------------------------------------------------------
    def _build_settings_general(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        bl = self._settings_box("SCAN & BEHAVIOUR", lay)
        self._s_interval = QSpinBox()
        self._s_interval.setRange(1, 30)
        self._s_interval.setSuffix(" s")
        self._s_interval.setValue(int(self.settings.value("scan_interval", 3)))
        self._s_interval.valueChanged.connect(self._apply_scan_interval)
        self._settings_row(
            bl, "USB / ADB auto-scan interval",
            "How often the app re-checks the USB bus for connected devices.",
            self._s_interval,
        )
        self._s_autoscan = self._settings_switch()
        self._s_autoscan.setChecked(
            self.settings.value("autoscan", "true", type=bool)
        )
        self._s_autoscan.toggled.connect(self._apply_autoscan)
        self._settings_row(
            bl, "Auto-scan on startup",
            "Begin monitoring devices immediately when the app opens.",
            self._s_autoscan,
        )
        self._s_toast = self._settings_switch()
        self._s_toast.setChecked(self.settings.value("toasts", "true", type=bool))
        self._s_toast.toggled.connect(self._apply_toasts)
        self._settings_row(
            bl, "Desktop notifications",
            "Show a toast when a device connects or disconnects.",
            self._s_toast,
        )

        bl = self._settings_box("DEFAULT PATHS", lay)
        self._s_dir_row = QHBoxLayout()
        self._s_dir = QLineEdit(
            self.settings.value("default_dir", os.path.expanduser("~/Downloads"))
        )
        self._s_dir.setStyleSheet(
            f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:6px 10px; color:{C['text']}; }}"
        )
        dir_btn = QPushButton("Browse...")
        dir_btn.setStyleSheet(_btn_ghost())
        dir_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dir_btn.clicked.connect(self._pick_default_dir)
        self._s_dir_row.addWidget(self._s_dir, 1)
        self._s_dir_row.addWidget(dir_btn)
        bl.addLayout(self._s_dir_row)
        self._s_dir.editingFinished.connect(self._apply_default_dir)

        bl = self._settings_box("FLASHING", lay)
        self._s_clear = self._settings_switch()
        self._s_clear.setChecked(
            self.settings.value("clear_on_run", "false", type=bool)
        )
        self._s_clear.toggled.connect(self._apply_clear_on_run)
        self._settings_row(
            bl, "Clear console before each run",
            "Automatically empty the log when you start an operation.",
            self._s_clear,
        )

        lay.addStretch(1)
        return page

    def _pick_default_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Default working folder", self._s_dir.text() or os.path.expanduser("~/Downloads")
        )
        if d:
            self._s_dir.setText(d)
            self._apply_default_dir()

    def _apply_default_dir(self):
        self.settings.setValue("default_dir", self._s_dir.text())
        self._ui.line.emit(f"[settings] default dir -> {self._s_dir.text()}")

    def _apply_scan_interval(self, v):
        self.settings.setValue("scan_interval", int(v))
        self._monitor.set_interval(int(v))

    def _apply_autoscan(self, on):
        self.settings.setValue("autoscan", on)
        if on:
            self._monitor.start()
        else:
            self._monitor.stop()

    def _apply_toasts(self, on):
        self.settings.setValue("toasts", on)
        self._toasts.setEnabled(on)

    def _apply_clear_on_run(self, on):
        self.settings.setValue("clear_on_run", on)
        if getattr(self, "clear_on_run", None) is not None:
            self.clear_on_run.setChecked(on)

    # --- Appearance --------------------------------------------------------
    def _build_settings_appearance(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        bl = self._settings_box("THEME", lay)
        self._s_theme = QComboBox()
        self._s_theme.addItems(list(ACCENT_THEMES))
        self._s_theme.setCurrentText(
            self.settings.value("theme", "Cobalt Blue")
        )
        self._style_combo(self._s_theme)
        self._s_theme.currentTextChanged.connect(self._apply_theme)
        self._settings_row(
            bl, "Accent theme",
            "Colour pack used across buttons, gradients and highlights.",
            self._s_theme,
        )

        bl = self._settings_box("EFFECTS", lay)
        self._s_anim = self._settings_switch()
        self._s_anim.setChecked(self.settings.value("animations", "true", type=bool))
        self._s_anim.toggled.connect(self._apply_animations)
        self._settings_row(
            bl, "Animated effects",
            "Live cable pulse, status orb and shimmer sweeps.",
            self._s_anim,
        )
        self._s_blur = self._settings_switch()
        self._s_blur.setChecked(self.settings.value("blur", "true", type=bool))
        self._s_blur.toggled.connect(self._apply_blur)
        self._settings_row(
            bl, "Window glow / shadow",
            "Drop shadow and halo around the main window.",
            self._s_blur,
        )

        lay.addStretch(1)
        return page

    def _apply_theme(self, name):
        self.settings.setValue("theme", name)
        if name in ACCENT_THEMES:
            C.update(ACCENT_THEMES[name])
            self._rebuild_theme()
        self._ui.line.emit(f"[settings] theme -> {name}")

    def _rebuild_theme(self):
        self._toasts.show_ok("Theme applied", "Restyled accent & gradients")
        self.setStyleSheet(_BASE_QSS + _console_qss())
        for combo in (self._s_theme,):
            self._style_combo(combo)

    def _apply_animations(self, on):
        self.settings.setValue("animations", on)
        self._anim_enabled = bool(on)
        for w in (self.scene, self.orb):
            w.set_animations(bool(on))

    def _apply_blur(self, on):
        self.settings.setValue("blur", on)
        if self._root_shadow is not None:
            self._root_shadow.setEnabled(bool(on))

    # --- Tools --------------------------------------------------------------
    def _build_settings_tools(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        bl = self._settings_box("ENGINE", lay)
        rows = [
            ("Engine", "Rust core (flashpilot-bridge) + PyQt6 shell"),
            ("Bridge binary", str(bridge.BRIDGE)),
            ("Bridge built", "yes" if bridge.BRIDGE.exists()
             else "no (run `cargo build --release`)"),
            ("ADB available", "yes" if bridge.has_adb() else "no (adb not on PATH)"),
        ]
        for label, value in rows:
            row = QHBoxLayout()
            lab = QLabel(label)
            lab.setStyleSheet(f"color:{C['dim']}; font-weight:600; min-width:110px;")
            val = QLabel(value)
            val.setStyleSheet(f"color:{C['text']}; font-size:12px;")
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(lab)
            row.addWidget(val, 1)
            bl.addLayout(row)

        bl = self._settings_box("ACTIONS", lay)
        act = QHBoxLayout()
        act.setSpacing(10)
        b1 = QPushButton("Rebuild bridge (cargo)")
        b1.setStyleSheet(_btn_ghost())
        b1.setCursor(Qt.CursorShape.PointingHandCursor)
        b1.clicked.connect(self._rebuild_bridge)
        act.addWidget(b1)
        b2 = QPushButton("Open log folder")
        b2.setStyleSheet(_btn_ghost())
        b2.setCursor(Qt.CursorShape.PointingHandCursor)
        b2.clicked.connect(self._open_log_dir)
        act.addWidget(b2)
        b3 = QPushButton("Reset all settings")
        b3.setStyleSheet(_btn_danger())
        b3.setCursor(Qt.CursorShape.PointingHandCursor)
        b3.clicked.connect(self._reset_settings)
        act.addWidget(b3)
        act.addStretch(1)
        bl.addLayout(act)

        lay.addStretch(1)
        return page

    def _rebuild_bridge(self):
        def work():
            self._ui.line.emit("[build] cargo build --release ...")
            rc = os.system("cd %s && cargo build --release 2>&1" % (
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            ))
            self._ui.line.emit(
                f"[build] {'OK' if rc == 0 else f'FAILED (rc={rc})'}"
            )
            self._ui.toast.emit(
                "ok", "Bridge build", "Succeeded" if rc == 0 else "Failed - see console"
            )
        threading.Thread(target=work, daemon=True).start()

    def _open_log_dir(self):
        os.system('xdg-open "%s" 2>/dev/null' % os.path.expanduser("~/Downloads"))

    def _reset_settings(self):
        self.settings.clear()
        self._toasts.show_info("Settings reset", "Values restored to defaults")
        self._switch_settings("general")

    # --- About --------------------------------------------------------------
    def _build_settings_about(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        card = QFrame()
        card.setObjectName("aboutcard")
        card.setStyleSheet(
            f"QFrame#aboutcard {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f" stop:0 rgba(37, 99, 235, 26), stop:1 rgba(6, 182, 212, 18));"
            f" border: 1px solid {C['border']}; border-top: 1px solid {C['border_hi']};"
            f" border-radius: 14px; }}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 22, 20, 22)
        cl.setSpacing(6)
        logo = QLabel()
        logo.setPixmap(_draw_logo(56))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(logo)
        name = QLabel("flashpilot FLASHING TOOL")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet(
            f"color:{C['text']}; font-size:17px; font-weight:800; letter-spacing:1px;"
        )
        cl.addWidget(name)
        ver = QLabel("Version 1.2  ·  Rust core + PyQt6")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        cl.addWidget(ver)
        tag = QLabel(
            "Samsung · MediaTek · Qualcomm low-level flashing & repair\n"
            "FRP bypass · screen-lock removal · download-mode tooling"
        )
        tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tag.setStyleSheet(f"color:{C['mute']}; font-size:10px;")
        cl.addWidget(tag)
        lay.addWidget(card)

        bl = self._settings_box("SHORTCUTS", lay)
        for k, d in (
            ("F5", "Re-scan USB / ADB"),
            ("Ctrl+Enter", "Run the selected operation"),
            ("Ctrl+L", "Clear console"),
            ("Ctrl+S", "Save console log"),
            ("Ctrl+F", "Find in console"),
        ):
            row = QHBoxLayout()
            chip = QLabel(k)
            chip.setStyleSheet(
                f"color:{C['dim']}; font-weight:700; font-size:10px;"
                f" background:{C['card_hover']}; border:1px solid {C['border']};"
                f" border-radius:6px; padding:3px 8px;"
            )
            chip.setFixedWidth(90)
            desc = QLabel(d)
            desc.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
            row.addWidget(chip)
            row.addWidget(desc, 1)
            bl.addLayout(row)

        lay.addStretch(1)
        return page

    @staticmethod
    def _field_label(text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{C['mute']}; font-size:11px; font-weight:700; letter-spacing:1px;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        return lbl

    def _tool_button(self, text, slot):
        btn = QPushButton(text)
        btn.setStyleSheet(_btn_ghost())
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(slot)
        return btn

    def _style_combo(self, combo):
        """Force a dark, premium dropdown popup regardless of platform."""
        combo.setCursor(Qt.CursorShape.PointingHandCursor)
        combo.setMaxVisibleItems(8)
        view = combo.view()
        view.setStyleSheet(
            f"QListView {{ background:{C['panel']}; color:{C['text']};"
            f" border:1px solid {C['border_hi']}; border-radius:8px;"
            f" outline:0; padding:4px; }}"
        )
        pal = view.palette()
        pal.setColor(QPalette.ColorRole.Base, QColor(C["panel"]))
        pal.setColor(QPalette.ColorRole.Window, QColor(C["panel"]))
        pal.setColor(QPalette.ColorRole.Text, QColor(C["text"]))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(C["text"]))
        pal.setColor(QPalette.ColorRole.Button, QColor(C["card"]))
        pal.setColor(QPalette.ColorRole.Highlight, QColor(C["accent_dim"]))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(C["accent_hi"]))
        view.setPalette(pal)
        combo.setItemDelegate(_ComboItemDelegate(view))

    def _toggle_max(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            maximized = self.isMaximized()
            if maximized:
                self._outer.setContentsMargins(0, 0, 0, 0)
                self._root_shadow.setEnabled(False)
            else:
                self._outer.setContentsMargins(30, 26, 30, 34)
                self._root_shadow.setEnabled(True)

    # ----------------------------- UI helpers -----------------------------
    # ----------------------------- console engine --------------------------
    # Levels: 'err' | 'warn' | 'ok' | 'info'
    _LEVEL_COLOR = {"err": C["err"], "warn": C["warn"], "ok": C["ok"], "info": C["text"]}

    def _classify(self, msg):
        m = msg.strip()
        if (
            m.startswith("[error]")
            or m.startswith("[cancelled]")
            or m.startswith("[FAILED]")
            or "bridge error" in m
            or m.startswith("[err]")
        ):
            return "err"
        if (
            m.startswith("[step]")
            or "not authorized" in m
            or "timeout" in m.lower()
            or "NOT switching" in m
            or "NOT FOUND" in m
            or "WARNING" in m
            or "does not answer" in m
        ):
            return "warn"
        if (
            m.startswith("[done]")
            or m.startswith("Done")
            or m.startswith("Flow completed")
            or m.startswith("adb device online")
            or m.startswith("ADB: device")
            or "reconnected" in m
            or m == "OK"
        ):
            return "ok"
        return "info"

    def log_line(self, msg):
        level = self._classify(msg)
        self._log_buffer.append((level, msg))
        if len(self._log_buffer) > 6000:
            del self._log_buffer[:-2000]
        if self._filter.get(level, True):
            self._append_to_widget(level, msg)
            if self.find_edit.text():
                self._apply_find()
        self._update_count()

    def _append_to_widget(self, level, msg):
        stamp = _time.strftime("%H:%M:%S")
        fmt = QTextCharFormat()
        m = msg.strip()
        if level == "err":
            fmt.setForeground(QColor(C["err"]))
        elif level == "warn":
            fmt.setForeground(QColor(C["warn"]))
        elif level == "ok":
            fmt.setForeground(QColor(C["ok"]))
        elif m.startswith(">>> ") or m.startswith("== running flow:") or m.startswith("== flow finished:"):
            fmt.setForeground(QColor(C["accent_hi"]))
            fmt.setFontWeight(QFont.Weight.DemiBold)
        else:
            fmt.setForeground(QColor(C["text"]))

        self.log.appendPlainText(f"[{stamp}] {msg}")
        cur = self.log.textCursor()
        cur.movePosition(cur.MoveOperation.StartOfLine)
        cur.movePosition(cur.MoveOperation.EndOfLine, cur.MoveMode.KeepAnchor)
        cur.mergeCharFormat(fmt)
        self.log.setTextCursor(cur)

    def _set_filter(self, level, checked):
        self._filter[level] = checked
        self._rebuild_console()

    def _rebuild_console(self):
        """Re-render the console respecting the level filters."""
        self.log.clear()
        for level, msg in self._log_buffer:
            if self._filter.get(level, True):
                self._append_to_widget(level, msg)
        self._update_count()
        self._apply_find()

    def _update_count(self):
        self.console_count.setText(f"{len(self._log_buffer)} lines")

    def _clear_console(self):
        self._log_buffer.clear()
        self.log.clear()
        self._update_count()

    def _copy_console(self):
        QApplication.clipboard().setText(self.log.toPlainText())
        self.set_status("Console copied to clipboard")

    def _save_console(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save console log", "samsung-console.log", "Log files (*.log);;Text (*.txt);;All files (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(m for _, m in self._log_buffer))
            self.set_status(f"Console saved: {path}")

    def _toggle_wrap(self):
        wrapping = self.log.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth
        self.log.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.NoWrap
            if wrapping
            else QPlainTextEdit.LineWrapMode.WidgetWidth
        )
        self.wrap_btn.setText("Wrap" if wrapping else "NoWrap")

    def _apply_find(self):
        selections = []
        text = self.find_edit.text()
        if text:
            doc = self.log.document()
            cursor = QTextCursor(doc)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(C["warn_dim"]))
            fmt.setForeground(QColor(C["warn"]))
            while not cursor.isNull() and not cursor.atEnd():
                cursor = doc.find(text, cursor)
                if cursor.isNull():
                    break
                sel = QTextEdit.ExtraSelection()
                sel.cursor = cursor
                sel.format = fmt
                selections.append(sel)
        self.log.setExtraSelections(selections)

    def _find_nav(self, direction):
        text = self.find_edit.text()
        if not text:
            return
        doc = self.log.document()
        cur = self.log.textCursor()
        if direction > 0:
            found = doc.find(text, cur)
            if found.isNull():
                found = doc.find(text, QTextCursor(doc))
        else:
            start = QTextCursor(doc)
            start.setPosition(cur.selectionStart())
            found = doc.find(text, start, QTextDocument.FindFlag.FindBackward)
            if found.isNull():
                c = QTextCursor(doc)
                c.movePosition(QTextCursor.MoveOperation.End)
                found = doc.find(text, c, QTextDocument.FindFlag.FindBackward)
        if not found.isNull():
            self.log.setTextCursor(found)

    def set_status(self, msg):
        self.status.setText(msg)

    def _set_metric(self, name, value):
        if name in self.info:
            self.info[name].set(value)

    def _show_qr_dialog(self, data):
        """Pop a dark-themed dialog showing the generated provisioning QR(s).

        `data` is either a single PNG path or a list of (label, path) pairs;
        with several QRs a dropdown lets the operator switch between them.
        """
        import os

        if isinstance(data, (list, tuple)) and data and isinstance(data[0], (list, tuple)):
            qrs = [(str(lbl), str(path)) for lbl, path in data]
        elif isinstance(data, (list, tuple)):
            qrs = [("QR code", str(p)) for p in data]
        elif data:
            qrs = [("QR code", str(data))]
        else:
            qrs = []
        if not qrs:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("MDM provisioning QR code")
        dlg.setModal(False)
        dlg.setMinimumSize(360, 520)
        dlg.setStyleSheet(f"background:{C['panel']}; color:{C['text']};")

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        if len(qrs) > 1:
            sel = QComboBox()
            for lbl, _path in qrs:
                sel.addItem(lbl, _path)
            self._style_combo(sel)
            lay.addWidget(sel)
        else:
            sel = None

        img = QLabel()
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setStyleSheet("background:#ffffff; border-radius:10px;")
        lay.addWidget(img)

        hint = QLabel()
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{C['dim']}; font-size:12px;")

        path_lbl = QLabel()
        path_lbl.setWordWrap(True)
        path_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_lbl.setStyleSheet(
            f"color:{C['mute']}; font-size:10px; font-family:monospace;"
        )

        hints = {
            "unenroll_testdpc":
                "Scans as a NEUTRAL controller (Test DPC). Enrolls the phone with "
                "the benign Test DPC instead of the corporate MDM - effectively "
                "removing the management after a factory reset.",
            "google":
                "Google's demo DPC (oobconfig). Provisions the device as a normal "
                "Google-managed device - the default choice for a fresh setup.",
            "custom":
                "Your custom DPC component from MDM_DPC_COMPONENT.",
        }

        def show(index=0):
            path = sel.itemData(index) if sel else qrs[0][1]
            pix = QPixmap(path)
            if not pix.isNull():
                pix = pix.scaled(
                    300, 300,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                img.setPixmap(pix)
                img.setVisible(True)
            else:
                img.clear()
                img.setVisible(False)
                hint.setText(f"Could not load QR image:\n{path}")
                path_lbl.setText(path)
                return
            name = (sel.itemText(index) if sel else qrs[0][0]).lower()
            hint.setText(
                "Scan this QR from the phone's setup wizard (4-dot grid / "
                "'QR code' button) to provision the device.\n\n"
                + hints.get(name, "")
            )
            path_lbl.setText(path)

        if sel is not None:
            sel.currentIndexChanged.connect(show)
        lay.addWidget(hint)
        lay.addWidget(path_lbl)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(_btn_primary())
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn)

        dlg.show()
        show(sel.currentIndex() if sel else 0)

    def _on_finished(self):
        self.stop_btn.setEnabled(False)
        self.shimmer.set_active(False)
        self.shimmer.setVisible(False)
        self._accent_strip.set_active(False)

    def _show_toast(self, kind, title, detail):
        getattr(self._toasts, f"show_{kind}")(title, detail)

    def _run_on_ui(self, fn):
        fn()

    # ----------------------------- device state ---------------------------
    def _on_device_state(self, state):
        if "error" in state:
            self.badge.set_state(None)
            self.orb.set_connected(False)
            self.scene.set_connected(False)
            self.scene.set_vendor(None)
            self._set_conn_glow(C["border_hi"])
            self.conn_state.setText(f"Scan error: {state['error']}")
            self._update_device_info(False, None, None)
            return
        samsung = state["samsung"]
        mtk_devs = state.get("mtk", [])
        fastboot = state.get("fastboot", [])
        edl_devs = state.get("edl", [])
        qcom_devs = state.get("qcom", [])
        spd_devs = state.get("spd", [])
        adb_devs = state.get("adb", [])
        mode = state["mode"]
        self.badge.set_state(mode)
        self._last_spd_target = (
            f"{spd_devs[0]['bus']}:{spd_devs[0]['address']}" if spd_devs else None
        )
        connected_any = bool(fastboot or samsung or mtk_devs or edl_devs or qcom_devs or spd_devs)
        self._accent_strip.set_active(connected_any)

        # toast on connect / disconnect transitions
        if connected_any and not getattr(self, "_last_conn", False):
            self._toasts.show_ok("Device connected", mode or "USB device detected")
        elif not connected_any and getattr(self, "_last_conn", False):
            self._toasts.show_info("Device disconnected")
        self._last_conn = connected_any

        # Any connected low-level/composite device gets the live animation;
        # only a truly empty bus stays disconnected.
        if fastboot:
            d = fastboot[0]
            self.orb.set_connected(True)
            self.scene.set_connected(True)
            self.scene.set_vendor("FASTBOOT", C["warn"])
            self._set_conn_glow(C["warn"])
            self.conn_state.setText(
                f"18d1:{d['pid']:04x}\nbus {d['bus']} · addr {d['address']}"
            )
            self.conn_state.setStyleSheet(
                f"color:{C['warn']}; font-size:12px; font-weight:600; background:transparent;"
            )
            self._update_device_info(True, d["pid"], mode)
        elif samsung:
            first = samsung[0]
            self.orb.set_connected(True)
            self.scene.set_connected(True)
            self.scene.set_vendor("SAMSUNG", C["ok"])
            self._set_conn_glow(C["ok"])
            self.conn_state.setText(
                f"04e8:{first['pid']:04x}\nbus {first['bus']} · addr {first['address']}"
            )
            self.conn_state.setStyleSheet(
                f"color:{C['ok']}; font-size:12px; font-weight:600; background:transparent;"
            )
            self._update_device_info(True, first["pid"], mode)
        elif "RECOVERY" in mode.upper():
            rec = [d for d in adb_devs if d["state"] in ("recovery", "sideload")]
            serial = rec[0]["serial"] if rec else "unknown"
            self.orb.set_connected(True)
            self.scene.set_connected(True)
            self.scene.set_vendor("RECOVERY", C["warn"])
            self._set_conn_glow(C["warn"])
            self.conn_state.setText(f"adb {rec[0]['state'] if rec else 'recovery'}\n{serial}")
            self.conn_state.setStyleSheet(
                f"color:{C['warn']}; font-size:12px; font-weight:600; background:transparent;"
            )
            self._update_device_info(True, None, mode)
        elif edl_devs:
            d = edl_devs[0]
            pid = d.get("pid")
            self.orb.set_connected(True)
            self.scene.set_connected(True)
            self.scene.set_vendor("QUALCOMM EDL", C["err"])
            self._set_conn_glow(C["err"])
            self.conn_state.setText(
                f"05c6:{pid:04x} · EDL\nbus {d['bus']} · addr {d['address']}"
            )
            self.conn_state.setStyleSheet(
                f"color:{C['err']}; font-size:12px; font-weight:600; background:transparent;"
            )
            self._update_device_info(True, pid, mode)
        elif qcom_devs:
            d = qcom_devs[0]
            pid = d.get("pid")
            self.orb.set_connected(True)
            self.scene.set_connected(True)
            self.scene.set_vendor("QUALCOMM", C["warn"])
            self._set_conn_glow(C["warn"])
            self.conn_state.setText(
                f"05c6:{pid:04x} · Qualcomm device\nbus {d['bus']} · addr {d['address']}"
            )
            self.conn_state.setStyleSheet(
                f"color:{C['warn']}; font-size:12px; font-weight:600; background:transparent;"
            )
            self._update_device_info(True, pid, mode)
        elif spd_devs:
            d = spd_devs[0]
            pid = d.get("pid")
            spd_label = _spd_mode(d) or "SPREADTRUM DEVICE"
            self.orb.set_connected(True)
            self.scene.set_connected(True)
            self.scene.set_vendor("SPREADTRUM", C["warn"])
            self._set_conn_glow(C["warn"])
            self.conn_state.setText(
                f"1782:{pid:04x} · {spd_label}\nbus {d['bus']} · addr {d['address']}"
            )
            self.conn_state.setStyleSheet(
                f"color:{C['warn']}; font-size:12px; font-weight:600; background:transparent;"
            )
            self._update_device_info(True, pid, mode)
        elif mtk_devs:
            d = mtk_devs[0]
            pid = d.get("pid")
            stage = {0x2000: "MediaTek BROM", 0x0003: "MediaTek Preloader",
                     0x0004: "MediaTek Download Agent"}.get(pid, "MediaTek low-level")
            self.orb.set_connected(True)
            self.scene.set_connected(True)
            mfr = (d.get("manufacturer") or "").lower()
            prod = (d.get("product") or "").lower()
            is_samsung_mtk = "samsung" in mfr or "samsung" in prod
            if is_samsung_mtk:
                self.scene.set_vendor("SAMSUNG (MTK)", C["warn"])
            else:
                self.scene.set_vendor("MEDIATEK", C["warn"])
            self._set_conn_glow(C["warn"])
            self.conn_state.setText(
                f"0e8d:{pid:04x} · {stage}\nbus {d['bus']} · addr {d['address']}"
            )
            self.conn_state.setStyleSheet(
                f"color:{C['warn']}; font-size:12px; font-weight:600; background:transparent;"
            )
            self._update_device_info(True, pid, mode)
        elif adb_devs:
            auth_adb = [d for d in adb_devs if d["state"] == "device"]
            d = auth_adb[0] if auth_adb else adb_devs[0]
            serial = d.get("serial", "unknown")
            self.orb.set_connected(True)
            self.scene.set_connected(True)
            brand = "ADB DEVICE"
            if self._cached_model:
                parts = self._cached_model.split()
                brand = parts[0].upper()
            self.scene.set_vendor(brand, C["ok"] if auth_adb else C["warn"])
            self._set_conn_glow(C["ok"] if auth_adb else C["warn"])
            state_str = "connected" if auth_adb else d.get("state", "connected")
            self.conn_state.setText(f"ADB · {state_str}\n{serial}")
            self.conn_state.setStyleSheet(
                f"color:{C['ok'] if auth_adb else C['warn']}; font-size:12px; font-weight:600; background:transparent;"
            )
            self._update_device_info(True, None, mode)
        else:
            self.orb.set_connected(False)
            self.scene.set_connected(False)
            self.scene.set_vendor(None)
            self._set_conn_glow(C["border_hi"])
            self.conn_state.setText("No device connected")
            self.conn_state.setStyleSheet(
                f"color:{C['dim']}; font-size:12px; background:transparent;"
            )
            self._update_device_info(False, None, None)

    def _update_device_info(self, connected, pid, mode):
        if not connected:
            self._cached_model = None
            self._cached_adb_status = None
            self._update_in_progress = False
            self._last_pid = None
            for name in self.info:
                self.info[name].set("--")
            return

        self._last_pid = pid
        self.info["Device Model"].set(
            self._cached_model
            if self._cached_model is not None
            else ("0x%04x" % pid if pid is not None else "adb device")
        )
        self.info["USB Mode"].set((mode or "--")[:40])
        self.info["Interface"].set("USB")
        self._refresh_model_and_adb()

    def _refresh_model_and_adb(self):
        """Background probe for the real model + adb state. Reruns on a timer
        so it picks up the phone's 'Allow USB debugging' acceptance without
        needing a USB re-enumeration."""
        if self._update_in_progress:
            return
        if not self._last_pid:
            return
        self._update_in_progress = True
        pid = self._last_pid
        current_adb = self.info["ADB Status"].value.text()
        # Only show a transient "Checking..." on the first resolution; keep the
        # last known value afterwards so the metric does not flicker every poll.
        if self._cached_adb_status is None and not current_adb.startswith("Connected"):
            self.info["ADB Status"].set("Checking...")

        def work():
            model = ""
            adb_status = "Not connected"
            try:
                adb_devs = bridge.adb_status()
                authorized = [d for d in adb_devs if d["state"] == "device"]
                if authorized:
                    serial = authorized[0]["serial"]
                    adb_status = f"Connected ({serial})"
                    try:
                        model = bridge.adb_shell(
                            "getprop ro.product.model", timeout=8
                        ).strip()
                        mfr = bridge.adb_shell(
                            "getprop ro.product.manufacturer", timeout=8
                        ).strip()
                        brand = bridge.adb_shell(
                            "getprop ro.product.brand", timeout=8
                        ).strip()
                    except bridge.BridgeError:
                        model = ""
                        mfr = ""
                        brand = ""
                    if model and model != self._cached_model:
                        self._cached_model = model
                        self._ui.line.emit(f"Device Model: {model}")
                    # Update vendor badge with model name (e.g., "TECNO KG6")
                    display_name = model or (mfr or brand)
                    if display_name and display_name.lower() != "samsung":
                        self._ui.metric.emit("Vendor", display_name)
                        # Update the scene vendor badge above the phone
                        if hasattr(self, "scene") and self.scene:
                            self.scene.set_vendor(display_name.upper(), C["ok"])
                    if self._cached_adb_status != adb_status:
                        self._cached_adb_status = adb_status
                        self._ui.line.emit(f"ADB: {serial}")
                elif any(d["state"] == "unauthorized" for d in adb_devs):
                    adb_status = "Unauthorized - tap Allow"
                    self._ui.line.emit(
                        "ADB: device present but NOT authorized - tap Allow on the phone"
                    )
                else:
                    # No ADB transport. If the device exposes the diag AT port,
                    # the model may still be readable via AT+DEVCONINFO while in
                    # test mode (*#0*#) - try it before falling back to the pid.
                    try:
                        if mtp.is_diag_config(mtp.find_samsung() or {}):
                            model = mtp.read_model_via_at(timeout_ms=5000)
                            if model and model != self._cached_model:
                                self._cached_model = model
                                self._ui.line.emit(
                                    f"Device Model: {model} (via AT channel)"
                                )
                    except Exception:  # noqa: BLE001
                        pass
                self._cached_adb_status = adb_status
                self._ui.metric.emit(
                    "Device Model", model or self._cached_model or f"0x{pid:04x}"
                )
                self._ui.metric.emit("ADB Status", adb_status)
            except bridge.BridgeError:
                self._ui.metric.emit("ADB Status", "Error")
            finally:
                self._update_in_progress = False

        threading.Thread(target=work, daemon=True).start()

    def _poll_adb_metric(self):
        if self._last_pid:
            self._refresh_model_and_adb()

    def closeEvent(self, event):
        self._monitor.stop()
        self._adb_timer.stop()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_toasts"):
            self._toasts._relayout()

    # ----------------------------- device scan ----------------------------
    def refresh_device(self):
        def work():
            lines = []
            try:
                usb = bridge.detect_usb()
                hid = bridge.list_samsung_hid()
            except bridge.BridgeError as e:
                self._ui.status.emit(f"bridge error: {e}")
                return

            samsung = [d for d in usb if d.get("is_samsung")]
            mtk_devs = [d for d in usb if d.get("vid") == mtk.MTK_VID]
            fastboot = [d for d in usb if _is_fastboot(d)]
            try:
                adb_devs = bridge.adb_status()
            except bridge.BridgeError as e:
                self._ui.status.emit(f"adb unavailable: {e}")
                adb_devs = []
            if fastboot:
                lines.append("FASTBOOT USB DEVICE(S):")
                for d in fastboot:
                    lines.extend(_fmt_usb_full(d))
                lines.append("")
                lines.append(f">>> MODE: {_detect_mode([], [], adb_devs, fastboot)}")
                lines.append(
                    "  Fastboot mode - can flash partitions / clear FRP via fastboot"
                )
            elif samsung:
                lines.append("SAMSUNG USB DEVICE(S):")
                for d in samsung:
                    lines.extend(_fmt_usb_full(d))
                lines.append("")
                mode = _detect_mode(samsung, mtk_devs, adb_devs, fastboot)
                lines.append(f">>> MODE: {mode}")
                if "DIAG" in mode and not any(
                    i["class"] == 255 and i["subclass"] == 66
                    for d in samsung for i in d["interfaces"]
                ):
                    lines.append(
                        "  model hint: AT+DEVCONINFO only answers inside test mode "
                        "(*#0*# from the Emergency call dialer), or enable USB "
                        "debugging for ADB getprop"
                    )
            elif mtk_devs:
                d = mtk_devs[0]
                mfr = (d.get("manufacturer") or "").lower()
                prod = (d.get("product") or "").lower()
                is_samsung_mtk = "samsung" in mfr or "samsung" in prod
                if is_samsung_mtk:
                    lines.append("SAMSUNG (MTK) DEVICE(S):")
                else:
                    lines.append("MEDIATEK DEVICE(S):")
                for d in mtk_devs:
                    lines.extend(_fmt_usb_full(d))
                lines.append("")
                mode = _detect_mode([], mtk_devs, adb_devs, fastboot)
                lines.append(f">>> MODE: {mode}")
                if is_samsung_mtk:
                    lines.append(
                        "  Samsung MTK models (Galaxy A05/A06) enumerate as MediaTek "
                        "0e8d in BROM / preloader / DA. Flash them from the FLASH tab "
                        "(Odin) or use MTK Tools for DA-level operations."
                    )
                else:
                    lines.append(
                        "  MediaTek low-level device detected. Use MTK Tools / BROM operations."
                    )
            else:
                lines.append("No Samsung device over USB (plug it in, check cable/port)")

            if hid:
                lines.append("HID targets (download mode):")
                for t in hid:
                    lines.append(
                        f"   {t['label']} iface={t['interface']} "
                        f"in=0x{t['in_ep']:02x} out=0x{t['out_ep']:02x}"
                    )
            else:
                lines.append("No HID interface exposed (not in download mode?)")

            lines.append("")
            if adb_devs:
                lines.append("ADB transport(s):")
                for d in adb_devs:
                    lines.append(
                        f"   {d.get('serial', '?')} [{d.get('state', '?')}]"
                        f"{'  ' + d.get('model', '') if d.get('model') else ''}"
                    )
            lines.append("")
            try:
                sam = mtp.find_samsung()
                if sam:
                    lines.append(
                        f"AT/control: Samsung pid={sam['pid']:04x} reachable -> "
                        f"switch_to_diag() exposes the AT port"
                    )
                else:
                    lines.append("AT/control: no Samsung device for AT channel")
            except mtp.MtpError as e:
                lines.append(f"AT/control: error - {e}")

            self._ui.line.emit("\n".join(lines))

        threading.Thread(target=work, daemon=True).start()

    # ----------------------------- battery repair --------------------------
    def _battery_report(self):
        """ADB battery diagnostics with accurate health estimation: reads the
        fuel-gauge sysfs (charge_full / charge_full_design -> health %), plus
        dumpsys battery / batteryproperties and top consumers."""
        def _sysfs(path):
            try:
                return bridge.adb_shell(f"cat {path}", timeout=8).strip()
            except bridge.BridgeError:
                return None
            except Exception:  # noqa: BLE001
                return None

        def _health_desc(pct):
            if pct is None:
                return None
            if pct >= 90:
                return "Excellent"
            if pct >= 80:
                return "Good"
            if pct >= 70:
                return "Fair - degrading, may need replacement soon"
            if pct >= 50:
                return "Poor - significant capacity loss"
            return "Critical - replace the battery"

        def work():
            try:
                devs = bridge.adb_status()
                auth = [d for d in devs if d["state"] == "device"]
                if not auth:
                    self._ui.line.emit(
                        "[warn] Battery report needs an authorized ADB device - "
                        "enable USB debugging and tap Allow"
                    )
                    self._ui.toast.emit(
                        "warn", "No ADB device", "Connect + authorize the phone"
                    )
                    return
                lines = ["=== Battery Report ==="]

                # -- fuel gauge (accurate health) --
                charge_full = _sysfs("/sys/class/power_supply/battery/charge_full")
                charge_design = _sysfs(
                    "/sys/class/power_supply/battery/charge_full_design"
                )
                lines.append("--- Fuel gauge (sysfs) ---")
                health = None
                cf_mah = None
                cd_mah = None
                try:
                    if charge_full and charge_design:
                        cf = int(charge_full)
                        cd = int(charge_design)
                        # Device units vary: charge_full is normally µAh but
                        # some kernels report charge_full_design scaled (mAh,
                        # x10µAh, etc.). Try plausible interpretations and pick
                        # the one that yields a sane health % (30..120).
                        best = None
                        for cf_u in (cf, cf * 1000):
                            for cd_u in (cd, cd * 10, cd * 100, cd * 1000, cd / 10):
                                if cd_u <= 0:
                                    continue
                                pct = cf_u / cd_u * 100.0
                                if 30.0 <= pct <= 120.0:
                                    if best is None or abs(pct - 100) < abs(best - 100):
                                        best = pct
                                        cf_mah = cf_u / 1000
                                        cd_mah = cd_u / 1000
                        if best is not None:
                            health = best
                            lines.append(
                                f"   Battery health : {health:.1f}%  "
                                f"({_health_desc(health)})"
                            )
                            lines.append(
                                f"   Full capacity  : {cf_mah:.0f} mAh  "
                                f"(design {cd_mah:.0f} mAh)"
                            )
                except ValueError:
                    pass
                for key, path in (
                    ("Current level", "/sys/class/power_supply/battery/capacity"),
                    ("Current draw", "/sys/class/power_supply/battery/current_now"),
                    ("Voltage", "/sys/class/power_supply/battery/voltage_now"),
                    ("Temp (raw)", "/sys/class/power_supply/battery/temp"),
                    ("Status", "/sys/class/power_supply/battery/status"),
                    ("Technology", "/sys/class/power_supply/battery/technology"),
                    ("Cycle count", "/sys/class/power_supply/battery/cycle_count"),
                ):
                    v = _sysfs(path)
                    if v:
                        try:
                            if "Current draw" in key:
                                v = f"{int(v)/1000:.0f} mA"
                            elif "Voltage" in key:
                                v = f"{int(v)/1000:.0f} mV"
                            elif "Temp" in key:
                                v = f"{int(v)/10:.1f} C"
                        except ValueError:
                            pass
                        lines.append(f"   {key:15}: {v}")
                if health is None:
                    lines.append(
                        "   (charge_full/design not readable - health estimate "
                        "unavailable without fuel-gauge access)"
                    )
                lines.append("")

                # -- dumpsys battery --
                try:
                    raw = bridge.adb_shell("dumpsys battery", timeout=15)
                    lines.append("--- dumpsys battery ---")
                    for line in raw.splitlines():
                        s = line.strip()
                        if ":" in s:
                            k, _, v = s.partition(":")
                            kk = k.strip()
                            if kk in ("AC powered", "USB powered",
                                      "Wireless powered", "status",
                                      "health", "present", "level",
                                      "scale", "voltage", "temperature",
                                      "technology", "Charge counter",
                                      "Max charging current",
                                      "Max charging voltage"):
                                if kk == "temperature":
                                    try:
                                        v = f"{int(v.strip())/10:.1f} C"
                                    except ValueError:
                                        pass
                                elif kk == "health":
                                    v = {
                                        "1": "unknown", "2": "good",
                                        "3": "overheat", "4": "dead",
                                        "5": "over voltage",
                                        "6": "unspecified failure",
                                        "7": "cold",
                                    }.get(v.strip(), v.strip())
                                elif kk == "status":
                                    v = {
                                        "1": "unknown", "2": "charging",
                                        "3": "discharging", "4": "not charging",
                                        "5": "full",
                                    }.get(v.strip(), v.strip())
                                lines.append(f"   {kk}: {v.strip()}")
                except bridge.BridgeError as e:
                    lines.append(f"   (dumpsys battery failed: {e})")

                # -- dumpsys batteryproperties --
                try:
                    raw = bridge.adb_shell(
                        "dumpsys batteryproperties", timeout=15
                    )
                    lines.append("--- dumpsys batteryproperties ---")
                    for line in raw.splitlines():
                        s = line.strip()
                        if s and ":" in s:
                            k, _, v = s.partition(":")
                            kk, vv = k.strip(), v.strip()
                            if kk == "batteryHealth":
                                vv = {
                                    "1": "unknown", "2": "good",
                                    "3": "overheat", "4": "dead",
                                    "5": "over voltage",
                                    "6": "unspecified failure", "7": "cold",
                                }.get(vv, vv)
                            elif kk == "batteryStatus":
                                vv = {
                                    "1": "unknown", "2": "charging",
                                    "3": "discharging", "4": "not charging",
                                    "5": "full",
                                }.get(vv, vv)
                            lines.append(f"   {kk}: {vv}")
                except bridge.BridgeError as e:
                    lines.append(f"   (batteryproperties failed: {e})")

                # -- top consumers --
                try:
                    raw = bridge.adb_shell(
                        "dumpsys batterystats | grep -A2 'Estimated power use\\|Power use by\\|Uid u0a'",
                        timeout=30,
                    )
                    if raw.strip():
                        lines.append("--- top consumers ---")
                        for line in raw.splitlines()[:30]:
                            lines.append(f"   {line}")
                except bridge.BridgeError:
                    pass
                lines.append("")
                lines.append("Health below 80% means noticeable runtime loss; below 60%")
                lines.append("the battery should be replaced.")
                self._ui.line.emit("\n".join(lines))
            except Exception as e:  # noqa: BLE001
                self._ui.line.emit(f"[error] battery report: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _battery_repair(self):
        """ADB battery repair: the same resets/fixes commercial tools apply.
        Runs a safe, reversible set of adb commands to re-calibrate stats,
        stop background drains and re-tune power settings."""
        self._confirm_overlay(
            "Battery Repair (ADB)",
            "Run the ADB battery fixes commercial tools use?\n\n"
            "  - reset battery statistics (re-calibrate)\n"
            "  - clear battery stats file (root attempt)\n"
            "  - enable Battery Saver\n"
            "  - disable Bluetooth/BLE + Wi-Fi background scanning\n"
            "  - stop background apps + trim app caches\n"
            "  - lower screen timeout + reduce animations\n"
            "  - reset power/stats services\n\n"
            "All steps are reversible from Android settings.",
            "Repair Battery",
            self._battery_repair_run,
        )

    def _battery_repair_run(self):
        if not _flow_start("Battery repair", destructive=False):
            self._ui.status.emit("Busy: " + _flow_busy_msg())
            self._ui.toast.emit("warn", "Operation already running", _flow_busy_msg())
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg()}")
            return

        def work():
            try:
                devs = bridge.adb_status()
                auth = [d for d in devs if d["state"] == "device"]
                if not auth:
                    self._ui.line.emit(
                        "[warn] Battery repair needs an authorized ADB device - "
                        "enable USB debugging and tap Allow"
                    )
                    self._ui.toast.emit(
                        "warn", "No ADB device", "Connect + authorize the phone"
                    )
                    return
                serial = auth[0]["serial"]
                self._ui.line.emit(f"[step] Battery repair on {serial}")

                steps = [
                    ("reset battery statistics (cmd batterystats reset)",
                     "cmd batterystats reset"),
                    ("reset dumpsys battery virtual state",
                     "dumpsys battery reset"),
                    ("clear battery stats file (root)",
                     "su -c 'rm -f /data/system/batterystats.bin'"),
                    ("enable Battery Saver",
                     "settings put global low_power 1"),
                    ("set low_power_sticky",
                     "settings put global low_power_sticky 1"),
                    ("auto low-power trigger at 15%",
                     "settings put global low_power_trigger_level 15"),
                    ("disable BLE background scanning",
                     "settings put global ble_scan_always_enabled 0"),
                    ("disable Wi-Fi scanning",
                     "settings put global wifi_scan_always_enabled 0"),
                    ("disable backup auto-run",
                     "settings put global backup_manager_constants 'key_value_backup_interval_millis=0'"),
                    ("lower screen timeout to 30s",
                     "settings put system screen_off_timeout 30000"),
                    ("reduce window animations",
                     "settings put global window_animation_scale 0.5"),
                    ("reduce transition animations",
                     "settings put global transition_animation_scale 0.5"),
                    ("kill all background apps",
                     "am kill-all"),
                    ("trim app caches",
                     "pm trim-caches 100G"),
                ]
                for label, cmd in steps:
                    try:
                        bridge.adb_shell(cmd, timeout=90)
                        self._ui.line.emit(f"   [ok] {label}")
                    except bridge.BridgeError as e:
                        self._ui.line.emit(f"   [skip] {label}: {e}")
                    except Exception as e:  # noqa: BLE001
                        self._ui.line.emit(f"   [skip] {label}: {e}")

                lines = ["", "--- verification ---"]
                for k in ("low_power", "low_power_sticky",
                          "ble_scan_always_enabled", "wifi_scan_always_enabled"):
                    try:
                        v = bridge.adb_shell(
                            f"settings get global {k}", timeout=12
                        ).strip()
                        lines.append(f"   {k} = {v}")
                    except bridge.BridgeError:
                        lines.append(f"   {k} = (unreadable)")
                try:
                    v = bridge.adb_shell(
                        "settings get system screen_off_timeout", timeout=12
                    ).strip()
                    lines.append(f"   screen_off_timeout = {v}")
                except bridge.BridgeError:
                    pass
                self._ui.line.emit("\n".join(lines))

                self._ui.line.emit(
                    "\nBattery repair done. Tip: discharge to ~10% then charge "
                    "to 100% without interruption to finish re-calibration."
                )
                self._ui.toast.emit(
                    "ok", "Battery repair", "Fixes applied - re-calibration tip shown"
                )
            except Exception as e:  # noqa: BLE001
                self._ui.line.emit(f"[error] battery repair: {e}")
            finally:
                _flow_end()

        threading.Thread(target=work, daemon=True).start()

    def _battery_load_test(self):
        """Low-voltage load test: puts the phone under heavy load (screen on
        full brightness + Wi-Fi/data radios on + CPU burn) while reading the
        battery voltage. A big sag = high internal resistance = dying cell."""
        self._confirm_overlay(
            "Low-Voltage Load Test",
            "Stress the battery to measure internal resistance?\n\n"
            "The phone will be put under heavy load (max brightness, radios "
            "on, CPU burn) for ~15s while voltage is sampled.\n\n"
            "If the battery is weak, the phone may SHUT OFF mid-test - that "
            "itself is the diagnosis.\n\n"
            "Keep the USB cable plugged in during the test.",
            "Start Load Test",
            self._battery_load_test_run,
        )

    def _battery_load_test_run(self):
        if not _flow_start("Battery load test", destructive=False):
            self._ui.status.emit("Busy: " + _flow_busy_msg())
            self._ui.toast.emit("warn", "Operation already running", _flow_busy_msg())
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg()}")
            return

        def work():
            restored = False
            try:
                devs = bridge.adb_status()
                auth = [d for d in devs if d["state"] == "device"]
                if not auth:
                    self._ui.line.emit(
                        "[warn] Load test needs an authorized ADB device"
                    )
                    self._ui.toast.emit(
                        "warn", "No ADB device", "Connect + authorize the phone"
                    )
                    return
                self._ui.line.emit("[step] Battery load test started")
                self._ui.status.emit("Battery load test: stressing...")

                def read():
                    try:
                        v = bridge.adb_shell(
                            "cat /sys/class/power_supply/battery/voltage_now",
                            timeout=8,
                        ).strip()
                        return int(v) / 1000.0 if v else None
                    except (bridge.BridgeError, ValueError):
                        return None

                def read_temp():
                    try:
                        t = bridge.adb_shell(
                            "cat /sys/class/power_supply/battery/temp",
                            timeout=8,
                        ).strip()
                        return int(t) / 10.0 if t else None
                    except (bridge.BridgeError, ValueError):
                        return None

                idle_v = read()
                idle_t = read_temp()
                self._ui.line.emit(
                    f"   idle voltage : {idle_v:.3f} V  "
                    f"temp {idle_t:.1f} C" if idle_v else "   idle voltage : n/a"
                )

                # enable radios + full brightness + screen on
                for cmd in (
                    "svc wifi enable",
                    "svc data enable",
                    "settings put system screen_brightness_mode 0",
                    "settings put system screen_brightness 255",
                    "input keyevent KEYCODE_WAKEUP",
                ):
                    try:
                        bridge.adb_shell(cmd, timeout=10)
                    except bridge.BridgeError:
                        pass
                restored = False  # phone is now maxed - must restore below

                # CPU burn in background
                bridge.adb_shell(
                    "nohup sh -c 'i=0; while [ $i -lt 10000000 ]; do i=$((i+1)); done' >/dev/null 2>&1 &",
                    timeout=8,
                )

                import time as _time
                samples = []
                t0 = _time.time()
                while _time.time() - t0 < 14:
                    if frp.cancel_requested():
                        self._ui.line.emit("[cancelled] load test stopped by user")
                        return
                    v = read()
                    if v:
                        samples.append(v)
                    _time.sleep(0.8)
                # loop done (not cancelled) - the full stress window ran
                restored = True  # handled by finally below

                if not samples:
                    self._ui.line.emit("[error] load test: no voltage samples read")
                    return
                load_v = min(samples)
                load_t = read_temp()
                sag = (idle_v - load_v) if idle_v else None
                self._ui.line.emit("   --- load test result ---")
                self._ui.line.emit(
                    f"   idle voltage : {idle_v:.3f} V" if idle_v else "   idle voltage : n/a"
                )
                self._ui.line.emit(
                    f"   min voltage under load: {load_v:.3f} V  "
                    f"temp {load_t:.1f} C" if load_t else
                    f"   min voltage under load: {load_v:.3f} V"
                )
                if sag is not None:
                    self._ui.line.emit(f"   voltage sag   : {sag*1000:.0f} mV")
                    if sag * 1000 > 250:
                        self._ui.line.emit(
                            "   >>> HIGH sag (>250mV): high internal resistance - "
                            "cell is weak, replace the battery"
                        )
                    elif sag * 1000 > 150:
                        self._ui.line.emit(
                            "   >>> Moderate sag (150-250mV): degraded cell, "
                            "watch for shutdowns under load"
                        )
                    else:
                        self._ui.line.emit(
                            "   Sag within normal range (<150mV): cell looks healthy"
                        )
                self._ui.line.emit(
                    "   If the phone shut off during the test, that confirms a "
                    "weak cell (voltage dropped below cutoff)."
                )
                self._ui.status.emit("Battery load test complete")
                self._ui.toast.emit("ok", "Load test", "Result printed to console")
            except Exception as e:  # noqa: BLE001
                self._ui.line.emit(f"[error] battery load test: {e}")
            finally:
                # Restore brightness even if the burn/read path raised or was
                # cancelled - otherwise the phone is left at 100% brightness.
                if not restored:
                    try:
                        bridge.adb_shell(
                            "settings put system screen_brightness_mode 1", timeout=8
                        )
                    except bridge.BridgeError:
                        pass
                _flow_end()

        threading.Thread(target=work, daemon=True).start()

    # ----------------------------- network repair -------------------------
    def _get_authorized_adb(self):
        try:
            devs = bridge.adb_status()
            auth = [d for d in devs if d["state"] == "device"]
            return auth[0]["serial"] if auth else None
        except bridge.BridgeError:
            return None

    def _require_adb(self):
        serial = self._get_authorized_adb()
        if not serial:
            self._ui.line.emit(
                "[warn] Network tools need an authorized ADB device - enable "
                "USB debugging and tap Allow"
            )
            self._ui.toast.emit(
                "warn", "No ADB device", "Connect + authorize the phone"
            )
        return serial

    def _poll_net_live(self):
        """Live network readout on the Network page. Runs from the 3s ADB
        timer; updates the metric cards while an authorized ADB device is
        connected, so diagnostics appear without clicking anything."""
        if not hasattr(self, "net_cards"):
            return
        if self._update_net_in_progress:
            return
        self._update_net_in_progress = True

        def work():
            try:
                try:
                    adb_devs = bridge.adb_status()
                except bridge.BridgeError:
                    adb_devs = []
                authorized = [d for d in adb_devs if d["state"] == "device"]
                if not authorized:
                    self._ui.ui.emit(self._net_set_offline)
                    return
                serial = authorized[0]["serial"]
                try:
                    get = lambda prop: bridge.adb_shell(
                        f"getprop {prop}", timeout=8
                    ).strip()
                    settings_get = lambda key: bridge.adb_shell(
                        f"settings get global {key}", timeout=8
                    ).strip()
                    sim = get("gsm.sim.state")
                    net = get("gsm.network.type")
                    mode = settings_get("preferred_network_mode")
                    data = settings_get("mobile_data")
                    wifi = settings_get("wifi_on")
                    dns = settings_get("private_dns_mode")
                    airplane = settings_get("airplane_mode_on")
                except (bridge.BridgeError, ValueError):
                    self._ui.ui.emit(self._net_set_offline)
                    return
                vals = {
                    "sim": sim or "unknown",
                    "net": net or "unknown",
                    "mode": mode or "unknown",
                    "data": data or "unknown",
                    "wifi": wifi or "unknown",
                    "dns": dns or "unknown",
                    "airplane": airplane or "unknown",
                }
                try:
                    sig = bridge.adb_shell(
                        "dumpsys telephony.registry 2>/dev/null | grep -m1 "
                        "'mSignalStrength' | awk -F'=' '{print $2}'",
                        timeout=8,
                    ).strip()
                    vals["signal"] = sig or "unknown"
                except bridge.BridgeError:
                    vals["signal"] = "unknown"
                self._ui.ui.emit(lambda: self._net_apply(vals, serial))
            except Exception:  # noqa: BLE001
                pass
            finally:
                self._update_net_in_progress = False

        threading.Thread(target=work, daemon=True).start()

    def _net_apply(self, vals, serial):
        for k, v in vals.items():
            card = self.net_cards.get(k)
            if card:
                card.set(v)
        self.net_status.setText(f"Live from {serial} - updates every 3 seconds")

    def _net_set_offline(self):
        for k, card in self.net_cards.items():
            card.set("--")
        self.net_status.setText(
            "No authorized ADB device - connect + authorize to see live diagnostics"
        )

    def _network_report(self):
        def work():
            try:
                serial = self._require_adb()
                if not serial:
                    return
                lines = [f"=== Network Report ({serial}) ==="]
                probes = [
                    ("SIM state", "getprop gsm.sim.state"),
                    ("Network type", "getprop gsm.network.type"),
                    ("Preferred mode", "settings get global preferred_network_mode"),
                    ("Mobile data", "settings get global mobile_data"),
                    ("Wi-Fi on", "settings get global wifi_on"),
                    ("Wi-Fi scan always", "settings get global wifi_scan_always_enabled"),
                    ("Private DNS", "settings get global private_dns_mode"),
                    ("Airplane mode", "settings get global airplane_mode_on"),
                    ("WLAN IP", "ip addr show wlan0 2>/dev/null | grep 'inet '"),
                    ("Radio version", "getprop gsm.version.baseband"),
                ]
                for label, cmd in probes:
                    try:
                        v = bridge.adb_shell(cmd, timeout=12).strip()
                        if v:
                            lines.append(f"   {label:16}: {v}")
                    except (bridge.BridgeError, ValueError):
                        pass
                try:
                    w = bridge.adb_shell(
                        "dumpsys wifi 2>/dev/null | grep -i 'Wi-Fi is' | head -1",
                        timeout=15,
                    ).strip()
                    if w:
                        lines.append(f"   {'Wi-Fi status':16}: {w}")
                except bridge.BridgeError:
                    pass
                try:
                    c = bridge.adb_shell(
                        "dumpsys connectivity 2>/dev/null | grep -i "
                        "'Active default network' | head -1",
                        timeout=15,
                    ).strip()
                    if c:
                        lines.append(f"   {'Active net':16}: {c}")
                except bridge.BridgeError:
                    pass
                self._ui.line.emit("\n".join(lines))
                self._ui.ui.emit(lambda: self.net_status.setText(
                    "Report printed to console"))
            except Exception as e:  # noqa: BLE001
                self._ui.line.emit(f"[error] network report: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _network_repair(self):
        self._confirm_overlay(
            "Network Repair (ADB)",
            "Run the ADB network fixes commercial tools use?\n\n"
            "  - reset all radios (airplane-mode cycle)\n"
            "  - re-enable Wi-Fi + mobile data\n"
            "  - restore preferred network mode\n"
            "  - reset DNS to automatic\n"
            "  - flush phone + telephony caches\n"
            "  - clear proxy settings\n\n"
            "Safe + reversible from Android settings.",
            "Repair Network",
            self._network_repair_run,
        )

    def _network_repair_run(self):
        if not _flow_start("Network repair", destructive=False):
            self._ui.status.emit("Busy: " + _flow_busy_msg())
            self._ui.toast.emit("warn", "Operation already running", _flow_busy_msg())
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg()}")
            return

        def work():
            try:
                serial = self._require_adb()
                if not serial:
                    return
                self._ui.line.emit(f"[step] Network repair on {serial}")
                self._ui.status.emit("Network repair: resetting radios...")

                steps = [
                    ("airplane mode ON",
                     "settings put global airplane_mode_on 1"),
                    ("wait for radios down",
                     "sleep 2"),
                    ("airplane mode OFF",
                     "settings put global airplane_mode_on 0"),
                    ("enable Wi-Fi",
                     "svc wifi enable"),
                    ("enable mobile data",
                     "svc data enable"),
                    ("restore preferred network mode",
                     "settings put global preferred_network_mode 9,9,9"),
                    ("reset private DNS to automatic",
                     "settings put global private_dns_mode opportunistic"),
                    ("clear HTTP proxy",
                     "settings put global http_proxy :0"),
                    ("kill stale network apps",
                     "am kill-all"),
                    ("flush phone app cache",
                     "pm clear com.android.phone 2>/dev/null || true"),
                    ("flush telephony cache",
                     "pm clear com.android.providers.telephony 2>/dev/null || true"),
                ]
                for label, cmd in steps:
                    try:
                        bridge.adb_shell(cmd, timeout=30)
                        self._ui.line.emit(f"   [ok] {label}")
                    except bridge.BridgeError as e:
                        self._ui.line.emit(f"   [skip] {label}: {e}")
                    except Exception as e:  # noqa: BLE001
                        self._ui.line.emit(f"   [skip] {label}: {e}")

                self._ui.line.emit("")
                self._ui.line.emit("Network repair done. Re-open Settings -> "
                                   "Connections if the phone needs a moment.")
                self._ui.toast.emit("ok", "Network repair", "Radios reset + caches flushed")
            except Exception as e:  # noqa: BLE001
                self._ui.line.emit(f"[error] network repair: {e}")
            finally:
                _flow_end()

        threading.Thread(target=work, daemon=True).start()

    def _network_modem_reset(self):
        self._confirm_overlay(
            "Mobile Data Reset",
            "Force the modem to re-register?\n\n"
            "  - airplane-mode cycle (drops + re-attaches to network)\n"
            "  - set preferred network mode to auto\n"
            "  - re-enable mobile data\n\n"
            "Use when stuck on 'No service' / no data after flashing or "
            "in an area with weak signal.",
            "Reset Modem",
            self._network_modem_reset_run,
        )

    def _network_modem_reset_run(self):
        if not _flow_start("Modem reset", destructive=False):
            self._ui.status.emit("Busy: " + _flow_busy_msg())
            self._ui.toast.emit("warn", "Operation already running", _flow_busy_msg())
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg()}")
            return

        def work():
            try:
                serial = self._require_adb()
                if not serial:
                    return
                self._ui.line.emit(f"[step] Modem reset on {serial}")
                self._ui.status.emit("Modem reset: re-registering...")

                steps = [
                    ("airplane mode ON",
                     "settings put global airplane_mode_on 1"),
                    ("hold radios down",
                     "sleep 5"),
                    ("airplane mode OFF",
                     "settings put global airplane_mode_on 0"),
                    ("preferred network mode auto",
                     "settings put global preferred_network_mode 9,9,9"),
                    ("re-enable mobile data",
                     "svc data enable"),
                    ("force data connect",
                     "cmd connectivity mobile-data enable 2>/dev/null || true"),
                ]
                for label, cmd in steps:
                    try:
                        bridge.adb_shell(cmd, timeout=30)
                        self._ui.line.emit(f"   [ok] {label}")
                    except bridge.BridgeError as e:
                        self._ui.line.emit(f"   [skip] {label}: {e}")
                    except Exception as e:  # noqa: BLE001
                        self._ui.line.emit(f"   [skip] {label}: {e}")

                try:
                    v = bridge.adb_shell(
                        "getprop gsm.sim.state", timeout=12
                    ).strip()
                    self._ui.line.emit(f"\nSIM state after reset: {v or '(unknown)'}")
                except bridge.BridgeError:
                    pass
                self._ui.toast.emit("ok", "Modem reset", "Modem re-registering")
            except Exception as e:  # noqa: BLE001
                self._ui.line.emit(f"[error] modem reset: {e}")
            finally:
                _flow_end()

        threading.Thread(target=work, daemon=True).start()

    # ----------------------------- run flow -------------------------------
    def _carrier_lock_status(self):
        name = frp.FLOWS["carrier_lock_status"]().name
        self._run_ops_flow("Carrier lock", "ADB", "carrier_lock_status", name)

    def _carrier_lock_mtk(self):
        name = frp.FLOWS["carrier_lock_mtk"]().name
        self._run_ops_flow("Carrier lock", "MTK BROM", "carrier_lock_mtk", name)

    def _on_flash_slots(self):
        """Primary FLASH button: confirm what will be flashed, then run the
        5-slot advanced flash. Refuses to start with no slots selected, and
        always asks for confirmation since flashing overwrites the device."""
        picked = []
        for name, edit in self.slot_inputs.items():
            val = edit.text().strip()
            if val:
                picked.append((name, os.path.basename(val)))
        if not picked:
            self._toasts.show_warn(
                "No firmware selected",
                "Pick at least one AP / BL / CP / CSC / USERDATA archive before flashing.",
            )
            self._ui.status.emit("Flash blocked: no firmware slot selected")
            self._ui.line.emit("\n[blocked] flash aborted - select a firmware slot first")
            return

        detail = "\n".join(f"    {n} <- {f}" for n, f in picked)
        self._confirm_overlay(
            "Flash Firmware",
            "This will OVERWRITE the following partitions on your device.\n\n"
            f"{detail}\n\n"
            "DO NOT unplug the phone and keep the battery above 50% until the "
            "flash finishes. A failed bootloader flash can permanently brick "
            "the device.",
            confirm_label="Flash now",
            on_confirm=lambda: self._run_ops_flow(
                "Odin Flashing (Advanced)", "Download mode",
                "odin_advanced_flash", "Advanced flash (AP/BL/CP/CSC + Unofficial)",
            ),
        )

    def _browse_slot(self, edit_widget, slot_name):
        # Native Linux (GTK) file dialogs select the FIRST filter by default;
        # using a single comprehensive filter guarantees .img/.lz4/.bin/.pit/
        # .tar files are visible instead of the folder looking empty.
        name_filter = "Samsung images & archives (*.img *.lz4 *.bin *.pit *.tar *.tar.md5)"
        dlg = QFileDialog(
            self,
            f"Select {slot_name}",
            os.path.expanduser("~/Downloads"),
            name_filter,
        )
        dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog, False)
        dlg.selectNameFilter(name_filter)
        if dlg.exec() and dlg.selectedFiles():
            edit_widget.setText(dlg.selectedFiles()[0])

    def _on_job_changed(self, job):
        pass

    def _on_mode_changed(self, mode):
        pass

    def on_stop(self):
        frp.request_cancel()
        bridge.request_cancel()
        self._ui.status.emit("Stopping flow ...")

    def _run_ops_flow(self, job, mode, method, label):
        """Run a Samsung Operations flow directly from its button - no
        job/mode/method dropdowns, each operation is its own button."""
        if not _flow_start(label, destructive=True):
            self._ui.status.emit("Busy: " + _flow_busy_msg())
            self._ui.toast.emit("warn", "Operation already running", _flow_busy_msg())
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg()}")
            return
        frp.clear_cancel()
        bridge.clear_cancel()
        self._toasts.show_progress("Operation started", label)
        if job == "Odin Flashing (Advanced)":
            os.environ["ODIN4_ALLOW_UNKNOWN"] = "1" if self.allow_unknown_cb.isChecked() else "0"
            os.environ["ODIN4_REBOOT"] = "1" if self.auto_reboot_cb.isChecked() else "0"
            os.environ["ODIN4_ERASE_NV"] = "1" if self.erase_nv_cb.isChecked() else "0"
            os.environ["ODIN4_CHECK_ONLY"] = "1" if self.check_only_cb.isChecked() else "0"
            os.environ["ODIN4_REDOWNLOAD"] = "1" if self.redownload_cb.isChecked() else "0"
            os.environ["ODIN4_VERBOSE"] = "1" if self.verbose_cb.isChecked() else "0"
            os.environ["ODIN4_FORCE_BL"] = "1" if self.force_bl_cb.isChecked() else "0"
            os.environ["VBMETA_PATCH"] = "1" if self.vbmeta_patch_cb.isChecked() else "0"
            # GUI-triggered Odin flows must flash ONLY the files the user
            # picked in the slots - never auto-discover in ~/Downloads.
            os.environ["ODIN4_EXACT_SLOTS"] = "1"
            for s_name, s_edit in self.slot_inputs.items():
                val = s_edit.text().strip()
                if val:
                    os.environ[f"{s_name}_TAR"] = val
                else:
                    os.environ.pop(f"{s_name}_TAR", None)

            part = self.partition_edit.text().strip()
            img = self.image_edit.text().strip()
            sc = self.sales_code_edit.text().strip().upper()
            specs = self.flash_specs_edit.text().strip()
            pit = self.pit_file_edit.text().strip()
            if part:
                os.environ["FLASH_PARTITION"] = part
            else:
                os.environ.pop("FLASH_PARTITION", None)
            if img:
                os.environ["FLASH_IMAGE"] = img
            else:
                os.environ.pop("FLASH_IMAGE", None)
            if sc:
                os.environ["SALES_CODE"] = sc
            else:
                os.environ.pop("SALES_CODE", None)
            if specs:
                os.environ["FLASH_SPECS"] = specs
            else:
                os.environ.pop("FLASH_SPECS", None)
            if pit:
                os.environ["PIT_FILE"] = pit
            else:
                os.environ.pop("PIT_FILE", None)

            vbmeta = self.vbmeta_edit.text().strip()
            if vbmeta:
                os.environ["VBMETA_FILE"] = vbmeta
            else:
                os.environ.pop("VBMETA_FILE", None)

        if method == "carrier_lock_mtk":
            mtk_files = getattr(self, "mtk_files", None)
            if mtk_files:
                da = mtk_files["da"].text().strip()
                if da:
                    os.environ["MTK_DA"] = da
                else:
                    os.environ.pop("MTK_DA", None)
            else:
                os.environ.pop("MTK_DA", None)

        if self.clear_on_run.isChecked():
            self._clear_console()
        self.stop_btn.setEnabled(True)
        self.shimmer.setVisible(True)
        self.shimmer.set_active(True)
        self._accent_strip.set_active(True)
        self._ui.status.emit(f"Running: {label}")
        self._ui.line.emit(f"\n>>> started: {label}")

        def work():
            ctx = {}
            try:
                flow = frp.flow_for(job, mode, method)
                flow.run(ctx, self._ui.line.emit)
                if ctx.get("mdm_qr_pngs"):
                    self._ui.qr.emit(ctx["mdm_qr_pngs"])
                elif ctx.get("mdm_qr_png"):
                    self._ui.qr.emit(ctx["mdm_qr_png"])
                self._ui.status.emit(f"Flow '{label}' finished")
                self._ui.line.emit("Flow completed successfully")
                self._ui.toast.emit("ok", "Operation completed", label)
            except frp.FlowCancelled as e:
                self._ui.line.emit(f"[cancelled] flow stopped by user ({e})")
                self._ui.status.emit(f"Flow '{label}' cancelled")
                self._ui.toast.emit("warn", "Operation cancelled", str(e))
            except Exception as e:  # noqa: BLE001
                self._emit_flow_error(label, e, mode=mode)
            finally:
                _flow_end()
                self._ui.ui.emit(self._toasts.dismiss_progress)
                self._ui.finished.emit()

        threading.Thread(target=work, daemon=True).start()

    def _coach_no_device(self, mode):
        """When a flow failed because no device was present, print plain-language
        instructions for getting the phone into the right mode. Uses the mode
        the operation was launched with so the guidance is specific."""
        from python.core.mtp import find_samsung

        cur = find_samsung()
        if cur:
            self._ui.line.emit(
                f"  [hint] a Samsung device IS connected (pid 04e8:{cur.get('pid', 0):04x}),"
                " but not in the mode this operation needs."
            )
        self._ui.line.emit("  [hint] what to do:")
        mode = (mode or "").strip().lower()
        if "download" in mode:
            self._ui.line.emit(
                "    1. Power the phone fully OFF (hold power, tap Power off)."
            )
            self._ui.line.emit(
                "    2. Hold Volume Down + Power for a few seconds."
            )
            self._ui.line.emit(
                "    3. On the warning screen press Volume Up to enter"
                " 'Downloading...' mode."
            )
            self._ui.line.emit(
                "    The phone now shows a blue 'Downloading' screen - do NOT"
                " press Volume Down on it."
            )
        elif "edl" in mode or "qualcomm" in mode:
            self._ui.line.emit(
                "    1. Power the phone fully OFF."
            )
            self._ui.line.emit(
                "    2. Hold Volume Up + Volume Down together, then plug in the"
                " USB cable (or hold Volume Up + Power on some models)."
            )
            self._ui.line.emit(
                "    The Qualcomm EDL port (05c6:9008) should now appear - a"
                " window may pop up asking for a driver on Windows."
            )
        elif "brom" in mode or "mtk" in mode:
            self._ui.line.emit(
                "    1. Power the phone fully OFF."
            )
            self._ui.line.emit(
                "    2. Hold Volume Up + Volume Down, then plug in the USB cable"
                " (MediaTek BROM/preloader mode)."
            )
            self._ui.line.emit(
                "    The MediaTek port (0e8d:0003 BROM) should now appear."
            )
        elif "fastboot" in mode:
            self._ui.line.emit(
                "    1. Boot the phone to fastboot: hold Volume Down + Power from"
                " the bootloader screen, then select 'fastboot' with Volume"
                " keys + Power."
            )
        elif "adb" in mode:
            self._ui.line.emit(
                "    1. On the phone enable Developer Options, then USB Debugging."
            )
            self._ui.line.emit(
                "    2. Plug in the USB cable and tap 'Allow' on the RSA"
                " debugging prompt on the phone screen."
            )
        else:
            self._ui.line.emit(
                "    Put the phone in the mode this operation needs (see the"
                " operation description / console output for which one)."
            )
        self._ui.line.emit(
            "  If it is already in the right mode, press F5 to re-scan USB."
        )

    def _emit_flow_error(self, label, e, mode=None):
        """Render a failed flow so the real error is unmissable: a FAILED status,
        the error + bridge log tail in the console, and a red toast. If the
        failure looks like a missing device, add mode-specific coaching."""
        msg = f"{type(e).__name__}: {e}"
        self._ui.line.emit(f"\n[FAILED] {label}")
        self._ui.line.emit(f"  {msg.splitlines()[0]}")
        if "bridge log tail" in msg:
            tail = msg.split("[bridge log tail]", 1)[1].strip()
            if tail:
                self._ui.line.emit("  -- last bridge output --")
                for ln in tail.splitlines():
                    self._ui.line.emit(f"  {ln}")
        self._ui.status.emit(f"FAILED: {label} - {msg.splitlines()[0]}")
        self._ui.toast.emit("error", "Operation failed", msg.splitlines()[0])
        low = msg.lower()
        if any(
            k in low
            for k in (
                "no device",
                "not in download mode",
                "device not found",
                "no samsung",
                "no target",
                "not connected",
                "no adb",
                "not in the right mode",
                "device in fastboot",
                "not found",
            )
        ):
            self._coach_no_device(mode)

    def _run_job_flow(self, job, mode, method, label, stop_btn, progress, reset_ui):
        """Run one of the frp job flows (screen lock remove, MDM unlock, BROM
        info, ...) directly from the MTK / Qualcomm / SPD chip pages. The
        Samsung Operations panel exposes the same flows through its job/mode/
        method pickers; this lets the dedicated chip pages run them too."""
        if not _flow_start(label, destructive=True):
            self._ui.status.emit("Busy: " + _flow_busy_msg())
            self._ui.toast.emit("warn", "Operation already running", _flow_busy_msg())
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg()}")
            return
        frp.clear_cancel()
        bridge.clear_cancel()
        self._toasts.show_progress("Operation started", label)
        self._ui.line.emit(f"\n>>> started: {label}")
        self._ui.status.emit(f"Running: {label}")
        stop_btn.setEnabled(True)
        progress.setVisible(True)
        progress.setValue(150)

        def work():
            ctx = {}
            try:
                flow = frp.flow_for(job, mode, method)
                flow.run(ctx, self._ui.line.emit)
                if ctx.get("mdm_qr_pngs"):
                    self._ui.qr.emit(ctx["mdm_qr_pngs"])
                elif ctx.get("mdm_qr_png"):
                    self._ui.qr.emit(ctx["mdm_qr_png"])
                self._ui.status.emit(f"Flow '{label}' finished")
                self._ui.line.emit("Flow completed successfully")
                self._ui.toast.emit("ok", "Operation completed", label)
            except frp.FlowCancelled as e:
                self._ui.line.emit(f"[cancelled] flow stopped by user ({e})")
                self._ui.status.emit(f"Flow '{label}' cancelled")
                self._ui.toast.emit("warn", "Operation cancelled", str(e))
            except Exception as e:  # noqa: BLE001
                self._emit_flow_error(label, e, mode=mode)
            finally:
                _flow_end()
                self._ui.ui.emit(self._toasts.dismiss_progress)
                self._ui.ui.emit(reset_ui)

        threading.Thread(target=work, daemon=True).start()


def _app_icon():
    """Window / taskbar icon: the packaged logo when present, else a drawn one.
    Resolves docs/logo_256.png in both the dev tree and the installed layout
    (/usr/share/flashpilot/docs/)."""
    logo_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..", "docs", "logo_256.png",
    )
    if os.path.exists(logo_path):
        return QIcon(logo_path)
    pix = _draw_logo(256)
    return QIcon(pix)


def main():
    app = QApplication([])
    QApplication.setDesktopFileName("flashpilot.desktop")
    app.setWindowIcon(_app_icon())
    splash = SplashScreen()
    splash.show()

    def _boot():
        win = FrpWindow()
        win.setWindowIcon(_app_icon())
        win.show()

    QTimer.singleShot(2500, _boot)
    app.exec()
