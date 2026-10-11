# battery/ — Battery / health / emmc / UFS
Health & storage: battery status, emmc/ufs raw, pit health.

Sources:
 - Rust flows (`src/flows.rs` registry, `flow-run` CLI): `emmc_health` / `emmc_raw` (storage health + raw reads feed the health pages)
 - python: `python/core/device_info.py` (device fingerprint used by the health pages)
(The old `python/core/health.py` + `python/core/emmc.py` engine modules were retired when the flows moved to Rust.)
 - Rust: battery via adb/odin battery HID? (future), `src/bulk.rs`, `src/usb.rs` device_speed/bcdDevice
Future: battery/health/, battery/emmc/
