# ImproveCore — Rust コア改善

Language switcher: [English](../../improvecore.md) · [Français](../fr/improvecore.md) · [Español](../es/improvecore.md) · [Deutsch](../de/improvecore.md) · [简体中文](../zh/improvecore.md) · [Русский](../ru/improvecore.md) · [Português](../pt/improvecore.md) · **日本語** · [العربية](../ar/improvecore.md) · [हिन्दी](../hi/improvecore.md) · [Türkçe](../tr/improvecore.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

出典：`ui-improvement.md` から移動した Rust 関連項目。

## デバイス別 ADB 書き込み
- リトライ/バックオフと明確な状態機械を備えたデバイスキー付き ADB セッション。
- デフォルトで verify-after-write（ハッシュ）；パーティション単位の進捗。
- 未認可/オフラインへの堅牢な処理；自動再認証プロンプト。
- 相互干渉なしで複数の同時 ADB デバイスをサポート。

## Odin（Samsung）イノベーション
- 最新 Odin を超える：単一セッションのレジリエンス、ポートリセット復旧、マルチパーティションストリーミング。
- より良い PIT 検証、vbmeta/AVB 処理、drk 修復ガイド。
- 瞬間的な USB エラーからの復旧/リトライ；詳細な失敗説明。

## BROM / 低レベル通信
- MTK、Samsung、SPD、Qualcomm の統一 BROM 抽象。
- crash-to-BROM ヘルパー、SLA/認証、DA アップロードの信頼性。
- 実行可能な修正を伴うエラー分類；段階ごとのタイムアウト。

## 最新 MTK サポート
- Preloader V5/V6 解析と DA 選択（`mtk_daloader.rs`）。
- 最新 MTK DA/preloader バージョンを追跡；自動検出と選択。
- 最新チップでも exploit/SLA パスが動作することを保証；テストフィクスチャを追加。

## USB インターフェース検出
- CDC ACM、ECM/NCM、mass storage、HID、ベンダー専用、診断/モデムを検出。
- bootrom、preloader、ADB、download モード、EDL、MTK、SPD を検出。
- インターフェース一覧をデバイス行に公開；サポートフローに対応付け。

## 即時削除（FRP/MDM/ロック）
- 安全な範囲での高速パスを含む、HiProTool のような研究統合、文書化。
- 検証済み手順を含む `operations/` のデバイス別 playbook。
- リスクのある操作には実験ゲーティング + 監査ログを維持。