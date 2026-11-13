# Design System — FlashPilot

Language switcher: [English](../../design.md) · [Français](../fr/design.md) · [Español](../es/design.md) · [Deutsch](../de/design.md) · [简体中文](../zh/design.md) · [Русский](../ru/design.md) · [Português](../pt/design.md) · **日本語** · [العربية](../ar/design.md) · [हिन्दी](../hi/design.md) · [Türkçe](../tr/design.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 原則
- 一貫性と集中のため、単一のダークテーマ（ライト版なし）。
- アクセントは設定可能。セマンティックカラーはアクセントで色付けしない。
- UI トークンはすべて `python/gui/theme.py` に格納（`C`, `ACCENT_THEMES`）。

## トークン
- カラー: `bg`, `panel`, `card`, `card_hover`, `inset`, `border`, `border_hi`, `text`, `text_hi`, `dim`, `mute`, `accent`, `accent_hi`, `ok`, `warn`, `err`。
- セマンティック UI トークン: `focus_ring`, `sel_border`, `sel_border_hi`（アクセントで色付けしない）。
- スペーシングスケール: 4, 8, 12, 16, 24。
- ラジウススケール: 8, 10, 12, 14, 16。
- タイポグラフィ: Inter/Segoe UI/Roboto。コンソール用等幅は JetBrains Mono/Consolas。

## コンポーネント
- カード: ガラスグラデーション、微妙な境界線、左端にアクセント。`QFrame#card`。
- ボタン: プライマリ（アクセントグラデーション）、ゴースト（控えめ）、デンジャー（赤）。
- 入力: 10px の角丸、フォーカスリングはアクセント。
- コンソール: 等幅、インセット背景、12px。
- Toast: 積み重ね、重大度で色分け、自動非表示。

## モーション
- ページフェード 120–160ms。ボタン押下、toast スライド。
- `reduced-motion` 設定を尊重する。

## ルール
- ウィジェットにハードコードの色は使わない。`C` を使う。
- テーマトークンに追加しない新しい色は作らない。
- 破壊的アクションにはすべて確認ダイアログが必要。
- 実験的機能はアンバー色の破線境界 + 承認ゲート (ack gate)。