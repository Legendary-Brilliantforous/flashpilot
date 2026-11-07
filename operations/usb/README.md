# usb/ — USB taşıma
Tüm USB/Touch katmanları buraya taşındı: rusb glue, descriptorler, kernel detach.

```
usb/
  usb.rs       (712 satır)  — çekirdek algılama, descriptorler, kernel detach
  bulk.rs      (258 satır)  — bulk uç noktaları, bulk_send, bulk_session
  hid.rs       (200 satır)  — Samsung için HID arayüzleri
  mtp.rs       (295 satır)  — MTP katmanı
  at.rs        (322 satır)  — CDC ACM üzerinden AT
  bulk.rs, hid.rs mantıksal olarak burada; src/ içinden taşınacak
  config.rs    (272 satır)  — usb/ yapılandırma + zaman aşımları
```
Telefon flashing mantığı burada yok, yalnızca taşıma katmanı.
