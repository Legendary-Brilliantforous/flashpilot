# Система дизайна — FlashPilot

Language switcher: [English](../../design.md) · [Français](../fr/design.md) · [Español](../es/design.md) · [Deutsch](../de/design.md) · [简体中文](../zh/design.md) · **Русский** · [Português](../pt/design.md) · [日本語](../ja/design.md) · [العربية](../ar/design.md) · [हिन्दी](../hi/design.md) · [Türkçe](../tr/design.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## Принципы
- Единая тёмная тема (без светлого варианта) для единообразия и фокуса.
- Акцент настраивается; семантические цвета никогда не тонируются акцентом.
- Все UI-токены живут в `python/gui/theme.py` (`C`, `ACCENT_THEMES`).

## Токены
- Цвета: `bg`, `panel`, `card`, `card_hover`, `inset`, `border`, `border_hi`, `text`, `text_hi`, `dim`, `mute`, `accent`, `accent_hi`, `ok`, `warn`, `err`.
- Семантические UI-токены: `focus_ring`, `sel_border`, `sel_border_hi` (никогда не тонируются акцентом).
- Шкала отступов: 4, 8, 12, 16, 24.
- Шкала радиусов: 8, 10, 12, 14, 16.
- Типографика: Inter/Segoe UI/Roboto; моноширинная JetBrains Mono/Consolas для консоли.

## Компоненты
- Карточки: `QFrame#card` со стеклянным градиентом, тонкой границей, акцентной левой кромкой.
- Кнопки: primary (акцентный градиент), ghost (приглушённая), danger (красная).
- Ввод: округление 10px, focus ring акцентом.
- Консоль: моноширинная, вложенный фон, 12px.
- Toast'ы: стопкой, раскрашенные по severity, автоматически исчезающие.

## Motion
- Появление страницы 120–160мс; нажатие кнопки; выезд toast.
- Учитывать настройку reduced-motion.

## Правила
- Никаких жёстко заданных цветов в виджетах; использовать `C`.
- Никаких новых цветов без добавления в токены темы.
- Все деструктивные действия требуют диалог подтверждения.
- Экспериментальные возможности: янтарная пунктирная граница + ack gate.