Language switcher: [English](../../SECURITY.md) · [Français](../../fr/SECURITY.md) · [Español](../../es/SECURITY.md) · [Deutsch](../../de/SECURITY.md) · [简体中文](../../zh/SECURITY.md) · [Русский](../../ru/SECURITY.md) · [Português](../../pt/SECURITY.md) · [日本語](../../ja/SECURITY.md) · **العربية** · [हिन्दी](../../hi/SECURITY.md) · [Türkçe](../../tr/SECURITY.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

# سياسة الأمان

## الإصدارات المدعومة

المشروع في مرحلة ما قبل 1.0. إصلاحات الأمان تصل إلى فرع `main` و، عند وجوده، إلى آخر إصدار مُوسم.

## الإبلاغ عن ثغرة

الرجاء **عدم** فتح issue عام لمشاكل الأمان. أبلغ بشكل خصوصي:

- بريد إلكتروني: **flashpilot@proton.me** (أنشئ هذا العنوان at proton.me → حساب free)، أو
- نموذج الإبلاغ الخاص بالثغرات в GitHub لهذا المستودع.

يرجى تضمين:

- الأمر / التدفق المتأثر والنسخة،
- خطوات إعادة الإنتاج،
- الأثر (e.g. تنفيذ code عشوائي، risk brick، فقدان بيانات، exposure credentials).

نهدف إلى الإقرار في غضون 72 ساعة وتنسيق الإفصاح.

## النطاق والتوقعات

تعمل هذه الأداة deliberamente performs low-level USB / bootloader operations. بحكم طبيعتها، يمكن it wipe أو brick a device. ذلك behaviour موثّق، not a vulnerability. Nous nous soucions de:

- exploits that run untrusted code beyond the intended operation،
- bypassing safety confirmations / device checks in a way that harms users،
- shipping proprietary blobs or secrets in the repository،
- anything that leaks a user's device data or credentials.

الرجاء operate only on devices you own or are authorized to service.