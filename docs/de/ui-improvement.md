# FlashPilot Intensiver UI-Verbesserungsplan

Language switcher: [English](../../ui-improvement.md) · [Français](../fr/ui-improvement.md) · [Español](../es/ui-improvement.md) · **Deutsch** · [简体中文](../zh/ui-improvement.md) · [Русский](../ru/ui-improvement.md) · [Português](../pt/ui-improvement.md) · [日本語](../ja/ui-improvement.md) · [العربية](../ar/ui-improvement.md) · [हिन्दी](../hi/ui-improvement.md) · [Türkçe](../tr/ui-improvement.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## Ziel
Die PyQt6-GUI von einem funktionalen Monolithen in ein poliertes, wartbares und leistungsfähiges Workbench verwandeln, während alle Rust-gestützten Flows und das Mehrgeräte-Verhalten erhalten bleiben.

## Aktueller Zustand
- `python/gui/qt_app.py` (~15k LOC) ist ein einziges monolithisches Fenster.
- Das Theme-System (`theme.py`) ist zentralisiert, aber das QSS ist groß und an Stellen dupliziert.
- Verbindungsleiste, Navigations-Rail, chip-spezifische Seiten, Konsole und Einstellungen sind alle in einer Datei.
- Es existiert bereits eine starke visuelle Identität (Glas-Karten, 10 Akzente, Kabel-Szene).

## Prinzipien
1. Keine Protokolllogik in Python; die UI rendert nur und ruft die Bridge auf.
2. Rust bleibt die Quelle der Wahrheit für Flows/Jobs/Modes.
3. Responsivität verbessern: schwere Arbeit aus dem UI-Thread herausnehmen, Widget-Churn reduzieren.
4. Barrierefreiheit: Tastaturnavigation, Fokusringe, Screenreader-Labels.
5. Wartbarkeit: `qt_app.py` in Feature-Module aufspalten.

## Phase 0 — Fenster-Shell, Logo, Splash (neu)
- Aktuelles Logo durch ein professionelles Vektor/SVG-Zeichen ersetzen (monochrome + Akzent-Varianten, 16/32/64/128/256px + .ico/.icns).
- Splash-Screen: animiertes Markenzeichen, Fortschrittsstufen (Rust-Bridge initialisieren, Geräte scannen, Theme laden), Version, kein Flackern; Ein-/Ausblenden 200ms.
- Fenster-Rendering: rahmenloses durchscheinendes Fenster mit compositor-freundlichem Alpha, abgerundeten Ecken, Drop-Shadow, DPI-bewusster Skalierung, Fensterplatzierungsspeicher über mehrere Monitore.
- Flüssigkeit: Qt `AA_UseHighDpiPixmaps` aktivieren, Surface-Format (OpenGL/RGBA) setzen, vsync-freundliche Animationen, Layout-Thrashing reduzieren; Ziel 60fps-Interaktionen.
- Branding: konsistentes Logo in Titelleiste, Taskleiste, About-Dialog, Installer.
- Größenveränderbare Shell-Spalten: die Grenze **Gerätepanel | Seite** ist ein ziehbarer horizontaler Splitter (Standard 232px, ziehbar 228–420px, gespeichert in `layout/device_panel_width`). Die Seite behält ihre natürliche Breite und lebt in einem rahmenlosen Scroll-Bereich, sodass sie beim Zusammendrücken seitlich scrollt, statt ihre Tabs/Grids zu reflowen; die Panelbreite wird über Fenstergrößenänderungen hinweg gehalten, bis der Nutzer sie zieht. _Entscheidung (Nutzer): zuvor ein hartes `setFixedWidth(232)`._

## Phase 1 — Architekturaufteilung (keine visuelle Änderung)
- Page-Builder extrahieren in `python/gui/pages/`:
  - `samsung.py`, `mtk.py`, `qc.py`, `spd.py`, `battery.py`, `network.py`, `settings.py`, `quick.py`.
- Gemeinsame Widgets extrahieren in `python/gui/widgets/`: `metric_card.py`, `collapsible.py`, `console.py`, `device_picker.py`.
- `qt_app.py` als Shell behalten: Fenster-Chrome, Navigation, Routing, Signale.
- Akzeptanz: App startet, alle Tabs rendern, Tests bestehen.

## Phase 2 — Leistung
- Geräte- und Konsolenliste virtualisieren (QAbstractListModel + QListView), um O(n)-Widget-Erzeugung zu vermeiden.
- Log-Updates batchen (alle 50ms oder 100 Zeilen).
- Gerendertes QSS pro Theme cachen; nur bei Akzentänderung neu generieren.
- Schwere Seiten lazy laden (beim ersten Besuch aufbauen).
- Akzeptanz: 10k Log-Zeilen ohne UI-Stall; Scrollen bleibt 60fps.

## Phase 3 — Visueller Feinschliff
- Design-Tokens: Abstands-Skala (4/8/12/16/24), Radius-Skala, Elevation.
- Konsistente Karten-Elevation/Schatten; Hover-/Fokus-Zustände.
- Bewegung: Seiten-Fade 120ms, Button-Druck-Skalierung, Toast-Gleiten.
- Icon-System: Emoji durch SVG-Icons ersetzen (Marken-Glyphen).
- Leere Zustände und Skeletons für Geräteerkennung.
- Hochkontrast-Modus + Reduced-Motion-Schalter.

## Phase 4 — UX-Flows
- Einheitlicher Geräte-Picker-Dialog mit Suche/Filter und Transport-Badges.
- Operation-Fortschritt: Schrittliste mit Häkchen, ETA, Abbruch pro Gerät.
- Fehlerdarstellung: handlungsorientierte Karten mit „retry / open docs / copy log“.
- Einstellungen: durchsuchbar, gruppiert, mit Zurücksetzen auf Standardwerte.
- Konsole: nach Level/Gerät filtern, exportieren, suchen.

## Phase 5 — Barrierefreiheit & i18n
- Vollständige Tab-Reihenfolge, sichtbarer Fokus, ARIA-ähnliche Labels.
- Tastenkürzel in der App dokumentiert.
- Zeichenketten-Extraktion für Übersetzungen (keine hardcodierten Nutzer-Zeichenketten in Widgets).

## Phase 6 — Tests
- GUI-Smoke-Tests mit pytest-qt (headless).
- Visuelle Regressions-Screenshots für jede Seite/Theme.
- Performance-Benchmarks für Log-/Geräte-Rendering.

## Deliverables
- `python/gui/pages/*`, `python/gui/widgets/*`
- Aktualisiertes `theme.py`-Token-System
- `tests/test_gui_smoke.py`
- Dokumentations-Update in README/INDEX.

## Risiken
- 15k-LOC-Monolith; inkrementelle Extraktion erforderlich.
- PyQt-Threading-Regeln; alle Widget-Zugriffe auf dem Hauptthread halten.
- Mehrgeräte-Scoping und Abbruch-Semantik erhalten.

## Vorgeschlagene erste Aufgabe
`_build_console` und `_build_conn_bar` in `widgets/console.py` und `widgets/connection_bar.py` mit Signal-basierter API extrahieren; keine Verhaltensänderung.

## Phase 7 — Flow & Job Rendering (neu)
### Beobachtete Probleme
- `_add_job_flows` flacht alle Modi zu einer Button-Liste pro Job; der Modus ist nur im Tooltip, was für Verwirrung sorgt.
- Doppelte Buttons über Seiten (Quick, Chip-Ops-Abschnitte, Unlock-Tabs) mit inkonsistentem Gating.
- Experimentelle/destruktive Buttons sind nur durch Farbe/Rahmen unterscheidbar; keine Legende.
- Keine Suche/Filterung, keine zuletzt verwendeten, keine Favoriten.
- Lange Flow-Labels laufen in `FlowLayout` unvorhersehbar über/um.
- Keine visuelle Gruppierung nach Risiko (nur lesend vs. Flash vs. experimentell).

### Vorgeschlagenes Rendering-Modell
- **Job → Mode → Method** dreistufige Navigation:
  - Links: Job-Liste (verbo-first, Icons).
  - Mitte: Mode-Tabs (ADB, MTP, …) mit Zählern.
  - Rechts: Method-Karten (Name, Risiko-Badge, Experimental-Badge, Tooltip).
- Single Source of Truth: `core.modes_for` / `core.methods_for`; keine doppelten Listen in Seiten.
- Global deduplizieren nach (job, mode, key); Chip-Seiten filtern nach unterstützten Modes statt `_add_job_flows` erneut auszuführen.
- Method-Karten-Zustände: aktiviert/deaktiviert durch Geräte capability-Gates, laufend (Spinner), letztes Ergebnis (ok/fail).

### Was zu verschieben ist
- Button-Konstruktion aus `_add_job_flows` in `widgets/flow_button.py` + `widgets/method_card.py` verschieben.
- Mode/Job-Enumeration in ein `FlowRegistryView`-Modell (dünn, keine Logik) für UI-Bindung verschieben.
- Destruktiv/Experimentell-Bestätigungslogik in einen wiederverwendbaren `ConfirmDialog` verschieben.

### Was zu verschmelzen ist
- Quick-Seite und Chip-Ops-Seiten zu Nutzung desselben `FlowBrowser`-Widgets mit `modes`-Filter verschmelzen.
- Experimentelle Warnungsbehandlung in Card-Badge + Dialog verschmelzen.

### Was zu entfernen / duplizieren ist
- Per-Seiten-`_add_job_flows`-Aufrufe entfernen, die dieselben Job-Flows duplizieren; durch gefilterten `FlowBrowser` ersetzen.
- Doppelte `Flow`-Instanzen (derselbe Schlüssel unter mehreren Modes) durch Gruppieren der Modes auf der Karte entfernen.
- Raw `QLabel(job.upper())`-Header zugunsten von Abschnitts-Headern mit Zählern entfernen.

### Neue Features
- Suchbox filtert nach Job/Mode/Method-Name und Schlüssel.
- Favoriten/Zuletzt verwendete werden in den Einstellungen gespeichert.
- Risiko-Legende: nur lesend (grün), mittel (bernstein), hoch (rot), experimentell (gestrichelt bernstein).
- Batch-Auswahl: Checkboxen zum Einreihen mehrerer Methoden (sequentiell mit Abbruch pro Schritt).
- Drag-to-Reorder für Favoriten.

### Akzeptanz
- Ein konsistenter Flow-Browser auf allen Seiten.
- Keine doppelten Method-Buttons für dasselbe (job, mode, key).
- Suchfilter in <50ms für 280 Zeilen.
- Capability-Gates deaktivieren Methoden visuell mit Grund im Tooltip.

### Phase 7 — Status (bisher implementiert)
- **Gewählte Form: In-Place-Upgrade.** Den einzelnen Rendering-Pfad jetzt einführen und ihn an Ort und Stelle aufrüsten — `FlowBrowser` (View) + `MethodCard` (Button) + `flow_meta` (Routing/Risiko) — *ohne* die dreiteilige Job → Mode → Method-Navigation. Seiten behalten ihr aktuelles Layout; `_add_job_flows` baut Zeilen und rendert sie durch `FlowBrowser`, und Klicks routen durch `flow_meta.route_for`.
- **Abgeleitetes Risiko-Modell** (`flow_meta.risk_for`, die einzige Quelle, aus der ein Badge lesen darf): `experimental` = Schlüssel in `_EXPERIMENTAL_FLOW_MAP`; `high` = Schlüssel in `_DESTRUCTIVE_CONFIRM` und damit **genau die Flows, nach denen die UI ohnehin schon fragt** (ein Badge kann nie `high` behaupten ohne Dialog, noch `read` ohne nur lesend zu sein); `read` = nur für `READ_ONLY_JOBS` (`{"Read Device Info", "Detect Devices"}`); alles andere, einschließlich unbekannter Schlüssel/Jobs, fail-closed nach `medium`.
- **Slice B1 — gruppiertes Flow-Rendering (dieser Slice).** `FlowBrowser.set_rows` gruppiert jetzt, was es rendert, und behebt die drei benannten Probleme:
  - Job-Header ist jetzt `{"REMOVE FRP"} · 6` — das rohe `QLabel(job.upper())` erhielt eine Methoden-**Zählung** (gedimmt mit dem `border_hi`-Token, der Name behält die bestehende 11px/800/1px-Behandlung).
  - Innerhalb jedes Jobs werden Karten nach **Transport-Mode** mit einer kleinen Mode-Unterüberschrift (`— ADB`) gruppiert, statt als eine flache Per-Job-Liste mit dem Mode nur im Tooltip. Zeilen kommen mode-major aus `_flow_rows`, sodass ein Lauf gleicher Modes ein Abschnitt ist; kein Mode wird jemals in extra Karten expandiert.
  - Jede `MethodCard` malt eine semantische **Linkskante** (`ok` nur lesend, `warn` mittel, `err` hoch, `experimental` experimentell) komponiert über `_btn_ghost()`, sodass Risiko auf einen Blick neben der bestehenden Legende sichtbar ist. Experimentelle Karten behalten ihren bernsteinfarbenen **gestrichelten** Rahmen — nun im Besitz von `MethodCard.set_risk(level)`; `set_state` bleibt inert.
  - Unverändert durch Konstruktion: die gerenderte Zeilenmenge, die Dedupe-Regel („erster Mode gewinnt“ pro Job), Button-Text (`btn_sha`), jede Tooltip-Zeichenkette, Klick-Routing, die Confirm/Experimental-Overlays und die Gate-Registry (`job=`/`mode=`, nie `command=`). Nur Gruppierungs-/Label-Widgets wurden hinzugefügt.
- **Goldene Datei hier bewusst regeneriert.** `tests/ui_inventory_golden.json` wurde mit `REGEN_INVENTORY=1` in diesem Slice neu erzeugt. Der **einzige** Diff ist die **Widget-Anzahl pro Seite** (die hinzugefügten Mode-Unterüberschrifts-Labels; +113 Widgets über die fünf flow-lastigen Seiten). `gated_count`, `gated_unique_triples`, `gated_triples_sha256`, `core_flows`, `action_meta` und jede Seite's `buttons`/`acts`/`btn_sha` sind byte-identisch — die Gate-Registry und die Klick-Oberfläche haben sich nicht bewegt.
- **Slice B2 — Device-Model-Board (vertikale Action-Karten) (dieser Slice).** Die Per-Action-Zeilen der Modellseite sind jetzt `ActionRow`-Karten (`python/gui/widgets/action_row.py`) statt des 50px handgefertigten `QFrame` mit monkeygepatchtem `mousePressEvent`:
  - eine **3px semantische Linkskante** (`err` für wipe/destruktive Aktionen, sonst `accent_hi`) — dieselbe risiko-Kantensprache, die `MethodCard.set_risk` im Flow-Browser malt,
  - ein **40x40 Icon-Tile**, ein **13px/800**-Titel und eine **einzeilige, ellipsierte** Beschreibung. Das behebt das Problem der Planung „lange Flow-Labels laufen über/um unvorhersehbar“: die Beschreibung ellipsiert statt zu umbrechen, sodass ein langes Label das Board nie breiter machen kann als seine Leiste noch als ragged Mehrzeilen-Block lesen lässt,
  - optionaler Engine/Mode-**Chip** und ein gedimmter **`›`-Chevron**; Hover/Pressed/Focus gehören dem Widget (QSS dynamische Property + Fokus-Ring). Der Chip wird als **Single-Hue-Pille** aus der Akzentfarbe gemalt, die `common._mode_chip` bereits zurückgibt (Akzent-Tint-Füllung, Akzent-Text, Akzent-Haarlinien-Rahmen), sodass jedes Badge als eine Familie liest,
  - **tastatur-erreichbar** — `StrongFocus` + Enter/Return/Space emittieren das `activated`-Signal (ersetzen das monkeygepatchte `mousePressEvent`). Das Board behält seine `flow_act`/`flow_tip`-Tags und verbindet nur `activated`, sodass das Routing unverändert ist,
  - Gruppen-Container tragen jetzt die Action-**Zählung** des Jobs (`FRP REMOVE · 4`) — dieselbe Name + Zähl-Sprache wie die Job-Header des Flow-Browsers.
- **Invarianten gehalten.** `_ACTION_META` sind immer noch **62** Einträge; jedes `dev_*`-Seite's `acts` und `btn_sha` sind byte-identisch (keine Aktions-Zeile, kein Button-Text und kein Button wurde hinzugefügt/entfernt/umbenannt); `gated_count` **418**, `gated_triples_sha256` `c89acce…7d75`, `gated_unique_triples` **61**, `core_flows` **116**, `stack_count` **25**. Die natürliche Mindestbreite des Seiten-Stacks ist immer noch **699px**, was beweist, dass die ellipsierten Labels nichts verbreitert haben.
- **Goldene Datei hier bewusst regeneriert.** `tests/ui_inventory_golden.json` wurde mit `REGEN_INVENTORY=1` in diesem Slice neu erzeugt: der einzige Diff ist die **Widget-Anzahl pro Seite** (`dev_apple` 59→63, `dev_motorola` 85→99 — die zwei recherchierten Boards' hinzugefügte Karten/Labels). Der transiente goldene md5 nach B2 war `929f428638e91a42865ddde1ac96dd19`. Die nachfolgende Politur dieses Dokument-Slices (die Single-Hue-Chip-Familie und der First-Show-Gerätepanel-Split) änderte **keine** Seiten-Widget-Anzahl, daher brauchte das Goldene **keine** weitere Regenerierung.
- **Slice B4 — das Model-Board füllt die Seitenhöhe (dieser Slice).** Auf der Gerät → Modell-Board-Seite (`devices.build_brand_page`) bekam die zweiteilige Split-Zeile nicht die Höhe der Seite, sodass unter beiden Paneelen ein breites leeres Band blieb. Bei einem 1600x951-Fenster (äußerer Seiten-Viewport `878x717`) maßen die Panele `left 250x313 / right 598x333` mit einem **333px-Dead-Band** darunter, und das Action-Board bekam nur `333` von `717px`. Grundursache: die Split-Zeile wurde `outer` mit Stretch 1 hinzugefügt *und* direkt danach ein abschließendes `outer.addStretch(1)` — die beiden gestreckten Items teilten den übrig gebliebenen vertikalen Platz ~50/50, und kein Panel war vertikal `Expanding`, sodass nichts ihn absorbierte. Fix (chirurgisch, nur in `build_brand_page`): den konkurrierenden abschließenden Stretch entfernen (die Split-Zeile nimmt jetzt **die ganze** übrige Höhe), und dem linken `list_col` sowie dem rechten `right_stack` eine explizite vertikale `Expanding`-Policy geben, sodass das interne `lscroll` und die aktuelle Modellseite's interner `_scroll` die volle Höhe erhalten und eigene Scrollbars besitzen. Die linken Zeilen bleiben oben ausgerichtet (`lv2.addStretch(1)` unangetastet) und scrollen, wenn die Liste wächst. Nachher: `left 250x646 / right 598x665`, Dead-Band **1px** (nur der 8px-Unterrand des Layouts), das rechte Board zeigt deutlich mehr Flows und scrollt den Rest intern (`vscroll_max` 900 → 557), und das äußere `_page_scroll` der Shell bleibt versteckt (`verticalScrollBar().maximum() == 0`). Zur Untermauerung der künftigen Anforderung des Nutzers: 40 extra In-Memory-Modelle vergrößern den Scroll-Bereich der **linken** Liste (`vscroll_max > 0`) **ohne** Änderung der Höhe eines der beiden Panele.
  - Neue Tests: `tests/test_device_board_layout.py` — `TestBrandPageFillsHeight::test_no_dead_band_below_split`, `::test_both_panes_get_the_real_height`, `::test_right_board_scrolls_its_own_content`, `::test_more_devices_scroll_left_without_growing_the_panes`. Beide Geometrie-Tests wurden bestätigt, dass sie **auf dem unfixierten Code zuerst fehlschlagen** (Dead-Band 295px bei H=640; linkes Panel 275px vs. dem 412px-Floor), bevor der Fix kam.
  - **Kein Widget wurde hinzugefügt oder entfernt** (nur eine Size-Policy geändert und ein Stretch-Spacer entfernt), daher bewegte sich die Widget-Anzahl keiner Seite und `tests/ui_inventory_golden.json` brauchte **keine** Regenerierung — immer noch `929f428638e91a42865ddde1ac96dd19`.
- **Slice C — volle Flow-Registry auf dem Geräte-Board (ZURÜCKGENOMMEN).**  Dieser Slice fügte eine abschließende `MORE FLOWS · N`-Gruppe hinzu, die die komplette Flow-Registry des Geräte-Engines als `ActionRow`-Karten renderte, plus eine Text/Mode-Filter-Leiste. Sie war nach **Engine + Transport-Mode** scoped, was nicht dasselbe ist wie die *Funktionen dieses Geräts*: jedes Telefon, das ADB exponiert, zog damit sämtliche ADB-registrierten Flows der Registry an, sodass das Motorola-Board rein Samsung-Jobs anbot (`knox_bypass`, `kg_remove`, `odin_flash_tar`), `imei_repair_spd`, `apple_icloud_*` und `huawei_frp_guide`. Schlimmer noch, die Motorola-Modelle tragen **Per-Modell-Engines** (`Moto G13` = `spd`, `G24` = `mtk`, `G6` = `qcom`), sodass `planned`-Modelle eine ganze SPD/MTK-Registry für Arbeit anzeigten, die noch nicht gemacht wurde, und die Motorola/Apple-Marken umgehen die `researched`-Gates auf dem Board by design. Vollständig zurückgenommen: die Registry-Gruppe, ihre Filter-Leiste, `_ENGINE_MODES`, die First-Show-Deferral und `tests/test_device_flows.py` sind weg; das Board ist wieder genau die kuratierten per-Gerät-Aktionen. Das Inventar-Goldene war die gesamte Zeit byte-identisch (`929f428638e91a42865ddde1ac96dd19`), weil die Gruppe lazy gebaut wurde, daher braucht der Revert keine Regenerierung.
  - Lektion für jeden Wiederholungsversuch: nach den **eigenen deklarierten `actions` des Modells** scopieren (`supported_devices.json`), nur die Flows expandierend, zu denen diese Aktionen wirklich dispatchen — niemals nach Engine + Mode.
  - Vettierte Tatsache, die überlebt und wiederverwendbar ist: `win._route_flow_activation(job, mode, key, label)` ist der einzige Sink, der die destruktive Bestätigung und die EXPERIMENTAL-Inhaber-Ack anwendet; `_dispatch`/`start_model_action` tut das nicht (dessen Experimental-Check ist das enge `devices._EXPERIMENTAL_ACTS`-Set, sodass z. B. `emmc_raw` unacknowledged liefe).
- **Noch aufgeschoben:** Suchbox / Mode-Filter-Chips über eine Per-Gerät-Flow-Liste, Favoriten/Zuletztverwendete (settings-persistiert), die Batch-Auswahl-Queue (Checkboxen + sequentieller Lauf), Drag-to-Reorder, die dreiteilige Job → Mode → Method-Navigation, das Expandieren von Mode-Varianten eines Jobs in extra Karten (eine Karte pro `(job, mode, key)` ist eine bewusste spätere Entscheidung — dieser Slice expandiert **keine** Modes) und ein wiederverwendbarer `ConfirmDialog` (die Confirm/Experimental-Overlays bleiben fenstereigene Modale).

## Phase 8 — Professioneller Feinschliff & Differenzierung (neu)
### Visuelle Identität
- Signatur-„Atelier“-Dunkeltheme mit subtiler Körnung/Rauschtextur und sanftem Vignette.
- Markenzeichen + Monogramm; konsistente Ikonografie (Lucide-Stil) über alle Aktionen.
- Device-Hero-Karten: Modellbild-Silhouette, Chip, Transport-Badges, zuletzt gesehen.
- Animierte Verbindungsszene aufgewertet: echter Kabel-Puls, Per-Gerät-Statuspunkte.

### Informationsdichte
- Einklappbares Inspektor-Panel: Details des ausgewählten Geräts, Partitionen, PIT-Zusammenfassung, Logs.
- Zeitachsenansicht der Operationen (Start/Ende, Dauer, Ergebnis) pro Gerät.
- Diff-Ansicht für PIT/Partition-Änderungen vor dem Flash.

### Sicherheit & Vertrauen
- Pre-Flight-Checklisten-Karte vor destruktiven Ops (Gerät, Firmware, PIT-Match).
- Klare Risiko-Leiter mit Farbe + Icon + Text; nie nur Farbe.
- Audit-Log-Viewer (experimentelle Aktionen) mit Export.

### Produktivität
- Command Palette (Ctrl+K) zum Suchen von Flows, Geräten, Einstellungen.
- Globalsuche über Logs und Geräte.
- Keyboard-first-Navigation; Shortcuts-Overlay (?).
- Sitzungswiederherstellung: letztes Gerät + Seite wieder öffnen.

### Linux-natives Gefühl
- Native Dateidialoge, System-Theme-Bewusstsein, Wayland/X11-Behandlung.
- Desktop-Benachrichtigungen für lange Ops; Tray-Icon mit Fortschritt.
- Drag-and-Drop von Firmware-Dateien auf die Flash-Seite.

### Onboarding
- First-Run-Wizard: udev-Setup, Bridge-Build-Status, Gerätetest.
- Leere Zustände mit Illustrationen und nächsten Schritten.
- Kontextueller Hilfe-Drawer mit per-Flow-Docs aus `operations/`.

### Branding-Assets
- Neues Logo-Set, Splash, Installer-Grafiken, App-Icon.
- README-Screenshots aktualisiert, um zur neuen UI zu passen.

## Phase 9 — Konsole-/Terminal-Redesign (neu)
### Ziel
Das Log-Konsole soll sich wie ein First-Class-Linux-Terminal (UEFI-Shell/TTY-Ästhetik) anfühlen statt wie eine beengte Textbox.

### Layout
- Dediziertes **rechtes** Dock in einem horizontalen Splitter (Seiten links, Konsole rechts); größenveränderbar, einklappbar zu einem dünnen Streifen. Standardbreite 420px, Minimum 360px (gemessen von der eigenen Steuerzeile des Docks, sodass nichts abgeschnitten werden kann). _Entscheidung (Nutzer): die Konsole bleibt rechts — ein früherer Entwurf dieser Phase sagte „unteres Dock / 35% Höhe“; der ist hiermit überholt._
- Breites, monospaced Terminal mit komfortablem Padding (16px), Zeilenhöhe 1.45.
- Optionaler Vollbild-Terminal-Modus (F11) mit minimalem Chrome.
- Per-Gerät-Tabs oder Filter-Chips, damit Logs nicht ineinanderlaufen.

### Styling
- Dunkle TTY-Palette: schwarzer Hintergrund, grüner/bernsteinfarbener/cyanfarbener Text, optionale subtile Scanline.
- ANSI-Farbein für Bridge-Ausgabe; fettgedruckte Header, gedimmte Zeitstempel.
- Zeilennummern / Zeitstempel umschaltbar.
- Auswahl + Kopieren; Rechtsklick-Menü (kopieren, speichern, leeren, filtern).

### Verhalten
- Streaming mit Backpressure; kein UI-Freeze bei 10k+ Zeilen.
- Suche mit Regex, Treffer hervorheben, nächstes/vorheriges springen.
- Export in Datei; automatisches Speichern des Sitzungslogs.
- Geräte-Filter und Level-Filter (info/warn/error/step).

### Nicht gequetscht
- Minimale Breiten-/Höhen-Constraints; responsive Umbruch; horizontaler Scroll für lange Zeilen.
- Größenveränderbare Spalten für Zeitstempel/Level/Gerät.

## Phase 10 — Konsolenmeldungen & Toast-System (neu)
### Konsolenmeldungen
- Strukturierte Log-Einträge: Zeitstempel, Geräteschlüssel, Level, Nachricht.
- Farbcodierte Level: info (schiefergrau), success (grün), warn (bernstein), error (rot), step (cyan).
- Einklappbare Mehrzeilen-Ausgabe (Stacktraces, JSON) mit „show more“.
- Inline-Fortschrittsbalken für Flash-Schritte; Per-Schritt-Status-Icons.
- Klickbare Geräteschlüssel zum Fokussieren des Geräts; klickbare Flow-Schlüssel zum Öffnen der Docs.

### Toasts
- Nicht-blockierende, gestapelte Toasts mit Icon, Titel, Nachricht, Aktionsbutton.
- Auto-Ausblenden mit Fortschrittsbalken; Pause bei Hover.
- Schweregrad-Stile (info/success/warn/error) mit konsistenter Palette.
- Queue-Cap (max. 3 sichtbar) mit Überlauf-Zähler.
- Positions-Optionen (oben-rechts/unten-rechts) und Reduced-Motion-Unterstützung.
- Optionaler Sound/Haptic für Fehler.

## Phase 12 — HiProTool-Paritäts-Recherche (neu)
### Status
- Onlinesuche in dieser Umgebung nicht verfügbar (HTTP 402). Manuelle Recherche erforderlich.

### Recherche-Aufgaben
- HiProTool-Feature-Liste sammeln (FRP, MDM, Bildschirmsperre, Carrier, IMEI, Flashing).
- Jede Methode einem Engine zuordnen (ADB, Download-Modus, BROM, EDL, Fastboot, SPD).
- Gerätespezifische Shortcuts und Voraussetzungen identifizieren.
- In `operations/` dokumentieren mit Verifikations-Schritten und Sicherheitshinweisen.
- Zuerst High-Value-, Low-Risk-Methoden priorisieren.

## Phase 14 — Nächste Features (neu)
### Ziel-Features
- IMEI-Blacklist-Entfernung (Recherche + gerätespezifische Playbooks).
- Carrier-Unlock-Verbesserungen (SIM-Lock, NVDATA/QCN-Pfade).
- MDM-Unlock-Verbesserungen (Device Owner, QR-Provisioning, Recovery).
- FRP-Verbesserungen (pro Chip/pro Android-Version Methoden).
- Verbesserungen beim Entfernen von Bildschirmsperren (ADB, Recovery, Download, EDL).
- Samsung Knox Guard Removal (EXPERIMENTAL, audit-protokolliert).
- Apple MDM Enrollment Removal (Profile/DEP).
- Samsung Knox Management Tools.
- Android Enterprise Enrollment Handling.
- Zero-Touch Enrollment Handling.
- Apple Activation Lock Removal (checkm8/DFU-Scope, ehrliche Grenzen).
- SIM-PUK-Abruf zum Entsperren von SIM-PIN.
- Biometric-Lock-Entfernung (Recherche, Gerätegrenzen).

### Hinweise
- Jedes Feature muss Rust-gestützt und, wo riskant, als EXPERIMENTAL gegatet sein.
- In `operations/` mit Verifikation und Sicherheitshinweisen dokumentieren.

## Phase 15 — Dokumentations-Audit & Aufräumen (neu)
### Veraltete Referenzen gefunden (historisch/retired)
- `operations/*/README.md` erwähnen retired Python-Module (`knox.py`, `qcn.py`, `health.py`, `apple.py`, `flows/*.py`) als Kontext; akzeptabel, aber klar als historisch markieren.
- `INDEX.md` referenzierte zuvor fehlendes `SPLIT_PLAN.md` (behoben).
- `README.md` Repository-Layout listete zuvor nichtexistierende Module (behoben).
- `DESCRIPTION.md` hatte falsche Transport-/Job-Zählungen (behoben).

### Verbleibende Doc-Aufgaben
- Alle „retired“-Notizen in einen einzigen „History“-Abschnitt pro Datei normalisieren.
- Eine „Current architecture“-Notiz oben in jedem operations-README hinzufügen.
- Obsolete Migrationspläne entfernen oder archivieren (DESIGN.md → neue Version).
- `operations/` als research-only beibehalten; Code-Pointer müssen `src/flows.rs` sagen.