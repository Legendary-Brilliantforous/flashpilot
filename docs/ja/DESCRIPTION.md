# FlashPilot 1.2.1 — 安定版

Language switcher: [English](../../DESCRIPTION.md) · [Français](../fr/DESCRIPTION.md) · [Español](../es/DESCRIPTION.md) · [Deutsch](../de/DESCRIPTION.md) · [简体中文](../zh/DESCRIPTION.md) · [Русский](../ru/DESCRIPTION.md) · [Português](../pt/DESCRIPTION.md) · **日本語** · [العربية](../ar/DESCRIPTION.md) · [हिन्दी](../hi/DESCRIPTION.md) · [Türkçe](../tr/DESCRIPTION.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

オープンソースの Linux 用 Android デバイス書き込み・修復ワークベンチ — 商用 Windows 書き込みスイートの無料相当品。**1.2.0 は安定性 + 進化リリース：`cargo check` 警告 0 件、`cargo test` 60 件 + `pytest` 149 件が合格、実稼働 GitHub リリースチャンネル、監査可能な履歴。**

ネイティブの **Rust** コア（`flashpilot-bridge`、約 9,300 行、vendored libusb）がブートローダープロトコルに直接話します — Samsung Odin/HID、MediaTek BROM/DA、Qualcomm Sahara/Firehose、Spreadtrum/UNISOC BSL — 一方、洗練された **PyQt6** スタジオは9つの転送手段、13のジョブカテゴリ、約120の操作を表示します：書き込み、FRP バイパス、画面ロック解除、MDM アンロック、パーティションツール、デバイス情報、再起動、任意の ADB デバイスでのバッテリー/ネットワーク修復。

**1.2.0 安定版の新機能：**
- **Bridge 警告 0 件** — 18本のデッドパスを接続：AT `Context` 保持と `vid` 検証（`+DEBUGLVC` 後の `AT/control` 再列挙）、USB `EndpointConfig.max_packet_size` チャンキングと `open_target/read_exact/info`、SPD `BSL_CMD`/`BSL_REP` + `iface` + `flush/read_flash/chip_uid/power_off`、`ProgressReporter` → 実書き込み %、Qualcomm `QcomDeviceInfo`/`FirehosePacket`、MTK `read16/write16` — `-80KB` `lto`、ハンドル漏れなし。
- **動的バージョン** — `APP_VERSION` はインストール済み `importlib.metadata` から（deb の `pyproject.toml` が真実源）、`_display_version` `1.2.0→1.2` / `1.2.1→1.2.1`、実稼働 GitHub `latest stable`（手書きハードコードなし）、ロゴ/タイトルバーの BETA ピル。
- **統一された大ダイアログ** — 320px toast に対し 620px の中央ドラッグ可能カード、高コントラスト `#e2e8f0` テキスト、`✕` + `X` ドラッグ、チップカラー：`MTK amber`、`QCOM red`、`SPD violet`、`SAMSUNG blue`；ベータゲートは `I accept` チェックボックス必須（バージョンごとに永続化、`first_install` デフォルト / Settings → Updates の `every_boot` 切替）、`Exit` でアプリ終了、stable の `UPDATE/AHEAD/PATCH` は同じ大ダイアログを使用、書き込み/FRP 確認オーバーレイはチップグラデーション。
- **単一グローバル STOP** — 任意のカード外のタイトルバー内単一 `⏹ STOP`、150ms で `_FLOW_LABEL` に同期、**任意の** Samsung/MTK/QC/SPD フローを停止；旧来のチップごとの STOP は非表示。
- **ガバナンス** — `dev`/`main` 保護：`strict` CI `Rust+Python`、`1` レビュー、`dismiss_stale`、`require_last_push_approval`、`linear_history`、`force_push:false`；`devin-ai-integration[bot]` を履歴/タグ `v1.2.1-beta.1` → `55c0da3` から削除。

- **プラットフォーム：** Linux
- **言語：** Rust（コア）+ Python 3.10+ / PyQt6（UI）
- **ライセンス：** MIT
- **状態：** stable 1.2.0 — 貢献者歓迎

所有するか、サービスを認可されたデバイスでのみ使用してください。