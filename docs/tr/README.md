# 🔧 FlashPilot

Language switcher: [English](../README.md) · [Français](../fr/README.md) · [Español](../es/README.md) · [Deutsch](../de/README.md) · [简体中文](../zh/README.md) · [Русский](../ru/README.md) · [Português](../pt/README.md) · [日本語](../ja/README.md) · [العربية](../ar/README.md) · [हिन्दी](../hi/README.md) · **Türkçe**

> English kanonik kaynaktır. Bu sayfa bir çeviridir; katkı memnuniyetle karşılanır — bkz. [`../TRANSLATION.md`](../TRANSLATION.md).

> **Linux için açık kaynaklı bir Samsung firmware flashlama & onarım tezgahı — Galaxy telefonları (Download/Odin modu), MediaTek (BROM/DA), Qualcomm (EDL) ve Spreadtrum/UNISOC cihazlarını flashlamak için bir Odin / Heimdall alternatifi.**

**Arama anahtar kelimeleri:** Samsung flashing tool · Odin alternative · Android firmware flashing Linux · Heimdall GUI · Galaxy phone repair · MTK BROM flash · Qualcomm EDL · FRP unlock · UNISOC flashing · device firmware tool · mobile repair · Android bootloader · USB flashing · Linux flashing suite · proprietary tool alternative

[![Rust](https://img.shields.io/badge/Rust-1.70+-orange?logo=rust&logoColor=white)](https://www.rust-lang.org)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52)](https://www.riverbankcomputing.com/software/pyqt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![CI](https://github.com/Legendary-Brilliantforous/flashpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Legendary-Brilliantforous/flashpilot/actions)
[![Good First Issues](https://img.shields.io/github/issues/Legendary-Brilliantforous/flashpilot/good%20first%20issue)](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
[![Contributors](https://img.shields.io/github/contributors/Legendary-Brilliantforous/flashpilot)](https://github.com/Legendary-Brilliantforous/flashpilot/graphs/contributors)

**Bu nedir?** Ücretli Windows flashlama paketlerinin Linux'ta çalışan yerli karşılığı — **Samsung, MediaTek, Qualcomm ve Spreadtrum/UNISOC cihazlarının** bootloader'ıyla doğrudan konuşan tek bir birleşik araç. Tersine mühendislikle elde edilmiş protokoller + yerli Rust performansı + güzel bir PyQt6 GUI = Odin, Heimdall ve pahalı ticari araçların açık kaynak alternatifi.

---

## ✨ Bu proje neden önemli

Android onarım dünyası kapalı, yalnızca Windows'ta çalışan ticari araçlarla işliyor. Protokolleri küçük bir meraklı topluluğu tersine mühendislikle çözüyor — ve bu bilginin çoğu ücretli paketlerin içinde kilitli ya da forumlarda eksik halde.

**Projenin yanıtı bu.** Tersine mühendislikle elde edilen protokolleri, herkesin okuyabileceği, çalıştırabileceği, genişletebileceği ve kendi flashlama paketi olarak yayımlayabileceği temiz, denetlenebilir, MIT lisanslı bir kod tabanına dönüştürür.

| Ticari araç | Yalnızca Windows, kapalı kaynak | Bu proje |
|---|---|---|
| Odin / Smart Switch | Windows, yalnızca GUI | Açık kaynak Odin protokolü (Rust, yerli) + PIT araçları |
| MTK flash araçları | Windows, kapalı DA | MTK BROM/DA flashlama & yedekleme (scatter + GPT) |
| Qualcomm EDL araçları | Windows | Sahara + Firehose protokol uygulaması |
| SPD/UNISOC araçları | Windows | Baştan yazılmış BSL indirme (clean-room) uygulaması |
| FRP / kilit araçları | Ücretli, gri pazar | Şeffaf ADB + download-mode akışları, MDM kilit açma |

---

## 🚀 Öne çıkanlar — 1.2.1 Stabil (0 uyarı)

- **9 taşıma modu** — ADB, MTP, Samsung Download mode, Samsung BROM, MTK, MTK BROM, Fastboot, Qualcomm EDL, SPD.
- **13 iş kategorisi** — Flash Firmware, Remove FRP, Remove Screen Lock, Remove MDM, Unlock Carrier, Read Device Info, Detect Devices, Reboot, Repair Settings, ayrıca çip başına DENEYSEL: Knox / Garanti (Samsung), QCN / Modem (Qualcomm), IMEI Repair / Change (MTK/SPD/Qualcomm), eMMC / UFS.
- **Çoklu cihaz** — birkaç telefon bağlayın: bağlantı çubuğu her birini listeler, her işlem hangi telefona uygulanacağını sorar (yalnızca biri eşleşirse sessizce çalışır) ve farklı telefonlar işlemleri paralel çalıştırabilir (cihaz başına bir işlem, STOP tümüne yayın).
- **Rust çekirdeği (`flashpilot-bridge`, ~9.3k LOC) — 0 `cargo check` uyarısı** — *vendored libusb* ile ham USB (sistem bağımlılığı yok), gerçek protokol uygulamaları (+ 18 kablo bağlı ölü yol, -80KB ltcg kırpma).
  - **Samsung** : tersine mühendislikle elde edilmiş Odin oturum protokolü (Heimdall tabanlı), HID download-mode payload'ları, PIT okuma/yazma/flash — AT `Context` korunur, `EndpointConfig` parçalama.
  - **MediaTek** : BROM / preloader / DA el sıkışması, scatter & GPT, BROM exploit'leri, SLA anahtarları — `ProgressReporter` gerçek %.
  - **Qualcomm** : `ProtocolError` Sahara + Firehose `QcomDeviceInfo`, `Duration` zaman aşımlarıyla bağlanmış.
  - **SPD/UNISOC** : temiz oda (clean-room) BSL — tüm `BSL_CMD/REP`, `iface`, `flush/read_flash/chip_uid/power_off` bağlanmış.
  - Ayrıca **MTP**, **AT-komutu** ve tam **ADB** altyapısı.
- **Stüdyo kalitesinde GUI** — çerçevesiz yarı saydam pencere, 10 aksan teması, animasyonlu kablo/durum sahnesi, canlı konsol.
  - **Marka simgeleri & ayrı düğme arka planları** — net marka simgeleri (Samsung Ⓢ, Apple kırmızı elma 🍎, Motorola Ⓜ, LG Ⓛ, vb.) ve üst çip çubuğundaki her OEM düğmesinde uyarlanmış marka arka plan renkleri.
  - **Motorola & Apple için yatay görünümler** — model işlem panoları varsayılan olarak temiz yatay sekmeli düzenler.
  - **Mikro etkileşimler & cam morfizm** — akıcı 160 ms sayfa geçişi solmaları, tek aralıklı meta veri rozet tipografisi (`Consolas`, `Monaco`) ve geliştirilmiş cam morfik kart kenarlıkları.
  - **Büyük ortalanmış diyaloglar (620 px, sürüklenebilir, ✕)** — beta kapısı + stabil `UPDATE/AHEAD/PATCH` + flash/FRP onayları, çip renkleri `MTK amber` `QCOM red` `SPD violet` `SAMSUNG blue`, yüksek kontrastlı metin.
  - **Çip başına DENEYSEL açılır bölümler** — Knox (Samsung), QCN/IMEI (Qualcomm), IMEI (MTK/SPD): amber banner, her çalıştırmada sahiplik onay kutusu, IMEI değişikliği için `I UNDERSTAND` yazarak onay, denetim günlüğü.
  - **⏹ STOP** başlık çubuğunda tüm çalışan işlemleri durdurur; cihaz başına kilitler diğer telefonların çalışmaya devam etmesini sağlar.

---

## 📸 Ekran görüntüleri

| Samsung işlemleri | MediaTek tezgahı | Pil onarımı | SPD indirme |
|---|---|---|---|
| ![Samsung](docs/samsung.png) | ![MediaTek](docs/mtk.png) | ![Pil](docs/battery.png) | ![SPD](docs/spd.png) |

---

## 🧩 Özellik matrisi

| Yetenek | Samsung | MediaTek | Qualcomm | SPD/UNISOC | Herhangi ADB |
|---|---|---|---|---|---|
| Algıla / bilgi | ✅ | ✅ (+ crash preloader→BROM) | ✅ (Sahara) | ✅ | ✅ |
| Firmware flashla | ✅ (Odin, yerli Rust) | ✅ (scatter + GPT) | ✅ (Firehose) | ✅ (FDL/bölgeler) | — |
| Partition yedekle | ✅ (EFS) | ✅ | ✅ | ✅ | — |
| FRP bypass | ✅ (ADB + download) | ✅ | ✅ (EDL) | ✅ | ✅ |
| Ekran kilidi kaldırma | ✅ | ✅ | ✅ (EDL) | — | ✅ |
| MDM kilit açma | ✅ (ADB, QR, recovery) | — | — | — | — |
| Knox garanti/bypass (DENEYSEL) | ✅ | — | — | — | — |
| QCN yedek/geri yükleme + IMEI onarımı/değişimi (DENEYSEL) | — | ✅ (NVRAM) | ✅ (NV 550/682) | ✅ (BSL NV) | — |
| Partition araçları | ✅ (PIT) | ✅ (GPT) | ✅ | ✅ (PAC çıkart/paketle) | — |
| Düşük seviye exploit'ler | ✅ (HID/BROM) | ✅ (BROM exploit, SLA) | ✅ (Sahara) | ✅ (BSL) | — |
| Pil / ağ onarımı | — | — | — | — | ✅ |

> 💡 **Pil** ve **Ağ** bölümleri USB hata ayıklama etkin herhangi bir Android cihazda çalışır — satıcı donanımı gerekmez.

---

## 🖥️ GUI

Çerçevesiz, yarı saydam, köşeli kart penceresi; üstte canlı **bağlantı bandı** (bilgisayar → kablo → telefon sahnesi, animasyonlu veri darbesi), solda **nav rail** ve sağda **konsol/log bölmesi**.

- **Bağlantı çubuğu** — canlı cihaz listesi (telefon başına bir satır: model · seri · taşıma yolları); incelemek için satıra tıklayın. Çeşitli cihaz eşleştiğinde işlem düğmeleri hangi telefonu sorar.
- **Samsung** — Samsung hub alt sekmeleri: `ODIN FLASH · UNLOCK · ADVANCED FLASH · INFO & TOOLS`, ayrıca firmware yuvaları (AP/BL/CP/CSC/USERDATA), Odin araçları ve `KNOX — EXPERIMENTAL` açılır bölümü.
- **MediaTek / Qualcomm / SPD** — yerli düşük seviye araçlarla özel tezgahlar (scatter/DA + crash-to-BROM, programmer/XML + QCN/IMEI, FDL ikilileri + base adresler + IMEI), her biri kendi `— EXPERIMENTAL` açılır bölümüyle.
- **Pil** — pil göstergesi sağlık %, sıcaklık/gerilim/akım, en çok tüketenler; tek tıkla onarım.
- **Ağ** — SIM durumu, veri/Wi-Fi bayrakları, DNS modu; radyo sıfırlama ve yeniden kayıt.
- **Ayarlar** — otomatik tarama aralığı, varsayılan yollar, konsol otomatik temizleme, 10 aksan teması, animasyonlar (shake/rubber/cable/bubble geçişleri), pencere parıltısı, motor durumu ve uygulama içi `cargo build`.

**Kısayollar:** `F5` yeniden tara · `Ctrl+Enter` çalıştır · `Ctrl+L` konsolu temizle · `Ctrl+S` günlüğü kaydet · `Ctrl+F` bul.

---

## 📦 Hızlı başlangıç

**Gereksinimler:** Rust toolchain, Python 3.10+, bir Linux masaüstü. Hepsi bu — libusb vendored gelir.

```bash
# 1. Rust köprüsünü derle (ilk derleme libusb'i kaynaktan derler)
cargo build --release

# 2. (Önerilen) Telefonların sudo istememesi için USB udev kurallarını kur
sudo bash root/setup-usb.sh

# 3. Python ortamı
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Başlat
.venv/bin/python -m python.main        # veya: python3 main.py
```

Samsung download-mode flashlama yerlidir (Rust Odin protokolü) — tescilli odin4 ikilisi getirilmez, dağıtılmaz ya da gerekli değildir. Samsung combo firmware Samsung'ın resmi destek sayfalarından veya güvenilir firmware arşivlerinden edinilmelidir.

---

## 🖥️ Platform desteği — sözünüzü isteriz

**Linux desteklenen platformdur.** FlashPilot, bilinçli olarak *Windows'a özgü flashlama paketlerinin Linux yerli cevabıdır* — geliştirme, test ve sürümler Linux'u hedefler ve bu değişmeyecek.

**Windows / macOS bugün desteklenmiyor**, pratik nedenlerle:

- Windows USB'si telefon modu başına sürücü cehennemidir (Zadig/WinUSB, QDLoader, Samsung sürücüleri birbirine girer); çoğu "telefon algılanmıyor" raporu uzaktan hata ayıklanamaz olurdu.
- macOS, sıfıra yakın onarım atölyesi talebi için imzalama/noter onayı ek yükü ekler.
- Yığın taşınabildir (Rust + rusb, Python, Qt), bu yüzden bu bir bakım kararıdır, teknik bir imkânsızlık değil.

**Ancak bu bir hükmen karar değil, açık bir soru.** Windows/macOS desteği istiyorsanız — veya sonsuza kadar yalnızca Linux'u savunmak istiyorsanız — bize söyleyin:

- 💬 Kullanım durumunuzla bir **[tartışma](https://github.com/Legendary-Brilliantforous/flashpilot/discussions)** açın (onarım atölyesi? lab? hangi OS? hangi telefonlar?).
- 🔧 Kod en iyi söz: plan `python/core/platform.py` soyutlamasıdır (`open_file_manager()`, `detach_kernel_drivers()`, `usb_device_path()`, `needs_udev_setup()`) Linux tek backend olacak şekilde, böylece portlar fork yerine ek PR'ler haline gelir. Bu yönde PR'lar şu anda memnuniyetle karşılanır.
- 🎨 İlgili: katkıda bulunanlar PyQt6 (GPLv3) yerine **PySide6** (LGPL, bu MIT projesiyle lisans uyumlu) önerdi. Aynı tartışma üzerinden görüşünüzü belirtin — geçiş mekanik ancak önce GUI smoke-test kapsamı gerekiyor.

Karar, katkıda bulunan sesleri olmadan verilmeyecek. Gel ve onlardan biri ol.

### CLI / köprü

```bash
./target/release/flashpilot-bridge detect          # tüm USB + Samsung filtresi (JSON)
./target/release/flashpilot-bridge fastboot-devices  # fastboot arayüzü olan USB cihazlar (JSON)
./target/release/flashpilot-bridge fastboot-cmd 22b8:2e80@2:16 20000 getvar securestate  # tek bir ham fastboot komutu
./target/release/flashpilot-bridge mtk-detect      # MediaTek BROM (0e8d:0003) / preloader (0e8d:2000) / DA
./target/release/flashpilot-bridge mtk-crash-brom <bus:addr>  # preloader'ı held BROM'a çökert
./target/release/flashpilot-bridge qcom-detect     # Qualcomm EDL
./target/release/flashpilot-bridge spd-detect      # Spreadtrum/UNISOC (VID 0x1782)
./target/release/flashpilot-bridge odin-pit 04e8:xxxx@bus:addr  # PIT oku
./target/release/flashpilot-bridge at-send <t> ATI # CDC ACM üzerinden AT
./target/release/flashpilot-bridge adb-devices     # adb devices -l JSON olarak
```

---

## 📁 Depo düzeni

```
flashpilot/
├── src/                      # Rust köprü (~13k LOC) — TÜM akışlar burada
│   ├── main.rs               #   komut satırı giriş (80+ komut) + flow-run dağıtım
│   ├── flows.rs              #   KAYIT: FLOWS / JOBS / MODES (flow! macro, ~280 satır)
│   ├── usb/                  #   USB numaralandırma / arayüzler / filtreleme (mod.rs + filtering.rs)
│   ├── devices.rs            #   birleştirilmiş USB+ADB cihaz satırları
│   ├── sam_download.rs       #   Samsung Download/Odin protokolü (odin-* komutları)
│   ├── mtk.rs mtk_da.rs      #   MediaTek BROM/DA flashlama
│   ├── mtk_exploit.rs        #   BROM exploit'leri (bypass/kamakiri2/crash-to-BROM)
│   ├── mtk_sla.rs            #   MediaTek SLA anahtar işleme
│   ├── qualcomm/             #   Sahara + Firehose + GPT (EDL)
│   ├── spd.rs                #   Spreadtrum/UNISOC BSL protokolü (+ PAC)
│   ├── pac.rs                #   SPD PAC çıkart/paketle
│   ├── pit.rs                #   Samsung PIT ayrıştırıcı
│   ├── mtp.rs at.rs adb.rs   #   MTP, AT komutu, ADB altyapısı
│   ├── fastboot.rs           #   yerli fastboot taşıması
│   ├── moto_flash.rs         #   Motorola aşamalı fastboot FRP
│   ├── apple.rs              #   Apple usbmuxd/lockdown
│   ├── hid.rs bulk.rs        #   HID + bulk yardımcılar
│   ├── fwtar.rs sparse.rs    #   firmware tar + seyrek (sparse) işleme
│   ├── imgtools.rs           #   boot/vbmeta cerrahisi
│   ├── hostinfo.rs           #   host eMMC/UFS sağlığı
│   ├── sam_*.rs              #   Samsung yardımcıları (hatalar/kurulum)
│   └── config.rs error.rs util.rs
├── main.py                   # uygulama giriş (venv-güvenli başlatıcı → python.gui.qt_app)
├── python/
│   ├── core/
│   │   ├── core.py           #   ince shim: bridge.flow_list() üzerinden Rust FLOWS/JOBS/MODES aynası
│   │   ├── frp.py            #   yalnızca FRP yeniden dışa aktarım yüzeyi (ad == sorumluluk)
│   │   ├── devices.py        #   çoklu cihaz kimliği: stabil anahtarlar, liste, çözümleme, taşıma eşlemesi
│   │   ├── bridge.py         #   Rust ikilisi ile konuşur (+ anahtar başına iptal)
│   │   ├── flow.py           #   Flow/Step temelleri + iptal
│   │   ├── jobs.py           #   FlashJob yaşam döngüsü (izole job katmanı)
│   │   ├── cancel.py         #   işbirlikçi iptal kaydı
│   │   ├── mtk.py            #   MTK PID'leri/aşamaları/chipleri (0003=BROM, 2000=preloader)
│   │   ├── mtp.py            #   Samsung MTP/AT (çok sıralı ADB etkinleştirme)
│   │   ├── pit.py pitstore.py  # Samsung PIT ayrıştırıcı + önbellek
│   │   ├── adb.py            #   ADB yardımcıları
│   │   ├── device_info.py    #   canlı cihaz kimliği
│   │   ├── actions.py        #   işlem yardımcıları
│   │   ├── experimental.py   #   çalıştırma başına ack geçitleri + denetim günlüğü
│   │   ├── fus.py            #   Samsung FUS yardımcıları
│   │   └── (no flows/ dir)   #   akışlar src/flows.rs'de yaşar; Python yalnızca devrededer
│   └── gui/
│       ├── qt_app.py         #   PyQt6 stüdyosu (~12k LOC)
│       ├── devices.py        #   marka→model→işlem detaylandırma sayfaları
│       ├── nav.py            #   nav rail + OEM çip çubuğu
│       ├── theme.py          #   tokenlar (accent vs focus_ring/sel_border) + QSS
│       ├── animations.py     #   Motion (shake/rubber serileştirilmiş, takılı durum yok)
│       ├── toast.py          #   toast bildirimleri
│       └── supported_devices.json  #   marka/model/chip araştırma tablosu
├── operations/               # işlem başına dokümanlar + araştırma (frp/mdm/flashing/…)
├── docs/                     # ekran görüntüleri (güncel) + logo
├── root/                     # udev kuralları + setup-usb.sh
├── scripts/                  # dump-connected.sh, validate_mtp_at.py
├── INDEX.md CHANGELOG.md     # mühendislik indeksi + sürüm değişiklik günlüğü
└── tests/                    # pytest paketi (flow, MTK, PIT, odin safety, cihazlar…)
```

---

## 🧑‍💻 Katkı

**Proje sizinle birlikte gelişir.** Sürdürücüler, protokol hacker'ları, GUI tasarımcıları, doküman yazarları ve testçiler istiyoruz.

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — başlamak için gereken her şey.
- **[`good first issue`](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) etiketinden başlayın** — seçilmiş, yeni başlayan dostu görevler.
- **[hata bildirimi](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml)** / **[özellik isteği](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=enhancement&template=feature_request.yml)** şablonlarını kullanın.
- **Yeni başlayan dostu görevler** — `src/flows.rs` içindeki her akış satırı bir fırsattır: bir `flow!(...)` satırı ekleyin, bir komut dizisini ayarlayın, yeni bir cihaz kombinasyonu bağlayın. Python `bridge.flow_list()` üzerinden otomatik keşfeder.
- **Önceden flashlama deneyimi gerekmez.** Akış çerçevesi (`src/flows.rs`) son derece basittir — yeni bir yöntem tek satır:

```rust
flow!("my_method", "My method", "Read Device Info", "ADB"),
```

GUI'da otomatik olarak görünür. Tüm katkı döngüsü bu: **bir akış satırı yaz, bir özellik gönder.**
- **Multi-cihaz kuralı** — asla "o" cihazı kapmayın; `key=None` (ortam kapsamı) kabul edin ve buna göre filtreleyin. Bkz. `python/core/devices.py` ve `CONTRIBUTING.md`.
- **Adlandırma kuralları** — işler fiil-önce (`Remove FRP`, `FRP bypass` değil); akış anahtarları kısa snake_case (FLOWS'da `flow_` öneki yok); MTK PID'leri `0003`=BROM / `2000`=preloader (mtkclient geleneği — bunları takas etmeyin).

**Yardım almak isterdik:**
- Akış tablolarında yeni cihaz modelleri / firmware kombinasyonları.
- MediaTek DA varyantları, yeni scatter/GPT tuhaflıkları.
- Qualcomm rawprogram & patch XML uç durumları.
- Android sürümü başına ek FRP / kilit-kaldırma yöntemleri.
- Paketleme (Flatpak, AppImage, AUR, `cargo` + `pip`), CI, birim testleri.
- Daha fazla ODIN protokolü, eMMC/UFS araçları, iCloud'a bitişik ve EDL yardımcıları.
- Çeviriler, temalar ve erişilebilirlik.

---

## 🛡️ Güvenlik & yasallık

Bu araç bootloader'larla doğrudan konuşur ve yanlış kullanılırsa veriyi silebilir ya da cihazı brickleyebilir.

- Yalnızca **sahip olduğunuz veya servis etme yetkiniz olan cihazlarda** kullanın (izne sahip müşteri telefonlarını servis eden onarım atölyeleri).
- On-screen uyarıları her zaman okuyun ve flashlamadan önce **partition'ları yedekleyin**.
- Size ait olmayan bir cihazda FRP/MDM aşmak yargı yetkinizde **yasa dışı** olabilir — bu yazılımı nasıl kullandığınız sizin sorumluluğunuzdur.
- FlashPilot, ticari flashlama paketlerinin yaptığı gibi işlemlerin ihtiyaç duyduğu protokol payload'larını (MTK DA/BROM payload'ları, Qualcomm firehose programmer'ları, Unisoc FDL1/FDL2, Samsung bootloader'ları) paketler. Belirli bir telefona ait firmware görüntüleri hâlâ kullanıcıdan veya satıcıdan gelir.

---

## 📄 Lisans

MIT — bkz. [LICENSE](LICENSE). Odin protokol sabitleri Heimdall projesinden (MIT) türetilmiştir; SPD BSL referansı temiz oda protokol yazımından (spd_cmd.h / Opus-Spreadtrum docs) gelir.

---

**Bu repoyu yıldızlayın ⭐, issue açın, PR gönderin — ve Linux'un en iyi açık flashlama paketini birlikte kuralım.**