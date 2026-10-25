# ImproveCore — Rust Core Improvements

Source: Rust-related items moved from `ui-improvement.md`.

## ADB flashing per device
- Device-keyed ADB sessions with retry/backoff and clear state machine.
- Verify-after-write (hash) by default; per-partition progress.
- Robust unauthorized/offline handling; auto re-auth prompt.
- Support multiple concurrent ADB devices without cross-talk.

## Odin (Samsung) innovation
- Outperform latest Odin: single-session resilience, port reset recovery, multi-partition streaming.
- Better PIT validation, vbmeta/AVB handling, drk repair guidance.
- Resume/retry on transient USB errors; detailed failure explanations.

## BROM / low-level comms
- Unified BROM abstraction for MTK, Samsung, SPD, Qualcomm.
- Crash-to-BROM helpers, SLA/auth, DA upload reliability.
- Error classification with actionable fixes; timeouts per stage.

## Latest MTK support
- Preloader V5/V6 parsing and DA selection (`mtk_daloader.rs`).
- Track latest MTK DA/preloader versions; auto-detect and select.
- Ensure exploit/SLA paths work on newest chips; add test fixtures.

## USB interface detection
- Detect CDC ACM, ECM/NCM, mass storage, HID, vendor-specific, diagnostic/modem.
- Detect bootrom, preloader, ADB, download mode, EDL, MTK, SPD.
- Expose interface list in device rows; map to supported flows.

## Instant removal (FRP/MDM/locks)
- Research integration like HiProTool: fast paths where safe, documented.
- Device-specific playbooks in `operations/` with verified steps.
- Keep experimental gating + audit logging for risky ops.
