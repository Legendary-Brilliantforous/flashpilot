Language switcher: [English](../../CONTRIBUTING.md) · [Français](../../fr/CONTRIBUTING.md) · [Español](../../es/CONTRIBUTING.md) · [Deutsch](../../de/CONTRIBUTING.md) · [简体中文](../../zh/CONTRIBUTING.md) · [Русский](../../ru/CONTRIBUTING.md) · [Português](../../pt/CONTRIBUTING.md) · [日本語](../../ja/CONTRIBUTING.md) · [العربية](../../ar/CONTRIBUTING.md) · **हिन्दी** · [Türkçe](../../tr/CONTRIBUTING.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

# 🧑‍💻 FlashPilot mein yogdaan (Contributing)

Thanks for stopping by! Yeh project reverse-engineered protocols aur open knowledge
par bana hai — har contribution ise zyada capable, zyada reliable banata hai, aur
paid Windows suites ke closer laata hai. Aapko flashing expert banne ki jarurat
nahi hai help karne ke liye.

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

[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) dekho. Respectful raho, good intent
assume karo, aur discussions technical aur helpful rakho. Yeh hobbyist-turned-serious
project hai: hum beginners aur veterans dono ko welcome karte hain. Harassment,
gatekeeping, ya secrets/credentials commit karna tolerate nahi kiya jayega. Protocol
payloads tab welcome hain jab unki provenance aur license documented ho.

---

## How the project is organized

Do halves saath kaam karte hain:

| Layer | Location | Language | Role |
|---|---|---|---|
| **Core / protocol engine** | `src/` | Rust | Raw USB, sab bootloader protocols (`flashpilot-bridge` CLI) |
| **Flow registry** | `src/flows.rs` | Rust | `flow!` macro rows → `FLOWS` / `JOBS` / `MODES` (source of truth) |
| **Flow shim** | `python/core/core.py` | Python | Thin `_RustFlow` wrappers + `JOBS` fallback; `bridge flow-run` par delegate |
| **Device identity** | `python/core/devices.py` | Python | Stable keys, device list, target re-resolution, thread scope |
| **FRP surface** | `python/core/frp.py` | Python | FRP-only re-export (name == responsibility) |
| **GUI studio** | `python/gui/` | Python / PyQt6 | Workbench (`qt_app.py`), pages (`devices.py`), theme, animations |

Python kabhi USB se directly baat nahi karta. Yeh `target/release/flashpilot-bridge`
(Rust binary) ko shell out karta hai, jo JSON/text return karta hai. GUI sirf
worker threads ke signals sunta hai — background thread se kabhi widgets touch mat karo.

---

## Ways to contribute

No coding? No problem:

- **Testing on real hardware** — report karo ki kaun se devices/firmwares par ek
  flow kaam karta hai.
- **Documentation** — README, is file, aur flow descriptions improve karo.
- **Firmware / DA / combo archives** — legitimate, freely available binaries ke
  pointers.
- **Translations & themes** — GUI themable hai; new accent packs easy wins hain.
- **UI/UX** — mockups, accessibility passes, keyboard-shortcut design.
- **Bug reports** — bug report template use karo (steps, logs,
  `flashpilot-bridge detect` output, device model + firmware version).
- **Code** — see below.

> 💡 **New here?** Issue tracker par **`good first issue`** label dekho —
> curated, beginner-friendly tasks jo fully scoped aur safe to pick up hain.

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

App native PyQt6 window kholti hai. **Settings → Tools** page par jaakar dekho
ki bridge build ho chuka hai aur ADB detect ho raha hai.

---

## Migrating from an older checkout (read this first if you're returning)

Churn ka plain note: 1.2.0 aur abke beech humne central module rename kiya,
one god-file ko focused modules mein split kiya, har job rename kiya, aur
dozen files add kiye. Yeh purane imports, purane docs references, aur
out-of-tree scripts ko break karta hai jo `python.core.frp` ke against
likhe the. Sorry for that — god-file kill karne, MTK PID mix-up fix karne,
aur multi-device support possible banane ke liye bina hacks ke yeh ek hi tarika
tha. Yeh section complete adaptation guide hai; kuch bhi deprecated-gradually
nahi hai, sab ek saath change hua, to table ek baar work karo aur aap current ho.

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

### The Rust move (current architecture — the table above is history)

Upar ka split hone ke baad, engines Rust mein move ho gaye aur Python side
thinned out. Current truth:

- **Flows `src/flows.rs` mein hain** (registry + `flow-run <key> [target]
  [--code/--partition/--file/--dpc ...]`). `flow-list` source of truth hai — docs
  mein koi flow key cite karne se pehle wahan verify karo.
- **`python/core/core.py` thin shim hai** (~450 lines): `_RustFlow` `bridge flow-run`
  par delegate karta hai, registry bridge se aata hai with `JOBS` fallback. 16
  per-domain engine modules (`knox`, `qcn`, `emmc`, `imei`, `apple`, `ofp`, `pac`,
  `health`, `flashing`, `spd_adb`, `integrity`, `fastboot`, `usb_watch`, `compat`,
  `updater`, `safety`) delete kiye gaye — new docs mein unhe reference mat karo.
- **GUI Python mein rehta hai** (`python/gui/qt_app.py` + `devices.py`); Rust
  registry via `bridge.flow_list()` consume karta hai.
- Old test files for removed Python flows unke saath delete hue; coverage per-area
  suites + cargo `flows::tests` hai.

### API changes you must adapt to

- **Resolvers take `key=None`.** `find_samsung()`, `_download_mode_device()`,
  `_wait_for_adb()`, `_wait_mtk_brom_target()`, `_mtk_retry()`,
  `wait_clean_download_mode()`, `pit_contract()` sab optional stable device key accept
  karte hain (ambient thread scope by default — old call sites kaam karte rahenge,
  jab koi key set nahi hota first-match behavior preserved).
- **Cancel is per-device.** `request_cancel()` / `clear_cancel()` /
  `cancel_requested()` in `flow.py` aur `bridge.py` accept `key=None`.
  Keyless `request_cancel()` abhi bhi broadcast karta hai (global STOP); keyless checks
  ambient scope consult karte hain, phir broadcast bus.
- **Run-guard is per-device.** `_flow_start(label, destructive, key=None)` /
  `_flow_end(key=None)` / `_flow_busy_msg(key=None)` in `qt_app.py`; old
  `_FLOW_LOCK` / `_FLOW_LABEL` globals gayab hue (per-key dicts +
  `_flows_running()` se replace).
- **Runners take `device_key=None`.** `_run_ops_flow()` / `_run_job_flow()`
  device picker dikhate hain jab multiple phones match karein, phir
  `ctx["device_key"]` (+ `ctx["target"]` where resolvable) set karte hain aur
  `devices.device_scope()` ke andar run karte hain.
- **New transport mode `"SPD"`** in `MODES` (VID `0x1782`); new jobs
  `Knox / Warranty`, `QCN / Modem`, `IMEI Repair / Change`, `eMMC / UFS`.
- **Job names are verb-first** (`Remove FRP`, not `FRP bypass`; see README).
  Agar aapki branch abhi old names reference karti hai, to “Architecture tour”
  table ke names par rename karo.
- **MTK PIDs are mtkclient-convention**: `0e8d:0003` = BROM,
  `0e8d:2000` = preloader. Kai old comments/logs mein swapped the;
  trust `mtk.pid_stage()` / Rust `boot_stage_for()`, not old strings.

### If you have an open PR from before the restructure

1. Rebase onto the new tree; expect conflicts confined to imports and the
   `JOBS`/`FLOWS` blocks.
2. Niche checklist run karo — `pytest` stale key/name references immediately catch
   karega (registry tests assert every `JOBS` method resolves).
3. If your PR touched `flows/` (the removed split-package experiment): woh
   directory gayab hai, change ko `core.py` + domain module par port karo.

---

## Architecture tour (10 minutes)

1. **`src/main.rs`** — 80+-command CLI. Har `match` arm ek command hai
   (`detect`, `mtk-flash`, `mtk-crash-brom`, `qcom-firehose`, `spd-format`,
   `odin-pit`, ...).
2. **`src/usb.rs`** — devices VID/PID se find karta hai, endpoints deta hai (plus
   stable `port_numbers` re-enumeration-proof addressing ke liye).
3. **`src/odin.rs`** — Samsung download mode (reverse-engineered Odin 3
   protocol, Heimdall-derived). Reads/writes PIT, flashes partitions
   (persistent `odin-agent` session multiplexer incl.).
4. **`src/mtk*.rs`** — MediaTek BROM (`0e8d:0003`) → preloader (`0e8d:2000`) →
   Download Agent handshake, scatter parsing, GPT partition work, SLA keys,
   BROM exploits, crash-to-BROM. ⚠️ PID convention mtkclient-style hai:
   `0003`=BROM, `2000`=preloader — swap mat karo.
5. **`src/qualcomm/`** — Sahara (EDL) handshake aur Firehose sessions.
6. **`src/spd.rs`** — Spreadtrum/UNISOC BSL: FDL download, format, FRP, backup,
   PAC extract/pack.
7. **`src/flows.rs`** — app ka **heart**. `flow!(key, label, job, mode)` rows
   `FLOWS` / `JOBS` / `MODES` registry build karte hain (~280 rows, 13 jobs,
   9 modes incl. `SPD`). `python/core/core.py` sirf GUI lookup ke liye mirror karta hai.
8. **`python/core/devices.py`** — multi-device identity. Stable keys
   (`adb:<serial>` → `usb:<port-path>` → volatile fallback), `list_devices()`,
   `resolve_usb_target()`, aur `device_scope()` thread-local jo chosen phone
   resolvers tak carry hota hai.
9. **`python/gui/qt_app.py`** — all sections (Samsung / MTK / QC / SPD /
   Battery / Network / Settings) aur sub-tab workbenches build karta hai, plus
   per-operation device picker aur per-device run-guard.

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

Sabse simple feature jo aap ship kar sakte ho. `src/flows.rs` open karo aur ek
row add karo:

```rust
flow!("my_method", "My method", "Remove FRP", "ADB"),
```

Key short snake_case hota hai (`flow_` prefix nahi). Python `bridge.flow_list()`
via auto-discover karta hai aur GUI ka job/mode/method drill-down use karta hai;
execution `flashpilot-bridge flow-run my_method` se hota hai.

Phir (sirf jab new low-level protocol work ho) bridge command
`src/<concern>.rs` + `src/main.rs` mein add karo. Job/mode wiring flow row mein
pehle se hai.

Flow automatically GUI dropdown/sub-tab aur CLI dono mein appear karta hai. **Yeh
highest-value/easiest-entry area hai.**

> Steps ke andar `log(...)` use karo console output ke liye, `ctx` state carry
> karne ke liye, aur `bridge._run(...)` kisi bhi Rust binary hit ke liye. Steps
> cooperative rakhne ke liye `cancel_requested()` with appropriate places use karo
> taki Stop kaam kare (cancel per-device scoped hai — see below).

### Rules every flow must follow

- **Never grab "the" device.** Koi bhi resolver add karte waqt `key=None` (ambient
  thread scope) accept karo, aur filter by it — dekho `devices.device_key()`,
  `devices.match_key()`, `devices.device_scope()`. GUI per operation scope set
  karta hai; headless callers bhi kar sakte hain.
- **Job names are verb-first** (`Remove FRP`, `Flash Firmware`, `Unlock Carrier`).
  **Flow keys are short snake_case** (`adb_frp`, not `flow_adb_frp`); single
  historical alias (`fastboot_read`) remove ho chuka — aliases mat add karo.
- **MTK PID convention is mtkclient-style**: `0e8d:0003` = BROM (held),
  `0e8d:2000` = preloader. Rust, Python, GUI labels, aur docs sab agree karna
  chahiye.
- **EXPERIMENTAL writes** (Knox/IMEI/QCN/eMMC) `experimental.check_gate_strict()`
  ke through per-run ack ke saath jaane chahiye — stored ack kabhi
  auto-pass nahi hona chahiye. GUI-gate `_EXPERIMENTAL_FLOW_MAP` + amber
  collapsible pattern chip page par (kabhi global LAB page nahi).
- **Bridge targets volatile hote hain** (`vid:pid@bus:addr` re-enumeration par
  change hota hai). Sessions open karne se pehle stable key se re-resolve karo
  (`devices.resolve_usb_target()`); odin4 ko pin karo
  `-d /dev/bus/usb/BBB/AAA` ke saath.

---

## Adding a new USB protocol / Rust command

1. Apna module `src/` ke under add karo (e.g. `src/myproto.rs`).
2. `src/main.rs` mein `mod myproto;` aur new `match` arm + usage line add karo.
3. `crate::error` via `Result<T>` return karo aur structured output ke liye
   `serde_json` use karo.
4. Python side `python/core/bridge.py` mein wrapper expose karo around `_run([...])`.
5. `core.py` mein `Flow` build karo jo usse call kare (flow rules follow karo).
6. Test add karo if possible — unit tests `src/*.rs` (`#[test]`) aur `tests/` mein.

**Protocol hygiene:** module docstring mein apna source cite karo (forums,
clean-room write-ups, other OSS projects). Hum proprietary blobs include nahi karte —
sirf protocol implementation.

---

## GUI guidelines

- **Sirf PyQt6.** Koi other Qt bindings, koi extra UI deps (requirements.txt dekho).
- Existing visual language match karo: `_btn_ghost()`, `_btn_primary()`,
  `_card_qss()`, `SectionTitle`, `C[...]` theme colors, `FlowLayout` button grids ke liye.
- **Theme tokens, not raw accent:** fills `C['accent'/'grad_a'/'grad_b']` use kar
  sakte hain, lekin focus rings, selected-tab borders aur checkboxes MUST neutral
  `C['focus_ring']` / `C['sel_border']` use karen — otherwise red accent themes
  (Crimson, Sunset) focus states mein red leak karte hain. Chrome ke liye kabhi hex hardcode mat karo.
- **Thread rule:** background work `threading.Thread` mein; GUI updates sirf
  `self._ui.*` signals (`.line`, `.status`, `.toast`, `.ui`, `.progress`) se.
- **Animations:** `Motion.shake()` / `Motion.rubber()` per widget mutually exclusive
  hain (guarded by `_anim_lock`) — kabhi concurrently run mat karo ya call sites
  `QTimer.singleShot` se serialize kar. Koi `setFixedSize`, restyled borders, ya
  disabled layouts behind nahi chorna chahiye; `cleanup()` sab restore karta hai.
- Long-lived UI rows scrollable rakho — chip pages content ko `QScrollArea`
  wrap karte hain taki chhote windows par crush na ho.
- New sub-tabs `SamsungSubTabs` + `QStackedWidget` reuse karte hain (see
  `_build_chip_ops_section`).
- Action buttons `NoFocus` (no sticky focus ring); checkable tab pills active state
  ke liye `checked` styling retain karte hain.

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

Agar aap Rust logic add karte ho, same file mein `#[test]` modules add karo. Agar
flows add karte ho, jahan possible ho fake/offline context se flow run karne ka
pytest add karo. New resolvers `key=None` accept karna chahiye; new tests multi-device
filtering cover karna chahiye (see `test_devices.py`) single phone assume nahi.

---

## Pull request checklist

- [ ] `cargo build --release` passes.
- [ ] `cargo test` passes (ya note karo why not runnable).
- [ ] `.venv/bin/python -m pytest tests/` passes.
- [ ] New flow: wired into `JOBS` (job + mode) taki GUI mein reachable ho.
- [ ] New resolver: `key=None` (ambient scope) accept kare + multi-device test cover ho.
- [ ] New Rust command: `main.rs` usage text + `bridge.py` wrapper mein add ho.
- [ ] GUI changes: themed colors (neutral focus tokens!), signal-based updates, scroll-safe layouts.
- [ ] No secrets/binaries/device-identifying data repo mein add ho.
- [ ] README feature matrix updated if capability add ki.

PRs focused rakho. One feature ya fix per PR ideal; issue number reference karo.

---

## Platform support policy (read before porting)

**Linux is the only supported platform.** Development, hardware testing aur
releases Linux target karte hain. Windows/macOS issues unsupported declare karke
close kiye jayenge — unless they code ke form mein aayein, as follows.

**Why:** `odin4` Linux-only hai; Windows USB per-mode drivers chahiye (Zadig /
QDLoader / Samsung) jo remotely debug nahi ho sakte; macOS signing/notarization
negligible demand ke liye. README ka “Platform support” section full reasoning
aur open invitation dekho argue karne ke liye.

**How to contribute a port anyway (accepted shape):**

1. Flows ya GUI mein `sys.platform` checks sprinkle mat karo.
2. `python/core/platform.py` add karo backend functions ke saath —
   `open_file_manager()`, `detach_kernel_drivers(target)`,
   `usb_device_path(bus, addr)`, `needs_udev_setup()`,
   `kernel_module_loaded(name)` — Linux implemented, others `NotImplementedError`
   with helpful message raising.
3. Existing Linux-only call sites (`xdg-open`, `rmmod cdc_acm`,
   `/dev/bus/usb`, `lsmod`, udev docs) migrate karo onto it, one PR per
   call-site group.
4. Windows/macOS backend PR must include: backend implementation, docs
   updates, aur CI ya maintainer-verified manual test evidence. Core team
   non-Linux test hardware own nahi karta — port PRs apne author ki ability par
   jite/marte hain prove karne ki.

**PySide6 vs PyQt6:** PySide6 (LGPL, MIT-compatible — PyQt6 GPLv3 hai)
migration wanted but GUI smoke-test coverage par blocked hai. If aap lete ho:
`pyqtSignal→Signal`, `pyqtProperty→Property`, `PyQt6.sip→shiboken6`
mechanically convert karo, `tests/` mein offscreen window/picker/guard smoke
tests extend karo, behavior pixel-identical rakho. Pehle Discussions mein
discuss karo.

## Roadmap & ideas

We'd love contributors to champion any of these:

- **Ports & packaging:** Flatpak / AppImage / AUR, CI matrix (Linux distros), `pip`/`cargo` release flow.
- **MediaTek:** more DA variants, scatter edge cases, eMMC/UFS backup dumps, new `hw_code` entries in `CHIP_NAMES` (with a cited source — never guess hex codes).
- **Qualcomm:** rawprogram/patch XML edge cases, fh-loader combos, more chip PIDs.
- **Samsung:** additional HID download-mode payloads per SoC, Odin multi-partition UX polish.
- **Multi-device:** per-device console tabs/progress, per-device STOP granularity (STOP currently broadcasts), `port_numbers` correlation for exotic hubs.
- **New sections:** TEE/keyboard FRP, carrier (de-bloating) profiles, EDL-only utilities.
- **Community:** translations, device-compatibility wiki, reproducible firmware-archive catalog.
- **Safety:** dry-run mode, automatic pre-flash backup, brick-recovery docs.

---

## Contributors

Everyone who helps — code, docs, device reports, ya tested combo — yahan list
hota hai aur celebrated. PR open karo apne aap add karne ke liye (username se
alphabetical, one link line):

```md
- [@your-github](https://github.com/your-github) — what you did
```

Is project ke first contributors ne ise real banaya. Be next.

---

**Questions?** Discussion/issue open karo. Linux par free, open flashing software
advance karne ke liye thanks. 🚀
