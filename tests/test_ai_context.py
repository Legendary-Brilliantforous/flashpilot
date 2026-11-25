"""Context assembly: capability grounding, redaction, budget truncation."""

from __future__ import annotations

from python.core.ai import context, guard

FLOWS = [
    {"key": "odin_flash_tar", "label": "Flash firmware tar", "job": "Flash Firmware", "mode": "ADB"},
    {"key": "odin_frp", "label": "Remove FRP", "job": "Remove FRP", "mode": "Download"},
    {"key": "mtk_frp", "label": "Remove FRP (BROM)", "job": "Remove FRP", "mode": "MTK"},
    {"key": "mtk_info", "label": "Device info", "job": "Read Device Info", "mode": "MTK"},
]

DEVICE = {
    "model": "SM-A125F",
    "brand": "Samsung",
    "chip": "Exynos 850",
    "mode": "MTP",
    "adb": "unauthorized",
    "serial": "R58M12ABCDE",
}


class _StubIndex:
    def render(self, query, k=4):
        return (
            "[operations/frp/samsung.md · Samsung]\n"
            "Samsung FRP removal uses the ADB setup-wizard path."
        )


def test_capability_card_lists_real_flows_and_lock_labels():
    card = context.capability_card(FLOWS)
    assert "odin_flash_tar" in card
    assert "odin_frp (Remove FRP)" in card
    assert "does not exist" in card


def test_capability_card_without_registry_refuses_to_invent_keys():
    card = context.capability_card(None)
    assert "Do not name flow keys" in card


def test_device_block_masks_the_serial():
    block = context.device_block(DEVICE)
    assert "SM-A125F" in block
    assert "unauthorized" in block
    assert "R58M12ABCDE" not in block
    assert "BCDE" in block


def test_build_messages_orders_system_history_and_question():
    history = [
        {"role": "user", "content": "older question"},
        {"role": "assistant", "content": "older answer"},
    ]
    built = context.build_messages(
        "why is ADB unauthorized?",
        flows=FLOWS,
        device=DEVICE,
        log_tail="error: not authorized",
        history=history,
        index=_StubIndex(),
    )
    roles = [m["role"] for m in built.messages]
    assert roles[0] == "system"
    assert roles[1:3] == ["user", "assistant"]
    assert roles[-1] == "user"
    final = built.messages[-1]["content"]
    assert "why is ADB unauthorized?" in final
    assert "<device_log>" in final
    assert "Samsung FRP removal" in final
    assert built.used_docs == ["operations/frp/samsung.md"]
    assert any("ADB is not authorised" in title for title in built.matched_causes)
    assert built.input_tokens > 0


def test_budget_drops_documents_then_log_before_the_question():
    built = context.build_messages(
        "why did the flash fail?",
        flows=FLOWS,
        device=DEVICE,
        log_tail="\n".join(f"line {i} not authorized" for i in range(400)),
        index=_StubIndex(),
        max_input_tokens=1500,
    )
    assert "documents" in built.dropped
    final = built.messages[-1]["content"]
    assert "why did the flash fail?" in final
    assert built.input_tokens <= 1500 + 50


def test_history_is_trimmed_to_the_requested_turns():
    history = []
    for i in range(10):
        history.append({"role": "user", "content": f"q{i}"})
        history.append({"role": "assistant", "content": f"a{i}"})
    built = context.build_messages(
        "current", flows=FLOWS, history=history, history_turns=2
    )
    contents = [m["content"] for m in built.messages[1:-1]]
    assert contents == ["q8", "a8", "q9", "a9"]


def test_redaction_applies_to_history_and_log():
    built = context.build_messages(
        "help",
        flows=FLOWS,
        device={"serial": "R58M12ABCDE"},
        log_tail="serial R58M12ABCDE imei 356938035643809",
        history=[{"role": "user", "content": "my imei is 356938035643809"}],
    )
    everything = "\n".join(m["content"] for m in built.messages)
    assert "356938035643809" not in everything
    assert "R58M12ABCDE" not in everything
    assert guard.mask_serial("R58M12ABCDE") in everything or "BCDE" in everything
