# Design-System — FlashPilot

Language switcher: [English](../../design.md) · [Français](../fr/design.md) · [Español](../es/design.md) · **Deutsch** · [简体中文](../zh/design.md) · [Русский](../ru/design.md) · [Português](../pt/design.md) · [日本語](../ja/design.md) · [العربية](../ar/design.md) · [हिन्दी](../hi/design.md) · [Türkçe](../tr/design.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## Prinzipien
- Einzelnes dunkles Theme (keine helle Variante) für Konsistenz und Fokus.
- Der Akzent ist konfigurierbar; semantische Farben werden nie Akzent-getönt.
- Alle UI-Tokens leben in `python/gui/theme.py` (`C`, `ACCENT_THEMES`).

## Tokens
- Farben: `bg`, `panel`, `card`, `card_hover`, `inset`, `border`, `border_hi`, `text`, `text_hi`, `dim`, `mute`, `accent`, `accent_hi`, `ok`, `warn`, `err`.
- Semantische UI-Tokens: `focus_ring`, `sel_border`, `sel_border_hi` (nie Akzent-getönt).
- Abstands-Skala: 4, 8, 12, 16, 24.
- Radius-Skala: 8, 10, 12, 14, 16.
- Typografie: Inter/Segoe UI/Roboto; Monospace JetBrains Mono/Consolas für die Konsole.

## Komponenten
- Karten: `QFrame#card` mit Glas-Gradient, subtiler Rahmenlinie, Akzent-Linkskante.
- Buttons: primär (Akzent-Gradient), Ghost (dezent), Danger (rot).
- Eingaben: gerundet 10px, Fokus-Ring in Akzentfarbe.
- Konsole: Monospace, eingelassener Hintergrund, 12px.
- Toasts: gestapelt, nach Schweregrad farbcodiert, automatisches Ausblenden.

## Bewegung
- Seiten-Fade 120–160ms; Button-Druck; Toast-Gleiten.
- Respektiere die Bewegungsreduzierung (Reduced Motion).

## Regeln
- Keine hardcodierten Farben in Widgets; verwende `C`.
- Keine neuen Farben ohne Hinzufügen zu den Theme-Tokens.
- Alle destruktiven Aktionen erfordern einen Bestätigungsdialog.
- Experimentelle Features verwenden einen bernsteinfarbenen gestrichelten Rahmen + Ack-Gate.