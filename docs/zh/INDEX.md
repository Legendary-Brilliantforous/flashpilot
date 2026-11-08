# FlashPilot — 索引

Language switcher: [English](../INDEX.md) · [Français](../fr/INDEX.md) · [Español](../es/INDEX.md) · [Deutsch](../de/INDEX.md) · **简体中文** · [Русский](../ru/INDEX.md) · [Português](../pt/INDEX.md) · [日本語](../ja/INDEX.md) · [العربية](../ar/INDEX.md) · [हिन्दी](../hi/INDEX.md) · [Türkçe](../tr/INDEX.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

README 负责营销。这个文件是工程索引 —— 每个文件夹、作用，以及从哪里开始。

## 运行

```bash
# GUI
python main.py

# CLI（桥接）— 同一协议，无 GUI
./target/release/flashpilot-bridge detect-all
./target/release/flashpilot-bridge spd-detect
```

## 根目录结构（17 个条目）

| 条目 | 作用 | 何时打开 |
|---|---|---|
| `main.py` | 应用入口。把仓库加入 `sys.path` 并调用 `python.gui.qt_app.main()`。 | 修改应用启动方式。 |
| `pyproject.toml` | Python 包元数据（name=flashpilot、依赖、构建后端）。 | 添加 Python 依赖或提高版本。 |
| `Cargo.toml` / `Cargo.lock` | Rust 核心（`flashpilot-bridge` 二进制）。 | 修改桥接 CLI 或添加新协议。 |
| `python/` | Rust 引擎之上的薄 Python 层：`python/core/`（shim + GUI 辅助）与 `python/gui/`（PyQt6）。所有流程位于 `src/flows.rs`。 | GUI 与设备通道。 |
| `src/` | Rust 源码。布局镜像 `python/core/`。 | 添加新桥接命令或修改 USB 协议。 |
| `tests/` | pytest 套件。约 149 个测试，约 1s 运行。 | 运行 `.venv/bin/python -m pytest tests/ -q`。 |
| `scripts/` | 独立 shell 工具。当前：`dump-connected.sh`、`validate_mtp_at.py`。 | 需要非 GUI 批量操作时。 |
| `docs/` | README 资源（截图、logo）。 | README 使用。 |
| `packaging/` | `.deb` 构建脚本 + 控制文件。 | 发布。 |
| `root/` | udev 规则（让用户手机无需 sudo 工作）。 | 一次性设置。 |
| `operations/` | **按任务的文档树** —— 见下文 "operations/" 部分。 | 理解某项任务（FRP、MDM、屏幕锁等）。 |
| `build/` | **所有 gitignored 的构建/运行时产物** —— 见下文 "build/" 部分。 | 几乎从不打开。 |
| `.github/` | CI 工作流、issue 模板。 | 修改 CI。 |
| `LICENSE` `CODE_OF_CONDUCT.md` `CONTRIBUTING.md` `SECURITY.md` `DESCRIPTION.md` | 标准项目元数据。 | 发布时。 |

## `python/` 布局

```
python/
├── main.py                 <- app entry (adds repo to sys.path, calls python.gui.qt_app.main)
├── gui/                    <- PyQt6 app
│   ├── qt_app.py           <- The main window + every device-mode UI (~12k LOC)
│   ├── devices.py          <- Data-driven "supported devices" drill-down (brand -> model -> action)
│   ├── theme.py            <- Design tokens (colors, button styles, version helpers)
│   ├── animations.py       <- Painted glyphs: connection scene, status orb, etc.
│   ├── nav.py              <- Top-level navigation rail + OEM chip bar
│   ├── toast.py            <- Toast notifications
│   └── supported_devices.json  <- The database of which model gets which action
└── core/                   <- Thin Python layer (no Qt deps; delegates to Rust bridge)
    ├── core.py             <- FLOWS/JOBS/MODES mirror (hardcoded cache + Rust flow_list())
    ├── bridge.py           <- Talks to the Rust `flashpilot-bridge` binary
    ├── flow.py             <- Flow/Step primitives + cancellation
    ├── jobs.py             <- FlashJob lifecycle (isolated job layer)
    ├── cancel.py           <- Cooperative cancellation registry
    ├── devices.py          <- Multi-device identity (stable keys, list, resolve, transport mapping)
    ├── frp.py              <- FRP-only re-export surface (name == responsibility)
    ├── mtk.py              <- MTK PIDs/stages/chips (0003=BROM, 2000=preloader)
    ├── mtp.py              <- Samsung MTP/AT (multi-sequence ADB enable)
    ├── pit.py pitstore.py  <- Samsung PIT parser + cache
    ├── adb.py device_info.py actions.py experimental.py fus.py
    └── (no flows/ dir)     <- flows live in src/flows.rs; Python only delegates via bridge.flow_run()
```

**流程位于 Rust。** `python/core/core.py` 是薄 shim：`_RustFlow` 将执行委托给 `bridge flow-run <key>`。规范的注册表是 `src/flows.rs`（`flow!` 宏，约 280 行）；Python 镜像它以供 GUI 查找。

## `src/` 布局（Rust）

```
src/
├── main.rs                 <- All CLI dispatch (eprintln! is the "log" channel) + flow-run
├── flows.rs                <- THE flow registry (flow! macro; FLOWS/JOBS/MODES)
├── usb/                    <- libusb context, descriptor parsing, filtering (mod.rs + filtering.rs)
├── devices.rs              <- merged USB+ADB device rows
├── sam_download.rs         <- Samsung Download/Odin session (odin-* commands)
├── sam_errors.rs sam_setup.rs sam_*.rs  <- Samsung helpers
├── mtk.rs mtk_da.rs        <- MediaTek BROM/DA flashing
├── mtk_exploit.rs          <- BROM exploits (bypass/kamakiri2/crash-to-BROM)
├── mtk_sla.rs mtk_sla_keys.rs <- Secure Lock Authentication
├── mtk_daloader.rs         <- DA container parsing
├── qualcomm/               <- EDL: Sahara + Firehose + GPT
├── spd.rs                  <- UNISOC BSL (BSL_CMD_*, BSL_REP_*, FDL1/FDL2)
├── pac.rs                  <- SPD PAC extract/pack
├── pit.rs                  <- Samsung PIT parser
├── mtp.rs at.rs adb.rs     <- MTP, AT command, ADB plumbing
├── fastboot.rs             <- native fastboot transport
├── moto_flash.rs           <- Motorola staged fastboot FRP
├── apple.rs                <- Apple usbmuxd/lockdown
├── bulk.rs hid.rs          <- bulk + HID helpers
├── fwtar.rs sparse.rs imgtools.rs <- firmware tar/sparse/boot-vbmeta
├── hostinfo.rs             <- host eMMC/UFS health
├── config.rs error.rs util.rs device.rs
└── (no odin.rs)            <- Odin logic lives in sam_download.rs
```

## `operations/` —— 按任务的文档树

这些文件夹包含 **每个操作的 README 树**，解释每个任务如何工作、使用哪些 flow 键、支持哪些设备，以及已知注意事项。它们不是代码 —— 树是纯 Markdown（过去清理移除了曾经在这里的过时 `.py` shim；没有任何东西导入 `operations/`）。代码位于 `src/flows.rs`（`flow!` 注册表；`python/core/core.py` 是薄 shim）和领域特定模块（`knox.py`、`qcn.py`、`imei.py`、`emmc.py` 等）。`operations/` 中的 README 面向最终用户 / 商业工具研究人员；代码是真相来源。

| 文件夹 | 作用 | 真实代码在 |
|---|---|---|
| `operations/apple/` | Apple iCloud、激活锁、MDM、移除密码/丢失模式 | Rust 流程（`src/flows.rs`：`apple_*` 行、`flow-run` CLI） |
| `operations/frp/` | 按引擎的 FRP 绕过 + 按设备研究笔记。**从 `operations/frp/INDEX.md` 开始**。 | Rust 流程（注册表 `src/flows.rs`、`flow-run` CLI）；薄 shim `python/core/core.py` |
| `operations/mdm/` | MDM / 设备所有者解锁 + 按品牌设备笔记 | Rust 流程（注册表 `src/flows.rs`、`flow-run` CLI） |
| `operations/screen_unlock/` | 屏幕锁移除（ADB / recovery / download / 综合） | Rust 流程（注册表 `src/flows.rs`、`flow-run` CLI） |
| `operations/battery/` | 电池报告 / 修复 / 负载测试（经 ADB） | Rust 流程（注册表 `src/flows.rs`、`flow-run` CLI） |
| `operations/network/` | SIM 状态、DNS、射频重置 | Rust 流程（注册表 `src/flows.rs`、`flow-run` CLI） |
| `operations/carrier_unlock/` | 运营商锁（Apple、MTK） | Rust 流程（注册表 `src/flows.rs`、`flow-run` CLI） |
| `operations/flashing/` | 按厂商刷写指南（Samsung Odin、MTK DA、Qualcomm EDL、UNISOC SPD、PIT） | Rust 流程（注册表 `src/flows.rs`、`flow-run` CLI） |
| `operations/usb/` | USB 枚举与检测笔记 | `src/usb/`、`src/devices.rs`、`python/core/devices.py` |

## `build/` —— gitignored 的运行时/构建产物

| 子目录 | 内容 | 由谁创建 |
|---|---|---|
| `build/target/` | Rust `cargo build` 输出 | `cargo build` |
| `build/dist/` | `.deb` 包 | `packaging/build-deb.sh` |
| `build/cache/` | 按设备的 TAR 缓存与逆向工程转储 | GUI / `scripts/dump-connected.sh` |
| `build/mdm_qr/` | 生成的 MDM 配置 QR 码 | GUI MDM 流程 |
| `build/pit/` | 缓存的 `.pit` 分区表文件 | GUI PIT 流程 |

**规则：** 永远不要 `git add` `build/` 中的任何东西。若要清除状态，删除子目录即可 —— 会被重建。

## 添加新功能（“我该动哪个文件？”作弊表）

| 你想... | 动 |
|---|---|
| 添加新设备到支持列表 | `python/gui/supported_devices.json` |
| 为受支持的设备添加新按厂商操作 | `src/flows.rs`（添加一行 `flow!(...)`）；Python 通过 `bridge.flow_list()` 自动发现 |
| 为已有关注点添加新的 ADB 流程 | 同上（Rust `src/flows.rs`） |
| 添加新的桥接 CLI 命令 | `src/<关注点>.rs` + `src/main.rs`（match 中的 `<cmd>` 分支） |
| 添加新的顶级导航页面 | `python/gui/qt_app.py`（`_build_*_page` + `_section_index`） |
| 添加新的设计颜色 / 按钮样式 | `python/gui/theme.py`（`C` 字典 / `_btn_*()`） |
| 记录新设备的按任务笔记 | `operations/<任务>/<品牌>/<型号>.md` |
| 添加测试 | `tests/test_<领域>.py`，遵循 `test_mtk.py` 模式 |

## 操作运行器如何工作（读一次）

GUI 从不直接调用流程。按操作的设备选择器（`FlashPilotWindow._choose_device`）先解析稳定设备键；然后 `_run_ops_flow` / `_run_job_flow` 调用 `python.core.core.flow_for(job, mode, method)`，返回 `Flow()` 对象（`Step()` 列表），随后在 `devices.device_scope(key)` 内的 worker 线程上调用 `flow.run(ctx, log)`（使每个 resolver 目标为所选手机）。每个流程记录到 GUI 接到其控制台的 `log(line)` 可调用对象。取消按设备作用域（`flow.request_cancel(key)`；无键广播停止一切），在每个 `_run` 顶部检查。

要添加一个流程：在 `src/flows.rs` 中添加一行 `flow!("my_op", "My op", "Job Name", "MODE")`。Python 通过 `bridge.flow_list()` 自动发现，GUI 的 job/mode/method 下钻会自动拾取。Rust `flow-run` CLI 执行它；resolver 必须接受目标 serial / `vid:pid@bus:addr`（见 `src/device.rs`）。
