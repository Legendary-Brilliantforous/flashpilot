# Changelog

## 1.2.2 (modem-safe ADB + display fixes)

### ADB transport (fixed)
- Poll/monitor/display paths are zero-touch (`adb-devices --no-probe`,
  `adb_presence`): no open/claim/handshake from loops. Fixes USB modems
  re-enumerating every cycle (verified live: 114 quiet poll cycles on an
  MSM8916 modem after ~1 Hz storms).
- Delegate ladder on claim fights: native -> Rust server transport
  (`adb-shell-server`, explicit serial only) -> host binary -> rescue
  kill (last resort). ADB ops now succeed with the system server holding
  the interface instead of evicting it.
- USB-ADB merge fix: row strings are parsed (struct deserialization had
  silently yielded zero ADB entries, so rows never carried ADB state).
- QCOM corner now shows the ADB overlay like sibling branches.

### Robustness (fixed)
- Single settle-retry on transient gate refusals (re-enumeration windows)
  with accurate messages; `rescue=False` + serial pinning across all
  diagnostic/tool shells; Firehose FAIL detection; CLI input panics;
  allocation clamps; tar traversal guards; strict XML numerics.

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
