"""Context assembly for the AI advisor.

Builds the exact message list sent to a provider:

1. the system prompt (role, strict domain, safety rules, answer contract);
2. recent conversation turns;
3. one user turn holding the question plus grounded context —
   the capability card, the current device (redacted), matched failure
   causes, the console tail, and retrieved operation notes.

The bundle has a token budget. When it is exceeded, context is dropped in a
fixed order — retrieved documents first, then the console tail, then the
oldest history — so the question and the device state always survive.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import errors, guard
from .provider import estimate_tokens

DEFAULT_MAX_INPUT_TOKENS = 6000
DEFAULT_LOG_LINES = 120
DEFAULT_HISTORY_TURNS = 6

_LOCK_HINTS = ("frp", "lock", "mdm", "unlock", "carrier", "knox")


@dataclass
class AdvisorContext:
    """A ready-to-send bundle plus what went into it."""

    messages: list[dict]
    used_docs: list[str] = field(default_factory=list)
    matched_causes: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    input_tokens: int = 0


def capability_card(flows, max_flows_per_mode: int = 40) -> str:
    """Render the real flow registry as a compact capability list.

    Grounding the model in the flows that actually exist is what stops it
    inventing a command. Lock-removal jobs also get their human labels.
    """
    if not flows:
        return (
            "FlashPilot flow list unavailable. Do not name flow keys; describe "
            "methods generically and tell the user to open the matching page."
        )

    grouped: dict[str, dict[str, list[dict]]] = {}
    for flow in flows:
        if not isinstance(flow, dict):
            continue
        job = (flow.get("job") or "Other").strip()
        mode = (flow.get("mode") or "—").strip()
        grouped.setdefault(job, {}).setdefault(mode, []).append(flow)

    lines = [
        "FlashPilot flows that exist (the only methods you may recommend):",
    ]
    for job in sorted(grouped):
        lock_job = any(hint in job.lower() for hint in _LOCK_HINTS)
        for mode in sorted(grouped[job]):
            entries = grouped[job][mode][:max_flows_per_mode]
            if lock_job:
                names = ", ".join(
                    f"{f.get('key')} ({f.get('label')})" for f in entries
                )
            else:
                names = ", ".join(str(f.get("key")) for f in entries)
            lines.append(f"- {job} [{mode}]: {names}")
    lines.append(
        "Anything not listed above does not exist in FlashPilot — say so "
        "plainly instead of suggesting it."
    )
    return "\n".join(lines)


def device_block(device: dict | None) -> str:
    """Render the current device with identifiers masked."""
    if not device:
        return "No device is currently selected in FlashPilot."
    fields = (
        ("model", "Model"),
        ("brand", "Brand"),
        ("chip", "Chip"),
        ("engine", "Engine"),
        ("device_type", "Form factor"),
        ("transport", "Transport"),
        ("mode", "USB mode"),
        ("adb", "ADB status"),
        ("android", "Android"),
        ("build", "Build"),
    )
    lines = ["Current device (selected in FlashPilot):"]
    for key, label in fields:
        value = device.get(key)
        if value:
            lines.append(f"- {label}: {guard.redact(str(value))}")
    serial = device.get("serial")
    if serial:
        lines.append(f"- Serial: {guard.mask_serial(serial)}")
    if len(lines) == 1:
        lines.append("- No identity details are available yet (run Detect).")
    return "\n".join(lines)


def _tail(text: str, max_lines: int) -> str:
    if not text:
        return ""
    lines = str(text).splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
        return "…(earlier lines omitted)\n" + "\n".join(lines)
    return "\n".join(lines)


def _history_messages(history, turns: int, serial: str | None = None) -> list[dict]:
    if not history:
        return []
    rows = list(history)[-max(0, turns) * 2 :]
    out: list[dict] = []
    for row in rows:
        role = row.get("role")
        content = row.get("content") or ""
        if role in ("user", "assistant") and content:
            if serial:
                content = content.replace(serial, guard.mask_serial(serial))
            out.append(
                {
                    "role": role,
                    "content": guard.redact(content)[:2000],
                }
            )
    return out


def _compose(
    question: str,
    capability: str,
    device_text: str,
    causes_text: str,
    docs_text: str,
    log_text: str,
    history: list[dict],
) -> list[dict]:
    blocks: list[str] = []
    if capability:
        blocks.append("## Capabilities\n" + capability)
    if device_text:
        blocks.append("## Device\n" + device_text)
    if causes_text:
        blocks.append("## Known causes\n" + causes_text)
    if log_text:
        blocks.append(
            "## Console tail\n" + guard.wrap_untrusted("device_log", log_text)
        )
    if docs_text:
        blocks.append(
            "## Relevant notes\n" + guard.wrap_untrusted("document", docs_text)
        )
    body = "\n\n".join(blocks)
    user_content = (
        f"Question: {question.strip()}\n\n{body}" if body else question.strip()
    )
    messages = [{"role": "system", "content": guard.system_prompt()}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_content})
    return messages


def _total_tokens(messages: list[dict]) -> int:
    return sum(estimate_tokens(m.get("content") or "") for m in messages)


def build_messages(
    question: str,
    *,
    flows=None,
    device: dict | None = None,
    log_tail: str = "",
    history=None,
    index=None,
    include_docs: bool = True,
    max_input_tokens: int = DEFAULT_MAX_INPUT_TOKENS,
    log_lines: int = DEFAULT_LOG_LINES,
    history_turns: int = DEFAULT_HISTORY_TURNS,
) -> AdvisorContext:
    """Assemble the advisor request within *max_input_tokens*.

    *history* is a list of ``{"role", "content"}`` dicts (oldest first);
    *index* is a :class:`python.core.ai.retrieval.KnowledgeIndex` or ``None``.
    """
    capability = capability_card(flows) if flows else ""
    device_text = device_block(device)
    causes_text = errors.render(log_tail) if log_tail else ""
    matched = [cause.title for cause, _line in errors.match(log_tail)]

    docs_text = ""
    used_docs: list[str] = []
    if include_docs and index is not None:
        rendered = index.render(question, k=4)
        if rendered:
            docs_text = rendered
            used_docs = [
                line[1:].split(" · ")[0]
                for line in rendered.splitlines()
                if line.startswith("[") and " · " in line
            ]

    serial = (device or {}).get("serial") or None
    raw_log = log_tail or ""
    if serial:
        raw_log = raw_log.replace(str(serial), guard.mask_serial(serial))
    log_text = _tail(guard.redact(raw_log), log_lines) if raw_log else ""
    history_msgs = _history_messages(history, history_turns, serial=serial)

    dropped: list[str] = []
    messages = _compose(
        question, capability, device_text, causes_text, docs_text,
        log_text, history_msgs,
    )
    tokens = _total_tokens(messages)

    # Drop in the documented order: documents, console tail, oldest history.
    if tokens > max_input_tokens and docs_text:
        docs_text = ""
        dropped.append("documents")
        messages = _compose(
            question, capability, device_text, causes_text, "", log_text,
            history_msgs,
        )
        tokens = _total_tokens(messages)

    if tokens > max_input_tokens and log_text:
        log_text = _tail(log_text, 30)
        dropped.append("console tail (shortened)")
        messages = _compose(
            question, capability, device_text, causes_text, "", log_text,
            history_msgs,
        )
        tokens = _total_tokens(messages)

    while tokens > max_input_tokens and len(history_msgs) > 2:
        history_msgs = history_msgs[2:]
        dropped.append("oldest history")
        messages = _compose(
            question, capability, device_text, causes_text, "", log_text,
            history_msgs,
        )
        tokens = _total_tokens(messages)

    if tokens > max_input_tokens and log_text:
        log_text = ""
        dropped.append("console tail")
        messages = _compose(
            question, capability, device_text, causes_text, "", "", history_msgs,
        )
        tokens = _total_tokens(messages)

    return AdvisorContext(
        messages=messages,
        used_docs=used_docs,
        matched_causes=matched,
        dropped=dropped,
        input_tokens=tokens,
    )
