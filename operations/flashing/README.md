# flashing/ — Cihaz yazma (flashing) motorları
Motor başına bir klasör, model farkındalığı.

```
flashing/
  samsung/   — Odin / PIT / sam_flash.rs (src/odin.rs 1960 satırının bölünmüş hali) + vbmeta yamalama
  mediatek/  — MTK DA / scatter / GPT (src/mtk.rs 946, mtk_da.rs 1846, mtk_exploit.rs 824)
  qualcomm/  — QCOM Sahara/Firehose (src/qualcomm/{sahara,firehose,mbn,gpt,mod}.rs)
  unisoc/    — SPD FDL + PAC (src/spd.rs 2496, `pac_extract`/`pac_pack` + `ofp_extract` satırları `src/flows.rs`; eski `python/core/pac.py` Python motoru ile birlikte emekliye ayrıldı)
  pit/       — PIT zekâsı (python/core/pit.py 636 satır, pitstore, odin4 doğrulayıcı)
```
Büyük dosyalar özellik bazında bölünecek: sam_flash.rs -> samsung/{pit.rs, odin_session.rs, vbmeta.rs, flash.rs}

Motor bazlı yetenek kayıtları (komutlar, ön koşullar, cihaz sayfası
bağlantıları, açık boşluklar) `../device_research/feature_logic_matrix.md` içinde yaşar;
MTK SoC bazlı tablolar `../device_research/mtk_chip_matrix.md` içinde.

Dahil edilen yükler: `payloads/mtk` (mtkclient DA/payloadler, GPLv3) ve
`payloads/qcom` (firehose programcıları + SoC dizini). Unisoc FDL1/FDL2 PAC içinden okunur, bu nedenle yükleyici deposu teslim edilmez.
