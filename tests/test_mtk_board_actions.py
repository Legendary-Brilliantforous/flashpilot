"""Devices-page (MTK) board actions run real bridge commands.

Regression contract for `FlashPilotWindow.start_model_action` on MediaTek
models: FRP, screen lock, backup and flash used to open the MTK workbench or
show a "Wiring lands in the next step" toast. They now run the BROM bridge
commands for the *selected* device (never "the first device"), behind the
confirmation overlay, with the bundled DA where the command takes one.

The routing sinks are replaced with recorders, so these tests assert the exact
argv and device scope without touching USB, BROM or a real phone.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from python.gui import qt_app

KEY = "usb:0e8d:2000:1-1.2"
DA = "/opt/flashpilot/root/tools/mtk"
META = {"engine": "mtk", "model": "Redmi Note 8", "vid": "0e8d"}
BRAND = "Xiaomi"
LABEL = "Xiaomi Redmi Note 8"


class _Rec:
    def __init__(self):
        self.runs = []          # (argv, kwargs) from _mtk_run
        self.flows = []         # universal ADB flows
        self.sections = []      # workbench navigation
        self.flash_routes = []  # _route_model_flash
        self.confirms = []      # (title, text, confirm_label, chip)
        self.toasts = []        # (kind, title, detail)
        self.lines = []
        self.detected = 0
        self.refreshed = 0
        self.adb = False
        self.confirm_ok = True
        self.pick_dir = ""
        self.flash_mode = "flash"   # _mtk_board_flash_mode sink
        self.flash_mode_calls = 0


@pytest.fixture(scope="module")
def win(test_window):
    """One real window for the module (construction is the slow part)."""
    return test_window()


@pytest.fixture()
def board(win, monkeypatch):
    """Window with every routing sink recorded; `_display_key` set."""
    rec = _Rec()

    monkeypatch.setattr(win, "_display_key", KEY)
    monkeypatch.setattr(win, "_adb_ready_for_key",
                        lambda *a, **k: rec.adb)
    monkeypatch.setattr(win, "_mtk_run",
                        lambda args, **kw: rec.runs.append((list(args), kw)))
    monkeypatch.setattr(win, "_run_ops_flow",
                        lambda *a, **kw: rec.flows.append((a, kw)))
    monkeypatch.setattr(win, "_on_section", lambda key: rec.sections.append(key))
    monkeypatch.setattr(win, "_route_model_flash",
                        lambda *a, **k: rec.flash_routes.append((a, k)))

    def _detect():
        rec.detected += 1

    monkeypatch.setattr(win, "_mtk_detect", _detect)

    def _flash_mode():
        rec.flash_mode_calls += 1
        return rec.flash_mode

    monkeypatch.setattr(win, "_mtk_board_flash_mode", _flash_mode)

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
    monkeypatch.setattr(
        qt_app.QFileDialog, "getExistingDirectory",
        staticmethod(lambda *a, **k: rec.pick_dir),
    )
    monkeypatch.setattr(qt_app.bridge, "bundled_mtk_da_dir", lambda: DA)
    return win, rec


def _run(win, act, meta=META, brand=BRAND):
    win.start_model_action(act, brand, meta)


def _assert_no_run(rec):
    assert rec.runs == []
    assert rec.flows == []
    assert all(k != "ok" for k, _t, _d in rec.toasts)


# --------------------------------------------------------------------- FRP
def test_frp_no_adb_uses_brom_selected_key_and_bundled_da(board):
    win, rec = board
    _run(win, "frp")

    assert rec.flows == [], "no ADB -> must not route the ADB flow"
    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["mtk-frp-brom", "auto", DA]
    assert kw["timeout"] == 1800
    assert kw["device_key"] == KEY, "must target the selected device"
    assert rec.confirms and rec.confirms[0][0] == f"{LABEL} · Remove FRP"
    assert "BROM" in rec.confirms[0][1]
    assert rec.confirms[0][3] == "frp"
    # No green "done" toast before the run completes.
    assert [t for t in rec.toasts if t[0] == "ok"] == []


def test_frp_with_adb_stays_on_adb_flow(board):
    win, rec = board
    rec.adb = True
    _run(win, "frp")

    assert rec.runs == []
    assert rec.confirms == []
    assert len(rec.flows) == 1
    args, _kw = rec.flows[0]
    assert args[2] == "adb_frp"


def test_frp_empty_bundled_da_errors_and_runs_nothing(board, monkeypatch):
    win, rec = board
    monkeypatch.setattr(qt_app.bridge, "bundled_mtk_da_dir", lambda: "")
    _run(win, "frp")

    _assert_no_run(rec)
    assert rec.confirms == [], "must not offer to run without the DA"
    errors = [t for t in rec.toasts if t[0] == "error"]
    assert errors, "missing bundled DA must surface an error"
    assert "bundled" in errors[0][2].lower()


def test_frp_confirm_cancel_runs_nothing(board):
    win, rec = board
    rec.confirm_ok = False
    _run(win, "frp")

    assert rec.runs == []
    assert len(rec.confirms) == 1


# ------------------------------------------------------------ screen lock
def test_screen_lock_with_adb_stays_on_locksettings(board):
    win, rec = board
    rec.adb = True
    _run(win, "screen_lock")

    assert rec.runs == []
    assert len(rec.flows) == 1
    assert rec.flows[0][0][2] == "screen_lock_locksettings"


def test_screen_lock_erase_variant(board, monkeypatch):
    win, rec = board
    monkeypatch.setattr(win, "_mtk_board_screen_lock_choice",
                        lambda label: "erase")
    _run(win, "screen_lock")

    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["mtk-screen-lock", "auto", DA]
    assert kw["timeout"] == 1800
    assert kw["device_key"] == KEY
    assert rec.confirms and rec.confirms[0][0] == f"{LABEL} · Remove Screen Lock"
    assert rec.confirms[0][3] == "lock"


def test_screen_lock_wipe_variant(board, monkeypatch):
    win, rec = board
    monkeypatch.setattr(win, "_mtk_board_screen_lock_choice",
                        lambda label: "wipe")
    _run(win, "screen_lock")

    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["mtk-screen-lock", "auto", DA, "--wipe-userdata"]
    assert kw["device_key"] == KEY
    assert rec.confirms and rec.confirms[0][3] == "wipe"
    assert "FACTORY RESET" in rec.confirms[0][1]


def test_screen_lock_choice_cancel_runs_nothing(board, monkeypatch):
    win, rec = board
    monkeypatch.setattr(win, "_mtk_board_screen_lock_choice",
                        lambda label: None)
    _run(win, "screen_lock")

    _assert_no_run(rec)
    assert rec.confirms == []


def test_screen_lock_confirm_cancel_runs_nothing(board, monkeypatch):
    win, rec = board
    rec.confirm_ok = False
    monkeypatch.setattr(win, "_mtk_board_screen_lock_choice",
                        lambda label: "wipe")
    _run(win, "screen_lock")

    assert rec.runs == []


# ------------------------------------------------------------------ backup
def test_backup_uses_selected_key_da_and_output_dir(board):
    win, rec = board
    rec.pick_dir = "/tmp/mtk_backup_run"
    _run(win, "backup")

    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["mtk-backup-gpt", "auto", DA, "/tmp/mtk_backup_run"]
    assert kw["timeout"] == 1800
    assert kw["device_key"] == KEY
    assert callable(kw.get("on_done")), "result path reported after the run"
    assert rec.confirms and rec.confirms[0][0] == f"{LABEL} · Backup GPT"
    # The path is not reported as a finished result before the flow returns.
    assert not any("/tmp/mtk_backup_run" in line for line in rec.lines)
    kw["on_done"]("wrote gpt.bin")
    assert any("/tmp/mtk_backup_run" in line for line in rec.lines)


def test_backup_dialog_cancel_runs_nothing(board):
    win, rec = board
    rec.pick_dir = ""
    _run(win, "backup")

    _assert_no_run(rec)
    assert rec.confirms == []


# ------------------------------------------------------------------- flash
def test_flash_runs_auto_da_without_opening_workbench(board):
    win, rec = board
    rec.pick_dir = "/tmp/firmware"
    _run(win, "flash")

    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["mtk-flash-auto", "auto", "/tmp/firmware", "--da", "auto"]
    assert kw["device_key"] == KEY
    assert rec.sections == [], "flash must not open the MTK workbench"
    assert rec.flash_routes == []
    assert rec.confirms and rec.confirms[0][0] == f"{LABEL} · Flash Firmware"
    assert "OVERWRITES" in rec.confirms[0][1]
    assert rec.confirms[0][3] == "flash"


def test_flash_dialog_cancel_runs_nothing(board):
    win, rec = board
    rec.pick_dir = ""
    _run(win, "flash")

    _assert_no_run(rec)
    assert rec.confirms == []


def test_flash_confirm_cancel_runs_nothing(board):
    win, rec = board
    rec.confirm_ok = False
    rec.pick_dir = "/tmp/firmware"
    _run(win, "flash")

    assert rec.runs == []


def test_flash_mode_prompt_cancel_runs_nothing(board):
    win, rec = board
    rec.pick_dir = "/tmp/firmware"
    rec.flash_mode = ""          # user cancelled the mode prompt
    _run(win, "flash")

    assert rec.flash_mode_calls == 1
    assert rec.runs == []
    assert rec.confirms == []


def test_format_all_flash_flag(board):
    win, rec = board
    rec.pick_dir = "/tmp/firmware"
    rec.flash_mode = "format"
    _run(win, "flash")

    argv, _kw = rec.runs[0]
    assert argv == [
        "mtk-flash-auto", "auto", "/tmp/firmware",
        "--da", "auto", "--format-all",
    ]
    assert "Format All + download" in rec.confirms[0][1]


def test_format_all_wipe_data_flags(board):
    win, rec = board
    rec.pick_dir = "/tmp/firmware"
    rec.flash_mode = "format_data"
    _run(win, "flash")

    argv, _kw = rec.runs[0]
    assert argv == [
        "mtk-flash-auto", "auto", "/tmp/firmware",
        "--da", "auto", "--format-all", "--erase-userdata",
    ]
    assert "Format All + wipe data" in rec.confirms[0][1]


# ------------------------------------------------------- info / kirin guard
def test_info_still_routes_to_detect(board):
    win, rec = board
    _run(win, "info")

    # Device info is a read-only refresh at the top of the router (unchanged).
    assert rec.refreshed == 1
    assert rec.runs == []


def test_kirin_frp_guidance_unchanged(board):
    win, rec = board
    meta = {"engine": "kirin", "model": "P30 Lite", "vid": "12d1"}
    _run(win, "frp", meta=meta, brand="Huawei")

    assert rec.runs == []
    assert rec.flows == []
    assert rec.sections == ["mtk"]
    assert any(t[0] == "info" for t in rec.toasts)
