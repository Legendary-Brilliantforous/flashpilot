# Cihaz kataloğu araştırması — FlashPilot cihaz veritabanı karşısında kapsam

Bu dizin, FlashPilot'in kendi cihaz/protokol araştırma külliyatını barındırır:
normalleştirilmiş 1.396 satırlık cihaz kataloğu, motor bazlı gap register'ları ve
MTK yonga/payload matrisi. Bunların tümü katalogun ayrıştırılması ve
FlashPilot'in sevk edilen veritabanı (`python/gui/supported_devices.json`) üzerinden
elde edilmiştir. Donanım üzerinde hiçbir ölçüm yapılmamıştır.

Eşlik eden dosya: [`device_catalogue.json`](./device_catalogue.json) — 1.396
normalleştirilmiş `{brand, model, engine, connection, storage}` satırı. Satır başına
provenans taşımıyor: katalog **araştırma girdisidir** ve sevk edilen ürün
databası (`python/gui/supported_devices.json`) FlashPilot markalı çıktıdır.

## Özet

| Metrik | Değer |
|---|---|
| Katalog satırı | **1.396** |
| Farklı marka | **35** |
| Motor dağılımı | MTK 739 (%53), QCOM 280 (%20), SPD/UNISOC 94 (%7), Odin 71 (%5), bilinmeyen 212 (%15) |
| FlashPilot cihaz veritabanı | **719 model / 21 marka bucket** (650 araştırılmış, 69 planlı) |
| Veritabanında temsil edilen katalog satırı | **745 (%53)** |
| Henüz ithal edilmeyen katalog satırı | **651 (%47)** |
| Analiz edilen MTK scatter düzeni | 28 gerçek scatter → 33 depolama düzeni, 7 SoC, 166 farklı bölüm adı |

Katalog, 2016–2022 orta seviye pazarlık cihaz haritasıdır (A71'e kadar Samsung
A serisi, 11'e kadar Redmi Note, 8'e kadar Tecno Spark, A96'ya kadar Oppo A).
FlashPilot veritabanı 719 girdiden oluşur ve 2023–2025 donanımına daha çok eğilimlidir.
Bunlar birbirinin üst kümesi değildir: katalogun yaklaşık yarısı veritabanına
katılmıştır ve geriye kalan boşluk, 2020 öncesi Samsung, eski MediaTek bütçe
parçaları, Kirin dönemi Huawei ve hiç bucket'ı olmayan 12 marka üzerinde
yoğunlaşır.

## 1. Katalog nasıl oluşturuldu

Ham corpus, 27 export dosyasından oluşuyordu (16 marka JSON dosyası ve 11 düz
metin model listesi). Bunlar beş alanlı tek bir cihaz satırına dönüştürüldü:

| Alan | Kaynak |
|---|---|
| `brand` | Cihaz adı öneki, dosya adı değil (bir export 21 markalık genel bir toplamaydı) |
| `model` | Pazarlama adı; export içinde model kodları da satırda tutuldu |
| `engine` | Önce taşıma bayrakları (`Edl` → qcom, `spd` → spd, `Odin` → odin, `Brom`/`auth`/`Preloader` → mtk), sonra platform ailesi yedeği |
| `connection` | Ham taşıma ipuçları, bir satır birden fazla taşıma bilgisi taşıyorsa `; ` ile birleştirildi |
| `storage` | Ham not alanı — **depolama türü değildir** (bkz. §3) |

Export tarafı toplamları:

| Metrik | Değer |
|---|---|
| JSON export dosyası | 16 |
| Ham nesne | 1,280 |
| Başlık/yer tutucu satır (`Devices : Auto`, vb.) | 13 |
| Gerçek cihaz satırı | 1,267 |
| Benzersiz `(brand, model)` çiftleri | **1,184** (%6.3 tekrar) |
| `.txt` model listesi | 11 dosya, 303 satır |
| JSON içinde bulunmayan `.txt` satırlar | **216** ham → **212** iç liste tekilleştirme sonrası |
| **Katalog toplamı** | **1,396** (1,184 + 212) |

Tekrarlama oranı düşüktür; tekrar eden çiftler Meizu (iki export'ta da görünür) ve
Asus (iki export'ta da görünür). Daha katı tam tuple tekilleştirme ile 1,210
elde edilir; katalog `(brand, model)` temelli çalışır, böylece farklı taşıma
bayrakları olan satırlar sessizce birleştirilmez.

### İthalatı etkileyen bileşen notları

- **Bir export marka dosyası değil genel toplamdı.** Satırlarının 262'si iTel,
  Alcatel, TCL, Lava, BLU, HTC, Motorola, Allview, Coolpad, Micromax, Wiko,
  Ulefone, Yezz, Blackview, ZTE, Amazon, Archos, T-Mobile, OnePlus ve Symphony
  için tek kaynaktır. Marka cihaz adı ön ekinden türetilmelidir.
- **19 Huawei satırı SoC kaydı, cihaz değil** (`HiSilicon kirin 620` …
  `kirin 970 v3`). Gerçek platform/FRP bilgisi taşırlar; bu yüzden katalogta
  kalırlar ama cihaz kapsamı hesabına dahil edilmezler.
- **Realme, marka hatları yerine SoC hatlarıyla bölünmüş.** Oppo export'ı,
  Realme export'ından daha fazla Realme satırı (62) taşır ve Realme export'ı
  yalnızca MediaTek içindir. Bir satır yanlış büyük/küçük harf kullanımına sahip
  (`Realme7i`) ve sınıflandırma öncesi önek normalizasyonu gerekir.
- **Beş JSON dosyası UTF-8 BOM ile başlar ve biri ham kontrol karakter içerir.**
  Naif `json.load` bunları sessizce düşürür; parse `utf-8-sig` / `strict=False`
  ile yapılmazsa corpus %30 daha küçük görünür.

## 2. Ham exportların şema gariplikleri

Anahtarlar dosyalar arasında tutarsızdır. Tüm 1,267 cihaz satırına dair birleşim:

| Anahtar | Satır | Anlam |
|---|---:|---|
| `Devices` | 1264 | ürün adı (marka ön ekiyle) |
| `Models` | 1264 | model kodu(ları) — bazen takma ad (`dandelion`), bazen virgülle ayrılmış liste |
| `Platform` | 1264 | SoC dizesi, serbest biçimli (`MT6765`, `Helio G85`, `Snapdragon 662`, `kirin 970`) |
| `Conn` | 888 | `auth` (554), boş (258), `enable adb` (55), `usb 1.0` (19), `SAVE`, `Harmony` |
| `Brom` | 844 | `Brom` (730), boş (103), `Preloader` (11) |
| `Edl` | 220 | Qualcomm EDL mevcut |
| `Beta` | 182 | `Beta` (49), `Sideload` (49), `FS` (37), `TP` (29), `[SIDELOAD]` (18) |
| `spd` | 94 | Spreadtrum/UNISOC |
| `Storage` | 82 | `UFS` (30), `FRP` (17), `TP` (16), `Test` (10), `eMMC 5.1` (3), gereksiz değerler |
| `Odin` | 56 | Samsung Odin |
| `""` (boş anahtar) | 67 | export içindeki bozuk sondaki virgül |

`Storage` pratikte **depolama alanı değildir** — `FRP`, `TP`, `Test`, `factory` ve
`MIUI 12` hepsi burada görünür. Bunu serbest metin olarak değerlendirin. Gerçek
taşıma ipuçları `Conn`/`Brom`/`Edl`/`spd`/`Odin` olup katalog içinde `engine`
kolonunu bunlardan türetiriz.

## 3. Marka bazlı kapsama

`Catalogue` = `device_catalogue.json` içinde o markaya ait satırlar. Motor sütunları
o taşıma türünü taşıyan satırları gösterir. `In DB` = `python/gui/supported_devices.json`
ile eşleşen katalog satırları (§6). `Gap` = henüz temsil edilmeyen satırlar.

| Marka | Katalog satırı | MTK | QCOM | SPD | Odin | Bilinmeyen | Veritabanı | Boşluk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Xiaomi | 210 | 44 | 111 | 0 | 0 | 55 | 132 | 78 |
| Oppo | 157 | 81 | 66 | 0 | 0 | 10 | 93 | 64 |
| Huawei | 135 | 47 | 13 | 0 | 19 | 56 | 30 | 105 |
| Samsung | 131 | 26 | 36 | 5 | 52 | 12 | 88 | 43 |
| Vivo | 116 | 55 | 39 | 0 | 0 | 22 | 69 | 47 |
| itel | 107 | 0 | 0 | 65 | 0 | 42 | 29 | 78 |
| Tecno | 85 | 79 | 0 | 6 | 0 | 0 | 63 | 22 |
| Realme | 71 | 49 | 9 | 9 | 0 | 4 | 67 | 4 |
| Infinix | 56 | 52 | 0 | 4 | 0 | 0 | 47 | 9 |
| LG | 38 | 35 | 0 | 0 | 0 | 3 | 0 | 38 |
| Honor | 35 | 29 | 6 | 0 | 0 | 0 | 28 | 7 |
| Lenovo | 33 | 31 | 0 | 0 | 0 | 2 | 17 | 16 |
| Alcatel | 31 | 31 | 0 | 0 | 0 | 0 | 0 | 31 |
| Meizu | 20 | 20 | 0 | 0 | 0 | 0 | 4 | 16 |
| TCL | 17 | 17 | 0 | 0 | 0 | 0 | 10 | 7 |
| Lava | 16 | 14 | 0 | 2 | 0 | 0 | 15 | 1 |
| Nokia | 16 | 12 | 0 | 2 | 0 | 0 | 10 | 6 |
| BLU | 13 | 13 | 0 | 0 | 0 | 0 | 10 | 3 |
| HTC | 13 | 13 | 0 | 0 | 0 | 0 | 0 | 13 |
| Motorola | 11 | 11 | 0 | 0 | 0 | 0 | 10 | 1 |
| Allview | 10 | 10 | 0 | 0 | 0 | 0 | 0 | 10 |
| Coolpad | 9 | 9 | 0 | 0 | 0 | 0 | 0 | 9 |
| Micromax | 9 | 9 | 0 | 0 | 0 | 0 | 0 | 9 |
| Vsmart | 9 | 5 | 0 | 0 | 0 | 4 | 0 | 9 |
| Wiko | 8 | 8 | 0 | 0 | 0 | 0 | 7 | 1 |
| Ulefone | 7 | 7 | 0 | 0 | 0 | 0 | 7 | 0 |
| Yezz | 6 | 6 | 0 | 0 | 0 | 0 | 0 | 6 |
| Asus | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 5 |
| Blackview | 5 | 5 | 0 | 0 | 0 | 0 | 1 | 4 |
| ZTE | 5 | 5 | 0 | 0 | 0 | 0 | 4 | 1 |
| Amazon | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 4 |
| Archos | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 3 |
| OnePlus | 2 | 2 | 0 | 0 | 0 | 0 | 2 | 0 |
| T-Mobile | 2 | 2 | 0 | 0 | 0 | 0 | 2 | 0 |
| Symphony | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 |
| **Toplam** | **1,396** | **739** | **280** | **94** | **71** | **212** | **745** | **651** |

Not: `In DB` kolonunda *katalog satırları* sayılır; tek bir veritabanı girdisi
birden fazla SKU satırını toplayabilir (ör. tek bir `itel A14` girdisi `A14`,
`A14 Max` ve `A14 Plus`'ı kapsar).

On iki marka tamamen **FlashPilot bucket'ı olmadan** kalır (148 satır): LG 38,
Alcatel 31, HTC 13, Allview 10, Coolpad 9, Micromax 9, Vsmart 9, Yezz 6, Asus 5,
Amazon 4, Archos 3, Symphony 1. LG kasıtlı olarak hariç tutuldu — marka telefon
işinden çıktı — geri kalanı neredeyse tamamı tek taşıma türü MTK satırlarıdır.
Daha sonra 18 satır, bucket'ı olan markalarda kısmi boşluk oluşturur (Meizu 16,
Blackview 4, BLU 3, …).

## 4. MediaTek scatter araştırması

28 gerçek MediaTek scatter düzeni analiz edildi (artı §4.3'te tartışılan altı
Qualcomm FlashTool XML sarmalayıcısı). Beş scatter, her biri iki depolama düzeni
(EMMC + UFS blokları) içerdiği için toplam **33 düzen** oluştu.

Bir scatter'ın `storage:` başlığı güvenilmezdir: bir düzen başlıkta `storage:
UFS` bildirirken 24 bölümün 23'ü `HW_STORAGE_EMMC`'dir. Güvenilen tek şey bölüm
bazlı `storage:` anahtarıdır.

| Dosya | Platform | Proje | Depolama | Bölümler |
|---|---|---|---|---:|
| `01c.txt` | MT6739 | — | EMMC | 49 |
| `02.txt` | MT6739 | — | EMMC | 51 |
| `03s.txt` | MT6765 | `AndroidBate` | EMMC | 52 |
| `10s.txt` | MT6765 | `s96116ca1` | EMMC | 42 |
| `12.txt` | MT6765 | `k65v1_64_bsp_titan_rat` | EMMC | 52 |
| `22.txt` | MT6768 | — | EMMC | 51 |
| `Android_scatter.txt` | MT6580 | `mtk_android` | UFS (başlık) / EMMC (24 bölümün 23'ü) | 24 |
| `MT6735_Android_scatter.txt` | MT6735 | — | EMMC + UFS | 1 + 1 |
| `_Android_scatter.txt` | *(boş)* | — | EMMC + UFS | 1 + 1 |
| `ambio.txt` | MT6765 | `k65v1_64_bsp` | EMMC | 58 |
| `aqibong.txt` | MT6765 | `k65v1_64_bsp` | EMMC | 58 |
| `biji.txt` | MT6768 | `lancelot` | EMMC | 50 |
| `brow.txt` | MT6765 | `cereus` | EMMC | 44 |
| `crew.txt` | MT6765 | `2022.08.17.2` | EMMC | 57 |
| `dualima.txt` | MT6877 | `k6877v1_64_k419` | EMMC + UFS | 65 + 65 |
| `due.txt` | MT6765 | `oppo6765_18511` | EMMC | 43 |
| `empat.txt` | MT6765 | `oppo6765_19451` | EMMC | 45 |
| `engkah.txt` | MT6765 | `oppo6765` | EMMC | 50 |
| `kak.txt` | MT6785 | `rosemary` | EMMC + UFS | 65 + 65 |
| `kanjut.txt` | MT6765 | `dandelion` | EMMC | 46 |
| `lime.txt` | MT6765 | `oppo6765` | EMMC | 50 |
| `mayan.txt` | MT6785 | `begonia` | EMMC + UFS | 50 + 50 |
| `pipit.txt` | MT6765 | `oppo6765_19581` | EMMC | 45 |
| `raqib.txt` | MT6765 | `angelica` | EMMC | 46 |
| `sca.txt` | MT6768 | `k69v1_64_k419` | EMMC | 54 |
| `seke.txt` | MT6765 | `oppo6765` | EMMC | 51 |
| `toket.txt` | MT6768 | `merlin` | EMMC | 50 |
| `tri.txt` | MT6765 | `oppo6762_18540` | EMMC | 45 |

### 4.1 SoC kapsamı

| SoC | Dosya | Bölüm sayısı |
|---|---:|---|
| MT6765 (Helio P35/G35) | 16 | 42–58 |
| MT6768 (Helio P65/G85) | 4 | 50–54 |
| MT6739 | 2 | 49–51 |
| MT6785 (Helio G95) | 2 | 50/65 (×2 depolama) |
| MT6580 | 1 | 24 |
| MT6735 | 1 | 1 (stub) |
| MT6877 (Dimensity 900) | 1 | 65 (×2 depolama) |
| *(boş)* | 1 | 1 (stub) |

**Yalnızca yedi SoC** var ve dağılım aşırı dengesiz: 28 scatter'ın 16'sı MT6765.
Bu Dimensity değil, Helio P35/G35/G85 külliyatıdır.

### 4.2 Stub scatter'lar

`_Android_scatter.txt` ve `MT6735_Android_scatter.txt` **stub**'dır — bu projede
var olmayan sabit mutlak Windows yoluna sahip tek bir `preloader` girdisi vardır.
Bunlar düzen değil şablondur ve kapsama sayılmamalıdır.

### 4.3 Bölüm düzen sinyali

33 düzen, **166 farklı bölüm adı**. Değişmeyen çekirdek (≥%85 düzenlerde mevcut)
yalnızca 10 addır:

```
preloader  pgpt  para  expdb  metadata  protect1  protect2  seccfg  proinfo  userdata
```

Geri kalanı OEM/SoC'a özeldir. Dikkat çekici gruplar:

| Grup | Bölümler | Nerede görüldü |
|---|---|---|
| Retrofit dinamik | `super` (20/33), `vbmeta` (22/33), `vbmeta_system` (13/33), `vendor_boot` (4/33), `dtbo` (21/33) | Android 10+ düzenleri |
| A/B slotlar | `boot_a`/`boot_b` (5/33), `vbmeta_a`/`vbmeta_b`, `lk_a`/`lk_b`, `tee_a`/`tee_b` | `kak.txt` (17 `_a` çifti), `ambio`/`aqibong`/`crew` (14'er), `dualima` |
| Oppo/Realme rezervleri | `opporeserve1/2/3` (7 dosya), `oplusreserve1/2/3` (3 dosya), `oppo_custom`, `oplus_custom` | `due/empat/engkah/lime/pipit/seke/tri` (oppo), `ambio/aqibong/crew` (oplus) |
| Samsung türevi | `md_udc` (18/33), `gsort` (8), `ffu` (6), `cust` (9), `countrycode` (2), `blk1` (2), `rescue` (2) | MT6785/MT6877 düzenleri |
| MTK NV/güvenlik | `nvram`, `nvdata`, `nvcfg`, `protect1/2`, `seccfg`, `proinfo`, `otp`, `efuse`, `sec1` | evrensel |
| FRP hedefi | `frp` (27/33) | evrensel |

Pratik sonuç: **genel MTK bölüm haritası varsayılmaz.** `frp` 33 düzenin 27'sinde
mevcut, ancak çevre düzen index yerine bölüm adıyla çözülmelidir, çünkü ortam çok
farklıdır (`opporeserve*` vs `oplusreserve*` vs Samsung `md_udc`/`gsort`).

### 4.4 Qualcomm tarafı

Adları `rawprogram*.txt` olsa da altı dosya **Qualcomm rawprogram XML'i değildir**;
MediaTek FlashTool `<flashtool-config version="2.0">` sarmalayıcısıdır ve
yukarıdaki scatter'lara geri işaret eder:

| Dosya | Yonga | Depolama | Referans scatter |
|---|---|---|---|
| `rawprogram1.txt` | MT6739 | EMMC | `01c.txt` |
| `rawprogram2.txt` | MT6739 | EMMC | `02.txt` |
| `rawprogram3.txt` | MT6765 | EMMC | `03s.txt` |
| `rawprogram4.txt` | — | — | bozuk 1,332 baytlık blob (XML değil) |
| `rawprogram5.txt` | MT6765 | EMMC | `12.txt` |
| `rawprogram6.txt` | MT6768 | EMMC | `22.txt` |

Kataloğun 280 Qualcomm satırı bu corpus içindeki herhangi bir
rawprogram/patch XML'e dayanmaz; kullanıcı tarafından sağlanan Firehose
programcılara güvenmektedir.

## 5. Düz metin model listeleri

11 metin listesi, 303 satır, **JSON export'ında görünmeyen 216 satır** (4 iç liste
tekilleştirmesini kaldırınca 212). Bunlar kopya değil ayrı, daha eski bir listedir
(çoğunlukla 2016–2020 Huawei/Honor, Xiaomi/Redmi ve iTel).

| Liste | Satır | Marka | Notlar |
|---|---:|---|---|
| `H.txt` | 59 | Huawei / Honor | Sadece model kodları (`lld-al10`, `BKL-AL20`, `ANE-LX1`), bazı tabletler (`Mediapad`, `Meta 7/8/9/10/20` — "Mate" yanlış yazılmış) |
| `X.txt` | 64 | Xiaomi / Redmi / POCO | Pazarlama adı + takma ad karışımı (`Redmi NOTE 7 (violet)`, `POCO X3 Pro (vayu)`) |
| `itel.txt` | 60 | iTel | Temiz pazarlama isimleri, satır 1'de `Select Model...` yer tutucu |
| `V.txt` | 38 | Vivo / iQOO | Pazarlama isimleri + `PD####` kodları; biri `Vivo NEX` sondaki boşlukla çoğaltılmış |
| `S.txt` | 28 | Samsung | `Samsung A03 SM-A035F SPD` — metin listelerindeki tek taşıma türü açıklaması |
| `Oppo.txt` | 27 | Oppo **+ Realme** | Karışık: `OPPO A76 (CPH2375)` … `REALME 9 (RMX3521)` |
| `O.txt` | 14 | Oppo | `Oppo.txt` ile örtüşür; ayrıca 2 Realme satırı taşır (bir tanesi `Relme Q3 Pro 5G` şeklinde yanlış yazılmış) |
| `VS.txt` | 4 | Vsmart | `V140A`, `V430A`, `V620A`, `V640A` |
| `L.txt` | 5 | LG | `Q51`, `Stylo 6`, `K51`, `V50 ThinQ`, `V60 ThinQ` |
| `N.txt` | 2 | Nokia | `3.2`, `3.4 TA-1288/TA-1283` |
| `I.txt` | 3 | iTel | `S42`, `A22`, `A22 Pro` |

Karşılaştırma: 303 satırın yalnızca **39**'u JSON export'ındaki model koduyla ortaklık
gösterir. Metin listeleri tamamlayıcıdır, yedek değildir; platform bilgisi yoksa
`device_catalogue.json` içinde `engine: "unknown"` olarak tutulurlar.

## 6. FlashPilot'in cihaz veritabanı

`python/gui/supported_devices.json` — 21 marka bucket, **719 model** (650
`researched`, 69 `planned`):

| Bucket | Modeller | Motorlar |
|---|---:|---|
| xiaomi | 112 | mtk 90, qcom 22 |
| oppo | 80 | mtk 48, qcom 32 |
| samsung | 71 | qcom 31, mtk 30, odin 6, spd 4 |
| vivo | 70 | mtk 49, qcom 21 |
| realme | 68 | mtk 49, spd 10, qcom 9 |
| tecno | 66 | mtk 59, spd 7 |
| infinix | 47 | mtk 42, spd 5 |
| huawei | 40 | mtk 33, qcom 7 |
| tcl_zte | 34 | mtk 32, spd 2 |
| itel | 24 | spd 24 |
| motorola | 17 | mtk 12, qcom 3, motorola 1, spd 1 |
| nokia | 15 | mtk 9, spd 4, qcom 2 |
| lava | 15 | mtk 13, spd 2 |
| lenovo | 13 | mtk 13 |
| blu | 10 | mtk 10 |
| others | 10 | mtk 10 (Blackview, T-Mobile, Ulefone) |
| oneplus | 7 | qcom 5, mtk 2 |
| wiko | 7 | mtk 7 |
| apple | 6 | apple 6 |
| meizu | 4 | mtk 4 |
| asus_sharp | 3 | qcom 3 |

Veritabanının motor dağılımı: **mtk 512, qcom 135, spd 59, odin 6, apple 6,
motorola 1**.

## 7. Kapsama karşılaştırması

### 7.1 Eşleştirme yöntemi ve sınırları

Eşleştirme kasıtlı olarak muhafazakâr yapılmıştır, şu sırayla:

1. **Model kodu** — `SM-A155F`, `CPH2219`, `RMX3081`, `TA-1277`,
   `LM-K520`, `PD1901` biçimlerini normalleştir (noktalama/harf büyüklüğünü
   kaldır) ve tam kesişim gerektir. En güçlü sinyal.
2. **Tam ürün adı** — marka öneki, model kodu ve gürültü kelimeleri (`dual`,
   `sim`, `5G`, `Pro`) kaldırıldıktan sonra kalan kısım üzerinde tam eşleşme.
3. **Token-prefix** — bir isim diğerinin tam token-prefix'idir; arasında eşleşmeyen
   *sayı* olmamalıdır (yani `A14` ≠ `A14 Plus` reddedilir ama `Y5p` = `Y5P (DRA-LXX)`
   kabul edilir).

Marka anahtarları açıkça eşlenir (Honor→`huawei`, Lenovo/Motorola→`motorola` ve
`lenovo`, TCL/ZTE→`tcl_zte`, Asus→`asus_sharp`, ölü markalar→`others`).

Sınırlar açıkça şöyle:

- Katalog adları `Devices` + `Models` birleştirmeleridir
  (`Samsung Galaxy A5 2016 (SM-A510F)`); veritabanı kısa adlar kullanır
  (`Galaxy A15`). İnsan daha çok eşleşme yapardı; script tahmin etmez.
- Veritabanı **tek nesil başına bir giriş** taşır, katalog ise **tek SKU başına
  bir giriş** taşır. `Galaxy A15` dolayısıyla tek bir katalog satırına karşılık
  gelmez; çünkü katalogun en yeni Samsung A serisi satırı A71/A52'dir.
- 212 metin-only satırın platformu yoktur ve çoğu model kodu da yoktur; bunlar
  yalnızca isimle eşlenebilir — çoğu 2020 öncesi cihazdır ve veritabanında yoktur.
- 19 HiSilicon sahte satırı ve 2 stub scatter cihaz değildir. Huawei'nin 135
  katalog satırı bu yüzden yaklaşık 116 telefon + 19 SoC satırıdır.

Sonuç: **1,396 katalog satırının 745'i (%53) veritabanı modeline çözümlenir**, 719
veritabanı girdisi üzerinden. Geriye kalan 651 satırın dağılımı: MTK 276,
bilinmeyen platform 181, QCOM 101, SPD 49, Odin 44. 181 bilinmeyen platform satırı
çoğunlukla metin listesi girdileridir (§5) ve hiç yonga almamıştır.

### 7.2 Yapısal olarak ilginç kalan boşluklar

Sadece “daha fazlası” değil:

| Boşluk | Katalog kanıtı | FlashPilot için neden önemli |
|---|---|---|
| **2020 öncesi Samsung A/M/C/J serisi** | 131 Samsung satırı; modern uç A71/A52'yle biter, 2016–2018 A3/A5/A7/A9 kapsamı çok geniştir | FlashPilot Samsung bucket'ı 2023–2025 ağırlıklı. Bunlar tamir atölyelerinde görülen cihazlar. |
| **Tecno/Infinix MTK hacmi** | Tecno 85 (79 MTK), Infinix 56 (52 MTK) — Camon 11–18, Spark 2–8, Hot 6–12, Note 3–11 | 22 + 9 satır hâlâ ithal edilmedi, vaikka her satır SoC dizesi taşıyor. |
| **Oppo/Realme MTK düzenleri** | Oppo 157 (81 MTK), Realme 71 (49 MTK) ve `opporeserve*` bölüm setleri | MTK akışının Oppo/Realme FRP bölüm çözücüsü için doğrudan önemli (hangi bölümleri kaçınmalı). |
| **iTel SPD genişliği** | 107 iTel satırı, 65 SPD (SC7731/SC7731E/SC9832E/SC9863A), 42 bilinmeyen platform metin satırı | A12–A60 / Vision / S serisi tam haritası; 78 satır hâlâ eksik. |
| **Huawei/Honor Kirin FRP** | 19 HiSilicon yonga düzeyi satırı (kirin 620–970) + 116 Huawei/Honor telefonu | FlashPilot Huawei bucket'ı yalnızca MediaTek/Qualcomm. Kirin TP/FRP yolu kapalı. |
| **Bucket'ı olmayan 12 marka** | LG, Alcatel, HTC, Allview, Coolpad, Micromax, Vsmart, Yezz, Asus (eski), Amazon, Archos, Symphony üzerinde 148 satır | Hemen hemen hepsi MTK, platform verisi zaten var — en düşük risk ithalat. |
| **Qualcomm EDL genişliği** | `Edl` bayrağı taşıyan 280 satır, 215'i açıkça `Edl:Edl` | Veritabanında henüz olmayan 101 QCOM satırı hazır EDL aday seti oluşturur. |

### 7.3 FlashPilot'in katalogdan daha çok kapsadığı alanlar

69 `planned` model ve seçilmiş çekirdek için özetlenmiş şekilde:

| Kategori | Sayı | Örnekler |
|---|---:|---|
| 2023–2025 Samsung | 8 | Galaxy A05, A06, A14, A15, A15 5G, A16, A16 5G |
| Apple (tamamı) | 6 | iPhone 6s → iPhone 12, SE 2020 — katalogda **Apple verisi yok** |
| 2023+ Xiaomi/Redmi/POCO | 8 | Redmi 12, 13C, Note 12, Note 13 4G/5G, Poco C65/M6/X6 |
| 2023+ Oppo/Realme | 10 | Oppo A17/A18/A38/A58, Reno 10/11, Realme C53/C55/Note 50/11 Pro |
| 2023+ Tecno/Infinix | 9 | Tecno Pop 8, Spark 10/10C/20, Camon 20; Infinix Hot 30i/40, Smart 8, Note 30 |
| OnePlus | 5 | Nord N20/N30/CE3, 11R, 12R — katalogda yalnızca 2 OnePlus satırı var |
| Motorola modern | 6 | Moto G13/G24/G34/G84, Edge 40 |
| ZTE Blade / TCL 2023 | 5 | ZTE Blade A54/A72, TCL 40 SE, 305 |
| Asus/Sharp 2022+ | 3 | Zenfone 9/10, Aquos sense7 |
| Nokia 2021+ | 4 | G21, G42, C32, 3.4 |

İki dürüst uyarı:

- **Katalog daha eski ama daha geniştir.** En yeni satırları ~2022 civarıdır (Oppo
  Reno 6, Redmi Note 11, Tecno Camon 18). FlashPilot'in `planned` listesi daha yeni.
  İkisi de üst küme değildir.
- **Bazı “boşluklar” adlandırma artefaklarıdır.** `Galaxy A15` ile `Galaxy A71`
  gerçek nesil farkı; `Nokia G21` ile `Nokia G20` bitişik ama farklı cihazdır. Bazıları
  saf yazım hatasıdır (`Pocophone` vs `Poco`, `Relme`, `Meta` for Mate). İnsan
doğrulamalı bir geçiş bu yazım vakalarını kapatır, nesil boşluklarını değil.

### 7.4 Nesil tavanları (sağlamlık kontrolü)

Katalogdaki her aile için en yüksek model numarası — verinin ne kadar eski olduğunu
en net gösteren ifade:

| Aile | Katalog tavanı | FlashPilot'in en yenisi |
|---|---:|---|
| Samsung Galaxy A | A71 | A16 |
| Samsung Galaxy M | M32 | (M serisi girişi yok) |
| Redmi Note | Note 11 | Note 13 |
| Redmi (sayısal) | 9 (artı 10X/20X) | 13C |
| Oppo A | A96 | A58 |
| Oppo Reno | Reno 6 | Reno 11 |
| Vivo Y | Y95 | Y36 |
| Realme C | C35 | C55 |
| Tecno Spark | Spark 8 | Spark 20 |
| Tecno Camon | Camon 18 | Camon 20 |
| Infinix Hot | Hot 12 | Hot 40 |
| Infinix Note | Note 11 | Note 30 |
| itel A | A60 | A70 |
| Nokia G | G20 | G42 |
| Honor | Honor 50 | Honor 90 |

## 8. Veritabanı için kullanılan ithalat kuralları

- **Motor** taşıma bayraklarından gelir: `Edl` → `qcom`, `spd` → `spd`, `Odin` →
  `odin`, aksi halde `mtk`. `Conn=auth`/`Brom` satırın bağlantı durumunu korur.
- **Kimlik**: temizlenen cihaz satırı `model` olarak; model kodları parantez içinde
  tutulur; `vid` motor bazlı sabittir (mtk `0e8d`, qcom `05c6`, spd `1782`, odin `04e8`).
  Samsung MediaTek satırları çift `04e8|0e8d` taşır.
- **İthalat dışı**: ölü marka satırları (LG/HTC/BlackBerry/…), 2016–2017 dönem SoC'leri
  (MT65xx/MT6735/6737/MT6750/53/55/679x, SD410/425/430/450/615/625,
  SC7731x), Exynos/Odin satırları ve arayüz yer tutucuları (`* : Auto`).
- **Durum**: ithal edilen satırlar `researched`'tır çünkü motor seviyesindeki akışlar
  bağlanmıştır; model sayfası tooltip'lerinin `actions` alanı yine satıra dayanır.
- **`source` alanı yok.** Veritabanı kasıtlı olarak satır başına provenans taşımıyor;
  katalog araştırma girdisidir, veritabanı ürün çıktısıdır.

## 9. Sonraki adımlar

Değer / iş hacmi sırasına göre:

1. **12 bucket'ı olmayan markadan kalan 148 satırı** `status: "planned"` olarak
   ithal et. Hemen hemen hepsi MediaTek, platform satır başına verilmiş ve ad
   çakışma riski düşüktür. En düşük risk, en büyük marka sayısı kazancı.
2. **Katalogun satır başına `Platform` alanını yonga alanı olarak kullan.** Bu,
   corpus içindeki en yararlı sütundur: neredeyse her cihaz satırı somut bir SoC
   dizesi taşır (çok azı boş), 719 elle yazılmış veritabanı `chip` değerine kıyasla
   çok daha yararlıdır.
3. **MTK akışının bölüm çözücü testine `opporeserve*` / `oplusreserve*` bölüm
   setlerini uygula.** Bunlar gerçek Oppo/Realme düzenleri; A/B + `super`
   düzenleri Android 10+ durumunu kapsar.
4. **`Storage`'a güvenme.** İçinde `FRP`, `TP`, `Test`, `factory`, `MIUI 12`
   bulunur. Depolama, export'tan değil scatter'dan gelmelidir.
5. **İki stub scatter'ı yalnızca şablon olarak gör.** Tek `preloader` satırı ve ölü
   mutlak yol, cihaz düzeni değildir.
6. **Qualcomm için `rawprogram*` dosyalarını görmezden gel.** Bunlar MediaTek
  FlashTool XML'leri; corpus içinde Qualcomm rawprogram XML yoktur.
7. **19 HiSilicon satırını cihaz olarak ithal etme** — bunlar yonga düzeyi FRP/TP
   girdileridir. `chip` metadata olarak yararlıdır, `model` olarak yanlıştır.

## 10. Doğrulama

```bash
python3 -c "import json;json.load(open('operations/device_research/device_catalogue.json'))"
```

Bu dokümandaki sayımlar yazıldığı tarihte kataloga göre yeniden üretildi: 1,396
katalog satırı, 35 marka, 719 veritabanı modeli, 745 eşleşen satır.
