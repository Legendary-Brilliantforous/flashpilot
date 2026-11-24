# चेंजलॉग (Changelog)

Language switcher: [English](../../CHANGELOG.md) · [Français](../fr/CHANGELOG.md) · [Español](../es/CHANGELOG.md) · [Deutsch](../de/CHANGELOG.md) · [简体中文](../zh/CHANGELOG.md) · [Русский](../ru/CHANGELOG.md) · [Português](../pt/CHANGELOG.md) · [日本語](../ja/CHANGELOG.md) · [العربية](../ar/CHANGELOG.md) · **हिन्दी** · [Türkçe](../tr/CHANGELOG.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 1.2.2 (ऑटो-अपडेट, 10 भाषाएँ, Rockchip + मोडेम-सेफ मल्टी-डिवाइस)

*1.2.2 → 1.3.2 डेव-साइकिल नोट्स को समेकित करता है — 1.2.1 के बाद से शिप हुआ सब कुछ।*

### ऑटो-अपडेट और What's New (नया)
- अपडेट ऑटो-इंस्टॉल होते हैं: डाउनलोड किया गया `.deb` बैकग्राउंड में sudo से इंस्टॉल होता है, ऐप रीस्टार्ट होता है, और पहली लॉन्च पर एक वन-शॉट "क्या जुड़ा या बदला" विंडो नए वर्शन का changelog दिखाती है (Settings → Updates में ऑटो-इंस्टॉल ऑफ़ होने पर मैनुअल "Install Now" प्रॉम्प्ट बना रहता है)।

### 10-भाषा UI + लाइव भाषा स्विच (नया)
- पूरा UI 10 अतिरिक्त भाषाओं में आता है (Français, Español, Deutsch, 简体中文, Русский, Português, 日本語, العربية, हिन्दी, Türkçe): सेटिंग्स, डिवाइस टाइल्स, पेजेज़ और कंसोल स्ट्रिंग्स।
- UI भाषा बदलना तुरंत है — रीस्टार्ट नहीं; लेआउट असली फ़ॉन्ट मीट्रिक्स पर क्लैंप होते हैं ताकि लंबे अनुवाद कंट्रोल क्लिप किए बिना रैप हों।
- की-बेस्ड JSON ट्रांसलेशन कैटलॉग कवरेज वेरिफिकेशन के साथ; CI इंस्टॉल्ड कैटलॉग का स्मोक-टेस्ट करता है।

### Rockchip + स्मार्टर डिटेक्शन (नया)
- नया Rockchip ब्रांड पेज: fastboot मोड से RK28xx–RK35xx फैमिली।
- डिटेक्शन सिर्फ चिप नहीं — मॉडल, ब्रांड और फ़ॉर्म फैक्टर पहचानता है।
- हर फ्लैशिंग स्टेज पकड़ा जाता है (TFT पैरिटी): MediaTek BROM/preloader/DA पूरे स्टेज PID सेट और OEM VIDs (preloader VCOM 0x2000/0x2001 समेत) में, एक्सटेंडेड Qualcomm EDL download-PID फैमिली, SPD download-PID यूनियन, और Qualcomm HS-USB Diagnostics को अपने अलग मोड के रूप में नाम दिया गया।
- मोड बैज SELECTED डिवाइस का पालन करता है और OTHER की जगह असली USB प्रोटोकॉल (ADB/MTP/PTP/DIAG/storage/RNDIS) बताता है: सिर्फ फ्लैशिंग PIDs लो-लेवल MediaTek लेबल दावा करते हैं, Qualcomm EDL अपना बैज चिप रखता है, और 'MEDIATEK'/'download' सबस्ट्रिंग फॉल-थ्रू फिक्स हो गए।

### Motorola FRP (नया)
- CVE-2016-10277 fastboot FRP चेन, own-DPC फेक-लॉगिन QR प्रोविज़निंग (TestDPC / Device Policy / Adobe), फ्लैश + रीबूट साइकिल वाला स्टेज्ड fastboot FRP, और factory-bootmode ADB साइकिल।

### असली इंजन पाथ (नया)
- Rust कोर में असली MTK/QCOM/Unisoc/Samsung फ्लैश, FRP और लॉक पाथ।
- odin4 गया: नेटिव Rust Odin इंजन पूरा tar पाइपलाइन, PIT और हर ज्ञात odin4 इश्यू क्लास संभालता है; Apple usbmuxd/lockdown Rust में चला गया; कोर Rust-ओनली है (सभी Python डिवाइस/प्रोटोकॉल फॉलबैक हटा दिए गए)।

### मोडेम-सेफ ADB (फिक्स्ड)
- पोल/मॉनिटर/डिस्प्ले पाथ ज़ीरो-टच हैं (`adb-devices --no-probe`): लूप्स से कोई open/claim/handshake नहीं — USB मोडेम्स हर साइकल री-एन्यूमरेट करना बंद करते हैं (लाइव वेरिफाइड: MSM8916 मोडेम पर 114 शांत पोल साइकल)।
- क्लेम फाइट्स लैडर से डेलिगेट होते हैं: नेटिव → Rust server transport (explicit serial) → host binary → rescue kill (लास्ट रिज़ॉर्ट), ताकि सिस्टम सर्वर इंटरफेस होल्ड करते समय भी ADB ऑप्स सफल हों।
- USB-ADB मर्ज फिक्स (row strings पार्स होते हैं, इसलिए रोज़ असल में ADB स्टेट ले जाते हैं), busy-होल्डर रेस्क्यू + ट्रांज़िएंट रिट्राई + ईमानदार busy स्टेट, babble/overflow गार्ड, क्लेम-टेस्ट आइसोलेशन कमांड, मॉडर्न adb CNXN वैल्यूज़, और QCOM/MTK कॉर्नर सिब्लिंग ब्रांचेज़ की तरह ADB ओवरले दिखाते हैं।

### मल्टी-डिवाइस रिलायबिलिटी (फिक्स्ड)
- सेटल-रिट्राई वाला पिक: जब स्कैन किसी री-एन्यूमरेटिंग डिवाइस को ट्रांज़िएंटली मिस करता है, तो हर टूल रनर 2.5s बाद एक बार रिट्राई करता है, बजाय इसके कि GUI connected दिखाते समय "no device" से रिफ्यूज़ करे।
- ADB AUTH टोकन राउंड्स में SHA-256 को खेल में रखता है (odd SHA-256, even SHA-1), ताकि खोया round-1 सिग्नेचर झूठे "not authorized" की दीवार में न बदले; `_wait_for_adb` ट्रांज़िएंट स्कैन फेलियर्स सहता है।
- टार्गेट-आइडेंटिटी बाइंडिंग: दोबारा उपयोग हुए bus:addr पर बैठा रिप्लेस्ड डिवाइस रिफ्यूज होता है (ज़ीरो-टच सीरियल चेक) — ट्रांसपोर्ट कभी किसी दूसरे फोन का पीछा नहीं करता।
- डिवाइस-लिस्ट स्विचिंग: जब दूसरा स्कैन डिवाइस गिरा दे तो कनेक्शन-बार रिबिल्ड रिट्राई करता है, डिवाइस बदलना अब पहले फोन पर फॉलबैक नहीं होता, और USB पिक मिस होने पर ADB टूल्स ADB daemon row पर फॉलबैक करते हैं ("shows connected but actions say no adb")।
- डिवाइस क्लासिफिकेशन + पिकर: अनमैच्ड डिवाइस गलत MTP लेबल की जगह USB रिपोर्ट करते हैं, और मिस हुआ USB पिक रिफ्यूज़ करने की जगह daemon-row पिकर ऑफ़र करता है ("Run on this device" / "Cancel")।

### ईमानदार रिज़ल्ट्स और GUI पॉलिश (फिक्स्ड)
- FRP फ्लोज़ को वेरिफाइड फ़्लैग्स और असली shell एग्ज़िट स्टेटस चाहिए; नॉन-ज़ीरो bridge एग्ज़िट लॉग टेल के साथ फेलियर उठाता है — अब झूठे "completed" टोस्ट नहीं।
- GUI: प्रति-रो जॉब चिप्स, विंडो मेमोरी, टोस्ट कैप, कीबोर्ड नेविगेशन, डिवाइस-अवेयर STOP (एक जॉब उसी डिवाइस को कैंसिल करता है), kg_unlock वर्कर थ्रेड में गया (30-सेकंड चेन अब विंडो फ्रीज़ नहीं करते), splash असली बिल्ड ट्रैक करता है, डेफ़र्ड पेजेज़ रिट्रायेबल रहते हैं, टोस्ट टॉप बार साफ़ करते हैं।

### सिक्योरिटी और रोबस्टनेस
- डिफ़ॉल्ट रूप से प्राइवेट आउटपुट, symlink-प्रूफ़ टेम्प नाम, symlink चेक।
- फर्मवेयर डिफ़ॉल्ट रूप से राइट-के-बाद-वेरिफाई + मॉडल गेट + न्यूमेरिक फिक्स।
- FRP: DPC साइनिंग सर्टिफ़िकेट नेटिव रूप से पढ़ा जाता है और प्रोविज़निंग चेकसम फिक्स है।
- HIL हार्डवेयर टेस्ट हार्नेस: असली हार्डवेयर पर मल्टी-डिवाइस / डिवाइस-रिप्लेसमेंट / USB-स्टॉर्म रिग्रेशन; ADB-मॉनिटर बैकऑफ़ टेस्ट डिटरमिनिस्टिक बनाए गए।
- पब्लिक लैंडिंग पेज (`website/`) कैपेबिलिटी मैट्रिक्स और प्रोटोकॉल कंसोल के साथ।

## 1.2.1 (स्थिर रिलीज़)

### मल्टी-डिवाइस सपोर्ट (नया)
- कई फोन प्लग इन करें: कनेक्शन बार हर एक लिस्ट करता है (model · serial ·
  transports); इंस्पेक्ट करने के लिए एक row क्लिक करें।
- जब कई मैच होते हैं, तो हर ऑपरेशन पूछता है कि वह किस फोन पर लागू होगा
  (0–1 मैच होने पर silent)। कंसोल लाइन्स `[device-key]` टैग ले जाती हैं।
- प्रति डिवाइस एक ऑपरेशन: अलग-अलग फोन बाहर फ्लैश हो सकते हैं; वही
  फोन अभी भी सीरियलिज़ होता है। ग्लोबल STOP सभी रनर्स को ब्रॉडकास्ट होता है।
- स्थिर आइडेंटिटी (`python/core/devices.py`): `adb:<serial>` → `usb:<port-path>`
  → वोलाटाइल फॉलबैक। सेशन खुलने से पहले टार्गेट्स री-रिज़ॉल्व होते हैं,
  ताकि USB री-एन्यूमरेशन फ्लैश अनाथ न बना दे (`usb device Fail`)।
- फोन-ओनली डिवाइस लिस्ट: हब्स, HID, वेबकैम्स और कार्ड रीडर्स फिल्टर होते हैं।
- नया `SPD` ट्रांसपोर्ट मोड + रीड-ओनली Qualcomm/SPD डिटेक्ट फ्लोज़।

### प्रति-चिप एक्सपेरिमेंटल (नया)
- Samsung `Knox / Warranty`, Qualcomm `QCN / Modem`, प्रति-चिप `IMEI Repair /
  Change`, `eMMC / UFS` — ओनिंग चिप पेज पर एम्बर कोलैप्सिबल (कोई ग्लोबल
  LAB पेज नहीं)। हर-रन ओनरशिप चेकबॉक्स; IMEI change को अतिरिक्त रूप से
  `I UNDERSTAND` टाइप करना ज़रूरी। ऑडिट-लॉग्ड; पर्सिस्टेड acks कभी ऑटो-पास
  नहीं होते (`check_gate_strict`)।

### MTK BROM (फिक्स्ड + इम्प्रूव्ड)
- **PID/स्टेज मैपिंग** mtkclient convention (`0e8d:0003`=BROM,
  `0e8d:2000`=preloader) के अनुसार Rust, Python, GUI लेबल्स, लॉग्स और डॉक्स में
  सही की गई।
- नया `mtk_crash_brom` ब्रिज कमांड + `MTK crash preloader into BROM` फ्लो
  (MTK BROM के अंतर्गत registred)।
- `_wait_mtk_brom_target()` स्टेबल हेल्ड BROM को प्रीलोडर विंडो पर प्रिफ़र
  करता है; DA डिस्कवरी ट्रंकेटेड (<1KB) बाइनरी रिफ्यूज़ करती है।

### Odin / फ्लैशिंग (हार्डन्ड)
- `_prepare_download_session()`: कर्नल-ड्राइवर detach + री-एन्यूमरेशन पर
  3× हैंडशेक रिट्राई; सभी Odin PIDs स्वीकार्य; PIT कैश फ्लैश से पहले वार्म।
- odin4 pinned with `-d /dev/bus/usb/BBB/AAA` + USB loss पर एक ऑटोमैटिक रिट्राई;
  `.tar.md5` ट्रेलर EOF पर anchored (streaming, कोई फुल RAM read नहीं)।
- नेटिव स्मार्ट फ्लैश प्रति-पार्टिशन MB/s + ETA लॉग करता है।

### रोबस्टनेस हार्डनिंग (रिव्यू-ड्रिवन)
- Sahara: HELLO command/version/mode/packet-size पार्स टाइम पर वैलिडेटेड (पहले:
  कोई भी ≥32-बाइट ब्लॉब trusted); ट्रांसफर-फॉर्मेट सेल्फ-चेक अब बाइट्स ड्रॉप
  करने के बजाय स्ट्रक्ट राउंड-ट्रिप करता है; close failures लॉग्ड; detach claim
  से पहले रन्स; हैंडशेक ट्रांसफर/close/reset आउटकम्स JSON में रिपोर्ट करता है
  discard करने के बजाय (reset एक्सप्लिसिट और विज़िबल)।
- ADB auth:  टोकन राउंड्स के बीच कैप्ड एक्सपोनेंशियल बैकऑफ; एक-बार वाला
  कीजन पॉज़ अनाउंस्ड लगने के बजाय अनाउंस होता है।
- MTK: कॉन्फ़िगर्ड पैकेट साइज़ वास्तव में DA सेशन तक पहुँचता है (पहले कम्प्यूट
  होकर ड्रॉप; सेशन्स हार्डकोडेड 64K), 512B–1MB तक clamp।
- सेफ्टी बैकअप्स: फेलियर एक अनमिसेबल बैनर प्रिंट करता है जिसमें elapsed time और
  STOP हिंट (कॉन्ट्रैक्ट बिना बदलाव: ऑपरेशन कभी ब्लॉक नहीं होता)।
- एक्सपेरिमेंटल गेट्स: iCloud + Pixel फ्लोज़ strict per-run acks में migrate;
  GUI ack टोकन्स अब प्रति फीचर गिने जाते हैं एक्सपायरी के साथ (न क्रॉस-फीचर
  ब्लीड, न लॉस्ट acks, न स्टेल ऑथराइज़ेशन्स)।

### GUI फिक्स
- टॉप-बार रेड बॉर्डर्स + बटन श्रिंक कॉन्करेंट शेक/रबर एनिमेशन और एक्सेंट-टिंटेड
  फोकस रिंग्स तक ट्रेस हुए: एनिमेशन्स `_anim_lock` से सीरियलाइज़ + फुल क्लीनअप;
  नए न्यूट्रल `focus_ring`/`sel_border` थीम टोकन्स (रेड एक्सेंट्स अब फोकस में लीक
  नहीं हो सकते)।
- `os.system()` → ब्रिज रिबिल्ड / लॉग-डिर ओपन के लिए `subprocess`।
- डुप्लिकेट SPD "Enable ADB" स्टब, `fastboot_unlock` एक्सपेरिमेंटल मिस-गेटिंग,
  डेड FUS→AP-slot पाथ, और मिसिंग `finished` emit फिक्स्ड। डेड
  LAB/Knox/QCN/PAC एक्सपेरिमेंटल सर्फेस हटाया गया।

### रिस्ट्रक्चर
- `python/core/frp.py` (गॉड फाइल) → `python/core/core.py` (रजिस्ट्री + फ्लोज़);
  `frp.py` अब केवल FRP है। डेड `python/core/flows/` स्प्लिट हटाया गया।
- वर्ब-फर्स्ट जॉब नाम (`Remove FRP`, `Flash Firmware`, …); फ्लो का एक कैनॉनिकल
  snake_case key; डिस्प्ले-नाम casing नॉर्मलाइज़्ड।

### डॉक्स
- फ्रेश स्क्रीनशॉट्स (`docs/samsung.png`, `mtk.png`, `spd.png`), रीराइटेन
  README हाइलाइट्स/मैट्रिक्स/लेआउट, CONTRIBUTING आर्किटेक्चर + फ्लो रूल्स,
  यह चेंजलॉग।

### boot.img + AVB (सिंगल नेटिव इंजन)
- Rust ब्रिज में नया इमेज-सर्जरी इंजन (`src/imgtools.rs`): Android
  बूट हेडर पार्स, cpio newc स्कैन, prop patching (pad-in-place या
  magiskboot-style grow with header rewrite), deterministic gzip
  (mtime=0, level 9), AVB vbmeta flags। `boot-info` / `boot-patch-adb` /
  `vbmeta-patch` CLI।
- Python `spd_adb` repack + `core._patch_vbmeta_flags` डेलिगेट विद लोकल
  फॉलबैक (signatures और return contracts अनचेंज्ड)।
- इक्विवलेंस वर्क ने दो रिअल बग्स फिक्स किए: grow splice रीडर के
  एलाइनमेंट से 2 बाइट्स डिसअग्री (बाद की हर एंट्री भ्रष्ट — दोनों
  इम्प्लीमेंटेशन्स), और री-पैचिंग हर रन ग्रूथ `\n` (अब दोनों साइड्स इडेम्पोटेंट)।
  gzip बाइट्स पैरिटी से इंटेंशनली एक्सक्लूड (zlib इम्प्लीमेंटेशन्स डिफर);
  डिकम्प्रेस्ड कंटेंट, साइज़ें और फील्ड्स मैच।
- 6 Rust यूनिट टेस्ट्स + 9 क्रॉस-इम्प्लीमेंटेशन टेस्ट्स।

### PAC (सिंगल नेटिव इंजन + वायर्ड GUI एक्शन्स)
- Rust ब्रिज में नया SPD PAC इंजन (`src/pac.rs`): parse/extract/pack
  YGDP लेआउट के साथ, शेयर्ड हेडर/स्लॉट बिल्डर्स अब `spd-readback` राइटर द्वारा
  भी उपयोग (बाइट-आइडेंटिकल आउटपुट; इसके हिस्टोरिकल डबल्ड स्लॉट नेम्स
  क्वारंटाइन्ड, नॉट प्रोपेगेटेड)। `pac-parse` / `pac-extract` /
  `pac-pack` CLI।
- Python `pac.*` डेलिगेट विद लोकल फॉलबैक; नए `flow_pac_extract` /
  `flow_pac_pack` (file-only, ofp-style env inputs) FLOWS में registered
  और GUI डिस्पैचर में मैप्ड — पहले डेड PAC बटन्स अब चलते हैं।
- इक्विवलेंस टेस्ट्स ने एक रिअल बग पकड़ा: लोकल पैकर product string साइलेंटली
  ड्रॉप करता था (slice-copy write); उसी मैसेज के साथ दोनों इंजन्स पर u32
  overflow guards।
- 5 Rust यूनिट टेस्ट्स + 7 क्रॉस-इम्प्लीमेंटेशन टेस्ट्स (दोनों दिशाओं में
  राउंडट्रिप्स, sanitize पैरिटी incl. dir collision, एरर मैपिंग)।

### PIT (सिंगल नेटिव इंजन)
- Rust ब्रिज में नया Samsung PIT इंजन (`src/pit.rs`): parse (28/132
  लेआउट), हेडर/मॉडल स्ट्रिंग्स, नाम नॉर्मलाइज़ेशन, find, overlap scan,
  फोरेन्सिक वैलिडेशन + हेल्थ वर्डिक्ट्स — रियल डंप्स और एज केसेज़ पर
  Python इम्प्लीमेंटेशन जैसे बाइट-आइडेंटिकल मैसेजेस, समरिज़ और वर्डिक्ट्स
  (Python-`repr` पैरिटी सहित जंक नेम्स के लिए)।
- `pit-parse` / `pit-health` / `pit-find` / `pit-overlaps` / `pit-model`
  CLI; Python `pit.*` रॉ-बाइट्स पाथ्स ब्रिज डेलिगेट विद लोकल फॉलबैक जब
  बाइनरी गायब हो (कॉन्ट्रैक्ट्स संरक्षित: ValueError/None/never-raise)।
  इन-मेमोरी ऑब्जेक्ट पाथ्स और डिस्प्ले हेल्पर्स लोकल और फास्ट रहते हैं;
  शेयर्ड रूल्स 11 क्रॉस-इम्प्लीमेंटेशन इक्विवलेंस टेस्ट्स से pinned।
- 8 Rust यूनिट टेस्ट्स (लेआउट वेक्टर्स, नॉर्मलाइज़ टेबल, meta overlap
  क्लासिफिकेशन, समरी/ह्यूमन-साइज़ शेप्स)।

### ADB (नेटिव ट्रांसपोर्ट, नो प्लेटफ़ॉर्म-टूल्स)
- Rust ब्रिज में नया नेटिव ADB क्लाइंट (`src/adb.rs`): USB ट्रांसपोर्ट
  (255/66/1) with kernel-driver detach, CNXN हैंडशेक, RSA-SHA256/SHA-1
  AUTH (reuses `~/.android/adbkey`, missing होने पर generated), `shell:` and
  `sync:` (STAT/RECV/SEND) सर्विसेज़।
- `adb-devices` नेटिव स्कैन से अपना `adb devices -l` लाइन कॉन्ट्रैक्ट रखता है
  (`device` / `unauthorized` / `no permissions`); `adb-shell` एक serial लेता है
  (`-` = first authorized), plus new serial-pinned `adb-pull` / `adb-push`।
- Python: `bridge.adb_shell()` resolves explicit > ambient-scope > first
  authorized serial (मल्टी-डिवाइस ADB अब target-pinned); `adb.py`
  ब्रिज डेलिगेट करता है; EFS backup/restore pull/push ब्रिज से जाते हैं
  instead of unpinned system `adb` calls। `has_adb()` अब "bridge built" का मतलब।
- 6 Rust टेस्ट्स (framing, banner, PKCS#1 sign/verify, DER roundtrip,
  system adb की key से बाइट-आइडेंटिकल pubkey blob) + 9 Python टेस्ट्स।

### Fastboot (नेटिव ट्रांसपोर्ट + मोटोरोला universal)
- Rust ब्रिज में नया नेटिव fastboot USB transport (`src/fastboot.rs`):
  `fastboot-devices` (JSON) + `fastboot-cmd <vid:pid@bus:addr> <ms> <cmd…>`
  command phase (getvar/oem/erase/reboot) के लिए, with kernel-driver detach।
  Device-side FAIL `FAILED (remote: …)` जैसा render होता है exit 0 के साथ,
  system binary के transcript shape को मैच करता है (Moto MBM bootloaders पर
  OKAY packet में राइड करने वाले lone `getvar` values सहित)।
- शेयर्ड Python हेल्पर्स (`_fastboot_run`, `_wait_fastboot`,
  `_fastboot_getvar`) नेटिव-फर्स्ट with system-binary fallback; DATA-phase
  commands (flash/boot/…) हमेशा system binary, और host-side `devices` listing
  नेटिव detect से सर्व। सारा fastboot ट्रैफिक अब target-pinned है
  (`vid:pid@bus:addr`), नो-`-s` व्रॉन्ग-फोन हैज़र्ड बंद।
- नए brand-wide मोटोरोला फ्लोज़ (`moto_frp_adb`, `moto_frp_fastboot`,
  `moto_oem_unlock_token`): ADB provisioning reset, ऑफिशियल unlock-token flow
  with lock-state read + session resets, रीड-ओनली टोकन रीडर। Motorola →
  All Motorola / Lenovo (universal) और हर Moto मॉडल के अंतर्गत दिखे; unlock
  पोर्टल URL सही किया (पुराना `motorola.com/unlockbootloader` डेड है)।
- `python/core/fastboot.py` (Pixel) और `usb_watch.py` (lsusb scraping) ब्रिज
  पर मूव; 7 नए `tests/test_fastboot_native.py` टेस्ट्स।