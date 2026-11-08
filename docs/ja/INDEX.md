# FlashPilot — インデックス

Language switcher: [English](../INDEX.md) · [Français](../fr/INDEX.md) · [Español](../es/INDEX.md) · [Deutsch](../de/INDEX.md) · [简体中文](../zh/INDEX.md) · [Русский](../ru/INDEX.md) · [Português](../pt/INDEX.md) · **日本語** · [العربية](../ar/INDEX.md) · [हिन्दी](../hi/INDEX.md) · [Türkçe](../tr/INDEX.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

README がマーケティングです。このファイルはエンジニアリングインデックス — 全フォルダ、その役割、見始める場所を説明します。

## 実行方法

```bash
# GUI
python main.py

# CLI (bridge) — 同じプロトコル、GUI なし
./target/release/flashpilot-bridge detect-all
./target/release/flashpilot-bridge spd-detect
```

## ルートレイアウト（17 エントリ）

| エントリ | 何 | いつ開くか |
|---|---|---|
| `main.py` | アプリのエントリポイント。リポジトリを `sys.path` に追加し、`python.gui.qt_app.main()` を呼ぶ。 | アプリ起動方法を変えるとき。 |
| `pyproject.toml` | Python パッケージメタデータ（name=flashpilot、deps、build backend）。 | Python 依存を追加したりバージョンを上げるとき。 |
| `Cargo.toml` / `Cargo.lock` | Rust コア（`flashpilot-bridge` バイナリ）。 | ブリッジ CLI を変える、または新規プロトコル追加時。 |
| `python/` | Rust エンジン上の薄い Python 層：`python/core/`（shim + GUI ヘルパー）と `python/gui/`（PyQt6）。全フローは `src/flows.rs` に存在。 | GUI とデバイス配管。 |
| `src/` | Rust ソース。`python/core/` とミラー構造。 | 新規 bridge コマンド追加や USB プロトコル変更時。 |
| `tests/` | pytest スイート。約 149 テスト、約 1s。 | `.venv/bin/python -m pytest tests/ -q` で実行。 |
| `scripts/` | スタンドアロンのシェルツール。今日：`dump-connected.sh`、`validate_mtp_at.py`。 | GUI なしのバッチ操作が必要なとき。 |
| `docs/` | README 資産（スクリーンショット、ロゴ）。 | README 用。 |
| `packaging/` | `.deb` ビルドスクリプト + コントロールファイル。 | リリース出荷時。 |
| `root/` | udev ルール（電話が sudo なしで動くように）。 | 一度きりのセットアップ。 |
| `operations/` | **per-job ドキュメントツリー** — 下の「operations/」参照。 | 特定ジョブ（FRP、MDM、画面ロック等）の理解時。 |
| `build/` | **gitignore された全 build/runtime 成果物** — 下の「build/」参照。 | ほぼ開かない。 |
| `.github/` | CI ワークフロー、issue テンプレート。 | CI を変えるとき。 |
| `LICENSE` `CODE_OF_CONDUCT.md` `CONTRIBUTING.md` `SECURITY.md` `DESCRIPTION.md` | 標準プロジェクトメタデータ。 | リリース時。 |

## `python/` レイアウト

```
python/
├── main.py                 <- app entry (adds repo to sys.path, calls python.gui.qt_app.main)
├── gui/                    <- PyQt6 app
│   ├── qt_app.py           <- The main window + every device-mode UI (~12k LOC)
│   ├── devices.py          <- Data-driven "supported devices" drill-down (brand -> model -> action)
│   ├── theme.py            <- Design tokens (colors, button styles, version helpers)
│   ├── animations.py       <- Painted glyphs: connection scene, status orb, etc.
│   ├── nav.py              <- Top-level navigation rail + OEM chip bar
│   ├── toast.py            <- Toast notifications
│   └── supported_devices.json  <- The database of which model gets which action
└── core/                   <- Thin Python layer (no Qt deps; delegates to Rust bridge)
    ├── core.py             <- FLOWS/JOBS/MODES mirror (hardcoded cache + Rust flow_list())
    ├── bridge.py           <- Talks to the Rust `flashpilot-bridge` binary
    ├── flow.py             <- Flow/Step primitives + cancellation
    ├── jobs.py             <- FlashJob lifecycle (isolated job layer)
    ├── cancel.py           <- Cooperative cancellation registry
    ├── devices.py          <- Multi-device identity (stable keys, list, resolve, transport mapping)
    ├── frp.py              <- FRP-only re-export surface (name == responsibility)
    ├── mtk.py              <- MTK PIDs/stages/chips (0003=BROM, 2000=preloader)
    ├── mtp.py              <- Samsung MTP/AT (multi-sequence ADB enable)
    ├── pit.py pitstore.py  <- Samsung PIT parser + cache
    ├── adb.py device_info.py actions.py experimental.py fus.py
    └── (no flows/ dir)     <- flows live in src/flows.rs; Python only delegates via bridge.flow_run()
```

**フローは Rust に存在します。** `python/core/core.py` は薄い shim です：`_RustFlow` は実行を `bridge flow-run <key>` に委譲します。正規のレジストリは `src/flows.rs`（`flow!` マクロ、約 280 行）；Python は GUI 検索向けにそれを反映します。

## `src/` レイアウト（Rust）

```
src/
├── main.rs                 <- All CLI dispatch (eprintln! is the "log" channel) + flow-run
├── flows.rs                <- THE flow registry (flow! macro; FLOWS/JOBS/MODES)
├── usb/                    <- libusb context, descriptor parsing, filtering (mod.rs + filtering.rs)
├── devices.rs              <- merged USB+ADB device rows
├── sam_download.rs         <- Samsung Download/Odin session (odin-* commands)
├── sam_errors.rs sam_setup.rs sam_*.rs  <- Samsung helpers
├── mtk.rs mtk_da.rs        <- MediaTek BROM/DA flashing
├── mtk_exploit.rs          <- BROM exploits (bypass/kamakiri2/crash-to-BROM)
├── mtk_sla.rs mtk_sla_keys.rs <- Secure Lock Authentication
├── mtk_daloader.rs         <- DA container parsing
├── qualcomm/               <- EDL: Sahara + Firehose + GPT
├── spd.rs                  <- UNISOC BSL (BSL_CMD_*, BSL_REP_*, FDL1/FDL2)
├── pac.rs                  <- SPD PAC extract/pack
├── pit.rs                  <- Samsung PIT parser
├── mtp.rs at.rs adb.rs     <- MTP, AT command, ADB plumbing
├── fastboot.rs             <- native fastboot transport
├── moto_flash.rs           <- Motorola staged fastboot FRP
├── apple.rs                <- Apple usbmuxd/lockdown
├── bulk.rs hid.rs          <- bulk + HID helpers
├── fwtar.rs sparse.rs imgtools.rs <- firmware tar/sparse/boot-vbmeta
├── hostinfo.rs             <- host eMMC/UFS health
├── config.rs error.rs util.rs device.rs
└── (no odin.rs)            <- Odin logic lives in sam_download.rs
```

## `operations/` — per-job ドキュメントツリー

これらのフォルダは **per-operation の README ツリー**を保持しており、各ジョブの動作、使用する flow key、サポート端末、既知の caveats を説明します。コードではありません — ツリーは純粋な markdown です（過去のクリーンアップでここにあった stale な `.py` shim は除去済み；`operations/` を import するものはありません）。コードは `src/flows.rs`（`flow!` レジストリ；`python/core/core.py` は薄い shim）と per-domain モジュール（`knox.py`、`qcn.py`、`imei.py`、`emmc.py`、…）に存在します。`operations/` の README はエンドユーザー / 商用ツール研究者向けに書かれています；コードが信頼できる情報源です。

| フォルダ | 何 | 実コード |
|---|---|---|
| `operations/apple/` | Apple iCloud、アクティベーションロック、MDM、パスコード/紛失モード除去 | Rustフロー (`src/flows.rs`: `apple_*` 行、`flow-run` CLI) |
| `operations/frp/` | FRP バイパス per-engine + per-device 研究メモ。**`operations/frp/INDEX.md` から始めること**。 | Rustフロー (`src/flows.rs` レジストリ、`flow-run` CLI)；薄い `python/core/core.py` shim |
| `operations/mdm/` | MDM / device-owner アンロック + ブランド別デバイスメモ | Rustフロー (`src/flows.rs` レジストリ、`flow-run` CLI) |
| `operations/screen_unlock/` | 画面ロック解除 (ADB / recovery / download / comprehensive) | Rustフロー (`src/flows.rs` レジストリ、`flow-run` CLI) |
| `operations/battery/` | バッテリーレポート / 修復 / 負荷試験 (ADB 上) | Rustフロー (`src/flows.rs` レジストリ、`flow-run` CLI) |
| `operations/network/` | SIM 状態、DNS、無線リセット | Rustフロー (`src/flows.rs` レジストリ、`flow-run` CLI) |
| `operations/carrier_unlock/` | キャリアロック (Apple、MTK) | Rustフロー (`src/flows.rs` レジストリ、`flow-run` CLI) |
| `operations/flashing/` | ベンダー別書き込みガイド (Samsung Odin、MTK DA、Qualcomm EDL、UNISOC SPD、PIT) | Rustフロー (`src/flows.rs` レジストリ、`flow-run` CLI) |
| `operations/usb/` | USB 列挙・検出メモ | `src/usb/`, `src/devices.rs`, `python/core/devices.py` |

## `build/` — gitignore された runtime/build 成果物

| サブディレクトリ | 内容 | 作成者 |
|---|---|---|
| `build/target/` | Rust `cargo build` 出力 | `cargo build` |
| `build/dist/` | `.deb` パッケージ | `packaging/build-deb.sh` |
| `build/cache/` | 端末別 TAR キャッシュとリバースエンジニアリング dump | GUI / `scripts/dump-connected.sh` |
| `build/mdm_qr/` | 生成された MDM プロビジョニング QR コード | GUI MDM フロー |
| `build/pit/` | キャッシュされた `.pit` パーティションテーブルファイル | GUI PIT フロー |

**ルール:** `build/` の中身は `git add` しないこと。状態を消したいならサブディレクトリを削除 — 再生成されます。

## 新機能を追加するには（「どのファイルを触る？」チートシート）

| したいこと | 触る場所 |
|---|---|
| サポートリストに新規端末を追加 | `python/gui/supported_devices.json` |
| サポート済み端末に per-vendor アクションを追加 | `src/flows.rs`（`flow!(...)` 行を追加）；Python は `bridge.flow_list()` 経由で自動検出 |
| 既存の concern に新規 ADB コマンドフローを追加 | 同上（Rust `src/flows.rs`） |
| 新規 bridge CLI コマンドを追加 | `src/<concern>.rs` + `src/main.rs`（match の `<cmd>` arm） |
| 新規トップレベルナビページを追加 | `python/gui/qt_app.py` (`_build_*_page` + `_section_index`) |
| 新規デザイン色 / ボタンスタイル追加 | `python/gui/theme.py` (`C` dict / `_btn_*()`) |
| 新しいデバイスの per-job メモを文書化 | `operations/<job>/<brand>/<model>.md` |
| テスト追加 | `tests/test_<area>.py`、`test_mtk.py` パターンに従う |

## 操作ランナーの仕組み（一度読めば十分）

GUI はフローを直接呼びません。per-operation のデバイス選択機（`FlashPilotWindow._choose_device`）がまず安定デバイスキーを解決し、その後 `_run_ops_flow` / `_run_job_flow` が `python.core.core.flow_for(job, mode, method)` を呼び `Flow()` オブジェクト（`Step()` のリスト）を返し、`flow.run(ctx, log)` を `devices.device_scope(key)` 内の worker スレッドで呼びます（すべての resolver が選択した電話を対象にするため）。各フローは GUI がコンソールに接続する callable `log(line)` に記録します。キャンセルはデバイススコープ（`flow.request_cancel(key)`；キーなしブロードキャストは全停止）、各 `_run` 冒頭でチェック。

フローを追加するには：`src/flows.rs` に 1 行 `flow!("my_op", "My op", "Job Name", "MODE")` を追加。Python は `bridge.flow_list()` 経由で自動検出し、GUI の job/mode/method ドリルダウンが自動的に拾います。Rust の `flow-run` CLI が実行；resolver はターゲット serial / `vid:pid@bus:addr` を受け取る必要があります（`src/device.rs` を参照）。