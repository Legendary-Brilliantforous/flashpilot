Language switcher: [English](../../mdm/README.md) · [Français](../../fr/mdm/README.md) · [Español](../../es/mdm/README.md) · [Deutsch](../../de/mdm/README.md) · [简体中文](../../zh/mdm/README.md) · [Русский](../../ru/mdm/README.md) · [Português](../../pt/mdm/README.md) · **日本語** · [العربية](../../ar/mdm/README.md) · [हिन्दी](../../hi/mdm/README.md) · [Türkçe](../../tr/mdm/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# mdm/ — Mobile Device Management + KnoxGuard

MDM アンロック、KG/RMM、Knox 保証。

ソース: Rust フロー（`src/flows.rs` レジストリ、`flow-run` CLI）: `mdm_qr`、`mdm_diagnostics`、`mdm_unlock*`、`knox_check` / `knox_bypass`
Rust: `src/at.rs` の AT+KSTRINGB / KGLOCK パス
QR ジェネレータ出力: `mdm_qr/`（リポジトリルート）
（引退済み: `python/core/knox.py`。`python/core/flows/mdm.py` は計画されたが公開されることはなかった — MDM ロジックは Rust フローに存在します。）

構造:
```
mdm/
  devices/  — apple 以外の全ブランド（apple の MDM は apple/mdm/ 配下）
    samsung/   — Samsung Knox MDM / KG（A シリーズ）
    tecno/ infinix/ itel/ xiaomi/ oppo/ realme/ oneplus/ vivo/ huawei/ motorola/ nokia/ tcl_zte/ lg/ asus_sharp
    ...        — frp/devices から apple を除いたミラー
```

ホスト予定: mdm.py の分割 + mdm_qr 生成。
注意: apple の MDM はトップレベルの `apple/mdm/` にあり、ここではありません。
