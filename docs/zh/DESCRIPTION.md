# FlashPilot 1.2.1 — 稳定版

Language switcher: [English](../../DESCRIPTION.md) · [Français](../fr/DESCRIPTION.md) · [Español](../es/DESCRIPTION.md) · [Deutsch](../de/DESCRIPTION.md) · **简体中文** · [Русский](../ru/DESCRIPTION.md) · [Português](../pt/DESCRIPTION.md) · [日本語](../ja/DESCRIPTION.md) · [العربية](../ar/DESCRIPTION.md) · [हिन्दी](../hi/DESCRIPTION.md) · [Türkçe](../tr/DESCRIPTION.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

开源 Linux Android 设备刷机与修复工作台 —— 商用 Windows 刷机套件的免费等价物。**1.2.0 是稳定性 + 进阶发布版：`cargo check` 0 警告，`cargo test` 60 项 + `pytest` 149 项全部通过，实时 GitHub release 通道，可审计的历史记录。**

原生 **Rust** 核心（`flashpilot-bridge`，约 9,300 行代码，内嵌 libusb）直接与 bootloader 协议对话 —— Samsung Odin/HID、MediaTek BROM/DA、Qualcomm Sahara/Firehose、Spreadtrum/UNISOC BSL —— 而精致的 **PyQt6** 工作室呈现 9 种传输方式、13 个任务类别和约 120 个操作：刷机、FRP 绕过、移除屏幕锁、MDM 解锁、分区工具、设备信息、重启，以及任何 ADB 设备上的电池/网络修复。

**1.2.0 稳定版的新内容：**
- **Bridge 0 警告** — 接通了 18 条死路径：AT `Context` 保留与 `vid` 校验（`+DEBUGLVC` 后 `AT/control` 重新枚举）、USB `EndpointConfig.max_packet_size` 分块与 `open_target/read_exact/info`、SPD `BSL_CMD`/`BSL_REP` + `iface` + `flush/read_flash/chip_uid/power_off`、`ProgressReporter` → 真实刷机百分比、Qualcomm `QcomDeviceInfo`/`FirehosePacket`、MTK `read16/write16` —— `-80KB` `lto`，无句柄泄漏。
- **动态版本** — `APP_VERSION` 来自已安装的 `importlib.metadata`（deb 的 `pyproject.toml` 为真源），`_display_version` `1.2.0→1.2` / `1.2.1→1.2.1`，实时 GitHub `latest stable`（绝不手写硬编码），Logo/标题栏 BETA 胶囊。
- **统一大对话框** — 620px 居中可拖拽卡片（对比 320px toast）配高对比 `#e2e8f0` 文字、`✕` + `X` 拖拽、芯片颜色：`MTK amber`、`QCOM red`、`SPD violet`、`SAMSUNG blue`；beta 门控需要 `I accept` 复选框（按版本持久化，`first_install` 默认 / 设置 → 更新中的 `every_boot` 切换），`Exit` 退出应用，稳定版 `UPDATE/AHEAD/PATCH` 使用相同的大对话框，刷机/FRP 确认遮罩使用芯片渐变。
- **一个全局 STOP** — 标题栏内单一 `⏹ STOP`（任何卡片外），150ms 同步到 `_FLOW_LABEL`，停止 *任何* Samsung/MTK/QC/SPD 流程；旧的每芯片 STOP 已隐藏。
- **治理** — `dev`/`main` 受保护：`strict` CI `Rust+Python`、`1` 审查、`dismiss_stale`、`require_last_push_approval`、`linear_history`、`force_push:false`；`devin-ai-integration[bot]` 已从历史/标签 `v1.2.1-beta.1` → `55c0da3` 中移除。

- **平台：** Linux
- **语言：** Rust（核心）+ Python 3.10+ / PyQt6（UI）
- **许可：** MIT
- **状态：** stable 1.2.0 — 欢迎贡献者

仅用于你拥有或被授权维修的设备。