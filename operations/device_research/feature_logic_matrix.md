# Feature and logic matrix — FlashPilot engine capabilities

This is FlashPilot's own capability register: which CLI commands each engine
exposes, how a device row's transport flags map to the actions the device page
lights up, and which operations remain unwired. It is a planning document, not a
user manual — the CLI is the source of truth (`src/main.rs`).

Status legend: **wired** = command exists and is exercised in a flow;
**partial** = command exists but one path is a stub or hardware-unverified;
**absent** = no command.

---

## 1. Capability flags → enabled actions

The device database (`python/gui/supported_devices.json`) stores **transport
capability**, not per-action flags. The action set for a model is derived:

```
enabled_actions(model) = actions_for(engine) ∩ model.actions
```

| Row signal | Engine | Actions that light up |
|---|---|---|
| `Brom` / `Preloader` / `auth` | `mtk` | info, da-upload, flash, read, backup, frp, imei, factory, adb-enable |
| `Edl` | `qcom` | info, sahara/firehose, flash, partitions, backup, frp-reset |
| `spd` | `spd` | info, flash, partitions, format, backup, frp, spl-patch |
| `Odin` | `odin` | info, pit, flash, agent |
| `apple` | `apple` | detect, info |
| *(none)* | `mtk` fallback | info only |

A row with no transport flag still renders, with everything but `info` disabled.
That is deliberate: the catalogue has 212 rows whose platform was never recorded
(§ device_coverage.md), and guessing a transport is how a device gets bricked.

The GUI renders each action row with a real label and a tooltip naming the bridge
command behind it; command wiring lands per step, so a lit action means "this
engine supports it", not "this button is finished".

### Gating conditions

| Gate | Where | Effect |
|---|---|---|
| `connection: "auth"` | row | Requires an authenticated/signed session (SLA or vendor auth) before the engine accepts commands. |
| `connection: "Preloader"` | row | Device is in preloader, not BROM — needs a crash step first. |
| `status: "planned"` | row | Actions render disabled; research only. |
| loader/programmer source | runtime | MTK needs a DA/scatter, Qualcomm a Firehose programmer, SPD an FDL. FlashPilot ships no firmware images. |
| experimental flag | runtime | IMEI, NV/EFS backup and SAM/knox operations are audit-logged and confirmation-gated. |

---

## 2. MTK engine

BROM exploit, DA upload, scatter-driven flash, FRP, partition work.

| Command | Operation | Status |
|---|---|---|
| `mtk-detect` | list MTK devices (BROM/preloader/DA) | wired |
| `mtk-detect-extended` | extended detection (mode + identity) | wired |
| `mtk-payload-check` | verify bundled BROM payloads resolve | wired |
| `mtk-da-upload` | upload Download Agent | wired |
| `mtk-scatter` | parse scatter file | wired |
| `mtk-flash` | flash firmware from scatter | wired |
| `mtk-flash-part` | flash a single partition | wired |
| `mtk-flash-samsung` | flash Samsung firmware over MTK | partial |
| `mtk-backup` | back up partitions | wired |
| `mtk-read-part` | read a partition | wired |
| `mtk-verify-part` | verify a partition (SHA-256) | wired |
| `mtk-gpt` | generate GPT from device | wired |
| `mtk-scatter-gpt` | generate scatter from GPT | wired |
| `mtk-frp` | FRP bypass (scatter-based) | wired |
| `mtk-frp-brom` | FRP bypass via BROM exploit | wired |
| `mtk-frp-gpt` | FRP bypass (GPT-based) | wired |
| `mtk-adb-enable` | enable ADB via FRP bypass | wired |
| `mtk-factory` | factory reset | wired |
| `mtk-reboot` / `mtk-reset` | reboot / reset device | wired |
| `mtk-emergency` / `mtk-emergency-mode` | detect/enter emergency mode | wired |
| `mtk-bypass` | BROM exploit (dump preloader) | wired |
| `mtk-brom-exploit` | kamakiri2 / bypass_utility exploit | wired |
| `mtk-exploit` | BROM exploit with a custom payload | partial — logging stub on some paths |
| `mtk-crash-brom` | force a BROM crash | wired |
| `mtk-dealer` | dealer/authorized mode | partial |
| `mtk-mem-probe` | probe RAM read/write after exploit | wired |

## 3. Qualcomm engine

Sahara handshake, Firehose XML flashing, GPT/LUN handling, MBN parsing.

| Command | Operation | Status |
|---|---|---|
| `qcom-detect` | list Qualcomm devices (Sahara/EDL) | wired |
| `qcom-sahara` | Sahara handshake, enter EDL/9008 | wired |
| `qcom-firehose` | raw Firehose session | wired |
| `qcom-flash` | full Firehose flash (XML-driven) | wired |
| `qcom-flash-one` | single-partition flash | wired |
| `qcom-verify-part` | partition verification | wired |
| `qcom-info` | device/SoC info | wired |
| `qcom-partitions` | list partitions | wired |
| `qcom-backup` | token-gated DIAG/QCN backup | partial — experimental |
| `qcom-frp-reset` | FRP reset guidance/ADB path | partial — no EDL FRP writer |
| `qcom-reboot` | reboot device | wired |

Protocol notes: Sahara (VID 0x05C6: PID 0x2003/0x9008/0x4003), Firehose
`rawprogram`/`patch`/`program` XML, MBN programmer parsing, GPT with LUN
awareness, VIP/auth handling for signed Firehose, sparse image support.
Storage: eMMC 4.5/5.1/5.2, UFS 2.1/2.2.

## 4. SPD/Unisoc engine

Download-mode upload, partition management, FRP, SPL patch.

| Command | Operation | Status |
|---|---|---|
| `spd-detect` | detect SPD/Unisoc devices | wired |
| `spd-info` | chip, version, security state | wired |
| `spd-partitions` | list partitions | wired |
| `spd-flash` | flash firmware | wired |
| `spd-format` | format partitions | wired |
| `spd-backup` | back up partitions | wired |
| `spd-readback` | readback partitions | wired |
| `spd-frp` | FRP bypass (wipe frp/nvdata/persistent) | wired |
| `spd-reset` | factory reset | wired |
| `spd-spl-patch` | SPL patch (bypass security checks) | partial — hardware-unverified |
| `spd-magic-pack` | build a custom pack | wired |
| `spd-boot` | boot to download mode | wired |

Protocol notes: VID 0x1782 (PIDs 0x0001/0x0002), FDL1/FDL2 upload, BSL
handshake, NVRAM backup via `SP_META_*` semantics.

## 5. Samsung / Odin engine

| Command | Operation | Status |
|---|---|---|
| `odin-connect` | connect in Odin download mode | wired |
| `odin-info` | bootloader/PDA/CSC versions | wired |
| `odin-pit` / `odin-pit-mtk` | read PIT (Qualcomm/Exynos and MTK) | wired |
| `odin-send-pit` | write PIT | partial — destructive, confirmation-gated |
| `odin-flash` | flash a tar | wired |
| `odin-flash-tar` | flash an explicit tar | wired |
| `odin-flash-multi` | multi-file flash (BL/AP/CP/CSC) | wired |
| `odin-agent` | Odin agent mode | partial |
| `odin-model` | identify model from PIT | wired |

Samsung-specific flows (FRP, factory reset, ADB enable, Knox/KG) ride
`src/flows.rs` and are audit-logged.

## 6. Apple engine

| Command | Operation | Status |
|---|---|---|
| `apple-detect` | list iDevices (normal/recovery/DFU) | wired |
| `apple-info` | device info | wired |

No restore/update flow: that requires a signed IPSW chain and is intentionally
out of scope for a Linux-native tool.

## 7. Shared infrastructure

| Command | Operation |
|---|---|
| `detect-all` / `detect-merged` | unified bus scan across all engines |
| `unified-flash` | engine-agnostic flash dispatch |
| `flow-list` / `flow-run` | named operation flows |
| `actions-for` / `validate-action` | action gating used by the GUI |
| `pit-parse` / `pit-find` / `pit-model` / `pit-health` / `pit-overlaps` | Samsung PIT analysis |
| `pac-parse` / `pac-extract` / `pac-pack` | SPD PAC containers |
| `adb-*` | ADB shell/push/pull |
| `fastboot-*` | fastboot passthrough |
| `usb-*` / `bulk-*` / `hid-*` | raw USB transport helpers |

---

## 8. Comparison: what other engines in this space do that FlashPilot does not

Kept short and generic; none of it is code that can be copied.

| Area | Industry practice | FlashPilot |
|---|---|---|
| Vendor-specific flashing (LGUP/KDZ, Huawei update.app, Xiaomi fastboot ROM) | Bundled Windows EXEs driven by the GUI | absent — out of scope on Linux; fastboot and Odin cover the common cases |
| Apple restore/update | libimobiledevice + signed IPSW | absent |
| KitKat-era SPD/budget MTK | Dedicated download tools per vendor | covered generically where the BROM/DA path exists |
| IMEI/NV editing on Qualcomm | QMSL/DIAG NV item writers | partial — token-gated DIAG backup only, no NV writer |
| Preloader corpus per model | Hundreds of bundled preloaders as a fallback | absent — user supplies firmware |

---

## 9. Device-page wiring (real operations per engine)

The device page no longer shows a "wiring lands later" toast for the primary
actions. Each action resolves the **selected** device key and runs the engine
command below with a confirmation overlay first. Bundled payloads make the
transport work without the user hunting for files; firmware images still come
from the user.

| Action | MTK | Qualcomm | Unisoc |
|---|---|---|---|
| info | `mtk-detect` | `qcom-detect` | `spd-detect` |
| FRP (no ADB) | `mtk-frp-brom auto <bundled-da-dir>` — BROM exploit, per-chip DA, erase `frp`/lock partitions from the device GPT | `qcom-frp-reset auto [--wipe-data]` — Sahara programmer, Firehose erase `frp, frp_a, frp_b, persist, config, misc` (all LUNs) | `spd-flash-pac auto <pac> --mode frp` (or `spd-frp` with FDLs typed) |
| screen lock (no ADB) | `mtk-screen-lock auto <da>` — erase `metadata, persistent, keystore, oemkeystore, protect1/2, misc`; `--wipe-userdata` adds `userdata, cache, nvdata` | ADB `locksettings` path; EDL `--wipe-data` BCB write to `misc` | `spd-flash-pac --mode erase` |
| backup | `mtk-backup-gpt auto <da> <dir>` — every GPT partition + `manifest.json` | `qcom-backup auto <dir>` — every partition/LUN + manifest; errors on an empty table | `spd-flash-pac --mode backup --out <dir>` (or `spd-backup`) |
| flash | `mtk-flash-auto auto <folder>` — discovers the scatter, expands sparse/`.lz4`, skips boot regions, A/B slot fallback | `qcom-flash auto <rawprogram.xml> <folder>` — sparse expansion, per-op LUN, storage auto (emmc→ufs), `<patch>`/erase semantics | `spd-flash-pac <pac> --mode flash` — FDLs read from the PAC |

Payloads bundled with the build: `payloads/mtk` (mtkclient DA/payloads, GPLv3),
`payloads/qcom` (firehose programmers + SoC index; auto-tries candidates in
order). FDL1/FDL2 for Unisoc come out of the PAC itself, so no loader store is
needed.

## 10. Recommendations

| # | Change | Payoff | Effort |
|---|---|---|---|
| 1 | Wire `mtk-exploit`/`mtk-dealer` end-to-end (they still short-circuit to logging stubs) | removes the "looks supported, silently does nothing" class of bug | S |
| 2 | Add the watchdog disable before long dumps (see `mtk_gap_analysis.md` §4.3) | removes mid-dump resets on armed BROMs | S |
| 3 | Extend the Qualcomm programmer index beyond the bundled set (per-model `~/.local/share/flashpilot/payloads/qcom/<soc>/`) | covers models whose programmer is not in the bundle | M |
| 4 | Add more FRP bypass methods for MTK/QC/SPD | already covered per engine; more variants possible | M |
| 5 | Add more IMEI repair methods | already covered per engine; more variants possible | M |
| 6 | Add more partition operations (restore-in-place, region clone) | format/backup/restore/readback exist; more possible | S/M |
| 7 | Add vendor buckets for the 148 unbucketed catalogue rows | brand-count gain, no protocol work | S |

All of the above need hardware to validate. Nothing here should ship on
table-only reasoning.
