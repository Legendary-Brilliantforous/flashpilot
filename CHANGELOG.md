# Changelog

## 1.2.4 (Advisor: Markdown, auto-suggest, named sessions, expanded RAG)

### Device detection & battery/network diagnostics (read-only, ADB)
- Apple (VID 0x05ac) devices are kept out of the generic-Android bucket, so the
  USB mode badge no longer mislabels an iPhone as "ANDROID DEVICE - …".
- Multi-phone: when both device scans come up empty, the device picker falls
  back to the DeviceMonitor's cached rows before giving up.

### MTK / BROM device wait
- Device picking for MTK / BROM-targeted operations now polls on a longer
  mode-aware budget (25 s) before giving up, so a phone that is mid
  power-cycle into BROM (Vol-key + USB plug) is given time to enumerate
  before tools refuse with "no device".
- The MTK Detect scan now polls on the same budget before reporting
  "no device".

### Battery & network diagnostics (read-only, ADB)

### AI — local FlashPilot Assistant (error, device & command awareness)
- **Error awareness**: the local assistant now grounds answers in the expanded
  failure-cause catalogue (17 known causes) and surfaces the matched cause —
  Why, Fix, Risk and the exact log line — alongside retrieved notes.
- **Device awareness**: failure/connection questions fold in live device context
  (ADB status, model, transport, mode) so "is the ADB connected?" gets a grounded reply.
- **Command awareness**: flow keys mentioned in a question are resolved against
  the real registry and near-miss commands are corrected (e.g. `frp_adb` →
  `adb_frp`).
- **Wiring**: the Ask Assistant action feeds the live console tail, selected
  device and flow registry into the local answer.

### Battery & network diagnostics (read-only, ADB)
- Battery report now prints an exact integer health percentage plus the current
  battery level (%), with an honest note when a fuel-gauge estimate is unavailable.
- Battery load test restores screen brightness on exit (the restore guard was
  previously never armed).

### AI Advisor (beta) — more features
- Answers now render as **Markdown**: headings, lists, links and fenced code blocks
  (with monospace styling) instead of plain text.
- **Failure classifier**: after each reply the advisor lists candidate
  FlashPilot flows that match the console tail, as one-click chips that open
  the relevant page (still read-only — nothing is run).
- **Named sessions**: create, rename, switch, delete and export conversations;
  each session is its own transcript file under
  `~/.local/share/flashpilot/ai_sessions/`. The legacy single transcript is
  migrated into a "Default" session on first run.
- **Expanded retrieval**: the advisor now also indexes `docs/` and the flow
  registry in `src/flows.rs`, so it can cite real flow keys and documentation,
  not only `operations/`.
- **Fixed**: the Advisor page now fits narrow viewports — the session row
  wraps via a flow layout instead of forcing a wide minimum width, so the chat
  page no longer overflows the middle panel.

## 1.2.3 (AI Advisor beta, read-only)

*AI Advisor is a beta feature: it explains flashing and lock-removal failures
from your own console tail, device state and FlashPilot's operation notes, and
never executes a flow itself. Verify its suggestions before acting.*

### AI Advisor (new, beta)
- Read-only chat assistant grounded in FlashPilot's real flow registry, the
  selected device (serial masked), the console tail and a BM25 index over
  `operations/*.md` — no tool-calling, no execution path.
- Explains failures with a fixed contract (What happened / Why / Evidence /
  Fix / Risk) and refuses off-topic requests and anything that would change an
  IMEI, bypass Knox or unlock a device you do not own.
- Providers: OpenAI, OpenRouter, Groq, Google Gemini (native API), any
  OpenAI-compatible endpoint and local servers (Ollama / llama.cpp).
- Available both as a dedicated **Advisor** page and a draggable floating
  panel (Ctrl+Shift+A); attach a text file (log/crash report) to a question.
- API keys live in the system keyring only (gnome-keyring / KWallet); with no
  backend the advisor stays disabled instead of writing keys to disk.
- Transcript persists across restarts (`~/.local/share/flashpilot/ai_history.json`,
  0600) and is deletable from the page or Settings; a hashed, secret-free
  audit log records requests.
- Settings → AI: provider, base URL, model, reply length, Test connection,
  masked key, context switches, console-line budget, transcript management.
- Rust core untouched; advisor is Python-side only over the existing bridge.

## 1.2.2 (auto-updates, 10 languages, Rockchip + modem-safe multi-device)

### Auto-updates & What's New (new)
- Updates auto-install: the downloaded `.deb` installs via sudo in the background, the app restarts, and a one-shot "what was added or changed" window shows the new version's changelog on first launch (the manual "Install Now" prompt remains when auto-install is off in Settings → Updates).

### 10-language UI + live language switch (new)
- The whole UI ships in 10 additional languages (Français, Español, Deutsch, 简体中文, Русский, Português, 日本語, العربية, हिन्दी, Türkçe): settings, device tiles, pages and console strings.
- Switching the UI language is immediate — no restart; layouts clamp to real font metrics so long translations wrap instead of clipping controls.
- Key-based JSON translation catalogs with coverage verification; CI smoke-tests the installed catalogs.

### Rockchip + smarter detection (new)
- New Rockchip brand page: RK28xx–RK35xx family via fastboot mode.
- Detection identifies model, brand and form factor — not just the chip.
- Every flashing stage is caught (TFT parity): MediaTek BROM/preloader/DA across the full stage PID set and OEM VIDs (including preloader VCOM 0x2000/0x2001), the extended Qualcomm EDL download-PID family, the SPD download-PID union, and Qualcomm HS-USB Diagnostics named as its own mode.
- The mode badge follows the SELECTED device and names the actual USB protocol (ADB/MTP/PTP/DIAG/storage/RNDIS) instead of OTHER: only flashing PIDs claim the low-level MediaTek label, Qualcomm EDL keeps its badge chip, and the 'MEDIATEK'/'download' substring fall-throughs are fixed.

### Motorola FRP (new)
- CVE-2016-10277 fastboot FRP chain, own-DPC fake-login QR provisioning (TestDPC / Device Policy / Adobe), staged fastboot FRP with flash + reboot cycles, and a factory-bootmode ADB cycle.

### Real engine paths (new)
- Real MTK/QCOM/Unisoc/Samsung flash, FRP and lock paths in the Rust core.
- odin4 is gone: the native Rust Odin engine handles the full tar pipeline, PIT and every known odin4 issue class; Apple usbmuxd/lockdown moved to Rust; the core is Rust-only (all Python device/protocol fallbacks removed).

### Modem-safe ADB (fixed)
- Poll/monitor/display paths are zero-touch (`adb-devices --no-probe`): no open/claim/handshake from loops — USB modems stop re-enumerating every cycle (verified live: 114 quiet poll cycles on an MSM8916 modem).
- Claim fights delegate down a ladder: native → Rust server transport (explicit serial) → host binary → rescue kill (last resort), so ADB ops succeed while the system server holds the interface.
- USB-ADB merge fix (row strings are parsed, so rows actually carry ADB state), busy-holder rescue + transient retry + honest busy state, babble/overflow guard, claim-test isolation command, modern adb CNXN values, and the QCOM/MTK corners show the ADB overlay like sibling branches.

### Multi-device reliability (fixed)
- Pick with settle-retry: every tool runner retries once after 2.5 s when a scan transiently misses a re-enumerating device, instead of refusing with "no device" while the GUI shows it connected.
- ADB AUTH keeps SHA-256 in play across token rounds (odd SHA-256, even SHA-1), so a lost round-1 signature no longer walls into a false "not authorized"; `_wait_for_adb` tolerates transient scan failures.
- Target-identity binding: a replaced device occupying a reused bus:addr is refused (zero-touch serial check) — the transport never follows a different phone.
- Device-list switching: the connection-bar rebuild retries when the second scan drops a device, switching devices no longer falls back to the first phone, and ADB tools fall back to the ADB daemon row when the USB pick misses ("shows connected but actions say no adb").
- Device classification + picker: unmatched devices report USB instead of a wrong MTP label, and a missed USB pick offers the daemon-row picker ("Run on this device" / "Cancel") instead of refusing.

### Honest results & GUI polish (fixed)
- FRP flows require verified flags and a real shell exit status; a non-zero bridge exit raises a failure with the log tail — no more false "completed" toasts.
- GUI: per-row job chips, window memory, toast cap, keyboard navigation, device-aware STOP (one job cancels that device), kg_unlock moved to a worker thread (30-second chains no longer freeze the window), splash tracks the real build, deferred pages stay retryable, toasts clear the top bar.

### Security & robustness
- Private-by-default outputs, symlink-proof temp names, symlink checks.
- Firmware verify-after-write by default + model gate + numeric fixes.
- FRP: the DPC signing certificate is read natively and the provisioning checksum is fixed.
- HIL hardware test harness: multi-device / device-replacement / USB-storm regressions on real hardware; ADB-monitor backoff tests made deterministic.
- Public landing page (`website/`) with the capability matrix and protocol console.

## 1.2.1 (Stable Release)

### Multi-device support (new)
- Plug in several phones: the connection bar lists each one (model · serial ·
  transports); click a row to inspect it.
- Every operation asks which phone it applies to when several match (silent
  when 0–1 match). Console lines carry a `[device-key]` tag.
- One operation per device: different phones can flash in parallel; the same
  phone still serializes. Global STOP broadcasts to all runners.
- Stable identity (`python/core/devices.py`): `adb:<serial>` → `usb:<port-path>`
  → volatile fallback. Targets are re-resolved before sessions open, so USB
  re-enumeration no longer orphans a flash (`usb device Fail`).
- Phone-only device list: hubs, HID, webcams and card readers are filtered out.
- New `SPD` transport mode + read-only Qualcomm/SPD detect flows.

### Per-chip EXPERIMENTAL (new)
- Samsung `Knox / Warranty`, Qualcomm `QCN / Modem`, per-chip `IMEI Repair /
  Change`, `eMMC / UFS` — amber collapsibles on the owning chip page (no
  global LAB page). Every-run ownership checkbox; IMEI change additionally
  requires typing `I UNDERSTAND`. Audit-logged; persisted acks never auto-pass
  (`check_gate_strict`).

### MTK BROM (fixed + improved)
- **PID/stage mapping corrected** to mtkclient convention (`0e8d:0003`=BROM,
  `0e8d:2000`=preloader) across Rust, Python, GUI labels, logs and docs.
- New `mtk_crash_brom` bridge command + `MTK crash preloader into BROM` flow
  (registered under MTK BROM).
- `_wait_mtk_brom_target()` prefers the stable held BROM over the preloader
  window; DA discovery refuses truncated (<1KB) binaries.

### Odin / flashing (hardened)
- `_prepare_download_session()`: kernel-driver detach + 3× handshake retry
  across re-enumeration; all Odin PIDs accepted; PIT cache warmed pre-flash.
- odin4 pinned with `-d /dev/bus/usb/BBB/AAA` + one automatic retry on USB
  loss; `.tar.md5` trailer anchored to end-of-file (streaming, no full RAM read).
- Native smart flash logs per-partition MB/s + ETA.

### Robustness hardening (review-driven)
- Sahara: HELLO command/version/mode/packet-size validated at parse (was:
  any ≥32-byte blob trusted); transfer-format self-check now round-trips
  structs instead of dropping bytes; close failures logged; detach runs
  before claim; handshake reports transfer/close/reset outcomes in JSON
  instead of discarding them (reset is explicit and visible).
- ADB auth: capped exponential backoff between token rounds; one-time
  keygen pause announced instead of looking hung.
- MTK: configured packet size actually reaches the DA session (was computed
  and dropped; sessions hardcoded 64K), clamped to 512B–1MB.
- Safety backups: failures print an unmissable banner with elapsed time
  and a STOP hint (contract unchanged: never blocks the operation).
- Experimental gates: iCloud + Pixel flows migrated to strict per-run acks;
  GUI ack tokens are now counted per feature with expiry (no cross-feature
  bleed, no lost acks, no stale authorizations).

### GUI fixes
- Top-bar red borders + button shrink traced to concurrent shake/rubber
  animations and accent-tinted focus rings: animations serialized with
  `_anim_lock` + full cleanup; new neutral `focus_ring`/`sel_border` theme
  tokens (red accents can no longer leak into focus).
- `os.system()` → `subprocess` for bridge rebuild / log-dir open.
- Duplicate SPD "Enable ADB" stub, `fastboot_unlock` experimental mis-gating,
  dead FUS→AP-slot path, and missing `finished` emit fixed. Removed the dead
  LAB/Knox/QCN/PAC experimental surface.

### Restructure
- `python/core/frp.py` (god file) → `python/core/core.py` (registry + flows);
  `frp.py` is now FRP-only. Dead `python/core/flows/` split removed.
- Verb-first job names (`Remove FRP`, `Flash Firmware`, …); one canonical
  snake_case key per flow; display-name casing normalized.

### Docs
- Fresh screenshots (`docs/samsung.png`, `mtk.png`, `spd.png`), rewritten
  README highlights/matrix/layout, CONTRIBUTING architecture + flow rules,
  this changelog.

### boot.img + AVB (single native engine)
- New image-surgery engine in the Rust bridge (`src/imgtools.rs`): Android
  boot header parse, cpio newc scan, prop patching (pad-in-place or
  magiskboot-style grow with header rewrite), deterministic gzip
  (mtime=0, level 9), AVB vbmeta flags. `boot-info` / `boot-patch-adb` /
  `vbmeta-patch` CLI.
- Python `spd_adb` repack + `core._patch_vbmeta_flags` delegate with local
  fallback (signatures and return contracts unchanged).
- Equivalence work fixed two real bugs: the grow splice disagreed with the
  reader's alignment by 2 bytes (corrupting every later entry — both
  implementations), and re-patching grew by `\n` each run (both sides now
  idempotent). gzip bytes are intentionally excluded from parity (zlib
  implementations differ); decompressed content, sizes and fields match.
- 6 Rust unit tests + 9 cross-implementation tests.

### PAC (single native engine + wired GUI actions)
- New SPD PAC engine in the Rust bridge (`src/pac.rs`): parse/extract/pack
  with the YGDP layout, shared header/slot builders now also used by the
  `spd-readback` writer (byte-identical output; its historical doubled slot
  names quarantined, not propagated). `pac-parse` / `pac-extract` /
  `pac-pack` CLI.
- Python `pac.*` delegates with local fallback; new `flow_pac_extract` /
  `flow_pac_pack` (file-only, ofp-style env inputs) registered in FLOWS and
  mapped in the GUI dispatcher — the previously dead PAC buttons now run.
- Equivalence tests caught and fixed a real bug: the local packer silently
  dropped the product string (slice-copy write); plus u32 overflow guards
  with identical messages on both engines.
- 5 Rust unit tests + 7 cross-implementation tests (roundtrips both
  directions, sanitize parity incl. dir collision, error mapping).

### PIT (single native engine)
- New Samsung PIT engine in the Rust bridge (`src/pit.rs`): parse (28/132
  layout), header/model strings, name normalization, find, overlap scan,
  forensic validation + health verdicts — byte-identical messages, summaries
  and verdicts to the Python implementation on real dumps and edge cases
  (including Python-`repr` parity for junk names).
- `pit-parse` / `pit-health` / `pit-find` / `pit-overlaps` / `pit-model`
  CLI; Python `pit.*` raw-bytes paths delegate with local fallback when the
  binary is absent (contracts preserved: ValueError/None/never-raise).
  In-memory object paths and display helpers stay local and fast; shared
  rules pinned by 11 cross-implementation equivalence tests.
- 8 Rust unit tests (layout vectors, normalize table, meta overlap
  classification, summary/human-size shapes).

### ADB (native transport, no platform-tools)
- New native ADB client in the Rust bridge (`src/adb.rs`): USB transport
  (255/66/1) with kernel-driver detach, CNXN handshake, RSA-SHA256/SHA-1
  AUTH (reuses `~/.android/adbkey`, generated when missing), `shell:` and
  `sync:` (STAT/RECV/SEND) services.
- `adb-devices` keeps its `adb devices -l` line contract from a native scan
  (`device` / `unauthorized` / `no permissions`); `adb-shell` takes a serial
  (`-` = first authorized), plus new serial-pinned `adb-pull` / `adb-push`.
- Python: `bridge.adb_shell()` resolves explicit > ambient-scope > first
  authorized serial (multi-device ADB is now target-pinned); `adb.py`
  delegates to the bridge; EFS backup/restore pull/push go through the
  bridge instead of unpinned system `adb` calls. `has_adb()` now means
  "bridge built".
- 6 Rust tests (framing, banner, PKCS#1 sign/verify, DER roundtrip,
  bit-identical pubkey blob vs system adb's key) + 9 Python tests.

### Fastboot (native transport + Motorola universal)
- New native fastboot USB transport in the Rust bridge (`src/fastboot.rs`):
  `fastboot-devices` (JSON) + `fastboot-cmd <vid:pid@bus:addr> <ms> <cmd…>`
  for the command phase (getvar/oem/erase/reboot) with kernel-driver detach.
  Device-side FAIL renders as `FAILED (remote: …)` with exit 0, matching the
  system binary's transcript shape (including lone `getvar` values that ride
  in the OKAY packet on Moto MBM bootloaders).
- Shared Python helpers (`_fastboot_run`, `_wait_fastboot`,
  `_fastboot_getvar`) are native-first with system-binary fallback;
  DATA-phase commands (flash/boot/…) always use the system binary, and the
  host-side `devices` listing is served from native detect. All fastboot
  traffic is now target-pinned (`vid:pid@bus:addr`), closing the no-`-s`
  wrong-phone hazard.
- New brand-wide Motorola flows (`moto_frp_adb`, `moto_frp_fastboot`,
  `moto_oem_unlock_token`): ADB provisioning reset, official unlock-token
  flow with lock-state read + session resets, read-only token reader. Shown
  under Motorola → All Motorola / Lenovo (universal) and every Moto model;
  unlock portal URL corrected (old `motorola.com/unlockbootloader` is dead).
- `python/core/fastboot.py` (Pixel) and `usb_watch.py` (lsusb scraping) moved
  onto the bridge; 7 new `tests/test_fastboot_native.py` tests.
