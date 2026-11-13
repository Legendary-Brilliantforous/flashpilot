# نظام التصميم — FlashPilot

Language switcher: [English](../../design.md) · [Français](../fr/design.md) · [Español](../es/design.md) · [Deutsch](../de/design.md) · [简体中文](../zh/design.md) · [Русский](../ru/design.md) · [Português](../pt/design.md) · [日本語](../ja/design.md) · **العربية** · [हिन्दी](../hi/design.md) · [Türkçe](../tr/design.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## المبادئ
- سمة داكنة واحدة (لا متغير فاتح) من أجل الاتساق والتركيز.
- التمييز (accent) قابل للتهيئة؛ ألوان الدلالات (semantic) لا تُصبغ أبداً بالتمييز.
- كل رموز UI تعيش في `python/gui/theme.py` (الكائنات `C` و `ACCENT_THEMES`).

## الرموز (tokens)
- الألوان: `bg`، `panel`، `card`، `card_hover`، `inset`، `border`، `border_hi`، `text`، `text_hi`، `dim`، `mute`، `accent`، `accent_hi`، `ok`، `warn`، `err`.
- رموز UI دلالية: `focus_ring`، `sel_border`، `sel_border_hi` (لا تُصبغ أبداً بالتمييز).
- سلم التباعد (spacing): 4، 8، 12، 16، 24.
- سلم نصف القطر (radius): 8، 10، 12، 14، 16.
- الطباعة: Inter/Segoe UI/Roboto؛ monospace JetBrains Mono/Consolas لوحدة التحكم (console).

## المكونات
- البطاقات (cards): `QFrame#card` مع تدرّج زجاجي، حد subtيل، وحافة يسرى مميّزة (accent).
- الأزرار: أساسي (تدرّج التمييز)، شبح (subtle)، خطر (أحمر).
- الحقول (inputs): مستديرة 10px، حلقة focus بالتمييز.
- Console: monospace، خلفية inset، 12px.
- Toasts: مكدّسة، ملوّنة حسب الشدة (severity)، اختفاء تلقائي.

## الحركة (motion)
- تلاشي الصفحة (page fade) 120–160ms؛ ضغط الزر؛ انزلاق toast.
- احترام إعداد تقليل الحركة (reduced-motion).

## القواعد
- لا ألوان مُشفّرة (hardcoded) في widgets؛ استخدم `C`.
- لا لون جديد من دون إضافته إلى رموز الثيم.
- كل إجراء مدمّر يحتاج إلى صندوق حوار تأكيد.
- المزايا التجريبية (experimental) تستخدم حدًا متقطّعًا برتقاليًا + بوابة إقرار (ack gate).