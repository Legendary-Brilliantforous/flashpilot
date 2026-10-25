"""Click-routing contract for rendered flow buttons.

A behavioural (not white-box) test of the click chain that must survive the
FlowBrowser refactor: the real window is built, its three routing sinks are
replaced with recorders, and rendered buttons are found by their tooltip
``"{job} / {mode} / {key}"``. It does not depend on private renderer
attributes, so it keeps guarding the safety path after the renderer moves into
:class:`python.gui.widgets.flow_browser.FlowBrowser`.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from python.core import core
from python.gui.common import _DESTRUCTIVE_CONFIRM, _EXPERIMENTAL_FLOW_MAP


@pytest.fixture(scope="module")
def win(test_window):
    w = test_window()
    assert len(w._gated_buttons) > 100, "gated registry unexpectedly small"
    return w


class _Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


def _patch_sinks(monkeypatch, win):
    exp, conf, run = _Recorder(), _Recorder(), _Recorder()
    monkeypatch.setattr(win, "_confirm_experimental_overlay", exp)
    monkeypatch.setattr(win, "_confirm_overlay", conf)
    monkeypatch.setattr(win, "_run_ops_flow", run)
    return exp, conf, run


def _find_rendering(key):
    """First (job, mode) whose method list contains ``key``."""
    for job in core.JOBS:
        for mode in core.modes_for(job):
            if key in core.methods_for(job, mode):
                return job, mode
    raise AssertionError(f"{key!r} is not offered by any (job, mode)")


def _render(win, job, mode, run_cb=None):
    """Render one job/mode through the window's renderer into a fresh host."""
    host = QWidget()
    lay = QVBoxLayout(host)
    win._add_job_flows(lay, [job], modes={mode}, run_cb=run_cb)
    return host


def _find_button(host, mode, key):
    for b in host.findChildren(QPushButton):
        if f" / {mode} / {key}" in b.toolTip():
            return b
    raise AssertionError(f"no rendered button for {mode} / {key}")


def _gate_entry(win, btn):
    for ref, job, mode, command, base in win._gated_buttons:
        if ref() is btn:
            return job, mode, command, base
    return None


# --- precedence / map hygiene ---------------------------------------------
def test_experimental_and_destructive_maps_are_disjoint():
    """The precedence rule must be unambiguous: no key in both maps."""
    assert not (set(_EXPERIMENTAL_FLOW_MAP) & set(_DESTRUCTIVE_CONFIRM))


# --- experimental keys -----------------------------------------------------
@pytest.mark.parametrize("key", sorted(_EXPERIMENTAL_FLOW_MAP))
def test_experimental_key_routes_to_experimental_overlay(win, monkeypatch, key):
    exp, conf, run = _patch_sinks(monkeypatch, win)
    job, mode = _find_rendering(key)
    host = _render(win, job, mode)
    btn = _find_button(host, mode, key)
    btn.setEnabled(True)
    btn.click()

    assert conf.calls == [], "experimental flow must not use the plain confirm"
    assert len(exp.calls) == 1
    args, kwargs = exp.calls[0]
    feature, _title, _text, method_key = args
    assert feature == _EXPERIMENTAL_FLOW_MAP[key]
    assert method_key == key
    assert kwargs["chip"] == "wipe"
    assert kwargs["confirm_label"] == "I Accept — Run"
    # Nothing runs before the user confirms.
    assert run.calls == []

    kwargs["on_confirm"]()
    assert len(run.calls) == 1
    rargs, _ = run.calls[0]
    assert rargs == (job, mode, key, btn.text())


def test_experimental_run_cb_variant(win, monkeypatch):
    exp, conf, run = _patch_sinks(monkeypatch, win)
    calls = []
    key = "knox_bypass"
    job, mode = _find_rendering(key)
    host = _render(win, job, mode, run_cb=lambda *a: calls.append(a))
    btn = _find_button(host, mode, key)
    btn.click()
    assert calls == []
    assert len(exp.calls) == 1
    exp.calls[0][1]["on_confirm"]()
    assert calls == [(job, mode, key, btn.text())]
    assert run.calls == [], "run_cb variant must not fall back to _run_ops_flow"


# --- destructive (confirm) keys --------------------------------------------
@pytest.mark.parametrize("key", sorted(_DESTRUCTIVE_CONFIRM))
def test_destructive_key_routes_to_confirm_overlay(win, monkeypatch, key):
    exp, conf, run = _patch_sinks(monkeypatch, win)
    job, mode = _find_rendering(key)
    host = _render(win, job, mode)
    btn = _find_button(host, mode, key)
    btn.setEnabled(True)
    btn.click()

    assert exp.calls == [], "destructive flow must not use the experimental gate"
    assert len(conf.calls) == 1
    args, kwargs = conf.calls[0]
    title, body = args
    assert (title, body) == _DESTRUCTIVE_CONFIRM[key]
    assert kwargs["confirm_label"] == "Continue"
    assert run.calls == []

    kwargs["on_confirm"]()
    assert len(run.calls) == 1
    rargs, _ = run.calls[0]
    assert rargs == (job, mode, key, btn.text())


def test_destructive_run_cb_variant(win, monkeypatch):
    exp, conf, run = _patch_sinks(monkeypatch, win)
    calls = []
    key = "factory_reset"
    job, mode = _find_rendering(key)
    host = _render(win, job, mode, run_cb=lambda *a: calls.append(a))
    btn = _find_button(host, mode, key)
    btn.click()
    assert calls == []
    assert len(conf.calls) == 1
    conf.calls[0][1]["on_confirm"]()
    assert calls == [(job, mode, key, btn.text())]
    assert run.calls == []


# --- plain keys run directly -----------------------------------------------
@pytest.mark.parametrize("job,mode,key", [
    ("Read Device Info", "ADB", "adb_info"),
    ("Reboot", "ADB", "reboot_normal"),
])
def test_plain_key_runs_directly(win, monkeypatch, job, mode, key):
    exp, conf, run = _patch_sinks(monkeypatch, win)
    host = _render(win, job, mode)
    btn = _find_button(host, mode, key)
    btn.setEnabled(True)
    btn.click()
    assert exp.calls == [] and conf.calls == []
    assert len(run.calls) == 1
    args, _ = run.calls[0]
    assert args == (job, mode, key, btn.text())


def test_plain_run_cb_variant(win, monkeypatch):
    exp, conf, run = _patch_sinks(monkeypatch, win)
    calls = []
    host = _render(win, "Reboot", "ADB", run_cb=lambda *a: calls.append(a))
    btn = _find_button(host, "ADB", "reboot_normal")
    btn.click()
    assert calls == [("Reboot", "ADB", "reboot_normal", btn.text())]
    assert run.calls == []


# --- gating registry -------------------------------------------------------
def test_renderer_registers_gates_with_job_and_mode_and_no_command(win):
    host = _render(win, "Read Device Info", "ADB")
    buttons = host.findChildren(QPushButton)
    assert buttons
    for btn in buttons:
        entry = _gate_entry(win, btn)
        assert entry is not None, "renderer button was not gated"
        job, mode, command, _base = entry
        assert command is None, f"renderer must not pass command= ({command!r})"
        assert job == "Read Device Info"
        assert mode == "ADB"


def test_all_rendered_window_buttons_are_gated_job_mode_without_command(win):
    """Flow gates are job/mode based; none of them carry a raw command.

    Non-flow buttons (gated with no metadata at all, e.g. a plain status
    button) are exempt — they never go through the renderer.
    """
    for ref, job, mode, command, _base in win._gated_buttons:
        if job is None and mode is None:
            continue
        assert command is None, (
            f"renderer-style gate must not pass command=: {(job, mode, command)}")
        assert job is not None and mode is not None, (
            f"flow gate missing job/mode: {(job, mode, command)}")
