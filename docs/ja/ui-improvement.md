# FlashPilot 集中的 UI 改善計画

Language switcher: [English](../../ui-improvement.md) · [Français](../fr/ui-improvement.md) · [Español](../es/ui-improvement.md) · [Deutsch](../de/ui-improvement.md) · [简体中文](../zh/ui-improvement.md) · [Русский](../ru/ui-improvement.md) · [Português](../pt/ui-improvement.md) · **日本語** · [العربية](../ar/ui-improvement.md) · [हिन्दी](../hi/ui-improvement.md) · [Türkçe](../tr/ui-improvement.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 目標
すべての Rust-backed flows と multi-device behavior を保ちながら、PyQt6 GUI を機能的な monolith から、磨き上げられた、保守しやすく、高性能な workbench へ変革する。

## 現在の状態
- `python/gui/qt_app.py`（約 15k LOC）は単一の monolithic window。
- テーマシステム（`theme.py`）は集中管理されているが、QSS は大きく、場所によって重複がある。
- 接続バー、ナビゲーション rail、チップごとのページ、コンソール、設定がすべて同一ファイルにある。
- 強いビジュアルアイデンティティは既に存在する（ガラスカード、10 のアクセントカラー、ケーブルシーン）。

## 原則
1. Python にプロトコルロジックは入れない。UI はレンダリングし、bridge を呼び出すだけ。
2. flows/jobs/modes の truth source は Rust を維持する。
3. レスポンシブネス改善: 重い処理を UI スレッドから外し、widget churn を減らす。
4. アクセシビリティ: キーボードナビゲーション、focus ring、スクリーンリーダーラベル。
5. 保守性: `qt_app.py` を機能モジュールに分割する。



## Phase 0 — ウィンドウシェル、ロゴ、スプラッシュ（新規）
- 現在のロゴを、プロフェッショナルなベクター/SVG マークに置き換える（monochrome + アクセント variants、16/32/64/128/256px + `.ico`/`.icns`）。
- スプラッシュスクリーン: アニメーション付き brand mark、進捗ステージ（Rust bridge の初期化、デバイススキャン、テーマ読み込み）、バージョン、flicker なし。fade-in/out 200ms。
- ウィンドウレンダリング: compositor-friendly な alpha を持つ frameless translucent window、角丸、drop shadow、DPI-aware scaling、multi-monitor での配置記憶。
- スムーズネス: Qt `AA_UseHighDpiPixmaps` を有効化、surface format を設定（OpenGL/RGBA）、vsync-friendly な animation、layout thrash の削減。target 60fps interactions。
- ブランディング: title bar、taskbar、about dialog、installer で一貫したロゴ。
- 調整可能なシェル列: **device panel | page** の境界は、ドラッグ可能な水平 splitter（デフォルト 232px、ドラッグ範囲 228–420px、`layout/device_panel_width` に記憶）。ページは自然幅を保ち、frame-less scroll area に置かれるため、圧縮してもタブ/グリッドを reflow するのではなく横スクロールする。user がドラッグするまで panel 幅は window resize 跨いで保持される。_Decision (user): 従来はハードコードの `setFixedWidth(232)`。_

## Phase 1 — アーキテクチャ分割（視覚変更なし）
- ページ builder を `python/gui/pages/` に抽出:
  - `samsung.py`, `mtk.py`, `qc.py`, `spd.py`, `battery.py`, `network.py`, `settings.py`, `quick.py`。
- 共有 widgets を `python/gui/widgets/` に抽出: `metric_card.py`, `collapsible.py`, `console.py`, `device_picker.py`。
- `qt_app.py` は shell として維持: window chrome、nav、routing、signals。
- Acceptance: アプリが起動し、すべての tab がレンダリングされ、tests が pass。

## Phase 2 — パフォーマンス
- デバイス一覧とコンソールログを virtualize（`QAbstractListModel` + `QListView`）し、O(n) の widget 作成を避ける。
- ログ更新を batch（50ms または 100 行ごとに flush）。
- テーマごとにレンダリング済み QSS を cache。アクセント変更時のみ再生成。
- 重いページを lazy-load（初回 visit 時に build）。
- Acceptance: 10k ログ行で UI stall なし。スクロールは 60fps を維持。

## Phase 3 — ビジュアルポリッシュ
- デザイントークン: spacing scale（4/8/12/16/24）、radius scale、elevation。
- 一貫した card elevation/shadow。hover/focus states。
- Motion: page fade 120ms、button press scale、toast slide。
- Icon system: emoji を SVG icons（brand glyphs）に置き換え。
- デバイス検出の empty states と skeleton。
- High-contrast mode + reduced-motion toggle。

## Phase 4 — UX flows
- search/filter と transport badges を持つ unified device picker dialog。
- 操作 progress: checkmark 付きステップリスト、ETA、device ごとの cancel。
- エラー表示: “retry / open docs / copy log” を持つ actionable cards。
- Settings: searchable、grouped、reset-to-defaults 付き。
- Console: level/device で filter、export、find。

## Phase 5 — アクセシビリティ & i18n
- 完全な Tab order、可視 focus、ARIA-like labels。
- アプリ内で文書化された keyboard shortcuts。
- 翻訳のための string extraction（widgets に hardcoded user strings なし）。

## Phase 6 — テスト
- pytest-qt による GUI smoke tests（headless）。
- ページ / テーマごとの visual regression screenshots。
- ログ / デバイスレンダリングの performance benchmarks。

## Deliverables
- `python/gui/pages/*`, `python/gui/widgets/*`
- 更新された `theme.py` トークンシステム
- `tests/test_gui_smoke.py`
- README/INDEX の docs 更新。

## Risks
- 15k LOC monolith。incremental extraction が必要。
- PyQt threading rules。すべての widget touches は main thread に保つ。
- multi-device scoping と cancel semantics を保つ。

## Suggested first task
`_build_console` と `_build_conn_bar` を `widgets/console.py` と `widgets/connection_bar.py` に抽出し、signal-based API にする。behavior change なし。



## Phase 7 — Flow & Job Rendering（新規）
### 観察された問題
- `_add_job_flows` はすべての modes を 1 つの job につき 1 つの button list に flatten する。mode は tooltip にしかなく、混乱を招く。
- ページ間でボタンが重複（Quick、chip ops sections、Unlock tabs）、gating が不一致。
- experimental/destructive ボタンは color/border だけで区別; legend なし。
- search/filter なし、recently used なし、favorites なし。
- 長い flow labels が `FlowLayout` で unpredictable に overflow/wrap。
- リスク別の visual grouping なし（read-only vs flash vs experimental）。

### 提案レンダリングモデル
- **Job → Mode → Method** 3 レベルナビゲーション:
  - 左: Job list（verb-first、icons）。
  - 中央: Mode tabs（ADB, MTP, …）に counts。
  - 右: Method cards（name、risk badge、experimental badge、tooltip）。
- 単一の truth source: `core.modes_for` / `core.methods_for`。pages に duplicate lists なし。
- `(job, mode, key)` で global に dedupe。chip pages は `_add_job_flows` を再実行するのではなく supported modes で filter。
- Method card states: device capability gates による enabled/disabled、running（spinner）、last result（ok/fail）。

### What to move
- button construction を `_add_job_flows` から `widgets/flow_button.py` + `widgets/method_card.py` へ移動。
- mode/job enumeration を `FlowRegistryView` model（thin、logic なし）へ移動し、UI binding 用に。
- destructive/experimental confirm logic を reusable `ConfirmDialog` へ移動。

### What to merge
- Quick page と chip ops pages を、同一 `FlowBrowser` widget + `modes` filter を使うように merge。
- experimental warning handling を card badge + dialog に merge。

### What to remove / deduplicate
- 同じ job flows を duplicate する per-page `_add_job_flows` 呼び出しを remove。filtered `FlowBrowser` に置き換え。
- duplicate `Flow` instances（同一 key が複数 modes 下にある）を remove。cards 上で modes を grouping。
- raw `QLabel(job.upper())` headers を、counts 付き section headers に置き換え。

### New features
- search box が job/mode/method name と key で filter。
- Favorites/recents を settings に persist。
- risk legend: read-only（green）、medium（amber）、high（red）、experimental（dashed amber）。
- batch selection: 複数 methods を queue する checkboxes（sequential run、per-step cancel）。
- drag-to-reorder favorites。

### Acceptance
- すべての pages で 1 つの consistent flow browser。
- 同一 `(job, mode, key)` の duplicate method buttons なし。
- 280 rows の search filter <50ms。
- capability gates は理由 tooltip で method を visually disable。

### Phase 7 — status（実装済み分）
- **Chosen shape: in-page upgrade.** single rendering path を今導入し、その場で upgrade する——`FlowBrowser`（view）+ `MethodCard`（button）+ `flow_meta`（routing/risk）——**まだ** Job → Mode → Method 3-pane navigation なし。pages は current layout を維持。`_add_job_flows` が rows を build し `FlowBrowser` 経由で render、clicks は `flow_meta.route_for` 経由で route。
- **Derived risk model**（`flow_meta.risk_for`、badge が唯一 read できる source）: `experimental` = key が `_EXPERIMENTAL_FLOW_MAP` にある; `high` = key が `_DESTRUCTIVE_CONFIRM` にある、つまり UI が **すでに confirm を要求する flows と正確一致**（badge は dialog なしで `high` を主張できないし、read-only でないのに `read` を主張できない）; `read` = `READ_ONLY_JOBS` のみ（`{"Read Device Info", "Detect Devices"}`）; その他すべて、unknown keys/jobs を含め、fail closed で `medium`。
- **Slice B1 — grouped flow rendering（本 slice）。** `FlowBrowser.set_rows` は now render するものを group し、named problems 3 つを修正:
  - Job header は今や `{"REMOVE FRP"} · 6`——raw `QLabel(job.upper())` に method **count** を追加（`border_hi` token で dim、name は既存の 11px / 800 / 1px treatment を維持）。
  - 各 job 内で、cards は small mode sub-heading（`— ADB`）の背後で **transport mode** ごとに group される。tooltip にしか mode がない 1 つの flat per-job list ではなくなった。rows は `_flow_rows` から mode-major で到着するため、equal modes の run は 1 section。mode が extra cards に expand されることがない。
  - すべての `MethodCard` は `_btn_ghost()` 上に semantic **left edge** を描く（`ok` read-only、`warn` medium、`err` high、`experimental` experimental）ので、risk は existing legend と並んで at a glance visible。experimental cards は amber **dashed** border を維持——今や `MethodCard.set_risk(level)` に owned; `set_state` は inert のまま。
  - construction 上 unchanged: rendered row set、dedupe rule（job ごと “first mode wins”）、button text（`btn_sha`）、すべての tooltip string、click routing、confirm/experimental overlays、gate registry（`job=`/`mode=`、決して `command=`）。grouping/label widgets のみ追加。
- **Golden regenerated deliberately here.** 本 slice では `REGEN_INVENTORY=1` で `tests/ui_inventory_golden.json` を rebuild。**唯一の** diff は per-page **widget count**（added mode sub-heading labels; 5 flow-heavy pages で +113 widgets）。`gated_count`, `gated_unique_triples`, `gated_triples_sha256`, `core_flows`, `action_meta`, すべての page の `buttons` / `acts` / `btn_sha` は byte-identical——gate registry と click surface は動いていない。
- **Slice B2 — device model board (vertical action cards) (本 slice)。** model page の per-action rows は now `ActionRow` cards（`python/gui/widgets/action_row.py`）であり、monkeypatched `mousePressEvent` 付きの 50px 手組み `QFrame` ではない:
  - **3px semantic left edge**（wipe/destructive actions は `err`、それ以外は `accent_hi`）——flow browser の `MethodCard.set_risk` が paint するのと同じ risk-edge language,
  - **40x40 icon tile**、**13px / 800** title、**one-line elided** description。これにより plan の “long flow labels overflow / wrap unpredictably” を修正: description ellipsises し wrap しないので、long label が pane より board を広げることはなく、ragged multi-line block としても読めない,
  - optional engine/mode **chip** と dim **`›` chevron**; hover / pressed / focus は widget が owner（QSS dynamic property + focus ring）。chip は accent colour から `common._mode_chip` が already return する値で **single-hue pill** として paint（accent tint fill、accent text、accent hairline border）、すべての badge が 1 family になる,
  - **keyboard reachable**——`StrongFocus` + Enter / Return / Space が `activated` signal を emit（monkeypatched `mousePressEvent` を置き換え）。board は `flow_act` / `flow_tip` tags を保持し `activated` を connect するだけ、routing は変わらない,
  - group containers は now job の action **count** を carry（`FRP REMOVE · 4`）——flow browser の job headers と同じ name + count language。
- **Invariants held.** `_ACTION_META` は still **62** entries。すべての `dev_*` page の `acts` と `btn_sha` は byte-identical（action row、button text、button の add/remove/rename なし）; `gated_count` **418**、`gated_triples_sha256` `c89acce…7d75`、`gated_unique_triples` **61**、`core_flows` **116**、`stack_count` **25**。page stack の natural minimum width は still **699px**、ellided labels は何も広げていないことを証明。
- **Golden regenerated deliberately here.** 本 slice では `REGEN_INVENTORY=1` で `tests/ui_inventory_golden.json` を rebuild: 唯一の diff は per-page **widget count**（`dev_apple` 59→63、`dev_motorola` 85→99——2 つの researched boards の added cards/labels）。B2 後の transient golden md5 は `929f428638e91a42865ddde1ac96dd19`。この document slice の follow-up polish（single-hue chip family と first-show device-panel split）は page widget count を 1 つも変えなかったので、golden は **further regen 不要**。
- **Slice B4 — model board fills the page height (本 slice)。** device → model board（`devices.build_brand_page`）で two-pane split row が page height を得ず、**両 panes の下**に大きな empty band が残った。1600x951 window（outer page viewport `878x717`）で、panes は `left 250x313 / right 598x333` で下方に **333px dead band**、action board は `333` of `717`px しか得なかった。Root cause: split row が stretch 1 で `outer` に add され、**かつ** その直後に trailing `outer.addStretch(1)` が add された——2 つの stretched items が leftover vertical space を ~50/50 で split、どちらの pane も vertical `Expanding` ではなかったので何も吸収しなかった。Fix（surgical、`build_brand_page` のみ）: competing trailing stretch を drop（split row が now **all** leftover height を取る）し、left `list_col` と right `right_stack` に explicit vertical `Expanding` policy を与え、inner `lscroll` と current model page の inner `_scroll` が full height を receive し own scrollbars を持つようにする。left rows は top-aligned のまま（`lv2.addStretch(1)` untouched）、list growth 時に scroll。After: `left 250x646 / right 598x665`、dead band **1px**（layout の 8px bottom margin のみ）、right board は far more flows を表示し残りは internally scroll（`vscroll_max` 900 → 557）、shell の outer `_page_scroll` は hidden のまま（`verticalScrollBar().maximum() == 0`）。user の未来 requirement を backing し、memory 内に 40 extra models を増やすと **left** list の scroll range が grow（`vscroll_max > 0`）しても panes の height は no change。
  - New tests: `tests/test_device_board_layout.py` ——
    `TestBrandPageFillsHeight::test_no_dead_band_below_split`,
    `::test_both_panes_get_the_real_height`,
    `::test_right_board_scrolls_its_own_content`,
    `::test_more_devices_scroll_left_without_growing_the_panes`。両 geometry tests は fix 前に **fail** と confirm（H=640 で dead band 295px; left pane 275px vs 412px floor）。
  - **No widget was added or removed**（size policy が changed し stretch spacer が dropped しただけ）、なので no page の widget count が move し、`tests/ui_inventory_golden.json` は **no regen**——still `929f428638e91a42865ddde1ac96dd19`。
- **Slice C — full flow registry on the device board (REVERTED)。**
  本 slice は final に `MORE FLOWS · N` group を追加し、device engine の complete flow registry を `ActionRow` cards として render、text/mode filter bar も付いた。scope は **engine + transport mode**、これは *that device の functions* とは違う: ADB を expose する phone なら registry のすべての ADB-registered flows を pulled し、Motorola board は Samsung-only jobs（`knox_bypass`, `kg_remove`, `odin_flash_tar`）、`imei_repair_spd`, `apple_icloud_*`, `huawei_frp_guide` を offered。さらに Motorola models は **per-model engines**（`Moto G13` = `spd`, `G24` = `mtk`, `G6` = `qcom`）を持つため、`planned` models は未完了 work に対して entire SPD/MTK registry を showed、motorola/apple brands は by design board 上で `researched` gate を bypass。Reverted in full: registry group、filter bar、`_ENGINE_MODES`、first-show deferral、`tests/test_device_flows.py` は gone。board は again exactly the per-device curated actions。inventory golden は throughout byte-identical（`929f428638e91a42865ddde1ac96dd19`）、group は lazily built だったため revert は no regen。
  - re-attempt の lesson: scope by **the model's own declared `actions`**（`supported_devices.json`）、really dispatch する flows のみ expand——決して engine + mode による scope ではない。
  - reusable として生き残った vetted fact: `win._route_flow_activation(job, mode, key, label)` は唯一 destructive confirm と EXPERIMENTAL ownership ack を apply する sink。`_dispatch`/`start_model_action` ではない（experimental check は narrow な `devices._EXPERIMENTAL_ACTS` set なので、例: `emmc_raw` は unacknowledged で run）。
- **まだ deferred:** search box / mode filter chips over a per-device flow list、favourites/recents（settings-persisted）、batch selection queue（checkboxes + sequential run）、drag-to-reorder、Job → Mode → Method 3-pane navigation、expanding する job の mode variants into extra cards（each `(job, mode, key)` 1 card は deliberate later decision——本 slice は modes を expand しない）、reusable `ConfirmDialog`（confirm/experimental overlays は window-owned modals のまま）。



## Phase 8 — プロフェッショナルポリッシュ & 差別化（新規）
### ビジュアルアイデンティティ
- subtle grain/noise texture と soft vignette を持つ signature “atelier” dark theme。
- brand mark + monogram。すべての actions で consistent iconography（Lucide-style）。
- device hero cards: model image silhouette、chip、transport badges、last-seen。
- animated connection scene upgraded: real cable pulse、per-device status dots。

### 情報密度
- collapsible inspector panel: selected device details、partitions、PIT summary、logs。
- per-device の operations timeline view（start/end、duration、result）。
- flash 前の PIT/partition changes diff view。

### 安全 & 信頼
- destructive ops 前の pre-flight checklist card（device、firmware、PIT match）。
- clear risk ladder（color + icon + text、color-only ではない）。
- experimental actions の audit log viewer（export 付き）。

### 生産性
- flows、devices、settings を search する command palette（Ctrl+K）。
- logs と devices 跨ぎの global search。
- keyboard-first navigation; shortcuts overlay（?）。
- session restore: reopen last device + page。

### Linux-native feel
- native file dialogs、system theme awareness、Wayland/X11 handling。
- 長時間 ops の desktop notifications; tray icon with progress。
- firmware files の flash page への drag-and-drop。

### オンボーディング
- first-run wizard: udev setup、bridge build status、device test。
- illustrations と next steps 付き empty states。
- per-flow docs from `operations/` の contextual help drawer。

### ブランディング assets
- new logo set、splash、installer graphics、app icon。
- new UI に match する refreshed README screenshots。



## Phase 9 — コンソール / ターミナル redesign（新規）
### ゴール
log console を窮屈な text box ではなく、first-class Linux terminal（UEFI-shell/TTY aesthetic）のように感じさせる。

### Layout
- horizontal splitter 内の **right-hand** dock（pages left、console right）; resizable、thin bar に collapsible。デフォルト width 420px、minimum 360px（dock 自身の control row で measure し、nothing が clip しない）。_Decision (user): console は right に置く——本 phase の earlier draft は “bottom dock / 35% height” と言っていた; superseded。_
- wide、monospace terminal with comfortable padding（16px）、line height 1.45。
- optional full-screen terminal mode（F11）with minimal chrome。
- per-device tabs or filter chips で logs が interleave しないように。

### Styling
- dark TTY palette: black background、green/amber/cyan text、subtle scanline optional。
- bridge output の ANSI color support; bold headers、dim timestamps。
- line numbers / timestamps toggle。
- selection + copy; right-click menu（copy、save、clear、filter）。

### Behavior
- streaming with backpressure; 10k+ lines でも UI freeze なし。
- regex search、highlight matches、jump next/prev。
- export to file; auto-save session log。
- device filter と level filter（info/warn/error/step）。

### Not squeezed
- 最小 width/height constraints; responsive wrapping; 長い line の horizontal scroll。
- timestamp/level/device の resizable columns。



## Phase 10 — コンソールメッセージ & toast システム（新規）
### Console messages
- structured log entries: timestamp、device key、level、message。
- level ごとの color-coded: info（slate）、success（green）、warn（amber）、error（red）、step（cyan）。
- collapsible multi-line output（stack traces、JSON）with “show more”。
- flashing steps の inline progress bars; per-step status icons。
- device keys を clickable して device focus; flow keys を clickable して docs open。

### Toasts
- non-blocking、stacked toasts with icon、title、message、action button。
- progress bar 付き auto-dismiss; hover で pause。
- severity styles（info/success/warn/error）with consistent palette。
- queue cap（max 3 visible）with overflow counter。
- position options（top-right/bottom-right）と reduced-motion support。
- errors 用 optional sound/haptic。



## Phase 12 — HiProTool parity research（新規）
### 状態
- この環境では online search unavailable（HTTP 402）。manual research required。

### 研究タスク
- HiProTool feature list を収集（FRP、MDM、screen lock、carrier、IMEI、flashing）。
- 各 method を engine に map（ADB、download mode、BROM、EDL、fastboot、SPD）。
- device-specific shortcuts と prerequisites を identify。
- verification steps と safety notes 付きで `operations/` に document。
- high-value、low-risk methods を first priority。



## Phase 14 — Next features（新規）
### Target features
- IMEI blacklist removal（research + device-specific playbooks）。
- Carrier unlock improvements（SIM lock、NVDATA/QCN paths）。
- MDM unlock improvements（device owner、QR provisioning、recovery）。
- FRP improvements（per-chip / per-Android-version methods）。
- Screen lock removal improvements（ADB、recovery、download、EDL）。
- Samsung Knox Guard removal（EXPERIMENTAL、audit-logged）。
- Apple MDM enrollment removal（profile/DEP）。
- Samsung Knox management tools。
- Android Enterprise enrollment handling。
- Zero-touch enrollment handling。
- Apple Activation Lock removal（checkm8/DFU scope、honest limits）。
- SIM PUK retrieval to unlock SIM PIN。
- Biometric lock removal（research、device limits）。

### Notes
- 各 feature は Rust-backed で、risky な場合は EXPERIMENTAL として gated。
- verification と safety notes 付きで `operations/` に document。



## Phase 15 — Documentation audit & cleanup（新規）
### 見つかった stale references（historical/retired）
- `operations/*/README.md` は retired Python modules（`knox.py`, `qcn.py`, `health.py`, `apple.py`, `flows/*.py`）を context として mention。acceptable だが、history として clearly marked すべき。
- `INDEX.md` は previously missing `SPLIT_PLAN.md` を referenced（fixed）。
- `README.md` repository layout は previously nonexistent modules を listed（fixed）。
- `DESCRIPTION.md` は wrong transport/job counts（fixed）。

### 残った doc tasks
- すべての “retired” notes を、file ごとの single “History” section に normalize。
- 各 operations README の top に “Current architecture” note を add。
- obsolete migration plans を remove/archive（`DESIGN.md` → new version）。
- `operations/` を research-only に保つ。code pointers は `src/flows.rs` を指さなければならない。