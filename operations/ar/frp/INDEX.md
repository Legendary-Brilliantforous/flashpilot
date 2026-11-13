Language switcher: [English](../../frp/INDEX.md) · [Français](../../fr/frp/INDEX.md) · [Español](../../es/frp/INDEX.md) · [Deutsch](../../de/frp/INDEX.md) · [简体中文](../../zh/frp/INDEX.md) · [Русский](../../ru/frp/INDEX.md) · [Português](../../pt/frp/INDEX.md) · [日本語](../../ja/frp/INDEX.md) · **العربية** · [हिन्दी](../../hi/frp/INDEX.md) · [Türkçe](../../tr/frp/INDEX.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# operations/frp/ — الحماية من إعادة الضبط (Factory Reset Protection) (Android فقط)

> أجهزة Apple لا تحتوي على FRP (تستخدم Apple بدلًا من ذلك Activation Lock / iCloud) —
> راجع `operations/apple/`.

يحتوي هذا الدليل على **أشجار توثيق لكل محرك** لتجاوز FRP. الكود الفعلي يعيش في `src/flows.rs` (Rust). عندما تحصل على وصفة عمل لجهاز (الشريحة، زوج FDL، إزاحات الأقسام، إلخ)، ضع ملاحظة بحث قصيرة في `devices/<brand>/<model>.md`. ملف README في جذر هذا الدليل يربط كل تدفق FRP في قاعدة الكود بموقعه وما يحتاجه.

## خريطة المحركات

| المحرك | متى يُستخدم | الكود | CLI الخاص بالجسر |
|---|---|---|---|
| **عام (ADB)** | أول محاولة على أي هاتف تم تمكين USB debugging فيه | تدفقات Rust (`adb_frp`، صفوف `frp_*` في `src/flows.rs`) | `flow-run adb_frp` / `adb shell ...` عبر `bridge.adb_shell` |
| **MTK BROM** | أجهزة MediaTek (Helio / Dimensity / MT6765) — أطفئ → اضغط Vol-/+ → وصل USB | تدفقات Rust (صفوف `mtk_*` في `src/flows.rs`) | `flow-run mtk_brom_info` (CLI: `mtk-detect`، `mtk-da-upload`، `mtk-frp`، `mtk-bypass`) |
| **MTK DA** | MTK BROM التي نجا من رفع DA (شرائح بحالة قفل) | تدفقات Rust (`mtk_brom_backup`، `mtk_auth_flash`) | `flow-run mtk_brom_backup` |
| **Qualcomm EDL** | تنزيل طوارئ 9008 (Snapdragon) | تدفقات Rust (صفوف `edl_*`، `qcom_*`) | `flow-run edl_frp` (CLI: `qcom-*`) |
| **Samsung Exynos** | A14 (Exynos 850/1330)، A15/A16 — وضع download في Odin للتفليش فقط، وليس لـ FRP | صفوف Rust `frp_*` (تجاوز حساب Samsung) | (في الغالب على الجهاز، بدون جسر) |
| **Samsung MTK (A05/A06)** | A05/A06 مع Helio G85 — يستخدم MTK BROM (أعلاه) | تدفقات Rust (`mtk_brom_info`، `mtk_brom_backup`) | `flow-run mtk_brom_backup` |
| **UNISOC/SPD** | 1782:4d00 FDL1+FDL2 (SC9863A، T606/UMS9230) | تدفقات Rust (صفوف `spd_*`) + `src/spd.rs` | `flow-run spd_detect_info` (CLI: `spd-detect`، `spd-frp`، `spd-format`، `spd-magic-pack`) |
| **HiSilicon Kirin** | 12d1 — لا يوجد تدفق مفتوح بعد (لم يُ reverse-engineered) | (لا شيء بعد) | (لا شيء) |

(وحدات المحرك القديمة `python/core/flows/*.py` لم تُشحن أبدًا؛
`mtk-brom-backup` هو صف التدفق `mtk_brom_backup`. تحقّق من أي مفتاح
باستخدام `flow-list`.)

## خريطة مفتاح التدفق → الدالة

كل تدفق يمكن لإجراءات FRP في GUI استدعاؤه. المفاتيح هي صفوف سجل Rust
(`src/flows.rs`، استخدم `flow-list` للتحقّق)؛ GUI توجّهها حسب (job، mode) والجسر ينفّذها عبر `flow-run <key> [target]`.

| مفتاح التدفق | المحرك | ماذا يفعل |
|---|---|---|
| `adb_frp` | ADB عام | `settings put secure frp 0` + تعطيل معالجات الإعداد + مسح بيانات GMS |
| `frp_browser` | ADB عام | فتح `chrome://settings/` على الجهاز عبر intent |
| `frp_emergency` | ADB عام | فتح Settings عبر dialer called Emergency (على الجهاز) |
| `frp_settings` | ADB عام | فتح Settings via مسار shade الإشعارات (على الجهاز) |
| `frp_fake_login` (+`_testdpc`، `+_adp`) | ADB عام | Provisioning عبر QR مع DPC device-owner، ثم مسح FRP |
| `at_info` | Samsung MTP/AT | قراءة mode + devconinfo через canal AT (Samsung pre-Android 8) |
| `at_method` | Samsung MTP/AT | AT+DEBUGLVC لتمكين ADB через port diag |
| `download_frp` | وضع Download Samsung | إزالة FRP through firmware CSC/Combination (عقد أمان PIT) |
| `odin_enable_adb` | وضع Download Samsung | تمكين ADB من وضع download through Odin tarball |
| `mtk_combo_flash` | MTK Download | تفليش firmware combo (PIT + DA) |
| `mtk_recovery_reset` | MTK Download | إعادة ضبط المصنع في وضع recovery |
| `mtk_brom_info` | MTK BROM | قراءة chip id / handshake (needed قبل أي flash BROM) |
| `mtk_brom_backup` | MTK BROM | تفريغ الأقسام through BROM DA |
| `edl_frp` | Qualcomm EDL | مسح Sahara + Firehose (05c6:9008) |
| `qcom_detect_info` | Qualcomm EDL | كشف + معلومات (قراءة فقط) |
| `frp_qr_provision` | ADB عام | Provisioning through QR (مسار TestDPC) |

(تم إيقاف: أسماء المفاتيح القديمة المسبوقة بـ `flow_*` و
`python/core/flows/*.py` لم تُشحن أبدًا — المفاتيح لا تحمل بادئة `flow_`.)

## كيف تصل وصفة جديدة per-model إلى هنا

1. **شغّل dump جهاز real** (راجع `scripts/dump-connected.sh` لمسار
   côté ADB، أو `flashpilot-bridge spd-format` لمسار côté BROM
   على Unisoc). الـ dump يذهب إلى `build/cache/dumps/<model>_<codename>/`.
2. **من الـ dump، حدّد** engine + chip + اسم partition FRP
   (تقريبًا دائمًا `frp`، `frp_a`، أو `userdata` على Android 11+).
3. **أضف entry الجهاز** في `python/gui/supported_devices.json` تحت
   المارca right، مع `actions: ["frp", "info", "backup", "flash"]`
   و `status: "researched"`. (التدفق الخاص بالمحرك existant picks it up
   تلقائيًا — لا حاجة لتدفق nouveau ما لم يكن المحرك selbst missing.)
4. **ضع ملاحظة بحث قصيرة** في
   `operations/frp/devices/<brand>/<model>.md` مع الشريحة، المحرك، القسم،
   build fingerprint، وстрока one-liner confirming recipe
   (e.g. « mmcblk0p4 = frp، instant BROM DA erase، no combo »).
   راجع `operations/frp/devices/nokia/nokia_g20.md` للتنسيق.
5. **إذا لم يكن لدى المحرك selbst تدفق** لهذا chipset، سجّل التدفق
   في `src/flows.rs` (строка `flow!(...)`) وأضف dispatch CLI
   في `src/<engine>.rs` + `src/main.rs`.

## لماذا اختفت ملفات per-chip

أعادت refactorings antérieures تقسيم god `frp.py` إلى ملفات per-chip تحت
`operations/frp/chips/` وملفات per-engine تحت
`operations/frp/{mtk,qualcomm,unisoc,samsung}_frp/`. إصدار قديم من
هذا INDEX زعم وجود docstubs ميتة وdispatch `python/core/flows/brom.py`
— هذا module never shipped. dispatch per-chip real هو registry тدفقات Rust
(`src/flows.rs` : lignes `mtk_*`/`qcom_*`/`spd_*`، flow-list للتحقّق)؛
هذا INDEX.md هو خريطة чтобы новый dev знал где يعيش код engine-specific بالفعل.

## لماذا اختفت شیم‌های Python per-engine

`operations/frp/mtk_frp/mtk_frp.py` (و 4 أشقاء) استورد functions من
`python.core.flows.brom` وأعاد تصديرها под **вторым** dict `FLOWS = {}` الذي
GUI لا يقرأ أبدًا. تصادمت с canonique `FLOWS` в `python/core/flows/__init__.py`
وكانت бы маскировать real ones если GUI ever did read them. Replaced with README
в каждом dossier engine который يشير إلى true modules Python.