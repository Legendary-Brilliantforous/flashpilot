# 安全策略

Language switcher: [English](../../SECURITY.md) · [Français](../../fr/SECURITY.md) · [Español](../../es/SECURITY.md) · [Deutsch](../../de/SECURITY.md) · **简体中文** · [Русский](../../ru/SECURITY.md) · [Português](../../pt/SECURITY.md) · [日本語](../../ja/SECURITY.md) · [العربية](../../ar/SECURITY.md) · [हिन्दी](../../hi/SECURITY.md) · [Türkçe](../../tr/SECURITY.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 支持的版本

项目处于 pre-1.0 阶段。安全修复会进入 `main` 分支，如果存在，也进入最新的打了 tag 的发布版本。

## 报告漏洞

请 **不要** 为安全问题公开提 issue。请私下报告：

- 邮箱：**flashpilot@proton.me**（在 proton.me 创建该地址 → 免费账户），或
- 本仓库的 GitHub 私有漏洞报告表单。

请包括：

- 受影响的命令 / flow 及版本，
- 复现步骤，
- 影响（如任意代码执行、砖机风险、数据丢失、凭证泄露）。

我们力争在 72 小时内确认报告，并协调披露。

## 范围与期望

此工具故意执行底层 USB / bootloader 操作。本质上它可能 wipe 或砖掉一台设备。这是文档化的行为，而非漏洞。我们关心：

- 超出预期操作、运行不受信任代码的 exploit，
- 以损害用户为代价绕过安全确认 / 设备检查，
- 在仓库中发布专有 blob 或 secrets，
- 任何泄露用户设备数据或凭证的行为。

仅在你拥有或被授权维修的设备上操作。