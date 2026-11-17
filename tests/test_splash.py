"""Splash screen + startup progress wiring.

Regression guards for the reported "splash is not fluid" bug:

* the bar follows real build progress (``set_progress``) instead of a fixed
  increment, and keeps creeping on a time curve between reports;
* the whole card fades (the old code changed opacity only for the accent bar's
  drawing state, so the background never faded);
* the logo is decoded/scaled once instead of being regenerated every frame;
* ``main()`` keeps the splash animating during the eager window build via the
  startup hook, then calls ``finish()``.
"""
import inspect
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def splash():
    from tests.conftest import ensure_qapp

    ensure_qapp()
    from python.gui.qt_app import SplashScreen

    s = SplashScreen()
    yield s
    try:
        s._timer.stop()
        s.close()
        s.deleteLater()
    except Exception:
        pass


def test_progress_reports_are_monotonic_and_clamped(splash):
    splash.set_progress(0.2)
    assert splash._reported == pytest.approx(0.2)
    splash.set_progress(0.1)
    assert splash._reported == pytest.approx(0.2)
    splash.set_progress(1.0)
    assert splash._reported == pytest.approx(1.0)
    splash.set_progress("nonsense")
    splash.set_progress(None)
    assert splash._reported == pytest.approx(1.0)


def test_progress_creeps_forward_without_reports():
    """Between milestones the bar keeps moving instead of looking hung."""
    from tests.conftest import ensure_qapp

    ensure_qapp()
    from python.gui.qt_app import SplashScreen

    s = SplashScreen()
    try:
        s._clock -= 8.0  # simulate eight seconds of build time
        start = s._progress
        for _ in range(30):
            s._tick()
        assert s._progress > start
        assert s._progress <= 0.96 + 1e-9
    finally:
        s._timer.stop()
        s.close()
        s.deleteLater()


def test_progress_eases_toward_the_reported_stage():
    from tests.conftest import ensure_qapp

    ensure_qapp()
    from python.gui.qt_app import SplashScreen

    s = SplashScreen()
    try:
        s.set_progress(0.8)
        s._clock = time.monotonic()  # creep is still ~0
        for _ in range(200):
            s._tick()
        assert s._progress == pytest.approx(0.8, abs=0.02)
    finally:
        s._timer.stop()
        s.close()
        s.deleteLater()


def test_fade_covers_the_whole_card(splash):
    splash._set_fade(0.5)
    assert splash._fade == pytest.approx(0.5)
    splash._set_fade(-3)
    assert splash._fade == 0.0
    splash._set_fade(4)
    assert splash._fade == 1.0
    splash._set_fade(1.0)


def test_finish_is_idempotent_and_stops_the_timer(splash):
    splash.finish()
    assert splash._closing is True
    assert splash._reported == 1.0
    splash.finish()  # no second fade-out request / no error
    # The fade waits for the bar to complete, so it starts on demand here.
    assert splash._fade_out_started is False
    splash._start_fade_out()
    assert splash._fade_out_started is True
    splash._start_fade_out()  # idempotent
    splash._finish_done()
    assert splash._timer.isActive() is False
    if splash._fade_anim is not None:
        splash._fade_anim.stop()
    # Re-arm for any later test that reuses the module fixture.
    splash._closing = False
    splash._fade_out_started = False
    splash._set_fade(1.0)
    splash._timer.start(16)


def test_closing_fills_the_bar_before_fading():
    from tests.conftest import ensure_qapp

    ensure_qapp()
    from python.gui.qt_app import SplashScreen

    s = SplashScreen()
    try:
        s.set_progress(0.4)
        assert s._progress == pytest.approx(0.28, abs=0.01)
        s.finish()
        for _ in range(20):
            s._tick()
        assert s._progress > 0.98
    finally:
        s._timer.stop()
        s.close()
        s.deleteLater()


def test_progress_snap_keeps_the_bar_near_the_reported_stage(splash):
    splash.set_progress(0.0)
    splash._progress = 0.0
    splash.set_progress(0.9)
    # The bar can no longer sit at 40% while the build reports 90%.
    assert splash._progress >= 0.9 - 0.12 - 1e-9
    assert splash._progress <= splash._reported
    splash._progress = 0.0
    splash._reported = 0.0


def test_static_artwork_and_logo_are_cached(splash):
    assert not splash._static.isNull()
    assert splash._static.size() == splash.size()
    assert not splash._logo.isNull()
    assert splash._logo.width() == 128

    # Painting must not regenerate the vector logo (the old per-frame cost).
    from python.gui import qt_app

    calls = []
    original = qt_app._draw_logo

    def counting(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    qt_app._draw_logo = counting
    try:
        splash.grab()
    finally:
        qt_app._draw_logo = original
    assert calls == []


def test_startup_hook_reports_progress_and_swallows_errors(monkeypatch):
    from python.gui import startup

    seen = []
    monkeypatch.setattr(startup, "_HOOK", lambda f=None: seen.append(f))
    startup.stage(0.25)
    startup.stage()
    assert seen == [0.25, None]

    def boom(_fraction=None):
        raise RuntimeError("builder hook failed")

    monkeypatch.setattr(startup, "_HOOK", boom)
    startup.stage(0.5)  # must not raise

    monkeypatch.setattr(startup, "_HOOK", None)
    startup.stage(0.75)  # no hook -> no-op
    assert startup.get_hook() is None


def test_set_hook_installs_and_clears():
    from python.gui import startup

    previous = startup.get_hook()
    try:
        calls = []

        def hook(fraction=None):
            calls.append(fraction)

        startup.set_hook(hook)
        assert startup.get_hook() is hook
        startup.stage(0.3)
        assert calls == [0.3]
    finally:
        startup.set_hook(previous)


def test_build_ui_reports_stages_and_main_finishes_the_splash():
    from python.gui import qt_app

    build_src = inspect.getsource(qt_app.FlashPilotWindow._build_ui)
    assert "_startup_stage(0.04)" in build_src
    assert "_startup_stage(0.99)" in build_src
    # Heavy shell pieces each pump once so the splash keeps moving.
    assert "_startup_stage(0.7)" in build_src
    assert "_startup_stage(0.94)" in build_src

    main_src = inspect.getsource(qt_app.main)
    assert "_set_startup_hook(_pump)" in main_src
    assert "_set_startup_hook(None)" in main_src
    assert "splash.finish()" in main_src
    assert "singleShot(800" in main_src


@pytest.fixture(scope="module")
def raw_window():
    """A window built exactly like production (deferred pages, no harness)."""
    from tests.conftest import destroy_test_window, ensure_qapp

    ensure_qapp()
    from python.gui import qt_app

    w = qt_app.FlashPilotWindow()
    yield w
    destroy_test_window(w)


def test_pages_are_deferred_until_first_visit(raw_window):
    w = raw_window
    assert w._lazy_sections, "tool/brand pages should be deferred at startup"
    key = next(iter(w._lazy_sections))
    index = w._section_index[key]
    count = w._stack.count()

    assert w._build_section(key) is True
    assert key not in w._lazy_sections
    # Index mapping and stack length are unchanged: the placeholder was
    # replaced in place, not appended.
    assert w._section_index[key] == index
    assert w._stack.count() == count
    assert w._stack.widget(index) is not None
    # Idempotent: a second call is a no-op.
    assert w._build_section(key) is False


def test_on_section_builds_and_shows(raw_window):
    w = raw_window
    key = next(iter(w._lazy_sections))
    w._on_section(key)
    assert key not in w._lazy_sections
    assert w._stack.currentIndex() == w._section_index[key]
    assert w._current_section == key


def test_ensure_all_pages_materialises_everything(raw_window):
    w = raw_window
    w._ensure_all_pages()
    assert w._lazy_sections == {}
    assert w._stack.count() == len(w._section_index)
    # Every registered section now has a real page, not a bare placeholder.
    for key, index in w._section_index.items():
        page = w._stack.widget(index)
        assert page is not None, key

