"""Click-routing and risk metadata for rendered flow buttons.

Single source of truth for (a) what a flow button does when clicked and
(b) how risky that flow is. Both are derived ONLY from the existing metadata
in :mod:`python.gui.common` — ``_EXPERIMENTAL_FLOW_MAP`` (experimental
features behind a per-run ownership ack) and ``_DESTRUCTIVE_CONFIRM`` (flows
that wipe data / clear security state). No Qt import and no widget
construction happens here, so this module is importable and testable without
a ``QApplication``.

Risk levels and why they are honest
-----------------------------------
* ``"experimental"`` — the key is in ``_EXPERIMENTAL_FLOW_MAP``; the UI shows
  the amber EXPERIMENTAL overlay with a mandatory ownership checkbox every
  run.
* ``"high"`` — the key is in ``_DESTRUCTIVE_CONFIRM``. This is intentionally
  equivalent to *"the UI will actually ask for confirmation"*: a flow can
  never be badged ``high`` without a dialog, and a flow with a dialog can
  never be badged anything less.
* ``"read"`` — the flow belongs to a read-only job
  (:data:`READ_ONLY_JOBS`) and is neither of the above; it only reads state
  off the device.
* ``"medium"`` — everything else, including unknown keys and unknown jobs.
  Unknown input therefore FAILS CLOSED to ``medium``, never to ``read``.

Precedence
----------
Experimental always wins over confirm (see :func:`route_for` / :func:`risk_for`).
``tests/test_flow_routing_contract.py`` asserts the two maps stay disjoint so
the precedence is unambiguous.
"""
from .common import _DESTRUCTIVE_CONFIRM, _EXPERIMENTAL_FLOW_MAP

# Jobs whose flows only read state off the device — never write, wipe or
# change security state. Any new read-only job must be added here explicitly,
# otherwise its flows fail closed to "medium".
READ_ONLY_JOBS = frozenset({"Read Device Info", "Detect Devices"})

__all__ = ["READ_ONLY_JOBS", "route_for", "risk_for"]


def route_for(flow_key):
    """How a click on ``flow_key``'s button must be routed.

    Returns ``"experimental"`` (EXPERIMENTAL ownership overlay),
    ``"confirm"`` (destructive confirm dialog) or ``"direct"`` (run now).
    Experimental wins over confirm.
    """
    if flow_key in _EXPERIMENTAL_FLOW_MAP:
        return "experimental"
    if flow_key in _DESTRUCTIVE_CONFIRM:
        return "confirm"
    return "direct"


def risk_for(flow_key, job=None):
    """Risk level of ``flow_key`` (``job`` disambiguates the read-only case).

    Returns one of ``"read"``, ``"medium"``, ``"high"`` or
    ``"experimental"``. See the module docstring for the exact rules; unknown
    keys/jobs fail closed to ``"medium"``.
    """
    if flow_key in _EXPERIMENTAL_FLOW_MAP:
        return "experimental"
    if flow_key in _DESTRUCTIVE_CONFIRM:
        return "high"
    if job in READ_ONLY_JOBS:
        return "read"
    return "medium"
