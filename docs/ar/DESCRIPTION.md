# FlashPilot 1.2.1 — مستقر

Language switcher: [English](../../DESCRIPTION.md) · [Français](../fr/DESCRIPTION.md) · [Español](../es/DESCRIPTION.md) · [Deutsch](../de/DESCRIPTION.md) · [简体中文](../zh/DESCRIPTION.md) · [Русский](../ru/DESCRIPTION.md) · [Português](../pt/DESCRIPTION.md) · [日本語](../ja/DESCRIPTION.md) · **العربية** · [हिन्दी](../hi/DESCRIPTION.md) · [Türkçe](../tr/DESCRIPTION.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

منصّة Linux مفتوحة المصدر لتفليش وإصلاح أجهزة Android — المكافئ المجاني لحزم التفليش التجارية على Windows. **1.2.0 هي إصدار استقرار + تقدم: `cargo check` 0 warnings، `cargo test` 60 + `pytest` 149 يمر، قناة إصدار GitHub مباشرة، وتاريخ قابل للتدقيق.**

النواة Rust أصلية (`flashpilot-bridge`، ~9,300 سطر، libusb مُضمَّن) تتحدث بروتوكولات bootloader مباشرة — Samsung Odin/HID، MediaTek BROM/DA، Qualcomm Sahara/Firehose، Spreadtrum/UNISOC BSL — بينما تُقدِّم واجهة studio بـ PyQt6 9 وسائل نقل و13 فئة jobs و~120 عملية: تفليش، تجاوز FRP، إزالة قفل الشاشة، فتح MDM، أدوات partitions، معلومات الجهاز، إعادة تشغيل، وإصلاح battery/network على أي جهاز ADB.

**ما الجديد في 1.2.0 مستقر:**
- **Bridge 0 warnings** — تم توصيل 18 dead-path: retention سياق AT و`vid` validation (`AT/control` re-enumeration بعد `+DEBUGLVC`)، تقطيع USB `EndpointConfig.max_packet_size` و`open_target/read_exact/info`، SPD `BSL_CMD`/`BSL_REP` + `iface` + `flush/read_flash/chip_uid/power_off`، `ProgressReporter` → % تفليش حقيقية، Qualcomm `QcomDeviceInfo`/`FirehosePacket`، MTK `read16/write16` — `-80KB` `lto`، بدون تسرب handles.
- **Dynamic version** — `APP_VERSION` من `importlib.metadata` المثبت (deb `pyproject.toml` هو الحقيقة)، `_display_version` `1.2.0→1.2` / `1.2.1→1.2.1`، GitHub `latest stable` مباشرة (بدون ترميز يدوي)، شارة BETA على الشعار/شريط العنوان.
- **Unified big dialogs** — بطاقات centered قابلة للسحب 620px (مقابل toast 320px) مع نص high-contrast `#e2e8f0`، `✕` + سحب `X`، ألوان chips: `MTK amber`، `QCOM red`، `SPD violet`، `SAMSUNG blue`؛ beta gate يتطلب checkbox `I accept` (يُحفظ لكل إصدار، افتراض `first_install` / toggle `every_boot` في Settings → Updates)، `Exit` يغلق التطبيق، stable `UPDATE/AHEAD/PATCH` تستخدم نفس الحوار الكبير، تأكيدات flash/FRP تستخدم تدرج chip.
- **One global STOP** — `⏹ STOP` واحد في شريط العنوان (خارج أي card)، مزامنة 150ms إلى `_FLOW_LABEL`، يوقف *أي* تدفق Samsung/MTK/QC/SPD؛ Stops per-chip القديمة مخفية.
- **Governance** — `dev`/`main` protected: CI `strict` `Rust+Python`، مراجعة `1`، `dismiss_stale`، `require_last_push_approval`، `linear_history`، `force_push:false`؛ تمت إزالة `devin-ai-integration[bot]` من history/tag `v1.2.1-beta.1` → `55c0da3`.

- **Platform:** Linux
- **Language:** Rust (core) + Python 3.10+ / PyQt6 (UI)
- **License:** MIT
- **Status:** stable 1.2.0 — contributors welcome

استخدمه على أجهزة تملكها أو مصرح لك بخدمتها.