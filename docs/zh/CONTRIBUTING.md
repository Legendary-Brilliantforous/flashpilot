# 🧑‍💻 贡献 FlashPilot

Language switcher: [English](../../CONTRIBUTING.md) · [Français](../fr/CONTRIBUTING.md) · [Español](../es/CONTRIBUTING.md) · [Deutsch](../de/CONTRIBUTING.md) · **简体中文** · [Русский](../ru/CONTRIBUTING.md) · [Português](../pt/CONTRIBUTING.md) · [日本語](../ja/CONTRIBUTING.md) · [العربية](../ar/CONTRIBUTING.md) · [हिन्दी](../hi/CONTRIBUTING.md) · [Türkçe](../tr/CONTRIBUTING.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

感谢驻足！项目基于逆向工程协议与开放知识构建 —— 每一次贡献都能让它更强大、更可靠，并向付费的 Windows 套件看齐。你并不需要是刷机专家才能参与。

## 目录

- [行为准则](#行为准则)
- [项目组织](#项目组织)
- [贡献方式](#贡献方式)
- [开始上手](#开始上手)
- [从旧 checkout 迁移（若你回来看看请先读这个）](#从旧-checkout-迁移若你回来看看请先读这个)
- [架构导览（10 分钟）](#架构导览10-分钟)
- [如何添加新 flow](#如何添加新-flow)
- [添加新的 USB 协议 / Rust 命令](#添加新的-usb-协议--rust-命令)
- [GUI 指南](#gui-指南)
- [测试](#测试)
- [Pull Request 检查清单](#pull-request-检查清单)
- [平台支持政策（移植前先读）](#平台支持政策移植前先读)
- [路线图与想法](#路线图与想法)

---

## 行为准则

见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。尊重他人，假定善意，保持讨论技术化且有帮助。这是一个从爱好者走向严肃的项目：欢迎新手与老手。骚扰、账号风暴（gatekeeping）或提交机密/凭证的行为不可容忍。协议载荷在记录其出处与许可后是欢迎的。

---

## 项目组织

两个部分协作：

| 层 | 位置 | 语言 | 角色 |
|---|---|---|---|
| **核心 / 协议引擎** | `src/` | Rust | 原始 USB + 所有 bootloader 协议（`flashpilot-bridge` CLI） |
| **流程注册表** | `src/flows.rs` | Rust | `flow!` 宏行 → `FLOWS` / `JOBS` / `MODES`（事实之源） |
| **流程 shim** | `python/core/core.py` | Python | 薄层 `_RustFlow` 包装 + `JOBS` 回退；委托给 `bridge flow-run` |
| **设备身份** | `python/core/devices.py` | Python | 稳定键、设备列表、目标重新解析、线程作用域 |
| **FRP 表层** | `python/core/frp.py` | Python | 仅 FRP 重新导出（名称 == 职责） |
| **GUI 工作台** | `python/gui/` | Python / PyQt6 | `qt_app.py` 工作台、`devices.py` 页面、主题、动画 |

Python 永远不直接与 USB 通信。它调用 `target/release/flashpilot-bridge`（Rust 二进制），该二进制返回 JSON/文本。GUI 仅监听工作线程信号 —— 永远不要从后台线程触摸控件。

---

## 贡献方式

不会写代码？没问题：

- **真实硬件测试** —— 报告某个流程在哪些设备/固件上有效。
- **文档** —— 改进 README、本文件与流程描述。
- **固件 / DA / 组合包归档** —— 提供合法且自由可得的二进制指针。
- **翻译与主题** —— GUI 可主题化；新增强调包是容易的战果。
- **UI/UX** —— 原型、无障碍检查、键盘快捷键设计。
- **Bug 报告** —— 使用 [bug report 模板](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml)：步骤、日志、`flashpilot-bridge detect` 输出、设备型号 + 固件版本。
- **代码** —— 见下文。

> 💡 **新手？** 在 issue 跟踪器查找 **`good first issue`** 标签 —— 精选的、对新手友好、范围明确、可安全上手的任务。

---

## 开始上手

```bash
# 1. 构建 Rust 桥接
cargo build --release

# 2. （推荐）USB udev 规则
sudo bash root/setup-usb.sh

# 3. 创建 venv + 运行
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m python.main
```

应用会打开一个原生 PyQt6 窗口。使用 **Settings → Tools** 页面查看桥接是否构建、是否检测到 ADB。

---

## 从旧 checkout 迁移（若你回来看看请先读这个）

对 churn 直说：在 1.2.0 与现在之间，我们重命名了中心模块，把一个 god-file 拆成专注模块，重命名了每个 job，并增加了十几个文件。这会破坏旧导入、旧文档引用，以及针对 `python.core.frp` 写的任何树外脚本。抱歉 —— 这是杀死 god-file、修正 MTK PID 混淆、并让多设备支持无需在 atop 堆 hack 的唯一方式。本节是完整的适配指南；没有任何东西在渐进弃用 —— 一切一次性变了，所以通读表格一次你就追上潮流了。

### 重命名的路径

| 之前 | 之后 | 要改什么 |
|---|---|---|
| `python/core/frp.py`（god file：注册表 + 每个 flow） | `python/core/core.py` | `from python.core import frp` → `from python.core import core`；`frp.FLOWS` → `core.FLOWS` 等。 |
| *（没有 —— FRP 在 god file 内）* | `python/core/frp.py`（新增，仅 FRP） | 若仅需 FRP flows，从这里导入而非 `core`。 |
| *（没有）* | `python/core/devices.py`（新增） | 设备身份、`list_devices()`、`resolve_usb_target()`、`device_scope()`。 |
| *（没有）* | `python/core/imei.py`（新增） | MTK/SPD IMEI 修复 + 变更 flows。 |
| *（没有）* | `python/core/experimental.py`（新增） | EXPERIMENTAL 门禁 + 审计日志。 |
| *（没有）* | `python/core/{knox,qcn,emmc,pac,apple,health,compat,device_info,fastboot,integrity,safety,spd_adb}.py`（新增） | 每域逻辑，此前内联在 god file 或缺失。 |
| *（没有）* | `tests/test_devices.py`（新增） | 多设备 + 取消作用域测试。 |
| *（没有）* | `CHANGELOG.md`（新增） | 按发布分组的变更；先查它。 |

### Rust 移动（当前架构 —— 上面表格是历史）

完成上述拆分后，引擎移到了 Rust，Python 端变薄。当前事实：

- **Flows 在 `src/flows.rs`**（注册表 + `flow-run <key> [target] [--code/--partition/--file/--dpc ...]`）。`flow-list` 是事实之源 —— 在文档引用某个 flow key 前先在那里核实。
- **`python/core/core.py` 是薄 shim**（~450 行）：`_RustFlow` 委托给 `bridge flow-run`，注册表来自 bridge 并带 `JOBS` 回退。16 个每域引擎模块（`knox`、`qcn`、`emmc`、`imei`、`apple`、`ofp`、`pac`、`health`、`flashing`、`spd_adb`、`integrity`、`fastboot`、`usb_watch`、`compat`、`updater`、`safety`）已被删除 —— 新文档中不要引用它们。
- **GUI 仍是 Python**（`python/gui/qt_app.py` + `devices.py`）；它通过 `bridge.flow_list()` 消费 Rust 注册表。
- 被移除的 Python flows 相关旧测试文件已一并删除；覆盖由每域套件 + cargo `flows::tests` 提供。

### 你必须适配的 API 变更

- **Resolver 接受 `key=None`。** `find_samsung()`、`_download_mode_device()`、`_wait_for_adb()`、`_wait_mtk_brom_target()`、`_mtk_retry()`、`wait_clean_download_mode()`、`pit_contract()` 都接受可选的稳定设备 key（默认环境线程作用域 —— 旧调用点仍可工作，未设 key 时保持 first-match 行为）。
- **Cancel 按设备。** `flow.py` 与 `bridge.py` 中的 `request_cancel()` / `clear_cancel()` / `cancel_requested()` 接受 `key=None`。无 key 的 `request_cancel()` 仍广播（全局 STOP）；无 key 的检查先查环境作用域，再查广播总线。
- **Run-guard 按设备。** `qt_app.py` 中的 `_flow_start(label, destructive, key=None)` / `_flow_end(key=None)` / `_flow_busy_msg(key=None)`；旧的 `_FLOW_LOCK` / `_FLOW_LABEL` 全局已消失（被每 key 字典 + `_flows_running()` 取代）。
- **Runner 接受 `device_key=None`。** `_run_ops_flow()` / `_run_job_flow()` 在匹配多部手机时显示设备选择器，然后设 `ctx["device_key"]`（+ 可解析时的 `ctx["target"]`），并在 `devices.device_scope()` 中运行。
- **MODES 中新增 `"SPD"` transport mode**（VID `0x1782`）；新增 jobs `Knox / Warranty`、`QCN / Modem`、`IMEI Repair / Change`、`eMMC / UFS`。
- **Job 名称动词在前**（`Remove FRP`，而非 `FRP bypass`；见 README）。若分支仍引用旧名称，请按 "架构导览" 中的表重命名。
- **MTK PIDs 是 mtkclient 约定**：`0e8d:0003` = BROM，`0e8d:2000` = preloader。多个旧注释/日志曾把它们交换；信任 `mtk.pid_stage()` / Rust `boot_stage_for()`，而非旧字符串。

### 若你有 restructure 前的开放 PR

1. rebase 到新树；期望冲突仅限于 import 和 `JOBS`/`FLOWS` 块。
2. 运行下方清单 —— `pytest` 会立刻捕获过时的 key/名称引用（注册表测试断言每个 `JOBS` 方法可解析）。
3. 若 PR 触 touched `flows/`（已移除的 split-package 实验）：该目录已不存在，把你的改动移植到 `core.py` + 对应域模块。

---

## 架构导览（10 分钟）

1. **`src/main.rs`** — 80+ 命令 CLI。每个 `match` 臂一个命令（`detect`、`mtk-flash`、`mtk-crash-brom`、`qcom-firehose`、`spd-format`、`odin-pit` ...）。
2. **`src/usb.rs`** — 按 VID/PID 找设备，给出端点（加上稳定的 `port_numbers` 用于抗重新枚举寻址）。
3. **`src/odin.rs`** — Samsung download mode（逆向工程的 Odin 3 协议，源自 Heimdall）。读/写 PIT、刷写分区（含常驻 `odin-agent` 会话多路复用器）。
4. **`src/mtk*.rs`** — MediaTek BROM（`0e8d:0003`）→ preloader（`0e8d:2000`）→ Download Agent 握手、scatter 解析、GPT 分区工作、SLA 密钥、BROM 漏洞、crash-to-BROM。⚠️ PID 约定是 mtkclient 风格：`0003`=BROM，`2000`=preloader —— 不要交换。
5. **`src/qualcomm/`** — Sahara（EDL）握手与 Firehose 会话。
6. **`src/spd.rs`** — Spreadtrum/UNISOC BSL：FDL 下载、格式化、FRP、备份、PAC 提取/打包。
7. **`src/flows.rs`** — **应用核心**。`flow!(key, label, job, mode)` 行构建 `FLOWS` / `JOBS` / `MODES` 注册表（~280 行、13 jobs、9 modes 含 `SPD`）。`python/core/core.py` 仅镜像它供 GUI 查找。
8. **`python/core/devices.py`** — 多设备身份。稳定键（`adb:<serial>` → `usb:<port-path>` → volatile 回退）、`list_devices()`、`resolve_usb_target()`、把选中手机送入 resolver 的 `device_scope()` 线程本地。
9. **`python/gui/qt_app.py`** — 构建所有分区（Samsung / MTK / QC / SPD / Battery / Network / Settings）及子标签工作台，加上每操作的设备选择器与每设备 run-guard。

### 数据流

```
click button
  → _choose_device(job, mode)          # 匹配 0-1 部手机时静默，否则选择器
  → _run_ops_flow(job, mode, method, name, device_key)
  → per-device _flow_start(key) + device_scope(key) + ctx["device_key"]
  → core.flow_for(...) -> Flow (Step list)
  → each Step runs in a worker thread, calling bridge._run([...])
  → bridge spawns target/release/flashpilot-bridge ...
  → Rust does USB I/O, prints JSON/text
  → Python parses + emits _ui.line() signals (tagged [device-key])
  → GUI updates console / status / progress safely
```

---

## 如何添加新 flow

你能发布的最简单功能。打开 `src/flows.rs` 并添加一行：

```rust
flow!("my_method", "My method", "Remove FRP", "ADB"),
```

key 是短的 snake_case（无 `flow_` 前缀）。Python 通过 `bridge.flow_list()` 自动发现，GUI 的 job/mode/method drill-down 自动选中；执行经 `flashpilot-bridge flow-run my_method`。

之后（仅在需要新的底层协议工作时）在 `src/<concern>.rs` + `src/main.rs` 添加桥接命令。job/mode 接线已经在 flow 行中了。

就这些 —— flow 自动出现在 GUI 的 dropdown/子标签中，也能从 CLI 访问。**这是投入产出比最高的、最易入门的领域。**

> 在 step 中用 `log(...)` 做控制台输出；用 `ctx` 携带你希望在 step 间传递的状态；任何命中 Rust 二进制的东西用 `bridge._run(...)`。在适当时让 step 与 `cancel_requested()` 协作，以便 Stop 生效（cancel 是按设备作用域的 —— 见下文）。

### 每个 flow 必须遵守的规则

- **永远不要抓取“那个”设备。** 在你增加的任何 resolver 中接受 `key=None`（环境线程作用域），并按其过滤 —— 见 `devices.device_key()`、`devices.match_key()`、`devices.device_scope()`。GUI 按操作设置作用域；无 GUI 调用方也可以。
- **Job 名称动词在前**（`Remove FRP`、`Flash Firmware`、`Unlock Carrier`）。**Flow keys 使用简短 snake_case**（`adb_frp`，而非 `flow_adb_frp`）；唯一的历史别名（`fastboot_read`）已被移除 —— 不要添加别名。
- **MTK PID 约定为 mtkclient 风格**：`0e8d:0003` = BROM（held），`0e8d:2000` = preloader。Rust、Python、GUI 标签与文档必须都一致。
- **EXPERIMENTAL 写入**（Knox/IMEI/QCN/eMMC）通过 `experimental.check_gate_strict()` 配合每次运行的 ack —— 存储的 ack 绝不能自动通过。经 `_EXPERIMENTAL_FLOW_MAP` + 所属 chip 页上的琥珀色可折叠模式作 GUI 门禁（永远不是全局 LAB 页）。
- **Bridge targets 是 volatile 的**（`vid:pid@bus:addr` 在重新枚举时变化）。在打开会话前从稳定 key 重新解析（`devices.resolve_usb_target()`）；用 `-d /dev/bus/usb/BBB/AAA` 钉住 odin4。

---

## 添加新的 USB 协议 / Rust 命令

1. 在 `src/` 下加你的模块（如 `src/myproto.rs`）。
2. 在 `src/main.rs` 加 `mod myproto;` 以及新的 `match` 臂 + usage 行。
3. 经 `crate::error` 返回 `Result<T>`，结构化输出用 `serde_json`。
4. 在 `python/core/bridge.py` 暴露为 `_run([...])` 的包装。
5. 在 `core.py` 中构建调用它的 `Flow`（遵循上面的 flow 规则）。
6. 若能加，加个测试 —— 单元测试位于 `src/*.rs`（`#[test]`）与 `tests/`。

**协议卫生：** 在模块 docstring 中引用来源（论坛、清房 write-up、其他 OSS 项目）。我们不包含专有 blob —— 只有协议实现。

---

## GUI 指南

- **仅 PyQt6。** 无其他 Qt 绑定，无额外 UI 依赖（见 `requirements.txt`）。
- 匹配现有视觉语言：`_btn_ghost()`、`_btn_primary()`、`_card_qss()`、`SectionTitle`、`C[...]` 主题颜色、`FlowLayout` 用于按钮网格。
- **主题令牌，而非原始强调色：** 填充可使用 `C['accent'/'grad_a'/'grad_b']`，但 focus rings、选中 Tab 边框、复选框必须使用中性 `C['focus_ring']` / `C['sel_border']` —— 否则红色强调色主题（Crimson、Sunset）会把红色泄漏到 focus 状态。永远不要为 chrome 硬编码 hex。
- **线程规则：** 后台工作放 `threading.Thread`；GUI 更新只经 `self._ui.*` 信号（`.line`、`.status`、`.toast`、`.ui`、`.progress`）。
- **动画：** `Motion.shake()` / `Motion.rubber()` 对同一 widget 互斥（由 `_anim_lock` 守护）—— 永远不要并发运行两者，或者调用点必须经 `QTimer.singleShot` 串行。它们都不能留下 `setFixedSize`、restyled borders 或 disabled layouts；`cleanup()` 恢复一切。
- 为长寿命 UI 行保持可滚动 —— chip 页面把内容包在 `QScrollArea` 中，这样在小窗口下也不会被压扁。
- 新子标签复用 `SamsungSubTabs` + `QStackedWidget`（见 `_build_chip_ops_section`）。
- Action 按钮是 `NoFocus`（无粘性 focus ring）；可选中的 Tab pills 为 active 状态保留 `checked` 样式。

---

## 测试

```bash
cargo test                      # Rust 单元测试（incl. MTK stage mapping, SLA, PIT）
.venv/bin/python -m pytest tests/   # Python 套件（当前 173 passed, 4 skipped）
```

测试套件布局：

- `tests/test_frp_flow.py` — `Flow`/`Step` 执行 + 协作式取消 + 按设备的 run-guard。
- `tests/test_mtk.py` — MediaTek 逻辑（scatter、DA、boot-stage helper、BROM 等待/crash 重试）。
- `tests/test_devices.py` — 稳定设备 key、手机过滤、目标重新解析、作用域取消。
- `tests/test_carrier_lock.py` — SIM 锁 verdict + MTK 补丁门禁 + DA 发现。
- `tests/test_odin_safety.py` — tar.md5 校验、BL 门禁、odin4 flag 协商。
- `tests/test_pit.py` — Samsung PIT 解析。
- `tests/test_bridge_io.py`、`tests/test_fus.py` — 桥接 I/O + Samsung 固件下载器。

若你添加 Rust 逻辑，在同文件添加 `#[test]` 模块。若你添加 flows，给 fake/offline context 能运行的 flow 加 pytest。新的 resolver 必须接受 `key=None`；新测试应覆盖多设备过滤（见 `test_devices.py`），而非假设一部手机。

---

## Pull Request 检查清单

- [ ] `cargo build --release` 通过。
- [ ] `cargo test` 通过（或说明为何不可运行）。
- [ ] `.venv/bin/python -m pytest tests/` 通过。
- [ ] 新 flow：接入 `JOBS`（job + mode），以便在 GUI 中可达。
- [ ] 新 resolver：接受 `key=None`（环境作用域）且被多设备测试覆盖。
- [ ] 新 Rust 命令：加到 `main.rs` usage text + `bridge.py` 包装。
- [ ] GUI 变更：主题化颜色（中性 focus token！）、基于信号的更新、安全滚动布局。
- [ ] 不向仓库添加 secrets/binaries/设备标识数据。
- [ ] 若添加了能力，更新 README 功能矩阵。

保持 PR 聚焦。一个 PR 一个功能或修复最好；引用 issue 编号。

---

## 平台支持政策（移植前先读）

**Linux 是唯一支持的平台。** 开发、硬件测试与发布会面向 Linux。Windows/macOS issue 将作为不支持关闭 —— 除非以代码形式到来，如下所述。

**Why：** `odin4` 仅限 Linux；Windows USB 需要各类模式驱动（Zadig / QDLoader / Samsung）无法远程调试；macOS 需要签名/公证，需求微乎其微。见 README 的 "Platform support" 小节查完整理由与公开邀请来争论它。

**如何无论如何贡献移植（接受形态）：**

1. 不要通过 flows 或 GUI 无差别地撒 `sys.platform` checks。
2. 添加 `python/core/platform.py`，含后端函数 —— `open_file_manager()`、`detach_kernel_drivers(target)`、`usb_device_path(bus, addr)`、`needs_udev_setup()`、`kernel_module_loaded(name)` —— Linux 已实现，其它抛出 `NotImplementedError` 附带有帮助的消息。
3. 将已有 Linux-only 调用点（`xdg-open`、`rmmod cdc_acm`、`/dev/bus/usb`、`lsmod`、udev 文档）迁移到它，每组调用点一个 PR。
4. Windows/macOS 后端 PR 必须包含：后端实现、docs 更新、以及 CI 或维护者验证过的手动测试证据。核心团队不拥有非 Linux 测试硬件 —— port PR 的存亡取决于作者能否证明它们。

**PySide6 vs PyQt6：** 迁移到 PySide6（LGPL，MIT 兼容 —— PyQt6 是 GPLv3）是想要的但被 GUI 冒烟测试覆盖阻塞。若你来做：机械转换 `pyqtSignal→Signal`、`pyqtProperty→Property`、`PyQt6.sip→shiboken6`，扩展 `tests/` 中的 offscreen window/picker/guard smoke tests，并保持行为像素完全相同。先在 Discussions 讨论。

## 路线图与想法

我们希望贡献者 champion 这些中的任意项：

- **端口与打包：** Flatpak / AppImage / AUR、CI 矩阵（Linux 发行版）、`pip` / `cargo` 发布流程。
- **MediaTek：** 更多 DA 变体、scatter 边缘情况、eMMC/UFS 备份 dump、`CHIP_NAMES` 中新的 `hw_code` 条目（附引用 —— 绝不猜 hex code）。
- **Qualcomm：** rawprogram/patch XML 边缘情况、fh-loader combos、更多芯片 PIDs。
- **Samsung：** 按 SoC 的额外 HID download-mode 载荷、Odin 多分区 UX 打磨。
- **多设备：** 按设备控制台 tab/progress、按设备粒度的 STOP（STOP 目前广播）、exotic hub 的 `port_numbers` 关联。
- **新章节：** TEE/keyboard FRP、carrier (去 bloat) 配置、EDL-only 工具。
- **社区：** 翻译、设备兼容性 wiki、可复现的 firmware-archive catalog。
- **安全：** dry-run 模式、自动 pre-flash 备份、brick-recovery docs。

---

## 贡献者

帮助过的所有人 —— 代码、文档、设备报告、或测试过的组合 —— 都列在这里并受庆祝。开 PR 把自己加下去（按 username 字母顺序，一行链接）：

```md
- [@your-github](https://github.com/your-github) — what you did
```

本项目的第一批贡献者让它真实起来。下一个就是你。

---

## 问题？开一个 discussion/issue。感谢你助力 Linux 上自由、开放的刷机软件。 🚀