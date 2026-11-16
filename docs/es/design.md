# Sistema de diseño — FlashPilot

Language switcher: [English](../../design.md) · [Français](../fr/design.md) · **Español** · [Deutsch](../de/design.md) · [简体中文](../zh/design.md) · [Русский](../ru/design.md) · [Português](../pt/design.md) · [日本語](../ja/design.md) · [العربية](../ar/design.md) · [हिन्दी](../hi/design.md) · [Türkçe](../tr/design.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## Principios
- Tema oscuro único (sin variante clara) para consistencia y enfoque.
- El acento es configurable; los colores semánticos nunca se tiñen con el acento.
- Todos los tokens de UI viven en `python/gui/theme.py` (`C`, `ACCENT_THEMES`).

## Tokens
- Colores: `bg`, `panel`, `card`, `card_hover`, `inset`, `border`, `border_hi`, `text`, `text_hi`, `dim`, `mute`, `accent`, `accent_hi`, `ok`, `warn`, `err`.
- Tokens de UI semánticos: `focus_ring`, `sel_border`, `sel_border_hi` (nunca teñidos con el acento).
- Escala de espaciado: 4, 8, 12, 16, 24.
- Escala de radio: 8, 10, 12, 14, 16.
- Tipografía: Inter/Segoe UI/Roboto; monoespaciada JetBrains Mono/Consolas para la consola.

## Componentes
- Tarjetas: `QFrame#card` con gradiente de cristal, borde sutil, borde izquierdo de acento.
- Botones: primario (gradiente de acento), fantasma (sutil), peligro (rojo).
- Entradas: redondeadas 10px, anillo de foco con acento.
- Consola: monoespaciada, fondo encajado, 12px.
- Notificaciones: apiladas, coloreadas por severidad, auto-descarte.

## Movimiento
- Fundido de página 120–160ms; pulsación de botón; deslizamiento de notificación.
- Respetar la configuración de movimiento reducido.

## Reglas
- Sin colores codificados en widgets; usar `C`.
- Sin colores nuevos sin añadirlos a los tokens del tema.
- Todas las acciones destructivas requieren diálogo de confirmación.
- Las funciones experimentales usan borde discontinuo ámbar + puerta de acuse (ack gate).