# FlashPilot Intensive UI Improvement Plan

Language switcher: [English](../../ui-improvement.md) · [Français](../fr/ui-improvement.md) · [Español](../es/ui-improvement.md) · [Deutsch](../de/ui-improvement.md) · [简体中文](../zh/ui-improvement.md) · [Русский](../ru/ui-improvement.md) · [Português](../pt/ui-improvement.md) · [日本語](../ja/ui-improvement.md) · [العربية](../ar/ui-improvement.md) · **हिन्दी** · [Türkçe](../tr/ui-improvement.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## लक्ष्य (Goal)
PyQt6 GUI को functional monolith से polished, maintainable, high-performance workbench में बदलना, ताकि सभी Rust-backed flows और multi-device behavior बरकरार रहें।

## वर्तमान स्थिति (Current state)
- `python/gui/qt_app.py` (~15k LOC) एक अकेला monolithic window है।
- थीम सिस्टम (`theme.py`) मध्यीकृत है, लेकिन QSS बड़ा है और जगह-जगह duplicate है।
- कनेक्शन बार, nav rail, chip-wise pages, कंसोल, सेटिंग्स सब एक ही फ़ाइल में हैं।
- मज़बूत visual identity पहले से मौजूद है (glass cards, 10 accents, cable scene)।

## सिद्धांत (Principles)
1. Python में कोई protocol logic नहीं; UI सिर्फ render करता है और bridge को call करता है।
2. flows/jobs/modes का source of truth Rust है।
3. responsiveness बढ़ाएँ: heavy work UI thread से हटाएँ, widget churn घटाएँ।
4. accessibility: keyboard navigation, focus rings, screen-reader labels।
5. maintainability: `qt_app.py` को feature modules में split करें।

## Phase 0 — Window shell, logo, splash (नया)
- मौजूदा logo को professional vector/SVG mark से बदलें (monochrome + accent variants, 16/32/64/128/256px + .ico/.icns)।
- Splash screen: animated brand mark, progress stages (init Rust bridge, scan devices, load theme), version, कोई flicker नहीं; 200ms fade-in/out।
- window rendering: compositor-friendly alpha वाला frameless translucent window, rounded corners, drop shadow, DPI-aware scaling, multi-monitor placement memory।
- smoothness: Qt `AA_UseHighDpiPixmaps` enable, surface format set (OpenGL/RGBA), vsync-friendly animations, layout thrash कम करें; 60fps interactions target।
- branding: title bar, taskbar, about dialog, installer में consistent logo।
- resizable shell columns: **device panel | page** boundary एक draggable horizontal splitter है (default 232px, draggable 228–420px, `layout/device_panel_width` में remember)। page अपनी natural width रखता है और frame-less scroll area में रहता है, इसलिए squeeze होने पर tabs/grid reflow होने के बजाय sideways scroll होता है; panel width window resize के दौरान user drag होने तक persist करता है। _Decision (user): पहले hard `setFixedWidth(232)` था._

## Phase 1 — Architecture split (कोई visual change नहीं)
- page builders extract करें `python/gui/pages/` में:
  - `samsung.py`, `mtk.py`, `qc.py`, `spd.py`, `battery.py`, `network.py`, `settings.py`, `quick.py`.
- shared widgets extract करें `python/gui/widgets/` में: `metric_card.py`, `collapsible.py`, `console.py`, `device_picker.py`.
- `qt_app.py` shell की तरह रखें: window chrome, nav, routing, signals।
- acceptance: app boot हो, सब tabs render हों, tests pass हों।

## Phase 2 — Performance
- device list और console log virtualize करें (QAbstractListModel + QListView) ताकि O(n) widget creation avoid हो।
- log updates batch करें (हर 50ms या 100 lines flush)।
- rendered QSS per theme cache करें; सिर्फ accent change पर regenerate करें।
- heavy pages lazy-load करें (first visit पर build)।
- acceptance: 10k log lines बिना UI stall; scroll 60fps रहे।

## Phase 3 — Visual polish
- design tokens: spacing scale (4/8/12/16/24), radius scale, elevation।
- consistent card elevation/shadow; hover/focus states।
- motion: page fade 120ms, button press scale, toast slide।
- icon system: emoji को SVG icons (brand glyphs) से replace करें।
- empty states और skeletons for device detection।
- high-contrast mode + reduced-motion toggle।

## Phase 4 — UX flows
- unified device picker dialog with search/filter और transport badges।
- operation progress: checkmarks वाला step list, ETA, per device cancel।
- error presentation: actionable cards जिनमें "retry / open docs / copy log"।
- settings: searchable, grouped, reset-to-defaults के साथ।
- console: level/device से filter, export, find।

## Phase 5 — Accessibility & i18n
- full Tab order, visible focus, ARIA-like labels।
- keyboard shortcuts in-app documented।
- translations के लिए string extraction (widgets में hardcoded user strings नहीं)।

## Phase 6 — Testing
- pytest-qt से GUI smoke tests (headless)।
- हर page/theme के लिए visual regression screenshots।
- log/device rendering के performance benchmarks।

## Deliverables
- `python/gui/pages/*`, `python/gui/widgets/*`
- updated `theme.py` token system
- `tests/test_gui_smoke.py`
- README/INDEX में docs update।

## Risks
- 15k LOC monolith; incremental extraction ज़रूरी।
- PyQt threading rules; सब widget touches main thread पर रखने हैं।
- multi-device scoping और cancel semantics preserve करने हैं।

## Suggested first task
`_build_console` और `_build_conn_bar` को `widgets/console.py` और `widgets/connection_bar.py` में extract करें signal-based API के साथ; कोई behavior change नहीं।

## Phase 7 — Flow & Job Rendering (नया)
### देखी गई समस्याएँ (Problems observed)
- `_add_job_flows` हर job के flows को एक ही button list में flatten करता है; mode सिर्फ tooltip में होता है, इससे confusion होता है।
- Quick, chip ops sections, Unlock tabs जैसे pages में duplicate buttons हैं, gating inconsistent है।
- experimental/destructive buttons सिर्फ color/border से distinguish होते हैं; कोई legend नहीं।
- कोई search/filter, हाल ही में used, या favorites नहीं।
- long flow labels FlowLayout में unpredictably overflow/wrap होते हैं।
- risk के basis पर visual grouping नहीं है (read-only vs flash vs experimental)।

### Proposed rendering model
- **Job → Mode → Method** three-level navigation:
  - Left: Job list (verb-first, icons)।
  - Middle: Mode tabs (ADB, MTP, …) with counts।
  - Right: Method cards (name, risk badge, experimental badge, tooltip)।
- Single source of truth: `core.modes_for` / `core.methods_for`; pages में duplicate lists नहीं।
- globally deduplicate by (job, mode, key); chip pages re-run `_add_job_flows` के बजाय supported modes filter करें।
- Method card states: device capability gates से enabled/disabled, running (spinner), last result (ok/fail)।

### क्या move करना है (What to move)
- button construction `_add_job_flows` से `widgets/flow_button.py` + `widgets/method_card.py` में move करें।
- mode/job enumeration `FlowRegistryView` model में move करें (thin, no logic) UI binding के लिए।
- destructive/experimental confirm logic reusable `ConfirmDialog` में move करें।

### क्या merge करना है (What to merge)
- Quick page और chip ops pages को same `FlowBrowser` widget use करने के लिए merge करें `modes` filter के साथ।
- experimental warning handling card badge + dialog में merge करें।

### क्या remove / deduplicate करना है (What to remove / deduplicate)
- per-page `_add_job_flows` calls remove करें जो same job flows duplicate करते हैं; filtered `FlowBrowser` से replace करें।
- duplicate `Flow` instances (same key multiple modes में) remove करें by grouping modes on card।
- raw `QLabel(job.upper())` headers remove करें section headers with counts के लिए।

### New features
- search box filters by job/mode/method name और key।
- favorites/recents settings में persisted।
- risk legend: read-only (green), medium (amber), high (red), experimental (dashed amber)।
- batch selection: checkboxes multiple methods queue करने के लिए (sequentially run with per-step cancel)।
- drag-to-reorder favorites।

### Acceptance
- ek consistent flow browser सभी pages पर।
- same (job, mode, key) के लिए duplicate method buttons नहीं।
- search 280 rows के लिए <50ms में filter करे।
- capability gates visually disable methods with reason tooltip।

### Phase 7 — status (implemented so far)
- **Chosen shape: in-page upgrade.** Single rendering path अभी introduce करें — `FlowBrowser` (view) + `MethodCard` (button) + `flow_meta` (routing/risk) — *bina* Job → Mode → Method three-pane navigation के। Pages current layout रखें; `_add_job_flows` rows build करता है और उन्हें `FlowBrowser` के ज़रिए render करता है, clicks `flow_meta.route_for` से route होते हैं।
- **Derived risk model** (`flow_meta.risk_for`, जिसे एक badge पढ़ सकता है): `experimental` = key `_EXPERIMENTAL_FLOW_MAP` में; `high` = key `_DESTRUCTIVE_CONFIRM` में, और इसलिए UI जिन flows की पहले से confirmation माँगता है वही (`high`); एक badge बिना dialog के `high` claim नहीं कर सकता और बिना read-only के `read` नहीं; `read` = sirf `READ_ONLY_JOBS` (`{"Read Device Info", "Detect Devices"}`); बाकी सब, unknown keys/jobs भी, `medium` पर fail closed होते हैं।

- **Slice B1 — grouped flow rendering (this slice).** `FlowBrowser.set_rows` अब वह ग्रुप render करता है जो render होना है, तीन named problems fix करने के लिए:
  - Job header अब `{"REMOVE FRP"} · 6` है — raw `QLabel(job.upper())` को method **count** मिला (`border_hi` token से dimmed, name existing 11px / 800 / 1px treatment retain करता है)।
  - हर job के अंदर, cards **transport mode** के अनुसार group होते हैं behind a small mode sub-heading (`— ADB`), ek flat per-job list ki jagah jisme mode sirf tooltip mein hota hai। Rows mode-major `_flow_rows` se aate हैं, isliye equal modes ka run ek section hota hai; koi mode extra cards mein expand nahi hota।
  - हर `MethodCard` semantic **left edge** paint karta hai (`ok` read-only, `warn` medium, `err` high, `experimental` experimental) composed over `_btn_ghost()`, toh risk at a glance visible hai existing legend ke alongside। Experimental cards apna amber **dashed** border retain karte हैं — ab `MethodCard.set_risk(level)` own karta hai; `set_state` inert rehta hai।
  - unchanged by construction: rendered row set, dedupe rule ("first mode wins" per job), button text (`btn_sha`), har tooltip string, click routing, confirm/experimental overlays, aur gate registry (`job=`/`mode=`, kabhi `command=` nahi)। Sirf grouping/label widgets added hain।

- **Slice B2 — device model board (vertical action cards) (this slice).** model page के per-action rows अब `ActionRow` cards (`python/gui/widgets/action_row.py`) हैं, 50px hand-rolled `QFrame` with monkeypatched `mousePressEvent` के बजाय:
  - **3px semantic left edge** (`err` wipe/destructive actions के लिए, else `accent_hi`) — same risk-edge language जो flow browser में `MethodCard.set_risk` paint करता है,
  - **40x40 icon tile**, **13px / 800** title और **one-line elided** description। यह plan का "long flow labels overflow / wrap unpredictably" fix करता है: description ellipsise होता है wrapping के बजाय, इसलिए long label board को pane से wider नहीं बना सकता और ragged multi-line block read नहीं होगा,
  - optional engine/mode **chip** और dim **`›` chevron**; hover / pressed / focus widget-owned हैं (QSS dynamic property + focus ring)। Chip accent color `common._mode_chip` जो return करता है उससे **single-hue pill** paint होता है (accent tint fill, accent text, accent hairline border), इसलिए every badge एक family की tarah read होता है,
  - **keyboard reachable** — `StrongFocus` + Enter / Return / Space `activated` signal emit करते हैं (monkeypatched `mousePressEvent` replace)। Board अपने `flow_act` / `flow_tip` tags retain करता है और sirf `activated` connect करता है, routing unchanged,
  - group containers अब job का action **count** carry करते हैं (`FRP REMOVE · 4`) — flow browser job headers का same name + count language।
- **Invariants held.** `_ACTION_META` अबhi bhi **62** entries; har `dev_*` page ke `acts` aur `btn_sha` byte-identical (koi action row, button text ya button added/removed/renamed nahi); `gated_count` **418**, `gated_triples_sha256` `c89acce…7d75`, `gated_unique_triples` **61**, `core_flows` **116**, `stack_count` **25**। Page stack ka natural minimum width abhi bhi **699px**, proving elided labels ne kuch nahi widen kiya।
- **Golden deliberately regenerated here.** `tests/ui_inventory_golden.json` `REGEN_INVENTORY=1` ke saath rebuild: only diff per-page **widget count** (`dev_apple` 59→63, `dev_motorola` 85→99 — two researched boards' added cards/labels)। Transient golden md5 after B2 `929f428638e91a42865ddde1ac96dd19` tha। Is doc slice ka follow-up polish (single-hue chip family aur first-show device-panel split) ne **koi** page widget count nahi badla, isliye golden ko further regen nahi chahiye tha।

- **Slice B4 — model board fills the page height (this slice).** device → model board (`devices.build_brand_page`) par two-pane split row ko page ki height nahi mil rahi thi, isliye dono panes ke **neeche** big empty band chhuta tha. At 1600x951 window (outer page viewport `878x717`) panes `left 250x313 / right 598x333` measure huye with **333px dead band** underneath, aur action board ko sirf `333` mila `717`px ka. Root cause: split row `outer` mein **stretch 1** ke saath add hua *and* immediately baad trailing `outer.addStretch(1)` add hua — two stretched items leftover vertical space ~50/50 split karte hain, aur koi pane vertically `Expanding` nahi tha, isliye kuch absorb nahi karta. Fix (surgical, only `build_brand_page`): competing trailing stretch drop karo (split row ab **all** leftover height leta hai) aur left `list_col` + right `right_stack` ko explicit vertical `Expanding` policy do, toh inner `lscroll` aur current model page ka inner `_scroll` full height receive kare aur apna scrollbar own kare. Left rows top-aligned (`lv2.addStretch(1)` untouched) aur list grow hone par scroll kare. After: `left 250x646 / right 598x665`, dead band **1px** (sirf layout ka 8px bottom margin), right board far more flows show karta hai aur rest internally scroll karta hai (`vscroll_max` 900 → 557), shell ka outer `_page_scroll` hidden rehta hai (`verticalScrollBar().maximum() == 0`)। Backing user ka future requirement, 40 extra in-memory models left list ka scroll range grow karte hain (**no** pane height change)।
  - New tests: `tests/test_device_board_layout.py` —
    `TestBrandPageFillsHeight::test_no_dead_band_below_split`,
    `::test_both_panes_get_the_real_height`,
    `::test_right_board_scrolls_its_own_content`,
    `::test_more_devices_scroll_left_without_growing_the_panes`।
  - **Koi widget add/remove nahi hua** (sirf size policy changed aur stretch spacer dropped), isliye kisi page ka widget count nahi badla aur `tests/ui_inventory_golden.json` ko regen nahi chahiye tha — still `929f428638e91a42865ddde1ac96dd19`।
- **Slice C — full flow registry on the device board (REVERTED).**
  Yeh slice final `MORE FLOWS · N` group add karta tha jo device engine ka complete flow registry `ActionRow` cards ke liye render karta hai, plus text/mode filter bar. Scoped by **engine + transport mode**, jo *this device's functions* ke same nahi hai: any phone ADB expose karta hai toh registry ka every ADB-registered flow pull ho jata hai, isliye Motorola board Samsung-only jobs (`knox_bypass`, `kg_remove`, `odin_flash_tar`), `imei_repair_spd`, `apple_icloud_*` aur `huawei_frp_guide` offer karta tha। Worse, Motorola models carry **per-model engines** (`Moto G13` = `spd`, `G24` = `mtk`, `G6` = `qcom`), toh `planned` models ek entire SPD/MTK registry show karte hain kaam jo hua nahi hai, aur motorola/apple brands researched gate ko by design bypass karte hain board par। Full revert hua: registry group, its filter bar, `_ENGINE_MODES`, first-show deferral aur `tests/test_device_flows.py` gone hain; board again exactly per-device curated actions hai। Inventory golden byte-identical throughout raha (`929f428638e91a42865ddde1ac96dd19`) because group lazily built tha, isliye revert ko regen nahi chahiye।
  - Re-attempt ka lesson: scope by **model's own declared `actions`** (`supported_devices.json`), expanding only flows those actions really dispatch to — engine + mode se kabhi nahi।
  - Vetted reusable fact: `win._route_flow_activation(job, mode, key, label)` hi ek sink hai jo destructive confirm aur EXPERIMENTAL ownership ack apply karta hai; `_dispatch`/`start_model_action` nahi (its experimental check narrow `devices._EXPERIMENTAL_ACTS` set hai, toh e.g. `emmc_raw` unacknowledged run ho jayega)।
- **Deferred (still):** search box / mode filter chips over a per-device flow list, favourites/recents (settings-persisted), batch selection queue (checkboxes + sequential run), drag-to-reorder, Job → Mode → Method three-pane navigation, job ke mode variants expand karna into extra cards (one card per `(job, mode, key)` deliberate later decision — this slice modes expand Nahi karta), aur reusable `ConfirmDialog` (confirm/experimental overlays abhi window-owned modals rehenge)।

## Phase 8 — Professional polish & differentiation (नया)
### Visual identity
- signature “atelier” dark theme with subtle grain/noise texture aur soft vignette।
- brand mark + monogram; consistent iconography (Lucide-style) across all actions।
- device hero cards: model image silhouette, chip, transport badges, last-seen।
- animated connection scene upgraded: real cable pulse, per-device status dots।

### Information density
- collapsible inspector panel: selected device details, partitions, PIT summary, logs।
- operations ka timeline view (start/end, duration, result) per device।
- PIT/partition changes ke before flash diff view।

### Safety & trust
- destructive ops se pehle pre-flight checklist card (device, firmware, PIT match)।
- clear risk ladder with color + icon + text; kabhi color-only nahi।
- experimental actions ka audit log viewer with export।

### Productivity
- command palette (Ctrl+K) flows, devices, settings search।
- logs aur devices par global search।
- keyboard-first navigation; shortcuts overlay (?)।
- session restore: last device + page reopen।

### Linux-native feel
- native file dialogs, system theme awareness, Wayland/X11 handling।
- long ops ke liye desktop notifications; tray icon with progress।
- drag-and-drop firmware files onto flash page।

### Onboarding
- first-run wizard: udev setup, bridge build status, device test।
- illustrations + next steps wale empty states।
- per-flow docs from `operations/` ka contextual help drawer।

### Branding assets
- new logo set, splash, installer graphics, app icon।
- README screenshots refreshed to match new UI।

## Phase 9 — Console / terminal redesign (नया)
### लक्ष्य (Goal)
Log console ko cramped text box ki jagah first-class Linux terminal (UEFI-shell/TTY aesthetic) banana।

### Layout
- horizontal splitter mein dedicated **right-hand** dock (pages left, console right); resizable, collapsible to thin bar। Default width 420px, minimum 360px (dock ke own control row se measured so nothing clip ho)।
  _Decision (user): console right par rahega — is phase ke earlier draft ne "bottom dock / 35% height" bola; superseded._
- wide, monospace terminal with comfortable padding (16px), line height 1.45।
- optional full-screen terminal mode (F11) minimal chrome ke saath।
- per-device tabs ya filter chips taaki logs interleave na hon।

### Styling
- dark TTY palette: black background, green/amber/cyan text, subtle scanline optional।
- bridge output ke liye ANSI color support; bold headers, dim timestamps।
- line numbers / timestamps toggle।
- selection + copy; right-click menu (copy, save, clear, filter)।

### Behavior
- streaming with backpressure; 10k+ lines par koi UI freeze nahi।
- regex search, highlight matches, jump next/prev।
- file export; auto-save session log।
- device filter and level filter (info/warn/error/step)।

### Not squeezed
- minimum width/height constraints; responsive wrapping; long lines ke liye horizontal scroll।
- timestamp/level/device ke resizable columns।

## Phase 10 — Console messages & toast system (नया)
### Console messages
- structured log entries: timestamp, device key, level, message।
- color-coded levels: info (slate), success (green), warn (amber), error (red), step (cyan)।
- collapsible multi-line output (stack traces, JSON) with “show more”।
- flashing steps ke inline progress bars; per-step status icons।
- clickable device keys focus device; clickable flow keys open docs।

### Toasts
- non-blocking, stacked toasts with icon, title, message, action button।
- auto-dismiss with progress bar; hover par pause।
- severity styles (info/success/warn/error) consistent palette ke saath।
- queue cap (max 3 visible) overflow counter ke saath।
- position options (top-right/bottom-right) aur reduced-motion support।
- errors ke optional sound/haptic।

## Phase 12 — HiProTool parity research (नया)
### Status
- is environment mein online search unavailable (HTTP 402)। Manual research required।

### Research tasks
- HiProTool feature list collect karo (FRP, MDM, screen lock, carrier, IMEI, flashing)।
- har method ko engine map karo (ADB, download mode, BROM, EDL, fastboot, SPD)।
- device-specific shortcuts aur prerequisites identify karo।
- verification steps aur safety notes ke saath `operations/` mein document karo।
- high-value, low-risk methods pehle prioritize karo।

## Phase 14 — Next features (नया)
### Target features
- IMEI blacklist removal (research + device-specific playbooks)।
- carrier unlock improvements (SIM lock, NVDATA/QCN paths)।
- MDM unlock improvements (device owner, QR provisioning, recovery)।
- FRP improvements (per-chip/per-Android-version methods)।
- screen lock removal improvements (ADB, recovery, download, EDL)।
- Samsung Knox Guard removal (EXPERIMENTAL, audit-logged)।
- Apple MDM enrollment removal (profile/DEP)।
- Samsung Knox management tools।
- Android Enterprise enrollment handling।
- zero-touch enrollment handling।
- Apple Activation Lock removal (checkm8/DFU scope, honest limits)।
- SIM PUK retrieval SIM PIN unlock ke liye।
- biometric lock removal (research, device limits)।

### Notes
- har feature Rust-backed aur risky hone par EXPERIMENTAL gated hona chahiye।
- verification aur safety notes ke saath `operations/` mein document karen।

## Phase 15 — Documentation audit & cleanup (नया)
### Stale references found (historical/retired)
- `operations/*/README.md` retired Python modules (`knox.py`, `qcn.py`, `health.py`, `apple.py`, `flows/*.py`) mention karte hain as context; acceptable but clearly marked historical hona chahiye।
- `INDEX.md` ne pehle missing `SPLIT_PLAN.md` reference kiya (fixed)।
- `README.md` repository layout ne pehle nonexistent modules listed kiye (fixed)।
- `DESCRIPTION.md` transport/job counts wrong the (fixed)।

### Remaining doc tasks
- normalize all “retired” notes into single “History” section per file।
- har operations README ke top par “Current architecture” note add karen।
- obsolete migration plans remove/archive karen (DESIGN.md → new version)।
- `operations/` research-only rakhen; code pointers `src/flows.rs` hone chahiye।
