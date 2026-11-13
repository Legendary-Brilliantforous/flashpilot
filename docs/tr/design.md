# Tasarım sistemi — FlashPilot

Language switcher: [English](../../design.md) · [Français](../fr/design.md) · [Español](../es/design.md) · [Deutsch](../de/design.md) · [简体中文](../zh/design.md) · [Русский](../ru/design.md) · [Português](../pt/design.md) · [日本語](../ja/design.md) · [العربية](../ar/design.md) · [हिन्दी](../hi/design.md) · **Türkçe**

> English kanonik kaynaktır. Bu sayfa bir çeviridir; katkı memnuniyetle karşılanır — bkz. [`../TRANSLATION.md`](../TRANSLATION.md).

## İlkeler
- Tutarlılık ve odak için tek bir dark tema (açık varyant yok).
- Aksan rengi yapılandırılabilir; semantik renkler hiçbir zaman aksan tonu almaz.
- Tüm UI token'ları `python/gui/theme.py` içinde (`C`, `ACCENT_THEMES`).

## Token'lar
- Renkler: `bg`, `panel`, `card`, `card_hover`, `inset`, `border`, `border_hi`, `text`, `text_hi`, `dim`, `mute`, `accent`, `accent_hi`, `ok`, `warn`, `err`.
- Semantik UI token'ları: `focus_ring`, `sel_border`, `sel_border_hi` (asla aksan tonlu değil).
- Boşluk ölçeği: 4, 8, 12, 16, 24.
- Yarıçap ölçeği: 8, 10, 12, 14, 16.
- Tipografi: Inter/Segoe UI/Roboto; konsol için tek aralıklı JetBrains Mono/Consolas.

## Bileşenler
- Kartlar: `QFrame#card`, cam gradyanı, ince kenarlık, solda aksan kenarı.
- Düğmeler: birincil (aksan gradyanı), ghost (ince), danger (kırmızı).
- Girdiler: yuvarlak 10px, aksan odak halkası.
- Konsol: tek aralıklı, içe gömülü arka plan, 12px.
- Toast'lar: yığınlı, önem derecesine göre renklendirilmiş, otomatik kapanır.

## Hareket
- Sayfa solması 120–160ms; düğme basışı; toast kayması.
- Azaltılmış hareket ayarına saygı göster.

## Kurallar
- Widget'larda sabit kodlanmış renk yok; `C` kullanın.
- Tema token'larından başka yeni renk yok.
- Tüm yıkıcı işlemler için onay diyaloğu gerekir.
- Deneysel özellikler amber kesikli kenarlık + ack geçidi kullanır.