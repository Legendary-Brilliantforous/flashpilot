# FlashPilot 1.2.1 — स्थिर (Stable)

Language switcher: [English](../../DESCRIPTION.md) · [Français](../fr/DESCRIPTION.md) · [Español](../es/DESCRIPTION.md) · [Deutsch](../de/DESCRIPTION.md) · [简体中文](../zh/DESCRIPTION.md) · [Русский](../ru/DESCRIPTION.md) · [Português](../pt/DESCRIPTION.md) · [日本語](../ja/DESCRIPTION.md) · [العربية](../ar/DESCRIPTION.md) · **हिन्दी** · [Türkçe](../tr/DESCRIPTION.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

Linux पर Android डिवाइसों के लिए ओपन-सोर्स फ्लैशिंग और रिपेयर वर्कबेंच — व्यावसायिक Windows फ्लैशिंग सूट्स का मुफ्त विकल्प। **1.2.0 एक स्थिरता + प्रगति रिलीज़ है: `cargo check` 0 चेतावनियाँ, `cargo test` 60 + `pytest` 149 पास, लाइव GitHub रिलीज़ चैनल, और ऑडिट-योग्य इतिहास।**

एक नेटिव **Rust** कोर (`flashpilot-bridge`, ~9,300 LOC, vendored libusb) बूटलोडर प्रोटोकॉल सीधे बोलता है — Samsung Odin/HID, MediaTek BROM/DA, Qualcomm Sahara/Firehose, Spreadtrum/UNISOC BSL — जबकि एक साफ-सुथरा **PyQt6** स्टूडियो 9 ट्रांसपोर्ट, 13 जॉब श्रेणियाँ और ~120 ऑपरेशन दिखाता है: फ्लैशिंग, FRP बायपास, स्क्रीन-लॉक हटाना, MDM अनलॉक, पार्टिशन टूल्स, डिवाइस जानकारी, रिबूट, और किसी भी ADB डिवाइस पर बैटरी/नेटवर्क रिपेयर।

**1.2.0 स्थिर में नया क्या है:**
- **ब्रिज 0 चेतावनियाँ** — 18 डेड-पाथ वायर किए: AT `Context` रिटेंशन और `vid` वैलिडेशन (`+DEBUGLVC` के बाद `AT/control` री-एन्यूमरेशन), USB `EndpointConfig.max_packet_size` चंकिंग और `open_target/read_exact/info`, SPD `BSL_CMD`/`BSL_REP` + `iface` + `flush/read_flash/chip_uid/power_off`, `ProgressReporter` → वास्तविक फ्लैश %, Qualcomm `QcomDeviceInfo`/`FirehosePacket`, MTK `read16/write16` — `-80KB` `lto`, कोई हैंडल लीक नहीं।
- **डायनामिक वर्शन** — इंस्टॉल्ड `importlib.metadata` से `APP_VERSION` (deb का `pyproject.toml` सत्य है), `_display_version` `1.2.0→1.2` / `1.2.1→1.2.1`, लाइव GitHub `latest stable` (कभी हाथ से नहीं लिखा), लोगो/टाइटलबार पर BETA पिल।
- **एकीकृत बड़े डायलॉग** — 620px केंद्रित ड्रैगेबल कार्ड (320px टोस्ट की जगह) जिनमें हाई-कॉन्ट्रास्ट `#e2e8f0` टेक्स्ट, `✕` + `X` ड्रैग, चिप रंग: `MTK amber`, `QCOM red`, `SPD violet`, `SAMSUNG blue`; बीटा गेट को `I accept` चेकबॉक्स चाहिए (प्रति-वर्शन पर्सिस्ट, `first_install` डिफ़ॉल्ट / `every_boot` टॉगल Settings → Updates में), `Exit` ऐप बंद करता है, स्थिर `UPDATE/AHEAD/PATCH` वही बड़ा डायलॉग उपयोग करते हैं, फ्लैश/FRP कन्फर्म ओवरले चिप ग्रेडिएंट उपयोग करते हैं।
- **एक ग्लोबल STOP** — टाइटलबार में एक ही `⏹ STOP` (किसी भी कार्ड के बाहर), `_FLOW_LABEL` में 150ms सिंक, *किसी भी* Samsung/MTK/QC/SPD फ्लो को रोकता है; लेगेसी प्रति-चिप Stop छिपे हुए।
- **गवर्नेंस** — `dev`/`main` संरक्षित: `strict` CI `Rust+Python`, `1` रिव्यू, `dismiss_stale`, `require_last_push_approval`, `linear_history`, `force_push:false`; `devin-ai-integration[bot]` इतिहास/टैग `v1.2.1-beta.1` से हटा → `55c0da3`.

- **प्लेटफ़ॉर्म:** Linux
- **भाषा:** Rust (कोर) + Python 3.10+ / PyQt6 (UI)
- **लाइसेंस:** MIT
- **स्थिति:** stable 1.2.0 — योगदानकर्ता स्वागत हैं

इसे केवल उन डिवाइसों पर उपयोग करें जो आपके हैं या जिनकी सर्विस करने का आपको अधिकार है।