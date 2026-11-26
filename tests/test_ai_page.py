"""AI advisor GUI: page, floating panel, settings section, streaming.

The provider is stubbed so these tests never touch the network. Everything
else is the real window: real QSettings, real transcript file (redirected to
a temp XDG_DATA_HOME by ``tests/conftest.py``), real worker thread and the
real ``_ui.ui`` marshalling back to the GUI thread.
"""

from __future__ import annotations

import os
import time

import pytest
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FLOWS = [
    {"key": "odin_flash_tar", "label": "Flash firmware tar", "job": "Flash Firmware", "mode": "ADB"},
    {"key": "odin_frp", "label": "Remove FRP", "job": "Remove FRP", "mode": "Download"},
]


def _settle(rounds=60, until=None):
    for _ in range(rounds):
        QApplication.processEvents()
        if until is not None and until():
            return True
        time.sleep(0.01)
    return until() if until is not None else True


def _ai_module():
    from python.gui.pages import ai as ai_page

    return ai_page


@pytest.fixture()
def ready_advisor(monkeypatch):
    """Keyring + provider config that validate cleanly, with a stub stream."""
    mod = _ai_module()
    monkeypatch.setattr(mod.ai_keys, "available", lambda: (True, ""))
    monkeypatch.setattr(mod.ai_keys, "get_key", lambda _preset: "sk-test")
    monkeypatch.setattr(mod.ai_keys, "backend_name", lambda: "test-keyring")
    monkeypatch.setattr(mod.bridge, "flow_list", lambda: FLOWS)
    monkeypatch.setattr(mod.ai_retrieval, "default_index", lambda: None)

    seen = {"calls": 0}

    def fake_stream(config, messages, cancel=None, usage_out=None):
        seen["calls"] += 1
        seen["messages"] = messages
        for piece in ("What happened: ", "the device left download mode."):
            if cancel is not None and cancel():
                return
            yield piece
        if usage_out is not None:
            usage_out.update({"in": 21, "out": 7})

    monkeypatch.setattr(mod.ai_provider, "stream_chat", fake_stream)
    return seen


def _configure(win):
    win.settings.setValue("ai_preset", "openai")
    win.settings.setValue("ai_base_url", "https://api.example.test/v1")
    win.settings.setValue("ai_model", "gpt-test")
    win.settings.setValue("ai_include_device", True)
    win.settings.setValue("ai_include_log", True)
    win.settings.setValue("ai_include_docs", True)


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------

def test_page_has_transcript_input_and_read_only_note(test_window):
    from PyQt6.QtWidgets import QLabel

    win = test_window(settings_clear=("ai_preset",))
    win._on_section("ai")
    assert win._ai_view is not None
    assert win._ai_input.placeholderText()
    assert win._ai_send_btn.text() == "Send"
    assert win._ai_stop_btn.isEnabled() is False
    # The read-only promise is visible on the page itself.
    page = win._ai_view.parent()
    labels = [label.text() for label in page.findChildren(QLabel)]
    assert any("Read-only" in text for text in labels)


def test_disabled_state_explains_why_and_disables_send(test_window, monkeypatch):
    mod = _ai_module()
    monkeypatch.setattr(
        mod.ai_keys, "available", lambda: (False, "no Secret Service backend")
    )
    win = test_window()
    win._on_section("ai")
    assert "AI disabled" in win._ai_status.text()
    assert "no Secret Service backend" in win._ai_status.text()
    assert win._ai_send_btn.isEnabled() is False


def test_local_preset_is_ready_without_a_keyring(test_window, monkeypatch):
    mod = _ai_module()
    monkeypatch.setattr(
        mod.ai_keys, "available", lambda: (False, "no Secret Service backend")
    )
    win = test_window()
    win.settings.setValue("ai_preset", "local")
    win.settings.setValue("ai_base_url", "http://127.0.0.1:11434/v1")
    win.settings.setValue("ai_model", "llama3.2")
    ready, reason = win._ai_ready()
    assert ready is True, reason


def test_diagnose_button_fills_the_prompt(test_window):
    win = test_window()
    win._on_section("ai")
    win._ai_diagnose()
    assert "Explain exactly why" in win._ai_input.toPlainText()


def test_ask_local_answers_from_the_knowledge_base(test_window):
    win = test_window()
    win._on_section("ai")
    win._ai_input.setPlainText("what is the odin frp flow")
    win._ai_ask_local()
    text = win._ai_view.toPlainText()
    # The local assistant answered from the real corpus and cited sources.
    assert "Sources:" in text
    assert win._ai_chat().messages[-1]["role"] == "assistant"
    assert win._ai_chat().messages[-1]["content"].strip()


# --------------------------------------------------------------------------
# Streaming
# --------------------------------------------------------------------------

def test_send_streams_into_the_view_and_persists(test_window, ready_advisor):
    win = test_window()
    _configure(win)
    win._on_section("ai")
    win._ai_chat().clear()

    win._ai_input.setPlainText("why did odin fail?")
    win._ai_send()
    assert _settle(until=lambda: not win._ai_busy)

    text = win._ai_view.toPlainText()
    assert "the device left download mode." in text
    assert win._ai_chat().messages[-1]["role"] == "assistant"
    assert "download mode" in win._ai_chat().messages[-1]["content"]
    assert win._ai_stop_btn.isEnabled() is False
    assert ready_advisor["calls"] == 1
    # The console tail / device block reached the provider as one user turn.
    final = ready_advisor["messages"][-1]["content"]
    assert "why did odin fail?" in final


def test_send_refuses_when_advisor_is_disabled(test_window, monkeypatch):
    mod = _ai_module()
    monkeypatch.setattr(mod.ai_keys, "available", lambda: (False, "no keyring"))
    calls = {"n": 0}
    monkeypatch.setattr(
        mod.ai_provider,
        "stream_chat",
        lambda *a, **k: calls.__setitem__("n", calls["n"] + 1),
    )
    win = test_window()
    win._ai_chat().clear()
    win._ai_input.setPlainText("anything")
    win._ai_send()
    _settle(rounds=10)
    assert calls["n"] == 0
    assert win._ai_chat().messages == []


def test_log_tail_returns_the_newest_lines(test_window):
    win = test_window()
    win._log_buffer = [("info", f"line {i}") for i in range(300)]
    tail = win.ai_log_tail(5).splitlines()
    assert tail == [f"line {i}" for i in range(295, 300)]


# --------------------------------------------------------------------------
# Floating panel
# --------------------------------------------------------------------------

def test_panel_builds_on_first_toggle_and_shares_history(test_window, ready_advisor):
    win = test_window()
    _configure(win)
    win._on_section("ai")
    win._ai_chat().clear()
    win.show()
    _settle(rounds=10)

    assert getattr(win, "_ai_panel", None) is None
    win._ai_toggle_panel()
    panel = win._ai_panel
    assert panel is not None
    assert panel.isVisible() is True
    assert panel.parent() is win._root

    win._ai_panel_input.setPlainText("what does BROM mean?")
    win._ai_panel_send()
    assert _settle(until=lambda: not win._ai_busy)
    assert "download mode" in win._ai_panel_view.toPlainText()
    # The page was rebuilt from the same transcript.
    assert "download mode" in win._ai_view.toPlainText()

    win._ai_toggle_panel()
    assert panel.isVisible() is False
    win.close()


def test_panel_geometry_is_persisted(test_window):
    win = test_window()
    win._on_section("ai")
    win.show()
    _settle(rounds=5)
    win._ai_toggle_panel()
    win._ai_panel.move(40, 50)
    win._ai_panel_moved()
    saved = win.settings.value("ai_panel_geometry", "")
    assert str(saved).startswith("40,50,")
    win._ai_toggle_panel()
    win.close()


# --------------------------------------------------------------------------
# History
# --------------------------------------------------------------------------

def test_delete_history_clears_file_and_every_view(test_window, ready_advisor):
    win = test_window()
    _configure(win)
    win._on_section("ai")
    win._ai_chat().clear()
    win._ai_chat().append("user", "old question")
    win._ai_chat().append("assistant", "old answer")
    win._ai_render_history()
    assert "old question" in win._ai_view.toPlainText()

    path = win._ai_chat().path
    assert os.path.exists(path)
    win._ai_clear_history()
    assert not os.path.exists(path)
    assert win._ai_view.toPlainText().strip() == ""
    assert win._ai_chat().messages == []


# --------------------------------------------------------------------------
# Settings section
# --------------------------------------------------------------------------

def test_settings_ai_section_lists_every_preset_and_the_keyring_state(test_window):
    win = test_window()
    win._on_section("settings")
    win._switch_settings("ai")
    assert win._settings_pages.currentIndex() == 4
    listed = {
        win._ai_preset.itemData(i) for i in range(win._ai_preset.count())
    }
    assert listed == set(_ai_module().ai_provider.PRESETS)
    assert win._ai_base_url.text()
    assert win._ai_model.text()
    assert win._ai_key_state.text()


def test_settings_preset_switch_updates_url_and_model(test_window):
    win = test_window()
    win._on_section("settings")
    win._switch_settings("ai")
    win._ai_on_preset_changed("gemini")
    assert win.settings.value("ai_preset") == "gemini"
    assert "generativelanguage" in win._ai_base_url.text()
    assert win._ai_model.text().startswith("gemini")


def test_saving_a_key_goes_through_the_keyring_only(test_window, monkeypatch):
    mod = _ai_module()
    stored = {}
    monkeypatch.setattr(mod.ai_keys, "available", lambda: (True, ""))
    monkeypatch.setattr(mod.ai_keys, "get_key", lambda p: stored.get(p))
    monkeypatch.setattr(
        mod.ai_keys, "set_key", lambda p, k: stored.__setitem__(p, k)
    )
    monkeypatch.setattr(mod.ai_keys, "delete_key", lambda p: stored.pop(p, None))
    monkeypatch.setattr(mod.ai_keys, "mask_key", lambda k: "sk-…" + k[-4:])

    win = test_window()
    win._on_section("settings")
    win._switch_settings("ai")
    win.settings.setValue("ai_preset", "openai")
    win._ai_key.setText("sk-secret-1234")
    win._ai_save_key()

    assert stored == {"openai": "sk-secret-1234"}
    assert win._ai_key.text() == ""
    assert "1234" in win._ai_key_state.text()

    win._ai_clear_key()
    assert stored == {}


def test_attach_file_loads_its_contents_into_the_input(test_window, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    sample = tmp_path / "crash.log"
    sample.write_text("IMEI 356938035643809 failed\n", encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(sample), "")
    )

    win = test_window()
    win._on_section("ai")
    win._ai_input.setPlainText("what happened?")
    win._ai_attach()
    text = win._ai_input.toPlainText()
    assert "what happened?" in text
    assert "attached: crash.log" in text
    assert "356938035643809" not in text
