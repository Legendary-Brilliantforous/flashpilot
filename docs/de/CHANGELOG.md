# Änderungsprotokoll

Language switcher: [English](../../CHANGELOG.md) · [Français](../fr/CHANGELOG.md) · [Español](../es/CHANGELOG.md) · **Deutsch**

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 1.2.2 (Auto-Updates, 10 Sprachen, Rockchip + modemsicheres Multi-Device)

*Konsolidiert die Entwicklungszyklus-Notizen 1.2.2 → 1.3.2 — alles, was seit 1.2.1 ausgeliefert wurde.*

### Auto-Updates & What's New (neu)
- Updates installieren sich automatisch: das heruntergeladene `.deb` installiert sich per sudo im Hintergrund, die App startet neu, und ein Einmal-Fenster "was hinzugekam oder geändert wurde" zeigt das Changelog der neuen Version beim ersten Start (die manuelle "Install Now"-Aufforderung bleibt, wenn Auto-Install in Einstellungen → Updates ausgeschaltet ist).

### 10-Sprachen-UI + Live-Sprachwechsel (neu)
- Die ganze UI kommt in 10 zusätzlichen Sprachen (Français, Español, Deutsch, 简体中文, Русский, Português, 日本語, العربية, हिन्दी, Türkçe): Einstellungen, Geräte-Kacheln, Seiten und Konsolen-Strings.
- Der UI-Sprachwechsel ist sofort — kein Neustart; Layouts klemmen an echten Font-Metriken, sodass lange Übersetzungen umbrechen statt Controls abzuschneiden.
- Key-basierte JSON-Übersetzungskataloge mit Coverage-Verifikation; die CI smoke-testet die installierten Kataloge.

### Rockchip + schlauere Erkennung (neu)
- Neue Rockchip-Marken-Seite: RK28xx–RK35xx-Familie über den Fastboot-Modus.
- Die Erkennung identifiziert Modell, Marke und Formfaktor — nicht nur den Chip.
- Jede Flash-Stage wird erwischt (TFT-Parität): MediaTek BROM/Preloader/DA über den vollen Stage-PID-Satz und OEM-VIDs (inkl. Preloader-VCOM 0x2000/0x2001), die erweiterte Qualcomm-EDL-Download-PID-Familie, die Vereinigung der SPD-Download-PIDs, und Qualcomm HS-USB-Diagnostics als eigener Modus benannt.
- Der Modus-Badge folgt dem AUSGEWÄHLTEN Gerät und nennt das tatsächliche USB-Protokoll (ADB/MTP/PTP/DIAG/storage/RNDIS) statt OTHER: nur Flash-PIDs beanspruchen das Low-Level-MediaTek-Label, Qualcomm-EDL behält seinen Badge-Chip, und die 'MEDIATEK'/'download'-Teilzeichenketten-Durchfälle sind behoben.

### Motorola-FRP (neu)
- CVE-2016-10277-Fastboot-FRP-Kette, Fake-Login-QR-Provisionierung mit eigenem DPC (TestDPC / Device Policy / Adobe), gestuftes Fastboot-FRP mit Flash- + Reboot-Zyklen, und ein ADB-Zyklus im Factory-Bootmode.

### Echte Engine-Pfade (neu)
- Echte MTK/QCOM/Unisoc/Samsung-Flash-, FRP- und Lock-Pfade im Rust-Kern.
- odin4 ist weg: die native Rust-Odin-Engine bewältigt die komplette tar-Pipeline, PIT und jede bekannte odin4-Problemklasse; Apple usbmuxd/lockdown zog nach Rust; der Kern ist Rust-only (alle Python-Geräte-/Protokoll-Fallbacks entfernt).

### Modemsicheres ADB (behoben)
- Poll-/Monitor-/Anzeige-Pfade sind zero-touch (`adb-devices --no-probe`): kein open/claim/handshake aus Schleifen — USB-Modems enumerieren sich nicht mehr jeden Zyklus neu (live verifiziert: 114 ruhige Poll-Zyklen auf einem MSM8916-Modem).
- Bei Claim-Kämpfen wird eine Leiter hinunter delegiert: nativ → Rust-Server-Transport (explizite Seriennummer) → Host-Binary → Rettungs-kill (letzter Ausweg), sodass ADB-Ops gelingen, während der System-Server die Schnittstelle hält.
- USB-ADB-Merge-Korrektur (Reihenzeichenketten werden geparst, sodass Reihen tatsächlich ADB-Zustand tragen), Busy-Halter-Rettung + transientes Retry + ehrlicher Busy-Zustand, Babble/Overflow-Guard, Claim-Test-Isolationsbefehl, moderne adb-CNXN-Werte, und die QCOM-/MTK-Ecken zeigen das ADB-Overlay wie Geschwister-Zweige.

### Multi-Device-Zuverlässigkeit (behoben)
- Pick mit Settle-Retry: jeder Tool-Runner wiederholt einmal nach 2,5 s, wenn ein Scan ein re-enumerierendes Gerät transient verfehlt, statt mit "no device" abzulehnen, während die GUI es verbunden anzeigt.
- ADB-AUTH hält SHA-256 über Token-Runden im Spiel (ungerade Runden SHA-256, gerade SHA-1), sodass eine verlorene Runde-1-Signatur nicht mehr in ein falsches "not authorized" mauert; `_wait_for_adb` toleriert transiente Scan-Fehler.
- Ziel-Identitätsbindung: ein ersetztes Gerät, das einen wiederverwendeten bus:addr besetzt, wird abgelehnt (Zero-Touch-Serienprüfung) — der Transport verfolgt nie ein anderes Telefon.
- Gerätelisten-Wechsel: der Neuaufbau der Verbindungsleiste wiederholt sich, wenn der zweite Scan ein Gerät verliert, der Gerätewechsel fällt nicht mehr auf das erste Telefon zurück, und ADB-Tools fallen auf die ADB-Daemon-Reihe zurück, wenn der USB-Pick verfehlt ("zeigt verbunden, aber Aktionen sagen kein adb").
- Geräte-Klassifizierung + Picker: nicht zugeordnete Geräte melden USB statt eines falschen MTP-Labels, und ein verpasster USB-Pick bietet den Daemon-Reihen-Picker ("Run on this device" / "Cancel") statt abzulehnen.

### Ehrliche Ergebnisse & GUI-Politur (behoben)
- FRP-Flows verlangen verifizierte Flags und einen echten Shell-Exit-Status; ein nicht-null Bridge-Exit wirft einen Fehler mit dem Log-Tail — keine falschen "completed"-Toasts mehr.
- GUI: Job-Chips pro Reihe, Fenster-Gedächtnis, Toast-Obergrenze, Tastaturnavigation, gerätebewusstes STOP (ein Job bricht dieses Gerät ab), kg_unlock in einen Worker-Thread verschoben (30-Sekunden-Ketten frieren das Fenster nicht mehr ein), Splash folgt dem echten Build, verschobene Seiten bleiben wiederholbar, Toasts räumen die oberste Leiste.

### Sicherheit & Robustheit
- Private-by-default-Ausgaben, symlink-sichere temporäre Namen, Symlink-Prüfungen.
- Firmware-Verify-after-Write standardmäßig + Modell-Gate + numerische Korrekturen.
- FRP: das DPC-Signaturzertifikat wird nativ gelesen und die Provisionierungs-Prüfsumme ist korrigiert.
- HIL-Hardware-Test-Harness: Multi-Device-/Geräteersatz-/USB-Sturm-Regressionen auf echter Hardware; ADB-Monitor-Backoff-Tests deterministisch gemacht.
- Öffentliche Landing-Page (`website/`) mit Capability-Matrix und Protokoll-Konsole.

## 1.2.1 (Stabile Release)

### Multi-Device-Unterstützung (neu)
- Mehrere Telefone einstöpseln: die Verbindungsleiste listet jedes (Modell · Seriennummer · Transporte); klicke eine Reihe, um sie zu inspizieren.
- Jede Operation fragt, auf welches Telefon sie zutrifft, wenn mehrere passen (stillschweigend bei 0–1 Treffern). Konsolenzeilen tragen ein `[device-key]`-Tag.
- Eine Operation pro Gerät: verschiedene Telefone können parallel flashen; dasselbe Telefon serialisiert weiterhin. Globales STOP broadcastet an alle Runner.
- Stabile Identität (`python/core/devices.py`): `adb:<serial>` → `usb:<port-path>` → volatiler Fallback. Ziele werden vor dem Öffnen der Sessions neu aufgelöst, sodass USB-Re-Enumeration keinen Flash mehr verwaist (`usb device Fail`).
- Nur-Telefon-Geräteliste: Hubs, HID, Webcams und Kartenleser werden herausgefiltert.
- Neuer `SPD`-Transportmodus + read-only Qualcomm-/SPD-Detect-Flows.

### Pro-Chip EXPERIMENTAL (neu)
- Samsung `Knox / Warranty`, Qualcomm `QCN / Modem`, pro-Chip `IMEI Repair / Change`, `eMMC / UFS` — bernsteinfarbene Aufklappbereiche auf der zugehörigen Chip-Seite (keine globale LAB-Seite). Jeden-Lauf-Eigentümer-Checkbox; IMEI-Änderung erfordert zusätzlich das Eintippen von `I UNDERSTAND`. Audit-geloggt; persistierte Acknowledgements passen nie automatisch (`check_gate_strict`).

### MTK BROM (behoben + verbessert)
- **PID/Stage-Zuordnung korrigiert** nach mtkclient-Konvention (`0e8d:0003`=BROM, `0e8d:2000`=Preloader) quer durch Rust, Python, GUI-Labels, Logs und Docs.
- Neuer `mtk_crash_brom`-Bridge-Befehl + Flow `MTK crash preloader into BROM` (registriert unter MTK BROM).
- `_wait_mtk_brom_target()` bevorzugt den stabil gehaltenen BROM über das Preloader-Fenster; DA-Erkennung lehnt abgeschnittene (<1KB) Binaries ab.

### Odin / Flashing (gehärtet)
- `_prepare_download_session()`: Kernel-Treiber-Detach + 3× Handshake-Retry über Re-Enumeration; alle Odin-PIDs akzeptiert; PIT-Cache vor Flash vorgewärmt.
- odin4 gepinnt mit `-d /dev/bus/usb/BBB/AAA` + einem automatischen Retry bei USB-Verlust; `.tar.md5`-Trailer am Dateiende verankert (streaming, kein vollständiger RAM-Read).
- Nativer Smart-Flash loggt pro Partition MB/s + ETA.

### Robustheitshärtung (review-gesteuert)
- Sahara: HELLO command/version/mode/packet-size bei Parse validiert (war: jedes ≥32-Byte-Blob vertraut); Transfer-Format-Selbstprüfung round-tript jetzt Structs statt Bytes zu verlieren; Close-Fehler geloggt; Detach vor Claim; Handshake meldet Transfer/Close/Reset-Ergebnisse in JSON statt sie zu verwerfen (Reset explizit und sichtbar).
- ADB-Auth: begrenztes exponentielles Backoff zwischen Token-Runden; einmalige Keygen-Pause angekündigt statt hängend zu wirken.
- MTK: konfigurierte Paketgröße erreicht tatsächlich die DA-Session (wurde berechnet und verworfen; Sessions hardcodiert 64K), auf 512B–1MB geklemmt.
- Sicherheits-Backups: Fehler drucken ein unübersehbares Banner mit verstrichener Zeit und STOP-Hinweis (Vertrag unverändert: blockiert die Operation nie).
- Experimentelle Gates: iCloud + Pixel-Flows auf strikte Per-Run-Acks migriert; GUI-Ack-Token werden jetzt pro Feature gezählt mit Ablauf (kein Cross-Feature-Bleed, keine verlorenen Acks, keine veralteten Autorisierungen).

### GUI-Korrekturen
- Obere rote Rahmen + Button-Schrumpfen auf konkurrierende Shake-/Gummi-Animationen und akzent-eingefärbte Fokus-Ringe zurückgeführt: Animationen mit `_anim_lock` serialisiert + vollständige Bereinigung; neue neutrale `focus_ring`/`sel_border`-Theme-Tokens (rote Akzente können nicht mehr in den Fokus laufen).
- `os.system()` → `subprocess` für Bridge-Rebuild / Log-Dir-Öffnen.
- Doppelter SPD-"Enable ADB"-Stub, `fastboot_unlock`-experimentelles Fehl-Gating, toter FUS→AP-Slot-Pfad und fehlendes `finished`-Emit behoben. Tote LAB/Knox/QCN/PAC-experimentelle Oberfläche entfernt.

### Umstrukturierung
- `python/core/frp.py` (God-Datei) → `python/core/core.py` (Registry + Flows); `frp.py` jetzt nur noch FRP. Tote `python/core/flows/`-Aufteilung entfernt.
- Verb-first Job-Namen (`Remove FRP`, `Flash Firmware`, …); ein kanonischer snake_case-Key pro Flow; Display-Namens-Großschreibung normalisiert.

### Docs
- Neue Screenshots (`docs/samsung.png`, `mtk.png`, `spd.png`), überarbeitete README-Hervorhebungen/Matrix/Layout, CONTRIBUTING-Architektur + Flow-Regeln, dieses Änderungsprotokoll.

### boot.img + AVB (einzelne native Engine)
- Neue Image-Surgery-Engine im Rust-Bridge (`src/imgtools.rs`): Android-Boot-Header-Parse, cpio-newc-Scan, Prop-Patching (pad-in-place oder magiskboot-style Grow mit Header-Rewrite), deterministisches gzip (mtime=0, Level 9), AVB-vbmeta-Flags. CLI `boot-info` / `boot-patch-adb` / `vbmeta-patch`.
- Python-`spd_adb`-Repack + `core._patch_vbmeta_flags` delegieren mit lokalem Fallback (Signaturen und Rückgabeverträge unverändert).
- Equivalenz-Arbeit fand zwei echte Bugs: der Grow-Splice stimmte mit der Leser-Ausrichtung um 2 Bytes nicht überein (verkoroht jeden späteren Eintrag — beide Implementierungen), und erneutes Patchen wuchs pro Lauf um `\n` (beide Seiten jetzt idempotent). gzip-Bytes sind absichtlich von der Parität ausgeschlossen (zlib-Implementierungen differieren); dekomprimierter Inhalt, Größen und Felder stimmen überein.
- 6 Rust-Unit-Tests + 9 Cross-Implementation-Tests.

### PAC (einzelne native Engine + verdrahtete GUI-Aktionen)
- Neue SPD-PAC-Engine im Rust-Bridge (`src/pac.rs`): Parse/Extract/Pack mit dem YGDP-Layout, gemeinsam genutzte Header-/Slot-Builder jetzt auch vom `spd-readback`-Writer verwendet (byte-identische Ausgabe; historische verdoppelte Slot-Namen quarantäniert, nicht propagiert). CLI `pac-parse` / `pac-extract` / `pac-pack`.
- Python `pac.*` delegiert mit lokalem Fallback; neue `flow_pac_extract` / `flow_pac_pack` (nur Datei, ofp-style Env-Eingaben) in FLOWS registriert und im GUI-Dispatcher gemappt — die zuvor toten PAC-Buttons laufen jetzt.
- Äquivalenz-Tests fanden und behoben einen echten Bug: der lokale Packer ließ stillschweigend den Produkt-String fallen (slice-copy write); plus u32-Überlauf-Guards mit identischen Meldungen auf beiden Engines.
- 5 Rust-Unit-Tests + 7 Cross-Implementation-Tests (Roundtrips in beide Richtungen, Sanitize-Parität incl. Dir-Collision, Fehler-Mapping).

### PIT (einzelne native Engine)
- Neue Samsung-PIT-Engine im Rust-Bridge (`src/pit.rs`): Parse (28/132-Layout), Header-/Model-Strings, Name-Normalisierung, Find, Overlap-Scan, forensische Validierung + Gesundheitsverdikte — byte-identische Meldungen, Zusammenfassungen und Verdikte wie die Python-Implementierung auf echten Dumps und Grenzfällen (incl. Python-`repr`-Parität für Junk-Namen).
- CLI `pit-parse` / `pit-health` / `pit-find` / `pit-overlaps` / `pit-model`; Python-`pit.*`-Rohbytes-Pfade delegieren mit lokalem Fallback, wenn das Binary fehlt (Verträge erhalten: ValueError/None/never-raise). In-Memory-Objektpfade und Display-Helfer bleiben lokal und schnell; gemeinsame Regeln von 11 Cross-Implementation-Äquivalenz-Tests gepinnt.
- 8 Rust-Unit-Tests (Layout-Vektoren, Normalize-Tabelle, Meta-Overlap-Klassifikation, Summary/Human-Size-Formen).

### ADB (nativer Transport, keine plattform-tools)
- Neuer nativer ADB-Client im Rust-Bridge (`src/adb.rs`): USB-Transport (255/66/1) mit Kernel-Treiber-Detach, CNXN-Handshake, RSA-SHA256/SHA-1-AUTH (nutzt `~/.android/adbkey`, generiert wenn fehlend), `shell:`- und `sync:`-Services (STAT/RECV/SEND).
- `adb-devices` behält seinen `adb devices -l`-Zeilenvertrag aus nativem Scan (`device` / `unauthorized` / `no permissions`); `adb-shell` nimmt eine Seriennummer (`-` = erstes autorisiertes), plus neue seriennummer-gepinnte `adb-pull` / `adb-push`.
- Python: `bridge.adb_shell()` löst explizit > ambient-scope > erste autorisierte Seriennummer auf (Multi-Device-ADB ist jetzt ziel-gepinnt); `adb.py` delegiert an die Bridge; EFS-Backup/Restore-Pull/Push laufen über die Bridge statt über ungepinnte system-`adb`-Aufrufe. `has_adb()` bedeutet jetzt "Binary gebaut".
- 6 Rust-Tests (Framing, Banner, PKCS#1 Sign/Verify, DER-Roundtrip, bit-identischer Pubkey-Blob vs. system-adb-Key) + 9 Python-Tests.

### Fastboot (nativer Transport + Motorola universal)
- Neuer nativer Fastboot-USB-Transport im Rust-Bridge (`src/fastboot.rs`): `fastboot-devices` (JSON) + `fastboot-cmd <vid:pid@bus:addr> <ms> <cmd…>` für die Kommandophase (getvar/oem/erase/reboot) mit Kernel-Treiber-Detach. Geräteseitiges FAIL rendert als `FAILED (remote: …)` mit Exit 0, passend zur Transkriptform des System-Binaries (incl. einzelner `getvar`-Werte, die auf Moto MBM-Bootloadern im OKAY-Paket reisen).
- Gemeinsame Python-Helfer (`_fastboot_run`, `_wait_fastboot`, `_fastboot_getvar`) sind native-first mit System-Binary-Fallback; DATA-Phasen-Kommandos (flash/boot/…) nutzen stets das System-Binary, und die Host-seitige `devices`-Liste wird aus nativem Detect bedient. Sämtlicher Fastboot-Verkehr ist jetzt ziel-gepinnt (`vid:pid@bus:addr`), schließt die Kein-`-s`-Falsch-Telefon-Gefahr.
- Neue markenweite Motorola-Flows (`moto_frp_adb`, `moto_frp_fastboot`, `moto_oem_unlock_token`): ADB-Provisioning-Reset, offizieller Unlock-Token-Flow mit Lock-State-Lesen + Session-Resets, read-only Token-Reader. Angezeigt unter Motorola → All Motorola / Lenovo (universal) und jedem Moto-Modell; Unlock-Portal-URL korrigiert (altes `motorola.com/unlockbootloader` tot).
- `python/core/fastboot.py` (Pixel) und `usb_watch.py` (lsusb-Scraping) auf die Bridge umgezogen; 7 neue `tests/test_fastboot_native.py`-Tests.
