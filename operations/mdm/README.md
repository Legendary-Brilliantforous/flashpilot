# mdm/ — Mobile Device Management + KnoxGuard
MDM unlock, KG/RMM, Knox warranty.

Sources: Rust flows (`src/flows.rs` registry, `flow-run` CLI): `mdm_qr`, `mdm_diagnostics`, `mdm_unlock*`, `knox_check` / `knox_bypass`
Rust: AT+KSTRINGB / KGLOCK paths in src/at.rs
QR generator output: `mdm_qr/` (repo root)
(Retired: `python/core/knox.py`; `python/core/flows/mdm.py` was planned but never shipped — the MDM logic lives in the Rust flows.)

Structure:
```
mdm/
  devices/  — all brands EXCEPT apple (apple MDM lives under apple/mdm/)
    samsung/   — Samsung Knox MDM / KG (A-series)
    tecno/ infinix/ itel/ xiaomi/ oppo/ realme/ oneplus/ vivo/ huawei/ motorola/ nokia/ tcl_zte/ lg/ asus_sharp
    ...        — mirror of frp/devices minus apple
```

Will host: mdm.py splits + mdm_qr generation.
Note: apple MDM is under top-level `apple/mdm/` not here.
