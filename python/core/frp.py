"""FRP (Factory Reset Protection) operations — this module is FRP-only.

Historically ``frp.py`` was a "god file" that held every flow in the app.
That is now fixed:

  * ``python/core/core.py``  — the canonical registry (FLOWS/JOBS/MODES) and
    every cross-cutting helper the GUI and tests consume.
  * ``python/core/frp.py``   — *this* module: FRP-removal flows only.

Import FRP flows from here:

    from python.core.frp import flow_adb_frp, flow_download_mode_frp

The FRP flows are implemented in ``python.core.core``; this module re-exports
only the FRP surface so its name maps 1:1 to its responsibility.
"""

from __future__ import annotations

from .core import (  # noqa: F401  re-export FRP flows
    flow_frp_clear_adb,
    flow_adb_frp,
    flow_frp_browser,
    flow_frp_emergency,
    flow_frp_settings,
    flow_universal_frp_bypass,
    flow_qualcomm_edl_frp,
    flow_qualcomm_qfil_frp,
    flow_download_mode_frp,
    flow_samsung_emergency_call,
    flow_samsung_talkback,
    flow_samsung_account_bypass,
)

# Re-export the flow primitives FRP callers historically pulled from `frp`.
from .flow import (  # noqa: F401
    Flow,
    Step,
    FlowCancelled,
    request_cancel,
    clear_cancel,
    cancel_requested,
)

# The ADB FRP command sequence (shared constant used by several FRP flows).
from .core import _ADB_FRP_STEPS  # noqa: F401
from .core import _wait_for_adb  # noqa: F401  # re-exported helper

__all__ = [
    "flow_frp_clear_adb",
    "flow_adb_frp",
    "flow_frp_browser",
    "flow_frp_emergency",
    "flow_frp_settings",
    "flow_universal_frp_bypass",
    "flow_qualcomm_edl_frp",
    "flow_qualcomm_qfil_frp",
    "flow_download_mode_frp",
    "flow_samsung_emergency_call",
    "flow_samsung_talkback",
    "flow_samsung_account_bypass",
    "Flow",
    "Step",
    "FlowCancelled",
    "request_cancel",
    "clear_cancel",
    "cancel_requested",
    "_ADB_FRP_STEPS",
    "_wait_for_adb",
]