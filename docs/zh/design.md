# 设计系统 — FlashPilot

Language switcher: [English](../../design.md) · [Français](../fr/design.md) · [Español](../es/design.md) · [Deutsch](../de/design.md) · **简体中文** · [Русский](../ru/design.md) · [Português](../pt/design.md) · [日本語](../ja/design.md) · [العربية](../ar/design.md) · [हिन्दी](../hi/design.md) · [Türkçe](../tr/design.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 原则
- 单一暗色主题（无浅色变体），保证一致性与专注度。
- 强调色可配置；语义颜色永远不带强调色调。
- 所有 UI 令牌都位于 `python/gui/theme.py`（`C`、`ACCENT_THEMES`）。

## 令牌
- 颜色：`bg`、`panel`、`card`、`card_hover`、`inset`、`border`、`border_hi`、`text`、`text_hi`、`dim`、`mute`、`accent`、`accent_hi`、`ok`、`warn`、`err`。
- 语义化 UI 令牌：`focus_ring`、`sel_border`、`sel_border_hi`（永远不带强调色调）。
- 间距比例：4、8、12、16、24。
- 圆角比例：8、10、12、14、16。
- 字体：Inter/Segoe UI/Roboto；控制台使用 JetBrains Mono/Consolas 等宽字体。

## 组件
- 卡片：`QFrame#card`，带有玻璃渐变、细微边框、左侧强调色边缘。
- 按钮：主按钮（强调色渐变）、幽灵按钮（低调）、危险按钮（红色）。
- 输入框：圆角 10px，聚焦环使用强调色。
- 控制台：等宽字体、内嵌背景、12px。
- Toast：堆叠显示、按严重级别着色、自动消失。

## 动效
- 页面淡入 120–160ms；按钮按下；Toast 滑入。
- 尊重“减少动态效果”的设置。

## 规则
- 小组件中不得硬编码颜色；使用 `C`。
- 不得在主题令牌之外新增颜色。
- 所有破坏性操作都需要确认对话框。
- 实验性功能使用琥珀色虚线边框 + 确认门禁。
