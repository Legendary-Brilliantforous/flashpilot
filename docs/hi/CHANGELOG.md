# चेंजलॉग (Changelog)

Language switcher: [English](../../CHANGELOG.md) · [Français](../fr/CHANGELOG.md) · [Español](../es/CHANGELOG.md) · [Deutsch](../de/CHANGELOG.md) · [简体中文](../zh/CHANGELOG.md) · [Русский](../ru/CHANGELOG.md) · [Português](../pt/CHANGELOG.md) · [日本語](../ja/CHANGELOG.md) · [العربية](../ar/CHANGELOG.md) · **हिन्दी** · [Türkçe](../tr/CHANGELOG.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 1.3.2 (बैज USB प्रोटोकॉल का नाम बताता है)

- मोड बैज अब किसी जुड़े डिवाइस के लिए OTHER नहीं दिखाता:
  'MEDIATEK' में 'MTK' सबस्ट्रिंग नहीं होती, इसलिए एक जेनेरिक
  MTK-मोड लेबल ('MEDIATEK MODE (VID 0x0E8D PID 0x2008)') अंत तक
  OTHER तक गिर जाता था।
- बिना मैच वाले PID (0e8d:2008, still-image/MTP इंटरफेस, बिना ADB row)
  के साथ नॉर्मल-बूट MediaTek/Tecno फोन अब लो-लेवल MediaTek के रूप में
  दावा नहीं किए जाते: केवल फ्लैशिंग PIDs (BROM/preloader/DA) ही लो-लेवल
  लेबल दावा करते हैं; बाकी सब इंटरफ़ेस-आधारित प्रोटोकॉल नामकरण
  (ADB/MTP/PTP/DIAG/storage/RNDIS) पर गिरते हैं, और यह अब सभी डिवाइस
  लिस्ट्स में होता है — पहले केवल Samsung डिवाइस ही प्रोटोकॉल-स्कैन होते थे।
- Rust ट्रांसपोर्ट्स: बिना मैच वाला PID जो फिर भी still-image (class 6)
  इंटरफेस expose करता है, USB के बजाय MTP रिपोर्ट करता है; बिना MTP
  इंटरफेस वाला हार्डवेयर ईमानदार USB लेबल रखता है।
- कनेक्शन लेबल नॉन-फ्लैशिंग PIDs के लिए 'MediaTek low-level' के बजाय
  'MediaTek device (normal boot)' दिखाता है।
- Qualcomm EDL अपना बैज चिप रखता है: 'EDL MODE (Qualcomm Emergency
  Download)' में 'download' सबस्ट्रिंग होती है और यह DOWNLOAD चिप तक
  गिर जाता था।
- Qualcomm HS-USB Diagnostics (05c6:9006, जैसे Diag में Moto) का नाम
  जेनेरिक 'QUALCOMM DEVICE' लेबल में मिलाने के बजाय
  'QUALCOMM DIAG MODE (HS-USB Diagnostics 9006)' रखा गया।

## 1.3.1 (ModeBadge फिक्स)

- डिवाइस-मोड बैज (टॉप बार, Stop के पास) SELECTED डिवाइस का अनुसरण
  करता है और अब Qualcomm-नॉर्मल सेटअप्स में MTP नहीं पढ़ता (सबस्ट्रिंग
  'normal' MTP चिप तक गिर जाती थी)।

## 1.3.0 (डिवाइस क्लासिफिकेशन + पिकर)

- अनमैच्ड डिवाइस (vendor-specific/diag composite) 'MTP' के बजाय
  'USB' रिपोर्ट करते हैं।
- जब USB pick फ्लैप पर मिस होता है, तो ADB टूल्स रिफ्यूज करने के बजाय
  daemon-row पिकर दिखाते हैं: चुनें कि ऑप किस डिवाइस को टार्गेट करेगा।

## 1.2.9 (डिस्प्लेड-डिवाइस आइडेंटिटी)

- डिवाइस बदलने पर अब पहले फोन पर फॉलबैक नहीं होता: 3s रिफ्रेश,
  लाइव-आइडेंटिटी रिज़ॉल्वर और सभी फॉलबैक्स डिस्प्लेड डिवाइस पर की होती हैं;
  अनुपस्थिति पथ रो के स्टैटिक टाइल्स रखता है।

## 1.2.8 (डिवाइस-लिस्ट स्विचिंग फिक्स)

- कनेक्शन-बार रिबिल्ड रिट्राई करता है जब इसका दूसरा स्कैन एक डिवाइस गिरा
  देता है जिसे मॉनिटर अभी देख रहा था (री-एन्यूमरेशन विंडो): दोनों डिवाइस
  रेंडर होते हैं और फ्लैपिंग लिंक्स पर स्विचिंग काम करती है।

## 1.2.7 (टार्गेट-आइडेंटिटी बाइंडिंग)

- दोबारा उपयोग हुए बस:addr पर बैठा रिप्लेस्ड डिवाइस रिफ्यूज होता है
  (टार्गेट पर ज़ीरो-टच सीरियल चेक; ओपन vid/pid/bus/addr से मैच होता है,
  सीरियल से नहीं)। डिवाइस-रिप्लेसमेंट सिनेरियो बंद होता है: ट्रांसपोर्ट कभी
  किसी दूसरे डिवाइस का अनुसरण नहीं करता।

## 1.2.6 (डेमन-रो फॉलबैक)

- ADB टूल्स फ्लैपिंग बस पर USB-स्कैन पिक मिस होने पर ADB daemon row पर
  फॉलबैक करते हैं (daemon TCP-आधारित है और प्रेज़ेंस के लिए ऑथॉरिटेटिव रहता है)।
  'shows connected but actions say no adb' फिक्स होता है।

## 1.2.5 (MTK कॉर्नर ADB ओवरले)

- mtk_devs कॉर्नर ब्रांच अब सिब्लिंग ब्रांचेज़ की तरह ADB ओवरले दिखाता है:
  ऑथराइज्ड ADB वाला Tecno/MTK डिवाइस टॉप-राइट कॉर्नर में ट्रांसपोर्ट नाम देता है
  (पहले केवल 'MediaTek low-level' दिखाता था जबकि ADB Status connected दिखाता था)।

## 1.2.4 (ADB AUTH फिक्स)

- AUTH हैश अल्टर्नेशन सही किया: SHA-256 टोकन राउंड्स में बना रहता है
  (odd राउंड्स SHA-256, even SHA-1)। पहले नॉइज़ी लिंक पर खोया हुआ round-1
  सिग्नेचर SHA-1 की दीवार में री-टोकन हो जाता था → डिवाइस ऑथराइज्ड होते हुए भी
  झूठा 'not authorized'।
- _wait_for_adb ट्रांज़िएंट स्कैन फेलियर्स mid-wait सहता है।

## 1.2.3 (पिक रेज़िलिएंस)

- सेटल-रिट्राई वाला डिवाइस पिक: हर टूल रनर जब एक स्कैन ट्रांज़िएंटली री-एन्यूमरेटिंग
  डिवाइस मिस करता है, तो 2.5s बाद एक बार रिट्राई करता है, बजाय इसके कि
  जब GUI connected दिखा रहा हो तब "no device" से रिफ्यूज करे।
  यूज़र-कैंसिल्ड चूज़र कभी रिट्राई नहीं होते।

## 1.2.2 (मोडेम-सेफ ADB + डिस्प्ले फिक्स)

### ADB ट्रांसपोर्ट (फिक्स्ड)
- पोल/मॉनिटर/डिस्प्ले पाथ ज़ीरो-टच हैं (`adb-devices --no-probe`,
  `adb_presence`): लूप्स से कोई open/claim/handshake नहीं। USB मोडेम्स का हर
  साइकल री-एन्यूमरेशन फिक्स होता है (लाइव वेरिफाइड: ~1 Hz तूफ़ानों के बाद
  एक MSM8916 मोडेम पर 114 शांत पोल साइकल)।
- डेलिगेट लैडर on claim फाइट्स: नेटिव -> Rust server transport
  (`adb-shell-server`, explicit serial only) -> host binary -> rescue kill
  (लास्ट रिज़ॉर्ट)। ADB ऑप्स अब तब सफल होते हैं जब सिस्टम सर्वर इंटरफेस
  होल्ड कर रहा हो, बजाय उसे एविक्ट करने का।
- USB-ADB मर्ज फिक्स: row strings पार्स होते हैं (struct डिसीरियलाइज़ेशन
  चुपचाप ज़ीरो ADB एंट्री देता था, इसलिए रोज़ कभी ADB स्टेट नहीं ले जाते थे)।
- QCOM कॉर्नर अब सिब्लिंग ब्रांचेज़ की तरह ADB ओवरले दिखाता है।

### रोबस्टनेस (फिक्स्ड)
- ट्रांज़िएंट गेट रिफ्यूज़ल्स (री-एन्यूमरेशन विंडोज़) पर single settle-retry
  अक्यूरेट मैसेज के साथ; सभी डायग्नोस्टिक/टूल शेल में `rescue=False` +
  serial pinning; Firehose FAIL डिटेक्शन; CLI input panics; allocation clamps;
  tar traversal guards; strict XML numerics।

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