Language switcher: [English](../../SECURITY.md) · [Français](../fr/SECURITY.md) · [Español](../es/SECURITY.md) · [Deutsch](../de/SECURITY.md) · [简体中文](../zh/SECURITY.md) · [Русский](../ru/SECURITY.md) · [Português](../pt/SECURITY.md) · **日本語** · [العربية](../ar/SECURITY.md) · [हिन्दी](../hi/SECURITY.md) · [Türkçe](../tr/SECURITY.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

# セキュリティポリシー

## サポート対象バージョン

本プロジェクトは 1.0 未満です。セキュリティ修正は `main` ブランチに、存在する場合は最新のタグ付きリリースに適用されます。

## 脆弱性の報告

セキュリティ問題について **公開 issue を開かないでください**。非公開で報告してください：

- メール: **flashpilot@proton.me**（proton.me で作成 → 無料アカウント）、または
- GitHub のこのリポジトリにおける非公開脆弱性報告フォーム。

次の情報を含めてください：

- 影響を受けるコマンド / フローとバージョン、
- 再現手順、
- 影響（例：任意コード実行、ブリックリスク、データ損失、資格情報の露出）。

72 時間以内に報告を受理することを目指し、開示については調整します。

## 範囲と前提

このツールは意図的に低レベルな USB / ブートローダ操作を行います。本質的に、デバイスを消去したりブリックしたりする可能性があります。それは文書化された動作であり、脆弱性ではありません。私たちが重視するのは：

- 意図された操作を超えて信頼できないコードを実行するエクスプロイト、
- ユーザーに害を与える形での安全確認 / デバイスチェックのバイパス、
- リポジトリへの独自 blob や秘密情報の同梱、
- ユーザーのデバイスデータや資格情報を漏洩するあらゆるもの。

あなたが所有する、またはサービスを authorized されているデバイスに対してのみ操作を行ってください。
