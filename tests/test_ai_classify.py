"""Failure classifier -> candidate flows."""

from __future__ import annotations

from python.core.ai import classify

FLOWS = [
    {"key": "odin_flash_tar", "label": "Flash firmware tar", "job": "Flash Firmware", "mode": "Download"},
    {"key": "odin_frp", "label": "Remove FRP", "job": "Remove FRP", "mode": "Download"},
    {"key": "odin_pit_tools", "label": "PIT tools", "job": "PIT", "mode": "Download"},
    {"key": "mtk_frp", "label": "Remove FRP (BROM)", "job": "Remove FRP", "mode": "MTK"},
    {"key": "mtk_detect", "label": "Detect MTK", "job": "Detect", "mode": "MTK"},
    {"key": "adb_info", "label": "ADB info", "job": "Read Device Info", "mode": "ADB"},
    {"key": "detect", "label": "Detect", "job": "Detect", "mode": "ADB"},
]


def test_unauthorised_adb_suggests_adb_info():
    log = "error: not authorized\n"
    suggestions = classify.classify(log, FLOWS)
    keys = [s.key for s in suggestions]
    assert "adb_info" in keys
    assert all(s.section in ("adb", "general", "samsung") for s in suggestions)


def test_pit_mismatch_suggests_pit_tools():
    log = "scatter parse error\n"
    suggestions = classify.classify(log, FLOWS)
    keys = [s.key for s in suggestions]
    assert "odin_pit_tools" in keys


def test_no_flows_returns_empty():
    assert classify.classify("error: not authorized", []) == []


def test_unknown_keys_are_filtered_out():
    log = "error: not authorized\n"
    suggestions = classify.classify(log, FLOWS)
    for s in suggestions:
        assert s.key in {f["key"] for f in FLOWS}


def test_limit_is_respected():
    log = "error: not authorized\n" + "not authorized\n" * 5
    suggestions = classify.classify(log, FLOWS, limit=2)
    assert len(suggestions) <= 2


def test_question_keyword_fallback():
    suggestions = classify.classify("", FLOWS, question="how do I remove frp?")
    keys = [s.key for s in suggestions]
    assert "odin_frp" in keys or "mtk_frp" in keys


def test_section_mapping():
    assert classify._section_for("MTK BROM") == "mtk"
    assert classify._section_for("Download") == "samsung"
    assert classify._section_for("ADB") == "adb"
    assert classify._section_for("EDL") == "qc"
