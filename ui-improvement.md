# FlashPilot Intensive UI Improvement Plan

## Goal
Transform the PyQt6 GUI from a functional monolith into a polished, maintainable, high-performance workbench while preserving all Rust-backed flows and multi-device behavior.

## Current state
- `python/gui/qt_app.py` (~15k LOC) is a single monolithic window.
- Theme system (`theme.py`) is centralized but QSS is large and duplicated in places.
- Connection bar, nav rail, per-chip pages, console, settings all in one file.
- Strong visual identity already exists (glass cards, 10 accents, cable scene).

## Principles
1. No protocol logic in Python; UI only renders and calls bridge.
2. Keep Rust as source of truth for flows/jobs/modes.
3. Improve responsiveness: move heavy work off UI thread, reduce widget churn.
4. Accessibility: keyboard navigation, focus rings, screen-reader labels.
5. Maintainability: split qt_app.py into feature modules.



## Phase 0 — Window shell, logo, splash (new)
- Replace current logo with a professional vector/SVG mark (monochrome + accent variants, 16/32/64/128/256px + .ico/.icns).
- Splash screen: animated brand mark, progress stages (init Rust bridge, scan devices, load theme), version, no flicker; fade-in/out 200ms.
- Window rendering: frameless translucent window with compositor-friendly alpha, rounded corners, drop shadow, DPI-aware scaling, multi-monitor placement memory.
- Smoothness: enable Qt AA_UseHighDpiPixmaps, set surface format (OpenGL/RGBA), vsync-friendly animations, reduce layout thrash; target 60fps interactions.
- Branding: consistent logo in title bar, taskbar, about dialog, installer.
- Resizable shell columns: the **device panel | page** boundary is a draggable
  horizontal splitter (default 232px, draggable 228–420px, remembered in
  `layout/device_panel_width`). The page keeps its own natural width and lives
  in a frame-less scroll area, so squeezing it scrolls sideways instead of
  reflowing its tabs/grid; the panel width is held across window resizes until
  the user drags it. _Decision (user): previously a hard `setFixedWidth(232)`._

## Phase 1 — Architecture split (no visual change)
- Extract page builders into `python/gui/pages/`:
  - `samsung.py`, `mtk.py`, `qc.py`, `spd.py`, `battery.py`, `network.py`, `settings.py`, `quick.py`.
- Extract shared widgets into `python/gui/widgets/`: `metric_card.py`, `collapsible.py`, `console.py`, `device_picker.py`.
- Keep `qt_app.py` as shell: window chrome, nav, routing, signals.
- Acceptance: app boots, all tabs render, tests pass.

## Phase 2 — Performance
- Virtualize device list and console log (QAbstractListModel + QListView) to avoid O(n) widget creation.
- Batch log updates (flush every 50ms or 100 lines).
- Cache rendered QSS per theme; regenerate only on accent change.
- Lazy-load heavy pages (build on first visit).
- Acceptance: 10k log lines without UI stall; scroll stays 60fps.

## Phase 3 — Visual polish
- Design tokens: spacing scale (4/8/12/16/24), radius scale, elevation.
- Consistent card elevation/shadow; hover/focus states.
- Motion: page fade 120ms, button press scale, toast slide.
- Icon system: replace emoji with SVG icons (brand glyphs).
- Empty states and skeletons for device detection.
- High-contrast mode + reduced-motion toggle.

## Phase 4 — UX flows
- Unified device picker dialog with search/filter and transport badges.
- Operation progress: step list with checkmarks, ETA, cancel per device.
- Error presentation: actionable cards with “retry / open docs / copy log”.
- Settings: searchable, grouped, with reset-to-defaults.
- Console: filter by level/device, export, find.

## Phase 5 — Accessibility & i18n
- Full Tab order, visible focus, ARIA-like labels.
- Keyboard shortcuts documented in-app.
- String extraction for translations (no hardcoded user strings in widgets).

## Phase 6 — Testing
- GUI smoke tests with pytest-qt (headless).
- Visual regression screenshots for each page/theme.
- Performance benchmarks for log/device rendering.

## Deliverables
- `python/gui/pages/*`, `python/gui/widgets/*`
- Updated `theme.py` token system
- `tests/test_gui_smoke.py`
- Docs update in README/INDEX.

## Risks
- 15k LOC monolith; incremental extraction required.
- PyQt threading rules; keep all widget touches on main thread.
- Preserve multi-device scoping and cancel semantics.

## Suggested first task
Extract `_build_console` and `_build_conn_bar` into `widgets/console.py` and `widgets/connection_bar.py` with signal-based API; no behavior change.

## Phase 7 — Flow & Job Rendering (new)
### Problems observed
- `_add_job_flows` flattens all modes into one button list per job; mode is only in tooltip, causing confusion.
- Duplicate buttons across pages (Quick, chip ops sections, Unlock tabs) with inconsistent gating.
- Experimental/destructive buttons only distinguished by color/border; no legend.
- No search/filter, no recently used, no favorites.
- Long flow labels overflow/wrap unpredictably in FlowLayout.
- No visual grouping by risk (read-only vs flash vs experimental).

### Proposed rendering model
- **Job → Mode → Method** three-level navigation:
  - Left: Job list (verb-first, icons).
  - Middle: Mode tabs (ADB, MTP, …) with counts.
  - Right: Method cards (name, risk badge, experimental badge, tooltip).
- Single source of truth: `core.modes_for` / `core.methods_for`; no duplicate lists in pages.
- Deduplicate by (job, mode, key) globally; chip pages filter by supported modes instead of re-running `_add_job_flows`.
- Method card states: enabled/disabled by device capability gates, running (spinner), last result (ok/fail).

### What to move
- Move button construction from `_add_job_flows` into `widgets/flow_button.py` + `widgets/method_card.py`.
- Move mode/job enumeration into a `FlowRegistryView` model (thin, no logic) for UI binding.
- Move destructive/experimental confirm logic into a reusable `ConfirmDialog`.

### What to merge
- Merge Quick page and chip ops pages to use the same `FlowBrowser` widget with a `modes` filter.
- Merge experimental warning handling into card badge + dialog.

### What to remove / deduplicate
- Remove per-page `_add_job_flows` calls that duplicate the same job flows; replace with filtered `FlowBrowser`.
- Remove duplicate `Flow` instances (same key under multiple modes) by grouping modes on the card.
- Remove raw `QLabel(job.upper())` headers in favor of section headers with counts.

### New features
- Search box filters by job/mode/method name and key.
- Favorites/recents persisted in settings.
- Risk legend: read-only (green), medium (amber), high (red), experimental (dashed amber).
- Batch selection: checkboxes to queue multiple methods (run sequentially with per-step cancel).
- Drag-to-reorder favorites.

### Acceptance
- One consistent flow browser across all pages.
- No duplicate method buttons for the same (job, mode, key).
- Search filters in <50ms for 280 rows.
- Capability gates visually disable methods with reason tooltip.

### Phase 7 — status (implemented so far)
- **Chosen shape: in-page upgrade.** Introduce the single rendering path now
  and upgrade it in place — `FlowBrowser` (view) + `MethodCard` (button) +
  `flow_meta` (routing/risk) — *without* the Job → Mode → Method three-pane
  navigation yet. Pages keep their current layout; `_add_job_flows` builds
  rows and renders them through `FlowBrowser`, and clicks route through
  `flow_meta.route_for`.
- **Derived risk model** (`flow_meta.risk_for`, the only source a badge may
  read): `experimental` = key in `_EXPERIMENTAL_FLOW_MAP`; `high` = key in
  `_DESTRUCTIVE_CONFIRM` and therefore **exactly the flows the UI already asks
  to confirm** (a badge can never claim `high` without a dialog, nor `read`
  without being read-only); `read` = only for `READ_ONLY_JOBS`
  (`{"Read Device Info", "Detect Devices"}`); everything else, including
  unknown keys/jobs, fails closed to `medium`.
- **Slice B1 — grouped flow rendering (this slice).** `FlowBrowser.set_rows`
  now groups what it renders, fixing the three named problems:
  - Job header is now `{"REMOVE FRP"} · 6` — the raw `QLabel(job.upper())`
    gained a method **count** (dimmed with the `border_hi` token, name keeps
    the existing 11px / 800 / 1px treatment).
  - Within each job, cards are grouped by **transport mode** behind a small
    mode sub-heading (`— ADB`), instead of one flat per-job list with the mode
    only in the tooltip. Rows arrive mode-major from `_flow_rows`, so a run of
    equal modes is one section; no mode is ever expanded into extra cards.
  - Every `MethodCard` paints a semantic **left edge** (`ok` read-only, `warn`
    medium, `err` high, `experimental` experimental) composed over
    `_btn_ghost()`, so risk is visible at a glance alongside the existing
    legend. Experimental cards keep their amber **dashed** border — now owned
    by `MethodCard.set_risk(level)`; `set_state` stays inert.
  - Unchanged by construction: the rendered row set, the dedupe rule ("first
    mode wins" per job), button text (`btn_sha`), every tooltip string, click
    routing, the confirm/experimental overlays, and the gate registry
    (`job=`/`mode=`, never `command=`). Only grouping/label widgets were added.
- **Golden regenerated deliberately here.** `tests/ui_inventory_golden.json`
  was rebuilt with `REGEN_INVENTORY=1` in this slice. The **only** diff is the
  per-page **widget count** (the added mode sub-heading labels; +113 widgets
  across the five flow-heavy pages). `gated_count`, `gated_unique_triples`,
  `gated_triples_sha256`, `core_flows`, `action_meta`, and every page's
  `buttons` / `acts` / `btn_sha` are byte-identical — the gate registry and the
  click surface did not move.
- **Slice B2 — device model board (vertical action cards) (this slice).** The
  model page's per-action rows are now `ActionRow` cards
  (`python/gui/widgets/action_row.py`) instead of the 50px hand-rolled
  `QFrame` with a monkeypatched `mousePressEvent`:
  - a **3px semantic left edge** (`err` for wipe/destructive actions, else
    `accent_hi`) — the same risk-edge language `MethodCard.set_risk` paints in
    the flow browser,
  - a **40x40 icon tile**, a **13px / 800** title and a **one-line elided**
    description. This fixes the plan's "long flow labels overflow / wrap
    unpredictably": the description ellipsises instead of wrapping, so a long
    label can never force the board wider than its pane nor read as a ragged
    multi-line block,
  - an optional engine/mode **chip** and a dim **`›` chevron**; hover /
    pressed / focus are owned by the widget (QSS dynamic property + focus
    ring). The chip is painted as a **single-hue pill** from the accent colour
    `common._mode_chip` already returns (accent tint fill, accent text, accent
    hairline border), so every badge reads as one family,
  - **keyboard reachable** — `StrongFocus` + Enter / Return / Space emit the
    `activated` signal (replacing the monkeypatched `mousePressEvent`). The
    board keeps its `flow_act` / `flow_tip` tags and just connects `activated`,
    so routing is unchanged,
  - group containers now carry the job's action **count** (`FRP REMOVE · 4`) —
    the same name + count language the flow browser's job headers use.
- **Invariants held.** `_ACTION_META` is still **62** entries; every `dev_*`
  page's `acts` and `btn_sha` are byte-identical (no action row, button text or
  button was added / removed / renamed); `gated_count` **418**,
  `gated_triples_sha256` `c89acce…7d75`, `gated_unique_triples` **61**,
  `core_flows` **116**, `stack_count` **25**. The page stack's natural minimum
  width is still **699px**, proving the elided labels widened nothing.
- **Golden regenerated deliberately here.** `tests/ui_inventory_golden.json`
  was rebuilt with `REGEN_INVENTORY=1` in this slice: the only diff is the
  per-page **widget count** (`dev_apple` 59→63, `dev_motorola` 85→99 — the two
  researched boards' added cards/labels). The transient golden md5 after B2 was
  `929f428638e91a42865ddde1ac96dd19`. The follow-up polish of this document
  slice (the single-hue chip family and the first-show device-panel split)
  changed **no** page widget count, so the golden needed **no** further regen.
- **Slice B4 — model board fills the page height (this slice).** On the
  device → model board (`devices.build_brand_page`) the two-pane split row did
  not get the page's height, so a big empty band was left **below** both panes.
  At a 1600x951 window (outer page viewport `878x717`) the panes measured
  `left 250x313 / right 598x333` with a **333px dead band** underneath, and the
  action board got only `333` of `717`px. Root cause: the split row was added to
  `outer` **with stretch 1** *and* a trailing `outer.addStretch(1)` was added
  right after it — the two stretched items split the leftover vertical space
  ~50/50, and neither pane was vertically `Expanding`, so nothing absorbed it.
  Fix (surgical, in `build_brand_page` only): drop the competing trailing
  stretch (the split row now takes **all** the leftover height) and give the
  left `list_col` and the right `right_stack` an explicit vertical `Expanding`
  policy, so the inner `lscroll` and the current model page's inner `_scroll`
  receive the full height and own their own scrollbars. The left rows stay
  top-aligned (`lv2.addStretch(1)` is untouched) and scroll when the list grows.
  After: `left 250x646 / right 598x665`, dead band **1px** (only the layout's
  8px bottom margin), the right board shows far more flows and scrolls the rest
  internally (`vscroll_max` 900 → 557), and the shell's outer `_page_scroll`
  stays hidden (`verticalScrollBar().maximum() == 0`). Backing the user's future
  requirement, 40 extra in-memory models grow the **left** list's scroll range
  (`vscroll_max > 0`) with **no** change to either pane's height.
  - New tests: `tests/test_device_board_layout.py` —
    `TestBrandPageFillsHeight::test_no_dead_band_below_split`,
    `::test_both_panes_get_the_real_height`,
    `::test_right_board_scrolls_its_own_content`,
    `::test_more_devices_scroll_left_without_growing_the_panes`. Both geometry
    tests were confirmed to **fail** on the unfixed code first (dead band 295px
    at H=640; left pane 275px vs the 412px floor) before the fix.
  - **No widget was added or removed** (only a size policy changed and a stretch
    spacer was dropped), so no page's widget count moved and
    `tests/ui_inventory_golden.json` needed **no** regen — still
    `929f428638e91a42865ddde1ac96dd19`.
- **Slice C — full flow registry on the device board (REVERTED).**
  This slice added a final `MORE FLOWS · N` group rendering the device engine's
  complete flow registry as `ActionRow` cards, plus a text/mode filter bar. It
  was scoped by **engine + transport mode**, which is not the same as *this
  device's functions*: any phone exposing ADB therefore pulled in every
  ADB-registered flow in the registry, so the Motorola board offered
  Samsung-only jobs (`knox_bypass`, `kg_remove`, `odin_flash_tar`),
  `imei_repair_spd`, `apple_icloud_*` and `huawei_frp_guide`. Worse, the
  Motorola models carry **per-model engines** (`Moto G13` = `spd`, `G24` =
  `mtk`, `G6` = `qcom`), so `planned` models showed an entire SPD/MTK registry
  for work that has not been done, and the motorola/apple brands bypass the
  `researched` gate on the board by design. Reverted in full: the registry
  group, its filter bar, `_ENGINE_MODES`, the first-show deferral and
  `tests/test_device_flows.py` are gone; the board is again exactly the
  per-device curated actions. The inventory golden was byte-identical
  throughout (`929f428638e91a42865ddde1ac96dd19`) because the group was built
  lazily, so the revert needs no regen either.
  - Lesson for any re-attempt: scope by **the model's own declared `actions`**
    (`supported_devices.json`), expanding only the flows those actions really
    dispatch to — never by engine + mode.
  - Vetted fact that survives and is reusable: `win._route_flow_activation(job,
    mode, key, label)` is the only sink that applies the destructive confirm
    and the EXPERIMENTAL ownership ack; `_dispatch`/`start_model_action` is not
    (its experimental check is the narrow `devices._EXPERIMENTAL_ACTS` set, so
    e.g. `emmc_raw` would run unacknowledged).
- **Deferred (still):** search box / mode filter chips over a per-device flow
  list, favourites/recents
  (settings-persisted), the batch selection queue (checkboxes + sequential
  run), drag-to-reorder, the Job → Mode → Method three-pane navigation,
  expanding a job's mode variants into extra cards (one card per
  `(job, mode, key)` is a deliberate later decision — this slice does NOT
  expand modes), and a reusable `ConfirmDialog` (the confirm/experimental
  overlays remain window-owned modals).

## Phase 8 — Professional polish & differentiation (new)
### Visual identity
- Signature “atelier” dark theme with subtle grain/noise texture and soft vignette.
- Brand mark + monogram; consistent iconography (Lucide-style) across all actions.
- Device hero cards: model image silhouette, chip, transport badges, last-seen.
- Animated connection scene upgraded: real cable pulse, per-device status dots.

### Information density
- Collapsible inspector panel: selected device details, partitions, PIT summary, logs.
- Timeline view of operations (start/end, duration, result) per device.
- Diff view for PIT/partition changes before flash.

### Safety & trust
- Pre-flight checklist card before destructive ops (device, firmware, PIT match).
- Clear risk ladder with color + icon + text; never color-only.
- Audit log viewer (experimental actions) with export.

### Productivity
- Command palette (Ctrl+K) to search flows, devices, settings.
- Global search across logs and devices.
- Keyboard-first navigation; shortcuts overlay (?).
- Session restore: reopen last device + page.

### Linux-native feel
- Native file dialogs, system theme awareness, Wayland/X11 handling.
- Desktop notifications for long ops; tray icon with progress.
- Drag-and-drop firmware files onto flash page.

### Onboarding
- First-run wizard: udev setup, bridge build status, device test.
- Empty states with illustrations and next steps.
- Contextual help drawer with per-flow docs from `operations/`.

### Branding assets
- New logo set, splash, installer graphics, app icon.
- README screenshots refreshed to match new UI.

## Phase 9 — Console / terminal redesign (new)
### Goal
Make the log console feel like a first-class Linux terminal (UEFI-shell/TTY aesthetic) instead of a cramped text box.

### Layout
- Dedicated **right-hand** dock in a horizontal splitter (pages left, console
  right); resizable, collapsible to a thin bar. Default width 420px, minimum
  360px (measured from the dock's own control row so nothing can clip).
  _Decision (user): the console stays on the right — an earlier draft of this
  phase said "bottom dock / 35% height"; that is superseded._
- Wide, monospace terminal with comfortable padding (16px), line height 1.45.
- Optional full-screen terminal mode (F11) with minimal chrome.
- Per-device tabs or filter chips so logs don’t interleave.

### Styling
- Dark TTY palette: black background, green/amber/cyan text, subtle scanline optional.
- ANSI color support for bridge output; bold headers, dim timestamps.
- Line numbers / timestamps toggle.
- Selection + copy; right-click menu (copy, save, clear, filter).

### Behavior
- Streaming with backpressure; no UI freeze on 10k+ lines.
- Search with regex, highlight matches, jump next/prev.
- Export to file; auto-save session log.
- Device filter and level filter (info/warn/error/step).

### Not squeezed
- Minimum width/height constraints; responsive wrapping; horizontal scroll for long lines.
- Resizable columns for timestamp/level/device.

## Phase 10 — Console messages & toast system (new)
### Console messages
- Structured log entries: timestamp, device key, level, message.
- Color-coded levels: info (slate), success (green), warn (amber), error (red), step (cyan).
- Collapsible multi-line output (stack traces, JSON) with “show more”.
- Inline progress bars for flashing steps; per-step status icons.
- Clickable device keys to focus device; clickable flow keys to open docs.

### Toasts
- Non-blocking, stacked toasts with icon, title, message, action button.
- Auto-dismiss with progress bar; pause on hover.
- Severity styles (info/success/warn/error) with consistent palette.
- Queue cap (max 3 visible) with overflow counter.
- Position options (top-right/bottom-right) and reduced-motion support.
- Sound/haptic optional for errors.


## Phase 12 — HiProTool parity research (new)
### Status
- Online search unavailable in this environment (HTTP 402). Manual research required.

### Research tasks
- Collect HiProTool feature list (FRP, MDM, screen lock, carrier, IMEI, flashing).
- Map each method to an engine (ADB, download mode, BROM, EDL, fastboot, SPD).
- Identify device-specific shortcuts and prerequisites.
- Document in `operations/` with verification steps and safety notes.
- Prioritize high-value, low-risk methods first.


## Phase 14 — Next features (new)
### Target features
- IMEI blacklist removal (research + device-specific playbooks).
- Carrier unlock improvements (SIM lock, NVDATA/QCN paths).
- MDM unlock improvements (device owner, QR provisioning, recovery).
- FRP improvements (per-chip/per-Android-version methods).
- Screen lock removal improvements (ADB, recovery, download, EDL).
- Samsung Knox Guard removal (EXPERIMENTAL, audit-logged).
- Apple MDM enrollment removal (profile/DEP).
- Samsung Knox management tools.
- Android Enterprise enrollment handling.
- Zero-touch enrollment handling.
- Apple Activation Lock removal (checkm8/DFU scope, honest limits).
- SIM PUK retrieval to unlock SIM PIN.
- Biometric lock removal (research, device limits).

### Notes
- Each feature must be Rust-backed and gated as EXPERIMENTAL where risky.
- Document in `operations/` with verification and safety notes.

## Phase 15 — Documentation audit & cleanup (new)
### Stale references found (historical/retired)
- `operations/*/README.md` mention retired Python modules (`knox.py`, `qcn.py`, `health.py`, `apple.py`, `flows/*.py`) as context; acceptable but should be clearly marked historical.
- `INDEX.md` previously referenced missing `SPLIT_PLAN.md` (fixed).
- `README.md` repository layout previously listed nonexistent modules (fixed).
- `DESCRIPTION.md` had wrong transport/job counts (fixed).

### Remaining doc tasks
- Normalize all “retired” notes into a single “History” section per file.
- Add a “Current architecture” note at top of each operations README.
- Remove or archive obsolete migration plans (DESIGN.md → new version).
- Keep `operations/` as research-only; code pointers must say `src/flows.rs`.
