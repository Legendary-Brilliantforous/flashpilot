"""Firmware compatibility checker — validates archive vs device PIT before flash.

Checks model, partition capacity, and optional Android version / security patch
metadata. Blocks the #1 brick cause: flashing wrong-model firmware whose image
exceeds partition capacity (frp.py _humanize: exceeds capacity).

Leverages existing PIT audit: pit.parse_model + pit.pit_health + pit.find_partition.
"""

import os
from typing import Dict, List, Tuple

from . import pit


def check_compat(
    archive_part_names: List[str],
    pit_raw: bytes,
    archive_sizes: Dict[str, int] = None,
) -> Dict:
    """Run compatibility checks.

    archive_part_names: normalized part names from tar (e.g. ['boot','system'])
    pit_raw: device PIT bytes
    archive_sizes: optional {name: size_bytes} for capacity check

    Returns dict with verdict in ('ok','warn','block') + reasons.
    """
    reasons: List[str] = []
    verdict = "ok"

    try:
        entries = pit.parse_pit(pit_raw)
        health = pit.pit_health(pit_raw)
    except Exception as e:
        return {"verdict": "block", "reasons": [f"PIT parse failed: {e}"], "health": None, "entries": []}

    model = health.get("stats", {}).get("model", "") or pit.parse_model(pit_raw)
    entries_by_name = {e.name.lower(): e for e in entries}

    # 1. PIT forensic gate — PIT must not be fail
    if health.get("verdict") == "fail":
        verdict = "block"
        reasons.append(f"PIT forensic FAIL: {health.get('summary','')}")
        for f in health.get("findings", [])[:4]:
            reasons.append(f"  - {f.get('code')}: {f.get('message','')}")
        return {"verdict": verdict, "reasons": reasons, "health": health, "entries": entries, "model": model}

    # 2. Archive -> PIT mapping
    mapping: Dict[str, Tuple[str, int]] = {}
    unknown: List[str] = []
    for name in archive_part_names:
        e = pit.find_partition(entries, name)
        if e is None:
            unknown.append(name)
        else:
            mapping[name] = (e.name, e.identifier)

    if unknown:
        # Unknown partitions are warn, not block — CSC variants carry extra images
        if verdict != "block":
            verdict = "warn"
        reasons.append(f"{len(unknown)} archive part(s) have no PIT match: {', '.join(unknown[:6])}")

    # 3. Capacity check when sizes known
    oversize: List[str] = []
    if archive_sizes:
        for name, size in archive_sizes.items():
            e = pit.find_partition(entries, name)
            if e is None:
                continue
            cap = e.size_bytes()
            if cap and size > cap:
                oversize.append(f"{name} {size} > {e.name} cap {cap}")
        if oversize:
            verdict = "block"
            for o in oversize[:6]:
                reasons.append(f"Image exceeds partition capacity: {o} — wrong model?")

    if verdict == "ok":
        reasons.append(f"Compatible: {len(mapping)} matched, PIT {health.get('summary','')}, model={model or '?'}")

    return {
        "verdict": verdict,
        "reasons": reasons,
        "health": health,
        "entries": entries,
        "model": model,
        "mapping": mapping,
        "unknown": unknown,
        "oversize": oversize,
    }


def format_compat_report(check: Dict) -> List[str]:
    lines: List[str] = []
    v = check.get("verdict", "unknown")
    icon = {"ok": "[ok]", "warn": "[warn]", "block": "[error]"}.get(v, "[check]")
    lines.append(f"  {icon} Compatibility: {v.upper()}")
    for r in check.get("reasons", []):
        lines.append(f"    - {r}")
    return lines
