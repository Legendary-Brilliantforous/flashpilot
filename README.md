# 🔧 FlashPilot

> **An open-source Samsung firmware flashing & repair workbench for Linux — an Odin / Heimdall alternative for flashing Galaxy phones (Download/Odin mode), MediaTek (BROM/DA), Qualcomm (EDL) and Spreadtrum/UNISOC devices.**

**Search keywords:** Samsung flashing tool · Odin alternative · Android firmware flashing Linux · Heimdall GUI · Galaxy phone repair · MTK BROM flash · Qualcomm EDL · FRP unlock · UNISOC flashing · device firmware tool · mobile repair · Android bootloader · USB flashing · Linux flashing suite · proprietary tool alternative

[![Rust](https://img.shields.io/badge/Rust-1.70+-orange?logo=rust&logoColor=white)](https://www.rust-lang.org)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52)](https://www.riverbankcomputing.com/software/pyqt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![CI](https://github.com/Legendary-Brilliantforous/flashpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Legendary-Brilliantforous/flashpilot/actions)
[![Good First Issues](https://img.shields.io/github/issues/Legendary-Brilliantforous/flashpilot/good%20first%20issue)](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
[![Contributors](https://img.shields.io/github/contributors/Legendary-Brilliantforous/flashpilot)](https://github.com/Legendary-Brilliantforous/flashpilot/graphs/contributors)

**What is this?** A Linux-native equivalent of the paid Windows flashing suites — one unified tool that talks straight to the bootloader of **Samsung, MediaTek, Qualcomm and Spreadtrum/UNISOC devices**. Reverse-engineered protocols + native Rust performance + a beautiful PyQt6 GUI = the open alternative to Odin, Heimdall, and expensive commercial tools.

---

## ✨ Why this project matters

The Android repair world runs on closed, Windows-only commercial tools. Their protocols are reverse-engineered by a small community of tinkerers — and most of that knowledge is locked inside paid suites or scattered across forums in incomplete form.

**This project is our answer.** It turns those reverse-engineered protocols into a clean, auditable, MIT-licensed codebase that anyone can read, run, extend — and ship as their own flashing suite.

| Commercial tool | Windows-only, closed source | This project |
|---|---|---|
| Odin / Smart Switch | Windows, GUI only | Open-source Odin protocol + leaked odin4 + PIT tools |
| MTK flash tools | Windows, closed DA | MTK BROM/DA flashing & backup (scatter + GPT) |
| Qualcomm EDL tools | Windows | Sahara + Firehose protocol implementation |
| SPD/UNISOC tools | Windows | Clean-room BSL download implementation |
| FRP / lock tools | Paid, grey-market | Transparent ADB + download-mode flows, MDM unlock |

---

## 🚀 Highlights — 1.2.1-beta (0 warnings)

- **9 transport modes** — ADB, MTP, Samsung Download mode, Samsung BROM, MTK, MTK BROM, Fastboot, Qualcomm EDL, SPD.
- **13 job categories** — Flash Firmware, Remove FRP, Remove Screen Lock, Remove MDM, Unlock Carrier, Read Device Info, Detect Devices, Reboot, Repair Settings, plus per-chip EXPERIMENTAL: Knox / Warranty (Samsung), QCN / Modem (Qualcomm), IMEI Repair / Change (MTK/SPD/Qualcomm), eMMC / UFS.
- **Multi-device** — plug in several phones: the connection bar lists each one, every operation asks which phone it applies to (or runs silently when only one matches), and different phones can run operations in parallel (one op per device, STOP broadcasts to all).
- **Rust core (`flashpilot-bridge`, ~9.3k LOC) — 0 `cargo check` warnings** — raw USB with *vendored libusb* (no system deps), real protocol implementations (+ 18 wired dead-paths, `-80KB` ltcg trim).
  - **Samsung**: reverse-engineered Odin session protocol (Heimdall-based), HID download-mode payloads, PIT read/write/flash — AT `Context` retained, `EndpointConfig` chunking.
  - **MediaTek**: BROM / preloader / DA handshake, scatter & GPT, BROM exploits, SLA keys — `ProgressReporter` real %.
  - **Qualcomm**: Sahara `ProtocolError` + Firehose `QcomDeviceInfo` wired via `Duration` timeouts.
  - **SPD/UNISOC**: clean-room BSL — all `BSL_CMD/REP`, `iface`, `flush/read_flash/chip_uid/power_off` wired.
  - Plus **MTP**, **AT-command**, and full **ADB** plumbing.
- **A studio-grade GUI** — frameless translucent window, 10 accent themes, animated cable/status scene, live console.
  - **Dynamic version** — installed `APP_VERSION` via `importlib.metadata` (deb truth), `_display_version` `1.2.0→1.2`, live GitHub latest stable, BETA pill.
  - **Big centered dialogs (620px, draggable, ✕)** — beta gate + stable `UPDATE/AHEAD/PATCH` + flash/FRP confirms, chip colors `MTK amber` `QCOM red` `SPD violet` `SAMSUNG blue`, high-contrast text.
  - **Per-chip EXPERIMENTAL collapsibles** — Knox (Samsung), QCN/IMEI (Qualcomm), IMEI (MTK/SPD): amber banner, every-run ownership checkbox, `I UNDERSTAND` type-to-confirm for IMEI change, audit-logged.
  - **⏹ STOP** in titlebar stops all running operations; per-device locks let other phones keep working.

---

## 📸 Screenshots

| Samsung ops | MediaTek workbench | Battery repair | SPD download |
|---|---|---|---|
| ![Samsung](docs/samsung.png) | ![MediaTek](docs/mtk.png) | ![Battery](docs/battery.png) | ![SPD](docs/spd.png) |

---

## 🧩 Feature matrix

| Capability | Samsung | MediaTek | Qualcomm | SPD/UNISOC | Any ADB |
|---|---|---|---|---|---|
| Detect / info | ✅ | ✅ (+ crash preloader→BROM) | ✅ (Sahara) | ✅ | ✅ |
| Flash firmware | ✅ (Odin / odin4) | ✅ (scatter + GPT) | ✅ (Firehose) | ✅ (FDL/regions) | — |
| Backup partitions | ✅ (EFS) | ✅ | ✅ | ✅ | — |
| FRP bypass | ✅ (ADB + download) | ✅ | ✅ (EDL) | ✅ | ✅ |
| Screen-lock removal | ✅ | ✅ | ✅ (EDL) | — | ✅ |
| MDM unlock | ✅ (ADB, QR, recovery) | — | — | — | — |
| Knox warranty/bypass (EXPERIMENTAL) | ✅ | — | — | — | — |
| QCN backup/restore + IMEI repair/change (EXPERIMENTAL) | — | ✅ (NVRAM) | ✅ (NV 550/682) | ✅ (BSL NV) | — |
| Partition tools | ✅ (PIT) | ✅ (GPT) | ✅ | ✅ (PAC extract/pack) | — |
| Low-level exploits | ✅ (HID/BROM) | ✅ (BROM exploit, SLA) | ✅ (Sahara) | ✅ (BSL) | — |
| Battery / network repair | — | — | — | — | ✅ |

> 💡 **Battery** and **Network** sections work on *any* Android device with USB debugging — no vendor hardware needed.

---

## 🖥️ The GUI

A frameless, translucent, radius-card window with a live **connection banner** (computer → cable → phone scene with an animated data pulse) above a left **nav rail** and a right **console/log pane**.

- **Connection bar** — live device list (one row per phone: model · serial · transports); click a row to inspect it. Operation buttons ask which phone when several match.
- **Samsung** — TFT-style sub-tabs: `ODIN FLASH · UNLOCK · ADVANCED FLASH · INFO & TOOLS`, plus firmware slots (AP/BL/CP/CSC/USERDATA), Odin utilities, and a `KNOX — EXPERIMENTAL` collapsible.
- **MediaTek / Qualcomm / SPD** — dedicated workbenches with native low-level tools (scatter/DA + crash-to-BROM, programmer/XML + QCN/IMEI, FDL binaries + base addresses + IMEI), each with its own `— EXPERIMENTAL` collapsible.
- **Battery** — fuel-gauge health %, temp/voltage/current, top consumers; one-click repair.
- **Network** — SIM state, data/Wi-Fi flags, DNS mode; radio reset & re-registration.
- **Settings** — auto-scan interval, default paths, console auto-clear, 10 accent themes, animations (shake/rubber/cable/bubble toggles), window glow, engine status, and in-app `cargo build`.

**Shortcuts:** `F5` rescan · `Ctrl+Enter` run · `Ctrl+L` clear console · `Ctrl+S` save log · `Ctrl+F` find.

---

## 📦 Quick start

**Requirements:** Rust toolchain, Python 3.10+, a Linux desktop. That's it — libusb is vendored.

```bash
# 1. Build the Rust bridge (first build compiles libusb from source)
cargo build --release

# 2. (Recommended) install the USB udev rules so phones need no sudo
sudo bash root/setup-usb.sh

# 2b. Fetch the proprietary odin4 binary (Samsung download-mode flashing).
#     It is NOT redistributed here for legal reasons; this pulls it from a
#     public mirror and verifies it runs.
bash scripts/fetch-odin4.sh

# 3. Python environment
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Launch
.venv/bin/python -m python.main        # or: python3 main.py
```

The **odin4** tool (Samsung download-mode flashing) is fetched at setup by `scripts/fetch-odin4.sh` — Samsung's proprietary binary is not redistributed in this repo. Samsung combo firmware should be sourced from Samsung's official support pages or trusted firmware archives.

---

## 🖥️ Platform support — we want your words

**Linux is the supported platform.** FlashPilot is deliberately *the Linux-native
answer to Windows-only flashing suites* — development, testing and releases
target Linux, and that is not changing.

**Windows / macOS are not supported today**, for practical reasons:

- `odin4` (Samsung flashing) is a Linux-only binary — Windows would need a
  different flash path entirely.
- Windows USB is driver hell per phone mode (Zadig/WinUSB, QDLoader, Samsung
  drivers fighting each other); most "phone not detected" reports would be
  undebuggable remotely.
- macOS adds signing/notarization overhead for near-zero repair-shop demand.
- The stack *is* portable (Rust + rusb, Python, Qt), so this is a maintenance
  decision, not a technical impossibility.

**But this is an open question, not a verdict.** If you want Windows/macOS
support — or you want to argue Linux-only forever — tell us:

- 💬 Open a **[Discussion](https://github.com/Legendary-Brilliantforous/flashpilot/discussions)**
  with your use case (repair shop? lab? which OS? which phones?).
- 🔧 Code speaks loudest: the plan is a `python/core/platform.py` abstraction
  (`open_file_manager()`, `detach_kernel_drivers()`, `usb_device_path()`,
  `needs_udev_setup()`) with Linux as the only backend, so ports become
  additive PRs instead of forks. PRs in that direction are welcome now.
- 🎨 Related: contributors have proposed **PySide6** (LGPL, license-compatible
  with this MIT project) over PyQt6 (GPLv3). Weigh in on the same Discussion —
  the migration is mechanical but needs GUI smoke-test coverage first.

No decision will be made without contributor voices. Come and be one of them.

### CLI / bridge

```bash
./target/release/flashpilot-bridge detect          # all USB + Samsung filter (JSON)
./target/release/flashpilot-bridge mtk-detect      # MediaTek BROM (0e8d:0003) / preloader (0e8d:2000) / DA
./target/release/flashpilot-bridge mtk-crash-brom <bus:addr>  # crash preloader into held BROM
./target/release/flashpilot-bridge qcom-detect     # Qualcomm EDL
./target/release/flashpilot-bridge spd-detect      # Spreadtrum/UNISOC (VID 0x1782)
./target/release/flashpilot-bridge odin-pit 04e8:xxxx@bus:addr  # read PIT
./target/release/flashpilot-bridge at-send <t> ATI # AT over CDC ACM
./target/release/flashpilot-bridge adb-devices     # adb devices -l as JSON
```

---

## 📁 Repository layout

```
flashpilot/
├── src/                      # Rust bridge (~13k LOC)
│   ├── main.rs               #   command-line entry (80+ commands)
│   ├── usb.rs                #   USB enumeration / interfaces (+ port_numbers)
│   ├── odin.rs               #   reverse-engineered Odin session protocol
│   ├── mtk.rs mtk_da.rs      #   MediaTek BROM/DA flashing
│   ├── mtk_exploit.rs        #   BROM exploits (bypass/kamakiri2/crash-to-BROM)
│   ├── mtk_sla.rs            #   MediaTek SLA key handling
│   ├── qualcomm/             #   Sahara + Firehose + GPT (EDL)
│   ├── spd.rs                #   Spreadtrum/UNISOC BSL protocol (+ PAC)
│   ├── mtp.rs at.rs adb.rs   #   MTP, AT command, ADB plumbing
│   └── config.rs error.rs util.rs
├── python/
│   ├── core/
│   │   ├── core.py           #   THE registry: FLOWS / JOBS / MODES + all flows
│   │   │                     #   (verb-first jobs; short snake_case method keys)
│   │   ├── frp.py            #   FRP-only re-export (name == responsibility)
│   │   ├── devices.py        #   multi-device identity: stable keys, list,
│   │   │                     #   resolve, transport mapping, thread scope
│   │   ├── bridge.py         #   talks to the Rust binary (+ per-key cancel)
│   │   ├── flow.py           #   Flow/Step primitives (+ per-key cancel)
│   │   ├── mtp.py            #   Samsung MTP/AT (multi-sequence ADB enable)
│   │   ├── mtk.py            #   MTK PIDs/stages/chips (0003=BROM, 2000=preloader)
│   │   ├── knox.py qcn.py imei.py emmc.py pac.py  # EXPERIMENTAL domains
│   │   ├── experimental.py   #   per-run ack gates + audit log (Q2-B strict)
│   │   ├── pit.py pitstore.py safety.py flashing.py fastboot.py
│   │   └── adb.py device_info.py health.py integrity.py knox.py ...
│   └── gui/
│       ├── qt_app.py         #   the PyQt6 studio (~12k LOC)
│       ├── devices.py        #   brand→model→action drill-down pages
│       ├── nav.py            #   nav rail + OEM chip bar
│       ├── theme.py          #   tokens (accent vs focus_ring/sel_border) + QSS
│       ├── animations.py     #   Motion (shake/rubber serialized, no stuck state)
│       └── supported_devices.json  #   brand/model/chip research table
├── docs/                     # screenshots (fresh) + logo
├── root/                     # udev rules (odin4 fetched by scripts/fetch-odin4.sh)
├── scripts/                  # fetch-odin4.sh, dev scripts
├── pit/ mdm_qr/              # sample PIT + MDM QR provisioning assets (git-ignored)
└── tests/                    # pytest suite (flow, MTK, PIT, odin safety, devices…)
```

---

## 🧑‍💻 Contributing

**This project only gets better with you.** We want maintainers, protocol hackers, GUI designers, doc writers, and testers.

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — everything you need to start.
- **Start with the [`good first issue`](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) label** — curated, beginner-friendly tasks.
- Use the **[bug report](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml)** / **[feature request](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=enhancement&template=feature_request.yml)** templates.
- **Beginner-friendly tasks** — every `flow_*` function in `python/core/core.py` is an opportunity: add a method, tune a command sequence, wire up a new device combo.
- **No prior flashing experience required.** The flow framework (`python/core/core.py`) is dead simple — a new method is ~5 lines:

```python
def flow_my_method():
    return Flow("my method", [Step("do thing", lambda ctx, log: log("hi"))])

FLOWS["my_method"] = flow_my_method              # short snake_case key
JOBS["Read Device Info"]["ADB"].append("my_method")  # ...and it shows in the GUI
```

It appears in the GUI automatically. That's the whole contribution loop: **write a flow, ship a feature.**
- **Multi-device rule** — never grab "the" device; accept `key=None` (ambient scope) and filter by it. See `python/core/devices.py` and `CONTRIBUTING.md`.
- **Naming rules** — jobs are verb-first (`Remove FRP`, not `FRP bypass`); flow keys are short snake_case (no `flow_` prefix in `FLOWS`); MTK PIDs are `0003`=BROM / `2000`=preloader (mtkclient convention — don't swap them).

**Ideas we'd love help with:**
- New device models / firmware combos in the flow tables.
- MediaTek DA variants, new scatter/GPT quirks.
- Qualcomm rawprogram & patch XML edge cases.
- Additional FRP / lock-removal methods per Android version.
- Packaging (Flatpak, AppImage, AUR, `cargo` + `pip`), CI, unit tests.
- More ODIN protocols, eMMC/UFS tooling, iCloud-adjacent and EDL utilities.
- Translations, themes, and accessibility.

---

## 🛡️ Safety & legality

This tool talks directly to bootloaders and can wipe data or brick a device if misused.

- Use it only on **devices you own or are authorized to service** (repair shops servicing customer phones with consent).
- Always read the on-screen warnings and **back up partitions** before flashing.
- Bypassing FRP/MDM on a device you don't own may be **illegal in your jurisdiction** — you are responsible for how you use this software.
- The project ships **no proprietary "secret sauce"** (HID unlock payloads, leaked DAs are *not* vendored) — you supply the firmware/binaries for your specific device, exactly like every commercial flashing suite.

---

## 📄 License

MIT — see [LICENSE](LICENSE). The Odin protocol constants are derived from the Heimdall project (MIT), and the SPD BSL reference comes from clean-room protocol write-ups (spd_cmd.h / Opus-Spreadtrum docs).

---

**Star ⭐ this repo, open an issue, send a PR — and let's build the best open flashing suite on Linux together.**
