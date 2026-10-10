# operations/frp/mtk_frp/
#
# MediaTek FRP engine — actual implementation lives in:
#   src/flows.rs registry  (mtk_download_info, mtk_brom_info,
#                           mtk_brom_backup, mtk_combo_flash,
#                           mtk_recovery_reset, mtk_crash_brom, mtk_verify,
#                           mtk_auth_flash — run via `flow-run <key>`)
#   src/mtk_da.rs          (DA protocol + carrier/SIM lock patch)
#   src/mtk_exploit.rs     (kamakiri2 + BROM auth bypass)
#   python/core/mtk.py     (USB helpers: find_mtk(), chip-id routing)
#   (retired) python/core/flows/{brom,screenlock,mdm}.py (never shipped)
#
# Bridge CLI (flashpilot-bridge):
#   mtk-detect / mtk-da-upload / mtk-frp / mtk-bypass / mtk-brom-exploit
#   (verify names with `flashpilot-bridge --help`; flows preferred)
#
# Per-chip DA/loader pairs (helio_g85, dimensity_8020, mt6765, etc.) are
# picked automatically by python/core/mtk.py based on the chip id reported
# by the BROM handshake. See src/mtk.rs.
#
# Add a per-model research note in operations/frp/devices/<brand>/ when you
# have a real FRP recipe (e.g. "mmcblk0p4 = frp, instant BROM DA erase").
