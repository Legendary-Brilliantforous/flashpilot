# Système de design — FlashPilot

Language switcher: [English](../../design.md) · **Français** · [Español](../es/design.md) · [Deutsch](../de/design.md) · [简体中文](../zh/design.md) · [Русский](../ru/design.md) · [Português](../pt/design.md) · [日本語](../ja/design.md) · [العربية](../ar/design.md) · [हिन्दी](../hi/design.md) · [Türkçe](../tr/design.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## Principes
- Thème sombre unique (aucune variante claire) pour la cohérence et la concentration.
- L'accent est configurable ; les couleurs sémantiques ne sont jamais teintées à l'accent.
- Tous les jetons UI vivent dans `python/gui/theme.py` (`C`, `ACCENT_THEMES`).

## Jetons
- Couleurs : `bg`, `panel`, `card`, `card_hover`, `inset`, `border`, `border_hi`, `text`, `text_hi`, `dim`, `mute`, `accent`, `accent_hi`, `ok`, `warn`, `err`.
- Jetons UI sémantiques : `focus_ring`, `sel_border`, `sel_border_hi` (jamais teintés à l'accent).
- Échelle d'espacement : 4, 8, 12, 16, 24.
- Échelle de rayon : 8, 10, 12, 14, 16.
- Typographie : Inter/Segoe UI/Roboto ; monospace JetBrains Mono/Consolas pour la console.

## Composants
- Cartes : `QFrame#card` avec dégradé verre, bordure subtile, bord gauche accent.
- Boutons : primaire (dégradé accent), fantôme (subtil), danger (rouge).
- Champs de saisie : arrondis 10px, anneau de focus accent.
- Console : monospace, fond encastré, 12px.
- Toasts : empilés, colorés par sévérité, disparition automatique.

## Motion
- Fondu de page 120–160 ms ; pression de bouton ; glissement de toast.
- Respecter le réglage de mouvement réduit.

## Règles
- Aucune couleur codée en dur dans les widgets ; utiliser `C`.
- Aucune nouvelle couleur sans ajout aux jetons de thème.
- Toutes les actions destructives nécessitent une boîte de dialogue de confirmation.
- Les fonctionnalités expérimentales utilisent une bordure pointillée ambre + portillon d'acquittement.