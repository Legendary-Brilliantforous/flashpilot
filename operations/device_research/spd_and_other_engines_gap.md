# SPD/Unisoc ve diğer motorlar — yetenek kaydı

**Kapsam:** FlashPilot'in Spreadtrum/Unisoc taşıma yolu ve kasıtlı olarak
uygulamadığı motorlar (LG, Apple restore, satıcıya özgü flasher'lar). Statik analiz
ve corpus incelemesi; cihaz dokunulmadı.

---

## 1. Özet

- FlashPilot SPD/Unisoc indirme yolunu doğrudan uygular: FDL yükleme,
  bölüm listeleme/biçimlendirme/yedekleme/okuma, FRP silme, fabrika sıfırlama,
  SPL yamalama, magic pack, indirme moduna başlatma.
- Corpus **94 SPD satırı** taşır; **45'i veritabanında**, 49'u değil (çoğunlukla iTel).
- Bu alandaki geri kalan her şey — LGUP/KDZ, Huawei update araçları, Apple
  restore — Linux üzerinde kapsam dışıdır; bu tasarım kararıdır, backlog maddesi değildir.

---

## 2. Motor ne yapar

### 2.1 Giriş noktaları (`src/spd.rs`)

| Fonksiyon | Amaç |
|----------|---------|
| `detect_spd()` | SPD/Unisoc cihazlarını algıla (VID 0x1782) |
| `spd_detect_cli()` | CLI algılama |
| `spd_info_cli()` | yonga, sürüm, güvenlik durumu |
| `spd_partitions_cli()` | bölümleri listele |
| `spd_flash_cli()` / `spd_flash_cli_v()` | firmware flash et |
| `spd_format_cli()` | bölümleri biçimlendir |
| `spd_backup_cli()` | bölümleri yedekle |
| `spd_readback_cli()` | bölümleri geri oku |
| `spd_frp_cli()` | FRP silme (frp, nvdata, persistent) |
| `spd_reset_cli()` | fabrika sıfırlama |
| `spd_spl_patch_cli()` | SPL yamalama (güvenlik kontrollerini atla) |
| `spd_magic_pack_cli()` | özel paket oluştur |
| `spd_boot_cli()` | indirme moduna başlat |

### 2.2 Komutlar

| Komut | İşlem |
|---------|-----------|
| `spd-detect` | SPD/Unisoc cihazlarını algıla |
| `spd-info` | cihaz bilgisi |
| `spd-partitions` | bölümleri listele |
| `spd-flash` | firmware flash et |
| `spd-format` | bölümleri biçimlendir |
| `spd-backup` | bölümleri yedekle |
| `spd-readback` | bölümlerin geri okumasını al |
| `spd-frp` | FRP bypass |
| `spd-reset` | fabrika sıfırlama |
| `spd-spl-patch` | SPL yamalama |
| `spd-magic-pack` | magic pack oluşturma |
| `spd-boot` | indirme moduna başlat |

### 2.3 Protokol kapsamı

- **Algılama** — VID `0x1782`, indirme modu PIDs (0x0001, 0x0002).
- **FDL yükleme** — FDL1/FDL2 aşama, BSL el sıkışması, baud switch.
- **Bölüm işleri** — listeleme, biçimlendirme, yedekleme, okuma, işlem.
- **Güvenlik** — SPL yamalama (imza denetimi bölgesinin silinmesi/yeniden yazılması),
  imzalı paket cihazları için magic-pack oluşturma.
- **IMEI** — paylaşılan MTK/SPD akış yardımcılarını yeniden kullanır; özel SPD NV
  yazıcısı yoktur.
- **NVRAM** — `SP_META_*` eşdeğer işlemleriyle yedekleme.

### 2.4 Cihaz kapsamı

FDL1/FDL2 ve firmware sağlandığında indirme modunda görünen her Unisoc cihaz
ulaşılabilir. Veritabanı 59 SPD modeli taşır, özellikle:

- Samsung A03/A03s/A03 Core (T606/SC9863A)
- Tecno/Infinix T6xx modelleri
- Oppo/Realme bütçe modelleri (SC9863A)
- iTel (24 model, hepsi SPD)
- Nokia ve Lava Unisoc modelleri

---

## 3. Samsung / Odin

Odin doğrudan uygulanmıştır (`odin-*`), PIT okuma/yazma, tar ve çok dosyalı flash
(BL/AP/CP/CSC) ve MTK varyant yolu dahil. Samsung FRP, fabrika sıfırlama, ADB
etkinleştirme ve Knox/KG işlemleri `src/flows.rs` içinde çalışır ve denetim
günlüğüne kaydedilir.

Boşluklar:

- **Write-PIT yıkıcı ve hafif test edilmiştir.** Zorunlu PIT yedeği ve güvenli
  sayılmadan önce ikinci onay gerektirir.
- **Heimdall interop yok.** Gerek yok — yerel yol aynı cihazları Heimdall'ın
  `libusb` gariplikleri olmadan kapsar.
- **LGUP/KDZ yok.** LG firmware KDZ arşivi olarak gelir ve LG'nin kendi protokolünü
  gerektirir; LG ayrıca telefon işinden çıktı, bu yüzden veritabanı bucket'ı
  kaldırıldı.

## 4. Apple

`apple-detect` ve `apple-info` normal/recovery/DFU numaralandırmasını kapsar. Geri
yükleme/güncelleme akışı yok: bunun için imzalanmış IPSW zinciri gerekir ve kapsam
dışıdır.

## 5. Satıcıya özgü flasher'lar

| Alan | Durum | Gerekçe |
|---|---|---|
| LGUP/KDZ | yok | Windows-only, ölü satıcı |
| Huawei `update.app` / Kirin flashing | yok | Satıcı imzası gerekir; Kirin FRP açık araştırma boşluğudur |
| Xiaomi fastboot ROM | `fastboot-*` + `unified-flash` ile kapsanır | Satıcı aracı gerekmez |
| Motorola blank-flash | `moto_flash.rs` yolu | Yerel |
| Apple restore | yok | İmzalanmış IPSW zinciri |

Desen tutarlıdır: taşıma yolunu uygula, kullanıcıdan firmware sağlar, hiçbir satıcı
EXE'sini paketleme.

---

## 6. Boşluklar ve riskler

| Boşluk | Etki | Çaba |
|---|---|---|
| SPL patch donanım doğrulanmadı | Reklamı yapılan işlem güvenli cihazlarda başarısız olabilir | M |
| 49 SPD katalog satırı ithal edilmedi | iTel ağırlıklı liste kapsamı küçümser | S |
| SPD özel NV/IMEI yazıcısı yok | IMEI işi paylaşılan yardımcılara bağlı | M |
| Write-PIT güvenliği | Bir yanlış PIT cihazı hard-brick edebilir | S/M |
| SPD 5G (T7xx) doğrulaması yok | Daha yeni Unisoc parçaları farklı FDL aşaması gerektirebilir | M |

## 7. Öneriler

1. Kalan 49 SPD satırını (çoğunlukla iTel A12–A60 / Vision / S-serisi) ithal et.
2. Güvenli bir SC9863A cihazında SPL patch'i doğrularken `partial` statüsünden
   çıkarma.
3. `odin-send-pit` etrafına PIT yedeği + çift onay ekle.
4. Mevcut token kuralı ve denetim günlüğü arkasında SPD NV/IMEI yazıcısı ekle.
5. Cihaz mevcutsa SPD 5G (T7xx)'yi FDL matrisi içine ekle.

## 8. Sonuç

SPD/Unisoc kapsamı FlashPilot'in hedeflediği 4G parçaları için protokol olarak
tamdır. Kalan iş doğrulama ve cihaz listesi genişliğidir; amaç dışı işler (LG,
Huawei satıcı flashing, Apple restore) amaç dışı kalmaya devam eder.
