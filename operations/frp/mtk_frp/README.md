# operations/frp/mtk_frp/
#
# MediaTek FRP engine — actual implementation lives in:
#   python/core/flows/brom.py       (DA upload, BROM/DA backup, GPT-based frp wipe)
#   python/core/flows/screenlock.py (MTK sp_flash + meta_mode for combo screens)
#   src/mtk_da.rs                   (DA protocol + carrier/SIM lock patch)
#   src/mtk_exploit.rs              (kamakiri2 + BROM auth bypass)
#
# Flow keys registered in python/core/flows/{brom,screenlock,mdm}.py:
#   flow_mtk_download_info  flow_mtk_brom_info  flow_mtk_brom_backup
#   flow_mtk_combo_flash    flow_mtk_recovery_reset
#   flow_mtk_sp_flash       flow_mtk_meta_mode
#   flow_mtk_frp            (thin wrapper that chains mtk-frp-gpt)
#
# Per-chip DA/loader pairs (helio_g85, dimensity_8020, mt6765, etc.) are
# picked automatically by python/core/mtk.py based on the chip id reported
# by the BROM handshake. See src/mtk.rs.
#
# Add a per-model research note in operations/frp/devices/<brand>/ when you
# have a real FRP recipe (e.g. "mmcblk0p4 = frp, instant BROM DA erase").
