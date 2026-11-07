# screen_unlock/
Ekran kilidi kaldırma: locksettings, CSC flash, recovery, download, EDL, kapsamlı.

Kaynaklar: Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI):
`screen_lock_remove`, `screen_lock_locksettings`, `screen_lock_csc`,
`screen_lock_recovery`, `screen_lock_download`, `screen_lock_edl`,
`screen_lock_comprehensive`; MTK sp-flash/meta yolları `mtk_*` satırları
(`mtk_combo_flash`, `mtk_recovery_reset`) + `python/core/mtk.py` yardımcıları aracılığıyla.
(Emekliye ayrılan: `python/core/flows/screenlock.py` asla teslim edilmedi — mantık Rust akışlarında yaşıyor.)
Rust: at.rs taşıyıcı/slock bölümleri daha sonra burada bölündü.
