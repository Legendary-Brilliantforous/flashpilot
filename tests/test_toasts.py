"""Toast system (S2c) regression tests.

Covers the reworked ``python/gui/toast.py`` overlay:

* deterministic visible cap (``_MAX_VISIBLE == 3``) plus a "+N more" overflow
  chip that appears, updates and clears as toasts dismiss;
* hover pauses the auto-dismiss timer and countdown bar, and leaving resumes
  from the remaining time (never from the full duration);
* auto-dismiss countdown bar for transient toasts;
* optional single action button that runs its callback then dismisses;
* ``toast/position`` (top-right default / bottom-right) drives the layout and is
  honoured at window construction;
* reduced motion (master ``animations`` or granular ``anim_toast`` off) skips
  the slide and still auto-dismisses;
* the historical ``show_*`` / ``update_progress`` API is unchanged;
* the overlay is click-through except over the toast cards themselves.

Run:  QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_toasts.py -q
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, QSettings, Qt


@pytest.fixture(scope="module")
def win(test_window):
    # Clear the persisted position so the default corner is deterministic.
    return test_window(("toast/position",))


def _reset(host):
    """Empty the stack + queue and relayout (no stale toasts between tests)."""
    host._queue.clear()
    for toast in list(host._toasts):
        host.dismiss(toast)
    host._update_overflow()
    host._relayout()


def _settings():
    return QSettings("FlashPilot", "FlashingTool")


# --------------------------------------------------------------------------
# 1. Visible cap + overflow chip
# --------------------------------------------------------------------------
def test_cap_at_three_with_overflow_chip(win):
    host = win._toasts
    _reset(host)
    assert host._MAX_VISIBLE == 3

    for i in range(host._MAX_VISIBLE):
        assert host.show_info(f"t{i}", "d", duration=100000) is not None
    assert len(host._toasts) == 3
    assert host._overflow is None or host._overflow.isHidden()

    # Beyond the cap: queued, not dropped; overflow chip appears.
    assert host.show_info("t3", "d", duration=100000) is None
    assert host.show_warn("t4", "d", duration=100000) is None
    assert len(host._toasts) == 3
    assert len(host._queue) == 2
    assert host._overflow.isHidden() is False
    assert host._overflow.text() == "+2 more"

    # Dismissing a visible toast promotes the next queued toast and updates.
    host.dismiss(host._toasts[0])
    assert len(host._toasts) == 3
    assert len(host._queue) == 1
    assert host._overflow.text() == "+1 more"

    # Draining the queue clears the chip.
    host.dismiss(host._toasts[0])
    assert len(host._queue) == 0
    assert host._overflow.isHidden() is True

    _reset(host)


def test_progress_toast_stays_visible_within_cap(win):
    """A live flash progress toast is shown even at the cap (strict cap kept)."""
    host = win._toasts
    _reset(host)
    for i in range(host._MAX_VISIBLE):
        host.show_info(f"t{i}", "d", duration=100000)
    prog = host.show_progress("Flashing", "super")
    assert prog is not None
    assert prog in host._toasts
    assert len(host._toasts) <= host._MAX_VISIBLE
    host.dismiss_progress()
    _reset(host)


def test_overflow_chip_is_part_of_the_stack(win):
    """The chip is laid out inside the toast column, below the cards."""
    host = win._toasts
    _reset(host)
    cards = [host.show_info(f"t{i}", "d", duration=100000) for i in range(4)]
    assert cards[-1] is None  # 4th queued
    host._relayout()
    last = host._toasts[-1]
    assert host._overflow.isHidden() is False
    assert host._overflow.geometry().y() >= last.geometry().bottom()
    _reset(host)


# --------------------------------------------------------------------------
# 2. Hover pause / resume
# --------------------------------------------------------------------------
def test_hover_pauses_and_resume_keeps_remaining(win):
    host = win._toasts
    _reset(host)
    card = host.show_info("hover", "d", duration=1500)
    assert card is not None
    assert card._dismiss_timer.isActive()
    # A fresh transient toast: armed with the full duration, positive.
    assert 0 < card.remaining_ms() <= 1500

    # Model "some time elapsed, 1200 ms left" deterministically by repointing
    # the running countdown, rather than racing QTest.qWait(250) inside a
    # wall-clock window (that flaked under cumulative suite load).
    card._start_countdown(1200)
    before = card.remaining_ms()
    assert 0 < before < 1500  # some time "elapsed", not full

    # Hover: timer + bar freeze; the remaining time is captured.
    card.enterEvent(None)
    assert card._paused is True
    assert card._dismiss_timer.isActive() is False
    frozen = card.remaining_ms()
    assert 0 < frozen <= before
    # The paused remaining is a stored constant that never consults the clock,
    # so re-reading it can never move — checked without any sleep.
    assert card.remaining_ms() == frozen
    assert card in host._toasts

    # Leave: resumes from the *remaining* time, not the full duration.
    card.leaveEvent(None)
    assert card._paused is False
    assert card._dismiss_timer.isActive() is True
    after = card.remaining_ms()
    # Continues monotonically from what was frozen and stays below the full
    # 1500 ms — i.e. it was not reset to full.
    assert 0 < after <= frozen < 1500
    # The card kept the captured remaining, and the timer was re-armed with
    # exactly that value (interval() is exact; remainingTime() is coarse-rounded
    # by Qt and may read a few percent high, so it is not used as the oracle).
    assert card._remaining == frozen
    assert card._dismiss_timer.interval() == frozen
    _reset(host)


def test_countdown_bar_tracks_remaining(win):
    host = win._toasts
    _reset(host)
    card = host.show_info("count", "d", duration=100000)
    assert card._countdown is not None
    assert card._countdown.value() == 1000

    # Repoint the countdown at 2000 ms of the 100000 ms duration. The bar is a
    # pure function of remaining/duration, so refresh it directly instead of
    # racing the 50 ms tick timer with a sleep.
    card._start_countdown(2000)
    assert card._countdown.value() == 20  # 2000/100000, set synchronously
    card._update_countdown()
    assert 0 < card._countdown.value() <= 20
    assert card.remaining_ms() <= 2000

    # Persistent progress toasts have no countdown bar.
    prog = host.show_progress("p", "d")
    assert prog._countdown is None
    host.dismiss_progress()
    _reset(host)


# --------------------------------------------------------------------------
# 3. Action button
# --------------------------------------------------------------------------
def test_action_button_fires_callback_and_dismisses(win):
    host = win._toasts
    _reset(host)
    calls = []
    card = host.show_error(
        "Flash failed", "bad sector", duration=100000,
        action_label="Retry", action_cb=lambda: calls.append("retry"))
    assert card._action_btn is not None
    assert card._action_btn.text() == "Retry"

    card._action_btn.click()
    assert calls == ["retry"]
    assert card not in host._toasts

    # Default (no action) keeps today's shape.
    plain = host.show_error("plain", "d", duration=100000)
    assert plain._action_btn is None
    _reset(host)


# --------------------------------------------------------------------------
# 4. Position
# --------------------------------------------------------------------------
def test_position_moves_stack_to_bottom_right(win):
    host = win._toasts
    _reset(host)
    card = host.show_info("pos", "d", duration=100000)

    host.set_position("top-right")
    host._relayout()
    top = card.geometry()

    host.set_position("bottom-right")
    host._relayout()
    bottom = card.geometry()

    assert bottom.y() > top.y()
    # Bottom-aligned within the margin.
    assert abs((host.height() - host._MARGIN) - bottom.bottom()) <= 1

    host.set_position("top-right")
    host._relayout()
    _reset(host)


def test_position_applied_on_window_construction(test_window, win):
    _ = win  # build the module window first so this extra build is isolated
    settings = _settings()
    settings.setValue("toast/position", "bottom-right")
    try:
        fresh = test_window()
        assert fresh._toasts.position() == "bottom-right"
    finally:
        settings.remove("toast/position")


def test_invalid_position_falls_back_to_top_right(win):
    host = win._toasts
    host.set_position("sideways")
    assert host.position() == "top-right"
    host.set_position("top-right")


# --------------------------------------------------------------------------
# 5. Reduced motion
# --------------------------------------------------------------------------
def test_reduced_motion_skips_animation_and_still_dismisses(win):
    host = win._toasts
    _reset(host)
    settings = _settings()
    saved = {k: settings.value(k, "true", type=bool)
             for k in ("animations", "anim_toast")}
    try:
        for key in ("animations", "anim_toast"):
            settings.setValue("animations", True)
            settings.setValue("anim_toast", True)
            settings.setValue(key, False)

            card = host.show_info("instant", "d", duration=100000)
            assert card._anim is None
            assert card.get_offset() == 0.0
            host.dismiss(card)

        # Motion on -> slides.
        settings.setValue("animations", True)
        settings.setValue("anim_toast", True)
        moving = host.show_info("moving", "d", duration=100000)
        assert moving._anim is not None
        host.dismiss(moving)

        # Reduced motion still auto-dismisses on its timer. Assert it was armed
        # with the full duration (exact stored/interval values), then fire its
        # timeout directly so the assertion cannot flake on a starved loop.
        settings.setValue("anim_toast", False)
        short = host.show_info("short", "d", duration=250)
        assert short._dismiss_timer.isActive()
        assert short._remaining == 250
        assert short._dismiss_timer.interval() == 250
        short._dismiss_timer.timeout.emit()
        assert short not in host._toasts
    finally:
        for k, v in saved.items():
            settings.setValue(k, v)
        _reset(host)


# --------------------------------------------------------------------------
# 6. Existing API
# --------------------------------------------------------------------------
def test_existing_show_and_progress_api(win):
    host = win._toasts
    _reset(host)

    toast = host.show_progress("Flashing", "super")
    assert toast is not None
    assert toast._bar is not None
    host.update_progress(0.5, title="Flashing 50%", detail="half way")
    assert toast._bar.value() == 500
    assert toast._title.text() == "Flashing 50%"
    assert toast._detail.text() == "half way"
    host.dismiss_progress()
    assert host._progress is None

    for name in ("show_info", "show_ok", "show_warn", "show_error"):
        card = getattr(host, name)("title", "detail", 100000)
        assert card is not None
        assert card._title.text() == "title"
        host.dismiss(card)
    _reset(host)


# --------------------------------------------------------------------------
# 7. Click-through overlay
# --------------------------------------------------------------------------
def test_overlay_is_click_through_except_over_cards(win):
    host = win._toasts
    _reset(host)

    # No toasts -> whole overlay click-through.
    assert host.testAttribute(
        Qt.WidgetAttribute.WA_TransparentForMouseEvents) is True

    card = host.show_info("there", "d", duration=100000)
    assert host.testAttribute(
        Qt.WidgetAttribute.WA_TransparentForMouseEvents) is False
    mask = host.mask()
    assert not mask.isEmpty()
    # Far from the toast column (left/centre) the overlay does not intercept.
    assert mask.contains(QPoint(5, host.height() // 2)) is False
    # Over the card / its column it does.
    centre = card.geometry().center()
    assert mask.contains(QPoint(host.width() - 30, centre.y())) is True

    _reset(host)
    # Back to click-through once empty.
    assert host.testAttribute(
        Qt.WidgetAttribute.WA_TransparentForMouseEvents) is True


# --------------------------------------------------------------------------
# 8. Host shown before the parent has a size
# --------------------------------------------------------------------------
def test_host_shown_before_parent_has_size():
    from PyQt6.QtWidgets import QWidget

    from python.gui.toast import ToastHost

    parent = QWidget()
    parent.resize(0, 0)
    host = ToastHost(parent)
    host.show()  # must not raise / not divide by a zero size

    card = host.show_info("early", "d", duration=100000)
    assert card is not None
    assert host._toasts == [card]

    # A real size later lets the stack lay out normally.
    parent.resize(800, 600)
    host._relayout()
    assert card.geometry().x() > 0
    assert card.width() == 340
    _reset(host)
