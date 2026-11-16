# ImproveCore — تحسينات نواة Rust

Language switcher: [English](../../improvecore.md) · [Français](../fr/improvecore.md) · [Español](../es/improvecore.md) · [Deutsch](../de/improvecore.md) · [简体中文](../zh/improvecore.md) · [Русский](../ru/improvecore.md) · [Português](../pt/improvecore.md) · [日本語](../ja/improvecore.md) · **العربية** · [हिन्दी](../hi/improvecore.md) · [Türkçe](../tr/improvecore.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

المصدر: عناصر Rust نُقلت من `ui-improvement.md`.

## ADB flashing per device
- جلسات ADB keyed حسب الجهاز مع retry/backoff وstate machine واضح.
- verify-after-write (hash) by default; تقدم per-partition.
- معالجة قوية لحالات unauthorized/offline; auto re-auth prompt.
- دعم multiple concurrent ADB devices without cross-talk.

## Odin (Samsung) innovation
- تفوق أحدث Odin: single-session resilience، port reset recovery، multi-partition streaming.
- تحقق أفضل لـ PIT، معالجة vbmeta/AVB، إرشاد drk repair.
- Resume/retry على transient USB errors; شروح failures مفصلة.

## BROM / low-level comms
- Unified BROM abstraction لـ MTK، Samsung، SPD، Qualcomm.
- Crash-to-BROM helpers، SLA/auth، DA upload reliability.
- Error classification with actionable fixes; timeouts per stage.

## Latest MTK support
- Preloader V5/V6 parsing و DA selection (`mtk_daloader.rs`).
- تتبّع أحدث إصدارات MTK DA/preloader; auto-detect and select.
- ضمان عمل exploit/SLA paths على أحدث chips; add test fixtures.

## USB interface detection
- Detect CDC ACM، ECM/NCM، mass storage، HID، vendor-specific، diagnostic/modem.
- Detect bootrom، preloader، ADB، download mode، EDL، MTK، SPD.
- Expose interface list in device rows; map to supported flows.

## Instant removal (FRP/MDM/locks)
- Research integration like HiProTool: fast paths where safe, documented.
- Device-specific playbooks in `operations/` with verified steps.
- Keep experimental gating + audit logging for risky ops.