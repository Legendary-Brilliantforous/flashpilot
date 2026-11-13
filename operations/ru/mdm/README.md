Language switcher: [English](../../mdm/README.md) · [Français](../../fr/mdm/README.md) · [Español](../../es/mdm/README.md) · [Deutsch](../../de/mdm/README.md) · [简体中文](../../zh/mdm/README.md) · **Русский** · [Português](../../pt/mdm/README.md) · [日本語](../../ja/mdm/README.md) · [العربية](../../ar/mdm/README.md) · [हिन्दी](../../hi/mdm/README.md) · [Türkçe](../../tr/mdm/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# mdm/ — Mobile Device Management + KnoxGuard

MDM unlock, KG/RMM, Knox warranty.

Источники: Rust-потоки (реестр `src/flows.rs`, CLI `flow-run`): `mdm_qr`, `mdm_diagnostics`, `mdm_unlock*`, `knox_check` / `knox_bypass`
Rust: пути AT+KSTRINGB / KGLOCK в `src/at.rs`
Выход генератора QR: `mdm_qr/` (корень репозитория)
(Устарело: `python/core/knox.py`; `python/core/flows/mdm.py` был запланирован, но никогда не поставлялся — логика MDM живёт в Rust-потоках.)

Структура:
```
mdm/
  devices/  — все бренды КРОМЕ apple (apple MDM живёт под apple/mdm/)
    samsung/   — Samsung Knox MDM / KG (A-series)
    tecno/ infinix/ itel/ xiaomi/ oppo/ realme/ oneplus/ vivo/ huawei/ motorola/ nokia/ tcl_zte/ lg/ asus_sharp
    ...        — зеркало frp/devices минус apple
```

Будет содержать: splits mdm.py + генерация mdm_qr.
Примечание: apple MDM находится в top-level `apple/mdm/`, не здесь.