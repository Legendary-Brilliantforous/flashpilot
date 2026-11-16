# FlashPilot Yoğun UI İyileştirme Planı

Language switcher: [English](../../ui-improvement.md) · [Français](../fr/ui-improvement.md) · [Español](../es/ui-improvement.md) · [Deutsch](../de/ui-improvement.md) · [简体中文](../zh/ui-improvement.md) · [Русский](../ru/ui-improvement.md) · [Português](../pt/ui-improvement.md) · [日本語](../ja/ui-improvement.md) · [العربية](../ar/ui-improvement.md) · [हिन्दी](../hi/ui-improvement.md) · **Türkçe**

> English kanonik kaynaktır. Bu sayfa bir çeviridir; katkı memnuniyetle karşılanır — bkz. [`../TRANSLATION.md`](../TRANSLATION.md).

## Amaç
PyQt6 GUI'sini, tüm Rust-destekli akışları ve çoklu cihaz davranışını koruyarak işlevsel bir monolitten cilalı, bakımı kolay, yüksek performanslı bir tezgaha dönüştürmek.

## Mevcut durum
- `python/gui/qt_app.py` (~15k LOC) tek parçalı bir penceredir.
- Tema sistemi (`theme.py`) merkezileştirilmiştir, ancak QSS yer yer büyüktür ve tekrarlanır.
- Bağlantı çubuğu, nav rail, chip başına sayfalar, konsol, ayarlar hepsi aynı dosyadadır.
- Güçlü bir görsel kimlik zaten mevcuttur (cam kartlar, 10 aksan, kablo sahnesi).

## İlkeler
1. Python'da protokol mantığı yok; UI yalnızca render eder ve köprüyü çağırır.
2. Akışlar/işler/modlar için Rust tek doğru kaynaktır.
3. Duyarlılığı artır: ağır işi UI thread'den uzaklaştır, widget churn'ü azalt.
4. Erişilebilirlik: klavye navigasyonu, odak halkaları, ekran okuyucu etiketleri.
5. Bakımı kolaylık: `qt_app.py`'yi özellik modüllerine böl.

## Phase 0 — Pencere kabuğu, logo, açılış ekranı (yeni)
- Mevcut logoyu profesyonel bir vektör/SVG marka ile değiştir (monokrom + aksan varyantları, 16/32/64/128/256px + `.ico`/`.icns`).
- Açılış ekranı: animasyonlu marka logosu, ilerleme aşamaları (Rust köprüsünü başlat, cihazları tara, temayı yükle), sürüm, flicker yok; 200ms fade-in/out.
- Pencere render'ı: compositor-dostu alpha'lı çerçevesiz yarı saydam pencere, yuvarlatılmış köşeler, gölge, DPI-aware ölçekleme, çoklu monitör yerleştirme belleği.
- Akıcılık: Qt `AA_UseHighDpiPixmaps` etkinleştir, yüzey formatını ayarla (OpenGL/RGBA), vsync-dostu animasyonlar, layout thrash'ı azalt; 60fps etkileşim hedefi.
- Markalaşma: başlık çubuğu, görev çubuğu, hakkında diyaloğu, yükleyici içinde tutarlı logo.
- Yeniden boyutlandırılabilir kabuk sütunları: **cihaz paneli | sayfa** sınırı sürüklenebilir bir yatay ayırıcıdır (varsayılan 232px, sürüklenebilir aralık 228–420px, `layout/device_panel_width` içinde hatırlanır). Sayfa kendi doğal genişliğini korur ve çerçevesiz bir scroll area içinde yaşar, böylece sıkıştırılırsa sekmeleri/ızgarası reflow yapmak yerine yatay kaydırır; panel genişliği kullanıcı sürükleyene kadar pencere yeniden boyutlandırmalarının boyunca korunur. _Kullanıcı kararı: önceden katı bir `setFixedWidth(232)` vardı._

## Phase 1 — Mimari bölme (görsel değişiklik yok)
- Sayfa yapılandırıcılarını `python/gui/pages/` içine çıkar:
  - `samsung.py`, `mtk.py`, `qc.py`, `spd.py`, `battery.py`, `network.py`, `settings.py`, `quick.py`.
- Paylaşılan widget'ları `python/gui/widgets/` içine çıkar: `metric_card.py`, `collapsible.py`, `console.py`, `device_picker.py`.
- `qt_app.py`'yi kabuk olarak tut: pencere chrome, nav, yönlendirme, sinyaller.
- Kabul: uygulama açılır, tüm sekmeler render olur, testler geçer.

## Phase 2 — Performans
- Aygıt listesini ve konsol günlüğünü sanallaştır (`QAbstractListModel` + `QListView`) — O(n) widget oluşturmayı önle.
- Günlük güncellemelerini toplu olarak yap (her 50ms veya 100 satırda bir flush).
- Render edilmiş QSS'yi tema başına önbelleğe al; yalnızca aksan değiştiğinde yeniden oluştur.
- Ağır sayfaları lazy-load et (ilk ziyarette inşa et).
- Kabul: UI donması olmadan 10k günlük satırı; kaydırma 60fps kalır.

## Phase 3 — Görsel cilalama
- Tasarım token'ları: boşluk ölçeği (4/8/12/16/24), yarıçap ölçeği, elevation.
- Tutarlı kart elevation/gölge; hover/focus durumları.
- Hareket: 120ms sayfa solması, düğme basma ölçeği, toast kayması.
- İkon sistemi: emoji'leri SVG ikonlarla değiştir (marka glyph'leri).
- Aygıt tespiti için boş durumlar ve skeleton'lar.
- Yüksek kontrast modu + azaltılmış hareket toggle'ı.

## Phase 4 — UX akışları
- Arama/filtre ve taşıma badge'leri ile birleşik aygıt seçici diyaloğu.
- İşlem ilerlemesi: onay işaretli adım listesi, ETA, aygıt başına iptal.
- Hata sunumu: "yeniden dene / dokümanı aç / günlüğü kopyala" içeren eyleme geçirilebilir kartlar.
- Ayarlar: aranabilir, gruplanmış, varsayılanlara geri yükleme.
- Konsol: seviye/aygıt filtresi, dışa aktarma, bulma.

## Phase 5 — Erişilebilirlik & i18n
- Tam Tab sırası, görünür odak, ARIA-benzeri etiketler.
- Uygulama içi belgelenmiş klavye kısayolları.
- Çeviriler için string extraction (widget'larda sabit kullanıcı stringleri yok).

## Phase 6 — Test
- pytest-qt ile headless GUI duman testleri.
- Her sayfa/tema için görsel regresyon ekran görüntüleri.
- Günlük/aygıt render için performans benchmark'ları.

## Teslimatlar
- `python/gui/pages/*`, `python/gui/widgets/*`
- Güncellenmiş `theme.py` token sistemi
- `tests/test_gui_smoke.py`
- README/INDEX'de doküman güncellemesi.

## Riskler
- 15k LOC monolit; artımlı extraction gerekir.
- PyQt threading kuralları; tüm widget dokunuşları ana thread'de tutulmalı.
- Çoklu aygıt kapsamı ve iptal semantiğini koru.

## Önerilen ilk görev
`_build_console` ve `_build_conn_bar`'ı signal-tabanlı API ile `widgets/console.py` ve `widgets/connection_bar.py`'ye çıkar; davranış değişikliği yok.

## Phase 7 — Akış & Görev Render'ı (yeni)
### Gözlemlenen sorunlar
- `_add_job_flows` tüm modları job başına tek buton listesine düzleştirir; mod yalnızca tooltip'tedir, bu kafa karıştırıcıdır.
- Sayfalar arasında tekrarlanan düğmeler (Quick, chip ops sections, Unlock sekmeleri) ile tutarsız gating.
- Deneysel/yıkıcı düğmeler yalnızca renk/kenarlıkla ayırt edilir; legend yok.
- Arama/filtre, son kullanılanlar, favoriler yok.
- Uzun akış etiketleri `FlowLayout` içinde öngörülemez biçimde overflow/wrap olur.
- Risk bazlı görsel gruplama yok (read-only vs flash vs experimental).

### Önerilen render modeli
- **Job → Mode → Method** üç seviyeli navigasyon:
  - Sol: Job listesi (fiil-önce, ikonlar).
  - Orta: Sayısız Mode sekmeleri (ADB, MTP, …).
  - Sağ: Yöntem kartları (ad, risk badge, deneysel badge, tooltip).
- Tek doğru kaynak: `core.modes_for` / `core.methods_for`; sayfalarda yinelenen liste yok.
- Global olarak `(job, mode, key)` ile dedupe; chip sayfaları `_add_job_flows`'u yeniden çalıştırmak yerine desteklenen modlara göre filtreler.
- Yöntem kartı durumları: aygıt kapasite kapılarına göre enabled/disabled, çalışıyor (spinner), son sonuç (ok/fail).

### Neye taşınacak
- Buton oluşturma `_add_job_flows`'dan `widgets/flow_button.py` + `widgets/method_card.py`'ye taşı.
- Mod/job sayımı `FlowRegistryView` modeline (ince, mantıksız) UI binding için taşı.
- Yıkıcı/deneysel onay mantığını yeniden kullanılabilir `ConfirmDialog`'a taşı.

### Neye birleştirilecek
- Quick sayfası ile chip ops sayfaları aynı `modes` filtresiyle aynı `FlowBrowser` widget'ını kullanacak şekilde birleştir.
- Deneysel uyarı işleme kart badge + diyaloğa birleştir.

### Neler kaldırılacak / dedupe edilecek
- Aynı job flow'ları yineleyen sayfa başına `_add_job_flows` çağrılarını kaldır; filtered `FlowBrowser` ile değiştir.
- (Aynı key birden çok mod altında) yinelenen `Flow` örneklerini modları kartta gruplayarak kaldır.
- Ham `QLabel(job.upper())` başlıklarını sayımlı section başlıklarıyla değiştir.

### Yeni özellikler
- Arama kutusu job/mode/yöntem adı ve key'e göre filtreler.
- Favoriler/son kullanılanlar ayarlarda kalıcı.
- Risk legend: read-only (yeşil), medium (amber), high (kırmızı), experimental (dashed amber).
- Toplu seçim: birden çok yöntemi kuyruğa almak için checkbox'lar (adım adım sıralı çalıştırma, adım başına iptal).
- Favorileri sürükle-bırakla yeniden sıralama.

### Kabul
- Tüm sayfalarda tek tutarlı flow browser.
- Aynı `(job, mode, key)` için yinelenen yöntem düğmesi yok.
- 280 satır için arama filtresi <50ms.
- Kapasite kapıları yöntemleri neden tooltip'i ile görsel olarak devre dışı bırakır.

### Phase 7 — durum (şimdiye kadar uygulanan)
- **Seçilen form: sayfa içi yükseltme.** Tek render yolunu şimdi tanıt ve yerinde yükselt — `FlowBrowser` (view) + `MethodCard` (düğme) + `flow_meta` (routing/risk) — henüz Job → Mode → Method üç panelli navigasyon olmadan. Sayfalar mevcut düzenlerini korur; `_add_job_flows` satırları inşa eder ve `FlowBrowser` üzerinden render eder, tıklamalar `flow_meta.route_for` üzerinden route olur.
- **Türetilmiş risk modeli** (`flow_meta.risk_for`, badge'in okuyabileceği tek kaynak): `experimental` = key `_EXPERIMENTAL_FLOW_MAP` içinde; `high` = key `_DESTRUCTIVE_CONFIRM` içinde ve dolayısıyla **UI'nin zaten onay istemesini gerektiren tam olarak bu akışlar** (badge, diyalog olmadan hiç `high` iddiasında bulunamaz, read-only olmayan bir şey `read` iddiasında bulunamaz); `read` = yalnızca `READ_ONLY_JOBS` için (`{"Read Device Info", "Detect Devices"}`); geri kalan her şey, bilinmeyen key/job'lar dahil, fail-closed `medium`.
- **Slice B1 — gruplu akış render'ı (bu slice).** `FlowBrowser.set_rows` artık render ettiği içeriği gruplar ve adlandırılmış üç sorunu çözer:
  - Job başlığı artık `{"REMOVE FRP"} · 6` — raw `QLabel(job.upper())` bir yöntem **count**'u aldı (`border_hi` token'ıyla loşlaştırıldı, ad mevcut 11px / 800 / 1px düzenini korudu).
  - Her job içinde kartlar **taşıma moduna** göre küçük bir mod alt başlığı (`— ADB`) ile gruplanır, modun yalnızca tooltip'te olduğu tek düz job listesinin yerine. Satırlar `_flow_rows`'dan mode-major olarak gelir, bu yüzden aynı mod aralığı tek bir bölümdür; mod hiçbir zaman ekstra kartlara açılmaz.
  - Her `MethodCard`, `_btn_ghost()`'un üzerine, mevcut legend'ın yanında riski bir bakışta görünür kılan semantik **sol kenar** (`ok` read-only, `warn` medium, `err` high, `experimental` experimental) çizer. Deneysel kartlar amber **dashed** kenarlıklarını korur — artık `MethodCard.set_risk(level)` tarafından sahiplenilir; `set_state` inert kalır.
  - Construction gereği değişmeyen: render edilen satır kümesi, dedupe kuralı (job başına "first mode wins"), düğme metni (`btn_sha`), her tooltip string, tıklama routing, onay/deneysel overlay'ler ve gate registry (`job=`/`mode=`, asla `command=`). Yalnızca gruplama/etiket widget'ları eklendi.
- **Burada golden bilinçli olarak yeniden üretildi.** Bu slice'ta `REGEN_INVENTORY=1` ile `tests/ui_inventory_golden.json` yeniden inşa edildi. **Tek** fark sayfa başına **widget sayısıdır** (eklenen mode alt başlığı etiketleri; beş akış-ağır sayfada +113 widget). `gated_count`, `gated_unique_triples`, `gated_triples_sha256`, `core_flows`, `action_meta` ve her sayfanın `buttons` / `acts` / `btn_sha` byte-identical — gate registry ve tıklama yüzeyi hareket etmedi.
- **Slice B2 — aygıt model board'u (dikey aksiyon kartları) (bu slice).** Model sayfasının aksiyon başına satırları artık `ActionRow` kartlarıdır (`python/gui/widgets/action_row.py`), 50px elle yazılmış `mousePressEvent` monkeypatch'li `QFrame` yerine:
  - **3px semantik sol kenar** (wipe/yıkıcı aksiyonlar için `err`, aksi halde `accent_hi`) — akış tarayıcısında `MethodCard.set_risk`'ın boyadığı aynı risk-kenar dili,
  - **40x40 ikon tile**, **13px / 800** başlık ve **tek satır elided** açıklama. Bu planın "uzun akış etiketleri öngörülemez overflow/wrap" sorununu çözer: açıklama wrap yerine ellipsis olur, böylece uzun bir etiket panelinden geniş bir board yapamaz ve dağınık çok satırlı blok olarak okunmaz,
  - isteğe bağlı engine/mode **chip** ve loş **`›` chevron**; hover/pressed/focus widget'a aittir (QSS dynamic property + focus ring). Chip, `common._mode_chip`'in zaten döndürdüğü aksan renginden **tek tonlu pill** olarak boyanır (aksan tint fill, aksan text, aksan hairline border), böylece her badge bir aile olarak okunur,
  - **klavye erişilebilir** — `StrongFocus` + Enter / Return / Space `activated` sinyalini emit eder (monkeypatch `mousePressEvent` yerine). Board `flow_act` / `flow_tip` tag'lerini korur ve sadece `activated`'ı bağlar, routing değişmez,
  - grup container'ları artık job'un aksiyon **count**'unu taşıyor (`FRP REMOVE · 4`) — akış tarayıcısının job başlıklarıyla aynı "ad + count" dili.
- **İnvariyantlar korundu.** `_ACTION_META` hâlâ **62** girdidir; her `dev_*` sayfasının `acts` ve `btn_sha`'sı byte-identical (hiçbir aksiyon satırı, düğme metni veya düğme eklenmedi/silinmedi/yeniden adlandırılmadı); `gated_count` **418**, `gated_triples_sha256` `c89acce…7d75`, `gated_unique_triples` **61**, `core_flows` **116**, `stack_count` **25**. Sayfa stack'ının doğal minimum genişliği hâlâ **699px**, bu da elided etiketlerin hiçbir şeyi genişletmediğini kanıtlar.
- **Burada golden bilinçli olarak yeniden üretildi.** Bu slice `REGEN_INVENTORY=1` ile `tests/ui_inventory_golden.json`'u rebuild etti: tek fark sayfa başına **widget count** (`dev_apple` 59→63, `dev_motorola` 85→99 — iki araştırılmış board'un eklenen kartları/etiketleri). B2'nin geçici golden md5'i `929f428638e91a42865ddde1ac96dd19` idi. Bu doc slice'ının sonraki cilası (tek-tonlu chip ailesi ve first-show device-panel split) hiçbir sayfanın widget sayısını değiştirmedi, bu yüzden golden **ek bir regen gerekmedi**.
- **Slice B4 — model board sayfa yüksekliğini doldurur (bu slice).** Aygıt → model board (`devices.build_brand_page`) üzerinde two-pane split row sayfanın yüksekliğini almadı, böylece **her iki panenin altına** büyük bir boş bant kaldı. 1600x951 pencerede (dış sayfa viewport `878x717`) paneller `left 250x313 / right 598x333` ölçtü ve altında **333px dead band** vardı; aksiyon board'u `333` / `717`px aldı. Kök neden: split row, trailing `outer.addStretch(1)` hemen ardından outer'a stretch 1 ile eklendi — iki stretch öğe kalan dikey alanı ~50/50 böldü ve hiçbir panel dikey `Expanding` değildi, bu yüzden hiçbiri absorbe etmedi. Düzeltme (yalnızca `build_brand_page` içinde, cerrahi): rekabet eden trailing stretch'i düşür (split row artık **tüm** kalan yüksekliği alır) ve sol `list_col` ile sağ `right_stack`'e açıkça dikey `Expanding` policy ver, böylece iç `lscroll` ve mevcut model sayfasının iç `_scroll` tam yüksekliği alır ve kendi scrollbar'larını sahiplenir. Sol satırlar üst-hizalı kalır (`lv2.addStretch(1)` dokunulmadı) ve liste büyüdükçe scroll olur. Sonrası: `left 250x646 / right 598x665`, dead band **1px** (sadece layout'un 8px alt margin'i), sağ board daha fazla flow gösterir ve gerisini dahili kaydırır (`vscroll_max` 900 → 557), ve shell'in dış `_page_scroll` gizli kalır (`verticalScrollBar().maximum() == 0`). Kullanıcının gelecekteki gereksinimini destekleyerek, bellekte 40 ek model **sol** listenin scroll aralığını büyütür (`vscroll_max > 0`) ve her iki panenin yüksekliği değişmez.
  - Yeni testler: `tests/test_device_board_layout.py` —
    `TestBrandPageFillsHeight::test_no_dead_band_below_split`,
    `::test_both_panes_get_the_real_height`,
    `::test_right_board_scrolls_its_own_content`,
    `::test_more_devices_scroll_left_without_growing_the_panes`. Her iki geometri testi düzeltmeden önce **fail** etmeyi doğruladı (H=640'ta dead band 295px; sol panel 275px vs 412px floor).
  - **Hiçbir widget eklenmedi veya kaldırılmadı** (yalnızca bir size policy değişti ve bir stretch spacer dropped), bu yüzden hiçbir sayfanın widget count'u hareket etmedi ve `tests/ui_inventory_golden.json` regen gerekmedi — hâlâ `929f428638e91a42865ddde1ac96dd19`.
- **Slice C — aygıt board'unda tam akış registry'si (GERİ ALINDI).**
  Bu slice cihaz engine'inin tam akış registry'sini `ActionRow` kartları olarak render eden final bir `MORE FLOWS · N` grubu artı bir text/mode filter bar ekledi. **engine + transport mode** ile scope'landı; bu *bu cihazın fonksiyonları* ile aynı şey değil: ADB expose eden her telefon registry'deki tüm ADB-registered akışları çekerdi, bu yüzden Motorola board Samsung-only job'ları (`knox_bypass`, `kg_remove`, `odin_flash_tar`), `imei_repair_spd`, `apple_icloud_*` ve `huawei_frp_guide` sundu. Daha da kötüsü, Motorola modelleri **per-model engine** taşır (`Moto G13` = `spd`, `G24` = `mtk`, `G6` = `qcom`), bu yüzden `planned` modeller henüz yapılmamış iş için tüm SPD/MTK registry'sini gösterir ve motorola/apple markaları board'da `researched` gate'i tasarımı gereği bypass eder. Tamamen revert: registry grubu, filter bar'ı, `_ENGINE_MODES`, first-show deferral ve `tests/test_device_flows.py` gitti; board tekrar tam olarak per-device curated actions. Inventory golden boyunca byte-identical (`929f428638e91a42865ddde1ac96dd19`) çünkü grup lazy inşa edildi, bu yüzden revert regen gerektirmez.
  - Herhangi bir yeniden deneme için ders: **modelin kendi declared `actions`'ı** ile scope'la (`supported_devices.json`), sadece bu aksiyonların gerçekten dispatch ettiği akışları genişlet — asla engine + mode ile.
  - Hayatta kalan ve reusable vetted fact: `win._route_flow_activation(job, mode, key, label)` destructive confirm ve EXPERIMENTAL ownership ack'ı uygulayan tek sink'tir; `_dispatch`/`start_model_action` değildir (experimental check'i yalnızca dar `devices._EXPERIMENTAL_ACTS` kümesidir, bu yüzden örn. `emmc_raw` ack'sız çalışır).
- **Hâlâ ertelenen:** per-device flow listesi üzerinde search box / mode filter chips, favoriler/recents (settings-persisted), batch seçim kuyruğu (checkbox + sequential run), drag-to-reorder, Job → Mode → Method üç panelli navigasyon, bir job'un mode varyantlarını ekstra kartlara genişletme (her `(job, mode, key)` başına bir kart kasıtlı bir sonraki karardır — bu slice modları **genişletmez**), ve yeniden kullanılabilir `ConfirmDialog` (confirm/experimental overlay'ler window-owned modals olarak kalır).

## Phase 8 — Profesyonel cilalama & farklılaşma (yeni)
### Görsel kimlik
- Subtle grain/noise texture ve soft vignette'li imza “atelier” dark tema.
- Brand mark + monogram; tüm aksiyonlarda tutarlı ikonografi (Lucide tarzı).
- Aygıt hero kartları: model görseli silueti, chip, taşıma badge'leri, last-seen.
- Animasyonlu bağlantı sahnesi upgraded: gerçek kablo pulse, aygıt başına status dots.

### Bilgi yoğunluğu
- Çökertilebilir inspector paneli: seçili aygıt detayları, partition'lar, PIT özeti, log'lar.
- Aygıt başına operasyon timeline görünümü (başlangıç/bitiş, süre, sonuç).
- Flash öncesi PIT/partition değişiklikleri için diff görünümü.

### Güven & güvenlik
- Yıkıcı operasyonlar öncesi pre-flight checklist kartı (aygıt, firmware, PIT eşleşmesi).
- Renk + ikon + text ile net risk merdiveni; asla yalnızca renk.
- Dışa aktarılabilir denetim günlüğü (deneysel aksiyonlar) görüntüleyici.

### Üretkenlik
- Flow'ları, aygıtları, ayarları aramak için komut paleti (Ctrl+K).
- Log'lar ve aygıtlar arası global search.
- Klavye-öncelikli navigasyon; kısayol overlay'i (?).
- Oturum geri yükleme: son aygıt + sayfayı yeniden aç.

### Linux-native his
- Native dosya dialogları, sistem teması farkındalığı, Wayland/X11 işleme.
- Uzun operasyonlar için masaüstü bildirimleri; ilerlemeli tray ikonu.
- Firmware dosyalarını flash sayfasına sürükle-bırak.

### Onboarding
- İlk çalıştırma sihirbazı: udev setup, bridge build durumu, aygıt testi.
- İllüstrasyonlar ve sonraki adımlarla boş durumlar.
- `operations/`'dan flow başına doküman içeren içerik tabanlı yardım çekmecesi.

### Marka varlıkları
- Yeni logo seti, splash, yükleyici grafikleri, uygulama ikonu.
- README ekran görüntüleri yeni UI'ye göre yenilenir.

## Phase 9 — Konsol / terminal yeniden tasarımı (yeni)
### Amaç
Log konsolunu sıkışık bir text box yerine birinci sınıf bir Linux terminali (UEFI-shell/TTY estetiği) gibi hissettirmek.

### Layout
- Yatay bir splitter'da sağ tarafta dedicated dock (sayfalar sol, konsol sağ); yeniden boyutlandırılabilir, ince bir çubuğa daraltılabilir. Varsayılan genişlik 420px, minimum 360px (dock'un kendi control row'undan ölçüldüğü için hiçbir şey clip olmaz). _Kullanıcı kararı: konsol sağda kalır — bu phase'in erken bir taslağı “bottom dock / 35% height” diyordu; o superseded._
- Rahat padding (16px) ile geniş tek aralıklı terminal, line height 1.45.
- Minimal chrome ile opsiyonel tam ekran terminal modu (F11).
- Log'ların iç içe geçmemesi için aygıt başına tabs veya filter chips.

### Styling
- Dark TTY paleti: siyah arka plan, yeşil/amber/cyan text, opsiyonel hafif scanline.
- Bridge çıktısı için ANSI renk desteği; bold başlıklar, loş timestamp'lar.
- Satır numarası / timestamp toggle.
- Seçim + kopyalama; sağ tık menüsü (kopyala, kaydet, temizle, filtrele).

### Davranış
- Backpressure ile streaming; 10k+ satırda UI freeze yok.
- Regex arama, eşleşmeleri highlight, sonraki/önceki sıçrama.
- Dosyaya dışa aktarma; otomatik oturum günlüğü kaydı.
- Aygıt filtresi ve seviye filtresi (info/warn/error/step).

### Sıkıştırılmayacak
- Minimum genişlik/yükseklik kısıtları; responsive wrap; uzun satırlar için yatay kaydırma.
- Timestamp/level/aygıt için yeniden boyutlandırılabilir sütunlar.

## Phase 10 — Konsol mesajları & toast sistemi (yeni)
### Konsol mesajları
- Yapılandırılmış günlük girdileri: timestamp, aygıt key, seviye, mesaj.
- Seviyelere göre renk: info (slate), success (green), warn (amber), error (red), step (cyan).
- "show more" ile çok satırlı çıktıyı (stack trace, JSON) daralt.
- Flash adımları için inline progress bar'lar; her adım için status ikonları.
- Aygıtı odaklamak için tıklanabilir aygıt key'leri; dokümanı açmak için tıklanabilir akış key'leri.

### Toast'lar
- İkon, başlık, mesaj, aksiyon düğmesi ile bloklamayan, yığınlı toasts.
- Otomatik kapanma progress bar ile; hover'da duraklatma.
- Tutarlı palet ile önem derecesi stilleri (info/success/warn/error).
- Overflow counter ile kuyruk üst sınırı (en fazla 3 görünür).
- Konum seçenekleri (sağ üst/sağ alt) ve reduced-motion desteği.
- Hatalar için opsiyonel ses/tactile geri bildirim.

## Phase 12 — HiProTool parity research (yeni)
### Durum
- Bu ortamda online arama kullanılamıyor (HTTP 402). Manuel araştırma gerekli.

### Araştırma görevleri
- HiProTool özellik listesi topla (FRP, MDM, screen lock, carrier, IMEI, flashing).
- Her yöntemi bir engine'e eşle (ADB, download mode, BROM, EDL, fastboot, SPD).
- Aygıta özel kısayolları ve önkoşulları belirle.
- `operations/` içinde doğrulama adımları ve güvenlik notlarıyla belgele.
- Önce yüksek değerli, düşük riskli yöntemleri öncelikle.

## Phase 14 — Sonraki özellikler (yeni)
### Hedef özellikler
- IMEI blacklist removal (araştırma + aygıta özgü playbooks).
- Carrier unlock improvements (SIM lock, NVDATA/QCN yolları).
- MDM unlock improvements (device owner, QR provisioning, recovery).
- FRP improvements (chip/Android-sürümü başına yöntemler).
- Screen lock removal improvements (ADB, recovery, download, EDL).
- Samsung Knox Guard removal (EXPERIMENTAL, audit-logged).
- Apple MDM enrollment removal (profile/DEP).
- Samsung Knox yönetim araçları.
- Android Enterprise enrollment handling.
- Zero-touch enrollment handling.
- Apple Activation Lock removal (checkm8/DFU scope, honest limits).
- SIM PUK retrieval to unlock SIM PIN.
- Biometric lock removal (araştırma, aygıt limitleri).

### Notlar
- Her özellik Rust-destekli olmalı ve riskli olması halinde EXPERIMENTAL olarak gated edilmelidir.
- Doğrulama ve güvenlik notlarıyla `operations/` içinde belgele.

## Phase 15 — Doküman denetimi & temizlik (yeni)
### Bulunan eski referanslar (tarihsel/retired)
- `operations/*/README.md` retired Python modüllerini (`knox.py`, `qcn.py`, `health.py`, `apple.py`, `flows/*.py`) bağlam olarak anar; kabul edilebilir ancak açıkça tarihsel olarak işaretlenmeli.
- `INDEX.md` daha önce eksik `SPLIT_PLAN.md`'ye referans veriyordu (düzeltildi).
- `README.md` depo düzeni daha önce var olmayan modülleri listeliyordu (düzeltildi).
- `DESCRIPTION.md` yanlış transport/job sayılarına sahipti (düzeltildi).

### Kalan doc görevleri
- Tüm “retired” notlarını dosya başına tek “History” bölümüne normalize et.
- Her operations README'nin üstüne “Current architecture” notu ekle.
- Eski migration planlarını kaldır veya arşivle (`DESIGN.md` → yeni sürüm).
- `operations/`'i araştırma odaklı tut; kod işaretleri `src/flows.rs` demeli.