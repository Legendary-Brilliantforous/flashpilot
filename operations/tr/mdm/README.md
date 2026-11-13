Language switcher: [English](../../mdm/README.md) · [Français](../../fr/mdm/README.md) · [Español](../../es/mdm/README.md) · [Deutsch](../../de/mdm/README.md) · [简体中文](../../zh/mdm/README.md) · [Русский](../../ru/mdm/README.md) · [Português](../../pt/mdm/README.md) · [日本語](../../ja/mdm/README.md) · [العربية](../../ar/mdm/README.md) · [हिन्दी](../../hi/mdm/README.md) · **Türkçe**

> English kanonik kaynaktır. Bu sayfa bir çeviridir; katkı memnuniyetle karşılanır — bkz. [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# mdm/ — Mobil Cihaz Yönetimi + KnoxGuard

MDM kilidi açma, KG/RMM, Knox garantisi.

Kaynaklar: Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI): `mdm_qr`, `mdm_diagnostics`, `mdm_unlock*`, `knox_check` / `knox_bypass`
Rust: src/at.rs içindeki AT+KSTRINGB / KGLOCK yolları
QR oluşturucu çıktısı: `mdm_qr/` (repo kökü)
(Emekliye ayrılan: `python/core/knox.py`; `python/core/flows/mdm.py` planlanmış ama hiç gönderilmedi — MDM mantığı Rust akışlarında yaşar.)

Yapı:

```
mdm/
  devices/  — apple hariç tüm markalar (apple MDM apple/mdm/ altında yaşar)
    samsung/   — Samsung Knox MDM / KG (A serisi)
    tecno/ infinix/ itel/ xiaomi/ oppo/ realme/ oneplus/ vivo/ huawei/ motorola/ nokia/ tcl_zte/ lg/ asus_sharp
    ...        — frp/devices'in apple eksik hali
```

Barındıracak: mdm.py bölümleri + mdm_qr üretimi.
Not: apple MDM üst düzey `apple/mdm/` altındadır, burada değil.
