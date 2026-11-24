# Değişiklik Günlüğü

Language switcher: [English](../../CHANGELOG.md) · [Français](../fr/CHANGELOG.md) · [Español](../es/CHANGELOG.md) · [Deutsch](../de/CHANGELOG.md) · [简体中文](../zh/CHANGELOG.md) · [Русский](../ru/CHANGELOG.md) · [Português](../pt/CHANGELOG.md) · [日本語](../ja/CHANGELOG.md) · [العربية](../ar/CHANGELOG.md) · [हिन्दी](../hi/CHANGELOG.md) · **Türkçe**

> English kanonik kaynaktır. Bu sayfa bir çeviridir; katkı memnuniyetle karşılanır — bkz. [`../TRANSLATION.md`](../TRANSLATION.md).

## 1.2.2 (otomatik güncellemeler, 10 dil, Rockchip + modem-güvenli çoklu cihaz)

*1.2.2 → 1.3.2 geliştirme döngüsü notlarını birleştirir — 1.2.1'den bu yana çıkan her şey.*

### Otomatik güncellemeler ve What's New (yeni)

- Güncellemeler otomatik kurulur: indirilen `.deb` arka planda sudo ile kurulur, uygulama yeniden başlar ve ilk açılışta tek seferlik bir "neler eklendi veya değişti" penceresi yeni sürümün değişiklik günlüğünü gösterir (Ayarlar → Güncellemeler'de otomatik kurulum kapalıyken manuel "Install Now" istemi kalır).

### 10 dilli arayüz + canlı dil değişimi (yeni)

- Arayüzün tamamı 10 ek dilde gelir (Français, Español, Deutsch, 简体中文, Русский, Português, 日本語, العربية, हिन्दी, Türkçe): ayarlar, cihaz kutucukları, sayfalar ve konsol dizeleri.
- Arayüz dilini değiştirmek anlıktır — yeniden başlatma yok; düzenler gerçek yazı tipi metriklerine uyarlanır, böylece uzun çeviriler kontrolleri kırpmadan satır sonuna iner.
- Anahtar tabanlı JSON çeviri katalogları kapsam doğrulamasıyla; CI kurulu katalogları smoke-test eder.

### Rockchip + daha akıllı algılama (yeni)

- Yeni Rockchip marka sayfası: fastboot modu üzerinden RK28xx–RK35xx ailesi.
- Algılama yalnızca çipi değil, modeli, markayı ve form faktörünü tanımlar.
- Her flash aşaması yakalanır (TFT paritesi): MediaTek BROM/preloader/DA tüm aşama PID kümesi ve OEM VID'ler (preloader VCOM 0x2000/0x2001 dahil), genişletilmiş Qualcomm EDL download-PID ailesi, SPD download-PID birleşimi ve kendi modu olarak adlandırılan Qualcomm HS-USB Diagnostics boyunca.
- Mod rozeti SEÇİLEN cihazı takip eder ve OTHER yerine gerçek USB protokolünü adlandırır (ADB/MTP/PTP/DIAG/storage/RNDIS): düşük seviyeli MediaTek etiketini yalnızca flashing PID'leri sahiplenir, Qualcomm EDL kendi rozet çipini korur ve 'MEDIATEK'/'download' alt dize düşüşleri düzeltildi.

### Motorola FRP (yeni)

- CVE-2016-10277 fastboot FRP zinciri, own-DPC sahte-giriş QR sağlama (TestDPC / Device Policy / Adobe), flash + yeniden başlatma döngülerini içeren kademeli fastboot FRP ve factory-bootmode ADB döngüsü.

### Gerçek motor yolları (yeni)

- Rust çekirdeğinde gerçek MTK/QCOM/Unisoc/Samsung flash, FRP ve kilit yolları.
- odin4 gitti: yerel Rust Odin motoru tüm tar hattını, PIT'yi ve bilinen her odin4 sorun sınıfını işler; Apple usbmuxd/lockdown Rust'a taşındı; çekirdek Rust-özel (tüm Python cihaz/protokol geri dönüşleri kaldırıldı).

### Modem-güvenli ADB (düzeltildi)

- Poll/monitor/display yolları zero-touch (`adb-devices --no-probe`): döngülerden open/claim/handshake yok — USB modemler her döngüde yeniden numaralandırmayı bırakır (canlı doğrulandı: bir MSM8916 modemde 114 sessiz poll döngüsü).
- Claim çatışmaları merdivenle devredilir: native → Rust server transport (explicit serial) → host binary → rescue kill (son çare); böylece sistem sunucusu arayüzü elinde tutarken ADB işlemleri başarılı olur.
- USB-ADB birleştirme düzeltmesi (satır dizeleri ayrıştırılır, böylece satırlar gerçekten ADB durumu taşır), busy tutucusu kurtarma + geçici yeniden deneme + dürüst busy durumu, babble/overflow koruması, claim-test izolasyon komutu, modern adb CNXN değerleri ve QCOM/MTK köşeleri sibling dallar gibi ADB yer paylaşımını gösterir.

### Çoklu cihaz güvenilirliği (düzeltildi)

- Settle-retry ile seçim: bir tarama yeniden numaralandırılan bir cihazı geçici olarak ıskaladığında her araç çalıştırıcısı 2,5 s sonra bir kez yeniden dener; GUI onu connected gösterirken "no device" ile reddetmek yerine.
- ADB AUTH, token turları boyunca SHA-256'yı oyunda tutar (tek turlar SHA-256, çift turlar SHA-1); kaybedilen bir round-1 imzası artık yanlış bir "not authorized" duvarına dönüşmez; `_wait_for_adb` geçici tarama hatalarına tolerans gösterir.
- Hedef kimlik bağlama: yeniden kullanılan bir bus:addr'ı işgal eden değiştirilmiş cihaz reddedilir (zero-touch seri kontrolü) — taşıma asla farklı bir telefonu takip etmez.
- Cihaz listesi geçişi: ikinci tarama bir cihazı düşürdüğünde bağlantı çubuğu yeniden oluşturma yeniden dener, cihaz değiştirmek artık ilk telefona geri düşmez ve USB seçimi ıskalanınca ADB araçları ADB daemon satırına geri düşer ("connected görünüyor ama actions no adb diyor").
- Cihaz sınıflandırma + seçici: eşleşmeyen cihazlar yanlış MTP etiketi yerine USB rapor eder ve kaçırılan USB seçimi reddetmek yerine daemon-satır seçiciyi sunar ("Run on this device" / "Cancel").

### Dürüst sonuçlar ve GUI cila (düzeltildi)

- FRP akışları doğrulanmış bayraklar ve gerçek kabuk çıkış durumu ister; sıfır olmayan bridge çıkışı günlük kuyruğuyla bir hata yükseltir — bir daha sahte "completed" toast yok.
- GUI: satır başına iş rozetleri, pencere belleği, toast üst sınırı, klavye gezinme, cihaz-farkında STOP (bir iş o cihazı iptal eder), kg_unlock bir worker thread'e taşındı (30 saniyelik zincirler pencereyi dondurmuyor), splash gerçek derlemeyi izler, ertelenmiş sayfalar yeniden denenebilir kalır, toast'lar üst çubuğu temizler.

### Güvenlik ve sağlamlık

- Varsayılan olarak özel çıktılar, symlink'e dayanıklı geçici adlar, symlink kontrolleri.
- Firmware için varsayılan yaz-sonra-doğrula + model kapısı + sayısal düzeltmeler.
- FRP: DPC imza sertifikası yerel olarak okunur ve provisioning checksum'ı düzeltildi.
- HIL donanım test düzeneği: gerçek donanımda çoklu cihaz / cihaz-değişimi / USB-fırtınası gerileme testleri; ADB-izleyici backoff testleri deterministik yapıldı.
- Yetenek matrisi ve protokol konsoluyla genel açılış sayfası (`website/`).

## 1.2.1 (stabil sürüm)

### Çoklu cihaz desteği (yeni)

- Birden fazla telefon takın: bağlantı çubuğu her birini listeler (model · seri ·
  taşıma yolları); incelemek için bir satıra tıklayın.
- Birkaç eşleşme olduğunda her işlem hangi telefona uygulandığını sorar (0–1
  eşleşmede sessiz). Konsol satırları bir `[device-key]` etiketi taşır.
- Cihaz başına bir işlem: farklı telefonlar paralel flashlayabilir; aynı telefon
  yine seri işler. Global STOP tüm çalıştırıcılara yayılır.
- Kararlı kimlik (`python/core/devices.py`): `adb:<serial>` → `usb:<port-path>`
  → volatile geri dönüş. Hedefler oturumlar açılmadan önce yeniden çözülür,
  böylece USB re-enumeration bir flash'ı artık yetim bırakmaz (`usb device Fail`).
- Yalnızca telefon cihaz listesi: hub'lar, HID, webcam'ler ve kart okuyucular
  filtrenir.
- Yeni `SPD` taşıma modu + salt okunur Qualcomm/SPD algılama akışları.

### Çip başına DENEYSEL (yeni)

- Samsung `Knox / Warranty`, Qualcomm `QCN / Modem`, çip başına `IMEI Repair /
  Change`, `eMMC / UFS` — sahip çip sayfasında amber açılır bölümler (global LAB
  sayfası yok). Her çalıştırmada sahiplik onay kutusu; IMEI değişikliği ayrıca
  `I UNDERSTAND` yazmayı gerektirir. Denetim günlüğüne kaydedilir; kalıcı
  ack'ler asla otomatik geçmez (`check_gate_strict`).

### MTK BROM (düzeltildi + geliştirildi)

- **PID/aşama eşlemesi** mtkclient geleneğine (`0e8d:0003`=BROM,
  `0e8d:2000`=preloader) düzeltildi; Rust, Python, GUI etiketleri, loglar ve
  docs boyunca.
- Yeni `mtk_crash_brom` köprü komutu + `MTK crash preloader into BROM` akışı
  (MTK BROM altında kayıtlı).
- `_wait_mtk_brom_target()` preloader penceresi yerine stabil tutulan BROM'u
  tercih eder; DA keşfi kesilmiş (<1 KB) ikili dosyaları reddeder.

### Odin / flashing (güçlendirildi)

- `_prepare_download_session()`: kernel-driver detach + re-enumeration boyunca 3×
  handshake retry; tüm Odin PID'leri kabul edilir; PIT önbelleği pre-flash
  ısıtılır.
- odin4 `-d /dev/bus/usb/BBB/AAA` ile pin'lenir + USB kaybında tek otomatik
  retry; `.tar.md5` trailer dosya sonuna sabitlenir (streaming, tam RAM read
  yok).
- Native smart flash partition başına MB/s + ETA loglar.

### Sağlamlık güçlendirmesi (review-güdümlü)

- Sahara: parse'ta HELLO command/version/mode/packet-size doğrulanır (eskiden:
  herhangi ≥32-byte blob güvenilirdi); transfer-format self-check artık byte'ları
  düşürmek yerine struct'ları round-trip eder; close hataları loglanır; detach
  claim öncesinde çalışır; handshake transfer/close/reset sonuçlarını atmak
  yerine JSON'a raporlar (reset açık ve görünür).
- ADB auth: token turları arasında sınırlı exponential backoff; takılı görünmek
  yerine tek seferlik keygen duraklaması duyurulur.
- MTK: yapılandırılmış paket boyutu gerçekten DA session'a ulaşır (hesaplanıp
  düşürülüyordu; session'lar 64K hardcode'lu), 512B–1MB'ye clamp'lenir.
- Safety backups: hatalar geçen süre ve STOP ipucu içeren kaçırılmaz bir banner
  yazdırır (sözleşme değişmedi: işlemi asla engellemez).
- Deneyel geçitler: iCloud + Pixel akışları strict per-run ack'lere taşındı; GUI
  ack token'ları artık expiry ile feature başına sayılır (cross-feature bleed
  yok, kayıp ack yok, stale yetkilendirme yok).

### GUI düzeltmeleri

- Üst çubuk kırmızı kenarlıklar + düğme küçülmesi eşzamanlı shake/rubber
  animasyonları ve accent-tinted focus ring'lere izlendi: animasyonlar
  `_anim_lock` ile serileştirildi + tam temizlik; yeni neutral `focus_ring`/
  `sel_border` tema token'ları (kırmızı accent'ler artık focus'a sızamaz).
- bridge rebuild / log-dir open için `os.system()` → `subprocess`.
- Yinelenen SPD "Enable ADB" stub, `fastboot_unlock` experimental mis-gating,
  dead FUS→AP-slot yolu ve eksik `finished` emit düzeltildi. Dead
  LAB/Knox/QCN/PAC experimental yüzey kaldırıldı.

### Yeniden yapılandırma

- `python/core/frp.py` (god file) → `python/core/core.py` (registry + flows);
  `frp.py` artık yalnızca FRP. Dead `python/core/flows/` bölünmesi kaldırıldı.
- Fiil-önce iş adları (`Remove FRP`, `Flash Firmware`, …); flow başına tek
  canonical snake_case key; display-name casing normalize edildi.

### Docs

- Güncel ekran görüntüleri (`docs/samsung.png`, `mtk.png`, `spd.png`), yeniden
  yazılmış README öne çıkanlar/matris/layout, CONTRIBUTING mimarisi + flow
  kuralları, bu changelog.

### boot.img + AVB (tek native motor)

- Rust köprüsüne yeni image-surgery motoru (`src/imgtools.rs`): Android boot
  header parse, cpio newc scan, prop patching (pad-in-place veya header rewrite ile
  magiskboot-style grow), deterministik gzip (mtime=0, level 9), AVB vbmeta flags.
  `boot-info` / `boot-patch-adb` / `vbmeta-patch` CLI.
- Python `spd_adb` repack + `core._patch_vbmeta_flags` local fallback ile
  devreder (imzalar ve dönüş sözleşmeleri değişmedi).
- Eşdeğerlik çalışması iki gerçek bug'ı düzeltti: grow splice reader'ın
  hizalamasıyla 2 byte uyuşmazdı (sonraki her girdiyi bozuyordu — her iki
  implementasyon), ve re-patching her çalıştırmada `\n` kadar büyüyordu (her iki
  taraf artık idempotent). gzip byte'ları kasten parity'den hariç (zlib
  implementasyonları farklı); decompres edilmiş içerik, boyutlar ve alanlar
  eşleşir.
- 6 Rust birim testi + 9 cross-implementation testi.

### PAC (tek native motor + kablolu GUI aksiyonları)

- Rust köprüsünde yeni SPD PAC motoru (`src/pac.rs`): YGDP layout ile
  parse/extract/pack, paylaşılan header/slot builder'lar artık `spd-readback`
  writer tarafından da kullanılır (byte-identical output; tarihsel doubled slot
  adları karantinaya alındı, propagate edilmiyor). `pac-parse` / `pac-extract` /
  `pac-pack` CLI.
- Python `pac.*` local fallback ile devreder; FLOWS'a kayıtlı ve GUI dispatcher'da
  map'lenmiş yeni `flow_pac_extract` / `flow_pac_pack` (file-only, ofp-style env
  inputs) — daha önce dead olan PAC düğmeleri artık çalışır.
- Eşdeğerlik testleri yakaladı ve gerçek bir bug düzeltti: local packer sessizce
  product string'i düşürür (slice-copy write); ayrıca her iki motorde de aynı
  mesajlarla u32 overflow guard'ları.
- 5 Rust birim testi + 7 cross-implementation testi (her iki yöne roundtrip, sanitize
  parity incl. dir collision, error mapping).

### PIT (tek native motor)

- Rust köprüsünde yeni Samsung PIT motoru (`src/pit.rs`): parse (28/132 layout),
  header/model string'leri, name normalization, find, overlap scan, forensic
  validation + health verdict'ları — gerçek dump'larda ve edge case'lerde (junk
  isimler için Python-`repr` parity dahil) Python implementasyonuna
  byte-identical mesajlar, özetler ve verdict'ler.
- `pit-parse` / `pit-health` / `pit-find` / `pit-overlaps` / `pit-model` CLI; binary
  absent olduğunda Python `pit.*` raw-bytes paths local fallback ile devreder
  (sözleşmeler korunur: ValueError/None/never-raise). In-memory object paths ve
  display helper'lar local ve hızlı kalır; shared rules 11 cross-implementation
  equivalence testiyle sabitlenir.
- 8 Rust birim testi (layout vectors, normalize table, meta overlap
  classification, summary/human-size shapes).

### ADB (native transport, no platform-tools)

- Rust köprüsünde yeni native ADB client (`src/adb.rs`): kernel-driver detach'li
  USB transport (255/66/1), CNXN handshake, RSA-SHA256/SHA-1 AUTH (eksik
  olduğunda üretilen `~/.android/adbkey` yeniden kullanılır), `shell:` ve
  `sync:` (STAT/RECV/SEND) servisleri.
- `adb-devices` native bir taramadan `adb devices -l` satır sözleşmesini korur
  (`device` / `unauthorized` / `no permissions`); `adb-shell` bir serial alır (`-`
  = first authorized), artı serial-pinned yeni `adb-pull` / `adb-push`.
- Python: `bridge.adb_shell()` explicit > ambient-scope > first authorized serial
  çözer (multi-device ADB artık target-pinned); `adb.py` bridge'e devreder; EFS
  backup/restore pull/push unpinned system `adb` çağrıları yerine bridge üzerinden
  gider. `has_adb()` artık "bridge built" anlamına gelir.
- 6 Rust testi (framing, banner, PKCS#1 sign/verify, DER roundtrip, system adb
  key'ine karşı bit-identical pubkey blob) + 9 Python testi.

### Fastboot (native transport + Motorola universal)

- Rust köprüsünde yeni native fastboot USB transport'u (`src/fastboot.rs`):
  command phase (getvar/oem/erase/reboot) için kernel-driver detach'li
  `fastboot-devices` (JSON) + `fastboot-cmd <vid:pid@bus:addr> <ms> <cmd…>`.
  Device-side FAIL exit 0 ile `FAILED (remote: …)` olarak render edilir, system
  binary transcript şekliyle eşleşir (Moto MBM bootloader'larda OKAY packet
  içinde yol alan lone `getvar` değerleri dahil).
- Paylaşılan Python helper'lar (`_fastboot_run`, `_wait_fastboot`,
  `_fastboot_getvar`) system-binary fallback'li native-first; DATA-phase
  komutları (flash/boot/…) her zaman system binary kullanır ve host-side
  `devices` listesi native detect'tan servis edilir. Tüm fastboot trafiği
  artık target-pinned (`vid:pid@bus:addr`), no-`-s` wrong-phone hazard'ını
  kapatır.
- Yeni brand-wide Motorola akışları (`moto_frp_adb`, `moto_frp_fastboot`,
  `moto_oem_unlock_token`): ADB provisioning reset, lock-state read + session
  resets'li official unlock-token akışı, read-only token reader. Motorola → All
  Motorola / Lenovo (universal) ve her Moto modeli altında gösterilir; unlock
  portal URL düzeltildi (eski `motorola.com/unlockbootloader` ölü).
- `python/core/fastboot.py` (Pixel) ve `usb_watch.py` (lsusb scraping) köprüye
  taşındı; 7 yeni `tests/test_fastboot_native.py` testi.