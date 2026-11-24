# سجل التغييرات

Language switcher: [English](../../CHANGELOG.md) · [Français](../fr/CHANGELOG.md) · [Español](../es/CHANGELOG.md) · [Deutsch](../de/CHANGELOG.md) · [简体中文](../zh/CHANGELOG.md) · [Русский](../ru/CHANGELOG.md) · [Português](../pt/CHANGELOG.md) · [日本語](../ja/CHANGELOG.md) · **العربية** · [हिन्दी](../hi/CHANGELOG.md) · [Türkçe](../tr/CHANGELOG.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 1.2.2 (تحديثات تلقائية، 10 لغات، Rockchip + تعدد أجهزة آمن للمودم)

*يدمج ملاحظات دورة التطوير 1.2.2 → 1.3.2 — كل ما أُصدر منذ 1.2.1.*

### التحديثات التلقائية و What's New (جديد)
- التحديثات تُثبَّت تلقائياً: ملف `.deb` المُنزَّل يُثبَّت عبر sudo في الخلفية، يُعاد تشغيل التطبيق، وتظهر عند أول تشغيل نافذة تُستخدم مرة واحدة "ما الذي أُضيف أو تغيّر" تعرض changelog الإصدار الجديد (يبقى مربع الحوار اليدوي "Install Now" عندما يكون التثبيت التلقائي معطلاً في Settings → Updates).

### واجهة بـ 10 لغات + تبديل لغة فوري (جديد)
- الواجهة كاملة تُشحن بعشر لغات إضافية (Français، Español، Deutsch، 简体中文، Русский، Português، 日本語، العربية، हिन्दी، Türkçe): الإعدادات، بلاطات الأجهزة، الصفحات وسلاسل console.
- تبديل لغة الواجهة فوري — بدون إعادة تشغيل؛ التخطيطات تُضبَط على مقاييس الخطوط الحقيقية فتلتف الترجمات الطويلة بدلاً من قص عناصر التحكم.
- فهارس ترجمة JSON مبنية على مفاتيح مع تحقق من التغطية؛ CI يُجري smoke-tests على الفهارس المثبَّتة.

### Rockchip + كشف أذكى (جديد)
- صفحة علامة Rockchip جديدة: عائلة RK28xx–RK35xx عبر وضع fastboot.
- الكشف يُعرِّف الموديل والعلامة وشكل العامل — وليس الشريحة فقط.
- كل مرحلة تفليش تُلتقط (TFT parity): MediaTek BROM/preloader/DA عبر كامل مجموعة stage PIDs وOEM VIDs (بما فيها preloader VCOM 0x2000/0x2001)، وعائلة Qualcomm EDL download-PIDs الموسَّعة، واتحاد SPD download-PIDs، وQualcomm HS-USB Diagnostics كوضع مُسمّى بذاته.
- شارة الوضع تتبع الجهاز المحدَّد (SELECTED) وتُسمّي بروتوكول USB الفعلي (ADB/MTP/PTP/DIAG/storage/RNDIS) بدلاً من OTHER: فقط flashing PIDs تحصل على تسمية MediaTek low-level، وQualcomm EDL يحتفظ بـ badge chip الخاص، وسقوطا substring‏ 'MEDIATEK'/'download' مُصلَحان.

### Motorola FRP (جديد)
- سلسلة CVE-2016-10277 fastboot FRP، وتوفير QR بتسجيل دخول وهمي عبر own-DPC (TestDPC / Device Policy / Adobe)، وfastboot FRP على مراحل بدورات flash + reboot، ودورة ADB بوضع factory-bootmode.

### مسارات محرك حقيقية (جديد)
- مسارات flash وFRP وlock حقيقية لـ MTK/QCOM/Unisoc/Samsung في نواة Rust.
- odin4 أُزيل: محرك Odin الأصلي في Rust يعالج خط tar كاملاً وPIT وكل فئة مشاكل odin4 المعروفة؛ انتقلت Apple usbmuxd/lockdown إلى Rust؛ النواة Rust فقط (أُزيلت جميع fallbacks الأجهزة/البروتوكولات في Python).

### ADB آمن للمودم (مُصلَح)
- مسارات poll/monitor/display صارت zero-touch (`adb-devices --no-probe`): لا open/claim/handshake من الحلقات — مودمات USB تتوقف عن إعادة التعداد كل دورة (تم التحقق مباشرة: 114 دورة poll هادئة على مودم MSM8916).
- صراعات claim تُفوَّض عبر سُلَّم: native → Rust server transport (serial صريح) → host binary → rescue kill (الملاذ الأخير)، فتنجح عمليات ADB بينما يحتفظ system server بالواجهة.
- إصلاح دمج USB-ADB (تُحلَّل سلاسل الصفوف فتحمل الصفوف فعلاً حالة ADB)، وإنقاذ حامل busy + إعادة محاولة عابرة + حالة busy صادقة، وحرس babble/overflow، وأمر عزل اختبار claim، وقيم CNXN حديثة لـ adb، وتُظهر زوايا QCOM/MTK الـ ADB overlay مثل الفروع الشقيقة.

### موثوقية تعدد الأجهزة (مُصلَح)
- pick مع settle-retry: كل tool runner يعيد المحاولة مرة بعد 2.5 s عندما يخطئ scan عابراً جهازاً يعيد التعداد، بدلاً من الرفض بـ "no device" بينما تُظهر GUI أنه متصل.
- ADB AUTH يُبقي SHA-256 في اللعب عبر جولات token (جولات فردية SHA-256، وزوجية SHA-1)، فلا يتحول توقيع round-1 المفقود إلى "not authorized" زائف؛ `_wait_for_adb` يتسامح مع أخطاء scan عابرة.
- ربط هوية الهدف: يُرفض جهاز مُستبدَل يشغل bus:addr معاد الاستخدام (فحص serial بدون لمس) — الـ transport لا يتبع هاتفاً مختلفاً أبداً.
- تبديل قائمة الأجهزة: إعادة بناء connection-bar تعيد المحاولة عندما يُسقط scan ثانٍ جهازاً، والتبديل بين الأجهزة لا يعود إلى الهاتف الأول، وأدوات ADB ترجع إلى صف ADB daemon عندما يخطئ pick الـ USB ("يظهر connected لكن actions تقول no adb").
- تصنيف الأجهزة + picker: الأجهزة غير المطابقة تُبلِّغ USB بدلاً من تسمية MTP خاطئة، وpick الـ USB الفائت يعرض picker صف الـ daemon ("Run on this device" / "Cancel") بدلاً من الرفض.

### نتائج صادقة وتهذيب GUI (مُصلَح)
- تدفقات FRP تتطلب flags مُتحقق منها وحالة خروج shell حقيقية؛ خروج bridge غير صفري يرفع فشلاً مع ذيل السجل — لا مزيد من toasts "completed" الزائفة.
- GUI: chips jobs لكل صف، ذاكرة نافذة، حد أقصى للـ toast، تنقّل بلوحة المفاتيح، STOP واعٍ بالجهاز (job واحد يلغي ذلك الجهاز)، kg_unlock نُقل إلى worker thread (سلاسل 30 ثانية لم تعد تجمّد النافذة)، splash يتبع البناء الحقيقي، الصفحات المؤجَّلة تبقى قابلة لإعادة المحاولة، الـ toasts تُصفّي الشريط العلوي.

### الأمان والمتانة
- مخارج خاصة افتراضياً، وأسماء مؤقتة مقاومة للـ symlink، وفحوص symlink.
- تحقق بعد الكتابة للـ firmware افتراضياً + بوابة model + إصلاحات رقمية.
- FRP: شهادة توقيع DPC تُقرأ أصلياً وchecksum التوفير مُصلَح.
- حزمة اختبار HIL العتادية: تراجعات multi-device / device-replacement / USB-storm على عتاد حقيقي؛ اختبارات backoff لمراقب ADB صارت حتمية.
- صفحة هبوط عامة (`website/`) مع مصفوفة القدرات وconsole البروتوكولات.

## 1.2.1 (Stable Release)

### Multi-device support (new)
- Plug in several phones: connection bar lists each one (model · serial · transports); click a row to inspect it.
- Every operation asks which phone it applies to when several match (silent when 0–1 match). Console lines carry a `[device-key]` tag.
- One operation per device: different phones can flash in parallel; same phone still serializes. Global STOP broadcasts to all runners.
- Stable identity (`python/core/devices.py`): `adb:<serial>` → `usb:<port-path>` → volatile fallback. Targets are re-resolved before sessions open، so USB re-enumeration no longer orphans a flash (`usb device Fail`).
- Phone-only device list: hubs، HID، webcams and card readers are filtered out.
- New `SPD` transport mode + read-only Qualcomm/SPD detect flows.

### Per-chip EXPERIMENTAL (new)
- Samsung `Knox / Warranty`، Qualcomm `QCN / Modem`، per-chip `IMEI Repair / Change`، `eMMC / UFS` — amber collapsibles on the owning chip page (no global LAB page). Every-run ownership checkbox; IMEI change additionally requires typing `I UNDERSTAND`. Audit-logged; persisted acks never auto-pass (`check_gate_strict`).

### MTK BROM (fixed + improved)
- PID/stage mapping corrected to mtkclient convention (`0e8d:0003`=BROM، `0e8d:2000`=preloader) across Rust، Python، GUI labels، logs and docs.
- New `mtk_crash_brom` bridge command + `MTK crash preloader into BROM` flow (registered under MTK BROM).
- `_wait_mtk_brom_target()` prefers stable held BROM over preloader window; DA discovery refuses truncated (<1KB) binaries.

### Odin / flashing (hardened)
- `_prepare_download_session()`: kernel-driver detach + 3× handshake retry across re-enumeration; all Odin PIDs accepted; PIT cache warmed pre-flash.
- odin4 pinned with `-d /dev/bus/usb/BBB/AAA` + one automatic retry on USB loss; `.tar.md5` trailer anchored to end-of-file (streaming، no full RAM read).
- Native smart flash logs per-partition MB/s + ETA.

### Robustness hardening (review-driven)
- Sahara: HELLO command/version/mode/packet-size validated at parse (was: any ≥32-byte blob trusted); transfer-format self-check now round-trips structs instead of dropping bytes; close failures logged; detach runs before claim; handshake reports transfer/close/reset outcomes in JSON instead of discarding them (reset is explicit and visible).
- ADB auth: capped exponential backoff between token rounds; one-time keygen pause announced instead of looking hung.
- MTK: configured packet size actually reaches the DA session (was computed and dropped; sessions hardcoded 64K)، clamped to 512B–1MB.
- Safety backups: failures print an unmissable banner with elapsed time and a STOP hint (contract unchanged: never blocks the operation).
- Experimental gates: iCloud + Pixel flows migrated to strict per-run acks; GUI ack tokens are now counted per feature with expiry (no cross-feature bleed، no lost acks، no stale authorizations).

### GUI fixes
- Top-bar red borders + button shrink traced to concurrent shake/rubber animations and accent-tinted focus rings: animations serialized with `_anim_lock` + full cleanup; new neutral `focus_ring`/`sel_border` theme tokens (red accents can no longer leak into focus).
- `os.system()` → `subprocess` for bridge rebuild / log-dir open.
- Duplicate SPD "Enable ADB" stub، `fastboot_unlock` experimental mis-gating، dead FUS→AP-slot path، and missing `finished` emit fixed. Removed the dead LAB/Knox/QCN/PAC experimental surface.

### Restructure
- `python/core/frp.py` (god file) → `python/core/core.py` (registry + flows); `frp.py` is now FRP-only. Dead `python/core/flows/` split removed.
- Verb-first job names (`Remove FRP`، `Flash Firmware`، …); one canonical snake_case key per flow; display-name casing normalized.

### Docs
- Fresh screenshots (`docs/samsung.png`، `mtk.png`، `spd.png`)، rewritten README highlights/matrix/layout، CONTRIBUTING architecture + flow rules، this changelog.

### boot.img + AVB (single native engine)
- New image-surgery engine in Rust bridge (`src/imgtools.rs`): Android boot header parse، cpio newc scan، prop patching (pad-in-place or magiskboot-style grow with header rewrite)، deterministic gzip (mtime=0، level 9)، AVB vbmeta flags. `boot-info` / `boot-patch-adb` / `vbmeta-patch` CLI.
- Python `spd_adb` repack + `core._patch_vbmeta_flags` delegate with local fallback (signatures and return contracts unchanged).
- Equivalence work fixed two real bugs: grow splice disagreed with reader's alignment by 2 bytes (corrupting every later entry — both implementations)، and re-patching grew by `\n` each run (both sides now idempotent). gzip bytes intentionally excluded from parity (zlib implementations differ); decompressed content، sizes and fields match.
- 6 Rust unit tests + 9 cross-implementation tests.

### PAC (single native engine + wired GUI actions)
- New SPD PAC engine in Rust bridge (`src/pac.rs`): parse/extract/pack with YGDP layout، shared header/slot builders now also used by `spd-readback` writer (byte-identical output; its historical doubled slot names quarantined، not propagated). `pac-parse` / `pac-extract` / `pac-pack` CLI.
- Python `pac.*` delegates with local fallback; new `flow_pac_extract` / `flow_pac_pack` (file-only، ofp-style env inputs) registered in FLOWS and mapped in GUI dispatcher — previously dead PAC buttons now run.
- Equivalence tests caught and fixed a real bug: local packer silently dropped product string (slice-copy write); plus u32 overflow guards with identical messages on both engines.
- 5 Rust unit tests + 7 cross-implementation tests (roundtrips both directions، sanitize parity incl. dir collision، error mapping).

### PIT (single native engine)
- New Samsung PIT engine in Rust bridge (`src/pit.rs`): parse (28/132 layout)، header/model strings، name normalization، find، overlap scan، forensic validation + health verdicts — byte-identical messages، summaries and verdicts to Python implementation on real dumps and edge cases (including Python-`repr` parity for junk names).
- `pit-parse` / `pit-health` / `pit-find` / `pit-overlaps` / `pit-model` CLI; Python `pit.*` raw-bytes paths delegate with local fallback when binary absent (contracts preserved: ValueError/None/never-raise). In-memory object paths and display helpers stay local and fast; shared rules pinned by 11 cross-implementation equivalence tests.
- 8 Rust unit tests (layout vectors، normalize table، meta overlap classification، summary/human-size shapes).

### ADB (native transport, no platform-tools)
- New native ADB client in Rust bridge (`src/adb.rs`): USB transport (255/66/1) with kernel-driver detach، CNXN handshake، RSA-SHA256/SHA-1 AUTH (reuses `~/.android/adbkey`، generated when missing)، `shell:` and `sync:` (STAT/RECV/SEND) services.
- `adb-devices` keeps `adb devices -l` line contract from native scan (`device` / `unauthorized` / `no permissions`); `adb-shell` takes a serial (`-` = first authorized)، plus new serial-pinned `adb-pull` / `adb-push`.
- Python: `bridge.adb_shell()` resolves explicit > ambient-scope > first authorized serial (multi-device ADB is now target-pinned); `adb.py` delegates to the bridge; EFS backup/restore pull/push go through the bridge instead of unpinned system `adb` calls. `has_adb()` now means "bridge built".
- 6 Rust tests (framing، banner، PKCS#1 sign/verify، DER roundtrip، bit-identical pubkey blob vs system adb's key) + 9 Python tests.

### Fastboot (native transport + Motorola universal)
- New native fastboot USB transport in Rust bridge (`src/fastboot.rs`): `fastboot-devices` (JSON) + `fastboot-cmd <vid:pid@bus:addr> <ms> <cmd…>` for command phase (getvar/oem/erase/reboot) with kernel-driver detach. Device-side FAIL renders as `FAILED (remote: …)` with exit 0، matching system binary's transcript shape (including lone `getvar` values that ride in the OKAY packet on Moto MBM bootloaders).
- Shared Python helpers (`_fastboot_run`، `_wait_fastboot`، `_fastboot_getvar`) are native-first with system-binary fallback; DATA-phase commands (flash/boot/…) always use system binary، and host-side `devices` listing is served from native detect. All fastboot traffic is now target-pinned (`vid:pid@bus:addr`)، closing no-`-s` wrong-phone hazard.
- New brand-wide Motorola flows (`moto_frp_adb`، `moto_frp_fastboot`، `moto_oem_unlock_token`): ADB provisioning reset، official unlock-token flow with lock-state read + session resets، read-only token reader. Shown under Motorola → All Motorola / Lenovo (universal) and every Moto model; unlock portal URL corrected (old `motorola.com/unlockbootloader` is dead).
- `python/core/fastboot.py` (Pixel) and `usb_watch.py` (lsusb scraping) moved onto the bridge; 7 new `tests/test_fastboot_native.py` tests.