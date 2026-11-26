"""FlashPilot Advisor — the read-only AI assistant core.

This package answers questions about Android flashing and FRP/lock removal,
grounded in FlashPilot's own flow registry, device state, console output and
operation notes.

It is deliberately read-only: nothing here can execute a flow. The GUI passes
context in, receives text out, and the user decides what to run.

Public surface:

* :mod:`python.core.ai.provider` — OpenAI-compatible + Gemini streaming calls
* :mod:`python.core.ai.keys` — system-keyring API-key storage
* :mod:`python.core.ai.context` — prompt/context assembly with a token budget
* :mod:`python.core.ai.retrieval` — BM25-lite over ``operations/`` + docs + flows
* :mod:`python.core.ai.assistant` — the text-based FlashPilot Assistant
* :mod:`python.core.ai.guard` — domain policy, redaction, untrusted wrapping
* :mod:`python.core.ai.errors` — known failure causes from real log strings
* :mod:`python.core.ai.history` — persisted, deletable chat transcript
* :mod:`python.core.ai.audit` — hashed, secret-free request audit log
"""

from __future__ import annotations

from . import (
    assistant,
    audit,
    classify,
    context,
    errors,
    guard,
    history,
    keys,
    provider,
    retrieval,
)

__all__ = [
    "assistant",
    "audit",
    "classify",
    "context",
    "errors",
    "guard",
    "history",
    "keys",
    "provider",
    "retrieval",
]
