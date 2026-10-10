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
| **Generic (ADB)** | First attempt on any phone with USB debugging on | `python/core/flows/frp.py` | `adb shell ...` via `bridge.adb_shell` |
| **MTK BROM** | MediaTek (Helio / Dimensity / MT6765) — power off → hold Vol-/+ → plug USB | `python/core/flows/brom.py` | `mtk-detect`, `mtk-da-upload`, `mtk-frp`, `mtk-bypass` |
| **MTK DA** | MTK BROM that survived DA upload (lock-state chips) | `python/core/flows/screenlock.py` | `mtk-frp`, `mtk-brom-backup` |
| **Qualcomm EDL** | 9008 emergency download (Snapdragon) | `python/core/flows/frp.py` | `edl-frp`, `qcom-*` |
| **Samsung Exynos** | A14 (Exynos 850/1330), A15/A16 — Odin download mode is flashing only, NOT for FRP | `python/core/flows/oem_odin.py` (carrier state) + `frp.py` (Samsung account-bypass) | (mostly on-device, no bridge) |
| **Samsung MTK (A05/A06)** | A05/A06 with Helio G85 — uses MTK BROM (above) | `python/core/flows/brom.py` | `mtk-frp` |
| **UNISOC/SPD** | 1782:4d00 FDL1+FDL2 (SC9863A, T606/UMS9230) | `python/core/flows/brom.py`, `src/spd.rs` | `spd-detect`, `spd-frp`, `spd-format`, `spd-magic-pack` |
| **HiSilicon Kirin** | 12d1 — no open flow yet (not reverse-engineered) | (planned in `python/core/flows/`) | (none) |

## Flow key → function map

Every flow the GUI's "FRP bypass" button can call. The keys are the
strings in `supported_devices.json` `actions: ["frp"]` and the
entries in `python/core/flows/frp.py`'s `FLOWS = {}` dict.

| Flow key | Function | Engine | What it does |
|---|---|---|---|
| `flow_adb_frp` | `flow_adb_frp` | Generic ADB | `settings put secure frp_done 1` + disable setup wizards + clear GMS data |
| `flow_frp_clear_adb` | `flow_frp_clear_adb` | Generic ADB | Same as above but explicitly named "clear" |
| `flow_frp_browser` | `flow_frp_browser` | Generic ADB | Open `chrome://settings/` on-device via intent |
| `flow_frp_emergency` | `flow_frp_emergency` | Generic ADB | Open Settings via Emergency-call dialer (on-device) |
| `flow_frp_settings` | `flow_frp_settings` | Generic ADB | Open Settings via notification-shade path (on-device) |
| `flow_universal_frp_bypass` | `flow_universal_frp_bypass` | Generic ADB | Combined-method ladder |
| `flow_at_info` | `flow_at_info` | Samsung MTP/AT | Read mode + devconinfo via AT channel (Samsung pre-Android 8) |
| `flow_at_method` | `flow_at_control` | Samsung MTP/AT | AT+DEBUGLVC to enable ADB over the diag port |
| `flow_download_mode_frp` | `flow_download_mode_frp` | Samsung Download mode | CSC/Combination firmware FRP remove (PIT safety contract) |
| `flow_odin_enable_adb` | `flow_odin_enable_adb` | Samsung Download mode | Enable ADB from download mode via Odin tarball |
| `flow_mtk_combo_flash` | `flow_mtk_combo_flash` | MTK Download | Combination firmware flash (PIT + DA) |
| `flow_mtk_recovery_reset` | `flow_mtk_recovery_reset` | MTK Download | Recovery-mode factory reset |
| `flow_mtk_brom_info` | `flow_mtk_brom_info` | MTK BROM | Read chip id / handshake (needed before any BROM flash) |
| `flow_mtk_brom_backup` | `flow_mtk_brom_backup` | MTK BROM | Dump partitions via BROM DA |
| `flow_mtk_frp` | (chain) | MTK BROM | Wipe frp + nvdata partitions via BROM (Android Q-compat) |
| `flow_qualcomm_edl_frp` | `flow_qualcomm_edl_frp` | Qualcomm EDL | Sahara + Firehose erase (05c6:9008) |
| `flow_qualcomm_qfil_frp` | `flow_qualcomm_qfil_frp` | Qualcomm EDL | QFIL XML variant |
| `flow_samsung_emergency_call` | `flow_samsung_emergency_call` | Samsung MTP/AT | On-device: emergency dialer path |
| `flow_samsung_talkback` | `flow_samsung_talkback` | Samsung MTP/AT | On-device: TalkBack path |
| `flow_samsung_account_bypass` | `flow_samsung_account_bypass` | Samsung MTP/AT | On-device: Samsung-account side bypass |

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
`operations/frp/{mtk,qualcomm,unisoc,samsung}_frp/`. Those turned out
to be **dead docstubs** — `FLOWS = {}`, wrong imports (`sd695.py`
importing an MTK flow), no callers. The real per-chip dispatch is in
`python/core/flows/brom.py` (`_mtk_fdl_base`, `chip_id` recognition, etc.).
Those dead files were deleted; this INDEX.md is the replacement so a
new dev knows where the engine-specific code actually lives.

## Why the per-engine Python shims are gone

`operations/frp/mtk_frp/mtk_frp.py` (and its 4 siblings) imported
functions from `python.core.flows.brom` and re-exported them under a
**second** `FLOWS = {}` dict that the GUI never reads. They collided
with the canonical `FLOWS` in `python/core/flows/__init__.py` and would
have masked the real ones if the GUI ever did read them. Replaced with
a README in each engine folder that points at the real Python
modules.
