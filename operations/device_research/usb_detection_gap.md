# USB algılama — yetenek kaydı

**Kapsam:** FlashPilot'in USB bus'ında cihazı nasıl bulup sınıflandırdığı ve hala
eksik olan şeyler. `src/usb/` üzerine salt okuma inceleme; cihaz dokunulmadı.

---

## 1. Yürütme özeti

- Algılama **bus genelinde** çalışır, port bazlı değil: `libusb` numaralandırma + ADB
  birleştirme; cihaz BROM, EDL, indirme modu, fastboot, ADB ya da MTP olarak
  görünse de bulunur.
- Sınıflandırma **arayüz farkındalıklı**dır: VID/PID tabloları satıcı ve aşamayı
  verir; tanımlayıcı sınıflar (ADB 255/66/1, MTP sınıf 6, HID sınıf 3) gerisini
  ayırır.
- Kalan boşluklar, tanımlayıcı düzeyindeki gariplikler (numaralandırma öncesi port
  reset) ve PID tablosunun görülen çiftler kadar iyi olmasıdır.

---

## 2. Tablolar

### 2.1 Tanınan telefon vendor ID'leri (`src/usb/filtering.rs`)

| Vendor | VID | Not |
|---|---|---|
| Samsung | `0x04E8` | Odin, ADB, MTP, HID |
| Qualcomm | `0x05C6` | EDL, DIAG, modem |
| MediaTek | `0x0E8D` | BROM, preloader, DA |
| Spreadtrum/Unisoc | `0x1782` | indirme modu |
| Google | `0x18D1` | ADB, fastboot, MTP |
| Apple | `0x05AC` | normal/recovery/DFU |

### 2.2 MediaTek OEM VIDs

MTK preloader ya da BROM sık sık `0x0E8D` yerine OEM VID altında yeniden
numaralandırılır. Bunlar MTK flashing aşamaları olarak kabul edilir; cihaz hiç
string veya arayüz göstermese bile, çıplak aşama düşürülmez:

`0x0E8D`, `0x0FCE` (Sony), `0x1004` (LG), `0x22D9` (Oppo), `0x9BB5` (InFocus).

### 2.3 Genel Android VIDs

`0x18D1` (Google), `0x0BB4` (HTC), `0x2717`/`0x2A70` (Xiaomi), `0x12D1`
(Huawei), `0x22D9` (ZTE), `0x2AE5` (OnePlus), `0x22B8` (Motorola).

### 2.4 Qualcomm PIDs (`src/qualcomm/sahara.rs`)

| Grup | PIDs | Anlam |
|---|---|---|
| EDL | `0x9008`, `0x900E`, `0x901D`, `0x9025`, `0x9046`, `0x9066`, `0x90DB` | Sahara/Firehose programlanabilir |
| DIAG | `0x9006`, `0x9026` | diag composite'lar — Sahara hello alamaz |
| Geniş | `0x9091`, `0x903A`, `0x6000` | DIAG, modem |

EDL/DIAG ayrımı önemli: `0x9006` composite'a Sahara hello göndermek portu kilitler.

### 2.5 Samsung PIDs (`src/usb/mod.rs`)

| Grup | PIDs | Anlam |
|---|---|---|
| İndirme modu | `0x6601`, `0x685D`, `0x68C3`, `0x68EF`, `0x4EEE`, `0x4EEF` | Odin |
| ADB composite | `0x685E`, `0x68A3`, `0x6868` | açık 255/66 arayüzü olmayan ADB |
| Özel | `0x685C` | Samsung BROM |
| MTP | `0x6860` | MTP |

`0x685D` aynı zamanda normal boot ADB composite'lerinde de kullanılır; kaba ipucu
`samsung-odin` derken Python katmanı ADB imzasını tekrar kontrol eder.

---

## 3. Sınıflandırma

`mode_hint` / `classify_mode` tarafından yayılan mod etiketleri:

| Etiket | Koşul |
|---|---|
| `mediatek-brom` | `0x0E8D:0x0003` |
| `mediatek-preloader` | `0x0E8D:0x2000` |
| `mediatek-da` | `0x0E8D:0x0004` / `0x1004` |
| `mediatek` | diğer `0x0E8D` ya da her MTK OEM VID |
| `qualcomm-edl` | `0x05C6` + EDL PID |
| `qualcomm-diag` | `0x05C6` + DIAG PID |
| `qualcomm` | diğer `0x05C6` |
| `spd` | `0x1782` |
| `apple` | `0x05AC` |
| `samsung-odin` | `0x04E8` + indirme PID, ADB arayüzü yok |
| `samsung-brom` | `0x04E8:0x685C` |
| `samsung-hid` | `0x04E8` + HID sınıf 3 |
| `motorola` / `motorola-adb` / `motorola-mtp` | `0x22B8` |
| `android-adb` | ADB arayüzü 255/66, her VID |
| `android-mtp` | MTP sınıf 6, her VID |
| `fastboot` | `0x18D1:0x4EE0` / `0xD00D` |
| `google` | `0x18D1`, ADB/MTP değil |
| `other` | geri kalan her şey |

### Algılama yöntemleri

1. **Bus numaralandırma** — her cihaz için `libusb` taraması, tanımlayıcı gezinmesi.
2. **ADB birleştirme** — `adb devices -l` satırları seri/VID/PID üzerinden bus listesine
   birleştirilir; aynı telefon çift kez görünmez.
3. **Arayüz tabanlı sınıflandırma** — ADB (`255/66/1`), MTP (sınıf 6), HID
   (sınıf 3) önce kontrol edilir, ardından VID tek başına fallback yapılır.
4. **İsim anahtar kelimeleri** — `android`, `phone` ve Transsion/vendor adları,
   eşleşen VID yoksa son çare telefon sinyali olarak kullanılır.
5. **Hotplug / yeniden numaralandırma** — reset veya exploit sonrası köprü yeniden
   çağrılır; kullanıcı eski tutma ağzında bekletilmez.

---

## 4. Boşluklar

| Boşluk | Etki | Çaba |
|---|---|---|
| Numara taramasında port-reset tekrar yok | Bazı cihazlar yalnızca `usb_reset` sonrası görünür | S |
| PID tablosu görülen çiftler kadar iyi | Bilinmeyen PIDs vendor-only etiketlere düşer | S (devam ediyor) |
| USB tanımlayıcı garipliği veritabanı yok | Bozuk tanımlayıcıya sahip cihazlar yanlış sınıflandırılabilir | M |
| GUI'de izin ön kontrolü yok | Eksik udev kuralı “cihaz yok” gibi görünür, “izin yok” değil | S |
| Çoklu cihaz belirsizliği | `find_mtk_dev("auto")` belirsiz bus'ta reddeder (iyi), ama GUI'de seçim yok | M |

## 5. Öneriler

1. **Tarama hiçbir şey bulamazsa port reset + yeniden numaralandırma** uygula; daha
   önce cihaz görünmüşse.
2. **İzin hatalarını “cihaz yok” ile karıştırma** — erişim eksikliğini `no device`
   yerine “0e8d:0003 erişimi yok” gibi göster.
3. **Belirsiz bus için cihaz seçici ekle**; reddetmek yerine.
4. **Gözlemlenen VID/PID çiftlerini tabloya eklemeye devam et**; her çiftin hangi
   cihaz üzerinde görüldüğünü belirten bir yorumu olsun.
5. **Sadece gerçek cihazın gerektirdiğinde tanımlayıcı-quirk tablosu ekle** — spekülatif
   değil.

## 6. Sonuç

Algılama FlashPilot'in uyguladığı taşıma yolları için kapsamlıdır. Kalan iş hata
yolları için cilalama (izinler, reset+yeniden tarama, belirsiz bus), yeni protokol
kapsamı değil.
