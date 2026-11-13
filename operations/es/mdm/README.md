Language switcher: [English](../../mdm/README.md) · [Français](../../fr/mdm/README.md) · **Español** · [Deutsch](../../de/mdm/README.md) · [简体中文](../../zh/mdm/README.md) · [Русский](../../ru/mdm/README.md) · [Português](../../pt/mdm/README.md) · [日本語](../../ja/mdm/README.md) · [العربية](../../ar/mdm/README.md) · [हिन्दी](../../hi/mdm/README.md) · [Türkçe](../../tr/mdm/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# mdm/ — Gestión móvil de dispositivos + KnoxGuard
Desbloqueo MDM, KG/RMM, garantía Knox.

Fuentes: flujos Rust (registro `src/flows.rs`, CLI `flow-run`): `mdm_qr`, `mdm_diagnostics`, `mdm_unlock*`, `knox_check` / `knox_bypass`
Rust: rutas AT+KSTRINGB / KGLOCK en src/at.rs
Salida del generador QR: `mdm_qr/` (raíz del repositorio)
(Retirado: `python/core/knox.py`; `python/core/flows/mdm.py` se planeó pero nunca se publicó — la lógica MDM vive en los flujos Rust.)

Estructura:
```
mdm/
  devices/  — todas las marcas EXCEPTO apple (el MDM de Apple vive bajo apple/mdm/)
    samsung/   — MDM / KG Knox de Samsung (serie A)
    tecno/ infinix/ itel/ xiaomi/ oppo/ realme/ oneplus/ vivo/ huawei/ motorola/ nokia/ tcl_zte/ lg/ asus_sharp
    ...        — espejo de frp/devices menos apple
```

Alojará: splits de mdm.py + generación mdm_qr.
Nota: el MDM de Apple está bajo `apple/mdm/` de nivel superior, no aquí.