"""The AI audit log stores hashes and drops anything secret-shaped."""

from __future__ import annotations

import json
import os
import stat

from python.core.ai import audit


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_log_event_hashes_the_question_and_drops_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    question = "why is my imei 356938035643809 rejected?"
    audit.log_event(
        "request",
        question=question,
        provider="openai",
        model="gpt-test",
        api_key="sk-should-never-appear",
        authorization="Bearer nope",
        tokens_in=42,
    )
    path = audit.audit_path()
    assert os.path.exists(path)
    rows = _read(path)
    assert len(rows) == 1
    row = rows[0]
    assert row["event"] == "request"
    assert row["feature"] == "ai_advisor"
    assert row["experimental"] is False
    assert row["provider"] == "openai"
    assert row["tokens_in"] == 42
    assert "api_key" not in row
    assert "authorization" not in row
    assert row["question_sha256"] == audit.hash_question(question)
    raw = open(path, encoding="utf-8").read()
    assert "356938035643809" not in raw
    assert "sk-should-never-appear" not in raw
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_audit_never_raises_when_the_directory_is_unwritable(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(blocker))
    audit.log_event("error", provider="openai", detail="boom")  # must not raise


def test_hash_is_stable_and_short():
    digest = audit.hash_question("same question")
    assert digest == audit.hash_question("  same question  ")
    assert len(digest) == 32
    assert digest != audit.hash_question("different question")
