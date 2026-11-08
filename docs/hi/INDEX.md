# FlashPilot — सूचकांक (Index)

Language switcher: [English](../INDEX.md) · [Français](../fr/INDEX.md) · [Español](../es/INDEX.md) · [Deutsch](../de/INDEX.md) · [简体中文](../zh/INDEX.md) · [Русский](../ru/INDEX.md) · [Português](../pt/INDEX.md) · [日本語](../ja/INDEX.md) · [العربية](../ar/INDEX.md) · **हिन्दी** · [Türkçe](../tr/INDEX.md)

> English canonical source है। यह पेज अनुवाद है; सहायता चाहिए — देखें [`../TRANSLATION.md`](../TRANSLATION.md).

README marketing ka kaam karta hai. Yeh file engineering index hai — har folder kya karta hai aur kahan se shuru karna hai. (Note: niche headings Romanized Hinglish mein hain taaki code/identifiers English rahen.)

## चलाना (Run)

```bash
# GUI
python main.py

# CLI (bridge) — same protocol, bina GUI
./target/release/flashpilot-bridge detect-all
./target/release/flashpilot-bridge spd-detect
```

## जड़ लेआउट (Root layout) — 17 प्रविष्टियाँ

| प्रविष्टि | क्या है | कब खोलें |
|---|---|---|
| `main.py` | ऐप एंट्री पॉइंट। रिपॉज़िटरी को `sys.path` में जोड़ता है और `python.gui.qt_app.main()` कॉल करता है। | ऐप का बूट बदलने के लिए। |
| `pyproject.toml` | Python पैकेज मेटाडेटा (name=flashpilot, deps, build backend)। | Python dependency जोड़ने या version bump के लिए। |
| `Cargo.toml` / `Cargo.lock` | Rust core (`flashpilot-bridge` binary)। | Bridge CLI बदलने या protocol जोड़ने के लिए। |
| `python/` | Rust engine ke upar thin Python layer: `python/core/` (shim + GUI helpers) aur `python/gui/` (PyQt6). Saare flows `src/flows.rs` mein hain. | GUI aur device plumbing. |
| `src/` | Rust sources. Layout `python/core/` ko mirror karta hai. | Nayi bridge command add ya USB protocol change karne ke liye. |
| `tests/` | pytest suite. ~149 tests, ~1s run. | `.venv/bin/python -m pytest tests/ -q` chalane ke liye. |
| `scripts/` | Standalone shell tools. Aaj kal: `dump-connected.sh`, `validate_mtp_at.py`. | Non-GUI batch operation chahiye ho toh. |
| `docs/` | README assets (screenshots, logo). | README ke liye. |
| `packaging/` | `.deb` build script + control files. | Release ship karne ke liye. |
| `root/` | udev rules (taaki phones bina sudo kaam karein). | Ek-baar setup. |
| `operations/` | **Per-job documentation trees** — neeche "operations/" section dekho. | Kisi specific job ko samajhne ke liye (FRP, MDM, screen lock, etc.). |
| `build/` | **Saare gitignored build/runtime artifacts** — neeche "build/" section dekho. | Lagbhag kabhi nahi khola jata. |
| `.github/` | CI workflows, issue templates. | CI change karne ke liye. |
| `LICENSE` `CODE_OF_CONDUCT.md` `CONTRIBUTING.md` `SECURITY.md` `DESCRIPTION.md` | Standard project metadata. | Release ke time. |

## `python/` layout

```
python/
├── main.py                 <- app entry (adds repo to sys.path, calls python.gui.qt_app.main)
├── gui/                    <- PyQt6 app
│   ├── qt_app.py           <- The main window + every device-mode UI (~12k LOC)
│   ├── devices.py          <- Data-driven "supported devices" drill-down (brand -> model -> action)
│   ├── theme.py            <- Design tokens (colors, button styles, version helpers)
│   ├── animations.py       <- Painted glyphs: connection scene, status orb, etc.
│   ├── nav.py              <- Top-level navigation rail + OEM chip bar
│   ├── toast.py            <- Toast notifications
│   └── supported_devices.json  <- The database of which model gets which action
└── core/                   <- Thin Python layer (no Qt deps; delegates to Rust bridge)
    ├── core.py             <- FLOWS/JOBS/MODES mirror (hardcoded cache + Rust flow_list())
    ├── bridge.py           <- Talks to the Rust `flashpilot-bridge` binary
    ├── flow.py             <- Flow/Step primitives + cancellation
    ├── jobs.py             <- FlashJob lifecycle (isolated job layer)
    ├── cancel.py           <- Cooperative cancellation registry
    ├── devices.py          <- Multi-device identity (stable keys, list, resolve, transport mapping)
    ├── frp.py              <- FRP-only re-export surface (name == responsibility)
    ├── mtk.py              <- MTK PIDs/stages/chips (0003=BROM, 2000=preloader)
    ├── mtp.py              <- Samsung MTP/AT (multi-sequence ADB enable)
    ├── pit.py pitstore.py  <- Samsung PIT parser + cache
    ├── adb.py device_info.py actions.py experimental.py fus.py
    └── (no flows/ dir)     <- flows live in src/flows.rs; Python only delegates via bridge.flow_run()
```

**Flows Rust mein hote hain.** `python/core/core.py` ek thin shim hai: `_RustFlow` execution `bridge flow-run <key>` par delegate karta hai. Canonical registry `src/flows.rs` hai (`flow!` macro, ~280 rows); Python GUI lookup ke liye mirror karta hai.

## `src/` layout (Rust)

```
src/
├── main.rs                 <- All CLI dispatch (eprintln! is the "log" channel) + flow-run
├── flows.rs                <- THE flow registry (flow! macro; FLOWS/JOBS/MODES)
├── usb/                    <- libusb context, descriptor parsing, filtering (mod.rs + filtering.rs)
├── devices.rs              <- merged USB+ADB device rows
├── sam_download.rs         <- Samsung Download/Odin session (odin-* commands)
├── sam_errors.rs sam_setup.rs sam_*.rs  <- Samsung helpers
├── mtk.rs mtk_da.rs        <- MediaTek BROM/DA flashing
├── mtk_exploit.rs          <- BROM exploits (bypass/kamakiri2/crash-to-BROM)
├── mtk_sla.rs mtk_sla_keys.rs <- Secure Lock Authentication
├── mtk_daloader.rs         <- DA container parsing
├── qualcomm/               <- EDL: Sahara + Firehose + GPT
├── spd.rs                  <- UNISOC BSL (BSL_CMD_*, BSL_REP_*, FDL1/FDL2)
├── pac.rs                  <- SPD PAC extract/pack
├── pit.rs                  <- Samsung PIT parser
├── mtp.rs at.rs adb.rs     <- MTP, AT command, ADB plumbing
├── fastboot.rs             <- native fastboot transport
├── moto_flash.rs           <- Motorola staged fastboot FRP
├── apple.rs                <- Apple usbmuxd/lockdown
├── bulk.rs hid.rs          <- bulk + HID helpers
├── fwtar.rs sparse.rs imgtools.rs <- firmware tar/sparse/boot-vbmeta
├── hostinfo.rs             <- host eMMC/UFS health
├── config.rs error.rs util.rs device.rs
└── (no odin.rs)            <- Odin logic sam_download.rs mein hai
```

## `operations/` — per-job documentation trees

Yeh folders **per-operation README trees** hold karte hain jo explain karte hain ki har job kaise kaam karta hai, kaun se flow keys use karta hai, kaun se devices supported hain, aur known caveats. Yeh code nahi hai — tree pure markdown hai (ek past cleanup ne stale `.py` shims remove kiye jo yahan the; koi bhi `operations/` import nahi karta). Code `src/flows.rs` (the `flow!` registry; `python/core/core.py` ek thin shim hai) aur domain-specific modules (`knox.py`, `qcn.py`, `imei.py`, `emmc.py`, …) mein hai. `operations/` ki READMEs end users / commercial-tool researchers ke liye hain; code source of truth hai.

| Folder | Kya | Real code kahan hai |
|---|---|---|
| `operations/apple/` | Apple icloud, activation lock, MDM, passcode/lost mode remove | Rust flows (`src/flows.rs`: `apple_*` rows, `flow-run` CLI) |
| `operations/frp/` | FRP bypass per-engine + per-device research notes. **`operations/frp/INDEX.md` se shuru karo**. | Rust flows (`src/flows.rs` registry, `flow-run` CLI); thin `python/core/core.py` shim |
| `operations/mdm/` | MDM / device-owner unlock + per-brand device notes | Rust flows (`src/flows.rs` registry, `flow-run` CLI) |
| `operations/screen_unlock/` | Screen lock remove (ADB / recovery / download / comprehensive) | Rust flows (`src/flows.rs` registry, `flow-run` CLI) |
| `operations/battery/` | Battery report / repair / load test (ADB ke through) | Rust flows (`src/flows.rs` registry, `flow-run` CLI) |
| `operations/network/` | SIM state, DNS, radio reset | Rust flows (`src/flows.rs` registry, `flow-run` CLI) |
| `operations/carrier_unlock/` | Carrier lock (Apple, MTK) | Rust flows (`src/flows.rs` registry, `flow-run` CLI) |
| `operations/flashing/` | Per-vendor flashing guides (Samsung Odin, MTK DA, Qualcomm EDL, UNISOC SPD, PIT) | Rust flows (`src/flows.rs` registry, `flow-run` CLI) |
| `operations/usb/` | USB enumeration aur detection notes | `src/usb/`, `src/devices.rs`, `python/core/devices.py` |

## `build/` — gitignored runtime/build artifacts

| Subdir | Contents | Kisne banaya |
|---|---|---|
| `build/target/` | Rust `cargo build` output | `cargo build` |
| `build/dist/` | `.deb` packages | `packaging/build-deb.sh` |
| `build/cache/` | Per-device TAR caches aur reverse-engineered dumps | GUI / `scripts/dump-connected.sh` |
| `build/mdm_qr/` | Generated MDM provisioning QR codes | GUI MDM flow |
| `build/pit/` | Cached `.pit` partition-table files | GUI PIT flow |

**Rule:** `build/` se kabhi `git add` mat karo. State wipe karna ho toh subdirectory delete kar do — rebuild ho jayega.

## Naya feature kaise add karein (cheat sheet)

| Aap chahte ho... | Touch karo |
|---|---|
| Supported list mein naya device | `python/gui/supported_devices.json` |
| Supported device ke liye naya per-vendor action | `src/flows.rs` (ek `flow!(...)` row add karo); Python auto-discover karta hai `bridge.flow_list()` ke through |
| Existing concern ke liye naya ADB-command flow | same as above (Rust `src/flows.rs`) |
| Naya bridge CLI command | `src/<concern>.rs` + `src/main.rs` (`<cmd>` arm in match) |
| Naya top-level nav page | `python/gui/qt_app.py` (`_build_*_page` + `_section_index`) |
| Naya design color / button style | `python/gui/theme.py` (`C` dict / `_btn_*()`) |
| Naye device ke per-job notes document karna | `operations/<job>/<brand>/<model>.md` |
| Test add karna | `tests/test_<area>.py`, `test_mtk.py` pattern follow karo |

## Operation runner kaise kaam karta hai (ek baar padho)

GUI kabhi direct flow call nahi karta. Per-operation device picker (`FlashPilotWindow._choose_device`) pehle stable device key resolve karta hai; phir `_run_ops_flow` / `_run_job_flow` `python.core.core.flow_for(job, mode, method)` call karte hain, jo `Flow()` object (list of `Step()`s) return karta hai, phir `flow.run(ctx, log)` worker thread mein `devices.device_scope(key)` ke andar call hota hai (taaki every resolver chosen phone target kare). Har flow `log(line)` callable mein log karta hai jise GUI console se wire karta hai. Cancellation per-device scoped hai (`flow.request_cancel(key)`; keyless broadcast sab stop karta hai), har `_run` ke top pe check hota hai.

Flow add karne ke liye: ek `flow!("my_op", "My op", "Job Name", "MODE")` row `src/flows.rs` mein add karo. Python `bridge.flow_list()` se auto-discover karta hai aur GUI ka job/mode/method drill-down automatically pick up karta hai. Rust `flow-run` CLI execute karta hai; resolvers ek target serial/`vid:pid@bus:addr` accept karna chahiye (dekho `src/device.rs`).