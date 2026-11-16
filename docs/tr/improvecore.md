# ImproveCore — Rust Çekirdek İyileştirmeleri (Rust Core Improvements)

Language switcher: [English](../../improvecore.md) · [Français](../fr/improvecore.md) · [Español](../es/improvecore.md) · [Deutsch](../de/improvecore.md) · [简体中文](../zh/improvecore.md) · [Русский](../ru/improvecore.md) · [Português](../pt/improvecore.md) · [日本語](../ja/improvecore.md) · [العربية](../ar/improvecore.md) · [हिन्दी](../hi/improvecore.md) · **Türkçe**

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

Kaynak: `ui-improvement.md`'dan taşınan Rust ile ilgili maddeler.

## Cihaz başına ADB flash
- Yeniden deneme/geri çekilme (backoff) ve net durum makinesi ile cihaz anahtarlı ADB oturumları.
- Varsayılan olarak yazma sonrası doğrulama (hash); bölüm başına ilerleme.
- Sağlam yetkisiz/çevrimdışı yönetimi; otomatik yeniden yetkilendirme istemi.
- Parazitsiz (cross-talk) birden çok eşzamanlı ADB cihazını destekle.

## Odin (Samsung) yeniliği
- En son Odin'i aşacak performans: tek oturum dayanıklılığı, port sıfırlama kurtarma, çok bölmeli akış.
- Daha iyi PIT doğrulama, vbmeta/AVB yönetimi, drk onarım rehberliği.
- Geçici USB hatalarında devam et/yeniden dene; ayrıntılı hata açıklamaları.

## BROM / düşük seviyeli iletişim
- MTK, Samsung, SPD, Qualcomm için birleşik BROM soyutlaması.
- Çöküş-BROM yardımcıları, SLA/auth, DA yükleme güvenilirliği.
- Eyleme dönüşebilir düzeltmelerle hata sınıflandırması; aşama başına zaman aşımı.

## En güncel MTK desteği
- Preloader V5/V6 ayrıştırma ve DA seçimi (`mtk_daloader.rs`).
- En güncel MTK DA/preloader sürümlerini izle; otomatik algıla ve seç.
- Exploit/SLA yollarının en yeni çiplerde çalışmasını sağla; test armatürleri ekle.

## USB arayüz algılama
- CDC ACM, ECM/NCM, yığın depolama, HID, satıcıya özgü, tanılama/modem algılama.
- bootrom, preloader, ADB, download mode, EDL, MTK, SPD algılama.
- Cihaz satırlarında arayüz listesini açığa çıkar; desteklenen akışlarla eşle.

## Anında kaldırma (FRP/MDM/kilitler)
- Güvenli yerlerde hızlı yollar: HiProTool benzeri araştırma entegrasyonu, belgelendirilmiş.
- `operations/` içinde doğrulanmış adımlarla cihaza özgü oynatım kitapları (playbook).
- Riskli işlemler için deneysel geçit + denetim günlüğü (audit logging) korunsun.