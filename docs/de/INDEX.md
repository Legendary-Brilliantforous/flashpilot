# FlashPilot — Index

Language switcher: [English](../INDEX.md) · [Français](../fr/INDEX.md) · [Español](../es/INDEX.md) · **Deutsch** · [简体中文](../zh/INDEX.md) · [Русский](../ru/INDEX.md) · [Português](../pt/INDEX.md) · [日本語](../ja/INDEX.md) · [العربية](../ar/INDEX.md) · [हिन्दी](../hi/INDEX.md) · [Türkçe](../tr/INDEX.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

Das README macht das Marketing. Diese Datei ist der Engineering-Index — jeder Ordner, was er tut und wo man anfängt.

## Ausführen

```bash
# GUI
python main.py

# CLI (Bridge) — gleiches Protokoll, ohne GUI
./target/release/flashpilot-bridge detect-all
./target/release/flashpilot-bridge spd-detect
```

## Wurzelstruktur (17 Einträge)

| Eintrag | Was | Wann öffnen |
|---|---|---|
| `main.py` | App-Einstiegspunkt. Fügt das Repo zu `sys.path` hinzu und ruft `python.gui.qt_app.main()` auf. | Um zu ändern, wie die App startet. |
| `pyproject.toml` | Python-Paketmetadaten (name=flashpilot, deps, Build-Backend). | Um eine Python-Abhängigkeit hinzuzufügen oder die Version anzuheben. |
| `Cargo.toml` / `Cargo.lock` | Rust-Kern (das `flashpilot-bridge`-Binary). | Um die Bridge-CLI zu ändern oder ein Protokoll hinzuzufügen. |
| `python/` | Dünne Python-Schicht über der Rust-Engine: `python/core/` (Shim + GUI-Helfer) und `python/gui/` (PyQt6). Alle Flows leben in `src/flows.rs`. | GUI- und Geräte-Plumbing. |
| `src/` | Rust-Quellen. Spiegelt das Layout von `python/core/`. | Wenn du einen neuen Bridge-Befehl hinzufügst oder ein USB-Protokoll änderst. |
| `tests/` | pytest-Suite. ~149 Tests, ~1s Laufzeit. | Ausführen mit `.venv/bin/python -m pytest tests/ -q`. |
| `scripts/` | Eigenständige Shell-Werkzeuge. Heute: `dump-connected.sh`, `validate_mtp_at.py`. | Für eine nicht-GUI-Batch-Operation. |
| `docs/` | README-Assets (Screenshots, Logo). | Für das README. |
| `packaging/` | `.deb`-Build-Skript + Steuerdateien. | Um einen Release zu verschicken. |
| `root/` | udev-Regeln (damit Telefone ohne sudo funktionieren). | Einmalige Einrichtung. |
| `operations/` | **Per-Job-Dokumentationsbäume** — siehe Abschnitt „operations/“ unten. | Um einen bestimmten Job zu verstehen (FRP, MDM, Bildschirmsperre usw.). |
| `build/` | **Alle gitignored Build-/Laufzeit-Artefakte** — siehe Abschnitt „build/“ unten. | Du öffnest das fast nie. |
| `.github/` | CI-Workflows, Issue-Templates. | Um die CI zu ändern. |
| `LICENSE` `CODE_OF_CONDUCT.md` `CONTRIBUTING.md` `SECURITY.md` `DESCRIPTION.md` | Standard-Projektmetadaten. | Beim Releasen. |

## Struktur `python/`

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

**Flows leben in Rust.** `python/core/core.py` ist ein dünner Shim: `_RustFlow` delegiert die Ausführung an `bridge flow-run <key>`. Das kanonische Registry ist `src/flows.rs` (`flow!`-Makro, ~280 Zeilen); Python spiegelt es für die GUI-Suche.

## Struktur `src/` (Rust)

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

## `operations/` — Per-Job-Dokumentationsbäume

Diese Ordner enthalten **READMEs pro Operation**, die erklären, wie jeder Job funktioniert, welche Flow-Schlüssel er nutzt, welche Geräte er unterstützt und bekannte Fallstricke. Es ist kein Code — der Baum ist reines Markdown (eine frühere Bereinigung hat die veralteten `.py`-Shims entfernt, die hier einst lebten; nichts importiert `operations/`). Der Code lebt in `src/flows.rs` (das `flow!`-Registry; `python/core/core.py` ist ein dünner Shim) und den domänenspezifischen Modulen (`knox.py`, `qcn.py`, `imei.py`, `emmc.py`, …). Die READMEs in `operations/` sind für Endnutzer / kommerzielle-Werkzeug-Forscher geschrieben; der Code ist die Quelle der Wahrheit.

| Ordner | Was | Echter Code in |
|---|---|---|
| `operations/apple/` | iCloud, Aktivierungssperre, MDM, Entfernen von Code/Lost-Modus | Rust-Flows (`src/flows.rs`: `apple_*`-Zeilen, `flow-run`-CLI) |
| `operations/frp/` | FRP-Bypass pro Engine + Forschungsnotizen pro Gerät. **Beginne mit `operations/frp/INDEX.md`**. | Rust-Flows (Registry `src/flows.rs`, `flow-run`-CLI); dünner Shim `python/core/core.py` |
| `operations/mdm/` | MDM- / Device-Owner-Entsperrung + Notizen pro Marke | Rust-Flows (Registry `src/flows.rs`, `flow-run`-CLI) |
| `operations/screen_unlock/` | Bildschirmsperre entfernen (ADB / Recovery / Download / umfassend) | Rust-Flows (Registry `src/flows.rs`, `flow-run`-CLI) |
| `operations/battery/` | Batterie-Report / -Reparatur / -Lasttest (über ADB) | Rust-Flows (Registry `src/flows.rs`, `flow-run`-CLI) |
| `operations/network/` | SIM-Zustand, DNS, Funk-Reset | Rust-Flows (Registry `src/flows.rs`, `flow-run`-CLI) |
| `operations/carrier_unlock/` | Carrier-Lock (Apple, MTK) | Rust-Flows (Registry `src/flows.rs`, `flow-run`-CLI) |
| `operations/flashing/` | Flash-Anleitungen pro Vendor (Samsung Odin, MTK DA, Qualcomm EDL, UNISOC SPD, PIT) | Rust-Flows (Registry `src/flows.rs`, `flow-run`-CLI) |
| `operations/usb/` | USB-Enumerations- und Detektionsnotizen | `src/usb/`, `src/devices.rs`, `python/core/devices.py` |

## `build/` — gitignored Laufzeit-/Build-Artefakte

| Unterverzeichnis | Inhalt | Erstellt von |
|---|---|---|
| `build/target/` | Rust-`cargo build`-Ausgabe | `cargo build` |
| `build/dist/` | `.deb`-Pakete | `packaging/build-deb.sh` |
| `build/cache/` | Per-Gerät TAR-Caches und Reverse-Engineering-Dumps | GUI / `scripts/dump-connected.sh` |
| `build/mdm_qr/` | Erzeugte MDM-Provisioning-QR-Codes | GUI-MDM-Flow |
| `build/pit/` | Gecachte `.pit`-Partitionstabellendateien | GUI-PIT-Flow |

**Regel:** nie `git add` für irgendetwas aus `build/`. Wenn du den Zustand löschen willst, lösche das Unterverzeichnis — es wird neu erstellt.

## Wie man ein neues Feature hinzufügt (die „welche Datei fasse ich an?“-Spickzettel)

| Du willst... | Anfassen |
|---|---|
| Ein neues Gerät zur unterstützten Liste hinzufügen | `python/gui/supported_devices.json` |
| Eine neue per-Vendor-Aktion zu einem unterstützten Gerät hinzufügen | `src/flows.rs` (eine `flow!(...)`-Zeile hinzufügen); Python entdeckt sie automatisch über `bridge.flow_list()` |
| Einen neuen ADB-Flow für ein bestehendes Thema hinzufügen | wie oben (Rust `src/flows.rs`) |
| Einen neuen Bridge-CLI-Befehl hinzufügen | `src/<thema>.rs` + `src/main.rs` (Zweig `<cmd>` im match) |
| Eine neue Top-Level-Navigationsseite hinzufügen | `python/gui/qt_app.py` (`_build_*_page` + `_section_index`) |
| Eine neue Designfarbe / einen neuen Button-Stil hinzufügen | `python/gui/theme.py` (`C`-Dict / `_btn_*()`) |
| Die Per-Job-Notizen eines neuen Geräts dokumentieren | `operations/<job>/<marke>/<modell>.md` |
| Einen Test hinzufügen | `tests/test_<bereich>.py`, folge dem `test_mtk.py`-Muster |

## Wie der Operation Runner funktioniert (einmal lesen)

Die GUI ruft nie direkt einen Flow auf. Der per-Operation-Gerätepicker (`FlashPilotWindow._choose_device`) löst zuerst einen stabilen Geräteschlüssel auf; dann rufen `_run_ops_flow` / `_run_job_flow` `python.core.core.flow_for(job, mode, method)` auf, das ein `Flow()`-Objekt (eine Liste von `Step()`s) zurückgibt, und dann wird `flow.run(ctx, log)` in einem Worker-Thread innerhalb von `devices.device_scope(key)` aufgerufen (sodass jeder Resolver auf das gewählte Telefon zielt). Jeder Flow schreibt in ein `log(line)`-Callable, das die GUI an ihre Konsole hängt. Die Abbruchfunktion ist pro Gerät gescoped (`flow.request_cancel(key)`; Sendung ohne Schlüssel stoppt alles), geprüft am Anfang jedes `_run`.

Um einen Flow hinzuzufügen: füge eine `flow!("my_op", "My op", "Job Name", "MODE")`-Zeile zu `src/flows.rs` hinzu. Python entdeckt sie automatisch über `bridge.flow_list()` und das Job/Mode/Methode-Drill-down der GUI übernimmt sie. Die Rust-`flow-run`-CLI führt sie aus; Resolver müssen ein Ziels (Serial / `vid:pid@bus:addr`) akzeptieren (siehe `src/device.rs`).