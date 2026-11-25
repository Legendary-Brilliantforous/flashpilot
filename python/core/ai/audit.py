"""Audit trail for advisor requests.

Every question, provider call, refusal and failure is recorded in
``~/.local/share/flashpilot/ai_audit.jsonl`` — same directory and shape as the
EXPERIMENTAL audit log, but with its own file and ``experimental: false``.

Privacy rules baked into this module:

* the question text is stored as a **SHA-256 hash**, not verbatim;
* anything whose field name looks like a secret (key, token, password,
  secret, authorization) is dropped;
* long free-text details are truncated;
* the API key is never passed in, and even if it were, it would be dropped.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

try:  # version is optional so this module works standalone in tests
    from .. import APP_VERSION  # type: ignore
except Exception:  # noqa: BLE001
    APP_VERSION = "unknown"

_SECRET_HINTS = ("key", "token", "secret", "password", "authorization", "bearer")
_MAX_DETAIL = 500


def audit_path() -> str:
    """``$XDG_DATA_HOME/flashpilot/ai_audit.jsonl``."""
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "flashpilot", "ai_audit.jsonl")


def _clean(fields: dict) -> dict:
    out = {}
    for name, value in fields.items():
        lowered = name.lower()
        # A secret-shaped *name* only drops string values; numeric counters
        # such as ``tokens_in`` are safe and useful in the audit trail.
        if any(hint in lowered for hint in _SECRET_HINTS) and isinstance(
            value, str
        ):
            continue
        if isinstance(value, str) and len(value) > _MAX_DETAIL:
            value = value[:_MAX_DETAIL] + "…"
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[name] = value
        elif isinstance(value, (list, tuple)):
            out[name] = [str(v)[:80] for v in list(value)[:12]]
    return out


def hash_question(question: str) -> str:
    """Stable, non-reversible identifier for a question."""
    return hashlib.sha256((question or "").strip().encode("utf-8")).hexdigest()[:32]


def log_event(event: str, question: str | None = None, **fields) -> None:
    """Append one audit entry. Never raises."""
    entry = {
        "ts": time.time(),
        "ts_human": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "version": APP_VERSION,
        "feature": "ai_advisor",
        "event": event,
        "experimental": False,
    }
    if question is not None:
        entry["question_sha256"] = hash_question(question)
        entry["question_len"] = len(question or "")
    entry.update(_clean(fields))
    path = audit_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except OSError:
        pass
