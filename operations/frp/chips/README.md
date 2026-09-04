# operations/frp/chips/
#
# Per-chip FRP handlers LIVE in the engine modules, not here.
# This directory exists so the FRP tree has a place to land
# chip-specific notes / research dumps, but the Python dispatch
# is in:
#
#   MediaTek (Helio / Dimensity / MT6765 / etc.)  →  python/core/flows/brom.py
#   Qualcomm (Snapdragon / SD 695 / SD 8 Gen1)   →  python/core/flows/frp.py
#   Samsung Exynos (850 / 1330)                   →  python/core/flows/oem_odin.py
#   UNISOC / Spreadtrum (SC9863A / T606 / UMS9230) →  python/core/flows/brom.py
#   HiSilicon (Kirin 710)                          →  no flow yet (HW not reverse-engineered)
#
# For a per-device lookup (model → chip → engine → action), see
# operations/frp/INDEX.md and python/gui/supported_devices.json.
#
# To add a chip-specific recipe:
#   1. Add the chip entry to supported_devices.json (chip + engine)
#   2. If the engine needs a new flow, register it in the appropriate
#      python/core/flows/<engine>.py file under FLOWS['flow_xxx']
#   3. Drop a research note here only if the device needs a manual
#      workaround that the generic flow doesn't cover (offset, timing,
#      pinout). Keep it short and link to the flow.
