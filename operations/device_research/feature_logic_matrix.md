# Özellik ve mantık matrisi — FlashPilot motor yetenekleri

Bu, FlashPilot'in kendi yetenek kaydıdır: her motor hangi CLI komutlarını
ortaya çıkarır, bir cihaz satırının taşıma bayrakları cihaz sayfasında hangi
eylemlerin yanıp sönmesini sağlar ve hangileri henüz bağlanmamıştır. Bu bir
planlama belgesidir, kullanıcı kılavuzu değil — kaynak gerçeklik `src/main.rs`'tir.

Durum açıklaması: **wired** = komut vardır ve bir akışta kullanılır;
**partial** = komut vardır ancak bir yol stub veya donanım doğrulanmamış durumdadır;
**absent** = komut yok.

---

## 1. Yetenek bayrakları → etkin eylemler

Cihaz veritabanı (`python/gui/supported_devices.json`) **taşıma yeteneğini**
saklar; eylem kümesi model için türetilir:

```
enabled_actions(model) = actions_for(engine) ∩ model.actions
```

| Satır sinyali | Motor | Açılan eylemler |
|---|---|---|
| `Brom` / `Preloader` / `auth` | `mtk` | bilgi, da-yükleme, flash, okuma, yedekleme, frp, imei, fabrika, adb-etkinleştirme |
| `Edl` | `qcom` | bilgi, sahara/firehose, flash, bölümler, yedekleme, frp-sıfırlama |
| `spd` | `spd` | bilgi, flash, bölümler, biçimlendirme, yedekleme, frp, spl-yama |
| `Odin` | `odin` | bilgi, pit, flash, aracı |
| `apple` | `apple` | algıla, bilgi |
| *(yok)* | `mtk` yedeği | yalnızca bilgi |

Taşıma bayrağı olmayan bir satır yine de render edilir; `info` haricinde her şey
kapalıdır. Bu kasıtlıdır: katalogda platform kaydı tutulmayan 212 satır vardır
(§ device_coverage.md), taşıma türünü tahmin etmek cihazı briklemeye yol açar.

GUI, her eylem satırını gerçek etiket ve arka plandaki köprü komutunu belirten
bir ipucu ile render eder; komut bağlama adım adım yapılır; dolayısıyla yanan bir
eylem “bu motor bunu destekliyor” demektir, “bu düğme bitti” değil.

### Kısıtlama koşulları

| Kısıt | Nerede | Etki |
|---|---|---|
| `connection: "auth"` | satır | Motor komutları kabul etmeden önce doğrulanmış/imzalanmış bir oturum (SLA veya satıcı kimliği) gerekir. |
| `connection: "Preloader"` | satır | Cihaz BROM değil, preloader durumundadır — önce crash adımı gerekir. |
| `status: "planned"` | satır | Eylemler devre dışı render edilir; yalnızca araştırma amacıyla. |
| loader/programmer kaynağı | çalışma zamanı | MTK için DA/scatter, Qualcomm için Firehose programcısı, SPD için FDL gerekir. FlashPilot firmware görseli göndermiyor. |
| deneysel bayrak | çalışma zamanı | IMEI, NV/EFS yedekleme ve SAM/knox işlemleri denetim günlüğüne kaydedilir ve onayla kısıtlanır. |

---

## 2. MTK motoru

BROM exploit, DA yükleme, scatter tabanlı flash, FRP, bölüm çalışması.

| Komut | İşlem | Durum |
|---|---|---|
| `mtk-detect` | MTK cihazlarını listele (BROM/preloader/DA) | wired |
| `mtk-detect-extended` | genişletilmiş algılama (mod + kimlik) | wired |
| `mtk-payload-check` | paketlenmiş BROM payload'larının çözülüp çözülmediğini doğrula | wired |
| `mtk-da-upload` | Download Agent yükleme | wired |
| `mtk-scatter` | scatter dosyasını çözümle | wired |
| `mtk-flash` | scatter'dan firmware flash et | wired |
| `mtk-flash-part` | tek bölümü flash et | wired |
| `mtk-flash-samsung` | MTK üzerinden Samsung firmware flash et | partial |
| `mtk-backup` | bölümleri yedekle | wired |
| `mtk-read-part` | bir bölümü oku | wired |
| `mtk-verify-part` | bir bölümü doğrula (SHA-256) | wired |
| `mtk-gpt` | cihazdan GPT oluştur | wired |
| `mtk-scatter-gpt` | GPT'den scatter oluştur | wired |
| `mtk-frp` | FRP bypass (scatter tabanlı) | wired |
| `mtk-frp-brom` | BROM exploit üzerinden FRP bypass | wired |
| `mtk-frp-gpt` | FRP bypass (GPT tabanlı) | wired |
| `mtk-adb-enable` | FRP bypass vasıtasıyla ADB'i etkinleştir | wired |
| `mtk-factory` | fabrika sıfırlama | wired |
| `mtk-reboot` / `mtk-reset` | cihazı yeniden başlat / resetle | wired |
| `mtk-emergency` / `mtk-emergency-mode` | acil mod tespiti / girme | wired |
| `mtk-bypass` | BROM exploit (preloader dump) | wired |
| `mtk-brom-exploit` | kamakiri2 / bypass_utility exploit | wired |
| `mtk-exploit` | özel payload ile BROM exploit | partial — bazı yollarda logging stub |
| `mtk-crash-brom` | BROM crash zorla | wired |
| `mtk-dealer` | dealer / yetkili mod | partial |
| `mtk-mem-probe` | exploit sonrası RAM okuma/yazma taraması | wired |

## 3. Qualcomm motoru

Sahara el sıkışması, Firehose XML flashing, GPT/LUN yönetimi, MBN ayrıştırma.

| Komut | İşlem | Durum |
|---|---|---|
| `qcom-detect` | Qualcomm cihazlarını listele (Sahara/EDL) | wired |
| `qcom-sahara` | Sahara el sıkışması, EDL/9008'e gir | wired |
| `qcom-firehose` | ham Firehose oturumu | wired |
| `qcom-flash` | tam Firehose flash (XML tabanlı) | wired |
| `qcom-flash-one` | tek bölüm flash | wired |
| `qcom-verify-part` | bölüm doğrulama | wired |
| `qcom-info` | cihaz/SoC bilgisi | wired |
| `qcom-partitions` | bölümleri listele | wired |
| `qcom-backup` | token-kısıtlı DIAG/QCN yedekleme | partial — deneysel |
| `qcom-frp-reset` | FRP sıfırlama kılavuzu / ADB yolu | partial — EDL FRP yazıcısı yok |
| `qcom-reboot` | yeniden başlatma | wired |

Protokol notları: Sahara (VID 0x05C6: PID 0x2003/0x9008/0x4003), Firehose
`rawprogram`/`patch`/`program` XML, MBN programcı ayrıştırma, LUN farkındalığıyla
GPT, imzalı Firehose için VIP/kimlik doğrulama, seyrek imaj desteği.
Depolama: eMMC 4.5/5.1/5.2, UFS 2.1/2.2.

## 4. SPD/Unisoc motoru

İndirme modu yükleme, bölüm yönetimi, FRP, SPL yamalama.

| Komut | İşlem | Durum |
|---|---|---|
| `spd-detect` | SPD/Unisoc cihazlarını algıla | wired |
| `spd-info` | yonga, sürüm, güvenlik durumu | wired |
| `spd-partitions` | bölümleri listele | wired |
| `spd-flash` | firmware flash et | wired |
| `spd-format` | bölümleri biçimlendir | wired |
| `spd-backup` | bölümleri yedekle | wired |
| `spd-readback` | bölümlerin okuma sonrası kopyasını al | wired |
| `spd-frp` | FRP bypass (frp/nvdata/persistent silme) | wired |
| `spd-reset` | fabrika sıfırlama | wired |
| `spd-spl-patch` | SPL yamalama (güvenlik kontrollerini atla) | partial — donanım doğrulanmadı |
| `spd-magic-pack` | özel paket oluştur | wired |
| `spd-boot` | indirme moduna başlat | wired |

Protokol notları: VID 0x1782 (PIDs 0x0001/0x0002), FDL1/FDL2 yükleme, BSL
el sıkışması, `SP_META_*` semantiği üzerinden NVRAM yedekleme.

## 5. Samsung / Odin motoru

| Komut | İşlem | Durum |
|---|---|---|
| `odin-connect` | Odin indirme modunda bağlan | wired |
| `odin-info` | bootloader/PDA/CSC sürümleri | wired |
| `odin-pit` / `odin-pit-mtk` | PIT oku (Qualcomm/Exynos ve MTK) | wired |
| `odin-send-pit` | PIT yaz | partial — yıkıcı, onayla-kısıtlı |
| `odin-flash` | tar dosyasını flash et | wired |
| `odin-flash-tar` | açık tar dosyasını flash et | wired |
| `odin-flash-multi` | çoklu dosya flash (BL/AP/CP/CSC) | wired |
| `odin-agent` | Odin aracı modu | partial |
| `odin-model` | PIT'ten modeli tanımla | wired |

Samsung'a özgü akışlar (FRP, fabrika sıfırlama, ADB etkinleştirme, Knox/KG),
`src/flows.rs` içinde çalışır ve denetim günlüğüne kaydedilir.

## 6. Apple motoru

| Komut | İşlem | Durum |
|---|---|---|
| `apple-detect` | iDevice'ları listele (normal/recovery/DFU) | wired |
| `apple-info` | cihaz bilgisi | wired |

Geri yükleme/güncelleme akışı yok: bunun için imzalanmış IPSW zinciri gerekir ve
Linux-native araç için kasıtlı olarak kapsam dışıdır.

## 7. Paylaşılan altyapı

| Komut | İşlem |
|---|---|
| `detect-all` / `detect-merged` | tüm motorlar için birleşik bus taraması |
| `unified-flash` | motor-agnostik flash dağıtımı |
| `flow-list` / `flow-run` | adlandırılmış operasyon akışları |
| `actions-for` / `validate-action` | GUI için eylem kısıtlaması |
| `pit-parse` / `pit-find` / `pit-model` / `pit-health` / `pit-overlaps` | Samsung PIT analizi |
| `pac-parse` / `pac-extract` / `pac-pack` | SPD PAC konteynerleri |
| `adb-*` | ADB kabuğu/push/pull |
| `fastboot-*` | fastboot passthrough |
| `usb-*` / `bulk-*` / `hid-*` | ham USB taşıma yardımcıları |

---

## 8. Karşılaştırma: bu alandaki diğer motorlar ne yapar da FlashPilot yapmaz

Kısa ve genel tutuldu; hiçbiri kopyalanabilir kod değildir.

| Alan | Endüstri uygulaması | FlashPilot |
|---|---|---|
| Satıcıya özgü flashing (LGUP/KDZ, Huawei update.app, Xiaomi fastboot ROM) | GUI tarafından çalıştırılan gömülü Windows EXE'leri | yok — Linux'ta kapsam dışı; fastboot ve Odin ortak durumları kapsar |
| Apple restore/update | libimobiledevice + imzalanmış IPSW | yok |
| KitKat dönemi SPD/uygun fiyatlı MTK | her satıcıya ait özel indirme araçları | BROM/DA yolu mevcutsa genel olarak kapsanır |
| IMEI/NV düzenleme Qualcomm | QMSL/DIAG NV öğe yazıcıları | partial — yalnızca token-kısıtlı DIAG yedekleme, NV yazıcısı yok |
| Model başına preloader derlemesi | Fallback olarak yüzlerce paketlenmiş preloader | yok — kullanıcı firmware sağlar |

---

## 9. Cihaz sayfası kablolaması (motor başına gerçek operasyonlar)

Cihaz sayfası artık birincil eylemler için “kablolama daha sonra gelir” uyarısını
göstermiyor. Her eylem **seçili** cihaz anahtarını çözer ve arka plan komutunu,
önce bir onay katmanı ile çalıştırır. Paketlenmiş payload'lar kullanıcıyı dosya
aramaktan kurtarır; firmware görselleri hâlâ kullanıcıdan gelir.

| Eylem | MTK | Qualcomm | Unisoc |
|---|---|---|---|
| bilgi | `mtk-detect` | `qcom-detect` | `spd-detect` |
| FRP (ADB yok) | `mtk-frp-brom auto <bundled-da-dir>` — BROM exploit, yonga bazlı DA, cihaz GPT içindeki `frp`/lock bölümlerini siler | `qcom-frp-reset auto [--wipe-data]` — Sahara programcısı, Firehose `frp, frp_a, frp_b, persist, config, misc` alanlarını siler (tüm LUN'lar) | `spd-flash-pac auto <pac> --mode frp` (veya `spd-frp` ile FDL yazılır) |
| ekran kilidi (ADB yok) | `mtk-screen-lock auto <da>` — `metadata, persistent, keystore, oemkeystore, protect1/2, misc` siler; `--wipe-userdata` ek olarak `userdata, cache, nvdata` siler | ADB `locksettings` yolu; EDL `--wipe-data` BCB yazımı `misc` için | `spd-flash-pac --mode erase` |
| yedekleme | `mtk-backup-gpt auto <da> <dir>` — her GPT bölümü + `manifest.json` | `qcom-backup auto <dir>` — her bölüm/LUN + manifest; boş tablo durumunda hata verir | `spd-flash-pac --mode backup --out <dir>` (veya `spd-backup`) |
| flash | `mtk-flash-auto auto <folder>` — scatter'ı bulur, seyrek/`.lz4` genişletir, boot bölgelerini atlar, A/B slot fallback uygular | `qcom-flash auto <rawprogram.xml> <folder>` — seyrek genişletme, işlem başına LUN, depolama otomatik (emmc→ufs), `<patch>`/silme semantiği | `spd-flash-pac <pac> --mode flash` — FDL'ler PAC içinden okunur |

Derlemede paketlenmiş payload'lar: `payloads/mtk` (mtkclient DA/payload'ları, GPLv3),
`payloads/qcom` (Firehose programcıları + SoC indeksi; adayları sırayla dener).
Unisoc için FDL1/FDL2 PAC'ın kendisinden gelir; bu nedenle loader deposu gerekmez.

## 10. Öneriler

| # | Değişiklik | Fayda | Çaba |
|---|---|---|---|
| 1 | `mtk-exploit`/`mtk-dealer`'ı uçtan uca bağla (halen logging stubs'a düşüyorlar) | “destekleniyor gibi görünür ama sessizce hiçbir şey yapmaz” sınıfındaki hatayı kaldırır | S |
| 2 | Uzun dump'ların öncesinde watchdog kapatma ekle (bkz. `mtk_gap_analysis.md` §4.3) | silahlı BROM'larda dump sırasında resetleri ortadan kaldırır | S |
| 3 | Paketlenmiş setin ötesinde Qualcomm programcı indeksini genişlet (`~/.local/share/flashpilot/payloads/qcom/<soc>/`) | paket içinde olmayan modelleri kapsar | M |
| 4 | MTK/QC/SPD için daha fazla FRP bypass yöntemi ekle | motor başına zaten kapsanmış; daha çok varyant mümkün | M |
| 5 | Daha fazla IMEI tamir yöntemi ekle | motor başına zaten kapsanmış; daha çok varyant mümkün | M |
| 6 | Daha fazla bölüm operasyonu ekle (yerinde geri yükleme, bölge klonlama) | biçimlendirme/yedekleme/geri yükleme/okuma vardır; daha fazlası mümkün | S/M |
| 7 | 148 tanesini kapsam dışında bırakan katalog satırları için satıcı bucket'ları ekle | marka sayısı artar, protokol çalışması gerekmez | S |

Yukarıdakilerin hepsi doğrulama için donanım gerektirir. Bunların hiçbiri yalnızca
tablo mantığına dayanarak yayınlanmamalıdır.
