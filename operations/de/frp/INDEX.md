Language switcher: [English](../../frp/INDEX.md) · [Français](../../fr/frp/INDEX.md) · [Español](../../es/frp/INDEX.md) · **Deutsch** · [简体中文](../../zh/frp/INDEX.md) · [Русский](../../ru/frp/INDEX.md) · [Português](../../pt/frp/INDEX.md) · [日本語](../../ja/frp/INDEX.md) · [العربية](../../ar/frp/INDEX.md) · [हिन्दी](../../hi/frp/INDEX.md) · [Türkçe](../../tr/frp/INDEX.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# operations/frp/ — Factory Reset Protection (nur Android)

> Apple-Geräte haben keine FRP (Apple verwendet stattdessen Activation Lock / iCloud) —
> siehe `operations/apple/`.

Dieses Verzeichnis enthält **Per-Engine-Dokumentationsbäume** für FRP-Bypass.
Der eigentliche Code lebt in `src/flows.rs` (Rust). Wenn du ein echtes
Rezept für ein Gerät hast (Chip, FDL-Paar, Partitions-Offsets usw.), legst du
eine kurze Research-Notiz in `devices/<brand>/<model>.md` ab. Das README im
Root dieser Datei ordnet jeden FRP-Flow im Codebase seinem Ort und seinen
Anforderungen zu.

## Engine-Map

| Engine | Wann verwenden | Code | Bridge-CLI |
|---|---|---|---|
| **Generic (ADB)** | Erster Versuch auf jedem Telefon mit USB-Debugging an | Rust-Flows (`adb_frp`, `frp_*`-Zeilen in `src/flows.rs`) | `flow-run adb_frp` / `adb shell ...` via `bridge.adb_shell` |
| **MTK BROM** | MediaTek (Helio / Dimensity / MT6765) — ausschalten → Vol-/+ halten → USB einstecken | Rust-Flows (`mtk_*`-Zeilen in `src/flows.rs`) | `flow-run mtk_brom_info` (CLI: `mtk-detect`, `mtk-da-upload`, `mtk-frp`, `mtk-bypass`) |
| **MTK DA** | MTK BROM, der DA-Upload überlebt hat (lock-state-Chips) | Rust-Flows (`mtk_brom_backup`, `mtk_auth_flash`) | `flow-run mtk_brom_backup` |
| **Qualcomm EDL** | 9008 Emergency Download (Snapdragon) | Rust-Flows (`edl_*`, `qcom_*`-Zeilen) | `flow-run edl_frp` (CLI: `qcom-*`) |
| **Samsung Exynos** | A14 (Exynos 850/1330), A15/A16 — Odin-Download-Modus ist nur Flashen, NICHT für FRP | Rust `frp_*`-Zeilen (Samsung-Account-Bypass) | (meist on-device, keine Bridge) |
| **Samsung MTK (A05/A06)** | A05/A06 mit Helio G85 — nutzt MTK BROM (siehe oben) | Rust-Flows (`mtk_brom_info`, `mtk_brom_backup`) | `flow-run mtk_brom_backup` |
| **UNISOC/SPD** | 1782:4d00 FDL1+FDL2 (SC9863A, T606/UMS9230) | Rust-Flows (`spd_*`-Zeilen) + `src/spd.rs` | `flow-run spd_detect_info` (CLI: `spd-detect`, `spd-frp`, `spd-format`, `spd-magic-pack`) |
| **HiSilicon Kirin** | 12d1 — noch kein offener Flow (nicht reverse-engineered) | (noch nichts) | (nichts) |

( Die alten Engine-Module unter `python/core/flows/*.py` wurden nie ausgeliefert;
`mtk-brom-backup` ist die Flow-Zeile `mtk_brom_backup`. Verifiziere jeden Key
mit `flow-list`. )

## Flow key → Funktions-Map

Jeder Flow, den die FRP-Aktionen der GUI aufrufen können. Keys sind Rust-
Registry-Zeilen (`src/flows.rs`, mit `flow-list` verifizieren); die GUI routet
über (job, mode) und die Bridge führt sie via `flow-run <key> [target]` aus.

| Flow key | Engine | Was es tut |
|---|---|---|
| `adb_frp` | Generic ADB | `settings put secure frp 0` + Setup-Wizards deaktivieren + GMS-Daten löschen |
| `frp_browser` | Generic ADB | `chrome://settings/` on-device per Intent öffnen |
| `frp_emergency` | Generic ADB | Settings via Emergency-Call-Dialer öffnen (on-device) |
| `frp_settings` | Generic ADB | Settings via Notification-Shade-Pfad öffnen (on-device) |
| `frp_fake_login` (+`_testdpc`, `+_adp`) | Generic ADB | QR-Provisioning mit einem Device-Owner-DPC, dann FRP-Clear |
| `at_info` | Samsung MTP/AT | Modus + devconinfo über AT-Kanal lesen (Samsung pre-Android 8) |
| `at_method` | Samsung MTP/AT | AT+DEBUGLVC, um ADB über den diag-Port freizuschalten |
| `download_frp` | Samsung Download mode | CSC-/Combination-Firmware FRP-Entfernung (PIT-Safety-Vertrag) |
| `odin_enable_adb` | Samsung Download mode | ADB aus dem Download-Modus über Odin-Tarball freischalten |
| `mtk_combo_flash` | MTK Download | Combination-Firmware-Flash (PIT + DA) |
| `mtk_recovery_reset` | MTK Download | Factory-Reset im Recovery-Modus |
| `mtk_brom_info` | MTK BROM | Chip-ID / Handshake lesen (vor jedem BROM-Flash nötig) |
| `mtk_brom_backup` | MTK BROM | Partitionen via BROM-DA dumpen |
| `edl_frp` | Qualcomm EDL | Sahara + Firehose Erase (05c6:9008) |
| `qcom_detect_info` | Qualcomm EDL | Erkennen + Info (read-only) |
| `frp_qr_provision` | Generic ADB | QR-Provisioning (TestDPC-Pfad) |

(Als retired gilt: alte `flow_*`-präfixierte Key-Namen und `python/core/flows/*.py`
wurden nie ausgeliefert — Keys haben kein `flow_`-Präfix.)

## Wie ein neues Per-Modell-Rezept hier landet

1. **Echten Geräte-Dump fahren** (siehe `scripts/dump-connected.sh` für den
   ADB-Pfad, oder `flashpilot-bridge spd-format` für den BROM-Pfad auf Unisoc).
   Der Dump landet in `build/cache/dumps/<model>_<codename>/`.

2. **Aus dem Dump ermitteln:** Engine + Chip + Name der FRP-Partition
   (fast immer `frp`, `frp_a` oder `userdata` unter Android 11+).

3. **Geräte-Eintrag hinzufügen** in `python/gui/supported_devices.json` unter der
   richtigen Marke, mit `actions: ["frp", "info", "backup", "flash"]` und
   `status: "researched"`. (Der bestehende Per-Engine-Flow nimmt ihn automatisch
   auf — kein neuer Flow nötig, sofern nicht die Engine selbst fehlt.)

4. **Kurze Research-Notiz ablegen** in
   `operations/frp/devices/<brand>/<model>.md` mit Chip, Engine, Partition,
   Build-Fingerprint und einem Einzeiler, der das Rezept bestätigt (z. B.
   "mmcblk0p4 = frp, sofortiger BROM-DA-Erase, kein Combo nötig"). Siehe
   `operations/frp/devices/nokia/nokia_g20.md` für das Format.

5. **Falls die Engine selbst für diesen Chipset keinen Flow hat**, den Flow in
   `src/flows.rs` registrieren (eine `flow!(...)`-Zeile) und den CLI-Dispatch in
   `src/<engine>.rs` + `src/main.rs` hinzufügen.

## Warum die Per-Chip-Dateien weg sind

Frühere Refactorings splitte das God-`frp.py` in Per-Chip-Dateien unter
`operations/frp/chips/` und Per-Engine-Dateien unter
`operations/frp/{mtk,qualcomm,unisoc,samsung}_frp/` auf. Eine ältere Revision
dieser INDEX behauptete Dead-Docstubs und einen `python/core/flows/brom.py`-
Dispatch — dieses Modul wurde nie ausgeliefert. Der echte Per-Chip-Dispatch
ist die Rust-Flow-Registry (`src/flows.rs`: `mtk_*`/`qcom_*`/`spd_*`-Zeilen,
mit `flow-list` verifizieren); diese INDEX.md ist die Karte, damit ein neuer
Dev weiß, wo der Engine-spezifische Code tatsächlich lebt.

## Warum die Per-Engine-Python-Shims weg sind

`operations/frp/mtk_frp/mtk_frp.py` (und seine 4 Geschwister) importierten
Funktionen aus `python.core.flows.brom` und re-exportierten sie unter einem
**zweiten** `FLOWS = {}`-Dict, das die GUI nie las. Sie kollidierten mit dem
kanonischen `FLOWS` in `python/core/flows/__init__.py` und hätten die echten
maskiert, wenn die GUI sie gelesen hätte. Ersetzt durch ein README in jedem
Engine-Ordner, das auf die echten Python-Module verweist.
