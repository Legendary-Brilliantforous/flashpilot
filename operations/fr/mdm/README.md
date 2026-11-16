# mdm/ — Mobile Device Management + KnoxGuard

Language switcher: [English](../../mdm/README.md) · **Français**

Déverrouillage MDM, KG/RMM, garantie Knox.

Sources : Flux Rust (registre `src/flows.rs`, CLI `flow-run`) : `mdm_qr`,
`mdm_diagnostics`, `mdm_unlock*`, `knox_check` / `knox_bypass`
Rust : chemins AT+KSTRINGB / KGLOCK dans `src/at.rs`
Sortie du générateur QR : `mdm_qr/` (racine du dépôt)
(Retiré : `python/core/knox.py` ; `python/core/flows/mdm.py` était prévu mais
jamais livré — la logique MDM vit dans les flux Rust.)

Structure :
```
mdm/
  devices/  — toutes les marques SAUF apple (le MDM apple vit sous apple/mdm/)
    samsung/   — MDM Samsung Knox / KG (série A)
    tecno/ infinix/ itel/ xiaomi/ oppo/ realme/ oneplus/ vivo/ huawei/ motorola/ nokia/ tcl_zte/ lg/ asus_sharp
    ...        — miroir de frp/devices sans apple
```

Accueillera : découpes mdm.py + génération mdm_qr.
Note : le MDM apple est sous `apple/mdm/` au niveau supérieur, pas ici.