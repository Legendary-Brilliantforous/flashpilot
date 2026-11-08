# 🔧 FlashPilot

Language switcher: [English](../README.md) · [Français](../fr/README.md) · [Español](../es/README.md) · [Deutsch](../de/README.md) · **简体中文** · [Русский](../ru/README.md) · [Português](../pt/README.md) · [日本語](../ja/README.md) · [العربية](../ar/README.md) · [हिन्दी](../hi/README.md) · [Türkçe](../tr/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

> **一款 Linux 下的开源 Samsung 固件刷写与修复工作台 —— 作为 Odin / Heimdall 的替代品，用于刷写 Galaxy 手机（Download/Odin 模式）、MediaTek（BROM/DA）、Qualcomm（EDL）与 Spreadtrum/UNISOC 设备。**

**搜索关键词：** Samsung flashing tool · Odin alternative · Android firmware flashing Linux · Heimdall GUI · Galaxy phone repair · MTK BROM flash · Qualcomm EDL · FRP unlock · UNISOC flashing · device firmware tool · mobile repair · Android bootloader · USB flashing · Linux flashing suite · proprietary tool alternative

[![Rust](https://img.shields.io/badge/Rust-1.70+-orange?logo=rust&logoColor=white)](https://www.rust-lang.org)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-41cd52)](https://www.riverbankcomputing.com/software/pyqt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![CI](https://github.com/Legendary-Brilliantforous/flashpilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Legendary-Brilliantforous/flashpilot/actions)
[![Good First Issues](https://img.shields.io/github/issues/Legendary-Brilliantforous/flashpilot/good%20first%20issue)](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
[![Contributors](https://img.shields.io/github/contributors/Legendary-Brilliantforous/flashpilot)](https://github.com/Legendary-Brilliantforous/flashpilot/graphs/contributors)

**这是什么？** 付费 Windows 刷机套件的 Linux 原生等价物 —— 一个统一的工具，直接与 **Samsung、MediaTek、Qualcomm 与 Spreadtrum/UNISOC 设备** 的 bootloader 对话。逆向工程的协议 + 原生 Rust 性能 + 精美的 PyQt6 GUI = Odin、Heimdall 以及昂贵商业工具的开源替代品。

---

## ✨ 为什么这个项目重要

Android 修复的世界运行在封闭、仅 Windows 的商业工具之上。它们的协议由一小批爱好者逆向工程而来 —— 其中大部分知识被锁在付费套件里，或不完整地散落在论坛中。

**这个项目就是我们的回答。** 它把这些逆向工程的协议变成干净、可审计、MIT 许可的代码库，任何人都能阅读、运行、扩展 —— 并作为自己的刷机套件发布。

| 商业工具 | 仅 Windows、闭源 | 本项目 |
|---|---|---|
| Odin / Smart Switch | Windows，仅 GUI | 开源 Odin 协议（Rust，原生）+ PIT 工具 |
| MTK 刷机工具 | Windows，闭源 DA | MTK BROM/DA 刷写与备份（scatter + GPT） |
| Qualcomm EDL 工具 | Windows | Sahara + Firehose 协议实现 |
| SPD/UNISOC 工具 | Windows | 清房 BSL 下载实现（clean-room） |
| FRP / 锁具工具 | 付费、灰色市场 | 透明的 ADB + download 模式流程、MDM 解锁 |

---

## 🚀 亮点 — 1.2.1 Stable（0 警告）

- **9 种传输模式** —— ADB、MTP、Samsung Download 模式、Samsung BROM、MTK、MTK BROM、Fastboot、Qualcomm EDL、SPD。
- **13 个任务类别** —— Flash Firmware（刷写固件）、Remove FRP（移除 FRP）、Remove Screen Lock（移除屏幕锁）、Remove MDM（移除 MDM）、Unlock Carrier（运营商解锁）、Read Device Info（读取设备信息）、Detect Devices（检测设备）、Reboot（重启）、Repair Settings（修复设置），以及按芯片的 EXPERIMENTAL（实验性）：Knox / Warranty（Samsung）、QCN / Modem（Qualcomm）、IMEI Repair / Change（MTK/SPD/Qualcomm）、eMMC / UFS。
- **多设备** —— 插入多部手机：连接栏列出每一部，每项操作询问作用于哪部手机（或仅匹配一台时静默运行），不同手机可并行执行操作（每台设备一项操作，STOP 广播到所有设备）。
- **Rust 核心（`flashpilot-bridge`，约 9.3k LOC）—— 0 个 `cargo check` 警告** —— 原始 USB + *随附的 libusb*（无系统依赖），真实的协议实现（+ 18 条接通的死路径，`-80KB` ltcg 裁剪）。
  - **Samsung**：逆向工程的 Odin 会话协议（基于 Heimdall）、HID download-mode 载荷、PIT 读/写/刷写 —— 保留 AT `Context`，`EndpointConfig` 分块。
  - **MediaTek**：BROM / preloader / DA 握手、scatter & GPT、BROM 漏洞、SLA 密钥 —— `ProgressReporter` 真实百分比。
  - **Qualcomm**：Sahara `ProtocolError` + Firehose `QcomDeviceInfo`，通过 `Duration` 超时接通。
  - **SPD/UNISOC**：清房 BSL —— 所有 `BSL_CMD/REP`、`iface`、`flush/read_flash/chip_uid/power_off` 已接通。
  - 以及 **MTP**、**AT 命令** 和完整的 **ADB** 通道。
- **工作室级 GUI** —— 无边框半透明窗口、10 种强调色主题、动画电缆/状态场景、实时控制台。
  - **品牌图标与差异化按钮背景** —— 清晰的品牌图标（Samsung Ⓢ、Apple 红苹果 🍎、Motorola Ⓜ、LG Ⓛ 等）以及顶部 OEM 芯片栏每个按钮的专属品牌背景色。
  - **摩托罗拉与苹果的横向视图** —— 型号操作板默认采用干净的横向选项卡布局。
  - **微交互与玻璃拟态** —— 流畅的 160ms 页面切换淡入动画、等宽元数据徽章字体（`Consolas`、`Monaco`）以及增强的玻璃拟态卡片边框。
  - **大尺寸居中对话框（620px，可拖动，✕）** —— beta 门控 + 稳定版 `UPDATE/AHEAD/PATCH` + 刷写/FRP 确认，芯片颜色 `MTK amber` `QCOM red` `SPD violet` `SAMSUNG blue`，高对比度文本。
  - **按芯片的 EXPERIMENTAL 折叠面板** —— Knox（Samsung）、QCN/IMEI（Qualcomm）、IMEI（MTK/SPD）：琥珀色横幅、每次运行的所有权复选框、IMEI 变更的 `I UNDERSTAND` 输入确认、审计日志。
  - 标题栏 **⏹ STOP** 停止所有运行中的操作；每设备锁让其他手机继续工作。

---

## 📸 截图

| Samsung 操作 | MediaTek 工作台 | 电池修复 | SPD 下载 |
|---|---|---|---|
| ![Samsung](docs/samsung.png) | ![MediaTek](docs/mtk.png) | ![Battery](docs/battery.png) | ![SPD](docs/spd.png) |

---

## 🧩 功能矩阵

| 能力 | Samsung | MediaTek | Qualcomm | SPD/UNISOC | 任意 ADB |
|---|---|---|---|---|---|
| 检测 / 信息 | ✅ | ✅（+ crash preloader→BROM） | ✅（Sahara） | ✅ | ✅ |
| 刷写固件 | ✅（Odin，原生 Rust） | ✅（scatter + GPT） | ✅（Firehose） | ✅（FDL/regions） | — |
| 备份分区 | ✅（EFS） | ✅ | ✅ | ✅ | — |
| FRP 绕过 | ✅（ADB + download） | ✅ | ✅（EDL） | ✅ | ✅ |
| 屏幕锁移除 | ✅ | ✅ | ✅（EDL） | — | ✅ |
| MDM 解锁 | ✅（ADB、QR、recovery） | — | — | — | — |
| Knox 保修/绕过（EXPERIMENTAL） | ✅ | — | — | — | — |
| QCN 备份/恢复 + IMEI 修复/变更（EXPERIMENTAL） | — | ✅（NVRAM） | ✅（NV 550/682） | ✅（BSL NV） | — |
| 分区工具 | ✅（PIT） | ✅（GPT） | ✅ | ✅（PAC 提取/打包） | — |
| 底层漏洞 | ✅（HID/BROM） | ✅（BROM 漏洞、SLA） | ✅（Sahara） | ✅（BSL） | — |
| 电池 / 网络修复 | — | — | — | — | ✅ |

> 💡 **电池**与**网络**部分适用于*任何*开启 USB 调试的 Android 设备 —— 无需厂商硬件。

---

## 🖥️ GUI

无边框、半透明、卡片圆角窗口，上方是实时**连接横幅**（电脑 → 数据线 → 手机场景，带动画数据脉冲），左侧是**导航栏**，右侧是**控制台/日志面板**。

- **连接栏** —— 实时设备列表（每部手机一行：型号 · 序列号 · 传输方式）；点击一行可查看。多个匹配时操作按钮会询问是哪部手机。
- **Samsung** —— Samsung 中心子标签：`ODIN FLASH · UNLOCK · ADVANCED FLASH · INFO & TOOLS`，加上固件槽位（AP/BL/CP/CSC/USERDATA）、Odin 工具，以及 `KNOX — EXPERIMENTAL` 折叠面板。
- **MediaTek / Qualcomm / SPD** —— 专用工作台，具备原生底层工具（scatter/DA + crash-to-BROM、programmer/XML + QCN/IMEI、FDL 二进制 + 基地址 + IMEI），每个都有自己的 `— EXPERIMENTAL` 折叠面板。
- **电池** —— 燃料电计量健康 %、温度/电压/电流、顶部耗电者；一键修复。
- **网络** —— SIM 状态、数据/Wi-Fi 标志、DNS 模式；射频重置与重新注册。
- **设置** —— 自动扫描间隔、默认路径、控制台自动清除、10 种强调色主题、动画（shake/rubber/cable/bubble 开关）、窗口光晕、引擎状态、内置 `cargo build`。

**快捷键：** `F5` 重新扫描 · `Ctrl+Enter` 运行 · `Ctrl+L` 清除控制台 · `Ctrl+S` 保存日志 · `Ctrl+F` 查找。

---

## 📦 快速开始

**要求：** Rust 工具链、Python 3.10+、Linux 桌面环境。仅此而已 —— libusb 已随附。

```bash
# 1. 编译 Rust 桥接（首次构建从源码编译 libusb）
cargo build --release

# 2. （推荐）安装 USB udev 规则，使手机无需 sudo
sudo bash root/setup-usb.sh

# 3. Python 环境
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. 启动
.venv/bin/python -m python.main        # 或：python3 main.py
```

Samsung download 模式刷写是原生的（Rust Odin 协议）—— 不会获取、发布或需要任何专有的 odin4 二进制文件。Samsung 组合固件应从 Samsung 官方支持页面或可信固件存档获取。

---

## 🖥️ 平台支持 —— 我们想要你的声音

**Linux 是受支持的平台。** FlashPilot 被刻意定位为 *Linux 原生的、对应 Windows-only 刷机套件* 的回答 —— 开发、测试与发布面向 Linux，且这一点不会改变。

**Windows / macOS 当前不支持**，出于现实考量：

- Windows USB 是每种手机模式的驱动地狱（Zadig/WinUSB、QDLoader、Samsung 驱动互相打架）；大多数“手机未检测到”报告在远程将无法调试。
- macOS 增加签名/公证开销，而维修店需求几乎为零。
- 技术栈*是*可移植的（Rust + rusb、Python、Qt），因此这是维护决策，而非技术不可能。

**但这是开放问题，而非判决。** 如果你希望支持 Windows/macOS —— 或希望永远只支持 Linux —— 告诉我们：

- 💬 开一个 **[Discussion](https://github.com/Legendary-Brilliantforous/flashpilot/discussions)**，附上你的用例（维修店？实验室？哪种 OS？哪些手机？）。
- 🔧 代码最有说服力：计划是 `python/core/platform.py` 抽象层（`open_file_manager()`、`detach_kernel_drivers()`、`usb_device_path()`、`needs_udev_setup()`），以 Linux 作为唯一后端，使移植变成追加式 PR 而非分叉。欢迎现在就提交该方向的 PR。
- 🎨 相关：贡献者提议用 **PySide6**（LGPL，与本 MIT 项目许可兼容）替代 PyQt6（GPLv3）。在同一 Discussion 中发表意见 —— 迁移是机械的，但需要先有 GUI 冒烟测试覆盖。

没有贡献者的声音，不会做出决定。来吧，成为其中之一。

### CLI / 桥接

```bash
./target/release/flashpilot-bridge detect          # all USB + Samsung filter (JSON)
./target/release/flashpilot-bridge fastboot-devices  # USB devices with a fastboot interface (JSON)
./target/release/flashpilot-bridge fastboot-cmd 22b8:2e80@2:16 20000 getvar securestate  # one raw fastboot command
./target/release/flashpilot-bridge mtk-detect      # MediaTek BROM (0e8d:0003) / preloader (0e8d:2000) / DA
./target/release/flashpilot-bridge mtk-crash-brom <bus:addr>  # crash preloader into held BROM
./target/release/flashpilot-bridge qcom-detect     # Qualcomm EDL
./target/release/flashpilot-bridge spd-detect      # Spreadtrum/UNISOC (VID 0x1782)
./target/release/flashpilot-bridge odin-pit 04e8:xxxx@bus:addr  # read PIT
./target/release/flashpilot-bridge at-send <t> ATI # AT over CDC ACM
./target/release/flashpilot-bridge adb-devices     # adb devices -l as JSON
```

---

## 📁 仓库结构

```
flashpilot/
├── src/                      # Rust bridge (~13k LOC) — ALL flows live here
│   ├── main.rs               #   command-line entry (80+ commands) + flow-run dispatch
│   ├── flows.rs              #   THE registry: FLOWS / JOBS / MODES (flow! macro, ~280 rows)
│   ├── usb/                  #   USB enumeration / interfaces / filtering (mod.rs + filtering.rs)
│   ├── devices.rs            #   merged USB+ADB device rows
│   ├── sam_download.rs       #   Samsung Download/Odin protocol (odin-* commands)
│   ├── mtk.rs mtk_da.rs      #   MediaTek BROM/DA flashing
│   ├── mtk_exploit.rs        #   BROM exploits (bypass/kamakiri2/crash-to-BROM)
│   ├── mtk_sla.rs            #   MediaTek SLA key handling
│   ├── qualcomm/             #   Sahara + Firehose + GPT (EDL)
│   ├── spd.rs                #   Spreadtrum/UNISOC BSL protocol (+ PAC)
│   ├── pac.rs                #   SPD PAC extract/pack
│   ├── pit.rs                #   Samsung PIT parser
│   ├── mtp.rs at.rs adb.rs   #   MTP, AT command, ADB plumbing
│   ├── fastboot.rs           #   native fastboot transport
│   ├── moto_flash.rs         #   Motorola staged fastboot FRP
│   ├── apple.rs              #   Apple usbmuxd/lockdown
│   ├── hid.rs bulk.rs        #   HID + bulk helpers
│   ├── fwtar.rs sparse.rs    #   firmware tar + sparse handling
│   ├── imgtools.rs           #   boot/vbmeta surgery
│   ├── hostinfo.rs           #   host eMMC/UFS health
│   ├── sam_*.rs              #   Samsung helpers (errors/setup)
│   └── config.rs error.rs util.rs
├── main.py                   # app entry (venv-safe launcher → python.gui.qt_app)
├── python/
│   ├── core/
│   │   ├── core.py           #   thin shim: mirrors Rust FLOWS/JOBS/MODES via bridge.flow_list()
│   │   ├── frp.py            #   FRP-only re-export surface (name == responsibility)
│   │   ├── devices.py        #   multi-device identity: stable keys, list, resolve, transport mapping
│   │   ├── bridge.py         #   talks to the Rust binary (+ per-key cancel)
│   │   ├── flow.py           #   Flow/Step primitives + cancellation
│   │   ├── jobs.py           #   FlashJob lifecycle (isolated job layer)
│   │   ├── cancel.py         #   cooperative cancellation registry
│   │   ├── mtk.py            #   MTK PIDs/stages/chips (0003=BROM, 2000=preloader)
│   │   ├── mtp.py            #   Samsung MTP/AT (multi-sequence ADB enable)
│   │   ├── pit.py pitstore.py  # Samsung PIT parser + cache
│   │   ├── adb.py            #   ADB helpers
│   │   ├── device_info.py    #   live device identity
│   │   ├── actions.py        #   action helpers
│   │   ├── experimental.py   #   per-run ack gates + audit log
│   │   ├── fus.py            #   Samsung FUS helpers
│   │   └── (no flows/ dir)   #   flows live in src/flows.rs; Python only delegates
│   └── gui/
│       ├── qt_app.py         #   the PyQt6 studio (~12k LOC)
│       ├── devices.py        #   brand→model→action drill-down pages
│       ├── nav.py            #   nav rail + OEM chip bar
│       ├── theme.py          #   tokens (accent vs focus_ring/sel_border) + QSS
│       ├── animations.py     #   Motion (shake/rubber serialized, no stuck state)
│       ├── toast.py          #   toast notifications
│       └── supported_devices.json  #   brand/model/chip research table
├── operations/               # per-operation docs + research (frp/mdm/flashing/…)
├── docs/                     # screenshots (fresh) + logo
├── root/                     # udev rules + setup-usb.sh
├── scripts/                  # dump-connected.sh, validate_mtp_at.py
├── INDEX.md CHANGELOG.md     # engineering index + release changelog
└── tests/                    # pytest suite (flow, MTK, PIT, odin safety, devices…)
```

---

## 🧑‍💻 贡献

**这个项目只有在你的帮助下才会变得更好。** 我们需要维护者、协议黑客、GUI 设计师、文档作者与测试者。

- **[CONTRIBUTING.md](CONTRIBUTING.md)** —— 开始所需的一切。
- **从 [`good first issue`](https://github.com/Legendary-Brilliantforous/flashpilot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) 标签开始** —— 精选的、适合新手的任务。
- 使用 **[bug report](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml)** / **[feature request](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=enhancement&template=feature_request.yml)** 模板。
- **新手友好的任务** —— `src/flows.rs` 中的每一行流程都是机会：添加一行 `flow!(...)`，调整一段命令序列，接通一个新的设备组合。Python 通过 `bridge.flow_list()` 自动发现它。
- **流程框架（`src/flows.rs`）极其简单** —— 一个新方法只需一行：

```rust
flow!("my_method", "My method", "Read Device Info", "ADB"),
```

它会自动出现在 GUI 中。这就是整个贡献循环：**写一行流程，交付一个功能。**
- **多设备规则** —— 永远不要抓取“那个”设备；接受 `key=None`（环境作用域）并按其过滤。见 `python/core/devices.py` 与 `CONTRIBUTING.md`。
- **命名规则** —— 任务动词在前（`Remove FRP`，而非 `FRP bypass`）；流程键使用简短的 snake_case（`FLOWS` 中不加 `flow_` 前缀）；MTK PID 为 `0003`=BROM / `2000`=preloader（mtkclient 约定 —— 不要交换）。

**我们希望得到帮助的方向：**
- 流程表中的新设备型号 / 固件组合。
- MediaTek DA 变体、新的 scatter/GPT 怪癖。
- Qualcomm rawprogram & patch XML 边缘情况。
- 按 Android 版本的额外 FRP / 锁移除方法。
- 打包（Flatpak、AppImage、AUR、`cargo` + `pip`）、CI、单元测试。
- 更多 ODIN 协议、eMMC/UFS 工具、与 iCloud 相关及 EDL 工具。
- 翻译、主题与无障碍。

---

## 🛡️ 安全与合法性

该工具直接与 bootloader 对话；误用可能 wipe data 或砖机。

- 仅在 **你拥有或被授权维修的设备** 上使用（维修店为经客户同意的手机提供服务）。
- 始终阅读屏幕上的警告，并在刷写前 **备份分区**。
- 在你并不拥有设备的情况下绕过 FRP/MDM 在你所在的司法管辖区**可能违法** —— 你如何使用本软件，责任自负。
- FlashPilot 随附操作所需的协议载荷（MTK DA/BROM 载荷、Qualcomm firehose programmer、Unisoc FDL1/FDL2、Samsung bootloaders），与商业刷机套件相同。特定手机的固件镜像仍然来自用户或厂商。

---

## 📄 许可证

MIT —— 见 [LICENSE](LICENSE)。Odin 协议常量源自 Heimdall 项目（MIT），SPD BSL 参考来自清房协议文档（spd_cmd.h / Opus-Spreadtrum 文档）。

---

**把此仓库加 ⭐，提一个 issue，送一个 PR —— 让我们一起构建 Linux 上最好的开源刷机套件。**
