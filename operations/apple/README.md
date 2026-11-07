# apple/ — Apple cihaz operasyonları (yalnızca FRP değil)
Apple akışları: iCloud, Activation Lock, MDM — A9–A11 için checkm8 DFU (A12+ için usbmuxd/lockdownd) kullanır.

```
apple/
  icloud/                  — iCloud kaldırma/ekleme (DENEYSEL, A9–A11 DFU 05ac:1227, ramdisk)
  activation_lock/         — Activation Lock (Find My) atlama yolları
  mdm/                     — Apple MDM / DEP kaldırma (profil, ABM)
  enterprise_remote_lock/  — Kurumsal uzaktan kilit (MDM/DEP uzaktan kilit temizleme)
  lost_mode_remove/        — Lost Mode kaldırma (Find My kayıp modu)
  passcode_lock_remove/    — Parola / Screen Time kaldırma
```

İşlem bazlı durum (tüm kilit kaldırmalar DENEYSEL, sahiplik kanıtı + denetim günlüğü gerektirir; A9–A11 = checkm8 DFU ramdisk, A12+ = yalnız bilgi):

- `icloud/` — iCloud/Activation Lock kaldırma yolları.
- `activation_lock/` — Find My Activation Lock atlama yolları.
- `mdm/` — MDM / DEP profil kaldırma (ABM).
- `enterprise_remote_lock/` — kurumsal/DEP uzaktan kilit temizleme.
- `lost_mode_remove/` — Find My Lost Mode temizleme.
- `passcode_lock_remove/` — parola / Screen Time kaldırma.

Kaynaklar: Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI): `apple_info`, `apple_passcode_guide`, `apple_icloud_remove/add`; USB 05ac işleme `src/usb/` içinde.
(Eski `python/core/apple.py` motor modülü, akışlar Rust'a taşındığında emekliye ayrıldı; `python/core/flows/apple` planlandı ancak asla teslim edilmedi.)
Tüm kilit kaldırmalar artık buraya taşındı (carrier_unlock altında değil).
