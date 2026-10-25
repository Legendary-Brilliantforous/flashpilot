# FlashPilot — index

The README has the marketing. This file is the engineering index — every
folder, what it does, and where to start.

## Run it

```bash
# GUI
python main.py

# CLI (bridge) — same protocol, no GUI
./target/release/flashpilot-bridge detect-all
./target/release/flashpilot-bridge spd-detect
```

## Root layout (17 entries)

| Entry | What | When you open it |
|---|---|---|
| `main.py` | The app entry point. Adds the repo to `sys.path` and calls `python.gui.qt_app.main()`. | To change how the app boots. |
| `pyproject.toml` | Python package metadata (name=flashpilot, deps, build backend). | To add a Python dep or bump the version. |
| `Cargo.toml` / `Cargo.lock` | Rust core (the `flashpilot-bridge` binary). | To change the bridge CLI or add a new protocol. |
| `python/` | Thin Python layer over the Rust engine: `python/core/` (shim + GUI helpers) and `python/gui/` (PyQt6). All flows live in `src/flows.rs`. | GUI and device plumbing. |
| `src/` | Rust sources. Mirrored layout to `python/core/`. | When you add a new bridge command or change a USB protocol. |
| `tests/` | pytest suite. ~149 tests, runs in ~1s. | Run with `.venv/bin/python -m pytest tests/ -q`. |
| `scripts/` | Standalone shell tools. Today: `dump-connected.sh`, `validate_mtp_at.py`. | When you need a non-GUI batch operation. |
| `docs/` | README assets (screenshots, logo). | For the README. |
| `packaging/` | `.deb` build script + control files. | To ship a release. |
| `root/` | udev rules (so phones work without sudo). | One-time setup. |
| `operations/` | **Per-job documentation trees** — see "operations/" section below. | When you want to understand a specific job (FRP, MDM, screen lock, etc.). |
| `build/` | **All gitignored build/runtime artifacts** — see "build/" section below. | You almost never open this. |
| `.github/` | CI workflows, issue templates. | To change CI. |
| `LICENSE` `CODE_OF_CONDUCT.md` `CONTRIBUTING.md` `SECURITY.md` `DESCRIPTION.md` | Standard project metadata. | When releasing. |

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

**Flows live in Rust.** `python/core/core.py` is a thin shim: `_RustFlow`
delegates execution to `bridge flow-run <key>`. The canonical registry is
`src/flows.rs` (`flow!` macro, ~280 rows); Python mirrors it for GUI lookup.

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
└── (no odin.rs)            <- Odin logic lives in sam_download.rs
```

## `operations/` — per-job documentation trees

These folders hold **per-operation README trees** that explain how each
job works, which flow keys it uses, which devices it supports, and
known caveats. They are **not** code — the tree is pure markdown (a past
cleanup removed the stale `.py` shims that used to live here; nothing
imports `operations/`). The code lives in `src/flows.rs` (the `flow!` registry; `python/core/core.py` is a thin shim) and the per-domain
modules (`knox.py`, `qcn.py`, `imei.py`, `emmc.py`, …). The READMEs in
`operations/` are written for end users / commercial-tool researchers;
the code is the source of truth.

| Folder | What | Real code in |
|---|---|---|
| `operations/apple/` | Apple icloud, activation lock, MDM, passcode/lost mode remove | Rust flows (`src/flows.rs`: `apple_*` rows, `flow-run` CLI) |
| `operations/frp/` | FRP bypass per-engine + per-device research notes. **Start with `operations/frp/INDEX.md`**. | Rust flows (`src/flows.rs` registry, `flow-run` CLI); thin `python/core/core.py` shim |
| `operations/mdm/` | MDM / device-owner unlock + per-brand device notes | Rust flows (`src/flows.rs` registry, `flow-run` CLI) |
| `operations/screen_unlock/` | Screen lock remove (ADB / recovery / download / comprehensive) | Rust flows (`src/flows.rs` registry, `flow-run` CLI) |
| `operations/battery/` | Battery report / repair / load test (over ADB) | Rust flows (`src/flows.rs` registry, `flow-run` CLI) |
| `operations/network/` | SIM state, DNS, radio reset | Rust flows (`src/flows.rs` registry, `flow-run` CLI) |
| `operations/carrier_unlock/` | Carrier lock (Apple, MTK) | Rust flows (`src/flows.rs` registry, `flow-run` CLI) |
| `operations/flashing/` | Per-vendor flashing guides (Samsung Odin, MTK DA, Qualcomm EDL, UNISOC SPD, PIT) | Rust flows (`src/flows.rs` registry, `flow-run` CLI) |
| `operations/usb/` | USB enumeration and detection notes | `src/usb/`, `src/devices.rs`, `python/core/devices.py` |

## `build/` — gitignored runtime/build artifacts

| Subdir | Contents | Created by |
|---|---|---|
| `build/target/` | Rust `cargo build` output | `cargo build` |
| `build/dist/` | `.deb` packages | `packaging/build-deb.sh` |
| `build/cache/` | Per-device TAR caches and reverse-engineered dumps | GUI / `scripts/dump-connected.sh` |
| `build/mdm_qr/` | Generated MDM provisioning QR codes | GUI MDM flow |
| `build/pit/` | Cached `.pit` partition-table files | GUI PIT flow |

**Rule:** never `git add` anything from `build/`. If you need to wipe
state, delete the subdirectory — it'll be rebuilt.

## How to add a new feature (the "which file do I touch?" cheat sheet)

| You want to... | Touch |
|---|---|
| Add a new device to the supported list | `python/gui/supported_devices.json` |
| Add a new per-vendor action to a supported device | `src/flows.rs` (add a `flow!(...)` row); Python auto-discovers via `bridge.flow_list()` |
| Add a new ADB-command flow for an existing concern | same as above (Rust `src/flows.rs`) |
| Add a new bridge CLI command | `src/<concern>.rs` + `src/main.rs` (`<cmd>` arm in match) |
| Add a new top-level nav page | `python/gui/qt_app.py` (`_build_*_page` + `_section_index`) |
| Add a new design color / button style | `python/gui/theme.py` (`C` dict / `_btn_*()`) |
| Document a new device's per-job notes | `operations/<job>/<brand>/<model>.md` |
| Add a test | `tests/test_<area>.py`, follow the `test_mtk.py` pattern |

## How the operation runner works (read this once)

The GUI never calls a flow directly. The per-operation device picker
(`FlashPilotWindow._choose_device`) resolves a stable device key first;
then `_run_ops_flow` / `_run_job_flow` call
`python.core.core.flow_for(job, mode, method)`, which returns a
`Flow()` object (a list of `Step()`s), then `flow.run(ctx, log)` is
called on a worker thread inside `devices.device_scope(key)` (so every
resolver targets the chosen phone). Every flow logs to a `log(line)`
callable that the GUI wires to its console. Cancellation is per-device
scoped (`flow.request_cancel(key)`; keyless broadcast stops everything),
checked at the top of each `_run`.

To add a flow: add one `flow!("my_op", "My op", "Job Name", "MODE")`
row to `src/flows.rs`. Python auto-discovers it via `bridge.flow_list()`
and the GUI's job/mode/method drill-down picks it up automatically.
The Rust `flow-run` CLI executes it; resolvers must accept a target
serial/`vid:pid@bus:addr` (see `src/device.rs`).
