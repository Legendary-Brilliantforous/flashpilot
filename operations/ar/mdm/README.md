Language switcher: [English](../../mdm/README.md) · [Français](../../fr/mdm/README.md) · [Español](../../es/mdm/README.md) · [Deutsch](../../de/mdm/README.md) · [简体中文](../../zh/mdm/README.md) · [Русский](../../ru/mdm/README.md) · [Português](../../pt/mdm/README.md) · [日本語](../../ja/mdm/README.md) · **العربية** · [हिन्दी](../../hi/mdm/README.md) · [Türkçe](../../tr/mdm/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# mdm/ — إدارة الأجهزة المحمولة (Mobile Device Management) + KnoxGuard

إلغاء قفل MDM، KG/RMM، Knox warranty.

المصادر: تدفقات Rust (registry في `src/flows.rs`، CLI `flow-run`): `mdm_qr`، `mdm_diagnostics`، `mdm_unlock*`، `knox_check` / `knox_bypass`
Rust: مسارات AT+KSTRINGB / KGLOCK في `src/at.rs`
مخرج QR generator: `mdm_qr/` (root المستودع)
(تم إيقاف: `python/core/knox.py`؛ تم التخطيط لـ `python/core/flows/mdm.py` but never shipped — منطق MDM يعيش في тدفقات Rust.)

البنية:
```
mdm/
  devices/  — all brands EXCEPT apple (apple MDM lives under apple/mdm/)
    samsung/   — Samsung Knox MDM / KG (A-series)
    tecno/ infinix/ itel/ xiaomi/ oppo/ realme/ oneplus/ vivo/ huawei/ motorola/ nokia/ tcl_zte/ lg/ asus_sharp
    ...        — mirror of frp/devices minus apple
```

Will host: تقسيمات mdm.py + توليد mdm_qr.
Note: apple MDM تحت top-level `apple/mdm/` not هنا.