# 🔧 FlashPilot

Language switcher: [English](../../README.md) · [Français](../fr/README.md) · [Español](../es/README.md) · [Deutsch](../de/README.md) · [简体中文](../zh/README.md) · [Русский](../ru/README.md) · [Português](../pt/README.md) · [日本語](../ja/README.md) · [العربية](../ar/README.md) · **हिन्दी** · [Türkçe](../tr/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

> **लिनक्स के लिए एक ओपन-सोर्स सैमसंग फर्मवेयर फ्लैशिंग एवं रिपेयर वर्कबेंच — गैलेक्सी फोन (डाउनलोड/ओडिन मोड), MediaTek (BROM/DA), Qualcomm (EDL) और Spreadtrum/UNISOC डिवाइस फ्लैश करने के लिए ओडिन / हाइमडॉल का विकल्प।**

**Search keywords:** Samsung flashing tool · Odin alternative · Android firmware flashing Linux · Heimdall GUI · Galaxy phone repair · MTK BROM flash · Qualcomm EDL · FRP unlock · UNISOC flashing · device firmware tool · mobile repair · Android bootloader · USB flashing · Linux flashing suite · proprietary tool alternative

[![Rust](https://img.shields.io/badge/Rust-1.70+-orange?logo=rust&logoColor=white)](https://www.rust-lang.org)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52)](https://www.riverbankcomputing.com/software/pyqt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](../../LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![CI](https://github.com/Legendary-Brilliantforous/flashpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Legendary-Brilliantforous/flashpilot/actions)
[![Good First Issues](https://img.shields.io/github/issues/Legendary-Brilliantforous/flashpilot/good%20first%20issue)](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
[![Contributors](https://img.shields.io/github/contributors/Legendary-Brilliantforous/flashpilot)](https://github.com/Legendary-Brilliantforous/flashpilot/graphs/contributors)

**यह क्या है?** भुगतान वाली Windows फ्लैशिंग सूट्स का लिनक्स-नेटिव विकल्प — एक एकीकृत टूल जो **Samsung, MediaTek, Qualcomm और Spreadtrum/UNISOC डिवाइस** के बूटलोडर से सीधे बात करता है। Reverse-engineered protocols + native Rust performance + एक खूबसूरत PyQt6 GUI = Odin, Heimdall और महंगे commercial tools का ओपन-सोर्स विकल्प।

---

## ✨ यह प्रोजेक्ट क्यों मायने रखता है

Android रिपेयर की दुनिया बंद, केवल Windows पर उपलब्ध commercial tools पर चलती है। उनके protocols एक छोटे tinkering समुदाय द्वारा reverse-engineer किए जाते हैं — और उस ज्ञान का अधिकांश हिस्सा भुगतान सूट्स के अंदर या फोरम्स में अधूरे रूप में बिखरा हुआ है।

**यह प्रोजेक्ट हमारा जवाब है।** यह उन reverse-engineered protocols को एक साफ, ऑडिट करने योग्य, MIT-लाइसेंस्ड codebase में बदलता है जिसे कोई भी पढ़, चला, विस्तार, और अपनी flashing suite के रूप में ship कर सकता है।

| Commercial tool | केवल Windows, closed source | यह प्रोजेक्ट |
|---|---|---|
| Odin / Smart Switch | Windows, केवल GUI | ओपन-सोर्स Odin protocol (Rust, native) + PIT टूल्स |
| MTK flash tools | Windows, बंद DA | MTK BROM/DA फ्लैशिंग & बैकअप (scatter + GPT) |
| Qualcomm EDL tools | Windows | Sahara + Firehose protocol का implementation |
| SPD/UNISOC tools | Windows | Clean-room BSL डाउनलोड implementation |
| FRP / lock tools | भुगतान, grey-market | Transparent ADB + download-mode flows, MDM unlock |

---

## 🚀 हाइलाइट्स — 1.2.1 Stable (0 warnings)

- **9 transport modes** — ADB, MTP, Samsung Download mode, Samsung BROM, MTK, MTK BROM, Fastboot, Qualcomm EDL, SPD.
- **13 job categories** — Flash Firmware, Remove FRP, Remove Screen Lock, Remove MDM, Unlock Carrier, Read Device Info, Detect Devices, Reboot, Repair Settings, और per-chip EXPERIMENTAL: Knox / Warranty (Samsung), QCN / Modem (Qualcomm), IMEI Repair / Change (MTK/SPD/Qualcomm), eMMC / UFS.
- **Multi-device** — कई फोन plug करें: connection bar हर एक को list करता है, हर operation पूछता है कि वह किस फोन पर लागू हो (या जब केवल एक match हो तो silently चलता है), और अलग-अलग फोन एक साथ operations चला सकते हैं (प्रति डिवाइस एक op, STOP सभी को broadcast होता है)।
- **Rust core (`flashpilot-bridge`, ~9.3k LOC) — 0 `cargo check` warnings** — raw USB *vendored libusb* (कोई system deps नहीं), असली protocol implementations (+ 18 wired dead-paths, `-80KB` ltcg trim).
  - **Samsung**: reverse-engineered Odin session protocol (Heimdall-based), HID download-mode payloads, PIT read/write/flash — AT `Context` retained, `EndpointConfig` chunking.
  - **MediaTek**: BROM / preloader / DA handshake, scatter & GPT, BROM exploits, SLA keys — `ProgressReporter` real %.
  - **Qualcomm**: Sahara `ProtocolError` + Firehose `QcomDeviceInfo` wired via `Duration` timeouts.
  - **SPD/UNISOC**: clean-room BSL — all `BSL_CMD/REP`, `iface`, `flush/read_flash/chip_uid/power_off` wired.
  - Plus **MTP**, **AT-command**, और full **ADB** plumbing.
- **एक studio-grade GUI** — frameless translucent window, 10 accent themes, animated cable/status scene, live console.
  - **Brand Icons & Distinct Button Backgrounds** — crisp brand icons (Samsung Ⓢ, Apple red apple 🍎, Motorola Ⓜ, LG Ⓛ, आदि) और हर OEM button पर अनुकूलित brand background colors टॉप chip bar में।
  - **Motorola & Apple के लिए Horizontal Views** — model action boards default clean horizontal tabbed layouts।
  - **Micro-Interactions & Glassmorphism** — smooth 160ms page-switch fade-in animations, monospaced metadata badge typography (`Consolas`, `Monaco`), और enhanced glassmorphic card borders।
  - **बड़े centered dialogs (620px, draggable, ✕)** — beta gate + stable `UPDATE/AHEAD/PATCH` + flash/FRP confirms, chip colors `MTK amber` `QCOM red` `SPD violet` `SAMSUNG blue`, high-contrast text.
  - **Per-chip EXPERIMENTAL collapsibles** — Knox (Samsung), QCN/IMEI (Qualcomm), IMEI (MTK/SPD): amber banner, हर बार ownership checkbox, IMEI change के लिए `I UNDERSTAND` type-to-confirm, audit-logged.
  - **⏹ STOP** titlebar में सभी चल रहे operations रोकता है; per-device locks दूसरे फोन को काम जारी रखने देते हैं।

---

## 📸 Screenshots

| Samsung ops | MediaTek workbench | Battery repair | SPD download |
|---|---|---|---|
| ![Samsung](../../docs/samsung.png) | ![MediaTek](../../docs/mtk.png) | ![Battery](../../docs/battery.png) | ![SPD](../../docs/spd.png) |

---

## 🧩 Feature matrix

| Capability | Samsung | MediaTek | Qualcomm | SPD/UNISOC | Any ADB |
|---|---|---|---|---|---|
| Detect / info | ✅ | ✅ (+ crash preloader→BROM) | ✅ (Sahara) | ✅ | ✅ |
| Flash firmware | ✅ (Odin, native Rust) | ✅ (scatter + GPT) | ✅ (Firehose) | ✅ (FDL/regions) | — |
| Backup partitions | ✅ (EFS) | ✅ | ✅ | ✅ | — |
| FRP bypass | ✅ (ADB + download) | ✅ | ✅ (EDL) | ✅ | ✅ |
| Screen-lock removal | ✅ | ✅ | ✅ (EDL) | — | ✅ |
| MDM unlock | ✅ (ADB, QR, recovery) | — | — | — | — |
| Knox warranty/bypass (EXPERIMENTAL) | ✅ | — | — | — | — |
| QCN backup/restore + IMEI repair/change (EXPERIMENTAL) | — | ✅ (NVRAM) | ✅ (NV 550/682) | ✅ (BSL NV) | — |
| Partition tools | ✅ (PIT) | ✅ (GPT) | ✅ | ✅ (PAC extract/pack) | — |
| Low-level exploits | ✅ (HID/BROM) | ✅ (BROM exploit, SLA) | ✅ (Sahara) | ✅ (BSL) | — |
| Battery / network repair | — | — | — | — | ✅ |

> 💡 **Battery** और **Network** वाले sections *किसी भी* USB debugging वाले Android device पर काम करते हैं — कोई vendor hardware नहीं चाहिए।

---

## 🖥️ The GUI

एक frameless, translucent, radius-card window जिसमें live **connection banner** (computer → cable → phone scene with an animated data pulse) left **nav rail** और right **console/log pane** के ऊपर है।

- **Connection bar** — live device list (एक row प्रति फोन: model · serial · transports); inspect करने के लिए row click करें। जब कई match हों तो operation buttons फोन पूछते हैं।
- **Samsung** — Samsung hub sub-tabs: `ODIN FLASH · UNLOCK · ADVANCED FLASH · INFO & TOOLS`, plus firmware slots (AP/BL/CP/CSC/USERDATA), Odin utilities, और `KNOX — EXPERIMENTAL` collapsible।
- **MediaTek / Qualcomm / SPD** — dedicated workbenches जिनमें native low-level tools (scatter/DA + crash-to-BROM, programmer/XML + QCN/IMEI, FDL binaries + base addresses + IMEI) और अपना `— EXPERIMENTAL` collapsible है।
- **Battery** — fuel-gauge health %, temp/voltage/current, top consumers; one-click repair.
- **Network** — SIM state, data/Wi-Fi flags, DNS mode; radio reset & re-registration.
- **Settings** — auto-scan interval, default paths, console auto-clear, 10 accent themes, animations (shake/rubber/cable/bubble toggles), window glow, engine status, और in-app `cargo build`.

**Shortcuts:** `F5` rescan · `Ctrl+Enter` run · `Ctrl+L` clear console · `Ctrl+S` save log · `Ctrl+F` find.

---

## 📦 Quick start

**Requirements:** Rust toolchain, Python 3.10+, Linux desktop. बस इतना — libusb vendored है।

```bash
# 1. Build the Rust bridge (first build compiles libusb from source)
cargo build --release

# 2. (Recommended) install the USB udev rules so phones need no sudo
sudo bash root/setup-usb.sh

# 3. Python environment
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Launch
.venv/bin/python -m python.main        # or: python3 main.py
```

Samsung download-mode flashing native है (Rust Odin protocol) — कोई proprietary odin4 binary fetch, ship, या required नहीं है। Samsung combo firmware Samsung की official support pages या trusted firmware archives से source किया जाना चाहिए।

---

## 🖥️ Platform support — we want your words

**लिनक्स ही समर्थित प्लेटफ़ॉर्म है।** FlashPilot जानबूझकर *Windows-केवल फ्लैशिंग सूट्स का लिनक्स-नेटिव उत्तर* है — विकास, परीक्षण और रिलीज़ लिनक्स को लक्षित करते हैं, और यह बदलने वाला नहीं है।

**Windows / macOS आज समर्थित नहीं हैं**, व्यावहारिक कारणों से:

- Windows USB, प्रति फोन मोड एक driver दुःस्वप्न है (Zadig/WinUSB, QDLoader, Samsung drivers एक-दूसरे से टकराते हैं); अधिकांश "phone not detected" रिपोर्ट दूरस्थ रूप से debuggable नहीं होंगी।
- macOS signing/notarization overhead लगभग शून्य repair-shop demand के लिए जोड़ता है।
- Stack *portable* है (Rust + rusb, Python, Qt), तो यह एक maintenance निर्णय है, तकनीकी असंभवता नहीं।

**लेकिन यह एक खुला प्रश्न है, verdict नहीं.** अगर आप Windows/macOS समर्थन चाहते हैं — या Linux-only forever argue karna चाहते हैं — हमें बताएं:

- 💬 एक **[Discussion](https://github.com/Legendary-Brilliantforous/flashpilot/discussions)** खोलें अपने use case के साथ (repair shop? lab? कौन-सा OS? कौन-से phones?).
- 🔧 Code सबसे ज़ोर से बोलता है: योजना एक `python/core/platform.py` abstraction है (`open_file_manager()`, `detach_kernel_drivers()`, `usb_device_path()`, `needs_udev_setup()`) लिनक्स को एकमात्र backend बनाकर, ताकि ports additive PRs बनें, forks नहीं। उस दिशा में PRs अभी स्वागत योग्य हैं।
- 🎨 संबंधित: contributors ने PyQt6 (GPLv3) के बजाय **PySide6** (LGPL, इस MIT project के साथ license-compatible) प्रस्तावित किया है। उसी Discussion में अपनी राय दें — migration mechanical है लेकिन इससे पहले GUI smoke-test coverage चाहिए।

Contributor voices के बिना कोई निर्णय नहीं लिया जाएगा। आइए और उनमें से एक बनिए।

### CLI / bridge

```bash
./target/release/flashpilot-bridge detect          # all USB + Samsung filter (JSON)
./target/release/flashpilot-bridge fastboot-devices  # USB devices with a fastboot interface (JSON)
./target/release/flashpilot-bridge fastboot-cmd 22b8:2e80@2:16 20000 getvar securestate  # one raw fastboot command
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
├── src/                      # Rust bridge (~13k LOC) — ALL flows live here
│   ├── main.rs               #   command-line entry (80+ commands) + flow-run dispatch
│   ├── flows.rs              #   THE registry: FLOWS / JOBS / MODES (flow! macro, ~280 rows)
│   ├── usb/                  #   USB enumeration / interfaces / filtering (mod.rs + filtering.rs)
│   ├── devices.rs            #   merged USB+ADB device rows
│   ├── sam_download.rs       #   Samsung Download/Odin protocol (odin-* commands)
│   ├── mtk.rs mtk_da.rs      #   MediaTek BROM/DA flashing
│   ├── mtk_exploit.rs        #   BROM exploits (bypass/kamakiri2/crash-to-BROM)
│   ├── mtk_sla.rs            #   MediaTek SLA key handling
│   ├── qualcomm/             #   Sahara + Firehose + GPT (EDL)
│   ├── spd.rs                #   Spreadtrum/UNISOC BSL protocol (+ PAC)
│   ├── pac.rs                #   SPD PAC extract/pack
│   ├── pit.rs                #   Samsung PIT parser
│   ├── mtp.rs at.rs adb.rs   #   MTP, AT command, ADB plumbing
│   ├── fastboot.rs           #   native fastboot transport
│   ├── moto_flash.rs         #   Motorola staged fastboot FRP
│   ├── apple.rs              #   Apple usbmuxd/lockdown
│   ├── hid.rs bulk.rs        #   HID + bulk helpers
│   ├── fwtar.rs sparse.rs    #   firmware tar + sparse handling
│   ├── imgtools.rs           #   boot/vbmeta surgery
│   ├── hostinfo.rs           #   host eMMC/UFS health
│   ├── sam_*.rs              #   Samsung helpers (errors/setup)
│   └── config.rs error.rs util.rs
├── main.py                   # app entry (venv-safe launcher → python.gui.qt_app)
├── python/
│   ├── core/
│   │   ├── core.py           #   thin shim: mirrors Rust FLOWS/JOBS/MODES via bridge.flow_list()
│   │   ├── frp.py            #   FRP-only re-export surface (name == responsibility)
│   │   ├── devices.py        #   multi-device identity: stable keys, list, resolve, transport mapping
│   │   ├── bridge.py         #   talks to the Rust binary (+ per-key cancel)
│   │   ├── flow.py           #   Flow/Step primitives + cancellation
│   │   ├── jobs.py           #   FlashJob lifecycle (isolated job layer)
│   │   ├── cancel.py         #   cooperative cancellation registry
│   │   ├── mtk.py            #   MTK PIDs/stages/chips (0003=BROM, 2000=preloader)
│   │   ├── mtp.py            #   Samsung MTP/AT (multi-sequence ADB enable)
│   │   ├── pit.py pitstore.py  # Samsung PIT parser + cache
│   │   ├── adb.py            #   ADB helpers
│   │   ├── device_info.py    #   live device identity
│   │   ├── actions.py        #   action helpers
│   │   ├── experimental.py   #   per-run ack gates + audit log
│   │   ├── fus.py            #   Samsung FUS helpers
│   │   └── (no flows/ dir)   #   flows live in src/flows.rs; Python only delegates
│   └── gui/
│       ├── qt_app.py         #   the PyQt6 studio (~12k LOC)
│       ├── devices.py        #   brand→model→action drill-down pages
│       ├── nav.py            #   nav rail + OEM chip bar
│       ├── theme.py          #   tokens (accent vs focus_ring/sel_border) + QSS
│       ├── animations.py     #   Motion (shake/rubber serialized, no stuck state)
│       ├── toast.py          #   toast notifications
│       └── supported_devices.json  #   brand/model/chip research table
├── operations/               # per-operation docs + research (frp/mdm/flashing/…)
├── docs/                     # screenshots (fresh) + logo
├── root/                     # udev rules + setup-usb.sh
├── scripts/                  # dump-connected.sh, validate_mtp_at.py
├── INDEX.md CHANGELOG.md     # engineering index + release changelog
└── tests/                    # pytest suite (flow, MTK, PIT, odin safety, devices…)
```

---

## 🧑‍💻 Contributing

**यह प्रोजेक्ट केवल आपके साथ ही बेहतर होता जाएगा.** हम maintainers, protocol hackers, GUI designers, doc writers, और testers चाहते हैं।

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — शुरू करने के लिए आवश्यक सब कुछ।
- **[`good first issue`](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) label से शुरू करें** — curated, beginner-friendly tasks.
- **[bug report](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml)** / **[feature request](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=enhancement&template=feature_request.yml)** templates इस्तेमाल करें।
- **Beginner-friendly tasks** — `src/flows.rs` की हर flow row एक opportunity है: एक `flow!(...)` line जोड़ें, command sequence tune करें, नया device combo wire करें। Python इसे `bridge.flow_list()` के जरिए auto-discover करता है।
- **Flashing का prior experience ज़रूरी नहीं.** Flow framework (`src/flows.rs`) बेहद simple है — एक new method एक line है:

```rust
flow!("my_method", "My method", "Read Device Info", "ADB"),
```

यह GUI में automatically appear होता है. यही है पूरा contribution loop: **flow row लिखो, feature ship करो.**
- **Multi-device rule** — कभी "वह" डिवाइस assume मत करो; `key=None` (ambient scope) accept करो और filter करो. देखो `python/core/devices.py` और `CONTRIBUTING.md`.
- **Naming rules** — jobs verb-first होते हैं (`Remove FRP`, not `FRP bypass`); flow keys short snake_case होते हैं (no `flow_` prefix in `FLOWS`); MTK PIDs `0003`=BROM / `2000`=preloader होते हैं (mtkclient convention — inhe swap mat karo).

**Ideas jinmein humein help chahiye:**
- Flow tables mein नए device models / firmware combos.
- MediaTek DA variants, नए scatter/GPT quirks.
- Qualcomm rawprogram & patch XML edge cases.
- Android version के हिसाब से additional FRP / lock-removal methods.
- Packaging (Flatpak, AppImage, AUR, `cargo` + `pip`), CI, unit tests.
- More ODIN protocols, eMMC/UFS tooling, iCloud-adjacent aur EDL utilities.
- Translations, themes, aur accessibility.

---

## 🛡️ Safety & legality

Yeh tool directly bootloaders se baat karta hai aur misuse hone par data wipe ya brick kar sakta hai.

- Use karo sirf **un devices pe jo aapke hain ya jo service ke liye authorized hain** (repair shops servicing customer phones with consent).
- Hamesha on-screen warnings padho aur flashing se pehle **partitions back up** karo.
- FRP/MDM bypass karna ek aise device pe jo aapka nahi hai aapke jurisdiction mein illegal ho sakta hai — aap responsible ho is software ke use ke liye.
- FlashPilot un protocol payloads ko bundle karta hai jo operations ko chahiye (MTK DA/BROM payloads, Qualcomm firehose programmers, Unisoc FDL1/FDL2, Samsung bootloaders), jaise commercial flashing suites karte hain. Firmware images for a specific phone user ya vendor se aati hain.

---

## 📄 License

MIT — dekho [LICENSE](../../LICENSE). Odin protocol constants Heimdall project (MIT) se derived hain, aur SPD BSL reference clean-room protocol write-ups (spd_cmd.h / Opus-Spreadtrum docs) se aata hai.

---

**Star ⭐ is repo ko, issue kholo, PR bhejo — aur milke build karo best open flashing suite on Linux.**