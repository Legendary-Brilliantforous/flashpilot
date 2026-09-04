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
| `python/` | The whole app. Split into `python/core/` (engine) and `python/gui/` (PyQt6). | 99% of your work. |
| `src/` | Rust sources. Mirrored layout to `python/core/`. | When you add a new bridge command or change a USB protocol. |
| `tests/` | pytest suite. ~149 tests, runs in ~1s. | Run with `.venv/bin/python -m pytest tests/ -q`. |
| `scripts/` | Standalone shell tools. Today: `dump-connected.sh`, `fetch-odin4.sh`, `validate_mtp_at.py`. | When you need a non-GUI batch operation. |
| `docs/` | README assets (screenshots, logo). | For the README. |
| `packaging/` | `.deb` build script + control files. | To ship a release. |
| `root/` | udev rules (so phones work without sudo). | One-time setup. |
| `operations/` | **Per-job documentation trees** — see "operations/" section below. | When you want to understand a specific job (FRP, MDM, screen lock, etc.). |
| `build/` | **All gitignored build/runtime artifacts** — see "build/" section below. | You almost never open this. |
| `.github/` | CI workflows, issue templates. | To change CI. |
| `LICENSE` `CODE_OF_CONDUCT.md` `CONTRIBUTING.md` `SECURITY.md` `DESCRIPTION.md` | Standard project metadata. | When releasing. |
| `SPLIT_PLAN.md` | Historical refactor plan (now obsolete — was a workplan, not a spec). | For archaeology. |

## `python/` layout

```
python/
├── main.py                 <- usually re-exports the GUI entry; almost never the file you want
├── gui/                    <- PyQt6 app
│   ├── qt_app.py           <- The 11k-line main window + every device-mode UI. Yes, it's a monolith — by design, to keep the per-mode glue in one place.
│   ├── devices.py          <- Data-driven "supported devices" drill-down (brand -> model -> action)
│   ├── theme.py            <- Design tokens (colors, button styles, version helpers)
│   ├── animations.py       <- Painted glyphs: connection scene, status orb, etc.
│   ├── nav.py              <- Top-level navigation rail + OEM chip bar
│   ├── toast.py            <- Toast notifications
│   └── supported_devices.json  <- The database of which model gets which action
└── core/                   <- Engine (no Qt deps; usable from CLI)
    ├── bridge.py           <- Talks to the Rust `flashpilot-bridge` binary
    ├── mtp.py              <- Media Transfer Protocol sessions
    ├── mtk.py              <- MediaTek preloader/DA detection
    ├── spd_adb.py          <- SPD boot-image ADB-enable patch
    ├── pit.py              <- Samsung PIT partition-table parser
    ├── knox.py             <- Samsung Knox state checker
    ├── qcn.py              <- Qualcomm modemst (QCN) backup/restore
    ├── apple.py            <- Apple-specific flows
    ├── device_info.py      <- Live device identity (resolves serial/build/version with no fakes)
    ├── safety.py           <- Pre-flash safety contract
    ├── flows/              <- The operations: one module per concern, registers into a single `FLOWS` dict
    │   ├── __init__.py     <- Aggregates FLOWS, JOBS, MODES; GUI's lookup surface
    │   ├── adb.py          <- ADB-side operations
    │   ├── brom.py         <- MTK/MTK-Samsung BROM flows
    │   ├── screenlock.py   <- Screen lock remove (ADB, recovery, download, EDL)
    │   ├── mdm.py          <- MDM / device-owner unlock
    │   ├── frp.py          <- FRP bypass (the central flow)
    │   ├── oem_odin.py     <- Samsung Odin flows (advanced flash, PIT, vbmeta, EFS)
    │   ├── info.py         <- Read device info / reboot / factory reset
    │   ├── fastboot.py     <- Fastboot flows
    │   └── common.py       <- Shared helpers (process runners, integrity, AES, ODIN4 hashes)
    ├── flows.py            <- Legacy back-compat shim — import from `python.core.flows` instead
    └── frp.py              <- Legacy back-compat shim — import from `python.core.flows` instead
```

**Two `frp.py` files in `python/core/`?** Yes. They're intentional back-compat
shims (the test suite still imports `from python.core.frp`). New code
imports from `python.core.flows`. The shims will go away in 1.4.

## `src/` layout (Rust)

```
src/
├── main.rs                 <- All CLI dispatch (eprintln! is the "log" channel)
├── bridge/                 <- Cross-concern helpers (logging, paths)
├── usb/                    <- libusb context, descriptor parsing
├── mtk/                    <- MediaTek BROM / Download Agent / preloader
├── mtk_exploit.rs          <- kamakiri2 + friends (BROM auth bypass)
├── mtk_sla.rs              <- Secure Lock Authentication (RSA challenge)
├── mtk_sla_keys.rs         <- Known SLA keys for known chipsets
├── mtk_da.rs               <- Download Agent protocol
├── qualcomm/               <- EDL: Sahara + Firehose
├── spd.rs                  <- UNISOC BSL (BSL_CMD_*, BSL_REP_*, FDL1/FDL2)
├── odin.rs                 <- Samsung Odin session (0x64/0x01 probe, PIT, Tara, vbmeta)
├── mtp.rs                  <- MTP GetDeviceInfo (device vendor / model / serial)
├── at.rs                   <- AT-command channel (Samsung diag port)
├── apple.rs                <- Apple lockdown (DFU checkm8 placeholders)
├── adb.rs                  <- adb device-list / shell / devices
├── bulk.rs                 <- Bulk endpoint helper
├── hid.rs                  <- HID downloads
├── config.rs               <- Shared config + error types
└── error.rs                <- BridgeError + UsbError + ProtocolError
```

## `operations/` — per-job documentation trees

These folders hold **per-operation README trees** that explain how each
job works, which flow keys it uses, which devices it supports, and
known caveats. They are **not** code; the code lives in `python/core/flows/`.
The READMEs in `operations/` are written for end users / commercial-tool
researchers; the code is the source of truth.

| Folder | What | Real code in |
|---|---|---|
| `operations/apple/` | Apple icloud, activation lock, MDM, passcode/lost mode remove | `python/core/flows/apple.py` (or wherever it's registered) |
| `operations/frp/` | FRP bypass per-engine + per-device research notes. **Start with `operations/frp/INDEX.md`**. | `python/core/flows/{frp,brom,screenlock,oem_odin,info,mdm}.py` |
| `operations/mdm/` | MDM / device-owner unlock + per-brand device notes | `python/core/flows/mdm.py` |
| `operations/screen_unlock/` | Screen lock remove (ADB / recovery / download / comprehensive) | `python/core/flows/screenlock.py` |
| `operations/battery/` | Battery report / repair / load test (over ADB) | `python/core/frp.py` (legacy) — see `flows/screenlock.py` for the modern path |
| `operations/network/` | SIM state, DNS, radio reset | `python/core/frp.py` (legacy) |
| `operations/carrier_unlock/` | Carrier lock (Apple, MTK) | `python/core/flows/{mdm,brom}.py` |
| `operations/flashing/` | Per-vendor flashing guides (Samsung Odin, MTK DA, Qualcomm EDL, UNISOC SPD, PIT) | `python/core/flows/oem_odin.py` |
| `operations/usb/` | USB enumeration and detection notes | `python/core/{usb_watch,bridge}.py` |

The thin `__init__.py` in some of these is just to mark the folder as
intentional — it does **not** import code. (After the FRP-tree cleanup,
none of the operation folders have an `__init__.py`; the tree is pure
markdown.)

## `build/` — gitignored runtime/build artifacts

| Subdir | Contents | Created by |
|---|---|---|
| `build/target/` | Rust `cargo build` output | `cargo build` |
| `build/dist/` | `.deb` packages | `packaging/build-deb.sh` |
| `build/cache/` | Per-device TAR caches and reverse-engineered dumps | GUI / `scripts/dump-connected.sh` |
| `build/odin4_cache/` | Cached Odin4 archive downloads | `scripts/fetch-odin4.sh` |
| `build/mdm_qr/` | Generated MDM provisioning QR codes | GUI MDM flow |
| `build/pit/` | Cached `.pit` partition-table files | GUI PIT flow |

**Rule:** never `git add` anything from `build/`. If you need to wipe
state, delete the subdirectory — it'll be rebuilt.

## How to add a new feature (the "which file do I touch?" cheat sheet)

| You want to... | Touch |
|---|---|
| Add a new device to the supported list | `python/gui/supported_devices.json` |
| Add a new per-vendor action to a supported device | `python/core/flows/<concern>.py` (register in its `FLOWS = {}` block) |
| Add a new ADB-command flow for an existing concern | same as above |
| Add a new bridge CLI command | `src/<concern>.rs` + `src/main.rs` (`<cmd>` arm in match) |
| Add a new top-level nav page | `python/gui/qt_app.py` (`_build_*_page` + `_section_index`) |
| Add a new design color / button style | `python/gui/theme.py` (`C` dict / `_btn_*()`) |
| Document a new device's per-job notes | `operations/<job>/<brand>/<model>.md` (see `operations/frp/INDEX.md` for the per-device template) |
| Add a test | `tests/test_<area>.py`, follow the `test_mtk.py` pattern |

## How the operation runner works (read this once)

The GUI never calls a flow directly. It calls
`python.core.flows.flow_for(job, mode, method)`, which returns a
`Flow()` object (a list of `Step()`s), then `flow.run(ctx, log)` is
called on a worker thread. Every flow logs to a `log(line)` callable
that the GUI wires to its console. Cancellation is a shared
threading.Event that every step checks at the top of `_run`.

To add a flow: write `flow_my_op()` returning a `Flow(name, [Step(...)])`
in the right `python/core/flows/<concern>.py` file, then add it to that
file's `FLOWS = {}` dict. The GUI's job/mode/method drill-down picks it
up automatically.
