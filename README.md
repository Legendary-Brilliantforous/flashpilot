# 🔧 FlashPilot

> **Açık kaynaklı bir Samsung firmware flashing ve onarım çalışma masası — Linux için Odin / Heimdall alternatifi; Galaxy telefonları (Download/Odin modu), MediaTek (BROM/DA), Qualcomm (EDL) ve Spreadtrum/UNISOC cihazları için flashing aracı.**

**Arama anahtar kelimeleri:** Samsung flashing aracı · Odin alternatifi · Android firmware flashing Linux · Heimdall GUI · Galaxy telefon onarımı · MTK BROM flash · Qualcomm EDL · FRP unlock · UNISOC flashing · cihaz firmware aracı · mobil onarım · Android bootloader · USB flashing · Linux flashing suite · mülkiyetli araç alternatifi

[![Rust](https://img.shields.io/badge/Rust-1.70+-orange?logo=rust&logoColor=white)](https://www.rust-lang.org)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52)](https://www.riverbankcomputing.com/software/pyqt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![CI](https://github.com/Legendary-Brilliantforous/flashpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Legendary-Brilliantforous/flashpilot/actions)
[![Good First Issues](https://img.shields.io/github/issues/Legendary-Brilliantforous/flashpilot/good%20first%20issue)](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
[![Contributors](https://img.shields.io/github/contributors/Legendary-Brilliantforous/flashpilot)](https://github.com/Legendary-Brilliantforous/flashpilot/graphs/contributors)

**Bu nedir?** Windows'taki ücretli flashing suite'lerine Linux merkezli eşdeğer — **Samsung, MediaTek, Qualcomm ve Spreadtrum/UNISOC cihazlarının** bootloader'ına doğrudan konuşan tek birleştirilmiş araç. Tersine mühendislik edilmiş protokoller + yerel Rust performansı + güzel bir PyQt6 arayüzü = Odin, Heimdall ve pahalı ticari araçların açık alternatifi.

---

## ✨ Bu proje neden önemli

Android onarım dünyası kapalı, Windows'a bağımlı ticari araçlara dayanır. Bu protokollerin tersine mühendisliği küçük bir hobi/araştırma topluluğu tarafından yapılır — ve bu bilgi çoğu zaman ücretli paketlerin içinde ya da eksik forum paylaşımlarında dağınık biçimde kalır.

**Bu proje ise cevap.** Bu tersine mühendislik edilmiş protokolleri, herkesin okuyup, çalıştırıp, genişletebileceği ve kendi flashing suite'ini çıkarabileceği temiz, denetlenebilir, MIT lisanslı bir kod tabanına çevirir.

| Ticari araç | Windows-only, kapalı kaynak | Bu proje |
|---|---|---|
| Odin / Smart Switch | Windows, yalnızca GUI | Açık kaynaklı Odin protokolü (Rust, yerel) + PIT araçları |
| MTK flash araçları | Windows, kapalı DA | MTK BROM/DA flashing & yedekleme (scatter + GPT) |
| Qualcomm EDL araçları | Windows | Sahara + Firehose protokol uygulaması |
| SPD/UNISOC araçları | Windows | Temiz oda BSL indirme uygulaması |
| FRP / kilit araçları | Ücretli, gri piyasa | Şeffaf ADB + download-mode akışları, MDM unlock |

---

## 🚀 Öne çıkanlar — 1.2.1 Stabil (0 uyarı)

- **9 taşıma modu** — ADB, MTP, Samsung Download modu, Samsung BROM, MTK, MTK BROM, Fastboot, Qualcomm EDL, SPD.
- **13 iş kategorisi** — Firmware Flash, FRP Kaldır, Ekran Kilidini Kaldır, MDM Kaldır, Operatör Kilidini Aç, Cihaz Bilgisi Oku, Cihazları Tespit Et, Yeniden Başlat, Ayarları Onar, ve her çip için DENEYSEL: Knox / Garanti (Samsung), QCN / Modem (Qualcomm), IMEI Onarımı / Değiştirme (MTK/SPD/Qualcomm), eMMC / UFS.
- **Çoklu cihaz** — birkaç telefon takın: bağlantı çubuğu her birini listeler, her operasyon hangi telefona ait olduğunu sorar (veya sadece bir eşleşme varsa sessizce çalışır) ve farklı telefonlar işlemleri paralel şekilde çalıştırabilir (cihaz başına bir işlem, STOP tümüne yayılır).
- **Rust çekirdek (`flashpilot-bridge`, ~9.3k LOC) — 0 `cargo check` uyarısı** — ham USB ile *vendored libusb* (sistem bağımlılığı yok), gerçek protokol uygulamaları (+ 18 bağlı ölü-yol, `-80KB` ltcg kesimi).
  - **Samsung**: tersine mühendislik edilmiş Odin oturum protokolü (Heimdall tabanlı), HID download-mode yükleri, PIT oku/yaz/flash — AT `Context` korunur, `EndpointConfig` parçalama.
  - **MediaTek**: BROM / preloader / DA el sıkışma, scatter & GPT, BROM açıkları, SLA anahtarları — `ProgressReporter` gerçek %.
  - **Qualcomm**: Sahara `ProtocolError` + Firehose `QcomDeviceInfo` `Duration` zaman aşımlarıyla bağlı.
  - **SPD/UNISOC**: temiz oda BSL — tüm `BSL_CMD/REP`, `iface`, `flush/read_flash/chip_uid/power_off` bağlı.
  - Ayrıca **MTP**, **AT-command** ve tam **ADB** arayüzü.
- **Stüdyo kalitesinde GUI** — çerçevesiz yarı saydam pencere, 10 vurgu teması, animasyonlu kablo/durum sahnesi, canlı konsol.
  - **Marka ikonları ve ayrı düğme arka planları** — keskin marka ikonları (Samsung Ⓢ, Apple red apple 🍎, Motorola Ⓜ, LG Ⓛ vb.) ve üst çip çubuğundaki her OEM düğmesinde özel marka arka plan renkleri.
  - **Motorola & Apple için yatay görünümler** — model eylem panelleri varsayılan olarak temiz yatay sekmeli düzenler kullanır.
  - **Mikro etkileşimler & Cam efekti** — yumuşak 160ms sayfa geçişi solma animasyonları, monospace meta veri rozet tipografisi (`Consolas`, `Monaco`) ve geliştirilmiş cam efekti kart kenarları.
  - **Geniş merkezlenmiş diyaloglar (620px, sürüklenebilir, ✕)** — beta kapısı + kararlı `UPDATE/AHEAD/PATCH` + flash/FRP onayı, çip renkleri `MTK amber` `QCOM red` `SPD violet` `SAMSUNG blue`, yüksek kontrastlı metin.
  - **Çip bazlı DENEYSEL katlanabilirler** — Knox (Samsung), QCN/IMEI (Qualcomm), IMEI (MTK/SPD): turuncu banner, her çalıştırmada sahiplik onay kutusu, IMEI değişikliği için `I UNDERSTAND` yazılı onay, denetim günlükleri.
  - **Başlıktaki ⏹ STOP** tüm çalışan işlemleri durdurur; cihaz bazlı kilitler diğer telefonların çalışmasına izin verir.

---

## 📸 Ekran görüntüleri

| Samsung operasyonları | MediaTek çalışma masası | Pil onarımı | SPD download |
|---|---|---|---|
| ![Samsung](docs/samsung.png) | ![MediaTek](docs/mtk.png) | ![Battery](docs/battery.png) | ![SPD](docs/spd.png) |

---

## 🧩 Özellik matrisi

| Yetenek | Samsung | MediaTek | Qualcomm | SPD/UNISOC | Herhangi bir ADB |
|---|---|---|---|---|---|
| Tespit / bilgi | ✅ | ✅ (+ crash preloader→BROM) | ✅ (Sahara) | ✅ | ✅ |
| Firmware flash | ✅ (Odin, native Rust) | ✅ (scatter + GPT) | ✅ (Firehose) | ✅ (FDL/regions) | — |
| Bölüm yedekleme | ✅ (EFS) | ✅ | ✅ | ✅ | — |
| FRP bypass | ✅ (ADB + download) | ✅ | ✅ (EDL) | ✅ | ✅ |
| Ekran kilidi kaldırma | ✅ | ✅ | ✅ (EDL) | — | ✅ |
| MDM unlock | ✅ (ADB, QR, recovery) | — | — | — | — |
| Knox garanti/bypass (DENEYSEL) | ✅ | — | — | — | — |
| QCN yedekleme/geri yükleme + IMEI onarımı/değiştirme (DENEYSEL) | — | ✅ (NVRAM) | ✅ (NV 550/682) | ✅ (BSL NV) | — |
| Bölüm araçları | ✅ (PIT) | ✅ (GPT) | ✅ | ✅ (PAC extract/pack) | — |
| Düşük seviye exploit'ler | ✅ (HID/BROM) | ✅ (BROM exploit, SLA) | ✅ (Sahara) | ✅ (BSL) | — |
| Pil / ağ onarımı | — | — | — | — | ✅ |

> 💡 **Pil** ve **Ağ** bölümleri USB hata ayıklaması açık olan *herhangi bir* Android cihazı üzerinde çalışır — ek donanım gerektirmez.

---

## 🖥️ Arayüz

Canlı bir **bağlantı bandı** (bilgisayar → kablo → telefon sahnesi, animasyonlu veri darbesi) üstünde sol **navigasyon çubuğu** ve sağ **konsol/günlük paneli** bulunan, çerçevesiz, yarı saydam, yuvarlatılmış kart penceresi.

- **Bağlantı çubuğu** — canlı cihaz listesi (telefon başına satır: model · seri · taşıyıcılar); cihazı incelemek için satıra tıklayın. Birden çok eşleşme olduğunda operasyon düğmeleri hangi telefonu sorar.
- **Samsung** — Samsung merkez alt sekmeleri: `ODIN FLASH · UNLOCK · ADVANCED FLASH · INFO & TOOLS`, ayrıca firmware yuvaları (AP/BL/CP/CSC/USERDATA), Odin yardımcıları ve `KNOX — DENEYSEL` katlanabilir alan.
- **MediaTek / Qualcomm / SPD** — kendi `— DENEYSEL` katlanabilir alanlarına sahip, yerel düşük seviyeli araçlarla donatılmış özel çalışma masaları (scatter/DA + crash-to-BROM, programmer/XML + QCN/IMEI, FDL ikili dosyaları + base adresleri + IMEI).
- **Pil** — pil sağlığı yüzde, sıcaklık/gerilim/akım, en yüksek tüketiciler; tek tıklamayla onarım.
- **Ağ** — SIM durumu, veri/Wi‑Fi bayrakları, DNS modu; radyo sıfırlama ve yeniden kaydolma.
- **Ayarlar** — otomatik tarama aralığı, varsayılan yollar, konsol otomatik temizleme, 10 vurgu teması, animasyonlar (shake/rubber/cable/bubble geçişleri), pencere parıltısı, motor durumu ve uygulama içi `cargo build`.

**Kısayollar:** `F5` yeniden tara · `Ctrl+Enter` çalıştır · `Ctrl+L` konsolu temizle · `Ctrl+S` günlük kaydet · `Ctrl+F` bul.

---

## 📦 Hızlı başlangıç

**Gereksinimler:** Rust araç zinciri, Python 3.10+, bir Linux masaüstü. Bu kadar — libusb dahili olarak gelir.

```bash
# 1. Rust köprüsünü derleyin (ilk derleme libusb'i kaynak kodundan derler)
cargo build --release

# 2. (Önerilen) USB udev kurallarını kurun, böylece telefonlar sudo gerektirmez
sudo bash root/setup-usb.sh

# 3. Python ortamı
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Başlat
.venv/bin/python -m python.main        # veya: python3 main.py
```

Samsung download-mode flashing native olarak çalışır (Rust Odin protokolü) — mülkiyetli odin4 ikili dosyası getirilmez, paketlenmez ya da gerekli değildir. Samsung combo firmware'ler Samsung'un resmi destek sayfalarından veya güvenilir firmware arşivlerinden alınmalıdır.

---

## 🖥️ Platform desteği — sözünüzü istiyoruz

**Linux desteklenen platformdur.** FlashPilot kasıtlı olarak Windows'a bağımlı flashing suite'lerine karşı **Linux merkezli cevap** — geliştirme, test ve sürümler Linux için hedeflenmiş ve bu değişmeyecek.

**Windows / macOS bugün desteklenmiyor**, pratik nedenlerle:

- Windows USB, telefon moduna göre sürücü çılgınlığıdır (Zadig/WinUSB, QDLoader, birbiriyle çarpışan Samsung sürücüleri); çoğu "telefon algılanmadı" bildirimi uzaktan çözülemez.
- macOS, neredeyse sıfır tamir-cihazi talebi için imzalama/notarya ek yükü getirir.
- Yığın *taşınabilir* (Rust + rusb, Python, Qt), bu nedenle bu bakım kararıdır, teknik imkânsızlık değil.

**Ama bu açık bir soru, kesin bir karar değil.** Windows/macOS desteği istiyorsanız — ya da Linux-only kalmasını savunuyorsanız — bize söyleyin:

- 💬 Bir **[Tartışma](https://github.com/Legendary-Brilliantforous/flashpilot/discussions)** açın
  kullanım durumunuzla (tamir atölyesi? laboratuvar? hangi OS? hangi telefonlar?).
- 🔧 Kod en çok konuşur: plan, `python/core/platform.py` soyutlamasıdır
  (`open_file_manager()`, `detach_kernel_drivers()`, `usb_device_path()`,
  `needs_udev_setup()`) ve Linux tek arka uç, böylece portlar fork yerine ekleyici PR'lar olur. Bu yönde PR'lar şimdi kabul edilir.
- 🎨 Benzer şekilde: katkıda bulunanlar **PySide6** (LGPL, bu MIT projesiyle lisans uyumlu) yerine PyQt6 (GPLv3) üzerine öneride bulundular. Aynı Tartışma üzerinden oy kullanın — geçiş mekanik olsa da önce GUI duman testi kapsamı gerekir.

Karar katkıda bulunan sesleri olmadan verilmeyecek. Gelin siz de onlardan biri olun.

### CLI / köprü

```bash
./target/release/flashpilot-bridge detect          # tüm USB + Samsung filtresi (JSON)
./target/release/flashpilot-bridge fastboot-devices  # fastboot arayüzü bulunan USB cihazları (JSON)
./target/release/flashpilot-bridge fastboot-cmd 22b8:2e80@2:16 20000 getvar securestate  # tek ham fastboot komutu
./target/release/flashpilot-bridge mtk-detect      # MediaTek BROM (0e8d:0003) / preloader (0e8d:2000) / DA
./target/release/flashpilot-bridge mtk-crash-brom <bus:addr>  # preloader'ı tutulmuş BROM'a düşür
./target/release/flashpilot-bridge qcom-detect     # Qualcomm EDL
./target/release/flashpilot-bridge spd-detect      # Spreadtrum/UNISOC (VID 0x1782)
./target/release/flashpilot-bridge odin-pit 04e8:xxxx@bus:addr  # PIT oku
./target/release/flashpilot-bridge at-send <t> ATI # CDC ACM üzerinden AT
./target/release/flashpilot-bridge adb-devices     # adb devices -l olarak JSON
```

---

## 📁 Depo düzeni

```
flashpilot/
├── src/                      # Rust köprü (~13k LOC) — TÜM akışlar burada yaşar
│   ├── main.rs               #   komut satırı girişi (80+ komut) + akış çalıştırma dağıtımı
│   ├── flows.rs              #   REGİSTRASYON: FLOWS / JOBS / MODES (flow! makrosu, ~280 satır)
│   ├── usb/                  #   USB numaralandırma / arayüzler / filtreleme (mod.rs + filtering.rs)
│   ├── devices.rs            #   birleşik USB+ADB cihaz satırları
│   ├── sam_download.rs       #   Samsung Download/Odin protokolü (odin-* komutları)
│   ├── mtk.rs mtk_da.rs      #   MediaTek BROM/DA flashing
│   ├── mtk_exploit.rs        #   BROM açıkları (bypass/kamakiri2/crash-to-BROM)
│   ├── mtk_sla.rs            #   MediaTek SLA anahtar işleme
│   ├── qualcomm/             #   Sahara + Firehose + GPT (EDL)
│   ├── spd.rs                #   Spreadtrum/UNISOC BSL protokolü (+ PAC)
│   ├── pac.rs                #   SPD PAC extract/pack
│   ├── pit.rs                #   Samsung PIT ayrıştırıcı
│   ├── mtp.rs at.rs adb.rs   #   MTP, AT komutu, ADB arayüzü
│   ├── fastboot.rs           #   yerel fastboot taşıyıcı
│   ├── moto_flash.rs         #   Motorola aşamalı fastboot FRP
│   ├── apple.rs              #   Apple usbmuxd/lockdown
│   ├── hid.rs bulk.rs        #   HID + bulk yardımcıları
│   ├── fwtar.rs sparse.rs    #   firmware tar + sparse işleme
│   ├── imgtools.rs           #   boot/vbmeta ameliyatı
│   ├── hostinfo.rs           #   host eMMC/UFS sağlığı
│   ├── sam_*.rs              #   Samsung yardımcıları (hatalar/kurulum)
│   └── config.rs error.rs util.rs
├── main.py                   # uygulama girişi (venv-safe launcher → python.gui.qt_app)
├── python/
│   ├── core/
│   │   ├── core.py           #   ince şemsiye: Rust FLOWS/JOBS/MODES'i bridge.flow_list() ile aynalar
│   │   ├── frp.py            #   FRP-only re-export yüzeyi (ad = sorumluluk)
│   │   ├── devices.py        #   çoklu cihaz kimliği: kararlı anahtarlar, listeleme, çözümleme, taşıma eşlemesi
│   │   ├── bridge.py         #   Rust ikili dosyasıyla konuşur (+ anahtar bazlı iptal)
│   │   ├── flow.py           #   Flow/Step yapıları + iptal
│   │   ├── jobs.py           #   FlashJob yaşam döngüsü (izole iş katmanı)
│   │   ├── cancel.py         #   işbirlikçi iptal kaydı
│   │   ├── mtk.py            #   MTK PIDs/stages/chips (0003=BROM, 2000=preloader)
│   │   ├── mtp.py            #   Samsung MTP/AT (çoklu sıra ADB etkinleştirme)
│   │   ├── pit.py pitstore.py  # Samsung PIT ayrıştırıcısı + önbellek
│   │   ├── adb.py            #   ADB yardımcıları
│   │   ├── device_info.py    #   canlı cihaz kimliği
│   │   ├── actions.py        #   eylem yardımcıları
│   │   ├── experimental.py   #   çalışma bazlı onay kapıları + denetim günlüğü
│   │   ├── fus.py            #   Samsung FUS yardımcıları
│   │   └── (no flows/ dir)   #   akışlar src/flows.rs içinde yaşar; Python sadece devredir
│   └── gui/
│       ├── qt_app.py         #   PyQt6 stüdyo (~12k LOC)
│       ├── devices.py        #   marka→model→eylem detay sayfaları
│       ├── nav.py            #   navigasyon çubuğu + OEM çip çubuğu
│       ├── theme.py          #   tokenlar (vurgu vs focus_ring/sel_border) + QSS
│       ├── animations.py     #   Hareket (shake/rubber serialized, takılı durum yok)
│       ├── toast.py          #   toast bildirimleri
│       └── supported_devices.json  #   hangi modelin hangi eylemi aldığını gösteren araştırma tablosu
├── operations/               # işlem başına dokümanlar + araştırma (frp/mdm/flashing/…)
├── docs/                     # ekran görüntüleri (yenilenmiş) + logo
├── root/                     # udev kuralları + setup-usb.sh
├── scripts/                  # dump-connected.sh, validate_mtp_at.py
├── INDEX.md CHANGELOG.md     # mühendislik dizini + sürüm günlüğü
└── tests/                    # pytest takımı (flow, MTK, PIT, odin safety, devices…)
```

---

## 🧑‍💻 Katkıda bulunma

**Bu proje sadece sizinle daha iyi olur.** Bakımcılar, protokol hacker'ları, GUI tasarımcıları, dokümantasyon yazarları ve testçiler istiyoruz.

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — başlamak için ihtiyacınız olan her şey.
- **[`good first issue`](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) etiketiyle başlayın** — seçilmiş, yeni başlayan dostu görevler.
- **[hata raporu](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml)** / **[özellik isteği](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=enhancement&template=feature_request.yml)** şablonlarını kullanın.
- **Yeni başlayan dostu görevler** — `src/flows.rs` içindeki her akış satırı bir fırsat: `flow!(...)` satırı ekleyin, komut dizisini ayarlayın, yeni bir cihaz kombinasyonu bağlayın. Python bunu `bridge.flow_list()` üzerinden otomatik keşfeder.
- **Önce flashing deneyimi gerekmez.** Akış çerçevesi (`src/flows.rs`) çok basittir — yeni bir yöntem tek satırdır:

```rust
flow!("my_method", "My method", "Read Device Info", "ADB"),
```

Görüntüde otomatik görünür. Bu katkı döngüsü tamamen budur: **bir akış satırı yaz, özelliği yayınla.**
- **Çoklu cihaz kuralı** — asla "cihaz"ı kapmayın; `key=None` (ortam kapsamı) kabul edin ve buna göre filtreleyin. Bakın `python/core/devices.py` ve `CONTRIBUTING.md`.
- **İsimlendirme kuralları** — işler fiil-önce (`FRP bypass` değil `Remove FRP`); akış anahtarları kısa snake_case (FLOWS içinde `flow_` öneki yok); MTK PID'ler `0003`=BROM / `2000`=preloader (mtkclient kuralı — bunları değiştirmeyin).

**Yardımcı olacağımız fikirler:**
- Akış tablolarında yeni cihaz modelleri / firmware kombinasyonları.
- MediaTek DA varyasyonları, yeni scatter/GPT tuhaflıkları.
- Qualcomm rawprogram & patch XML uç durumları.
- Ek FRP / kilit kaldırma yöntemleri per Android sürümü.
- Paketleme (Flatpak, AppImage, AUR, `cargo` + `pip`), CI, birim testleri.
- Daha fazla ODIN protokolü, eMMC/UFS araçları, iCloud benzeri ve EDL yardımcıları.
- Çeviriler, temalar ve erişilebilirlik.

---

## 🛡️ Güvenlik & yasal durum

Bu araç doğrudan bootloader'lara erişir ve yanlış kullanılırsa verileri silebilir ya da cihazı brick edebilir.

- Bunu yalnızca **kendi sahip olduğunuz ya da servis etmeye yetkin olduğunuz cihazlarda** kullanın (müşteri telefonlarını izniyle servis eden tamir atölyeleri).
- Her zaman ekranda görünen uyarıları okuyun ve flashing öncesinde **bölümleri yedekleyin**.
- FRP/MDM'yi size ait olmayan bir cihazda bypass etmek, yargı bölgenize göre **yasadışı olabilir** — bu yazılımı nasıl kullandığınızdan siz sorumlusunuz.
- FlashPilot, gereken protokol yüklerini paketler (MTK DA/BROM yükleri, Qualcomm firehose programcıları, Unisoc FDL1/FDL2, Samsung bootloader'ları), tıpkı ticari flashing suite'leri gibi. Belirli bir telefon için firmware görselleri hala kullanıcıdan veya satıcıdan gelir.

---

## 📄 Lisans

MIT — bkz. [LICENSE](LICENSE). Odin protokol sabitleri Heimdall projesinden türetilmiştir (MIT), ve SPD BSL referansı temiz oda protokol yazılarından gelir (spd_cmd.h / Opus-Spreadtrum docs).

---

**Repo'yu yıldızlayın ⭐, bir issue açın, PR gönderin — ve Linux üzerinde en iyi açık flashing suite'ini birlikte inşa edelim.**
