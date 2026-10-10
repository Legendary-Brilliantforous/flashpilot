# mdm/ — Mobile Device Management + KnoxGuard
MDM unlock, KG/RMM, Knox warranty.

Sources: `python/core/flows/mdm.py` (52 KB), `python/core/knox.py`, `python/mdm_qr/`
Rust: AT+KSTRINGB / KGLOCK paths in src/at.rs

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
