# डिज़ाइन सिस्टम — FlashPilot

Language switcher: [English](../../design.md) · [Français](../fr/design.md) · [Español](../es/design.md) · [Deutsch](../de/design.md) · [简体中文](../zh/design.md) · [Русский](../ru/design.md) · [Português](../pt/design.md) · [日本語](../ja/design.md) · [العربية](../ar/design.md) · **हिन्दी** · [Türkçe](../tr/design.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## सिद्धांत (Principles)
- एक ही डार्क थीम (कोई लाइट वेरिएंट नहीं) — एकरूपता और फोकस के लिए।
- एक्सेंट (accent) बदला जा सकता है; सिमैंटिक रंग कभी एक्सेंट-टिंटेड नहीं होते।
- सभी UI टोकन `python/gui/theme.py` में रहते हैं (`C`, `ACCENT_THEMES`)।

## टोकन (Tokens)
- रंग: `bg`, `panel`, `card`, `card_hover`, `inset`, `border`, `border_hi`, `text`, `text_hi`, `dim`, `mute`, `accent`, `accent_hi`, `ok`, `warn`, `err`।
- सिमैंटिक UI टोकन: `focus_ring`, `sel_border`, `sel_border_hi` (कभी एक्सेंट-टिंटेड नहीं)।
- स्पेसिंग स्केल: 4, 8, 12, 16, 24।
- रेडियस स्केल: 8, 10, 12, 14, 16।
- टाइपोग्राफी: Inter/Segoe UI/Roboto; कंसोल के लिए monospace JetBrains Mono/Consolas।

## कम्पोनेंट (Components)
- कार्ड: glass ग्रेडिएंट, हल्का border, एक्सेंट बाएँ edge के साथ `QFrame#card`।
- बटन: primary (एक्सेंट ग्रेडिएंट), ghost (subtle), danger (लाल)।
- इनपुट: rounded 10px, फोकस ring एक्सेंट।
- कंसोल: monospace, inset बैकग्राउंड, 12px।
- टोस्ट: stacked, severity-colored, auto-dismiss।

## मोशन (Motion)
- पेज फ़ेड 120–160ms; बटन प्रेस; टोस्ट स्लाइड।
- reduced-motion सेटिंग का सम्मान करें।

## नियम (Rules)
- विजेट्स में कोई hardcoded रंग नहीं; `C` इस्तेमाल करें।
- थीम टोकन में जोड़े बिना कोई नया रंग नहीं।
- सभी destructive actions के लिए confirmation डायलॉग ज़रूरी है।
- प्रयोगात्मक (experimental) फ़ीचर एम्बर dashed border + ack gate इस्तेमाल करते हैं।
