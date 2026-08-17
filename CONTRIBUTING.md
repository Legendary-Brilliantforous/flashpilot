# 🧑‍💻 Contributing to Brilliant Flashing Tool

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
| **Core / protocol engine** | `src/` | Rust | Raw USB, all bootloader protocols (`brilliant-bridge` CLI) |
| **Flow orchestrator** | `python/core/frp.py` | Python | Turns operations into a list of human-readable steps |
| **GUI studio** | `python/gui/qt_app.py` | Python / PyQt6 | The user-facing workbench |

Python never talks to USB directly. It shells out to `target/release/brilliant-bridge`
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
- **Bug reports** — use the [bug report template](https://github.com/Legendary-Brilliantforous/brilliant-flashing-tool/issues/new?labels=bug&template=bug_report.yml): steps, logs, `brilliant-bridge detect` output, device model + firmware version.
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

## Architecture tour (10 minutes)

1. **`src/main.rs`** — a ~60-command CLI. Each `match` arm is one command
   (`detect`, `mtk-flash`, `qcom-firehose`, `spd-format`, `odin-pit`, ...).
2. **`src/usb.rs`** — finds devices by VID/PID, gives you endpoints.
3. **`src/odin.rs`** — Samsung download mode (the reverse-engineered Odin 3
   protocol, Heimdall-derived). Reads/writes PIT, flashes partitions.
4. **`src/mtk*.rs`** — MediaTek BROM → preloader → Download Agent handshake,
   scatter parsing, GPT partition work, SLA keys, BROM exploits.
5. **`src/qualcomm/`** — Sahara (EDL) handshake and Firehose sessions.
6. **`src/spd.rs`** — Spreadtrum/UNISOC BSL: FDL download, format, FRP, backup.
7. **`python/core/frp.py`** — the **heart of the GUI**. `JOBS` maps
   `job → mode → [flow keys]`. `FLOWS` maps a flow key to a function returning a
   `Flow` (a list of `Step`s). 8 jobs, 68 flows, 8 modes.
8. **`python/gui/qt_app.py`** — builds all sections (Samsung / MTK / QC / SPD /
   Battery / Network / Settings) and the sub-tab workbenches.

### Data flow

```
click button
  → _run_ops_flow(job, mode, method, name)
  → frp.flow_for(...) -> Flow (list of Steps)
  → each Step runs in a worker thread, calling bridge._run([...])
  → bridge spawns target/release/brilliant-bridge ...
  → Rust does USB I/O, prints JSON/text
  → Python parses + emits _ui.line() signals
  → GUI updates console / status / progress safely
```

---

## How to add a new flow

The simplest feature you can ship. Open `python/core/frp.py`:

```python
def flow_my_method():
    return Flow(
        "my method",                       # human-readable name
        [
            Step("step 1", lambda ctx, log: log("hello")),
            Step("step 2", lambda ctx, log: bridge._run([...], timeout=60)),
        ],
    )

FLOWS["my_method"] = flow_my_method
```

Then wire it into a job's mode in `JOBS`:

```python
"FRP bypass": {
    ...
    "ADB": ["adb_frp", "frp_browser", "my_method"],
    ...
}
```

That's it — the flow appears in the GUI's dropdown/sub-tab automatically and is
also reachable from the CLI. **This is the highest-value/easiest-entry area.**

> Use `log(...)` inside steps for console output, `ctx` for state you want to
> carry between steps, and `bridge._run(...)` for anything that hits the Rust
> binary. Keep steps cooperative with `request_cancel()` where appropriate so the
> Stop button works.

---

## Adding a new USB protocol / Rust command

1. Add your module under `src/` (e.g. `src/myproto.rs`).
2. Add `mod myproto;` to `src/main.rs` and a new `match` arm + usage line.
3. Return `Result<T>` via `crate::error` and use `serde_json` for structured output.
4. Expose it from Python in `python/core/bridge.py` as a wrapper around `_run([...])`.
5. Build a `Flow` in `frp.py` that calls it.
6. Add a test if you can — unit tests live in `src/*.rs` (`#[test]`) and `tests/`.

**Protocol hygiene:** cite your source (forums, clean-room write-ups, other OSS
projects) in the module docstring. We don't include proprietary blobs — only the
protocol implementation.

---

## GUI guidelines

- **PyQt6 only.** No other Qt bindings, no extra UI deps (see `requirements.txt`).
- Match the existing visual language: `_btn_ghost()`, `_btn_primary()`,
  `_card_qss()`, `SectionTitle`, `C[...]` theme colors, `FlowLayout` for button grids.
- All colors come from the active theme (`ACCENT_THEMES`). Don't hardcode hex.
- **Thread rule:** background work goes in `threading.Thread`; GUI updates happen
  only through `self._ui.*` signals (`.line`, `.status`, `.toast`, `.ui`, `.progress`).
- Keep long-lived UI rows scrollable — the chip pages wrap content in a
  `QScrollArea` so they never crush on small windows.
- New sub-tabs reuse `SamsungSubTabs` + a `QStackedWidget` (see `_build_chip_ops_section`).

---

## Testing

```bash
cargo test --release        # Rust unit tests (incl. BROM exploit, SLA, MTK)
python3 -m pytest tests/    # Python flow / MTK / PIT tests
```

Test suite layout:

- `tests/test_frp_flow.py` — `Flow`/`Step` execution + cooperative cancellation.
- `tests/test_mtk.py` — MediaTek logic (scatter, DA, boot-stage helpers).
- `tests/test_pit.py` — Samsung PIT parsing.

If you add Rust logic, add `#[test]` modules in the same file. If you add flows,
add a pytest that runs the flow with a fake/offline context where possible.

---

## Pull request checklist

- [ ] `cargo build --release` passes.
- [ ] `cargo test --release` passes (or note why not runnable).
- [ ] `python3 -m pytest tests/` passes.
- [ ] New flow: wired into `JOBS` (job + mode) so it's reachable in the GUI.
- [ ] New Rust command: added to `main.rs` usage text + `bridge.py` wrapper.
- [ ] GUI changes: themed colors, signal-based updates, scroll-safe layouts.
- [ ] No secrets/binaries/device-identifying data added to the repo.
- [ ] Updated the README feature matrix if you added a capability.

Keep PRs focused. One feature or fix per PR is ideal; reference the issue number.

---

## Roadmap & ideas

We'd love contributors to champion any of these:

- **Ports & packaging:** Flatpak / AppImage / AUR, CI matrix (Linux distros), `pip`/`cargo` release flow.
- **MediaTek:** more DA variants, scatter edge cases, eMMC/UFS backup dumps.
- **Qualcomm:** rawprogram/patch XML edge cases, fh-loader combos, more chip PIDs.
- **Samsung:** additional HID download-mode payloads per SoC, Odin multi-partition UX polish.
- **New sections:** IMEI repair, TEE/keyboard FRP, carrier (de-bloating) profiles, EDL-only utilities.
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