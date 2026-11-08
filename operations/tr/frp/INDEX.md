Language switcher: [English](../../frp/INDEX.md) · [Français](../../fr/frp/INDEX.md) · [Español](../../es/frp/INDEX.md) · [Deutsch](../../de/frp/INDEX.md) · [简体中文](../../zh/frp/INDEX.md) · [Русский](../../ru/frp/INDEX.md) · [Português](../../pt/frp/INDEX.md) · [日本語](../../ja/frp/INDEX.md) · [العربية](../../ar/frp/INDEX.md) · [हिन्दी](../../hi/frp/INDEX.md) · **Türkçe**

> English kanonik kaynaktır. Bu sayfa bir çeviridir; katkı memnuniyetle karşılanır — bkz. [`../../../docs/TRANSLATION.md`](../../../docs/TRANSLATION.md).

# operations/frp/ — Factory Reset Protection (yalnızca Android)

> Apple cihazlarda FRP yoktur (Apple bunun yerine Activation Lock / iCloud kullanır) —
> bkz. `operations/apple/`.

Bu dizin FRP aşma için **motor başına doküman ağaçları** barındırır.
Asıl kod `src/flows.rs` (Rust) içinde yaşar. Bir cihaz için gerçek bir
tarifin varsa (çip, FDL çifti, partition offset'leri vb.), kısa bir araştırma
notunu `devices/<brand>/<model>.md` içine bırakırsın. Bu dosyanın kökündeki
README, kod tabanındaki her FRP akışını nereye ait olduğuna ve neye
ihtiyaç duyduğuna haritalandırır.

## Motor haritası

| Motor | Ne zaman kullanılır | Kod | Bridge CLI |
|---|---|---|---|
| **Generic (ADB)** | USB debugging açık her telefonda ilk deneme | Rust akışları (`adb_frp`, `src/flows.rs` içindeki `frp_*` satırları) | `flow-run adb_frp` / `adb shell ...` (`bridge.adb_shell` üzerinden) |
| **MTK BROM** | MediaTek (Helio / Dimensity / MT6765) — kapat → Vol-/+ basılı tut → USB tak | Rust akışları (`src/flows.rs` içindeki `mtk_*` satırları) | `flow-run mtk_brom_info` (CLI: `mtk-detect`, `mtk-da-upload`, `mtk-frp`, `mtk-bypass`) |
| **MTK DA** | DA yüklemesini atlatan MTK BROM (lock-state çipler) | Rust akışları (`mtk_brom_backup`, `mtk_auth_flash`) | `flow-run mtk_brom_backup` |
| **Qualcomm EDL** | 9008 acil indirme (Snapdragon) | Rust akışları (`edl_*`, `qcom_*` satırları) | `flow-run edl_frp` (CLI: `qcom-*`) |
| **Samsung Exynos** | A14 (Exynos 850/1330), A15/A16 — Odin download mode yalnızca flashlamak içindir, FRP için DEĞİL | Rust `frp_*` satırları (Samsung hesap-aşma) | (çoğunlukla cihaz üzerinde, bridge yok) |
| **Samsung MTK (A05/A06)** | Helio G85'li A05/A06 — MTK BROM kullanır (yukarıda) | Rust akışları (`mtk_brom_info`, `mtk_brom_backup`) | `flow-run mtk_brom_backup` |
| **UNISOC/SPD** | 1782:4d00 FDL1+FDL2 (SC9863A, T606/UMS9230) | Rust akışları (`spd_*` satırları) + `src/spd.rs` | `flow-run spd_detect_info` (CLI: `spd-detect`, `spd-frp`, `spd-format`, `spd-magic-pack`) |
| **HiSilicon Kirin** | 12d1 — henüz açık akış yok (reverse-engineered değil) | (henüz yok) | (yok) |

(Eski `python/core/flows/*.py` motor modülleri hiçbir zaman gönderilmedi;
`mtk-brom-backup` akış satırı `mtk_brom_backup`'tır. Her anahtarı `flow-list`
ile doğrula.)

## Flow anahtarı → işlev haritası

GUI'nin FRP eylemlerinin çağırabileceği her akış. Anahtarlar Rust kayıt
satırlarıdır (`src/flows.rs`, doğrulama için `flow-list`); GUI (job, mode) ile
yönlendirir ve köprü `flow-run <key> [target]` ile çalıştırır.

| Flow anahtarı | Motor | Ne yapar |
|---|---|---|
| `adb_frp` | Generic ADB | `settings put secure frp 0` + kurulum sihirbazlarını devre dışı bırak + GMS verisini temizle |
| `frp_browser` | Generic ADB | On-device intent ile `chrome://settings/` aç |
| `frp_emergency` | Generic ADB | Acil arama çeviricisi ile Settings aç (on-device) |
| `frp_settings` | Generic ADB | Bildirim gölgesi yolundan Settings aç (on-device) |
| `frp_fake_login` (+`_testdpc`, `+_adp`) | Generic ADB | Bir device-owner DPC ile QR provision, sonra FRP temizle |
| `at_info` | Samsung MTP/AT | AT kanalından mod + devconinfo oku (Samsung pre-Android 8) |
| `at_method` | Samsung MTP/AT | Diag port üzerinden ADB etkinleştirmek için AT+DEBUGLVC |
| `download_frp` | Samsung Download mode | CSC/Combination firmware FRP kaldırma (PIT güvenlik sözleşmesi) |
| `odin_enable_adb` | Samsung Download mode | Odin tarball üzerinden download mode'dan ADB etkinleştir |
| `mtk_combo_flash` | MTK Download | Combination firmware flash (PIT + DA) |
| `mtk_recovery_reset` | MTK Download | Recovery-modunda fabrika sıfırlama |
| `mtk_brom_info` | MTK BROM | Çip id / handshake oku (her BROM flashından önce gerekli) |
| `mtk_brom_backup` | MTK BROM | BROM DA ile partition'ları dump et |
| `edl_frp` | Qualcomm EDL | Sahara + Firehose erase (05c6:9008) |
| `qcom_detect_info` | Qualcomm EDL | Algıla + bilgi (salt okunur) |
| `frp_qr_provision` | Generic ADB | QR provision (TestDPC yolu) |

(Emekli: eski `flow_*`-önekli anahtar adları ve `python/core/flows/*.py`
hiç gönderilmedi — anahtarlar `flow_` öneki taşımaz.)

## Yeni per-model bir tarif buraya nasıl iner

1. **Gerçek bir cihaz dump'u çalıştır** (ADB yolu için `scripts/dump-connected.sh`,
   Unisoc'ta BROM yolu için `flashpilot-bridge spd-format`). Dump
   `build/cache/dumps/<model>_<codename>/` içine gider.

2. **Dump'tan belirle:** motor + çip + FRP partition adı
   (Android 11+'da neredeyse her zaman `frp`, `frp_a` veya `userdata`).

3. **Cihaz girdisini ekle** `python/gui/supported_devices.json` içinde doğru
   marka altında, `actions: ["frp", "info", "backup", "flash"]` ve
   `status: "researched"` ile. (Mevcut motor-başına akış onu otomatik
   alır — yalnızca motorun kendisi eksikse yeni akış gerekir.)

4. **Kısa bir araştırma notu bırak** şu adreste:
   `operations/frp/devices/<brand>/<model>.md`, çip, motor, partition, build
   fingerprint ve tarifi onaylayan bir satır (örn. "mmcblk0p4 = frp, anlık
   BROM DA erase, combo gerekmez"). Format için
   `operations/frp/devices/nokia/nokia_g20.md` dosyasına bak.

5. **Eğer motorun kendisi bu chipset için bir akışa sahip değilse**, akışı
   `src/flows.rs` içinde kaydet (bir `flow!(...)` satırı) ve CLI dispatch'i
   `src/<engine>.rs` + `src/main.rs` içinde ekle.

## Per-chip dosyalar neden gitti

Önceki refactor'lar tanrı dosya `frp.py`'yi `operations/frp/chips/` altında
per-chip dosyalara ve `operations/frp/{mtk,qualcomm,unisoc,samsung}_frp/`
altında per-motor dosyalara böldü. Bu INDEX'in daha eski bir sürümü ölü
docstub'lardan ve bir `python/core/flows/brom.py` dispatch'ten bahsetti — o
modül hiçbir zaman gönderilmedi. Gerçek per-chip dispatch Rust akış takvimidir
(`src/flows.rs`: `mtk_*`/`qcom_*`/`spd_*` satırları, `flow-list` ile doğrula);
bu INDEX.md bir haritadır, böylece yeni bir dev motor-spesifik kodun gerçekte
nerede yaşadığını bilir.

## Per-motor Python shim'leri neden gitti

`operations/frp/mtk_frp/mtk_frp.py` (ve 4 kardeşi) `python.core.flows.brom`
içinden fonksiyon import edip bunları GUI'nin hiçbir zaman okumadığı **ikinci**
bir `FLOWS = {}` dict'i altında yeniden dışa aktardı. Bunlar kanonik
`python/core/flows/__init__.py` içindeki `FLOWS` ile çakışıyordu ve GUI onları
okusa gerçeklerin üzerini maskelerdi. Her motor klasöründeki bir README ile
değiştirildi; burada gerçek Python modüllerine işaret eder.
