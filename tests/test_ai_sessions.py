"""Named chat sessions."""

from __future__ import annotations

import os
import tempfile

from python.core.ai import sessions


def test_create_switch_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    manager = sessions.SessionManager()
    assert manager.active_name in manager.list_names()
    name = manager.create("Work")
    assert name == "Work"
    assert "Work" in manager.list_names()
    manager.switch(manager.list_names()[0])
    manager.delete("Work")
    assert "Work" not in manager.list_names()


def test_rename_moves_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    manager = sessions.SessionManager()
    manager.create("Alpha")
    manager.rename("Alpha", "Beta")
    assert "Beta" in manager.list_names()
    assert "Alpha" not in manager.list_names()
    assert os.path.exists(os.path.join(sessions.sessions_dir(), "Beta.json"))


def test_cannot_delete_the_last_session(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    manager = sessions.SessionManager()
    only = manager.list_names()[0]
    manager.delete(only)
    assert manager.list_names() == [only]


def test_export_markdown_contains_messages(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    manager = sessions.SessionManager()
    manager.active.append("user", "hello")
    manager.active.append("assistant", "hi there")
    md = manager.export_markdown()
    assert "hello" in md
    assert "hi there" in md
    assert "## You" in md
    assert "## Advisor" in md


def test_legacy_transcript_is_migrated(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    legacy_dir = os.path.join(str(tmp_path), "flashpilot")
    os.makedirs(legacy_dir, exist_ok=True)
    legacy_path = os.path.join(legacy_dir, "ai_history.json")
    import json
    with open(legacy_path, "w", encoding="utf-8") as fh:
        json.dump({"version": 1, "messages": [{"role": "user", "content": "old", "ts": 1.0}]}, fh)
    manager = sessions.SessionManager()
    assert "old" in [m["content"] for m in manager.active.messages]
