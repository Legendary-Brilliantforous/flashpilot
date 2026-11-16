# ImproveCore — Verbesserungen des Rust-Kerns

Language switcher: [English](../../improvecore.md) · [Français](../fr/improvecore.md) · [Español](../es/improvecore.md) · **Deutsch**

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

Quelle: Rust-bezogene Punkte, die aus `ui-improvement.md` verschoben wurden.

## ADB-Flashing pro Gerät
- Gerätespezifische ADB-Sessions mit Retry/Backoff und klarer Zustandsmaschine.
- Verify-after-Write (Hash) standardmäßig; Fortschritt pro Partition.
- Robuster Umgang mit nicht autorisierten/Offline-Zuständen; automatische Re-Auth-Aufforderung.
- Unterstützung mehrerer gleichzeitiger ADB-Geräte ohne Übersprechen.

## Odin (Samsung) Innovation
- Besser als neuestes Odin: Single-Session-Resilienz, Port-Reset-Wiederherstellung, Multi-Partition-Streaming.
- Bessere PIT-Validierung, vbmeta/AVB-Handling, drk-Reparaturhinweise.
- Fortsetzen/Wiederholen bei transienten USB-Fehlern; detaillierte Fehlererklärungen.

## BROM / Low-Level-Kommunikation
- Einheitliche BROM-Abstraktion für MTK, Samsung, SPD, Qualcomm.
- Crash-to-BROM-Helfer, SLA/Auth, zuverlässiger DA-Upload.
- Fehlerklassifikation mit umsetzbaren Fixes; Timeouts pro Stage.

## Neueste MTK-Unterstützung
- Preloader V5/V6-Parsing und DA-Auswahl (`mtk_daloader.rs`).
- Verfolgung der neuesten MTK-DA-/Preloader-Versionen; automatische Erkennung und Auswahl.
- Sicherstellen, dass Exploit-/SLA-Pfade auf neuesten Chips funktionieren; Test-Fixtures hinzufügen.

## USB-Schnittstellenerkennung
- Erkennung von CDC ACM, ECM/NCM, Mass Storage, HID, Vendor-Specific, Diagnose/Modem.
- Erkennung von BootROM, Preloader, ADB, Download-Mode, EDL, MTK, SPD.
- Schnittstellenliste in Gerätereihen exponieren; Zuordnung zu unterstützten Flows.

## Sofortige Entfernung (FRP/MDM/Sperren)
- Recherche-Integration wie HiProTool: schnelle Pfade, wo sicher, dokumentiert.
- Gerätespezifische Playbooks in `operations/` mit verifizierten Schritten.
- Experimentelles Gating + Audit-Logging für riskante Operationen beibehalten.
