Language switcher: [English](../../SECURITY.md) · [Français](../fr/SECURITY.md) · [Español](../es/SECURITY.md) · [Deutsch](../de/SECURITY.md) · [简体中文](../zh/SECURITY.md) · [Русский](../ru/SECURITY.md) · [Português](../pt/SECURITY.md) · [日本語](../ja/SECURITY.md) · [العربية](../ar/SECURITY.md) · [हिन्दी](../hi/SECURITY.md) · **Türkçe**

> English kanonik kaynaktır. Bu sayfa bir çeviridir; katkı memnuniyetle karşılanır — bkz. [`../TRANSLATION.md`](../TRANSLATION.md).

# Güvenlik Politikası

## Desteklenen sürümler

Proje pre-1.0 aşamasındadır. Güvenlik düzeltmeleri `main` dalına ve varsa en son etiketli sürüme uygulanır.

## Bir güvenlik açığı bildirme

Lütfen güvenlik sorunları için **herkese açık bir issue açmayın**. Gizli olarak bildirin:

- E-posta: **flashpilot@proton.me** (proton.me → ücretsiz hesap oluşturun), veya
- Bu depodaki GitHub'ın özel güvenlik açığı bildirim formu.

Lütfen şunları ekleyin:

- Etkilenen komut / akış ve sürüm,
- Yeniden üretme adımları,
- Etki (ör. keyfi kod çalıştırma, brick riski, veri kaybı, kimlik bilgisi sızıntısı).

Bildirimleri 72 saat içinde onaylamayı hedefliyoruz ve açıklamayı koordine edeceğiz.

## Kapsam ve beklentiler

Bu araç kasıtlı olarak düşük seviyeli USB / önyükleyici işlemi yapar. Doğası gereği bir cihazı silebilir veya brick'leyebilir. Bu belgelenmiş davranıştır, bir güvenlik açığı değil. Bizi ilgilendiren konular:

- Niyetlenen işlemin ötesinde güvenilmeyen kod çalıştıran exploit'ler,
- Kullanıcılara zarar verecek şekilde güvenlik onaylarını / cihaz kontrollerini atlatma,
- Depoya tescilli blob'lar veya sırlar gönderme,
- Bir kullanıcının cihaz verilerini veya kimlik bilgilerini sızdıran her şey.

Lütfen yalnızca sahip olduğunuz veya hizmet vermeye yetkili olduğunuz cihazlar üzerinde çalışın.
