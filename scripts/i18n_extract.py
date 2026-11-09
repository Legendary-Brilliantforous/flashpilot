#!/usr/bin/env python3
"""Keep the UI translation catalogs in sync with the source code.

The GUI marks user-visible text with ``self.tr("...")`` / ``tr("...")``. This
script scans the Python sources for those literals and merges them into
``i18n/json/en.json`` (English is the canonical key catalog). Every other
catalog must contain the same keys; missing entries are added empty so
translators can see exactly what is left to do.

Usage
-----
::

    .venv/bin/python scripts/i18n_extract.py            # merge + coverage report
    .venv/bin/python scripts/i18n_extract.py --check    # CI: fail if stale
    .venv/bin/python scripts/i18n_extract.py --prune    # drop keys no longer used
    .venv/bin/python scripts/i18n_extract.py --seed     # machine-fill empties

Translation policy
------------------
* The key **is** the English source phrase, so reviewers can see what changed.
* Whole phrases only — never single words, and never the values used for
  routing (job/mode identifiers stay untouched).
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
ENGLISH = "en"


def _load_runtime():
    """Import ``python/gui/i18n.py`` without importing the whole GUI package."""
    path = ROOT / "python" / "gui" / "i18n.py"
    spec = importlib.util.spec_from_file_location("_flashpilot_i18n", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def tr_literals(source: Path):
    """Yield ``(key, lineno)`` for every literal ``tr()`` call in ``source``.

    Non-literal arguments (f-strings, variables) are returned separately by
    :func:`scan_sources` because they can never be translated by the catalog.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_tr = (isinstance(func, ast.Name) and func.id == "tr") or (
            isinstance(func, ast.Attribute) and func.attr == "tr"
        )
        if not is_tr or not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            if arg.value:
                yield arg.value, node.lineno


def scan_sources(root: Path = SOURCE_DIR):
    """Return ``(keys, warnings)`` for the Python sources under ``root``."""
    keys: set[str] = set()
    warnings: list[str] = []
    for source in sorted(root.rglob("*.py")):
        try:
            literals = list(tr_literals(source))
        except (OSError, SyntaxError) as exc:  # pragma: no cover - defensive
            warnings.append(f"{_display(source)}: cannot parse ({exc})")
            continue
        keys.update(key for key, _ in literals)

        # Flag tr() calls whose argument is not a static string.
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_tr = (isinstance(func, ast.Name) and func.id == "tr") or (
                isinstance(func, ast.Attribute) and func.attr == "tr"
            )
            if not is_tr or not node.args:
                continue
            arg = node.args[0]
            if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                warnings.append(
                    f"{_display(source)}:{node.lineno}: "
                    "dynamic tr() argument cannot be extracted"
                )
    return keys, warnings


def load_catalog(path: Path):
    """Return ``(data, strings)`` with defensive defaults."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    strings = data.get("strings")
    if not isinstance(strings, dict):
        strings = {}
    return data, {str(k): v for k, v in strings.items()}


def save_catalog(path: Path, data: dict, strings: dict):
    """Write a stable, human-reviewable catalog (sorted keys, UTF-8)."""
    payload = {"strings": {key: strings.get(key, "") for key in sorted(strings)}}
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


def merge(keys, catalog_dir: Path = CATALOG_DIR, prune: bool = False):
    """Merge ``keys`` into every catalog. Returns ``(changed, report)``."""
    wanted = set(keys)
    changed = []
    report = []

    paths = catalog_paths(catalog_dir)
    if not paths:
        paths = [catalog_dir / f"{ENGLISH}.json"]

    for path in paths:
        code = path.stem
        data, strings = load_catalog(path)
        before = dict(strings)

        if prune:
            strings = {k: v for k, v in strings.items() if k in wanted}

        for key in wanted:
            if code == ENGLISH:
                # English is the identity catalog: the key is its own value.
                if not strings.get(key):
                    strings[key] = key
            else:
                strings.setdefault(key, "")
                if strings[key] is None:
                    strings[key] = ""

        if strings != before:
            save_catalog(path, data, strings)
            changed.append(_display(path))
        report.append(coverage(code, strings))

    return changed, report


def coverage(code, strings):
    total = len(strings)
    done = sum(1 for value in strings.values() if str(value).strip())
    missing = sorted(key for key, value in strings.items() if not str(value).strip())
    return {"code": code, "total": total, "translated": done, "missing": missing}


def print_report(report):
    if not report:
        return
    width = max(len(row["code"]) for row in report)
    print(f"{'lang'.ljust(width)}  keys  translated  missing")
    for row in report:
        print(
            f"{row['code'].ljust(width)}  {row['total']:4}  "
            f"{row['translated']:10}  {len(row['missing']):7}"
        )
    for row in report:
        if row["missing"]:
            preview = ", ".join(row["missing"][:8])
            if len(row["missing"]) > 8:
                preview += ", ..."
            print(f"  {row['code']}: {preview}")


def check(keys, catalog_dir: Path = CATALOG_DIR):
    """Return a list of problems; empty means the catalogs are up to date."""
    wanted = set(keys)
    problems = []
    en_data, en_strings = load_catalog(catalog_dir / f"{ENGLISH}.json")
    del en_data

    missing = sorted(wanted - set(en_strings))
    stale = sorted(set(en_strings) - wanted)
    if missing:
        problems.append(f"en.json is missing {len(missing)} key(s): {missing[:8]}")
    if stale:
        problems.append(
            f"en.json has {len(stale)} stale key(s) (use --prune): {stale[:8]}"
        )
    empty_en = sorted(k for k, v in en_strings.items() if not str(v).strip())
    if empty_en:
        problems.append(f"en.json has empty value(s): {empty_en[:8]}")

    for path in catalog_paths(catalog_dir):
        code = path.stem
        if code == ENGLISH:
            continue
        _, strings = load_catalog(path)
        absent = sorted(wanted - set(strings))
        extra = sorted(set(strings) - wanted)
        if absent:
            problems.append(f"{code}.json is missing {len(absent)} key(s)")
        if extra:
            problems.append(f"{code}.json has {len(extra)} stale key(s)")
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
        data, strings = load_catalog(path)
        missing = sorted(key for key, value in strings.items() if not str(value).strip())
        if not missing:
            continue
        translator = GoogleTranslator(source="en", target=code)
        marked = set(data.get("meta", {}).get("machine_translated", []))
        for key in missing:
            try:
                strings[key] = translator.translate(key) or ""
            except Exception as exc:  # network/rate limit
                print(f"  {code}: failed on {key!r}: {exc}")
                continue
            marked.add(key)
        data["meta"] = dict(data.get("meta", {}))
        data["meta"]["machine_translated"] = sorted(marked)
        save_catalog(path, data, strings)
        seeded.append(f"{code}: {len(missing)}")

        # Verify placeholder parity and warn (never silently ship a broken one).
        for key in missing:
            if runtime.placeholders(key) != runtime.placeholders(strings.get(key, "")):
                print(
                    f"  {code}: placeholder mismatch for {key!r} -> "
                    f"{strings.get(key)!r} (needs review)"
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
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(f"found {len(keys)} translatable literal(s)")

    if args.check:
        problems = check(keys)
        if problems:
            for problem in problems:
                print(f"error: {problem}", file=sys.stderr)
            return 1
        print("i18n catalogs are up to date")
        return 0

    if args.seed:
        seeded = seed(languages=args.lang or None)
        print("seeded: " + (", ".join(seeded) if seeded else "nothing to do"))

    changed, report = merge(keys, prune=args.prune)
    print_report(report)
    if changed:
        print("updated: " + ", ".join(changed))
    else:
        print("catalogs already up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
