# FlashPilot 1.2.1 — Stabil

Language switcher: [English](../../DESCRIPTION.md) · [Français](../fr/DESCRIPTION.md) · [Español](../es/DESCRIPTION.md) · **Deutsch**

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

Open-Source-Linux-Workbench zum Flashen und Reparieren von Android-Geräten — das
kostenlose Äquivalent zu kommerziellen Windows-Flash-Suiten. **1.2.0 ist ein
Stabilitäts- + Fortschritts-Release: `cargo check` 0 Warnungen, `cargo test` 60 +
`pytest` 149 bestanden, live GitHub-Release-Kanal und nachvollziehbare
Historie.**

Ein nativer **Rust**-Kern (`flashpilot-bridge`, ~9.300 LOC, vendored libusb)
spricht direkt mit Bootloader-Protokollen — Samsung Odin/HID, MediaTek
BROM/DA, Qualcomm Sahara/Firehose, Spreadtrum/UNISOC BSL — während ein
poliertes **PyQt6**-Studio 9 Transporte, 13 Job-Kategorien und ~120
Operationen präsentiert: Flashen, FRP-Bypass, Bildschirmsperre entfernen,
MDM-Entsperrung, Partitionstools, Geräteinfo, Neustart sowie Akku-/Netzwerk-
Reparatur an jedem ADB-Gerät.

**Neu in 1.2.0 stabil:**
- **Bridge 0 Warnungen** — 18 tote Pfade verdrahtet: AT-`Context`-Retention
  und `vid`-Validierung (`AT/control`-Re-Enumeration nach `+DEBUGLVC`),
  USB-`EndpointConfig.max_packet_size`-Chunking & `open_target/read_exact/info`,
  SPD `BSL_CMD`/`BSL_REP` + `iface` + `flush/read_flash/chip_uid/power_off`,
  `ProgressReporter` → echte Flash-%, Qualcomm `QcomDeviceInfo`/
  `FirehosePacket`, MTK `read16/write16` — `-80KB` `lto`, keine Handle-Lecks.
- **Dynamische Version** — `APP_VERSION` aus installiertem
  `importlib.metadata` (deb-`pyproject.toml` ist Truth), `_display_version`
  `1.2.0→1.2` / `1.2.1→1.2.1`, live GitHub `latest stable` (niemals
  händisch codiert), BETA-Pille auf Logo/Titelbar.
- **Einheitliche große Dialoge** — 620 px zentrierte ziehbare Karten (vs.
  320 px Toast) mit hochkontrastierendem `#e2e8f0`-Text, `✕` + `X`-Drag,
  Chip-Farben: `MTK amber`, `QCOM red`, `SPD violet`, `SAMSUNG blue`; Beta-Gate
  erfordert Checkbox `I accept` (persistiert pro Version, `first_install`-
  Standard / `every_boot`-Toggle in Einstellungen → Updates), `Exit` beendet
  die App, stabiles `UPDATE/AHEAD/PATCH` nutzt denselben großen Dialog,
  Flash-/FRP-Bestätigungs-Overlays nutzen den Chip-Gradienten.
- **Ein globales STOP** — einzelnes `⏹ STOP` in der Titelleiste (außerhalb
  jeder Karte), 150 ms Sync zu `_FLOW_LABEL`, stoppt *jeden* Samsung/MTK/
  QC/SPD-Flow; veraltete Chip-STOPs sind versteckt.
- **Governance** — `dev`/`main` geschützt: `strict`-CI `Rust+Python`, `1`
  Review, `dismiss_stale`, `require_last_push_approval`, `linear_history`,
  `force_push:false`; `devin-ai-integration[bot]` aus Historie/Tag
  `v1.2.1-beta.1` → `55c0da3`.

- **Plattform:** Linux
- **Sprache:** Rust (Kern) + Python 3.10+ / PyQt6 (UI)
- **Lizenz:** MIT
- **Status:** stabil 1.2.0 — Mitwirkende willkommen

Verwende es nur an Geräten, die dir gehören oder die du reparieren darfst.
