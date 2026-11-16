Language switcher: [English](../../frp/INDEX.md) · [Français](../../fr/frp/INDEX.md) · [Español](../../es/frp/INDEX.md) · [Deutsch](../../de/frp/INDEX.md) · **简体中文** · [Русский](../../ru/frp/INDEX.md) · [Português](../../pt/frp/INDEX.md) · [日本語](../../ja/frp/INDEX.md) · [العربية](../../ar/frp/INDEX.md) · [हिन्दी](../../hi/frp/INDEX.md) · [Türkçe](../../tr/frp/INDEX.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# operations/frp/ — 出厂重置保护（Factory Reset Protection，仅 Android）

> Apple 设备没有 FRP（Apple 改用激活锁 / iCloud）——
> 参见 `operations/apple/`。

本目录保存 FRP 绕过相关的 **按引擎文档树**。
实际代码位于 `src/flows.rs`（Rust）。当你为某个设备拿到真实
方案（芯片、FDL 对、分区偏移等）时，把简短的研究笔记放到
`devices/<brand>/<model>.md`。本文件根部的 README 将 codebase 中的每个 FRP
流程映射到其所在位置与所需条件。

## 引擎映射

| 引擎 | 何时使用 | 代码 | 桥接 CLI |
|---|---|---|---|
| **通用（ADB）** | 任何开启 USB 调试的手机的首选尝试 | Rust 流程（`src/flows.rs` 中的 `adb_frp`、`frp_*` 行） | `flow-run adb_frp` / `adb shell ...` 通过 `bridge.adb_shell` |
| **MTK BROM** | MediaTek（Helio / Dimensity / MT6765）—— 关机 → 按住 Vol-/+ → 插入 USB | Rust 流程（`src/flows.rs` 中的 `mtk_*` 行） | `flow-run mtk_brom_info`（CLI：`mtk-detect`、`mtk-da-upload`、`mtk-frp`、`mtk-bypass`） |
| **MTK DA** | 存活 DA 上传的 MTK BROM（锁态芯片） | Rust 流程（`mtk_brom_backup`、`mtk_auth_flash`） | `flow-run mtk_brom_backup` |
| **Qualcomm EDL** | 9008 紧急下载（Snapdragon） | Rust 流程（`edl_*`、`qcom_*` 行） | `flow-run edl_frp`（CLI：`qcom-*`） |
| **Samsung Exynos** | A14（Exynos 850/1330）、A15/A16 —— Odin 下载模式仅用于刷机，**不**用于 FRP | Rust `frp_*` 行（Samsung 账号绕过） | （主要在设备端，无桥接） |
| **Samsung MTK（A05/A06）** | 搭载 Helio G85 的 A05/A06 —— 使用 MTK BROM（见上） | Rust 流程（`mtk_brom_info`、`mtk_brom_backup`） | `flow-run mtk_brom_backup` |
| **UNISOC/SPD** | 1782:4d00 FDL1+FDL2（SC9863A、T606/UMS9230） | Rust 流程（`spd_*` 行）+ `src/spd.rs` | `flow-run spd_detect_info`（CLI：`spd-detect`、`spd-frp`、`spd-format`、`spd-magic-pack`） |
| **HiSilicon Kirin** | 12d1 —— 尚无开放流程（未逆向工程） | （暂无） | （暂无） |

（旧的 `python/core/flows/*.py` 引擎模块从未发布；`mtk-brom-backup` 是 `mtk_brom_backup` 流程行。使用 `flow-list` 校验任意键。）

## 流程键 → 函数映射

GUI 的 FRP 操作可调用的每个流程。键是 Rust 注册表行
（`src/flows.rs`，用 `flow-list` 校验）；GUI 按
(job, mode) 路由，桥接通过 `flow-run <key> [target]` 执行。

| 流程键 | 引擎 | 作用 |
|---|---|---|
| `adb_frp` | 通用 ADB | `settings put secure frp 0` + 禁用设置向导 + 清除 GMS 数据 |
| `frp_browser` | 通用 ADB | 通过 intent 在设备上打开 `chrome://settings/` |
| `frp_emergency` | 通用 ADB | 通过紧急呼叫拨号器打开设置（设备端） |
| `frp_settings` | 通用 ADB | 通过通知栏路径打开设置（设备端） |
| `frp_fake_login`（+`_testdpc`、`+_adp`） | 通用 ADB | 使用设备所有者 DPC 进行 QR 配置，随后清除 FRP |
| `at_info` | Samsung MTP/AT | 通过 AT 通道读取模式 + devconinfo（Samsung pre-Android 8） |
| `at_method` | Samsung MTP/AT | AT+DEBUGLVC，经 diag 端口启用 ADB |
| `download_frp` | Samsung 下载模式 | 使用 CSC/Combination 固件移除 FRP（PIT 安全契约） |
| `odin_enable_adb` | Samsung 下载模式 | 通过 Odin tarball 从下载模式启用 ADB |
| `mtk_combo_flash` | MTK 下载 | Combination 固件刷写（PIT + DA） |
| `mtk_recovery_reset` | MTK 下载 | 恢复模式出厂重置 |
| `mtk_brom_info` | MTK BROM | 读取芯片 id / 握手（任何 BROM 刷写前必需） |
| `mtk_brom_backup` | MTK BROM | 通过 BROM DA 转储分区 |
| `edl_frp` | Qualcomm EDL | Sahara + Firehose 擦除（05c6:9008） |
| `qcom_detect_info` | Qualcomm EDL | 检测 + 信息（只读） |
| `frp_qr_provision` | 通用 ADB | QR 配置（TestDPC 路径） |

（已退役：旧的带 `flow_*` 前缀的键名以及
`python/core/flows/*.py` 从未发布——键没有 `flow_` 前缀。）

## 新的单机型方案如何落地

1. **运行真实的设备转储**（ADB 路径参见 `scripts/dump-connected.sh`，
   或 Unisoc 的 BROM 路径用 `flashpilot-bridge spd-format`）。转储输出到
   `build/cache/dumps/<model>_<codename>/`。

2. **从转储中识别** 引擎 + 芯片 + FRP 分区名称
   （Android 11+ 几乎总是 `frp`、`frp_a` 或 `userdata`）。

3. **在 `python/gui/supported_devices.json` 的对应品牌下添加设备条目**，
   设置 `actions: ["frp", "info", "backup", "flash"]` 与
   `status: "researched"`。（现有按引擎流程会自动拾取——除非引擎本身
   缺失，否则不需要新增流程。）

4. **在 `operations/frp/devices/<brand>/<model>.md` 中放置简短研究笔记**，
   包含芯片、引擎、分区、构建指纹以及确认方案的一行描述（例如 "mmcblk0p4 = frp，
   BROM DA 即时擦除，无需 combo"）。格式参考
   `operations/frp/devices/nokia/nokia_g20.md`。

5. **若该芯片的引擎尚无流程**，在 `src/flows.rs` 中注册流程（一行 `flow!(...)`），
   并在 `src/<engine>.rs` + `src/main.rs` 中添加 CLI 分派。

## 为什么按芯片文件已消失

早期重构将庞大的 `frp.py` 拆分为 `operations/frp/chips/` 下的按芯片文件与
`operations/frp/{mtk,qualcomm,unisoc,samsung}_frp/` 下的按引擎文件。本 INDEX 的更
旧版本声称存在已死的文档存根与 `python/core/flows/brom.py` 分派
——该模块从未发布。真实的按芯片分派是 Rust 流程注册表
（`src/flows.rs`：`mtk_*`/`qcom_*`/`spd_*` 行，`flow-list` 校验）；本
INDEX.md 是映射图，让新开发者知道引擎特定代码实际位于何处。

## 为什么按引擎 Python shim 已消失

`operations/frp/mtk_frp/mtk_frp.py`（及其 4 个兄弟）从 `python.core.flows.brom`
导入函数，并在 GUI 从不读取的 **第二个** `FLOWS = {}` 字典下重新导出。
它们与 `python/core/flows/__init__.py` 中的规范 `FLOWS` 冲突，若 GUI 曾读取
会遮蔽真正的流程。现以各引擎文件夹内的 README 替代，指向真正的 Python 模块。
