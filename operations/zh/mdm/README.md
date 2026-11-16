Language switcher: [English](../../mdm/README.md) · [Français](../../fr/mdm/README.md) · [Español](../../es/mdm/README.md) · [Deutsch](../../de/mdm/README.md) · **简体中文** · [Русский](../../ru/mdm/README.md) · [Português](../../pt/mdm/README.md) · [日本語](../../ja/mdm/README.md) · [العربية](../../ar/mdm/README.md) · [हिन्दी](../../hi/mdm/README.md) · [Türkçe](../../tr/mdm/README.md)

> English is the canonical source. This page is a translation; help wanted — see [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# mdm/ — 移动设备管理 + KnoxGuard
MDM 解锁、KG/RMM、Knox 保修。

来源：Rust 流程（`src/flows.rs` 注册表、`flow-run` CLI）：`mdm_qr`、`mdm_diagnostics`、`mdm_unlock*`、`knox_check` / `knox_bypass`
Rust：`src/at.rs` 中的 AT+KSTRINGB / KGLOCK 路径
QR 生成器输出：`mdm_qr/`（仓库根目录）
（已退役：`python/core/knox.py`；`python/core/flows/mdm.py` 曾计划但从未交付——MDM 逻辑位于 Rust 流程中。）

结构：
```
mdm/
  devices/  — 除 apple 外的所有品牌（apple 的 MDM 位于 apple/mdm/）
    samsung/   — Samsung Knox MDM / KG（A 系列）
    tecno/ infinix/ itel/ xiaomi/ oppo/ realme/ oneplus/ vivo/ huawei/ motorola/ nokia/ tcl_zte/ lg/ asus_sharp
    ...        — frp/devices 的镜像，剔除 apple
```

将承载：mdm.py 拆分 + mdm_qr 生成。
注意：apple 的 MDM 位于顶层的 `apple/mdm/`，不在此处。
