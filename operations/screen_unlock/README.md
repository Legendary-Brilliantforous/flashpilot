# screen_unlock/
Screen lock removal: locksettings, CSC flash, recovery, download, EDL, comprehensive.

Sources: Rust flows (`src/flows.rs` registry, `flow-run` CLI):
`screen_lock_remove`, `screen_lock_locksettings`, `screen_lock_csc`,
`screen_lock_recovery`, `screen_lock_download`, `screen_lock_edl`,
`screen_lock_comprehensive`; MTK sp-flash/meta paths via the `mtk_*` rows
(`mtk_combo_flash`, `mtk_recovery_reset`) + `python/core/mtk.py` helpers.
(Retired: `python/core/flows/screenlock.py` never shipped — the logic
lives in the Rust flows.)
Rust: at.rs carrier/slock portions splitted here later
