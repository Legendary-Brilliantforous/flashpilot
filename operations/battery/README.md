# battery/ — Pil / sağlık / emmc / UFS
Sağlık ve depolama: pil durumu, emmc/ufs ham veri ve pit sağlığı.

Kaynaklar:
 - Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI): `emmc_health` / `emmc_raw` (depolama sağlığı + ham okuma sağlık sayfalarını besler)
 - python: `python/core/device_info.py` (sağlık sayfaları için cihaz parmak izi)
(Eski `python/core/health.py` + `python/core/emmc.py` motor modülleri, akışlar Rust'a taşındığında emekliye ayrıldı.)
 - Rust: adb/odin pil HID ile? (gelecek), `src/bulk.rs`, `src/usb.rs` device_speed/bcdDevice
Gelecek: battery/health/, battery/emmc/
