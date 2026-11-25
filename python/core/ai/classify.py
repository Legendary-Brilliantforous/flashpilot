"""Failure classifier for the AI advisor.

Turns a console tail (and an optional question) into a ranked list of
candidate FlashPilot flows the user might want to run. The classifier is
deliberately read-only: it never executes anything, it only names flows that
already exist in the registry and explains why each one is relevant.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import match as match_causes


@dataclass
class Suggestion:
    key: str
    label: str
    job: str
    mode: str
    reason: str
    confidence: float = 0.5
    section: str = ""


# Curated: known-cause title -> candidate flow keys (subset; filtered against
# the live registry so stale keys never surface).
_CAUSE_TO_FLOWS: dict[str, list[str]] = {
    "ADB is not authorised on the device": [
        "adb_info", "detect",
    ],
    "The target device is no longer on the bus": [
        "detect", "adb_info",
    ],
    "Another process (or the kernel driver) holds the USB interface": [
        "detect", "adb_info",
    ],
    "The device was unplugged or reset mid-operation": [
        "detect", "adb_info",
    ],
    "Read-back verification did not match": [
        "odin_preflight", "mtk-scatter",
    ],
    "A stage timed out": [
        "mtk-detect", "spd-detect", "qcom-detect", "odin_preflight",
    ],
    "The device is in the wrong bootloader mode": [
        "odin_preflight", "mtk-detect", "spd-detect", "qcom-detect",
    ],
    "The bootloader handshake was rejected": [
        "mtk-detect", "spd-detect", "qcom-detect", "odin_preflight",
    ],
    "The firmware/scatter package does not match the device": [
        "mtk-scatter", "odin_pit_tools",
    ],
    "The bootloader is protected (SLA / secure boot)": [
        "mtk-detect",
    ],
    "The USB link produced corrupt data": [
        "detect",
    ],
    "The device or firmware does not implement this command": [
        "detect",
    ],
}

# Keyword fallback: if a cause is not curated, look for these tokens in the
# flow label/job and suggest anything that mentions them.
_KEYWORDS = ("frp", "flash", "backup", "info", "detect", "unlock")

_MODE_TO_SECTION = {
    "mtk": "mtk",
    "mtk brom": "mtk",
    "download": "samsung",
    "odin": "samsung",
    "adb": "adb",
    "fastboot": "fastboot",
    "edl": "qc",
    "qcom": "qc",
    "spd": "spd",
    "bsl": "spd",
}


def _section_for(mode: str) -> str:
    lowered = (mode or "").lower()
    for token, section in _MODE_TO_SECTION.items():
        if token in lowered:
            return section
    return "general"


def classify(log_tail: str, flows, question: str = "", limit: int = 5) -> list[Suggestion]:
    """Return up to *limit* ranked suggestions for *log_tail*.

    *flows* is the live flow registry (list of dicts with key/label/job/mode).
    """
    if not flows:
        return []
    index = {str(f.get("key")): f for f in flows if isinstance(f, dict)}
    seen: dict[str, Suggestion] = {}

    # 1. Curated cause -> flow mapping (highest confidence).
    for cause, _line in match_causes(log_tail):
        for key in _CAUSE_TO_FLOWS.get(cause.title, []):
            flow = index.get(key)
            if flow is None:
                continue
            if key in seen:
                continue
            seen[key] = Suggestion(
                key=key,
                label=str(flow.get("label") or key),
                job=str(flow.get("job") or ""),
                mode=str(flow.get("mode") or ""),
                reason=f"{cause.title} - {cause.fix}",
                confidence=0.8,
                section=_section_for(str(flow.get("mode") or "")),
            )

    # 2. Keyword fallback from the question/log into flow labels.
    haystack = (question + "\n" + (log_tail or "")).lower()
    for token in _KEYWORDS:
        if token not in haystack:
            continue
        for flow in flows:
            if not isinstance(flow, dict):
                continue
            key = str(flow.get("key") or "")
            if not key or key in seen:
                continue
            label = str(flow.get("label") or "").lower()
            job = str(flow.get("job") or "").lower()
            if token in label or token in job:
                seen[key] = Suggestion(
                    key=key,
                    label=str(flow.get("label") or key),
                    job=str(flow.get("job") or ""),
                    mode=str(flow.get("mode") or ""),
                    reason=f"Mentioned '{token}' in the question or console.",
                    confidence=0.4,
                    section=_section_for(str(flow.get("mode") or "")),
                )
                if len(seen) >= limit:
                    break
        if len(seen) >= limit:
            break

    ranked = sorted(seen.values(), key=lambda s: -s.confidence)
    return ranked[:limit]
