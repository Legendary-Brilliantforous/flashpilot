# FlashPilot 1.2.0 — Stable

Open-source Linux flashing & repair workbench for Android devices — the free
equivalent of commercial Windows flashing suites. **1.2.0 is a stability +
advancement release: `cargo check` 0 warnings, `cargo test` 60 + `pytest` 149
pass, live GitHub release channel, and auditable history.**

A native **Rust** core (`flashpilot-bridge`, ~9,300 LOC, vendored libusb)
speaks bootloader protocols directly — Samsung Odin/HID, MediaTek BROM/DA,
Qualcomm Sahara/Firehose, Spreadtrum/UNISOC BSL — while a polished **PyQt6**
studio presents 8 transports, 8 job categories and ~120 operations: flashing,
FRP bypass, screen-lock removal, MDM unlock, partition tools, device info,
reboot, and battery/network repair on any ADB device.

**What's new in 1.2.0 stable:**
- **Bridge 0 warnings** — wired 18 dead-paths: AT `Context` retention & `vid`
  validation (`AT/control` re-enumeration after `+DEBUGLVC`), USB
  `EndpointConfig.max_packet_size` chunking & `open_target/read_exact/info`,
  SPD `BSL_CMD`/`BSL_REP` + `iface` + `flush/read_flash/chip_uid/power_off`,
  `ProgressReporter` → real flash %, Qualcomm `QcomDeviceInfo`/`FirehosePacket`,
  MTK `read16/write16` — `-80KB` `lto`, no handle leaks.
- **Dynamic version** — `APP_VERSION` from installed `importlib.metadata`
  (deb `pyproject.toml` is truth), ` _display_version` `1.2.0→1.2` / `1.2.1→1.2.1`,
  live GitHub `latest stable` (never hand-coded), BETA pill on logo/titlebar.
- **Unified big dialogs** — 620px centered draggable cards (vs 320px toast) with
  high-contrast `#e2e8f0` text, `✕` + `X` drag, chip colors: `MTK amber`,
  `QCOM red`, `SPD violet`, `SAMSUNG blue`; beta gate requires `I accept`
  checkbox (persists per-version, `first_install` default / `every_boot` toggle
  in Settings → Updates), `Exit` quits app, stable `UPDATE/AHEAD/PATCH` use
  same big dialog, flash/FRP confirm overlays use chip gradient.
- **One global STOP** — single `⏹ STOP` in titlebar (outside any card), 150ms
  sync to `_FLOW_LABEL`, stops *any* Samsung/MTK/QC/SPD flow; legacy per-chip
  Stops hidden.
- **Governance** — `dev`/`main` protected: `strict` CI `Rust+Python`, `1`
  review, `dismiss_stale`, `require_last_push_approval`, `linear_history`,
  `force_push:false`; `devin-ai-integration[bot]` removed from history/tag
  `v1.2.1-beta.1` → `55c0da3`.

- **Platform:** Linux
- **Language:** Rust (core) + Python 3.10+ / PyQt6 (UI)
- **License:** MIT
- **Status:** stable 1.2.0 — contributors welcome

Use it on devices you own or are authorized to service.