# Design System — FlashPilot

## Principles
- Single dark theme (no light variant) for consistency and focus.
- Accent is configurable; semantic colors are never accent-tinted.
- All UI tokens live in `python/gui/theme.py` (`C`, `ACCENT_THEMES`).

## Tokens
- Colors: `bg`, `panel`, `card`, `card_hover`, `inset`, `border`, `border_hi`, `text`, `text_hi`, `dim`, `mute`, `accent`, `accent_hi`, `ok`, `warn`, `err`.
- Semantic UI tokens: `focus_ring`, `sel_border`, `sel_border_hi` (never accent-tinted).
- Spacing scale: 4, 8, 12, 16, 24.
- Radius scale: 8, 10, 12, 14, 16.
- Typography: Inter/Segoe UI/Roboto; monospace JetBrains Mono/Consolas for console.

## Components
- Cards: `QFrame#card` with glass gradient, subtle border, accent left edge.
- Buttons: primary (accent gradient), ghost (subtle), danger (red).
- Inputs: rounded 10px, focus ring accent.
- Console: monospace, inset background, 12px.
- Toasts: stacked, severity-colored, auto-dismiss.

## Motion
- Page fade 120–160ms; button press; toast slide.
- Respect reduced-motion setting.

## Rules
- No hardcoded colors in widgets; use `C`.
- No new colors without adding to theme tokens.
- All destructive actions require confirmation dialog.
- Experimental features use amber dashed border + ack gate.
