# Changelog

## Unreleased (toward 1.2.1)

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
