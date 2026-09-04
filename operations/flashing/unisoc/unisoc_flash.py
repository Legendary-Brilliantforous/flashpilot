"""UNISOC/SPD flashing — flash protocol .py under flashing (not FRP), includes FDL1/FDL2 PAC.
Split from god frp.py — SPD flashing via 1782:4d00 FDL, PAC.
FRP via SPD lives in frp/unisoc_frp/unisoc_frp.py (BROM FRP erase, not flashing).
"""
from __future__ import annotations
try:
    from python.core.pac import flow_pac_flash  # noqa: F401
    from python.core.spd_adb import enable_adb_via_boot_patch  # noqa: F401
except ImportError:
    pass
