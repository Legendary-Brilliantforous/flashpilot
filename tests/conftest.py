"""Test-suite-wide isolation of Qt's persisted settings.

The GUI stores user preferences with ``QSettings("FlashPilot", "FlashingTool")``,
which on Linux resolves to ``$XDG_CONFIG_HOME/FlashPilot/FlashingTool.conf``
(``~/.config/FlashPilot/FlashingTool.conf`` by default). Several tests build the
real window — and ``test_console_dock.py`` even writes/removes dock keys — so
without this redirect, simply running the suite mutates the developer's real
application config (e.g. forcing the console dock to a test window's height).

Mechanism: the block below runs at *import time*, before any test module can
``import PyQt6``, and points ``XDG_CONFIG_HOME`` at a throwaway temp directory.
Qt's ``QStandardPaths`` reads ``XDG_CONFIG_HOME`` when a ``QSettings`` object is
constructed, so every settings handle in the suite lands in the temp dir and the
real config is never touched. This is dependency-free and needs no monkeypatching.
"""
import atexit
import os
import shutil
import tempfile
import threading

# --- redirect persisted settings before Qt (or anything else) is imported ---
_TEST_CONFIG_HOME = tempfile.mkdtemp(prefix="flashpilot-test-config-")
os.environ["XDG_CONFIG_HOME"] = _TEST_CONFIG_HOME


def _cleanup_test_config_home():
    shutil.rmtree(_TEST_CONFIG_HOME, ignore_errors=True)


atexit.register(_cleanup_test_config_home)

# Do not override an explicit platform the user/CI may have set.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402  (must follow the environment setup above)


@pytest.fixture(scope="session", autouse=True)
def _isolated_qsettings():
    """Fail loudly if QSettings ever stops resolving inside the temp dir.

    Regression guard: if this assertion trips, the suite is writing to the
    developer's real ``~/.config/FlashPilot/FlashingTool.conf`` again, which can
    silently clobber their preferences (the console dock height in particular).
    """
    from PyQt6.QtCore import QSettings

    resolved = QSettings("FlashPilot", "FlashingTool").fileName()
    expected = os.path.realpath(_TEST_CONFIG_HOME)
    if not os.path.realpath(resolved).startswith(expected + os.sep):
        raise AssertionError(
            "QSettings is not isolated from the real user config.\n"
            f"  resolved: {resolved}\n"
            f"  expected under: {_TEST_CONFIG_HOME}\n"
            "The suite would now mutate the user's real application config "
            "(e.g. persist a test window's console dock height into "
            "~/.config/FlashPilot/FlashingTool.conf). Fix the XDG_CONFIG_HOME "
            "redirect in tests/conftest.py before running these tests."
        )


# --- shared window harness -------------------------------------------------
#
# Three modules build the real ``FlashPilotWindow`` headless. ``DeviceMonitor``'s
# poll thread and the window's periodic QTimers used to outlive the module that
# built them: tests only called ``w._monitor.stop()`` (which sets an event but
# never joins) and never closed the window. With a phone attached those stray
# thread(s) repopulated the process-wide ``python.core.device_info._LIVE_CACHE``
# from a later test module, and at interpreter exit one was still alive while Qt
# tore down the ``QApplication``/``LogBridge`` — segfaulting the process (exit
# 139). The helpers below build a window, join and quiesce its background
# thread, stop its periodic timers, clear the live-identity cache, and later
# fully destroy it. A session-scoped autouse fixture reaps anything left over so
# nothing is alive when the interpreter shuts down.

_WINDOWS = []
_WINDOWS_LOCK = threading.Lock()
_QAPP = None


def clear_live_cache():
    """Reset the process-wide live-identity cache (module attribute).

    A stray window poll can otherwise learn a real attached phone's identity
    and leak it (extra ``adb shell getprop`` sessions) into an unrelated test
    module — e.g. test_devices' live-identity burst-cache assertion.
    """
    try:
        from python.core import device_info as _di

        _di._LIVE_CACHE.update({"probed": None, "at": 0.0, "result": None})
    except Exception:
        pass


def ensure_qapp():
    """Return the process-wide QApplication, creating it on first use."""
    global _QAPP
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QAPP = app  # strong ref: never let the QApplication be GC'd mid-suite
    return app


def _stop_window_timers(window):
    for attr in ("_global_stop_timer", "_row_state_timer", "_adb_timer"):
        timer = getattr(window, attr, None)
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass


def _quiesce_window(window):
    """Stop-and-join the monitor, then stop the window's periodic timers."""
    try:
        window._monitor.stop(join_timeout=5.0)
    except Exception:
        pass
    _stop_window_timers(window)


def build_test_window(settings_clear=()):
    """Build and quiesce a real window; keep a strong ref until destroyed.

    ``settings_clear`` lists QSettings keys to remove *before* construction
    (e.g. the console-dock keys, so the default split is deterministic).
    """
    ensure_qapp()
    if settings_clear:
        from PyQt6.QtCore import QSettings

        settings = QSettings("FlashPilot", "FlashingTool")
        for key in settings_clear:
            settings.remove(key)

    from python.gui import qt_app as _qt

    clear_live_cache()
    window = _qt.FlashPilotWindow()
    with _WINDOWS_LOCK:
        _WINDOWS.append(window)  # module-scope strong ref: Qt must not GC it
    _quiesce_window(window)
    clear_live_cache()
    return window


def destroy_test_window(window):
    """Fully tear down a window built by ``build_test_window``."""
    if window is None:
        return
    with _WINDOWS_LOCK:
        try:
            _WINDOWS.remove(window)
        except ValueError:
            pass
    _quiesce_window(window)
    try:
        # Headless: bypass the shrink-close animation so closeEvent runs the
        # real teardown (monitor join + state save) deterministically instead
        # of parking on an animation that needs a running event loop.
        window._close_anim_done = True
        window.close()
    except Exception:
        pass
    try:
        window.deleteLater()
    except Exception:
        pass
    try:
        ensure_qapp().processEvents()
    except Exception:
        pass
    clear_live_cache()


@pytest.fixture(scope="module")
def test_window():
    """Factory fixture: build windows for a module and fully tear them down.

    Yields ``make(settings_clear=()) -> window``. Every window it creates is
    destroyed at module teardown (and reaped at session end even if a module
    fails to tidy up).
    """
    created = []

    def _make(settings_clear=()):
        window = build_test_window(settings_clear=settings_clear)
        created.append(window)
        return window

    yield _make
    for window in created:
        destroy_test_window(window)


@pytest.fixture(scope="session", autouse=True)
def _reap_test_windows():
    """Last line of defence: nothing built by the harness is left alive."""
    yield
    with _WINDOWS_LOCK:
        remaining = list(_WINDOWS)
        _WINDOWS.clear()
    for window in remaining:
        try:
            destroy_test_window(window)
        except Exception:
            pass
    clear_live_cache()
