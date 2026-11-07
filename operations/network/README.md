# network/ — Taşıyıcı / modem / APN / QCN / RNDIS
Ağ yığını: AT+ komutları, modem tanı, QCN yedekleme/geri yükleme, RNDIS bağlanma.

Kaynaklar:
 - Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI): `qcn_backup`, `qcn_imei_repair`, `qcn_nv_browser`, `carrier_lock_*`; modem flashing `fastboot_*` satırları (`flash_partition` DATA aşaması `src/fastboot.rs` içinde)
 - Rust: `src/at.rs` (322 satır), `src/mtp.rs` (295 satır), `src/qualcomm/mbn.rs`, `src/spd.rs` modem bölümleri
Gelecek: network/at/, network/qcn/, network/rndis/
(Eski `python/core/qcn.py` + `python/core/fastboot.py` motor modülleri, akışlar Rust'a taşındığında emekliye ayrıldı.)
