# operations/frp/chips/
#
# Per-chip FRP handlers LIVE in the Rust engine, not here.
# This directory exists so the FRP tree has a place to land
# chip-specific notes / research dumps; dispatch is per-flow:
#
#   MediaTek (Helio / Dimensity / MT6765 / etc.)  →  `mtk_*` rows in src/flows.rs
#   Qualcomm (Snapdragon / SD 695 / SD 8 Gen1)   →  `edl_*` / `qcom_*` rows in src/flows.rs
#   Samsung Exynos (850 / 1330)                   →  Odin flashing only (no FRP erase path)
#   UNISOC / Spreadtrum (SC9863A / T606 / UMS9230) →  `spd_*` rows in src/flows.rs
#   HiSilicon (Kirin 710)                          →  no flow yet (HW not reverse-engineered)
#
# (Retired: `python/core/flows/{brom,frp,oem_odin}.py` never shipped.)
#
# For a per-device lookup (model → chip → engine → action), see
# operations/frp/INDEX.md and python/gui/supported_devices.json.
#
# To add a chip-specific recipe:
#   1. Add the chip entry to supported_devices.json (chip + engine)
#   2. If the engine needs a new flow, register it in src/flows.rs
#      and verify with `flashpilot-bridge flow-list`
#   3. Drop a research note here only if the device needs a manual
#      workaround that the generic flow doesn't cover (offset, timing,
#      pinout). Keep it short and link to the flow.
