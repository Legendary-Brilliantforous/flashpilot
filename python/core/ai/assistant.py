"""The FlashPilot Assistant — local, text-based, knowledge-grounded.

This is the assistant layer *behind* the LLM chat advisor: a text-based
assistant that reads FlashPilot's own knowledge base and answers from it.

It is built on the same BM25-lite :class:`~python.core.ai.retrieval.KnowledgeIndex`
used by the advisor, but over the *combined* corpus — operation notes, docs and
the flow registry (``src/flows.rs``) — so it understands every FlashPilot flow,
job, mode, document and repo text we have.

It is error-aware: pass a console tail (from the live window, an attached file or
a pasted failure) and the assistant grounds the answer in the known failure
causes the tail actually matches, alongside the retrieved notes.

It is device-aware: the selected device (ADB status, model, transport, mode) can
be folded into the answer, so "is the ADB connected?" gets a grounded reply.

It is command-aware: flow keys mentioned in a question are resolved against the
real registry, so near-miss commands ("frp_adb") are corrected to the real key
("adb_frp") instead of being answered blindly.

Today it is deliberately text-based and read-only: it retrieves and answers
from the corpus, citing sources. The roadmap (per the Advisor design) is for it
to grow into the local assistant that eventually debugs problems, flashes and
removes locks — but it must never execute anything, and it must never invent
commands that do not exist.

Nothing here calls an LLM and nothing here executes a flow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import errors, guard
from .retrieval import KnowledgeIndex

# Snake_case identifiers are how FlashPilot names its flows (``adb_frp``,
# ``frp_browser``, ``mtk_frp``, ``odin_flash_tar`` …); kebab-case variants
# (``adb-frp``) normalize onto the same shape.
_FLOW_KEY_RE = re.compile(r"\b[a-z][a-z0-9]*(?:[_\-][a-z0-9]+)+\b")

# Tokens that switch the assistant into "explain the failure / check the
# connection" mode, where live device context is relevant.
_CONTEXT_TOKENS = (
    "adb",
    "connect",
    "device",
    "transport",
    "mode",
    "unauthor",
    "permission",
    "usb",
    "fastboot",
    "lock",
)


DEFAULT_TOP_K = 4
DEFAULT_MAX_ANSWER_CHARS = 2400


@dataclass
class AssistantAnswer:
    """A retrieved, source-cited answer from the FlashPilot Assistant."""

    question: str
    answer: str
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.0
    complete: bool = True
    corrections: list[str] = field(default_factory=list)


class FlashPilotAssistant:
    """Text-based assistant over FlashPilot's full knowledge base."""

    def __init__(
        self,
        index: KnowledgeIndex | None = None,
        top_k: int = DEFAULT_TOP_K,
        max_answer_chars: int = DEFAULT_MAX_ANSWER_CHARS,
        flows: list[dict] | None = None,
    ):
        self.index = index
        self.top_k = max(1, int(top_k))
        self.max_answer_chars = max(1, int(max_answer_chars))
        self.flows = list(flows or [])

    @classmethod
    def from_default(cls, flows: list[dict] | None = None) -> "FlashPilotAssistant":
        """Build the assistant over the shared default corpus index."""
        from . import retrieval

        return cls(index=retrieval.default_index(), flows=flows)

    # ------------------------------------------------------------------
    # Flow awareness — flow-key retrieval + command correction
    # ------------------------------------------------------------------
    def _flow_key_mentions(self, question: str) -> list[str]:
        """Normalized flow keys mentioned in *question*, in order of appearance."""
        found: list[str] = []
        for match in _FLOW_KEY_RE.finditer(question or ""):
            token = re.sub(r"[^a-z0-9]+", "_", match.group(0).lower()).strip("_")
            if token and token not in found:
                found.append(token)
        return found

    def _resolve_flow(self, token: str, flows: list[dict] | None) -> tuple[dict | None, bool]:
        """Resolve a mentioned flow token against the real registry.

        Returns ``(flow, corrected)`` — *corrected* is True when the token did
        not match a real key but fuzzy-matched a flow label (the user used a
        wrong command; we are correcting them).
        """
        norm = re.sub(r"[^a-z0-9]+", "_", str(token).strip().lower()).strip("_")
        registry = [f for f in (flows if flows is not None else self.flows) or [] if isinstance(f, dict)]
        best: dict | None = None
        best_score = 0
        for flow in registry:
            key = str(flow.get("key") or "")
            if not key:
                continue
            if key.strip().lower().replace("-", "_") == norm:
                return flow, False
            label = str(flow.get("label") or "").lower()
            score = sum(1 for word in norm.split("_") if len(word) > 2 and word in label)
            if score > best_score:
                best, best_score = flow, score
        if best is None or best_score <= 0:
            return None, False
        return best, True

    def _flow_context(
        self, question: str, flows: list[dict] | None, top_k: int
    ) -> tuple[list[tuple], list[str]]:
        """Flow-key hits for the question plus any command corrections."""
        hits: list[tuple] = []
        corrections: list[str] = []
        if self.index is None:
            return hits, corrections
        tokens = self._flow_key_mentions(question)
        if not tokens:
            return hits, corrections
        seen: set = set()
        for token in tokens:
            flow, corrected = self._resolve_flow(token, flows)
            if corrected and flow is not None:
                corrections.append(
                    f"Command correction: `{token}` is not a FlashPilot flow key — "
                    f"the right key is `{flow.get('key')}`."
                )
            for chunk, score in self.index.search(token, k=top_k):
                if chunk in seen:
                    continue
                seen.add(chunk)
                hits.append((chunk, score))
        return hits, corrections

    # ------------------------------------------------------------------
    # Device context
    # ------------------------------------------------------------------
    def _device_context(self, device: dict | None) -> str:
        """One-line redacted device context (ADB status, model, mode …)."""
        if not device:
            return ""
        parts: list[str] = []
        adb = str(device.get("adb") or "").strip()
        if adb:
            parts.append(f"ADB status: {adb}")
        for key, label in (
            ("model", "Model"),
            ("transport", "Transport"),
            ("mode", "Mode"),
            ("device_type", "Form factor"),
            ("android", "Android"),
        ):
            value = str(device.get(key) or "").strip()
            if value:
                parts.append(f"{label}: {value}")
        if not parts:
            return ""
        return "Device context: " + " · ".join(guard.redact(p) for p in parts)

    def _needs_context(self, question: str, error_hits: list) -> bool:
        """Does this question / failure call for live device context?"""
        if error_hits:
            return True
        q = (question or "").lower()
        return any(token in q for token in _CONTEXT_TOKENS)

    # ------------------------------------------------------------------
    # Answering
    # ------------------------------------------------------------------
    def ask(
        self,
        question: str,
        *,
        log_tail: str = "",
        device: dict | None = None,
        flows: list[dict] | None = None,
    ) -> AssistantAnswer:
        """Retrieve and return a text answer for *question*.

        *log_tail* (console output) grounds the answer in matched known causes;
        *device* (live device state) is folded in when relevant;
        *flows* (the flow registry) enables command correction.

        Returns an :class:`AssistantAnswer` with the retrieved text (or an
        explicit "not complete" marker when nothing could be retrieved). The
        answer is assembled from the best-matching knowledge-base chunks, plus
        any flow chunks named by flow keys in the question, plus any failure
        causes matched in the console tail. It cites its sources and may carry
        command corrections.
        """
        question = (question or "").strip()
        if not question or self.index is None:
            return AssistantAnswer(
                question=question, answer="", sources=[], confidence=0.0, complete=False
            )

        hits = list(self.index.search(question, k=self.top_k))
        flow_hits, corrections = self._flow_context(question, flows, self.top_k)
        for chunk, score in flow_hits:
            if any(existing == chunk for existing, _score in hits):
                continue
            hits.append((chunk, score))

        error_hits = errors.match(log_tail, limit=6) if log_tail else []
        sections: list[str] = []
        if corrections:
            sections.extend(corrections)
        device_context = ""
        if self._needs_context(question, error_hits):
            device_context = self._device_context(device)
            if device_context:
                sections.insert(0, device_context)
        used = 0
        sources: list[str] = []
        for chunk, score in hits:
            piece = f"[{chunk.path} · {chunk.heading}]\n{chunk.text.strip()}"
            if used + len(piece) > self.max_answer_chars:
                continue
            sections.append(piece)
            used += len(piece)
            if chunk.path not in sources:
                sources.append(chunk.path)
        for cause, line in error_hits:
            piece = f"[console · {cause.title}]\nWhy: {cause.why}\nFix: {cause.fix}"
            if cause.risk:
                piece = f"{piece}\nRisk: {cause.risk}"
            if line:
                piece = f"{piece}\nMatched: {line}"
            if used + len(piece) > self.max_answer_chars:
                break
            sections.append(piece)
            used += len(piece)
        answer = "\n\n".join(sections).strip()
        confidence = sum(score for _chunk, score in hits) / len(hits) if hits else 0.0
        return AssistantAnswer(
            question=question,
            answer=answer,
            sources=sources,
            confidence=confidence,
            complete=bool(answer),
            corrections=list(corrections),
        )
