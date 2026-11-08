Language switcher: [English](../../CONTRIBUTING.md) · [Français](../../fr/CONTRIBUTING.md) · [Español](../../es/CONTRIBUTING.md) · [Deutsch](../../de/CONTRIBUTING.md) · [简体中文](../../zh/CONTRIBUTING.md) · [Русский](../../ru/CONTRIBUTING.md) · [Português](../../pt/CONTRIBUTING.md) · **日本語** · [العربية](../../ar/CONTRIBUTING.md) · [हिन्दी](../../hi/CONTRIBUTING.md) · [Türkçe](../../tr/CONTRIBUTING.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

# 🧑‍💻 FlashPilot への貢献

通りがかりにありがとうございます！このプロジェクトはリバースエンジニアリングされたプロトコルと
オープンな知識の上に成り立っています — すべての貢献が、より高機能に、より信頼性高く、
有料 Windows スイートにより近づけます。フラッシュの専門家でなくても手伝えます。

## 目次

- [コードオブコンダクト](#コードオブコンダクト)
- [プロジェクトの構成](#プロジェクトの構成)
- [貢献の方法](#貢献の方法)
- [はじめに](#はじめに)
- [アーキテクチャツアー（10 分）](#アーキテクチャツアー10-分)
- [新しいフローの追加方法](#新しいフローの追加方法)
- [新しい USB プロトコル / Rust コマンドの追加](#新しい-usb-プロトコル--rust-コマンドの追加)
- [GUI ガイドライン](#gui-ガイドライン)
- [テスト](#テスト)
- [プルリクエストチェックリスト](#プルリクエストチェックリスト)
- [ロードマップとアイデア](#ロードマップとアイデア)

---

## コードオブコンダクト

[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) を参照。敬意を払い、善意を仮定し、
議論は技術的かつ有益に保ってください。これは趣味から真面目になったプロジェクトです:
初心者もベテランも歓迎します。ハラスメント、ゲートキーピング、
秘密情報 / 資格情報のコミットは容認しません。プロトコルのペイロードは、
出所とライセンスが文書化されている場合に歓迎します。

---

## プロジェクトの構成

二つの半分が連携します:

| レイヤー | 場所 | 言語 | 役割 |
|---|---|---|---|
| **コア / プロトコルエンジン** | `src/` | Rust | 生 USB、すべてのブートローダプロトコル（`flashpilot-bridge` CLI） |
| **フローレジストリ** | `src/flows.rs` | Rust | `flow!` マクロ行 → `FLOWS` / `JOBS` / `MODES`（信頼できる唯一の情報源） |
| **フロー shim** | `python/core/core.py` | Python | 薄い `_RustFlow` ラッパー + `JOBS` フォールバック; `bridge flow-run` に委譲 |
| **デバイス識別** | `python/core/devices.py` | Python | 安定キー、デバイス一覧、ターゲットの再解決、スレッドスコープ |
| **FRP サーフェス** | `python/core/frp.py` | Python | FRP のみの再エクスポート（名前 == 責務） |
| **GUI スタジオ** | `python/gui/` | Python / PyQt6 | Workbench (`qt_app.py`)、ページ (`devices.py`)、テーマ、アニメーション |

Python は USB と直接話しません。Rust バイナリ（`target/release/flashpilot-bridge`）を
呼び出し、JSON / テキストを受け取ります。GUI はワーカースレッドのシグナルだけを
聞きます — バックグラウンドスレッドからウィジェットを触らないでください。

---

## 貢献の方法

コードなしでも問題ありません:

- **実機でのテスト** — フローがどのデバイス / ファームウェアで動作するかを報告。
- **ドキュメント** — README、このファイル、フロー説明の改善。
- **ファームウェア / DA / コンボアーカイブ** — 合法で自由に入手可能なバイナリへのポインタ。
- **翻訳とテーマ** — GUI はテーマ可能; 新しいアクセントパックは簡単な勝利。
- **UI/UX** — モックアップ、アクセシビリティパス、キーボードショートカット設計。
- **バグ報告** — [バグ報告テンプレート](https://github.com/Legendary-Brilliantforous/flashpilot/issues/new?labels=bug&template=bug_report.yml)を使用: 手順、ログ、`flashpilot-bridge detect` 出力、デバイスモデル + ファームウェアバージョン。
- **コード** — 下記参照。

> 💡 **初めてですか?** issue トラッカーの **`good first issue`** ラベルを探してください —
> キュレートされた、初心者向けで、完全にスコープが定まり、着手しやすいタスクです。

---

## はじめに

```bash
# 1. Rust ブリッジをビルド
cargo build --release

# 2. (推奨) USB udev ルール
sudo bash root/setup-usb.sh

# 3. venv を作成して実行
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m python.main
```

アプリはネイティブ PyQt6 ウィンドウを開きます。**Settings → Tools** ページで
ブリッジがビルド済みかどうかと ADB が検出されているかを確認できます。

---

## 古いチェックアウトからの移行（戻ってきた場合はまずこれを読む）

 churn について率直に: 1.2.0 と現在の間に、中央モジュールのリネーム、god-file の
フォーカスされたモジュールへの分割、すべてのジョブ名のリネーム、十数ファイルの追加を
行いました。古い import、古い docs 参照、`python.core.frp` に対して書いたツリー外
スクリプトは壊れます。申し訳ありません — god-file を倒し、MTK PID の混乱を修正し、
ハックを積み上げずにマルチデバイス対応を可能にする唯一の方法でした。この節は完全な
適応ガイドです。ここにあるものは段階的に非推奨になるものではなく、一度にすべて変更
されたので、表を一度通れば現行です。

### リネームされたパス

| Before | After | 変更点 |
|---|---|---|
| `python/core/frp.py` (god file: レジストリ + すべてのフロー) | `python/core/core.py` | `from python.core import frp` → `from python.core import core`; `frp.FLOWS` → `core.FLOWS`, etc. |
| *(nothing — FRP lived inside the god file)* | `python/core/frp.py` (新規, FRP のみ) | FRP フローだけが必要なら、`core` の代わりにここから import。 |
| *(nothing)* | `python/core/devices.py` (新規) | デバイス識別、`list_devices()`、`resolve_usb_target()`、`device_scope()`。 |
| *(nothing)* | `python/core/imei.py` (新規) | MTK/SPD の IMEI 修復 + 変更フロー。 |
| *(nothing)* | `python/core/experimental.py` (新規) | EXPERIMENTAL ゲート + 監査ログ。 |
| *(nothing)* | `python/core/{knox,qcn,emmc,pac,apple,health,compat,device_info,fastboot,integrity,safety,spd_adb}.py` (新規) | 以前は god-file 内のインラインだった、または欠けていたドメイン単位のロジック。 |
| *(nothing)* | `tests/test_devices.py` (新規) | マルチデバイス + cancel-scope テスト。 |
| *(nothing)* | `CHANGELOG.md` (新規) | リリースごとにグループ化された変更; まず確認。 |

### Rust への移行（現在のアーキテクチャ — 上の表は履歴）

上記の分割の後、エンジンは Rust に移り、Python 側は薄くなりました。現在の真実:

- **フローは `src/flows.rs` に存在**（レジストリ + `flow-run <key> [target]
  [--code/--partition/--file/--dpc ...]`）。`flow-list` が信頼できる情報源 — docs で
  フローキーを引用する前にそこで確認。
- **`python/core/core.py` は薄い shim**（約 450 行）: `_RustFlow` は `bridge flow-run`
  に委譲し、レジストリはフォールバック `JOBS` 付きでブリッジから取得。16 の
  ドメイン別エンジンモジュール（`knox`, `qcn`, `emmc`, `imei`, `apple`, `ofp`,
  `pac`, `health`, `flashing`, `spd_adb`, `integrity`, `fastboot`, `usb_watch`,
  `compat`, `updater`, `safety`）は削除されました — 新しい docs で参照しないこと。
- **GUI は Python のまま**（`python/gui/qt_app.py` + `devices.py`）;
  Rust レジストリを `bridge.flow_list()` 経由で消費。
- 削除された Python フローの古いテストファイルはそれらと一緒に削除されました;
  カバレッジはドメイン別スイート + cargo `flows::tests` です。

### 適応が必要な API 変更

- **リゾルバは `key=None` を受け取る。** `find_samsung()`、`_download_mode_device()`、
  `_wait_for_adb()`、`_wait_mtk_brom_target()`、`_mtk_retry()`、
  `wait_clean_download_mode()`、`pit_contract()` はすべてオプションの安定デバイスキーを
  受け取る（デフォルトは ambient thread scope — 古い call site は動作し続け、キーが
  未設定の場合は first-match 動作を維持）。
- **キャンセルはデバイス単位。** `flow.py` と `bridge.py` の `request_cancel()` /
  `clear_cancel()` / `cancel_requested()` は `key=None` を受け取る。キーなしの
  `request_cancel()` は引き続きブロードキャスト（global STOP）; キーなしチェックは
  まず ambient scope を見、次に broadcast bus を見ます。
- **run-guard はデバイス単位。** `qt_app.py` の `_flow_start(label, destructive, key=None)` /
  `_flow_end(key=None)` / `_flow_busy_msg(key=None)`; 古い globals `_FLOW_LOCK` /
  `_FLOW_LABEL` は消えました（per-key dicts + `_flows_running()` に置換）。
- **ランナーは `device_key=None` を受け取る。** `_run_ops_flow()` / `_run_job_flow()`
  は複数の電話が一致するとデバイスピッカーを表示し、その後
  `ctx["device_key"]`（+ 解決可能なら `ctx["target"]`）を設定し、
  `devices.device_scope()` の中で実行します。
- **新しいトランスポートモード `"SPD"`** が `MODES` に（VID `0x1782`）; 新しいジョブ
  `Knox / Warranty`、`QCN / Modem`、`IMEI Repair / Change`、`eMMC / UFS`。
- **ジョブ名は動詞先頭**（`Remove FRP`、`FRP bypass` ではなく; README 参照）。
  ブランチがまだ古い名前を参照している場合は、「アーキテクチャツアー」の表に
  沿ってリネーム。
- **MTK PID は mtkclient 規約**：`0e8d:0003` = BROM、`0e8d:2000` = preloader。
  多くの古いコメント / ログで逆になっていました; 古い文字列ではなく
  `mtk.pid_stage()` / Rust `boot_stage_for()` を信頼。

### 再構成前の PR が開いている場合

1. 新しいツリーに rebase; conflict は import と `JOBS`/`FLOWS` ブロックに
   局限される想定。
2. 下のチェックリストを実行 — `pytest` が古いキー/名前参照を即座に検出します
   （レジストリテストはすべての `JOBS` メソッドが解決することを assert）。
3. PR が `flows/`（削除された分割パッケージの実験）に触っていた場合:
   そのディレクトリは消滅しました。変更を `core.py` + ドメインモジュールへ移植。

---

## アーキテクチャツアー（10 分）

1. **`src/main.rs`** — 80+ コマンドの CLI。各 `match` arm が 1 コマンド
   （`detect`, `mtk-flash`, `mtk-crash-brom`, `qcom-firehose`, `spd-format`,
   `odin-pit`, ...）。
2. **`src/usb.rs`** — VID/PID でデバイスを検出し、エンドポイントを提供
   （再列挙に耐える安定した `port_numbers` も）。
3. **`src/odin.rs`** — Samsung download モード（Heimdall 派生のリバースエンジニアリング
   Odin 3 プロトコル）。PIT の read/write、パーティション flash
   （永続 `odin-agent` セッションマルチプレクサ含む）。
4. **`src/mtk*.rs`** — MediaTek BROM (`0e8d:0003`) → preloader (`0e8d:2000`) →
   Download Agent ハンドシェイク、scatter 解析、GPT パーティション作業、SLA キー、
   BROM エクスプロイト、crash-to-BROM。⚠️ PID 規約は mtkclient スタイル:
   `0003`=BROM、`2000`=preloader — 入れ替えない。
5. **`src/qualcomm/`** — Sahara (EDL) ハンドシェイクと Firehose セッション。
6. **`src/spd.rs`** — Spreadtrum/UNISOC BSL: FDL ダウンロード、フォーマット、FRP、
   バックアップ、PAC extract/pack。
7. **`src/flows.rs`** — **アプリの心臓部**。`flow!(key, label, job, mode)` 行が
   `FLOWS` / `JOBS` / `MODES` レジストリを構築（約 280 行、13 ジョブ、
   `SPD` を含む 9 モード）。`python/core/core.py` は GUI 検索用にそれを鏡写し。
8. **`python/core/devices.py`** — マルチデバイス識別。安定キー
   (`adb:<serial>` → `usb:<port-path>` → 揮発性フォールバック)、`list_devices()`、
   `resolve_usb_target()`、選択した電話をリゾルバへ運ぶ thread-local `device_scope()`。
9. **`python/gui/qt_app.py`** — 全セクション（Samsung / MTK / QC / SPD / Battery /
   Network / Settings）とサブタブ Workbench、加えて操作単位のデバイスピッカーと
   デバイス単位の run-guard を構築。

### データフロー

```
ボタンクリック
  → _choose_device(job, mode)          # 0-1 台一致なら黙って、そうでなければピッカー
  → _run_ops_flow(job, mode, method, name, device_key)
  → デバイス単位の _flow_start(key) + device_scope(key) + ctx["device_key"]
  → core.flow_for(...) -> Flow (Step のリスト)
  → 各 Step がワーカースレッドで実行し bridge._run([...]) を呼ぶ
  → bridge が target/release/flashpilot-bridge ... を起動
  → Rust が USB I/O を行い JSON/text を出力
  → Python が解析 + _ui.line() シグナルを発行（[device-key] タグ付き）
  → GUI がコンソール / 状態 / 進捗を安全に更新
```

---

## 新しいフローの追加方法

出荷できる最も簡単な機能。`src/flows.rs` を開いて 1 行追加:

```rust
flow!("my_method", "My method", "Remove FRP", "ADB"),
```

キーは短い snake_case（`flow_` プレフィックスなし）。Python は `bridge.flow_list()` 経由で
自動検出し、GUI の job/mode/method ドリルダウンが自動的に取り込みます;
実行は `flashpilot-bridge flow-run my_method` を通ります。

その後（新しい低レベルプロトコル作業が必要な場合のみ）`src/<concern>.rs` + `src/main.rs`
にブリッジコマンドを追加。job/mode の配線はフロー行に既にあります。

以上 — フローは GUI のドロップダウン / サブタブに自動表示され、CLI からも
到達可能です。**ここが最も価値が高く、最も入りやすい領域です。**

> ステップ内ではコンソール出力に `log(...)`、ステップ間で引き継ぐ状態に `ctx`、
> Rust バイナリに触れるものに `bridge._run(...)` を使用。Stop が機能するよう、
> 適切な箇所で `cancel_requested()` と協調的に（キャンセルはデバイススコープ —
> 下記参照）。

### すべてのフローが従うべきルール

- **"その" デバイスをつかまない。** 追加するあらゆるリゾルバで `key=None`
  （ambient thread scope）を受け取り、それでフィルタ — `devices.device_key()`、
  `devices.match_key()`、`devices.device_scope()` を参照。GUI は操作単位でスコープを
  設定; ヘッドレス呼び出し元も可能。
- **ジョブ名は動詞先頭**（`Remove FRP`, `Flash Firmware`, `Unlock Carrier`）。
  **フローキーは短い snake_case**（`adb_frp`、`flow_adb_frp` ではない）; 唯一の
  歴史的 alias（`fastboot_read`）は削除済み — alias を追加しないこと。
- **MTK PID 規約は mtkclient スタイル**：`0e8d:0003` = BROM（保持）、`0e8d:2000` =
  preloader。Rust、Python、GUI ラベル、docs はすべて一致していなければならない。
- **EXPERIMENTAL 書き込み**（Knox/IMEI/QCN/eMMC）は per-run ack 付きで
  `experimental.check_gate_strict()` を通す — 保存された ack が自動通過しては
  ならない。GUI 側は所有チップページ上の `_EXPERIMENTAL_FLOW_MAP` + 琥珀色の
  折りたたみパターンで gate する（決してグローバル LAB ページではない）。
- **ブリッジターゲットは揮発性**（`vid:pid@bus:addr` は再列挙で変わる）。
  セッションを開く前に安定キーから再解決（`devices.resolve_usb_target()`）;
  odin4 は `-d /dev/bus/usb/BBB/AAA` でピン留め。

---

## 新しい USB プロトコル / Rust コマンドの追加

1. `src/` 配下にモジュールを追加（例: `src/myproto.rs`）。
2. `src/main.rs` に `mod myproto;` と新しい `match` arm + 使用法行を追加。
3. `crate::error` 経由で `Result<T>` を返し、構造化出力に `serde_json` を使用。
4. Python 側では `python/core/bridge.py` で `_run([...])` のラッパーとして露出。
5. それを呼ぶ `Flow` を `core.py` に構築（上記フロールールを守る）。
6. 可能ならテストを追加 — ユニットテストは `src/*.rs`（`#[test]`）と `tests/`。

**プロトコル衛生:** モジュール docstring に出所（フォーラム、クリーンルーム write-up、
他の OSS プロジェクト）を cites する。プロトコル実装のみ、独自 blob は含めません。

---

## GUI ガイドライン

- **PyQt6 のみ。** 他の Qt バインディングや追加 UI deps なし（`requirements.txt` 参照）。
- 既存のビジュアル言語に合わせる: `_btn_ghost()`, `_btn_primary()`,
  `_card_qss()`, `SectionTitle`, `C[...]` テーマ色, ボタングリッドには `FlowLayout`。
- **生のアクセントではなくテーマトークン:** 塗りは `C['accent'/'grad_a'/'grad_b']` を
  使ってよいが、フォーカスリング、選択タブの枠線、チェックボックスは必ず中立の
  `C['focus_ring']` / `C['sel_border']` を使用 — そうでなければ red アクセントテーマ
  (Crimson, Sunset) が red を focus 状態に漏らす。chrome に hex をハードコードしない。
- **スレッドルール:** バックグラウンド作業は `threading.Thread` へ; GUI 更新は
  `self._ui.*` シグナル（`.line`, `.status`, `.toast`, `.ui`, `.progress`）経由のみ。
- **アニメーション:** `Motion.shake()` / `Motion.rubber()` はウィジェット単位で
  相互排他（`_anim_lock` でガード）— 両方を同時に実行したり、呼び出し側が
  `QTimer.singleShot` で直列化しないこと。どちらも `setFixedSize`、再スタイルされた
  枠線、無効化されたレイアウトを残してはならない; `cleanup()` がすべて復元する。
- 長寿命の UI 行はスクロール可能に保つ — チップページはコンテンツを `QScrollArea`
  でラップし、小さなウィンドウで押しつぶされない。
- 新しいサブタブは `SamsungSubTabs` + `QStackedWidget` を再利用
  （`_build_chip_ops_section` 参照）。
- アクションボタンは `NoFocus`（粘着フォーカスリングなし）; checkable タブピルは
  アクティブ状態の `checked` スタイリングを保持。

---

## テスト

```bash
cargo test                      # Rust ユニットテスト（MTK stage mapping、SLA、PIT を含む）
.venv/bin/python -m pytest tests/   # Python スイート（現在 173 passed, 4 skipped）
```

テストスイートのレイアウト:

- `tests/test_frp_flow.py` — `Flow`/`Step` 実行 + 協調的キャンセル + デバイス単位 run-guard。
- `tests/test_mtk.py` — MediaTek ロジック（scatter, DA, boot-stage helper, BROM wait/crash-retry）。
- `tests/test_devices.py` — 安定デバイスキー、電話フィルタリング、ターゲット再解決、スコープ付きキャンセル。
- `tests/test_carrier_lock.py` — SIM ロック判定 + MTK パッチゲーティング + DA ディスカバリ。
- `tests/test_odin_safety.py` — tar.md5 検証、BL ゲート、odin4 フラグ交渉。
- `tests/test_pit.py` — Samsung PIT 解析。
- `tests/test_bridge_io.py`, `tests/test_fus.py` — ブリッジ I/O + Samsung ファームウェアダウンローダ。

Rust ロジックを追加する場合は同じファイルに `#[test]` モジュールを追加。フローを
追加する場合は、可能なら fake/offline コンテキストでフローを実行する pytest を追加。
新しいリゾルバは `key=None` を受け取る必要がある; 新しいテストは 1 台の電話を
仮定するのではなくマルチデバイスフィルタリングをカバーすべき
（`test_devices.py` 参照）。

---

## プルリクエストチェックリスト

- [ ] `cargo build --release` がパス。
- [ ] `cargo test` がパス（または実行不能の理由を記載）。
- [ ] `.venv/bin/python -m pytest tests/` がパス。
- [ ] 新規フロー: GUI から到達できるよう `JOBS`（job + mode）に配線。
- [ ] 新規リゾルバ: `key=None`（ambient scope）を受け取り、マルチデバイステストでカバー。
- [ ] 新規 Rust コマンド: `main.rs` の使用法テキスト + `bridge.py` ラッパーに追加。
- [ ] GUI 変更: テーマ色（中立 focus トークン！）、シグナルベース更新、スクロール安全レイアウト。
- [ ] シークレット / バイナリ / デバイス識別データを repo に追加していない。
- [ ] 能力を追加した場合は README の機能マトリクスを更新。

PR は的を絞ること。1 機能または 1 修正 per PR が理想; issue 番号を参照。

---

## プラットフォームサポート方針（移植前に読む）

**Linux が唯一サポートされるプラットフォームです。** 開発、ハードウェアテスト、
リリースは Linux を対象とします。Windows/macOS の issue はサポート外としてクローズ
します — 以下の形でコードとして届けば例外です。

**理由:** `odin4` は Linux 専用; Windows USB はモードごとのドライバ（Zadig /
QDLoader / Samsung）が必要でリモートデバッグ不可; macOS は要求がほぼないのに
署名/公証が必要。完全な根拠と反論のオープンな招待は README の
“Platform support” を参照。

**それでも移植する場合（受け入れられる形）:**

1. フローまたは GUI に `sys.platform` チェックを散らさない。
2. `open_file_manager()`, `detach_kernel_drivers(target)`,
   `usb_device_path(bus, addr)`, `needs_udev_setup()`,
   `kernel_module_loaded(name)` を持つ backend 関数を備えた
   `python/core/platform.py` を追加 — Linux は実装し、他は役立つメッセージ付きで
   `NotImplementedError` を送出。
3. 既存の Linux 専用 call site（`xdg-open`, `rmmod cdc_acm`,
   `/dev/bus/usb`, `lsmod`, udev docs）を、call-site グループ単位で 1 PR ずつ、それへ
   移行。
4. Windows/macOS の backend PR には: backend 実装、docs 更新、CI またはメンテナ検証済み
   手動テスト証拠を含むこと。コアチームは non-Linux テストハードウェアを所有しない —
   port PR は著者がそれを証明できるかどうかで成否が決まる。

**PySide6 vs PyQt6:** PySide6（LGPL、MIT 互換 — PyQt6 は GPLv3）への移行は
望まれるが GUI smoke-test カバレッジでブロックされている。着手する場合:
`pyqtSignal→Signal`, `pyqtProperty→Property`, `PyQt6.sip→shiboken6` を機械的に変換、
`tests/` の offscreen window/picker/guard smoke test を拡張し、動作を
pixel-identical に保つ。まず Discussions で議論。

## ロードマップとアイデア

貢献者が champion することを歓迎するアイデア:

- **Ports & packaging:** Flatpak / AppImage / AUR, CI マトリクス (Linux distros),
  `pip`/`cargo` リリースフロー。
- **MediaTek:** DA バリアント追加、scatter エッジケース、eMMC/UFS バックアップ
  ダンプ、`CHIP_NAMES` の新しい `hw_code` エントリ（引用ソース必須 — hex コードを
  推測しない）。
- **Qualcomm:** rawprogram/patch XML エッジケース、fh-loader コンボ、PID 追加。
- **Samsung:** SoC 別追加 HID download-mode ペイロード、Odin multi-partition UX
  ポリッシュ。
- **Multi-device:** デバイス別コンソールタブ / 進捗、デバイス別 STOP 粒度（STOP は
  現在ブロードキャスト）、exotic hub 用の `port_numbers` 相関。
- **New sections:** TEE/キーボード FRP、carrier（de-bloating）プロファイル、
  EDL-only ユーティリティ。
- **Community:** 翻訳、デバイス互換性 wiki、再現可能なファームウェアアーカイブ
  カタログ。
- **Safety:** dry-run モード、自動 pre-flash バックアップ、brick-recovery docs。

---

## コントリビューター

コード、docs、デバイス報告、テスト済みコンボ — 手伝った人は皆ここにリストされ祝われます。
PR を開いて自分を追加してください（username のアルファベット順、リンク 1 行）:

```md
- [@your-github](https://github.com/your-github) — what you did
```

このプロジェクトを本物にした最初のコントリビューターたち。次はあなた。

---

**質問?** discussion / issue を開いてください。Linux での自由でオープンなフラッシュ
ソフトウェア前進への助力に感謝します。🚀
