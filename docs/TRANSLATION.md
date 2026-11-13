# Translation guide

FlashPilot uses English as the canonical language for both the documentation
and the application UI. Other languages live in `docs/<lang>/` (documentation)
and `i18n/json/<lang>.json` (in-app UI).

## Coverage

| Language | Code | UI | Docs |
|---|---|---|---|
| English | `en` | yes (default) | yes |
| Français | `fr` | yes | yes |
| Español | `es` | yes | yes |
| Deutsch | `de` | yes | yes |
| 简体中文 | `zh` | yes | yes |
| Русский | `ru` | yes | yes |
| Português | `pt` | yes | yes |
| 日本語 | `ja` | yes | yes |
| العربية | `ar` | yes (RTL) | yes |
| हिन्दी | `hi` | yes | yes |
| Türkçe | `tr` | yes | yes |

The single source of truth for selectable languages is
`i18n/manifest.json`: adding a language there plus a catalog file makes it
appear in **Settings → Language & region**, with no code change.

## UI translations (`i18n/json/`)

The app does **plain, offline dictionary lookups** at runtime. There is no
network call, no API key, and no service that sees device data. Machine
translation is only a build-time helper for seeding new entries.

### Catalog shape

```json
{
  "strings": {
    "Flash firmware": "Flasher le firmware"
  },
  "keys": {
    "flow.odin_flash_tar": "Flasher l'archive firmware",
    "job.remove_frp": "Supprimer FRP",
    "mode.edl": "EDL"
  },
  "meta": {
    "machine_translated": ["Flash firmware"]
  }
}
```

* `strings` is keyed by the **English source phrase** — whole phrases, never
  single words. That keeps catalogs reviewable and Qt-idiomatic.
* `keys` holds **stable ids** for data-driven labels (flow captions, job and
  transport-mode names). The GUI translates them at render time with
  `i18n.tr_key()`; English text changes never orphan these entries.
* `en.json` is the identity catalog (`"Flash firmware": "Flash firmware"`,
  `"flow.odin_flash_tar": "Flash firmware tar (native)"`) and defines the
  required key set.
* Missing or empty values fall back to English, so partial translations are
  always safe to ship.
* Keep placeholders exactly as written: `{model}`, `{0}`, `%n`, `%1`.
* Do **not** translate brands, model numbers, or protocol terms such as FRP,
  BROM, EDL, fastboot, DA, PIT, Knox, Odin, MTK, QCOM, SPD.
* `meta.machine_translated` lists entries that came from machine translation
  and still need a human review. Deleting the `meta` block is fine once a
  language has been reviewed.

#### What is translated today

The catalogs hold **612 phrases** (`strings`) plus **138 stable keys**
(`keys` = flow captions, job names, transport modes), and every language
ships them translated. Covered surfaces:

- Shared chrome: title bar, OEM chip bar, device strip, transport picker,
  console dock (header, controls, search/filter, context menu).
- Flow captions, job headers and transport-mode headings (stable ids, so
  English wording changes never orphan a translation).
- Every operations page: Samsung (Odin), MediaTek, Qualcomm, SPD/UNISOC,
  Samsung FUS firmware downloader, quick actions, battery/network tools,
  and settings (including the language picker itself).
- The device drill-down board (brand → model → actions) and the shared QR
  provisioning helpers.
- Toasts (title and detail) and the application's own console status lines.

Three rules keep this honest:

1. **Console level prefixes stay English.** `_classify()` matches `[error]`,
   `[step]`, `[refused]`, `[device]`, `[fus]`, so those lines are built as
   `"[step] " + tr("...")` — the prefix is never handed to a translator.
   `tests/test_i18n.py` fails if a catalog key starts with a level token.
2. **Raw tool output is never translated.** Bridge/adb/fastboot output,
   device text, serials, paths, protocol tokens and anything under
   `supported_devices.json` stay exactly as the device reported them.
3. **Module-level helpers use `i18n.tr()`.** Code with no widget to call
   `self.tr()` on (device-board applicability, QR helpers) goes through
   `i18n.tr()`, which performs the same offline lookup at call time.

Safety-review hold: the long **confirmation-dialog bodies**
(`_DESTRUCTIVE_CONFIRM`) and the **EXPERIMENTAL legal warnings**
(`python/core/experimental.py`) remain English on purpose. Machine-translating
words like "IRREVERSIBLE" or "may void warranty" without a native-speaker
review is too risky; they will be handled by a dedicated reviewed pass.

#### Pseudo-locale smoke test

`tests/test_i18n_pseudo.py` installs a synthetic catalog that wraps every
value in `⟦…⟧`, builds the real window, and asserts the markers reach the
chrome, the flow browser rows (label, job header, mode heading) and
`i18n.tr()`. It catches strings that never reach the translator, and proves
the layouts survive visibly longer labels.

### Workflow

1. Wrap user-facing text in `self.tr("...")` / `tr("...")` in the GUI code.
2. Run the extractor; it merges new keys into every catalog and prints the
   coverage gap:

   ```bash
   .venv/bin/python scripts/i18n_extract.py
   ```

3. Fill the empty values in `i18n/json/<lang>.json` (or optionally seed them
   with machine translation, then review):

   ```bash
   .venv/bin/python scripts/i18n_extract.py --seed --lang fr
   ```

4. Verify nothing is stale or missing:

   ```bash
   .venv/bin/python scripts/i18n_extract.py --check
   .venv/bin/pytest tests/test_i18n.py tests/test_i18n_pseudo.py -q
   ```

5. Test the switch in **Settings → Language & region** (applies on restart).

Only run `--prune` when you intend to delete keys that no longer exist in the
source; it drops them from every catalog.

Arabic (`ar`) automatically switches the Qt layout direction to
right-to-left. Layouts are derived from the language code, so `ar-EG` works
too.

## Documentation translations (`docs/<lang>/`)

1. Copy the English source file to the matching `docs/<lang>/` path.
2. Translate prose; keep code blocks, commands, paths, and identifiers in English.
3. Keep the language-switcher header at the top of each file. From
   `docs/<lang>/`, siblings are one level up (`../ru/CONTRIBUTING.md`) and the
   English canonical file is two levels up (`../../CONTRIBUTING.md`).
4. Open a PR labelled `i18n`.

`tests/test_docs_links.py` checks that every relative link resolves and that
each translation links back to its English canonical copy.
