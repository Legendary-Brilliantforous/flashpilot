Language switcher: [English](../../CONTRIBUTING.md) · [Français](../fr/CONTRIBUTING.md) · [Español](../es/CONTRIBUTING.md) · [Deutsch](../de/CONTRIBUTING.md) · [简体中文](../zh/CONTRIBUTING.md) · [Русский](../ru/CONTRIBUTING.md) · [Português](../pt/CONTRIBUTING.md) · [日本語](../ja/CONTRIBUTING.md) · [العربية](../ar/CONTRIBUTING.md) · [हिन्दी](../hi/CONTRIBUTING.md) · **Türkçe**

> English kanonik kaynaktır. Bu sayfa bir çeviridir; katkı memnuniyetle karşılanır — bkz. [`../TRANSLATION.md`](../TRANSLATION.md).

# 🧑‍💻 FlashPilot'a Katkıda Bulunma

Durduğunuz için teşekkürler! Bu proje tersine mühendislikle oluşturulmuş protokoller
ve açık bilgi üzerine kurulmuştur — her katkı onu daha yetenekli, daha güvenilir
kılar ve ücretli Windows paketlerine daha da yaklaştırır. Katkıda bulunmak için
flash uzmanı olmanız gerekmez.

## İçindekiler

- [Davranış kuralları](#davranış-kuralları)
- [Proje nasıl organize edilmiş](#proje-nasıl-organize-edilmiş)
- [Katkı yolları](#katkı-yolları)
- [Başlarken](#başlarken)
- [Mimari turu (10 dakika)](#mimari-turu-10-dakika)
- [Yeni bir akış ekleme](#yeni-bir-akış-ekleme)
- [Yeni USB protokolü / Rust komutu ekleme](#yeni-usb-protokolü--rust-komutu-ekleme)
- [GUI kuralları](#gui-kuralları)
- [Test](#test)
- [Pull request kontrol listesi](#pull-request-kontrol-listesi)
- [Platform desteği politikası (port etmeden önce okuyun)](#platform-desteği-politikası-port-etmeden-önce-okuyun)
- [Yol haritası ve fikirler](#yol-haritası-ve-fikirler)
- [Katkıda bulunanlar](#katkıda-bulunanlar)
- [Sorular?](#sorular)

---

## Davranış kuralları

Bkz. [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Saygılı olun, iyi niyet varsayın
ve tartışmaları teknik ve yardımcı tutun. Bu bir hobi olarak başlayıp ciddi
olmuş bir projedir: yeni başlayanları ve veteranları eşit şekilde memnuniyetle
karşılarız. Taciz, gatekeeping veya sırlar/kimlik bilgileri gönderme tolere
edilmeyecektir. Protokol yükleri, kökenleri ve lisansları belgelendiğinde
memnuniyetle kabul edilir.

---

## Proje nasıl organize edilmiş

İki yarı birlikte çalışır:

| Katman | Konum | Dil | Rol |
|---|---|---|---|
| **Core / protokol motoru** | `src/` | Rust | Ham USB, tüm önyükleyici protokolleri (`flashpilot-bridge` CLI) |
| **Akış kaydı** | `src/flows.rs` | Rust | `flow!` makro satırları → `FLOWS` / `JOBS` / `MODES` (tek kaynak) |
| **Akış shim** | `python/core/core.py` | Python | İnce `_RustFlow` sarmalayıcıları + `JOBS` fallback; `bridge flow-run`'a devredер |
| **Cihaz kimliği** | `python/core/devices.py` | Python | Stabil anahtarlar, cihaz listesi, hedef yeniden çözümleme, thread scope |
| **FRP yüzeyi** | `python/core/frp.py` | Python | Yalnızca FRP yeniden dışa aktarım (ad == sorumluluk) |
| **GUI studio** | `python/gui/` | Python / PyQt6 | Workbench (`qt_app.py`), sayfalar (`devices.py`), tema, animasyonlar |

Python hiçbir zaman doğrudan USB ile konuşmaz. `target/release/flashpilot-bridge`
(Rust ikilisi) subprocess olarak çağrılır ve JSON/text döner. GUI yalnızca
worker thread'lerden gelen sinyalleri dinler — arka plan thread'inden asla
widget'lara dokunmayın.

---

## Katkı yolları

Kod yok? Sorun değil:

- **Gerçek donanımda test** — bir akışın hangi cihaz/firmware'de çalıştığını rapor edin.
- **Dokümantasyon** — README'yi, bu dosyayı ve akış açıklamalarını iyileştirin.
- **Firmware / DA / combo arşivleri** — meşru ve ücretsiz kullanılabilir binary'lere işaretler.
- **Çeviriler ve temalar** — GUI темalanabilir; yeni accent paketleri kolay kazanç.
- **UI/UX** — mockup'lar, erişilebilirlik pass'ları, klavye kısayolu tasarımı.
- **Hata raporları** — [hata raporu şablonunu](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml) kullanın: adımlar, log'lar, `flashpilot-bridge detect` çıktısı, cihaz modeli + firmware sürümü.
- **Kod** — aşağıya bakın.

> 💡 **Yeni misiniz?** Issue tracker'da **`good first issue`** etiketini arayın —
> tüm kapsamı belirlenmiş, alması güvenli, başlangıç dostu görevler.

---

## Başlarken

```bash
# 1. Rust köprüsünü derle
cargo build --release

# 2. (Önerilen) USB udev kuralları
sudo bash root/setup-usb.sh

# 3. Venv oluştur + çalıştır
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m python.main
```

Uygulama yerel bir PyQt6 penceresi açar. Köprünün derlenip derlenmediğini
ve ADB'nin algılanıp algılanmadığını görmek için **Settings → Tools** sayfasını
kullanın.

---

## Eski bir checkout'tan geçiş (geri dönüyorsanız önce bunu okuyun)

Churn hakkında açıkça bir not: 1.2.0 ile şu an arasında merkezi modülü
yeniden adlandırdık, bir god-file'ı odaklanmış modüllere böldük, her job'ı
yeniden adlandırdık ve bir düzine dosya ekledik. Bu eski import'ları, eski
doküman referanslarını ve `python.core.frp`'e karşı yazmış herhangi bir
dışarıdaki script'i bozar. Üzgünüz — god-file'ı öldürmenin, MTK PID
karışıklığını düzeltmenin ve multi-device desteği hack katmanları eklemeden
mümkün kılmanın tek yolu buydu. Bu bölüm tam adaptasyon rehberidir; burada
hiçbir şey kademeli olarak depreke edilmedi, hepsi birden değişti, bu yüzden
tabloyu bir kez çalışın ve güncel olursunuz.

### Yeniden adlandırılan yollar

| Önce | Sonra | Ne değişmeli |
|---|---|---|
| `python/core/frp.py` (god file: registry + her akış) | `python/core/core.py` | `from python.core import frp` → `from python.core import core`; `frp.FLOWS` → `core.FLOWS`, vb. |
| *(hiçbir şey — FRP god file içinde yaşıyordu)* | `python/core/frp.py` (yeni, yalnızca FRP) | Sadece FRP akışlarına ihtiyacınız varsa buradan import edin, `core` yerine. |
| *(hiçbir şey)* | `python/core/devices.py` (yeni) | Cihaz kimliği, `list_devices()`, `resolve_usb_target()`, `device_scope()`. |
| *(hiçbir şey)* | `python/core/imei.py` (yeni) | MTK/SPD IMEI onarım + değişiklik akışları. |
| *(hiçbir şey)* | `python/core/experimental.py` (yeni) | EXPERIMENTAL gate'leri + denetim (audit) logu. |
| *(hiçbir şey)* | `python/core/{knox,qcn,emmc,pac,apple,health,compat,device_info,fastboot,integrity,safety,spd_adb}.py` (yeni) | Daha önce god file içinde inline veya eksik olan alan başına mantık. |
| *(hiçbir şey)* | `tests/test_devices.py` (yeni) | Multi-device + cancel-scope testleri. |
| *(hiçbir şey)* | `CHANGELOG.md` (yeni) | Release başına gruplu değişiklikler; önce bunu kontrol edin. |

### Rust taşıması (güncel mimari — yukarıdaki tablo tarihtir)

Yukarıdaki split'ten sonra motorlar Rust'a taşındı ve Python tarafı inceldi.
Güncel gerçek:

- **Akışlar `src/flows.rs` içinde yaşar** (registry + `flow-run <key> [target]
  [--code/--partition/--file/--dpc ...]`). `flow-list` tek kaynaktır —
  dokümanda bir akış anahtarı anmadan önce orada doğrulayın.
- **`python/core/core.py` ince bir shim'dir** (~450 satır): `_RustFlow`
  köprüye `bridge flow-run` olarak devreder, registry bridge'ten `JOBS` fallback'ıyla gelir.
  16 alan başına motor modülü (`knox`, `qcn`, `emmc`, `imei`, `apple`, `ofp`, `pac`,
  `health`, `flashing`, `spd_adb`, `integrity`, `fastboot`, `usb_watch`, `compat`,
  `updater`, `safety`) silindi — yeni dokümanlarda onlara referans vermeyin.
- **GUI Python'da kalır** (`python/gui/qt_app.py` + `devices.py`); Rust registry'yi
  `bridge.flow_list()` üzerinden tüketir.
- Kaldırılan Python akışlarının eski test dosyaları onlarla birlikte silindi; coverage
  alan başına test paketleri + cargo `flows::tests`'dir.

### Uyarlamanız gereken API değişiklikleri

- **Resolver'lar `key=None` alır.** `find_samsung()`, `_download_mode_device()`,
  `_wait_for_adb()`, `_wait_mtk_brom_target()`, `_mtk_retry()`,
  `wait_clean_download_mode()`, `pit_contract()` hepsi isteğe bağlı stabil bir
  cihaz anahtarı kabul eder (varsayılan olarak ambient thread scope — eski
  çağrı yerleri çalışmaya devam eder, key ayarlanmadığında first-match davranışı
  korunur).
- **Cancel cihaz başına.** `flow.py` ve `bridge.py` içindeki `request_cancel()` /
  `clear_cancel()` / `cancel_requested()` `key=None` kabul eder.
  Keysiz `request_cancel()` hâlâ broadcast yapar (global STOP); keysiz kontroller
  önce ambient scope'u, sonra broadcast bus'ı sorgular.
- **Run-guard cihaz başına.** `qt_app.py` içindeki `_flow_start(label, destructive, key=None)` /
  `_flow_end(key=None)` / `_flow_busy_msg(key=None)`; eski global'ler `_FLOW_LOCK` /
  `_FLOW_LABEL` gitti (per-key dict'ler + `_flows_running()` ile değiştirildi).
- **Runner'lar `device_key=None` alır.** `_run_ops_flow()` / `_run_job_flow()`
  birkaç telefon eşleştiğinde cihaz seçiciyi gösterir, sonra
  `ctx["device_key"]` (+ çözülebildiğinde `ctx["target"]`) set eder ve
  `devices.device_scope()` içinde çalışır.
- **Yeni transport modu `"SPD"`** `MODES` içinde (VID `0x1782`); yeni job'lar
  `Knox / Warranty`, `QCN / Modem`, `IMEI Repair / Change`, `eMMC / UFS`.
- **Job adları verb-first** (`Remove FRP`, `FRP bypass` değil; bkz. README).
  Branch'iniz hâlâ eski adları referans alıyorsa, "Mimari turu" bölümündeki tabloya
  göre yeniden adlandırın.
- **MTK PID'leri mtkclient-konvansiyonudur**: `0e8d:0003` = BROM,
  `0e8d:2000` = preloader. Birkaç eski yorum/log onları takas etmişti;
  eski string'lere değil `mtk.pid_stage()` / Rust `boot_stage_for()`'a güvenin.

### Yeniden yapılandırmadan önce açık bir PR'iniz varsa

1. Yeni ağaca rebase edin; çakışmalar import'lar ve `JOBS`/`FLOWS` bloklarıyla
   sınırlı olmalı.
2. Aşağıdaki kontrol listesini çalıştırın — `pytest` eski key/ad referanslarını
   hemen yakalar (registry testleri her `JOBS` metodunun çözümlendiğini assert eder).
3. PR'iniz `flows/`'a dokunduysa (kaldırılan split-package deneyi): o dizin
   gitti, değişikliğinizi `core.py` + ilgili alan modülüne taşıyın.

---

## Mimari turu (10 dakika)

1. **`src/main.rs`** — 80+ komutlu bir CLI. Her `match` arm bir komutudur
   (`detect`, `mtk-flash`, `mtk-crash-brom`, `qcom-firehose`, `spd-format`,
   `odin-pit`, ...).
2. **`src/usb.rs`** — cihazları VID/PID ile bulur, endpoint'ler verir (artı
   yeniden numaralandırma-proof adresleme için stabil `port_numbers`).
3. **`src/odin.rs`** — Samsung download mode (reverse-engineered Odin 3 protokolü,
   Heimdall-türevli). PIT okur/yazar, partition'ları flashlar
   (kalıcı `odin-agent` oturum multiplexer dahil).
4. **`src/mtk*.rs`** — MediaTek BROM (`0e8d:0003`) → preloader (`0e8d:2000`) →
   Download Agent handshake, scatter parsing, GPT partition işleri, SLA anahtarları,
   BROM exploit'leri, crash-to-BROM. ⚠️ PID konvansiyonu mtkclient-stilidir:
   `0003`=BROM, `2000`=preloader — onları takas etmeyin.
5. **`src/qualcomm/`** — Sahara (EDL) handshake ve Firehose oturumları.
6. **`src/spd.rs`** — Spreadtrum/UNISOC BSL: FDL download, format, FRP, backup,
   PAC extract/pack.
7. **`src/flows.rs`** — **uygulamanın kalbi**. `flow!(key, label, job, mode)` satırları
   `FLOWS` / `JOBS` / `MODES` registry'sini oluşturur (~280 satır, 13 job, `SPD` dahil 9 mod).
   `python/core/core.py` yalnızca bunu GUI lookup için yansıtır.
8. **`python/core/devices.py`** — multi-device kimliği. Stabil anahtarlar
   (`adb:<serial>` → `usb:<port-path>` → volatile fallback), `list_devices()`,
   `resolve_usb_target()` ve seçilen telefonu resolver'lara taşıyan
   `device_scope()` thread-local.
9. **`python/gui/qt_app.py`** — tüm bölümleri (Samsung / MTK / QC / SPD /
   Battery / Network / Settings) ve sub-tab workbench'leri, artı per-operation cihaz
   seçici ve per-device run-guard'ı inşa eder.

### Veri akışı

```
buton tıkla
  → _choose_device(job, mode)          # 0-1 telefon eşleşirse sessiz, aksi halde seçici
  → _run_ops_flow(job, mode, method, name, device_key)
  → per-device _flow_start(key) + device_scope(key) + ctx["device_key"]
  → core.flow_for(...) -> Flow (Step listesi)
  → her Step worker thread'de çalışır, bridge._run([...]) çağırır
  → bridge target/release/flashpilot-bridge ... spawn eder
  → Rust USB I/O yapar, JSON/text yazdırır
  → Python parse eder + _ui.line() sinyalleri yayar ( [device-key] işaretli)
  → GUI konsolu / durumu / progress'i güvenle günceller
```

---

## Yeni bir akış ekleme

Ship edebileceğiniz en basit özellik. `src/flows.rs`'i açın ve bir satır ekleyin:

```rust
flow!("my_method", "My method", "Remove FRP", "ADB"),
```

Anahtar kısa snake_case'dir (`flow_` öneki yok). Python onu `bridge.flow_list()`
üzerinden otomatik keşfeder ve GUI'nin job/mode/method drill-down'ı onu
otomatik alır; çalıştırma `flashpilot-bridge flow-run my_method` üzerinden
yürür.

Sonra (yalnızca yeni düşük seviyeli protokol çalışması gerekiyorsa) köprü komutunu
`src/<concern>.rs` + `src/main.rs` içinde ekleyin. Job/mode wiring zaten akış
satırında mevcuttur.

İşte bu kadar — akış otomatik olarak GUI'nin dropdown/sub-tab'ında görünür ve
CLI'dan da erişilebilir olur. **Bu en yüksek değer/çaba oranına sahip ve
giriş yapması en kolay alandır.**

> Step'lerin içinde konsol çıktısı için `log(...)`, step'ler arasında taşımak
> istediğiniz state için `ctx` ve Rust ikilisine dokunan her şey için
> `bridge._run(...)` kullanın. Cancel çalışması için step'leri where
> appropriate `cancel_requested()` ile kooperatif tutun (cancel cihaz başına
> scoped — aşağıya bakın).

### Her akışın uyması gereken kurallar

- **Asla "o" cihazı kapmayın.** Eklediğiniz herhangi bir resolver'da `key=None`
  (ambient thread scope) kabul edin ve ona göre filtreleyin — bkz.
  `devices.device_key()`, `devices.match_key()`, `devices.device_scope()`. GUI
  scope'u işlem başına set eder; headless çağıranlar da edebilir.
- **Job adları verb-first** (`Remove FRP`, `Flash Firmware`, `Unlock Carrier`).
  **Flow anahtarları kısa snake_case** (`adb_frp`, `flow_adb_frp` değil); tek
  tarihsel alias (`fastboot_read`) kaldırıldı — alias eklemeyin.
- **MTK PID konvansiyonu mtkclient-stilidir**: `0e8d:0003` = BROM (held),
  `0e8d:2000` = preloader. Rust, Python, GUI etiketleri ve dokümanların hepsi
  uyuşmalıdır.
- **EXPERIMENTAL yazmalar** (Knox/IMEI/QCN/eMMC)
  `experimental.check_gate_strict()` üzerinden run başına ack ile geçer —
  saklanmış bir ack asla otomatik geçmemelidir. GUI'de `_EXPERIMENTAL_FLOW_MAP`
  + sahip olan çip sayfasındaki amber collapsible pattern ile gate'leyin (asla
  global bir LAB sayfasında).
- **Bridge target'ları volatildir** (`vid:pid@bus:addr` yeniden numaralandırmada
  değişir). Session açmadan önce stabil anahtardan yeniden çözümleyin
  (`devices.resolve_usb_target()`); odin4'ü `-d /dev/bus/usb/BBB/AAA` ile
  sabitleyin.

---

## Yeni USB protokolü / Rust komutu ekleme

1. `src/` altında modülünüzü ekleyin (ör. `src/myproto.rs`).
2. `src/main.rs` içine `mod myproto;` ve yeni bir `match` arm + usage satırı ekleyin.
3. `crate::error` üzerinden `Result<T>` döndürün ve yapılandırılmış çıktı için
   `serde_json` kullanın.
4. Python'da `python/core/bridge.py` içinde `_run([...])` sarmalayıcısı olarak
   dışa açın.
5. Onu çağıran bir `Flow`'u `core.py`'de oluşturun (yukarıdaki akış kurallarına
   uyun).
6. Yapabiliyorsanız test ekleyin — unit test'ler `src/*.rs` (`#[test]`) ve
   `tests/` içinde yaşar.

**Protokol hijyeni:** kaynağınızı (forumlar, clean-room write-up'lar, diğer OSS
projeler) modül docstring'inde alıntılayın. Tescilli blob'ları göndermiyoruz —
yalnızca protokol implementasyonunu.

---

## GUI kuralları

- **Yalnızca PyQt6.** Başka Qt binding'leri yok, ekstra UI bağımlılığı yok
  (bkz. `requirements.txt`).
- Mevcut görsel dili eşleştirin: `_btn_ghost()`, `_btn_primary()`,
  `_card_qss()`, `SectionTitle`, `C[...]` tema renkleri, button grid'ler için
  `FlowLayout`.
- **Tema token'ları, ham accent değil:** dolgular `C['accent'/'grad_a'/'grad_b']`
  kullanabilir, ama focus ring'ler, seçili tab border'lar ve checkbox'lar MUTLAKA
  nötr `C['focus_ring']` / `C['sel_border']` kullanmalıdır — aksi halde kırmızı
  accent temaları (Crimson, Sunset) focus state'lerine kırmızı sızdırır.
  Chrome için asla hex hardcode etmeyin.
- **Thread kuralı:** arka plan işi `threading.Thread` içinde; GUI güncellemeleri
  yalnızca `self._ui.*` sinyalleri üzerinden (`.line`, `.status`, `.toast`,
  `.ui`, `.progress`).
- **Animasyonlar:** `Motion.shake()` / `Motion.rubber()` widget başına karşılıklı
  olarak münferittir (`_anim_lock` ile korunur) — ikisini aynı anda çalıştırmayın
  veya call-site'lar `QTimer.singleShot` ile serialize etmelidir. Hiçbiri
  `setFixedSize`, restyle edilmiş border'lar veya disabled layout'lar geride
  bırakmamalıdır; `cleanup()` hepsini geri yükler.
- Uzun ömürlü UI satırlarını scrollable tutun — çip sayfaları content'i bir
  `QScrollArea` içine sarar, böylece küçük pencerelerde ezilmezler.
- Yeni sub-tab'lar `SamsungSubTabs` + bir `QStackedWidget` yeniden kullanır
  (bkz. `_build_chip_ops_section`).
- Action button'lar `NoFocus` (sticky focus ring yok); checkable tab pill'leri aktif
  durum için `checked` styling'i tutar.

---

## Test

```bash
cargo test                      # Rust unit test'leri (MTK stage mapping, SLA, PIT dahil)
.venv/bin/python -m pytest tests/   # Python suite (şu an 173 passed, 4 skipped)
```

Test suite düzeni:

- `tests/test_frp_flow.py` — `Flow`/`Step` çalıştırması + kooperatif iptal +
  per-device run-guard.
- `tests/test_mtk.py` — MediaTek mantığı (scatter, DA, boot-stage yardımcıları,
  BROM wait/crash-retry).
- `tests/test_devices.py` — stabil cihaz anahtarları, telefon filtreleme,
  hedef yeniden çözümleme, scoped cancel.
- `tests/test_carrier_lock.py` — SIM-lock verdict + MTK patch gating + DA discovery.
- `tests/test_odin_safety.py` — tar.md5 doğrulama, BL gate'leri, odin4 flag
  negotiation.
- `tests/test_pit.py` — Samsung PIT parsing.
- `tests/test_bridge_io.py`, `tests/test_fus.py` — bridge I/O + Samsung firmware
  downloader.

Rust mantığı eklerseniz aynı dosyada `#[test]` modülleri ekleyin. Akış
eklerseniz, mümkün olduğunda fake/offline context ile akışı çalıştıran bir pytest
ekleyin. Yeni resolver'lar `key=None` kabul etmelidir; yeni testler tek telefon
varsaymak yerine multi-device filtrelemeyi kapsamalıdır (bkz. `test_devices.py`).

---

## Pull request kontrol listesi

- [ ] `cargo build --release` geçer.
- [ ] `cargo test` geçer (veya neden çalıştırılamadığını not edin).
- [ ] `.venv/bin/python -m pytest tests/` geçer.
- [ ] Yeni akış: GUI'de erişilebilir olması için `JOBS`'a (job + mode) bağlandı.
- [ ] Yeni resolver: `key=None` (ambient scope) kabul eder ve bir multi-device testi
  ile kapsanmış.
- [ ] Yeni Rust komutu: `main.rs` usage text'ine + `bridge.py` sarmalayıcısına
  eklendi.
- [ ] GUI değişiklikleri: temalı renkler (nötr focus token'ları!), sinyal tabanlı
  güncellemeler, scroll-safe layout'lar.
- [ ] Repoya secret/binary/cihaz tanımlayıcı veri eklenmedi.
- [ ] Bir capability eklediyseniz README feature matrix güncellendi.

PR'ları odaklı tutun. PR başına bir feature veya fix idealdir; issue numarasına
referans verin.

---

## Platform desteği politikası (port etmeden önce okuyun)

**Linux tek desteklenen platformdur.** Geliştirme, donanım testleri ve
release'ler Linux hedeflidir. Windows/macOS issue'ları desteklenmeyen olarak
kapatılır — code olarak gelmedikleri sürece, aşağıda belirtildiği gibi.

**Neden:** `odin4` yalnızca Linux; Windows USB per-mode driver'lar (Zadig /
QDLoader / Samsung) gerektirir ve uzaktan debug edilemez; macOS negligible
talep için signing/notarization gerektirir. Tam argüman ve itiraz daveti için
README'nin "Platform support" bölümüne bakın.

**Yine de nasıl bir port katkıda bulunursunuz (kabul edilen şekil):**

1. Flow'lar veya GUI içine `sys.platform` check'leri serpistirmeyin.
2. Backend fonksiyonları ile `python/core/platform.py` ekleyin —
   `open_file_manager()`, `detach_kernel_drivers(target)`,
   `usb_device_path(bus, addr)`, `needs_udev_setup()`,
   `kernel_module_loaded(name)` — Linux implemente edilir, diğerleri yardımcı
   bir mesajla `NotImplementedError` fırlatır.
3. Mevcut Linux-only çağrı yerlerini (`xdg-open`, `rmmod cdc_acm`,
   `/dev/bus/usb`, `lsmod`, udev dokümanları) ona taşıyın, çağrı yeri grubu
   başına bir PR.
4. Bir Windows/macOS backend PR'ı şunları içermeli: backend implementasyonu,
   doküman güncellemeleri ve CI veya maintainer tarafından doğrulanmış manuel
   test kanıtı. Core takım non-Linux test donanımına sahip değil — port PR'ları
   yazarlarının onları kanıtlayabilme yeteneklerine göre yaşar veya ölür.

**PySide6 vs PyQt6:** PySide6 (LGPL, MIT-uyumlu — PyQt6 GPLv3) migrasyonu
isteniyor ama GUI smoke-test coverage'a blokeli. Eğer onu üstlenirseniz:
`pyqtSignal→Signal`, `pyqtProperty→Property`, `PyQt6.sip→shiboken6` mekanik
olarak dönüştürün, `tests/` içindeki offscreen window/picker/guard smoke test'lerini
genişletin ve davranışı pixel-identical tutun. Önce Discussions'ta tartışın.

## Yol haritası ve fikirler

Contributor'ların herhangi birini champion etmesini çok isteriz:

- **Port'lar ve packaging:** Flatpak / AppImage / AUR, CI matrix'i (Linux dağıtımları), `pip`/`cargo` release akışı.
- **MediaTek:** daha fazla DA varyantı, scatter edge case'ler,
  eMMC/UFS backup dump'ları, `CHIP_NAMES`'te yeni `hw_code` girdileri (alıntılanmış
  bir kaynakla — hex kodları asla tahmin etmeyin).
- **Qualcomm:** rawprogram/patch XML edge case'ler, fh-loader komboları, daha çoğu
  chip PID.
- **Samsung:** SoC başına ek HID download-mode payload'ları, Odin multi-partition
  UX polish.
- **Multi-device:** per-device konsol tab'ları/progress, per-device STOP
  granülaritesi (STOP şu an broadcast ediyor), egzotik hub'lar için
  `port_numbers` correlation.
- **Yeni bölümler:** TEE/keyboard FRP, carrier (de-bloating) profilleri,
  EDL-yalnızca araçlar.
- **Topluluk:** çeviriler, cihaz-uyumluluk wikisi, yeniden üretilebilir
  firmware-arşiv kataloğu.
- **Güvenlik:** dry-run modu, otomatik pre-flash backup, brick-recovery dokümanları.

---

## Katkıda bulunanlar

Yardımcı olan herkes — kod, doküman, cihaz raporları veya test edilmiş bir combo —
burada listelenir ve kutlanır. Kendinizi eklemek için bir PR açın (kullanıcı adına
göre alfabetik, tek link satırı):

```md
- [@your-github](https://github.com/your-github) — what you did
```

Bu projeyi gerçek yapan ilk katkıda bulunanlardır. Sıradaki siz olun.

---

## Sorular?

Bir discussion/issue açın. Linux'ta özgür, açık flashing yazılımının
ilerlemesine yardım ettiğiniz için teşekkürler. 🚀
