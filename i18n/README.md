# FlashPilot UI translations

Qt `.qm` files for supported UI languages live in `i18n/qm/` (e.g. `flashpilot_fr.qm`).

Workflow
1. Extract source strings with `pylupdate5`/`pylupdate6` into `i18n/ts/flashpilot_<lang>.ts`.
2. Translate the `.ts` (community + tooling).
3. Compile with `lrelease` to `i18n/qm/flashpilot_<lang>.qm`.
4. Set `ui_language` in Settings (or QSettings) to the code.

Supported UI language codes: `en` (default), `fr`, `es`, `de`, `zh`, `ru`, `pt`.
Additional documentation-only languages: `ja`, `ar`, `hi`, `tr`.
