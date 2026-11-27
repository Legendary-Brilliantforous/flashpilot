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


def test_assistant_corrects_a_wrong_flow_key_to_the_real_one(tmp_path):
    flows = tmp_path / "flows.rs"
    flows.write_text(
        'flow!("adb_frp", "ADB FRP clear", "Remove FRP", "ADB")\n',
        encoding="utf-8",
    )
    idx = retrieval.build_combined([str(tmp_path)], str(flows))
    adv = assistant.FlashPilotAssistant(
        index=idx,
        flows=[{"key": "adb_frp", "label": "ADB FRP clear", "job": "Remove FRP", "mode": "ADB"}],
    )
    answer = adv.ask("what does frp_adb do?")
    assert answer.complete is True
    assert any("Command correction" in c for c in answer.corrections)
    assert any("adb_frp" in c for c in answer.corrections)


def test_assistant_grounds_the_answer_in_matched_failure_causes(tmp_path):
    ops = tmp_path / "operations"
    (ops / "adb").mkdir(parents=True)
    (ops / "adb" / "index.md").write_text(
        "# ADB setup\n\nAuthorize USB debugging before any ADB flow.\n", encoding="utf-8"
    )
    idx = retrieval.build_combined([str(tmp_path)], None)
    adv = assistant.FlashPilotAssistant(index=idx)
    answer = adv.ask("why did the adb frp flow fail?", log_tail="error: not authorized")
    assert answer.complete is True
    assert "ADB is not authorised on the device" in answer.answer
    assert "Authorize USB debugging" in answer.answer


def test_assistant_includes_device_context_for_connection_questions(tmp_path):
    ops = tmp_path / "operations"
    ops.mkdir()
    (ops / "index.md").write_text("# Operations\n\nGeneral notes.\n", encoding="utf-8")
    idx = retrieval.build_combined([str(tmp_path)], None)
    adv = assistant.FlashPilotAssistant(index=idx)
    answer = adv.ask(
        "is adb connected to the phone?",
        device={"adb": "connected", "model": "SM-S911B"},
    )
    assert answer.complete is True
    assert "ADB status: connected" in answer.answer
    assert "Model: SM-S911B" in answer.answer


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
