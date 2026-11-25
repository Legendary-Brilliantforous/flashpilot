"""Persisted, deletable chat history."""

from __future__ import annotations

import json
import os
import stat

from python.core.ai.history import ChatHistory


def test_append_persists_and_reloads(tmp_path):
    path = tmp_path / "ai_history.json"
    history = ChatHistory(str(path))
    history.append("user", "why did odin fail?")
    history.append("assistant", "because the device left download mode")

    reloaded = ChatHistory(str(path))
    assert [m["role"] for m in reloaded.messages] == ["user", "assistant"]
    assert reloaded.messages[0]["content"] == "why did odin fail?"


def test_file_is_private(tmp_path):
    path = tmp_path / "ai_history.json"
    ChatHistory(str(path)).append("user", "hello")
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600


def test_clear_deletes_the_file_and_memory(tmp_path):
    path = tmp_path / "ai_history.json"
    history = ChatHistory(str(path))
    history.append("user", "hello")
    assert path.exists()
    history.clear()
    assert not path.exists()
    assert len(history) == 0
    assert ChatHistory(str(path)).messages == []


def test_limit_keeps_the_newest_messages(tmp_path):
    path = tmp_path / "ai_history.json"
    history = ChatHistory(str(path), limit=10)
    for i in range(15):
        history.append("user", f"m{i}")
    assert len(history) == 10
    assert history.messages[-1]["content"] == "m14"
    assert history.messages[0]["content"] == "m5"


def test_corrupt_file_is_treated_as_empty(tmp_path):
    path = tmp_path / "ai_history.json"
    path.write_text("{not json", encoding="utf-8")
    assert ChatHistory(str(path)).messages == []


def test_unknown_roles_are_rejected_and_bad_rows_skipped(tmp_path):
    path = tmp_path / "ai_history.json"
    history = ChatHistory(str(path))
    try:
        history.append("system", "nope")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("system role should be rejected")

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "messages": [
                    {"role": "user", "content": "ok"},
                    {"role": "tool", "content": "skipped"},
                    "garbage",
                ],
            }
        ),
        encoding="utf-8",
    )
    loaded = ChatHistory(str(path)).messages
    assert len(loaded) == 1
    assert loaded[0]["role"] == "user"
    assert loaded[0]["content"] == "ok"


def test_replace_last_updates_the_streaming_reply(tmp_path):
    path = tmp_path / "ai_history.json"
    history = ChatHistory(str(path))
    history.append("user", "q")
    history.append("assistant", "partial")
    history.replace_last("assistant", "partial answer")
    assert history.messages[-1]["content"] == "partial answer"
    assert len(history) == 2
