Language switcher: [English](../../SECURITY.md) · [Français](../../fr/SECURITY.md) · [Español](../../es/SECURITY.md) · **Deutsch** · [简体中文](../../zh/SECURITY.md) · [Русский](../../ru/SECURITY.md) · [Português](../../pt/SECURITY.md) · [日本語](../../ja/SECURITY.md) · [العربية](../../ar/SECURITY.md) · [हिन्दी](../../hi/SECURITY.md) · [Türkçe](../../tr/SECURITY.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

# Sicherheitsrichtlinie

## Unterstützte Versionen

Das Projekt ist pre-1.0. Sicherheitskorrekturen landen auf dem `main`-Branch
und, falls vorhanden, der neuesten getaggten Release.

## Melden einer Schwachstelle

Bitte **eröffne kein** öffentliches Issue für Sicherheitsprobleme. Melde sie
privat:

- E-Mail: **flashpilot@proton.me** (erstelle diese Adresse bei proton.me →
  kostenloses Konto), oder
- GitHubs privates Vulnerability-Reporting-Formular in diesem Repository.

Bitte gib an:
- Betroffener Befehl / Flow und Version,
- Schritte zur Reproduktion,
- Auswirkung (z. B. beliebige Codeausführung, Brick-Risiko, Datenverlust,
  Offenlegung von Zugangsdaten).

Wir bemühen uns, Berichte innerhalb von 72 Stunden zu bestätigen und koordinieren
die Veröffentlichung.

## Umfang und Erwartungen

Dieses Werkzeug führt absichtlich Low-Level-USB-/Bootloader-Operationen durch.
Seiner Natur nach kann es ein Gerät löschen oder bricken. Das ist dokumentiertes
Verhalten, keine Schwachstelle. Uns interessiert:

- Exploits, die unvertrauenswürdigen Code über die vorgesehene Operation hinaus
  ausführen,
- Umgehung von Sicherheitsbestätigungen / Geräteprüfungen zum Schaden der
  Benutzer,
- Auslieferung proprietärer Blobs oder Geheimnisse im Repository,
- Alles, was Gerätedaten oder Zugangsdaten des Benutzers preisgibt.

Bitte arbeite nur an Geräten, die dir gehören oder deren Reparatur du
autorisiert bist.
