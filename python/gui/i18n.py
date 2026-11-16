"""Lightweight runtime UI translation for FlashPilot.

We intentionally avoid Qt's binary ``.qm`` toolchain (pylupdate/lrelease are
not shipped everywhere). Instead each language is a plain JSON dictionary
``i18n/json/<lang>.json`` of ``{"strings": {"source": "translation"}}`` and
Qt widgets are marked with ``self.tr(...)``/``tr(...)`` as usual. A
:class:`JsonTranslator` makes those calls resolve at runtime.

Missing keys fall back to the English source text, so partial translations
are always safe. Machine-translated entries are flagged in the catalog's
``meta.machine_translated`` list; the runtime ignores that metadata and does
a plain, offline dictionary lookup.

Catalog layout (both work with the same code):

* source checkout: ``<repo>/i18n/json/*.json``
* installed package: ``/usr/share/flashpilot/i18n/json/*.json``
* override: ``$FLASHPILOT_I18N_DIR`` (point at the directory holding the JSON
  files, e.g. for testing or a portable build)
"""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QTranslator

DEFAULT_LANGUAGE = "en"
CATALOG_ENV = "FLASHPILOT_I18N_DIR"
STRICT_ENV = "FLASHPILOT_I18N_STRICT"

# Languages written right-to-left. Keys are language subtags (before any
# region/script suffix), so ``ar-EG`` and ``ar`` both resolve to RTL.
RTL_LANGUAGES = frozenset({"ar", "fa", "he", "ur"})

_INSTALLED = []
_INSTALLED_LOCK = threading.Lock()

# Placeholders that must survive translation unchanged: Python/str.format
# (``{model}``, ``{0}``), printf-style Qt/Qt6 plurals (``%n``) and Qt's
# numbered arguments (``%1``..``%9``).
_PLACEHOLDER = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}|\{[0-9]+\}|%[nsd]|%[1-9]")


def placeholders(text):
    """The set of interpolation placeholders in ``text``."""
    return set(_PLACEHOLDER.findall(text or ""))


def tr(text):
    """Translate a plain source phrase where no widget ``tr()`` is available.

    Module-level helpers (for example the device-board applicability pass) have
    no QObject to call ``self.tr()`` on. Translation is looked up at call time,
    so an installed translator takes effect without rebuilding any constants,
    and a missing translator returns the English source unchanged.
    """
    if not text:
        return text
    try:
        from PyQt6.QtCore import QCoreApplication

        hit = QCoreApplication.translate("flashpilot", text)
    except Exception:
        return text
    return hit or text


def stable_key(prefix, text):
    """A stable catalog key for a data-driven string (job/mode names).

    ``stable_key("job", "Flash Firmware")`` -> ``"job.flash_firmware"``.
    Job and mode strings are already routing identifiers, so their slug is as
    stable as the English text they replace.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")
    return f"{prefix}.{slug}" if slug else prefix


def tr_key(key, fallback=""):
    """Translate a stable catalog key, falling back to English display text.

    Used for data that never passes through a widget's ``tr()`` — flow
    captions, job names and transport modes. The key is looked up in the
    catalog's ``keys`` section; when it is missing or empty, ``fallback``
    (the original English label) is returned unchanged.
    """
    if not key:
        return fallback
    try:
        from PyQt6.QtCore import QCoreApplication

        hit = QCoreApplication.translate("flashpilot", key)
    except Exception:
        return fallback or key
    if hit and hit != key:
        return hit
    return fallback or key


def language_code(lang):
    """Normalise a language tag to a bare lookup code (``pt-BR`` -> ``pt``)."""
    return str(lang or "").strip().replace("_", "-").split("-")[0].lower()


def is_rtl(lang):
    """True when ``lang`` is a right-to-left language."""
    return language_code(lang) in RTL_LANGUAGES


def layout_direction(lang):
    """The Qt layout direction that matches ``lang``."""
    return (
        Qt.LayoutDirection.RightToLeft
        if is_rtl(lang)
        else Qt.LayoutDirection.LeftToRight
    )


def _catalog_dirs():
    """Directories that may hold catalogs, most specific first."""
    here = Path(__file__).resolve()
    override = os.environ.get(CATALOG_ENV, "").strip()
    if override:
        # An explicit override is authoritative: portable builds and tests
        # should not silently fall back to a different catalog tree.
        return [Path(override).expanduser()]
    candidates = []
    # ``here`` is [<root> or /usr/share/flashpilot]/python/gui/i18n.py, so
    # parents[2] is the application root in *both* layouts.
    candidates.append(here.parents[2] / "i18n" / "json")
    candidates.append(Path("/usr/share/flashpilot/i18n/json"))

    out, seen = [], set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            out.append(candidate)
    return out


def catalog_dir():
    """The catalog directory in use (first one that exists)."""
    dirs = _catalog_dirs()
    for directory in dirs:
        if directory.is_dir():
            return directory
    return dirs[0]


def json_path_for(lang):
    """Resolve ``lang`` to its catalog file.

    Prefers a catalog that actually exists (so source checkouts and installed
    packages both resolve correctly); otherwise returns the preferred path so
    callers can report a meaningful location.
    """
    name = f"{language_code(lang) or DEFAULT_LANGUAGE}.json"
    dirs = _catalog_dirs()
    for directory in dirs:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return dirs[0] / name


def manifest_path():
    """Path to ``i18n/manifest.json`` next to the catalog directory."""
    return catalog_dir().parent / "manifest.json"


def _read_manifest():
    try:
        with open(manifest_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def available_languages():
    """UI languages as ``[{"code", "name"}]`` from the manifest.

    Falls back to the catalog files on disk when the manifest is missing or
    malformed, so a dropped-in ``xx.json`` still appears.
    """
    manifest = _read_manifest()
    rows = manifest.get("ui")
    if isinstance(rows, list):
        langs = [
            {"code": str(row["code"]), "name": str(row.get("name") or row["code"])}
            for row in rows
            if isinstance(row, dict) and row.get("code")
        ]
        if langs:
            return langs

    codes = {DEFAULT_LANGUAGE}
    try:
        codes.update(p.stem for p in catalog_dir().glob("*.json"))
    except OSError:
        pass
    return [{"code": c, "name": c} for c in sorted(codes)]


class JsonTranslator(QTranslator):
    """A QTranslator backed by a JSON dictionary.

    Catalogs have two sections: ``strings`` (keyed by the English source
    phrase, used by ``tr()``) and ``keys`` (stable ids such as
    ``flow.odin_flash_tar``, used by :func:`tr_key`). Both are merged into one
    lookup table; empty values are treated as untranslated.
    """

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self._strings = {}
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                merged = {}
                for section in ("strings", "keys"):
                    rows = data.get(section)
                    if isinstance(rows, dict):
                        merged.update(rows)
                self._strings = {
                    k: v
                    for k, v in merged.items()
                    if isinstance(k, str) and isinstance(v, str) and v
                }
        except (OSError, ValueError, TypeError):
            self._strings = {}

    def translate(self, context, source_text, disambiguation=None, n=-1):
        if not source_text:
            return source_text
        try:
            return self._strings.get(source_text, source_text)
        except AttributeError:
            return source_text

    def __len__(self):
        return len(self._strings)


def install(app, lang):
    """Install a JSON-backed translator for ``lang`` if one is available.

    Also applies the matching layout direction (Arabic -> RTL). The translator
    is kept in a module-level list because ``QApplication.installTranslator``
    does not take ownership: without a reference Python would garbage-collect
    it and every ``tr()`` call would silently fall back to English.
    """
    code = language_code(lang) or DEFAULT_LANGUAGE
    app.setLayoutDirection(layout_direction(code))
    if code == DEFAULT_LANGUAGE:
        return None

    path = json_path_for(code)
    if not path.is_file():
        # A missing catalog is not fatal: English remains readable. In
        # development, FLASHPILOT_I18N_STRICT=1 turns the silent fallback into
        # a loud error so packaging mistakes cannot ship unnoticed.
        if os.environ.get(STRICT_ENV) == "1":
            raise FileNotFoundError(
                f"no UI translation catalog for {code!r}: {path}"
            )
        return None

    translator = JsonTranslator(str(path))
    if not app.installTranslator(translator):
        return None
    with _INSTALLED_LOCK:
        _INSTALLED.append(translator)
    return translator


def reset_for_tests():
    """Drop retained translators (tests only)."""
    with _INSTALLED_LOCK:
        _INSTALLED.clear()
