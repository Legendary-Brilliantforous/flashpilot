# ImproveCore — Rust कोर सुधार (Rust Core Improvements)

Language switcher: [English](../../improvecore.md) · [Français](../../fr/improvecore.md) · [Español](../../es/improvecore.md) · [Deutsch](../../de/improvecore.md) · [简体中文](../../zh/improvecore.md) · [Русский](../../ru/improvecore.md) · [Português](../../pt/improvecore.md) · [日本語](../../ja/improvecore.md) · [العربية](../../ar/improvecore.md) · **हिन्दी** · [Türkçe](../../tr/improvecore.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

स्रोत: `ui-improvement.md` से हटाए गए Rust-संबंधित आइटम।

## प्रति डिवाइस ADB फ्लैशिंग
- डिवाइस-कुंजी वाले ADB सेशन जिनमें retry/backoff और स्पष्ट state machine।
- डिफ़ॉल्ट रूप से verify-after-write (hash); प्रति-पार्टिशन प्रोग्रेस।
- रोबस्ट unauthorized/offline हैंडलिंग; ऑटो री-ऑथ प्रॉम्प्ट।
- क्रॉस-टॉक के बिना कई समवर्ती ADB डिवाइसों का समर्थन।

## Odin (Samsung) इनोवेशन
- नवीनतम Odin से आगे: single-session resilience, port reset recovery, multi-partition streaming।
- बेहतर PIT वैलिडेशन, vbmeta/AVB हैंडलिंग, drk रिपेयर मार्गदर्शन।
- ट्रांज़िएंट USB एरर्स पर रिज़्यूम/रिट्राई; विस्तृत फेलियर एक्सप्लेनेशन।

## BROM / लो-लेवल कम्यूनिकेशन
- MTK, Samsung, SPD, Qualcomm के लिए एकीकृत BROM एब्स्ट्रैक्शन।
- Crash-to-BROM हेल्पर्स, SLA/auth, DA अपलोड विश्वसनीयता।
- एक्शनेबल फिक्स के साथ एरर क्लासिफिकेशन; प्रति स्टेज टाइमआउट।

## नवीनतम MTK सपोर्ट
- Preloader V5/V6 पार्सिंग और DA चयन (`mtk_daloader.rs`)।
- नवीनतम MTK DA/preloader वर्शन ट्रैक करें; ऑटो-डिटेक्ट और चयन।
- सबसे नए चिप्स पर exploit/SLA पथ सुनिश्चित करें; टेस्ट फिक्स्चर जोड़ें।

## USB इंटरफ़ेस डिटेक्शन
- CDC ACM, ECM/NCM, mass storage, HID, vendor-specific, diagnostic/modem का डिटेक्शन।
- bootrom, preloader, ADB, download mode, EDL, MTK, SPD का डिटेक्शन।
- डिवाइस रोज़ में इंटरफ़ेस लिस्ट एक्सपोज़ करें; सपोर्टेड फ्लो से मैप करें।

## इंस्टैंट रिमूवल (FRP/MDM/लॉक्स)
- सुरक्षित जगहों पर फास्ट पाथ्स: HiProTool-जैसा रिसर्च इंटीग्रेशन, दस्तावेज़ीकृत।
- `operations/` में वेरिफाइड स्टेप्स के साथ डिवाइस-विशिष्ट प्लेबुक।
- रिस्की ऑप्स के लिए एक्सपेरिमेंटल गेटिंग + ऑडिट लॉगिंग बनाए रखें।