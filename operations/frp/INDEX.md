# operations/frp/ — Fabrika Reset Koruması (Yalnızca Android)

> Apple cihazlarında FRP yoktur (Apple Activation Lock / iCloud kullanır) —
> bakınız `operations/apple/`.

Bu dizin, FRP atlatma için **motor bazlı belge ağaçlarını** içerir.
Asıl kod `src/flows.rs` (Rust) içinde yer alır. Gerçek bir cihaz için
bir tarifiniz olduğunda (çip, FDL çifti, bölüm ofsetleri vb.) `devices/<brand>/<model>.md`
 içinde kısa bir araştırma notu bırakın. Bu kök README, kod tabanındaki her FRP akışının
nerede yaşadığını ve neye ihtiyaç duyduğunu haritalar.

## Motor haritası

| Motor | Ne zaman kullanılır | Kod | Bridge CLI |
|---|---|---|---|
| **Genel (ADB)** | USB hata ayıklama açık olan herhangi bir telefonda ilk deneme | Rust akışları (`adb_frp`, `src/flows.rs` içindeki `frp_*` satırları) | `flow-run adb_frp` / `bridge.adb_shell` üzerinden `adb shell ...` |
| **MTK BROM** | MediaTek (Helio / Dimensity / MT6765) — kapat → Ses-/+ basılı tut → USB tak | Rust akışları (`src/flows.rs` içindeki `mtk_*` satırları) | `flow-run mtk_brom_info` (CLI: `mtk-detect`, `mtk-da-upload`, `mtk-frp`, `mtk-bypass`) |
| **MTK DA** | DA yüklemesini atlatmayı başaran MTK BROM (kilit durumu çipleri) | Rust akışları (`mtk_brom_backup`, `mtk_auth_flash`) | `flow-run mtk_brom_backup` |
| **Qualcomm EDL** | 9008 acil indirme (Snapdragon) | Rust akışları (`edl_*`, `qcom_*` satırları) | `flow-run edl_frp` (CLI: `qcom-*`) |
| **Samsung Exynos** | A14 (Exynos 850/1330), A15/A16 — Odin indirme modu yalnızca flaşlama içindir, FRP için DEĞİL | Rust `frp_*` satırları (Samsung hesap-atlatma) | (çoğunlukla cihaz üzerinde, bridge yok) |
| **Samsung MTK (A05/A06)** | Helio G85 içeren A05/A06 — yukarıdaki MTK BROM kullanır | Rust akışları (`mtk_brom_info`, `mtk_brom_backup`) | `flow-run mtk_brom_backup` |
| **UNISOC/SPD** | 1782:4d00 FDL1+FDL2 (SC9863A, T606/UMS9230) | Rust akışları (`spd_*` satırları) + `src/spd.rs` | `flow-run spd_detect_info` (CLI: `spd-detect`, `spd-frp`, `spd-format`, `spd-magic-pack`) |
| **HiSilicon Kirin** | 12d1 — açık akış yok (tersine mühendislik yapılmadı) | (henüz yok) | (yok) |

(Eski `python/core/flows/*.py` motor modülleri hiç piyasaya sürülmedi; `mtk-brom-backup`
`mtk_brom_backup` akış satırının karşılığıdır. Herhangi bir anahtar `flow-list` ile doğrulayın.)

## Akış anahtarı → işlev haritası

GUI'nin FRP eylemleri tarafından çağrılabilen her akış. Anahtarlar Rust kayıt satırlarıdır
(`src/flows.rs`, doğrulamak için `flow-list`); GUI bunları
(job, mode) ile yönlendirir ve bridge bunları `flow-run <key> [target]` ile çalıştırır.

| Akış anahtarı | Motor | Ne yapar |
|---|---|---|
| `adb_frp` | Genel ADB | `settings put secure frp 0` + kurulum sihirbazlarını devre dışı bırak + GMS verilerini temizle |
| `frp_browser` | Genel ADB | Cihaz üzerinde `chrome://settings/` adresini intent ile aç |
| `frp_emergency` | Genel ADB | Acil arama çeviricisi üzerinden Ayarlar'ı aç (cihaz üzerinde) |
| `frp_settings` | Genel ADB | Bildirim gölgesi yolu üzerinden Ayarlar'ı aç (cihaz üzerinde) |
| `frp_fake_login` (+`_testdpc`, `+_adp`) | Genel ADB | QR sağlama ile cihaz sahibi DPC, ardından FRP temizleme |
| `at_info` | Samsung MTP/AT | AT kanalı üzerinden mod + devconinfo oku (Samsung Android 8 öncesi) |
| `at_method` | Samsung MTP/AT | diag port üzerinden ADB'yi etkinleştirmek için AT+DEBUGLVC |
| `download_frp` | Samsung Download modu | CSC/Bileşim yazılımı FRP kaldırma (PIT güvenlik sözleşmesi) |
| `odin_enable_adb` | Samsung Download modu | Odin tarbalı indirme modundan ADB'yi etkinleştir |
| `mtk_combo_flash` | MTK Download | Bileşim yazılımı flaşı (PIT + DA) |
| `mtk_recovery_reset` | MTK Download | Kurtarma modunda fabrika sıfırlama |
| `mtk_brom_info` | MTK BROM | Çip kimliği / el sıkışma oku (herhangi bir BROM flaşından önce gerekir) |
| `mtk_brom_backup` | MTK BROM | BROM DA ile bölümleri dök |
| `edl_frp` | Qualcomm EDL | Sahara + Firehose silme (05c6:9008) |
| `qcom_detect_info` | Qualcomm EDL | Tespit + bilgi (salt okunur) |
| `frp_qr_provision` | Genel ADB | QR sağlama (TestDPC yolu) |

(Kaldırılmış: eski `flow_*` ön ekli anahtar adları ve
`python/core/flows/*.py` hiç piyasaya sürülmedi — anahtarların `flow_` öneki yoktur.)

## Yeni bir model bazlı tarifin buraya gelme şekli

1. **Gerçek bir cihaz dökümü çalıştırın** (`scripts/dump-connected.sh` dosyasını ADB tarafı yolu için görün, veya Unisoc üzerinde BROM tarafı için `flashpilot-bridge spd-format` kullanın). Döküm `build/cache/dumps/<model>_<codename>/` içine gider.

2. **Dökümden motoru, çipi ve FRP bölüm adını belirleyin** (neredeyse her zaman Android 11+ üzerinde `frp`, `frp_a` veya `userdata`).

3. **Cihaz girişini ekleyin** `python/gui/supported_devices.json` içinde doğru markaya göre, `actions: ["frp", "info", "backup", "flash"]` ve `status: "researched"` ile. (Mevcut motor bazlı akış otomatik olarak alınır — motorun kendisi eksik değilse yeni akış gerekmez.)

4. **Kısa bir araştırma notu bırakın** `operations/frp/devices/<brand>/<model>.md` içinde
çip, motor, bölüm, derleme parmak izi ve tarife onay veren tek satırlık açıklama ile (ör. "mmcblk0p4 = frp, anında BROM DA silme, combo gerekmez"). Biçim için `operations/frp/devices/nokia/nokia_g20.md` dosyasına bakın.

5. **Motorun kendisinde akış yoksa** bu çipset için akışı `src/flows.rs` içinde kaydedin (`flow!(...)` satırı) ve CLI dağıtımını `src/<engine>.rs` + `src/main.rs` içine ekleyin.

## Çip bazlı dosyalar neden kayboldu

Daha önceki yeniden düzenlemeler gökçe `frp.py` dosyasını `operations/frp/chips/` altındaki çip bazlı dosyalara ve `operations/frp/{mtk,qualcomm,unisoc,samsung}_frp/` altındaki motor bazlı dosyalara böldü. Bu INDEX'in eski sürümünde ölü docsutları ve `python/core/flows/brom.py` dağıtımı iddia edilmişti — bu modül asla piyasaya sürülmedi. Gerçek çip bazlı dağıtım Rust akış kayıt defteridir (`src/flows.rs`: `mtk_*`/`qcom_*`/`spd_*` satırları, doğrulama için `flow-list`); bu INDEX.md yeni geliştiricinin hangi motor bazlı kodun gerçekten yaşam alanı olduğunu bilmesi için haritadır.

## Motor bazlı Python şimlerinin neden kayboldu

`operations/frp/mtk_frp/mtk_frp.py` (ve 4 kardeşi) `python.core.flows.brom` içinden işlevler içe aktarıp bunları **ikinci** bir `FLOWS = {}` sözlüğü altında yeniden dışa aktarıyordu. GUI bunları asla okumuyordu. Canonical `FLOWS` ile çakıştı ve GUI bunları okusaydı gerçek olanları maskeleyebilirdi. Her motor klasöründe gerçek Python modüllerine işaret eden bir README ile değiştirildi.
