"""Dependency-free retrieval over FlashPilot's operation notes.

The corpus is the hand-written research under ``operations/`` (about 112
files, ~290 KB). That is small enough to index in memory at first use, and
small enough that a BM25-lite ranking over heading chunks is accurate enough
— no embeddings, no vector database, no new runtime dependency.

Installed packages may not ship ``operations/``; when the directory is absent
:func:`default_index` returns ``None`` and callers fall back to the capability
card alone (still grounded, just less prose).
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass

_STOPWORDS = frozenset(
    """a an and are as at be been but by can could did do does for from had has
    have how i if in into is it its may might more most no not of on or other
    our out over said same see should so some such than that the their them
    then there these they this those to too under up use used using was we
    were what when where which while who why will with would you your""".split()
)

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9_.:+-]{1,}")
_HEADING_RE = re.compile(r"^(#{2,3})\s+(.*)$")


@dataclass(frozen=True)
class Chunk:
    """One retrievable slice of a markdown document."""

    path: str
    heading: str
    text: str


def _tokenize(text: str) -> list[str]:
    return [
        tok
        for tok in _WORD_RE.findall(text.lower())
        if tok not in _STOPWORDS and len(tok) > 1
    ]


def _split_chunks(path: str, text: str, max_chars: int = 1600) -> list[Chunk]:
    """Split a document at ``##``/``###`` headings, then at blank lines."""
    chunks: list[Chunk] = []
    heading = os.path.basename(path)
    body: list[str] = []

    def flush() -> None:
        content = "\n".join(body).strip()
        if not content:
            return
        if len(content) <= max_chars:
            chunks.append(Chunk(path, heading, content))
            return
        paragraphs: list[str] = []
        current: list[str] = []
        size = 0
        for para in content.split("\n\n"):
            if size + len(para) > max_chars and current:
                paragraphs.append("\n\n".join(current))
                current, size = [para], len(para)
            else:
                current.append(para)
                size += len(para) + 2
        if current:
            paragraphs.append("\n\n".join(current))
        for piece in paragraphs:
            chunks.append(Chunk(path, heading, piece))

    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            flush()
            body = []
            heading = match.group(2).strip() or heading
        else:
            body.append(line)
    flush()
    return chunks


class KnowledgeIndex:
    """In-memory BM25 index over markdown documents."""

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self._tokens = [Counter(_tokenize(c.text)) for c in chunks]
        self._lengths = [sum(c.values()) for c in self._tokens]
        self._avg_len = (sum(self._lengths) / len(self._lengths)) if chunks else 0.0
        df: Counter = Counter()
        for counts in self._tokens:
            df.update(counts.keys())
        total = len(chunks) or 1
        self._idf = {
            term: math.log(1 + (total - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def __len__(self) -> int:
        return len(self.chunks)

    def search(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]:
        """Return the *k* best chunks for *query*, best first."""
        terms = _tokenize(query)
        if not terms or not self.chunks:
            return []
        k1, b = 1.5, 0.75
        scored: list[tuple[float, int]] = []
        for idx, counts in enumerate(self._tokens):
            score = 0.0
            norm = k1 * (1 - b + b * (self._lengths[idx] / (self._avg_len or 1)))
            for term in set(terms):
                freq = counts.get(term, 0)
                if not freq:
                    continue
                score += self._idf.get(term, 0.0) * (
                    freq * (k1 + 1) / (freq + norm)
                )
            if score > 0:
                scored.append((score, idx))
        scored.sort(reverse=True)
        return [(self.chunks[i], score) for score, i in scored[: max(1, k)]]

    def render(self, query: str, k: int = 4, max_chars: int = 2400) -> str:
        """Render the best chunks as a compact, source-labelled block."""
        hits = self.search(query, k=k)
        if not hits:
            return ""
        out: list[str] = []
        used = 0
        for chunk, _score in hits:
            header = f"[{chunk.path} · {chunk.heading}]"
            piece = f"{header}\n{chunk.text.strip()}"
            if used + len(piece) > max_chars:
                continue
            out.append(piece)
            used += len(piece)
        return "\n\n".join(out)


def build_from_root(root: str) -> KnowledgeIndex | None:
    """Index every ``*.md`` under *root*; ``None`` when the tree is absent."""
    if not root or not os.path.isdir(root):
        return None
    chunks: list[Chunk] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            if not name.lower().endswith(".md"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            try:
                with open(full, encoding="utf-8") as fh:
                    text = fh.read()
            except OSError:
                continue
            chunks.extend(_split_chunks(rel, text))
    if not chunks:
        return None
    return KnowledgeIndex(chunks)


def candidate_roots() -> list[str]:
    """Where the operation notes may live (repo checkout, then install)."""
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    return [
        os.path.join(repo, "operations"),
        "/usr/share/flashpilot/operations",
    ]


_INDEX: KnowledgeIndex | None = None
_INDEX_ROOT: str | None = None


def default_index() -> KnowledgeIndex | None:
    """The shared index for this process (built on first use, then cached)."""
    global _INDEX, _INDEX_ROOT
    if _INDEX is not None:
        return _INDEX
    for root in candidate_roots():
        if _INDEX_ROOT is not None and root == _INDEX_ROOT:
            continue
        index = build_from_root(root)
        if index is not None:
            _INDEX, _INDEX_ROOT = index, root
            return _INDEX
        _INDEX_ROOT = root
    return None


def reset_default_index() -> None:
    """Drop the cached index (tests, or after an install changes the corpus)."""
    global _INDEX, _INDEX_ROOT
    _INDEX, _INDEX_ROOT = None, None
