# network/ — Carrier / modem / APN / QCN / RNDIS
Network stack: AT+ commands, modem diag, QCN backup/restore, RNDIS tethering.

Sources:
 - python: `python/core/qcn.py`, `python/core/fastboot.py` fastboot flash for modem, `src/at.rs`, `src/mtp.rs`
Rust: `src/at.rs` (322 lines), `src/mtp.rs` (295 lines), `src/qualcomm/mbn.rs`, `src/spd.rs` modem portions
Future: network/at/, network/qcn/, network/rndis/
