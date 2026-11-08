# Änderungsprotokoll

Language switcher: [English](../../CHANGELOG.md) · [Français](../fr/CHANGELOG.md) · [Español](../es/CHANGELOG.md) · **Deutsch**

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 1.3.2 (der Badge nennt das USB-Protokoll)

- Der Modus-Badge zeigt nicht mehr OTHER für ein verbundenes Gerät: "MEDIATEK" enthält die Teilzeichenkette "MTK" nicht, daher fiel ein generisches MTK-Modus-Label ('MEDIATEK MODE (VID 0x0E8D PID 0x2008)') ganz bis OTHER durch.
- Ein normal gebootetes MediaTek/Tecno-Telefon mit unpassender PID (0e8d:2008, Still-Image-/MTP-Schnittstelle, keine ADB-Reihe) wird nicht mehr als Low-Level-MediaTek in Anspruch genommen: nur Flash-PIDs (BROM/Preloader/DA) beanspruchen das Low-Level-Label, alles andere fällt durch auf schnittstellenbasierte Protokollbenennung (ADB/MTP/PTP/DIAG/storage/RNDIS) über ALLE Gerätelisten — zuvor wurden nur Samsung-Geräte protokollgescannt.
- Rust-Transporte: eine unpassende PID, die noch eine Still-Image-Schnittstelle (Klasse 6) exponiert, meldet MTP statt USB; Hardware ohne MTP-Schnittstelle behält das ehrliche USB-Label.
- Das Verbindungs-Label zeigt "MediaTek device (normal boot)" statt "MediaTek low-level" bei Nicht-Flash-PIDs.
- Qualcomm-EDL behält seinen eigenen Badge-Chip: "EDL MODE (Qualcomm Emergency Download)" enthält die Teilzeichenkette "download" und fiel zuvor auf den DOWNLOAD-Chip durch.
- Qualcomm-HS-USB-Diagnosen (05c6:9006, z. B. Moto in Diag) werden als "QUALCOMM DIAG MODE (HS-USB Diagnostics 9006)" benannt statt in das generische "QUALCOMM DEVICE"-Label zu verschmelzen.

## 1.3.1 (ModeBadge-Korrektur)

- Der Gerätemodus-Badge (oberste Leiste, bei Stop) folgt dem AUSGEWÄHLTEN Gerät und liest nicht mehr MTP für Qualcomm-normal-Konfigurationen (die Teilzeichenkette "normal" fiel auf den MTP-Chip durch).

## 1.3.0 (Geräteklassifizierung + Picker)

- Nicht zugeordnete Geräte (vendor-spezifische/diag-Komposite) melden "USB" statt des falschen "MTP"-Labels.
- Wenn der USB-Pick bei einem Flap verfehlt, zeigen ADB-Tools den Daemon-Reihen-Picker statt abzulehnen: wähle, auf welches Gerät die Operation zielt.

## 1.2.9 (Anzeige-Geräteidentität)

- Geräte zu wechseln fällt nicht mehr auf das erste Telefon zurück: die 3-s-Aktualisierung, der Live-Identitäts-Resolver und alle Fallbacks richten sich nach dem angezeigten Gerät; der Pfad bei Abwesenheit behält die statischen Kacheln der Reihe.

## 1.2.8 (Gerätelisten-Wechsel-Korrektur)

- Der Neuaufbau der Verbindungsleiste wiederholt sich, wenn der zweite Scan in einem Zeitfenster der Re-Enumeration ein vom Monitor gerade gesehenes Gerät verliert: beide Geräte werden gerendert und das Wechseln funktioniert auf flatternden Links.

## 1.2.7 (Ziel-Identitätsbindung)

- Ein ersetztes Gerät, das einen wiederverwendeten bus:addr besetzt, wird abgelehnt (Zero-Touch-Serienprüfung am Ziel; das Öffnen gleicht vid/pid/bus/addr ab, nicht die Seriennummer). Schließt das Szenario des Geräteersatzes: Der Transport wird nie zu einem anderen Gerät verfolgt.

## 1.2.6 (Daemon-Reihen-Fallback)

- ADB-Tools fallen auf die ADB-Daemon-Reihe zurück, wenn der USB-Scan-Pick auf einem flatternden Bus verfehlt (der Daemon ist TCP-basiert und bleibt autoritativ für Präsenz). Behebt "zeigt verbunden, aber Aktionen sagen kein adb".

## 1.2.5 (MTK-Ecken-ADB-Overlay)

- Der mtk_devs-Ecken-Zweig zeigt jetzt das ADB-Overlay wie Geschwister-Zweige: ein Tecno-/MTK-Gerät mit autorisiertem ADB benennt den Transport oben rechts (zuvor nur "MediaTek low-level", während ADB Status verbunden zeigte).

## 1.2.4 (ADB-AUTH-Korrektur)

- AUTH-Hash-Alternation korrigiert: SHA-256 bleibt über Token-Runden in Spiel (ungerade Runden SHA-256, gerade SHA-1). Zuvor re-tokenierte ein verlorener Runde-1-Signatur auf einer rauschigen Verbindung in eine Wand aus SHA-1 -> falsches "not authorized", obwohl das Gerät autorisiert war.
- `_wait_for_adb` toleriert transiente Scan-Fehler während des Wartens.

## 1.2.3 (Pick-Resilienz)

- Geräte-Pick mit Settle-Retry: jeder Tool-Runner wiederholt einmal nach 2,5 s, wenn ein Scan ein re-enumerierendes Gerät transient verfehlt, statt mit "no device" abzulehnen, während die GUI es verbunden anzeigt. Vom Benutzer abgebrochene Auswahlen werden nie wiederholt.

## 1.2.2 (modemsicheres ADB + Anzeigekorrekturen)

### ADB-Transport (behoben)
- Poll-/Monitor-/Anzeige-Pfade sind zero-touch (`adb-devices --no-probe`, `adb_presence`): keine open/claim/handshake aus Schleifen. Behebt USB-Modems, die jeden Zyklus re-enumerieren (live verifiziert: 114 ruhige Poll-Zyklen auf einem MSM8916-Modem nach ~1 Hz-Stürmen).
- Delegationsleiter bei Claim-Kämpfen: nativ -> Rust-Server-Transport (`adb-shell-server`, explizit nur Seriennummer) -> Host-Binary -> Rettungs-kill (letzter Ausweg). ADB-Ops gelingen jetzt mit dem System-Server, der die Schnittstelle hält, statt diese zu verdrängen.
- USB-ADB-Merge-Korrektur: Reihenzeichenketten werden geparst (Strukt-Deserialisierung hatte stillschweigend null ADB-Einträge geliefert, sodass Reihen nie ADB-Zustand trugen).
- QCOM-Ecke zeigt jetzt das ADB-Overlay wie Geschwister-Zweige.

### Robustheit (behoben)
- Einzelnes Settle-Retry bei transienten Gate-Ablehnungen (Re-Enumerations-Fenster) mit genauen Meldungen; `rescue=False` + Serien-Pinning über alle Diagnose-/Tool-Shells; Firehose-FAIL-Erkennung; CLI-Eingabe-Panics; Allokations-Klemmen; tar-Traversal-Guards; strenge XML-Numerik.

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
