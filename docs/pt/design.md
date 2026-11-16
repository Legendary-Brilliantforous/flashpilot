# Sistema de design — FlashPilot

Language switcher: [English](../../design.md) · [Français](../fr/design.md) · [Español](../es/design.md) · [Deutsch](../de/design.md) · [简体中文](../zh/design.md) · [Русский](../ru/design.md) · **Português** · [日本語](../ja/design.md) · [العربية](../ar/design.md) · [हिन्दी](../hi/design.md) · [Türkçe](../tr/design.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## Princípios
- Tema escuro único (sem variante clara) para consistência e foco.
- O acento é configurável; cores semânticas nunca são tingidas pelo acento.
- Todos os tokens de UI vivem em `python/gui/theme.py` (`C`, `ACCENT_THEMES`).

## Tokens
- Cores: `bg`, `panel`, `card`, `card_hover`, `inset`, `border`, `border_hi`, `text`, `text_hi`, `dim`, `mute`, `accent`, `accent_hi`, `ok`, `warn`, `err`.
- Tokens de UI semânticos: `focus_ring`, `sel_border`, `sel_border_hi` (nunca tingidos pelo acento).
- Escala de espaçamento: 4, 8, 12, 16, 24.
- Escala de raio: 8, 10, 12, 14, 16.
- Tipografia: Inter/Segoe UI/Roboto; monoespaçada JetBrains Mono/Consolas para o console.

## Componentes
- Cartões: `QFrame#card` com gradiente de vidro, borda sutil, borda esquerda de acento.
- Botões: primário (gradiente de acento), ghost (sutil), danger (vermelho).
- Entradas: arredondadas 10px, anel de foco com acento.
- Console: monoespaçado, fundo encaixado, 12px.
- Toasts: empilhados, coloridos por severidade, dispensa automática.

## Movimento
- Fade de página 120–160ms; pressão de botão; deslize de toast.
- Respeitar a configuração de movimento reduzido.

## Regras
- Nenhuma cor codificada em widgets; usar `C`.
- Nenhuma cor nova sem adicionar aos tokens de tema.
- Todas as ações destrutivas exigem diálogo de confirmação.
- Recursos experimentais usam borda tracejada âmbar + gate de aceite.
