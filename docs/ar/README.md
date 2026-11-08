# 🔧 FlashPilot

Language switcher: [English](../README.md) · [Français](../fr/README.md) · [Español](../es/README.md) · [Deutsch](../de/README.md) · [简体中文](../zh/README.md) · [Русский](../ru/README.md) · [Português](../pt/README.md) · [日本語](../ja/README.md) · **العربية** · [हिन्दी](../hi/README.md) · [Türkçe](../tr/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

> **منصة عمل مفتوحة المصدر لتفليش وإصلاح firmware أجهزة Samsung على Linux — بديل لـ Odin / Heimdall لتفليش هواتف Galaxy (وضع Download/Odin)، وأجهزة MediaTek (BROM/DA)، و Qualcomm (EDL)، و Spreadtrum/UNISOC.**

**كلمات البحث:** Samsung flashing tool · Odin alternative · Android firmware flashing Linux · Heimdall GUI · Galaxy phone repair · MTK BROM flash · Qualcomm EDL · FRP unlock · UNISOC flashing · device firmware tool · mobile repair · Android bootloader · USB flashing · Linux flashing suite · proprietary tool alternative

[![Rust](https://img.shields.io/badge/Rust-1.70+-orange?logo=rust&logoColor=white)](https://www.rust-lang.org)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52)](https://www.riverbankcomputing.com/software/pyqt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![CI](https://github.com/Legendary-Brilliantforous/flashpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Legendary-Brilliantforous/flashpilot/actions)
[![Good First Issues](https://img.shields.io/github/issues/Legendary-Brilliantforous/flashpilot/good%20first%20issue)](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
[![Contributors](https://img.shields.io/github/contributors/Legendary-Brilliantforous/flashpilot)](https://github.com/Legendary-Brilliantforous/flashpilot/graphs/contributors)

**ما هذا؟** معادل أصلي لـ Linux لحزم التفليش المدفوعة على Windows — أداة واحدة موحّدة تتحدث مباشرة إلى bootloader الخاص بـ **Samsung، MediaTek، Qualcomm و Spreadtrum/UNISOC**. بروتوكولات هندسة عكسية + أداء Rust أصلي + واجهة PyQt6 أنيقة = البديل مفتوح المصدر لـ Odin و Heimdall والأدوات التجارية المكلفة.

---

## ✨ لماذا يهم هذا المشروع

عالم إصلاح Android يعمل على أدوات تجارية مغلقة وحصرياً على Windows. بروتوكولاتها هندسة عكسية من مجتمع صغير من الهواة — ومعظم تلك المعرفة مغلقة داخل حزم مدفوعة أو مشتّتة في المنتديات بشكل غير مكتمل.

**هذا المشروع هو إجابتنا.** يحوّل تلك البروتوكولات من هندسة عكسية إلى قاعدة كود نظيفة، قابلة للتدقيق، مرخّصة بـ MIT، يمكن لأي شخص قراءتها، تشغيلها، توسيعها — وشحنها كحزمة تفليش خاصة.

| الأداة التجارية | Windows فقط، كود مغلق | هذا المشروع |
|---|---|---|
| Odin / Smart Switch | Windows، واجهة GUI فقط | بروتوكول Odin مفتوح المصدر (Rust، أصلي) + أدوات PIT |
| أدوات تفليش MTK | Windows، DA مغلق | تفليش MTK BROM/DA والنسخ الاحتياطي (scatter + GPT) |
| أدوات Qualcomm EDL | Windows | تنفيذ بروتوكول Sahara + Firehose |
| أدوات SPD/UNISOC | Windows | تنفيذ BSL في clean-room |
| أدوات FRP / القفل | مدفوعة، سوق رمادية | تدفّقات ADB + download-mode شفافة، إلغاء MDM |

---

## 🚀 أبرز الميزات — 1.2.1 Stable (0 warnings)

- **9 أوضاع نقل** — ADB، MTP، وضع Download Samsung، Samsung BROM، MTK، MTK BROM، Fastboot، Qualcomm EDL، SPD.
- **13 فئة jobs** — Flash Firmware، Remove FRP، Remove Screen Lock، Remove MDM، Unlock Carrier، Read Device Info، Detect Devices، Reboot، Repair Settings، بالإضافة إلى EXPERIMENTAL حسب Chip: Knox / Warranty (Samsung)، QCN / Modem (Qualcomm)، IMEI Repair / Change (MTK/SPD/Qualcomm)، eMMC / UFS.
- **متعدد الأجهزة** — وصّل عدة هواتف: شريط الاتصال يسرد كل واحد، وكل عملية تسأل عن أي هاتف تنطبق عليه (أو تعمل بصمت عندما يطابق واحد فقط)، ويمكن لهواتف مختلفة تشغيل عمليات بالتوازي (عملية واحدة لكل جهاز، وSTOP يُبث للجميع).
- **Rust core (`flashpilot-bridge`, ~9.3k LOC) — 0 تحذيرات `cargo check`** — USB خام مع *libusb مُضمَّن* (لا اعتماديات نظام)، تنفيذات بروتوكول حقيقية (+ 18 dead-path موصّلة، trim ltcg -80KB).
  - **Samsung**: بروتوكول جلسة Odin من هندسة عكسية (مبني على Heimdall)، payloads HID في وضع download، قراءة/كتابة/تفليش PIT — سياق `AT` محفوظ، تقطيع `EndpointConfig`.
  - **MediaTek**: handshake BROM / preloader / DA، scatter & GPT، BROM exploits، مفاتيح SLA — `ProgressReporter` نسب % حقيقية.
  - **Qualcomm**: `ProtocolError` Sahara + `QcomDeviceInfo` Firehose موصّلان عبر مهلات `Duration`.
  - **SPD/UNISOC**: BSL في clean-room — جميع `BSL_CMD/REP`، `iface`، `flush/read_flash/chip_uid/power_off` موصّلة.
  - بالإضافة إلى **MTP**، **AT-command**، وجميع channels الخاص بـ **ADB**.
- **GUI بمستوى studio** — نافذة frameless translucent مع بطاقات rounded radius، 10 themes accent، مشهد كابل/حالة متحرك، console حي.
  - **أيقونات العلامات التجارية وخلفيات أزرار متميزة** — أيقونات crisp (Samsung Ⓢ، Apple red apple 🍎، Motorola Ⓜ، LG Ⓛ، etc.) وألوان brand على كل زر OEM في شريط chips.
  - **عروض أفقية لـ Motorola و Apple** — لوحات إجراءات بنمط tabs نظيفة.
  - **Micro-interactions & Glassmorphism** — تأثيرات fade-in سلسة 160 ms، tipografía monospaced لشارات metadata (`Consolas`, `Monaco`)، وحدود بطاقات glassmorphic محسّنة.
  - **حوارات كبيرة centered (620px، قابلة للسحب، ✕)** — beta gate + stable `UPDATE/AHEAD/PATCH` + تأكيدات flash/FRP، ألوان chips `MTK amber` `QCOM red` `SPD violet` `SAMSUNG blue`، نص high-contrast.
  - **EXPERIMENTAL collapsibles لكل chip** — Knox (Samsung)، QCN/IMEI (Qualcomm)، IMEI (MTK/SPD): banner amber، checkbox ملكية في كل تشغيل، `I UNDERSTAND` type-to-confirm لتغيير IMEI، audit-logged.
  - **⏹ STOP** في titlebar يوقف كل operations قيد التشغيل؛ locks per-device تتيح للجهاز unaffected continued operation.

---

## 📸 لقطات الشاشة

| عمليات Samsung | workbench MediaTek | إصلاح بطارية | تحميل SPD |
|---|---|---|---|
| ![Samsung](docs/samsung.png) | ![MediaTek](docs/mtk.png) | ![Battery](docs/battery.png) | ![SPD](docs/spd.png) |

---

## 🧩 مصفوفة الميزات

| الإمكانية | Samsung | MediaTek | Qualcomm | SPD/UNISOC | أي ADB |
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

> 💡 قسمي **Battery** و **Network** يعملان على *أي* جهاز Android مع تمكين USB debugging — لا حاجة لعتاد vendor.

---

## 🖥️ الواجهة GUI

نافذة frameless، translucent، بطاقات rounded radius مع **banner اتصال** live (مشهد computer → cable → phone مع pulsing بيانات متحرك) فوق **nav rail** على اليسار و **console/log pane** على اليمين.

- **Connection bar** — قائمة devices live (صف واحد لكل phone: model · serial · transports)؛ اضغط على صف لفحصه. أزرار operations تسأل عن أي phone عند تطابق several.
- **Samsung** — sub-tabs hub Samsung: `ODIN FLASH · UNLOCK · ADVANCED FLASH · INFO & TOOLS`، بالإضافة إلى firmware slots (AP/BL/CP/CSC/USERDATA)، Odin utilities، وcollapsible `KNOX — EXPERIMENTAL`.
- **MediaTek / Qualcomm / SPD** — workbenches مخصصة مع Native low-level tools (scatter/DA + crash-to-BROM، programmer/XML + QCN/IMEI، FDL binaries + base addresses + IMEI)، كل with its own collapsible `— EXPERIMENTAL`.
- **Battery** — سلامة fuel-gauge %، temp/voltage/current، consumers الأعلى؛ إصلاح one-click.
- **Network** — حالة SIM، flags data/Wi-Fi، وضع DNS؛ radio reset & re-registration.
- **Settings** — interval auto-scan، paths الافتراضية، auto-clear console، 10 themes accent، animations (toggles shake/rubber/cable/bubble)، glow نافذة، حالة engine، و `cargo build` integrated.

**اختصارات:** `F5` إعادة scan · `Ctrl+Enter` تشغيل · `Ctrl+L` مسح console · `Ctrl+S` حفظ log · `Ctrl+F` بحث.

---

## 📦 Quick start

**المتطلبات:** Rust toolchain، Python 3.10+، سطح مكتب Linux. هذا كل شيء — libusb مُضمَّن.

```bash
# 1. بناء Rust bridge (البناء الأول يترجم libusb من source)
cargo build --release

# 2. (موصى به) تثبيت USB udev rules لكي لا need sudo phones
sudo bash root/setup-usb.sh

# 3. بيئة Python
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Launch
.venv/bin/python -m python.main        # or: python3 main.py
```

Samsung download-mode flashing أصلي (Rust Odin protocol) — لا odin4 binary مملوك يُجلب، يُشحن، أو يُطلب. firmware combo Samsung يجب الحصول من صفحات دعم Samsung الرسمية أو أرشيف firmware موثوق.

---

## 🖥️ دعم المنصات — نريد آراءك

**Linux هي المنصة المدعومة.** FlashPilot هو *الإجابة الأصلية على Linux لحزم التفليش Windows-only* — development، testing و releases target Linux، ولن يتغيّر ذلك.

**Windows / macOS غير مدعومين اليوم**، للأسباب practice: USB drivers على Windows، signing/notarization على macOS، portable stack (Rust + rusb، Python، Qt). راجع النص الإنجليزي for full details.

**سؤال مفتوح:** إذا أردت دعم Windows/macOS — أو argue Linux-only — أخبرنا via **[Discussion](https://github.com/Legendary-Brilliantforous/flashpilot/discussions)**. الخطة: `python/core/platform.py` абстракция with Linux backend único، ports as additive PRs. Also discuss **PySide6** vs PyQt6.


### سطر الأوامر / الجسر

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

## 📁 هيكل المستودع

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


---


## 🧑‍💻 المساهمة

**هذا المشروع يتحسن только معك.** We look for maintainers، protocol hackers، GUI designers، writers، testers.

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — all you need to get started.
- **ابدأ بـ [`good first issue`](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)** — curated beginner-friendly tasks.
- Use **[bug report](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml)** / **[feature request](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=enhancement&template=feature_request.yml)** templates.
- كل صف flow في `src/flows.rs` فرصة: añade `flow!(...)`، ajusta secuencia، conecta combo. Python auto-discubre via `bridge.flow_list()`. Example:

```rust
flow!("my_method", "My method", "Read Device Info", "ADB"),
```

يظهر automatically في GUI. The whole loop: **escribe una fila de flujo، entrega una funcionalidad.**
- **Regla multi-dispositivo** — never grab "the" device؛ accept `key=None` (alcance ambiental) and filter. See `python/core/devices.py` and `CONTRIBUTING.md`.
- **Reglas de nombres** — jobs verb-first (`Remove FRP`، not `FRP bypass`); flow keys snake_case (no `flow_` prefix); MTK PIDs `0003`=BROM / `2000`=preloader (mtkclient convention).
- Ideas: device models/firmware combos، DA variants، scatter/GPT quirks، Qualcomm XML edge cases، FRP/lock methods per Android version، packaging (Flatpak/AppImage/AUR/cargo+pip)، CI، tests، Odin protocols، eMMC/UFS tools، translations، themes، accessibility.

---

## 🛡️ الأمان والقانون

هذه الأداة talks directly to bootloaders وقد damage/brick a device if misused.

- Use only on **devices you own or are authorized to service** (with customer consent).
- Read on-screen warnings and **back up partitions** before flashing.
- Bypassing FRP/MDM on a device you don't own may be **illegal in your jurisdiction** — you are responsible.
- FlashPilot bundles protocol payloads (MTK DA/BROM، Qualcomm firehose، Unisoc FDL1/FDL2، Samsung bootloaders)، like commercial suites. Firmware images for a specific phone still come from user/vendor.

---

## 📄 الترخيص

MIT — see [LICENSE](LICENSE). Odin protocol constants derived from Heimdall (MIT)؛ SPD BSL reference from clean-room protocol write-ups (spd_cmd.h / Opus-Spreadtrum docs).

---

**Star ⭐ this repo، open issue، send PR — and let's build the best open flashing suite on Linux together.**
