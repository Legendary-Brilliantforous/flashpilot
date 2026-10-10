# network/ — Carrier / modem / APN / QCN / RNDIS
Network stack: AT+ commands, modem diag, QCN backup/restore, RNDIS tethering.

Sources:
 - Rust flows (`src/flows.rs` registry, `flow-run` CLI): `qcn_backup`, `qcn_imei_repair`, `qcn_nv_browser`, `carrier_lock_*`; modem flash via the `fastboot_*` rows (`flash_partition` DATA phase in `src/fastboot.rs`)
 - Rust: `src/at.rs` (322 lines), `src/mtp.rs` (295 lines), `src/qualcomm/mbn.rs`, `src/spd.rs` modem portions
Future: network/at/, network/qcn/, network/rndis/
(The old `python/core/qcn.py` + `python/core/fastboot.py` engine modules were retired when the flows moved to Rust.)
