"""Retrieval over the operation notes (stdlib BM25-lite)."""

from __future__ import annotations

from python.core.ai import retrieval


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_chunks_split_at_headings_and_rank_by_query(tmp_path):
    root = tmp_path / "operations"
    _write(
        root,
        "frp/samsung.md",
        "# Samsung FRP\n\nIntro text.\n\n"
        "## ADB path\n\nUse adb shell settings to clear the setup wizard.\n\n"
        "## BROM path\n\nEnter BROM, upload the DA, then clear the FRP partition.\n",
    )
    _write(
        root,
        "flash/mtk.md",
        "## Scatter\n\nThe scatter file names every partition for MTK flashing.\n",
    )
    index = retrieval.build_from_root(str(root))
    assert index is not None
    assert len(index) >= 3

    hits = index.search("brom preloader DA", k=1)
    assert hits and hits[0][0].heading == "BROM path"

    hits = index.search("scatter partition", k=1)
    assert hits and hits[0][0].path == "flash/mtk.md"


def test_long_sections_are_split_without_losing_content(tmp_path):
    root = tmp_path / "operations"
    body = "\n\n".join(f"paragraph {i} " + "x" * 200 for i in range(12))
    _write(root, "big.md", "## Big\n\n" + body)
    index = retrieval.build_from_root(str(root))
    assert index is not None
    assert len(index) > 1
    joined = "\n".join(chunk.text for chunk in index.chunks)
    assert "paragraph 0" in joined and "paragraph 11" in joined


def test_render_labels_every_chunk_with_its_source(tmp_path):
    root = tmp_path / "operations"
    _write(root, "frp/index.md", "## ADB\n\nADB FRP removal steps.\n")
    index = retrieval.build_from_root(str(root))
    rendered = index.render("adb frp", k=2)
    assert "[frp/index.md · ADB]" in rendered


def test_missing_root_returns_none(tmp_path):
    assert retrieval.build_from_root(str(tmp_path / "nope")) is None
    assert retrieval.build_from_root("") is None


def test_default_index_finds_the_repo_corpus():
    retrieval.reset_default_index()
    try:
        index = retrieval.default_index()
        assert index is not None, "operations/ should be indexed in a checkout"
        assert len(index) > 50
    finally:
        retrieval.reset_default_index()


def test_empty_query_returns_nothing(tmp_path):
    root = tmp_path / "operations"
    _write(root, "a.md", "## A\n\nsome text\n")
    index = retrieval.build_from_root(str(root))
    assert index.search("") == []
    assert index.search("the and of") == []
