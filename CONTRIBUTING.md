# 🧑‍💻 Contributing to FlashPilot

Thanks for stopping by! This project is built on reverse-engineered protocols and
open knowledge — every contribution makes it more capable, more reliable, and
closer to the paid Windows suites. You don't need to be a flashing expert to
help.

## Table of contents

- [Code of conduct](#code-of-conduct)
- [How the project is organized](#how-the-project-is-organized)
- [Ways to contribute](#ways-to-contribute)
- [Getting started](#getting-started)
- [Architecture tour (10 minutes)](#architecture-tour-10-minutes)
- [How to add a new flow](#how-to-add-a-new-flow)
- [Adding a new USB protocol / Rust command](#adding-a-new-usb-protocol--rust-command)
- [GUI guidelines](#gui-guidelines)
- [Testing](#testing)
- [Pull request checklist](#pull-request-checklist)
- [Roadmap & ideas](#roadmap--ideas)

---

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Be respectful, assume good intent,
and keep discussions technical and helpful. This is a hobbyist-turned-serious
project: we welcome beginners and veterans alike. Harassment, gatekeeping, or
pushing proprietary "secret sauce" into the repo will not be tolerated.

---

## How the project is organized

Two halves work together:

| Layer | Location | Language | Role |
|---|---|---|---|
| **Core / protocol engine** | `src/` | Rust | Raw USB, all bootloader protocols (`flashpilot-bridge` CLI) |
| **Flow orchestrator** | `python/core/core.py` | Python | `FLOWS` / `JOBS` / `MODES` registry + all flows |
| **Device identity** | `python/core/devices.py` | Python | Stable keys, device list, target re-resolution, thread scope |
| **FRP surface** | `python/core/frp.py` | Python | FRP-only re-export (name == responsibility) |
| **GUI studio** | `python/gui/` | Python / PyQt6 | Workbench (`qt_app.py`), pages (`devices.py`), theme, animations |

Python never talks to USB directly. It shells out to `target/release/flashpilot-bridge`
(the Rust binary), which returns JSON/text. The GUI only listens to signals from
worker threads — never touch widgets from a background thread.

---

## Ways to contribute

No coding? No problem:

- **Testing on real hardware** — report which devices/firmwares a flow works on.
- **Documentation** — improve the README, this file, and flow descriptions.
- **Firmware / DA / combo archives** — pointers to legitimate, freely available binaries.
- **Translations & themes** — the GUI is themable; new accent packs are easy wins.
- **UI/UX** — mockups, accessibility passes, keyboard-shortcut design.
- **Bug reports** — use the [bug report template](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml): steps, logs, `flashpilot-bridge detect` output, device model + firmware version.
- **Code** — see below.

> 💡 **New here?** Look for the **`good first issue`** label on the issue tracker —
> curated, beginner-friendly tasks that are fully scoped and safe to pick up.

---

## Getting started

```bash
# 1. Build the Rust bridge
cargo build --release

# 2. (Recommended) USB udev rules
sudo bash root/setup-usb.sh

# 3. Create the venv + run
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m python.main
```

The app opens a native PyQt6 window. Use the **Settings → Tools** page to see
whether the bridge is built and ADB is detected.

---

## Migrating from an older checkout (read this first if you're returning)

A note on the churn, plainly: between 1.2.0 and now we renamed the central
module, split one god-file into focused modules, renamed every job, and added
a dozen files. That breaks old imports, old docs references, and any
out-of-tree scripts you wrote against `python.core.frp`. Sorry about that —
it was the only way to kill the god-file, fix the MTK PID mix-up, and make
multi-device support possible without layering hacks on top. This section is
the complete adaptation guide; nothing here is deprecated-gradually, it all
changed at once, so work through the table once and you're current.

### Renamed paths

| Before | After | What to change |
|---|---|---|
| `python/core/frp.py` (god file: registry + every flow) | `python/core/core.py` | `from python.core import frp` → `from python.core import core`; `frp.FLOWS` → `core.FLOWS`, etc. |
| *(nothing — FRP lived inside the god file)* | `python/core/frp.py` (new, FRP-only) | If you only need FRP flows, import from here instead of `core`. |
| *(nothing)* | `python/core/devices.py` (new) | Device identity, `list_devices()`, `resolve_usb_target()`, `device_scope()`. |
| *(nothing)* | `python/core/imei.py` (new) | MTK/SPD IMEI repair + change flows. |
| *(nothing)* | `python/core/experimental.py` (new) | EXPERIMENTAL gates + audit log. |
| *(nothing)* | `python/core/{knox,qcn,emmc,pac,apple,health,compat,device_info,fastboot,integrity,safety,spd_adb}.py` (new) | Per-domain logic, previously inline in the god file or missing. |
| *(nothing)* | `tests/test_devices.py` (new) | Multi-device + cancel-scope tests. |
| *(nothing)* | `CHANGELOG.md` (new) | Per-release grouped changes; check it first. |

### API changes you must adapt to

- **Resolvers take `key=None`.** `find_samsung()`, `_download_mode_device()`,
  `_wait_for_adb()`, `_wait_mtk_brom_target()`, `_mtk_retry()`,
  `wait_clean_download_mode()`, `pit_contract()` all accept an optional stable
  device key (ambient thread scope by default — old call sites keep working,
  first-match behavior preserved when no key is set).
- **Cancel is per-device.** `request_cancel()` / `clear_cancel()` /
  `cancel_requested()` in `flow.py` and `bridge.py` accept `key=None`.
  Keyless `request_cancel()` still broadcasts (global STOP); keyless checks
  consult the ambient scope, then the broadcast bus.
- **Run-guard is per-device.** `_flow_start(label, destructive, key=None)` /
  `_flow_end(key=None)` / `_flow_busy_msg(key=None)` in `qt_app.py`; the old
  `_FLOW_LOCK` / `_FLOW_LABEL` globals are gone (replaced by per-key dicts +
  `_flows_running()`).
- **Runners take `device_key=None`.** `_run_ops_flow()` / `_run_job_flow()`
  show the device picker when several phones match, then set
  `ctx["device_key"]` (+ `ctx["target"]` where resolvable) and run inside
  `devices.device_scope()`.
- **New transport mode `"SPD"`** in `MODES` (VID `0x1782`); new jobs
  `Knox / Warranty`, `QCN / Modem`, `IMEI Repair / Change`, `eMMC / UFS`.
- **Job names are verb-first** (`Remove FRP`, not `FRP bypass`; see README).
  If your branch still references old names, rename to the table in
  “Architecture tour”.
- **MTK PIDs are mtkclient-convention**: `0e8d:0003` = BROM,
  `0e8d:2000` = preloader. Several old comments/logs had them swapped;
  trust `mtk.pid_stage()` / Rust `boot_stage_for()`, not old strings.

### If you have an open PR from before the restructure

1. Rebase onto the new tree; expect conflicts confined to imports and the
   `JOBS`/`FLOWS` blocks.
2. Run the checklist below — `pytest` will catch stale key/name references
   immediately (registry tests assert every `JOBS` method resolves).
3. If your PR touched `flows/` (the removed split-package experiment): that
   directory is gone, port your change onto `core.py` + the domain module.

---

## Architecture tour (10 minutes)

1. **`src/main.rs`** — an 80+-command CLI. Each `match` arm is one command
   (`detect`, `mtk-flash`, `mtk-crash-brom`, `qcom-firehose`, `spd-format`,
   `odin-pit`, ...).
2. **`src/usb.rs`** — finds devices by VID/PID, gives you endpoints (plus stable
   `port_numbers` for re-enumeration-proof addressing).
3. **`src/odin.rs`** — Samsung download mode (the reverse-engineered Odin 3
   protocol, Heimdall-derived). Reads/writes PIT, flashes partitions
   (incl. the persistent `odin-agent` session multiplexer).
4. **`src/mtk*.rs`** — MediaTek BROM (`0e8d:0003`) → preloader (`0e8d:2000`) →
   Download Agent handshake, scatter parsing, GPT partition work, SLA keys,
   BROM exploits, crash-to-BROM. ⚠️ PID convention is mtkclient-style:
   `0003`=BROM, `2000`=preloader — don't swap them.
5. **`src/qualcomm/`** — Sahara (EDL) handshake and Firehose sessions.
6. **`src/spd.rs`** — Spreadtrum/UNISOC BSL: FDL download, format, FRP, backup,
   PAC extract/pack.
7. **`python/core/core.py`** — the **heart of the GUI**. `JOBS` maps
   `job → mode → [flow keys]`. `FLOWS` maps a flow key to a function returning a
   `Flow` (a list of `Step`s). 13 jobs, 90+ flows, 9 modes (incl. `SPD`).
8. **`python/core/devices.py`** — multi-device identity. Stable keys
   (`adb:<serial>` → `usb:<port-path>` → volatile fallback), `list_devices()`,
   `resolve_usb_target()`, and the `device_scope()` thread-local that carries
   the chosen phone into resolvers.
9. **`python/gui/qt_app.py`** — builds all sections (Samsung / MTK / QC / SPD /
   Battery / Network / Settings) and the sub-tab workbenches, plus the
   per-operation device picker and per-device run-guard.

### Data flow

```
click button
  → _choose_device(job, mode)          # silent if 0-1 phones match, else picker
  → _run_ops_flow(job, mode, method, name, device_key)
  → per-device _flow_start(key) + device_scope(key) + ctx["device_key"]
  → core.flow_for(...) -> Flow (list of Steps)
  → each Step runs in a worker thread, calling bridge._run([...])
  → bridge spawns target/release/flashpilot-bridge ...
  → Rust does USB I/O, prints JSON/text
  → Python parses + emits _ui.line() signals (tagged [device-key])
  → GUI updates console / status / progress safely
```

---

## How to add a new flow

The simplest feature you can ship. Open `python/core/core.py`:

```python
def flow_my_method():
    return Flow(
        "my method",                       # human-readable name
        [
            Step("step 1", lambda ctx, log: log("hello")),
            Step("step 2", lambda ctx, log: bridge._run([...], timeout=60)),
        ],
    )

FLOWS["my_method"] = flow_my_method        # short snake_case key (no flow_ prefix)
```

Then wire it into a job's mode in `JOBS` (jobs are verb-first):

```python
"Remove FRP": {
    ...
    "ADB": ["adb_frp", "frp_browser", "my_method"],
    ...
}
```

That's it — the flow appears in the GUI's dropdown/sub-tab automatically and is
also reachable from the CLI. **This is the highest-value/easiest-entry area.**

> Use `log(...)` inside steps for console output, `ctx` for state you want to
> carry between steps, and `bridge._run(...)` for anything that hits the Rust
> binary. Keep steps cooperative with `cancel_requested()` where appropriate so
> Stop works (cancel is per-device scoped — see below).

### Rules every flow must follow

- **Never grab "the" device.** Accept `key=None` (ambient thread scope) in any
  resolver you add, and filter by it — see `devices.device_key()`,
  `devices.match_key()`, `devices.device_scope()`. The GUI sets the scope per
  operation; headless callers can too.
- **Job names are verb-first** (`Remove FRP`, `Flash Firmware`, `Unlock Carrier`).
  **Flow keys are short snake_case** (`adb_frp`, not `flow_adb_frp`); the one
  historical alias (`fastboot_read`) was removed — don't add aliases.
- **MTK PID convention is mtkclient-style**: `0e8d:0003` = BROM (held),
  `0e8d:2000` = preloader. Rust, Python, GUI labels and docs must all agree.
- **EXPERIMENTAL writes** (Knox/IMEI/QCN/eMMC) go through
  `experimental.check_gate_strict()` with a per-run ack — a stored ack must
  never auto-pass. GUI-gate them via `_EXPERIMENTAL_FLOW_MAP` + the amber
  collapsible pattern on the owning chip page (never a global LAB page).
- **Bridge targets are volatile** (`vid:pid@bus:addr` changes on re-enumeration).
  Re-resolve from the stable key before opening sessions
  (`devices.resolve_usb_target()`); pin odin4 with `-d /dev/bus/usb/BBB/AAA`.

---

## Adding a new USB protocol / Rust command

1. Add your module under `src/` (e.g. `src/myproto.rs`).
2. Add `mod myproto;` to `src/main.rs` and a new `match` arm + usage line.
3. Return `Result<T>` via `crate::error` and use `serde_json` for structured output.
4. Expose it from Python in `python/core/bridge.py` as a wrapper around `_run([...])`.
5. Build a `Flow` in `core.py` that calls it (respect the flow rules above).
6. Add a test if you can — unit tests live in `src/*.rs` (`#[test]`) and `tests/`.

**Protocol hygiene:** cite your source (forums, clean-room write-ups, other OSS
projects) in the module docstring. We don't include proprietary blobs — only the
protocol implementation.

---

## GUI guidelines

- **PyQt6 only.** No other Qt bindings, no extra UI deps (see `requirements.txt`).
- Match the existing visual language: `_btn_ghost()`, `_btn_primary()`,
  `_card_qss()`, `SectionTitle`, `C[...]` theme colors, `FlowLayout` for button grids.
- **Theme tokens, not raw accent:** fills may use `C['accent'/'grad_a'/'grad_b']`,
  but focus rings, selected-tab borders and checkboxes MUST use the neutral
  `C['focus_ring']` / `C['sel_border']` — otherwise red accent themes (Crimson,
  Sunset) leak red into focus states. Never hardcode hex for chrome.
- **Thread rule:** background work goes in `threading.Thread`; GUI updates happen
  only through `self._ui.*` signals (`.line`, `.status`, `.toast`, `.ui`, `.progress`).
- **Animations:** `Motion.shake()` / `Motion.rubber()` are mutually exclusive per
  widget (guarded by `_anim_lock`) — never run both concurrently or call sites
  must serialize via `QTimer.singleShot`. Neither may leave `setFixedSize`,
  restyled borders, or disabled layouts behind; `cleanup()` restores all.
- Keep long-lived UI rows scrollable — the chip pages wrap content in a
  `QScrollArea` so they never crush on small windows.
- New sub-tabs reuse `SamsungSubTabs` + a `QStackedWidget` (see `_build_chip_ops_section`).
- Action buttons are `NoFocus` (no sticky focus ring); checkable tab pills keep
  `checked` styling for the active state.

---

## Testing

```bash
cargo test                      # Rust unit tests (incl. MTK stage mapping, SLA, PIT)
.venv/bin/python -m pytest tests/   # Python suite (currently 173 passed, 4 skipped)
```

Test suite layout:

- `tests/test_frp_flow.py` — `Flow`/`Step` execution + cooperative cancellation + per-device run-guard.
- `tests/test_mtk.py` — MediaTek logic (scatter, DA, boot-stage helpers, BROM wait/crash-retry).
- `tests/test_devices.py` — stable device keys, phone filtering, target re-resolution, scoped cancel.
- `tests/test_carrier_lock.py` — SIM-lock verdict + MTK patch gating + DA discovery.
- `tests/test_odin_safety.py` — tar.md5 verification, BL gates, odin4 flag negotiation.
- `tests/test_pit.py` — Samsung PIT parsing.
- `tests/test_bridge_io.py`, `tests/test_fus.py` — bridge I/O + Samsung firmware downloader.

If you add Rust logic, add `#[test]` modules in the same file. If you add flows,
add a pytest that runs the flow with a fake/offline context where possible.
New resolvers must accept `key=None`; new tests should cover multi-device
filtering (see `test_devices.py`) rather than assuming one phone.

---

## Pull request checklist

- [ ] `cargo build --release` passes.
- [ ] `cargo test` passes (or note why not runnable).
- [ ] `.venv/bin/python -m pytest tests/` passes.
- [ ] New flow: wired into `JOBS` (job + mode) so it's reachable in the GUI.
- [ ] New resolver: accepts `key=None` (ambient scope) and is covered by a multi-device test.
- [ ] New Rust command: added to `main.rs` usage text + `bridge.py` wrapper.
- [ ] GUI changes: themed colors (neutral focus tokens!), signal-based updates, scroll-safe layouts.
- [ ] No secrets/binaries/device-identifying data added to the repo.
- [ ] Updated the README feature matrix if you added a capability.

Keep PRs focused. One feature or fix per PR is ideal; reference the issue number.

---

## Platform support policy (read before porting)

**Linux is the only supported platform.** Development, hardware testing and
releases target Linux. Windows/macOS issues will be closed as unsupported —
unless they arrive as code, as follows.

**Why:** `odin4` is Linux-only; Windows USB needs per-mode drivers (Zadig /
QDLoader / Samsung) that can't be debugged remotely; macOS needs
signing/notarization for negligible demand. See README's
“Platform support” section for the full reasoning and the open invitation
to argue it.

**How to contribute a port anyway (the accepted shape):**

1. Do NOT sprinkle `sys.platform` checks through flows or the GUI.
2. Add `python/core/platform.py` with backend functions —
   `open_file_manager()`, `detach_kernel_drivers(target)`,
   `usb_device_path(bus, addr)`, `needs_udev_setup()`,
   `kernel_module_loaded(name)` — Linux implemented, others raising
   `NotImplementedError` with a helpful message.
3. Migrate existing Linux-only call sites (`xdg-open`, `rmmod cdc_acm`,
   `/dev/bus/usb`, `lsmod`, udev docs) onto it, one PR per call-site group.
4. A Windows/macOS backend PR must include: the backend implementation,
   docs updates, and CI or maintainer-verified manual test evidence. The core
   team does not own non-Linux test hardware — port PRs live or die on their
   author's ability to prove them.

**PySide6 vs PyQt6:** migration to PySide6 (LGPL, MIT-compatible — PyQt6 is
GPLv3) is wanted but blocked on GUI smoke-test coverage. If you take it:
convert `pyqtSignal→Signal`, `pyqtProperty→Property`, `PyQt6.sip→shiboken6`
mechanically, extend the offscreen window/picker/guard smoke tests in
`tests/`, and keep behavior pixel-identical. Discuss first in Discussions.

## Roadmap & ideas

We'd love contributors to champion any of these:

- **Ports & packaging:** Flatpak / AppImage / AUR, CI matrix (Linux distros), `pip`/`cargo` release flow.
- **MediaTek:** more DA variants, scatter edge cases, eMMC/UFS backup dumps, new `hw_code` entries in `CHIP_NAMES` (with a cited source — never guess hex codes).
- **Qualcomm:** rawprogram/patch XML edge cases, fh-loader combos, more chip PIDs.
- **Samsung:** additional HID download-mode payloads per SoC, Odin multi-partition UX polish.
- **Multi-device:** per-device console tabs/progress, per-device STOP granularity (STOP currently broadcasts), `port_numbers` correlation for exotic hubs.
- **New sections:** TEE/keyboard FRP, carrier (de-bloating) profiles, EDL-only utilities.
- **Community:** translations, a device-compatibility wiki, reproducible firmware-archive catalog.
- **Safety:** dry-run mode, automatic pre-flash backup, brick-recovery docs.

---

## Contributors

Everyone who helps — code, docs, device reports, or a tested combo — is listed
here and celebrated. Open a PR adding yourself (alphabetical by username, one
link line):

```md
- [@your-github](https://github.com/your-github) — what you did
```

The first contributors to this project made it real. Be next.

---

**Questions?** Open a discussion/issue. Thanks for helping advance free, open
flashing software on Linux. 🚀