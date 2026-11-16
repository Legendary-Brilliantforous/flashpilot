Language switcher: [English](../../mdm/README.md) · [Français](../../fr/mdm/README.md) · [Español](../../es/mdm/README.md) · [Deutsch](../../de/mdm/README.md) · [简体中文](../../zh/mdm/README.md) · [Русский](../../ru/mdm/README.md) · [Português](../../pt/mdm/README.md) · [日本語](../../ja/mdm/README.md) · [العربية](../../ar/mdm/README.md) · **हिन्दी** · [Türkçe](../../tr/mdm/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# mdm/ — Mobile Device Management + KnoxGuard
MDM unlock, KG/RMM, Knox warranty.

स्रोत: Rust flows (`src/flows.rs` registry, `flow-run` CLI): `mdm_qr`, `mdm_diagnostics`, `mdm_unlock*`, `knox_check` / `knox_bypass`
Rust: `src/at.rs` में AT+KSTRINGB / KGLOCK paths
QR generator output: `mdm_qr/` (repo root)
(रिटायर्ड: `python/core/knox.py`; `python/core/flows/mdm.py` planned था लेकिन कभी shipped नहीं हुआ — MDM logic Rust flows में है.)

संरचना:
```
mdm/
  devices/  — Apple छोड़कर सभी brands (apple MDM `apple/mdm/` के अंदर है)
    samsung/   — Samsung Knox MDM / KG (A-series)
    tecno/ infinix/ itel/ xiaomi/ oppo/ realme/ oneplus/ vivo/ huawei/ motorola/ nokia/ tcl_zte/ lg/ asus_sharp
    ...        — `frp/devices` का mirror है, apple minus
```

होस्ट करेगा: mdm.py splits + mdm_qr generation.
नोट: Apple MDM top-level `apple/mdm/` के अंदर है, यहाँ नहीं।
