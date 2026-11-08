# ImproveCore — Rust 核心改进

Language switcher: [English](../../improvecore.md) · [Français](../fr/improvecore.md) · [Español](../es/improvecore.md) · [Deutsch](../de/improvecore.md) · **简体中文** · [Русский](../ru/improvecore.md) · [Português](../pt/improvecore.md) · [日本語](../ja/improvecore.md) · [العربية](../ar/improvecore.md) · [हिन्दी](../hi/improvecore.md) · [Türkçe](../tr/improvecore.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

来源：从 `ui-improvement.md` 迁移的 Rust 相关条目。

## 每设备 ADB 刷机
- 带重试/退避与清晰状态机的设备键控 ADB 会话。
- 默认 verify-after-write（哈希）；分区分粒度进度。
- 对未授权/离线的稳健处理；自动重新认证提示。
- 支持多台并发 ADB 设备，无串台。

## Odin（Samsung）创新
- 超越最新 Odin：单会话弹性、端口重置恢复、多分区流式传输。
- 更好的 PIT 校验、vbmeta/AVB 处理、drk 修复指引。
- 瞬态 USB 错误的恢复/重试；详细的失败解释。

## BROM / 底层通信
- MTK、Samsung、SPD、Qualcomm 的统一 BROM 抽象。
- 崩溃到 BROM 的助手、SLA/认证、DA 上传可靠性。
- 带可执行修复建议的错误分类；每阶段超时。

## 最新 MTK 支持
- Preloader V5/V6 解析与 DA 选择（`mtk_daloader.rs`）。
- 跟踪最新 MTK DA/preloader 版本；自动检测与选择。
- 确保 exploit/SLA 路径在最新芯片上可用；增加测试固件。

## USB 接口检测
- 检测 CDC ACM、ECM/NCM、大容量存储、HID、厂商专属、诊断/调制解调器。
- 检测 bootrom、preloader、ADB、download 模式、EDL、MTK、SPD。
- 在设备行中暴露接口列表；映射到支持的流程。

## 即时移除（FRP/MDM/锁）
- 如 HiProTool 般的研究集成：在安全前提下的快速路径，并有文档。
- `operations/` 中带已验证步骤的设备专用 playbook。
- 对风险操作保持实验门控 + 审计日志。