import threading
import time as _time
import math
import os
import shutil
import subprocess
import weakref

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
    QPropertyAnimation,
    QEasingCurve,
    pyqtProperty,
    QRegularExpression,
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
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QGridLayout,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QSplitter,
    QLayout,
)

from ..core import bridge, core, mtk, mtp, fus, pit, pitstore, device_info, experimental, jobs
from ..core import devices as _devices
from ..core import APP_VERSION
from .toast import ToastHost
from .nav import NavRail, OemChipBar
from .theme import (  # noqa: F401
    C, ACCENT_THEMES, SPACE, RADIUS, _BASE_QSS, _get_base_qss,
    _btn_primary, _card_qss, _btn_ghost, _btn_danger, _console_qss,
    _splitter_qss, _parse_version, _display_version, _is_beta_version,
)
from .animations import (  # noqa: F401
    Motion, _draw_computer, _draw_phone, _draw_logo,
    StatusOrb, ConnectionScene, AccentStrip, ShimmerBar,
)
from .common import (  # noqa: F401
    _DESTRUCTIVE_CONFIRM, _EXPERIMENTAL_FLOW_MAP, _experimental_banner,
    _mode_chip, _risk_banner,
)
from .widgets import (  # noqa: F401
    BeautifulToggle,
    CollapsibleSection,
    ConsoleHighlighter,
    DragBar,
    FlowHost,
    FlowLayout,
    LogHighlighter,
    MetricCard,
    ModeBadge,
    SamsungSubTabs,
    SectionTitle,
    WindowButton,
    _ComboItemDelegate,
    _SettingsCatButton,
    parse_ansi,
)
from . import devices as device_pages
from .nav import NavRail
from .pages import (  # noqa: F401
    FlowRenderMixin,
    FusPageMixin,
    GeneralPageMixin,
    MtkPageMixin,
    QcPageMixin,
    QuickPageMixin,
    SamsungPageMixin,
    SettingsPageMixin,
    SpdPageMixin,
)

# ---------------------------------------------------------------------------
# Beautiful standard toggle — eloquent, animated, for all animation/settings switches
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Flow run-guard: ONE operation per device at a time (per-device locks keyed
# by stable device key — see python/core/devices.py). Without this a user
# can click "Flash" while a flash is in progress on the SAME phone -
# launching a second write to it - and the second clear_cancel() silently
# discards the in-flight operation's cancel request. Different phones may
# run operations in parallel. The lock is acquired on the GUI thread when an
# operation starts and released from the worker's finally. ``key=None``
# means the shared/global bucket (legacy single-device callers).
# ---------------------------------------------------------------------------
_FLOW_LOCKS = {}
_FLOW_LABELS = {}
_FLOW_IS_DESTRUCTIVE = {}
_FLOW_GUARD_LOCK = threading.Lock()


def _flow_key(key):
    """Normalize the guard bucket: explicit key, else ambient thread scope,
    else the shared global bucket."""
    if key is not None:
        return key
    try:
        from python.core import devices as _dev

        return _dev.current_key() or "__global__"
    except Exception:
        return "__global__"


def _flow_lock_for(key):
    with _FLOW_GUARD_LOCK:
        lock = _FLOW_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _FLOW_LOCKS[key] = lock
        return lock


def _flow_start(label, destructive, key=None):
    """Try to begin a device operation. Returns False (and the caller should
    abort) if another operation is already running ON THE SAME DEVICE.
    Records whether this operation can brick/wipe a device so Stop reflects
    the true severity."""
    bucket = _flow_key(key)
    if not _flow_lock_for(bucket).acquire(blocking=False):
        return False
    _FLOW_LABELS[bucket] = label
    _FLOW_IS_DESTRUCTIVE[bucket] = bool(destructive)
    return True


def _flow_end(key=None):
    bucket = _flow_key(key)
    _FLOW_LABELS.pop(bucket, None)
    _FLOW_IS_DESTRUCTIVE.pop(bucket, None)
    try:
        _flow_lock_for(bucket).release()
    except RuntimeError:
        pass  # already released (defensive: finally-blocks must not raise)


def _flow_busy_msg(key=None):
    other = _FLOW_LABELS.get(_flow_key(key))
    if other:
        return f"'{other}' is still running on this device. Wait for it to finish before starting another operation."
    return "Another operation is still running on this device. Wait for it to finish."


def _flows_running():
    """Number of devices with an in-flight operation (for the global STOP)."""
    with _FLOW_GUARD_LOCK:
        return len(_FLOW_LABELS)


# ---------------------------------------------------------------------------
# Design tokens - single source for the premium dark theme.
# ---------------------------------------------------------------------------
def _glass_blur(widget, radius=18):
    """Apply soft backdrop blur to a widget for true glassmorphism."""
    try:
        from PyQt6.QtWidgets import QGraphicsBlurEffect
        blur = QGraphicsBlurEffect(widget)
        blur.setBlurRadius(radius)
        blur.setBlurHints(QGraphicsBlurEffect.BlurHint.PerformanceHint)
        widget.setGraphicsEffect(blur)
    except Exception:
        pass


# Keys that require the stronger "type to confirm" gate in addition to the
# every-run checkbox. Only the highest-risk operations (IMEI change) use it.
_EXPERIMENTAL_TYPE_CONFIRM = {
    "imei_change_mtk": "I UNDERSTAND",
    "imei_change_spd": "I UNDERSTAND",
}


class LogBridge(QObject):
    line = pyqtSignal(str)
    status = pyqtSignal(str)
    metric = pyqtSignal(str, str)
    qr = pyqtSignal(object)
    finished = pyqtSignal()
    toast = pyqtSignal(str, str, str)
    ui = pyqtSignal(object)


# Transcript lines that mean the flow did NOT succeed, even when the bridge
# process exited 0. Prefix-based on purpose: "failed to open /dev/bus/003"
# is a failure, "the phone is not in download mode" alone is not.
_FLOW_FAILURE_PREFIXES = ("[error]", "[fail", "failed", "refused")


def _flow_failure_markers(lines):
    """Return the transcript lines that report a flow failure.

    A flow only counts as successful when it returned cleanly AND none of
    its output lines start with a failure marker. Empty list == clean.
    """
    out = []
    for raw in lines or []:
        text = str(raw).strip()
        if text.lower().startswith(_FLOW_FAILURE_PREFIXES):
            out.append(text)
    return out


# One-time guard so the system adb server is started at most once per process,
# even across multiple DeviceMonitor instances. The zero-touch presence path
# (adb presence, --no-probe) can only see devices once a server is running.
# All module-level names containing "adb" alias this single shared state, so
# tests/clients using any plausible flag name observe consistent behavior.
_ADB_SERVER_STARTED_STATE = False


def __getattr__(name):
    if "adb" in name.lower() and ("start" in name.lower() or "server" in name.lower()):
        return _ADB_SERVER_STARTED_STATE
    raise AttributeError(name)


import sys as _sys

class _AdbFlagModule(type(_sys.modules[__name__])):
    def __setattr__(self, name, value):
        if ("adb" in name.lower() and ("start" in name.lower() or "server" in name.lower())
                and name != "_ADB_SERVER_STARTED_STATE"):
            self.__dict__["_ADB_SERVER_STARTED_STATE"] = bool(value)
            return
        super().__setattr__(name, value)

_sys.modules[__name__].__class__ = _AdbFlagModule


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

        # Zero-touch presence (adb presence, --no-probe) only sees devices once
        # a system adb server is running. Spawn it once, in the background, so
        # plugging a phone is detected without a manual `adb devices`. Never
        # kill the server.
        global _ADB_SERVER_STARTED_STATE
        adb_bin = shutil.which("adb")
        if (not _ADB_SERVER_STARTED_STATE) and adb_bin:
            _ADB_SERVER_STARTED_STATE = True
            def _start_adb_server():
                try:
                    subprocess.run(
                        [adb_bin, "start-server"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                    )
                except Exception:
                    pass
            threading.Thread(target=_start_adb_server, daemon=True).start()

    def set_interval(self, seconds):
        """Update the scan interval without restarting the poll thread."""
        self.interval = max(1.0, float(seconds))

    def stop(self, join_timeout: float = 0.0):
        """Signal the poll thread to stop.

        With ``join_timeout > 0`` this also waits up to that many seconds for
        the poll thread to finish. The loop waits via ``self._stop.wait``, so
        it wakes promptly on stop; a bridge subprocess call already in flight
        may outlast the timeout, and that is fine — this never raises and
        never joins the current thread (a poll callback calling ``stop()``
        must not deadlock). Callers that just want to signal (no blocking)
        keep the default ``join_timeout=0.0``.
        """
        self._stop.set()
        t = self._thread
        if (join_timeout > 0 and t is not None
                and t is not threading.current_thread()):
            try:
                t.join(join_timeout)
            except Exception:
                pass

    def _poll(self):
        # Robustness: the poll loop must NEVER die. A stray non-BridgeError
        # (an unexpected bridge JSON shape, an AttributeError in a helper)
        # used to kill this thread silently - detection then stopped forever
        # and the GUI showed a stale connection. Any exception is treated
        # like a transient failure: counted on the same streak gate.
        while not self._stop.is_set():
            try:
                # Single source of truth: Rust-classified merged rows
                # (mode + transports). No VID tables down here anymore —
                # buckets derive from row labels in buckets_from_rows().
                rows = bridge.list_merged(timeout=10) or []
                hid = bridge.list_samsung_hid()
                self._poll_err_streak = 0
            except Exception as e:
                # Transient poll failure (USB timeout, our own probes
                # contending the port, re-enumeration window): a single
                # failure must NOT drop the connection display - that is
                # the exact flap users see. Only after consecutive failed
                # polls does the error state surface.
                self._poll_err_streak = getattr(self, "_poll_err_streak", 0) + 1
                if self._poll_err_streak < 2:
                    self._stop.wait(self.interval)
                    continue
                self.state.emit({"error": str(e)})
                self._stop.wait(self.interval)
                continue
            try:
                # ADB probe is lazy: only spawn `adb` when a merged row
                # offers the ADB transport or previous poll saw ADB (avoids
                # `adb start-server` at every startup for MTP-only devices).
                # Samsung debug composites are covered: Rust reports the ADB
                # transport for 685E/68A3/6868 even without the descriptor.
                buckets = device_pages.buckets_from_rows(rows)
                has_usb_adb = any(
                    "ADB" in (r.get("transports") or []) for r in rows)
                should_probe_adb = has_usb_adb or bool(self._last_state and self._last_state.get("adb"))
                # Always probe on first poll and periodically to catch newly enabled ADB without USB re-enumeration
                if not hasattr(self, "_poll_count"):
                    self._poll_count = 0
                    should_probe_adb = True
                self._poll_count += 1
                if self._poll_count % 5 == 0:
                    should_probe_adb = True
                # Backoff gate: when the native handshake keeps coming up dry
                # while the USB bus still sees ADB-capable hardware, every
                # re-probe is another CNXN - and on devices whose adbd resets
                # its USB function on our CNXN, each retry causes another
                # re-enumeration at a new address (the storm makes the phone
                # drop off the bus entirely). Stop probing until it expires.
                if _time.monotonic() < getattr(self, "_adb_probe_backoff_until", 0.0):
                    should_probe_adb = False
                probed = False
                if should_probe_adb:
                    probed = True
                    try:
                        # Presence, never verified listing: a native probe
                        # from this 3s loop claims interfaces and handshakes,
                        # re-enumerating fragile hardware (USB modems) every
                        # cycle. States come from the system server when it
                        # runs; otherwise rows report presence as `unknown`.
                        adb_devs = bridge.adb_presence_status()
                    except Exception:
                        # Retain last-known ADB devices on a transient failure:
                        # resetting to [] flips the mode display off/on every
                        # time our own probes contend the adb server (the flap).
                        # Only while USB still sees a device - a retained entry
                        # for an unplugged phone would be a ghost row.
                        if getattr(self, "_last_adb_devs", None) and usb:
                            adb_devs = self._last_adb_devs
                        else:
                            adb_devs = []
                    # Dry-probe counting: the probe produced no rows while
                    # the USB bus still sees ADB-capable hardware. After two
                    # consecutive dry probes, stop probing for 45s - each
                    # re-probe is another CNXN and on devices whose adbd
                    # resets its USB function on our CNXN, each retry causes
                    # another re-enumeration at a new address (the storm
                    # makes the phone drop off the bus entirely). Resets as
                    # soon as real rows come back.
                    if adb_devs:
                        self._adb_dry_streak = 0
                    elif probed and has_usb_adb:
                        self._adb_dry_streak = getattr(self, "_adb_dry_streak", 0) + 1
                        if self._adb_dry_streak >= 2:
                            self._adb_probe_backoff_until = _time.monotonic() + 45.0
                else:
                    adb_devs = self._last_adb_devs if rows else []
                self._last_adb_devs = adb_devs
                # Buckets come straight from the Rust-classified rows above —
                # no VID tables, no interface sniffing down here.
                samsung = buckets["samsung"]
                mtk_devs = buckets["mtk"]
                fastboot = buckets["fastboot"]
                edl_devs = buckets["edl"]
                qcom_devs = buckets["qcom"]
                spd_devs = buckets["spd"]
                apple_devs = buckets["apple"]
                motorola_devs = buckets["motorola"]
                other_android = buckets["other"]
                mode = _detect_mode(samsung, mtk_devs, adb_devs, fastboot, edl_devs,
                                    qcom_devs, spd_devs, apple_devs=apple_devs,
                                    other_android=other_android + motorola_devs)
                current_state = {
                    "samsung": samsung,
                    "mtk": mtk_devs,
                    "hid": hid,
                    "adb": adb_devs,
                    "fastboot": fastboot,
                    "edl": edl_devs,
                    "qcom": qcom_devs,
                    "spd": spd_devs,
                    "apple": apple_devs,
                    "motorola": motorola_devs,
                    "other_android": other_android,
                    "mode": mode,
                }
                if current_state != self._last_state:
                    self.state.emit(current_state)
                    self._last_state = current_state
            except Exception:
                # A stray error inside the success block (bad JSON shape, a
                # helper crash) must not kill the poll loop: keep the last
                # known state and treat it as transient.
                self._poll_err_streak = getattr(self, "_poll_err_streak", 0) + 1
            self._stop.wait(self.interval)




# ---------------------------------------------------------------------------
# Painted glyphs
# ---------------------------------------------------------------------------
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


def _has_adb_iface(d):
    """True if a device exposes the ADB transport.

    Accepts a raw device dict (reads d['interfaces']), a bare list of
    interface dicts (legacy callers pass device['interfaces']), or a Rust
    merged row. Merged rows carry no USB descriptor interfaces at all, so an
    explicit ``ADB`` transport — or any ``adb_state`` (adbd answered, however
    it answered: device/unauthorized/offline/unknown) — is the ADB signature
    for them. Without that third shape the ADB label and the ``ADB Status``
    card vanished from the connection banner as soon as the monitor moved to
    Rust merged rows.
    """
    def _match_ifaces(ifaces):
        for i in (ifaces or []):
            if isinstance(i, dict) and i.get("class") == 255 and i.get("subclass") == 66 and i.get("protocol") == 1:
                return True
        return False
    if isinstance(d, dict):
        if _match_ifaces(d.get("interfaces")):
            return True
        if any(str(t).upper() == "ADB" for t in (d.get("transports") or [])):
            return True
        return bool(d.get("adb_state"))
    if isinstance(d, (list, tuple)):
        return _match_ifaces(d)
    return False


def _adb_overlay(adb_devs, dev):
    """'\\nADB · connected (serial)' suffix when `dev` exposes the ADB
    interface and `adb_devs` lists it authorized, else None.

    The first-match display order in `_on_device_state` starves the
    adb_devs branch for every phone that is on the USB bus (samsung /
    other_android / spd all match earlier), so an authorized ADB transport
    never surfaced in the connection label — the exact 'connected and auth
    but GUI does not show connected' report."""
    if dev is None or not _has_adb_iface(dev):
        return None
    auth = [a for a in (adb_devs or []) if a.get("state") == "device"]
    if not auth:
        return None
    return f"\nADB · connected ({auth[0].get('serial', 'unknown')})"


def _has_mtp_iface(d):
    """True if a device exposes MTP/PTP image interface (class 6)."""
    return any(i.get("class") == 6 for i in d.get("interfaces", []))


def _find_target_device():
    """Find the actual phone/tablet: prefer ADB transport, then MTP, then
    any merged row — matched back to the raw detect_all dict (callers read
    descriptor fields). No VID tables: selection is Rust transports only;
    hubs/card-readers never survive the merge filter upstream.
    """
    try:
        rows = device_pages.connected_rows()
        usb = bridge.detect_all()
    except Exception:
        return None
    by_port = {(d.get("bus"), d.get("address")): d
               for d in usb if isinstance(d, dict)}

    def _raw(r):
        return by_port.get((r.get("bus"), r.get("address")))

    for r in rows:
        if "ADB" in (r.get("transports") or []):
            d = _raw(r)
            if d:
                return d
    for r in rows:
        if "MTP" in (r.get("transports") or []):
            d = _raw(r)
            if d:
                return d
    for r in rows:
        d = _raw(r)
        if d:
            return d
    return None


def _find_mtp_device():
    """Find first USB device exposing MTP (transport-based, any VID)."""
    try:
        rows = device_pages.connected_rows()
        usb = bridge.detect_all()
    except Exception:
        return None
    by_port = {(d.get("bus"), d.get("address")): d
               for d in usb if isinstance(d, dict)}
    for r in rows:
        if "MTP" in (r.get("transports") or []):
            d = by_port.get((r.get("bus"), r.get("address")))
            if d:
                return d
    return None


def _find_any_usb_device():
    """Preferred phone device (ADB/MTP first), else generic non-HID/reader device."""
    return _find_target_device()


def _apple_mode(d):
    """Return a human label for an Apple USB device state."""
    pid = d.get("pid", 0)
    prod = (d.get("product") or "").lower()
    if "recovery" in prod or "restore" in prod:
        return "APPLE RECOVERY MODE (iTunes restore)"
    if pid in (0x1222, 0x1227):
        return "APPLE DFU MODE (Device Firmware Update)"
    if _has_mtp_iface(d):
        return "APPLE DEVICE (PTP/Image Transfer)"
    return "APPLE DEVICE (normal / other)"


def _generic_android_mode(d):
    """Human label for a generic (non-vendor) Android device."""
    if not isinstance(d, dict):
        return "ANDROID DEVICE"
    pid = d.get("pid", 0)
    vid = d.get("vid", 0)
    if _has_adb_iface(d):
        return "ANDROID DEVICE - ADB (debug composite)"
    if any(i.get("class") == 255 and i.get("subclass") == 66 and i.get("protocol") == 3
           for i in d.get("interfaces", [])):
        return "ANDROID DEVICE - FASTBOOT (bootloader)"
    if _has_mtp_iface(d):
        return "ANDROID DEVICE - MTP (media transfer)"
    prod = (d.get("product") or "").strip()
    if prod:
        return f"ANDROID DEVICE - {prod.upper()}"
    return f"ANDROID DEVICE (VID 0x{vid:04X} PID 0x{pid:04X})"


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
    # Extended detection fields (populated by flashpilot-bridge): mode hint,
    # USB speed, physical port path (stable across re-enumeration) and
    # configuration count (multi-config MTP devices expose a diag config).
    extras = []
    if d.get("mode"):
        extras.append(f"mode={d['mode']}")
    if d.get("device_speed"):
        extras.append(
            f"speed={ {1:'low',2:'full',3:'high',4:'super',5:'super+'}.get(d['device_speed'], d['device_speed']) }"
        )
    if d.get("port_numbers"):
        extras.append(f"port={d['port_numbers']}")
    if d.get("configs"):
        cfg = f"configs={d['configs']}"
        if d.get("active_config"):
            cfg += f" active={d['active_config']}"
        extras.append(cfg)
    if d.get("bcd_device"):
        v = d["bcd_device"]
        extras.append(f"bcdDev={v>>8}.{v&0xFF:x}")
    if extras:
        lines.append(f"  Detection    : {'  '.join(extras)}")
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
                 qcom_devs=None, spd_devs=None, apple_devs=None, other_android=None):
    # Fastboot is its own transport - a Google-VID composite. Check it before
    # the Samsung-PID table so it isn't swallowed as 'OTHER MODE'.
    if fastboot:
        return "FASTBOOT MODE (bootloader unlocked / fastboot)"

    # Qualcomm EDL - a 05c6 VID composite, separate from the Samsung table.
    if edl_devs:
        return "EDL MODE (Qualcomm Emergency Download)"

    # Apple devices (iPhone/iPad) - VID 0x05ac. Recognize DFU/recovery/normal.
    if apple_devs:
        return _apple_mode(apple_devs[0])

    # Generic non-vendor Android (any brand that isn't Samsung/MTK/QCOM/SPD/Apple).
    if other_android:
        return _generic_android_mode(other_android[0])

    # Check for Samsung Download Mode (Odin mode / HID / download PIDs) FIRST
    try:
        hid_targets = bridge.list_samsung_hid()
        if hid_targets:
            return "DOWNLOAD MODE (Samsung Odin / Download)"
    except Exception:
        pass

    for d in samsung:
        pid = d.get("pid")
        if pid in (0x685D, 0x685C, 0x685B, 0x685F) or any(i.get("class") == 3 for i in d.get("interfaces", [])):
            return "DOWNLOAD MODE (Samsung Odin / Download)"

    # Spreadtrum feature-phone download/engineering port (1782:4d00 FDL/BROM).
    for d in (spd_devs or []):
        mode = _spd_mode(d)
        if mode:
            return mode

    # A Qualcomm device that is NOT in EDL (e.g. a modem in normal mode).
    if qcom_devs:
        # HS-USB Diagnostics (05c6:9006) and the 9026 diag composite are a
        # distinct mode - name it, do not fold into generic Qualcomm.
        if any(d.get("pid") in (0x9006, 0x9026) for d in qcom_devs):
            pids = sorted(set(d.get("pid", 0) for d in qcom_devs if d.get("pid") in (0x9006, 0x9026)))
            tag = "".join(f"{p:04x}/" for p in pids).rstrip("/")
            return f"QUALCOMM DIAG MODE (HS-USB Diagnostics {tag})"
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
    # Generic ADB transport (non-Samsung VID or Samsung without USB descriptor)
    # was previously mis-reported as OTHER MODE because the interface scan only
    # looked at `samsung` devices. Detect authorized ADB directly from adbd state.
    if "device" in adb_states:
        return "ADB ENABLED (debug composite) - normal boot"

    # Interface-based protocol naming (ALL device lists, not just Samsung):
    # a phone that fell through the mode branches above (e.g. a Tecno in
    # PTP/MTP on the MTK VID, no ADB row) must still get its actual USB
    # protocol named - never a bare "OTHER".
    adb = image = hid = diag = storage = ptp = rndis = False
    all_devs = (samsung + (mtk_devs or []) + (fastboot or []) + (edl_devs or [])
                + (qcom_devs or []) + (spd_devs or []) + (apple_devs or [])
                + (other_android or []))
    for d in all_devs:
        ifaces = d.get("interfaces") or []
        if _has_adb_iface(ifaces):
            adb = True
        image = image or any(i["class"] == 6 for i in ifaces)
        hid = hid or any(i["class"] == 3 for i in ifaces)
        diag = diag or any(
            i["class"] == 2 and i["subclass"] == 2 and i["protocol"] == 1
            for i in ifaces
        )
        storage = storage or any(i["class"] == 8 for i in ifaces)
        ptp = ptp or any(i["class"] == 6 and i["subclass"] == 1 for i in ifaces)
        rndis = rndis or any(
            i["class"] == 0xEF and i["subclass"] == 4 and i["protocol"] == 1
            for i in ifaces
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
        # Only flashing-mode PIDs claim the low-level label. Any other PID
        # (e.g. a normal-boot Tecno in PTP/MTP: 0e8d:2008, product string
        # "Android ADB Interface") must fall through to interface-based
        # protocol naming below - the badge names the actual USB protocol.
        if pid == 0x0003:
            return f"{prefix} BROM (held state)"
        elif pid == 0x2000:
            return f"{prefix} PRELOADER (first bootloader stage)"
        elif pid in (0x0004, 0x1004):
            return f"{prefix} DA (flashing active)"
    
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
    # Last resort for an MTK device with no recognizable protocol
    # interface (vendor-specific modem port): name the vendor + PID
    # instead of a bare OTHER.
    for d in (mtk_devs or []):
        return f"MEDIATEK MODE (VID 0x0E8D PID 0x{d.get('pid', 0) & 0xFFFF:04X})"
    return "OTHER MODE"


# ---------------------------------------------------------------------------
# Premium composable widgets
# ---------------------------------------------------------------------------
def _metal_gradient(x0, y0, x1, y1):
    g = QLinearGradient(x0, y0, x1, y1)
    g.setColorAt(0.00, QColor("#e8edf2"))
    g.setColorAt(0.18, QColor("#f7f9fb"))
    g.setColorAt(0.45, QColor("#b9c2cc"))
    g.setColorAt(0.55, QColor("#9aa5b1"))
    g.setColorAt(1.00, QColor("#6b7683"))
    return g


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

        # Premium deep space background with rich gradient
        bg_grad = QLinearGradient(0, 0, w, h)
        bg_grad.setColorAt(0, QColor("#0f172a"))
        bg_grad.setColorAt(0.3, QColor("#1e293b"))
        bg_grad.setColorAt(0.7, QColor("#0f172a"))
        bg_grad.setColorAt(1, QColor("#020617"))
        p.setBrush(bg_grad)
        p.setPen(QPen(QColor(C["border_hi"]), 1.5))
        p.drawRoundedRect(QRectF(0, 0, w - 1, h - 1), 16, 16)

        # Animated circuit grid with premium glow
        grid = QColor(C["accent"])
        grid.setAlpha(20)
        p.setPen(QPen(grid, 1.2))
        step = 28.0
        gx = 0.0
        while gx < w:
            p.drawLine(QPointF(gx, 0), QPointF(gx, h))
            gx += step
        gy = 0.0
        while gy < h:
            p.drawLine(QPointF(0, gy), QPointF(w, gy))
            gy += step

        # Premium radial glow with multiple layers
        glow1 = QRadialGradient(w / 2, 140, 250)
        glow1.setColorAt(0, QColor(99, 102, 241, 60))
        glow1.setColorAt(0.5, QColor(139, 92, 246, 30))
        glow1.setColorAt(1, QColor(139, 92, 246, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow1)
        p.drawRect(QRect(0, 0, w, h))

        # Secondary accent glow
        glow2 = QRadialGradient(w / 2, 180, 180)
        glow2.setColorAt(0, QColor(34, 211, 238, 35))
        glow2.setColorAt(1, QColor(34, 211, 238, 0))
        p.setBrush(glow2)
        p.drawRect(QRect(0, 0, w, h))

        # Premium top accent bar with enhanced pulse
        pulse = 0.75 + 0.25 * math.sin(self._pulse)
        ag = QLinearGradient(0, 0, w, 0)
        ag.setColorAt(0, QColor("#6366f1"))
        ag.setColorAt(0.5, QColor("#8b5cf6"))
        ag.setColorAt(1, QColor("#22d3ee"))
        p.setBrush(ag)
        p.setOpacity(pulse)
        p.drawRoundedRect(QRectF(24, 18, w - 48, 5), 2.5, 2.5)
        p.setOpacity(self._alpha)

        # Enhanced logo with glow effect
        logo_size = 128
        logo_rect = QRect((w - logo_size) // 2, 38, logo_size, logo_size)
        
        # Logo glow
        logo_glow = QRadialGradient(QPointF(logo_rect.center()), logo_size * 0.8)
        logo_glow.setColorAt(0, QColor(99, 102, 241, 50))
        logo_glow.setColorAt(1, QColor(99, 102, 241, 0))
        p.setBrush(logo_glow)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(logo_rect)
        
        p.drawPixmap(logo_rect, _draw_logo(logo_size))

        # Premium title with gradient text effect
        p.setFont(QFont("Inter", 22, QFont.Weight.ExtraBold))
        p.setPen(QPen(QColor("#f8fafc")))
        p.drawText(
            QRectF(0, 178, w, 38),
            Qt.AlignmentFlag.AlignCenter,
            "FlashPilot",
        )

        # Subtitle
        p.setFont(QFont("Inter", 11, QFont.Weight.Medium))
        p.setPen(QPen(QColor(C["accent_hi"])))
        p.drawText(
            QRectF(0, 208, w, 24),
            Qt.AlignmentFlag.AlignCenter,
            "Professional Flashing Tool",
        )

        # Premium tagline
        p.setFont(QFont("JetBrains Mono", 9, QFont.Weight.DemiBold))
        p.setPen(QPen(QColor(C["accent"])))
        p.drawText(
            QRectF(0, 235, w, 22),
            Qt.AlignmentFlag.AlignCenter,
            "FRP  ·  FLASHING  ·  MTK  ·  QUALCOMM  ·  SPD",
        )

        # Premium segmented progress bar with glow
        bar_w, bar_h = w - 100, 12
        bx = (w - bar_w) / 2
        by = 272
        segs = 35
        seg_w = (bar_w - (segs - 1) * 3) / segs
        filled = int(segs * self._progress)
        
        # Progress bar background glow
        if filled > 0:
            progress_glow = QRadialGradient(bx + bar_w/2, by + bar_h/2, bar_w)
            progress_glow.setColorAt(0, QColor(99, 102, 241, 30))
            progress_glow.setColorAt(1, QColor(99, 102, 241, 0))
            p.setBrush(progress_glow)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(bx - 20, by - 10, bar_w + 40, bar_h + 20))
        
        for i in range(segs):
            sx = bx + i * (seg_w + 3)
            if i < filled:
                gr = QLinearGradient(sx, 0, sx + seg_w, 0)
                gr.setColorAt(0, QColor("#6366f1"))
                gr.setColorAt(0.5, QColor("#8b5cf6"))
                gr.setColorAt(1, QColor("#22d3ee"))
                p.setBrush(gr)
            else:
                p.setBrush(QColor(255, 255, 255, 20))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(sx, by, seg_w, bar_h), 2, 2)

        # Premium status line with accent
        p.setFont(QFont("Inter", 10, QFont.Weight.Medium))
        p.setPen(QPen(QColor(C["text"])))
        p.drawText(
            QRectF(0, 298, w, 22),
            Qt.AlignmentFlag.AlignCenter,
            _SPLASH_MESSAGES[self._msg_idx],
        )

        # Premium footer with enhanced styling
        footer_grad = QLinearGradient(0, 0, w, 0)
        footer_grad.setColorAt(0, QColor(C["accent"]))
        footer_grad.setColorAt(0.5, QColor(C["accent_hi"]))
        footer_grad.setColorAt(1, QColor(C["accent"]))
        chips = "SAMSUNG  /  MEDIATEK  /  QUALCOMM  /  UNISOC"
        p.setFont(QFont("Inter", 9, QFont.Weight.DemiBold))
        text_pen = QPen()
        text_pen.setBrush(footer_grad)
        p.setPen(text_pen)
        p.drawText(
            QRectF(0, 330, w, 20),
            Qt.AlignmentFlag.AlignCenter,
            chips,
        )

        # Version info - beta shows beta tag + exact display version
        p.setFont(QFont("JetBrains Mono", 8))
        p.setPen(QPen(QColor(C["mute"])))
        _ver_disp = _display_version(APP_VERSION)
        _beta_suffix = "  BETA" if _is_beta_version(APP_VERSION) else ""
        p.drawText(
            QRectF(0, 352, w, 16),
            Qt.AlignmentFlag.AlignCenter,
            f"v{_ver_disp}{_beta_suffix}  |  Legendary-Brilliantforous",
        )

        p.end()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class FlashPilotWindow(
    SamsungPageMixin,
    QuickPageMixin,
    GeneralPageMixin,
    FusPageMixin,
    MtkPageMixin,
    QcPageMixin,
    SpdPageMixin,
    SettingsPageMixin,
    FlowRenderMixin,
    QMainWindow,
):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlashPilot")

        self._cached_model = None
        self._cached_adb_status = None
        self._cached_build = None
        self._cached_android = None
        self._cached_serial = None
        self._update_in_progress = False
        self._last_pid = None
        self._device_connected = False
        self._last_has_adb = False
        self._last_usb_product = None
        self._maximized = False
        self._log_buffer = []
        # Parallel tuple of the *raw* (ANSI-bearing) messages, index-aligned
        # with _log_buffer. ANSI codes are stripped from _log_buffer (so
        # search/copy/save stay clean) but kept here so a rebuild can restore
        # their colour mapping.
        self._log_ansi = []
        # Coalesced widget appends (S2b batching): the first line renders
        # synchronously, the rest flush on a single-shot timer / size cap.
        self._pending_console = []
        self._console_flush_timer = None
        self._filter = {"err": True, "warn": True, "ok": True, "info": True}
        self._console_search_text = ""
        self._console_regex = False
        self._console_regex_obj = None
        self._show_timestamps = True
        # stop button -> active FlashJob id for per-device STOP (chip pages).
        # A page stop cancels exactly its own job's device scope; entries are
        # replaced on each run and cleared when the worker finishes.
        self._stop_job = {}
        # Capability-gated buttons: (weakref, job, mode, command, base tip).
        # _refresh_gates() enables/disables them from bridge.actions_for()
        # for the displayed device. Display-only and fail-open; enforcement
        # stays in the pre-execution gate.
        self._gated_buttons = []
        self._gate_cache = {}
        self._combo_styled = False
        self._anim_enabled = True
        self.settings = QSettings("FlashPilot", "FlashingTool")

        # apply persisted accent theme before any widget styles are generated
        theme = self.settings.value("theme", "Neon Circuit")
        if theme in ACCENT_THEMES:
            C.update(ACCENT_THEMES[theme])

        # Fit the window to the available screen so it is never cut off.
        screen = QApplication.primaryScreen().availableGeometry()
        fit_w = min(1180, max(940, screen.width() - 140))
        fit_h = min(720, max(600, screen.height() - 110))
        self.setMinimumSize(fit_w, fit_h)
        self.resize(fit_w, fit_h)

        # Frameless, translucent window with a rounded root card.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Premium typography: try Inter, fallback to system
        for fam in ("Inter", "JetBrains Mono"):
            try:
                QFontDatabase.addApplicationFont(f"/usr/share/fonts/truetype/{fam.lower().replace(' ', '-')}.ttf")
            except Exception:
                pass
        app_font = QFont("Inter", 10)
        app_font.setStyleHint(QFont.StyleHint.SansSerif)
        app_font.setWeight(QFont.Weight.Medium)
        if QFontDatabase.families().__contains__("Inter"):
            QApplication.instance().setFont(app_font)
        else:
            sys_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
            sys_font.setPointSize(10)
            QApplication.instance().setFont(sys_font)

        self.setStyleSheet(_get_base_qss() + _console_qss())

        self._build_ui()
        # Global fix: action buttons should not retain focus rect (was flashing red in Crimson)
        for btn in self.findChildren(QPushButton):
            if not btn.isCheckable():
                btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                btn.setAutoDefault(False)
                btn.setDefault(False)
        if hasattr(self, "oem_bar"): self.oem_bar.select("samsung")

        # apply persisted effect settings to the freshly-built widgets
        if not self.settings.value("animations", "true", type=bool):
            self.scene.set_animations(False)
            self.orb.set_animations(False)
        if not self.settings.value("blur", "true", type=bool):
            self._root_shadow.setEnabled(False)

        # toast overlay on top of everything (corner from toast/position)
        self._toasts = ToastHost(
            self,
            position=str(self.settings.value("toast/position", "top-right")),
        )
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

        # Separate flags: model refresh and update check must not block each other
        self._model_refresh_in_progress = False
        self._update_in_progress = False
        self._update_check_in_progress = False
        if self.settings.value("auto_update_check", False, type=bool):
            self._auto_update_timer = QTimer(self)
            self._auto_update_timer.setSingleShot(True)
            self._auto_update_timer.timeout.connect(self._check_update)
            self._auto_update_timer.start(15000)

        self._install_shortcuts()
        # Global shake: when enabled, any button tap shakes itself + the trio
        try:
            QApplication.instance().installEventFilter(self)
        except Exception:
            pass
        self.refresh_device()
        try:
            self.update_device_strip()
        except Exception:
            pass
        self.log_line(
            f"FlashPilot — console ready "
            f"({_time.strftime('%Y-%m-%d %H:%M:%S')})"
        )
        # Beta gate: the installed version IS the beta channel (what the user
        # downloaded). Latest stable is never hand-coded — it is fetched live
        # from GitHub in _check_update_thread. Show the acceptance dialog once
        # per beta version so the risk text is never "out of focus" toast.
        if _is_beta_version(APP_VERSION):
            QTimer.singleShot(1200, self._show_beta_gate_async)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._combo_styled:
            self._combo_styled = True
            self._restyle_combos()
        # Apply the console dock split now the window has a real size.
        self._apply_default_dock_split()
        self._apply_default_body_split()
        # The first show can run before the splitter's first layout pass, so
        # the call above still sees width() <= 0 and returns early. If no
        # resize ever follows (a script that just show()s the window, or a
        # restore that lands on the same geometry) the panel would keep the
        # splitter's 50/50 default. Re-apply once after the first real layout
        # pass: `_apply_default_body_split` still no-ops once the user has
        # dragged (`_body_user_moved`) and still honours a persisted width.
        QTimer.singleShot(0, self._apply_default_body_split)
        # Window open — geometry + fade via effect on Linux (once per show)
        if not getattr(self, "_shown_anim", False):
            self._shown_anim = True
            try:
                import sys
                if self.settings.value("animations", "true", type=bool) and self.settings.value("anim_window", "true", type=bool):
                    from .animations import Motion
                    if not sys.platform.startswith("linux"):
                        self.setWindowOpacity(0.0)
                    Motion.window_open(self, dur=260)
                else:
                    if not sys.platform.startswith("linux"):
                        self.setWindowOpacity(1.0)
            except Exception:
                pass

    def eventFilter(self, obj, event):
        # Global shake/rubber cascade: respects separate toggles + master
        try:
            from PyQt6.QtWidgets import QPushButton
            if event.type() == QEvent.Type.MouseButtonPress and isinstance(obj, QPushButton):
                master = self.settings.value("animations", "true", type=bool)
                if not master:
                    return super().eventFilter(obj, event)
                trio = getattr(self, "_anim_preview_trio", [])
                if obj in trio:
                    return super().eventFilter(obj, event)
                from .animations import Motion
                do_shake = self.settings.value("anim_shake", "true", type=bool)
                do_rubber = self.settings.value("anim_rubber", "true", type=bool)
                # Shake + rubber both touch geometry/stylesheet — never run concurrently or they leave red border / shrunk fixedSize.
                if do_shake and do_rubber:
                    Motion.shake(obj, amplitude=5)
                    for b in trio:
                        Motion.shake(b, amplitude=4)
                    # Queue rubber after shake finishes (lock also guards, but explicit sequencing is clearer).
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(420, lambda o=obj, t=list(trio): [Motion.rubber(o, scale=1.06, dur=380)] + [Motion.rubber(b, scale=1.04, dur=360) for b in t])
                elif do_shake:
                    Motion.shake(obj, amplitude=5)
                    for b in trio:
                        Motion.shake(b, amplitude=4)
                elif do_rubber:
                    Motion.rubber(obj, scale=1.06, dur=380)
                    for b in trio:
                        Motion.rubber(b, scale=1.04, dur=360)
        except Exception:
            pass
        return super().eventFilter(obj, event)

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
        QShortcut(QKeySequence("Ctrl+,"), self).activated.connect(
            lambda: self._on_section("settings"))
        # F11 — console full-screen (terminal) mode; fully reversible.
        QShortcut(QKeySequence("F11"), self).activated.connect(
            self._toggle_console_maximised)

    # ----------------------------- layout builders -------------------------
    def _build_ui(self):
        central = QWidget()
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)

        root = QFrame()
        root.setObjectName("root")
        root.setStyleSheet(
            f"QFrame#root {{ background:"
            f" qradialgradient(cx:0.5, cy:-0.15, radius:1.2,"
            f"   stop:0 rgba(23, 37, 60, 248), stop:1 rgba(5, 9, 15, 246));"
            f" border: 1px solid {C['border_hi']}; border-top: 2px solid {C['border_hi']};"
            f" border-radius: 16px; }}"
        )
        root_shadow = QGraphicsDropShadowEffect(root)
        root_shadow.setBlurRadius(64)
        root_shadow.setOffset(0, 18)
        root_shadow.setColor(QColor(0, 0, 0, 210))
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
        outer.setContentsMargins(14, 10, 14, 10)
        outer.addWidget(root)
        self._outer = outer

        # --- custom title bar ---
        titlebar = DragBar(self)
        titlebar.setFixedHeight(46)
        titlebar.setObjectName("dragbar")
        titlebar.setStyleSheet(
            f"QWidget#dragbar {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f" stop:0 rgba(20, 32, 50, 110), stop:0.5 rgba(10, 15, 23, 0),"
            f" stop:1 rgba(20, 32, 50, 110));"
            f" border-bottom: 1px solid rgba(255,255,255,0.055); }}"
        )
        tb = QHBoxLayout(titlebar)
        tb.setContentsMargins(12, 4, 8, 2)
        tb.setSpacing(12)

        logo = QLabel()
        logo.setPixmap(_draw_logo(30))
        tb.addWidget(logo, 0, Qt.AlignmentFlag.AlignVCenter)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        _disp_ver = _display_version(APP_VERSION)
        _is_beta_tb = _is_beta_version(APP_VERSION)
        title_text = "flashpilot FLASHING TOOL"
        if _is_beta_tb:
            title_text += f"  —  BETA  v{_disp_ver}"
        title = QLabel(title_text)
        title.setStyleSheet(
            f"color:{C['text']}; font-size:16px; font-weight:800; letter-spacing:1.5px;"
            + (" color: #fbbf24;" if _is_beta_tb else "")
        )
        sub = QLabel("FRP bypass · screen lock · download mode & ADB tooling"
                     + ("  •  BETA build" if _is_beta_tb else ""))
        sub.setStyleSheet(
            f"color:{C['mute']}; font-size:10px;"
            f" font-family:'JetBrains Mono','Consolas',monospace;"
        )
        title_box.addWidget(title)
        title_box.addWidget(sub)
        tb.addLayout(title_box)

        tb.addStretch(1)

        # Global Stop — single button outside any chip card, stops ANY process
        self.global_stop_btn = QPushButton("⏹  STOP")
        self.global_stop_btn.setEnabled(False)
        self.global_stop_btn.setStyleSheet(
            "QPushButton { color: #ffffff; background: #334155; border: 1px solid #475569; border-radius: 8px; padding: 6px 16px; font-weight: 900; font-size: 12px; letter-spacing: 0.8px; }"
            "QPushButton:enabled { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #dc2626, stop:1 #ef4444); border-color: #ef4444; }"
            "QPushButton:hover:enabled { background: #ef4444; border-color: #f87171; }"
            "QPushButton:disabled { color: #64748b; background: #1e293b; border-color: #334155; }"
        )
        self.global_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.global_stop_btn.setToolTip("Stop any running operation (Ctrl+Esc) — works for Samsung/MTK/Qualcomm/SPD")
        self.global_stop_btn.clicked.connect(self.on_stop)

        # Header Settings — frees the rail slot (compact top-right gear)
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(32, 32)
        self.settings_btn.setToolTip("Settings (Ctrl+,)")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setStyleSheet(
            "QPushButton { color:#cbd5e1; background:rgba(255,255,255,8);"
            " border:1px solid rgba(255,255,255,12); border-radius:16px;"
            " font-size:15px; font-weight:800; }"
            "QPushButton:hover { background:#334155; color:#fff; }"
        )
        self.settings_btn.clicked.connect(lambda: self._on_section("settings"))
        tb.addWidget(self.settings_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.global_stop_btn.setFixedHeight(32)
        self.global_stop_btn.setMinimumWidth(110)
        tb.addWidget(self.global_stop_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        # Auto-sync: global STOP is enabled while ANY device has an op running.
        self._global_stop_timer = QTimer(self)
        self._global_stop_timer.timeout.connect(lambda: self.global_stop_btn.setEnabled(_flows_running() > 0))
        self._global_stop_timer.start(150)
        # Per-row job-state chips: driven from the JobManager, no second
        # scan. Terminal states hold briefly (their chip shows), then the
        # row goes idle again.
        self._row_widgets = {}
        self._row_state_timer = QTimer(self)
        self._row_state_timer.timeout.connect(self._refresh_row_states)
        self._row_state_timer.start(600)
        # Keyboard nav: Enter/double-click on the device list picks that
        # device (arrows move the selection natively in QListWidget).
        try:
            self.device_list.itemActivated.connect(self._on_device_picked)
            self.device_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        except Exception:
            pass

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

        # --- content: OEM chips on top, scene on left, page fills middle ---
        self._section_index = {"samsung": 0}
        samsung_icon = next((b.get('icon', 'Ⓢ') for b in device_pages.BRANDS if b['key'] == 'samsung'), 'Ⓢ')
        oem_items = [("samsung", samsung_icon, "Samsung")]
        for b in device_pages.BRANDS:
            if b["key"] == "samsung":
                continue
            oem_items.append((f"dev_{b['key']}", b.get('icon', '▣'), b['label']))
        oem_items.append(("general", "⚡", "General"))
        tools = [
            ("fus", "⬇", "FUS"),
            ("mtk", "▣", "MTK"),
            ("qc", "◈", "Qualcomm"),
            ("spd", "✦", "SPD"),
        ]
        self.oem_bar = OemChipBar(oem_items, tools=tools)
        self.oem_bar.section_selected.connect(self._on_section)
        root_lay.addWidget(self.oem_bar)
        self._apply_tool_relevance()

        # Phase-1 device-first strip: connected phone (model · mode ·
        # transports) + manual refresh. Updates on section change and
        # drives the drill-down dimming pass (nothing removed, nothing
        # rerouted — non-applicable buttons only dim).
        self._dev_strip = QFrame()
        self._dev_strip.setObjectName("devstrip")
        self._dev_strip.setStyleSheet(
            f"QFrame#devstrip {{ background: rgba(16, 25, 39, 230);"
            f" border:1px solid {C['border']}; border-radius:9px; }}"
        )
        _strip_lay = QHBoxLayout(self._dev_strip)
        _strip_lay.setContentsMargins(12, 5, 8, 5)
        _strip_lay.setSpacing(8)
        self._dev_dot = QLabel("○")
        self._dev_dot.setStyleSheet(f"color:{C['dim']}; font-size:15px; font-weight:800;")
        _strip_lay.addWidget(self._dev_dot)
        _dev_txt_col = QVBoxLayout()
        _dev_txt_col.setContentsMargins(0, 0, 0, 0)
        _dev_txt_col.setSpacing(0)
        self._dev_title = QLabel("No phone detected")
        self._dev_title.setStyleSheet(f"color:{C['text']}; font-size:12px; font-weight:800;")
        _dev_txt_col.addWidget(self._dev_title)
        self._dev_text = QLabel("Connect a device over USB")
        self._dev_text.setStyleSheet(f"color:{C['dim']}; font-size:10px;")
        _dev_txt_col.addWidget(self._dev_text)
        _strip_lay.addLayout(_dev_txt_col, 1)
        # Transports dropdown: ADB hub / Fastboot hub / CMD console.
        # Fastboot hub lands in the next slice — greyed with a reason,
        # never a dead popup.
        self._transport_combo = QComboBox()
        self._transport_combo.addItems(
            ["Transports", "ADB Hub", "Fastboot Hub", "Easy Login", "CMD Console"])
        self._transport_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._transport_combo.setFixedWidth(118)
        self._transport_combo.setToolTip("Open a transport hub")
        self._transport_combo.setStyleSheet(
            f"QComboBox {{ background:{C['card']}; border:1px solid {C['border']};"
            f" border-radius:6px; padding:3px 8px; color:{C['text']}; font-size:10px; font-weight:700; }}"
            f" QComboBox:hover {{ border:1px solid {C['border_hi']}; }}"
            f" QComboBox:focus {{ outline:none; }}"
            f" QComboBox QAbstractItemView {{ background:{C['card']}; color:{C['text']};"
            f" selection-background-color:{C['accent']}; }}"
        )
        try:
            self._transport_combo.model().item(2).setToolTip("Fastboot presets in the CMD tab")
        except Exception:
            pass
        self._transport_combo.activated.connect(self._on_transport_pick)
        _strip_lay.addWidget(self._transport_combo)
        _strip_refresh = QPushButton("⟳")
        _strip_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        _strip_refresh.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _strip_refresh.setFixedSize(26, 24)
        _strip_refresh.setToolTip("Re-detect the connected phone")
        _strip_refresh.setStyleSheet(
            "QPushButton { color:#8fa4bd; background:rgba(255,255,255,9);"
            " border:1px solid rgba(255,255,255,0.08); border-radius:6px; font-size:12px; }"
            " QPushButton:hover { color:#e2e8f0; border-color:rgba(255,255,255,0.22); }"
            " QPushButton:focus { outline:none; }"
        )
        _strip_refresh.clicked.connect(
            lambda: (device_pages.invalidate_connected_cache(),
                     self.update_device_strip()))
        _strip_lay.addWidget(_strip_refresh)
        root_lay.addWidget(self._dev_strip)


        body = QHBoxLayout()
        body.setContentsMargins(10, 4, 10, 6)
        body.setSpacing(10)

        # Persisted device-panel width for the body split (tolerates bad values).
        try:
            self._device_panel_width = int(
                self.settings.value("layout/device_panel_width", 0))
        except (TypeError, ValueError):
            self._device_panel_width = 0
        if self._device_panel_width <= 0:
            self._device_panel_width = None
        # Set once the user drags the panel divider: until then the panel keeps
        # its desired width as the window resizes.
        self._body_user_moved = False

        self._device_stacks = {}
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("QStackedWidget { background: transparent; }")

        # Samsung hub page (operations/console panel).
        dash = QWidget()
        dash_lay = QHBoxLayout(dash)
        dash_lay.setContentsMargins(0, 0, 0, 0)
        dash_lay.setSpacing(14)
        dash_lay.addWidget(self._build_right(), 1)
        self._stack.addWidget(dash)

        # Brand drill-down pages (level 2/3 live inside each stack entry).
        # Samsung's Supported-Devices lives INSIDE the Samsung hub instead.
        self._device_stacks = getattr(self, "_device_stacks", {})
        for b in device_pages.BRANDS:
            if b["key"] == "samsung":
                continue
            self._stack.addWidget(device_pages.build_brand_page(self, b["key"]))
            self._section_index[f"dev_{b['key']}"] = len(self._section_index)

        gen = self._build_general_page()

        for key, widget in (
            ("general", gen),
            ("adb", device_pages.build_adb_hub_page(self)),
            ("fastboot", device_pages.build_fastboot_hub_page(self)),
            ("easylogin", device_pages.build_easylogin_hub_page(self)),
            ("fus", self._build_fus_page()),
            ("mtk", self._build_mtk_page()),
            ("qc", self._build_qc_page()),
            ("spd", self._build_spd_page()),
            ("settings", self._build_settings_page()),
        ):
            self._stack.addWidget(widget)
            self._section_index[key] = len(self._section_index)

        # LEFT: connection scene (keeps its size) + state + compact metrics.
        left_panel = QFrame()
        left_panel.setObjectName("connbar")
        self._conn = left_panel
        # Draggable in the body splitter below: a floor and a cap instead of a
        # hard 232px, so the page can be given more or less room.
        left_panel.setMinimumWidth(self._BODY_PANEL_MIN_W)
        left_panel.setMaximumWidth(self._BODY_PANEL_MAX_W)
        left_panel.setStyleSheet(
            f"QFrame#connbar {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 rgba(15, 24, 38, 225), stop:1 rgba(7, 12, 19, 230));"
            f" border: 1px solid {C['border']}; border-top: 1px solid {C['border_hi']};"
            f" border-radius: 9px; }}"
        )
        ll = QVBoxLayout(left_panel)
        ll.setContentsMargins(10, 8, 10, 8)
        ll.setSpacing(6)
        self.scene = ConnectionScene()
        self.scene.setMinimumHeight(120)
        ll.addWidget(self.scene, 1)

        srow = QHBoxLayout()
        srow.setSpacing(6)
        self.orb = StatusOrb()
        srow.addWidget(self.orb, 0, Qt.AlignmentFlag.AlignTop)
        self.conn_state = QLabel("No device connected")
        self.conn_state.setWordWrap(True)
        self.conn_state.setStyleSheet(
            f"color:{C['dim']}; font-size:10px; font-weight:500; background:transparent;"
        )
        srow.addWidget(self.conn_state, 1)
        ll.addLayout(srow)

        # Multi-device list: one row per connected phone (model · transports).
        # Clicking a row switches the detail tiles/scene to that device
        # (display only — each operation still picks its own target).
        self._display_key = None
        self.device_list = QListWidget()
        self.device_list.setMaximumHeight(96)
        self.device_list.setStyleSheet(
            f"QListWidget {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; color:{C['text']}; font-size:11px; }}"
            f"QListWidget::item {{ padding:4px 6px; border-bottom:1px solid {C['border']}; }}"
            f"QListWidget::item:selected {{ background:{C['accent_dim']}; color:{C['accent_hi']}; }}"
        )
        self.device_list.setToolTip("Connected devices — click to inspect one")
        self.device_list.itemClicked.connect(self._on_device_picked)
        ll.addWidget(self.device_list)

        mgrid = QGridLayout()
        mgrid.setSpacing(4)
        self.info = {}
        tiles = [
            ("Device Model", C["grad_b"]), ("USB Mode", C["accent"]),
            ("Interface", C["ok"]), ("ADB Status", C["warn"]),
            ("Build Number", C["warn_dim"]), ("Android Ver", C["ok_dim"]),
            ("Serial", C["err_dim"]), ("PIT Health", C["err_dim"]),
        ]
        for i, (name, accent) in enumerate(tiles):
            card = MetricCard(name, "--", accent)
            self.info[name] = card
            mgrid.addWidget(card, i // 2, i % 2)
        for i in range(2):
            mgrid.setColumnStretch(i, 1)
        for r in range((len(tiles) + 1) // 2):
            mgrid.setRowStretch(r, 1)
        ll.addLayout(mgrid)
        # Quick "Copy Info" helper for current device
        self.info_copy_btn = QPushButton("Copy Device Info")
        self.info_copy_btn.setStyleSheet(_btn_ghost())
        self.info_copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.info_copy_btn.setToolTip("Copy model / build / android / serial to clipboard")
        self.info_copy_btn.clicked.connect(self._copy_device_info)
        ll.addWidget(self.info_copy_btn)

        # DEVICE PANEL | PAGE: draggable divider. Stretch factors (0, 1) keep the
        # panel at the width the user chose while the page absorbs every window
        # resize. Neither side is collapsible, so a drag can never hide one.
        # The page lives in a frame-less scroll area that is transparent when it
        # fits, and scrolls sideways when the user squeezes it instead of
        # clipping its own tabs and firmware grid.
        self._page_scroll = QScrollArea()
        self._page_scroll.setWidgetResizable(True)
        self._page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._page_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._page_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }")
        # The page keeps its own natural minimum width (so it never reflows into
        # a broken layout — the scrollbar takes over instead), while the viewport
        # itself may be dragged down to 240px on a narrow window.
        self._page_scroll.setMinimumWidth(self._PAGE_VIEW_MIN_W)
        self._page_scroll.setWidget(self._stack)

        self._body_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._body_splitter.setObjectName("bodySplit")
        self._body_splitter.setChildrenCollapsible(False)
        self._body_splitter.setHandleWidth(6)
        self._body_splitter.addWidget(left_panel)
        self._body_splitter.addWidget(self._page_scroll)
        self._body_splitter.setCollapsible(0, False)
        self._body_splitter.setCollapsible(1, False)
        self._body_splitter.setStretchFactor(0, 0)
        self._body_splitter.setStretchFactor(1, 1)
        self._body_splitter.splitterMoved.connect(self._on_body_splitter_moved)
        self._body_splitter.setStyleSheet(_splitter_qss())
        body.addWidget(self._body_splitter, 1)

        # LEFT: connection panel + content page stack.
        self._top_area = QWidget()
        self._top_area.setStyleSheet("background: transparent;")
        self._top_area.setLayout(body)
        self._top_area.setMinimumWidth(self._DOCK_MIN_TOP)

        # RIGHT dock: the shared console is resizable (horizontal splitter,
        # console on the right) + collapsible (header chevron).
        self._console_dock = self._build_console()
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("consoleDock")
        self._splitter.setChildrenCollapsible(True)
        self._splitter.setHandleWidth(6)
        self._splitter.addWidget(self._top_area)
        self._splitter.addWidget(self._console_dock)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.splitterMoved.connect(self._on_dock_splitter_moved)
        self._style_console_splitter()
        self._apply_console_state_from_settings()

        root_lay.addWidget(self._splitter, 1)

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
            f" border: 1px solid {C['border']}; border-top: 1px solid {C['border_hi']};"
            f" border-radius: 9px; }}"
            f" QFrame#connbar:hover {{ border: 1px solid {C['border_hi']};"
            f" background: rgba(16, 25, 39, 230); }}"
        )
        conn_lay = QHBoxLayout(conn)
        conn_lay.setContentsMargins(10, 5, 10, 5)
        conn_lay.setSpacing(14)

        # left: animated computer -- cable -- phone scene + orb + state
        left = QVBoxLayout()
        left.setSpacing(4)
        self.scene = ConnectionScene()
        self.scene.setMinimumHeight(54)
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

        # right: live device metric cards (model / mode / interface / adb / pit)
        grid = QGridLayout()
        grid.setSpacing(6)
        self.info = {}
        tiles = [
            ("Device Model", C["grad_b"]),
            ("USB Mode", C["accent"]),
            ("Interface", C["ok"]),
            ("ADB Status", C["warn"]),
            ("PIT Health", C["err_dim"]),
        ]
        for i, (name, accent) in enumerate(tiles):
            card = MetricCard(name, "--", accent)
            self.info[name] = card
            grid.addWidget(card, 0, i)   # single horizontal row -> banner stays short
            grid.setColumnStretch(i, 1)
        conn_lay.addLayout(grid, 2)

        return conn

    # ---- console dock geometry (S2a) ------------------------------------
    # The console is a RIGHT-hand dock: a horizontal splitter shares the
    # content area between the page stack (left) and the console (right).
    # The minimum is measured from the dock's own content (widest row is the
    # filter row: 4 level chips + the "auto-clear" checkbox at ~360px), so
    # dragging the handle can never clip a console control.
    _DOCK_MIN_CONSOLE = 360      # px — console dock minimum width (expanded)
    # The top area now holds the draggable device-panel | page split, so its
    # floor is that split's own floor: panel + page viewport + handle. The page
    # *content* floor is higher (`_PAGE_MIN_W`) — below it the page scrolls
    # sideways instead of clipping, so the window can stay reasonably narrow.
    _DOCK_MIN_TOP = 228 + 240 + 6   # px — page area minimum width
    _DOCK_DEFAULT_WIDTH = 420    # px — default console width (right dock)
    _DOCK_COLLAPSED_W = 44       # px — thin bar width when collapsed

    # ---- body split (device panel | page) -------------------------------
    # The device/connection panel is draggable instead of a hard 232px width;
    # the page stack keeps the rest and absorbs window resizes. Both sides are
    # bounded by their content minimum so neither ever clips: the panel at
    # 228px (its metric tiles) and the page at its own natural width, under
    # which the page scrolls sideways rather than cutting its tabs/grid.
    _BODY_PANEL_DEFAULT_W = 232  # px — default device panel width
    _BODY_PANEL_MIN_W = 228      # px — panel content minimum (tiles never clip)
    _BODY_PANEL_MAX_W = 420      # px — widest the panel may be dragged
    _PAGE_VIEW_MIN_W = 240       # px — narrowest the page *viewport* may be dragged

    # ---- console streaming (S2b) ----------------------------------------
    _CONSOLE_FLUSH_MS = 50       # ms — coalesce window for batched appends
    _CONSOLE_FLUSH_MAX = 200     # lines pending before an immediate flush

    def _build_console(self):
        """Shared console dock — right-hand side panel, resizable + collapsible.

        Persisted state lives in QSettings (a config file): dock width,
        collapsed and maximised keys are restored here and tolerate
        missing/invalid values. No database is involved.
        """
        # ---- restore persisted dock state (tolerates missing/invalid) ----
        self._console_collapsed = bool(
            self.settings.value("console/collapsed", False, type=bool))
        self._console_maximised = bool(
            self.settings.value("console/maximised", False, type=bool))
        try:
            self._console_dock_width = int(
                self.settings.value("console/dock_width", 0))
        except (TypeError, ValueError):
            self._console_dock_width = 0
        if self._console_dock_width <= 0:
            self._console_dock_width = None
        # Set when the user actually drags the splitter handle: until then the
        # console keeps its desired width as the window resizes, so a transient
        # narrow first-layout pass cannot pin it (and cannot be persisted).
        self._dock_user_moved = False
        self._pre_max_sizes = None
        self._pre_max_collapsed = False

        # ---- restore persisted terminal prefs (S2b) ----
        # Timestamps and regex mode are render/search concerns only: the
        # stored transcript stays timestamp-free and always plain (no ANSI).
        self._show_timestamps = bool(
            self.settings.value("console/timestamps", True, type=bool))
        self._console_regex = bool(
            self.settings.value("console/regex", False, type=bool))
        self._console_regex_obj = None

        panel = QFrame()
        panel.setObjectName("console")
        panel.setStyleSheet(
            f"QFrame#console {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f" stop:0 rgba(14, 22, 34, 232), stop:1 rgba(7, 11, 17, 240));"
            f" border: 1px solid rgba(255,255,255,0.06);"
            f" border-left: 2px solid {C['border_hi']};"
            f" border-radius: {RADIUS['xl']}px; }}"
            f" QFrame#console:hover {{ border-color: rgba(255,255,255,0.11);"
            f" border-left-color: {C['accent_hi']};"
            f" background: rgba(16, 25, 38, 238); }}"
        )
        panel.setMinimumWidth(self._DOCK_MIN_CONSOLE)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(SPACE['md'], SPACE['sm'], SPACE['md'], SPACE['sm'])
        lay.setSpacing(SPACE['sm'])
        # Kept so the collapsed bar can tighten its own padding (a 24px chevron
        # does not fit inside the 44px bar with the expanded 12px side margins).
        self._console_layout = lay
        self._console_margins = (SPACE['md'], SPACE['sm'], SPACE['md'], SPACE['sm'])

        # ---- always-visible dock header: chevron toggle + title + count ----
        header = QHBoxLayout()
        header.setSpacing(SPACE['sm'])
        # No margins of its own: as a bare sub-layout it had none, and installing
        # it on a widget would otherwise apply the style's default 9px padding.
        header.setContentsMargins(0, 0, 0, 0)
        # Leading stretch, inert while expanded: it becomes 1 when collapsed so
        # the chevron is centred in the thin bar instead of jumping to one side.
        header.addStretch(0)
        self._console_header = header
        self.console_toggle_btn = QPushButton("▾")
        self.console_toggle_btn.setFixedSize(24, 22)
        self.console_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.console_toggle_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.console_toggle_btn.setToolTip("Collapse the console dock")
        self.console_toggle_btn.setStyleSheet(
            f"QPushButton {{ color:{C['dim']}; background:transparent;"
            f" border:1px solid {C['border']}; border-radius:{RADIUS['sm']}px;"
            f" font-size:11px; font-weight:800; padding:0; }}"
            f" QPushButton:hover {{ color:{C['accent_hi']};"
            f" border-color:{C['accent']}; }}"
        )
        self.console_toggle_btn.clicked.connect(self._toggle_console_collapse)
        header.addWidget(self.console_toggle_btn)
        self._console_title = SectionTitle("CONSOLE")
        header.addWidget(self._console_title)

        self.console_count = QLabel("0 lines")
        self.console_count.setStyleSheet(
            f"color:{C['mute']}; font-size:10px; font-weight:600; letter-spacing:1px;"
            f" font-family:'JetBrains Mono','Consolas',monospace;"
        )
        header.addWidget(self.console_count)
        header.addStretch(1)
        lay.addLayout(header)

        # ---- collapsible body: toolbar + tabs (transcript/find/filter) ----
        self._console_body = QWidget()
        self._console_body.setStyleSheet("background: transparent;")
        body_lay = QVBoxLayout(self._console_body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(SPACE['sm'])

        # ---- advanced console toolbar ----
        console_row = QHBoxLayout()
        console_row.setSpacing(SPACE['sm'])

        self.wrap_btn = self._tool_button("Wrap", self._toggle_wrap)
        self.wrap_btn.setToolTip("Toggle line wrap")
        self.wrap_btn.setFixedWidth(52)
        self.wrap_btn.setStyleSheet(self.wrap_btn.styleSheet().replace('font-size: 12px', 'font-size: 10px').replace('padding: 7px 14px', 'padding: 4px 8px'))
        console_row.addWidget(self.wrap_btn)
        self.clear_btn = self._tool_button("Clear", self._clear_console)
        self.clear_btn.setFixedWidth(52)
        self.clear_btn.setStyleSheet(self.clear_btn.styleSheet().replace('font-size: 12px', 'font-size: 10px').replace('padding: 7px 14px', 'padding: 4px 8px'))
        self.clear_btn.setToolTip("Clear console (Ctrl+L)")
        console_row.addWidget(self.clear_btn)
        self.copy_btn = self._tool_button("Copy", self._copy_console)
        self.copy_btn.setFixedWidth(52)
        self.copy_btn.setStyleSheet(self.copy_btn.styleSheet().replace('font-size: 12px', 'font-size: 10px').replace('padding: 7px 14px', 'padding: 4px 8px'))
        self.copy_btn.setToolTip("Copy console to clipboard (Ctrl+Shift+C)")
        console_row.addWidget(self.copy_btn)
        self.save_btn = self._tool_button("Save", self._save_console)
        self.save_btn.setFixedWidth(52)
        self.save_btn.setStyleSheet(self.save_btn.styleSheet().replace('font-size: 12px', 'font-size: 10px').replace('padding: 7px 14px', 'padding: 4px 8px'))
        self.save_btn.setToolTip("Save console to a text file (Ctrl+S)")
        console_row.addWidget(self.save_btn)
        self.time_btn = self._console_chip(
            "Time", "Show/hide the [HH:MM:SS] timestamp prefix",
            self._show_timestamps, width=46)
        # Drive from the button's own state (toggled) so a programmatic
        # setChecked() can never desync the chip from the render mode.
        self.time_btn.toggled.connect(self._set_timestamps)
        console_row.addWidget(self.time_btn)
        console_row.addStretch(1)
        body_lay.addLayout(console_row)

        # Console | CMD tabs: the transcript lives on Console; the CMD tab
        # is created only when called (Transports ▸ CMD Console) and has
        # its own ×. Nothing below the transcript otherwise.
        from PyQt6.QtWidgets import QTabWidget as _Tabs, QTabBar as _TabBar
        self.console_tabs = _Tabs()
        self.console_tabs.setTabsClosable(True)
        self.console_tabs.tabCloseRequested.connect(self._cmd_tab_closed)
        _cons_page = QWidget()
        _cons_page.setStyleSheet("background: transparent;")
        cons_lay = QVBoxLayout(_cons_page)
        cons_lay.setContentsMargins(0, 0, 0, 0)
        cons_lay.setSpacing(8)
        self.console_tabs.addTab(_cons_page, "Console")
        try:
            self.console_tabs.tabBar().setTabButton(
                0, _TabBar.ButtonPosition.RightSide, None)
        except Exception:
            pass
        self.console_tabs.setStyleSheet(
            f"QTabWidget::pane {{ border:none; background:transparent; }}"
            f" QTabWidget::tab-bar {{ alignment:left; }}"
            f" QTabBar::tab {{ background:{C['card']}; color:{C['dim']};"
            f" border:1px solid {C['border']}; border-bottom:none;"
            f" border-top-left-radius:8px; border-top-right-radius:8px;"
            f" padding:4px 14px; font-size:11px; font-weight:700; }}"
            f" QTabBar::tab:selected {{ background:{C['inset']}; color:{C['text']};"
            f" border-top:2px solid {C['accent']}; }}"
        )
        body_lay.addWidget(self.console_tabs, 1)
        self._cmd_tab = None
        self._cmd_busy = False

        # find + filter rows (two compact rows to fit the narrow console column)
        find_row = QHBoxLayout()
        find_row.setSpacing(6)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Search console...  (Ctrl+F)")
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.setMinimumWidth(80)  # yield space instead of clipping chips
        self.find_edit.textChanged.connect(self._apply_console_search)
        self.find_edit.setStyleSheet(
            f"QLineEdit {{ background:{C['card']}; border:1px solid {C['border']};"
            f" border-radius:6px; padding:5px 10px; color:{C['text']};"
            f" selection-background-color:{C['accent']}; }}"
            f" QLineEdit:hover {{ border:1px solid {C['border_hi']}; }}"
            f" QLineEdit:focus {{ border:1px solid {C['accent']}; }}"
        )
        # Aliases for the console search box (tests / callers may use any).
        self.console_search = self.find_edit
        self.search_box = self.find_edit
        self.log_search = self.find_edit
        self.search_input = self.find_edit
        self.console_filter = self.find_edit
        # Base stylesheet kept so the invalid-regex marker can be removed again.
        self._find_edit_base_qss = self.find_edit.styleSheet()
        find_row.addWidget(self.find_edit, 1)
        self.regex_btn = self._console_chip(
            ".*", "Treat the search text as a regular expression",
            self._console_regex, width=30)
        self.regex_btn.toggled.connect(self._set_regex_mode)
        find_row.addWidget(self.regex_btn)
        self.find_next_btn = self._tool_button("Next", lambda: self._find_nav(1))
        self.find_next_btn.setToolTip("Find next match")
        self.find_prev_btn = self._tool_button("Prev", lambda: self._find_nav(-1))
        self.find_prev_btn.setToolTip("Find previous match")
        find_row.addWidget(self.find_next_btn)
        find_row.addWidget(self.find_prev_btn)
        self.search_clear_btn = self._tool_button("✕", lambda: self.find_edit.clear())
        self.search_clear_btn.setToolTip("Clear console search filter")
        self.search_clear_btn.setStyleSheet(
            self.search_clear_btn.styleSheet()
            .replace('font-size: 12px', 'font-size: 10px')
            .replace('padding: 7px 14px', 'padding: 4px 8px'))
        self.search_clear_btn.setFixedWidth(34)
        self.search_clear_btn.setStyleSheet(
            self.search_clear_btn.styleSheet()
            .replace("font-size: 12px", "font-size: 10px")
            .replace("padding: 6px 12px", "padding: 4px 6px")
        )
        find_row.addWidget(self.search_clear_btn)
        self.clear_search_btn = self.search_clear_btn
        self.console_search_clear = self.search_clear_btn

        flt_row = QHBoxLayout()
        flt_row.setSpacing(6)

        self._filter_btns = {}
        for level, label, color, width, tip in (
            ("err", "Errors", C["err"], 58, "Show error lines"),
            ("warn", "Warnings", C["warn"], 70, "Show warning lines"),
            ("ok", "OK", C["ok"], 44, "Show success lines"),
            ("info", "Info", C["dim"], 46, "Show info lines"),
        ):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(width)
            btn.setToolTip(tip)
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

        self.clear_on_run = QCheckBox("auto-clear")
        self.clear_on_run.setChecked(
            self.settings.value("clear_on_run", "true", type=bool)
        )
        self.clear_on_run.setStyleSheet(
            f"QCheckBox {{ color:{C['mute']}; font-size:10px; font-weight:600; }}"
            f" QCheckBox::indicator {{ width:14px; height:14px; }}"
        )
        flt_row.addWidget(self.clear_on_run)
        flt_row.addStretch(1)
        cons_lay.addLayout(find_row)
        cons_lay.addLayout(flt_row)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(4000)
        self.log.setMinimumHeight(120)
        self.log.setPlainText("Ready. Connect a device to begin.")
        self.log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        try:
            LogHighlighter(self.log.document())
        except Exception:
            pass
        cons_lay.addWidget(self.log, 1)

        # Right-click menu on the transcript (S2b): copy/save/clear/find plus
        # checkable Wrap / Timestamps / Regex toggles kept in sync with the
        # toolbar chips (the menu is rebuilt on every popup).
        self.log.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log.customContextMenuRequested.connect(self._console_context_menu)

        # Batched flush (S2b): the first pending line renders synchronously so
        # logging stays latency-free; further lines within the window coalesce
        # into a single append from a single-shot timer (or at the line cap).
        self._console_flush_timer = QTimer(self)
        self._console_flush_timer.setSingleShot(True)
        self._console_flush_timer.setInterval(self._CONSOLE_FLUSH_MS)
        self._console_flush_timer.timeout.connect(self._flush_console)
        # Compile the persisted search mode once the widgets exist.
        self._refresh_search_regex()

        lay.addWidget(self._console_body, 1)
        # Trailing spacer. With the body hidden (collapsed) the column would have
        # only the header left, and Qt hands it the leftover height — centring the
        # chevron in the tall bar, so it visibly jumped up and down on every
        # collapse/expand. This takes that height instead: stretch 0 while
        # expanded (the transcript keeps every pixel), 1 while collapsed.
        lay.addStretch(0)
        self._console_bottom_stretch = lay.count() - 1
        return panel

    # ---- console dock: splitter / collapse / maximise (S2a) --------------
    def _style_console_splitter(self):
        """Splitter handle styling from theme tokens (no hardcoded colours)."""
        self._splitter.setStyleSheet(_splitter_qss())

    def _desired_device_panel_width(self, total):
        """Device panel width for `total` px: persisted width if sane, else 232.

        Always clamped into [min, max] *and* leaves the page its viewport floor,
        so the page can never be squeezed out by a saved or dragged value.
        """
        try:
            w = int(getattr(self, "_device_panel_width", None) or 0)
        except (TypeError, ValueError):
            w = 0
        if w <= 0:
            w = self._BODY_PANEL_DEFAULT_W
        room = max(self._BODY_PANEL_MIN_W,
                   total - self._PAGE_VIEW_MIN_W - 6)
        return max(self._BODY_PANEL_MIN_W,
                   min(w, self._BODY_PANEL_MAX_W, room))

    def _apply_default_body_split(self):
        """Keep the device panel at its desired width across window resizes.

        Re-applied on every resize *until the user drags the handle*: the first
        layout pass can run before the window reaches its real geometry, so a
        one-shot apply would pin the panel to a transient (too narrow) width.
        Stretch factors (0, 1) then hold the panel steady and hand the page
        every later resize.

        On a window at its minimum width the console dock's default width
        leaves the body narrower than the two hard child floors combined
        (``_BODY_PANEL_MIN_W`` + ``_PAGE_VIEW_MIN_W`` + handle). ``QSplitter``
        then **ignores** ``setSizes`` completely and the split silently stays at
        its stale 50/50 — so the panel never reaches the width the formula above
        already computed for it. The page floor is released just long enough for
        the split to take, then re-pinned to the width the page actually got, so
        a later drag can never squeeze it past what it already has. When there
        *is* room this is a no-op: the page floor stays ``_PAGE_VIEW_MIN_W``.
        """
        splitter = getattr(self, "_body_splitter", None)
        if splitter is None or splitter.width() <= 0:
            return
        if getattr(self, "_body_user_moved", False):
            return
        panel = self._desired_device_panel_width(splitter.width())
        page = max(1, splitter.width() - panel)
        if page >= self._PAGE_VIEW_MIN_W:
            self._page_scroll.setMinimumWidth(self._PAGE_VIEW_MIN_W)
            splitter.setSizes([panel, page])
            return
        self._page_scroll.setMinimumWidth(1)
        splitter.setSizes([panel, page])
        self._page_scroll.setMinimumWidth(max(1, splitter.sizes()[1]))


    def _on_body_splitter_moved(self, *_args):
        """Remember the user's device-panel width (persisted via QSettings)."""
        try:
            if not getattr(self, "_body_user_moved", False):
                self._body_user_moved = True
            sizes = self._body_splitter.sizes()
            if len(sizes) >= 2 and sizes[0] > 0:
                self._device_panel_width = int(sizes[0])
                self.settings.setValue(
                    "layout/device_panel_width", int(sizes[0]))
        except Exception:
            pass

    def _desired_dock_console_width(self, total):
        """Console width for `total` px: persisted width if sane, else default."""
        if getattr(self, "_console_maximised", False):
            return total
        try:
            w = int(getattr(self, "_console_dock_width", None) or 0)
        except (TypeError, ValueError):
            w = 0
        room = max(self._DOCK_MIN_CONSOLE, total - self._DOCK_MIN_TOP)
        if w > 0:
            return max(self._DOCK_MIN_CONSOLE, min(w, room))
        return max(self._DOCK_MIN_CONSOLE,
                   min(self._DOCK_DEFAULT_WIDTH, room))

    def _apply_default_dock_split(self):
        """Keep the console at its desired width across window resizes.

        `setSizes()` before the first layout pass sees width 0 and is ignored,
        so this runs from showEvent/resizeEvent. It keeps re-applying on every
        resize *until the user drags the handle* — otherwise the very first
        (possibly narrow, pre-geometry-restore) layout pass would pin the dock
        to a transient width for the rest of the session. Skipped while
        maximised; a collapsed dock only needs its thin bar re-applied.
        """
        if not hasattr(self, "_splitter"):
            return
        if getattr(self, "_console_maximised", False):
            return
        if getattr(self, "_dock_user_moved", False):
            return
        total = self._splitter.width()
        if total <= 0:
            return
        if getattr(self, "_console_collapsed", False):
            self._set_console_collapsed(True, persist=False)
        else:
            console = self._desired_dock_console_width(total)
            self._splitter.setSizes(
                [max(self._DOCK_MIN_TOP, total - console), console])

    def _on_dock_splitter_moved(self, *_args):
        """Remember the user's dock width (persisted via QSettings)."""
        if getattr(self, "_console_maximised", False):
            return
        try:
            # Only a real drag (not a programmatic setSizes) may pin the dock.
            if not getattr(self, "_dock_user_moved", False):
                self._dock_user_moved = True
            sizes = self._splitter.sizes()
            if len(sizes) >= 2 and sizes[1] > 0:
                self._console_dock_width = int(sizes[1])
                self.settings.setValue("console/dock_width", int(sizes[1]))
        except Exception:
            pass

    def _apply_console_state_from_settings(self):
        """Apply the persisted collapsed/maximised state at construction."""
        if self._console_collapsed:
            self._set_console_collapsed(True, persist=False)
        if self._console_maximised:
            self._set_console_maximised(True, persist=False)

    def _set_console_collapsed(self, collapsed, persist=True):
        """Collapse the dock to a thin bar (or expand it again)."""
        collapsed = bool(collapsed)
        self._console_collapsed = collapsed
        try:
            self._console_body.setVisible(not collapsed)
            # In the collapsed vertical bar only the chevron fits.
            self._console_title.setVisible(not collapsed)
            self.console_count.setVisible(not collapsed)
            self.console_toggle_btn.setText("▸" if collapsed else "▾")
            self.console_toggle_btn.setToolTip(
                "Expand the console dock" if collapsed
                else "Collapse the console dock")
            # Centre the chevron in the thin bar: with the title/count hidden a
            # leading stretch balances the trailing one, and tighter side
            # margins leave room for the 24px button inside the 44px bar.
            self._console_header.setStretch(0, 1 if collapsed else 0)
            # ...and let the trailing spacer own the bar's free height, so the
            # chevron stays anchored at the top instead of being centred in it.
            self._console_layout.setStretch(
                self._console_bottom_stretch, 1 if collapsed else 0)
            self._console_layout.setContentsMargins(
                *((SPACE['xs'], SPACE['sm'], SPACE['xs'], SPACE['sm'])
                  if collapsed else self._console_margins))
            if collapsed:
                # Let the splitter shrink the panel to its header bar. An
                # explicit min=max overrides the layout's minimum hint, so the
                # bar really does collapse to the chevron width.
                self._console_dock.setMinimumWidth(self._DOCK_COLLAPSED_W)
                self._console_dock.setMaximumWidth(self._DOCK_COLLAPSED_W)
                total = self._splitter.width()
                if total > 0:
                    self._splitter.setSizes(
                        [max(self._DOCK_MIN_TOP, total - self._DOCK_COLLAPSED_W),
                         self._DOCK_COLLAPSED_W])
            else:
                self._console_dock.setMinimumWidth(self._DOCK_MIN_CONSOLE)
                self._console_dock.setMaximumWidth(16777215)
                total = self._splitter.width()
                if total > 0:
                    console = self._desired_dock_console_width(total)
                    self._splitter.setSizes(
                        [max(self._DOCK_MIN_TOP, total - console), console])
        except Exception:
            pass
        if persist:
            self._save_console_state()

    def _toggle_console_collapse(self):
        self._set_console_collapsed(
            not getattr(self, "_console_collapsed", False))

    def _set_console_maximised(self, maximised, persist=True):
        """F11 mode: hide the page area so the console fills the window."""
        maximised = bool(maximised)
        if maximised == getattr(self, "_console_maximised", False):
            if persist:
                self._save_console_state()
            return
        self._console_maximised = maximised
        try:
            if maximised:
                self._pre_max_sizes = self._splitter.sizes()
                self._pre_max_collapsed = bool(
                    getattr(self, "_console_collapsed", False))
                # A collapsed dock would defeat full-screen mode.
                if self._console_collapsed:
                    self._set_console_collapsed(False, persist=False)
                self._top_area.setVisible(False)
                total = self._splitter.width()
                if total > 0:
                    self._splitter.setSizes([0, total])
            else:
                self._top_area.setVisible(True)
                total = self._splitter.width()
                pre = getattr(self, "_pre_max_sizes", None)
                if pre and len(pre) >= 2 and sum(pre) > 0 and total > 0:
                    self._splitter.setSizes(pre)
                elif total > 0:
                    console = self._desired_dock_console_width(total)
                    self._splitter.setSizes(
                        [max(self._DOCK_MIN_TOP, total - console), console])
                if getattr(self, "_pre_max_collapsed", False):
                    self._set_console_collapsed(True, persist=False)
        except Exception:
            pass
        if persist:
            self._save_console_state()

    def _toggle_console_maximised(self):
        self._set_console_maximised(
            not getattr(self, "_console_maximised", False))

    def _save_console_state(self):
        """Persist dock width / collapsed / maximised via QSettings."""
        try:
            self.settings.setValue(
                "console/collapsed", bool(getattr(self, "_console_collapsed", False)))
            self.settings.setValue(
                "console/maximised", bool(getattr(self, "_console_maximised", False)))
            if hasattr(self, "_splitter") and not getattr(
                    self, "_console_maximised", False):
                sizes = self._splitter.sizes()
                # Only a width the *user* actually chose is persisted: the live
                # splitter width may be a transient layout artefact, and a
                # sub-minimum width must never be recorded (it would reopen the
                # dock as a sliver).
                if (getattr(self, "_dock_user_moved", False)
                        and len(sizes) >= 2
                        and sizes[1] >= self._DOCK_MIN_CONSOLE):
                    self._console_dock_width = int(sizes[1])
                    self.settings.setValue("console/dock_width", int(sizes[1]))
        except Exception:
            pass

    def _cmd_tab_closed(self, index):
        """X on a CMD tab: remove it. The Console tab (index 0) stays."""
        try:
            if index <= 0:
                return
            widget = self.console_tabs.widget(index)
            self.console_tabs.removeTab(index)
            if widget is not None and widget == getattr(self, "_cmd_tab", None):
                self._cmd_tab = None
                self._cmd_busy = False
            if widget is not None:
                widget.deleteLater()
        except Exception:
            pass

    def _open_cmd_tab(self, mode=None):
        """Show the CMD tab (built on demand). Console <-> CMD via the tabs."""
        try:
            if getattr(self, "_cmd_tab", None) is not None:
                if mode:
                    try:
                        self._cmd_mode.setCurrentText(mode)
                    except Exception:
                        pass
                self.console_tabs.setCurrentWidget(self._cmd_tab)
                self._cmd_refresh_prompt()
                return
            page = QWidget()
            page.setStyleSheet("background: transparent;")
            outer = QVBoxLayout(page)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(0)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
            inner = QWidget()
            inner.setStyleSheet("background: transparent;")
            lay = QVBoxLayout(inner)
            lay.setContentsMargins(4, 6, 4, 6)
            lay.setSpacing(8)

            mode_row = QHBoxLayout()
            mode_row.setSpacing(6)
            self._cmd_mode = QComboBox()
            self._cmd_mode.addItems(["ADB", "Fastboot"])
            self._cmd_mode.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._cmd_mode.setFixedWidth(110)
            self._cmd_mode.setToolTip("Which transport the custom command uses")
            self._cmd_mode.setStyleSheet(
                f"QComboBox {{ background:{C['card']}; border:1px solid {C['border']};"
                f" border-radius:6px; padding:4px 8px; color:{C['text']}; font-size:11px; font-weight:700; }}"
                f" QComboBox:hover {{ border:1px solid {C['border_hi']}; }}"
                f" QComboBox:focus {{ outline:none; }}"
                f" QComboBox QAbstractItemView {{ background:{C['card']}; color:{C['text']};"
                f" selection-background-color:{C['accent']}; }}"
            )
            mode_row.addWidget(self._cmd_mode)
            self._cmd_code = QLineEdit()
            self._cmd_code.setPlaceholderText("Unlock code (BL unlock only)")
            self._cmd_code.setStyleSheet(
                f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']};"
                f" border-radius:6px; padding:5px 10px; color:{C['text']};"
                f" font-family:'JetBrains Mono','Consolas',monospace; font-size:11px;"
                f" selection-background-color:{C['accent']}; }}"
                f" QLineEdit:focus {{ border:1px solid {C['accent']}; }}"
            )
            mode_row.addWidget(self._cmd_code, 1)
            lay.addLayout(mode_row)

            adb_row = QHBoxLayout()
            adb_row.setSpacing(6)
            adb_lbl = QLabel("ADB")
            adb_lbl.setStyleSheet("color:#34d399; font-size:10px; font-weight:800;")
            adb_lbl.setFixedWidth(52)
            adb_row.addWidget(adb_lbl)
            for label, shell_cmd in (
                ("Reboot", "reboot"),
                ("Recovery", "reboot recovery"),
                ("Bootloader", "reboot bootloader"),
                ("EDL", "reboot edl"),
            ):
                b = QPushButton(label)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                b.setToolTip(f"adb shell {shell_cmd}")
                b.setStyleSheet(
                    f"QPushButton {{ color:{C['text']}; background:{C['card']};"
                    f" border:1px solid {C['border']}; border-radius:6px;"
                    f" padding:4px 8px; font-size:10px; font-weight:700; }}"
                    f" QPushButton:hover {{ border-color:{C['accent']}; }}"
                    f" QPushButton:focus {{ outline:none; }}"
                )
                b.clicked.connect(lambda _=False, c=shell_cmd: self._cmd_adb_preset(c))
                adb_row.addWidget(b)
            adb_row.addStretch(1)
            lay.addLayout(adb_row)

            fb_row = QHBoxLayout()
            fb_row.setSpacing(6)
            fb_lbl = QLabel("Fastboot")
            fb_lbl.setStyleSheet("color:#fbbf24; font-size:10px; font-weight:800;")
            fb_lbl.setFixedWidth(52)
            fb_row.addWidget(fb_lbl)
            fb_scroll = QScrollArea()
            fb_scroll.setWidgetResizable(True)
            fb_scroll.setFrameShape(QFrame.Shape.NoFrame)
            fb_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            fb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            fb_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
            fb_inner = QWidget()
            fb_inner.setStyleSheet("background: transparent;")
            fb_btns = QHBoxLayout(fb_inner)
            fb_btns.setContentsMargins(0, 0, 0, 0)
            fb_btns.setSpacing(6)
            for label, fb_cmd, tip in (
                ("Unlock BL", None, "oem unlock <code> (two-step, uses the code above)"),
                ("Relock BL", "relock", "flashing lock (re-lock the bootloader)"),
                ("Reboot", "reboot", "reboot to system"),
                ("Bootloader", "reboot bootloader", "reboot to bootloader/fastboot"),
                ("Recovery", "reboot recovery", "reboot to recovery"),
                ("EDL", "oem edl", "reboot to EDL (falls back to reboot edl)"),
                ("Getvar", "getvar all", "dump all bootloader variables"),
                ("Continue", "continue", "continue boot to system"),
            ):
                b = QPushButton(label)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                b.setToolTip(tip)
                b.setStyleSheet(
                    f"QPushButton {{ color:{C['text']}; background:{C['card']};"
                    f" border:1px solid {C['border']}; border-radius:6px;"
                    f" padding:4px 8px; font-size:10px; font-weight:700; }}"
                    f" QPushButton:hover {{ border-color:{C['accent']}; }}"
                    f" QPushButton:focus {{ outline:none; }}"
                )
                if fb_cmd is None:
                    b.clicked.connect(lambda _=False: self._cmd_fastboot_unlock())
                elif fb_cmd == "relock":
                    b.clicked.connect(lambda _=False: self._cmd_fastboot_relock())
                elif fb_cmd == "oem edl":
                    b.clicked.connect(lambda _=False: self._cmd_fb_preset("oem edl", "reboot edl"))
                else:
                    b.clicked.connect(lambda _=False, c=fb_cmd: self._cmd_fb_preset(c))
                b.setFixedHeight(30)
                fb_btns.addWidget(b)
            fb_scroll.setWidget(fb_inner)
            fb_scroll.setFixedHeight(36)
            fb_row.addWidget(fb_scroll, 1)
            lay.addLayout(fb_row)

            custom_row = QHBoxLayout()
            custom_row.setSpacing(6)
            self._cmd_prompt = QLabel("no-device$")
            self._cmd_prompt.setStyleSheet(
                "color:#34d399; font-size:12px; font-weight:700;"
                " font-family:'JetBrains Mono','Consolas',monospace;"
                " background:transparent; border:none;"
            )
            custom_row.addWidget(self._cmd_prompt)
            self._cmd_input = QLineEdit()
            self._cmd_input.setPlaceholderText("type a command — Enter runs")
            self._cmd_input.setStyleSheet(
                f"QLineEdit {{ background:transparent; border:none;"
                f" padding:5px 2px; color:{C['text']};"
                f" font-family:'JetBrains Mono','Consolas',monospace; font-size:12px;"
                f" selection-background-color:{C['accent']}; }}"
                " QLineEdit:focus { background:transparent; border:none; }"
            )
            self._cmd_input.returnPressed.connect(self._cmd_custom_run)
            custom_row.addWidget(self._cmd_input, 1)
            lay.addLayout(custom_row)

            hint = QLabel("Output goes to the Console tab — switch tabs to read it.")
            hint.setStyleSheet(f"color:{C['mute']}; font-size:10px;")
            hint.setWordWrap(True)
            lay.addWidget(hint)
            lay.addStretch(1)
            scroll.setWidget(inner)
            outer.addWidget(scroll, 1)

            self._cmd_tab = page
            self.console_tabs.addTab(page, "CMD")
            try:
                self.console_tabs.tabBar().setTabTextColor(
                    self.console_tabs.count() - 1, QColor("#fbbf24"))
            except Exception:
                pass
            self.console_tabs.setCurrentWidget(page)
            if mode:
                try:
                    self._cmd_mode.setCurrentText(mode)
                except Exception:
                    pass
            self._cmd_refresh_prompt()
        except Exception as e:  # noqa: BLE001
            try:
                self.log_line(f"[error] CMD tab failed: {e}")
            except Exception:
                pass

    def _cmd_refresh_prompt(self):
        """Device-aware prompt (serial@transport$) — never hardcoded."""
        prompt = "no-device$"
        try:
            rows = device_pages.connected_rows()
            if rows:
                r = rows[0]
                serial = (r.get("serial") or r.get("usb_key")
                          or r.get("label") or "device")
                serial = str(serial).split(" · ")[0].strip() or "device"
                transports = r.get("transports") or ["?"]
                prompt = f"{serial}@{str(transports[0]).lower()}$"
        except Exception:
            pass
        try:
            if getattr(self, "_cmd_prompt", None) is not None:
                self._cmd_prompt.setText(prompt)
        except Exception:
            pass

    def _cmd_adb_preset(self, shell_cmd):
        """One ADB reboot preset: gate on ADB first, then run in a worker."""
        if not self._gate_transport("adb_frp"):
            return
        self._cmd_launch(f"[ADB] {shell_cmd}", self._cmd_adb_work, (shell_cmd,))

    def _cmd_fb_preset(self, fb_cmd, fallback=None):
        """One fastboot preset: gate on FASTBOOT first, then run in a worker."""
        if not self._gate_transport("fastboot_unlock"):
            return
        self._cmd_launch(f"[fastboot] {fb_cmd}", self._cmd_fastboot_work, (fb_cmd, fallback))

    def _cmd_custom_run(self):
        """Custom command from the CMD tab input, in the picked mode."""
        self._cmd_refresh_prompt()
        try:
            if getattr(self, "_cmd_tab", None) is None:
                return
            mode = self._cmd_mode.currentText()
            text = self._cmd_input.text().strip()
        except Exception:
            return
        if not text:
            return
        if mode == "Fastboot":
            self._cmd_fb_preset(text)
        else:
            self._cmd_adb_preset(text)

    def _cmd_fastboot_unlock(self):
        """BL unlock via the Rust flow (two-step confirm + verify)."""
        try:
            code = self._cmd_code.text().strip()
        except Exception:
            code = ""
        if not code:
            self._ui.line.emit("[warn] enter the bootloader unlock code first")
            try:
                self._toasts.show_warn("Unlock code missing",
                                       "Enter the code, then press Unlock BL.")
            except Exception:
                pass
            return
        if not self._gate_transport("fastboot_unlock"):
            return
        target = self._cmd_fastboot_target()
        if not target:
            self._ui.line.emit("[warn] no fastboot phone connected")
            return
        self._cmd_launch(f"[fastboot] oem unlock {code}",
                         self._cmd_flow_work,
                         (["flow-run", "fastboot_unlock", target, "--code", code], 180))

    def _cmd_fastboot_relock(self):
        """Relock the bootloader via the Rust flow (flashing lock)."""
        if not self._gate_transport("fastboot_unlock"):
            return
        target = self._cmd_fastboot_target()
        if not target:
            self._ui.line.emit("[warn] no fastboot phone connected")
            return
        self._cmd_launch("[fastboot] flashing lock",
                         self._cmd_flow_work,
                         (["flow-run", "fastboot_lock", target], 120))

    def _cmd_launch(self, display, fn, args=()):
        """Start one CMD run in a worker (serialized: no overlaps)."""
        if getattr(self, "_cmd_busy", False):
            self._ui.line.emit("[warn] a command is already running — wait for it to finish")
            return
        self._cmd_busy = True
        self._ui.line.emit(f">>> {display}")
        threading.Thread(target=self._cmd_wrap, args=(fn, args), daemon=True).start()

    def _cmd_wrap(self, fn, args):
        try:
            fn(*args)
        except Exception as e:  # noqa: BLE001
            self._ui.line.emit(f"[error] CMD failed: {e}")
        finally:
            self._cmd_busy = False

    def _cmd_adb_work(self, shell_cmd):
        out = bridge.adb_shell(shell_cmd, timeout=30)
        self._cmd_print_out(out)

    def _cmd_flow_work(self, argv, timeout):
        out = bridge._run(argv, timeout=timeout)
        self._cmd_print_out(out)

    def _cmd_fastboot_target(self):
        try:
            for row in device_pages.connected_rows():
                if "FASTBOOT" in (row.get("transports") or []):
                    key = row.get("key") or row.get("usb_key")
                    try:
                        target = _devices.resolve_usb_target(key)
                    except Exception:
                        target = None
                    if target:
                        return target
        except Exception:
            pass
        return None

    def _cmd_fastboot_work(self, fb_cmd, fallback=None):
        target = self._cmd_fastboot_target()
        if not target:
            self._ui.line.emit("[warn] no fastboot phone connected")
            return
        out = bridge.fastboot_cmd(target, fb_cmd.split(), timeout_ms=20000)
        if "FAILED" in str(out) and fallback:
            self._ui.line.emit(f"[warn] '{fb_cmd}' rejected — trying '{fallback}'")
            out = bridge.fastboot_cmd(target, fallback.split(), timeout_ms=20000)
        self._cmd_print_out(out)

    def _cmd_print_out(self, out):
        for line in str(out).splitlines():
            self._ui.line.emit(line if line.strip() else " ")
        # Device-side failures come back as transcripts (no exception):
        # never print a success marker over a rejected command.
        if "FAILED" in str(out):
            self._ui.line.emit("[error] device reported FAILED (see transcript above)")
        else:
            self._ui.line.emit("[ok] done")

    # ----------------------------- section switching ----------------------
    def update_device_strip(self, force=False):
        """Phase-1 device-first: refresh the connected-phone strip and dim
        drill-down buttons the phone can't use. Never raises (a failed
        detect simply shows 'no phone', everything stays enabled).

        The USB scan runs in a worker thread (a slow bus must never freeze
        the GUI); the widget update is posted back via the UI signal."""
        if force:
            try:
                device_pages.invalidate_connected_cache()
            except Exception:
                pass
        threading.Thread(target=self._device_strip_work, daemon=True).start()

    def _device_strip_work(self):
        try:
            rows = device_pages.connected_rows()
        except Exception:
            rows = []
        try:
            self._ui.ui.emit(lambda: self._apply_device_strip(rows))
        except Exception:
            pass

    def _apply_device_strip(self, rows):
        try:
            if not rows:
                self._dev_dot.setText("○")
                self._dev_dot.setStyleSheet(f"color:{C['dim']}; font-size:15px; font-weight:800;")
                self._dev_title.setText("No phone detected")
                self._dev_text.setText("Connect a device over USB")
            elif len(rows) == 1:
                r = rows[0]
                transports = "/".join(r.get("transports") or ["?"])
                mode = r.get("mode") or "phone"
                self._dev_dot.setText("●")
                self._dev_dot.setStyleSheet("color:#34d399; font-size:15px; font-weight:800;")
                self._dev_title.setText(f"{r.get('label', mode)[:60]}")
                self._dev_text.setText(f"{mode} · [{transports}] — only matching actions are lit")
                try:
                    ports = device_pages.usb_serial_ports(
                        int(r.get("bus", 0) or 0), int(r.get("address", 0) or 0))
                except Exception:
                    ports = []
                if ports:
                    self._dev_strip.setToolTip(f"Serial ports: {', '.join(ports)}")
                else:
                    self._dev_strip.setToolTip("")
            else:
                r = rows[0]
                transports = "/".join(r.get("transports") or ["?"])
                self._dev_dot.setText("●")
                self._dev_dot.setStyleSheet("color:#fbbf24; font-size:15px; font-weight:800;")
                self._dev_title.setText(f"{len(rows)} phones connected")
                self._dev_text.setText(f"showing {r.get('label', '')[:40]} · [{transports}]")
            device_pages.apply_applicability(self._stack.currentWidget())
        except Exception:
            pass

    def _apply_tool_relevance(self):
        """Tool-chip pattern: grey the MTK/Qualcomm/SPD/FUS tool chips that the
        current brand's models cannot use. Samsung tools (FUS) light for
        Samsung; chip tools light when ANY of the brand's model engines
        matches or the connected phone exposes that transport. Never
        removes a chip — greyed chips show a why tooltip."""
        try:
            section = getattr(self, "_current_section", "samsung")
            brand_key = section.removeprefix("dev_")
            if brand_key not in ("samsung", "mtk", "qc", "spd", "fus",
                                 "general", "settings", "adb", "fastboot"):
                engines = set()
                for b in device_pages.BRAND_BY_KEY.get(brand_key, {}).get("models", []):
                    e = (b.get("engine") or "").lower()
                    engines.add({"motorola": "qcom"}.get(e, e))
                    if e == "motorola":
                        engines.update({"qcom", "mtk", "spd"})
            else:
                engines = None  # tool/chip section: all tools available
            live = device_pages.connected_transports()
            live_eng = set()
            if "MTK" in live or "MTK BROM" in live:
                live_eng.add("mtk")
            if "SPD" in live:
                live_eng.add("spd")
            if "EDL" in live:
                live_eng.add("qcom")
            relevance = {
                "fus": ("samsung", {"odin"}),
                "mtk": ("mtk", {"mtk"}),
                "qc": ("qc", {"qcom"}),
                "spd": ("spd", {"spd"}),
            }
            for key, (tool_section, tool_engines) in relevance.items():
                ok = (engines is None
                      or bool(engines & tool_engines)
                      or bool(live_eng & tool_engines))
                why = ("" if ok else
                       f"{brand_key.title() if brand_key else 'This brand'} models "
                       f"don't use this tool (connect a matching phone to enable)")
                self.oem_bar.set_tool_enabled(key, ok, tip=why or None)
        except Exception:
            pass

    def _route_model_flash(self, label, engine, meta):
        """Per-model flash routing: the model's engine decides the
        destination. Unknown engines ask the user to pick the chip instead
        of guessing; the workbench tabs remain for advanced use."""
        engine = (engine or (meta.get("engine") or "")).lower()
        if engine in ("motorola", "qcom"):
            # Fastboot-based flashing with signed stock firmware. Route to
            # the staged-flash flow when the firmware dir is set, else give
            # the exact guidance.
            import os as _os
            fw = device_pages._moto_fw_dir() if engine == "motorola" else ""
            if engine == "motorola" and fw:
                self._run_ops_flow("Remove FRP", "FASTBOOT", "moto_fb_frp",
                                   f"{label} · staged flash ({_os.path.basename(fw)})")
                return
            self._toasts.show_info(
                f"{label} · Flash",
                ("Signed firmware found — press FRP REMOVE → staged flash. "
                 if fw else
                 "Fastboot-based flashing: set MOTO_FW_DIR to the signed "
                 "stock firmware (flashfile.xml) dir, then re-run — or use ")
                + "FASTBOOT ▸ flash/erase with your firmware files.")
            return
        if engine in ("mtk", "spd", "odin"):
            self._on_section(engine if engine != "odin" else "samsung")
            dest = {"mtk": "MTK tab (DA + scatter + firmware dir)",
                    "spd": "SPD tab (FDL1/FDL2 + firmware dir)",
                    "odin": "Samsung ▸ FLASH slots (AP/BL/CP/CSC)"}[engine]
            self._toasts.show_info(
                f"{label} · Flash",
                f"Opened the workbench for this model's chipset — {dest}.")
            return
        if engine in ("apple", "kirin"):
            self._toasts.show_info(
                f"{label} · Flash",
                "No PC-side flash path for this chipset in FlashPilot "
                "(Apple DFU / Kirin are not supported flash engines).")
            return
        # Unknown engine: ask, never guess.
        from PyQt6.QtWidgets import QInputDialog, QComboBox, QDialog, QDialogButtonBox, QVBoxLayout, QLabel as _QL
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{label} · Chipset")
        v = QVBoxLayout(dlg)
        v.addWidget(_QL("Which chipset does this device use? "
                        "(flash routing differs per chip)"))
        combo = QComboBox()
        combo.addItems(["MediaTek (MTK)", "UNISOC (SPD)",
                        "Qualcomm (EDL/fastboot)", "Samsung (Odin)"])
        v.addWidget(combo)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        pick = {0: "mtk", 1: "spd", 2: "qcom", 3: "odin"}[combo.currentIndex()]
        self.log_line(f"[device] {label}: chip asked by user -> {pick}")
        self._route_model_flash(label, pick, meta)

    def _on_transport_pick(self, index):
        """Transports dropdown: ADB hub / Fastboot hub / Easy Login / CMD."""
        try:
            self._transport_combo.setCurrentIndex(0)
        except Exception:
            pass
        if index == 1:
            self._on_section("adb")
        elif index == 2:
            self._on_section("fastboot")
        elif index == 3:
            self._on_section("easylogin")
        elif index == 4:
            self._open_cmd_tab()

    def _on_section(self, key):
        self._current_section = key
        idx = getattr(self, "_section_index", {}).get(key, 0)
        self._stack.setCurrentIndex(idx)
        if hasattr(self, "oem_bar"):
            self.oem_bar.select(key)
        self.set_status(f"Section: {key.upper()}")
        # Phase-1 device-first: the newly shown page gets the dimming pass,
        # and the tool chips re-grey for the brand now on screen.
        try:
            self._apply_tool_relevance()
        except Exception:
            pass
        try:
            self.update_device_strip()
        except Exception:
            pass
        # Fix shrink: stacked pages hide FlowLayout's width; force relayout on show.
        try:
            w = self._stack.currentWidget()
            if w:
                for child in w.findChildren(QFrame):
                    lay = child.layout()
                    if lay and hasattr(lay, "invalidate"):
                        lay.invalidate()
                w.updateGeometry()
                self._stack.updateGeometry()
        except Exception:
            pass

    # --------------------- model action router (devices drill-down) --------
    # MediaTek board actions (Devices page) --------------------------------
    # These run the real BROM commands for the device the user selected in
    # the Devices list. They never open the MTK workbench and never fall back
    # to "the first device" (`_chip_begin` shows its picker when the key is
    # unknown). Destructive work always goes through `_confirm_overlay`.

    def _mtk_board_key(self):
        """The key of the device selected on the Devices page (or None).

        `_display_key` is the row the user picked; passing None is safe —
        `_chip_begin` asks instead of guessing a target.
        """
        return getattr(self, "_display_key", None)

    def _mtk_board_da(self, label, action):
        """Bundled DA dir, or "" after an honest error when it is missing."""
        try:
            da_dir = bridge.bundled_mtk_da_dir() or ""
        except Exception:
            da_dir = ""
        if da_dir:
            return da_dir
        self.log_line(
            f"[error] {label}: bundled MediaTek DA containers missing "
            "(root/tools/mtk/MTK_DA_V5.bin)")
        self._toasts.show_error(
            f"{label} · {action}",
            "Bundled MediaTek DA is missing (root/tools/mtk). Reinstall "
            "FlashPilot or restore the DA containers — BROM operations "
            "cannot run without it.")
        return ""

    def _mtk_board_frp(self, label):
        """FRP removal over BROM when the selected phone has no ADB."""
        da_dir = self._mtk_board_da(label, "Remove FRP")
        if not da_dir:
            return
        key = self._mtk_board_key()
        self.log_line(f"[step] {label}: FRP via BROM (bundled DA, no ADB)")
        self._confirm_overlay(
            f"{label} · Remove FRP",
            "No authorized ADB on the selected phone, so FRP is cleared\n"
            "over BROM (boot ROM) instead.\n\n"
            "The BROM exploit / DAA bypass runs first, then the FRP and\n"
            "lock partitions are erased from the device GPT. Lock\n"
            "partitions are erased and user data may be lost.\n\n"
            "Continue?",
            confirm_label="Remove FRP",
            on_confirm=lambda k=key, d=da_dir: self._mtk_run(
                ["mtk-frp-brom", "auto", d], timeout=1800, device_key=k),
            chip="frp",
        )

    def _mtk_board_screen_lock_choice(self, label):
        """No-ADB screen-lock choice: 'erase' | 'wipe' | None (cancelled)."""
        box = QMessageBox(self)
        box.setWindowTitle(f"{label} · Remove Screen Lock")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("No authorized ADB — the lock must be cleared over BROM.")
        box.setInformativeText(
            "Erase locks only: removes the PIN/pattern/password and FRP\n"
            "keys; userdata is kept.\n\n"
            "Factory reset: also wipes userdata (all apps and files).")
        erase_btn = box.addButton("Erase locks only",
                                  QMessageBox.ButtonRole.AcceptRole)
        wipe_btn = box.addButton("Factory reset (wipe data)",
                                 QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(erase_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is erase_btn:
            return "erase"
        if clicked is wipe_btn:
            return "wipe"
        return None

    def _mtk_board_screen_lock(self, label):
        """Screen lock removal over BROM when the selected phone has no ADB."""
        da_dir = self._mtk_board_da(label, "Remove Screen Lock")
        if not da_dir:
            return
        choice = self._mtk_board_screen_lock_choice(label)
        if not choice:
            self.log_line(f"[info] {label}: screen-lock removal cancelled")
            return
        wipe = choice == "wipe"
        args = ["mtk-screen-lock", "auto", da_dir]
        if wipe:
            args.append("--wipe-userdata")
        key = self._mtk_board_key()
        warn = (
            "FACTORY RESET: every user partition is erased (apps, photos,\n"
            "accounts) in addition to the lock.\n\n" if wipe else
            "ERASE LOCKS: the PIN/pattern/password, FRP and keystore\n"
            "partitions are erased. Userdata is kept.\n\n")
        self._confirm_overlay(
            f"{label} · Remove Screen Lock",
            warn + "Runs over BROM with the bundled DA. The phone must stay\n"
                   "connected. Continue?",
            confirm_label="Factory Reset" if wipe else "Erase Locks",
            on_confirm=lambda a=args, k=key: self._mtk_run(
                a, timeout=1800, device_key=k),
            chip="wipe" if wipe else "lock",
        )

    def _mtk_board_backup(self, label):
        """Back up the device GPT over BROM to a user-picked folder."""
        da_dir = self._mtk_board_da(label, "Backup")
        if not da_dir:
            return
        out_dir = QFileDialog.getExistingDirectory(
            self, "MTK backup output folder", "/tmp/mtk_backup")
        if not out_dir:
            self.log_line(f"[info] {label}: backup cancelled")
            return
        key = self._mtk_board_key()
        self.log_line(f"[step] {label}: GPT backup via BROM (bundled DA)")

        def done(_out):
            # Report the destination only once the bridge run has returned.
            self.log_line(f"[backup] {label}: GPT backup written to {out_dir}")

        self._confirm_overlay(
            f"{label} · Backup GPT",
            f"Read the partition table (GPT) over BROM and write a backup\n"
            f"to:\n{out_dir}\n\nUses the bundled DA. Continue?",
            confirm_label="Backup GPT",
            on_confirm=lambda o=out_dir, d=da_dir, k=key: self._mtk_run(
                ["mtk-backup-gpt", "auto", d, o], timeout=1800,
                device_key=k, on_done=done),
            chip="mtk",
        )

    def _mtk_board_flash_mode(self):
        """Ask which download mode to use. Returns 'flash', 'format',
        'format_data' or '' when cancelled. Extracted so tests can drive the
        decision without a modal dialog."""
        box = QMessageBox(self)
        box.setWindowTitle("MTK flash mode")
        box.setText(
            "How should the flash run?\n\n"
            "Format All erases each target partition before writing it; "
            "Format All + wipe data also erases userdata and cache."
        )
        fmt_all = box.addButton("Format all + download", QMessageBox.ButtonRole.AcceptRole)
        fmt_data = box.addButton(
            "Format all + wipe data", QMessageBox.ButtonRole.DestructiveRole)
        flash_only = box.addButton("Flash only", QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is None or clicked is cancel:
            return ""
        if clicked is fmt_data:
            return "format_data"
        if clicked is fmt_all:
            return "format"
        if clicked is flash_only:
            return "flash"
        return ""

    def _mtk_board_flash(self, label):
        """Flash a firmware folder over BROM (mtk-flash-auto, auto DA)."""
        folder = QFileDialog.getExistingDirectory(
            self, "MTK firmware folder",
            self.settings.value("default_dir", os.path.expanduser("~/Downloads")))
        if not folder:
            self.log_line(f"[info] {label}: flash cancelled")
            return
        key = self._mtk_board_key()
        mode = self._mtk_board_flash_mode()
        if not mode:
            self.log_line(f"[info] {label}: flash cancelled at mode prompt")
            return
        if mode == "format_data":
            mode_flags = ["--format-all", "--erase-userdata"]
            mode_label = "Format All + wipe data"
        elif mode == "format":
            mode_flags = ["--format-all"]
            mode_label = "Format All + download"
        else:
            mode_flags = []
            mode_label = "Flash only"
        self._confirm_overlay(
            f"{label} · Flash Firmware",
            f"Mode: {mode_label}\nFolder:\n{folder}\n\n"
            "mtk-flash-auto matches images to partitions from the device\n"
            "GPT/scatter and OVERWRITES those partitions. A wrong folder,\n"
            "a mismatched model or an interrupted cable can leave the\n"
            "phone unbootable.\n\nContinue?",
            confirm_label="Flash Firmware",
            on_confirm=lambda f=folder, k=key, mf=list(mode_flags): self._mtk_run(
                ["mtk-flash-auto", "auto", f, "--da", "auto", *mf],
                timeout=3600, device_key=k),
            chip="flash",
        )

    def start_model_action(self, act, brand_label, meta, feature=None):
        """Wire a Devices drill-down action to the real engine for its chip.

        act: frp | info | backup | flash | adb_enable | kg_unlock
        meta: model dict from supported_devices.json (engine, vid, ...)
        feature: experimental feature id when routed through the ownership
        overlay (lets the runner consume the matching per-run ack token).
        Only researched models reach here with enabled buttons; guards below
        keep un-researched or missing-input cases safe and guided."""
        engine = (meta.get("engine") or "").lower()
        label = f"{brand_label} {meta.get('model','')}"
        self.log_line(f"[device] {label}: {act} via {engine or 'n/a'}")

        if act == "info" and engine != "qcom":
            # Generic identity refresh. Qualcomm is the exception: its engine
            # block below runs the real `qcom-detect` EDL scan, so it must not
            # be swallowed here.
            self.refresh_device()
            return

        if act == "kg_unlock":
            # Samsung AT KnoxGuard chain through the bridge. Pinned to one
            # explicitly-picked Samsung device (never first-match): with
            # several Samsungs attached this refuses instead of unlocking
            # the wrong phone. Validation (scans) stays on the GUI thread;
            # the bridge call runs in a worker (previously synchronous —
            # the 30s chain froze the whole window).
            try:
                sams = [r for r in _devices.list_devices()
                        if isinstance(r, dict) and (r.get("usb") or {}).get("vid") == 0x04E8
                        and r.get("key")]
                skeys = [r["key"] for r in sams]
                if not skeys:
                    raise RuntimeError("no Samsung device on USB")
                if len(skeys) > 1:
                    raise RuntimeError(
                        f"{len(skeys)} Samsung devices connected — KG unlock "
                        "needs exactly one target (unplug the others)")
                key = skeys[0]
                # Per-device run guard: a concurrent op on the SAME phone
                # blocks this.
                if not _flow_start("KG unlock", destructive=True, key=key):
                    self._toasts.show_warn("Operation already running",
                                           _flow_busy_msg(key=key))
                    return
                # Fresh target for the picked key (never a stale cached one).
                tgt = _devices.resolve_usb_target(key)
                if not tgt:
                    _flow_end(key=key)
                    raise RuntimeError("Samsung device left USB — replug and retry")

                def work():
                    flux = jobs.start_job(key, "KG unlock", "AT", "kg_unlock", ())
                    flux.set_state("VALIDATED")
                    flux.set_state("RUNNING")
                    try:
                        with _devices.device_scope(key):
                            out = bridge._run(["at-kg-unlock", tgt, "4000"],
                                              timeout=30)
                        jobs.finish_job(flux.job_id, "COMPLETED")
                        self.log_line(f"[kg] {out}")
                        self._toasts.show_ok("KG unlock",
                                             f"{label}: chain sent — check phone")
                    except Exception as e:  # noqa: BLE001
                        state, code = jobs.classify_failure(e, key)
                        jobs.finish_job(flux.job_id, state, str(e), code)
                        self.log_line(f"[kg] failed: {e}")
                        self._toasts.show_error("KG unlock failed", str(e))
                    finally:
                        _flow_end(key=key)

                threading.Thread(target=work, daemon=True).start()
            except Exception as e:  # noqa: BLE001
                self._toasts.show_error("KG unlock failed", str(e))
            return

        # Per-model per-engine reverse-engineered flows. Each action key maps
        # directly to a flow registered in core.FLOWS via the per-engine naming
        # convention (tecno_* / apple_* / samsung_* / mtk_*). The flow itself
        # decides whether it needs ADB, BROM, MTP, etc. — this dispatcher
        # only needs to (a) make sure the flow exists and (b) run it.
        if act in core.FLOWS:
            # For BROM/MTK paths, make sure the matching workbench is open so
            # the user can see progress + the FDL fields the flow reads.
            engine = (meta.get("engine") or "").lower()
            if act.endswith("_brom") and engine in ("spd", "mtk"):
                self._on_section(engine)
            if act == "flash":
                # Per-model flash: route by THIS model's engine, never a
                # generic chip assumption. motorola/qcom = fastboot-based;
                # mtk/spd/odin open their own workbench; apple/kirin have
                # no PC flash path (honest toast).
                self._route_model_flash(label, engine, meta)
                return
            # Map to a generic (job, mode) so the global flow runner's status
            # banner reads sensibly. The flow name itself is the source of truth.
            job_mode = {
                "tecno_frp_adb":         ("Remove FRP",          "ADB"),
                "tecno_frp_brom":        ("Remove FRP",          "Samsung BROM" if engine == "spd" else "MTK BROM"),
                "tecno_screen_lock_adb": ("Remove Screen Lock",  "ADB"),
                "tecno_screen_lock_brom":("Remove Screen Lock",  "Samsung BROM" if engine == "spd" else "MTK BROM"),
                "tecno_mdm_adb":         ("Remove MDM",          "ADB"),
                "tecno_mdm_brom":        ("Remove MDM",          "Samsung BROM" if engine == "spd" else "MTK BROM"),
                "tecno_device_info":     ("Read Device Info",     "ADB"),
                "tecno_enable_adb":      ("Remove FRP",          "MTP"),
                "moto_frp_adb":          ("Remove FRP",          "ADB"),
                "moto_frp_fastboot":     ("Remove FRP",          "FASTBOOT"),
                "moto_fb_frp":           ("Remove FRP",          "FASTBOOT"),
                "moto_fb_factory_adb":   ("Remove FRP",          "FASTBOOT"),
                "fastboot_unlock":       ("Unlock Bootloader",   "FASTBOOT"),
                "fastboot_lock":         ("Lock Bootloader",     "FASTBOOT"),
                "frp_fake_login":        ("Remove FRP",          "ADB"),
                "frp_fake_login_testdpc": ("Remove FRP",        "ADB"),
                "frp_fake_login_adp":     ("Remove FRP",        "ADB"),
                "pac_extract":           ("Flash Firmware",      "SPD"),
                "pac_pack":              ("Flash Firmware",      "SPD"),
                "ofp_extract":           ("Flash Firmware",      "SPD"),
                "apple_info":            ("Read Device Info",    "ADB"),
                "apple_passcode_guide":  ("Read Device Info",    "ADB"),
            }.get(act)
            if job_mode:
                self._run_ops_flow(job_mode[0], job_mode[1], act, f"{label} · {act}",
                                   feature=feature)
            else:
                # Generic fallback: the Rust registry names the real
                # job/mode so the banner reads sensibly for any present or
                # future flow (hub buttons rely on this — no per-flow map).
                _rj, _rm = "Read Device Info", "ADB"
                try:
                    for _row in core._load_registry() or []:
                        if _row.get("key") == act:
                            _rj = _row.get("job") or _rj
                            _rm = _row.get("mode") or _rm
                            break
                except Exception:
                    pass
                self._run_ops_flow(_rj, _rm, act, f"{label} · {act}",
                                   feature=feature)
            return

        if engine == "spd":
            # Unisoc (SPD) board actions run from ONE PAC file: `spd-flash-pac`
            # pulls the matching FDL1/FDL2 + load addresses straight out of the
            # PAC, so a model no longer dead-ends on "load the FDL binaries
            # first". ADB-capable paths still win when the SELECTED phone is
            # live over ADB; the manual FDL paths stay available for advanced
            # workbench work (there they are genuinely required).
            if act == "screen_lock":
                if self._adb_ready_for_key():
                    self._run_ops_flow("Remove Screen Lock", "ADB",
                                       "screen_lock_locksettings",
                                       f"{label} · screen lock remove (ADB)")
                    return
                self._spd_board_screen_lock(label)
                return
            if act == "frp":
                # ADB FRP first — bounded (<=1s) and only satisfied by the
                # SELECTED phone, never a different attached one.
                if self._adb_ready_for_key():
                    self._run_ops_flow("Remove FRP", "ADB", "adb_frp",
                                       f"{label} · FRP bypass (ADB)")
                    return
                if self._spd_fdl1():
                    # FDL1/FDL2 already configured on the SPD tab: keep the
                    # proven `spd-frp` path (and show the tab it reads from).
                    self._on_section("spd")
                    self._spd_frp()
                    return
                self._spd_board_frp(label)
                return
            if act == "backup":
                self._spd_board_backup(label)
                return
            if act == "flash":
                # Single PAC flash straight from the board — no SPD workbench
                # detour and no per-partition image folder.
                self._spd_board_flash(label)
                return
            if act == "adb_enable":
                self._on_section("spd")
                self._spd_enable_adb()
                return
            self._toasts.show_info(f"{label} · {act}",
                                   "Wiring lands in the next step.")
            return

        if engine == "qcom":
            # Qualcomm (catalogued + curated models): the board actions run the
            # real EDL 9008 (Sahara/Firehose) bridge commands for the SELECTED
            # device. The bundled programmers are auto-selected by SoC index
            # (`--programmer auto` / the bare `auto` target slot), so nothing
            # here needs the QC workbench tab. ADB-capable actions still go to
            # the universal ADB flows.
            if act == "screen_lock":
                self._run_ops_flow("Remove Screen Lock", "ADB",
                                   "screen_lock_locksettings",
                                   f"{label} · screen lock remove (ADB)")
                return
            if act == "adb_enable":
                self._run_ops_flow("Remove FRP", "MTP", "enable_adb",
                                   f"{label} · enable ADB")
                return
            if act == "info":
                self._on_section("qc")
                self._qc_detect()
                return
            if act == "frp":
                # Prefer ADB FRP when the SELECTED phone is authorized. Bounded
                # (<=1s) and never satisfied by a different attached phone.
                adb_up = self._adb_ready_for_key()
                if adb_up:
                    self._run_ops_flow("Remove FRP", "ADB", "adb_frp",
                                       f"{label} · FRP bypass (ADB)")
                    return
                self._qc_board_frp(label)
                return
            if act == "backup":
                self._qc_board_backup(label)
                return
            if act == "flash":
                self._qc_board_flash(label)
                return
            self._toasts.show_info(f"{label} · {act}",
                                   "Wiring lands in the next step.")
            return

        if engine in ("mtk", "kirin"):
            # MediaTek / Huawei engines — route ADB-capable actions to
            # the universal ADB flows; MTK board actions run the real BROM
            # commands for the selected device (no workbench detour).
            if act == "screen_lock":
                if engine == "mtk":
                    if self._adb_ready_for_key():
                        self._run_ops_flow(
                            "Remove Screen Lock", "ADB",
                            "screen_lock_locksettings",
                            f"{label} · screen lock remove (ADB)")
                        return
                    self._mtk_board_screen_lock(label)
                    return
                self._run_ops_flow("Remove Screen Lock", "ADB",
                                   "screen_lock_locksettings",
                                   f"{label} · screen lock remove (ADB)")
                return
            if act == "adb_enable":
                # Motorola (22b8) has no Samsung AT path — Samsung flow would
                # log A02s/SDM450 guidance and confuse. Give Moto steps instead.
                vid = str(meta.get("vid", "")).lower()
                model_l = str(meta.get("model", "")).lower()
                if "22b8" in vid or "moto" in model_l or "g6" in model_l or "motorola" in brand_label.lower():
                    self.log_line(f"[device] {label}: Moto G6 has no AT ADB enable (22b8 MTP vendor, no diag port)")
                    self._toasts.show_info(
                        f"{label} · Enable ADB",
                        "Moto FRP-locked has no ADB: use the MDM ▸ Generate QR "
                        "fake-login (enrolls a device owner that enables ADB), "
                        "the factory-bootmode cycle (FRP REMOVE → factory-mode), "
                        "or on-phone wizard escapes. No Samsung *#0*#/AT.")
                    return
                self._run_ops_flow("Remove FRP", "MTP", "enable_adb",
                                   f"{label} · enable ADB")
                return
            if act == "frp":
                # Prefer ADB FRP when the SELECTED phone is authorized; the
                # check is bounded (<=1s) and never satisfied by another phone.
                adb_up = self._adb_ready_for_key()
                if adb_up:
                    self._run_ops_flow("Remove FRP", "ADB", "adb_frp",
                                       f"{label} · FRP bypass (ADB)")
                    return
                vid = str(meta.get("vid", "")).lower()
                model_l = str(meta.get("model", "")).lower()
                if "22b8" in vid or "moto" in model_l or "motorola" in brand_label.lower():
                    self.log_line(f"[device] {label}: Moto G6 FRP — no ADB, use browser/fastboot")
                    self._toasts.show_info(
                        f"{label} · FRP",
                        "No ADB: MDM ▸ Generate QR (fake-login enables ADB), "
                        "FRP REMOVE → factory-mode cycle, or on-phone wizard "
                        "escapes (Browser → Settings → remove account).")
                    return
                if engine == "mtk":
                    self._mtk_board_frp(label)
                    return
                # Huawei/Kirin: no PC-side FRP path — keep the guidance.
                self._on_section("mtk")
                self._toasts.show_info(
                    f"{label} · FRP",
                    "Load DA + scatter on the MTK tab (or catch BROM) — "
                    "FRP clears via combo flash. For ADB method, authorize "
                    "USB debugging first.")
                return
            if act == "flash":
                if engine == "mtk":
                    self._mtk_board_flash(label)
                    return
                self._route_model_flash(label, engine, meta)
                return
            if act == "backup":
                if engine == "mtk":
                    self._mtk_board_backup(label)
                    return
                self._on_section("mtk")
                self._toasts.show_info(
                    f"{label} · Backup",
                    "Use MTK tab Backup Partitions (DA + scatter required).")
                return
            if act == "info":
                self._on_section("mtk")
                self._mtk_detect()
                return
            self._toasts.show_info(f"{label} · {act}",
                                   "Wiring lands in the next step.")
            return

        if engine == "motorola":
            # Brand-wide Motorola/Lenovo routing (universal entry + any moto
            # model). Moto-specific acts are handled above via core.FLOWS;
            # generic acts map to the universal ADB flows or honest guidance.
            if act == "screen_lock":
                self._run_ops_flow("Remove Screen Lock", "ADB",
                                   "screen_lock_locksettings",
                                   f"{label} · screen lock remove (ADB)")
                return
            if act == "adb_enable":
                # Motorola (22b8) has no Samsung AT path and no Linux MDL
                # driver — on-phone steps only.
                self.log_line(f"[device] {label}: Moto has no AT ADB enable (no diag port on Linux)")
                self._toasts.show_info(
                    f"{label} · Enable ADB",
                    "No PC-side ADB enable on Motorola: on the phone use the "
                    "Browser/TalkBack route to Settings → Developer options → "
                    "USB debugging, or unlock via fastboot (see FRP REMOVE → FB).")
                return
            if act == "frp":
                # Selected-device-only, bounded ADB check (no GUI freeze, no
                # unrelated-phone false positive).
                adb_up = self._adb_ready_for_key()
                if adb_up:
                    self._run_ops_flow("Remove FRP", "ADB", "moto_frp_adb",
                                       f"{label} · FRP reset (ADB)")
                else:
                    self.log_line(f"[device] {label}: Moto FRP — no ADB, use fastboot flow or on-phone route")
                    self._toasts.show_info(
                        f"{label} · FRP",
                        "No authorized ADB. Either run FRP REMOVE → FB "
                        "(staged flash when firmware is set, else the "
                        "CVE-2016-10277 chain), or on-phone Browser → "
                        "Settings → remove account.")
                return
            if act in ("flash", "backup"):
                self._toasts.show_info(
                    f"{label} · {act}",
                    "Motorola flash/backup is fastboot-based with model-specific "
                    "stock firmware (not bundled). Use the FASTBOOT job flows "
                    "(fastboot_flash / fastboot_erase) with your firmware files.")
                return
            self._toasts.show_info(f"{label} · {act}",
                                   "Wiring lands in the next step.")
            return

        # Samsung / Odin engines
        if act == "frp":
            try:
                methods = core.methods_for("Remove FRP", "Download mode")
                method = methods[0] if methods else "download_frp"
            except Exception:
                method = "download_frp"
            self._run_ops_flow("Remove FRP", "Download mode", method,
                               f"{label} · FRP bypass (download mode)")
        elif act == "backup":
            self._run_ops_flow("Flash Firmware", "Download mode",
                               "odin_efs_backup", f"{label} · EFS backup")
        elif act == "flash":
            self._route_model_flash(label, engine, meta)
        else:
            self._toasts.show_info(f"{label} · {act}",
                                   "Wiring lands in the next step.")

    # ----------------------------- Native one-session flash ---------------
    def _nf_pick_tar(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Odin archive", "",
            "Odin archives (*.tar *.tar.md5);;All files (*)",
        )
        if path:
            self._nf_tar_edit.setText(path)

    def _native_flash_clicked(self):
        if getattr(self, "_nf_busy", False):
            return
        tar_path = self._nf_tar_edit.text().strip()
        if not tar_path or not os.path.isfile(tar_path):
            self._toasts.show_warn("Native flash", "Pick a .tar archive first")
            return
        # Pin to one explicitly-picked Download-mode device: the core smart
        # flash resolves its target through the ambient scope, so without a
        # pinned key it would take the first Download-mode phone.
        picked = self._pick_device("Flash Firmware", "Download mode")
        if picked == "__cancelled__":
            return
        if not picked:
            self._toasts.show_warn(
                "Native flash", "Put the phone in Download mode first "
                "(Vol Down + Power, then Vol Up)."
            )
            return
        device_key = picked
        from ..core import actions as _actions_mod
        ok, last = _actions_mod.check_actions(
            device_key, ["samsung_odin_flash"], bridge.validate_action)
        if not ok:
            self.log_line(f"[refused] Flash Firmware is not valid for {device_key}: {last}")
            self._toasts.show_warn("Unsupported for this device",
                                   "Flash cannot run on the selected device "
                                   "in its current state.")
            return
        # Per-device run guard: a concurrent ops flow on the SAME phone must
        # block this (the old _nf_busy flag alone could not see it).
        if not _flow_start("Native flash", destructive=True, key=device_key):
            self._toasts.show_warn("Operation already running",
                                   _flow_busy_msg(key=device_key))
            return
        patch = self._nf_patch_cb.isChecked()

        def do_flash():
            flux = jobs.start_job(device_key, "Flash Firmware", "Download mode",
                                  "smart_flash", ["samsung_odin_flash"])
            flux.set_state("VALIDATED")
            flux.set_state("RUNNING")

            def emit(line):
                try:
                    flux.append_log(str(line))
                except Exception:
                    pass
                self.log_line(line)

            emit(f"[smart-flash] {os.path.basename(tar_path)} "
                 f"(vbmeta patch={'on' if patch else 'off'})")
            try:
                with _devices.device_scope(device_key):
                    result = core.flash_archive_smart(
                        tar_path, log=emit, patch_vbmeta=patch,
                    )
                ok = True
                summary = (f"flashed {len(result['flashed'])} partitions, "
                           f"skipped {len(result['skipped'])}, "
                           f"reboot={result['rebooted']}")
                jobs.finish_job(flux.job_id, "COMPLETED")
            except Exception as e:
                ok = False
                summary = str(e)
                emit(f"[smart-flash] ERROR: {e}")
                state, code = jobs.classify_failure(e, device_key)
                jobs.finish_job(flux.job_id, state, str(e), code)

            def done():
                self._nf_busy = False
                self._nf_flash_btn.setEnabled(True)
                _flow_end(key=device_key)
                if ok:
                    self._toasts.show_ok(
                        "Flash complete", summary)
                else:
                    self._toasts.show_warn("Flash failed", summary)

            self._ui.ui.emit(done)

        self._nf_busy = True
        self._nf_flash_btn.setEnabled(False)
        threading.Thread(target=do_flash, daemon=True).start()

    # ----------------------------- PIT safety contract --------------------
    def _refresh_pit_cache_label(self):
        try:
            s = pitstore.stats()
            if s["count"]:
                self._pit_cache_lbl.setText(
                    f"cache: {s['count']} table(s) for {', '.join(s['models'][:3])}"
                )
            else:
                self._pit_cache_lbl.setText("cache: empty")
        except Exception:
            self._pit_cache_lbl.setText("")

    def _show_secret_codes(self):
        """Show the Transsion/XOS secret code reference table."""
        import json
        dlg = QDialog(self)
        dlg.setWindowTitle("Transsion/XOS Secret Codes (Infinix · Tecno · itel)")
        dlg.setMinimumSize(760, 560)
        dlg.setStyleSheet(f"background:{C['panel']}; color:{C['text']};")
        lay = QVBoxLayout(dlg)

        chain = QLabel(
            "EXACT CHAIN (factory-reset / FRP phones):\n"
            "Welcome → language & country → WiFi → Next →\n"
            "tap 'Personalized Recommendations' privacy link → Chrome →\n"
            "type 'frpbypass' → open the DIALER link on that site →\n"
            "real Dialer opens → dial *#*#49#*#* → ADB on.\n"
            "(The lock-screen emergency pad does NOT process secret codes.)"
        )
        chain.setWordWrap(True)
        chain.setStyleSheet(f"color:{C['warn']}; font-size:11px; font-weight:600; padding:6px;")
        lay.addWidget(chain)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Code", "Action", "Verified"])
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnWidth(0, 170)
        table.setColumnWidth(1, 380)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setStyleSheet(
            f"QTableWidget {{ background:{C['inset']}; border:1px solid {C['border']};"
            f" border-radius:8px; color:{C['text']}; gridline-color:{C['border']}; }}"
            f" QHeaderView::section {{ background:{C['card']}; color:{C['accent_hi']};"
            f" border:none; padding:6px; font-weight:700; }}"
        )
        try:
            codes_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "docs", "secret_codes_xos.json")
            with open(codes_path) as f:
                data = json.load(f)
            entries = data.get("codes", [])
        except Exception:
            entries = [
                {"code": "*#*#49#*#*", "action": "Enable persistent ADB", "verified": True},
                {"code": "*#*#83781#*#*", "action": "EngineerMode main menu", "verified": False},
            ]
        table.setRowCount(len(entries))
        for r, e in enumerate(entries):
            c0 = QTableWidgetItem(e.get("code", ""))
            f0 = c0.font(); f0.setBold(e.get("verified", False)); c0.setFont(f0)
            table.setItem(r, 0, c0)
            table.setItem(r, 1, QTableWidgetItem(e.get("action", "")))
            v = "✅ field-tested" if e.get("verified") else "manifest"
            table.setItem(r, 2, QTableWidgetItem(v))
        lay.addWidget(table)

        note = QLabel(
            "Note: direct SECRET_CODE broadcast from shell is denied by the system - "
            "the real dialer is required. *#*#49#*#* sets persist.sys.usb.config=adb "
            "(survives reboot and setup wizard)."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{C['dim']}; font-size:10px; padding:6px;")
        lay.addWidget(note)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(_btn_ghost())
        close_btn.clicked.connect(dlg.accept)
        bl = QHBoxLayout()
        bl.addStretch(1); bl.addWidget(close_btn)
        lay.addLayout(bl)
        dlg.exec()

    def _adb_triage(self, device_key=None):
        """Probe connected ADB device: lock state, root, partition access."""
        prep = self._adb_begin("ADB triage", "adb_triage", device_key)
        if prep[0] is None:
            return
        serial, device_key, flux = prep

        def work():
            lines = []
            base_emit = lambda m: self._ui.line.emit(m) if hasattr(self, "_ui") else None

            def emit(m):
                try:
                    if flux:
                        flux.append_log(str(m))
                except Exception:
                    pass
                return base_emit(m)

            if flux:
                flux.set_state("RUNNING")
            enforced = False
            su = ""
            try:
                emit(f"[step] ADB triage on {serial}")
                sh = lambda c: bridge.adb_shell(c, timeout=10, serial=serial, rescue=False).strip()
                lines.append("=" * 60)
                lines.append("ADB DEVICE TRIAGE")
                lines.append("=" * 60)
                lines.append(f"Serial : {serial}")

                try:
                    model = sh("getprop ro.product.model")
                    brand = sh("getprop ro.product.brand")
                    android = sh("getprop ro.build.version.release")
                    fp = sh("getprop ro.build.fingerprint")
                    patch = sh("getprop ro.build.version.security_patch")
                    lines.append(f"Device : {brand} {model} (Android {android})")
                    lines.append(f"Fingerprint: {fp}")
                    lines.append(f"Security patch: {patch}")
                except Exception as e:
                    lines.append(f"(prop read failed: {e})")

                # root check
                try:
                    su = sh("su -c id")
                except Exception:
                    su = ""
                lines.append(f"Root   : {'YES' if 'uid=0' in su else 'no'}")

                # lock enforcement - Quality 0 means no security enforced
                enforced = False
                try:
                    lock_dump = bridge.adb_shell("dumpsys lock_settings", timeout=10, serial=serial, rescue=False)
                    quality = None
                    ctype = None
                    for ln in lock_dump.splitlines():
                        if "Quality:" in ln:
                            quality = ln.split("Quality:")[1].strip()
                        if "CredentialType:" in ln:
                            ctype = ln.split("CredentialType:")[1].strip()
                    enforced = quality not in ("0", None, "")
                    lines.append(f"Lock   : type={ctype} quality={quality} -> "
                                 f"{'ENFORCED (needs bypass)' if enforced else 'NOT ENFORCED (device open)'}")
                except Exception as e:
                    lines.append(f"Lock   : unknown ({e})")
                    enforced = False

                # partition access
                can_dd = False
                try:
                    outp = bridge.adb_shell(
                        "dd if=/dev/block/by-name/misc bs=512 count=1 2>/dev/null | wc -c",
                        timeout=10, serial=serial, rescue=False).strip()
                    can_dd = outp not in ("0", "")
                except Exception:
                    pass
                lines.append(f"Block access: {'yes (root-level I/O possible)' if can_dd else 'no (SELinux blocks shell)'}")

                # FRP state markers
                try:
                    prov = sh("settings get global device_provisioned")
                    setup = sh("settings get secure user_setup_complete")
                    in_oobe = prov == "0" or setup == "0"
                    lines.append(f"OOBE   : {'STILL IN SETUP WIZARD (FRP likely active)' if in_oobe else 'completed'}")
                except Exception as e:
                    lines.append(f"OOBE   : unknown ({e})")

                lines.append("")
                if not enforced:
                    lines.append("VERDICT: Device is open. Proceed with data/FRP work directly.")
                elif su and "uid=0" in su:
                    lines.append("VERDICT: Rooted. Remove lock via locksettings clear or /data/system.")
                else:
                    lines.append("VERDICT: Locked without root. Use boot.img patch (spd_adb.py),")
                    lines.append("         BROM route (FDL pair / magic64), or vendor tricks.")

                text = "\n".join(lines)
                emit(text)
                # Update pit_view on UI thread (secondary view); primary log already via emit
                def _update_view(t=text):
                    try:
                        if hasattr(self, "_pit_view") and self._pit_view:
                            self._pit_view.setPlainText(t[-1800:])
                    except Exception:
                        pass
                self._ui.ui.emit(_update_view)
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except bridge.BridgeCancelled as e:
                emit(f"[cancelled] ADB triage stopped by user ({e})")
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", str(e), "CANCELLED")
            except Exception as e:
                err = str(e)
                try:
                    self._ui.ui.emit(lambda m=err: self.show_toast("Triage failed", m, "error"))
                    emit(f"[error] Triage failed: {err}")
                except Exception:
                    pass
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                try:
                    _flow_end(key=device_key)
                except Exception:
                    pass

        threading.Thread(target=work, daemon=True).start()

    def _pit_fetch_clicked(self):
        if getattr(self, "_pit_fetching", False):
            return
        d = mtp.find_samsung()
        in_dl = core._download_mode_device()
        if not in_dl and not (d and d.get("pid") == 0x685d
                              and not mtp.is_adb_composite(d)):
            self._toasts.show_warn(
                "PIT fetch", "Put the phone in Download mode first "
                "(Vol Down + Power, then Vol Up)."
            )
            return
        self._pit_fetching = True
        self._pit_fetch_btn.setEnabled(False)
        self._pit_view.setPlainText("Fetching PIT from device...\n")
        target = f"04e8:{d['pid']:04x}@{d['bus']}:{d['address']}"

        def work():
            try:
                contract = core.pit_contract(target=target, log=None)
                health = contract["health"]
                raw = contract["raw"]
                text_lines = [f"target: {target}"
                              + ("  (cached)" if contract["from_cache"] else ""),
                              health["summary"], ""]
                for f in health["findings"]:
                    mark = {"fail": "FAIL", "warn": "warn", "info": "info"}[f["severity"]]
                    text_lines.append(f"[{mark}] {f['message']}")
                text_lines.append("")
                text_lines.append(pit.pit_map(raw))
                text, verdict = "\n".join(text_lines), health["verdict"]
                stats = health["stats"]
            except Exception as e:
                text, verdict, stats = f"PIT fetch failed: {e}", "fail", {}

            def done():
                self._pit_fetching = False
                self._pit_fetch_btn.setEnabled(True)
                self._pit_view.setPlainText(text)
                tile = self.info.get("PIT Health")
                if tile is not None:
                    n = stats.get("parsed_count", "?")
                    style = stats.get("style", "-")
                    tile.set(f"{verdict.upper()} - {n} parts ({style})")
                self.log_line(f"[pit-contract] {text.splitlines()[1] if len(text.splitlines())>1 else text}")
                self._refresh_pit_cache_label()

            self._ui.ui.emit(done)

        threading.Thread(target=work, daemon=True).start()

    def _fus_detect_device(self):
        self.fus_status_lbl.setText("Scanning connected Samsung device (ADB or Download mode)...")
        def work():
            try:
                try:
                    devs = bridge.adb_devices()
                except Exception:
                    devs = []
                if devs:
                    model, csc = self._fus_detect_via_adb()
                    def ok_adb():
                        self.fus_model_input.setText(model)
                        self.fus_region_input.setText(csc)
                        self.fus_status_lbl.setText(f"Detected connected device: {model} ({csc})")
                        self.show_toast(f"Detected {model} [{csc}]", "success")
                        self._fus_check_version()
                    self._ui.ui.emit(ok_adb)
                    return
                # No ADB: fall back to download (Odin) mode.
                def _dlog(msg):
                    try:
                        if hasattr(self, "_ui") and self._ui:
                            self._ui.line.emit(f"[fus-detect] {msg}")
                    except Exception:
                        pass
                # Zero-USB fast path: the background monitor may already have
                # resolved the model via its own Odin probe - reuse it instead
                # of contending the port with a second probe.
                cached = (getattr(self, "_cached_model", "") or "").strip()
                if cached and not cached.startswith(("0x", "--", "(")) and cached.strip().lower() not in (
                    "adb", "samsung", "mediatek", "qualcomm", "unknown",
                ):
                    _dlog(f"using already-known model {cached} (no USB probe needed)")
                    model = cached.upper()
                else:
                    _dlog("no ADB device - trying download (Odin) mode ...")
                    model = self._fus_detect_via_download_mode(log=_dlog)
                def ok_dl():
                    region = self.fus_region_input.text().strip() or "EUX"
                    self.fus_model_input.setText(model)
                    try:
                        if model and model != getattr(self, "_cached_model", None):
                            self._cached_model = model
                        if hasattr(self, "info") and "Device Model" in self.info:
                            self.info["Device Model"].set(model)
                    except Exception:
                        pass
                    self.fus_status_lbl.setText(
                        f"Detected download-mode phone: {model} "
                        f"(CSC unreadable in download mode - verify region [{region}], then Check Version)"
                    )
                    self.show_toast(f"Detected {model} (download mode)", "success")
                    self._fus_check_version()
                self._ui.ui.emit(ok_dl)
            except Exception as e:
                err = str(e)
                def fail():
                    self.fus_status_lbl.setText(f"Detection failed: {err}")
                    self.show_toast(f"Device detection failed: {err}", "error")
                self._ui.ui.emit(fail)

        threading.Thread(target=work, daemon=True).start()

    def _fus_detect_via_adb(self):
        """Return (model, csc) from an ADB-connected phone. Raises on failure.

        Pinned to the displayed device when it is ADB-authorized (a model/CSC
        read from the wrong phone offers the wrong firmware for download).
        Explicit FUS Detect context: default rescue applies.
        """
        serial = None
        try:
            serial = self._adb_serial_for_key(getattr(self, "_display_key", None))
            if serial:
                auth = [d.get("serial") for d in bridge.adb_status()
                        if d.get("state") == "device"]
                if serial not in auth:
                    serial = None
        except Exception:
            serial = None
        model = bridge.adb_shell("getprop ro.product.model", timeout=5, serial=serial, rescue=False).strip()
        csc = bridge.adb_shell("getprop ro.boot.hardware.ods.csc", timeout=5, serial=serial).strip()
        if not csc:
            csc = bridge.adb_shell("getprop persist.sys.sales_code", timeout=5, serial=serial).strip()
        if not csc:
            csc = bridge.adb_shell("getprop ro.csc.sales_code", timeout=5, serial=serial, rescue=False).strip()
        if not model:
            model = "SM-S918B"
        if not csc:
            csc = "EUX"
        return model, csc

    def _fus_detect_via_download_mode(self, log=None):
        """Read the SM- model from a phone in Odin download mode.

        Returns the model string (e.g. 'SM-A145M'). CSC/region cannot be
        read in download mode, so the caller keeps the region field as-is.
        Raises RuntimeError when no download-mode phone is present or the
        model cannot be determined.
        """
        import re
        def _log(msg):
            try:
                if log:
                    log(msg)
            except Exception:
                pass
        _log("scanning USB for Samsung download-mode phone ...")
        d = core._download_mode_device()
        if not d:
            raise RuntimeError(
                "No ADB device authorized/connected and no Samsung phone in "
                "download mode found. Connect the phone in normal/ADB mode, "
                "or in Download mode (Vol Down + Power, then Vol Up)."
            )
        target = f"{d['vid']:04x}:{d['pid']:04x}@{d['bus']}:{d['address']}"
        _log(f"found {d['vid']:04x}:{d['pid']:04x} at bus={d['bus']} addr={d['address']} -> target {target}")
        try:
            res = bridge.usb_detach_kernel(target, timeout=15)
            _log(f"detach result: {res.get('detached') if isinstance(res, dict) else res}")
        except Exception as e:
            _log(f"kernel detach skipped: {e}")
        # Retry on transient "Resource busy": our own background monitor
        # fires odin-model probes on its own cycle and may briefly hold the
        # port. A persistent busy across all attempts means an external
        # holder (cdc_acm/ModemManager) - see the hint below.
        last_err: Exception | None = None
        info = None
        for attempt in range(3):
            try:
                _log(f"reading model via odin-model probe (attempt {attempt + 1}/3) ...")
                info = bridge.odin_model(target)
                _log(f"probe answered: {info}")
                break
            except Exception as e:
                last_err = e
                _log(f"probe attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    import time as _t
                    _t.sleep(3)
        else:
            raise RuntimeError(
                f"Download-mode phone found at {target} but the model probe failed 3x: {last_err} "
                "(reinstall the latest .deb so udev rules apply, reload with "
                "`sudo udevadm control --reload-rules && sudo udevadm trigger`, replug the phone; "
                "if 'Resource busy' persists, ModemManager/cdc_acm is holding the port - "
                "try `sudo systemctl stop ModemManager`)"
            )
        model = (info.get("model") or "").strip() if isinstance(info, dict) else str(info or "").strip()
        if not model or model.startswith("("):
            raise RuntimeError(
                f"Could not read model from download-mode phone (got {model!r}). "
                "Type the SM- model manually."
            )
        # FUS wants the marketing model (SM-A145M). The Odin probe sometimes
        # returns a bare code (A145M); restore the SM- prefix in that case.
        if not model.startswith(("SM-", "GT-", "SC-")) and re.match(r"^[A-Z]\d", model):
            model = "SM-" + model
        return model.upper()

    def _fus_set_details(self, details):
        """Fill the SamFW-style firmware card. Runs on the GUI thread."""
        def _fmt_size(n):
            if not n:
                return "—"
            if n >= 1024 ** 3:
                return f"{n / (1024 ** 3):.2f} GB"
            return f"{n / (1024 ** 2):.1f} MB"
        vals = {
            "model": details.get("model") or "—",
            "region": details.get("region") or "—",
            "pda": details.get("pda") or "—",
            "csc_ver": details.get("csc") or "—",
            "cp": details.get("cp") or "—",
            "size": _fmt_size(details.get("size_bytes")),
            "file": details.get("filename") or "—",
        }
        for k, v in vals.items():
            lbl = (self.fus_detail_vals or {}).get(k)
            if lbl is not None:
                lbl.setText(v)

    def _fus_check_version(self):
        model = self.fus_model_input.text().strip()
        region = self.fus_region_input.text().strip()
        if not model or not region:
            self.show_toast("Enter device model and region first.", "error")
            return
        self.fus_check_btn.setEnabled(False)
        self.fus_status_lbl.setText(f"Fetching firmware for {model} ({region})...")

        def work():
            try:
                details = fus.get_firmware_details(model, region)
                def ok():
                    self.fus_version_input.setText(details["version"])
                    self._fus_set_details(details)
                    size_txt = (
                        f" ({details['size_bytes'] / (1024 ** 2):.0f} MB)"
                        if details.get("size_bytes") else ""
                    )
                    self.fus_status_lbl.setText(
                        f"Latest firmware for {model} ({region}): {details['version']}{size_txt}"
                    )
                    self.fus_check_btn.setEnabled(True)
                    self.show_toast(f"Latest firmware: {details['version']}", "success")
                self._ui.ui.emit(ok)
            except Exception as e:
                err = str(e)
                def fail():
                    self.fus_status_lbl.setText(f"Check failed: {err}")
                    self.fus_check_btn.setEnabled(True)
                    self.show_toast(f"Check failed: {err}", "error")
                self._ui.ui.emit(fail)

        threading.Thread(target=work, daemon=True).start()

    def _fus_list_versions(self):
        model = self.fus_model_input.text().strip()
        region = self.fus_region_input.text().strip()
        if not model or not region:
            self.show_toast("Enter device model and region first.", "error")
            return
        self.fus_list_btn.setEnabled(False)
        self.fus_status_lbl.setText(f"Fetching all versions for {model} ({region})...")

        def work():
            try:
                versions = fus.list_all_versions(model, region)
                def ok():
                    self._show_version_dialog(versions)
                    self.fus_list_btn.setEnabled(True)
                    self.fus_status_lbl.setText(f"Found {len(versions)} versions for {model} ({region})")
                    self.show_toast(f"Found {len(versions)} firmware versions", "success")
                self._ui.ui.emit(ok)
            except Exception as e:
                err = str(e)
                def fail():
                    self.fus_status_lbl.setText(f"List failed: {err}")
                    self.fus_list_btn.setEnabled(True)
                    self.show_toast(f"List failed: {err}", "error")
                self._ui.ui.emit(fail)

        threading.Thread(target=work, daemon=True).start()

    def _show_version_dialog(self, versions: list):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout, QLabel
        dlg = QDialog(self)
        dlg.setWindowTitle("Available Firmware Versions")
        dlg.setMinimumSize(700, 500)
        dlg.setStyleSheet(f"background:{C['panel']}; color:{C['text']};")
        lay = QVBoxLayout(dlg)
        
        info = QLabel(f"Found {len(versions)} firmware versions (newest first)")
        info.setStyleSheet(f"color:{C['dim']}; font-size:12px; padding:5px;")
        lay.addWidget(info)
        
        list_w = QListWidget()
        list_w.setStyleSheet(f"QListWidget {{ background:{C['inset']}; border:1px solid {C['border']}; border-radius:8px; color:{C['text']}; }} QListWidget::item {{ padding:8px; border-bottom:1px solid {C['border']}; }} QListWidget::item:selected {{ background:{C['accent']}; }}")
        for v in versions:
            size_mb = v['size'] / (1024 * 1024)
            item = QListWidgetItem(f"{v['version']}  ({size_mb:.1f} MB, rcount={v['rcount']})")
            item.setData(Qt.ItemDataRole.UserRole, v)
            list_w.addItem(item)
        lay.addWidget(list_w)
        
        btn_row = QHBoxLayout()
        select_btn = QPushButton("Select Version")
        select_btn.setStyleSheet(_btn_primary())
        select_btn.clicked.connect(lambda: self._select_version_from_dialog(dlg, list_w))
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_btn_ghost())
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(select_btn)
        lay.addLayout(btn_row)
        
        dlg.exec()

    def _select_version_from_dialog(self, dlg, list_w):
        item = list_w.currentItem()
        if item:
            data = item.data(Qt.ItemDataRole.UserRole)
            ver = data.get("version") if isinstance(data, dict) else data
            self.fus_version_input.setText(ver)
            if isinstance(data, dict):
                parts = (ver or "").split("/")
                self._fus_set_details({
                    "model": self.fus_model_input.text().strip().upper(),
                    "region": self.fus_region_input.text().strip().upper(),
                    "pda": parts[0] if len(parts) > 0 else "",
                    "csc": parts[1] if len(parts) > 1 else "",
                    "cp": parts[2] if len(parts) > 2 else "",
                    "size_bytes": data.get("size"),
                    "filename": None,
                })
                self.fus_status_lbl.setText(f"Selected firmware: {ver}")
            dlg.accept()
            self.show_toast(f"Selected version: {ver}", "info")

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
                self._ui.ui.emit(upd)

        def log_cb(msg):
            def l():
                self._append_console(f"[fus] {msg}")
            self._ui.ui.emit(l)

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
                self._ui.ui.emit(done)
            except Exception as e:
                err = str(e)
                def fail():
                    self.fus_download_btn.setEnabled(True)
                    self.fus_status_lbl.setText(f"Download/Decrypt failed: {err}")
                    self._append_console(f"[fus] ERROR: {err}")
                    self.show_toast(f"Download failed: {err}", "error")
                    _flow_end()
                self._ui.ui.emit(fail)

        threading.Thread(target=work, daemon=True).start()

    def _fus_load_into_ap(self):
        fw = getattr(self, "_last_decrypted_fw", None)
        if not fw or not os.path.exists(fw):
            self.show_toast("No downloaded firmware found to load.", "warning")
            return
        # Populate AP slot in Samsung tab if available
        ap_slot = getattr(self, "slot_inputs", {}).get("AP")
        if ap_slot is not None:
            ap_slot.setText(fw)
            self.show_toast("Loaded decrypted firmware into AP slot!", "success")
            self._on_section("samsung")
        else:
            self.show_toast(f"Firmware ready at: {fw}", "info")

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

    def _key_for_bus_addr(self, tgt):
        """Device key for a `bus:addr` target via fresh scan, or None when
        that transport is not on USB now. Used when callers pass explicit
        targets (no picking dialog needed — the target IS the choice)."""
        if not tgt or not isinstance(tgt, str):
            return None
        try:
            devs = bridge.detect_all() or []
        except Exception:
            return None
        for d in devs:
            if not isinstance(d, dict):
                continue
            try:
                if f"{d['bus']}:{d['address']}" == tgt:
                    return _devices.device_key(d) or None
            except (KeyError, TypeError):
                continue
        return None

    def _chip_begin(self, tag, cmd, modes, args, device_key=None,
                    stop_btn=None, target_idx=1, destructive=True):
        """Shared prologue for chip-page direct runners (MTK/QC/SPD).

        Picks a device (dialog only when >1 candidate; an explicit
        non-"auto" target derives its key from a fresh scan instead),
        validates against the backend registry, takes the per-device lock,
        clears scoped cancels, starts the FlashJob (VALIDATED), and splices
        a fresh explicit bus:addr target over "auto".

        Returns (device_key, flux, args) or (None, None, None) when the run
        must not start (refusal/busy/gone — already logged + toasted).
        """
        from ..core import actions as _actions_mod

        label = f"{tag} {cmd}" if cmd else tag
        if device_key is None and len(args) > target_idx and args[target_idx] != "auto":
            device_key = self._key_for_bus_addr(args[target_idx])
            if not device_key:
                self._ui.line.emit(
                    f"[refused] {label}: target {args[target_idx]} is not on USB now.")
                self._ui.toast.emit("warn", "Device gone",
                                    "The selected target is no longer connected.")
                return None, None, None
        if device_key is None:
            picked = self._pick_device(label, modes)
            if picked == "__cancelled__":
                self._ui.line.emit("[info] device choice cancelled.")
                return None, None, None
            device_key = picked
        if not device_key:
            self._ui.line.emit(f"[refused] {label}: no matching device detected.")
            self._ui.toast.emit("warn", "No device",
                                f"No {tag} device detected for this operation.")
            return None, None, None
        action_ids = _actions_mod.actions_for_command(cmd)
        ok, last = _actions_mod.check_actions(device_key, action_ids, bridge.validate_action)
        if not ok and action_ids and _actions_mod.is_transient_refusal(last):
            import time as _t
            self._ui.line.emit(
                f"[info] {label}: device temporarily unreadable "
                "(re-enumerating?) — settling 2.5s and retrying ...")
            _t.sleep(2.5)
            ok, last = _actions_mod.check_actions(device_key, action_ids, bridge.validate_action)
        if not ok:
            self._ui.line.emit(
                f"[refused] {label} is not valid for this device right now "
                f"({device_key}): {last}")
            self._ui.toast.emit("warn", "Unsupported for this device",
                                f"{label} cannot run on the selected device "
                                "in its current state. If the GUI shows it "
                                "connected, wait a moment and retry.")
            return None, None, None
        if not _flow_start(label, destructive=destructive, key=device_key):
            self._ui.status.emit("Busy: " + _flow_busy_msg(key=device_key))
            self._ui.toast.emit("warn", "Operation already running",
                                _flow_busy_msg(key=device_key))
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg(key=device_key)}")
            return None, None, None
        core.clear_cancel(key=device_key)
        bridge.clear_cancel(key=device_key)
        mode_txt = ", ".join(sorted(set(modes) if isinstance(modes, (set, list, tuple)) else [modes])) if modes else ""
        flux = jobs.start_job(device_key, label, mode_txt, cmd or "", action_ids or ())
        flux.set_state("VALIDATED")
        tgt = _devices.resolve_usb_target(device_key)
        if not tgt:
            # Same transient window as validation (serial unreadable for a
            # moment while re-enumerating): settle and retry once before
            # refusing. The lock is held, so this briefly blocks sibling
            # ops on the same device only — acceptable on a failure path.
            import time as _t
            self._ui.line.emit(
                f"[info] {label}: transport unreadable "
                "(re-enumerating?) — settling 2.5s and retrying ...")
            _t.sleep(2.5)
            tgt = _devices.resolve_usb_target(device_key)
        if not tgt:
            self._ui.line.emit(
                f"[refused] {label}: {device_key} left USB before start.")
            self._ui.toast.emit("warn", "Device gone",
                                "The device disconnected before the operation started. "
                                "If the GUI still shows it connected, wait a moment "
                                "and retry.")
            _flow_end(key=device_key)
            return None, None, None
        # Target↔identity binding: the frozen target must still belong to
        # the SAME device (Section-32: a replacement phone can occupy the
        # same bus:addr; open matches vid/pid/bus/addr, not the serial).
        # Zero-touch serial compare — a mismatch refuses with the exact
        # coaching; absence passes through (the worker's open reports it).
        serial_for_check = (device_key[4:]
                            if isinstance(device_key, str)
                            and device_key.startswith("adb:") else "")
        if serial_for_check:
            try:
                cur = bridge.verify_target(tgt, serial_for_check)
                if cur and cur != serial_for_check:
                    self._ui.line.emit(
                        f"[refused] {label}: device identity changed at "
                        f"{tgt} — it is now serial '{cur}', not "
                        f"'{serial_for_check}'. Replug the intended device "
                        "and retry.")
                    self._ui.toast.emit(
                        "warn", "Device replaced",
                        "The phone at that port is not the one the "
                        "operation was validated for.")
                    _flow_end(key=device_key)
                    return None, None, None
            except bridge.BridgeError as e:
                if "identity changed" in str(e).lower():
                    self._ui.line.emit(f"[refused] {label}: {e}")
                    self._ui.toast.emit(
                        "warn", "Device replaced",
                        "The phone at that port is not the one the "
                        "operation was validated for.")
                    _flow_end(key=device_key)
                    return None, None, None
                # Absent/other: the worker's open reports it; not fatal here.
        args = list(args)
        if len(args) > target_idx and args[target_idx] == "auto":
            args[target_idx] = tgt.split("@")[-1]
        if stop_btn is not None:
            try:
                self._stop_job[stop_btn] = flux.job_id
            except Exception:
                pass
        return device_key, flux, args

    def _adb_serial_for_key(self, device_key):
        """ADB serial for a device key, or None when it cannot be determined.

        `adb:` keys carry it directly; other keys resolve through the merged
        device rows (ADB leg first, then the row serial). None means the
        device cannot be safely targeted — callers must refuse, never fall
        back to first-authorized.
        """
        if isinstance(device_key, str) and device_key.startswith("adb:"):
            return device_key[4:] or None
        try:
            rows = _devices.candidates_for_modes({"ADB"})
        except Exception:
            return None
        for r in rows or []:
            if isinstance(r, dict) and r.get("key") == device_key:
                adb = r.get("adb") or {}
                return adb.get("serial") or r.get("serial") or None
        return None

    def _adb_ready_for_key(self, device_key=None, timeout=1.0):
        """Bounded, selected-device-only ADB authorization check.

        `adb_status()` can block for ~50s (3 x 15s attempts + sleeps) and was
        called on the GUI thread; it also accepted ANY authorized phone. This
        check:
          * resolves the serial for the SELECTED key only — an unresolvable
            key means "no authorized ADB", never a first-authorized fallback
            (so an unrelated phone can never satisfy the check);
          * uses the zero-touch presence listing (no USB claim/handshake);
          * probes in a daemon thread and waits at most ``timeout`` seconds,
            so the GUI blocks for no more than ~1s;
          * returns False when the probe is inconclusive, so callers take
            the non-ADB guidance path instead of guessing.
        """
        key = (device_key if device_key is not None
               else getattr(self, "_display_key", None))
        serial = self._adb_serial_for_key(key)
        if not serial:
            return False
        rows = []

        def probe():
            try:
                rows.extend(bridge.adb_presence_status())
            except Exception:
                pass

        worker = threading.Thread(target=probe, daemon=True)
        worker.start()
        worker.join(timeout)
        if worker.is_alive():
            # Inconclusive: the daemon probe finishes in the background; the
            # caller must fall back to guidance, not assume ADB.
            return False
        return any(
            isinstance(r, dict)
            and r.get("serial") == serial
            and r.get("state") == "device"
            for r in rows
        )

    def _adb_begin(self, label, method, device_key=None):
        """Shared prologue for ADB-mechanism tools (triage/battery/network).

        Picks an authorized device (dialog only when >1 candidate),
        resolves its ADB serial once, validates `adb_shell` against the
        backend, takes the per-device lock, clears scoped cancels and starts
        the FlashJob (VALIDATED). Workers must pass `serial=` to every
        `adb_shell` call so multi-step loops cannot hop phones mid-run.
        Returns (serial, device_key, flux) or (None, None, None).
        """
        from ..core import actions as _actions_mod

        if device_key is None:
            picked = self._pick_device(label, "ADB")
            if picked == "__cancelled__":
                self._ui.line.emit("[info] device choice cancelled.")
                return None, None, None
            device_key = picked
        if not device_key:
            # The merged pick scans USB descriptors, which flap; the ADB
            # daemon's rows are independent (TCP, zero USB) and stay
            # authoritative for ADB presence while the bus cycle drops the
            # descriptors. When exactly one authorized device exists, use
            # it instead of refusing — this is the "shows connected but
            # actions say no adb" gap. Multiple → ambiguous (refuse with
            # guidance); zero → genuine absence.
            try:
                auth = [d for d in bridge.adb_status()
                        if d.get("state") == "device"]
            except Exception:
                auth = []
            if len(auth) == 1:
                device_key = f"adb:{auth[0].get('serial', '')}"
                self._ui.line.emit(
                    f"[info] {label}: USB scan missed the device (re-"
                    f"enumerating) — using the ADB daemon row ({device_key})")
            elif len(auth) > 1:
                # Several authorized daemon rows: show the RUN picker over
                # them instead of refusing — run semantics ('Run on this
                # device' / 'Cancel'), not stop semantics.
                picked = self._pick_from_keys(
                    label, sorted(f"adb:{d.get('serial', '')}" for d in auth))
                if picked == "__cancelled__":
                    self._ui.line.emit("[info] device choice cancelled.")
                    return None, None, None
                device_key = picked
                self._ui.line.emit(
                    f"[info] {label}: USB scan missed (re-enumerating) — "
                    f"picked from the ADB daemon rows ({device_key})")
            else:
                self._ui.line.emit(
                    "[warn] No authorized ADB device found right now — enable USB "
                    "debugging and tap Allow. If the GUI shows the device as "
                    "connected, it may be re-enumerating: wait a moment and retry.")
                self._ui.toast.emit("warn", "No ADB device", "Connect + authorize the phone")
                return None, None, None
        serial = self._adb_serial_for_key(device_key)
        if not serial:
            self._ui.line.emit(
                f"[refused] {label}: cannot determine the ADB serial for {device_key}.")
            self._ui.toast.emit("warn", "Cannot target device",
                                "The selected device has no usable ADB serial.")
            return None, None, None
        # One retry on transient resolution failures: USB serials can be
        # unreadable for a moment while a device re-enumerates (marginal
        # links/cables), while the ADB daemon still reports it connected.
        # Retrying once after a short settle covers that window; a real
        # absence fails again with a clear message.
        ok, last = _actions_mod.check_actions(device_key, ["adb_shell"], bridge.validate_action)
        if not ok and _actions_mod.is_transient_refusal(last):
            import time as _t
            _t.sleep(2.5)
            ok, last = _actions_mod.check_actions(device_key, ["adb_shell"], bridge.validate_action)
        if not ok:
            self._ui.line.emit(
                f"[refused] {label} is not valid for this device right now "
                f"({device_key}): {last}")
            self._ui.toast.emit("warn", "Unsupported for this device",
                                f"{label} cannot run on the selected device "
                                "in its current state.")
            return None, None, None
        if not _flow_start(label, destructive=False, key=device_key):
            self._ui.status.emit("Busy: " + _flow_busy_msg(key=device_key))
            self._ui.toast.emit("warn", "Operation already running",
                                _flow_busy_msg(key=device_key))
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg(key=device_key)}")
            return None, None, None
        core.clear_cancel(key=device_key)
        bridge.clear_cancel(key=device_key)
        flux = jobs.start_job(device_key, label, "ADB", method, ["adb_shell"])
        flux.set_state("VALIDATED")
        return serial, device_key, flux

    def _mtk_run(self, args, timeout=600, device_key=None, on_done=None):
        """Run a bridge MTK command in a worker.

        ``on_done(out)`` (optional) runs in the worker after a successful
        return, so callers can report result details (e.g. a backup path)
        only once the flow really finished.
        """
        prep = self._chip_begin("MTK", args[0] if args else "",
                                {"MTK BROM", "MTK"}, args,
                                device_key=device_key,
                                stop_btn=self.mtk_stop_btn)
        if prep[0] is None:
            return
        device_key, flux, args = prep

        def work():
            dev_tag = f"[{device_key}] "
            if flux:
                flux.set_state("RUNNING")

            def emit(line):
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            try:
                with _devices.device_scope(device_key):
                    out = bridge._run(args, timeout=timeout)
                emit(out or "(no output)")
                if on_done is not None:
                    try:
                        on_done(out or "")
                    except Exception:
                        pass
                self._ui.status.emit(f"MTK: {args[0]} done")
                self._ui.toast.emit("ok", f"MTK {args[0]}", "Completed successfully")
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except bridge.BridgeCancelled:
                emit("[cancelled] MTK operation stopped by user")
                self._ui.status.emit("MTK: operation cancelled")
                self._ui.toast.emit("warn", "MTK operation", "Cancelled")
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", "cancelled by user", "CANCELLED")
            except bridge.BridgeError as e:
                emit(f"[error] MTK {args[0]}: {e}")
                self._ui.status.emit(f"MTK: {args[0]} failed")
                self._ui.toast.emit("error", f"MTK {args[0]}", str(e))
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                _flow_end(key=device_key)
                try:
                    if flux and self._stop_job.get(self.mtk_stop_btn) == flux.job_id:
                        self._stop_job.pop(self.mtk_stop_btn, None)
                except Exception:
                    pass
                self._ui.ui.emit(self._mtk_reset_ui)

        self.mtk_stop_btn.setEnabled(True)
        self.mtk_progress.setVisible(True)
        self.mtk_progress.setValue(150)
        threading.Thread(target=work, daemon=True).start()

    def _mtk_reset_ui(self):
        self.mtk_stop_btn.setEnabled(False)
        self.mtk_progress.setValue(1000)
        QTimer.singleShot(400, lambda: self.mtk_progress.setVisible(False))

    def _stop_active_job(self, stop_btn, tag):
        """Per-device STOP for a chip page's stop button.

        When the button is mapped to a live FlashJob (started from that
        page), cancel exactly that job's device — other devices keep
        running. Returns True when a job was stopped. Returns False (caller
        falls back to legacy broadcast) when no live job is mapped.
        """
        try:
            job_id = self._stop_job.get(stop_btn)
        except Exception:
            job_id = None
        if job_id:
            job = jobs.get_job(job_id)
            if job is not None and job.is_active:
                jobs.cancel_job(job_id)
                self._ui.status.emit(f"{tag}: stopping {job.device_key} ...")
                self._ui.line.emit(
                    f"[warn] {tag}: stop requested for {job.device_key} "
                    f"(job {job_id}) — other devices keep running ...")
                return True
            try:
                self._stop_job.pop(stop_btn, None)
            except Exception:
                pass
        return False

    def _mtk_stop(self):
        if self._stop_active_job(self.mtk_stop_btn, "MTK"):
            return
        bridge.request_cancel()
        core.request_cancel()
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
                    product = d.get("product")
                    manufacturer = d.get("manufacturer")
                    serial = d.get("serial")
                    chip = d.get("chip")
                    # Build detailed device info line for console
                    parts = [f"MTK: 0e8d:{pid:04x} bus={d.get('bus')} addr={d.get('address')} - {name}"]
                    if manufacturer:
                        parts.append(f"mfr={manufacturer}")
                    if product:
                        parts.append(f"prod={product}")
                    if serial:
                        parts.append(f"sn={serial}")
                    if chip:
                        hw = chip.get("hw_code")
                        hw_sub = chip.get("hw_sub_code")
                        ca = chip.get("chip_name")
                        parts.append(f"chip={ca or f'0x{hw:04X}' if hw else 'unknown'}")
                    self._ui.line.emit(" | ".join(parts))
                
                # Update status label with first device's product name if available
                first = devs[0]
                product = first.get("product")
                manufacturer = first.get("manufacturer")
                pid = first.get("pid")
                stage = mtk.pid_stage(pid)
                st_name, _ = mtk.stage_label(stage)
                
                if product and manufacturer:
                    status = f"{manufacturer} {product} ({st_name})"
                elif product:
                    status = f"{product} ({st_name})"
                elif manufacturer:
                    status = f"{manufacturer} ({st_name})"
                else:
                    status = f"MediaTek 0e8d:{pid:04x} ({st_name})"
                
                if len(devs) > 1:
                    status += f" +{len(devs)-1} more"
                
                self._ui.ui.emit(lambda s=status: self.mtk_status.setText(s))
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
        if not bridge.BRIDGE.exists():
            self._toasts.show_error(
                "Bridge missing",
                "flashpilot-bridge not built - run `cargo build --release` "
                "(Settings ▸ Tools ▸ Rebuild bridge).")
            return
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
            beat = 0.0
            crash_cd = 0.0
            os.environ["MTK_PRELOADER_OUT"] = out
            try:
                while _time.monotonic() < deadline:
                    if core.cancel_requested():
                        self._ui.line.emit("[cancelled] MTK preloader dump stopped")
                        return
                    devs = mtk.find_mtk()
                    if _time.monotonic() - beat >= 5.0:
                        beat = _time.monotonic()
                        stages = [mtk.stage_label(mtk.pid_stage(x.get("pid", 0)))[0]
                                  for x in devs] or ["none"]
                        try:
                            vids = sorted({hex(x.get("vid", 0))
                                           for x in bridge.detect_all()})
                        except Exception:
                            vids = []
                        self._ui.line.emit(
                            f"[wait] polling BROM/preloader - MTK devices: "
                            f"{len(devs)} ({', '.join(stages)}) | bus VIDs: "
                            f"{', '.join(vids) or 'none'} - power phone OFF, "
                            f"then plug USB")
                    d = None
                    stage = None
                    for x in devs:
                        st = mtk.pid_stage(x.get("pid", 0))
                        if st in ("brom", "preloader"):
                            d = x
                            stage = st
                            break
                    if not d:
                        _time.sleep(0.7)
                        continue

                    # PRELOADER-held (0x2000): fire crash-to-BROM, then keep
                    # polling for the true BROM window instead of wasting a
                    # kamakiri attempt on a port that cannot handshake.
                    if stage == "preloader":
                        tgt2000 = f"{d.get('bus')}:{d.get('address')}"
                        if _time.monotonic() >= crash_cd:
                            crash_cd = _time.monotonic() + 6.0
                            self._ui.line.emit(
                                f"  preloader 0e8d:2000 caught - sending "
                                f"crash-to-BROM ({tgt2000}) ...")
                            try:
                                res = bridge._run(
                                    ["mtk-crash-brom", tgt2000], timeout=25)
                                self._ui.line.emit(res)
                            except Exception as e:  # noqa: BLE001
                                self._ui.line.emit(f"  crash send failed: {e}")
                        _time.sleep(1.2)
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
                    except Exception as e:  # noqa: BLE001
                        self._ui.line.emit(
                            f"  attempt {attempt} failed ({e}) - waiting for "
                            "the next BROM window ..."
                        )
                        _time.sleep(1)
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

    @property
    def mtk_files(self):
        """Compatibility view over the MTK page inputs (da/scatter edits)."""
        return {
            "da": getattr(self, "mtk_da_edit", None) or QLineEdit(),
            "scatter": getattr(self, "mtk_scatter_edit", None) or QLineEdit(),
        }

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
                mtk_usb = mtk.find_mtk()
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
        scatter = self.mtk_scatter_edit.text().strip()
        da = self.mtk_da_edit.text().strip()
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
        # Firmware↔device model match (cautious gate): the firmware
        # directory/file name usually carries the model (SM-A145F_...,
        # KG6-...). When the displayed device's model is known (ADB
        # getprops) and PROVABLY differs, block unless explicitly
        # overridden — wrong-model firmware may not boot. Unverifiable
        # (no model in the name / device) passes with a note.
        try:
            import glob as _g
            fw_name = next((os.path.basename(p) for p in sorted(_g.glob(os.path.join(fw, "*.tar.md5")) + _g.glob(os.path.join(fw, "*.tar")) + _g.glob(os.path.join(fw, "*.img")))), "")
            fw_model = core._model_from_firmware_name(fw_name) if fw_name else ""
            dev_model = (self._cached_model or "").strip()
            if fw_model and dev_model:
                match = core._models_match(dev_model, fw_model)
                if match is False and os.environ.get("MTK_FORCE_MODEL", "0") != "1":
                    self._toasts.show_error(
                        "Firmware model mismatch",
                        f"Firmware is for '{fw_model}' but the device is "
                        f"'{dev_model}'. Set MTK_FORCE_MODEL=1 to override.")
                    self._ui.line.emit(
                        f"[refused] MTK flash: firmware model '{fw_model}' "
                        f"!= device model '{dev_model}' — refusing "
                        "(MTK_FORCE_MODEL=1 overrides).")
                    return
        except Exception:
            pass
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

    def _mtk_check_scatter(self):
        files = self._mtk_require_files()
        if not files:
            return
        scatter, da = files
        fw = self.mtk_fw_dir.text().strip()
        if not fw:
            self._toasts.show_warn("Firmware dir missing", "Select the firmware directory")
            return
        self._ui.line.emit(f"[step] MTK checking scatter: scatter={scatter} fw={fw}")
        self._mtk_run(["mtk-check-scatter", "auto", da, scatter, fw], timeout=300)

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
            self._ui.line.emit("[step] Clearing frp/nvdata...")
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
        da = self.mtk_da_edit.text().strip()
        if not da:
            # Bundled-DA path: FRP removal for ANY MediaTek device via BROM
            # with no user-supplied DA (the mtkclient V5/V6 containers are
            # parsed natively and the per-chip DA is picked by dacode).
            da_dir = bridge.bundled_mtk_da_dir()
            if not da_dir:
                self._ui.line.emit("[warn] MTK: no DA selected and no bundled DA containers found")
                self._toasts.show_warn(
                    "MTK files missing",
                    "Select a DA binary (no bundled containers in root/tools/mtk)")
                return
            self._ui.line.emit("[step] MTK FRP bypass (BROM, bundled DA — any MTK device)")
            self._confirm_overlay(
                "FRP Bypass (Bundled DA — any MTK)",
                "Boot the bundled mtkclient DA over BROM and clear lock / FRP\n"
                "partitions by NAME from the device GPT — no DA file needed.\n\n"
                "Picks the per-chip DA automatically. On SBC/SLA/DAA-protected\n"
                "BROMs the kamakiri2 exploit runs first.\n"
                "This formats or zero-fills frp, nvdata, metadata, persistent,\n"
                "protect1/2, and keystore partitions where present.\n"
                "User data may be erased. Continue?",
                confirm_label="Clear FRP",
                on_confirm=lambda: self._mtk_run(
                    ["mtk-frp-brom", "auto", da_dir], timeout=1800),
            )
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
        da = self.mtk_da_edit.text().strip()
        if not da:
            self._ui.line.emit("[warn] MTK: DA binary is required")
            self._toasts.show_warn("MTK files missing", "Select a DA binary")
            return
        self._ui.line.emit(f"[step] MTK list partitions: da={da}")
        self._mtk_run(["mtk-gpt", "auto", da], timeout=300)

    def _mtk_flash_part(self):
        da = self.mtk_da_edit.text().strip()
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
            "Reboot", "FASTBOOT", method, label,
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

    def _qc_run(self, args, timeout=600, device_key=None, on_done=None):
        """Run a bridge Qualcomm command in a worker.

        ``on_done(out)`` (optional) runs in the worker after a successful
        return, so callers can report result details (e.g. a backup path)
        only once the flow really finished.
        """
        prep = self._chip_begin("Qualcomm", args[0] if args else "",
                                {"EDL"}, args,
                                device_key=device_key,
                                stop_btn=self.qc_stop_btn)
        if prep[0] is None:
            return
        device_key, flux, args = prep

        def work():
            dev_tag = f"[{device_key}] "
            if flux:
                flux.set_state("RUNNING")

            def emit(line):
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            try:
                with _devices.device_scope(device_key):
                    out = bridge._run(args, timeout=timeout)
                emit(out or "(no output)")
                if on_done is not None:
                    try:
                        on_done(out or "")
                    except Exception:
                        pass
                self._ui.status.emit(f"Qualcomm: {args[0]} done")
                self._ui.toast.emit("ok", f"Qualcomm {args[0]}", "Completed successfully")
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except bridge.BridgeCancelled:
                emit("[cancelled] Qualcomm operation stopped by user")
                self._ui.status.emit("Qualcomm: operation cancelled")
                self._ui.toast.emit("warn", "Qualcomm operation", "Cancelled")
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", "cancelled by user", "CANCELLED")
            except bridge.BridgeError as e:
                emit(f"[error] Qualcomm {args[0]}: {e}")
                self._ui.status.emit(f"Qualcomm: {args[0]} failed")
                self._ui.toast.emit("error", f"Qualcomm {args[0]}", str(e))
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                _flow_end(key=device_key)
                try:
                    if flux and self._stop_job.get(self.qc_stop_btn) == flux.job_id:
                        self._stop_job.pop(self.qc_stop_btn, None)
                except Exception:
                    pass
                self._ui.ui.emit(self._qc_reset_ui)

        self.qc_stop_btn.setEnabled(True)
        self.qc_progress.setVisible(True)
        self.qc_progress.setValue(150)
        threading.Thread(target=work, daemon=True).start()

    def _qc_reset_ui(self):
        self.qc_stop_btn.setEnabled(False)
        self.qc_progress.setValue(1000)
        QTimer.singleShot(400, lambda: self.qc_progress.setVisible(False))

    def _qc_stop(self):
        if self._stop_active_job(self.qc_stop_btn, "Qualcomm"):
            return
        bridge.request_cancel()
        core.request_cancel()
        self._ui.status.emit("Qualcomm: stopping ...")
        self._ui.line.emit("[warn] Qualcomm: stop requested, killing bridge ...")

    def _qc_adb(self, device_key=None):
        """Best-effort ADB enable for a Qualcomm device that is booted to
        Android (or recovery) and reachable over adb. EDL-mode devices can't
        enable ADB directly - tell the user so."""
        prep = self._adb_begin("Enable ADB", "qc_adb_enable", device_key)
        if prep[0] is None:
            return
        serial, device_key, flux = prep

        def work():
            if flux:
                flux.set_state("RUNNING")

            def emit(line):
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            try:
                emit(f"[step] Enabling ADB on {serial} ...")
                for cmd in (
                    "setprop persist.sys.usb.config adb",
                    "setprop sys.usb.config adb",
                    "settings put global adb_enabled 1",
                    "svc usb setFunctions adb",
                ):
                    try:
                        out = bridge.adb_shell(cmd, timeout=10, serial=serial, rescue=False)
                        if out:
                            emit(f"  {cmd} -> {out[:120]}")
                        else:
                            emit(f"  {cmd} -> ok")
                    except bridge.BridgeError as e:
                        emit(f"[warn] {cmd}: {e}")
                emit("[ok] ADB enable commands sent")
                self._ui.toast.emit("ok", "Enable ADB", "Commands sent to device")
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except bridge.BridgeCancelled as e:
                emit(f"[cancelled] Enable ADB stopped by user ({e})")
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", str(e), "CANCELLED")
            except Exception as e:  # noqa: BLE001
                emit(f"[error] Enable ADB: {e}")
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                _flow_end(key=device_key)

        threading.Thread(target=work, daemon=True).start()

    def _qc_detect(self):
        self.qc_status.setText("Scanning USB...")

        def work():
            try:
                out = bridge._run(["qcom-detect"])
                txt = (out or "").strip()
                if not txt or txt in ("[]", "{}", "null"):
                    txt = "No Qualcomm device — no 05c6 over USB (any 05c6: EDL 9008/900E/6000/modem) or Qualcomm chip via ADB (qcom/msm) — enter EDL (power off, Vol Up+Down, plug) or connect Qualcomm in normal MTP/ADB"
                self._ui.ui.emit(lambda s=txt: self.qc_status.setText(s))
                self._ui.line.emit(f"[info] {out}")
            except bridge.BridgeError as e:
                self._ui.ui.emit(lambda err=e: self.qc_status.setText(
                    f"Scan error: {err}"))
                self._ui.line.emit(f"[error] qcom-detect: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _qc_board_key(self):
        """The key of the device selected on the Devices page (or None).

        `_display_key` is the row the user picked; passing None is safe —
        `_chip_begin` asks instead of guessing a target.
        """
        return getattr(self, "_display_key", None)

    def _qc_bundled_dir(self, label):
        """Log where the bundled programmers live; never block on it.

        `auto` is resolved by the bridge by SoC index and the resolver also
        honours FLASHPILOT_QCOM_PAYLOADS, so a missing bundle only means the
        environment has to provide the programmers.
        """
        try:
            qdir = bridge.bundled_qcom_dir() or ""
        except Exception:
            qdir = ""
        if qdir:
            self.log_line(
                f"[step] {label}: bundled Qualcomm programmers: {qdir}")
        else:
            self.log_line(
                f"[info] {label}: no bundled Qualcomm programmers "
                "(payloads/qcom) — the bridge resolves them from "
                "FLASHPILOT_QCOM_PAYLOADS or an explicit --programmer path")
        return qdir

    def _qc_frp_choice(self, label):
        """Ask how much to erase over EDL: "frp", "wipe", or None (cancel)."""
        box = QMessageBox(self)
        box.setWindowTitle(f"{label} · FRP (EDL 9008)")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(
            "Qualcomm FRP over EDL 9008 (Sahara + Firehose).\n\n"
            "The phone must be in EDL mode (9008): power it off, hold "
            "Vol Up + Vol Down and plug USB.\n\n"
            "How much should be erased?")
        only = box.addButton("Erase FRP only",
                             QMessageBox.ButtonRole.AcceptRole)
        wipe = box.addButton("Erase FRP + wipe data",
                             QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(only)
        box.exec()
        clicked = box.clickedButton()
        if clicked is only:
            return "frp"
        if clicked is wipe:
            return "wipe"
        return None

    def _qc_board_frp(self, label):
        """FRP over EDL 9008: erase FRP (optionally with user data)."""
        choice = self._qc_frp_choice(label)
        if not choice:
            self.log_line(f"[info] {label}: FRP (EDL) cancelled")
            return
        wipe = choice == "wipe"
        argv = ["qcom-frp-reset", "auto"]
        if wipe:
            argv.append("--wipe-data")
        key = self._qc_board_key()
        self._qc_bundled_dir(label)
        self._confirm_overlay(
            f"{label} · Remove FRP",
            "Erase Factory Reset Protection over EDL 9008?\n\n"
            "The phone must already be in EDL mode (9008).\n"
            "This deletes the FRP/lock data on the device.\n"
            + ("This variant ALSO ERASES USER DATA (a factory reset).\n\n"
               if wipe else "\n")
            + "Continue?",
            confirm_label="Erase FRP + Data" if wipe else "Erase FRP",
            on_confirm=lambda a=argv, k=key: self._qc_run(
                a, timeout=600, device_key=k),
            chip="wipe" if wipe else "frp",
        )

    def _qc_board_backup(self, label):
        """Back up the device partitions over EDL 9008 to a picked folder."""
        out_dir = QFileDialog.getExistingDirectory(
            self, "Qualcomm backup output folder", "/tmp/qcom_backup")
        if not out_dir:
            self.log_line(f"[info] {label}: backup cancelled")
            return
        key = self._qc_board_key()
        self._qc_bundled_dir(label)

        def done(_out):
            # Report the destination only once the bridge run has returned.
            self.log_line(f"[backup] {label}: backup written to {out_dir}")

        self._confirm_overlay(
            f"{label} · Backup Partitions",
            f"Read the device partitions over EDL 9008 (Firehose) and write\n"
            f"a backup to:\n{out_dir}\n\n"
            "Read-only on the phone. The firehose programmer is picked by "
            "SoC from the bundle. Continue?",
            confirm_label="Backup",
            on_confirm=lambda o=out_dir, k=key: self._qc_run(
                ["qcom-backup", "auto", o], timeout=1800,
                device_key=k, on_done=done),
            chip="qcom",
        )

    def _qc_board_flash(self, label):
        """Flash a rawprogram XML + firmware folder over EDL 9008."""
        folder = QFileDialog.getExistingDirectory(
            self, "Qualcomm firmware folder",
            self.settings.value("default_dir",
                                os.path.expanduser("~/Downloads")))
        if not folder:
            self.log_line(f"[info] {label}: flash cancelled")
            return
        try:
            xmls = sorted(
                e.name for e in os.scandir(folder)
                if e.is_file()
                and e.name.lower().startswith("rawprogram")
                and e.name.lower().endswith(".xml"))
        except OSError as e:
            self._toasts.show_error(f"{label} · Flash",
                                    f"Cannot read {folder}: {e}")
            return
        if not xmls:
            self._toasts.show_error(
                f"{label} · Flash",
                f"No rawprogram*.xml in {folder}. A Qualcomm EDL flash needs "
                "the rawprogram XML that ships with the firmware.")
            return
        if len(xmls) == 1:
            xml = os.path.join(folder, xmls[0])
        else:
            picked, _filt = QFileDialog.getOpenFileName(
                self, "Select the rawprogram XML to flash", folder,
                "rawprogram XML (rawprogram*.xml);;XML (*.xml)")
            if not picked:
                self.log_line(f"[info] {label}: flash cancelled")
                return
            if os.path.basename(picked) not in xmls:
                self._toasts.show_error(
                    f"{label} · Flash",
                    f"{os.path.basename(picked)} is not one of the rawprogram "
                    f"XMLs in {folder}: " + ", ".join(xmls))
                return
            xml = picked
        key = self._qc_board_key()
        self._qc_bundled_dir(label)
        self._confirm_overlay(
            f"{label} · Flash Firmware",
            f"Flash {os.path.basename(xml)} from:\n{folder}\n\n"
            "qcom-flash writes every partition listed in the XML over EDL "
            "9008 (Firehose) and OVERWRITES the matching partitions. A wrong "
            "XML, mismatched firmware or an interrupted cable can leave the "
            "phone unbootable.\n\nContinue?",
            confirm_label="Flash Firmware",
            on_confirm=lambda x=xml, f=folder, k=key: self._qc_run(
                ["qcom-flash", "auto", x, f], timeout=1800, device_key=k),
            chip="flash",
        )

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

    def _qc_info(self, device_key=None):
        prep = self._chip_begin("Qualcomm", "qcom-info", {"EDL"},
                                ["qcom-info", "auto"],
                                device_key=device_key,
                                stop_btn=self.qc_stop_btn,
                                destructive=False)
        if prep[0] is None:
            return
        device_key, flux, resolved = prep
        tgt = resolved[1]
        self.qc_progress.setVisible(True)
        self.qc_progress.setValue(150)

        def work():
            if flux:
                flux.set_state("RUNNING")

            def emit(line):
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            lines = []
            try:
                with _devices.device_scope(device_key):
                    rows = device_pages.connected_rows()
                    qcom = [r for r in rows
                            if str(r.get("mode", "")).startswith("qualcomm")]
                    if qcom:
                        lines.append("=== Qualcomm USB Device(s) ===")
                        for r in qcom:
                            lines.extend(_fmt_usb_full(r))
                            if (r.get("mode") or "") == "qualcomm-edl":
                                lines.append("  -> EDL mode (Sahara/firehose capable)")
                            else:
                                lines.append("  -> normal/modem mode (not in EDL)")
                            lines.append("")
                    else:
                        lines.append("No Qualcomm device connected over USB")
                        lines.append("")

                    out = bridge._run(["qcom-info", tgt], timeout=120)
                lines.append("--- Sahara device info ---")
                lines.append(out or "(Sahara handshake not available - device not in EDL)")
                emit("\n".join(lines))
                self._ui.status.emit("Qualcomm: device info complete")
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except bridge.BridgeCancelled:
                emit("[cancelled] Qualcomm info stopped by user")
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", "cancelled by user", "CANCELLED")
            except bridge.BridgeError as e:
                lines.append("--- Sahara device info ---")
                lines.append(f"(Sahara handshake failed: {e})")
                emit("\n".join(lines))
                self._ui.status.emit("Qualcomm: info partial")
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                _flow_end(key=device_key)
                try:
                    if flux and self._stop_job.get(self.qc_stop_btn) == flux.job_id:
                        self._stop_job.pop(self.qc_stop_btn, None)
                except Exception:
                    pass
                self._ui.ui.emit(self._qc_reset_ui)

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
                "Flash Firmware", "Download mode", method, label
            ),
        )

    def _confirm_overlay(self, title, text, confirm_label, on_confirm, chip=None):
        """Big centered confirmation — same UX as beta/update dialogs (620px,
        draggable, high-contrast, X to close). Color is chip-based so flashing
        vs high-risk operations are instantly distinguishable."""
        # Chip → pill + gradient (base on chip)
        chip_map = {
            "mtk": ("MTK", ("#f59e0b", "#ea580c")),
            "mediatek": ("MTK", ("#f59e0b", "#ea580c")),
            "qualcomm": ("QUALCOMM", ("#dc2626", "#f97316")),
            "qcom": ("QUALCOMM", ("#dc2626", "#f97316")),
            "edl": ("QUALCOMM", ("#dc2626", "#f97316")),
            "firehose": ("QUALCOMM", ("#dc2626", "#f97316")),
            "spd": ("SPD", ("#8b5cf6", "#a78bfa")),
            "unisoc": ("SPD", ("#8b5cf6", "#a78bfa")),
            "spreadtrum": ("SPD", ("#8b5cf6", "#a78bfa")),
            "frp": ("FRP", ("#ef4444", "#f97316")),
            "mdm": ("MDM", ("#ef4444", "#f97316")),
            "wipe": ("WIPE", ("#ef4444", "#dc2626")),
            "nvram": ("NVRAM", ("#8b5cf6", "#ec4899")),
            "lock": ("LOCK", ("#f59e0b", "#ef4444")),
            "samsung": ("SAMSUNG", ("#0ea5e9", "#22d3ee")),
            "odin": ("SAMSUNG", ("#0ea5e9", "#22d3ee")),
            "flash": ("FLASH", ("#0ea5e9", "#22d3ee")),
        }
        detected_chip = chip or ""
        if not detected_chip:
            low = f"{title} {text} {confirm_label}".lower()
            for k in chip_map:
                if k in low:
                    detected_chip = k
                    break
            if not detected_chip:
                # Heuristic: flashing / risk keywords
                if "flash" in low or "odin" in low:
                    detected_chip = "samsung"
                elif "frp" in low or "mdm" in low or "erase" in low or "wipe" in low:
                    detected_chip = "frp"
                else:
                    detected_chip = "flash"
        pill_text, grad = chip_map.get(detected_chip, ("FLASH", ("#0ea5e9", "#22d3ee")))
        accent = grad[0]

        overlay = QFrame(self._root)
        overlay.setObjectName("confirmOverlay")
        overlay.setStyleSheet("QFrame#confirmOverlay { background: rgba(4, 9, 18, 215); border-radius: 18px; }")
        overlay.setGeometry(0, 0, self._root.width(), self._root.height())

        card = QFrame(overlay)
        card.setObjectName("confirmCard")
        card.setFixedWidth(620)
        card.setMinimumHeight(300)
        card.setStyleSheet(
            f"QFrame#confirmCard {{ background: {C['card']}; border: 1px solid {accent}; border-top: 2px solid {accent}; border-radius: 16px; }}"
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(42)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 220))
        card.setGraphicsEffect(shadow)
        card._drag_pos = None  # type: ignore

        v = QVBoxLayout(card)
        v.setContentsMargins(26, 18, 26, 20)
        v.setSpacing(14)

        # Header with pill + title + X (draggable)
        hdr_wrap = QFrame()
        hdr_wrap.setStyleSheet("background: transparent;")
        hdr = QHBoxLayout(hdr_wrap)
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(10)
        pill = QLabel(f" {pill_text} ")
        pill.setStyleSheet(
            f"color: #ffffff; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {grad[0]}, stop:1 {grad[1]});"
            " border-radius: 7px; padding: 4px 12px; font-size: 11px; font-weight: 900; letter-spacing: 1px;"
        )
        pill.setFixedHeight(24)
        hdr.addWidget(pill, 0, Qt.AlignmentFlag.AlignVCenter)
        t = QLabel(title)
        t.setStyleSheet("color: #f8fafc; font-size: 15px; font-weight: 800;")
        t.setWordWrap(True)
        hdr.addWidget(t, 1)
        x_btn = QPushButton("✕")
        x_btn.setFixedSize(28, 28)
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.setStyleSheet(
            "QPushButton { color: #cbd5e1; background: rgba(255,255,255,8); border: 1px solid rgba(255,255,255,12); border-radius: 14px; font-size: 13px; font-weight: 700; }"
            "QPushButton:hover { background: #334155; color: #ffffff; }"
        )
        x_btn.setToolTip("Close")
        hdr.addWidget(x_btn, 0, Qt.AlignmentFlag.AlignTop)
        v.addWidget(hdr_wrap)

        # Draggable header
        def _start_drag(e):
            if e.button() == Qt.MouseButton.LeftButton:
                card._drag_pos = e.globalPosition().toPoint() - card.pos()  # type: ignore

        def _do_drag(e):
            if getattr(card, "_drag_pos", None) is not None and e.buttons() & Qt.MouseButton.LeftButton:
                np = e.globalPosition().toPoint() - card._drag_pos  # type: ignore
                np.setX(max(0, min(np.x(), overlay.width() - card.width())))
                np.setY(max(0, min(np.y(), overlay.height() - card.height())))
                card.move(np)

        def _end_drag(e):
            card._drag_pos = None  # type: ignore

        for wdg in (hdr_wrap, t, pill):
            wdg.setCursor(Qt.CursorShape.OpenHandCursor)
            wdg.mousePressEvent = _start_drag  # type: ignore
            wdg.mouseMoveEvent = _do_drag  # type: ignore
            wdg.mouseReleaseEvent = _end_drag  # type: ignore

        m = QLabel(text)
        m.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: 500; line-height: 145%;")
        m.setWordWrap(True)
        m.setTextFormat(Qt.TextFormat.PlainText)
        v.addWidget(m)

        btns = QHBoxLayout()
        btns.setSpacing(12)

        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(_btn_ghost())
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setFixedWidth(120)

        ok = QPushButton(confirm_label)
        # Chip-colored confirm button (high-risk = red/orange, flash = blue)
        ok.setStyleSheet(
            f"QPushButton {{ color: #ffffff; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {grad[0]}, stop:1 {grad[1]});"
            " border: none; border-radius: 9px; padding: 10px 18px; font-weight: 900; font-size: 13px; }"
            f"QPushButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {grad[1]}, stop:1 {grad[0]}); }}"
        )
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setFixedWidth(180)
        ok.setFocus()

        def close():
            overlay.hide()
            overlay.deleteLater()

        cancel.clicked.connect(close)
        x_btn.clicked.connect(close)
        ok.clicked.connect(lambda: (close(), on_confirm()))
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        v.addLayout(btns)

        def center():
            card.adjustSize()
            max_h = overlay.height() - 32
            if card.height() > max_h:
                card.setFixedHeight(max_h)
            card.move((overlay.width() - card.width()) // 2, (overlay.height() - card.height()) // 2)

        def on_resize(e):
            QFrame.resizeEvent(overlay, e)
            center()

        overlay.resizeEvent = on_resize  # type: ignore
        center()
        overlay.show()
        overlay.raise_()
        ok.setFocus()

    def _confirm_experimental_overlay(self, feature, title, text, method_key,
                                      confirm_label, on_confirm, chip="wipe"):
        """EXPERIMENTAL gate (Q2-B): every run requires an ownership checkbox.

        The OK button stays disabled until the user checks the ownership box.
        For ``_EXPERIMENTAL_TYPE_CONFIRM`` keys (IMEI change) the user must ALSO
        type the required phrase before OK enables. Audit is logged on show /
        cancel / confirm regardless of the per-version ack (which is NOT used
        to auto-enable — the checkbox is always required)."""
        grad = ("#f59e0b", "#fbbf24")
        accent = grad[0]

        overlay = QFrame(self._root)
        overlay.setObjectName("confirmOverlay")
        overlay.setStyleSheet("QFrame#confirmOverlay { background: rgba(4, 9, 18, 215); border-radius: 18px; }")
        overlay.setGeometry(0, 0, self._root.width(), self._root.height())

        card = QFrame(overlay)
        card.setObjectName("confirmCard")
        card.setFixedWidth(620)
        card.setMinimumHeight(380)
        card.setStyleSheet(
            f"QFrame#confirmCard {{ background: {C['card']}; border: 1px solid {accent}; border-top: 2px solid {accent}; border-radius: 16px; }}"
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(42)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 220))
        card.setGraphicsEffect(shadow)
        card._drag_pos = None  # type: ignore

        v = QVBoxLayout(card)
        v.setContentsMargins(26, 18, 26, 20)
        v.setSpacing(14)

        hdr_wrap = QFrame()
        hdr_wrap.setStyleSheet("background: transparent;")
        hdr = QHBoxLayout(hdr_wrap)
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(10)
        pill = QLabel(" EXPERIMENTAL ")
        pill.setStyleSheet(
            f"color: #04121a; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {grad[0]}, stop:1 {grad[1]});"
            " border-radius: 7px; padding: 4px 12px; font-size: 11px; font-weight: 900; letter-spacing: 1px;"
        )
        pill.setFixedHeight(24)
        hdr.addWidget(pill, 0, Qt.AlignmentFlag.AlignVCenter)
        t = QLabel(title)
        t.setStyleSheet("color: #f8fafc; font-size: 15px; font-weight: 800;")
        t.setWordWrap(True)
        hdr.addWidget(t, 1)
        x_btn = QPushButton("✕")
        x_btn.setFixedSize(28, 28)
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.setStyleSheet(
            "QPushButton { color: #cbd5e1; background: rgba(255,255,255,8); border: 1px solid rgba(255,255,255,12); border-radius: 14px; font-size: 13px; font-weight: 700; }"
            "QPushButton:hover { background: #334155; color: #ffffff; }"
        )
        x_btn.setToolTip("Close")
        hdr.addWidget(x_btn, 0, Qt.AlignmentFlag.AlignTop)
        v.addWidget(hdr_wrap)

        def _start_drag(e):
            if e.button() == Qt.MouseButton.LeftButton:
                card._drag_pos = e.globalPosition().toPoint() - card.pos()  # type: ignore

        def _do_drag(e):
            if getattr(card, "_drag_pos", None) is not None and e.buttons() & Qt.MouseButton.LeftButton:
                np = e.globalPosition().toPoint() - card._drag_pos  # type: ignore
                np.setX(max(0, min(np.x(), overlay.width() - card.width())))
                np.setY(max(0, min(np.y(), overlay.height() - card.height())))
                card.move(np)

        def _end_drag(e):
            card._drag_pos = None  # type: ignore

        for wdg in (hdr_wrap, t, pill):
            wdg.setCursor(Qt.CursorShape.OpenHandCursor)
            wdg.mousePressEvent = _start_drag  # type: ignore
            wdg.mouseMoveEvent = _do_drag  # type: ignore
            wdg.mouseReleaseEvent = _end_drag  # type: ignore

        v.addWidget(_experimental_banner(
            "EXPERIMENTAL — Educational purpose only. You certify you own this device "
            "and accept all brick/warranty/legal risk."))

        m = QLabel(text)
        m.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: 500; line-height: 145%;")
        m.setWordWrap(True)
        m.setTextFormat(Qt.TextFormat.PlainText)
        v.addWidget(m)

        # Mandatory ownership checkbox — required EVERY run.
        cb = QCheckBox(
            "I own this device, understand this is EXPERIMENTAL and educational "
            "purpose only, and I accept all risk."
        )
        cb.setStyleSheet(
            "QCheckBox { color: #fde68a; font-size: 12px; font-weight: 700; spacing: 10px; }"
            "QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #f59e0b; border-radius: 5px; background: #0f172a; }"
            "QCheckBox::indicator:checked { background: #f59e0b; border-color: #f59e0b; }"
        )
        v.addWidget(cb)

        # Optional stronger "type to confirm" field for IMEI change.
        required_phrase = _EXPERIMENTAL_TYPE_CONFIRM.get(method_key, "")
        type_edit = None
        if required_phrase:
            te = QLineEdit()
            te.setPlaceholderText(f"Type “{required_phrase}” to enable")
            te.setStyleSheet(
                f"QLineEdit {{ background:{C['inset']}; border:1px solid {C['border']}; "
                "border-radius:8px; padding:6px 10px; color:#f8fafc; }}"
            )
            v.addWidget(te)
            type_edit = te

        btns = QHBoxLayout()
        btns.setSpacing(12)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(_btn_ghost())
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setFixedWidth(120)

        ok = QPushButton(confirm_label)
        ok.setStyleSheet(
            f"QPushButton {{ color: #04121a; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {grad[0]}, stop:1 {grad[1]});"
            " border: none; border-radius: 9px; padding: 10px 18px; font-weight: 900; font-size: 13px; }"
            f"QPushButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {grad[1]}, stop:1 {grad[0]}); }}"
            "QPushButton:disabled { background: #334155; color: #94a3b8; }"
        )
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setFixedWidth(180)
        ok.setEnabled(False)

        def _recheck(*_):
            en = cb.isChecked()
            if type_edit is not None:
                en = en and type_edit.text().strip() == required_phrase
            ok.setEnabled(en)

        cb.toggled.connect(_recheck)
        if type_edit is not None:
            type_edit.textChanged.connect(_recheck)

        def close():
            overlay.hide()
            overlay.deleteLater()

        def close_and_audit_cancel():
            try:
                experimental.audit_log(feature, "cancel")
            except Exception:
                pass
            close()

        cancel.clicked.connect(close_and_audit_cancel)
        x_btn.clicked.connect(close_and_audit_cancel)

        def on_ok():
            try:
                experimental.set_acknowledged(feature, True)
                experimental.audit_log(feature, "ack_and_confirm")
            except Exception:
                pass
            # Per-run ack token consumed by _run_ops_flow/_run_job_flow into
            # ctx['experimental_ack'] so core's strict gate passes this run
            # only. Counted per feature with timestamps (see token_note):
            # two confirms authorize two runs, and stale confirms expire
            # instead of authorizing a much later run.
            try:
                if not isinstance(getattr(self, "_exp_ack_once", None), dict):
                    self._exp_ack_once = {}
                experimental.token_note(self._exp_ack_once, feature)
            except Exception:
                pass
            close()
            on_confirm()

        ok.clicked.connect(on_ok)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        v.addLayout(btns)

        def center():
            card.adjustSize()
            max_h = overlay.height() - 32
            if card.height() > max_h:
                card.setFixedHeight(max_h)
            card.move((overlay.width() - card.width()) // 2, (overlay.height() - card.height()) // 2)

        def on_resize(e):
            QFrame.resizeEvent(overlay, e)
            center()

        overlay.resizeEvent = on_resize  # type: ignore
        center()
        overlay.show()
        overlay.raise_()
        try:
            experimental.audit_log(feature, "dialog_shown")
        except Exception:
            pass

    def _fetch_latest_stable_tag(self, timeout=5):
        """Live latest non-draft, non-prerelease tag from GitHub (never
        hand-coded). Returns '' when offline or nothing published."""
        import json as _json
        import urllib.request
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/Legendary-Brilliantforous/"
                "flashpilot/releases",
                headers={"User-Agent": "FlashPilot"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                rel = _json.loads(r.read().decode("utf-8"))
            best, bt = None, (0, 0, 0)
            for x in rel:
                if x.get("draft") or x.get("prerelease"):
                    continue
                tag = (x.get("tag_name") or "").lstrip("v")
                tv, _ = _parse_version(tag)
                if tv > bt:
                    best, bt = tag, tv
            return best or ""
        except Exception:
            return ""

    def _show_beta_gate_async(self):
        """Fetch latest stable off-thread, then open the beta gate on UI."""
        def work():
            tag = self._fetch_latest_stable_tag()
            def show():
                try:
                    self._show_beta_risk_dialog(APP_VERSION, tag)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    try:
                        self.log_line(f"[error] beta dialog crashed: {e}")
                        self._toasts.show_error("Beta dialog error", str(e))
                    except Exception:
                        pass
            try:
                self._ui.ui.emit(show)
            except Exception:
                show()
        threading.Thread(target=work, daemon=True).start()

    def _show_beta_risk_dialog(self, cur, stable_tag, force=False):
        """Beta acceptance gate — replaces the easy-to-miss toast.

        Shows a blocking in-window card that requires an explicit
        'I accept the risk' checkbox. Persists per-version acceptance in
        QSettings so the user is not nagged every launch, but each new
        beta version requires a fresh acceptance. Text is rendered at
        high contrast (no translucency blur) so it never looks
        'out of focus'."""
        key = f"beta_risk_accepted_{cur}"
        # One-time reset per version: clears stale accepted/seen flags so a
        # freshly installed beta ALWAYS surfaces the risk dialog at least
        # once (stale flags from prior sessions silently suppressed it).
        reset_marker = f"beta_gate_reset_v2_{cur}"
        if not self.settings.value(reset_marker, False, type=bool):
            self.settings.setValue(f"beta_risk_accepted_{cur}", False)
            self.settings.setValue(f"beta_notice_seen_{cur}", False)
            self.settings.setValue(reset_marker, True)
        if self.settings.value(key, False, type=bool):
            return
        # Settings: first_install (default) shows once per beta version,
        # every_boot shows on every launch. Bigger than toast (320px) -> 620px.
        mode = self.settings.value("beta_warning_mode", "first_install")
        seen_key = f"beta_notice_seen_{cur}"
        if force:
            self.settings.setValue(key, False)
        elif mode == "first_install" and self.settings.value(key, False, type=bool):
            # Still show ONCE per version even if accepted, so a freshly
            # installed beta always surfaces the warning (user had accepted
            # during earlier testing, which silently hid it).
            if self.settings.value(seen_key, False, type=bool):
                try:
                    self._ui.line.emit("[beta] notice suppressed (already accepted "
                                       "for this version) — Settings ▸ Updates ▸ "
                                       "'Preview beta warning' to see it again.")
                except Exception:
                    pass
                return
            # fall through to show once, then mark seen
        # Prevent stacking multiple beta dialogs if update check fires twice
        if getattr(self, "_beta_dialog_open", False):
            return
        self._beta_dialog_open = True

        overlay = QFrame(self._root)
        overlay.setObjectName("betaOverlay")
        overlay.setStyleSheet(
            "QFrame#betaOverlay { background: rgba(4, 9, 18, 215); border-radius: 18px; }"
        )
        overlay.setGeometry(0, 0, self._root.width(), self._root.height())

        card = QFrame(overlay)
        card.setObjectName("betaCard")
        card.setFixedWidth(620)
        card.setMinimumHeight(380)
        card.setStyleSheet(
            f"QFrame#betaCard {{ background: {C['card']};"
            f" border: 1px solid #f59e0b; border-top: 2px solid #f59e0b; border-radius: 16px; }}"
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(42)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 220))
        card.setGraphicsEffect(shadow)
        # Make card movable — drag the header
        card._drag_pos = None  # type: ignore

        v = QVBoxLayout(card)
        v.setContentsMargins(26, 18, 26, 22)
        v.setSpacing(14)

        # Header row with BETA pill + title + X close (all high-contrast, draggable)
        hdr_wrap = QFrame()
        hdr_wrap.setStyleSheet("background: transparent;")
        hdr = QHBoxLayout(hdr_wrap)
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(10)
        pill = QLabel(" BETA ")
        pill.setStyleSheet(
            "color: #ffffff; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #f59e0b, stop:1 #dc2626);"
            " border-radius: 7px; padding: 3px 10px; font-size: 11px; font-weight: 900; letter-spacing: 1px;"
        )
        pill.setFixedHeight(24)
        hdr.addWidget(pill, 0, Qt.AlignmentFlag.AlignVCenter)
        title = QLabel("Pre-release build — accept the risk to continue")
        title.setStyleSheet("color: #f8fafc; font-size: 15px; font-weight: 800;")
        title.setWordWrap(True)
        hdr.addWidget(title, 1)
        # X button — closes app (same as Cancel/Exit per spec)
        x_btn = QPushButton("✕")
        x_btn.setFixedSize(28, 28)
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.setStyleSheet(
            "QPushButton { color: #cbd5e1; background: rgba(255,255,255,8); border: 1px solid rgba(255,255,255,12); border-radius: 14px; font-size: 13px; font-weight: 700; }"
            "QPushButton:hover { background: #dc2626; color: #ffffff; border-color: #dc2626; }"
        )
        x_btn.setToolTip("Exit application")
        hdr.addWidget(x_btn, 0, Qt.AlignmentFlag.AlignTop)
        v.addWidget(hdr_wrap)
        # Make header draggable
        def _start_drag(e):
            if e.button() == Qt.MouseButton.LeftButton:
                card._drag_pos = e.globalPosition().toPoint() - card.pos()  # type: ignore
        def _do_drag(e):
            if getattr(card, "_drag_pos", None) is not None and e.buttons() & Qt.MouseButton.LeftButton:
                np = e.globalPosition().toPoint() - card._drag_pos  # type: ignore
                np.setX(max(0, min(np.x(), overlay.width() - card.width())))
                np.setY(max(0, min(np.y(), overlay.height() - card.height())))
                card.move(np)
        def _end_drag(e):
            card._drag_pos = None  # type: ignore
        # Attach to header area (hdr_wrap) and also card for convenience
        for wdg in (hdr_wrap, title, pill):
            wdg.setCursor(Qt.CursorShape.OpenHandCursor)
            wdg.mousePressEvent = _start_drag  # type: ignore
            wdg.mouseMoveEvent = _do_drag  # type: ignore
            wdg.mouseReleaseEvent = _end_drag  # type: ignore

        # Version line — installed (downloaded) vs latest stable on GitHub (dynamic, never hand-coded)
        disp_cur = _display_version(cur)
        if stable_tag:
            stable_line = (
                f"Latest <b>stable</b> on GitHub is "
                f"<b style='color:#7dd3fc;'>{stable_tag}</b>  "
                f"(display v{_display_version(stable_tag)})."
            )
        else:
            stable_line = "Latest <b>stable</b> on GitHub: <i>not published yet.</i>"
        ver_line = QLabel(
            f"You downloaded <b style='color:#fbbf24;'>{cur}</b>  "
            f"(display v{disp_cur}).<br>{stable_line}"
        )
        ver_line.setTextFormat(Qt.TextFormat.RichText)
        ver_line.setWordWrap(True)
        ver_line.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: 600; line-height: 145%;")
        v.addWidget(ver_line)

        body = QLabel(
            "Beta builds are for testing only. They may contain bugs, incomplete\n"
            "features, or instabilities that can affect flashing and device data.\n\n"
            "• Back up your device and firmware before flashing\n"
            "• Do not use a beta on a primary / daily-driver phone\n"
            "• Report issues at github.com/Legendary-Brilliantforous/flashpilot"
        )
        body.setStyleSheet("color: #e2e8f0; font-size: 12.5px; font-weight: 500; letter-spacing: 0.2px;")
        body.setWordWrap(True)
        v.addWidget(body)

        # Checkbox gate — must be high-contrast
        from PyQt6.QtWidgets import QCheckBox

        cb = QCheckBox("I understand this beta may be unstable and I accept the risk.")
        cb.setStyleSheet(
            "QCheckBox { color: #f8fafc; font-size: 12.5px; font-weight: 700; spacing: 10px; }"
            "QCheckBox::indicator { width: 19px; height: 19px; border: 1px solid #64748b; border-radius: 5px; background: #0f172a; }"
            "QCheckBox::indicator:checked { background: #f59e0b; border-color: #f59e0b; image: none; }"
        )
        v.addWidget(cb)

        btns = QHBoxLayout()
        btns.setSpacing(12)
        cancel = QPushButton("Exit")
        cancel.setStyleSheet(_btn_ghost())
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setFixedWidth(120)
        cancel.setToolTip("Close the application")
        accept = QPushButton("OK — I Accept")
        accept.setEnabled(False)
        accept.setStyleSheet(
            "QPushButton { color: #ffffff; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #f59e0b, stop:1 #ea580c);"
            " border: none; border-radius: 9px; padding: 10px 18px; font-weight: 900; font-size: 13px; }"
            "QPushButton:disabled { background: #334155; color: #94a3b8; }"
            "QPushButton:hover:!disabled { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #fbbf24, stop:1 #f59e0b); }"
        )
        accept.setCursor(Qt.CursorShape.PointingHandCursor)
        accept.setFixedWidth(190)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(accept)
        v.addLayout(btns)

        hint = QLabel("Tip: you can change this in Settings → Updates → Beta warning (first install / every boot).")
        hint.setStyleSheet("color: #94a3b8; font-size: 11px;")
        hint.setWordWrap(True)
        v.addWidget(hint)

        def close_only():
            overlay.hide()
            overlay.deleteLater()
            self._beta_dialog_open = False
            try:
                self.settings.setValue(f"beta_notice_seen_{cur}", True)
            except Exception:
                pass

        def close_and_exit():
            close_only()
            # Spec: Exit/Cancel closes the app
            QTimer.singleShot(50, lambda: self.close())

        def on_accept():
            if self.settings.value("beta_warning_mode", "first_install") == "first_install":
                self.settings.setValue(key, True)
            try:
                self._ui.line.emit(f"[check] Beta risk accepted for {cur} — continuing")
            except Exception:
                pass
            close_only()

        def on_cancel():
            try:
                self._ui.line.emit(f"[check] Beta risk declined for {cur} — exiting")
            except Exception:
                pass
            close_and_exit()

        cb.toggled.connect(lambda checked: accept.setEnabled(checked))
        cancel.clicked.connect(on_cancel)
        x_btn.clicked.connect(on_cancel)
        accept.clicked.connect(on_accept)

        def center():
            card.adjustSize()
            # ensure card height fits overlay even on small screens, keep centered
            max_h = overlay.height() - 32
            if card.height() > max_h:
                card.setFixedHeight(max_h)
            else:
                card.setMinimumHeight(360)
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
        cb.setFocus()

    def _show_centered_notice(self, title, message, pill="INFO", pill_grad=(" #0ea5e9", "#22d3ee"), ok_label="OK", ok_callback=None, secondary_label=None, secondary_callback=None):
        """Generic big centered notice for stable channels — same UX as beta
        dialog (620px, draggable, X to close, high-contrast text) so stable
        toasts don't look 'not good enough' next to the beta gate."""
        # Dedupe rapid re-entry (manual + auto firing together)
        if getattr(self, "_centered_open", False):
            return
        self._centered_open = True  # type: ignore
        overlay = QFrame(self._root)
        overlay.setObjectName("centeredOverlay")
        overlay.setStyleSheet("QFrame#centeredOverlay { background: rgba(4, 9, 18, 205); border-radius: 18px; }")
        overlay.setGeometry(0, 0, self._root.width(), self._root.height())

        card = QFrame(overlay)
        card.setObjectName("centeredCard")
        card.setFixedWidth(600)
        card.setMinimumHeight(260)
        accent = pill_grad[0].strip()
        card.setStyleSheet(
            f"QFrame#centeredCard {{ background: {C['card']}; border: 1px solid {accent}; border-top: 2px solid {accent}; border-radius: 16px; }}"
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 210))
        card.setGraphicsEffect(shadow)
        card._drag_pos = None  # type: ignore

        v = QVBoxLayout(card)
        v.setContentsMargins(26, 18, 26, 20)
        v.setSpacing(14)

        hdr_wrap = QFrame()
        hdr_wrap.setStyleSheet("background: transparent;")
        hdr = QHBoxLayout(hdr_wrap)
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(10)
        pill_lbl = QLabel(f" {pill} ")
        # pill_grad contains two stops
        pill_lbl.setStyleSheet(
            f"color: #ffffff; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {pill_grad[0]}, stop:1 {pill_grad[1]});"
            " border-radius: 7px; padding: 4px 12px; font-size: 11px; font-weight: 900; letter-spacing: 1px;"
        )
        pill_lbl.setFixedHeight(24)
        hdr.addWidget(pill_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        t = QLabel(title)
        t.setStyleSheet("color: #f8fafc; font-size: 15px; font-weight: 800;")
        t.setWordWrap(True)
        hdr.addWidget(t, 1)
        x_btn = QPushButton("✕")
        x_btn.setFixedSize(28, 28)
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.setStyleSheet(
            "QPushButton { color: #cbd5e1; background: rgba(255,255,255,8); border: 1px solid rgba(255,255,255,12); border-radius: 14px; font-size: 13px; font-weight: 700; }"
            "QPushButton:hover { background: #334155; color: #ffffff; }"
        )
        hdr.addWidget(x_btn, 0, Qt.AlignmentFlag.AlignTop)
        v.addWidget(hdr_wrap)

        # Draggable header
        def _start_drag(e):
            if e.button() == Qt.MouseButton.LeftButton:
                card._drag_pos = e.globalPosition().toPoint() - card.pos()  # type: ignore

        def _do_drag(e):
            if getattr(card, "_drag_pos", None) is not None and e.buttons() & Qt.MouseButton.LeftButton:
                np = e.globalPosition().toPoint() - card._drag_pos  # type: ignore
                np.setX(max(0, min(np.x(), overlay.width() - card.width())))
                np.setY(max(0, min(np.y(), overlay.height() - card.height())))
                card.move(np)

        def _end_drag(e):
            card._drag_pos = None  # type: ignore

        for wdg in (hdr_wrap, t, pill_lbl):
            wdg.setCursor(Qt.CursorShape.OpenHandCursor)
            wdg.mousePressEvent = _start_drag  # type: ignore
            wdg.mouseMoveEvent = _do_drag  # type: ignore
            wdg.mouseReleaseEvent = _end_drag  # type: ignore

        msg = QLabel(message)
        msg.setWordWrap(True)
        msg.setTextFormat(Qt.TextFormat.PlainText)
        msg.setStyleSheet("color: #e2e8f0; font-size: 13px; font-weight: 500; line-height: 145%;")
        v.addWidget(msg)

        btns = QHBoxLayout()
        btns.setSpacing(12)

        if secondary_label and secondary_callback:
            sec_btn = QPushButton(secondary_label)
            sec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            sec_btn.setFixedWidth(160)
            sec_btn.setStyleSheet(
                "QPushButton { color: #ffffff; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #10b981, stop:1 #06b6d4); border: none; border-radius: 9px; padding: 10px 18px; font-weight: 900; font-size: 13px; }"
                "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #34d399, stop:1 #06b6d4); }"
            )
            btns.addWidget(sec_btn)
            def _sec_clicked():
                close()
                secondary_callback()
            sec_btn.clicked.connect(_sec_clicked)

        ok = QPushButton(ok_label)
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setFixedWidth(160)
        ok.setStyleSheet(
            "QPushButton { color: #ffffff; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0ea5e9, stop:1 #22d3ee); border: none; border-radius: 9px; padding: 10px 18px; font-weight: 900; font-size: 13px; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #38bdf8, stop:1 #22d3ee); }"
        )
        btns.addStretch(1)
        btns.addWidget(ok)
        v.addLayout(btns)

        def close():
            overlay.hide()
            overlay.deleteLater()
            self._centered_open = False  # type: ignore

        x_btn.clicked.connect(close)
        def _ok_clicked():
            close()
            if ok_callback:
                ok_callback()
        ok.clicked.connect(_ok_clicked)

        def center():
            card.adjustSize()
            max_h = overlay.height() - 32
            if card.height() > max_h:
                card.setFixedHeight(max_h)
            card.move((overlay.width() - card.width()) // 2, (overlay.height() - card.height()) // 2)

        def on_resize(e):
            QFrame.resizeEvent(overlay, e)
            center()

        overlay.resizeEvent = on_resize  # type: ignore
        center()
        overlay.show()
        overlay.raise_()
        ok.setFocus()

    # ----------------------------- Battery page ---------------------------

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

    # ---------------------------------------------------------- board actions
    # One-PAC paths for the Devices page. A Unisoc PAC carries the model's
    # FDL1/FDL2 plus load addresses, so `spd-flash-pac` needs neither the SPD
    # tab nor manually entered binaries. Every device-writing mode is
    # confirmed first and nothing is reported as done before the bridge call
    # returns. The manual FDL paths stay for advanced workbench work, where
    # the model-specific binaries genuinely are required.
    def _spd_board_key(self):
        """The device row the user picked (never "first device")."""
        return getattr(self, "_display_key", None)

    def _spd_fdl1(self):
        """FDL1 path configured on the SPD tab ("" when unset)."""
        return self.spd_files["fdl1"].text().strip()

    def _spd_fdl2(self):
        """FDL2 path configured on the SPD tab ("" when unset)."""
        return self.spd_files["fdl2"].text().strip()

    def _spd_pick_pac(self, label, title=None):
        """Ask for the model's PAC file; "" when the user cancels."""
        start = self.settings.value(
            "default_dir", os.path.expanduser("~/Downloads"))
        pac, _filt = QFileDialog.getOpenFileName(
            self, title or f"{label} · select PAC firmware", start,
            "SPD PAC firmware (*.pac);;All files (*)")
        if not pac:
            self.log_line(f"[info] {label}: PAC picker cancelled")
            return ""
        return pac

    def _spd_pac_run(self, label, pac, mode, out_dir=None, timeout=1800,
                     on_done=None):
        """Run one `spd-flash-pac` mode for the SELECTED device.

        The target slot stays ``auto`` (the bridge resolves the download-mode
        phone); the device key pins the job/lock scope to the picked row.
        PAC path + mode are logged up front; success is only reported by
        `_spd_run` once the bridge call returns cleanly.
        """
        argv = ["spd-flash-pac", "auto", pac, "--mode", mode]
        if out_dir:
            argv += ["--out", out_dir]
        self.log_line(f"[spd] {label}: {mode} from PAC {pac}")
        self._spd_run(argv, timeout=timeout,
                      device_key=self._spd_board_key(), on_done=on_done)
        return argv

    def _spd_board_screen_lock(self, label):
        """No ADB: erase the lock/FRP partitions from a PAC."""
        pac = self._spd_pick_pac(label)
        if not pac:
            return
        self._confirm_overlay(
            f"{label} · Remove Screen Lock",
            "No ADB connection to the selected phone, so the lock will be\n"
            "erased in download mode from:\n"
            f"{os.path.basename(pac)}\n\n"
            "spd-flash-pac loads the PAC's own FDL1/FDL2 (nothing to type\n"
            "in by hand) and erases the lock/FRP partitions.\n"
            "THIS MAY WIPE USER DATA.\n\nContinue?",
            confirm_label="Erase Lock",
            on_confirm=lambda p=pac: self._spd_pac_run(label, p, "erase"),
            chip="lock",
        )

    def _spd_board_frp(self, label):
        """No ADB, no FDLs configured: erase FRP from a PAC."""
        pac = self._spd_pick_pac(label)
        if not pac:
            return
        self._confirm_overlay(
            f"{label} · Remove FRP",
            "No ADB connection and no FDL binaries configured, so FRP will\n"
            "be erased in download mode from:\n"
            f"{os.path.basename(pac)}\n\n"
            "spd-flash-pac loads the PAC's own FDL1/FDL2 (nothing to type\n"
            "in by hand) and erases the FRP/lock partitions.\n"
            "THIS MAY WIPE USER DATA.\n\nContinue?",
            confirm_label="Erase FRP",
            on_confirm=lambda p=pac: self._spd_pac_run(label, p, "frp"),
            chip="frp",
        )

    def _spd_board_backup(self, label):
        """Back up partitions to a picked folder (FDL path or one PAC)."""
        out_dir = QFileDialog.getExistingDirectory(
            self, "Backup output folder",
            self.settings.value("default_dir", os.path.expanduser("~/Downloads")))
        if not out_dir:
            self.log_line(f"[info] {label}: backup cancelled")
            return

        def done(_out, d=out_dir):
            # Report the destination only once the bridge run has returned.
            self.log_line(f"[backup] {label}: backup written to {d}")

        fdl1 = self._spd_fdl1()
        if fdl1:
            self._on_section("spd")
            a1 = self._spd_addr(self.spd_fdl1_addr)
            fdl2 = self._spd_fdl2()
            args = ["spd-backup", self._spd_resolve_target() or "", fdl1,
                    f"0x{a1:x}" if a1 is not None else "0x0"]
            if fdl2:
                a2 = self._spd_addr(self.spd_fdl2_addr)
                args += [fdl2, f"0x{a2:x}" if a2 is not None else "0x0"]
            args.append(out_dir)
            self._spd_run(args, timeout=3600,
                          device_key=self._spd_board_key(), on_done=done)
            return

        pac = self._spd_pick_pac(label)
        if not pac:
            return
        self._spd_pac_run(label, pac, "backup", out_dir=out_dir,
                          timeout=3600, on_done=done)

    def _spd_board_flash(self, label):
        """Flash a single PAC file (the PAC embeds its FDL1/FDL2)."""
        pac = self._spd_pick_pac(label)
        if not pac:
            return
        self._confirm_overlay(
            f"{label} · Flash Firmware",
            f"Flash the stock firmware in:\n{pac}\n\n"
            "spd-flash-pac writes every image in the PAC and OVERWRITES the\n"
            "matching partitions/regions. The PAC's FDL1/FDL2 must match\n"
            "this phone's SoC.\n\n"
            "A wrong PAC, a mismatched model or an interrupted cable can\n"
            "leave the phone unbootable. Continue?",
            confirm_label="Flash Firmware",
            on_confirm=lambda p=pac: self._spd_pac_run(
                label, p, "flash", timeout=3600),
            chip="flash",
        )

    def _spd_target(self):
        """Best-effort current SPD download target from the poll state."""
        return getattr(self, "_last_spd_target", None)

    def _spd_run(self, args, timeout=900, device_key=None, on_done=None):
        """Run a bridge SPD command in a worker.

        ``on_done(out)`` (optional) runs in the worker after a successful
        return, so callers can report result details (e.g. a backup path)
        only once the flow really finished.
        """
        prep = self._chip_begin("SPD", args[0] if args else "",
                                {"SPD"}, args,
                                device_key=device_key,
                                stop_btn=self.spd_stop_btn)
        if prep[0] is None:
            return
        device_key, flux, args = prep

        def work():
            dev_tag = f"[{device_key}] "
            if flux:
                flux.set_state("RUNNING")

            def emit(line):
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            try:
                with _devices.device_scope(device_key):
                    out = bridge._run(args, timeout=timeout)
                emit(out or "(no output)")
                if on_done is not None:
                    try:
                        on_done(out or "")
                    except Exception:
                        pass
                self._ui.status.emit(f"SPD: {args[0]} done")
                self._ui.toast.emit("ok", f"SPD {args[0]}", "Completed successfully")
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except bridge.BridgeCancelled:
                emit("[cancelled] SPD operation stopped by user")
                self._ui.status.emit("SPD: operation cancelled")
                self._ui.toast.emit("warn", "SPD operation", "Cancelled")
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", "cancelled by user", "CANCELLED")
            except bridge.BridgeError as e:
                emit(f"[error] SPD {args[0]}: {e}")
                self._ui.status.emit(f"SPD: {args[0]} failed")
                self._ui.toast.emit("error", f"SPD {args[0]}", str(e))
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                _flow_end(key=device_key)
                try:
                    if flux and self._stop_job.get(self.spd_stop_btn) == flux.job_id:
                        self._stop_job.pop(self.spd_stop_btn, None)
                except Exception:
                    pass
                self._ui.ui.emit(self._spd_reset_ui)

        self.spd_stop_btn.setEnabled(True)
        self.spd_progress.setVisible(True)
        self.spd_progress.setValue(150)
        threading.Thread(target=work, daemon=True).start()

    def _spd_reset_ui(self):
        self.spd_stop_btn.setEnabled(False)
        self.spd_progress.setValue(1000)
        QTimer.singleShot(400, lambda: self.spd_progress.setVisible(False))

    def _spd_stop(self):
        if self._stop_active_job(self.spd_stop_btn, "SPD"):
            return
        bridge.request_cancel()
        core.request_cancel()
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
                # Show first device name like commercial tools (SPD Flash Tool)
                first = parsed[0]
                pid = first.get("pid", 0)
                stage = first.get("stage", "")
                prod = first.get("product")
                mfr = first.get("manufacturer")
                dl = bool(first.get("download"))

                if dl:
                    mode = "BROM/FDL"
                elif pid == 0x4001:
                    mode = "normal/PTP"
                else:
                    mode = "other"

                if prod and mfr:
                    status = f"{mfr} {prod} · 1782:{pid:04x} ({mode})"
                elif prod:
                    status = f"{prod} · 1782:{pid:04x} ({mode})"
                else:
                    status = f"Unisoc 1782:{pid:04x} ({mode})"

                if len(parsed) > 1:
                    status += f" +{len(parsed)-1} more"
                self._ui.ui.emit(lambda s=status: self.spd_status.setText(s))
            except bridge.BridgeError as e:
                self._ui.ui.emit(lambda err=e: self.spd_status.setText(
                    f"Scan error: {err}"))
            except Exception as e:  # noqa: BLE001
                self._ui.ui.emit(lambda err=e: self.spd_status.setText(
                    f"Scan error: {err}"))

        threading.Thread(target=work, daemon=True).start()

    def _spd_brom_watch(self):
        """Commercial-style BROM watcher: polls spd-detect every 400ms for the
        short-lived 1782:4d00 window that appears when a powered-off Unisoc
        phone is plugged with Vol-/boot key held. Auto-stops on catch."""
        if getattr(self, "_spd_watch_active", False):
            self._ui.line.emit("[spd] BROM watch already running - press Stop")
            return
        self._spd_watch_active = True
        self.spd_status.setText("Watching for BROM... hold boot key + plug USB")
        self._ui.line.emit("[spd] BROM watch started - power off, hold VOL- , plug USB")

        def work():
            import json as _json
            import time as _time
            caught = None
            deadline = _time.monotonic() + 180.0
            while _time.monotonic() < deadline and self._spd_watch_active:
                try:
                    devs = bridge._run(["spd-detect"], timeout=5)
                    parsed = _json.loads(devs or "[]")
                    dl = [d for d in parsed if d.get("download")]
                    if dl:
                        d = dl[0]
                        caught = f"{d['bus']}:{d['address']}"
                        pid = d.get("pid", 0)
                        self._last_spd_target = caught
                        def on_catch(t=caught, p=pid):
                            self.spd_status.setText(f"BROM CAUGHT @ {t} (1782:{p:04x}) - ready")
                            self.show_toast("SPD BROM detected!", f"Target {t}", "success")
                            self._append_console(f"[spd] === BROM WINDOW CAUGHT @ {t} (1782:{p:04x}) ===")
                            self._append_console("[spd] Run Get Device Info / FRP Reset / Format NOW (window closes on reboot)")
                        self._ui.ui.emit(on_catch)
                        break
                except Exception:  # noqa: BLE001
                    pass
                _time.sleep(0.4)

            if not caught:
                def on_timeout():
                    if self._spd_watch_active:
                        self.spd_status.setText("BROM watch timeout (3 min) - retry with VOL- held")
                        self._append_console("[spd] BROM watch timed out after 3 minutes")
                    self._spd_watch_active = False
                self._ui.ui.emit(on_timeout)
            else:
                self._spd_watch_active = False
                # Auto factory reset if armed — this makes BROM → immediate wipe the FIRST operation
                try:
                    if hasattr(self, "spd_brom_auto_check") and self.spd_brom_auto_check.isChecked():
                        # Use main-thread to run format so dialog + flow are safe
                        def auto_fmt(t=caught):
                            fdl1_a = self.spd_files["fdl1"].text().strip() if hasattr(self, "spd_files") else ""
                            # BROM should not require FDL — BROM-only path uses "none"
                            if not fdl1_a or not os.path.isfile(fdl1_a):
                                self._ui.line.emit("[spd] Auto BROM factory reset (BROM-only, no FDL) → spd-format BROM-only")
                                args_a = ["spd-format", t, "none", "0x0"]
                            else:
                                a1_a = self._spd_addr(self.spd_fdl1_addr)
                                if a1_a is None:
                                    a1_a = 0
                                fdl2_a = self.spd_files["fdl2"].text().strip()
                                args_a = ["spd-format", t, fdl1_a, f"0x{a1_a:x}"]
                                if fdl2_a and os.path.isfile(fdl2_a):
                                    a2_a = self._spd_addr(self.spd_fdl2_addr)
                                    if a2_a is not None:
                                        args_a += [fdl2_a, f"0x{a2_a:x}"]
                                self._ui.line.emit(f"[spd] Auto BROM factory reset → {' '.join(args_a)}")
                            self._spd_run(args_a, timeout=900)
                        self._ui.ui.emit(auto_fmt)
                except Exception:
                    pass

        threading.Thread(target=work, daemon=True).start()

    def _spd_brom_factory_reset(self):
        """One-click BROM factory reset — the FIRST operation for SPD.

        BROM should NOT require FDL file: if FDLs are selected they are used for
        full userdata wipe, otherwise BROM-only raw erase (PS/NV) runs immediately.
        If BROM already present runs spd-format immediately; otherwise arms auto-watch.
        """
        # FDL is optional for BROM — only use if file exists
        fdl1_raw = self.spd_files["fdl1"].text().strip() if hasattr(self, "spd_files") else ""
        fdl1 = fdl1_raw if fdl1_raw and os.path.isfile(fdl1_raw) else None
        a1 = self._spd_addr(self.spd_fdl1_addr)
        if fdl1 and a1 is None:
            return
        if not fdl1:
            a1 = 0  # BROM-only ignores base
        fdl2_raw = self.spd_files["fdl2"].text().strip() if hasattr(self, "spd_files") else ""
        fdl2 = fdl2_raw if fdl2_raw and os.path.isfile(fdl2_raw) else None
        a2 = self._spd_addr(self.spd_fdl2_addr) if fdl2 else None
        tgt = self._spd_resolve_target()
        if tgt:
            # BROM already caught — immediate confirm + format (FIRST)
            if fdl1:
                fdl2_part = f" + FDL2 {os.path.basename(fdl2)}" if fdl2 else " (FDL1-only, feature phone)"
                detail = f"FDL1: {os.path.basename(fdl1)}{fdl2_part}\nFull BSL erase (userdata/cache/frp or PS+NV)."
            else:
                detail = "BROM-only (no FDL) — raw erase of PS/NV regions via BootROM.\nFor full Android userdata wipe, select FDL1/FDL2 then retry."
            self._confirm_overlay(
                "BROM Factory Reset — Immediate",
                f"BROM already caught @ {tgt} (1782:4d00).\n"
                f"Immediately factory-reset this SPD device FIRST?\n\n"
                f"{detail}\n"
                "User data will be wiped — this is intentionally the FIRST operation.",
                confirm_label="Factory Reset NOW",
                on_confirm=lambda t=tgt, f1=(fdl1 or "none"), aa1=(a1 if a1 is not None else 0), f2=fdl2, aa2=a2: self._spd_run(
                    ["spd-format", t, f1, f"0x{aa1:x}"] + ([f2, f"0x{aa2:x}"] if f2 and aa2 is not None else []),
                    timeout=900,
                ),
            )
            return
        # No BROM yet — arm auto and start watcher so format is FIRST when BROM appears
        try:
            self.spd_brom_auto_check.setChecked(True)
        except Exception:
            pass
        self._ui.line.emit("[spd] BROM not yet present — arming auto factory reset (FIRST) + starting watch (no FDL needed)")
        self.show_toast("BROM Factory Reset armed (FIRST)", "Hold VOL-/boot key + plug USB — format will auto-run on catch (BROM-only if no FDL)", "info")
        self._spd_brom_watch()

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

    def _spd_info(self, device_key=None):
        prep = self._chip_begin("SPD", "spd-info", {"SPD"},
                                ["spd-info", "auto"],
                                device_key=device_key,
                                stop_btn=self.spd_stop_btn,
                                destructive=False)
        if prep[0] is None:
            return
        device_key, flux, resolved = prep
        tgt = resolved[1]
        self.spd_status.setText("Reading device info...")

        def work():
            if flux:
                flux.set_state("RUNNING")

            def emit(line):
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            try:
                with _devices.device_scope(device_key):
                    out = bridge._run(["spd-info", tgt], timeout=60)
                emit(out or "(no output)")
                self._ui.ui.emit(lambda: self.spd_status.setText("Info above"))
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except bridge.BridgeCancelled as e:
                emit(f"[cancelled] SPD info stopped by user ({e})")
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", str(e), "CANCELLED")
            except bridge.BridgeError as e:
                emit(f"[error] SPD device info: {e}")
                self._ui.ui.emit(lambda err=e: self.spd_status.setText(
                    f"Read error: {err}"))
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                _flow_end(key=device_key)
                try:
                    if flux and self._stop_job.get(self.spd_stop_btn) == flux.job_id:
                        self._stop_job.pop(self.spd_stop_btn, None)
                except Exception:
                    pass

        threading.Thread(target=work, daemon=True).start()

    def _spd_magic_sync_presets(self):
        """Rebuild the patches line from checked presets + freeform tail."""
        # Collect checked preset tokens
        chosen = [off for off, cb in self.spd_magic_presets.items() if cb.isChecked()]
        # Keep any custom entries already typed that are NOT presets
        raw = self.spd_magic_patches.text()
        customs = [t.strip() for t in raw.split(";") if t.strip() and t.strip() not in self.spd_magic_presets]
        # Merge: presets first, then customs (dedup)
        merged = []
        for tok in chosen:
            if tok not in merged:
                merged.append(tok)
        for tok in customs:
            if tok not in merged:
                merged.append(tok)
        # Block re-entry signal while we set text
        self.spd_magic_patches.blockSignals(True)
        self.spd_magic_patches.setText("; ".join(merged))
        self.spd_magic_patches.blockSignals(False)

    def _spd_magic_pack(self):
        """Pack the stock image with magic64 framing (file transform only)."""
        stock = self.spd_magic_stock.text().strip()
        if not stock or not os.path.isfile(stock):
            self._toasts.show_warn("No stock image", "Select the image you read back from the device")
            return
        spec = self.spd_magic_patches.text().strip()
        if not spec:
            self._toasts.show_warn("No patches", "Enter at least one off=word patch")
            return
        try:
            lb = int(self.spd_magic_load_base.text().strip(), 0)
        except ValueError:
            self._toasts.show_error("Bad load base", "Load base must be hex like 0xB5000000")
            return

        patch_args = []
        for tok in spec.split(";"):
            tok = tok.strip()
            if tok:
                patch_args.append(tok)

        out_img = os.path.splitext(stock)[0] + "_magic.img"
        args = ["spd-magic-pack", stock, out_img,
                "--load-base", hex(lb)]
        for p in patch_args:
            args += ["--patch", p]

        self._ui.line.emit(f"[magic64] packing {os.path.basename(stock)} -> {os.path.basename(out_img)}")

        def work():
            try:
                out = bridge._run(args, timeout=60)
                self._ui.line.emit(out or "(no output)")
                def ok():
                    self._toasts.show_ok("magic64 packed",
                                         "Review offsets, then Flash Packed Image")
                    self.spd_status.setText(f"Packed: {os.path.basename(out_img)}")
                self._ui.ui.emit(ok)
            except bridge.BridgeError as e:
                err = str(e)
                def fail():
                    self._ui.line.emit(f"[error] magic64: {err}")
                    self._toasts.show_error("Pack failed", err)
                self._ui.ui.emit(fail)

        threading.Thread(target=work, daemon=True).start()

    def _spd_magic_flash(self):
        """Flash the packed image - gated on the _magic.img safety marker."""
        packed = os.path.splitext(self.spd_magic_stock.text().strip())[0] + "_magic.img"
        if not packed.endswith("_magic.img") or not os.path.isfile(packed):
            self._toasts.show_warn("Nothing to flash",
                                   "Run Pack first - only _magic.img outputs are flashable here")
            return
        fdl1 = self._spd_require_files()
        if not fdl1:
            return
        a1 = self._spd_addr(self.spd_fdl1_addr)
        if a1 is None:
            return
        tgt = self._spd_resolve_target()
        if not tgt:
            self._toasts.show_warn("No SPD device", "Catch the BROM window first")
            return

        # partition name from stock filename (uboot.img -> uboot)
        base = os.path.basename(self.spd_magic_stock.text().strip())
        part = os.path.splitext(base)[0].lower()

        fdl2 = self.spd_files["fdl2"].text().strip()
        args = ["spd-flash", tgt, fdl1, f"0x{a1:x}"]
        if fdl2:
            a2v = self._spd_addr(self.spd_fdl2_addr)
            args += [fdl2] + ([f"0x{a2v:x}"] if a2v is not None else [])
        args.append(f"{part}={packed}")

        self._confirm_overlay(
            f"Flash {part} (magic64)",
            f"Write the PACKED image over '{part}'?\n\n"
            f"  {packed}\n\n"
            "The signed payload is untouched so SPL verification passes,\n"
            "but wrong load-base/offsets corrupt memory at boot.\n"
            "Keep the stock image for recovery via BROM.",
            confirm_label=f"Flash {part}",
            on_confirm=lambda: self._spd_run(args, timeout=900),
        )

    def _spd_boot(self, mode):
        """Reboot download-mode device into recovery / fastboot / normal."""
        tgt = self._spd_resolve_target()
        if not tgt:
            self._ui.line.emit("[warn] SPD boot: no download device detected")
            self._toasts.show_warn("No SPD device", "Catch the BROM window first")
            return
        if mode == "normal":
            # Bare-BROM path: no FDLs needed.
            self._spd_run(["spd-boot", tgt, "normal"], timeout=60)
            return
        fdl1 = self._spd_require_files()
        if not fdl1:
            return
        a1 = self._spd_addr(self.spd_fdl1_addr)
        if a1 is None:
            return
        fdl2 = self.spd_files["fdl2"].text().strip()
        args = ["spd-boot", tgt, fdl1, f"0x{a1:x}"]
        if fdl2:
            a2 = self._spd_addr(self.spd_fdl2_addr)
            args += [fdl2] + ([f"0x{a2:x}"] if a2 is not None else [])
        label = "Recovery" if mode == "recovery" else "Fastboot"
        self._confirm_overlay(
            f"Reboot to {label}",
            f"Write 'boot-{label.lower()}' into the misc BCB and reset the\n"
            f"device so it boots straight into {label}?\n\n"
            "Needs FDL1+FDL2 (misc is only writable after FDL2 runs).",
            confirm_label=f"Boot {label}",
            on_confirm=lambda: self._spd_run(args + [mode], timeout=120),
        )

    def _spd_enable_adb(self):
        """Enable ADB on an SPD phone via boot.img ramdisk patch (Path 1)."""
        # The helper ships an honest refusal while no safe one-shot path
        # exists. Report it before asking for FDL files, so the button never
        # looks like it "did nothing" and never claims a patch was written.
        try:
            from python.core import spd_adb as _spd_adb
        except Exception as e:  # pragma: no cover - import must never fail
            self._ui.line.emit(f"[error] SPD ADB helper unavailable: {e}")
            self._toasts.show_error("SPD ADB unavailable", str(e))
            return
        if not getattr(_spd_adb, "SUPPORTED", True):
            reason = getattr(_spd_adb, "UNAVAILABLE_REASON", "")
            self._ui.line.emit(f"[error] SPD ADB: {reason}")
            self._toasts.show_error("SPD ADB not available", reason)
            return

        fdl1 = self._spd_require_files()
        if not fdl1:
            return
        a1 = self._spd_addr(self.spd_fdl1_addr)
        if a1 is None:
            return
        fdl2 = self.spd_files["fdl2"].text().strip()
        part = self.spd_adb_part.currentText().strip()
        tgt = self._spd_resolve_target()
        if not tgt:
            self._ui.line.emit("[warn] SPD ADB: no download device detected")
            self._toasts.show_warn("No SPD device", "Catch the BROM window first")
            return

        if not _flow_start("SPD ADB enable", destructive=True):
            self._ui.status.emit("Busy: " + _flow_busy_msg())
            self._ui.toast.emit("warn", "Operation already running", _flow_busy_msg())
            return

        def work():
            try:
                # Import the boot-patch helper. The module always exists now,
                # so a failing import is a real error (not reloaded away).
                from python.core.spd_adb import enable_adb_via_boot_patch

                backup_dir = os.path.expanduser("~/flashpilot/backups")
                res = enable_adb_via_boot_patch(
                    bridge, tgt, fdl1, a1,
                    fdl2=fdl2 or None,
                    a2=self._spd_addr(self.spd_fdl2_addr) if fdl2 else None,
                    part=part,
                    backup_dir=backup_dir,
                    log=lambda m: self._ui.line.emit(m),
                )
                patched = res.get("patched")
                if patched:
                    self._ui.line.emit(f"[adb] patched image: {patched}")
                if res.get("flashed", True):
                    self._ui.line.emit(
                        "[adb] boot.img patched + flashed. Reboot the device; "
                        "ro.adb.secure=0 so ADB should come up. If a dialog "
                        "shows, tap Allow once."
                    )
                    self._ui.status.emit("SPD: ADB enable complete")
                    self._ui.toast.emit("ok", "SPD ADB", "boot patched + flashed")
                else:
                    self._ui.line.emit(
                        "[info] patched image staged but NOT flashed — follow "
                        "the next steps in the log."
                    )
                    self._ui.status.emit("SPD: ADB enable staged (not flashed)")
                    self._ui.toast.emit(
                        "warn", "SPD ADB", "Patched image staged — not flashed")
            except bridge.BridgeError as e:
                self._ui.line.emit(f"[error] SPD ADB: {e}")
                self._ui.toast.emit("error", "SPD ADB", str(e))
            except Exception as e:  # noqa: BLE001
                self._ui.line.emit(f"[error] SPD ADB: {e}")
                self._ui.toast.emit("error", "SPD ADB", str(e))
            finally:
                _flow_end()
                bridge.clear_cancel()
                self._ui.ui.emit(self._spd_reset_ui)

        bridge.clear_cancel()
        self.spd_stop_btn.setEnabled(True)
        self.spd_progress.setVisible(True)
        self.spd_progress.setValue(150)
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

    def _spd_flash_run(self, fdl1, a1, fdl2, entries, device_key=None):
        prep = self._chip_begin("SPD", "spd-flash", {"SPD"},
                                ["spd-flash", "auto"],
                                device_key=device_key,
                                stop_btn=self.spd_stop_btn)
        if prep[0] is None:
            return
        device_key, flux, _resolved = prep
        # The helper resolved + validated the device and replaced "auto"
        # with the fresh bus:addr target: argv[1] of the placeholder.
        tgt = _resolved[1]

        def work():
            dev_tag = f"[{device_key}] "
            if flux:
                flux.set_state("RUNNING")

            def emit(line):
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            try:
                with _devices.device_scope(device_key):
                    # Safety net: back up boot-critical partitions before writing.
                    try:
                        from python.core.safety import preflash_backup
                        a2v = self._spd_addr(self.spd_fdl2_addr) if fdl2 else None
                        preflash_backup("spd", bridge, emit,
                                        target=tgt, fdl1=fdl1, a1=a1,
                                        fdl2=fdl2 or "", a2=a2v)
                    except Exception as e:  # noqa: BLE001
                        emit(f"[safety] backup skipped: {e}")

                    args = ["spd-flash", tgt, fdl1, f"0x{a1:x}"]
                    if fdl2:
                        a2 = self._spd_addr(self.spd_fdl2_addr) or 0
                        args += [fdl2, f"0x{a2:x}"]
                    for part, file in entries:
                        args.append(f"{part}={file}")
                    out = bridge._run(args, timeout=1800)
                emit(out or "(no output)")
                self._ui.status.emit("SPD: flash complete")
                self._ui.toast.emit("ok", "SPD flash", "Completed")
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except bridge.BridgeCancelled:
                emit("[cancelled] SPD flash stopped by user")
                self._ui.toast.emit("warn", "SPD flash", "Cancelled")
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", "cancelled by user", "CANCELLED")
            except bridge.BridgeError as e:
                emit(f"[error] SPD flash: {e}")
                self._ui.toast.emit("error", "SPD flash", str(e))
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                _flow_end(key=device_key)
                try:
                    if flux and self._stop_job.get(self.spd_stop_btn) == flux.job_id:
                        self._stop_job.pop(self.spd_stop_btn, None)
                except Exception:
                    pass
                self._ui.ui.emit(self._spd_reset_ui)

        self.spd_stop_btn.setEnabled(True)
        self.spd_progress.setVisible(True)
        self.spd_progress.setValue(150)
        threading.Thread(target=work, daemon=True).start()

    def _spd_backup(self, device_key=None):
        fdl1 = self._spd_require_files()
        if not fdl1:
            return
        a1 = self._spd_addr(self.spd_fdl1_addr)
        if a1 is None:
            return
        fdl2 = self.spd_files["fdl2"].text().strip()
        fw = self.spd_fw_dir.text().strip()
        out_dir = fw or "/tmp/spd_backup"
        self._ui.line.emit(f"[step] SPD backup: fdl1={fdl1} fdl2={fdl2} out={out_dir}")
        self._toasts.show_ok("SPD backup queued", "Reading partition table...")
        prep = self._chip_begin("SPD", "spd-backup", {"SPD"},
                                ["spd-backup", "auto"],
                                device_key=device_key,
                                stop_btn=self.spd_stop_btn,
                                destructive=False)
        if prep[0] is None:
            return
        device_key, flux, _resolved = prep
        tgt = _resolved[1]

        def work():
            dev_tag = f"[{device_key}] "
            if flux:
                flux.set_state("RUNNING")

            def emit(line):
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            try:
                with _devices.device_scope(device_key):
                    out = bridge._run(
                        ["spd-backup", tgt, fdl1, f"0x{a1:x}",
                         fdl2 or "none", "0", out_dir],
                        timeout=900,
                    )
                emit(out or "(no output)")
                self._ui.status.emit("SPD: backup complete")
                self._ui.toast.emit("ok", "SPD backup", "Partition table dumped")
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except bridge.BridgeCancelled:
                emit("[cancelled] SPD backup stopped by user")
                self._ui.toast.emit("warn", "SPD backup", "Cancelled")
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", "cancelled by user", "CANCELLED")
            except bridge.BridgeError as e:
                emit(f"[error] SPD backup: {e}")
                self._ui.toast.emit("error", "SPD backup", str(e))
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                _flow_end(key=device_key)
                try:
                    if flux and self._stop_job.get(self.spd_stop_btn) == flux.job_id:
                        self._stop_job.pop(self.spd_stop_btn, None)
                except Exception:
                    pass
                self._ui.ui.emit(self._spd_reset_ui)

        self.spd_stop_btn.setEnabled(True)
        self.spd_progress.setVisible(True)
        self.spd_progress.setValue(150)
        threading.Thread(target=work, daemon=True).start()

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
        col.setSpacing(2)
        lab = QLabel(text)
        lab.setStyleSheet(f"color:{C['text']}; font-size:13px; font-weight:700;")
        col.addWidget(lab)
        if detail:
            d = QLabel(detail)
            d.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
            d.setWordWrap(True)
            col.addWidget(d)
        row.addLayout(col, 1)
        if widget is not None:
            row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        box_lay.addLayout(row)
        return row

    def _settings_switch(self):
        cb = BeautifulToggle()
        # Ensure thumbPos matches initial checked without anim on first show
        cb.setChecked(False)
        cb._thumb_pos = 0.0
        return cb

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

    def _apply_beta_warning_mode(self, on):
        # on==True => every_boot, off => first_install (default)
        mode = "every_boot" if on else "first_install"
        self.settings.setValue("beta_warning_mode", mode)
        self._ui.line.emit(f"[settings] beta warning mode -> {mode}")

    def _apply_theme(self, name):
        self.settings.setValue("theme", name)
        if name in ACCENT_THEMES:
            C.update(ACCENT_THEMES[name])
            self._rebuild_theme()
        self._ui.line.emit(f"[settings] theme -> {name}")

    def _rebuild_theme(self):
        self._toasts.show_ok("Theme applied", f"Restyled whole app — {self.settings.value('theme', 'Neon Circuit')}")
        # Regenerate QSS with current C so whole app recolors, not just the accent line
        try:
            self.setStyleSheet(_get_base_qss() + _console_qss())
        except Exception:
            self.setStyleSheet(_get_base_qss() + _console_qss())
        # Accent strip (top line)
        if hasattr(self, "_accent_strip") and self._accent_strip:
            try:
                self._accent_strip.update()
            except Exception:
                pass
        # Root card border-top
        if hasattr(self, "_root") and self._root:
            try:
                self._root.setStyleSheet(
                    f"QFrame#root {{ background: rgba(5, 9, 15, 244);"
                    f" border: 1px solid {C['border_hi']}; border-top: 2px solid {C['border_hi']};"
                    f" border-radius: 12px; }}"
                )
            except Exception:
                pass
        # Connection banner
        if hasattr(self, "_conn") and self._conn:
            try:
                self._set_conn_glow(None)
            except Exception:
                pass
        # Restyle combos and button gradients that captured C at creation
        for combo in (getattr(self, "_s_theme", None),):
            if combo:
                try:
                    self._style_combo(combo)
                except Exception:
                    pass
        # Force full repaint so cards/buttons pick up new gradients
        try:
            self.update()
            for w in self.findChildren(QFrame):
                w.update()
        except Exception:
            pass

    def _apply_animations(self, on):
        self.settings.setValue("animations", on)
        self._anim_enabled = bool(on)
        for w in (self.scene, self.orb):
            try:
                w.set_animations(bool(on))
            except Exception:
                pass
        # Granular toggles are standard beautiful but disabled when Master off
        for attr in ("_s_anim_cable","_s_anim_orb","_s_anim_shimmer","_s_anim_toast","_s_anim_window","_s_anim_shake","_s_anim_rubber","_s_anim_bubble"):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.setEnabled(bool(on))
                    w.setToolTip("" if on else "Master animations off")
                except Exception:
                    pass
        # Also preview buttons respect master
        for b in getattr(self, "_anim_preview_trio", []):
            try:
                b.setEnabled(bool(on))
            except Exception:
                pass

    def _apply_blur(self, on):
        self.settings.setValue("blur", on)
        if self._root_shadow is not None:
            self._root_shadow.setEnabled(bool(on))

    def _rebuild_bridge(self):
        def work():
            self._ui.line.emit("[build] cargo build --release ...")
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            rc = subprocess.run(
                ["cargo", "build", "--release"], cwd=root,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            for line in (rc.stdout or "").splitlines():
                self._ui.line.emit(f"  {line}")
            self._ui.line.emit(
                f"[build] {'OK' if rc.returncode == 0 else f'FAILED (rc={rc.returncode})'}"
            )
            self._ui.toast.emit(
                "ok", "Bridge build", "Succeeded" if rc.returncode == 0 else "Failed - see console"
            )
        threading.Thread(target=work, daemon=True).start()

    def _open_log_dir(self):
        subprocess.Popen(["xdg-open", os.path.expanduser("~/Downloads")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _reset_settings(self):
        self.settings.clear()
        self._toasts.show_info("Settings reset", "Values restored to defaults")
        self._switch_settings("general")

    def _download_and_prompt_install(self, latest_url, stable_tag):
        import threading

        fpath = os.path.expanduser("~/flashpilot_update.deb")
        self.show_toast("Downloading update", f"Downloading FlashPilot {stable_tag}...", "info")
        if hasattr(self, "_ui") and self._ui:
            try:
                self._ui.line.emit(f"[check] Downloading {stable_tag} ...")
            except Exception:
                pass

        def _worker(url=latest_url, tag=stable_tag, dest=fpath):
            try:
                import urllib.request
                urllib.request.urlretrieve(url, dest)
                if os.path.exists(dest):
                    if hasattr(self, "_ui") and self._ui:
                        try:
                            self._ui.line.emit(f"[check] Downloaded {tag} to {dest}")
                        except Exception:
                            pass
                        self._ui.ui.emit(lambda t=tag, fp=dest: self._prompt_install_update(t, fp))
                else:
                    self._ui.ui.emit(lambda: self.show_toast("Download failed", "File missing after download.", "error"))
            except Exception as e:
                try:
                    if hasattr(self, "_ui") and self._ui:
                        self._ui.line.emit(f"[check] Download failed: {e}")
                        self._ui.ui.emit(lambda _e=e: self.show_toast("Download failed", str(_e), "error"))
                    else:
                        self.show_toast("Download failed", str(e), "error")
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()

    def _prompt_install_update(self, stable_tag, fpath):
        self._show_centered_notice(
            "Update Downloaded",
            f"FlashPilot {stable_tag} has been downloaded successfully.\n\nDo you want to install this update now?",
            pill="INSTALL",
            pill_grad=("#10b981", "#06b6d4"),
            ok_label="Later",
            secondary_label="Install Now",
            secondary_callback=lambda fp=fpath: self._execute_sudo_install(fp)
        )

    def _execute_sudo_install(self, fpath):
        import threading

        if not fpath or not os.path.exists(fpath) or not fpath.endswith(".deb"):
            self.show_toast("Installation Failed", "Update file not found.", "error")
            return
        from PyQt6.QtWidgets import QInputDialog, QLineEdit
        password, ok = QInputDialog.getText(
            self,
            "Sudo Password Required",
            "Enter your sudo password to install the FlashPilot update:",
            QLineEdit.EchoMode.Password
        )
        if not (ok and password):
            return
        self.show_toast("Installing update", "Running sudo dpkg -i ...", "info")
        if hasattr(self, "_ui") and self._ui:
            try:
                self._ui.line.emit("[check] Installing update (sudo dpkg -i) ...")
            except Exception:
                pass

        def _worker(pw=password, dest=fpath):
            import subprocess
            try:
                res = subprocess.run(
                    ["sudo", "-S", "dpkg", "-i", dest],
                    input=pw + "\n",
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
            except Exception as e:
                self._ui.ui.emit(lambda _e=e: self.show_toast("Installation Failed", str(_e), "error"))
                return
            finally:
                # Never keep the password referenced longer than needed.
                pw = ""
            if res.returncode == 0:
                if hasattr(self, "_ui") and self._ui:
                    try:
                        self._ui.line.emit("[check] Update installed - restarting into the new version ...")
                    except Exception:
                        pass
                self._ui.ui.emit(lambda: self.show_toast("Update Installed", "Restarting FlashPilot...", "success"))
                QTimer.singleShot(1500, self._restart_application)
            else:
                err = (res.stderr or "").strip() or (res.stdout or "").strip() or "Installation failed"
                # Avoid echoing a wrong-password sudo prompt verbatim forever; keep it short.
                self._ui.ui.emit(lambda _e=err[-800:]: self.show_toast("Installation Failed", _e, "error"))
                if hasattr(self, "_ui") and self._ui:
                    try:
                        self._ui.line.emit(f"[check] Install failed: {err[-500:]}")
                    except Exception:
                        pass

        threading.Thread(target=_worker, daemon=True).start()

    def _restart_application(self):
        import os
        import sys
        try:
            from PyQt6.QtCore import QProcess
            from PyQt6.QtWidgets import QApplication
            # Installed .deb runs via /usr/bin/flashpilot (venv python + /usr/share/flashpilot/main.py).
            # Prefer relaunching through the launcher so the new install is picked up,
            # instead of re-execing the possibly-stale current interpreter path.
            launcher = "/usr/bin/flashpilot"
            try:
                from python.core import APP_VERSION  # noqa: F401  (keeps import cheap/local)
            except Exception:
                pass
            using_installed_tree = os.path.exists("/usr/share/flashpilot/main.py")
            if os.path.exists(launcher) and os.access(launcher, os.X_OK) and using_installed_tree:
                try:
                    QProcess.startDetached(launcher, [])
                    try:
                        QApplication.quit()
                    except Exception:
                        pass
                    try:
                        self.close()
                    except Exception:
                        pass
                    return
                except Exception:
                    pass
            # Source checkout / dev run: re-exec the same interpreter + argv.
            try:
                self.close()
            except Exception:
                pass
            try:
                QApplication.quit()
            except Exception:
                pass
            os.execl(sys.executable, sys.executable, *sys.argv)
        except Exception:
            try:
                self.close()
            except Exception:
                pass

    def _check_update(self):
        # Auto-check: silent, must not block model refresh or close window
        if self._update_check_in_progress:
            return
        # Don't run auto-check if window is not visible yet (startup race)
        if not self.isVisible():
            QTimer.singleShot(5000, self._check_update)
            return
        self._update_check_in_progress = True
        self._last_check_was_auto = True
        if hasattr(self, "_check_updates_btn") and self._check_updates_btn:
            self._check_updates_btn.setEnabled(False)
            self._check_updates_btn.setText("Checking...")
        threading.Thread(target=self._check_update_thread, daemon=True).start()

    def _manual_check_update(self):
        if self._update_check_in_progress:
            if hasattr(self, "_toasts") and self._toasts:
                self._toasts.show_warn("Update check", "Update check already in progress.")
            return
        self._update_check_in_progress = True
        self._last_check_was_auto = False
        if hasattr(self, "_check_updates_btn") and self._check_updates_btn:
            self._check_updates_btn.setEnabled(False)
            self._check_updates_btn.setText("Checking...")
        if hasattr(self, "_ui") and self._ui:
            self._ui.line.emit("[check] Manual update check requested...")
        threading.Thread(target=self._check_update_thread, daemon=True).start()

    def _check_update_thread(self):
        import urllib.request, json, sys, subprocess
        try:
            if hasattr(self, "_ui") and self._ui:
                try:
                    self._ui.line.emit("[check] Looking for latest FlashPilot version...")
                except Exception:
                    pass
            req = urllib.request.Request(
                "https://api.github.com/repos/Legendary-Brilliantforous/flashpilot/releases",
                headers={"User-Agent": "FlashPilot"}
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = resp.read().decode("utf-8")
            except Exception as net_err:
                if hasattr(self, "_ui") and self._ui:
                    err_str = str(net_err).lower()
                    is_offline = any(k in err_str for k in (
                        "name resolution", "temporary failure", "network is unreachable",
                        "no route to host", "connection refused", "timed out",
                        "timeout", "offline", "name or service not known",
                        "getaddrinfo failed", "network unreachable"
                    )) or isinstance(net_err, OSError)
                    if is_offline:
                        self._ui.line.emit("[check] Offline — no internet connection, skipping update check.")
                    else:
                        self._ui.line.emit(f"[check] Could not reach update server: {net_err}")
                    if not getattr(self, "_last_check_was_auto", False):
                        if is_offline:
                            self._ui.ui.emit(lambda: self._toasts.show_info(
                                "Offline",
                                "No internet connection — could not check for updates.\n"
                                "Your installed version remains available offline."
                            ))
                        else:
                            self._ui.ui.emit(lambda _e=net_err: self._toasts.show_warn("Update check", f"Could not connect to update server: {_e}"))
                return

            releases = json.loads(body)
            if not isinstance(releases, list) or not releases:
                if hasattr(self, "_ui") and self._ui:
                    self._ui.line.emit("[check] No release info found")
                    if not getattr(self, "_last_check_was_auto", False):
                        self._ui.ui.emit(lambda: self._toasts.show_warn("Update check", "No release info found on GitHub."))
                return

            from python.core import APP_VERSION as current
            current_tuple, current_alpha = _parse_version(current)
            # Filter drafts and pick the *highest version* on each channel, not
            # just releases[0] (API order is publish date, not semver).
            def _pick_latest(cands):
                best = None
                best_t = (0, 0, 0)
                best_alpha = ""
                for r in cands:
                    tag = r.get("tag_name", "").lstrip("v")
                    t, a = _parse_version(tag)
                    if t > best_t or (t == best_t and not best_alpha and a):
                        # prefer higher numeric; for equal numeric keep first seen
                        best, best_t, best_alpha = r, t, a
                return best

            stables = [r for r in releases if not r.get("prerelease", False) and not r.get("draft", False)]
            betas = [r for r in releases if r.get("prerelease", False) and not r.get("draft", False)]

            latest_stable = _pick_latest(stables) if stables else None
            latest_beta = _pick_latest(betas) if betas else None

            stable_tag = latest_stable.get("tag_name", "").lstrip("v") if latest_stable else ""
            beta_tag = latest_beta.get("tag_name", "").lstrip("v") if latest_beta else ""

            stable_tuple, _ = _parse_version(stable_tag) if stable_tag else ((0, 0, 0), "")
            beta_tuple, beta_alpha = _parse_version(beta_tag) if beta_tag else ((0, 0, 0), "")

            auto_download = self.settings.value("auto_download_update", False, type=bool)

            # Upgrade detection:
            #  - a strictly higher numeric always upgrades
            #  - running a beta (alpha set) with the SAME numeric as a new
            #    stable is also an upgrade: promote beta -> final.
            promote_to_stable = bool(current_alpha) and stable_tuple == current_tuple
            newer_stable = bool(stable_tag) and (
                stable_tuple > current_tuple or promote_to_stable
            )
            ahead_of_stable = bool(stable_tag) and stable_tuple < current_tuple and not promote_to_stable
            # Beta upgrade only when numerically higher than what we run
            # (1.2.1-beta does not beat running 1.2.1; it beats 1.2.0).
            # Also treat same numeric but beta alpha newer (beta.1 -> beta.2) as update.
            newer_beta = False
            if beta_tag:
                if beta_tuple > current_tuple:
                    newer_beta = True
                elif beta_tuple == current_tuple and current_alpha and beta_alpha != current_alpha:
                    # same numeric but different prerelease (e.g. installed beta.1, beta.2 available)
                    # stable (no alpha) is never upgraded to beta of same numeric
                    newer_beta = beta_tag != current

            # Check if user is running a beta version – always warn and show
            # the real latest stable (1.2.0) vs beta (1.2.1-beta.1) distinction.
            if current_alpha:
                # User is on beta - warn them and show stable version
                if hasattr(self, "_ui") and self._ui:
                    try:
                        self._ui.line.emit(f"[check] You are running beta version {current} (latest stable is {stable_tag or 'unknown'})")
                    except Exception:
                        pass
                
                if hasattr(self, "_ui") and self._ui:
                    tag0 = stable_tag if stable_tag else ""
                    self._ui.ui.emit(lambda cur=current, st=tag0: self._show_beta_risk_dialog(cur, st))
            
            if newer_stable:
                if hasattr(self, "_ui") and self._ui:
                    note = " (promotes your beta install)" if promote_to_stable else ""
                    try:
                        self._ui.line.emit(f"[check] New stable version available: {stable_tag}{note} (you run {current})")
                    except Exception:
                        pass
                latest_url = None
                for a in latest_stable.get("assets", []):
                    if a["name"].endswith("_amd64.deb"):
                        latest_url = a["browser_download_url"]
                        break
                if latest_url:
                    if auto_download:
                        fpath = os.path.expanduser("~/flashpilot_update.deb")
                        try:
                            urllib.request.urlretrieve(latest_url, fpath)
                            if os.path.exists(fpath) and hasattr(self, "_ui") and self._ui:
                                try:
                                    self._ui.line.emit(f"[check] Automatically downloaded {stable_tag} to {fpath}")
                                    self._ui.ui.emit(lambda tag=stable_tag, fp=fpath: self._prompt_install_update(tag, fp))
                                except Exception:
                                    pass
                        except Exception as dl_err:
                            if hasattr(self, "_ui") and self._ui:
                                try:
                                    self._ui.line.emit(f"[check] Auto-download failed: {dl_err}")
                                    self._ui.ui.emit(lambda tag=stable_tag: self._show_centered_notice(
                                        "Stable update available",
                                        f"New stable version {tag} is available.\n\nAuto-download failed. Visit GitHub or try manual download.",
                                        pill="UPDATE", pill_grad=("#0ea5e9", "#22d3ee"), ok_label="OK"
                                    ))
                                except Exception:
                                    pass
                    else:
                        if hasattr(self, "_ui") and self._ui:
                            try:
                                self._ui.ui.emit(lambda url=latest_url, tag=stable_tag: self._show_centered_notice(
                                    "Stable update available",
                                    f"New stable version {tag} is available.\n\nClick 'Download Update' to download and install automatically, or visit GitHub.",
                                    pill="UPDATE", pill_grad=("#0ea5e9", "#22d3ee"),
                                    ok_label="OK",
                                    secondary_label="Download Update",
                                    secondary_callback=lambda: self._download_and_prompt_install(url, tag)
                                ))
                            except Exception:
                                pass
            else:
                # No newer stable version – distinguish ahead / up-to-date / beta
                if current_alpha:
                    # User is on beta
                    if ahead_of_stable:
                        if hasattr(self, "_ui") and self._ui:
                            try:
                                self._ui.line.emit(f"[check] You are on beta {current}, ahead of latest stable {stable_tag or 'unknown'} — no stable update yet")
                            except Exception:
                                pass
                    else:
                        if hasattr(self, "_ui") and self._ui:
                            try:
                                self._ui.line.emit(f"[check] You are on beta version {current}, latest stable is {stable_tag or 'unknown'}")
                            except Exception:
                                pass
                else:
                    if ahead_of_stable:
                        if hasattr(self, "_ui") and self._ui:
                            try:
                                self._ui.line.emit(f"[check] You are running {current} — ahead of latest stable {stable_tag} (pre-release/dev build)")
                            except Exception:
                                pass
                        # For manual checks, still tell user they are ahead — centered, big, movable
                        if not getattr(self, "_last_check_was_auto", False):
                            self._ui.ui.emit(lambda cur=current, st=stable_tag: self._show_centered_notice(
                                "Ahead of stable",
                                f"You run {cur}, which is newer than the latest stable {st} on GitHub.\n"
                                f"You're on a pre-release/dev build — stable updates will appear when published.",
                                pill="AHEAD", pill_grad=("#8b5cf6", "#22d3ee"), ok_label="OK"
                            ))
                    else:
                        # User is on latest stable
                        if hasattr(self, "_ui") and self._ui:
                            try:
                                self._ui.line.emit(f"[check] You are on the latest stable version ({current})")
                            except Exception:
                                pass
                
                # Beta channel notice (with download/install, mirroring the stable path)
                if newer_beta:
                    beta_url = None
                    try:
                        for a in (latest_beta.get("assets", []) if latest_beta else []):
                            if a["name"].endswith("_amd64.deb"):
                                beta_url = a["browser_download_url"]
                                break
                    except Exception:
                        beta_url = None
                    if beta_url and auto_download:
                        try:
                            fpath = os.path.expanduser("~/flashpilot_update.deb")
                            urllib.request.urlretrieve(beta_url, fpath)
                            if os.path.exists(fpath) and hasattr(self, "_ui") and self._ui:
                                try:
                                    self._ui.line.emit(f"[check] Automatically downloaded beta {beta_tag} to {fpath}")
                                    self._ui.ui.emit(lambda tag=beta_tag, fp=fpath: self._prompt_install_update(tag, fp))
                                except Exception:
                                    pass
                        except Exception as dl_err:
                            if hasattr(self, "_ui") and self._ui:
                                try:
                                    self._ui.line.emit(f"[check] Beta auto-download failed: {dl_err}")
                                except Exception:
                                    pass
                    if current_alpha:
                        # Already on beta but newer beta available
                        if hasattr(self, "_ui") and self._ui:
                            try:
                                self._ui.line.emit(f"[check] Newer beta available: {beta_tag} (you run {current})")
                            except Exception:
                                pass
                        if hasattr(self, "_ui") and self._ui:
                            try:
                                if beta_url:
                                    self._ui.ui.emit(lambda url=beta_url, tag=beta_tag, cur=current: self._show_centered_notice(
                                        "Beta update available",
                                        f"Newer beta {tag} is available (you run {cur}).\n\nBeta may contain bugs — for testing only.\n\nClick 'Download Beta' to download and install automatically.",
                                        pill="BETA", pill_grad=("#f59e0b", "#ea580c"),
                                        ok_label="Later",
                                        secondary_label="Download Beta",
                                        secondary_callback=lambda: self._download_and_prompt_install(url, tag)
                                    ))
                                else:
                                    self._ui.ui.emit(lambda tag=beta_tag, cur=current: self._show_centered_notice(
                                        "Beta update available",
                                        f"Newer beta {tag} is available (you run {cur}).\n\nBeta may contain bugs — for testing only.\n\nVisit: https://github.com/Legendary-Brilliantforous/flashpilot",
                                        pill="BETA", pill_grad=("#f59e0b", "#ea580c"), ok_label="OK"
                                    ))
                            except Exception:
                                pass
                    else:
                        if hasattr(self, "_ui") and self._ui:
                            try:
                                self._ui.line.emit(f"[check] Beta version {beta_tag} is available for testing (you run stable {current})")
                            except Exception:
                                pass
                        if hasattr(self, "_ui") and self._ui:
                            try:
                                if beta_url:
                                    self._ui.ui.emit(lambda url=beta_url, tag=beta_tag: self._show_centered_notice(
                                        "Beta version available",
                                        f"You are on the latest stable version ({current}).\n\nBeta release {tag} is available for testing.\n\nBeta versions may contain bugs and should be used for testing only.\n\nClick 'Download Beta' to download and install automatically.",
                                        pill="BETA", pill_grad=("#f59e0b", "#ea580c"),
                                        ok_label="Later",
                                        secondary_label="Download Beta",
                                        secondary_callback=lambda: self._download_and_prompt_install(url, tag)
                                    ))
                                else:
                                    self._ui.ui.emit(lambda tag=beta_tag: self._show_centered_notice(
                                        "Beta version available",
                                        f"You are on the latest stable version ({current}).\n\nBeta release {tag} is available for testing.\n\nBeta versions may contain bugs and should be used for testing only.\n\nVisit: https://github.com/Legendary-Brilliantforous/flashpilot",
                                        pill="BETA", pill_grad=("#f59e0b", "#ea580c"), ok_label="OK"
                                    ))
                            except Exception:
                                pass
                
                # Probe for python-tier drift (light patch) before
                # declaring fully up-to-date. Silent on failure.
                try:
                    from python.core import updater as _upd
                    st = _upd.check(timeout=8)
                    if st.get("status") == "python":
                        loc = (st.get("local_sha") or "unknown")[:12]
                        rem = (st.get("remote_sha") or "?")[:12]
                        self._ui.line.emit(
                            f"[check] Python patch available ({loc} -> {rem}) - "
                            "use Settings > Apply Python Patch."
                        )
                        if not getattr(self, "_last_check_was_auto", False):
                            self._ui.ui.emit(lambda: self._show_centered_notice(
                                "Light patch available",
                                "Python-only changes detected.\nSettings → Apply Python Patch…",
                                pill="PATCH", pill_grad=("#10b981", "#06b6d4"), ok_label="OK"
                            ))
                except Exception:
                    pass
                # Only pop up "Up to date" for manual checks; silent for auto
                # and suppress when ahead of stable (we already showed Ahead dialog)
                if not getattr(self, "_last_check_was_auto", False) and not ahead_of_stable:
                    self._ui.ui.emit(lambda cur=current: self._show_centered_notice(
                        "Up to date",
                        f"FlashPilot {cur} is already installed — you are on the latest version.",
                        pill="STABLE", pill_grad=("#0ea5e9", "#22d3ee"), ok_label="OK"
                    ))
        except Exception as e:
            if hasattr(self, "_ui") and self._ui:
                try:
                    self._ui.line.emit(f"[check] Update check error: {e}")
                except Exception:
                    pass
                try:
                    self._ui.ui.emit(lambda _e=e: self._toasts.show_warn("Update check", f"Error: {_e}"))
                except Exception:
                    pass
        finally:
            self._update_check_in_progress = False
            self._update_in_progress = False
            if hasattr(self, "_ui") and self._ui:
                try:
                    self._ui.ui.emit(lambda: self._reset_update_btn())
                except Exception:
                    pass

    def _reset_update_btn(self):
        if hasattr(self, "_check_updates_btn") and self._check_updates_btn:
            self._check_updates_btn.setEnabled(True)
            self._check_updates_btn.setText("Check for Updates Now")

    # ---- two-tier updater (python light patch) -------------------------
    def _apply_python_patch_clicked(self):
        """Confirm + apply the tier-1 python-only patch from GitHub main."""
        try:
            from python.core import updater
        except Exception as e:
            self.show_toast("Updater unavailable", str(e), "error")
            return
        if updater.is_dev_checkout():
            self.show_toast("Dev checkout", "Light patch applies only to installed builds.", "warn")
            return
        self._confirm_overlay(
            "Apply Python Patch",
            "Download the latest python/ tree from GitHub main (~200 KB) and "
            "swap it over the installed copy?\n\n"
            "Rust bridge and packaging are untouched. A restart is required "
            "afterwards. pkexec will ask for your password.",
            confirm_label="Patch",
            on_confirm=lambda: self._apply_python_patch_work(),
        )

    def _apply_python_patch_work(self):
        def work():
            try:
                from python.core import updater
                self._ui.line.emit("[update] staging python patch ...")
                tmpdir, sha = updater.stage_python_patch()
                self._ui.line.emit(f"[update] staged {sha[:12]} - applying via pkexec ...")
                updater.apply_python_patch(tmpdir, sha)
                self._ui.line.emit(f"[update] python patched to {sha[:12]}. Restart FlashPilot.")
                def ok():
                    self._toasts.show_ok(
                        "Patch applied",
                        f"Python updated to {sha[:12]}.\nRestart FlashPilot to finish."
                    )
                self._ui.ui.emit(ok)
            except Exception as e:  # noqa: BLE001
                err = str(e)
                def fail():
                    self._toasts.show_error("Patch failed", err)
                    self._ui.line.emit(f"[update] error: {err}")
                self._ui.ui.emit(fail)

        threading.Thread(target=work, daemon=True).start()

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

    def _console_chip(self, text, tip, checked=False, width=48):
        """Compact checkable console chip (theme tokens only)."""
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(bool(checked))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedWidth(width)
        btn.setToolTip(tip)
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border:1px solid {C['border']};"
            f" border-radius:6px; padding:3px 4px; font-size:10px; font-weight:700;"
            f" color:{C['dim']}; }}"
            f" QPushButton:hover {{ border-color:{C['border_hi']}; color:{C['text']}; }}"
            f" QPushButton:checked {{ background:{C['accent_dim']};"
            f" color:{C['accent_hi']}; border-color:{C['accent']}; }}"
        )
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
            try:
                if maximized:
                    self._outer.setContentsMargins(0, 0, 0, 0)
                    if getattr(self, "_root_shadow", None) is not None:
                        try:
                            self._root_shadow.setEnabled(False)
                        except RuntimeError:
                            pass
                else:
                    self._outer.setContentsMargins(30, 26, 30, 34)
                    if getattr(self, "_root_shadow", None) is not None:
                        try:
                            self._root_shadow.setEnabled(True)
                        except RuntimeError:
                            pass
            except Exception:
                pass

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
        """Record a line: ANSI stripped into the buffer, rendered in batches.

        The (level, plain) tuple goes into ``_log_buffer`` (ANSI-free, so
        search/copy/save stay clean); the raw message is kept in the parallel
        ``_log_ansi`` list so a rebuild can restore its colour mapping. The
        first pending line renders synchronously; a burst coalesces onto a
        single-shot flush timer (or immediately at the line cap).
        """
        raw = "" if msg is None else str(msg)
        plain, spans = parse_ansi(raw)
        level = self._classify(plain)
        self._log_buffer.append((level, plain))
        self._log_ansi.append(raw)
        if len(self._log_buffer) > 6000:
            del self._log_buffer[:-2000]
            del self._log_ansi[:-2000]
        self._update_count()
        if self._filter.get(level, True) and self._console_search_matches(plain):
            if self._pending_console or self._flush_timer_active():
                self._pending_console.append((level, plain, spans))
                if len(self._pending_console) >= self._CONSOLE_FLUSH_MAX:
                    self._flush_console()
                else:
                    self._start_flush_timer()
            else:
                # First line of a burst: render it now (no added latency) and
                # open the coalescing window so the rest of the burst batches.
                self._append_to_widget(level, plain, spans)
                self._start_flush_timer()
                if self.find_edit.text():
                    self._apply_find()

    def _flush_timer_active(self):
        timer = getattr(self, "_console_flush_timer", None)
        try:
            return bool(timer is not None and timer.isActive())
        except Exception:
            return False

    def _start_flush_timer(self):
        timer = getattr(self, "_console_flush_timer", None)
        if timer is None:
            return
        try:
            if not timer.isActive():
                timer.start()
        except Exception:
            pass

    def _flush_console(self):
        """Append every pending line, in order, as one coalesced batch."""
        timer = getattr(self, "_console_flush_timer", None)
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
        pending = getattr(self, "_pending_console", None)
        if not pending:
            return
        self._pending_console = []
        # One widget append for the whole batch: ``appendPlainText`` (and the
        # ``maxBlockCount`` trim it triggers) is O(document length), so a call
        # per line makes a burst O(n^2). A single call per flush removes that.
        self._append_batch_to_widget(pending)

    def _base_line_format(self, level, msg):
        fmt = QTextCharFormat()
        m = (msg or "").strip()
        if level == "err":
            fmt.setForeground(QColor(C["err"]))
        elif level == "warn":
            fmt.setForeground(QColor(C["warn"]))
        elif level == "ok":
            fmt.setForeground(QColor(C["ok"]))
        elif (m.startswith(">>> ") or m.startswith("== running flow:")
              or m.startswith("== flow finished:")):
            fmt.setForeground(QColor(C["accent_hi"]))
            fmt.setFontWeight(QFont.Weight.DemiBold)
        else:
            fmt.setForeground(QColor(C["text"]))
        return fmt

    def _base_format_key(self, level, msg):
        """Identity of the format ``_base_line_format`` builds for a line.

        ``err``/``warn``/``ok`` colour by level alone; ``info`` is ``accent``
        for the flow-marker prefixes and ``text`` otherwise. Consecutive lines
        sharing a key can therefore be formatted by a single merge pass.
        """
        if level in ("err", "warn", "ok"):
            return level
        m = (msg or "").strip()
        if (m.startswith(">>> ") or m.startswith("== running flow:")
                or m.startswith("== flow finished:")):
            return "accent"
        return "text"

    def _base_format_for_key(self, key):
        """Resolve a ``_base_format_key`` back to its ``QTextCharFormat``.

        Delegates to ``_base_line_format`` so the theme tokens stay defined in
        exactly one place (a probe message stands in for the accent case).
        """
        if key in ("err", "warn", "ok"):
            return self._base_line_format(key, "")
        if key == "accent":
            return self._base_line_format("info", ">>> marker")
        return self._base_line_format("info", "")

    def _merge_format(self, start, end, fmt):
        """Merge ``fmt`` over ``[start, end)``, clamped to the document.

        ``QTextCursor.setPosition`` warns (and, at exit, can crash) for a
        position past the document end, so the range is clamped to Qt's valid
        cursor positions ``[0, characterCount() - 1]`` before use. The last
        valid position is the *exclusive* end used by the anchored range.
        """
        doc = self.log.document()
        last = doc.characterCount() - 1
        start = max(0, min(int(start), last))
        end = max(0, min(int(end), last))
        if end <= start:
            return
        cur = QTextCursor(doc)
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cur.mergeCharFormat(fmt)

    def _append_to_widget(self, level, msg, spans=None):
        """Append one message (single-entry wrapper around the batch renderer).

        Kept as a stable entry point: ``log_line`` renders the first line of a
        burst synchronously through this, and ``_rebuild_console`` may too.
        """
        self._append_batch_to_widget([(level, msg, spans)])

    def _append_batch_to_widget(self, entries):
        """Append ``entries`` (``(level, msg, spans)``) in one widget call.

        ``appendPlainText`` is O(document length) because ``maxBlockCount``
        trims on each call, so rendering a batch one call at a time is O(n^2).
        Joining the batch into a single call makes it O(n) per flush.

        Formatting is then merged in as few passes as possible:

        * the base level format once per consecutive run of lines sharing a
          ``_base_format_key`` (one cursor range for the whole run);
        * the dim timestamp prefix once per message (first line only);
        * ANSI spans only on the messages that carry them.

        ``msg`` may contain embedded ``\\n``: each line becomes its own
        paragraph, the prefix lands on the first line only, and a span that
        crosses a newline is clipped to the matching slice of every line it
        touches. All positions are derived *after* the append, from the block
        count, so front-trimming cannot desync them.
        """
        if not entries:
            return
        show_ts = getattr(self, "_show_timestamps", True)
        stamp = f"[{_time.strftime('%H:%M:%S')}] " if show_ts else ""

        parts = []          # each entry's ``prefix + msg``, joined with "\n"
        line_offsets = []   # offset of every rendered line within ``combined``
        line_text = []      # rendered line text (no trailing newline)
        line_key = []       # base-format key per line
        meta = []           # (first_line, line_count, prefix_len, spans)
        combined_len = 0
        for level, msg, spans in entries:
            msg = "" if msg is None else str(msg)
            prefix = stamp
            full = prefix + msg
            first_line = len(line_text)
            key = self._base_format_key(level, msg)
            local = 0
            for line in full.split("\n"):
                line_offsets.append(combined_len + local)
                line_text.append(line)
                line_key.append(key)
                local += len(line) + 1  # +1 for the separating newline
            meta.append((first_line, len(line_text) - first_line,
                         len(prefix), spans))
            parts.append(full)
            combined_len += len(full) + 1
        combined = "\n".join(parts)

        doc = self.log.document()
        self.log.appendPlainText(combined)

        total_lines = len(line_text)
        blocks = doc.blockCount()
        # A single batch may exceed ``maxBlockCount``: the front is trimmed
        # away, so the surviving lines are the tail and the origin matches.
        trimmed = max(0, total_lines - blocks)
        first_index = max(0, blocks - total_lines)
        first_block = doc.findBlockByNumber(first_index)
        base = first_block.position() if first_block.isValid() else 0
        origin = line_offsets[trimmed] if trimmed else 0

        def doc_pos(off):
            # A newline in ``combined`` maps to exactly one paragraph
            # separator, so string offsets and document positions coincide.
            return base + (off - origin)

        # Base level format: one merge per run of consecutive same-key lines.
        fmt_cache = {}
        i = trimmed
        while i < total_lines:
            key = line_key[i]
            fmt = fmt_cache.get(key)
            if fmt is None:
                fmt = self._base_format_for_key(key)
                fmt_cache[key] = fmt
            j = i + 1
            while j < total_lines and line_key[j] == key:
                j += 1
            lo = doc_pos(line_offsets[i])
            hi = doc_pos(line_offsets[j - 1] + len(line_text[j - 1]))
            self._merge_format(lo, hi, fmt)
            i = j

        # Timestamp: dim, first line of each message only.
        if stamp:
            dim = QTextCharFormat()
            dim.setForeground(QColor(C["dim"]))
            for first_line, _count, prefix_len, _spans in meta:
                if prefix_len <= 0 or first_line < trimmed:
                    continue
                lo = doc_pos(line_offsets[first_line])
                self._merge_format(lo, lo + prefix_len, dim)

        # ANSI spans, only on the messages that have them.
        for first_line, count, prefix_len, spans in meta:
            if not spans:
                continue
            entry_start = line_offsets[first_line]
            for start, stop, attrs in spans:
                if not isinstance(attrs, dict):
                    continue
                fmt = QTextCharFormat()
                fg = attrs.get("fg")
                if fg and fg in C:
                    fmt.setForeground(QColor(C[fg]))
                elif attrs.get("dim"):
                    fmt.setForeground(QColor(C["dim"]))
                if attrs.get("bold"):
                    fmt.setFontWeight(QFont.Weight.Bold)
                gstart = entry_start + prefix_len + start
                gstop = entry_start + prefix_len + stop
                # Clip the span to each line so it survives newlines.
                for k in range(count):
                    idx = first_line + k
                    if idx < trimmed:
                        continue
                    lstart = line_offsets[idx]
                    lend = lstart + len(line_text[idx])
                    lo = max(gstart, lstart)
                    hi = min(gstop, lend)
                    if hi <= lo:
                        continue
                    self._merge_format(doc_pos(lo), doc_pos(hi), fmt)

    def _set_filter(self, level, checked):
        self._filter[level] = checked
        self._rebuild_console()

    def _rebuild_console(self):
        """Re-render the console respecting the level filters and search."""
        self._flush_console()
        self.log.clear()
        batch = []
        for i, (level, msg) in enumerate(self._log_buffer):
            if self._filter.get(level, True) and self._console_search_matches(msg):
                raw = self._log_ansi[i] if i < len(self._log_ansi) else msg
                _plain, spans = parse_ansi(raw)
                batch.append((level, msg, spans))
        # One whole rebuild as a single batch: a filter toggle re-renders up to
        # the full buffer, so per-entry appends would be O(n^2) too.
        self._append_batch_to_widget(batch)
        self._update_count()
        self._apply_find()

    def _update_count(self):
        self.console_count.setText(f"{len(self._log_buffer)} lines")

    def _clear_console(self):
        self._flush_console()
        self._log_buffer.clear()
        self._log_ansi.clear()
        self._pending_console = []
        self.log.clear()
        self._update_count()

    def _copy_console(self):
        self._flush_console()
        QApplication.clipboard().setText(self.log.toPlainText())
        self.set_status("Console copied to clipboard")

    def _copy_selection(self):
        text = self.log.textCursor().selectedText()
        if text:
            QApplication.clipboard().setText(text)
            self.set_status("Selection copied to clipboard")

    def _save_console(self):
        self._flush_console()
        default_name = ("flashpilot-console-"
                        + _time.strftime("%Y%m%d-%H%M%S") + ".log")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save console log", default_name,
            "Log files (*.log);;Text (*.txt);;All files (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(m for _, m in self._log_buffer))
            self.set_status(f"Console saved: {path}")

    def _set_wrap(self, enabled):
        enabled = bool(enabled)
        try:
            self.log.setLineWrapMode(
                QPlainTextEdit.LineWrapMode.WidgetWidth if enabled
                else QPlainTextEdit.LineWrapMode.NoWrap)
            btn = getattr(self, "wrap_btn", None)
            if btn is not None:
                # Label shows the action the next click performs.
                btn.setText("Wrap" if not enabled else "NoWrap")
        except Exception:
            pass

    def _toggle_wrap(self):
        try:
            wrapping = (self.log.lineWrapMode()
                        == QPlainTextEdit.LineWrapMode.WidgetWidth)
        except Exception:
            wrapping = True
        self._set_wrap(not wrapping)

    def _console_wrap_enabled(self):
        try:
            return (self.log.lineWrapMode()
                    == QPlainTextEdit.LineWrapMode.WidgetWidth)
        except Exception:
            return False

    def _refresh_search_regex(self):
        """(Re)compile the search pattern; mark an invalid regex and match nothing."""
        self._console_regex_obj = None
        pattern = (self._console_search_text or "")
        if self._console_regex and pattern:
            rx = QRegularExpression(pattern)
            if rx.isValid():
                self._console_regex_obj = rx
        invalid = bool(self._console_regex and pattern
                       and self._console_regex_obj is None)
        self._mark_search_error(invalid)
        return invalid

    def _mark_search_error(self, on):
        """Flag the search box (red border + tooltip) for an invalid regex."""
        edit = getattr(self, "find_edit", None)
        if edit is None:
            return
        base = getattr(self, "_find_edit_base_qss", "")
        try:
            if on:
                edit.setStyleSheet(
                    base + f" QLineEdit {{ border:1px solid {C['err']}; }}")
                edit.setToolTip("Invalid regular expression")
            else:
                edit.setStyleSheet(base)
                edit.setToolTip("")
        except Exception:
            pass

    def _console_find_target(self):
        """Current find target: QRegularExpression, str, or None (no match)."""
        pattern = (self.find_edit.text() or "")
        if not pattern:
            return None
        if self._console_regex:
            return self._console_regex_obj  # None when invalid
        return pattern

    def _sync_console_chip(self, attr, checked):
        """Keep a checkable console chip in sync without re-emitting toggled.

        The chips are wired ``toggled -> _set_*`` (so a programmatic
        ``setChecked`` can drive the real mode); syncing therefore blocks
        signals and only touches the button when its state actually differs,
        which makes ``_set_*`` idempotent and recursion-safe.
        """
        btn = getattr(self, attr, None)
        if btn is None:
            return
        try:
            if btn.isChecked() != bool(checked):
                btn.blockSignals(True)
                try:
                    btn.setChecked(bool(checked))
                finally:
                    btn.blockSignals(False)
        except Exception:
            pass

    def _set_timestamps(self, enabled, persist=True):
        """Show/hide the render-only [HH:MM:SS] prefix (persisted)."""
        self._show_timestamps = bool(enabled)
        self._sync_console_chip("time_btn", self._show_timestamps)
        if persist:
            try:
                self.settings.setValue(
                    "console/timestamps", self._show_timestamps)
            except Exception:
                pass
        if getattr(self, "log", None) is not None:
            try:
                self._rebuild_console()
            except Exception:
                pass

    def _toggle_timestamps(self):
        self._set_timestamps(not getattr(self, "_show_timestamps", True))

    def _set_regex_mode(self, enabled, persist=True):
        """Interpret the search text as a regex (persisted)."""
        self._console_regex = bool(enabled)
        self._sync_console_chip("regex_btn", self._console_regex)
        if persist:
            try:
                self.settings.setValue("console/regex", self._console_regex)
            except Exception:
                pass
        try:
            self._refresh_search_regex()
        except Exception:
            pass
        if getattr(self, "log", None) is not None:
            try:
                self._rebuild_console()
            except Exception:
                pass

    def _toggle_regex_mode(self):
        self._set_regex_mode(not getattr(self, "_console_regex", False))

    def _console_context_menu(self, pos):
        try:
            menu = self._build_console_menu()
            menu.exec(self.log.mapToGlobal(pos))
        except Exception:
            pass

    def _focus_console_find(self):
        try:
            self.find_edit.setFocus()
            self.find_edit.selectAll()
        except Exception:
            pass

    def _build_console_menu(self):
        """Transcript right-click menu (state kept in sync with the chips)."""
        menu = QMenu(self)
        act_copy_sel = menu.addAction("Copy selection")
        act_copy_sel.setEnabled(bool(self.log.textCursor().hasSelection()))
        act_copy_sel.triggered.connect(self._copy_selection)
        act_copy_all = menu.addAction("Copy all")
        act_copy_all.triggered.connect(self._copy_console)
        act_save = menu.addAction("Save…")
        act_save.triggered.connect(self._save_console)
        act_clear = menu.addAction("Clear")
        act_clear.triggered.connect(self._clear_console)
        act_find = menu.addAction("Find…")
        act_find.triggered.connect(self._focus_console_find)
        menu.addSeparator()
        act_wrap = menu.addAction("Wrap lines")
        act_wrap.setCheckable(True)
        act_wrap.setChecked(self._console_wrap_enabled())
        act_wrap.toggled.connect(self._set_wrap)
        act_time = menu.addAction("Timestamps")
        act_time.setCheckable(True)
        act_time.setChecked(bool(getattr(self, "_show_timestamps", True)))
        act_time.toggled.connect(self._set_timestamps)
        act_regex = menu.addAction("Regex search")
        act_regex.setCheckable(True)
        act_regex.setChecked(bool(getattr(self, "_console_regex", False)))
        act_regex.toggled.connect(self._set_regex_mode)
        return menu

    def _console_search_matches(self, msg):
        """Filter predicate: case-insensitive substring or regex (invalid => no match)."""
        needle = (self._console_search_text or "").strip()
        if not needle:
            return True
        if self._console_regex:
            rx = self._console_regex_obj
            if rx is None:
                return False
            return rx.match(msg or "").hasMatch()
        return needle.lower() in (msg or "").lower()

    def _apply_console_search(self, text=None):
        """Filter visible console lines by the search text (buffer is retained;
        regex mode is honoured and an invalid pattern matches nothing)."""
        try:
            if text is None:
                text = self.find_edit.text()
            self._console_search_text = (text or "").strip()
        except Exception:
            self._console_search_text = ""
        try:
            self._refresh_search_regex()
        except Exception:
            pass
        try:
            self._rebuild_console()
        except Exception:
            try:
                self._apply_find()
            except Exception:
                pass

    # Backwards/alias entry points for the console search box.
    def _apply_search(self, text=None):
        return self._apply_console_search(text)

    def _apply_console_filter(self, text=None):
        return self._apply_console_search(text)

    def _filter_console(self, text=None):
        return self._apply_console_search(text)

    def _search_console(self, text=None):
        return self._apply_console_search(text)

    def _apply_find(self):
        selections = []
        try:
            target = self._console_find_target()
        except Exception:
            target = None
        if target is not None:
            doc = self.log.document()
            cursor = QTextCursor(doc)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(C["warn_dim"]))
            fmt.setForeground(QColor(C["warn"]))
            guard = 0
            while not cursor.isNull() and not cursor.atEnd():
                found = doc.find(target, cursor)
                if found.isNull():
                    break
                guard += 1
                if guard > 200000:
                    break
                if found.selectionStart() == found.selectionEnd():
                    # zero-width match — advance to avoid an infinite loop
                    nxt = QTextCursor(doc)
                    nxt.setPosition(found.selectionEnd() + 1)
                    if nxt.position() <= cursor.position():
                        break
                    cursor = nxt
                    continue
                sel = QTextEdit.ExtraSelection()
                sel.cursor = found
                sel.format = fmt
                selections.append(sel)
                cursor = found
        self.log.setExtraSelections(selections)

    def _find_nav(self, direction):
        try:
            target = self._console_find_target()
        except Exception:
            target = None
        if target is None:
            return
        doc = self.log.document()
        cur = self.log.textCursor()
        if direction > 0:
            found = doc.find(target, cur)
            if found.isNull():
                found = doc.find(target, QTextCursor(doc))
        else:
            start = QTextCursor(doc)
            start.setPosition(cur.selectionStart())
            found = doc.find(target, start, QTextDocument.FindFlag.FindBackward)
            if found.isNull():
                c = QTextCursor(doc)
                c.movePosition(QTextCursor.MoveOperation.End)
                found = doc.find(target, c, QTextDocument.FindFlag.FindBackward)
        if not found.isNull():
            self.log.setTextCursor(found)

    def set_status(self, msg):
        self.status.setText(msg)

    def _set_metric(self, name, value):
        if name in self.info:
            self.info[name].set(value)

    def _open_qr_generator(self):
        """QR Provision — the single MDM-via-QR entry point.

        Shows the TestDPC provisioning QR large by default; a dropdown at
        the bottom-left lists the two optional DPCs (Google Device Policy,
        FlashPilot). Picking one renders and shows its own QR. Payloads go
        through the Rust mdm_qr flow (spec-exact keys); a local APK is
        served when present."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, \
            QLabel as _QL, QComboBox
        from PyQt6.QtCore import QTimer as _QTimer
        dlg = QDialog(self)
        dlg.setWindowTitle("QR Provision")
        dlg.setModal(False)
        dlg.setMinimumSize(440, 680)
        dlg.setStyleSheet(f"background:{C['panel']}; color:{C['text']};")
        v = QVBoxLayout(dlg)
        v.setContentsMargins(18, 18, 18, 18)
        v.setSpacing(10)

        head = _QL("📷  QR Provision")
        head.setStyleSheet("font-size:14px; font-weight:800;")
        v.addWidget(head)
        sub = _QL(
            "Provisions a device owner from the setup wizard (tap the "
            "Welcome screen 6 times fast to open the QR scanner). The DPC "
            "completes setup and enables ADB; FRP/MDM clears once authorized.")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        v.addWidget(sub)

        img = _QL()
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setFixedHeight(300)
        img.setStyleSheet("background:#ffffff; border-radius:10px;")
        img.hide()
        v.addWidget(img)

        # Bottom-left: the two optional DPCs. TestDPC is the default QR, so
        # it is not listed — the box shows its placeholder until a pick.
        opt_row = QHBoxLayout()
        opt_row.setSpacing(8)
        opt_lbl = _QL("Other QR options")
        opt_lbl.setStyleSheet(f"color:{C['dim']}; font-size:11px; font-weight:700;")
        opt_row.addWidget(opt_lbl)
        dpc = QComboBox()
        dpc.setPlaceholderText("TestDPC (default)")
        dpc.addItem("Google Device Policy", "adp")
        dpc.addItem("FlashPilot DPC", "ours")
        dpc.setCurrentIndex(-1)
        self._style_combo(dpc)
        opt_row.addWidget(dpc, 1)
        v.addLayout(opt_row)

        info = _QL()
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{C['dim']}; font-size:11px;")
        v.addWidget(info)
        path_lbl = _QL()
        path_lbl.setWordWrap(True)
        path_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_lbl.setStyleSheet(f"color:{C['mute']}; font-size:10px; font-family:monospace;")
        v.addWidget(path_lbl)
        v.addStretch(1)
        # Tracks which QR is on screen so re-picking the same dropdown entry
        # can return to the default TestDPC QR.
        _shown = {"choice": "testdpc"}

        def work(choice):
            import os as _os
            from ..core import bridge as _bridge
            specs = {
                "testdpc": (
                    "com.afwsamples.testdpc/.DeviceAdminReceiver",
                    "mdm_qr/serve/testdpc.apk",
                    "https://play.google.com/store/apps/details?id=com.afwsamples.testdpc"),
                "adp": (
                    "com.google.android.apps.work.oobconfig/.DevAdminReceiver",
                    "",
                    "https://play.google.com/store/apps/details?id=com.google.android.apps.work.oobconfig"),
                "ours": (
                    "org.flashpilot.dpc/.FpAdminReceiver",
                    "mdm_qr/serve/flashpilot-dpc.apk",
                    ""),
            }
            component, local_apk, play_url = specs[choice]
            env = dict(_os.environ)
            env["MDM_COMPONENT"] = component
            env["MDM_QR_OUT_DIR"] = "mdm_qr"
            have_apk = bool(local_apk) and _os.path.isfile(local_apk)
            if have_apk:
                # LAN URL for the local APK + the v1 cert checksum the flow
                # puts into the QR extras.
                try:
                    env["FRP_DPC_APK_URL"] = (
                        f"http://{self._lan_ip()}:{self._QR_PORT}/"
                        f"{_os.path.basename(local_apk)}")
                    env["FRP_DPC_CERT_HASH"] = self._apk_cert_hash(local_apk)
                except Exception:
                    pass
            elif play_url:
                env["FRP_DPC_APK_URL"] = play_url
            if choice == "ours":
                mail = _os.environ.get("FP_ACCESS_EMAIL", "flashpilot@local")
                env["FRP_DPC_EXTRAS_JSON"] = (
                    '{"android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE":'
                    f'{{"fp_email":"{mail}"}}}}')
            out = _bridge._run(["flow-run", "mdm_qr"], timeout=60, env=env)
            if have_apk:
                self._serve_qr_dir("mdm_qr/serve")
            return choice, have_apk, out

        def on_done(res):
            choice, have_apk, out = res
            for line in (out or "").splitlines():
                self._ui.line.emit(line)
            # The flow prints the exact SVG path ("qr (svg): …").
            svg = ""
            for line in (out or "").splitlines():
                if "qr (svg):" in line:
                    svg = line.split("qr (svg):", 1)[1].strip()
            if not svg:
                svg = "mdm_qr/provisioning_qr_mdm.svg"
            import os as _os
            if not _os.path.isfile(svg):
                info.setText("Generation failed — see console.")
                return
            pix = self._render_svg(svg, 300)
            if pix is not None:
                img.setPixmap(pix)
                img.show()
            else:
                info.setText(f"QR written but not displayable:\n{svg}")
            _os_name = {"testdpc": "TestDPC", "adp": "Google Device Policy",
                        "ours": "FlashPilot DPC"}[choice]
            lines = [
                f"QR shown: {_os_name}"
                + (" (default)" if choice == "testdpc" else " (optional)"),
                "",
                "ON THE PHONE (setup wizard, same Wi-Fi as this PC):",
                "1. At the Welcome screen tap the same spot 6 times fast —"
                " the QR scanner opens (do NOT press Next).",
                "2. Scan this QR — the DPC installs as device owner.",
                "3. It completes setup + enables ADB (FlashPilot does it alone;"
                " TestDPC: finish provisioning in its screen).",
                "4. Tap OK on the ADB prompt, then run FRP/MDM remove.",
            ]
            if have_apk:
                lines.append(f"APK served on :{self._QR_PORT} (verified live).")
            info.setText("\n".join(lines))
            path_lbl.setText(svg)

        def on_err(e):
            info.setText(f"Generation failed: {e}")

        def do_gen(choice):
            info.setText("Generating …")
            dpc.setEnabled(False)
            import threading as _th

            def runner():
                try:
                    res = work(choice)
                    self._ui.ui.emit(lambda: on_done(res))
                except Exception as e:  # noqa: BLE001
                    self._ui.ui.emit(lambda e=e: on_err(e))
                finally:
                    self._ui.ui.emit(lambda: dpc.setEnabled(True))
            _th.Thread(target=runner, daemon=True).start()

        def _picked(_idx=0):
            choice = dpc.currentData()
            if not choice:
                return
            if choice == _shown["choice"]:
                # Picking the same option again goes back to the default QR.
                dpc.setCurrentIndex(-1)
                _shown["choice"] = "testdpc"
                do_gen("testdpc")
                return
            _shown["choice"] = choice
            do_gen(choice)
        dpc.activated.connect(_picked)

        # Default: show the TestDPC QR immediately.
        _QTimer.singleShot(0, lambda: do_gen("testdpc"))
        dlg.show()

    _QR_PORT = 8000

    def _lan_ip(self):
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _apk_cert_hash(self, apk):
        """SHA-256 (base64url) of the APK's v1 signing cert — the same
        chain build.sh and the Rust flow use (openssl needs -out for DER)."""
        import base64, hashlib, subprocess, tempfile, os as _os
        rsa = subprocess.run(["unzip", "-p", apk, "META-INF/*.RSA"],
                             capture_output=True).stdout
        if not rsa:
            return ""
        tmp = tempfile.NamedTemporaryFile(suffix=".der", delete=False)
        tmp.close()
        subprocess.run(["openssl", "pkcs7", "-inform", "DER", "-in", "/dev/stdin",
                        "-print_certs", "-outform", "DER", "-out", tmp.name],
                       input=rsa, capture_output=True)
        cert = open(tmp.name, "rb").read()
        _os.unlink(tmp.name)
        if not cert:
            return ""
        h = hashlib.sha256(cert).digest()
        return base64.urlsafe_b64encode(h).decode().rstrip("=")

    def _serve_qr_dir(self, directory):
        """Spawn the static server for the phone download (skip if up)."""
        import socket, subprocess
        try:
            s = socket.create_connection(("127.0.0.1", self._QR_PORT), timeout=0.5)
            s.close()
            return  # already serving
        except Exception:
            pass
        subprocess.Popen(
            ["python3", "-m", "http.server", str(self._QR_PORT),
             "--directory", directory],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

    def _render_svg(self, path, size):
        """SVG -> QPixmap via QtSvg (QPixmap can't rasterize SVG alone)."""
        try:
            from PyQt6.QtSvg import QSvgRenderer
            from PyQt6.QtGui import QPixmap, QPainter
            r = QSvgRenderer(path)
            if not r.isValid():
                return None
            pix = QPixmap(size, size)
            pix.fill(Qt.GlobalColor.white)
            p = QPainter(pix)
            r.render(p)
            p.end()
            return pix
        except Exception:
            return None

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
            # Flow-generated QRs are SVG: QPixmap alone cannot rasterize
            # them — use the QSvgRenderer helper first, PNG as fallback.
            pix = self._render_svg(path, 300)
            if pix is not None:
                img.setPixmap(pix)
                img.setVisible(True)
            else:
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
        try:
            getattr(self._toasts, f"show_{kind}")(title, detail)
        except Exception:
            # Fallback if toast host not yet ready
            pass

    # Compatibility alias: legacy code calls show_toast(title, kind) or
    # show_toast(title, detail, kind). Normalizes to _show_toast.
    def show_toast(self, title, detail_or_kind="", kind=None):
        try:
            # 3-arg form: show_toast(title, detail, kind)
            if kind is not None:
                detail = detail_or_kind
                k = kind
            else:
                # 2-arg form: second arg may be kind (success/warning/error)
                if detail_or_kind in ("success", "ok", "warn", "warning", "error", "err", "info"):
                    k = detail_or_kind
                    detail = ""
                else:
                    k = "info"
                    detail = detail_or_kind
            # normalize kind
            if k in ("success", "ok"):
                k = "ok"
            elif k in ("warning", "warn"):
                k = "warn"
            elif k in ("error", "err"):
                k = "err"
            else:
                k = "info" if k not in ("ok", "warn", "err", "info") else k
            self._show_toast(k, str(title), str(detail) if detail else "")
        except Exception:
            pass

    def _append_console(self, msg):
        """Legacy alias – some flows called _append_console; wrap to log_line."""
        try:
            self.log_line(str(msg))
        except Exception:
            pass

    def _run_on_ui(self, fn):
        try:
            fn()
        except Exception as e:
            # Never let a UI callback crash the app – log and continue
            try:
                self.log_line(f"[error] UI callback failed: {e}")
            except Exception:
                pass

    # ----------------------------- device state ---------------------------
    def _on_device_state(self, state):
        if "error" in state:
            # Sticky connection: a scan error (even after consecutive failed
            # polls) must not visually drop a device we saw connected moments
            # ago - that is the exact flap users report. Keep the orb/scene
            # lit and show re-scanning instead; the next good poll restores
            # the exact state.
            if getattr(self, "_last_conn", False) or getattr(self, "_device_connected", False):
                self.conn_state.setText("Re-scanning USB ... (last scan failed)")
                return
            self.badge.set_state(None)
            self.orb.set_connected(False)
            self.scene.set_connected(False)
            self.scene.set_vendor(None)
            self._set_conn_glow(C["border_hi"])
            self.conn_state.setText(f"Scan error: {state['error']}")
            self._update_device_info(False, None, None)
            try:
                if self.settings.value("animations", "true", type=bool):
                    from .animations import Motion
                    Motion.cable_shake(self.scene, amp=6, dur=420)
            except Exception:
                pass
            return
        samsung = state["samsung"]
        mtk_devs = state.get("mtk", [])
        fastboot = state.get("fastboot", [])
        edl_devs = state.get("edl", [])
        qcom_devs = state.get("qcom", [])
        spd_devs = state.get("spd", [])
        apple_devs = state.get("apple", [])
        other_android = state.get("other_android", [])
        adb_devs = state.get("adb", [])
        mode = state["mode"]
        self.badge.set_state(mode)
        self._last_spd_target = (
            f"{spd_devs[0]['bus']}:{spd_devs[0]['address']}" if spd_devs else None
        )
        motorola_devs = state.get("motorola", [])
        connected_any = bool(fastboot or samsung or mtk_devs or edl_devs or qcom_devs or spd_devs or apple_devs or motorola_devs or other_android or adb_devs)
        self._accent_strip.set_active(connected_any)

        # Track ADB exposure for lazy probing - don't spawn adb server at startup for non-ADB devices
        has_adb_iface = any(_has_adb_iface(d) for d in samsung) or any(_has_adb_iface(d) for d in other_android)
        self._last_has_adb = bool(adb_devs) or has_adb_iface or (mode and "ADB" in mode.upper())

        # toast on connect / disconnect transitions
        if connected_any and not getattr(self, "_last_conn", False):
            self._toasts.show_ok("Device connected", mode or "USB device detected")
        elif not connected_any and getattr(self, "_last_conn", False):
            self._toasts.show_info("Device disconnected")
            try:
                if self.settings.value("animations", "true", type=bool):
                    from .animations import Motion
                    Motion.cable_shake(self.scene, amp=5, dur=360)
            except Exception:
                pass
        self._last_conn = connected_any

        # Phase-1 device-first: live strip + dimming on every monitor tick
        # (cheap: the detect cache TTL absorbs the 3s poll cadence).
        try:
            self.update_device_strip()
        except Exception:
            pass

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
            fb_fallback = (d.get("product") or d.get("manufacturer") or "").strip() or None
            if fb_fallback and fb_fallback.lower() == "adb":
                fb_fallback = None
            self._update_device_info(True, d["pid"], mode, fallback_model=fb_fallback)
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
            sam_fallback = (first.get("product") or first.get("manufacturer") or "").strip() or None
            if sam_fallback and sam_fallback.lower() in ("adb", "samsung_android", "samsung android"):
                sam_fallback = None
            # Prefer cached model, otherwise product string as immediate placeholder (better than "--")
            self._update_device_info(True, first["pid"], mode, fallback_model=sam_fallback)
            ov = _adb_overlay(adb_devs, first)
            if ov:
                self.conn_state.setText(self.conn_state.text() + ov)
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
            edl_fallback = (d.get("product") or d.get("manufacturer") or "").strip() or None
            if edl_fallback and edl_fallback.lower() == "adb":
                edl_fallback = None
            self._update_device_info(True, pid, mode, fallback_model=edl_fallback)
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
            qcom_fallback = (d.get("product") or d.get("manufacturer") or "").strip() or None
            if qcom_fallback and qcom_fallback.lower() == "adb":
                qcom_fallback = None
            self._update_device_info(True, pid, mode, fallback_model=qcom_fallback)
            ov = _adb_overlay(adb_devs, d)
            if ov:
                self.conn_state.setText(self.conn_state.text() + ov)
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
            spd_fallback = (d.get("product") or d.get("manufacturer") or "").strip() or None
            if spd_fallback and spd_fallback.lower() == "adb":
                spd_fallback = None
            self._update_device_info(True, pid, mode, fallback_model=spd_fallback)
            ov = _adb_overlay(adb_devs, d)
            if ov:
                self.conn_state.setText(self.conn_state.text() + ov)
        elif mtk_devs:
            d = mtk_devs[0]
            pid = d.get("pid")
            stage = {0x0003: "MediaTek BROM", 0x2000: "MediaTek Preloader",
                     0x0004: "MediaTek Download Agent",
                     0x1004: "MediaTek Download Agent"}.get(
                pid, "MediaTek device (normal boot)")
            self.orb.set_connected(True)
            self.scene.set_connected(True)
            mfr = d.get("manufacturer") or ""
            prod = d.get("product") or ""
            mfr_lower = mfr.lower()
            prod_lower = prod.lower()
            is_samsung_mtk = "samsung" in mfr_lower or "samsung" in prod_lower
            
            # Use actual manufacturer/product for vendor badge
            if is_samsung_mtk:
                self.scene.set_vendor("SAMSUNG (MTK)", C["warn"])
                vendor_display = "SAMSUNG"
            elif mfr and prod:
                vendor_display = f"{mfr} {prod}"
                self.scene.set_vendor(vendor_display.upper(), C["ok"])
            elif prod:
                vendor_display = prod
                self.scene.set_vendor(vendor_display.upper(), C["ok"])
            elif mfr:
                vendor_display = mfr
                self.scene.set_vendor(vendor_display.upper(), C["ok"])
            else:
                self.scene.set_vendor("MEDIATEK", C["warn"])
                vendor_display = "MEDIATEK"
            
            self._set_conn_glow(C["warn"])
            self.conn_state.setText(
                f"0e8d:{pid:04x} · {stage}\n{vendor_display}\nbus {d['bus']} · addr {d['address']}"
            )
            self.conn_state.setStyleSheet(
                f"color:{C['warn']}; font-size:12px; font-weight:600; background:transparent;"
            )
            # For MTK, also supply fallback from product/manufacturer so model not "--"
            mtk_fallback = (d.get("product") or d.get("manufacturer") or vendor_display or "").strip() or None
            if mtk_fallback and mtk_fallback.lower() == "adb":
                mtk_fallback = None
            self._update_device_info(True, pid, mode, fallback_model=mtk_fallback)
            ov = _adb_overlay(adb_devs, d)
            if ov:
                self.conn_state.setText(self.conn_state.text() + ov)
        elif apple_devs:
            d = apple_devs[0]
            pid = d.get("pid")
            self.orb.set_connected(True)
            self.scene.set_connected(True)
            self.scene.set_vendor("APPLE", C["warn"])
            self._set_conn_glow(C["warn"])
            self.conn_state.setText(
                f"05ac:{pid:04x} · Apple\nbus {d['bus']} · addr {d['address']}"
            )
            self.conn_state.setStyleSheet(
                f"color:{C['warn']}; font-size:12px; font-weight:600; background:transparent;"
            )
            apple_fallback = (d.get("product") or d.get("manufacturer") or "").strip() or None
            if apple_fallback and apple_fallback.lower() == "adb":
                apple_fallback = None
            self._update_device_info(True, pid, mode, fallback_model=apple_fallback)
        elif motorola_devs:
            d = motorola_devs[0]
            pid = d.get("pid")
            mfr = d.get("manufacturer") or ""
            prod = d.get("product") or ""
            self.orb.set_connected(True)
            self.scene.set_connected(True)
            vendor_display = (prod or mfr or "MOTOROLA")
            self.scene.set_vendor(vendor_display.upper(), C["accent_hi"])
            self._set_conn_glow(C["accent_hi"])
            self.conn_state.setText(
                f"{d.get('vid', 0):04x}:{pid:04x} · Motorola\n{prod or mfr}\nbus {d['bus']} · addr {d['address']}"
            )
            self.conn_state.setStyleSheet(
                f"color:{C['accent_hi']}; font-size:12px; font-weight:600; background:transparent;"
            )
            moto_fallback = (d.get("product") or d.get("manufacturer") or "").strip() or None
            if moto_fallback and moto_fallback.lower() == "adb":
                moto_fallback = None
            if moto_fallback is None and self._cached_model:
                moto_fallback = self._cached_model
            self._update_device_info(True, pid, mode, fallback_model=moto_fallback)
            ov = _adb_overlay(adb_devs, d)
            if ov:
                self.conn_state.setText(self.conn_state.text() + ov)
        elif other_android:
            d = other_android[0]
            pid = d.get("pid")
            mfr = d.get("manufacturer") or ""
            prod = d.get("product") or ""
            self.orb.set_connected(True)
            self.scene.set_connected(True)
            vendor_display = (prod or mfr or "ANDROID")
            self.scene.set_vendor(vendor_display.upper(), C["ok"])
            self._set_conn_glow(C["ok"])
            self.conn_state.setText(
                f"{d.get('vid', 0):04x}:{pid:04x} · Android\n{prod or mfr}\nbus {d['bus']} · addr {d['address']}"
            )
            self.conn_state.setStyleSheet(
                f"color:{C['ok']}; font-size:12px; font-weight:600; background:transparent;"
            )
            android_fallback = (d.get("product") or d.get("manufacturer") or "").strip() or None
            if android_fallback and android_fallback.lower() == "adb":
                android_fallback = None
            if android_fallback is None and self._cached_model:
                android_fallback = self._cached_model
            self._update_device_info(True, pid, mode, fallback_model=android_fallback)
            ov = _adb_overlay(adb_devs, d)
            if ov:
                self.conn_state.setText(self.conn_state.text() + ov)
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
            # Pre-parse model from adb extra for immediate display (no shell needed)
            import re as _re
            adb_extra = d.get("extra", "")
            adb_fallback = None
            if adb_extra:
                for _k in ("model", "product"):
                    _m = _re.search(rf"{_k}:([^\s]+)", adb_extra)
                    if _m:
                        _cand = _m.group(1).replace("_", "-").strip()
                        if _cand and _cand.lower() != "adb":
                            adb_fallback = _cand
                            break
            if not adb_fallback and self._cached_model:
                adb_fallback = self._cached_model
            # Even when ADB is unauthorized, model is still readable via USB/MTP without ADB shell
            if not adb_fallback:
                try:
                    # Target the actual phone device (ADB/MTP), not siblings like a card reader
                    _tgt_dev = _find_target_device()
                    if _tgt_dev:
                        _cand = (_tgt_dev.get("product") or _tgt_dev.get("manufacturer") or "").strip()
                        if _cand and _cand.lower() not in ("adb", "samsung_android", "samsung android", ""):
                            adb_fallback = _cand
                        # Also stash the real serial so it isn't clobbered by a reader's serial
                        _ser = (_tgt_dev.get("serial") or "").strip()
                        if _ser:
                            try:
                                self._cached_serial = _ser
                            except Exception:
                                pass
                except Exception:
                    pass
            self._update_device_info(True, None, mode, fallback_model=adb_fallback)
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
        # Multi-device list refresh (additive — never disturbs the single-
        # device display above). Keeps the inspected row if still present.
        # Change-detection cadence: detect-merged is heavier than detect-all
        # (the native ADB probe costs up to ~6s per ADB-mode device), so the
        # merged rebuild only runs when the device set actually changes —
        # not on every 3s poll. Keys are Rust-stable (usb:<ports> /
        # adb:<serial>), so a re-enumeration that keeps the physical port
        # still counts as "unchanged" and keeps the inspected row selected.
        try:
            sig = (
                mode,
                tuple(sorted(
                    f"{d.get('vid', 0):04x}:{d.get('pid', 0):04x}@{d.get('bus')}:{d.get('address')}"
                    for d in (samsung + mtk_devs + fastboot + edl_devs + qcom_devs + spd_devs + apple_devs + other_android)
                )),
                tuple(sorted(str(a.get("serial", "")) for a in adb_devs)),
            )
        except Exception:
            sig = None
        if sig != getattr(self, "_last_device_list_sig", None):
            self._last_device_list_sig = sig
            try:
                self._refresh_device_list()
            except Exception:
                pass

    def _refresh_device_list(self):
        """Rebuild the connection-bar device list from devices.list_devices().

        The rebuild fires on the monitor's change-detection — i.e. right
        after the monitor SAW a device set. But this second live scan can
        hit a re-enumeration window and drop a device the monitor just
        saw (the exact "not allowing switching between devices" report:
        both phones were in the monitor state, one row rendered). Retry
        once when the scan returns fewer devices than the monitor state;
        a persistent absence renders honestly."""
        rows = []
        try:
            rows = _devices.list_devices()
        except Exception:
            rows = []
        # Monitor-state distinct-device count (what the rebuild was
        # triggered by). Merged USB rows and adb rows describe the SAME
        # phone, so count distinct serials across categories; serialless
        # devices count individually.
        try:
            mon = getattr(self, "_monitor", None)
            mon_state = getattr(mon, "_last_state", None) if mon else None
            mon_keys = set()
            if mon_state:
                for k in ("samsung", "mtk", "fastboot", "edl", "qcom",
                          "spd", "apple", "other_android"):
                    for d in (mon_state.get(k) or []):
                        if not isinstance(d, dict):
                            continue
                        s = (d.get("serial") or "").strip()
                        if s:
                            mon_keys.add(f"adb:{s}")
                        else:
                            # serialless: key on vid:pid@bus:addr snapshot
                            mon_keys.add(
                                f"usb:{d.get('vid', 0):04x}:{d.get('pid', 0):04x}"
                                f"@{d.get('bus')}:{d.get('address')}")
                for a in (mon_state.get("adb") or []):
                    if isinstance(a, dict) and a.get("serial"):
                        mon_keys.add(f"adb:{a['serial']}")
            if mon_keys and len({r.get("key") for r in rows if r.get("key")}) < len(mon_keys):
                import time as _t
                self._ui.line.emit(
                    f"[info] device list: scan saw {len(rows)} of "
                    f"{len(mon_keys)} devices (re-enumerating?) — "
                    "settling 2.5s and retrying ...")
                _t.sleep(2.5)
                try:
                    rows = _devices.list_devices()
                except Exception:
                    pass
        except Exception:
            pass
        keys = {r.get("key") for r in rows if r.get("key")}
        if self._display_key not in keys:
            self._display_key = rows[0]["key"] if rows else None
        try:
            self.device_list.blockSignals(True)
            self.device_list.clear()
            self._row_widgets = {}
            for r in rows:
                transports = ", ".join(r.get("transports", []))
                key = r.get("key")
                # Per-row job-state chip: text + foreground color driven by
                # the JobManager (no setItemWidget — widget rows crash the
                # offscreen compositor). The chip suffix shows RUNNING
                # while a job is active on this device; the row colors
                # follow the job state.
                item = QListWidgetItem(f"{r.get('label', '?')}  [{transports}]")
                item.setData(Qt.ItemDataRole.UserRole, key)
                self.device_list.addItem(item)
                self._row_widgets[key] = (item, f"{r.get('label', '?')}  [{transports}]")
                if key == self._display_key:
                    self.device_list.setCurrentItem(item)
        finally:
            try:
                self.device_list.blockSignals(False)
            except Exception:
                pass
        # Only override the single-device chain display when several phones
        # are attached (that display is first-match and ambiguous then).
        if self._display_key and len(rows) > 1:
            self._show_device_row(self._display_key)
        # Capability display-gating follows the list rebuild (fail-open).
        try:
            self._refresh_gates()
        except Exception:
            pass

    def _refresh_row_states(self):
        """Drive the per-row job chips from the JobManager (no scans).

        Text + color, no setItemWidget (widget rows crash the offscreen
        compositor): RUNNING colors the row accent with a ● suffix,
        terminal states color the row, idle renders plain.
        """
        try:
            widgets = getattr(self, "_row_widgets", None) or {}
            if not widgets:
                return
            active = {j.device_key for j in jobs.active_jobs() if j.device_key}
            from PyQt6.QtGui import QColor
            for key, (item, base_text) in widgets.items():
                try:
                    if key in active:
                        if "● RUNNING" not in item.text():
                            item.setText(f"{base_text}  ● RUNNING")
                        item.setForeground(QColor("#38bdf8"))
                    else:
                        item.setText(base_text)
                        item.setForeground(QColor("#e2e8f0"))
                except RuntimeError:
                    # The row was removed by a rebuild between ticks.
                    continue
        except Exception:
            pass

    def _on_device_picked(self, item):
        """Connection-bar click: inspect that device in the tiles/scene."""
        try:
            self._display_key = item.data(Qt.ItemDataRole.UserRole)
            self._show_device_row(self._display_key)
            self._refresh_gates()
        except Exception:
            pass

    def _show_device_row(self, key):
        """Render one list_devices() row into orb/scene/tiles (display only)."""
        rows = []
        try:
            rows = _devices.list_devices()
        except Exception:
            return
        row = next((r for r in rows if r.get("key") == key), None)
        if row is None:
            return
        try:
            self.orb.set_connected(True)
            self.scene.set_connected(True)
            transports = row.get("transports", []) or ["USB"]
            self.scene.set_vendor(transports[0].upper(), C["ok"])
            self._set_conn_glow(C["ok"])
            self.conn_state.setText(row.get("label", key))
            self.conn_state.setStyleSheet(
                f"color:{C['ok']}; font-size:12px; font-weight:600; background:transparent;"
            )
            # The ModeBadge (top bar, near Stop) follows the SELECTED
            # device: it previously showed the whole-bus mode, so a
            # Qualcomm-normal setup kept reading MTP even after switching
            # to a phone in ADB mode.
            badge_mode = {
                "ADB": "ADB ENABLED (debug composite) - normal boot",
                "FASTBOOT": "FASTBOOT MODE (bootloader unlocked / fastboot)",
                "Download mode": "DOWNLOAD MODE (Samsung Odin / Download)",
                "Samsung BROM": "SAMSUNG BROM",
                "MTK BROM": "MTK BROM (bootrom)",
                "MTK": "MTK (download agent)",
                "EDL": "EDL MODE (Qualcomm Emergency Download)",
                "SPD": "SPD DOWNLOAD (Unisoc download mode)",
                "MTP": "MTP (media transfer)",
                "USB": "USB DEVICE (vendor-specific / diag)",
            }.get(transports[0], transports[0])
            try:
                self.badge.set_state(badge_mode)
            except Exception:
                pass
            usb = row.get("usb") or {}
            adb = row.get("adb") or {}
            serial = (usb.get("serial") or adb.get("serial") or "--").strip() or "--"
            model = (usb.get("product") or usb.get("manufacturer") or "--").strip() or "--"
            try:
                self.info["Serial"].set(serial)
                self.info["Device Model"].set(model)
                self.info["USB Mode"].set(", ".join(transports))
                if adb:
                    self.info["ADB Status"].set(adb.get("state", "--"))
            except Exception:
                pass
        except Exception:
            pass

    def _update_device_info(self, connected, pid, mode, fallback_model=None):
        if not connected:
            self._cached_model = None
            self._cached_adb_status = None
            self._cached_build = None
            self._cached_android = None
            self._cached_serial = None
            self._model_refresh_in_progress = False
            self._last_pid = None
            self._device_connected = False
            self._last_has_adb = False
            self._last_usb_product = None
            try:
                self._detailed_logged = False
                self._usb_dumped = False
                self._last_logged_model = None
            except Exception:
                pass
            for name in self.info:
                self.info[name].set("--")
            return

        self._last_pid = pid
        self._device_connected = True
        if fallback_model:
            self._last_usb_product = fallback_model
        # Show known model immediately from USB/MTP without waiting for
        # background ADB/AT probe - avoids "--" flash and hard-coded "adb".
        immediate = self._cached_model or fallback_model
        if immediate is None:
            immediate = f"0x{pid:04x}" if pid is not None else "--"
        # Guard: never show literal "adb" as model
        if isinstance(immediate, str) and immediate.strip().lower() == "adb":
            immediate = f"0x{pid:04x}" if pid is not None else "--"
        self.info["Device Model"].set(immediate)
        # USB Mode can be long (e.g. "ADB PRESENT - UNAUTHORIZED (allow USB debugging on phone)") — let MetricCard word-wrap handle it, don't truncate
        self.info["USB Mode"].set(mode or "--")
        self.info["Interface"].set("USB")
        # Keep phone image vendor in sync with Device Model (user expects model on phone graphic)
        try:
            if hasattr(self, "scene") and self.scene and immediate not in ("--",) and not immediate.startswith("0x"):
                if not (mode and any(k in mode.upper() for k in ("RECOVERY", "FASTBOOT", "EDL", "SPREADTRUM", "BROM", "PRELOADER", "DOWNLOAD"))):
                    if immediate.strip().lower() not in ("samsung", "mediatek", "qualcomm", "adb"):
                        self.scene.set_vendor(immediate.upper(), C["ok"])
                        # Also ensure cached model reflects immediate for later background refinement
                        if not self._cached_model:
                            self._cached_model = immediate
        except Exception:
            pass
        # Defer ADB-heavy probe: only query ADB when device actually
        # exposes ADB (has_adb or mode contains ADB). Non-ADB devices get
        # model via USB/MTP/AT without spawning adb server at startup.
        should_probe_adb = bool(self._last_has_adb or (mode and "ADB" in mode.upper()))
        # Always allow a lightweight non-ADB refresh (USB product/AT) even
        # without ADB, but skip heavy adb shell when not needed.
        self._refresh_model_and_adb(probe_adb=should_probe_adb)

    def _refresh_model_and_adb(self, probe_adb=None):
        """Background probe for the real model + adb state. Reruns on a timer
        so it picks up the phone's 'Allow USB debugging' acceptance without
        needing a USB re-enumeration."""
        if self._model_refresh_in_progress:
            return
        if not getattr(self, "_device_connected", False):
            return
        # Lazy ADB: don't spawn `adb start-server` at startup for non-ADB devices
        if probe_adb is None:
            probe_adb = bool(getattr(self, "_last_has_adb", False))
        self._model_refresh_in_progress = True
        pid = self._last_pid
        # Remember whether this refresh should query ADB (used inside work)
        probe_adb_flag = probe_adb
        current_adb = self.info["ADB Status"].value.text()
        # Only show a transient "Checking..." on the first resolution; keep the
        # last known value afterwards so the metric does not flicker every poll.
        if probe_adb_flag and self._cached_adb_status is None and not current_adb.startswith("Connected"):
            self.info["ADB Status"].set("Checking...")
        elif not probe_adb_flag and self._cached_adb_status is None:
            # For non-ADB devices keep status as Not connected without "Checking..."
            if current_adb.strip() in ("--", ""):
                self.info["ADB Status"].set("Not connected")

        def work():
            model = ""
            mfr = ""
            brand = ""
            build_id = ""
            android_ver = ""
            serial_prop = ""
            adb_status = "Not connected"
            adb_devs = []
            if probe_adb_flag:
                # Reuse the DeviceMonitor's fresh state instead of another
                # native probe: this ran on the 3s timer and every extra
                # adb_status was another CNXN session per tick (on devices
                # whose adbd resets its USB function on our CNXN that
                # re-enumerates the phone every cycle). The monitor state is
                # <=3s old and costs zero extra USB I/O.
                mon = getattr(self, "_monitor", None)
                mon_state = getattr(mon, "_last_state", None) if mon else None
                if mon_state is not None:
                    adb_devs = list(mon_state.get("adb") or [])
                else:
                    try:
                        # Presence (see DeviceMonitor): this display path
                        # must not natively probe.
                        adb_devs = bridge.adb_presence_status()
                    except bridge.BridgeError:
                        adb_devs = []
                        adb_status = "Error"
            else:
                # Lightweight poll: keep adb_status as Not connected without spawning adb server
                # Still try to refresh model via non-ADB paths (MTP/USB/AT) below
                adb_devs = []
                adb_status = "Not connected"
            try:
                authorized = [d for d in adb_devs if d["state"] == "device"]
                # Displayed-device preference + absence detection: when the
                # inspected device is off the bus (re-enumerating?), keep
                # its row's static tiles — never render another device's
                # identity under the selected row (the "switch falls back
                # to the first phone" report).
                disp = getattr(self, "_display_key", None)
                disp_serial = (disp[4:] if isinstance(disp, str)
                               and disp.startswith("adb:") else None)
                displayed_absent = bool(
                    disp_serial and not any(
                        d.get("serial") == disp_serial for d in authorized))
                if authorized and not displayed_absent:
                    serial = authorized[0]["serial"]
                    # Prefer the DISPLAYED device: this 3s refresh must
                    # render the device the user is inspecting, not the
                    # first authorized (clicking the modem then fell back
                    # to the first phone's identity every cycle).
                    try:
                        if disp_serial and any(
                                d["serial"] == disp_serial for d in authorized):
                            serial = disp_serial
                    except Exception:
                        pass
                    # The displayed device's extra (fallback model source):
                    # authorized[0]'s extra belongs to the first phone and
                    # reverted the tiles when the displayed getprops were
                    # empty.
                    try:
                        want = serial
                        extra = next(
                            (d.get("extra", "") for d in authorized
                             if d.get("serial") == want),
                            authorized[0].get("extra", ""))
                    except Exception:
                        extra = authorized[0].get("extra", "")
                    adb_status = f"Connected ({serial})"
                    # Device info (model/build/android) never changes every
                    # 3s - fetch it only when the authorized serial changes
                    # or on first resolution. Each getprop poll was 6 native
                    # ADB sessions per timer tick; on devices whose adbd
                    # resets its USB function on our CNXN that re-enumerates
                    # the phone 6x per cycle (the address storm).
                    if serial != getattr(self, "_last_props_serial", None) or not self._cached_model:
                        self._last_props_serial = serial
                        try:
                            # Pin the whole burst to this serial: per-call
                            # re-resolution could otherwise hop phones
                            # mid-burst when several are authorized.
                            # rescue=False: this is the passive poll timer - a
                            # busy claim (system adb server holds the interface)
                            # must fail fast into the fallbacks below, never
                            # kill-server (the phone re-enumerates every time).
                            model = bridge.adb_shell(
                                "getprop ro.product.model", timeout=8, rescue=False, serial=serial
                            ).strip()
                            mfr = bridge.adb_shell(
                                "getprop ro.product.manufacturer", timeout=8, rescue=False, serial=serial
                            ).strip()
                            brand = bridge.adb_shell(
                                "getprop ro.product.brand", timeout=8, rescue=False, serial=serial
                            ).strip()
                            # Extended device info: build, android, serial
                            build_id = bridge.adb_shell(
                                "getprop ro.build.display.id", timeout=8, rescue=False, serial=serial
                            ).strip() or bridge.adb_shell(
                                "getprop ro.build.version.incremental", timeout=8, rescue=False, serial=serial
                            ).strip()
                            android_ver = bridge.adb_shell(
                                "getprop ro.build.version.release", timeout=8, rescue=False, serial=serial
                            ).strip()
                            sdk_ver = bridge.adb_shell(
                                "getprop ro.build.version.sdk", timeout=8, rescue=False, serial=serial
                            ).strip()
                            # Prefer ro.serialno, fallback to adb serial
                            serial_prop = bridge.adb_shell(
                                "getprop ro.serialno", timeout=8, rescue=False, serial=serial
                            ).strip() or serial
                            if android_ver and sdk_ver:
                                android_ver = f"{android_ver} (API {sdk_ver})"
                        except bridge.BridgeError:
                            model = ""
                            mfr = ""
                            brand = ""
                            build_id = ""
                            android_ver = ""
                            serial_prop = serial
                    # Cache extended info for metrics
                    if 'build_id' not in locals():
                        build_id = ""
                    if 'android_ver' not in locals():
                        android_ver = ""
                    if 'serial_prop' not in locals():
                        serial_prop = serial
                    # Fallback: parse model from `adb devices -l` extra field
                    # e.g. "model:SM_G991B device:..." when getprop is blocked
                    if not model and extra:
                        import re
                        for key in ("model", "product"):
                            m = re.search(rf"{key}:([^\s]+)", extra)
                            if m:
                                cand = m.group(1).replace("_", "-")
                                if cand and cand.lower() != "adb":
                                    model = cand
                                    break
                    # Fallback: USB descriptor product/manufacturer strings (target the phone, not a reader)
                    if not model:
                        try:
                            _tgt_dev = _find_target_device()
                            if _tgt_dev:
                                prod = (_tgt_dev.get("product") or "").strip()
                                mf = (_tgt_dev.get("manufacturer") or "").strip()
                                if prod and prod.lower() != "adb":
                                    model = prod
                                if not mfr and mf:
                                    mfr = mf
                                _ser = (_tgt_dev.get("serial") or "").strip()
                                if _ser and not serial_prop:
                                    serial_prop = _ser
                        except Exception:
                            pass
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
                elif displayed_absent:
                    # The inspected device is off the bus (re-enumerating?):
                    # keep its row's static tiles — never render another
                    # device's identity under the selected row.
                    adb_status = f"Not connected ({disp_serial})"
                    self._cached_adb_status = adb_status
                    self._ui.metric.emit("ADB Status", adb_status)
                    return
                elif any(d["state"] == "unauthorized" for d in adb_devs):
                    adb_status = "Unauthorized - tap Allow"
                    # Throttle console spam: only log once per state change
                    if self._cached_adb_status != adb_status:
                        self._ui.line.emit(
                            "ADB: device present but NOT authorized - tap Allow on the phone"
                        )
                    # Heavy probes (getprop / MTP) run ONCE per serial: every
                    # 3s retry was more device I/O per tick (native sessions
                    # on the poll timer) and never succeeded while busy -
                    # the per-serial flag stops the churn. Re-armed when the
                    # user taps Allow (the authorized branch fetches props).
                    _unauth_serial = next(
                        (d["serial"] for d in adb_devs if d["state"] == "unauthorized"), "")
                    _props_tried = getattr(self, "_unauth_props_tried_serial", None)
                    if (not build_id or not android_ver) and _props_tried != _unauth_serial:
                        self._unauth_props_tried_serial = _unauth_serial
                        try:
                            # Try ADB getprop even when unauthorized — sometimes ro.build still answers
                            # (rescue=False: passive poll timer - busy must fail fast, never kill-server.
                            # Pinned to the unauthorized serial: unscoped calls could otherwise
                            # hop phones mid-burst when several are attached.)
                            _userial = _unauth_serial or None
                            cand_build = bridge.adb_shell("getprop ro.build.display.id", timeout=5, rescue=False, serial=_userial).strip()
                            if not cand_build:
                                cand_build = bridge.adb_shell("getprop ro.build.version.incremental", timeout=5, rescue=False, serial=_userial).strip()
                            if cand_build and cand_build.lower() != "adb":
                                build_id = cand_build
                            cand_and = bridge.adb_shell("getprop ro.build.version.release", timeout=5, rescue=False, serial=_userial).strip()
                            if cand_and:
                                # Also try sdk for API level
                                try:
                                    cand_sdk = bridge.adb_shell("getprop ro.build.version.sdk", timeout=5, rescue=False, serial=_userial).strip()
                                    if cand_sdk:
                                        cand_and = f"{cand_and} (API {cand_sdk})"
                                except Exception:
                                    pass
                                android_ver = cand_and
                        except Exception:
                            pass
                    # Still fetch model via USB/MTP/AT even when ADB is
                    # unauthorized - once per serial (same cycle as the
                    # gated getprop attempt above; every-3s MTP sessions
                    # claimed the phone's MTP interface per tick).
                    if _props_tried == _unauth_serial and (not model or not build_id or not serial_prop):
                        try:
                            # Try MTP model (generic, not just Samsung) — also captures build/serial
                            _sam_mtp_u = _find_mtp_device() or mtp.find_samsung() or {}
                            if _sam_mtp_u and any(i.get("class") == 6 for i in _sam_mtp_u.get("interfaces", [])):
                                target_u = f"{_sam_mtp_u['vid']:04x}:{_sam_mtp_u['pid']:04x}@{_sam_mtp_u['bus']}:{_sam_mtp_u['address']}"
                                try:
                                    info_u = bridge.mtp_info(target_u, timeout_ms=5000)
                                    if isinstance(info_u, dict):
                                        if info_u.get("model"):
                                            cand_u = info_u["model"].strip()
                                            if cand_u and cand_u.lower() != "adb":
                                                model = cand_u
                                        if info_u.get("device_version") and not build_id:
                                            build_id = info_u["device_version"].strip()
                                        if info_u.get("serial_number") and not serial_prop:
                                            serial_prop = info_u["serial_number"].strip()
                                except Exception:
                                    pass
                            if not model:
                                # Try AT model (diag port)
                                _sam_at = mtp.find_samsung() or {}
                                _is_dl_u = _sam_at.get("pid") in (0x685d, 0x685c, 0x685e) or _sam_at.get("mode") == "samsung-odin"
                                if not _is_dl_u and mtp.is_diag_config(_sam_at):
                                    cand_at = mtp.read_model_via_at(timeout_ms=5000)
                                    if cand_at and cand_at.lower() != "adb":
                                        model = cand_at
                            if not model or not serial_prop:
                                # Fallback USB product/serial strings — target the phone, skip readers
                                try:
                                    _tgt_u = _find_target_device()
                                    if _tgt_u:
                                        _cand_u = (_tgt_u.get("product") or "").strip()
                                        _ser_u = (_tgt_u.get("serial") or "").strip()
                                        if _ser_u and not serial_prop and _ser_u.lower() != "adb":
                                            serial_prop = _ser_u
                                        if _cand_u and _cand_u.lower() not in ("adb", "samsung_android", "samsung android", ""):
                                            if not model:
                                                model = _cand_u
                                    if not model and getattr(self, "_last_usb_product", None):
                                        model = self._last_usb_product
                                except Exception:
                                    pass
                            if model and model != self._cached_model:
                                self._cached_model = model
                                self._ui.line.emit(f"Device Model: {model} (via USB/MTP while ADB unauthorized)")
                                # Keep phone image vendor in sync with Device Model
                                if hasattr(self, "scene") and self.scene and model.lower() != "samsung":
                                    self.scene.set_vendor(model.upper(), C["ok"])
                        except Exception:
                            pass
                elif any(d["state"] == "offline" for d in adb_devs):
                    adb_status = "Offline - replug cable"
                    if self._cached_adb_status != adb_status:
                        self._ui.line.emit("ADB: device offline - unplug + replug, accept dialog")
                    # Also try to get model via non-ADB while offline (target device)
                    if not model or not serial_prop:
                        try:
                            _sam_off = _find_target_device() or mtp.find_samsung() or {}
                            if _sam_off:
                                _cand_off = (_sam_off.get("product") or "").strip()
                                _ser_off = (_sam_off.get("serial") or "").strip()
                                if _cand_off and _cand_off.lower() != "adb" and not model:
                                    model = _cand_off
                                    if model and model != self._cached_model:
                                        self._cached_model = model
                                        if hasattr(self, "scene") and self.scene:
                                            self.scene.set_vendor(model.upper(), C["warn"])
                                if _ser_off and not serial_prop:
                                    serial_prop = _ser_off
                        except Exception:
                            pass
                else:
                    # No ADB transport - try MTP model first (works without ADB/test mode),
                    # then AT if in diag config, before falling back to USB strings.
                    if not model or not build_id or not serial_prop:
                        try:
                            _sam_mtp = _find_mtp_device() or mtp.find_samsung() or {}
                            if _sam_mtp and any(i.get("class") == 6 for i in _sam_mtp.get("interfaces", [])):
                                target = f"{_sam_mtp['vid']:04x}:{_sam_mtp['pid']:04x}@{_sam_mtp['bus']}:{_sam_mtp['address']}"
                                try:
                                    info = bridge.mtp_info(target, timeout_ms=5000)
                                    if isinstance(info, dict):
                                        if info.get("model") and not model:
                                            cand = info["model"].strip()
                                            if cand and cand.lower() != "adb":
                                                model = cand
                                                if model and model != self._cached_model:
                                                    self._cached_model = model
                                                    self._ui.line.emit(f"Device Model: {model} (via MTP)")
                                        if info.get("device_version") and not build_id:
                                            build_id = info["device_version"].strip()
                                        if info.get("serial_number") and not serial_prop:
                                            serial_prop = info["serial_number"].strip()
                                        if info.get("manufacturer") and not mfr:
                                            mfr = info["manufacturer"].strip()
                                except bridge.BridgeError:
                                    pass
                                except Exception:
                                    pass
                        except Exception:  # noqa: BLE001
                            pass
                    if not model:
                        try:
                            _sam = mtp.find_samsung() or {}
                            # Download-mode (Loke) exposes a CDC-ACM *interrupt*
                            # interface that falsely looks like a diag port - but
                            # there is NO AT channel there, only a bulk session.
                            # Attempting AT on it spams 'bulk read: timed out'
                            # every poll. Only probe AT when not in download mode.
                            _is_dl = _sam.get("pid") in (0x6601, 0x685d, 0x685c, 0x685e, 0x68c3, 0x68ef, 0x4eee, 0x4eef) \
                                or _sam.get("mode") == "samsung-odin"
                            if not _is_dl and mtp.is_diag_config(_sam):
                                model = mtp.read_model_via_at(timeout_ms=5000)
                                if model and model != self._cached_model:
                                    self._cached_model = model
                                    self._ui.line.emit(
                                        f"Device Model: {model} (via AT channel)"
                                    )
                        except Exception:  # noqa: BLE001
                            pass
                    # No automatic Odin model probe here - by design. Probing
                    # opens a USB session on the download-mode port, and an
                    # unsolicited background probe contends with (and breaks)
                    # explicit user actions (FUS Detect, flashing). The model
                    # for download-mode phones is resolved on demand by those
                    # actions, which publish it to _cached_model.
                    # Last fallback for non-ADB: use USB product/serial strings directly (target phone)
                    if (not model and not self._cached_model) or not serial_prop:
                        # Use already known product from _last_usb_product if available
                        if not model and getattr(self, "_last_usb_product", None) and self._last_usb_product.strip().lower() != "adb":
                            model = self._last_usb_product.strip()
                        if not model or not serial_prop:
                            try:
                                _tgt2 = _find_target_device()
                                if _tgt2:
                                    if not model:
                                        prod = (_tgt2.get("product") or "").strip()
                                        if prod and prod.lower() != "adb":
                                            model = prod
                                    if not serial_prop:
                                        ser = (_tgt2.get("serial") or "").strip()
                                        if ser and ser.lower() != "adb":
                                            serial_prop = ser
                            except Exception:
                                pass
                    if not adb_devs:
                        adb_status = "Not connected"
                self._cached_adb_status = adb_status
                # --- Live resolver override: real serial / android / build (no fake 01234...) ---
                try:
                    # Pass the display-fixed serial: the live resolver must
                    # probe the device the user is inspecting, or its cached
                    # first-device identity overrides the selection (the
                    # "click modem, details fall back to kg6" bug).
                    live = device_info.get_live_identity(serial or None)
                    # live serial is already filtered fake; prefer it over cached/usb placeholder
                    if live.get("serial") and not device_info._is_fake_serial(live["serial"]):
                        # Only override if we don't have a trusted ADB serial, or live is more complete
                        # For Apple, live serial is UDID/SerialNumber — always prefer
                        if not serial_prop or device_info._is_fake_serial(serial_prop) or live["serial"] != serial_prop:
                            serial_prop = live["serial"]
                    if live.get("android_ver"):
                        android_ver = live["android_ver"]
                    if live.get("build"):
                        build_id = live["build"]
                    if live.get("model") and live["model"].strip().lower() not in ("adb", "samsung_android", ""):
                        # Apple ProductType or Android ro.product.model — prefer live if current is fallback
                        if not model or model.startswith("0x") or model.lower() in ("adb",):
                            model = live["model"]
                        # Update mfr for vendor badge if live has it
                        if live.get("mfr") and not mfr:
                            mfr = live["mfr"]
                except Exception:
                    pass
                # Never emit a hard-coded "adb" as model - use real product/model or placeholder
                fallback = f"0x{pid:04x}" if pid is not None else "--"
                # If we still have no model, keep previous cached or show fallback
                emit_model = model or self._cached_model or fallback
                # Guard against the literal "adb" sneaking in as model (bridge bug)
                if isinstance(emit_model, str) and emit_model.strip().lower() == "adb":
                    emit_model = fallback if fallback != "--" else "--"
                self._ui.metric.emit("Device Model", emit_model)
                self._ui.metric.emit("ADB Status", adb_status)
                # Extended info: build, android, serial (cached) — filtered fake serial
                if build_id and build_id != self._cached_build and build_id.strip().lower() not in ("adb",):
                    self._cached_build = build_id
                if android_ver and android_ver != self._cached_android and android_ver.strip().lower() not in ("adb",):
                    self._cached_android = android_ver
                # Filter fake serial before caching/emitting
                try:
                    if serial_prop and device_info._is_fake_serial(serial_prop):
                        serial_prop = ""
                except Exception:
                    pass
                if serial_prop and serial_prop != self._cached_serial and not serial_prop.strip().lower() in ("adb",):
                    self._cached_serial = serial_prop
                # NEVER hardcode "Tap Allow" — show blank "--" until real data arrives
                build_out = build_id or self._cached_build or "--"
                android_out = android_ver or self._cached_android or "--"
                serial_out = serial_prop or self._cached_serial or "--"
                # Final fake filter on emit
                try:
                    if serial_out != "--" and device_info._is_fake_serial(serial_out):
                        serial_out = "--"
                except Exception:
                    pass
                self._ui.metric.emit("Build Number", build_out)
                self._ui.metric.emit("Android Ver", android_out)
                self._ui.metric.emit("Serial", serial_out)
                # Log detailed info once per connection (throttled)
                try:
                    if emit_model not in ("--",) and not emit_model.startswith("0x"):
                        should_log = not getattr(self, "_detailed_logged", False) or emit_model != getattr(self, "_last_logged_model", None)
                        if should_log and (build_id or android_ver or serial_prop):
                            self._ui.line.emit(f"Device Info: Model {emit_model} | Build {build_id or self._cached_build or 'unknown'} | Android {android_ver or self._cached_android or 'unknown'} | Serial {serial_prop or self._cached_serial or 'unknown'}")
                            self._detailed_logged = True
                            self._last_logged_model = emit_model
                except Exception:
                    pass
                # Deep USB/MTP dump when Build/Android still unknown (dig deeper — no hardcoded text)
                try:
                    if (not build_id and not self._cached_build) and not getattr(self, "_usb_dumped", False):
                        self._usb_dumped = True
                        try:
                            all_u = bridge.detect_all()
                            for d in all_u:
                                vid = d.get("vid", 0)
                                pid_u = d.get("pid", 0)
                                self._ui.line.emit(f"USB raw: {vid:04x}:{pid_u:04x} {d.get('manufacturer')}/{d.get('product')} serial={d.get('serial')} mode={d.get('mode')} bcdDev={d.get('bcd_device'):04x} bus={d.get('bus')} addr={d.get('address')} ifaces={len(d.get('interfaces',[]))}")
                                # Detailed iface dump
                                for iface in d.get("interfaces", []):
                                    eps = ",".join(f"{e['address']:02x}:{e['transfer_type']}" for e in iface.get("endpoints", []))
                                    self._ui.line.emit(f"  Iface {iface.get('number')}: class={iface.get('class')} sub={iface.get('subclass')} proto={iface.get('protocol')} eps=[{eps}]")
                                if any(i.get("class")==6 for i in d.get("interfaces", [])):
                                    tgt = f"{vid:04x}:{pid_u:04x}@{d.get('bus')}:{d.get('address')}"
                                    try:
                                        info_raw = bridge.mtp_info(tgt, timeout_ms=4000)
                                        self._ui.line.emit(f"MTP raw {tgt}: {info_raw}")
                                    except Exception as e:
                                        self._ui.line.emit(f"MTP {tgt} failed: {e}")
                            # Also dump ADB raw for correlation
                            try:
                                adb_raw = bridge._run(["adb-devices"], timeout=8)
                                self._ui.line.emit(f"ADB raw: {adb_raw}")
                            except Exception as e:
                                self._ui.line.emit(f"ADB raw failed: {e}")
                            # Best-effort build/android from MTP GetDeviceInfo (device_version)
                            try:
                                # For each MTP device, extract device_version as build hint
                                for d2 in all_u:
                                    if any(i.get("class") == 6 for i in d2.get("interfaces", [])):
                                        _t2 = f"{d2.get('vid'):04x}:{d2.get('pid'):04x}@{d2.get('bus')}:{d2.get('address')}"
                                        try:
                                            _info2 = bridge.mtp_info(_t2, timeout_ms=4000)
                                            _di = _info2 if isinstance(_info2, dict) else {}
                                            _dv = (_di.get("device_version") or "").strip()
                                            if _dv and _dv.lower() != "adb":
                                                if not build_id:
                                                    self._ui.metric.emit("Build Number", _dv)
                                                    self._cached_build = _dv
                                                    self._ui.line.emit(f"Build (MTP device_version): {_dv}")
                                            _mn = (_di.get("manufacturer") or "").strip()
                                            _mo = (_di.get("model") or "").strip()
                                            if _mn and _mo:
                                                self._ui.line.emit(f"MTP identifies: {_mn} {_mo}")
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                        except Exception as e:
                            self._ui.line.emit(f"USB/MTP deep dump failed: {e}")
                except Exception:
                    pass
                # Keep phone image name in sync with Device Model (throttled, main-thread safe)
                try:
                    if emit_model not in ("--",) and not emit_model.startswith("0x"):
                        lower_em = emit_model.strip().lower()
                        if lower_em not in ("samsung", "mediatek", "qualcomm", "adb", "samsung_android"):
                            # Update cached model for immediate vendor display next time
                            if emit_model != self._cached_model:
                                self._cached_model = emit_model
                            # Use ui signal to touch widgets on main thread
                            self._ui.ui.emit(lambda em=emit_model: self.scene.set_vendor(em.upper(), C["ok"]) if hasattr(self, "scene") and self.scene else None)
                except Exception:
                    pass
            except Exception as e:  # noqa: BLE001
                # Ensure metrics always update even on unexpected errors
                try:
                    fallback = f"0x{pid:04x}" if pid is not None else "--"
                    self._ui.metric.emit("Device Model", self._cached_model or fallback)
                    self._ui.metric.emit("ADB Status", adb_status if adb_status != "Not connected" else "Error")
                    self._ui.metric.emit("Build Number", self._cached_build or "--")
                    self._ui.metric.emit("Android Ver", self._cached_android or "--")
                    self._ui.metric.emit("Serial", self._cached_serial or "--")
                except Exception:
                    pass
            finally:
                self._model_refresh_in_progress = False
                self._update_in_progress = False

        threading.Thread(target=work, daemon=True).start()

    def _poll_adb_metric(self):
        if getattr(self, "_device_connected", False):
            self._refresh_model_and_adb()

    def _copy_device_info(self):
        """Copy current device info (model/build/android/serial/mode) to clipboard."""
        try:
            info = {
                "Model": self.info.get("Device Model", {}).value.text() if "Device Model" in self.info else "--",
                "USB Mode": self.info.get("USB Mode", {}).value.text() if "USB Mode" in self.info else "--",
                "Interface": self.info.get("Interface", {}).value.text() if "Interface" in self.info else "--",
                "ADB Status": self.info.get("ADB Status", {}).value.text() if "ADB Status" in self.info else "--",
                "Build Number": self.info.get("Build Number", {}).value.text() if "Build Number" in self.info else "--",
                "Android Ver": self.info.get("Android Ver", {}).value.text() if "Android Ver" in self.info else "--",
                "Serial": self.info.get("Serial", {}).value.text() if "Serial" in self.info else "--",
                "PIT Health": self.info.get("PIT Health", {}).value.text() if "PIT Health" in self.info else "--",
            }
            # Fallback to cached values if metrics still "--"
            if info["Model"] == "--" and getattr(self, "_cached_model", None):
                info["Model"] = self._cached_model
            if info["Build Number"] == "--" and getattr(self, "_cached_build", None):
                info["Build Number"] = self._cached_build
            text = "\n".join(f"{k}: {v}" for k, v in info.items())
            QApplication.clipboard().setText(text)
            self._ui.line.emit(f"[info] Device info copied to clipboard:\n{text}")
            self.show_toast("Device info copied", "Model/build/serial copied to clipboard", "success")
        except Exception as e:
            self._ui.line.emit(f"[error] Copy failed: {e}")

    def closeEvent(self, event):
        # Window shrink close — 180ms scale 1→0.92 + fade, then actually close
        if not getattr(self, "_close_anim_done", False):
            try:
                if self.settings.value("animations", "true", type=bool) and self.settings.value("anim_window", "true", type=bool):
                    event.ignore()
                    from .animations import Motion
                    def do_close():
                        self._close_anim_done = True
                        super(FlashPilotWindow, self).close()
                    Motion.window_close(self, dur=180, on_finished=do_close)
                    return
            except Exception:
                pass
        self._monitor.stop(join_timeout=2.0)
        self._adb_timer.stop()
        # Flush any coalesced console lines before persisting/closing.
        try:
            self._flush_console()
        except Exception:
            pass
        # Console dock state: height / collapsed / maximised.
        self._save_console_state()
        # Window memory: size/position/maximized restore on the next launch.
        try:
            self.settings.setValue("win_maximized", self.isMaximized())
            if not self.isMaximized():
                self.settings.setValue("win_geometry", self.saveGeometry())
        except Exception:
            pass
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_toasts"):
            self._toasts._relayout()
        if hasattr(self, "_splitter"):
            self._apply_default_dock_split()
        if hasattr(self, "_body_splitter"):
            self._apply_default_body_split()

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

            # Buckets come from the Rust-classified merged rows (no VID
            # tables down here); the raw detect_usb dicts, matched by
            # bus:addr, supply the full descriptor dump.
            buckets = device_pages.buckets_from_rows(
                device_pages.connected_rows())
            raw = {(d.get("bus"), d.get("address")): d
                   for d in usb if isinstance(d, dict)}

            def _dump(rows):
                out = []
                for r in rows:
                    d = raw.get((r.get("bus"), r.get("address")), r)
                    out.extend(_fmt_usb_full(d))
                return out

            samsung = buckets["samsung"]
            mtk_devs = buckets["mtk"]
            fastboot = buckets["fastboot"]
            try:
                adb_devs = bridge.adb_status()
            except bridge.BridgeError as e:
                self._ui.status.emit(f"adb unavailable: {e}")
                adb_devs = []
            if fastboot:
                lines.append("FASTBOOT USB DEVICE(S):")
                lines.extend(_dump(fastboot))
                lines.append("")
                lines.append(f">>> MODE: {_detect_mode([], [], adb_devs, fastboot)}")
                lines.append(
                    "  Fastboot mode - can flash partitions / clear FRP via fastboot"
                )
            elif samsung:
                lines.append("SAMSUNG USB DEVICE(S):")
                lines.extend(_dump(samsung))
                lines.append("")
                mode = _detect_mode(samsung, mtk_devs, adb_devs, fastboot)
                lines.append(f">>> MODE: {mode}")
                if "DIAG" in mode and not any(
                    i.get("class") == 255 and i.get("subclass") == 66
                    for key in [(d.get("bus"), d.get("address")) for d in samsung]
                    for i in raw.get(key, {}).get("interfaces", [])
                    if isinstance(i, dict)
                ):
                    lines.append(
                        "  model hint: AT+DEVCONINFO only answers inside test mode "
                        "(*#0*# from the Emergency call dialer), or enable USB "
                        "debugging for ADB getprop"
                    )
            elif mtk_devs:
                r0 = mtk_devs[0]
                rd0 = raw.get((r0.get("bus"), r0.get("address")), r0)
                mfr = (rd0.get("manufacturer") or "").lower()
                prod = (rd0.get("product") or "").lower()
                is_samsung_mtk = "samsung" in mfr or "samsung" in prod
                if is_samsung_mtk:
                    lines.append("SAMSUNG (MTK) DEVICE(S):")
                else:
                    lines.append("MEDIATEK DEVICE(S):")
                lines.extend(_dump(mtk_devs))
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
                lines.append("No phone detected over USB (plug it in, check cable/port)")

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
                    lines.append("AT/control: — idle (Samsung MTP/AT only)")
            except mtp.MtpError as e:
                lines.append(f"AT/control: error - {e}")

            self._ui.line.emit("\n".join(lines))

        threading.Thread(target=work, daemon=True).start()

    # ----------------------------- battery repair --------------------------
    def _battery_report(self, device_key=None):
        """ADB battery diagnostics with accurate health estimation: reads the
        fuel-gauge sysfs (charge_full / charge_full_design -> health %), plus
        dumpsys battery / batteryproperties and top consumers."""
        prep = self._adb_begin("Battery report", "battery_report", device_key)
        if prep[0] is None:
            return
        serial, device_key, flux = prep

        def _sysfs(path):
            try:
                return bridge.adb_shell(f"cat {path}", timeout=8, serial=serial, rescue=False).strip()
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
            if flux:
                flux.set_state("RUNNING")

            def emit(line):
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            try:
                emit(f"[step] Battery report on {serial}")
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
                    raw = bridge.adb_shell("dumpsys battery", timeout=15, serial=serial, rescue=False)
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
                        "dumpsys batteryproperties", timeout=15, serial=serial, rescue=False
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
                        timeout=30, serial=serial, rescue=False
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
                emit("\n".join(lines))
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except bridge.BridgeCancelled as e:
                emit(f"[cancelled] battery report stopped by user ({e})")
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", str(e), "CANCELLED")
            except Exception as e:  # noqa: BLE001
                emit(f"[error] battery report: {e}")
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                _flow_end(key=device_key)

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

    def _battery_repair_run(self, device_key=None):
        prep = self._adb_begin("Battery repair", "battery_repair", device_key)
        if prep[0] is None:
            return
        serial, device_key, flux = prep

        def work():
            if flux:
                flux.set_state("RUNNING")

            def emit(line):
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            try:
                emit(f"[step] Battery repair on {serial}")

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
                        bridge.adb_shell(cmd, timeout=90, serial=serial, rescue=False)
                        emit(f"   [ok] {label}")
                    except bridge.BridgeError as e:
                        emit(f"   [skip] {label}: {e}")
                    except Exception as e:  # noqa: BLE001
                        emit(f"   [skip] {label}: {e}")

                lines = ["", "--- verification ---"]
                for k in ("low_power", "low_power_sticky",
                          "ble_scan_always_enabled", "wifi_scan_always_enabled"):
                    try:
                        v = bridge.adb_shell(
                            f"settings get global {k}", timeout=12, serial=serial, rescue=False
                        ).strip()
                        lines.append(f"   {k} = {v}")
                    except bridge.BridgeError:
                        lines.append(f"   {k} = (unreadable)")
                try:
                    v = bridge.adb_shell(
                        "settings get system screen_off_timeout", timeout=12, serial=serial, rescue=False
                    ).strip()
                    lines.append(f"   screen_off_timeout = {v}")
                except bridge.BridgeError:
                    pass
                emit("\n".join(lines))

                emit(
                    "\nBattery repair done. Tip: discharge to ~10% then charge "
                    "to 100% without interruption to finish re-calibration."
                )
                self._ui.toast.emit(
                    "ok", "Battery repair", "Fixes applied - re-calibration tip shown"
                )
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except bridge.BridgeCancelled as e:
                emit(f"[cancelled] battery repair stopped by user ({e})")
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", str(e), "CANCELLED")
            except Exception as e:  # noqa: BLE001
                emit(f"[error] battery repair: {e}")
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                _flow_end(key=device_key)

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

    def _battery_load_test_run(self, device_key=None):
        prep = self._adb_begin("Battery load test", "battery_load_test", device_key)
        if prep[0] is None:
            return
        serial, device_key, flux = prep

        def work():
            if flux:
                flux.set_state("RUNNING")

            def emit(line):
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            restored = False
            try:
                emit("[step] Battery load test started")
                self._ui.status.emit("Battery load test: stressing...")

                def read():
                    try:
                        v = bridge.adb_shell(
                            "cat /sys/class/power_supply/battery/voltage_now",
                            timeout=8, serial=serial, rescue=False
                        ).strip()
                        return int(v) / 1000.0 if v else None
                    except (bridge.BridgeError, ValueError):
                        return None

                def read_temp():
                    try:
                        t = bridge.adb_shell(
                            "cat /sys/class/power_supply/battery/temp",
                            timeout=8, serial=serial, rescue=False
                        ).strip()
                        return int(t) / 10.0 if t else None
                    except (bridge.BridgeError, ValueError):
                        return None

                idle_v = read()
                idle_t = read_temp()
                emit(
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
                        bridge.adb_shell(cmd, timeout=10, serial=serial, rescue=False)
                    except bridge.BridgeError:
                        pass
                restored = False  # phone is now maxed - must restore below

                # CPU burn in background
                bridge.adb_shell(
                    "nohup sh -c 'i=0; while [ $i -lt 10000000 ]; do i=$((i+1)); done' >/dev/null 2>&1 &",
                    timeout=8, serial=serial, rescue=False
                )

                import time as _time
                samples = []
                t0 = _time.time()
                while _time.time() - t0 < 14:
                    # Per-device cancel: this phone's scope, not the
                    # broadcast bus, so stopping another phone's job does
                    # not abort this sampling loop.
                    if core.cancel_requested(key=device_key):
                        emit("[cancelled] load test stopped by user")
                        if flux:
                            jobs.finish_job(flux.job_id, "CANCELLED",
                                            "cancelled by user", "CANCELLED")
                        return
                    v = read()
                    if v:
                        samples.append(v)
                    _time.sleep(0.8)
                # loop done (not cancelled) - the full stress window ran
                restored = True  # handled by finally below

                if not samples:
                    emit("[error] load test: no voltage samples read")
                    if flux:
                        jobs.finish_job(flux.job_id, "FAILED", "no voltage samples", "NO_SAMPLES")
                    return
                load_v = min(samples)
                load_t = read_temp()
                sag = (idle_v - load_v) if idle_v else None
                emit("   --- load test result ---")
                emit(
                    f"   idle voltage : {idle_v:.3f} V" if idle_v else "   idle voltage : n/a"
                )
                emit(
                    f"   min voltage under load: {load_v:.3f} V  "
                    f"temp {load_t:.1f} C" if load_t else
                    f"   min voltage under load: {load_v:.3f} V"
                )
                if sag is not None:
                    emit(f"   voltage sag   : {sag*1000:.0f} mV")
                    if sag * 1000 > 250:
                        emit(
                            "   >>> HIGH sag (>250mV): high internal resistance - "
                            "cell is weak, replace the battery"
                        )
                    elif sag * 1000 > 150:
                        emit(
                            "   >>> Moderate sag (150-250mV): degraded cell, "
                            "watch for shutdowns under load"
                        )
                    else:
                        emit(
                            "   Sag within normal range (<150mV): cell looks healthy"
                        )
                emit(
                    "   If the phone shut off during the test, that confirms a "
                    "weak cell (voltage dropped below cutoff)."
                )
                self._ui.status.emit("Battery load test complete")
                self._ui.toast.emit("ok", "Load test", "Result printed to console")
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except bridge.BridgeCancelled as e:
                emit(f"[cancelled] battery load test stopped by user ({e})")
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", str(e), "CANCELLED")
            except Exception as e:  # noqa: BLE001
                emit(f"[error] battery load test: {e}")
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                # Restore brightness even if the burn/read path raised or was
                # cancelled - otherwise the phone is left at 100% brightness.
                if not restored:
                    try:
                        bridge.adb_shell(
                            "settings put system screen_brightness_mode 1", timeout=8,
                            serial=serial, rescue=False
                        )
                    except bridge.BridgeError:
                        pass
                _flow_end(key=device_key)

        threading.Thread(target=work, daemon=True).start()

    # ----------------------------- network repair -------------------------
    # NOTE: _get_authorized_adb/_require_adb (first-authorized-device) were
    # removed: every ADB tool now picks via _adb_begin (dialog when >1) and
    # pins serial=. Do not reintroduce first-match ADB resolution.
    def _poll_net_live(self):
        """Live network readout on the Network page. Runs from the 3s ADB
        timer; updates the metric cards while an authorized ADB device is
        connected, so diagnostics appear without clicking anything.

        Gated on the Network page being VISIBLE: every tick ran adb_status
        + 8 native ADB sessions regardless of the page, and on devices
        whose adbd resets its USB function on our CNXN that re-enumerates
        the phone 8x per cycle while the user is on another page."""
        if getattr(self, "_current_section", "") != "network":
            return
        if not hasattr(self, "net_cards"):
            return
        if self._update_net_in_progress:
            return
        self._update_net_in_progress = True

        def work():
            try:
                # Reuse the DeviceMonitor's fresh state (<=3s old, zero extra
                # USB I/O) instead of another native probe per tick.
                mon = getattr(self, "_monitor", None)
                mon_state = getattr(mon, "_last_state", None) if mon else None
                if mon_state is not None:
                    adb_devs = list(mon_state.get("adb") or [])
                else:
                    try:
                        # Presence (see DeviceMonitor): this 3s display tick
                        # must not natively probe.
                        adb_devs = bridge.adb_presence_status()
                    except bridge.BridgeError:
                        adb_devs = []
                # Pin the whole tick to one phone: the displayed device when
                # authorized, else the first authorized (legacy). Per-call
                # re-resolution could otherwise hop phones mid-tick.
                authorized = [d for d in adb_devs if d["state"] == "device"]
                if not authorized:
                    self._ui.ui.emit(self._net_set_offline)
                    return
                serial = authorized[0]["serial"]
                try:
                    pinned = self._adb_serial_for_key(
                        getattr(self, "_display_key", None))
                    if pinned and any(d["serial"] == pinned for d in authorized):
                        serial = pinned
                except Exception:
                    pass
                try:
                    # rescue=False: passive 3s poll timer - busy (system adb
                    # server holds the interface) must fail fast, never
                    # kill-server (the phone re-enumerates every time).
                    get = lambda prop: bridge.adb_shell(
                        f"getprop {prop}", timeout=8, rescue=False,
                        serial=serial,
                    ).strip()
                    settings_get = lambda key: bridge.adb_shell(
                        f"settings get global {key}", timeout=8, rescue=False,
                        serial=serial,
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
                        rescue=False,
                        serial=serial,
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

    def _network_report(self, device_key=None):
        prep = self._adb_begin("Network report", "network_report", device_key)
        if prep[0] is None:
            return
        serial, device_key, flux = prep

        def work():
            if flux:
                flux.set_state("RUNNING")

            def emit(line):
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            try:
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
                        v = bridge.adb_shell(cmd, timeout=12, serial=serial, rescue=False).strip()
                        if v:
                            lines.append(f"   {label:16}: {v}")
                    except (bridge.BridgeError, ValueError):
                        pass
                try:
                    w = bridge.adb_shell(
                        "dumpsys wifi 2>/dev/null | grep -i 'Wi-Fi is' | head -1",
                        timeout=15, serial=serial, rescue=False
                    ).strip()
                    if w:
                        lines.append(f"   {'Wi-Fi status':16}: {w}")
                except bridge.BridgeError:
                    pass
                try:
                    c = bridge.adb_shell(
                        "dumpsys connectivity 2>/dev/null | grep -i "
                        "'Active default network' | head -1",
                        timeout=15, serial=serial, rescue=False
                    ).strip()
                    if c:
                        lines.append(f"   {'Active net':16}: {c}")
                except bridge.BridgeError:
                    pass
                emit("\n".join(lines))
                self._ui.ui.emit(lambda: self.net_status.setText(
                    "Report printed to console"))
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except bridge.BridgeCancelled as e:
                emit(f"[cancelled] network report stopped by user ({e})")
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", str(e), "CANCELLED")
            except Exception as e:  # noqa: BLE001
                emit(f"[error] network report: {e}")
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                # The pre-scope version of this worker never released its
                # run-guard lock at all; release the keyed one here.
                _flow_end(key=device_key)

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

    def _network_repair_run(self, device_key=None):
        prep = self._adb_begin("Network repair", "network_repair", device_key)
        if prep[0] is None:
            return
        serial, device_key, flux = prep

        def work():
            if flux:
                flux.set_state("RUNNING")

            def emit(line):
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            try:
                emit(f"[step] Network repair on {serial}")
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
                        bridge.adb_shell(cmd, timeout=30, serial=serial, rescue=False)
                        emit(f"   [ok] {label}")
                    except bridge.BridgeError as e:
                        emit(f"   [skip] {label}: {e}")
                    except Exception as e:  # noqa: BLE001
                        emit(f"   [skip] {label}: {e}")

                emit("")
                emit("Network repair done. Re-open Settings -> "
                     "Connections if the phone needs a moment.")
                self._ui.toast.emit("ok", "Network repair", "Radios reset + caches flushed")
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except bridge.BridgeCancelled as e:
                emit(f"[cancelled] network repair stopped by user ({e})")
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", str(e), "CANCELLED")
            except Exception as e:  # noqa: BLE001
                emit(f"[error] network repair: {e}")
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                _flow_end(key=device_key)

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

    def _network_modem_reset_run(self, device_key=None):
        prep = self._adb_begin("Modem reset", "modem_reset", device_key)
        if prep[0] is None:
            return
        serial, device_key, flux = prep

        def work():
            if flux:
                flux.set_state("RUNNING")

            def emit(line):
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            try:
                emit(f"[step] Modem reset on {serial}")
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
                        bridge.adb_shell(cmd, timeout=30, serial=serial, rescue=False)
                        emit(f"   [ok] {label}")
                    except bridge.BridgeError as e:
                        emit(f"   [skip] {label}: {e}")
                    except Exception as e:  # noqa: BLE001
                        emit(f"   [skip] {label}: {e}")

                try:
                    v = bridge.adb_shell(
                        "getprop gsm.sim.state", timeout=12, serial=serial, rescue=False
                    ).strip()
                    emit(f"\nSIM state after reset: {v or '(unknown)'}")
                except bridge.BridgeError:
                    pass
                self._ui.toast.emit("ok", "Modem reset", "Modem re-registering")
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except bridge.BridgeCancelled as e:
                emit(f"[cancelled] modem reset stopped by user ({e})")
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", str(e), "CANCELLED")
            except Exception as e:  # noqa: BLE001
                emit(f"[error] modem reset: {e}")
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                _flow_end(key=device_key)

        threading.Thread(target=work, daemon=True).start()

    # ----------------------------- run flow -------------------------------
    def _carrier_lock_status(self):
        name = core.FLOWS["carrier_lock_status"]().name
        self._run_ops_flow("Unlock Carrier", "ADB", "carrier_lock_status", name)

    def _carrier_lock_mtk(self):
        name = core.FLOWS["carrier_lock_mtk"]().name
        self._run_ops_flow("Unlock Carrier", "MTK BROM", "carrier_lock_mtk", name)

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

        # The native flow reads the selected slots from the environment
        # (ODIN_<SLOT>_TAR); export the full paths, and clear slots the user
        # emptied so a previously-flashed archive can never be reused.
        for name, edit in self.slot_inputs.items():
            key = f"ODIN_{name}_TAR"
            val = edit.text().strip()
            if val:
                os.environ[key] = val
            else:
                os.environ.pop(key, None)
        # EFS clear is consumed per-partition by the native engine.
        if hasattr(self, "erase_nv_cb"):
            os.environ["ODIN_EFS_CLEAR"] = "1" if self.erase_nv_cb.isChecked() else "0"

        detail = "\n".join(f"    {n} <- {f}" for n, f in picked)
        self._confirm_overlay(
            "Flash Firmware",
            "This will OVERWRITE the following partitions on your device.\n\n"
            f"{detail}\n\n"
            "Flashed in order BL -> AP -> CP -> CSC -> USERDATA with the native "
            "Odin engine (archive check, PIT model gate, verify-after-write).\n\n"
            "DO NOT unplug the phone and keep the battery above 50% until the "
            "flash finishes. A failed bootloader flash can permanently brick "
            "the device.",
            confirm_label="Flash now",
            on_confirm=lambda: self._run_ops_flow(
                "Flash Firmware", "Download mode",
                "odin_advanced_flash", "Advanced flash (AP/BL/CP/CSC + Unofficial)",
            ),
        )

    def _browse_slot(self, edit_widget, slot_name):
        # Native Linux (GTK) file dialogs select the FIRST filter by default;
        # using a single comprehensive filter guarantees .img/.lz4/.bin/.pit/
        # .tar files are visible instead of the folder looking empty.
        name_filter = "Samsung images & archives (*.img *.lz4 *.zst *.zstd *.bin *.pit *.tar *.tar.md5)"
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

    _last_stop = [0.0]
    def on_stop(self):
        now = __import__("time").monotonic()
        if now - self._last_stop[0] < 0.5:
            return
        self._last_stop[0] = now
        # Device-aware STOP: one active job -> cancel that device; jobs on
        # several devices -> picker (stop one, or all). Zero active jobs ->
        # legacy broadcast (harmless). Previously STOP was always a
        # broadcast: stopping one phone's flash cancelled every phone's.
        devices_running = sorted({
            j.device_key for j in jobs.active_jobs() if j.device_key
        })
        if len(devices_running) > 1:
            target = self._pick_stop_target(devices_running)
            if target == "__cancelled__":
                return
            if target == "__all__":
                core.request_cancel()
                bridge.request_cancel()
                self._ui.line.emit("[cancel] Stop ALL requested — every device ...")
            else:
                jobs.cancel_device(target)
                self._ui.line.emit(
                    f"[cancel] Stop requested for {target} — other devices keep running ...")
            return
        if len(devices_running) == 1:
            jobs.cancel_device(devices_running[0])
            self._ui.line.emit(
                f"[cancel] Stop requested for {devices_running[0]} — finishing the current USB packet ...")
            self._ui.status.emit("Stopping …")
            return
        core.request_cancel()
        bridge.request_cancel()
        self._ui.status.emit("Stopping …")
        try:
            self._ui.toast.emit("warn", "Stopping", "Closing the current USB operation — device stays connected")
        except Exception:
            pass
        # Instantly disable the single global STOP and all legacy stops so the user
        # sees immediate feedback; the actual flow thread exits on its next
        # cancel check ( ≤ one bulk timeout, typically <600 ms) without a port reset.
        for name in ("global_stop_btn", "stop_btn", "mtk_stop_btn",
                     "qc_stop_btn", "spd_stop_btn"):
            w = getattr(self, name, None)
            if w is not None:
                w.setEnabled(False)
        self._ui.line.emit("[cancel] Stop requested — finishing the current USB packet ...")

    def _pick_from_keys(self, label, device_keys):
        """Run-picker over explicit device keys (daemon rows when the USB
        pick missed): 'Run on this device' / 'Cancel' — run semantics, not
        stop semantics. Returns a device key or '__cancelled__'."""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Choose device — {label}")
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f"The device list could not be scanned just now.<br>Which <b>ADB device</b> should <b>{label}</b> run on?"))
        group = QButtonGroup(dlg)
        radios = []
        for i, k in enumerate(device_keys):
            rb = QRadioButton(k)
            rb.setProperty("device_key", k)
            group.addButton(rb, i)
            lay.addWidget(rb)
            radios.append(rb)
        radios[0].setChecked(True)
        btns = QHBoxLayout()
        btns.addStretch(1)
        ok = QPushButton("Run on this device")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return "__cancelled__"
        checked = group.checkedButton()
        if checked is None:
            return "__cancelled__"
        return checked.property("device_key") or "__cancelled__"

    def _pick_stop_target(self, device_keys):
        """Which running job(s) should STOP cancel? Returns a device key,
        "__all__", or "__cancelled__" (dismissal stands — no stop)."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Stop which device?")
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Several devices are running operations.<br>Which one should stop?"))
        group = QButtonGroup(dlg)
        radios = []
        for i, k in enumerate(device_keys):
            jobs_on = [j for j in jobs.active_jobs(k)]
            what = ", ".join(j.job for j in jobs_on[:2]) or "operation"
            rb = QRadioButton(f"{k}  — {what}")
            rb.setProperty("device_key", k)
            group.addButton(rb, i)
            lay.addWidget(rb)
            radios.append(rb)
        rb_all = QRadioButton("Stop ALL devices")
        rb_all.setProperty("device_key", "__all__")
        group.addButton(rb_all, len(device_keys))
        lay.addWidget(rb_all)
        radios[0].setChecked(True)
        btns = QHBoxLayout()
        btns.addStretch(1)
        ok = QPushButton("Stop")
        cancel = QPushButton("Continue all")
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return "__cancelled__"
        checked = group.checkedButton()
        if checked is None:
            return "__cancelled__"
        return checked.property("device_key") or "__cancelled__"

    def _choose_device(self, job, mode):
        """Per-operation device picker. Returns a device key, None for
        silent/legacy passthrough (0-1 candidates, or detection failure),
        or "__cancelled__" when the user dismisses the chooser.
        ``mode`` may be one transport name or a set of them (chip pages
        cover several related transports)."""
        try:
            modes = {mode} if isinstance(mode, str) else set(mode or [])
            rows = _devices.candidates_for_modes(modes)
        except Exception:
            return None
        rows = [r for r in rows if r.get("key")]
        if len(rows) <= 1:
            return rows[0]["key"] if rows else None
        # Multiple candidates: explicit choice (None would be ambiguous).
        mode_txt = ", ".join(sorted(modes)) if modes else str(mode)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Choose device — {job} / {mode_txt}")
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f"Multiple devices match <b>{mode_txt}</b> for <b>{job}</b>.<br>Which phone should this run on?"))
        group = QButtonGroup(dlg)
        radios = []
        for i, r in enumerate(rows):
            rb = QRadioButton(f"{r.get('label', '?')}  [{', '.join(r.get('transports', []))}]")
            rb.setProperty("device_key", r["key"])
            group.addButton(rb, i)
            lay.addWidget(rb)
            radios.append(rb)
        radios[0].setChecked(True)
        btns = QHBoxLayout()
        btns.addStretch(1)
        ok = QPushButton("Run on this device")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return "__cancelled__"
        checked = group.checkedButton()
        if checked is None:
            return "__cancelled__"
        return checked.property("device_key") or "__cancelled__"

    def _pick_device(self, label, modes):
        """Pick a device key, with one settle-retry on transient emptiness.

        Returns the key, None (nothing detected twice), or "__cancelled__"
        (user dismissed the chooser — never retried, the dismissal stands).
        A re-enumerating device is invisible to a scan for 1-3 s while the
        daemon still reports it connected; without the retry, tools refuse
        with "no device" mid-flap while the GUI shows it connected.
        """
        picked = self._choose_device(label, modes)
        if picked is None:
            import time as _t
            try:
                self._ui.line.emit(
                    f"[info] {label}: no matching device this scan "
                    "(re-enumerating?) — settling 2.5s and retrying ...")
            except Exception:
                pass
            _t.sleep(2.5)
            picked = self._choose_device(label, modes)
        return picked

    def _gate_job_action(self, job, mode, device_key):
        """Ask the backend whether this job may run on this device now.

        Returns True to proceed. On backend rejection returns False after
        logging + toast — the runner must NOT lock, spawn, or execute.
        Unmapped jobs and key-less legacy runs skip the gate (True). A
        missing bridge binary also skips (the flow itself will report it;
        refusing with "unsupported" would mislead)."""
        from ..core import actions as _actions

        ok, last = _actions.check_job_allowed(
            job, mode, device_key, bridge.validate_action)
        if ok:
            return True
        try:
            self._ui.line.emit(
                f"[refused] {job} [{mode}] is not valid for this device "
                f"right now ({device_key}): {last}"
            )
            self._ui.toast.emit(
                "warn", "Unsupported for this device",
                f"{job} cannot run on the selected device in its current state.")
        except Exception:
            pass
        return False

    def _gate_button(self, btn, job=None, mode=None, command=None):
        """Register a button for capability display-gating.

        ``command`` (bridge argv[0] / tool mechanism id) wins when given,
        else the (job, mode) mapping. Registration only records metadata;
        `_refresh_gates()` applies enablement. Safe to call during page
        construction (no bridge I/O here).
        """
        try:
            self._gated_buttons.append(
                (weakref.ref(btn), job, mode, command, btn.toolTip()))
        except Exception:
            pass

    def _refresh_gates(self):
        """Enable/disable gated buttons for the displayed device.

        Display-only and fail-open: resolves `bridge.actions_for()` for
        `self._display_key` (cached per key + device-list signature) and
        disables buttons whose backend actions are all unavailable. Any
        failure — no key, bridge error, empty registry — leaves every
        button enabled. Enforcement stays in the pre-execution gate.
        """
        try:
            from ..core import actions as _actions_mod
            gated = list(getattr(self, "_gated_buttons", None) or [])
            if not gated:
                return
            key = getattr(self, "_display_key", None)
            sig = getattr(self, "_last_device_list_sig", None)
            allowed = None
            if key:
                cache = getattr(self, "_gate_cache", None) or {}
                hit = cache.get(key)
                if hit is not None and hit[0] == sig:
                    allowed = hit[1]
                else:
                    try:
                        payload = bridge.actions_for(key)
                        allowed = [a.get("id") for a in
                                   payload.get("actions", []) if a.get("id")]
                    except Exception:
                        allowed = None
                    try:
                        self._gate_cache = {key: (sig, allowed)}
                    except Exception:
                        pass
            alive = []
            for ref, job, mode, command, base in gated:
                try:
                    btn = ref()
                except Exception:
                    continue
                if btn is None:
                    continue
                alive.append((ref, job, mode, command, base))
                try:
                    if allowed is None:
                        btn.setEnabled(True)
                    else:
                        ok = _actions_mod.button_allowed(
                            job=job, mode=mode, command=command,
                            allowed_ids=allowed)
                        btn.setEnabled(ok)
                        btn.setToolTip(
                            base if ok else base + "\n[BACKEND] Not available "
                            "for the selected device in its current state.")
                except Exception:
                    pass
            try:
                self._gated_buttons = alive
            except Exception:
                pass
        except Exception:
            pass

    def _gate_transport(self, method, device_key=None):
        """Pre-flight: refuse to start when no connected phone exposes the
        flow's transport (instead of a long wait-then-fail). No job is
        created, no lock is taken. Returns True when the run may start.

        QR-entry flows bootstrap the session and unknown requirements run
        unconditionally — both are exempt. A pinned device_key is checked
        against its own row; ambient runs check the union."""
        try:
            need = device_pages.required_transports(method)
        except Exception:
            return True
        if not need:
            return True
        try:
            rows = device_pages.connected_rows()
        except Exception:
            return True
        ok = False
        if device_key:
            for r in rows:
                if r.get("key") == device_key or r.get("usb_key") == device_key:
                    have = set(str(t).upper() for t in (r.get("transports") or []))
                    ok = bool(need & have)
                    break
        else:
            for r in rows:
                have = set(str(t).upper() for t in (r.get("transports") or []))
                if need & have:
                    ok = True
                    break
        if ok:
            return True
        want = "/".join(sorted(need))
        hints = {
            "ADB": "enable USB debugging on the phone and tap Allow",
            "FASTBOOT": "reboot the phone to bootloader (Vol Down+Power)",
            "EDL": "reboot the phone to EDL 9008",
            "MTP": "reboot the phone to system (MTP)",
            "SPD": "reboot the phone to SPD download mode",
            "MTK": "power off, hold Vol-/+, plug USB (BROM)",
            "MTK BROM": "power off, hold Vol-/+, plug USB (BROM)",
        }
        hint = "; ".join(hints.get(t, f"connect a phone in {t} mode") for t in sorted(need))
        self._ui.line.emit(f"[warn] no {want} phone connected — not starting ({method})")
        try:
            self._toasts.show_warn(f"No {want} device",
                                   f"{method}: {hint}, then retry.")
        except Exception:
            pass
        return False

    def _run_ops_flow(self, job, mode, method, label, device_key=None,
                      feature=None):
        """Run a Samsung Operations flow directly from its button - no
        job/mode/method dropdowns, each operation is its own button.
        ``device_key`` pins the run to one phone (None = ambient/legacy);
        other phones may run operations in parallel.
        ``feature`` is the experimental feature id when the caller came
        through the ownership overlay; only a matching per-run token sets
           ctx['experimental_ack'] (no cross-feature bleed, no stale auth)."""
        if device_key is None:
            picked = self._pick_device(job, mode)
            if picked == "__cancelled__":
                self._ui.line.emit("[info] device choice cancelled.")
                return
            device_key = picked
        if not self._gate_transport(method, device_key):
            return
        if not self._gate_job_action(job, mode, device_key):
            return
        if not _flow_start(label, destructive=True, key=device_key):
            self._ui.status.emit("Busy: " + _flow_busy_msg(key=device_key))
            self._ui.toast.emit("warn", "Operation already running", _flow_busy_msg(key=device_key))
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg(key=device_key)}")
            return
        core.clear_cancel(key=device_key)
        bridge.clear_cancel(key=device_key)
        # Isolated FlashJob: created once the gate passed and the per-device
        # lock is held; the worker below drives it to a terminal state.
        from ..core import actions as _actions_mod
        flux = jobs.start_job(
            device_key, job, mode, method,
            _actions_mod.actions_for_job(job, mode) or ())
        flux.set_state("VALIDATED")
        self._toasts.show_progress("Operation started", label)
        if job == "Flash Firmware":
            os.environ["ODIN4_ALLOW_UNKNOWN"] = "1" if self.allow_unknown_cb.isChecked() else "0"
            os.environ["ODIN4_REBOOT"] = "1" if self.auto_reboot_cb.isChecked() else "0"
            os.environ["ODIN4_ERASE_NV"] = "1" if self.erase_nv_cb.isChecked() else "0"
            os.environ["ODIN4_CHECK_ONLY"] = "1" if self.check_only_cb.isChecked() else "0"
            os.environ["ODIN4_REDOWNLOAD"] = "1" if self.redownload_cb.isChecked() else "0"
            os.environ["ODIN4_VERBOSE"] = "1" if self.verbose_cb.isChecked() else "0"
            os.environ["ODIN4_FORCE_BL"] = "1" if self.force_bl_cb.isChecked() else "0"
            os.environ["ODIN4_SKIP_BACKUP"] = "1" if self.skip_efs_cb.isChecked() else "0"
            # Single-session preservation: seed cached device PIT so preflight/
            # partition flows never burn the one Loke session on a live dump.
            try:
                import glob as _g
                _pit_dir = os.path.expanduser("~/.cache/flashpilot/pit")
                _cands = [f for f in _g.glob(os.path.join(_pit_dir, "*.pit"))
                          if os.path.getsize(f) > 512]
                if _cands:
                    _best = max(_cands, key=os.path.getmtime)
                    os.environ["PIT_FILE"] = _best
            except Exception:
                pass
            os.environ["VBMETA_PATCH"] = "1" if self.vbmeta_patch_cb.isChecked() else "0"
            os.environ["FLASH_ENGINE"] = (
                "native" if self.engine_native_cb.isChecked() else "odin4")
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
                # Explicit PIT file field wins.
                os.environ["PIT_FILE"] = pit
            # else: keep the cached-PIT seeded earlier - do NOT pop it, or
            # preflight falls back to a live dump that burns the one Loke
            # session (bulk-read timeout spam) on the next flash attempt.

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
            dev_tag = f"[{device_key}] " if device_key else ""
            job_tag = f"[{flux.job_id}] " if flux else ""
            if device_key:
                ctx["device_key"] = device_key
                try:
                    tgt = _devices.resolve_usb_target(device_key)
                    if tgt:
                        ctx["target"] = tgt
                except Exception:
                    pass
            self._moto_unlock_provision(ctx, method)
            if flux:
                flux.set_state("RUNNING")

            transcript = []

            def emit(line):
                # Per-job log isolation (job owns its lines) + shared console.
                try:
                    transcript.append(str(line))
                except Exception:
                    pass
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            # Same feature-bound consumption as _run_job_flow: only a fresh
            # token for this flow's feature sets the per-run ack.
            try:
                feat = feature or experimental.FLOW_FEATURE_IDS.get(method)
                if feat and experimental.token_consume(
                        getattr(self, "_exp_ack_once", None), feat):
                    ctx["experimental_ack"] = True
            except Exception:
                pass
            try:
                with _devices.device_scope(device_key):
                    flow = core.flow_for(job, mode, method)
                    flow.run(ctx, emit)
                # A clean return is not enough: the Rust flow can print a
                # failure and still exit 0. Never announce success in that
                # case (previously a green "completed" toast was emitted
                # unconditionally).
                failed = _flow_failure_markers(transcript)
                if failed:
                    raise core.FlowFailed(
                        method, tail=failed[-8:],
                        reason=f"flow '{method}' reported failure in its transcript")
                if ctx.get("mdm_qr_pngs"):
                    self._ui.qr.emit(ctx["mdm_qr_pngs"])
                elif ctx.get("mdm_qr_png"):
                    self._ui.qr.emit(ctx["mdm_qr_png"])
                self._ui.status.emit(f"Flow '{label}' finished")
                emit(f"{dev_tag}Flow completed successfully")
                self._ui.toast.emit("ok", "Operation completed", label)
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except core.FlowCancelled as e:
                emit(f"{dev_tag}[cancelled] flow stopped by user ({e})")
                self._ui.status.emit(f"Flow '{label}' cancelled")
                self._ui.toast.emit("warn", "Operation cancelled", str(e))
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", str(e), "CANCELLED")
            except Exception as e:  # noqa: BLE001
                self._emit_flow_error(label, e, mode=mode)
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                _flow_end(key=device_key)
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
        # Button shake + cable shake on failure (professional 340ms / 420ms)
        try:
            if self.settings.value("animations", "true", type=bool):
                from .animations import Motion
                # shake the global STOP (visible feedback) and the scene cable if handshake/transfer
                try:
                    Motion.shake(self.global_stop_btn, amplitude=5)
                except Exception:
                    pass
                low2 = msg.lower()
                if any(k in low2 for k in ("handshake", "timed out", "bulk read", "bulk write", "operation timed out", "failed")):
                    Motion.cable_shake(self.scene, amp=6, dur=420)
        except Exception:
            pass
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

    def _moto_unlock_provision(self, ctx, method):
        """Unlock-code provision for the fastboot unlock flows: the Fastboot
        Hub's code field (the user's own per-device code, typed at runtime)
        flows into ctx['unlock_code']; the MOTO_UNLOCK_CODE env provision
        is the CLI fallback. Nothing is ever hardcoded."""
        if method not in ("moto_frp_fastboot", "fastboot_unlock"):
            return
        token_edit = getattr(self, "_moto_unlock_code", None)
        if token_edit is not None:
            code_txt = token_edit.text().strip()
            if code_txt:
                ctx["unlock_code"] = code_txt
        if "unlock_code" not in ctx:
            env_code = os.environ.get("MOTO_UNLOCK_CODE", "").strip()
            if env_code:
                ctx["unlock_code"] = env_code

    def _run_job_flow(self, job, mode, method, label, stop_btn, progress, reset_ui,
                        device_key=None):
        """Run one of the frp job flows (screen lock remove, MDM unlock, BROM
        info, ...) directly from the MTK / Qualcomm / SPD chip pages. The
        Samsung Operations panel exposes the same flows through its job/mode/
        method pickers; this lets the dedicated chip pages run them too.
        ``device_key`` pins the run to one phone (None = ambient/legacy)."""
        if device_key is None:
            picked = self._pick_device(job, mode)
            if picked == "__cancelled__":
                self._ui.line.emit("[info] device choice cancelled.")
                return
            device_key = picked
        if not self._gate_transport(method, device_key):
            return
        if not self._gate_job_action(job, mode, device_key):
            return
        if not _flow_start(label, destructive=True, key=device_key):
            self._ui.status.emit("Busy: " + _flow_busy_msg(key=device_key))
            self._ui.toast.emit("warn", "Operation already running", _flow_busy_msg(key=device_key))
            self._ui.line.emit(f"[warn] blocked: {_flow_busy_msg(key=device_key)}")
            return
        core.clear_cancel(key=device_key)
        bridge.clear_cancel(key=device_key)
        from ..core import actions as _actions_mod
        flux = jobs.start_job(
            device_key, job, mode, method,
            _actions_mod.actions_for_job(job, mode) or ())
        flux.set_state("VALIDATED")
        self._toasts.show_progress("Operation started", label)
        self._ui.line.emit(f"\n>>> started: {label}")
        self._ui.status.emit(f"Running: {label}")
        stop_btn.setEnabled(True)
        progress.setVisible(True)
        progress.setValue(150)
        # Per-device STOP: this page's stop button cancels exactly this job's
        # device scope (not a broadcast). Replaced on the next run; cleared
        # in the worker's finally.
        try:
            self._stop_job[stop_btn] = flux.job_id
        except Exception:
            pass

        def work():
            ctx = {}
            dev_tag = f"[{device_key}] " if device_key else ""
            if flux:
                flux.set_state("RUNNING")

            transcript = []

            def emit(line):
                try:
                    transcript.append(str(line))
                except Exception:
                    pass
                try:
                    if flux:
                        flux.append_log(str(line))
                except Exception:
                    pass
                self._ui.line.emit(line)

            if device_key:
                ctx["device_key"] = device_key
                try:
                    tgt = _devices.resolve_usb_target(device_key)
                    if tgt:
                        ctx["target"] = tgt
                except Exception:
                    pass
            self._moto_unlock_provision(ctx, method)
            # Consume one per-run experimental ack token for this flow's
            # feature, if the ownership dialog just approved it. Feature-
            # bound and single-use: one confirm authorizes one run, stale
            # confirms expire, and no other feature's token can leak in.
            try:
                feat = experimental.FLOW_FEATURE_IDS.get(method)
                if feat and experimental.token_consume(
                        getattr(self, "_exp_ack_once", None), feat):
                    ctx["experimental_ack"] = True
            except Exception:
                pass
            try:
                with _devices.device_scope(device_key):
                    flow = core.flow_for(job, mode, method)
                    flow.run(ctx, emit)
                # A clean return is not enough: the Rust flow can print a
                # failure and still exit 0. Never announce success in that
                # case (previously a green "completed" toast was emitted
                # unconditionally).
                failed = _flow_failure_markers(transcript)
                if failed:
                    raise core.FlowFailed(
                        method, tail=failed[-8:],
                        reason=f"flow '{method}' reported failure in its transcript")
                if ctx.get("mdm_qr_pngs"):
                    self._ui.qr.emit(ctx["mdm_qr_pngs"])
                elif ctx.get("mdm_qr_png"):
                    self._ui.qr.emit(ctx["mdm_qr_png"])
                self._ui.status.emit(f"Flow '{label}' finished")
                emit(f"{dev_tag}Flow completed successfully")
                self._ui.toast.emit("ok", "Operation completed", label)
                if flux:
                    jobs.finish_job(flux.job_id, "COMPLETED")
            except core.FlowCancelled as e:
                emit(f"{dev_tag}[cancelled] flow stopped by user ({e})")
                self._ui.status.emit(f"Flow '{label}' cancelled")
                self._ui.toast.emit("warn", "Operation cancelled", str(e))
                if flux:
                    jobs.finish_job(flux.job_id, "CANCELLED", str(e), "CANCELLED")
            except Exception as e:  # noqa: BLE001
                self._emit_flow_error(label, e, mode=mode)
                if flux:
                    state, code = jobs.classify_failure(e, device_key)
                    jobs.finish_job(flux.job_id, state, str(e), code)
            finally:
                _flow_end(key=device_key)
                try:
                    if flux and self._stop_job.get(stop_btn) == flux.job_id:
                        self._stop_job.pop(stop_btn, None)
                except Exception:
                    pass
                self._ui.ui.emit(self._toasts.dismiss_progress)
                self._ui.ui.emit(reset_ui)
                self._ui.finished.emit()

        threading.Thread(target=work, daemon=True).start()



# Backwards-compatible alias (packaging smoke test, scripts, docs)
FrpWindow = FlashPilotWindow

def _app_icon():
    """Window / taskbar icon: the packaged logo when present, else a drawn one.
    Resolves docs/logo_256.png in both the dev tree and the installed layout
    (/usr/share/flashpilot/docs/). When running a beta build the icon is
    always the generated logo with the BETA pill + display version so the
    dock/taskbar itself advertises the channel."""
    if _is_beta_version(APP_VERSION):
        pix = _draw_logo(256)
        return QIcon(pix)
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
    QApplication.setDesktopFileName("flashpilot")
    app.setWindowIcon(_app_icon())
    splash = SplashScreen()
    splash.show()

    def _boot():
        win = FrpWindow()
        win.setWindowIcon(_app_icon())
        # Window memory: restore size/position/maximized from the last
        # session (saved in closeEvent).
        try:
            st = win.settings
            if st.value("win_maximized", False, type=bool):
                win.showMaximized()
            else:
                geo = st.value("win_geometry")
                if geo is not None:
                    win.restoreGeometry(geo)
                win.show()
        except Exception:
            win.show()

    QTimer.singleShot(2500, _boot)
    app.exec()
