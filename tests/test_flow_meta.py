"""`python.gui.flow_meta`: risk levels + click routing derived from the maps.

Pure/PyQt-light: importing :mod:`python.gui.flow_meta` pulls in
``python.gui.common`` (plain dicts) but needs no ``QApplication`` and builds
no widgets.
"""
from python.core import core
from python.gui import flow_meta
from python.gui.common import _DESTRUCTIVE_CONFIRM, _EXPERIMENTAL_FLOW_MAP

LEVELS = {"read", "medium", "high", "experimental"}

# The complete job inventory at this slice. A NEW Rust job MUST be added here
# (and reviewed for read-only-ness / risk) rather than silently defaulting to
# "medium" through `risk_for`.
KNOWN_JOBS = frozenset({
    "Flash Firmware",
    "Remove FRP",
    "Remove Screen Lock",
    "Read Device Info",
    "Detect Devices",
    "Reboot",
    "Repair Settings",
    "Unlock Carrier",
    "Remove MDM",
    "Knox / Warranty",
    "QCN / Modem",
    "IMEI Repair / Change",
    "eMMC / UFS",
})


def test_read_only_jobs_are_explicit():
    assert flow_meta.READ_ONLY_JOBS == frozenset({"Read Device Info",
                                                  "Detect Devices"})


def test_every_core_job_is_explicitly_classified():
    """A new job (e.g. a new Rust flow-list job) must fail this test."""
    assert frozenset(core.JOBS) == KNOWN_JOBS


def test_every_registered_flow_has_a_level():
    for key in core.FLOWS:
        assert flow_meta.risk_for(key) in LEVELS, key


def test_experimental_keys_are_experimental():
    for key in _EXPERIMENTAL_FLOW_MAP:
        assert flow_meta.risk_for(key) == "experimental", key


def test_destructive_keys_are_high():
    for key in _DESTRUCTIVE_CONFIRM:
        assert flow_meta.risk_for(key) == "high", key


def test_unknown_job_and_key_fail_closed_to_medium():
    assert flow_meta.risk_for("__nope__") == "medium"
    assert flow_meta.risk_for("__nope__", job="__nojob__") == "medium"
    # A real flow under an unknown job is medium, not read.
    assert flow_meta.risk_for("adb_info", job="__nojob__") == "medium"


def test_experimental_beats_confirm():
    """Precedence guard: a key in BOTH maps is still experimental."""
    key = "adb_info"  # any key; we only exercise the precedence ordering
    saved_exp = _EXPERIMENTAL_FLOW_MAP.get(key)
    saved_conf = _DESTRUCTIVE_CONFIRM.get(key)
    _EXPERIMENTAL_FLOW_MAP[key] = "knox_warranty"
    _DESTRUCTIVE_CONFIRM[key] = ("T", "B")
    try:
        assert flow_meta.route_for(key) == "experimental"
        assert flow_meta.risk_for(key, job="Remove FRP") == "experimental"
    finally:
        if saved_exp is None:
            _EXPERIMENTAL_FLOW_MAP.pop(key, None)
        else:
            _EXPERIMENTAL_FLOW_MAP[key] = saved_exp
        if saved_conf is None:
            _DESTRUCTIVE_CONFIRM.pop(key, None)
        else:
            _DESTRUCTIVE_CONFIRM[key] = saved_conf


def test_route_for_agrees_with_the_maps():
    for key in core.FLOWS:
        want = ("experimental" if key in _EXPERIMENTAL_FLOW_MAP
                else "confirm" if key in _DESTRUCTIVE_CONFIRM
                else "direct")
        assert flow_meta.route_for(key) == want, key


def test_every_job_is_covered_when_passed_as_job():
    """Passing each core job must yield a valid level for each of its flows."""
    for job in core.JOBS:
        for mode in core.modes_for(job):
            for key in core.methods_for(job, mode):
                assert flow_meta.risk_for(key, job) in LEVELS, (job, mode, key)


def test_no_lies_high_implies_confirm_and_read_implies_read_only_job():
    for job in core.JOBS:
        for mode in core.modes_for(job):
            for key in core.methods_for(job, mode):
                level = flow_meta.risk_for(key, job)
                if level == "high":
                    assert key in _DESTRUCTIVE_CONFIRM, key
                elif level == "experimental":
                    assert key in _EXPERIMENTAL_FLOW_MAP, key
                elif level == "read":
                    assert job in flow_meta.READ_ONLY_JOBS, (job, key)


def test_read_only_job_flows_are_read_unless_high_or_experimental():
    for job in flow_meta.READ_ONLY_JOBS:
        for mode in core.modes_for(job):
            for key in core.methods_for(job, mode):
                if key in _DESTRUCTIVE_CONFIRM or key in _EXPERIMENTAL_FLOW_MAP:
                    continue
                assert flow_meta.risk_for(key, job) == "read", key
