Language switcher: [English](../../CONTRIBUTING.md) · [Français](../fr/CONTRIBUTING.md) · [Español](../es/CONTRIBUTING.md) · **Deutsch** · [简体中文](../zh/CONTRIBUTING.md) · [Русский](../ru/CONTRIBUTING.md) · [Português](../pt/CONTRIBUTING.md) · [日本語](../ja/CONTRIBUTING.md) · [العربية](../ar/CONTRIBUTING.md) · [हिन्दी](../hi/CONTRIBUTING.md) · [Türkçe](../tr/CONTRIBUTING.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

# 🧑‍💻 Beitragen zu FlashPilot

Danke fürs Vorbeischauen! Dieses Projekt basiert auf reverse-engineerten Protokollen
und offenem Wissen — jeder Beitrag macht es leistungsfähiger, zuverlässiger und
bringt es den kostenpflichtigen Windows-Suiten näher. Du musst kein Flash-Experte
sein, um zu helfen.

## Inhaltsverzeichnis

- [Verhaltenskodex](#verhaltenskodex)
- [Wie das Projekt aufgebaut ist](#wie-das-projekt-aufgebaut-ist)
- [Beitragen ohne Code](#beitragen-ohne-code)
- [Erste Schritte](#erste-schritte)
- [Migration von einem älteren Checkout](#migration-von-einem-älteren-checkout-lies-das-zuerst-wenn-du-zurückkehrst)
- [Architektur-Tour (10 Minuten)](#architektur-tour-10-minuten)
- [Einen neuen Flow hinzufügen](#einen-neuen-flow-hinzufügen)
- [Ein neues USB-Protokoll / Rust-Kommando hinzufügen](#ein-neues-usb-protokoll--rust-kommando-hinzufügen)
- [GUI-Richtlinien](#gui-richtlinien)
- [Tests](#tests)
- [Pull-Request-Checkliste](#pull-request-checkliste)
- [Plattform-Support-Richtlinie](#plattform-support-richtlinie-lies-dies-vor-einem-port)
- [Roadmap & Ideen](#roadmap--ideen)
- [Beitragende](#beitragende)
- [Fragen?](#fragen)

---

## Verhaltenskodex

Siehe [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Sei respektvoll, gehe von guter
Absicht aus und halte Diskussionen fachlich und hilfreich. Dies ist ein
Hobbyprojekt, das ernst geworden ist: wir begrüßen Anfänger und Veteranen
gleichermaßen. Belästigung, Gatekeeping oder das Einchecken von
Geheimnissen/Zugangsdaten werden nicht toleriert. Protokoll-Payloads sind
willkommen, wenn ihre Herkunft und Lizenz dokumentiert sind.

---

## Wie das Projekt aufgebaut ist

Zwei Hälften arbeiten zusammen:

| Ebene | Ort | Sprache | Rolle |
|---|---|---|---|
| **Core / Protokoll-Engine** | `src/` | Rust | Rohes USB, alle Bootloader-Protokolle (`flashpilot-bridge` CLI) |
| **Flow-Registry** | `src/flows.rs` | Rust | `flow!`-Makrozeilen → `FLOWS` / `JOBS` / `MODES` (Source of Truth) |
| **Flow-Shim** | `python/core/core.py` | Python | Dünne `_RustFlow`-Wrapper + `JOBS`-Fallback; delegiert an `bridge flow-run` |
| **Geräteidentität** | `python/core/devices.py` | Python | Stabile Schlüssel, Geräte liste, Ziel-Neuauflösung, Thread-Scope |
| **FRP-Oberfläche** | `python/core/frp.py` | Python | FRP-only-Re-Export (Name == Verantwortung) |
| **GUI Studio** | `python/gui/` | Python / PyQt6 | Workbench (`qt_app.py`), Seiten (`devices.py`), Theme, Animationen |

Python spricht nie direkt mit USB. Es ruft `target/release/flashpilot-bridge`
(das Rust-Binary) per Subprocess auf, das JSON/Text zurückgibt. Die GUI lauscht
nur auf Signale aus Worker-Threads — greife nie aus einem Hintergrundthread auf
Widgets zu.

---

## Beitragen ohne Code

Kein Code? Kein Problem:

- **Tests auf echter Hardware** — melde, auf welchen Geräten/Firmwares ein Flow funktioniert.
- **Dokumentation** — verbessere README, diese Datei und Flow-Beschreibungen.
- **Firmware / DA / Combo-Archive** — Zeiger auf legitime, frei verfügbare Binaries.
- **Übersetzungen & Themes** — die GUI ist themable; neue Accent-Packs sind easy wins.
- **UI/UX** — Mockups, Accessibility-Pässe, Tastaturkürzel-Design.
- **Bugreports** — verwende die [Bug-Report-Vorlage](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml): Schritte, Logs, `flashpilot-bridge detect`-Ausgabe, Gerätemodell + Firmware-Version.
- **Code** — siehe unten.

> 💡 **Neu hier?** Schau nach dem **`good first issue`**-Label im Issue-Tracker —
> kuratierte, einsteigerfreundliche Aufgaben mit vollständigem Scope und sicher
> aufzunehmen.

---

## Erste Schritte

```bash
# 1. Rust-Bridge bauen
cargo build --release

# 2. (Empfohlen) USB-udev-Regeln
sudo bash root/setup-usb.sh

# 3. Venv anlegen + starten
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m python.main
```

Die App öffnet ein natives PyQt6-Fenster. Verwende die Seite
**Settings → Tools**, um zu prüfen, ob die Bridge gebaut ist und ADB erkannt wird.

---

## Migration von einem älteren Checkout (lies das zuerst, wenn du zurückkehrst)

Ein Wort zur Unruhe, klipp und klar: zwischen 1.2.0 und jetzt haben wir das
zentrale Modul umbenannt, eine God-Datei in fokussierte Module aufgeteilt,
jeden Job umbenannt und ein Dutzend Dateien hinzugefügt. Das bricht alte
Imports, alte Doku-Referenzen und außerhalb liegende Skripte, die gegen
`python.core.frp` geschrieben wurden. Tut uns leid — es war der einzige Weg,
die God-Datei zu töten, den MTK-PID-Mix-up zu fixen und Multi-Device-Support
ohne Hack-Schichten zu ermöglichen. Dieser Abschnitt ist die vollständige
Adaption-Anleitung; hier ist nichts schrittweise deprecated, alles änderte sich
auf einmal, arbeite also die Tabelle einmal durch und du bist aktuell.

### Umbenannte Pfade

| Vorher | Nachher | Was ändern |
|---|---|---|
| `python/core/frp.py` (God-File: Registry + alle Flows) | `python/core/core.py` | `from python.core import frp` → `from python.core import core`; `frp.FLOWS` → `core.FLOWS`, usw. |
| *(nichts — FRP lebte im God-File)* | `python/core/frp.py` (neu, nur FRP) | Wenn du nur FRP-Flows brauchst, importiere von hier statt aus `core`. |
| *(nichts)* | `python/core/devices.py` (neu) | Geräteidentität, `list_devices()`, `resolve_usb_target()`, `device_scope()`. |
| *(nichts)* | `python/core/imei.py` (neu) | MTK/SPD IMEI-Reparatur + Wechsel-Flows. |
| *(nichts)* | `python/core/experimental.py` (neu) | EXPERIMENTAL-Gates + Audit-Log. |
| *(nichts)* | `python/core/{knox,qcn,emmc,pac,apple,health,compat,device_info,fastboot,integrity,safety,spd_adb}.py` (neu) | Domain-Logik, vorher inline im God-File oder fehlend. |
| *(nichts)* | `tests/test_devices.py` (neu) | Multi-Device + Cancel-Scope-Tests. |
| *(nichts)* | `CHANGELOG.md` (neu) | Gruppierte Änderungen pro Release; prüfe es zuerst. |

### Die Rust-Verschiebung (aktuelle Architektur — die obige Tabelle ist Geschichte)

Nach dem obenstehenden Split sind die Engines nach Rust gewandert und die
Python-Seite dünner geworden. Aktuelle Wahrheit:

- **Flows leben in `src/flows.rs`** (Registry + `flow-run <key> [target]
  [--code/--partition/--file/--dpc ...]`). `flow-list` ist die Source of
  Truth — verifiziere dort einen Flow-Key, bevor du ihn in Doku zitierst.
- **`python/core/core.py` ist ein dünner Shim** (~450 Zeilen): `_RustFlow`
  delegiert an `bridge flow-run`, Registry kommt von der Bridge mit `JOBS`-Fallback.
  Die 16 Per-Domain-Engine-Module (`knox`, `qcn`, `emmc`, `imei`, `apple`, `ofp`,
  `pac`, `health`, `flashing`, `spd_adb`, `integrity`, `fastboot`, `usb_watch`,
  `compat`, `updater`, `safety`) wurden gelöscht — referenziere sie nicht in
  neuer Doku.
- **GUI bleibt Python** (`python/gui/qt_app.py` + `devices.py`); sie konsumiert
  die Rust-Registry via `bridge.flow_list()`.
- Alte Testdateien für entfernte Python-Flows wurden mit ihnen gelöscht;
  Coverage sind die Per-Bereich-Suites + cargos `flows::tests`.

### API-Änderungen, an die du dich anpassen musst

- **Resolvers nehmen `key=None`.** `find_samsung()`, `_download_mode_device()`,
  `_wait_for_adb()`, `_wait_mtk_brom_target()`, `_mtk_retry()`,
  `wait_clean_download_mode()`, `pit_contract()` akzeptieren alle einen optionalen
  stabilen Geräteschlüssel (standardmäßig ambient thread scope — alte Call-Sites
  funktionieren weiter, First-Match-Verhalten bleibt erhalten, wenn kein Key
  gesetzt ist).
- **Cancel ist per Gerät.** `request_cancel()` / `clear_cancel()` /
  `cancel_requested()` in `flow.py` und `bridge.py` akzeptieren `key=None`.
  Keyless `request_cancel()` broadcastet immer noch (globaler STOP); keyless
  Prüfungen konsultieren erst den ambient scope, dann den Broadcast-Bus.
- **Run-Guard ist per Gerät.** `_flow_start(label, destructive, key=None)` /
  `_flow_end(key=None)` / `_flow_busy_msg(key=None)` in `qt_app.py`; die alten
  Globals `_FLOW_LOCK` / `_FLOW_LABEL` sind weg (ersetzt durch Per-Key-Dicts +
  `_flows_running()`).
- **Runner nehmen `device_key=None`.** `_run_ops_flow()` / `_run_job_flow()`
  zeigen den Geräte-Picker bei mehreren passenden Telefonen, setzen dann
  `ctx["device_key"]` (+ `ctx["target"]` wo auflösbar) und laufen innerhalb
  von `devices.device_scope()`.
- **Neuer Transportmodus `"SPD"`** in `MODES` (VID `0x1782`); neue Jobs
  `Knox / Warranty`, `QCN / Modem`, `IMEI Repair / Change`, `eMMC / UFS`.
- **Job-Namen sind verb-first** (`Remove FRP`, nicht `FRP bypass`; siehe README).
  Falls dein Branch noch alte Namen referenziert, benenne nach der Tabelle in
  „Architektur-Tour“ um.
- **MTK-PIDs folgen der mtkclient-Konvention**: `0e8d:0003` = BROM,
  `0e8d:2000` = Preloader. Mehrere alte Kommentare/Logs hatten sie vertauscht;
  vertraue `mtk.pid_stage()` / Rust `boot_stage_for()`, nicht alten Strings.

### Wenn du einen offenen PR von vor der Restrukturierung hast

1. Rebase auf den neuen Baum; erwarte Konflikte, die auf Imports und die
   `JOBS`/`FLOWS`-Blöcke beschränkt sind.
2. Führe die Checkliste unten aus — `pytest` fängt sofort veraltete Key-/Namens-
   Referenzen (Registry-Tests asserten, dass jede `JOBS`-Methode auflöst).
3. Wenn dein PR `flows/` betraf (das entfernte Split-Package-Experiment): das
   Verzeichnis ist weg, portiere deine Änderung auf `core.py` + das Domain-Modul.

---

## Architektur-Tour (10 Minuten)

1. **`src/main.rs`** — eine CLI mit 80+ Befehlen. Jeder `match`-Arm ist ein
   Befehl (`detect`, `mtk-flash`, `mtk-crash-brom`, `qcom-firehose`,
   `spd-format`, `odin-pit`, ...).
2. **`src/usb.rs`** — findet Geräte per VID/PID, gibt dir Endpoints (plus stabile
   `port_numbers` für re-enumerationssichere Adressierung).
3. **`src/odin.rs`** — Samsung Download-Modus (das reverse-engineerte Odin-3-
   Protokoll, Heimdall-abgeleitet). Liest/schreibt PIT, flasht Partitionen
   (inkl. persistenten `odin-agent` Sitzungs-Multiplexer).
4. **`src/mtk*.rs`** — MediaTek BROM (`0e8d:0003`) → Preloader (`0e8d:2000`) →
   Download-Agent-Handshake, Scatter-Parsing, GPT-Partition-Work, SLA-Schlüssel,
   BROM-Exploits, Crash-to-BROM. ⚠️ PID-Konvention im mtkclient-Stil:
   `0003`=BROM, `2000`=Preloader — nicht vertauschen.
5. **`src/qualcomm/`** — Sahara- (EDL-)Handshake und Firehose-Sessions.
6. **`src/spd.rs`** — Spreadtrum/UNISOC BSL: FDL-Download, Format, FRP, Backup,
   PAC-Extract/Pack.
7. **`src/flows.rs`** — das **Herz der App**. `flow!(key, label, job, mode)`-Zeilen
   bauen die Registry `FLOWS` / `JOBS` / `MODES` (~280 Zeilen, 13 Jobs, 9 Modi
   inkl. `SPD`). `python/core/core.py` spiegelt sie nur für GUI-Lookup.
8. **`python/core/devices.py`** — Multi-Device-Identität. Stabile Schlüssel
   (`adb:<serial>` → `usb:<port-path>` → volatile Fallback), `list_devices()`,
   `resolve_usb_target()` und `device_scope()`-Threadlocal, der das gewählte
   Telefon in Resolver trägt.
9. **`python/gui/qt_app.py`** — baut alle Sektionen (Samsung / MTK / QC / SPD /
   Battery / Network / Settings) und Sub-Tab-Workbenches, plus den Per-Operation-
   Geräte-Picker und den Per-Device-Run-Guard.

### Datenfluss

```
Button geklickt
  → _choose_device(job, mode)          # still, wenn 0–1 Telefone passen, sonst Picker
  → _run_ops_flow(job, mode, method, name, device_key)
  → per-Gerät _flow_start(key) + device_scope(key) + ctx["device_key"]
  → core.flow_for(...) -> Flow (Liste von Steps)
  → jeder Step läuft in einem Worker-Thread, ruft bridge._run([...]) auf
  → bridge spawnt target/release/flashpilot-bridge ...
  → Rust macht USB-I/O, gibt JSON/Text aus
  → Python parst + sendet _ui.line()-Signale (markiert mit [device-key])
  → GUI aktualisiert Konsole / Status / Progress sicher
```

---

## Einen neuen Flow hinzufügen

Die einfachste Funktion, die du shippen kannst. Öffne `src/flows.rs` und füge
eine Zeile hinzu:

```rust
flow!("my_method", "My method", "Remove FRP", "ADB"),
```

Der Key ist kurzes snake_case (ohne `flow_`-Präfix). Python entdeckt ihn
automatisch via `bridge.flow_list()` und der Job/Mode/Method-Drill-down der GUI
übernimmt ihn automatisch; die Ausführung läuft über
`flashpilot-bridge flow-run my_method`.

Dann (nur wenn neue Low-Level-Protokollarbeit nötig ist) füge den Bridge-Befehl
in `src/<concern>.rs` + `src/main.rs` hinzu. Job/Mode-Wiring ist bereits in der
Flow-Zeile.

Das war's — der Flow erscheint automatisch im Dropdown/Sub-Tab der GUI und ist
auch über die CLI erreichbar. **Das ist der Bereich mit dem höchsten
Wert/Aufwand-Verhältnis und dem leichtesten Einstieg.**

> Verwende `log(...)` in Steps für Konsolenausgabe, `ctx` für Zustand, den du
> zwischen Steps tragen willst, und `bridge._run(...)` für alles, das das Rust-
> Binary trifft. Halte Steps kooperativ mit `cancel_requested()` wo angebracht,
> damit Stop funktioniert (Cancel ist per-Gerät gescopt — siehe unten).

### Regeln, denen jeder Flow folgen muss

- **Nie "das" Gerät schnappen.** Akzeptiere `key=None` (ambient thread scope) in
  jedem Resolver, den du hinzufügst, und filtere danach — siehe
  `devices.device_key()`, `devices.match_key()`, `devices.device_scope()`. Die GUI
  setzt den Scope pro Operation; headless Caller können es auch.
- **Job-Namen sind verb-first** (`Remove FRP`, `Flash Firmware`,
  `Unlock Carrier`). **Flow-Keys sind kurzes snake_case** (`adb_frp`, nicht
  `flow_adb_frp`); das einzige historische Alias (`fastboot_read`) wurde
  entfernt — füge keine Aliase hinzu.
- **MTK-PID-Konvention ist mtkclient-Stil**: `0e8d:0003` = BROM (gehalten),
  `0e8d:2000` = Preloader. Rust, Python, GUI-Labels und Doku müssen
  übereinstimmen.
- **EXPERIMENTAL-Schreibvorgänge** (Knox/IMEI/QCN/eMMC) laufen über
  `experimental.check_gate_strict()` mit Ack pro Lauf — ein gespeichertes Ack
  darf nie automatisch passieren. Gate sie in der GUI via `_EXPERIMENTAL_FLOW_MAP`
  + dem amber collapsible Pattern auf der besitzenden Chip-Seite (nie auf einer
  globalen LAB-Seite).
- **Bridge-Targets sind volatil** (`vid:pid@bus:addr` ändert sich bei
  Re-Enumeration). Löst vom stabilen Schlüssel neu auf, bevor Sessions geöffnet
  werden (`devices.resolve_usb_target()`); fixiere odin4 mit
  `-d /dev/bus/usb/BBB/AAA`.

---

## Ein neues USB-Protokoll / Rust-Kommando hinzufügen

1. Füge dein Modul unter `src/` hinzu (z. B. `src/myproto.rs`).
2. Füge `mod myproto;` in `src/main.rs` und einen neuen `match`-Arm +
   Usage-Zeile hinzu.
3. Gib `Result<T>` via `crate::error` zurück und verwende `serde_json` für
   strukturierte Ausgabe.
4. Exponiere es aus Python in `python/core/bridge.py` als Wrapper um
   `_run([...])`.
5. Baue einen `Flow` in `core.py`, der es aufruft (beachte die Flow-Regeln oben).
6. Füge einen Test hinzu, wenn möglich — Unit-Tests liegen in `src/*.rs`
   (`#[test]`) und `tests/`.

**Protokoll-Hygiene:** zitiere deine Quelle (Foren, Clean-Room-Write-ups, andere
OSS-Projekte) im Modul-Docstring. Wir liefern keine proprietären Blobs — nur
die Protokollimplementierung.

---

## GUI-Richtlinien

- **Nur PyQt6.** Keine anderen Qt-Bindings, keine zusätzlichen UI-Deps
  (siehe `requirements.txt`).
- An die bestehende visuelle Sprache anpassen: `_btn_ghost()`, `_btn_primary()`,
  `_card_qss()`, `SectionTitle`, `C[...]`-Theme-Farben, `FlowLayout` für
  Button-Grids.
- **Theme-Tokens, nicht roher Accent:** Füllungen dürfen `C['accent'/'grad_a'/'grad_b']`
  nutzen, aber Focus-Rings, ausgewählte Tab-Borders und Checkboxes MÜSSEN die
  neutralen `C['focus_ring']` / `C['sel_border']` verwenden — sonst leaken rote
  Accent-Themes (Crimson, Sunset) Rot in Focus-States. Verwende keine
  hartkodierten Hex-Werte für Chrome.
- **Thread-Regel:** Hintergrundarbeit in `threading.Thread`; GUI-Updates nur über
  `self._ui.*`-Signale (`.line`, `.status`, `.toast`, `.ui`, `.progress`).
- **Animationen:** `Motion.shake()` / `Motion.rubber()` sind pro Widget
  gegenseitig ausschließend (geschützt durch `_anim_lock`) — laufe nicht beide
  gleichzeitig, oder Call-Sites müssen via `QTimer.singleShot` serialisieren.
  Keiner darf `setFixedSize`, restyled Borders oder disabled Layouts
  zurücklassen; `cleanup()` stellt alles wieder her.
- Halte langlebige UI-Zeilen scrollbar — die Chip-Seiten wrappen Content in ein
  `QScrollArea`, damit sie auf kleinen Fenstern nie gequetscht werden.
- Neue Sub-Tabs wiederverwenden `SamsungSubTabs` + ein `QStackedWidget`
  (siehe `_build_chip_ops_section`).
- Action-Buttons sind `NoFocus` (kein sticky focus ring); checkable tab pills
  behalten `checked`-Styling für den aktiven Zustand.

---

## Tests

```bash
cargo test                      # Rust-Unit-Tests (incl. MTK-Stage-Mapping, SLA, PIT)
.venv/bin/python -m pytest tests/   # Python-Suite (aktuell 173 bestanden, 4 übersprungen)
```

Test-Suite-Layout:

- `tests/test_frp_flow.py` — `Flow`/`Step`-Ausführung + kooperative Annullierung + Per-Device-Run-Guard.
- `tests/test_mtk.py` — MediaTek-Logik (scatter, DA, Boot-Stage-Helfer, BROM-wait/crash-retry).
- `tests/test_devices.py` — stabile Geräteschlüssel, Telefonfilterung, Ziel-Neuauflösung, gescopter Cancel.
- `tests/test_carrier_lock.py` — SIM-Lock-Verdikt + MTK-Patch-Gating + DA-Discovery.
- `tests/test_odin_safety.py` — tar.md5-Verifizierung, BL-Gates, odin4-Flag-Negotiation.
- `tests/test_pit.py` — Samsung-PIT-Parsing.
- `tests/test_bridge_io.py`, `tests/test_fus.py` — Bridge-I/O + Samsung-Firmware-Downloader.

Wenn du Rust-Logik hinzufügst, füge `#[test]`-Module in dieselbe Datei ein.
Wenn du Flows hinzufügst, füge ein pytest hinzu, das den Flow mit einem
Fake/Offline-Kontext ausführt, wo möglich. Neue Resolver müssen `key=None`
akzeptieren; neue Tests sollten Multi-Device-Filterung abdecken
(siehe `test_devices.py`) statt anzunehmen, es gebe nur ein Telefon.

---

## Pull-Request-Checkliste

- [ ] `cargo build --release` läuft.
- [ ] `cargo test` läuft (oder begründe, warum nicht ausführbar).
- [ ] `.venv/bin/python -m pytest tests/` läuft.
- [ ] Neuer Flow: in `JOBS` (Job + Modus) verdrahtet, damit er in der GUI erreichbar ist.
- [ ] Neuer Resolver: akzeptiert `key=None` (ambient scope) und ist durch einen Multi-Device-Test abgedeckt.
- [ ] Neues Rust-Kommando: in `main.rs`-Usage-Text + `bridge.py`-Wrapper hinzugefügt.
- [ ] GUI-Änderungen: themefarbene Farben (neutrale Focus-Tokens!), signalbasierte Updates, scroll-sichere Layouts.
- [ ] Keine Secrets/Binaries/geräteidentifizierenden Daten ins Repository.
- [ ] README-Feature-Matrix aktualisiert, wenn du eine Fähigkeit hinzugefügt hast.

Halte PRs fokussiert. Ein Feature oder Fix pro PR ist ideal; referenziere die Issue-Nummer.

---

## Plattform-Support-Richtlinie (lies das vor einem Port)

**Linux ist die einzige unterstützte Plattform.** Entwicklung, Hardware-Tests und
Releases zielen auf Linux. Windows/macOS-Issues werden als nicht unterstützt
geschlossen — es sei denn, sie kommen als Code, wie folgt.

**Warum:** `odin4` ist Linux-only; Windows-USB braucht Per-Modus-Treiber (Zadig /
QDLoader / Samsung), die nicht remote debuggt werden können; macOS braucht
Signing/Notarisierung für vernachlässigbare Nachfrage. Siehe den Abschnitt
„Platform support“ im README für das vollständige Argument und die offene
Einladung, dagegen zu argumentieren.

**Wie du trotzdem einen Port beisteuern kannst (die akzeptierte Form):**

1. Streue keine `sys.platform`-Checks durch Flows oder GUI.
2. Füge `python/core/platform.py` mit Backend-Funktionen hinzu —
   `open_file_manager()`, `detach_kernel_drivers(target)`,
   `usb_device_path(bus, addr)`, `needs_udev_setup()`,
   `kernel_module_loaded(name)` — Linux implementiert, andere werfen
   `NotImplementedError` mit hilfreicher Meldung.
3. Migriere bestehende Linux-only-Aufrufstellen (`xdg-open`, `rmmod cdc_acm`,
   `/dev/bus/usb`, `lsmod`, udev-Docs) darauf, ein PR pro Aufrufstellen-Gruppe.
4. Ein Windows/macOS-Backend-PR muss enthalten: die Backend-Implementierung,
   Doku-Updates und CI- oder vom Maintainer verifizierte manuelle Testbelege.
   Das Core-Team besitzt keine Non-Linux-Testhardware — Port-PRs stehen oder
   fallen mit der Fähigkeit ihres Autors, sie zu beweisen.

**PySide6 vs PyQt6:** Migration zu PySide6 (LGPL, MIT-kompatibel — PyQt6 ist
GPLv3) wird gewünscht, aber durch GUI-Smoke-Test-Coverage blockiert. Wenn du
das übernimmst: konvertiere `pyqtSignal→Signal`, `pyqtProperty→Property`,
`PyQt6.sip→shiboken6` mechanisch, erweitere die Offscreen-Window/Picker/Guard-
Smoke-Tests in `tests/` und halte das Verhalten pixel-identisch. Vorher in
Discussions besprechen.

---

## Roadmap & Ideen

Wir würden uns freuen, wenn Contributor eines dieser Punkte championen:

- **Ports & Packaging:** Flatpak / AppImage / AUR, CI-Matrix (Linux-Distros),
  `pip`/`cargo`-Release-Flow.
- **MediaTek:** mehr DA-Varianten, Scatter-Edge-Cases, eMMC/UFS-Backup-Dumps,
  neue `hw_code`-Einträge in `CHIP_NAMES` (mit zitierter Quelle — rate nie Hex-Codes).
- **Qualcomm:** rawprogram/patch-XML-Edge-Cases, fh-loader-Kombos, mehr Chip-PIDs.
- **Samsung:** zusätzliche HID Download-Mode-Payloads pro SoC,
  Odin-Multi-Partition-UX-Polish.
- **Multi-Device:** Per-Gerät-Konsolen-Tabs/Progress, Per-Gerät-STOP-Granularität
  (STOP broadcastet derzeit), `port_numbers`-Korrelation für exotische Hubs.
- **Neue Sektionen:** TEE/Keyboard-FRP, Carrier (De-Bloating)-Profile,
  EDL-nur-Werkzeuge.
- **Community:** Übersetzungen, ein Gerätekompatibilitäts-Wiki, reproduzierbarer
  Firmware-Archive-Katalog.
- **Sicherheit:** Dry-Run-Modus, automatisches Pre-Flash-Backup,
  Brick-Recovery-Doku.

---

## Beitragende

Jeder, der hilft — Code, Doku, Geräteberichte oder eine getestete Combo — wird
hier aufgeführt und gefeiert. Öffne einen PR, um dich hinzuzufügen
(alphabetisch nach Benutzername, eine Linkzeile):

```md
- [@your-github](https://github.com/your-github) — what you did
```

Die ersten Beitragenden zu diesem Projekt haben es real gemacht. Sei der Nächste.

---

**Fragen?** Öffne ein Discussion/Issue. Danke, dass du zu freier, offener
Software beiträgst.
