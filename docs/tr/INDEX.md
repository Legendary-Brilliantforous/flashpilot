# FlashPilot — index

Language switcher: [English](../INDEX.md) · [Français](../fr/INDEX.md) · [Español](../es/INDEX.md) · [Deutsch](../de/INDEX.md) · [简体中文](../zh/INDEX.md) · [Русский](../ru/INDEX.md) · [Português](../pt/INDEX.md) · [日本語](../ja/INDEX.md) · [العربية](../ar/INDEX.md) · [हिन्दी](../hi/INDEX.md) · **Türkçe**

> English kanonik kaynaktır. Bu sayfa bir çeviridir; katkı memnuniyetle karşılanır — bkz. [`../TRANSLATION.md`](../TRANSLATION.md).

README pazarlama içeriğidir. Bu dosya mühendislik indeksidir — her klasör, ne işe yaradığı ve nereden başlayacağınız.

## Çalıştırma

```bash
# GUI
python main.py

# CLI (köprü) — aynı protokol, GUI yok
./target/release/flashpilot-bridge detect-all
./target/release/flashpilot-bridge spd-detect
```

## Kök düzen (17 giriş)

| Giriş | Ne | Ne zaman açarsınız |
|---|---|---|
| `main.py` | Uygulama giriş noktası. Depoyu `sys.path`'e ekler ve `python.gui.qt_app.main()` çağrır. | Uygulamanın nasıl başladığını değiştirmek için. |
| `pyproject.toml` | Python paket meta verisi (name=flashpilot, deps, build backend). | Bir Python bağımlılığı eklemek veya sürümlü yükseltmek için. |
| `Cargo.toml` / `Cargo.lock` | Rust çekirdeği (bina `flashpilot-bridge`). | Köprü CLI'sını değiştirmek veya yeni bir protokol eklemek için. |
| `python/` | Rust motorunun üstünde ince Python katmanı: `python/core/` (shim + GUI yardımcıları) ve `python/gui/` (PyQt6). Tüm akışlar `src/flows.rs`'de yaşar. | GUI ve cihaz altyapısı. |
| `src/` | Rust kaynakları. `python/core/` ile yansılı düzen. | Yeni bir köprü komutu eklediğinizde veya USB protokolünü değiştirdiğinizde. |
| `tests/` | pytest paketi. ~149 test, ~1s sürüyor. | `.venv/bin/python -m pytest tests/ -q` ile çalıştırın. |
| `scripts/` | Bağımsız shell araçları. Bugün: `dump-connected.sh`, `validate_mtp_at.py`. | GUI olmayan toplu bir işlem gerektiğinde. |
| `docs/` | README varlıkları (ekran görüntüleri, logo). | README için. |
| `packaging/` | `.deb` derleme betiği + kontrol dosyaları. | Bir sürüm yayınlamak için. |
| `root/` | udev kuralları (telefonların sudo olmadan çalışması için). | Tek seferlik kurulum. |
| `operations/` | **İş başına doküman ağaçları** — aşağıdaki "operations/" bölümüne bakın. | Belirli bir işi anlamak istiyorsanız (FRP, MDM, ekran kilidi vb.). |
| `build/` | **Tüm gitignored derleme/çalışma zamanı yapıtları** — aşağıdaki "build/" bölümüne bakın. | Hemen hiç açmazsınız. |
| `.github/` | CI iş akışları, issue şablonları. | CI'yi değiştirmek için. |
| `LICENSE` `CODE_OF_CONDUCT.md` `CONTRIBUTING.md` `SECURITY.md` `DESCRIPTION.md` | Standart proje meta verisi. | Sürüm çıkarırken. |

## `python/` düzeni

```
python/
├── main.py                 <- uygulama giriş (depoysu sys.path'a ekler, python.gui.qt_app.main çağırır)
├── gui/                    <- PyQt6 uygulaması
│   ├── qt_app.py           <- Ana pencere + tüm cihaz-modu UI (~12k LOC)
│   ├── devices.py          <- Veri güdümlü "desteklenen cihazlar" detaylandırma (marka -> model -> işlem)
│   ├── theme.py            <- Tasarım tokenları (renkler, düğme stilleri, sürüm yardımcıları)
│   ├── animations.py       <- Boyanmış glyph'ler: bağlantı sahnesi, durum orbi vb.
│   ├── nav.py              <- Üst düzey navigasyon rail'i + OEM çip çubuğu
│   ├── toast.py            <- Toast bildirimleri
│   └── supported_devices.json  <- Hangi modelin hangi işlemi aldığı veritabanı
└── core/                   <- İnce Python katmanı (Qt bağımlılığı yok; Rust köprüsüne devrededer)
    ├── core.py             <- FLOWS/JOBS/MODES aynası (kodlanmış önbellek + Rust flow_list())
    ├── bridge.py           <- Rust `flashpilot-bridge` ikilisi ile konuşur
    ├── flow.py             <- Flow/Step temelleri + iptal
    ├── jobs.py             <- FlashJob yaşam döngüsü (izole job katmanı)
    ├── cancel.py           <- İşbirlikçi iptal kaydı
    ├── devices.py          <- Çoklu cihaz kimliği (stabil anahtarlar, liste, çözümleme, taşıma eşlemesi)
    ├── frp.py              <- Yalnızca FRP yeniden dışa aktarım yüzeyi (ad == sorumluluk)
    ├── mtk.py              <- MTK PID'leri/aşamaları/chipleri (0003=BROM, 2000=preloader)
    ├── mtp.py              <- Samsung MTP/AT (çok sıralı ADB etkinleştirme)
    ├── pit.py pitstore.py  <- Samsung PIT ayrıştırıcı + önbellek
    ├── adb.py device_info.py actions.py experimental.py fus.py
    └── (no flows/ dir)     <- akışlar src/flows.rs'te yaşar; Python yalnızca bridge.flow_run() üzerinden devrededer
```

**Akışlar Rust'ta yaşar.** `python/core/core.py` ince bir shim'dir: `_RustFlow` yürütmeyi `bridge flow-run <key>` komutuna devrededer. Kanonik kayıt `src/flows.rs`'dir (`flow!` makrosu, ~280 satır); Python bunu GUI araması için yansır.

## `src/` düzeni (Rust)

```
src/
├── main.rs                 <- Tüm CLI dağıtımı (eprintln! "log" kanalıdır) + flow-run
├── flows.rs                <- AKIŞ kaydı (flow! macro; FLOWS/JOBS/MODES)
├── usb/                    <- libusb bağlamı, tanımlayıcı ayrıştırma, filtreleme (mod.rs + filtering.rs)
├── devices.rs              <- birleştirilmiş USB+ADB cihaz satırları
├── sam_download.rs         <- Samsung Download/Odin oturumu (odin-* komutları)
├── sam_errors.rs sam_setup.rs sam_*.rs  <- Samsung yardımcıları
├── mtk.rs mtk_da.rs        <- MediaTek BROM/DA flashlama
├── mtk_exploit.rs          <- BROM exploit'leri (bypass/kamakiri2/crash-to-BROM)
├── mtk_sla.rs mtk_sla_keys.rs <- Secure Lock Authentication
├── mtk_daloader.rs         <- DA kap ayrıştırma
├── qualcomm/               <- EDL: Sahara + Firehose + GPT
├── spd.rs                  <- UNISOC BSL (BSL_CMD_*, BSL_REP_*, FDL1/FDL2)
├── pac.rs                  <- SPD PAC çıkart/paketle
├── pit.rs                  <- Samsung PIT ayrıştırıcı
├── mtp.rs at.rs adb.rs     <- MTP, AT komutu, ADB altyapısı
├── fastboot.rs             <- yerli fastboot taşıması
├── moto_flash.rs           <- Aşamalı fastboot FRP Motorola
├── apple.rs                <- Apple usbmuxd/lockdown
├── bulk.rs hid.rs          <- bulk + HID yardımcılar
├── fwtar.rs sparse.rs imgtools.rs <- firmware tar/sparse/boot-vbmeta
├── hostinfo.rs             <- host eMMC/UFS sağlığı
├── config.rs error.rs util.rs device.rs
└── (no odin.rs)            <- Odin mantığı sam_download.rs içinde yaşar
```

## `operations/` — iş başına doküman ağaçları

Bu klasörler her **işin nasıl çalıştığını**, hangi akış anahtarlarını kullandığını, hangi cihazları desteklediğini ve bilinen uyarıları açıklayan **iş başına README ağaçları** içerir. Bunlar **kod değildir** — ağaç saf markdown'dır (bir önceki temizlik burada yaşamış eski `.py` shim'leri kaldırdı; hiçbir şey `operations/` import etmez). Kod `src/flows.rs` içinde yaşar (`flow!` kaydı; `python/core/core.py` ince bir shim'dir) ve alan başına modüller (`knox.py`, `qcn.py`, `imei.py`, `emmc.py`, …). `operations/` içindeki README'ler son kullanıcılar / ticari araç araştırmacıları için yazılmıştır; kod asıl kaynağın kendisidir.

| Klasör | Ne | Gerçek kod |
|---|---|---|
| `operations/apple/` | Apple icloud, activation lock, MDM, passcode/lost mode kaldırma | Rust akışları (`src/flows.rs`: `apple_*` satırları, `flow-run` CLI) |
| `operations/frp/` | Motor başına FRP aşma + cihaz başına araştırma notları. **`operations/frp/INDEX.md` ile başlayın**. | Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI); ince `python/core/core.py` shim |
| `operations/mdm/` | MDM / device-owner kilit açma + marka başına cihaz notları | Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI) |
| `operations/screen_unlock/` | Ekran kilidi kaldırma (ADB / recovery / download / tam) | Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI) |
| `operations/battery/` | Pil raporu / onarımı / yük testi (ADB üzerinden) | Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI) |
| `operations/network/` | SIM durumu, DNS, radyo sıfırlama | Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI) |
| `operations/carrier_unlock/` | Operatör kilidi (Apple, MTK) | Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI) |
| `operations/flashing/` | Satıcı başına flashlama rehberleri (Samsung Odin, MTK DA, Qualcomm EDL, UNISOC SPD, PIT) | Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI) |
| `operations/usb/` | USB numaralandırma ve algılama notları | `src/usb/`, `src/devices.rs`, `python/core/devices.py` |

## `build/` — gitignored çalışma/derleme yapıtları

| Alt klasör | İçerik | Oluşturan |
|---|---|---|
| `build/target/` | Rust `cargo build` çıktısı | `cargo build` |
| `build/dist/` | `.deb` paketleri | `packaging/build-deb.sh` |
| `build/cache/` | Cihaz başına TAR önbellekleri ve tersine mühendislik dökümleri | GUI / `scripts/dump-connected.sh` |
| `build/mdm_qr/` | Üretilen MDM sağlama QR kodları | GUI MDM akışı |
| `build/pit/` | Önbelleğe alınan `.pit` partition-tablo dosyaları | GUI PIT akışı |

**Kural:** Asla `build/` altından hiçbir şeyi `git add` yapmayın. Durumu silmek istiyorsanız alt klasörü silin — yeniden inşa edilir.

## Yeni özellik nasıl eklenir ("hangi dosyaya dokunacağım?" kılavuzu)

| Şunu istiyorsanız... | Dokunun |
|---|---|
| Desteklenen listeye yeni cihaz eklemek | `python/gui/supported_devices.json` |
| Desteklenen cihaza satıcı başına yeni işlem eklemek | `src/flows.rs` (bir `flow!(...)` satırı ekleyin); Python `bridge.flow_list()` üzerinden otomatik keşfeder |
| Mevcut bir konu için yeni ADB-komut akışı eklemek | Aynı (Rust `src/flows.rs`) |
| Yeni bir köprü CLI komutu eklemek | `src/<konu>.rs` + `src/main.rs` (match içinde `<cmd>` kolu) |
| Yeni üst düzey nav sayfası eklemek | `python/gui/qt_app.py` (`_build_*_page` + `_section_index`) |
| Yeni tasarım rengi / düğme stili eklemek | `python/gui/theme.py` (`C` sözlüğü / `_btn_*()`) |
| Yeni cihazın iş başına notlarını belgelemek | `operations/<iş>/<marka>/<model>.md` |
| Test eklemek | `tests/test_<alan>.py`, `test_mtk.py` motifini izleyin |

## İş koşucusu nasıl çalışır (bir kez okuyun)

GUI hiçbir zaman bir akışı doğrudan çağırmaz. İş başına cihaz seçicisi (`FlashPilotWindow._choose_device`) önce stabil bir cihaz anahtarı çözer; sonra `_run_ops_flow` / `_run_job_flow`, `python.core.core.flow_for(job, mode, method)` çağırır, bu bir `Flow()` nesnesi (bir `Step()` listesi) döndürür, ardından `flow.run(ctx, log)` worker thread içinde `devices.device_scope(key)` içinde çağrılır (böylece her çözümleyici seçilen telefona hedeflenir). Her akış, GUI'nin konsoluna bağladığı `log(line)` çağrılabilinine yazar. İptal cihaz başına kapsamlıdır (`flow.request_cancel(key)`; anahtarsız yayın her şeyi durdurur), her `_run`'ın başında denetlenir.

Bir akış eklemek için: `src/flows.rs` içine bir `flow!("my_op", "My op", "Job Name", "MODE")` satırı ekleyin. Python `bridge.flow_list()` üzerinden otomatik keşfeder ve GUI'nin job/mode/method detaylandırması onu otomatik olarak alır. Rust `flow-run` CLI onu çalıştırır; çözümleyiciler hedef serial'i / `vid:pid@bus:addr`'yi kabul etmelidir (bkz. `src/device.rs`).