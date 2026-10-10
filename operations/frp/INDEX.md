# operations/frp/ — Factory Reset Protection (Android only)

> Apple devices have no FRP (Apple uses Activation Lock / iCloud instead) —
> see `operations/apple/`.

This directory holds **per-engine documentation trees** for FRP bypass.
The actual code lives in `python/core/flows/`. When you have a real
recipe for a device (chip, FDL pair, partition offsets, etc.) you drop a
short research note in `devices/<brand>/<model>.md`. The README at the
root of this file maps every FRP flow in the codebase to where it lives
and what it needs.

## Engine map

| Engine | When to use | Code | Bridge CLI |
|---|---|---|---|
| **Generic (ADB)** | First attempt on any phone with USB debugging on | Rust flows (`adb_frp`, `frp_*` rows in `src/flows.rs`) | `flow-run adb_frp` / `adb shell ...` via `bridge.adb_shell` |
| **MTK BROM** | MediaTek (Helio / Dimensity / MT6765) — power off → hold Vol-/+ → plug USB | Rust flows (`mtk_*` rows in `src/flows.rs`) | `flow-run mtk_brom_info` (CLI: `mtk-detect`, `mtk-da-upload`, `mtk-frp`, `mtk-bypass`) |
| **MTK DA** | MTK BROM that survived DA upload (lock-state chips) | Rust flows (`mtk_brom_backup`, `mtk_auth_flash`) | `flow-run mtk_brom_backup` |
| **Qualcomm EDL** | 9008 emergency download (Snapdragon) | Rust flows (`edl_*`, `qcom_*` rows) | `flow-run edl_frp` (CLI: `qcom-*`) |
| **Samsung Exynos** | A14 (Exynos 850/1330), A15/A16 — Odin download mode is flashing only, NOT for FRP | Rust `frp_*` rows (Samsung account-bypass) | (mostly on-device, no bridge) |
| **Samsung MTK (A05/A06)** | A05/A06 with Helio G85 — uses MTK BROM (above) | Rust flows (`mtk_brom_info`, `mtk_brom_backup`) | `flow-run mtk_brom_backup` |
| **UNISOC/SPD** | 1782:4d00 FDL1+FDL2 (SC9863A, T606/UMS9230) | Rust flows (`spd_*` rows) + `src/spd.rs` | `flow-run spd_detect_info` (CLI: `spd-detect`, `spd-frp`, `spd-format`, `spd-magic-pack`) |
| **HiSilicon Kirin** | 12d1 — no open flow yet (not reverse-engineered) | (none yet) | (none) |

(The old `python/core/flows/*.py` engine modules never shipped; `mtk-brom-backup`
is the `mtk_brom_backup` flow row. Verify any key with `flow-list`.)

## Flow key → function map

Every flow the GUI's FRP actions can call. Keys are Rust registry rows
(`src/flows.rs`, `flow-list` to verify); the GUI routes them by
(job, mode) and the bridge runs them via `flow-run <key> [target]`.

| Flow key | Engine | What it does |
|---|---|---|
| `adb_frp` | Generic ADB | `settings put secure frp 0` + disable setup wizards + clear GMS data |
| `frp_browser` | Generic ADB | Open `chrome://settings/` on-device via intent |
| `frp_emergency` | Generic ADB | Open Settings via Emergency-call dialer (on-device) |
| `frp_settings` | Generic ADB | Open Settings via notification-shade path (on-device) |
| `frp_fake_login` (+`_testdpc`, `+_adp`) | Generic ADB | QR provisioning with a device-owner DPC, then FRP clear |
| `at_info` | Samsung MTP/AT | Read mode + devconinfo via AT channel (Samsung pre-Android 8) |
| `at_method` | Samsung MTP/AT | AT+DEBUGLVC to enable ADB over the diag port |
| `download_frp` | Samsung Download mode | CSC/Combination firmware FRP remove (PIT safety contract) |
| `odin_enable_adb` | Samsung Download mode | Enable ADB from download mode via Odin tarball |
| `mtk_combo_flash` | MTK Download | Combination firmware flash (PIT + DA) |
| `mtk_recovery_reset` | MTK Download | Recovery-mode factory reset |
| `mtk_brom_info` | MTK BROM | Read chip id / handshake (needed before any BROM flash) |
| `mtk_brom_backup` | MTK BROM | Dump partitions via BROM DA |
| `edl_frp` | Qualcomm EDL | Sahara + Firehose erase (05c6:9008) |
| `qcom_detect_info` | Qualcomm EDL | Detect + info (read-only) |
| `frp_qr_provision` | Generic ADB | QR provisioning (TestDPC path) |

(Retired: the old `flow_*`-prefixed key names and
`python/core/flows/*.py` never shipped — keys have no `flow_` prefix.)

## How a new per-model recipe lands here

1. **Run a real device dump** (see `scripts/dump-connected.sh` for the
   ADB-side path, or `flashpilot-bridge spd-format` for the BROM-side path
   on Unisoc). The dump goes to `build/cache/dumps/<model>_<codename>/`.

2. **From the dump, identify** the engine + chip + the FRP partition
   name (almost always `frp`, `frp_a`, or `userdata` on Android 11+).

3. **Add the device entry** to `python/gui/supported_devices.json` under
   the right brand, with `actions: ["frp", "info", "backup", "flash"]`
   and `status: "researched"`. (The existing per-engine flow will pick
   it up automatically — no new flow is needed unless the engine itself
   is missing.)

4. **Drop a short research note** in `operations/frp/devices/<brand>/<model>.md`
   with the chip, engine, partition, build fingerprint, and a
   one-liner confirming the recipe (e.g. "mmcblk0p4 = frp, instant
   BROM DA erase, no combo needed"). See
   `operations/frp/devices/nokia/nokia_g20.md` for the format.

5. **If the engine itself doesn't have a flow** for this chipset, register
   the flow in `python/core/flows/<engine>.py` under `FLOWS` and add
   the CLI dispatch in `src/<engine>.rs` + `src/main.rs`.

## Why the per-chip files are gone

Earlier refactors split the god `frp.py` into per-chip files under
`operations/frp/chips/` and per-engine files under
`operations/frp/{mtk,qualcomm,unisoc,samsung}_frp/`. An older revision of
this INDEX claimed dead docstubs and a `python/core/flows/brom.py` dispatch
— that module never shipped. The real per-chip dispatch is the Rust flow
registry (`src/flows.rs`: `mtk_*`/`qcom_*`/`spd_*` rows, `flow-list` to
verify); this INDEX.md is the map so a new dev knows where the
engine-specific code actually lives.

## Why the per-engine Python shims are gone

`operations/frp/mtk_frp/mtk_frp.py` (and its 4 siblings) imported
functions from `python.core.flows.brom` and re-exported them under a
**second** `FLOWS = {}` dict that the GUI never reads. They collided
with the canonical `FLOWS` in `python/core/flows/__init__.py` and would
have masked the real ones if the GUI ever did read them. Replaced with
a README in each engine folder that points at the real Python
modules.
