"""Devices-page (Unisoc/SPD) board actions run from a single PAC file.

Regression contract for `FlashPilotWindow.start_model_action` on Unisoc
models. The actions used to dead-end on "Load this model's FDL1/FDL2 binaries
on the SPD tab (they are model-specific) then press the action again." Now
`spd-flash-pac <target> <pac> [--mode ...]` carries everything: the PAC embeds
the model's FDL1/FDL2 plus load addresses.

Routing pinned here (all for the SELECTED device, never "the first device"):
* screen lock: ADB `screen_lock_locksettings` when the picked phone is
  authorized, else PAC `--mode erase`;
* FRP: ADB `adb_frp` first; else configured FDL1/FDL2 keep `spd-frp`;
  else PAC `--mode frp`;
* backup: folder picker first; FDL1 configured keeps `spd-backup`; else PAC
  `--mode backup --out <dir>`, path reported only after the run completes;
* flash: `.pac` picker + overwrite warning -> PAC `--mode flash`, and the SPD
  workbench is never opened;
* info: unchanged generic identity refresh.

The routing sinks are replaced with recorders, so these tests assert the
exact argv, the confirmation gate and the device scope without touching USB,
BROM or a real phone.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from python.gui import qt_app

KEY = "usb:1782:4d00:1-1.3"
META = {"engine": "spd", "model": "Spark 8", "vid": "1782"}
BRAND = "Tecno"
LABEL = "Tecno Spark 8"
PAC = "/firmware/Tecno_Spark8.pac"
OUT = "/tmp/spd_backup_run"
FDL1 = "/firmware/fdl1-sign.bin"
FDL2 = "/firmware/fdl2-sign.bin"
TGT = "1-1.3"


class _Rec:
    def __init__(self):
        self.runs = []          # (argv, kwargs) from _spd_run
        self.flows = []         # universal ADB flows
        self.sections = []      # workbench navigation
        self.flash_routes = []  # _route_model_flash
        self.confirms = []      # (title, text, confirm_label, chip)
        self.toasts = []        # (kind, title, detail)
        self.picks = []         # QFileDialog calls
        self.lines = []
        self.adb = False
        self.confirm_ok = True
        self.pick_file = ""
        self.pick_dir = ""
        self.detected = 0
        self.refreshed = 0
        self.target_resolves = 0


@pytest.fixture(scope="module")
def win(test_window):
    """One real window for the module (construction is the slow part)."""
    return test_window()


@pytest.fixture(autouse=True)
def _clean_spd_tab(win):
    """Blank FDL fields before/after each test (the window is module-scoped)."""
    for name in ("fdl1", "fdl2"):
        win.spd_files[name].setText("")
    win.spd_fdl1_addr.setText("0x40004000")
    win.spd_fdl2_addr.setText("0x14000000")
    yield
    for name in ("fdl1", "fdl2"):
        win.spd_files[name].setText("")


@pytest.fixture()
def board(win, monkeypatch):
    """Window with every routing sink recorded; `_display_key` set."""
    rec = _Rec()

    monkeypatch.setattr(win, "_display_key", KEY)
    monkeypatch.setattr(win, "_adb_ready_for_key", lambda *a, **k: rec.adb)
    monkeypatch.setattr(win, "_spd_run",
                        lambda args, **kw: rec.runs.append((list(args), kw)))
    monkeypatch.setattr(win, "_run_ops_flow",
                        lambda *a, **kw: rec.flows.append((a, kw)))
    monkeypatch.setattr(win, "_on_section", lambda key: rec.sections.append(key))
    monkeypatch.setattr(win, "_route_model_flash",
                        lambda *a, **k: rec.flash_routes.append((a, k)))

    def _resolve_target():
        rec.target_resolves += 1
        return TGT

    monkeypatch.setattr(win, "_spd_resolve_target", _resolve_target)

    def _detect():
        rec.detected += 1

    monkeypatch.setattr(win, "_spd_detect", _detect)

    def _refresh():
        rec.refreshed += 1

    monkeypatch.setattr(win, "refresh_device", _refresh)
    monkeypatch.setattr(win, "log_line", lambda m: rec.lines.append(str(m)))

    def _toast(kind):
        def _emit(title, detail="", *a, **kw):
            rec.toasts.append((kind, title, detail))
        return _emit

    monkeypatch.setattr(win._toasts, "show_info", _toast("info"))
    monkeypatch.setattr(win._toasts, "show_ok", _toast("ok"))
    monkeypatch.setattr(win._toasts, "show_warn", _toast("warn"))
    monkeypatch.setattr(win._toasts, "show_error", _toast("error"))

    def _confirm(title, text, confirm_label, on_confirm, chip=None):
        rec.confirms.append((title, text, confirm_label, chip))
        if rec.confirm_ok:
            on_confirm()

    monkeypatch.setattr(win, "_confirm_overlay", _confirm)

    def _pick_file(*a, **k):
        rec.picks.append(("file", a, k))
        return (rec.pick_file, "")

    def _pick_dir(*a, **k):
        rec.picks.append(("dir", a, k))
        return rec.pick_dir

    monkeypatch.setattr(qt_app.QFileDialog, "getOpenFileName",
                        staticmethod(_pick_file))
    monkeypatch.setattr(qt_app.QFileDialog, "getExistingDirectory",
                        staticmethod(_pick_dir))
    return win, rec


def _run(win, act, meta=META, brand=BRAND):
    win.start_model_action(act, brand, meta)


def _pac_picks(rec):
    """Only the `.pac` (open-file) picker calls."""
    return [p for p in rec.picks if p[0] == "file"]


def _assert_no_run(rec):
    assert rec.runs == []
    assert rec.flows == []
    assert all(k != "ok" for k, _t, _d in rec.toasts)


# ------------------------------------------------------------ screen lock
def test_screen_lock_with_adb_stays_on_locksettings(board):
    win, rec = board
    rec.adb = True
    rec.pick_file = PAC  # must never be asked for
    _run(win, "screen_lock")

    assert rec.runs == []
    assert _pac_picks(rec) == []
    assert rec.confirms == []
    assert len(rec.flows) == 1
    assert rec.flows[0][0][2] == "screen_lock_locksettings"


def test_screen_lock_without_adb_erases_from_pac(board):
    win, rec = board
    rec.pick_file = PAC
    _run(win, "screen_lock")

    assert rec.flows == [], "no ADB -> no locksettings flow"
    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["spd-flash-pac", "auto", PAC, "--mode", "erase"]
    assert kw["device_key"] == KEY, "must target the selected device"
    assert rec.confirms and rec.confirms[0][0] == f"{LABEL} · Remove Screen Lock"
    assert "WIPE USER DATA" in rec.confirms[0][1]
    assert rec.confirms[0][3] == "lock"
    assert [t for t in rec.toasts if t[0] == "ok"] == []


def test_screen_lock_pac_cancel_runs_nothing(board):
    win, rec = board
    rec.pick_file = ""
    _run(win, "screen_lock")

    _assert_no_run(rec)
    assert rec.confirms == []


def test_screen_lock_confirm_cancel_runs_nothing(board):
    win, rec = board
    rec.pick_file = PAC
    rec.confirm_ok = False
    _run(win, "screen_lock")

    assert rec.runs == []
    assert len(rec.confirms) == 1


# --------------------------------------------------------------------- FRP
def test_frp_with_adb_stays_on_adb_flow(board):
    win, rec = board
    rec.adb = True
    rec.pick_file = PAC  # must never be asked for
    _run(win, "frp")

    assert rec.runs == []
    assert _pac_picks(rec) == []
    assert rec.confirms == []
    assert len(rec.flows) == 1
    assert rec.flows[0][0][2] == "adb_frp"


def test_frp_with_pac_argv_and_warning(board):
    win, rec = board
    rec.pick_file = PAC
    _run(win, "frp")

    assert rec.flows == [], "no ADB -> no adb_frp flow"
    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["spd-flash-pac", "auto", PAC, "--mode", "frp"]
    assert kw["device_key"] == KEY, "must target the selected device"
    assert rec.confirms and rec.confirms[0][0] == f"{LABEL} · Remove FRP"
    assert "WIPE USER DATA" in rec.confirms[0][1]
    assert rec.confirms[0][3] == "frp"
    assert rec.sections == [], "a PAC run needs no SPD workbench detour"
    assert [t for t in rec.toasts if t[0] == "ok"] == []


def test_frp_with_configured_fdl_keeps_spd_frp(board):
    win, rec = board
    win.spd_files["fdl1"].setText(FDL1)
    win.spd_files["fdl2"].setText(FDL2)
    rec.pick_file = PAC  # must never be asked for
    _run(win, "frp")

    assert _pac_picks(rec) == [], "configured FDLs must not prompt for a PAC"
    assert len(rec.runs) == 1
    argv, _kw = rec.runs[0]
    assert argv[0] == "spd-frp"
    assert argv[1] == TGT, "existing path keeps the resolved target"
    assert argv[2:] == [FDL1, "0x40004000", FDL2, "0x14000000"]
    assert rec.sections == ["spd"], "the FDL path is a workbench path"


def test_frp_pac_cancel_runs_nothing(board):
    win, rec = board
    rec.pick_file = ""
    _run(win, "frp")

    _assert_no_run(rec)
    assert rec.confirms == []


def test_frp_confirm_cancel_runs_nothing(board):
    win, rec = board
    rec.pick_file = PAC
    rec.confirm_ok = False
    _run(win, "frp")

    assert rec.runs == []
    assert len(rec.confirms) == 1


# ------------------------------------------------------------------ backup
def test_backup_with_pac_reports_path_after_run(board):
    win, rec = board
    rec.pick_dir = OUT
    rec.pick_file = PAC
    _run(win, "backup")

    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["spd-flash-pac", "auto", PAC, "--mode", "backup",
                    "--out", OUT]
    assert kw["timeout"] == 3600
    assert kw["device_key"] == KEY
    assert callable(kw.get("on_done")), "result path reported after the run"
    # The destination is not reported as a finished result before the flow returns.
    assert not any(OUT in line for line in rec.lines)
    kw["on_done"]("wrote partitions")
    assert any(OUT in line for line in rec.lines)


def test_backup_with_configured_fdl_keeps_spd_backup(board):
    win, rec = board
    win.spd_files["fdl1"].setText(FDL1)
    rec.pick_dir = OUT
    rec.pick_file = PAC  # must never be asked for
    _run(win, "backup")

    assert _pac_picks(rec) == []
    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["spd-backup", TGT, FDL1, "0x40004000", OUT]
    assert kw["device_key"] == KEY
    assert callable(kw.get("on_done"))
    assert rec.sections == ["spd"]


def test_backup_dir_cancel_runs_nothing(board):
    win, rec = board
    rec.pick_dir = ""
    rec.pick_file = PAC
    _run(win, "backup")

    _assert_no_run(rec)
    assert _pac_picks(rec) == [], "no need to pick a PAC without a destination"


def test_backup_pac_cancel_runs_nothing(board):
    win, rec = board
    rec.pick_dir = OUT
    rec.pick_file = ""
    _run(win, "backup")

    _assert_no_run(rec)
    assert not any(OUT in line for line in rec.lines)


# ------------------------------------------------------------------- flash
def test_flash_runs_single_pac_without_opening_workbench(board):
    win, rec = board
    rec.pick_file = PAC
    _run(win, "flash")

    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["spd-flash-pac", "auto", PAC, "--mode", "flash"]
    assert kw["timeout"] == 3600
    assert kw["device_key"] == KEY
    assert rec.sections == [], "flash must not open the SPD workbench"
    assert rec.flash_routes == [], "PAC path replaces the workbench routing"
    assert rec.confirms and rec.confirms[0][0] == f"{LABEL} · Flash Firmware"
    assert "OVERWRITES" in rec.confirms[0][1]
    assert rec.confirms[0][3] == "flash"
    assert PAC in rec.lines[0] or any(PAC in line for line in rec.lines)
    assert [t for t in rec.toasts if t[0] == "ok"] == []


def test_flash_pac_cancel_runs_nothing(board):
    win, rec = board
    rec.pick_file = ""
    _run(win, "flash")

    _assert_no_run(rec)
    assert rec.confirms == []


def test_flash_confirm_cancel_runs_nothing(board):
    win, rec = board
    rec.pick_file = PAC
    rec.confirm_ok = False
    _run(win, "flash")

    assert rec.runs == []
    assert len(rec.confirms) == 1


# -------------------------------------------------------------------- info
def test_info_is_unchanged(board):
    win, rec = board
    _run(win, "info")

    assert rec.refreshed == 1, "SPD info keeps the generic identity refresh"
    assert rec.runs == []
    assert rec.flows == []
    assert rec.confirms == []
    assert rec.picks == []


def test_unknown_act_keeps_honest_guidance(board):
    win, rec = board
    _run(win, "carrier_unlock")

    _assert_no_run(rec)
    assert any(t[0] == "info" for t in rec.toasts)


# ------------------------------------------------- no FDL dead-end anymore
@pytest.mark.parametrize("act,pick_dir,pick_file", [
    ("frp", "", ""),
    ("screen_lock", "", ""),
    ("flash", "", ""),
    ("backup", OUT, ""),
])
def test_missing_fdl_is_not_a_dead_end(board, act, pick_dir, pick_file):
    """Cancelling the PAC picker must not resurrect the FDL1/FDL2 toast."""
    win, rec = board
    rec.pick_dir = pick_dir
    rec.pick_file = pick_file
    _run(win, act)

    _assert_no_run(rec)
    assert [t for t in rec.toasts if "FDL1/FDL2" in t[2]] == []
