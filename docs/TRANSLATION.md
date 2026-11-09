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
  "meta": {
    "machine_translated": ["Flash firmware"]
  }
}
```

* The **key is the English source phrase** — whole phrases, never single
  words. That keeps catalogs reviewable and Qt-idiomatic.
* `en.json` is the identity map (`"Flash firmware": "Flash firmware"`) and
  defines the required key set.
* Missing or empty values fall back to English, so partial translations are
  always safe to ship.
* Keep placeholders exactly as written: `{model}`, `{0}`, `%n`, `%1`.
* Do **not** translate brands, model numbers, or protocol terms such as FRP,
  BROM, EDL, fastboot, DA, PIT, Knox, Odin, MTK, QCOM, SPD.
* `meta.machine_translated` lists entries that came from machine translation
  and still need a human review. Deleting the `meta` block is fine once a
  language has been reviewed.

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
   .venv/bin/pytest tests/test_i18n.py -q
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
