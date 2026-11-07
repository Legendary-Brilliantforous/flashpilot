# FlashPilot — dizin

README pazarlama kısmı. Bu dosya mühendislik indeksidir — her klasör, ne yapar ve nereden başlanır.

## Çalıştır

```bash
# GUI
python main.py

# CLI (bridge) — aynı protokol, GUI yok
./target/release/flashpilot-bridge detect-all
./target/release/flashpilot-bridge spd-detect
```

## Kök düzeni (17 giriş)

| Giriş | Ne | Açtığınızda ne olur |
|---|---|---|
| `main.py` | Uygulama giriş noktası. Repo'yu `sys.path`'e ekler ve `python.gui.qt_app.main()` çağırır. | Uygulamanın nasıl önyükleneceğini değiştirmek için. |
| `pyproject.toml` | Python paket meta verisi (name=flashpilot, bağımlılıklar, build backend). | Python bağımlılığı eklemek veya sürümü artırmak için. |
| `Cargo.toml` / `Cargo.lock` | Rust çekirdek (the `flashpilot-bridge` binary). | Köprü CLI'ını değiştirmek veya yeni bir protokol eklemek için. |
| `python/` | Rust motorunun ince Python katmanı: `python/core/` (shim + GUI yardımcıları) ve `python/gui/` (PyQt6). Tüm akışlar `src/flows.rs` içinde yaşar. | GUI ve cihaz arayüzü. |
| `src/` | Rust kaynakları. `python/core/` ile eşlenik düzen. | Yeni bir köprü komutu eklediğinizde veya USB protokolünü değiştirdiğinizde. |
| `tests/` | pytest takımı. ~149 test, ~1s içinde çalışır. | `.venv/bin/python -m pytest tests/ -q` ile çalıştırın. |
| `scripts/` | Bağımsız shell araçları. Bugün: `dump-connected.sh`, `validate_mtp_at.py`. | GUI dışı toplu işlem gerektiğinde. |
| `docs/` | README varlıkları (ekran görüntüleri, logo). | README için. |
| `packaging/` | `.deb` derleme betiği + kontrol dosyaları. | Sürüm dağıtımı için. |
| `root/` | udev kuralları (telefonların sudo olmadan çalışması için). | Tek seferlik kurulum. |
| `operations/` | **İş başına dokümantasyon ağaçları** — aşağıdaki "operations/" bölümüne bakın. | Belirli bir işin (FRP, MDM, ekran kilidi vb.) nasıl çalıştığını anlamak istediğinizde. |
| `build/` | **Tüm gitignored derleme/çalıştırma çıktıları** — "build/" bölümüne bakın. | Bu dosyaya neredeyse hiç bakmazsınız. |
| `.github/` | CI iş akışları, issue şablonları. | CI'ı değiştirmek için. |
| `LICENSE` `CODE_OF_CONDUCT.md` `CONTRIBUTING.md` `SECURITY.md` `DESCRIPTION.md` | Standart proje meta verileri. | Sürüm çıkarmak için. |

## `python/` düzeni

```
python/
├── main.py                 <- uygulama girişi (repo'yu sys.path'e ekler, python.gui.qt_app.main çağırır)
├── gui/                    <- PyQt6 uygulaması
│   ├── qt_app.py           <- ana pencere + her cihaz modu UI (~12k LOC)
│   ├── devices.py          <- veri odaklı "desteklenen cihazlar" detay sayfası (marka -> model -> eylem)
│   ├── theme.py            <- tasarım tokenları (renkler, düğme stilleri, sürüm yardımcıları)
│   ├── animations.py       <- boyanmış glifler: bağlantı sahnesi, durum orb'i vb.
│   ├── nav.py              <- ana navigasyon çubuğu + OEM çip çubuğu
│   ├── toast.py            <- toast bildirimleri
│   └── supported_devices.json  <- hangi modelin hangi eylemi aldığını gösteren veritabanı
└── core/                   <- ince Python katmanı (Qt bağımlılığı yok; Rust köprüye devredir)
    ├── core.py             <- FLOWS/JOBS/MODES aynası (sabit önbellek + Rust flow_list())
    ├── bridge.py           <- Rust `flashpilot-bridge` ikili dosyasıyla konuşur
    ├── flow.py             <- Flow/Step yapıları + iptal
    ├── jobs.py             <- FlashJob yaşam döngüsü (izole iş katmanı)
    ├── cancel.py           <- işbirlikçi iptal kaydı
    ├── devices.py          <- çoklu cihaz kimliği (kararlı anahtarlar, liste, çözümleme, taşıma eşlemesi)
    ├── frp.py              <- FRP-only re-export yüzeyi (ad = sorumluluk)
    ├── mtk.py              <- MTK PIDs/stages/chips (0003=BROM, 2000=preloader)
    ├── mtp.py              <- Samsung MTP/AT (çoklu sıra ADB etkinleştirme)
    ├── pit.py pitstore.py  <- Samsung PIT ayrıştırıcı + önbellek
    ├── adb.py device_info.py actions.py experimental.py fus.py
    └── (no flows/ dir)     <- akışlar src/flows.rs içinde yaşar; Python sadece bridge.flow_run() ile devredir
```

**Akışlar Rust içinde yaşar.** `python/core/core.py` ince bir şemsiye: `_RustFlow`, çalıştırmayı `bridge flow-run <key>` çağrısıyla yapar. Kanonik kayıt `src/flows.rs` içinde (`flow!` makrosu, ~280 satır); Python arayüz için aynısını tutar.

## `src/` düzeni (Rust)

```
src/
├── main.rs                 <- Tüm CLI dağıtımı (eprintln! "log" kanalıdır) + flow-run
├── flows.rs                <- AKIŞ kaydı (flow! makrosu; FLOWS/JOBS/MODES)
├── usb/                    <- libusb bağlamı, tanımlayıcı ayrıştırma, filtreleme (mod.rs + filtering.rs)
├── devices.rs              <- birleşik USB+ADB cihaz satırları
├── sam_download.rs         <- Samsung Download/Odin oturumu (odin-* komutları)
├── sam_errors.rs sam_setup.rs sam_*.rs  <- Samsung yardımcıları
├── mtk.rs mtk_da.rs        <- MediaTek BROM/DA flashing
├── mtk_exploit.rs          <- BROM açıkları (bypass/kamakiri2/crash-to-BROM)
├── mtk_sla.rs mtk_sla_keys.rs <- Secure Lock Authentication
├── mtk_daloader.rs         <- DA kapsayıcı ayrıştırma
├── qualcomm/               <- EDL: Sahara + Firehose + GPT
├── spd.rs                  <- UNISOC BSL (BSL_CMD_*, BSL_REP_*, FDL1/FDL2)
├── pac.rs                  <- SPD PAC extract/pack
├── pit.rs                  <- Samsung PIT ayrıştırıcı
├── mtp.rs at.rs adb.rs     <- MTP, AT komutu, ADB arayüzü
├── fastboot.rs             <- yerel fastboot taşıyıcı
├── moto_flash.rs           <- Motorola staged fastboot FRP
├── apple.rs                <- Apple usbmuxd/lockdown
├── bulk.rs hid.rs          <- bulk + HID yardımcıları
├── fwtar.rs sparse.rs imgtools.rs <- firmware tar/sparse/boot-vbmeta
├── hostinfo.rs             <- host eMMC/UFS sağlığı
├── config.rs error.rs util.rs device.rs
└── (no odin.rs)            <- Odin mantığı sam_download.rs içinde yaşar
```

## `operations/` — iş başına dokümantasyon ağaçları

Bu klasörler her iş için **iş bazlı README ağaçları** içerir; her işin nasıl çalıştığını, hangi akış anahtarlarını kullandığını, hangi cihazları desteklediğini ve bilinen tuzakları açıklar. Bunlar **kod değil** — ağaç tamamen markdown'dur (önceki bir temizlik eski `.py` şablonlarını kaldırdı; `operations/` hiçbir şey içe aktarmaz). Kod `src/flows.rs` içinde yaşar (the `flow!` registry; `python/core/core.py` ince bir şemsiye) ve alan modülleri (`knox.py`, `qcn.py`, `imei.py`, `emmc.py`, …). `operations/` içindeki READMEs kullanıcılar / ticari araç araştırmacıları içindir; kaynak gerçek koddur.

| Klasör | Ne | Gerçek kod |
|---|---|---|
| `operations/apple/` | Apple icloud, activation lock, MDM, passcode/lost mode remove | Rust akışları (`src/flows.rs`: `apple_*` satırları, `flow-run` CLI) |
| `operations/frp/` | FRP bypass per-engine + per-device araştırma notları. **`operations/frp/INDEX.md` ile başlayın.** | Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI); ince `python/core/core.py` şemsiye |
| `operations/mdm/` | MDM / device-owner unlock + marka bazlı cihaz notları | Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI) |
| `operations/screen_unlock/` | Ekran kilidi kaldırma (ADB / recovery / download / kapsamlı) | Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI) |
| `operations/battery/` | Pil raporu / onarımı / yük testi (ADB üzerinden) | Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI) |
| `operations/network/` | SIM durumu, DNS, radyo sıfırlama | Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI) |
| `operations/carrier_unlock/` | Operatör kilidi (Apple, MTK) | Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI) |
| `operations/flashing/` | Cihaz bazlı flashing kılavuzları (Samsung Odin, MTK DA, Qualcomm EDL, UNISOC SPD, PIT) | Rust akışları (`src/flows.rs` kaydı, `flow-run` CLI) |
| `operations/usb/` | USB numaralandırma ve tespit notları | `src/usb/`, `src/devices.rs`, `python/core/devices.py` |

## `build/` — gitignored çalışma zamanı/derleme çıktıları

| Alt dizin | İçerik | Oluşturan |
|---|---|---|
| `build/target/` | Rust `cargo build` çıktısı | `cargo build` |
| `build/dist/` | `.deb` paketleri | `packaging/build-deb.sh` |
| `build/cache/` | Cihaz bazlı TAR önbellekleri ve tersine mühendislik dökümleri | GUI / `scripts/dump-connected.sh` |
| `build/mdm_qr/` | Üretilen MDM provisioning QR kodları | GUI MDM akışı |
| `build/pit/` | Önbelleğe alınmış `.pit` bölüm tablosu dosyaları | GUI PIT akışı |

**Kural:** `build/` içindeki hiçbir şeye `git add` yapmayın. Durumu silmeniz gerekiyorsa alt dizini silin — yeniden oluşturulacaktır.

## Yeni özellik nasıl eklenir ("hangi dosyaya dokunayım?" kopya tablosu)

| İstediğiniz | Dokunun |
|---|---|
| Desteklenen listeye yeni cihaz ekleme | `python/gui/supported_devices.json` |
| Desteklenen bir cihaza yeni marka bazlı eylem ekleme | `src/flows.rs` (bir `flow!(...)` satırı ekleyin); Python `bridge.flow_list()` üzerinden otomatik keşfeder |
| Var olan bir endişe için yeni ADB-komut akışı ekleme | aynı şekilde (Rust `src/flows.rs`) |
| Yeni bir köprü CLI komutu ekleme | `src/<concern>.rs` + `src/main.rs` (`<cmd>` arm in match) |
| Yeni üst düzey nav sayfası ekleme | `python/gui/qt_app.py` (`_build_*_page` + `_section_index`) |
| Yeni tasarım rengi / düğme stili ekleme | `python/gui/theme.py` (`C` dict / `_btn_*()`) |
| Yeni cihazın iş başına notlarını belgelemek | `operations/<job>/<brand>/<model>.md` |
| Test ekleme | `tests/test_<area>.py`, `test_mtk.py` örüntüsüne uyun |

## İş çalıştırıcı nasıl çalışır (bir kez okuyun)

GUI asla doğrudan akış çağırmaz. İş bazlı cihaz seçici
(`FlashPilotWindow._choose_device`) önce kararlı cihaz anahtarını çözer;
sonra `_run_ops_flow` / `_run_job_flow` çağrısı
`python.core.core.flow_for(job, mode, method)` ile `Flow()` nesnesi döndürür (bir `Step()` listesi), ardından `flow.run(ctx, log)` iş parçacığı içinde çalıştırılır`devices.device_scope(key)` içinde (böylece her çözümleyici seçilen telefona odaklanır). Her akış `log(line)` çağrısını kullanır; GUI bunu konsoluna bağlar. İptal cihaz kapsamlıdır (`flow.request_cancel(key)`; anahtarsız yaygın durdurma her şeyi durdurur), her `_run` başında kontrol edilir.

Yeni bir akış eklemek için `src/flows.rs` dosyasına bir `flow!("my_op", "My op", "Job Name", "MODE")` satırı ekleyin. Python `bridge.flow_list()` aracılığıyla otomatik keşfeder ve GUI iş/mod/metot hiyerarşisini otomatik olarak günceller. Rust `flow-run` CLI bunu çalıştırır; çözücüler hedef seri/`vid:pid@bus:addr` kabul etmelidir (bkz. `src/device.rs`).
