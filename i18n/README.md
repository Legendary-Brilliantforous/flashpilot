# FlashPilot UI translations

Runtime translations are **JSON dictionaries**, not Qt ``.qm`` files, so no
external toolchain (pylupdate/lrelease) is required.

Files:
- `i18n/json/<lang>.json` with shape:
  ```json
  {"strings": {"English source": "translation"}}
  ```
- Empty/missing keys fall back to the English source text.

Language codes: `en` (default), `fr`, `es`, `de`, `zh`, `ru`, `pt`,
`ja`, `ar`, `hi`, `tr`.

Workflow
1. Wrap user-facing literals in `self.tr(...)` / `tr(...)` in the GUI code.
2. Add the matching source → translation entry in the target JSON file.
3. Switch language in Settings (requires restart).
4. Test with `QT_QPA_PLATFORM=offscreen` builds and `ui_language=<code>`.

Contributions to these JSON dictionaries are very welcome.
