# FlashPilot UI translations

Runtime translations are **JSON dictionaries**, not Qt `.qm` files, so no
external toolchain (pylupdate/lrelease) is required and the app works fully
offline.

## Layout

- `i18n/manifest.json` — the single source of truth for selectable languages.
  `ui` drives **Settings → Language & region**; `docs` lists documentation
  translations.
- `i18n/json/<lang>.json` with shape:
  ```json
  {
    "strings": {"English source": "translation"},
    "keys": {"flow.odin_flash_tar": "translated flow caption"},
    "meta": {"machine_translated": ["English source"]}
  }
  ```
- `strings` is keyed by the English source phrase (widget `tr()` calls).
- `keys` holds stable ids (`flow.*`, `job.*`, `mode.*`) for data-driven labels
  translated at render time with `i18n.tr_key()`.
- `en.json` is the identity catalog and defines the required key set.
- Empty/missing keys fall back to the English source text.

Current size: **612 `strings` + 138 `keys`** per language, all translated.
They cover the shared chrome, every operations page (Samsung/Odin, MediaTek,
Qualcomm, SPD/UNISOC, FUS, quick actions, battery/network, settings), the
device board, QR provisioning helpers, toasts and the app's own console
status lines.

Console lines are built as `"[step] " + tr("...")`: `[error]`, `[refused]`,
`[device]` and friends are matched by `_classify()` and must stay outside the
translated phrase. Raw bridge/device output is never translated, and neither
are brands, model numbers or protocol terms.

`i18n.tr()` is the translation helper for module-level code that has no widget
to call `self.tr()` on. It does the same offline lookup at call time.

`tests/test_i18n_pseudo.py` builds the real window under a `⟦pseudo⟧` catalog
to prove those surfaces actually route through the translator.

Safety-review hold: long confirmation-dialog bodies and EXPERIMENTAL legal
warnings stay English until a native-speaker review; see
`docs/TRANSLATION.md`.

Language codes: `en` (default), `fr`, `es`, `de`, `zh`, `ru`, `pt`,
`ja`, `ar`, `hi`, `tr`.

## Workflow

1. Wrap user-facing literals in `self.tr(...)` / `tr(...)` in the GUI code.
2. Run the extractor — it merges new keys into every catalog and reports the
   per-language gap:
   ```bash
   .venv/bin/python scripts/i18n_extract.py
   ```
3. Fill in `i18n/json/<lang>.json`. Machine translation can seed empty entries
   at build time (marked for review, never used at runtime):
   ```bash
   .venv/bin/python scripts/i18n_extract.py --seed --lang fr
   ```
4. Verify:
   ```bash
   .venv/bin/python scripts/i18n_extract.py --check
   .venv/bin/pytest tests/test_i18n.py tests/test_i18n_pseudo.py -q
   ```
5. Switch language in Settings (requires restart). Arabic switches the layout
   direction to right-to-left automatically.

Rules: translate whole phrases, keep placeholders (`{model}`, `%n`, `%1`)
intact, and leave brands/model numbers/protocol terms (FRP, BROM, EDL,
fastboot, DA, PIT, Knox, Odin, MTK, QCOM, SPD) in English.

Contributions to these JSON dictionaries are very welcome.
