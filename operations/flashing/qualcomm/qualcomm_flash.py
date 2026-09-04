"""Qualcomm flashing — flash protocol .py under flashing (not FRP), includes Firehose/Sahara.
Split from god frp.py — QCOM flashing via EDL (05c6:9008) Firehose, Sahara.
FRP via EDL lives in frp/qualcomm_frp/qualcomm_frp.py (EDL FRP erase, not flashing).
"""
from __future__ import annotations
try:
    from python.core.flows.frp import flow_qualcomm_edl_frp, flow_qualcomm_qfil_frp  # noqa: F401 (FRP, but flashing shares EDL transport)
    from python.core.qcn import flow_qcn_backup, flow_qcn_restore  # noqa: F401
except ImportError:
    pass
