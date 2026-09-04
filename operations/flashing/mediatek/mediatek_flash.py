"""MediaTek flashing — flash protocol .py under flashing (not FRP), includes MTK DA flashing.
Split from god frp.py — MTK flashing via DA (MT6765/Helio G85 etc), SP Flash, GPT, BROM.
FRP via MTK BROM lives in frp/mtk_frp/mtk_frp.py (BROM FRP erase, not flashing).
"""
from __future__ import annotations
try:
    from python.core.flows.brom import flow_mtk_download_info, flow_mtk_brom_info, flow_mtk_brom_backup, flow_mtk_combo_flash, flow_mtk_recovery_reset  # noqa: F401
    from python.core.flows.screenlock import flow_mtk_sp_flash, flow_mtk_meta_mode  # noqa: F401
    from python.core.mtk import detect_mtk  # noqa: F401
except ImportError:
    pass
