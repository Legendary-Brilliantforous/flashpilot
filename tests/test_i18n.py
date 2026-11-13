"""Contract tests for the UI translation pipeline.

These guard the foundation that makes the language selector work at all:

* catalogs are valid, stable JSON;
* every ``tr()`` literal in the source is present in the English catalog;
* placeholders survive translation;
* the manifest, the catalog files and the settings dropdown agree;
* the runtime resolves catalogs in both source-checkout and installed layouts;
* importing the module never writes files (it used to create catalogs at
  import time, which fails on read-only installs and dirties the repo);
* Arabic gets a right-to-left layout direction.

The tests deliberately do not assert that every language is *fully* translated:
new strings are added empty and filled by contributors, which is a supported
state. ``--check`` reports the gap for CI visibility instead.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "i18n" / "json"
MANIFEST_PATH = ROOT / "i18n" / "manifest.json"


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


extract = _load("_i18n_extract_for_tests", "scripts/i18n_extract.py")

from python.gui import i18n  # noqa: E402  (after the extractor is loadable)


def _catalog_files():
    return sorted(CATALOG_DIR.glob("*.json"))


def _catalog_ids():
    return [path.stem for path in _catalog_files()]


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest():
    return _read(MANIFEST_PATH)


# --------------------------------------------------------------------------
# Catalog shape
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", _catalog_files(), ids=_catalog_ids())
def test_catalog_is_valid_json_with_string_map(path):
    data = _read(path)

    def no_duplicates(pairs):
        seen = {}
        for key, value in pairs:
            assert key not in seen, f"{path.name}: duplicate key {key!r}"
            seen[key] = value
        return seen

    json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)

    assert isinstance(data, dict), f"{path.name} must be an object"
    for section in ("strings", "keys"):
        rows = data.get(section)
        assert isinstance(rows, dict), f"{path.name} needs a '{section}' object"
        for key, value in rows.items():
            assert isinstance(key, str) and key, f"{path.name}: bad key {key!r}"
            assert isinstance(value, str), f"{path.name}: {key!r} is not a string"


def test_english_catalog_is_the_identity_map():
    data = _read(CATALOG_DIR / "en.json")
    wrong = {
        key: value for key, value in data["strings"].items() if value != key
    }
    assert not wrong, f"English string keys must map to themselves: {wrong}"
    # Data-driven ids map to the English display label the GUI passes as the
    # fallback, so a missing translation shows the right text.
    for key, value in data["keys"].items():
        assert value, f"en.json key {key!r} has no English label"


# --------------------------------------------------------------------------
# Source coverage / extractor
# --------------------------------------------------------------------------


def test_every_tr_literal_is_in_the_english_catalog():
    keys, warnings = extract.scan_sources()
    assert not [w for w in warnings if "cannot parse" in w], warnings
    strings = _read(CATALOG_DIR / "en.json")["strings"]
    missing = sorted(set(keys) - set(strings))
    assert not missing, f"run scripts/i18n_extract.py; missing: {missing}"


def test_english_catalog_has_no_stale_keys():
    keys, _ = extract.scan_sources()
    strings = _read(CATALOG_DIR / "en.json")["strings"]
    stale = sorted(set(strings) - set(keys))
    assert not stale, f"keys no longer used by source (--prune): {stale}"


@pytest.mark.parametrize("path", _catalog_files(), ids=_catalog_ids())
def test_catalog_key_sets_match_english(path):
    english = _read(CATALOG_DIR / "en.json")
    catalog = _read(path)
    for section in ("strings", "keys"):
        expected = set(english[section])
        actual = set(catalog[section])
        assert actual == expected, (
            f"{path.name} {section} drift from en.json; "
            f"missing={sorted(expected - actual)} "
            f"extra={sorted(actual - expected)}"
        )


def test_flow_job_mode_keys_match_the_display_sources():
    entries = extract.scan_key_entries()
    english = _read(CATALOG_DIR / "en.json")["keys"]
    assert set(entries) == set(english), (
        "run scripts/i18n_extract.py; "
        f"missing={sorted(set(entries) - set(english))[:8]} "
        f"stale={sorted(set(english) - set(entries))[:8]}"
    )
    drifted = {
        key: (value, english.get(key))
        for key, value in entries.items()
        if english.get(key) != value
    }
    assert not drifted, f"English labels drifted: {drifted}"


def test_key_entries_include_flows_jobs_and_modes():
    entries = extract.scan_key_entries()
    assert any(key.startswith("flow.") for key in entries)
    assert any(key.startswith("job.") for key in entries)
    assert any(key.startswith("mode.") for key in entries)
    assert len([key for key in entries if key.startswith("flow.")]) >= 100


def test_extractor_check_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "i18n_extract.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr + result.stdout


def test_extractor_merges_new_keys_without_losing_translations(tmp_path):
    (tmp_path / "en.json").write_text(
        json.dumps({"strings": {"Old": "Old"}}), encoding="utf-8"
    )
    (tmp_path / "fr.json").write_text(
        json.dumps({"strings": {"Old": "Ancien"}}), encoding="utf-8"
    )

    changed, report = extract.merge({"Old", "New"}, catalog_dir=tmp_path)

    french = _read(tmp_path / "fr.json")["strings"]
    english = _read(tmp_path / "en.json")["strings"]
    assert french["Old"] == "Ancien", "existing translations must be preserved"
    assert french["New"] == "", "new keys are added empty for translators"
    assert english["New"] == "New", "English is the identity catalog"
    assert changed and {row["code"] for row in report} == {"en", "fr"}


def test_extractor_merges_key_entries_without_losing_translations(tmp_path):
    (tmp_path / "en.json").write_text(
        json.dumps({"strings": {}, "keys": {"flow.a": "A label"}}), encoding="utf-8"
    )
    (tmp_path / "fr.json").write_text(
        json.dumps({"strings": {}, "keys": {"flow.a": "Libellé A"}}),
        encoding="utf-8",
    )

    extract.merge(
        set(),
        {"flow.a": "A label", "job.b": "B Job"},
        catalog_dir=tmp_path,
    )

    english = _read(tmp_path / "en.json")["keys"]
    french = _read(tmp_path / "fr.json")["keys"]
    assert english["flow.a"] == "A label"
    assert english["job.b"] == "B Job"
    assert french["flow.a"] == "Libellé A"
    assert french["job.b"] == ""


def test_extractor_prune_removes_only_unused_keys(tmp_path):
    (tmp_path / "en.json").write_text(
        json.dumps({"strings": {"Keep": "Keep", "Drop": "Drop"}}), encoding="utf-8"
    )
    (tmp_path / "fr.json").write_text(
        json.dumps({"strings": {"Keep": "Garder", "Drop": "Jeter"}}), encoding="utf-8"
    )

    extract.merge({"Keep"}, catalog_dir=tmp_path, prune=True)

    assert set(_read(tmp_path / "fr.json")["strings"]) == {"Keep"}
    assert _read(tmp_path / "fr.json")["strings"]["Keep"] == "Garder"


def test_extractor_flags_dynamic_tr_arguments(tmp_path):
    source = tmp_path / "sample.py"
    source.write_text(
        "tr('Static')\n"
        "tr(f'Dynamic {value}')\n"
        "self.tr('Method')\n"
        "QCoreApplication.translate('ctx', 'From translate')\n",
        encoding="utf-8",
    )
    keys, warnings = extract.scan_sources(tmp_path)
    assert keys == {"Static", "Method", "From translate"}
    assert any("dynamic tr()" in warning for warning in warnings)


# --------------------------------------------------------------------------
# Placeholders
# --------------------------------------------------------------------------


def test_placeholders_are_recognised():
    assert i18n.placeholders("{n} devices, {model} ready") == {"{n}", "{model}"}
    assert i18n.placeholders("Deleted %n files (%1)") == {"%n", "%1"}
    assert i18n.placeholders("No placeholders here") == set()


def test_stable_keys_are_readable_slugs():
    assert i18n.stable_key("job", "Flash Firmware") == "job.flash_firmware"
    assert i18n.stable_key("job", "QCN / Modem") == "job.qcn_modem"
    assert i18n.stable_key("mode", "Download mode") == "mode.download_mode"
    assert i18n.stable_key("job", "") == "job"


def test_tr_key_falls_back_to_english(monkeypatch):
    # No translator installed: the English label must be returned verbatim.
    assert (
        i18n.tr_key("flow.does_not_exist", "Pre-flight validation")
        == "Pre-flight validation"
    )
    assert i18n.tr_key("", "Fallback") == "Fallback"


def test_plain_tr_helper_falls_back_and_translates(tmp_path):
    # Used by module-level helpers that have no widget ``self``.
    assert i18n.tr("Scan USB bus") == "Scan USB bus"
    assert i18n.tr("") == ""

    path = tmp_path / "fr.json"
    path.write_text(
        json.dumps({"strings": {"Scan USB bus": "Analyser le bus USB"}}),
        encoding="utf-8",
    )
    from PyQt6.QtWidgets import QApplication

    translator = i18n.JsonTranslator(path)
    app = QApplication.instance() or QApplication([])
    app.installTranslator(translator)
    try:
        assert i18n.tr("Scan USB bus") == "Analyser le bus USB"
    finally:
        app.removeTranslator(translator)


def test_console_level_prefixes_stay_untranslated():
    """`_classify()` matches English `[error]`/`[step]` prefixes.

    A prefix inside a translated phrase would stop matching once a catalog is
    active, so console lines must be built as `"[step] " + tr("...")`.
    """
    import re

    pattern = re.compile(r"^\[[A-Za-z_]+\]\s")
    offenders = []
    for source in (ROOT / "python" / "gui").rglob("*.py"):
        for key, line in extract.translatable_literals(source):
            if pattern.match(key):
                offenders.append(f"{source.relative_to(ROOT)}:{line}: {key[:40]!r}")
    assert not offenders, offenders


def test_json_translator_reads_the_key_section(tmp_path):
    path = tmp_path / "fr.json"
    path.write_text(
        json.dumps(
            {
                "strings": {"Flash firmware": "Flasher le firmware"},
                "keys": {"flow.odin_flash_tar": "Flasher l'archive"},
            }
        ),
        encoding="utf-8",
    )
    translator = i18n.JsonTranslator(path)
    assert translator.translate("ctx", "flow.odin_flash_tar") == "Flasher l'archive"
    assert translator.translate("ctx", "Flash firmware") == "Flasher le firmware"


@pytest.mark.parametrize("path", _catalog_files(), ids=_catalog_ids())
def test_translations_preserve_placeholders(path):
    for section in ("strings", "keys"):
        rows = _read(path)[section]
        broken = []
        for key, value in rows.items():
            if not value.strip():
                continue  # untranslated entries are allowed
            if i18n.placeholders(key) != i18n.placeholders(value):
                broken.append((key, value))
        assert not broken, f"{path.name} {section} changed placeholders: {broken[:5]}"


# --------------------------------------------------------------------------
# Manifest / settings / files agreement
# --------------------------------------------------------------------------


def test_manifest_ui_languages_have_catalogs():
    manifest = _manifest()
    codes = [row["code"] for row in manifest["ui"]]
    assert codes[0] == manifest["default"]
    for code in codes:
        if code == "en":
            continue
        assert (CATALOG_DIR / f"{code}.json").is_file(), f"{code} has no catalog"


def test_manifest_ui_and_catalog_files_agree():
    manifest_codes = {row["code"] for row in _manifest()["ui"]}
    catalog_codes = {path.stem for path in _catalog_files()}
    assert manifest_codes == catalog_codes


def test_available_languages_matches_manifest(monkeypatch):
    monkeypatch.delenv(i18n.CATALOG_ENV, raising=False)
    expected = [
        {"code": row["code"], "name": row["name"]} for row in _manifest()["ui"]
    ]
    assert i18n.available_languages() == expected


def test_all_documented_languages_are_selectable():
    manifest = _manifest()
    ui = {row["code"] for row in manifest["ui"]}
    docs = {row["code"] for row in manifest["docs"]}
    assert ui == docs, "every documented language should also be a UI language"


# --------------------------------------------------------------------------
# Path resolution / installed layout
# --------------------------------------------------------------------------


def test_json_path_for_resolves_every_catalog(monkeypatch):
    monkeypatch.delenv(i18n.CATALOG_ENV, raising=False)
    for code in (row["code"] for row in _manifest()["ui"]):
        path = i18n.json_path_for(code)
        assert path.is_file(), f"{code} catalog not found at {path}"
        assert path.parent == CATALOG_DIR


def test_json_path_for_honours_the_env_override(tmp_path, monkeypatch):
    catalog = tmp_path / "fr.json"
    catalog.write_text('{"strings": {}}', encoding="utf-8")
    monkeypatch.setenv(i18n.CATALOG_ENV, str(tmp_path))
    assert i18n.json_path_for("fr") == catalog


def test_json_path_for_normalises_region_tags(monkeypatch):
    monkeypatch.delenv(i18n.CATALOG_ENV, raising=False)
    assert i18n.json_path_for("pt-BR") == i18n.json_path_for("pt")
    assert i18n.json_path_for("zh_CN") == i18n.json_path_for("zh")


def test_installed_layout_is_derived_from_the_module_location():
    # <root>/python/gui/i18n.py -> <root>/i18n/json, and for an installed
    # /usr/share/flashpilot/python/gui/i18n.py -> /usr/share/flashpilot/i18n/json.
    expected = Path(i18n.__file__).resolve().parents[2] / "i18n" / "json"
    assert expected in i18n._catalog_dirs()


def test_importing_the_module_does_not_write_files(tmp_path):
    """The old module created catalogs at import time (CWD-relative)."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env.pop(i18n.CATALOG_ENV, None)
    result = subprocess.run(
        [sys.executable, "-c", "import python.gui.i18n"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == [], "import must not create files"


# --------------------------------------------------------------------------
# Runtime translator
# --------------------------------------------------------------------------


def test_json_translator_translates_and_falls_back(tmp_path):
    path = tmp_path / "fr.json"
    path.write_text(
        json.dumps({"strings": {"Flash firmware": "Flasher le firmware", "Blank": ""}}),
        encoding="utf-8",
    )
    translator = i18n.JsonTranslator(path)
    assert translator.translate("Context", "Flash firmware") == "Flasher le firmware"
    assert translator.translate("Context", "Unknown") == "Unknown"
    assert translator.translate("Context", "Blank") == "Blank"
    assert translator.translate("Context", "") == ""


@pytest.mark.parametrize(
    "lang,expected",
    [("ar", True), ("ar-EG", True), ("AR", True), ("he", True),
     ("en", False), ("zh", False), ("pt-BR", False)],
)
def test_rtl_languages(lang, expected):
    assert i18n.is_rtl(lang) is expected


def test_rtl_layout_direction():
    from PyQt6.QtCore import Qt

    assert i18n.layout_direction("ar") == Qt.LayoutDirection.RightToLeft
    assert i18n.layout_direction("en") == Qt.LayoutDirection.LeftToRight


def test_install_is_a_noop_for_english(monkeypatch):
    from PyQt6.QtWidgets import QApplication

    monkeypatch.delenv(i18n.CATALOG_ENV, raising=False)
    app = QApplication.instance() or QApplication([])
    assert i18n.install(app, "en") is None
    assert app.layoutDirection() == i18n.layout_direction("en")


def test_install_keeps_a_reference_and_applies_rtl(monkeypatch):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    monkeypatch.delenv(i18n.CATALOG_ENV, raising=False)
    app = QApplication.instance() or QApplication([])
    i18n.reset_for_tests()

    translator = i18n.install(app, "ar")

    try:
        assert translator is not None
        assert translator in i18n._INSTALLED, "QTranslator must stay alive"
        assert app.layoutDirection() == Qt.LayoutDirection.RightToLeft
        # Exercise the real lookup path used by every self.tr() call, not just
        # the translator object directly.
        from PyQt6.QtCore import QCoreApplication

        assert (
            QCoreApplication.translate("FlashPilot", "Interface language")
            != "Interface language"
        )
    finally:
        # Never leak an Arabic translator into the English-only test suite.
        if translator is not None:
            app.removeTranslator(translator)
        app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        i18n.reset_for_tests()


def test_install_strict_mode_reports_a_missing_catalog(tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv(i18n.CATALOG_ENV, str(tmp_path))
    monkeypatch.setenv(i18n.STRICT_ENV, "1")
    with pytest.raises(FileNotFoundError):
        i18n.install(app, "fr")
