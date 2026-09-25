# FlashPilot — Full Engineering Audit, Architecture Review & Remediation Plan

**Date:** 2026-09-23 (UTC)
**Scope:** `.` — Rust core (`src/`, ~13k LOC), Python layer (`python/`, core + PyQt6 GUI), operations docs, `tests/`
**Method:** read-only audit of every protocol, identity, bridge, GUI, and test file; parallel deep-dives; first-hand verification of critical findings; empirically reproduced 2 Rust panics; ran `cargo check`, `cargo test` (129 pass), `pytest` (233 pass, 4 skipped).
**Working-tree state:** 8 files have **uncommitted changes** (+740/−82) that are active remediation work. All line numbers below reflect the working tree unless noted (`HEAD` = last commit `3ef51f5`).

---

## 0. Executive summary

FlashPilot is a Linux-native flashing suite: a Rust CLI binary (`flashpilot-bridge`, ~100 subcommands) that speaks raw USB protocols (ADB, Fastboot, Samsung Odin/Download, MTK BROM/DA, Qualcomm Sahara/Firehose, SPD BSL, Apple usbmuxd/lockdown), driven by a Python layer (`FLOWS`/`JOBS`/`MODES` registry + bridge subprocess wrapper) and a PyQt6 GUI (~12.7k LOC).

**What's already good (verified):**

- The Rust core is genuinely the protocol authority: native USB ADB, native fastboot, native Odin/MTK/QCOM/SPD engines. Recent migrations (Python→Rust detection merge, odin4 removal, native ADB) are directionally correct.
- Device identity is serial-first: stable keys `adb:<serial>` → `usb:<port-path>` → volatile `vid:pid@bus:addr` last resort, computed atomically in Rust (`src/usb/filtering.rs:116-146`) and mirrored in Python (`python/core/devices.py:97-124`).
- The process model gives *accidental* session isolation: one Rust process per command, fresh `rusb::Context` per open, zero `unsafe` blocks in `src/`, no global USB-handle registry. Concurrent flashes against different devices do not share buffers.
- Test suites are real and passing: 129 Rust unit tests (parser/codec/geometry/parity pins) + 233 pytest tests (flow framework, PIT/PAC/boot parity, ADB-native behavior, safety gates).

**What's broken or missing (the audit's load-bearing findings):**

1. **No DeviceProfile, no CapabilityDetector, no ActionRegistry exist anywhere** (verified by repo-wide search). The GUI builds static brand-driven pages at startup; FRP/MDM/screen-lock tabs render regardless of what is connected. `flow_for(job, mode, method)` (`python/core/core.py:9977-9978`) **ignores job and mode entirely**. The backend never validates that a flow matches the device's chipset/mode — the central P0 architecture gap.
2. **First-device fallbacks everywhere:** Rust `pick_target("-") → targets.remove(0)` (`src/adb.rs:1101-1104`); Python `_resolve_adb_serial` → first authorized → `"-"` (`python/core/bridge.py:798-820`); `fastboot.py:47-48` `devs[0]`; MTK/Qualcomm `"auto"` = first device (`src/mtk_da.rs:902-908`, `src/qualcomm/mod.rs:22-27`); chip-page GUI runners hardcode `"auto"` with no device scope (`python/gui/qt_app.py:5730,5799,5836-5837,6345`); battery/network tools take `auth[0]` (`qt_app.py:11944-11950`). Any of these can operate the wrong phone with 2+ devices attached.
3. **`FirehoseResponse::is_success()` always returns `true`** (`src/qualcomm/firehose.rs:157-170` — `value`/`error` hard-coded `None`; the device's real `value="FAIL"` attribute sits unread in the generic map). A failed EDL program/erase is silently reported as success. **Fix before any production Qualcomm flashing.**
4. **USB address-churn (§33) has 4 confirmed root causes** (see §24): CNXN probe storm from the 3s monitor; `adb kill-server` fired from the poll path; babble→port-reset from undersized URBs (already fixed in `be8fad3`); bus:addr-as-identity + scan/open TOCTOU. Working-tree changes already mitigate 1–3; only 4 needs architecture work.
5. **Panics on malformed input (empirically reproduced):** `mtk-crash-brom 5` → index-out-of-bounds at `src/main.rs:486`; `bulk-send 04e8:685d@2 aa` → panic at `src/bulk.rs:191`. Both are unguarded `loc[1]` indexing reachable from any Python caller.
6. **Device-controlled unbounded allocations** (4 GiB → allocator abort): MTK SLA challenge (`src/mtk.rs:445-446`), Sahara `read_memory` (`src/qualcomm/sahara.rs:383-386`), Firehose configure sizes (`src/qualcomm/firehose.rs:243-251,343,390`), GPT entry math with overflow (`src/qualcomm/gpt.rs:58-61`, confirmed first-hand).
7. **Two desynchronized cancel registries** (`python/core/flow.py` vs `python/core/bridge.py`); GUI STOP is broadcast-only (`qt_app.py:12319-12339`) — stopping one device's job stops *all* devices' jobs despite per-key infrastructure existing.
8. **Tar extraction path traversal:** Rust `fwtar.rs:171` (`out_dir.join(&name)`, no `..`/absolute guard) and Python `flashing.py:85-86` (`tarfile.extractall` without `filter=`) — a malicious firmware archive escapes the staging dir.

**Verdict:** the Rust core is the right backend foundation and the multi-device *plumbing* (stable keys, per-device locks, process isolation) is half-built, but the *architecture* the request demands — identity→profile→capabilities→actions→isolated job→validated execution, enforced by the backend — does not yet exist. §28–§29 give the phased remediation; the good news is the process model already provides session isolation, so Phase 0 is bounded bug-fix work, not a rewrite.

---

## 1. Current architecture & data flow (Deliverable 1)

```
PyQt6 GUI (python/gui/qt_app.py, ~12.7k LOC)
  │  bare daemon threads per operation (43 spawns; no QThread)
  │  display-only device list (DeviceMonitor 3s poll + change-detect rebuild)
  ▼
Python core (python/core/)
  ├── flow registry: FLOWS / JOBS / MODES (core.py, static globals)
  ├── devices.py: stable keys, resolve_usb_target, device_scope (ContextVar)
  ├── bridge.py: subprocess.Popen([bridge, *args]) per call; per-key cancel events
  └── protocol helpers: adb.py fastboot.py mtp.py mtk.py fus.py flashing.py ...
          │  argv: "vid:pid@bus:addr" | "bus:addr" | "auto" | serial | "-"
          ▼
Rust bridge (src/main.rs, ~100 subcommands, sync single-threaded CLI)
  ├── usb/mod.rs: collect_devices (fresh rusb scan/call), open(vid,pid,bus,addr)
  ├── usb/filtering.rs: is_phone / device_key / classify_mode / merge_devices
  ├── devices.rs: detect-merged rows (DeviceRow: key/label/transports/vid/pid/bus/addr/serial)
  ├── adb.rs / fastboot.rs: native USB sessions (one session per process)
  ├── sam_download.rs (+ agent multiplexer) / mtk*.rs / qualcomm/* / spd.rs / apple.rs
  └── error.rs: BridgeError (NO device identity context) → "error: {e}" on stderr
          │  Python re-classifies by SUBSTRING matching on stderr text
          ▼
GUI console (single shared log; only a "[device_key]" text prefix per device)
```

Synchronous single-threaded CLI: `tokio = "full"` and `async-trait` are declared (`Cargo.toml:18-19`) but have **zero uses** — dead dependency bloat. `clap` is declared but unused; parsing is a hand-rolled `match` (`src/main.rs:137-1126`) with **no `#[cfg(test)]` coverage**.

---

## 2. Device identity flow (Deliverable 2)

Key priority (Rust `filtering.rs:116-146`, Python `devices.py:97-124`, identical):

```
ADB serial (normalized)        →  "adb:<serial>"
USB serial  (normalized)       →  "adb:<serial>"   (merges USB+ADB views of one phone)
USB port path (stable)         →  "usb:<port-numbers>"
LAST RESORT (volatile)         →  "usb:<vid>:<pid>@<bus>:<addr>"
```

- Normalization drops `""`, `null`, `none`, `unknown`, `?` (`filtering.rs:66-73`).
- **Gap A:** USB `DeviceInfo` carries no persistent field at all (no struct has manufacturer/model/chipset/mode — only `mode: String` display hint). There is no `StableDeviceIdentity` type distinct from `CurrentTransport` (bus/addr) or `ProtocolSession`.
- **Gap B:** missing-serial ADB devices become the literal `"unknown"` (`src/adb.rs:959`); two serial-less devices are indistinguishable and `pick_target("unknown")` can hit either.
- **Gap C:** merge is per-scan, stateless. Reconnect (A→B at same bus:addr) is resolved only by re-keying — no revalidation that the *serial* behind a `usb:<ports>` key is unchanged (device-swap on the same port inherits the key).

---

## 3. USB transport lifecycle (Deliverable 3)

1. **Enumerate:** every call does a fresh `rusb::Context::new()` + full bus scan (`collect_devices`, `usb/mod.rs:419-543`). String descriptors are read by briefly `device.open()`-ing **every** device (lines 487-506) — transient contention with concurrent flashes is possible but benign on Linux.
2. **Open:** `UsbDevice::open(vid,pid,bus,addr)` (`usb/mod.rs:82-93`) matches descriptor VID/PID **and** bus **and** address in one scan. **TOCTOU window:** scan at `collect_adb()` → open later per target; a re-enumeration in between can put a *different* (same-VID:PID) device at that address.
3. **Claim:** per-protocol (Samsung: evict-all + config-1 + 4× claim retry, `sam_download.rs:255-294`; Sahara: detach-before-claim — correct order; Firehose: claim-**before**-detach — wrong order, `firehose.rs:196-197` vs `sahara.rs:230-234`).
4. **Session:** one session per process; no pooling; no handle registry (verified — inventory in §9).
5. **Teardown:** implicit `Drop` everywhere except SPD (`SpdSession` has an explicit `Drop`, `spd.rs:190-194`). Cancel/timeout = SIGTERM→(1.2s)→SIGKILL of the whole process (`bridge.py:213-234,286-293`) — potentially mid-chunk, mid-partition. `clear_halt` exists for the wedged-endpoint aftermath (`usb/mod.rs:248-253`) but only `adb.rs:1007` calls it.
6. **Re-enumeration:** Python re-resolves targets per command (`fastboot.py:68`, `core.py:1846`); `resolve_usb_target(key)` re-scans then formats fresh `vid:pid@bus:addr` (`devices.py:192-215`); `wait_for_usb_reenumeration`/`wait_for_mode_switch` poll `detect_all()` for VID (`bridge.py:956-991`) — VID-only matching can re-attach to the wrong one of two identical phones.

---

## 4–6. DeviceProfile / CapabilityDetector / ActionRegistry (Deliverables 4–6) — DO NOT EXIST

Repo-wide search for `CapabilityDetector|DeviceProfile|ActionRegistry|capability` returns **nothing** in `python/` or `src/`. Consequences (all verified):

- GUI action buttons are static, built at startup per brand/chip page (`qt_app.py:2392-2407,2430-2466`); the drill-down uses a hard-coded brand `if/elif` (`python/gui/devices.py:259-331`); the per-model `"actions"` array in `supported_devices.json` is **dead data** (never read).
- FRP REMOVE is offered for every non-Apple brand including the generic `else` branch (`devices.py:312-317`); chip pages embed FRP/MDM/screen-lock tabs gated only on *registered-flow existence for static mode names* (`qt_app.py:3220-3227`), never on the connected device.
- `flow_for` ignores job and mode (`core.py:9977-9978`); `modes_for` returns all 9 modes for every job (`core.py:9966-9969`). There is no per-device flow filtering anywhere.
- Generic destructive ops (factory reset, FRP, screen lock, MDM, slot flash) are **GUI-confirm-only** (`_DESTRUCTIVE_CONFIRM`, `qt_app.py:290-368`); only EXPERIMENTAL flows are backend-enforced (`check_gate_strict`, `experimental.py:220-237`).
- **Required fix** (§28, Phase 1): implement `DeviceProfile` + `CapabilityDetector` + `ActionRegistry` in the Rust core and expose one query (`detect-merged` already returns transports; add `actions-for <key>` returning the validated action set); the GUI must render *that* set.

---

## 7. Protocol/session architecture (Deliverable 7)

Process-per-command (`main.rs` single-threaded `match`). Each session struct owns a fresh `Context`+`DeviceHandle`; progress is per-session. Sessions cannot leak across devices by construction — **but** `"auto"` target resolution (MTK `mtk_da.rs:902-908`, Qualcomm `mod.rs:22-27`) picks `devices[0]`, and chip-page GUI runners hardcode `"auto"` unscoped, so the *wrong device's* session can be opened deliberately.

Notable protocol facts:

- **Samsung:** open by vid+bus+addr (PID not in initial find, `sam_download.rs:173-176`; re-verified at open `235-245`). Documented "re-resolve by stable port path" (`sam_download.rs:9-10`) is **not implemented** — still pins bus:addr. Sessions: handshake `ODIN→LOKE`, PIT dump with `PIT_MAX_BYTES` guard + streaming fallback, per-chunk ACKs (5× retry), `is_last=1` only on true-final partition, `odin-agent` multiplexer for one-session-per-plug firmwares. **Stale-PIT bug:** `AGENT_PIT: OnceLock` (`sam_download.rs:1153`) first-write-wins; a second `pit-dump` is silently not cached (`1197`), later `flash` uses the stale table (`1269,1326`).
- **MTK:** `brom_handshake` (5 sync rounds), DA upload with checksum gating, kamakiri2 exploit path, crash-preloader-to-BROM flow. `mtk_exploit::read_chip` deliberately holds the interface (`mtk_exploit.rs:393-397`) vs `mtk::read_report` releasing (`mtk.rs:785`) — implicit, regression-prone. DA writes have **no ACK retry** (`mtk_da.rs:367-373`).
- **Qualcomm:** Sahara handshake validates Hello (version≥2, known mode, non-zero max-packet). **Programmer is never transferred:** `qcom_firehose_start` reads the file for metadata then opens Firehose directly assuming the device already runs it (`mod.rs:120-167`; `handle_image_transfer` is a no-op self-check, `sahara.rs:417-485`). **Every Firehose command is single-shot, no retries; no post-write verification by default** (`qcom_verify_part_cli` is explicit only). `is_success()` always-true (§0.3), silent-zero rawprogram fallbacks (`mod.rs:382-384`; `firehose.rs:297-301`), unclamped configure sizes.
- **SPD:** strict HDLC validation (`spd.rs:336-342,362-369`); only session with `Drop`; BROM-only path retries handshake 3× (1.5–2 s window). No post-write verification.
- **Apple:** fully isolated (usbmuxd Unix socket, UDID/DeviceID identity, one-shot connections — no pooling, no Android-path mixing). **Zero socket timeouts** (`apple.rs` never calls `set_read_timeout`; verified) — unbounded block if usbmuxd stalls. iCloud/passcode flows are guide-only / ack-gated.

---

## 8. FlashJob lifecycle (Deliverable 8) — DOES NOT EXIST

There is no `FlashJob` type. The de-facto "job" is a bare daemon thread + `ContextVar` ambient key + per-key `_FLOW_LOCKS` entry + (optionally) a Rust subprocess. Required lifecycle (`ANALYZE→PATCH` item, §28):

```
create(job_id, stable_identity) → resolve transport → detect state →
validate target+capabilities → open protocol session →
execute → verify → release session → archive logs
```

with revalidation triggers on USB connect/disconnect/re-enumeration, ADB→bootloader, and protocol transitions. One op per device is enforced today (`_FLOW_LOCKS`, `qt_app.py:214-285`) but progress/logs/cancel are not per-job (console-global, broadcast STOP).

---

## 9. All global/shared device state (Deliverable 9)

**Rust (`src/`):** exactly two process globals — `CANCEL_FLAG: AtomicBool` (`error.rs:239`; `request_cancel` dead code, sole reader `sam_download.rs:139`) and `AGENT_PIT: OnceLock<Vec<u8>>` (`sam_download.rs:1153`; stale-PIT bug). Static SLA key table is immutable. Temp names are PID-keyed. **No session/transport/handle registry exists — verified.**

**Python:** `_current_key` ContextVar (`devices.py:34-36`, per-thread — safe); `_cancels` dict + `_cancel` event (`bridge.py:143-145`) and a **second, desynchronized** pair in `flow.py:10-12` (GUI Stop trips the bridge registry; flow `FlowCancelled` checks never see it — flows abort only via `BridgeCancelled` from the killed subprocess); `_odin_probe_lock` (single global probe lock); `_FLOW_LOCKS` (per-device run guard); GUI `_display_key` + `_cached_*` strings; `_last_spd_target` (stale-able, `qt_app.py:7847`); static `FLOWS`/`JOBS`/`MODES`.

---

## 10. Everywhere USB bus/address is stored or used (Deliverable 10)

Identity-ladder last resort `usb:<vid>:<pid>@<bus>:<addr>` (`filtering.rs:139-142`, `devices.py:124`); `DeviceRow.bus/address` echoed to every GUI row (`devices.rs:67-69`, re-adapted `devices.py:147-156`); all Rust protocol opens key on bus:addr (`UsbDevice::open`, `parse_target` `usb/mod.rs:582-605`, `find_mtk_dev` `mtk_da.rs:900-914`, `find_spd_target` `spd.rs:1473-1479`, `resolve_qcom_device` `mod.rs:17-36`, `parse_full_target` `fastboot.rs:87-110`); Python resolvers format fresh `vid:pid@bus:addr` per call (`devices.py:210-212`); GUI `_last_spd_target = f"{bus}:{address}"`; `wait_*` helpers re-scan by VID. No component treats bus:addr as permanent *identity* in the key ladder — the exposure is all in the transport/target layer, which must be re-resolved per session (mostly is, except cached GUI targets and `"auto"`).

---

## 11–12. ADB / Fastboot device targeting (Deliverables 11–12)

**ADB:** native USB protocol (no platform-tools for data); enumeration merges system-server rows (TCP `127.0.0.1:5037`, `adb.rs:854-900`) by serial with native USB probes. Every `adb-shell/pull/push` passes argv serial → `pick_target` (`adb.rs:1096-1109`): **empty/`-` → `targets.remove(0)` (first device)**. Python resolution is explicit>ambient>first-authorized>`-` (`bridge.py:798-820`); `adb.py` delegates pass **no serial** (`connected_serial` = first authorized, `adb.py:14-18`). Per-command fresh process; retry loop (4×, linear backoff) re-resolves address at the Rust layer per attempt; pull/push have no retry. Busy-holder kill-server exists but is being moved out of poll paths (working tree).

**Fastboot:** Rust requires full `vid:pid@bus:addr` with **no first-device fallback** (`fastboot.rs:87-110,224-232`) — correct. Python re-resolves per command but falls back to `devs[0]` (`fastboot.py:47-48`) and first-match (`core.py:1801`). Fresh USB session per command; `FB_CMD_MAX=64`, `FB_MAX_PACKETS=128` (§opaque caps are documented). **DATA phase deliberately unimplemented** (`fastboot.rs:186-190`); `core.py` routes flash/boot to the system binary (`_FB_DATA_CMDS`, `core.py:1706`) — but `fastboot.py:201-210`'s factory-flash fallback calls `_run_fastboot(["flash",…])`, which can **never succeed** (native-only + DATA rejected). Post-reboot-bootloader re-enumeration is picked up by per-command re-resolution; Moto flakiness is papered with fixed sleeps (`core.py:1935-1948`).

---

## 13–17. Protocol implementations (Deliverables 13–17)

Covered in §7. Test hooks: Samsung PIT regression tests (`sam_download.rs:2121+`), MTK mtkclient-parity vectors, SPD CRC/transcode tests, Firehose XML builders. Known HIL gaps: no test proves cross-protocol isolation; Qualcomm programmer-transfer unimplemented; MTK DA-write no-retry; Qualcomm no-retry anywhere.

---

## 18–20. FRP / MDM / screen-lock workflow mapping (Deliverables 18–20)

- **FRP:** registry `JOBS["Remove FRP"]` (`core.py:9818-9827`) lists ADB/MTP/download/BROM/EDL flows statically; GUI shows FRP for every non-Apple brand page (`devices.py:262-265,293-297,312-317`), Samsung UNLOCK tab (`qt_app.py:2742`), chip-page FRP tabs (`qt_app.py:5274-5278,6113-6117,7591-7595`). Runtime routing picks `methods[0]` or prefers authorized-ADB (`qt_app.py:4005-4032,4100-4107`). **Android ≠ FRP-capable is not enforced anywhere; Apple-brand isolation is page-only.** Backend gates: none (confirm overlays are GUI-side, `adb_frp`/`frp_browser`/`frp_settings` in `_DESTRUCTIVE_CONFIRM`).
- **MDM:** Tecno-only in drill-down (`devices.py:266-269`); global static tabs in Samsung hub (`qt_app.py:2743`) and chip pages (`qt_app.py:3207-3209`); registry `core.py:9902-9918`. No device-capability representation.
- **Screen lock:** registry `core.py:9728-9735,9828-9842` (ADB/locksettings/download/CSC/recovery/EDL/comprehensive); Apple has no lock group — only guide-only `flow_apple_passcode_guide` (`apple.py:162-212`, "Never writes to the device") — good separation, but the Samsung-hub SCREEN LOCK tab (`qt_app.py:2745`) renders Android flows regardless of connection. All are GUI-confirm-gated, none backend-validated.

---

## 21. Device/chipset/action compatibility matrix (Deliverable 21)

No matrix exists (static `JOBS` is a job→mode→flow-name map with no device dimension). Required matrix (Phase 1): Manufacturer × Model(+variant) × Chipset × Platform × Current boot mode × USB interface × Protocol × Capability ⇒ allowed `action_id`s, enforced in Rust (`actions-for <key>`), with negative tests proving e.g. Samsung+Download ⇒ Samsung actions only (no MTK/EDL/Apple/FRP-inapplicable), Apple+Recovery ⇒ no Android FRP/Samsung/MTK/EDL, and that hand-sent unsupported actions return `ACTION_NOT_SUPPORTED` siblings (`WRONG_PLATFORM/MANUFACTURER/CHIPSET/BOOT_MODE/PROTOCOL`, `DEVICE_CHANGED`, `TRANSPORT_INVALID`, `SESSION_INVALID`).

---

## 22. Python→Rust bridge entry points (Deliverable 22)

`bridge._run` (`bridge.py:237-251`): `Popen([bridge_path, *args])`, **no shell anywhere** (only `os.system` in repo is a constant `which gio`, `mtp.py:411-412`); list-args throughout, so injection risk is nil at this layer. ~100 Rust subcommands (`main.rs:137-1126` enumerated during audit). Gaps: JSON wrappers lack `try/except` (raw `JSONDecodeError` escapes the taxonomy); `flashpilot_BRIDGE` env override unvalidated; stderr-substring re-classification (`bridge.py:111-136`) loses device context (errors carry none — `error.rs`); `odin_model` is the only serialized call (`_odin_probe_lock`); drainer join can add ~60 s on wedged pipes (`bridge.py:302-303`).

---

## 23. GUI-worker-Rust state flow (Deliverable 23)

Button → `_dispatch`/`start_model_action` (`devices.py:572-596`, `qt_app.py:3854-4119`) → `_run_ops_flow` or `_run_job_flow` (keyed runners: `_choose_device` dialog only when >1 candidate, per-key lock, per-key `clear_cancel`, `device_scope`, `flow.run`, `threading.Thread(daemon).start()` at `qt_app.py:12515-12536,12710-12732`) **vs** unscoped chip-page direct runners (`_mtk_run:5315`, `_qc_run:6173`, `_spd_run:7638`, `_spd_flash_run:8230`, native flash, battery/network) that run in the `__global__` bucket with `"auto"` targets. Monitor: 3 s daemon thread (`detect_all` + gated ADB probe) + 3 s QTimer, change-detected rebuild keeping the inspected key (`qt_app.py:10677-10693,10702-10704`). Progress is console-global (`[device_key]` prefix only); no per-row bars. Disconnect mid-op is not proactively cancelled — flows fail at next bridge call with coached errors (`qt_app.py:12538-12659`).

---

## 24. USB address-churn bug: reproduction, root causes, fixes (Deliverable 24–25)

**Symptom:** connecting devices makes the USB address "change rapidly"; phones flap connected/disconnected.

**Reproduction (no hardware needed for 3 of 4):**

1. *Probe storm:* monitor polls `adb_status()` every 3 s; each poll opens a native CNXN handshake. On phones whose adbd resets its USB function on our CNXN, every poll re-enumerates the phone at a new address; dry-streak retries compound it until the phone drops off the bus.
2. *Poll-path kill-server (HEAD behavior):* `adb_devices()`/`adb_status()` called `_free_adb_interface("busy")` → `adb kill-server` on every 3 s poll → adbd USB-function reset → new address every cycle. (Working tree removes this; `rescue=False` for polls, kill only for user-initiated `adb_shell`.)
3. *Babble→port-reset:* any URB smaller than the endpoint MPS receiving a full MPS packet makes the host controller flag BABBLE → PORT RESET → device re-enumerates (EIO). Fixed in `be8fad3` (MPS-sized URBs always, `usb/mod.rs:304-319`).
4. *Identity-layer churn:* bus:addr cached or used as lookup (GUI `_last_spd_target`; `"auto"` first-match; scan→open TOCTOU between `collect_adb()` and `UsbDevice::open`; server-row staleness `adb.rs:1050-1054`; monitor ghost-row retention `qt_app.py:584-587`).

**Affected components:** `python/gui/qt_app.py` (DeviceMonitor poll, `_adb_overlay` starvation — fixed in tree), `python/core/bridge.py` (poll-path rescue — fixed in tree), `src/usb/mod.rs` (URB sizing — fixed), `src/adb.rs` (server-row trust, `"unknown"` serials), all `bus:addr`/`"auto"` target paths.

**Minimal safe fixes (remaining):** land the working-tree poll/backoff/rescue changes; add 45 s-scale probe backoff tests; replace `"unknown"` with per-transport synthetic keys; make `wait_for_usb_reenumeration` match VID+PID+serial/port; never cache `bus:addr` in GUI state (re-resolve per use). Do **not** hide churn by debouncing the display — the storm sources above are the fix.

---

## 26. Multi-device targeting root causes (Deliverable 26)

The `"auto"`/first-device/`"-"` fallbacks (§0.2, §11–12) plus unscoped GUI runners (§23) plus per-command re-resolution without identity revalidation (device-swap on one port inherits the key, §2 Gap C). Fix order: (1) make `"-"`/empty-target an error when >1 candidate exists (Rust + Python); (2) delete `connected_serial` first-device default or scope it; (3) require explicit targets for `mtk-frp*`/`qcom-frp-reset` (GUI already knows the key — pass it); (4) wrap all chip-page runners in `device_scope`; (5) resolve-then-freeze `(identity, transport, session)` per FlashJob instead of re-resolving per command.

---

## 27. Incorrect action placement root causes (Deliverable 27)

Static brand-page UI + `flow_for` ignoring job/mode + zero capability dimension anywhere (§4–6, §21). Fix = Phase 1 capability architecture, not more `if brand` branches.

---

## 28. Minimal safe fixes (Deliverable 28, ordered)

**Phase 0 — safety, no architecture (land first):**

1. `firehose.rs:157-165`: populate `value`/`more`/`error` from the response attributes; make `is_success()` require `value=="ACK"`/absence of FAIL; add regression test with a `value="FAIL"` transcript.
2. Panics: guard `loc[1]` (`main.rs:486`, `bulk.rs:68,191`) — reuse `fastboot::parse_full_target`-style validation, exit 2, add CLI tests.
3. Clamp device-controlled sizes: MTK SLA challenge (`mtk.rs:445-446`, cap e.g. 4 KiB), `brom_register_access` length (`mtk.rs:519`), Sahara `read_memory` (`sahara.rs:383-386`, cap by `max_packet_size`), Firehose configure (`firehose.rs:243-251` + buffers `343,390`), GPT math (`gpt.rs:58-61` → `checked_mul`/`checked_add` + bounds, keep the existing panic-regression test style).
4. First-device defaults: error on ambiguity (>1 candidate) instead of `targets.remove(0)` / `"-"` / `devs[0]` / `"auto"`.
5. Tar traversal: reject `..`/absolute members in `fwtar.rs:171`; `filter="data"` in `flashing.py:85-86`; predictable `samsung_pit.bin`/`samsung_dev.pit` temp names → `mkstemp`.
6. `AGENT_PIT`: replace `OnceLock::set`-and-ignore with re-cache-or-version semantics (`sam_download.rs:1197`).
7. Rawprogram/XML strictness: reject non-numeric sector/count instead of `unwrap_or(0)` (`mod.rs:382-384`, `firehose.rs:297-301`); validate `mtk-reboot` mode and SPD `fdl2_addr` (no silent 0).

**Phase 1 — backend-authoritative architecture (P0):** `StableDeviceIdentity`/`CurrentTransport`/`ProtocolSession` + `DeviceManager`; `DeviceProfile`; `CapabilityDetector`; `ActionRegistry` (`actions-for <key>` CLI; GUI renders only that set); `FlashJob` lifecycle with per-job transport/session/cancel/logs; structured errors carrying identity; unify the two cancel registries; per-device STOP. Migrate one protocol at a time behind the last-known-good behavior + new regression tests per §29–31 (per the request's ANALYZE→REPRODUCE→ISOLATE→PATCH→TEST→REVIEW→STRESS method).

**Phase 2 (P1):** Apple socket timeouts; Sahara short-read length validation (`sahara.rs:321-324,343-346,369-372`); Firehose claim/detach order; fastboot DATA phase in Rust (removes the system-binary dependency and fixes the dead `fastboot.py:201-210` fallback); `clear_halt` wired for flashing protocols; reconnect/re-enumeration semantics per job.

**Phase 3 (P2):** structured logging with `(timestamp, job_id, device identity, protocol, transport, mode, action, partition, result)`; dead-dep removal (tokio/async-trait/clap-or-use-it); `Session.ctx` wiring or removal; ghost-row/dry-streak hardening.

---

## 29–31. Regression tests: existing, missing, required (Deliverables 29–31)

**Existing (all passing, verified 2026-09-23):** `cargo test` 129 passed (packet codecs, PIT/PAC/boot parity, MTK/mtkclient vectors, SPD CRC/patch bounds, Sahara HELLO validation, ADB crypto); `pytest` 233 passed / 4 skipped (flow framework, run-guard, per-key cancel *events*, serial pinning *mock-level*, ADB-native poll/rescue behavior, PIT/PAC/boot Rust↔Python parity, ODIN safety gates, experimental ack gates). `cargo check`: 6 warnings (all from uncommitted new code; README's "0 warnings" is stale until the tree lands clean).

**Missing (must add):** device-replacement at same bus:addr; re-enumeration helpers (`bridge.py:956-991` untested); cancel-kills-right-subprocess (process-level, incl. orphans/`BridgeTimeout`); cross-protocol isolation (co-run MTK+Samsung+QCOM mocks, assert no cross-target); capability/action-matrix negatives (incl. hand-sent unsupported action ⇒ rejection); `main.rs`/`bulk.rs` arg-parsing panics; concurrent `_run` contention beyond `odin_model`; `=`-splitting edge cases.

**Hardware-gated (could not run here — no devices attached):** 1–5-device matrices, cross-protocol simultaneity (A=Samsung-DL, B=MTK-BROM, C=EDL, D=fastboot, E=ADB), disconnect/reconnect/cancel-one-continue-others, address-change-during-flash, ADB-server-restart-during-poll. Provide as `tests/test_multidevice_hil.py` (skipped without `--hil` + udev) plus the unit-level simulations above, which *can* run in CI today.

---

## 32–37. Protocol/FLOW mappings & matrices (Deliverables 32–37)

- §7 + §18–20 give the per-protocol and per-workflow maps with file:line anchors.
- The enforced matrix does not exist yet — §21 defines its axes and required negative cases; §28 Phase 0.4 + Phase 1 implement it.
- Bridge entry points: §22 (≈100 subcommands; targeting convention per family: Samsung/fastboot/USB `vid:pid@bus:addr`; MTK/SPD `bus:addr`|`"auto"`; Qualcomm target-scan; ADB serial|`-`).
- GUI-worker-Rust flow: §23. Address-bug repro + roots: §24. Targeting roots: §26. Placement roots: §27.

---

## 38. Security findings by severity (Deliverable 38)

- **High:** Firehose always-success (silent failed flashes, §0.3); device-controlled 4 GiB allocations (MTK SLA `mtk.rs:445-446`, `519`; Sahara `sahara.rs:383-386`; Firehose `firehose.rs:243-251,343,390`); tar path traversal (Rust `fwtar.rs:171`, Python `flashing.py:85-86` fully-trusted `extractall`); unguarded CLI panics reachable from GUI paths (`main.rs:486`, `bulk.rs:68,191`).
- **Medium:** GPT overflow panic from device data (`gpt.rs:58-61`, via `mtk_da.rs:393-400`); silent-zero sector parsing (QCOM XML) risking sector-0 writes; Sahara short-read→Success misparse; stale `AGENT_PIT` flashing against the wrong partition table; GUI-only destructive confirmations (backend executes whatever flow it is handed); no identity in errors + substring re-classification across concurrent devices; Apple unbounded socket I/O; `hex_decode` silently filtering non-hex (`bulk.rs:150-159`) diverging from strict `util::parse_hex`; Python temp-name symlink races (`samsung_pit.bin`, `samsung_dev.pit`); EFS/NV backups world-readable by umask default.
- **Low:** Firehose claim-before-detach; `expect()` on static SLA keys in live path (`mtk_sla.rs:47-49`); `usb-config` `as u8` truncation (`usb/mod.rs:629`); `parse_size` f64 precision loss >2^53 (`util.rs:56-74`); unbounded bulk read allocation from user input (`bulk.rs:122,229`); `zstd::decode_all` without output cap (`fwtar.rs:197-203`); predictable PID-keyed temp dirs (sticky-`/tmp` mitigated).
- **Positive:** zero `unsafe` in `src/`; strict HDLC/PIT/PAC/Apple-frame validation in the good paths; bounded deadline loops in MTK/SPD reads; no shell injection surface (argv-only, no `shell=True`); no secrets/tokens in tree; SLA keys are public mtkclient constants with attribution.

---

## 39. Remaining known limitations (Deliverable 39)

1. No DeviceProfile/CapabilityDetector/ActionRegistry/FlashJob — the architecture gap behind every P0 in the request.
2. Fastboot DATA phase absent in Rust (system binary still required for `flash/boot`).
3. Qualcomm programmer upload unimplemented (assumes device already in Firehose).
4. MTK DA-write and all Qualcomm commands: no retries; Qualcomm: no default verify-after-write.
5. Cancellation is process-kill only (no cooperative mid-command abort; Rust `CANCEL_FLAG` dead).
6. Apple path has no timeouts; `Session.ctx`/config overrides unwired for ADB.
7. HIL multi-device/cross-protocol/replacement tests cannot run without hardware.
8. Uncommitted working-tree changes (+740/−82) are unreviewed remediation — land, test, then proceed per §28.

---

## Appendix — key file:line index
Identity/transport: `src/usb/mod.rs:82-93,240-324,419-543,582-633`; `src/usb/filtering.rs:66-146,174-203,330-366`; `src/devices.rs:36-100`; `python/core/devices.py:34-232`; `python/core/bridge.py:956-991`. ADB: `src/adb.rs:496-506,854-900,944-963,980-998,1033-1109`; `python/core/bridge.py:710-882`. Fastboot: `src/fastboot.rs:87-232`; `python/core/fastboot.py:30-90,201-210`; `python/core/core.py:1740-1803,1846-1902`. Samsung: `src/sam_download.rs:130-296,1153,1197,1269,1660-1781`. MTK: `src/mtk.rs:137-181,440-450,585-667`; `src/mtk_da.rs:219-894,900-914`; `src/mtk_exploit.rs:250-377,751-823`. Qualcomm: `src/qualcomm/firehose.rs:124-170,230-440`; `src/qualcomm/sahara.rs:222-503`; `src/qualcomm/mod.rs:17-36,120-167,352-402`; `src/qualcomm/gpt.rs:47-82`. SPD: `src/spd.rs:190-235,305-372,703-752`. Apple: `src/apple.rs:114-229`. GUI/registry: `python/core/core.py:9676-9978`; `python/gui/devices.py:259-331,572-596`; `python/gui/qt_app.py:214-285,499-637,3854-4119,12319-12732`. Bridge: `python/core/bridge.py:139-317,798-882`. Errors: `src/error.rs:7-245`. Tests: `tests/test_*.py` (14 files); Rust `#[cfg(test)]` in 22 files (none in `main.rs`/`error.rs`/`config.rs`/`bulk.rs`/`at.rs`/`mtp.rs`).

---

## Remediation log — 2026-09-23 (Phase 0, landed in working tree)

Machine-specific paths were also stripped from this report (repo-relative paths only).

| # | Fix | Files | Tests |
|---|---|---|---|
| 1 | `FirehoseResponse::from_xml` now promotes `value`/`more`/`error` out of the attribute map; `FAIL` verdict synthesizes an error from log text; `is_success()` is case-insensitive on FAIL | `src/qualcomm/firehose.rs` | 3 new (`fail_verdict_is_not_success`, `ack_verdict_is_success`, `explicit_error_attribute_fails`) |
| 2 | `loc[1]` panics eliminated (`mtk-crash-brom`, `bulk-send`, `bulk-session`) → clean `InvalidArgument`/exit-2 errors; verified against release binary | `src/main.rs`, `src/bulk.rs` | 2 new (`colonless_bus_addr_is_error_not_panic`, `missing_at_separator_is_error_not_panic`) |
| 3a | MTK SLA challenge capped at 4 KiB; `brom_register_access` capped at 16 MiB | `src/mtk.rs` | — (bounds are pre-alloc; covered by existing handshake tests) |
| 3b | Sahara `read_memory` clamps `resp_len` to requested length; `send_done`/`switch_to_streaming`/header reads reject short reads (were misparsed as Success) | `src/qualcomm/sahara.rs` | existing suite green |
| 3c | Firehose configure sizes clamped to 8 MiB; sector size sanity-bounded | `src/qualcomm/firehose.rs` | covered by ACK test (`MaxPayloadSize…` still reachable) |
| 3d | GPT geometry via `checked_mul`/`checked_add` + `try_from` | `src/qualcomm/gpt.rs` | 2 new (`crafted_lba_overflow_is_error_not_panic`, `crafted_entry_count_exceeding_data_is_error`) |
| 4a | New `DeviceStateError::AmbiguousTarget{count}`; ADB `pick_target`, MTK `find_mtk_dev("auto")`, QCOM `resolve_qcom_device("auto")` reject multi-candidate unscoped targets | `src/error.rs`, `src/adb.rs`, `src/mtk_da.rs`, `src/qualcomm/mod.rs` | 3 new QCOM tests (ambiguous/single/explicit) |
| 4b | `_resolve_adb_serial`: >1 authorized + no scope → `ADB_AMBIGUOUS_TARGET` (single-device and scoped paths unchanged) | `python/core/bridge.py` | 2 new (raises; scoped-still-works) |
| 4c | `_native_target`: >1 fastboot device + no scope → `""` → guided RuntimeError | `python/core/fastboot.py` | existing suite green |
| 5a | `extract_tar` rejects `..`/absolute members → new `FirmwareError::ArchiveError` | `src/fwtar.rs`, `src/error.rs` | 2 new (raw-ustar traversal + absolute rejected; benign nested layout still extracts) |
| 5b | `extractall(filter="data")` + `_safe_extractall` fallback for <3.12 | `python/core/flashing.py` | 3 new in `tests/test_mtk.py` |
| 6a | `AGENT_PIT`: `OnceLock` → `Mutex<Option<…>>`, always-overwrite on re-dump | `src/sam_download.rs` | existing suite green |
| 6b | rawprogram `start_sector`/`num_sectors`/`physical_partition_number`: present-but-non-numeric → error (absent keeps default); device-log partition lines: malformed → dropped, plus `/>`-terminator value fix | `src/qualcomm/mod.rs`, `src/qualcomm/firehose.rs` (+`parse_partition_xml` now associated fn) | 3 new (corrupt-sector error, absent-defaults OK, malformed-dropped) |

**Verification:** `cargo test` 144 passed / 0 failed (was 129); `pytest` 238 passed / 4 skipped — pre-existing fixture skips (was 233); `cargo check` warnings unchanged at 6 pre-existing; both pre-fix panics re-run against the release binary and now exit cleanly (2 / 1).

**Deliberately deferred to Phase 1/2:** `DeviceProfile`/`CapabilityDetector`/`ActionRegistry`/`FlashJob` architecture; unifying the two Python cancel registries; per-device STOP; fastboot DATA phase; Apple socket timeouts; HIL multi-device tests (no hardware in this environment).

---

## Remediation log — Phase 1, backend-authoritative capability architecture (landed in working tree)

New modules: `src/device.rs` (identity → transport → profile → capabilities → actions), `python/core/actions.py` (job/mode → action-id map + gate decision), `python/core/cancel.py` (single cancel registry). New CLI: `actions-for <key>`, `validate-action <key> <action>`.

| # | Change | Files | Tests |
|---|---|---|---|
| 1 | `StableDeviceIdentity` (`Serial`/`PortPath`/`Volatile`) with canonical keys round-tripping GUI/Python/Rust; `parse` accepts `adb:`/`usb:`/volatile/`bus:addr`, rejects `-`/noise/`usb:vid:pid`-without-`@` | `src/device.rs` | `parse_keys_round_trip`, `keys_are_canonical` |
| 2 | `resolve_transport`: fresh re-scan per call; serial/port match with `AmbiguousTarget` on >1, `DeviceNotFound` on 0/gone; volatile never follows moved addresses | `src/device.rs` | (exercised via CLI + matrix tests) |
| 3 | `detect_capabilities`: conservative per-VID:PID/mode mapping — no chipset/model guessing; preloader exposes crash-not-flash; DA stage info-only; fastboot honestly lacks `PartitionFlash` (no native DATA phase); Samsung-BROM info-only; non-EDL Qualcomm info-only; Apple DFU/Recovery split, never Android workflows; workflows = platform + protocol mechanism | `src/device.rs` | 9 matrix tests incl. all negatives (Samsung-dl, ADB-composite, MTK-BROM/preloader, EDL, non-EDL, fastboot, Apple-recovery/DFU) + backend-rejection checks |
| 4 | `ACTION_REGISTRY` (16 actions) + `allowed_actions` + `validate_action` (unknown ids and unmet requirements rejected) | `src/device.rs` | covered by matrix tests |
| 5 | `actions-for` / `validate-action` CLI; every error line names its device (`[device …]`) via an explicit command allowlist (file-taking commands excluded) | `src/main.rs` | manual CLI verification (absent device, bad key) |
| 6 | Fast server-only ADB-state lookup (no native probe) for profile queries | `src/adb.rs` (`server_state_for_serial`) | — |
| 7 | `bridge.actions_for` / `bridge.validate_action` (`ACTION_NOT_SUPPORTED` code; gone-device errors keep identity codes) | `python/core/bridge.py` | 5 new in `tests/test_devices.py::TestBackendActions` |
| 8 | Pre-execution gate in `_run_ops_flow`/`_run_job_flow`: backend must allow ≥1 mapped action before lock/spawn; unmapped jobs and key-less runs skip; missing binary passes through | `python/gui/qt_app.py`, `python/core/actions.py` | 4 new (`TestJobActionGate`) |
| 9 | Cancel unification: `flow.py` + `bridge.py` delegate to `core/cancel.py` (zero call-site churn; `core` re-exports unchanged) | `python/core/cancel.py`, `flow.py`, `bridge.py` | 3 new cross-registry tests; all pre-existing cancel tests green |

**Verification:** `cargo test` 155 passed / 0 failed (was 144); `pytest` 250 passed / 4 skipped — pre-existing fixture skips (was 238); `cargo check` warnings unchanged (6 pre-existing).

**Still open (documented, not regressed):** `FlashJob` lifecycle type + session binding (`CurrentTransport::target` is built for it); GUI page re-render from `actions-for` (gate blocks wrong-device execution today; buttons remain static); per-device STOP affordance (registry now supports it — `request_cancel(key)` — GUI buttons still broadcast); fastboot DATA; Apple timeouts; HIL hardware matrices.

---

## Remediation log — Phase 2, FlashJob lifecycle + per-device STOP (landed in working tree)

New module: `python/core/jobs.py` (`FlashJob`, `JobManager`, failure classifier).

| # | Change | Files | Tests |
|---|---|---|---|
| 1 | `FlashJob`: job_id/device_key/job/mode/method/validated actions, CREATED→VALIDATED→RUNNING→COMPLETED/CANCELLED/TIMEOUT/FAILED (sticky terminals), per-job cancel event + log buffer (5k cap), error/code, durations, summaries; `JobManager` with bounded finished history (50) | `python/core/jobs.py` | lifecycle, isolation, prune |
| 2 | Both runners create the job after gate+lock, drive VALIDATED→RUNNING→terminal; worker log lines feed the job buffer AND the console; `FlowCancelled`→CANCELLED, else `classify_failure(exc, device_key)`→TIMEOUT/FAILED preserving codes | `python/gui/qt_app.py` | — (runner wiring; logic covered by jobs tests) |
| 3 | `classify_failure` scoped to the job's device: a timeout on phone B reads TIMEOUT while phone A is cancelled (cancel-check consulted per-device, cancel-exc types first) | `python/core/jobs.py` | scoped-classification test |
| 4 | Per-device STOP: `_run_job_flow` maps its page stop button → job id (replaced per run, cleared on finish); `_mtk_stop`/`_qc_stop`/`_spd_stop` cancel exactly that job's device scope via `_stop_active_job`, broadcast fallback when unmapped; titlebar STOP stays broadcast (documented) | `python/gui/qt_app.py` | — (Qt wiring; `cancel_device` covered) |
| 5 | `JobManager.cancel_job/cancel_device`: mark job(s) + trip the shared registry scope, so flow checks and bridge poll loops observe one stop; other devices unaffected | `python/core/jobs.py` | per-device cancel isolation incl. shared-registry observation |

**Verification:** `cargo test` 155 passed / 0 failed; `pytest` 256 passed / 4 skipped — pre-existing fixture skips (was 250); `cargo check` warnings at baseline.

**Still open:** Rust-side session binding to a job's frozen transport (`CurrentTransport::target` staged); GUI buttons still render statically (execution gated, display not yet); unscoped chip-page direct runners (`_mtk_run` etc.) remain outside the job system; Apple timeouts; fastboot DATA; HIL hardware matrices.

---

## Remediation log — Phase 3, chip-runner scoping + Apple timeouts (landed in working tree)

| # | Change | Files | Tests |
|---|---|---|---|
| 1 | `CHIP_COMMAND_ACTIONS` (23 commands) + `actions_for_command` + shared `check_actions`; `check_job_allowed` refactored onto it | `python/core/actions.py` | 3 new (`TestChipCommandActions`) |
| 2 | `_choose_device` accepts one mode or a set (MTK page covers BROM+DA) | `python/gui/qt_app.py` | — (Qt; string callers unchanged) |
| 3 | `_chip_begin` shared prologue for all chip-page direct runners: explicit-target key derivation (fresh scan) or picker dialog; backend validation; per-device lock; scoped cancel clear; `FlashJob` (VALIDATED); fresh explicit `bus:addr` spliced over `"auto"`; refusal paths release the lock | `python/gui/qt_app.py` | — (Qt; pure parts covered in §1) |
| 4 | `_mtk_run`/`_qc_run`/`_spd_run`/`_spd_flash_run` rewritten on the helper: no more hardcoded `"auto"` (MTK/QC), no more first-match `_spd_resolve_target` cache, `device_scope` + per-job logs + terminal states + race-safe stop-mapping cleanup | `python/gui/qt_app.py` | — (Qt wiring) |
| 5 | usbmuxd/lockdown sockets bounded (10 s read/write at the single choke point `usbmuxd_socket`) — a hung usbmuxd can no longer wedge the bridge forever | `src/apple.rs` | existing suite green |

**Verification:** `cargo test` 155 passed / 0 failed; `pytest` 259 passed / 4 skipped — pre-existing fixture skips (was 256); `cargo check` warnings at baseline.

**Still open:** Rust-side session binding to frozen transports; static button display (execution now gated everywhere GUI-driven); remaining keyless one-offs (`_spd_backup`, battery/network triage, `kg_unlock`, native flash click) predate the runner system and are next; fastboot DATA; HIL hardware matrices.

---

## Remediation log — Phase 4, one-off scoping (landed in working tree)

| # | Change | Files | Tests |
|---|---|---|---|
| 1 | `_spd_backup` rewritten on `_chip_begin` (was: keyless lock, first-match `tgt` in-worker, no cancel scope, no job); keeps `destructive=False` severity via new helper param; adds the previously-missing `BridgeCancelled` branch | `python/gui/qt_app.py` | — (Qt wiring) |
| 2 | `_adb_begin` + `_adb_serial_for_key` shared prologue for ADB tools: pick (dialog when >1), serial pinned once, `adb_shell` validation, per-device lock, scoped cancels, `FlashJob`; workers must pass `serial=` per call (loops can no longer hop phones) | `python/gui/qt_app.py` | — (Qt) |
| 3 | `_adb_triage`/`_battery_report`/`_battery_repair_run`/`_battery_load_test_run`/`_network_report`/`_network_repair_run`/`_network_modem_reset_run` rewritten on the helper: no `auth[0]`/`devs[0]`, per-job logs + terminals, keyed lock release (also fixes `_network_report` never releasing its guard); load-test sampling loop checks the job's device scope | `python/gui/qt_app.py` | — (Qt wiring) |
| 4 | First-match helpers `_get_authorized_adb`/`_require_adb` deleted (zero remaining callers); tombstone comment warns against reintroducing first-match ADB resolution | `python/gui/qt_app.py` | full suite green |
| 5 | `kg_unlock`: refuses unless exactly one Samsung is on USB; fresh per-key target; `FlashJob` + `device_scope` (still synchronous on the GUI thread — threading redesign deferred) | `python/gui/qt_app.py` | — (Qt) |
| 6 | `_native_flash_clicked`: picks one Download-mode device, validates `samsung_odin_flash`, takes the per-device run guard (previously only `_nf_busy` — could collide with an ops flow on the same phone), runs `flash_archive_smart` under `device_scope` with per-job log tee | `python/gui/qt_app.py` | — (Qt) |

**Verification:** `cargo test` 155 passed / 0 failed; `pytest` 267 passed / 4 skipped — pre-existing fixture skips (was 259); `cargo check` warnings at baseline.

---

## Remediation log — Phase 5, capability display gating (landed in working tree)

| # | Change | Files | Tests |
|---|---|---|---|
| 1 | `button_allowed(job/mode/command, allowed_ids)` pure decision; `adb_shell` + `mtk-flash-part` added to the command map; unmapped → fail-open True | `python/core/actions.py` | 3 new (`TestButtonDisplayGate`) |
| 2 | `_gated_buttons` weakref registry + `_gate_button` + `_refresh_gates` (per-key+sig cache, fail-open on any failure, dead-ref pruning, `[BACKEND]` tooltip suffix) | `python/gui/qt_app.py` | offscreen Qt tests below |
| 3 | 366 buttons registered: every `_add_job_flows` button centrally (job+mode), QC/SPD loops by label→command, MTK flash/check/part/FRP buttons, triage + native-flash + slot-flash buttons, both `action_card` factories by slot→`adb_shell` | `python/gui/qt_app.py` | registry size asserted |
| 4 | Refresh on device-list rebuild + connection-bar pick | `python/gui/qt_app.py` | — (wiring) |
| 5 | `tests/test_gates_display.py`: real window under `QT_QPA_PLATFORM=offscreen` — FRP hidden for EDL-without-workflow, shown for Download, MDM hidden without ADB mechanism, direct buttons follow protocol, fail-open on bridge error and without selection | `tests/test_gates_display.py` | 5 new |

**Still open:** Rust-side session binding to frozen transports; fastboot DATA; HIL hardware matrices (no devices in this environment — USB paths verified by unit/integration tests only); `kg_unlock` GUI-thread blocking; `_poll_net_live` passive monitor (display-only, intentionally unscoped).

---

## Remediation log — Phase 8, transient-refusal retry + kill-server purge (landed in working tree)

**Incident:** with the Tecno on a marginal link (proven -32/-71 electrical errors), the battery test refused with "no adb" while the monitor showed it connected; worse, one diagnostic helper call stormed the dongle 034→057 and hung its worker 120 s.

**Root causes:**
1. Refusal messages are categorical ("no adb") for transient states (USB serial unreadable for a moment mid re-enumeration while the daemon still reports the device). Proven live: merged row with `serial None` one moment, validation passing the next.
2. Default `rescue=True` on every diagnostic shell (triage/report/repair/load/network/modem/fus/info): any busy claim killed the server from poll-adjacent code — the exact storm vector Phase 6 removed from polls, still present in tools. A single `get_live_identity` call killed the daemon and stormed 23 re-enumerations; its worker then hung in 4× retry loops against the vanishing device.
3. No settle-retry anywhere: first transient failure = final refusal.

| # | Change | Files | Tests |
|---|---|---|---|
| 1 | `is_transient_refusal(err)` pure classifier (transient vs settled/ambiguous/permission) | `python/core/actions.py` | 2 new |
| 2 | `_adb_begin` + `_chip_begin` (validate and target-resolve): one 2.5 s settle + retry on transient refusals only; refusal/toast texts name re-enumeration explicitly | `python/gui/qt_app.py` | 2 new offscreen (`_adb_begin` retries transient once; settled refusal fails fast <2 s) |
| 3 | `rescue=False` on all ~30 diagnostic/tool shells (triage, battery ×4, network ×4, qc_adb, fus_detect, model-refresh burst, unauthorized burst, net-live); serial pinning completed alongside; flows keep default rescue (explicit mutating ops) | `python/gui/qt_app.py`, `python/core/device_info.py` | full suite green |
| 4 | Absent-retry taxonomy deliberately kept (reboot tolerance; absent retries are scan-only, USB-quiet — the killer was kill-server, now gated) | — | documented |

**Verification:** `pytest` 284 passed / 4 skipped; `cargo test` 164; warnings at baseline. **Live re-verify pending:** phone absent from bus at session end — re-run battery report on reattach (expect COMPLETED or an accurate transient message, never a storm).

---

## Remediation log — Phase 9, silent merge death + hardware flap diagnosis (landed in working tree)

**Incident:** "ADB Status shows connected but the device doesn't show connected" — plus a live flap storm with the app not even running.

**Root causes found:**
1. **Silent merge death (fixed):** `devices_json` emits an array of row *strings*, but both merge paths deserialized it as `Vec<AdbDevice>` (structs) — always failing into `unwrap_or_default()`. The USB↔ADB merge therefore never saw ADB entries: row `adb_state` permanently `None`, standalone ADB rows never created. Row-driven display (connection bar, tiles, chooser serials) showed no ADB while monitor-driven ADB Status showed connected. Fixed with `parse_adb_line`/`parse_adb_rows` in `usb::filtering`, used by both `devices.rs` and `filtering::detect_merged`; verified live (row now carries `adb_state: device`). The qcom-corner ADB overlay gap from the previous session was the same family (fixed + offscreen-tested).
2. **Hardware flap, not software (diagnosed, not fixable in code):** with no FlashPilot process running, the Tecno re-enumerates every ~30–150 s with `error -32`/`-71` descriptor failures and skipped device numbers — classic failing cable/port/PHY. Zero-touch polls were proven clean (114 quiet cycles on the modem); this phone errors even enumerating at idle plug-in. Recommendation given: different cable/port, check phone port; app-side identity/revalidation absorbs the rest (key stable across 010→012→068→071).

| # | Change | Files | Tests |
|---|---|---|---|
| 1 | `parse_adb_line`/`parse_adb_rows` + both merge paths switched | `src/usb/filtering.rs`, `src/devices.rs` | 2 new (line contract, string-array parsing incl. non-uptake regression) |

**Verification:** `pytest` 284 passed; `cargo test` 166 passed; warnings at baseline; live merged row carries ADB state.

---

## Remediation log — Phase 10, pick resilience (1.2.3, landed on `transport`)

**Incident (from the 1.2.2 installed app log):** model/build/Android all resolve, ADB transport shows `[device]`, yet a tool clicked seconds later refuses "No authorized ADB device" — the device was mid re-enumeration window (addr climbing) and the *pick* had no retry (only validation did).

**Fix:** `_pick_device(label, modes)` wraps every `_choose_device` call site (`_adb_begin`, `_chip_begin`, `_native_flash_clicked`, both generic runners): one 2.5 s settle-retry when a scan transiently misses; user-cancelled choosers never retried. Verified: 287 pytest + 166 cargo green, 3 new offscreen tests (retry-then-found, give-up-after-two, cancel-no-retry). Shipped in 1.2.3 (same .deb pipeline, smoke-tested).

---

## Remediation log — Phase 11, full ADB audit: AUTH wall found + fixed (1.2.4, on `transport`)

Comprehensive ADB audit (protocols, USB detection, flows, jobs, every loop) after "ADB connected but actions fail no adb" persisted through 1.2.3.

**Root cause (protocol, found + fixed):** the AUTH ladder's hash alternation was one-way — `use_sha256 = false` at round 2, never restored. A modern (SHA-256) adbd whose round-1 signature was lost to transport noise (the flapping link) re-tokened into rounds 2–6 signing SHA-1 it always rejects → `Unauthorized` after ~5.5 s of backoff **while the device was authorized all along** (the server held our key). Exactly the reported symptom: monitor shows connected (server rows), actions fail "no adb" (native AUTH wall).

**Audited clean:** ambient serial propagation (device_scope → ContextVar → unscoped in-flow calls resolve pinned); `_wait_fastboot` (cancel-scoped, serial-scoped, transient-tolerant); `compute_transports` for the 0e8d:201c composite (ADB transport correct); `shell_collect` timeouts (socket == deadline, no premature cut); string-descriptor reads (rusb-internal timeout, ENODEV fails fast); `_spd_brom_watch` (VID-filtered, cannot touch other devices); loops cadence (monitor 3s + load-test sampling + TTL caches — hardened in earlier phases).

| # | Change | Files | Tests |
|---|---|---|---|
| 1 | AUTH alternation: odd signature rounds SHA-256, even SHA-1 (both hashes stay in play) | `src/adb.rs` | `auth_hash_alternation_keeps_sha256_in_play` (r1==r3, r1!=r2, EM carries SHA-256 digest) |
| 2 | `_wait_for_adb` transient-scan tolerance | `python/core/core.py` | full suite green |

**Shipped:** 1.2.4 (committed `8f8db94`/`ea2359a`, .deb built from the fixed tree — release-codegen alternation test green). Verification: 287 pytest + 166 cargo.

---

## Remediation log — transport branch: Rust server transport (landed in working tree)

**Incident:** on the MSM8916 modem (server-authorized), explicit ADB ops could never succeed natively: open dies `Resource busy`, and the rescue eviction resets the dongle. Protocol/auth investigated and cleared (modern v1 CNXN accepted by the dongle's adbd via the server; `~/.android/adbkey` reused so identities match; SHA-1 fallback present) — the failure is purely the exclusivity fight.

**Fix — delegate ladder:** native → Rust server transport → host binary → rescue kill (last). `ServerConn` (TCP 5037, `host:transport` + service framing, shared amessage codec, lenient shell collect with A_EXIT/A_OPEN handling, per-op deadlines) + `adb-shell-server` CLI (explicit serial only — never first-device). Python tries server-TCP then binary on busy only; native success never consults PATH (hermetic tests); daemon FAILs fall through so native auth stays authoritative.

| # | Change | Files | Tests |
|---|---|---|---|
| 1 | `ServerConn`, `server_round` (OKAY/FAIL framing), `shell_collect`, `server_shell_cli`, `A_EXIT` | `src/adb.rs`, `src/main.rs` | 8 new (mock-TCP-daemon transcript, FAIL surfacing ×2, EXIT end, bad-ack, absent-daemon no-hang, unpinned rejection) |
| 2 | `_server_shell_for` + ladder order native → server-TCP → binary → rescue; pre-existing busy tests re-pointed at the ladder with PATH emptied | `python/core/bridge.py`, `tests/test_adb_native.py` | 3 new (preferred, fall-through, dash-skip) |

**Verification:** `cargo test` 164 passed; `pytest` 280 passed / 4 skipped; `cargo check` warnings at baseline. **Live verification pending:** dongle unplugged mid-session — reattach + run any ADB op (server up) to confirm server-TCP output with zero USB touch.

---

## Live verification — transport branch on Tecno KG6 (landed observations)

Hardware: Tecno Spark 8 / KG6, MTK 0e8d:201c, single ADB iface 255/66/1, Android 11 (API 30), `ro.adb.secure=1`, server-authorized. Corrects the design on real wire behavior: v1 `shell:` over daemon TCP carries **raw stdout bytes then close** (verified byte-level against platform-tools 35) — not amessages; `shell_collect` rewritten accordingly (mock tests reworked to raw semantics).

Results: `adb-shell-server` returns output, exit 0; Python ladder returns output with the server left running (no kill) and no storm; native-only still fails `Resource busy` as expected (proving the delegate did the work). Identity survived a mid-session address change (010→012): key `adb:06977371AD102074` stable, `validate-action adb_shell` allowed.

Caveat found live: this phone's link shows electrical errors (`device descriptor read/64 error -32` at idle plug-in; `not accepting address, error -71` on re-enumeration) — marginal cable/port/power, distinct from the dongle's clean software resets. Zero-touch polls: 0 bumps/114 cycles on the dongle, 1 bump/20 cycles here against that electrical background; 5-min idle watch clean. Recommendation carried to the user: reseat cable/port; app-side identity/revalidation absorbs the rest.

---

## Remediation log — Phase 7, server transport for ADB ops (landed in working tree)

**Incident:** on the MSM8916 modem (authorized in the system server as `3588b020 device`), every explicit ADB operation failed: native open hits `claim_interface: Resource busy` (server holds the iface), and the `rescue=True` kill-server eviction resets the dongle's USB function — "adb never works", and each attempt risks another flap storm.

**Fix — delegate, don't evict:** native-first ordering everywhere; on an exclusive-claim fight, route once through the system server transport (zero USB touch) instead of killing whoever holds the interface.
`_host_adb_binary` (cached `shutil.which`), `_run_host_adb_raw` (cancel-polling subprocess, timeout/cancel propagate), `_host_shell_for` (verbatim stdout even on remote nonzero exit — native parity; server disclaimers fall through so the backend reports auth/offline/presence), `_host_transfer_for` (handled only on rc 0). `adb_shell` tries host once per busy inside its retry loop (host errors fall through to rescue/retry unchanged); `adb_pull`/`adb_push` try host on busy then re-raise the original. Unit tests stay hermetic: native success never consults PATH (no real-binary dependence).

| # | Change | Files | Tests |
|---|---|---|---|
| 1 | Host transport helpers + native-first/busy-delegate wiring in shell/pull/push | `python/core/bridge.py` | 7 new (`TestHostTransportFallback`, fake-`adb` stub: busy-delegate, native-success isolation, disclaimer fall-through, remote-failure passthrough, no-binary skip, dash skip, pull/push handled + busy propagation) |
| 2 | Docstrings updated (transport order, rescue semantics) | `python/core/bridge.py` | — |

**Verification:** `pytest` 277 passed / 4 skipped (was 270); `cargo test` 157 unchanged; `cargo check` warnings at baseline. **Live verification pending:** the dongle was unplugged mid-session, so the host-delegate path has hermetic tests only — reattach + run any ADB op (server up) and confirm output without busy/kill/reset.

**Still open:** Rust-side session binding to frozen transports; Rust TCP server-transport (would remove even the fallback binary need); fastboot DATA; phone HIL matrices; `kg_unlock` GUI-thread blocking.

---

## Remediation log — Phase 6, USB-modem flap fix (landed in working tree)

**Incident:** a Qualcomm MSM8916 Android modem (05c6:90b4, RNDIS + 255/66/1 ADB, serial 3588b020) disconnected/re-enumerated in a loop (~1 Hz, device numbers climbing into the 30s, RNDIS dropping each cycle) from the moment the app started. Idle bus without the app: silent for 25 s. Reproduced live: a single native `adb-devices` probe (claim + detach + CLEAR_HALT + CNXN while the system server was down) knocked the dongle off the bus (033→034 + RNDIS drop).

**Root causes (two cooperating mechanisms):**
1. **Trigger — startup native burst:** with no adb server running, every poll's `adb-devices`/`adb_status` natively probed unknown serials, and model refresh fired ~8 getprop sessions on serial change. Each native session claims/detaches/handshakes; the dongle resets its USB function on it.
2. **Sustainer — absence-window probing:** each reset opens a window where the server lacks the serial, so the next poll probes natively again — the device never stabilizes. Worse, a second vector was found mid-fix: `device_info._adb_getprop` used default `rescue=True`, so a single live-identity call killed the server on busy and stormed 034→057 (observed live).
3. **Steady engine:** `get_live_identity` ran ~10 native getprops per 3 s tick with no gate.

| # | Change | Files | Tests |
|---|---|---|---|
| 1 | `adb-devices --no-probe`: server rows + `unknown`-state descriptor rows, never open/claim/handshake; pure `presence_lines` seam | `src/adb.rs`, `src/main.rs` | 2 new (server-win, unknown-marking, ghost-drop, dedupe) |
| 2 | `detect-merged` (row rebuilds fire on change-detection, i.e. mid-re-enumeration) and `filtering::detect_merged` switched to the zero-touch listing | `src/devices.rs`, `src/usb/filtering.rs` | existing suites green |
| 3 | `bridge.adb_presence()` / `adb_presence_status()` (shared `_parse_adb_lines`); verified `adb_status()` kept for flows/explicit ops only | `python/core/bridge.py` | presence flag + parse tests |
| 4 | Poll paths switched: DeviceMonitor, model-refresh, `_poll_net_live` fallback, `get_live_identity` | `python/gui/qt_app.py`, `python/core/device_info.py` | monitor-backoff test re-pointed |
| 5 | `get_live_identity`: serial-change + 60 s TTL gate around the getprop burst; serial-threaded probes | `python/core/device_info.py` | burst-once-then-cached + re-probe-on-change tests |
| 6 | `rescue=False` + serial pinning everywhere in poll/display paths: `_adb_getprop` (was default rescue — the 034→057 stormer), model-refresh burst, unauthorized-serial burst, `_poll_net_live` (display-preferred serial), `_fus_detect_via_adb` | `python/core/device_info.py`, `python/gui/qt_app.py` | full suite green |
| 7 | `button_allowed` unaffected; `validate_action`/flows keep verified listing + per-command native verification | — | 269 passed |

**Live verification (this machine, the flapping dongle):** 60 CLI poll cycles (detect-all + no-probe + merged) → 0 bumps; 54 full Python poll-surface cycles (incl. `get_live_identity`) → 0 bumps, device stable, RNDIS up, adb server alive. Before: 1 native probe → reset + RNDIS drop; journal showed 1 Hz disconnect storms.

**Follow-up (same session):** the corner label for non-EDL Qualcomm devices missed the ADB overlay its sibling branches have (qcom branch never called `_adb_overlay`), and the installed build predates `detect-merged` (its old Python transport mapping is where the stale "MTP" label comes from — current tree reports `['ADB']`). Added the overlay + offscreen regression test driving `_on_device_state` with a dongle-like state (corner must contain `05c6:90b4` + `ADB · connected (3588b020)`, no `MTP`). Until rebuilt/reinstalled, the `/usr/lib/flashpilot` copy stays stale: run from the tree (`.venv/bin/python -m python.main`, bridge auto-resolved to `target/release`) or rebuild the .deb (`packaging/build-deb.sh`) to pick up the flap fix and everything after Phase 0.

**Still open:** Rust-side session binding to frozen transports; fastboot DATA; HIL matrices on phones (modem-class hardware now covered live); `kg_unlock` GUI-thread blocking; `_poll_net_live` shells (page-visible explicit context, serial-pinned).
