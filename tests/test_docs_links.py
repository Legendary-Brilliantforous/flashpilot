"""Local-link integrity for the repository's Markdown (root docs + translations).

Regression: the translated docs shipped with the wrong relative depth in their
language switchers, e.g. ``docs/zh/CONTRIBUTING.md`` linked to
``../../ru/CONTRIBUTING.md``. GitHub resolves that to ``<repo>/ru/CONTRIBUTING.md``
and answers "The dev branch of flashpilot does not contain the path
ru/CONTRIBUTING.md." The English canonical copy of every document lives at the
repository root, so a translated page must use one level for siblings
(``../ru/CONTRIBUTING.md``) and two for the English file
(``../../CONTRIBUTING.md``).

These tests walk the real links so a mistranslated switcher (or a docs move)
fails here instead of on GitHub.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Every document that exists both in English (repo root) and per language.
CANONICAL_DOCS = (
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "DESCRIPTION.md",
    "INDEX.md",
    "README.md",
    "SECURITY.md",
    "design.md",
    "improvecore.md",
    "ui-improvement.md",
)
LANGS = ("ar", "de", "es", "fr", "hi", "ja", "pt", "ru", "tr", "zh")

_FENCE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def _markdown_files():
    """Every Markdown file whose local links must resolve."""
    files = sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").rglob("*.md"))
    return files


def _local_links(path):
    """Relative (non-URL, non-anchor) link targets in ``path``'s prose."""
    text = _FENCE.sub("", path.read_text(encoding="utf-8"))
    for match in _LINK.finditer(text):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "mailto:", "#", "<")):
            continue
        target = target.split("#", 1)[0]
        if target:
            yield target


def _id(path):
    return str(path.relative_to(ROOT))


@pytest.mark.parametrize("path", _markdown_files(), ids=_id)
def test_relative_links_resolve(path):
    broken = [
        target
        for target in _local_links(path)
        if not (path.parent / target).exists()
    ]
    assert not broken, f"{_id(path)} has links that do not resolve: {broken}"


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("name", CANONICAL_DOCS)
def test_translated_switcher_links_back_to_english(lang, name):
    """Every translated page offers a working way back to the English copy.

    Switchers are filled in as translations land, so they need not list every
    language — but the English canonical copy lives at the repository root and
    must be reachable with the right depth (``../../<name>`` from
    ``docs/<lang>/``).
    """
    path = ROOT / "docs" / lang / name
    if not path.is_file():
        pytest.skip(f"{_id(path)} is not translated yet")

    text = path.read_text(encoding="utf-8")
    switcher = next(
        (line for line in text.splitlines() if line.startswith("Language switcher")),
        None,
    )
    assert switcher, f"{_id(path)} has no language switcher line"
    assert f"](../../{name})" in switcher, (
        f"{_id(path)} does not link the English {name} correctly"
    )


def test_english_canonical_docs_exist_at_the_root():
    """The switchers' `../../<name>` targets are real files."""
    missing = [name for name in CANONICAL_DOCS if not (ROOT / name).is_file()]
    assert not missing, f"canonical documents missing from the repo root: {missing}"
