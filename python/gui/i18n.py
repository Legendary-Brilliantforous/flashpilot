"""Lightweight runtime UI translation for FlashPilot.

We intentionally avoid Qt's binary ``.qm`` toolchain (pylupdate/lrelease are
not shipped everywhere). Instead each language is a plain JSON dictionary
``i18n/json/<lang>.json`` of ``{"strings": {"source": "translation"}}`` and
Qt widgets are marked with ``self.tr(...)``/``tr(...)`` as usual. A
:class:`JsonTranslator` makes those calls resolve at runtime.

Missing keys fall back to the English source text, so partial translations
are always safe.
"""
import json
from pathlib import Path

from PyQt6.QtCore import QTranslator


class JsonTranslator(QTranslator):
    """A QTranslator backed by a JSON dictionary."""

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self._strings = {}
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self._strings = data.get("strings", data) or {}
        except (OSError, ValueError, TypeError):
            self._strings = {}

    def translate(self, context, source_text, disambiguation=None, n=-1):
        if not source_text:
            return source_text
        # Allow either top-level {"Hello": "..."} or {"strings": {...}}.
        try:
            hit = self._strings.get(source_text)
        except AttributeError:
            hit = None
        if isinstance(hit, str) and hit:
            return hit
        return source_text


def json_path_for(lang):
    root = Path(__file__).resolve().parent.parent / "i18n" / "json"
    # Installed layout fallback
    if not root.exists():
        root = Path("/usr/share/flashpilot/i18n/json")
    return root / f"{lang}.json"


_LANGS = ["en", "fr", "es", "de", "zh", "ru", "pt", "ja", "ar", "hi", "tr"]
for code in _LANGS:
    p = Path("i18n/json") / f"{code}.json"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"strings": {}}\n', encoding="utf-8")


def install(app, lang):
    """Install a JSON-backed translator for ``lang`` if one is available."""
    if not lang or lang == "en":
        return None
    path = json_path_for(lang)
    if not path.exists():
        return None
    tr = JsonTranslator(str(path))
    app.installTranslator(tr)
    return tr
