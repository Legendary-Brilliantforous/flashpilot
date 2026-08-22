"""FlashPilot flashing - Odin/Samsung firmware flashing.

Canonical location for all Odin/flashing flows. Previously these lived in
``frp.py`` (god-file). New code should::

    from .flashing import flow_odin_advanced_flash, flow_odin_flash_tar, ...

``frp.py`` re-exports the same symbols for backwards-compat but is
deprecated for flashing - it will be trimmed to FRP/lock-only in a
future release.

This module is currently a shim over ``frp`` to avoid a risky 2k-line
move in one commit. The next step is to move the implementations here
and make ``frp`` import from this module instead (requires extracting
shared helpers into ``flow.py``).
"""

# Re-export flashing symbols from the legacy location.
# Keep the list explicit so import cost stays low and linters see it.
from .frp import (  # noqa: F401
    ODIN4_SHA256,
    ODIN4_SHA256_MTK,
    ODIN4_SHA256S,
    flow_odin_enable_adb,
    flow_odin_flash_tar,
    flow_odin_check,
    flow_odin_list,
    flow_odin_advanced_flash,
    flow_odin_pit_tools,
    flow_odin_flash_partition_gui,
    flow_odin_vbmeta,
    flow_odin_flash_multi,
    flow_odin_send_pit,
    flow_efs_backup,
    flow_efs_restore,
    _find_odin4,
    _find_slot_tar,
    _run_odin4_streaming,
    _tar_md5_valid,
    _strip_odin4_md5_trailer,
    _enforce_flash_gates,
    _enforce_bl_downgrade_gate,
    _require_preflight,
    _require_recent_efs_backup,
)

__all__ = [
    "ODIN4_SHA256",
    "ODIN4_SHA256_MTK",
    "ODIN4_SHA256S",
    "flow_odin_enable_adb",
    "flow_odin_flash_tar",
    "flow_odin_check",
    "flow_odin_list",
    "flow_odin_advanced_flash",
    "flow_odin_pit_tools",
    "flow_odin_flash_partition_gui",
    "flow_odin_vbmeta",
    "flow_odin_flash_multi",
    "flow_odin_send_pit",
    "flow_efs_backup",
    "flow_efs_restore",
]
