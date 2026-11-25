"""Persisted chat history for the AI advisor.

History lives in the XDG data directory (``~/.local/share/flashpilot/
ai_history.json``) so a conversation survives a restart, and the file is
written atomically with ``0600`` permissions because transcripts can quote
device details.

It contains questions and answers only — never an API key, never the full
console log (only the excerpt the user chose to send is part of a message).
:meth:`ChatHistory.clear` deletes both the in-memory transcript and the file.
"""

from __future__ import annotations

import json
import os
import tempfile
import time

DEFAULT_LIMIT = 400
VERSION = 1


def default_path() -> str:
    """``$XDG_DATA_HOME/flashpilot/ai_history.json``."""
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "flashpilot", "ai_history.json")


class ChatHistory:
    """A small, bounded, persisted transcript."""

    def __init__(self, path: str | None = None, limit: int = DEFAULT_LIMIT):
        self.path = path or default_path()
        self.limit = max(10, int(limit))
        self._messages: list[dict] = []
        self.load()

    # -- reading ---------------------------------------------------------
    @property
    def messages(self) -> list[dict]:
        """A copy of the transcript (``{"role", "content", "ts"}`` dicts)."""
        return [dict(m) for m in self._messages]

    def __len__(self) -> int:
        return len(self._messages)

    def load(self) -> list[dict]:
        """Read the transcript from disk; a missing/corrupt file is empty."""
        self._messages = []
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return self._messages
        rows = data.get("messages") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return self._messages
        for row in rows:
            if not isinstance(row, dict):
                continue
            role = row.get("role")
            content = row.get("content")
            if role in ("user", "assistant") and isinstance(content, str):
                self._messages.append(
                    {
                        "role": role,
                        "content": content,
                        "ts": row.get("ts") or time.time(),
                    }
                )
        self._trim()
        return self.messages

    # -- writing ---------------------------------------------------------
    def append(self, role: str, content: str) -> None:
        """Add one message and persist immediately."""
        if role not in ("user", "assistant"):
            raise ValueError(f"unsupported role: {role!r}")
        self._messages.append(
            {"role": role, "content": str(content), "ts": time.time()}
        )
        self._trim()
        self.save()

    def replace_last(self, role: str, content: str) -> None:
        """Rewrite the newest message (used while a reply streams)."""
        if self._messages and self._messages[-1]["role"] == role:
            self._messages[-1]["content"] = str(content)
            self._messages[-1]["ts"] = time.time()
        else:
            self._messages.append(
                {"role": role, "content": str(content), "ts": time.time()}
            )
        self._trim()
        self.save()

    def save(self) -> None:
        """Atomically write ``0600`` JSON; failures are non-fatal."""
        directory = os.path.dirname(self.path) or "."
        try:
            os.makedirs(directory, exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                prefix=".ai_history-", suffix=".json", dir=directory
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(
                        {"version": VERSION, "messages": self._messages},
                        fh,
                        ensure_ascii=False,
                    )
                os.chmod(tmp, 0o600)
                os.replace(tmp, self.path)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except OSError:
            # A read-only home must not break the chat; keep it in memory.
            pass

    def clear(self) -> None:
        """Delete the transcript from memory and from disk."""
        self._messages = []
        try:
            os.unlink(self.path)
        except OSError:
            pass

    # -- internals -------------------------------------------------------
    def _trim(self) -> None:
        if len(self._messages) > self.limit:
            self._messages = self._messages[-self.limit :]
