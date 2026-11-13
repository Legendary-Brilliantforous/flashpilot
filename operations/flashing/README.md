# flashing/ — Device flashing engines
One folder per engine, model-aware.

```
flashing/
  samsung/   — Odin / PIT / sam_flash.rs (split of src/odin.rs 1960 lines) + vbmeta patch
  mediatek/  — MTK DA / scatter / GPT (src/mtk.rs 946, mtk_da.rs 1846, mtk_exploit.rs 824)
  qualcomm/  — QCOM Sahara/Firehose (src/qualcomm/{sahara,firehose,mbn,gpt,mod}.rs)
  unisoc/    — SPD FDL + PAC (src/spd.rs 2496, `pac_extract`/`pac_pack` + `ofp_extract` rows in `src/flows.rs`; the old `python/core/pac.py` was retired with the Python engine)
  pit/       — PIT intelligence (python/core/pit.py 636 lines, pitstore, odin4 verifier)
```
Big files will be split per-feature: sam_flash.rs -> samsung/{pit.rs, odin_session.rs, vbmeta.rs, flash.rs}

Per-engine capability registers (commands, prerequisites, device-page
wiring, open gaps) live in `../device_research/feature_logic_matrix.md`;
the MTK per-SoC tables are in `../device_research/mtk_chip_matrix.md`.

Bundled payloads: `payloads/mtk` (mtkclient DA/payloads, GPLv3) and
`payloads/qcom` (firehose programmers + SoC index). Unisoc FDL1/FDL2 are
read out of the PAC, so no loader store is shipped.
