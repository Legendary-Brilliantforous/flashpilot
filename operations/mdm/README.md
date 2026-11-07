# mdm/ — Mobil Cihaz Yönetimi + KnoxGuard
MDM kilidi açma, KG/RMM, Knox garantisi.

Kaynaklar: Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI): `mdm_qr`, `mdm_diagnostics`, `mdm_unlock*`, `knox_check` / `knox_bypass`
Rust: src/at.rs içindeki AT+KSTRINGB / KGLOCK yolları
QR üretici çıktısı: `mdm_qr/` (depo kökü)
(Kaldırılmış: `python/core/knox.py`; `python/core/flows/mdm.py` planlandı ama hiç piyasaya sürülmedi — MDM mantığı Rust akışlarında yaşıyor.)

Yapı:
```
mdm/
  devices/  — apple harici tüm markalar (apple MDM `apple/mdm/` altında yaşar)
    samsung/   — Samsung Knox MDM / KG (A-serisi)
    tecno/ infinix/ itel/ xiaomi/ oppo/ realme/ oneplus/ vivo/ huawei/ motorola/ nokia/ tcl_zte/ lg/ asus_sharp
    ...        — apple dışında FRP/devices ile aynı mirror
```

Barındıracak: mdm.py bölünmeleri + mdm_qr üretimi.
Not: Apple MDM üst düzey `apple/mdm/` altında bulunur; burada değil.
