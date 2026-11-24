# 変更履歴

Language switcher: [English](../../CHANGELOG.md) · [Français](../fr/CHANGELOG.md) · [Español](../es/CHANGELOG.md) · [Deutsch](../de/CHANGELOG.md) · [简体中文](../zh/CHANGELOG.md) · [Русский](../ru/CHANGELOG.md) · [Português](../pt/CHANGELOG.md) · **日本語** · [العربية](../ar/CHANGELOG.md) · [हिन्दी](../hi/CHANGELOG.md) · [Türkçe](../tr/CHANGELOG.md)

> English is the canonical source. This page is a translation; help wanted — see [`../TRANSLATION.md`](../TRANSLATION.md).

## 1.2.2（自動更新、10言語、Rockchip + モデムセーフなマルチデバイス）

*1.2.2 → 1.3.2 の開発サイクルノートを統合したもの — 1.2.1 以降にリリースされたすべての内容。*

### 自動更新と What's New（新機能）

- 更新の自動インストール：ダウンロードした `.deb` がバックグラウンドで sudo によりインストールされ、アプリが再起動し、初回起動時に 1 回限りの「何が追加・変更されたか」ウィンドウが新バージョンの changelog を表示します（Settings → Updates で自動インストールがオフの場合は、従来の手動 "Install Now" プロンプトがそのまま残ります）。

### 10言語 UI + リアルタイム言語切り替え（新機能）

- UI 全体が 10 の追加言語（Français、Español、Deutsch、简体中文、Русский、Português、日本語、العربية、हिन्दी、Türkçe）で提供されます：設定、デバイスタイル、ページ、コンソール文字列。
- UI 言語の切り替えは即時 — 再起動不要。レイアウトは実際のフォントメトリクスに合わせて調整されるため、長い翻訳でもコントロールを切り取らずに折り返します。
- キーベースの JSON 翻訳カタログにカバレッジ検証付き。CI はインストールされたカタログをスモークテストします。

### Rockchip + より賢い検出（新機能）

- 新しい Rockchip ブランドページ：fastboot モード経由で RK28xx–RK35xx ファミリーに対応。
- 検出はチップだけでなく、モデル・ブランド・フォームファクターを識別します。
- すべてのフラッシュ段階を捕捉（TFT パリティ）：MediaTek BROM/preloader/DA が全段階 PID セットと OEM VID（preloader VCOM 0x2000/0x2001 を含む）を網羅し、拡張された Qualcomm EDL download-PID ファミリー、SPD download-PID の和集合、そして固有のモードとして名付けられる Qualcomm HS-USB Diagnostics を扱います。
- モード badge は*選択された*デバイスに従い、OTHER の代わりに実際の USB プロトコル（ADB/MTP/PTP/DIAG/storage/RNDIS）を名付けます：low-level MediaTek ラベルを名乗るのはフラッシュ PID のみ、Qualcomm EDL は独自の badge chip を維持し、'MEDIATEK'/'download' 部分文字列のフォールスルーは修正済みです。

### Motorola FRP（新機能）

- CVE-2016-10277 fastboot FRP チェーン、own-DPC 偽ログイン QR プロビジョニング（TestDPC / Device Policy / Adobe）、フラッシュ + 再起動サイクルを伴う段階的 fastboot FRP、factory-bootmode ADB サイクル。

### 実エンジンパス（新機能）

- Rust コアに実 MTK/QCOM/Unisoc/Samsung のフラッシュ・FRP・ロックパス。
- odin4 は廃止：ネイティブ Rust Odin エンジンが tar パイプライン全体、PIT、既知の odin4 問題クラスすべてを処理します。Apple usbmuxd/lockdown は Rust へ移行。コアは Rust のみ（Python デバイス/プロトコルフォールバックは全廃）。

### モデムセーフ ADB（修正）

- poll/monitor/display パスは zero-touch（`adb-devices --no-probe`）：ループからの open/claim/handshake なし — USB モデムが毎サイクル再列挙するのを止めます（実測：MSM8916 モデムで 114 サイクルの静かな poll）。
- claim 争奪はラダーで委譲：ネイティブ → Rust サーバートランスポート（明示的 serial）→ ホストバイナリ → 救援 kill（最終手段）。システムサーバーがインターフェースを保持していても ADB op は成功します。
- USB-ADB マージ修正（行文字列を解析するため、行が実際に ADB 状態を持つ）、busy 保持者への救済 + 瞬時リトライ + 正直な busy 状態、babble/overflow ガード、claim テスト分離コマンド、現代的な adb CNXN 値、そして QCOM/MTK 角も兄弟分岐と同様に ADB オーバーレイを表示します。

### マルチデバイス信頼性（修正）

- settle-retry 付き pick：スキャンが再列挙中のデバイスを瞬時に取り逃したとき、すべてのツール runner は 2.5 秒後に一度リトライし、GUI が connected と表示しているのに "no device" で拒否することがなくなります。
- ADB AUTH は token ラウンドを通じて SHA-256 を維持します（奇数ラウンド SHA-256、偶数 SHA-1）。round-1 署名を失っても偽の "not authorized" に壁で塞がれなくなります。`_wait_for_adb` は瞬時のスキャン失敗に耐えます。
- ターゲットアイデンティティ束縛：再利用された bus:addr を占有する置換デバイスは拒否されます（zero-touch serial チェック）— トランスポートは別の電話を追跡しません。
- デバイスリスト切り替え：第二次スキャンがデバイスを落としたとき接続バーのリビルドがリトライし、デバイス切り替えが最初の電話へフォールバックしなくなり、USB pick が外れたとき ADB ツールは ADB daemon row にフォールバックします（"connected 表示なのに actions は no adb"）。
- デバイス分類 + 選択：不一致デバイスは誤った MTP ラベルではなく USB を報告し、外れた USB pick は拒否の代わりに daemon-row 選択を提示します（"Run on this device" / "Cancel"）。

### 正直な結果と GUI 磨き（修正）

- FRP フローは検証済みフラグと実際のシェル終了ステータスを要求します。非ゼロ bridge 終了はログ末尾付きで失敗を通知 — もう偽の "completed" toast はありません。
- GUI：行ごとのジョブ chip、ウィンドウ記憶、toast 上限、キーボードナビゲーション、デバイス認識 STOP（1 ジョブがそのデバイスをキャンセル）、kg_unlock をワーカースレッドへ移動（30 秒チェーンがウィンドウを凍結しなくなる）、splash が実際のビルドを追跡、延期ページはリトライ可能のまま、toast はトップバーをクリアします。

### セキュリティと堅牢性

- デフォルトでプライベートな出力、symlink 耐性のある一時名、symlink チェック。
- ファームウェアはデフォルトで書き込み後検証 + モデルゲート + 数値修正。
- FRP：DPC 署名証明書をネイティブに読み取り、provisioning チェックサムを修正。
- HIL ハードウェアテストハーネス：実ハードウェアでの multi-device / device-replacement / USB-storm 回帰。ADB モニターバックオフテストを決定論化。
- 公開ランディングページ（`website/`）：ケイパビリティマトリクスとプロトコルコンソール付き。

## 1.2.1（安定版リリース）

### マルチデバイスサポート（新機能）

- 複数の電話を接続可能：接続バーが各 телефонを列挙します（モデル · serial · トランスポート）；行をクリックして検査します。
- 一致が複数あるとき、各操作は適用先電話を尋ねます（0–1 件一致なら静か）。コンソール行は `[device-key]` タグを伴います。
- デバイスごとに 1 操作：異なる電話は並列にフラッシュ可能；同じ電話は依然直列化。グローバル STOP はすべての runner にブロードキャスト。
- 安定アイデンティティ（`python/core/devices.py`）：`adb:<serial>` → `usb:<port-path>` → 揮発フォールバック。セッションを開く前にターゲットを再解決するため、USB 再列挙でフラッシュが取り残されなくなります（`usb device Fail`）。
- 電話のみのデバイスリスト：ハブ、HID、ウェブカメラ、カードリーダーはフィルタされます。
- 新 `SPD` トランスポートモード + 読み取り専用 Qualcomm/SPD detect フロー。

### チップ別 EXPERIMENTAL（新機能）

- Samsung `Knox / Warranty`、Qualcomm `QCN / Modem`、チップ別 `IMEI Repair / Change`、`eMMC / UFS` —— 橙の折り畳みが所有チップページに（グローバル LAB ページなし）。毎実行の ownership チェックボックス；IMEI 変更はさらに `I UNDERSTAND` の入力必須。監査ログ記録；永続化された ack は自動では通りません（`check_gate_strict`）。

### MTK BROM（修正 + 改善）

- **PID/段階マッピングは mtkclient 慣例に修正**（`0e8d:0003`=BROM、`0e8d:2000`=preloader）が Rust、Python、GUI ラベル、ログ、docs を横断。
- 新 `mtk_crash_brom` bridge コマンド + `MTK crash preloader into BROM` フロー（MTK BROM 下に登録）。
- `_wait_mtk_brom_target()` は preloader 窓より安定保持 BROM を優先；DA 発見は切り詰められた（<1KB）バイナリを拒否。

### Odin / フラッシング（強化）

- `_prepare_download_session()`：kernel driver detach + 再列挙を跨ぐ 3× 握手リトライ；全 Odin PID を受け入れ；フラッシュ前 PIT キャッシュをウォーム。
- odin4 は `-d /dev/bus/usb/BBB/AAA` で固定 + USB ロス時の 1 回自動リトライ；`.tar.md5` トレーラーをファイル末尾にアンカー（ストリーミング、全 RAM 読み込みなし）。
- ネイティブスマートフラッシュがパーティション単位で MB/s + ETA をログ。

### 堅牢性強化（レビュー駆動）

- Sahara：HELLO コマンド/バージョン/モード/パケットサイズを解析時に検証（以前は：任意の ≥32 バイト blob が信頼）；transfer-format 自己検査は現在、構造体を round-trip（バイトを捨てるのではなく）；close 失敗をログ；detach は claim 前に実行；handshake は転送/close/reset 結果を JSON で報告（捨てるのではなく）— reset は明示的で可視。
- ADB auth：token ラウンド間の capped exponential backoff；1 回限りの keygen 一時停止を、止まったように見えるのではなく告知。
- MTK：設定された packet size が実際に DA セッションへ到達（以前は計算されて捨てられ、セッションは 64K ハードコード）、512B–1MB に clamp。
- 安全バックアップ：失敗時に経過時間と STOP ヒントを含む見落とせない banner を出力（契約は不変：操作を阻害しない）。
- 実験ゲート：iCloud + Pixel フローを厳格な毎実行 ack に移行；GUI ack トークンは feature ごとに計数し有効期限付き（クロス feature にじみなし、ack 損失なし、古い認可なし）。

### GUI 修正

- トップバーの赤ボーダー + ボタン縮小は、concurrent shake/rubber アニメーションと accent-tinted focus rings に追跡：アニメーションを `_anim_lock` でシリアライズ + 完全クリーンアップ；新しい中性 `focus_ring`/`sel_border` テーマ token（赤 accent が focus に漏れなくなる）。
- `os.system()` → `subprocess`（bridge rebuild / log-dir オープン用）。
- 重複した SPD "Enable ADB" スタブ、`fastboot_unlock` 実験誤ゲート、死 FUS→AP-slot パス、欠落 `finished` emit を修正。死 LAB/Knox/QCN/PAC 実験面を削除。

### 再構成

- `python/core/frp.py`（神ファイル）→ `python/core/core.py`（レジストリ + flows）；`frp.py` は現在 FRP のみ。死 `python/core/flows/` 分割を削除。

- 動詞先頭のジョブ名（`Remove FRP`、`Flash Firmware` など）；各 flow に 1 つの正規 snake_case key；表示名のキャスィングを normalize。

### ドキュメント

- 新スクリーンショット（`docs/samsung.png`、`mtk.png`、`spd.png`）、README の highlights/matrix/layout を書き換え、CONTRIBUTING のアーキテクチャ + flow ルール、本 changelog。

### boot.img + AVB（単一ネイティブエンジン）

- Rust bridge の新画像外科エンジン（`src/imgtools.rs`）：Android boot ヘッダー解析、cpio newc スキャン、prop パッチ（pad-in-place または magiskboot 風のヘッダー書き換えを伴う grow）、決定論的 gzip（mtime=0、level 9）、AVB vbmeta flags。`boot-info` / `boot-patch-adb` / `vbmeta-patch` CLI。
- Python `spd_adb` repack + `core._patch_vbmeta_flags` は委譲し、ローカルフォールバック付き（署名と戻り契約不変）。
- 等価作業で 2 つの真 bug を修正：grow splice が reader のアライメントと 2 バイトずれ（それ以降全エントリ破損 — 双方実装）、再パッチが毎回 `\n` で成長（双方は現在冪等）。gzip バイトは parity から意図的に除外（zlib 実装差）；解凍内容、サイズ、フィールドは一致。
- Rust unit test 6 件 + クロス実装 test 9 件。

### PAC（単一ネイティブエンジン + GUI actions 配線）

- Rust bridge の新 SPD PAC エンジン（`src/pac.rs`）：YGDP レイアウトで parse/extract/pack、共有 head/slot ビルダーは現在 `spd-readback` writer にも使用（バイト同一出力；その履歴的 doubled slot names は隔離され、伝播せず）。`pac-parse` / `pac-extract` / `pac-pack` CLI。
- Python `pac.*` は委譲し、ローカルフォールバック付き；新 `flow_pac_extract` / `flow_pac_pack`（ファイルのみ、ofp 風 env 入力）を FLOWS に登録し GUI dispatcher に対応付け — 以前は死んでいた PAC ボタンが現在 動作。
- 等価テストで 1 つの真 bug を検出・修正：ローカル packer は product string を静かにドロップ（slice-copy write）；加えて u32 overflow ガード、双エンジンでメッセージ identical。
- Rust unit test 5 件 + クロス実装 test 7 件（両方向 roundtrip、dir collision 含む sanitize parity、error mapping）。

### PIT（単一ネイティブエンジン）

- Rust bridge の新 Samsung PIT エンジン（`src/pit.rs`）：parse（28/132 レイアウト）、header/model 文字列、name normalization、find、overlap scan、forensic validation + health verdict —— 実 dump とエッジケース上で messages、summaries、verdicts がバイト identical（junk names の Python-`repr` parity を含む）。
- `pit-parse` / `pit-health` / `pit-find` / `pit-overlaps` / `pit-model` CLI；Python `pit.*` の raw-bytes パスは委譲し、バイナリ不在時はローカルフォールバック（契約保持：ValueError/None/never-raise）。
  in-memory object パスと表示 helper は local/fast のまま；共有ルールは 11 クロス実装等価 test で pin。
- Rust unit test 8 件（layouts ベクター、normalize テーブル、meta overlap 分類、summary/human-size 形態）。

### ADB（ネイティブトランスポート、platform-tools なし）

- Rust bridge の新 native ADB クライアント（`src/adb.rs`）：USB トランスポート（255/66/1）で kernel driver detach、CNXN handshake、RSA-SHA256/SHA-1 AUTH（`~/.android/adbkey` を再利用、欠落時は生成）、`shell:` と `sync:`（STAT/RECV/SEND）services。
- `adb-devices` は native スキャンから `adb devices -l` 行契約を維持（`device` / `unauthorized` / `no permissions`）；`adb-shell` は serial を受け取り（`-` = 最初の認可済み）、加えて serial-pinned の新 `adb-pull` / `adb-push`。
- Python：`bridge.adb_shell()` は explicit > ambient-scope > first authorized serial を解決（multi-device ADB は現在 ターゲット pin；`adb.py` は bridge へ委譲；EFS backup/restore の pull/push は bridge を通り、unpinned system `adb` 呼び出しではない。`has_adb()` は現在 "bridge built" を意味）。
- Rust test 6 件（framing、banner、PKCS#1 sign/verify、DER roundtrip、pubkey blob の system adb key とバイト相同）+ Python test 9 件。

### Fastboot（ネイティブトランスポート + Motorola universal）

- Rust bridge の新 native fastboot USB トランスポート（`src/fastboot.rs`）：`fastboot-devices`（JSON）+ `fastboot-cmd <vid:pid@bus:addr> <ms> <cmd…>`（getvar/oem/erase/reboot の command phase）、kernel driver detach 付き。
  デバイス側 FAIL は `FAILED (remote: …)` として exit 0 でレンダリングされ、system binary の transcript 形態に一致（Moto MBM bootloader で OKAY パケットに piggyback される lone `getvar` 値を含む）。
- 共有 Python helper（`_fastboot_run`、`_wait_fastboot`、`_fastboot_getvar`）は native-first + system-binary フォールバック；DATA phase コマンド（flash/boot/…）は常に system binary、ホスト側 `devices` 一覧は native detect 提供。全 fastboot トラフィックは現在 ターゲット pin（`vid:pid@bus:addr`）、no-`-s` 誤電話ハザードを閉じる。
- 新ブランド横断 Motorola フロー（`moto_frp_adb`、`moto_frp_fastboot`、`moto_oem_unlock_token`）：ADB provisioning reset、lock-state 読み + session resets を含む official unlock-token フロー、読み取り専用 token reader。Motorola → All Motorola / Lenovo（universal）および各 Moto モデル下に表示；unlock portal URL を修正（旧 `motorola.com/unlockbootloader` は死）。
- `python/core/fastboot.py`（Pixel）と `usb_watch.py`（lsusb scraping）を bridge へ移動；新 `tests/test_fastboot_native.py` test 7 件。