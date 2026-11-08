# 🔧 FlashPilot

Language switcher: [English](../../README.md) · [Français](../fr/README.md) · [Español](../es/README.md) · **Deutsch** · [简体中文](../zh/README.md) · [Русский](../ru/README.md) · [Português](../pt/README.md) · [日本語](../ja/README.md) · [العربية](../ar/README.md) · [हिन्दी](../hi/README.md) · [Türkçe](../tr/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

> **Ein Open-Source-Werkzeug für das Flashen und Reparieren von Samsung-Firmware unter Linux — eine Alternative zu Odin / Heimdall zum Flashen von Galaxy-Telefonen (Download-/Odin-Modus), MediaTek-Geräten (BROM/DA), Qualcomm (EDL) und Spreadtrum/UNISOC-Geräten.**

**Suchbegriffe:** Samsung flashing tool · Odin alternative · Android firmware flashing Linux · Heimdall GUI · Galaxy phone repair · MTK BROM flash · Qualcomm EDL · FRP unlock · UNISOC flashing · device firmware tool · mobile repair · Android bootloader · USB flashing · Linux flashing suite · proprietary tool alternative

[![Rust](https://img.shields.io/badge/Rust-1.70+-orange?logo=rust&logoColor=white)](https://www.rust-lang.org)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52)](https://www.riverbankcomputing.com/software/pyqt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](../../LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![CI](https://github.com/Legendary-Brilliantforous/flashpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Legendary-Brilliantforous/flashpilot/actions)
[![Good First Issues](https://img.shields.io/github/issues/Legendary-Brilliantforous/flashpilot/good%20first%20issue)](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
[![Contributors](https://img.shields.io/github/contributors/Legendary-Brilliantforous/flashpilot)](https://github.com/Legendary-Brilliantforous/flashpilot/graphs/contributors)

**Was ist das?** Das Linux-native Äquivalent der kostenpflichtigen Windows-Flash-Suiten — ein einheitliches Werkzeug, das direkt mit dem Bootloader von **Samsung-, MediaTek-, Qualcomm- und Spreadtrum/UNISOC-Geräten** spricht. Reverse-engineerte Protokolle + native Rust-Leistung + eine schöne PyQt6-GUI = die Open-Source-Alternative zu Odin, Heimdall und teuren kommerziellen Werkzeugen.

---

## ✨ Warum dieses Projekt wichtig ist

Die Android-Reparaturwelt basiert auf geschlossenen, nur unter Windows verfügbaren kommerziellen Werkzeugen. Ihre Protokolle werden von einer kleinen Gemeinschaft von Tüftlern reverse-engineered — und das meiste dieses Wissens steckt in bezahlten Suiten oder ist über Foren in unvollständiger Form verteilt.

**Dieses Projekt ist unsere Antwort.** Es verwandelt diese reverse-engineerten Protokolle in eine saubere, prüfbare, MIT-lizenzierte Codebasis, die jeder lesen, ausführen, erweitern — und als eigene Flash-Suite ausliefern kann.

| Kommerzielles Werkzeug | Nur Windows, geschlossener Quellcode | Dieses Projekt |
|---|---|---|
| Odin / Smart Switch | Windows, nur GUI | Offenes Odin-Protokoll (Rust, nativ) + PIT-Werkzeuge |
| MTK-Flash-Werkzeuge | Windows, geschlossene DA | MTK BROM/DA-Flashen & -Backup (Scatter + GPT) |
| Qualcomm-EDL-Werkzeuge | Windows | Sahara- + Firehose-Protokollimplementierung |
| SPD/UNISOC-Werkzeuge | Windows | Clean-Room-BSL-Download-Implementierung |
| FRP- / Sperrwerkzeuge | Bezahlt, Graumarkt | Transparente ADB- + Download-Modus-Flows, MDM-Unlock |

---

## 🚀 Highlights — 1.2.1 Stable (0 Warnungen)

- **9 Transportmodi** — ADB, MTP, Samsung Download-Modus, Samsung BROM, MTK, MTK BROM, Fastboot, Qualcomm EDL, SPD.
- **13 Job-Kategorien** — Flash Firmware, Remove FRP, Remove Screen Lock, Remove MDM, Unlock Carrier, Read Device Info, Detect Devices, Reboot, Repair Settings, plus pro Chip EXPERIMENTELL: Knox / Warranty (Samsung), QCN / Modem (Qualcomm), IMEI Repair / Change (MTK/SPD/Qualcomm), eMMC / UFS.
- **Mehrere Geräte** — schließe mehrere Telefone an: die Verbindungsleiste listet jedes auf, jede Operation fragt (oder läuft lautlos, wenn nur eines passt), für welches Telefon sie gilt, und verschiedene Telefone können Operationen parallel ausführen (eine Operation pro Gerät, STOP wird an alle gesendet).
- **Rust-Kern (`flashpilot-bridge`, ~9.3k LOC) — 0 `cargo check`-Warnungen** — rohes USB mit *vendored libusb* (keine System-Abhängigkeiten), echte Protokollimplementierungen (+ 18 verdrahtete Dead-Paths, `-80KB` ltcg-Trim).
  - **Samsung**: reverse-engineertes Odin-Sitzungsprotokoll (Heimdall-basiert), HID-Download-Modus-Payloads, PIT-Lesen/Schreiben/Flashen — AT-`Context` aufbewahrt, `EndpointConfig`-Chunking.
  - **MediaTek**: BROM- / Preloader- / DA-Handshake, Scatter & GPT, BROM-Exploits, SLA-Schlüssel — `ProgressReporter` echte %.
  - **Qualcomm**: Sahara `ProtocolError` + Firehose `QcomDeviceInfo` verdrahtet über `Duration`-Timeouts.
  - **SPD/UNISOC**: Clean-Room-BSL — alle `BSL_CMD/REP`, `iface`, `flush/read_flash/chip_uid/power_off` verdrahtet.
  - Plus **MTP**, **AT-Befehl** und volle **ADB**-Anbindung.
- **Ein Studio-GUI** — rahmenloses durchscheinendes Fenster, 10 Akzent-Themen, animierte Kabel-/Status-Szene, Live-Konsole.
  - **Brand Icons & Distinct Button Backgrounds** — scharfe Marken-Icons (Samsung Ⓢ, Apple roter Apfel 🍎, Motorola Ⓜ, LG Ⓛ, usw.) und passende Marken-Hintergrundfarben auf jedem OEM-Button in der oberen Chip-Leiste.
  - **Horizontale Ansichten für Motorola & Apple** — Modell-Aktionsboards standardmäßig in sauberen horizontalen Tab-Layouts.
  - **Mikro-Interaktionen & Glassmorphismus** — flüssige 160ms Fade-In-Animationen beim Seitenwechsel, monospaced Metadaten-Badge-Typografie (`Consolas`, `Monaco`) und verbesserte glasmorphe Kartenränder.
  - **Große zentrierte Dialoge (620px, ziehbar, ✕)** — Beta-Gate + stabiles `UPDATE/AHEAD/PATCH` + Flash-/FRP-Bestätigungen, Chip-Farben `MTK amber` `QCOM red` `SPD violet` `SAMSUNG blue`, kontrastreicher Text.
  - **Per-Chip-EXPERIMENTAL-Aufklappmenüs** — Knox (Samsung), QCN/IMEI (Qualcomm), IMEI (MTK/SPD): amber Banner, Besitzbestätigung bei jedem Lauf, `I UNDERSTAND` zum Eintippen für IMEI-Änderung, audit-protokolliert.
  - **⏹ STOP** in der Titelleiste stoppt alle laufenden Operationen; Sperren pro Gerät lassen andere Telefone weiterarbeiten.

---

## 📸 Screenshots

| Samsung ops | MediaTek workbench | Battery repair | SPD download |
|---|---|---|---|
| ![Samsung](../../docs/samsung.png) | ![MediaTek](../../docs/mtk.png) | ![Battery](../../docs/battery.png) | ![SPD](../../docs/spd.png) |

---

## 🧩 Funktionsmatrix

| Fähigkeit | Samsung | MediaTek | Qualcomm | SPD/UNISOC | Jedes ADB |
|---|---|---|---|---|---|
| Erkennen / Info | ✅ | ✅ (+ Crash Preloader→BROM) | ✅ (Sahara) | ✅ | ✅ |
| Firmware flashen | ✅ (Odin, nativ in Rust) | ✅ (Scatter + GPT) | ✅ (Firehose) | ✅ (FDL/Regions) | — |
| Partitionen sichern | ✅ (EFS) | ✅ | ✅ | ✅ | — |
| FRP-Bypass | ✅ (ADB + Download) | ✅ | ✅ (EDL) | ✅ | ✅ |
| Bildschirmsperre entfernen | ✅ | ✅ | ✅ (EDL) | — | ✅ |
| MDM-Entsperrung | ✅ (ADB, QR, Recovery) | — | — | — | — |
| Knox-Garantie/Bypass (EXPERIMENTELL) | ✅ | — | — | — | — |
| QCN-Sicherung/Wiederherstellung + IMEI-Reparatur/Änderung (EXPERIMENTELL) | — | ✅ (NVRAM) | ✅ (NV 550/682) | ✅ (BSL NV) | — |
| Partitionswerkzeuge | ✅ (PIT) | ✅ (GPT) | ✅ | ✅ (PAC entpacken/packen) | — |
| Low-Level-Exploits | ✅ (HID/BROM) | ✅ (BROM-Exploit, SLA) | ✅ (Sahara) | ✅ (BSL) | — |
| Batterie- / Netzwerk-Reparatur | — | — | — | — | ✅ |

> 💡 Die Bereiche **Batterie** und **Netzwerk** funktionieren auf *jedem* Android-Gerät mit USB-Debugging — keine Vendor-Hardware nötig.

---

## 🖥️ Die GUI

Ein rahmenloses, durchscheinendes Fenster mit Radiuskarten und einem Live-**Verbindungsbanner** (Computer → Kabel → Telefonszene mit animiertem Datenpuls) über dem linken **Navigations-Rail** und dem rechten **Konsole-/Log-Bereich**.

- **Verbindungsleiste** — Live-Geräteliste (eine Zeile pro Telefon: Modell · Seriennummer · Transporte); klicke eine Zeile zum Inspizieren. Bedienungsknöpfe fragen bei mehreren passenden nach dem Telefon.
- **Samsung** — Samsung-Hub-Untertabs: `ODIN FLASH · UNLOCK · ADVANCED FLASH · INFO & TOOLS`, plus Firmware-Slots (AP/BL/CP/CSC/USERDATA), Odin-Werkzeuge und ein aufklappbares `KNOX — EXPERIMENTAL`.
- **MediaTek / Qualcomm / SPD** — dedizierte Workbenches mit nativen Low-Level-Werkzeugen (Scatter/DA + Crash-zu-BROM, Programmer/XML + QCN/IMEI, FDL-Binärdateien + Basisadressen + IMEI), jeweils mit eigenem `— EXPERIMENTAL`-Aufklappmenü.
- **Batterie** — Fuel-Gauge-Zustand %, Temp/Spannung/Strom, Top-Verbraucher; Ein-Klick-Reparatur.
- **Netzwerk** — SIM-Zustand, Daten-/Wi-Fi-Flags, DNS-Modus; Funk-Reset & erneute Registrierung.
- **Einstellungen** — Auto-Scan-Intervall, Standardpfade, automatisches Konsolen-Leeren, 10 Akzent-Themen, Animationen (Shake/Rubber/Kabel/Blase-Schalter), Fenster-Glow, Engine-Status und `cargo build` in der App.

**Tastenkürzel:** `F5` erneutes Scannen · `Ctrl+Enter` ausführen · `Ctrl+L` Konsole leeren · `Ctrl+S` Log speichern · `Ctrl+F` suchen.

---

## 📦 Schnellstart

**Voraussetzungen:** Rust-Toolchain, Python 3.10+, Linux-Desktop. Das ist alles — libusb ist vendored.

```bash
# 1. Rust-Bridge bauen (erster Build kompiliert libusb aus Quellcode)
cargo build --release

# 2. (Empfohlen) USB-udev-Regeln installieren, damit Telefone kein sudo brauchen
sudo bash root/setup-usb.sh

# 3. Python-Umgebung
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Starten
.venv/bin/python -m python.main        # oder: python3 main.py
```

Das Samsung-Download-Modus-Flashen ist nativ (Rust-Odin-Protokoll) — es wird keine proprietäre odin4-Binärdatei geholt, mitgeliefert oder benötigt. Samsung-Combo-Firmware sollte von Samsungs offiziellen Supportseiten oder vertrauenswürdigen Firmware-Archiven bezogen werden.

---

## 🖥️ Plattformunterstützung — wir wollen Ihre Worte

**Linux ist die unterstützte Plattform.** FlashPilot ist bewusst *die Linux-native Antwort auf Windows-only-Flash-Suiten* — Entwicklung, Tests und Releases zielen auf Linux, und das ändert sich nicht.

**Windows / macOS werden heute nicht unterstützt**, aus praktischen Gründen:

- Windows-USB ist pro Telefonmodus ein Treiber-Albtraum (Zadig/WinUSB, QDLoader, Samsung-Treiber, die sich gegenseitig bekämpfen); die meisten „Telefon nicht erkannt“-Meldungen wären aus der Ferne nicht debuggbar.
- macOS bringt Signing-/Notarisierungs-Overhead bei fast null Nachfrage aus der Reparaturshop-Ecke.
- Der Stack *ist* portabel (Rust + rusb, Python, Qt), das ist also eine Wartungsentscheidung, keine technische Unmöglichkeit.

**Aber das ist eine offene Frage, kein Urteil.** Wenn Sie Windows/macOS-Unterstützung wollen — oder Linux-only für alle Zeiten verteidigen möchten — sagen Sie uns:

- 💬 Öffnen Sie eine **[Discussion](https://github.com/Legendary-Brilliantforous/flashpilot/discussions)** mit Ihrem Anwendungsfall (Reparaturshop? Labor? Welches OS? Welche Telefone?).
- 🔧 Code spricht am lautesten: der Plan ist eine `python/core/platform.py`-Abstraktion (`open_file_manager()`, `detach_kernel_drivers()`, `usb_device_path()`, `needs_udev_setup()`) mit Linux als einzigem Backend, sodass Ports additive PRs statt Forks werden. PRs in diese Richtung sind jetzt schon willkommen.
- 🎨 Verwandt: Mitwirkende haben **PySide6** (LGPL, lizenzkompatibel zu diesem MIT-Projekt) gegenüber PyQt6 (GPLv3) vorgeschlagen. Diskutieren Sie in derselben Discussion mit — die Migration ist mechanisch, braucht aber zuerst GUI-Smoke-Test-Abdeckung.

Keine Entscheidung wird ohne Mitwirkenden-Stimmen getroffen. Kommen Sie und werden Sie eine davon.

### CLI / Bridge

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

## 📁 Repository-Struktur

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

## 🧑‍💻 Mitwirken

**Dieses Projekt wird nur durch Sie besser.** Wir suchen Maintainer, Protokoll-Hacker, GUI-Designer, Dokumentationsautoren und Tester.

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — alles, was Sie zum Starten brauchen.
- **Starten Sie mit dem Label [`good first issue`](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)** — ausgewählte, anfängerfreundliche Aufgaben.
- Verwenden Sie die **[Bug-Report](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml)**- / **[Feature-Request](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=enhancement&template=feature_request.yml)**-Vorlagen.
- **Anfängerfreundliche Aufgaben** — jede Flow-Zeile in `src/flows.rs` ist eine Chance: füge eine `flow!(...)`-Zeile hinzu, stimme eine Befehlssequenz ab, verdrahte ein neues Geräte-Combo. Python entdeckt sie automatisch über `bridge.flow_list()`.
- **Keine Vorkenntnisse im Flashen nötig.** Das Flow-Framework (`src/flows.rs`) ist denkbar einfach — eine neue Methode ist eine Zeile:

```rust
flow!("my_method", "My method", "Read Device Info", "ADB"),
```

Sie erscheint automatisch in der GUI. Das ist der gesamte Beitragszyklus: **schreibe eine Flow-Zeile, liefere ein Feature aus.**
- **Multi-Gerät-Regel** — nehme niemals „das“ Gerät; akzeptiere `key=None` (ambient scope) und filtere danach. Siehe `python/core/devices.py` und `CONTRIBUTING.md`.
- **Namensregeln** — Jobs sind verbo-first (`Remove FRP`, nicht `FRP bypass`); Flow-Schlüssel sind kurzes snake_case (kein `flow_`-Präfix in `FLOWS`); MTK-PIDs sind `0003`=BROM / `2000`=Preloader (mtkclient-Konvention — tausche sie nicht).

**Ideen, bei denen wir gerne Hilfe hätten:**
- Neue Gerätemodelle / Firmware-Kombos in den Flow-Tabellen.
- MediaTek-DA-Varianten, Scatter/GPT-Sonderfälle.
- Qualcomm-rawprogram- & patch-XML-Grenzfälle.
- Zusätzliche FRP- / Sperr-Entfernungs-Methoden pro Android-Version.
- Paketierung (Flatpak, AppImage, AUR, `cargo` + `pip`), CI, Unit-Tests.
- Mehr ODIN-Protokolle, eMMC/UFS-Werkzeuge, iCloud-angrenzende und EDL-Werkzeuge.
- Übersetzungen, Themes und Barrierefreiheit.

---

## 🛡️ Sicherheit & Rechtliches

Dieses Werkzeug spricht direkt mit Bootloadern und kann Daten löschen oder ein Gerät bricken, wenn es missbraucht wird.

- Verwende es nur an **Geräten, die dir gehören oder die du reparieren darfst** (Reparaturshops, die Kunden-Telefone mit Einwilligung warten).
- Lies immer die Warnungen auf dem Bildschirm und **sichere Partitionen**, bevor du flashst.
- Das Bypassen von FRP/MDM an einem Gerät, das dir nicht gehört, kann in **deiner Jurisdiktion illegal** sein — du bist verantwortlich für die Nutzung dieser Software.
- FlashPilot bündelt die Protokoll-Payloads, die Operationen benötigen (MTK DA/BROM-Payloads, Qualcomm-Firehose-Programmer, Unisoc FDL1/FDL2, Samsung-Bootloader), so wie es kommerzielle Flash-Suiten tun. Firmware-Images für ein bestimmtes Telefon stammen weiterhin vom Nutzer oder vom Hersteller.

---

## 📄 Lizenz

MIT — siehe [LICENSE](../../LICENSE). Die Odin-Protokollkonstanten stammen aus dem Heimdall-Projekt (MIT), und die SPD-BSL-Referenz kommt aus Clean-Room-Protokolldokumentation (spd_cmd.h / Opus-Spreadtrum-Docs).

---

**Star ⭐ dieses Repo, öffne ein Issue, sende einen PR — und lass uns gemeinsam die beste offene Flash-Suite unter Linux bauen.**