Language switcher: [English](../../frp/INDEX.md) · [Français](../../fr/frp/INDEX.md) · [Español](../../es/frp/INDEX.md) · [Deutsch](../../de/frp/INDEX.md) · [简体中文](../../zh/frp/INDEX.md) · [Русский](../../ru/frp/INDEX.md) · [Português](../../pt/frp/INDEX.md) · [日本語](../../ja/frp/INDEX.md) · [العربية](../../ar/frp/INDEX.md) · **हिन्दी** · [Türkçe](../../tr/frp/INDEX.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# operations/frp/ — Factory Reset Protection (केवल Android)

> Apple डिवाइसेज में FRP नहीं होता (Apple इसके बजाय Activation Lock / iCloud use करता है) —
> देखें `operations/apple/`.

यह डायरेक्टरी FRP bypass के लिए **per-engine documentation trees** hold करती hai.
असली code `src/flows.rs` (Rust) में hai. Jab kisi device ka real
recipe (chip, FDL pair, partition offsets, etc.) hai to aap short research note
`devices/<brand>/<model>.md` में daalte hain. Is file ka root README codebase ke
har FRP flow ko uski jagah aur zaroorat ke saath map karta hai.

## Engine map

| Engine | Kab use karein | Code | Bridge CLI |
|---|---|---|---|
| **Generic (ADB)** | USB debugging on hone par kisi bhi phone ka first attempt | Rust flows (`adb_frp`, `frp_*` rows in `src/flows.rs`) | `flow-run adb_frp` / `adb shell ...` via `bridge.adb_shell` |
| **MTK BROM** | MediaTek (Helio / Dimensity / MT6765) — power off → Vol-/+ hold → plug USB | Rust flows (`mtk_*` rows in `src/flows.rs`) | `flow-run mtk_brom_info` (CLI: `mtk-detect`, `mtk-da-upload`, `mtk-frp`, `mtk-bypass`) |
| **MTK DA** | MTK BROM that survived DA upload (lock-state chips) | Rust flows (`mtk_brom_backup`, `mtk_auth_flash`) | `flow-run mtk_brom_backup` |
| **Qualcomm EDL** | 9008 emergency download (Snapdragon) | Rust flows (`edl_*`, `qcom_*` rows) | `flow-run edl_frp` (CLI: `qcom-*`) |
| **Samsung Exynos** | A14 (Exynos 850/1330), A15/A16 — Odin download mode सिर्फ flashing है, FRP के लिए नहीं | Rust `frp_*` rows (Samsung account-bypass) | (mostly on-device, no bridge) |
| **Samsung MTK (A05/A06)** | A05/A06 with Helio G85 — uses MTK BROM (above) | Rust flows (`mtk_brom_info`, `mtk_brom_backup`) | `flow-run mtk_brom_backup` |
| **UNISOC/SPD** | 1782:4d00 FDL1+FDL2 (SC9863A, T606/UMS9230) | Rust flows (`spd_*` rows) + `src/spd.rs` | `flow-run spd_detect_info` (CLI: `spd-detect`, `spd-frp`, `spd-format`, `spd-magic-pack`) |
| **HiSilicon Kirin** | 12d1 — अभी koi open flow nahi (not reverse-engineered) | (none yet) | (none) |

(Purani `python/core/flows/*.py` engine modules kabhi ship nahi hue;
`mtk-brom-backup` `mtk_brom_backup` flow row hai. Har key `flow-list` se verify karo.)

## Flow key → function map

GUI ke FRP actions jo bhi flow call kar sakte hain. Keys Rust registry rows hain
(`src/flows.rs`, `flow-list` se verify); GUI (job, mode) se route karta hai aur
bridge `flow-run <key> [target]` se chalata hai.

| Flow key | Engine | Kya karta hai |
|---|---|---|
| `adb_frp` | Generic ADB | `settings put secure frp 0` + disable setup wizards + clear GMS data |
| `frp_browser` | Generic ADB | on-device via intent `chrome://settings/` open karna |
| `frp_emergency` | Generic ADB | Emergency-call dialer se Settings open (on-device) |
| `frp_settings` | Generic ADB | notification-shade path se Settings open (on-device) |
| `frp_fake_login` (`_testdpc`, `+_adp`) | Generic ADB | device-owner DPC ke saath QR provisioning, phir FRP clear |
| `at_info` | Samsung MTP/AT | AT channel se mode + devconinfo read karna (Samsung pre-Android 8) |
| `at_method` | Samsung MTP/AT | diag port par ADB enable karne ke liye AT+DEBUGLVC |
| `download_frp` | Samsung Download mode | CSC/Combination firmware FRP remove (PIT safety contract) |
| `odin_enable_adb` | Samsung Download mode | Odin tarball se download mode se ADB enable |
| `mtk_combo_flash` | MTK Download | Combination firmware flash (PIT + DA) |
| `mtk_recovery_reset` | MTK Download | Recovery-mode factory reset |
| `mtk_brom_info` | MTK BROM | chip id / handshake read (kisi bhi BROM flash se pehle zaroori) |
| `mtk_brom_backup` | MTK BROM | BROM DA se partitions dump |
| `edl_frp` | Qualcomm EDL | Sahara + Firehose erase (05c6:9008) |
| `qcom_detect_info` | Qualcomm EDL | Detect + info (read-only) |
| `frp_qr_provision` | Generic ADB | QR provisioning (TestDPC path) |

(Retired: purane `flow_*`-prefixed key names aur
`python/core/flows/*.py` kabhi shipped nahi hue — keys mein `flow_` prefix nahi hai.)

## Naya per-model recipe yahan kaise land hota hai

1. **Real device dump run karo** (ADB-side path ke liye `scripts/dump-connected.sh`,
   Unisoc par BROM-side path ke liye `flashpilot-bridge spd-format`). Dump
   `build/cache/dumps/<model>_<codename>/` mein jata hai.

2. **Dump se identify karo** engine + chip + FRP partition
   name (almost always `frp`, `frp_a`, ya `userdata` Android 11+ par).

3. **Device entry add karo** `python/gui/supported_devices.json` mein
   right brand ke under, with `actions: ["frp", "info", "backup", "flash"]`
   aur `status: "researched"`. (existing per-engine flow automatically pickup
   kar lega — new flow nahi chahiye jab tak engine itself missing nahi hai.)

4. **Short research note drop karo** `operations/frp/devices/<brand>/<model>.md`
   mein chip, engine, partition, build fingerprint, aur ek one-liner
   confirming recipe ke saath (e.g. "mmcblk0p4 = frp, instant
   BROM DA erase, no combo needed"). Format ke liye
   `operations/frp/devices/nokia/nokia_g20.md` dekho.

5. **Agar engine itself mein flow nahi hai** is chipset ke liye, flow register
   karo `src/flows.rs` में (ek `flow!(...)` row) aur CLI dispatch
   `src/<engine>.rs` + `src/main.rs` में add karo.

## Why per-chip files are gone

Earlier refactors ne god `frp.py` ko per-chip files mein
`operations/frp/chips/` ke under aur per-engine files `operations/frp/{mtk,qualcomm,unisoc,samsung}_frp/`
ke under split kiya. Is INDEX ka ek older revision dead docstubs aur ek
`python/core/flows/brom.py` dispatch claim karta tha — woh module kabhi shipped nahi hua.
Real per-chip dispatch Rust flow registry hai (`src/flows.rs`: `mtk_*`/`qcom_*`/`spd_*` rows,
verify karne ke liye `flow-list`); yah INDEX.md map hai taaki naya dev jane
engine-specific code actually kahan lives.

## Why per-engine Python shims are gone

`operations/frp/mtk_frp/mtk_frp.py` (and its 4 siblings) functions
`python.core.flows.brom` se import karte the aur unhe ek **second**
`FLOWS = {}` dict ke under re-export karte the jo GUI kabhi read nahi karta.
Woh canonical `FLOWS` se `python/core/flows/__init__.py` mein collide karte the
aur GUI ever unhe read karta to real ones mask kar dete. Unhe per engine
folder mein README se replace kiya gaya jo real Python modules ko point karta hai.
