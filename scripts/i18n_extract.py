#!/usr/bin/env python3
"""Keep the UI translation catalogs in sync with the source code.

The GUI marks user-visible text in two ways:

* ``self.tr("...")`` / ``tr("...")`` — the key is the English source phrase.
* ``QCoreApplication.translate("context", "...")`` — used where no widget
  ``self`` exists (module-level dialog tables).
* stable ids such as ``flow.odin_flash_tar`` — data-driven labels (flow
  captions, job and transport-mode names) rendered with ``i18n.tr_key()``.

This script scans the sources and merges the keys into every catalog:

* ``en.json`` is the identity catalog (key -> English text) and defines the
  required key set.
* every other catalog gets missing entries added **empty**, so translators
  see exactly what is left to do.

Usage
-----
::

    .venv/bin/python scripts/i18n_extract.py            # merge + coverage report
    .venv/bin/python scripts/i18n_extract.py --check    # CI: fail if stale
    .venv/bin/python scripts/i18n_extract.py --prune    # drop keys no longer used
    .venv/bin/python scripts/i18n_extract.py --seed     # machine-fill empties

Translation policy
------------------
* The key **is** the English source phrase for GUI strings, so reviewers can
  see what changed. Data-driven labels use stable ids instead.
* Whole phrases only — never single words, and never the values used for
  routing (job/mode identifiers stay untouched; only display text is keyed).
* Machine translation is a *build-time* convenience (``--seed``); its output is
  listed in ``meta.machine_translated`` and must be reviewed. The app itself is
  a plain offline dictionary lookup.
* Never translate brands, model numbers, or protocol terms (FRP, BROM, EDL,
  fastboot, DA, PIT, Knox, Odin, MTK, QCOM, SPD...).
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "i18n" / "json"
SOURCE_DIR = ROOT / "python"
CORE_SOURCE = ROOT / "python" / "core" / "core.py"
ENGLISH = "en"

TRANSLATE_FUNCS = {"tr", "translate"}


def _load_runtime():
    """Import ``python/gui/i18n.py`` without importing the whole GUI package."""
    path = ROOT / "python" / "gui" / "i18n.py"
    spec = importlib.util.spec_from_file_location("_flashpilot_i18n", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _is_tr_call(node):
    func = node.func
    return (isinstance(func, ast.Name) and func.id == "tr") or (
        isinstance(func, ast.Attribute) and func.attr == "tr"
    )


def _is_translate_call(node):
    # QCoreApplication.translate("ctx", "text", ...) — second arg is the key.
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "translate"
        and len(node.args) >= 2
    )


def _string_arg(node):
    arg = node.args[1] if _is_translate_call(node) else (node.args[0] if node.args else None)
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


def translatable_literals(source: Path):
    """Yield ``(key, lineno)`` for every literal ``tr()``/``translate()`` call."""
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (_is_tr_call(node) or _is_translate_call(node)):
            continue
        text = _string_arg(node)
        if text:
            yield text, node.lineno


def scan_sources(root: Path = SOURCE_DIR):
    """Return ``(keys, warnings)`` for the Python sources under ``root``."""
    keys: set[str] = set()
    warnings: list[str] = []
    for source in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        except (OSError, SyntaxError) as exc:  # pragma: no cover - defensive
            warnings.append(f"{_display(source)}: cannot parse ({exc})")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _is_tr_call(node):
                if not node.args:
                    continue
                text = _string_arg(node)
                if text:
                    keys.add(text)
                else:
                    warnings.append(
                        f"{_display(source)}:{node.lineno}: "
                        "dynamic tr() argument cannot be extracted"
                    )
            elif _is_translate_call(node):
                text = _string_arg(node)
                if text:
                    keys.add(text)
    return keys, warnings


def scan_key_entries(core_source: Path = CORE_SOURCE):
    """Stable-id entries for data-driven labels.

    Reads the Python registry (``_RustFlow`` captions, ``JOBS``, ``MODES``)
    rather than the Rust table because that is exactly what the GUI renders.
    """
    runtime = _load_runtime()
    tree = ast.parse(core_source.read_text(encoding="utf-8"), filename=str(core_source))
    flows, jobs, modes = {}, [], []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "_RustFlow" and len(node.args) >= 2:
                key = node.args[0]
                label = node.args[1]
                if (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and isinstance(label, ast.Constant)
                    and isinstance(label.value, str)
                ):
                    flows[key.value] = label.value
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if target.id == "MODES" and isinstance(node.value, ast.List):
                    modes = [
                        e.value
                        for e in node.value.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)
                    ]
                elif target.id == "JOBS" and isinstance(node.value, ast.Dict):
                    jobs = [
                        k.value
                        for k in node.value.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)
                    ]

    entries = {}
    for key, label in flows.items():
        entries[f"flow.{key}"] = label
    for job in jobs:
        entries[runtime.stable_key("job", job)] = job
    for mode in modes:
        entries[runtime.stable_key("mode", mode)] = mode
    return entries


def load_catalog(path: Path):
    """Return ``(data, strings, keys)`` with defensive defaults."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    strings = data.get("strings")
    if not isinstance(strings, dict):
        strings = {}
    keys = data.get("keys")
    if not isinstance(keys, dict):
        keys = {}
    return (
        data,
        {str(k): v for k, v in strings.items()},
        {str(k): v for k, v in keys.items()},
    )


def save_catalog(path: Path, data: dict, strings: dict, keys: dict):
    """Write a stable, human-reviewable catalog (sorted keys, UTF-8)."""
    payload = {
        "strings": {key: strings.get(key, "") for key in sorted(strings)},
        "keys": {key: keys.get(key, "") for key in sorted(keys)},
    }
    meta = data.get("meta")
    if isinstance(meta, dict) and meta:
        payload["meta"] = meta
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def catalog_paths(catalog_dir: Path = CATALOG_DIR):
    return sorted(catalog_dir.glob("*.json"))


def _display(path: Path):
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def merge(
    keys,
    key_entries=None,
    catalog_dir: Path = CATALOG_DIR,
    prune: bool = False,
):
    """Merge source keys into every catalog. Returns ``(changed, report)``."""
    wanted = set(keys)
    wanted_keys = dict(key_entries or {})
    changed = []
    report = []

    paths = catalog_paths(catalog_dir)
    if not paths:
        paths = [catalog_dir / f"{ENGLISH}.json"]

    for path in paths:
        code = path.stem
        data, strings, catalog_keys = load_catalog(path)
        before = (dict(strings), dict(catalog_keys))

        if prune:
            strings = {k: v for k, v in strings.items() if k in wanted}
            catalog_keys = {k: v for k, v in catalog_keys.items() if k in wanted_keys}

        for key in wanted:
            if code == ENGLISH:
                # English is the identity catalog: the key is its own value.
                if not strings.get(key):
                    strings[key] = key
            else:
                strings.setdefault(key, "")
                if strings[key] is None:
                    strings[key] = ""

        for key, english in wanted_keys.items():
            if code == ENGLISH:
                if not catalog_keys.get(key):
                    catalog_keys[key] = english
            else:
                catalog_keys.setdefault(key, "")
                if catalog_keys[key] is None:
                    catalog_keys[key] = ""

        if (strings, catalog_keys) != before:
            save_catalog(path, data, strings, catalog_keys)
            changed.append(_display(path))
        report.append(coverage(code, strings, catalog_keys))

    return changed, report


def coverage(code, strings, keys):
    def done(rows):
        return sum(1 for value in rows.values() if str(value).strip())

    return {
        "code": code,
        "total": len(strings),
        "translated": done(strings),
        "key_total": len(keys),
        "key_translated": done(keys),
        "missing": sorted(k for k, v in strings.items() if not str(v).strip()),
        "missing_keys": sorted(k for k, v in keys.items() if not str(v).strip()),
    }


def print_report(report):
    if not report:
        return
    width = max(len(row["code"]) for row in report)
    print(
        f"{'lang'.ljust(width)}  ui keys  ui done  flow keys  flow done"
    )
    for row in report:
        print(
            f"{row['code'].ljust(width)}  {row['total']:7}  {row['translated']:7}  "
            f"{row['key_total']:9}  {row['key_translated']:9}"
        )
    for row in report:
        for label, missing in (("ui", row["missing"]), ("flow", row["missing_keys"])):
            if missing:
                preview = ", ".join(missing[:6])
                if len(missing) > 6:
                    preview += ", ..."
                print(f"  {row['code']} [{label}]: {preview}")


def check(keys, key_entries=None, catalog_dir: Path = CATALOG_DIR):
    """Return a list of problems; empty means the catalogs are up to date."""
    wanted = set(keys)
    wanted_keys = dict(key_entries or {})
    problems = []
    en_data, en_strings, en_keys = load_catalog(catalog_dir / f"{ENGLISH}.json")
    del en_data

    missing = sorted(wanted - set(en_strings))
    stale = sorted(set(en_strings) - wanted)
    if missing:
        problems.append(f"en.json is missing {len(missing)} string key(s): {missing[:8]}")
    if stale:
        problems.append(
            f"en.json has {len(stale)} stale string key(s) (use --prune): {stale[:8]}"
        )
    empty_en = sorted(k for k, v in en_strings.items() if not str(v).strip())
    if empty_en:
        problems.append(f"en.json has empty string value(s): {empty_en[:8]}")

    missing_keys = sorted(set(wanted_keys) - set(en_keys))
    stale_keys = sorted(set(en_keys) - set(wanted_keys))
    if missing_keys:
        problems.append(
            f"en.json is missing {len(missing_keys)} flow/job/mode key(s): "
            f"{missing_keys[:8]}"
        )
    if stale_keys:
        problems.append(
            f"en.json has {len(stale_keys)} stale flow/job/mode key(s) "
            f"(use --prune): {stale_keys[:8]}"
        )
    wrong_identity = sorted(
        key for key, value in wanted_keys.items() if en_keys.get(key) != value
    )
    if wrong_identity:
        problems.append(
            f"en.json key value(s) drifted from source: {wrong_identity[:8]}"
        )

    for path in catalog_paths(catalog_dir):
        code = path.stem
        if code == ENGLISH:
            continue
        _, strings, catalog_keys = load_catalog(path)
        absent = sorted(wanted - set(strings))
        extra = sorted(set(strings) - wanted)
        if absent:
            problems.append(f"{code}.json is missing {len(absent)} string key(s)")
        if extra:
            problems.append(f"{code}.json has {len(extra)} stale string key(s)")
        absent_keys = sorted(set(wanted_keys) - set(catalog_keys))
        extra_keys = sorted(set(catalog_keys) - set(wanted_keys))
        if absent_keys:
            problems.append(f"{code}.json is missing {len(absent_keys)} flow/job/mode key(s)")
        if extra_keys:
            problems.append(f"{code}.json has {len(extra_keys)} stale flow/job/mode key(s)")
    return problems


def seed(catalog_dir: Path = CATALOG_DIR, languages=None):
    """Machine-translate empty entries (build-time only, needs network).

    Requires the optional ``deep-translator`` package. Results are marked in
    ``meta.machine_translated`` and intentionally leave the app runtime
    dependency-free.
    """
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        raise SystemExit(
            "--seed needs the optional 'deep-translator' package:\n"
            "  .venv/bin/pip install deep-translator"
        )

    runtime = _load_runtime()
    seeded = []
    for path in catalog_paths(catalog_dir):
        code = path.stem
        if code == ENGLISH or (languages and code not in languages):
            continue
        data, strings, keys = load_catalog(path)
        missing = sorted(
            list(k for k, v in strings.items() if not str(v).strip())
            + list(k for k, v in keys.items() if not str(v).strip())
        )
        if not missing:
            continue
        translator = GoogleTranslator(source="en", target=code)
        marked = set(data.get("meta", {}).get("machine_translated", []))
        for key in missing:
            try:
                translated = translator.translate(key) or ""
            except Exception as exc:  # network/rate limit
                print(f"  {code}: failed on {key!r}: {exc}")
                continue
            if key in strings:
                strings[key] = translated
            else:
                keys[key] = translated
            marked.add(key)
        data["meta"] = dict(data.get("meta", {}))
        data["meta"]["machine_translated"] = sorted(marked)
        save_catalog(path, data, strings, keys)
        seeded.append(f"{code}: {len(missing)}")

        # Verify placeholder parity and warn (never silently ship a broken one).
        for key in missing:
            value = strings.get(key, keys.get(key, ""))
            if runtime.placeholders(key) != runtime.placeholders(value):
                print(
                    f"  {code}: placeholder mismatch for {key!r} -> "
                    f"{value!r} (needs review)"
                )
    return seeded


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 when catalogs are out of date",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="drop catalog keys that no longer appear in source",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="machine-translate empty entries (needs network + deep-translator)",
    )
    parser.add_argument(
        "--lang",
        action="append",
        default=[],
        help="limit --seed to these language codes (repeatable)",
    )
    args = parser.parse_args(argv)

    keys, warnings = scan_sources()
    key_entries = scan_key_entries()
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(
        f"found {len(keys)} translatable literal(s) and "
        f"{len(key_entries)} flow/job/mode key(s)"
    )

    if args.check:
        problems = check(keys, key_entries)
        if problems:
            for problem in problems:
                print(f"error: {problem}", file=sys.stderr)
            return 1
        print("i18n catalogs are up to date")
        return 0

    if args.seed:
        seeded = seed(languages=args.lang or None)
        print("seeded: " + (", ".join(seeded) if seeded else "nothing to do"))

    changed, report = merge(keys, key_entries, prune=args.prune)
    print_report(report)
    if changed:
        print("updated: " + ", ".join(changed))
    else:
        print("catalogs already up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
