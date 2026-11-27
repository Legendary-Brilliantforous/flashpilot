"""FlashPilot Assistant — local, text-based, knowledge-grounded."""

from __future__ import annotations

from python.core.ai import assistant, retrieval


def _flows_file(path, job: str = "Frp") -> None:
    path.write_text(
        f'flow!("frp_adb", "Remove FRP (ADB)", "{job}", "ADB")\n'
        'flow!("frp_brom", "Remove FRP (BROM)", "Frp", "MTK")\n',
        encoding="utf-8",
    )


def test_assistant_answers_from_the_corpus(tmp_path):
    idx = retrieval.build_combined([str(tmp_path)], None)
    adv = assistant.FlashPilotAssistant(index=idx)
    answer = adv.ask("brom preloader da")
    # The temp corpus has no such content -> not complete.
    assert answer.complete is False
    assert answer.answer == ""


def test_assistant_cites_sources_and_is_complete_when_relevant(tmp_path):
    ops = tmp_path / "operations"
    ops.mkdir()
    (ops / "frp" / "index.md").parent.mkdir(parents=True, exist_ok=True)
    (ops / "frp" / "index.md").write_text(
        "# FRP\n\nUse the ADB setup wizard path after authorization.\n", encoding="utf-8"
    )
    idx = retrieval.build_combined([str(tmp_path)], None)
    adv = assistant.FlashPilotAssistant(index=idx)
    answer = adv.ask("adb frp setup wizard authorization")
    assert answer.complete is True
    assert "[operations/frp/index.md" in answer.answer
    assert answer.sources
    assert answer.sources[0].startswith("operations/")
    assert answer.confidence > 0


def test_assistant_without_index_is_not_complete():
    adv = assistant.FlashPilotAssistant(index=None)
    answer = adv.ask("what flows exist?")
    assert answer.complete is False
    assert answer.answer == ""
    assert answer.sources == []


def test_assistant_empty_question_is_not_complete():
    adv = assistant.FlashPilotAssistant(index=None)
    answer = adv.ask("   ")
    assert answer.complete is False


def test_assistant_answers_flow_key_mentions_via_flow_chunks(tmp_path):
    flows = tmp_path / "flows.rs"
    _flows_file(flows)
    idx = retrieval.build_combined([str(tmp_path)], str(flows))
    adv = assistant.FlashPilotAssistant(index=idx)
    answer = adv.ask("what does frp_adb do?")
    assert answer.complete is True
    assert "src/flows.rs" in answer.answer
    assert any(s.startswith("src/") for s in answer.sources)


def test_assistant_from_default_uses_the_real_corpus():
    adv = assistant.FlashPilotAssistant.from_default()
    assert adv.index is not None
    assert len(adv.index) > 0
    answer = adv.ask("odin download mode frp")
    # The real repo corpus is large; some retrieval should happen.
    assert isinstance(answer.sources, list)


def test_assistant_flow_chunks_are_retrievable(tmp_path):
    flows = tmp_path / "flows.rs"
    _flows_file(flows)
    idx = retrieval.build_combined([str(tmp_path)], str(flows))
    adv = assistant.FlashPilotAssistant(index=idx)
    answer = adv.ask("remove frp")
    assert answer.complete is True
    assert "src/flows.rs" in answer.answer
    assert any(s.startswith("src/") for s in answer.sources)
