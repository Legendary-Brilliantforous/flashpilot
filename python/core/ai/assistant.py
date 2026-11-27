"""The FlashPilot Assistant — local, text-based, knowledge-grounded.

This is the assistant layer *behind* the LLM chat advisor: a text-based
assistant that reads FlashPilot's own knowledge base and answers from it.

It is built on the same BM25-lite :class:`~python.core.ai.retrieval.KnowledgeIndex`
used by the advisor, but over the *combined* corpus — operation notes, docs and
the flow registry (``src/flows.rs``) — so it understands every FlashPilot flow,
job, mode, document and repo text we have.

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

from .retrieval import KnowledgeIndex

# Snake-case identifiers are how FlashPilot names its flows (``frp_adb``,
# ``mtk_frp``, ``odin_flash_tar`` …) — the shape the user/LLM chat would use.
_FLOW_KEY_RE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")


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
    def from_default(cls) -> "FlashPilotAssistant":
        """Build the assistant over the shared default corpus index."""
        from . import retrieval

        return cls(index=retrieval.default_index())

    # ------------------------------------------------------------------
    # Answering
    # ------------------------------------------------------------------
    def _flow_key_mentions(self, question: str) -> list[str]:
        """Snake-case flow identifiers mentioned in *question*, in order."""
        found: list[str] = []
        for match in _FLOW_KEY_RE.finditer(question or ""):
            token = match.group(0)
            if token not in found:
                found.append(token)
        return found

    def _flow_hits(self, question: str, top_k: int) -> list[tuple]:
        """Chunks describing flows explicitly named in *question*."""
        hits: list[tuple] = []
        if self.index is None:
            return hits
        for key in self._flow_key_mentions(question):
            for chunk, score in self.index.search(key, k=top_k):
                if chunk not in [h[0] for h in hits]:
                    hits.append((chunk, score))
        return hits

    def ask(self, question: str) -> AssistantAnswer:
        """Retrieve and return a text answer for *question*.

        The answer is assembled from the best-matching knowledge-base chunks,
        plus any flow chunks named by snake-case flow keys in the question.
        Returns an :class:`AssistantAnswer` with the retrieved text (or an
        explicit "not complete" marker when nothing could be retrieved). The
        answer cites its sources.
        """
        question = (question or "").strip()
        if not question or self.index is None:
            return AssistantAnswer(
                question=question, answer="", sources=[], confidence=0.0, complete=False
            )
        hits = list(self.index.search(question, k=self.top_k))
        flow_hits = self._flow_hits(question, self.top_k)
        for chunk, score in flow_hits:
            if chunk not in [h[0] for h in hits]:
                hits.append((chunk, score))
        if not hits:
            return AssistantAnswer(
                question=question, answer="", sources=[], confidence=0.0, complete=False
            )
        pieces: list[str] = []
        sources: list[str] = []
        used = 0
        for chunk, score in hits:
            piece = f"[{chunk.path} · {chunk.heading}]\n{chunk.text.strip()}"
            if used + len(piece) > self.max_answer_chars:
                continue
            pieces.append(piece)
            used += len(piece)
            if chunk.path not in sources:
                sources.append(chunk.path)
        answer = "\n\n".join(pieces).strip()
        confidence = sum(score for _chunk, score in hits) / len(hits)
        return AssistantAnswer(
            question=question,
            answer=answer,
            sources=sources,
            confidence=confidence,
            complete=bool(answer),
        )
