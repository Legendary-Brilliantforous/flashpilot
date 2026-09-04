# flashing/ — Device flashing engines
One folder per engine, model-aware.

```
flashing/
  samsung/   — Odin / PIT / sam_flash.rs (split of src/odin.rs 1960 lines) + vbmeta patch
  mediatek/  — MTK DA / scatter / GPT (src/mtk.rs 946, mtk_da.rs 1846, mtk_exploit.rs 824)
  qualcomm/  — QCOM Sahara/Firehose (src/qualcomm/{sahara,firehose,mbn,gpt,mod}.rs)
  unisoc/    — SPD FDL + PAC (src/spd.rs 2496, python/core/pac.py)
  pit/       — PIT intelligence (python/core/pit.py 636 lines, pitstore, odin4 verifier)
```
Big files will be split per-feature: sam_flash.rs -> samsung/{pit.rs, odin_session.rs, vbmeta.rs, flash.rs}
