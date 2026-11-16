Language switcher: [English](../../frp/INDEX.md) · [Français](../../fr/frp/INDEX.md) · [Español](../../es/frp/INDEX.md) · [Deutsch](../../de/frp/INDEX.md) · [简体中文](../../zh/frp/INDEX.md) · [Русский](../../ru/frp/INDEX.md) · [Português](../../pt/frp/INDEX.md) · **日本語** · [العربية](../../ar/frp/INDEX.md) · [हिन्दी](../../hi/frp/INDEX.md) · [Türkçe](../../tr/frp/INDEX.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# operations/frp/ — ファクトリーリセットプロテクション（Android のみ）

> Apple デバイスには FRP がありません（Apple は代わりに Activation Lock / iCloud を使用します）—
> `operations/apple/` を参照。

このディレクトリは FRP バイパスの **エンジン別ドキュメントツリー** を保持します。
実際のコードは `src/flows.rs`（Rust）にあります。特定端末の実レシピ（チップ、FDL ペア、
パーティションオフセットなど）がある場合は、`devices/<brand>/<model>.md` に短い研究メモを
残します。このファイルのルートにある README は、コードベース内のすべての FRP フローを、
どこにあるかと何が必要かにマップします。

## エンジンマップ

| エンジン | いつ使うか | コード | Bridge CLI |
|---|---|---|---|
| **Generic (ADB)** | USB デバッグが有効な任意の電話での第一試行 | Rust フロー（`adb_frp`、`src/flows.rs` の `frp_*` 行） | `flow-run adb_frp` / `adb shell ...` via `bridge.adb_shell` |
| **MTK BROM** | MediaTek（Helio / Dimensity / MT6765） — 電源 OFF → Vol-/+ を押し続ける → USB 接続 | Rust フロー（`src/flows.rs` の `mtk_*` 行） | `flow-run mtk_brom_info`（CLI: `mtk-detect`, `mtk-da-upload`, `mtk-frp`, `mtk-bypass`） |
| **MTK DA** | DA アップロードを生き残った MTK BROM（ロック状態チップ） | Rust フロー（`mtk_brom_backup`, `mtk_auth_flash`） | `flow-run mtk_brom_backup` |
| **Qualcomm EDL** | 9008 緊急ダウンロード（Snapdragon） | Rust フロー（`edl_*`, `qcom_*` 行） | `flow-run edl_frp`（CLI: `qcom-*`） |
| **Samsung Exynos** | A14（Exynos 850/1330）、A15/A16 — Odin ダウンロードモードはフラッシュ専用、FRP には使えません | Rust `frp_*` 行（Samsung アカウントバイパス） | （主にデバイス上、ブリッジなし） |
| **Samsung MTK (A05/A06)** | Helio G85 の A05/A06 — MTK BROM を使用（上記） | Rust フロー（`mtk_brom_info`, `mtk_brom_backup`） | `flow-run mtk_brom_backup` |
| **UNISOC/SPD** | 1782:4d00 FDL1+FDL2（SC9863A、T606/UMS9230） | Rust フロー（`spd_*` 行）+ `src/spd.rs` | `flow-run spd_detect_info`（CLI: `spd-detect`, `spd-frp`, `spd-format`, `spd-magic-pack`） |
| **HiSilicon Kirin** | 12d1 — まだ公開フローなし（リバースエンジニアリング未完了） | （まだなし） | （なし） |

（古い `python/core/flows/*.py` エンジンモジュールは出荷されませんでした。
`mtk-brom-backup` は `mtk_brom_backup` フロー行です。キーは `flow-list` で確認してください。）

## フローキー → 関数マップ

GUI の FRP アクションが呼び出せるすべてのフロー。キーは Rust レジストリ行
（`src/flows.rs`、`flow-list` で確認）です。GUI はそれらを (job, mode) で
ルーティングし、ブリッジが `flow-run <key> [target]` 経由で実行します。

| フローキー | エンジン | 何をするか |
|---|---|---|
| `adb_frp` | Generic ADB | `settings put secure frp 0` + セットアップウィザードの無効化 + GMS データの消去 |
| `frp_browser` | Generic ADB | intent 経由でデバイス上の `chrome://settings/` を開く |
| `frp_emergency` | Generic ADB | Emergency-call ダイアラー経由で Settings を開く（デバイス上） |
| `frp_settings` | Generic ADB | 通知シェード経路経由で Settings を開く（デバイス上） |
| `frp_fake_login` (+`_testdpc`, `+_adp`) | Generic ADB | デバイスオーナー DPC による QR プロビジョニング、続いて FRP クリア |
| `at_info` | Samsung MTP/AT | AT チャネル経由でモード + devconinfo を読み取る（Samsung pre-Android 8） |
| `at_method` | Samsung MTP/AT | AT+DEBUGLVC で diag ポート経由の ADB を有効化 |
| `download_frp` | Samsung Download mode | CSC / Combination ファームウェアの FRP 除去（PIT 安全契約） |
| `odin_enable_adb` | Samsung Download mode | Odin tarball 経由でダウンロードモードから ADB を有効化 |
| `mtk_combo_flash` | MTK Download | Combination ファームウェアのフラッシュ（PIT + DA） |
| `mtk_recovery_reset` | MTK Download | recovery モードでのファクトリーリセット |
| `mtk_brom_info` | MTK BROM | チップ ID / ハンドシェイクを読み取る（BROM フラッシュ前の必要作業） |
| `mtk_brom_backup` | MTK BROM | BROM DA 経由でパーティションをダンプ |
| `edl_frp` | Qualcomm EDL | Sahara + Firehose erase（05c6:9008） |
| `qcom_detect_info` | Qualcomm EDL | 検出 + info（読み取り専用） |
| `frp_qr_provision` | Generic ADB | QR プロビジョニング（TestDPC パス） |

（引退済み: 古い `flow_*` プレフィックス付きキー名と
`python/core/flows/*.py` は出荷されませんでした — キーに `flow_` プレフィックスはありません。）

## 新しい per-model レシピがここに入るまでの流れ

1. **実機ダンプを実行**（ADB 側は `scripts/dump-connected.sh`、Unisoc の BROM 側は
   `flashpilot-bridge spd-format` を参照）。ダンプは `build/cache/dumps/<model>_<codename>/`
   に入ります。

2. **ダンプから特定**するもの: エンジン + チップ + FRP パーティション名
   （Android 11+ ではほぼ常に `frp`、`frp_a`、または `userdata`）。

3. **デバイスエントリを追加**し、正しいブランドの下に `python/gui/supported_devices.json`
   へ書きます。`actions: ["frp", "info", "backup", "flash"]` と
   `status: "researched"` を設定。（既存の per-engine フローが自動的に拾います —
   エンジン自体が無い場合にのみ新しいフローが必要です。）

4. **短い研究メモを落とす** `operations/frp/devices/<brand>/<model>.md` に、チップ、
   エンジン、パーティション、build fingerprint、およびレシピを確認する one-liner
   （例: "mmcblk0p4 = frp, instant BROM DA erase, no combo needed"）を含めます。形式は
   `operations/frp/devices/nokia/nokia_g20.md` を参照。

5. **エンジン自体がこの chipset のフローを持っていなければ**、`src/flows.rs`
   （`flow!(...)` 行）にフローを登録し、`src/<engine>.rs` + `src/main.rs` に CLI
   ディスパッチを追加します。

## per-chip ファイルがなくなった理由

以前のリファクタでは god `frp.py` を `operations/frp/chips/` 配下の per-chip ファイルと
`operations/frp/{mtk,qualcomm,unisoc,samsung}_frp/` 配下の per-engine ファイルに分割しました。
この INDEX の古いリビジョンは、デッド docstub と `python/core/flows/brom.py` ディスパッチを
主張していましたが、そのモジュールは出荷されませんでした。本当の per-chip ディスパッチは
Rust フローのレジストリ（`src/flows.rs`: `mtk_*`/`qcom_*`/`spd_*` 行、`flow-list` で
確認）です。この INDEX.md は、エンジン固有コードが実際にどこにあるかを新しい開発者が
知るための地図です。

## per-engine Python shim がなくなった理由

`operations/frp/mtk_frp/mtk_frp.py`（およびその 4 兄弟）は `python.core.flows.brom` から
関数を import し、GUI が読むことのない **第二の** `FLOWS = {}` dict の下にそれらを
re-export していました。それらは `python/core/flows/__init__.py` の正規 `FLOWS` と
衝突し、GUI が読めば本物をマスクしてしまいました。エンジンフォルダ内の README に置き
換えられ、実際の Python モジュールを指しています。
