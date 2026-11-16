Language switcher: [English](../../mdm/README.md) · [Français](../../fr/mdm/README.md) · [Español](../../es/mdm/README.md) · **Deutsch** · [简体中文](../../zh/mdm/README.md) · [Русский](../../ru/mdm/README.md) · [Português](../../pt/mdm/README.md) · [日本語](../../ja/mdm/README.md) · [العربية](../../ar/mdm/README.md) · [हिन्दी](../../hi/mdm/README.md) · [Türkçe](../../tr/mdm/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# mdm/ — Mobile Device Management + KnoxGuard
MDM-Unlock, KG/RMM, Knox-Garantie.

Quellen: Rust-Flows (`src/flows.rs`-Registry, `flow-run`-CLI): `mdm_qr`,
`mdm_diagnostics`, `mdm_unlock*`, `knox_check` / `knox_bypass`
Rust: AT+KSTRINGB / KGLOCK-Pfade in src/at.rs
QR-Generator-Ausgabe: `mdm_qr/` (Repo-Root)
(Als retired gilt: `python/core/knox.py`; `python/core/flows/mdm.py` war geplant,
wurde aber nie ausgeliefert — die MDM-Logik lebt in den Rust-Flows.)

Struktur:
```
mdm/
  devices/  — alle Marken AUSSER apple (apple MDM lebt unter apple/mdm/)
    samsung/   — Samsung Knox MDM / KG (A-Serie)
    tecno/ infinix/ itel/ xiaomi/ oppo/ realme/ oneplus/ vivo/ huawei/ motorola/ nokia/ tcl_zte/ lg/ asus_sharp
    ...        — Spiegel von frp/devices minus apple
```

Wird hosten: mdm.py-Splits + mdm_qr-Generierung.
Hinweis: Apple-MDM liegt unter top-level `apple/mdm/`, nicht hier.
