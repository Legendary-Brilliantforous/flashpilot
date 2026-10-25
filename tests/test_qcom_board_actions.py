"""Devices-page (Qualcomm) board actions run real EDL bridge commands.

Regression contract for `FlashPilotWindow.start_model_action` on Qualcomm
models: FRP, backup, flash and info used to show a "load it on the Qualcomm
tab" guidance toast (or a QCN/DIAG detour) instead of doing anything. They now
run the EDL 9008 (Sahara/Firehose) bridge commands for the *selected* device
(never "the first device") behind the confirmation overlay, with the bundled
programmer directory only logged (the resolver also honours the environment).

The routing sinks are replaced with recorders, so these tests assert the exact
argv and device scope without touching USB, EDL or a real phone.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from python.core import bridge
from python.gui import qt_app

KEY = "usb:05c6:9008:1-1.3"
META = {"engine": "qcom", "model": "Moto G7 Power", "vid": "05c6"}
BRAND = "Motorola"
LABEL = "Motorola Moto G7 Power"
QCOM_DIR = "/opt/flashpilot/payloads/qcom"


class _Rec:
    def __init__(self):
        self.runs = []          # (argv, kwargs) from _qc_run
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
        self.pick_file = ""
        self.frp_choice = "frp"


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
    monkeypatch.setattr(win, "_qc_run",
                        lambda args, **kw: rec.runs.append((list(args), kw)))
    monkeypatch.setattr(win, "_run_ops_flow",
                        lambda *a, **kw: rec.flows.append((a, kw)))
    monkeypatch.setattr(win, "_on_section", lambda key: rec.sections.append(key))
    monkeypatch.setattr(win, "_route_model_flash",
                        lambda *a, **k: rec.flash_routes.append((a, k)))

    def _detect():
        rec.detected += 1

    monkeypatch.setattr(win, "_qc_detect", _detect)

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
    monkeypatch.setattr(win, "_qc_frp_choice",
                        lambda label: rec.frp_choice)
    monkeypatch.setattr(
        qt_app.QFileDialog, "getExistingDirectory",
        staticmethod(lambda *a, **k: rec.pick_dir),
    )
    monkeypatch.setattr(
        qt_app.QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (rec.pick_file, "")),
    )
    monkeypatch.setattr(qt_app.bridge, "bundled_qcom_dir", lambda: QCOM_DIR)
    return win, rec


def _run(win, act, meta=META, brand=BRAND):
    win.start_model_action(act, brand, meta)


def _assert_no_run(rec):
    assert rec.runs == []
    assert rec.flows == []
    assert all(k != "ok" for k, _t, _d in rec.toasts)


# --------------------------------------------------------------------- FRP
def test_frp_erase_only_argv_selected_key(board):
    win, rec = board
    _run(win, "frp")

    assert rec.flows == [], "no ADB -> must not route the ADB flow"
    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["qcom-frp-reset", "auto"]
    assert kw["timeout"] == 600
    assert kw["device_key"] == KEY, "must target the selected device"
    assert rec.confirms and rec.confirms[0][0] == f"{LABEL} · Remove FRP"
    assert "EDL 9008" in rec.confirms[0][1]
    assert rec.confirms[0][3] == "frp"
    # No green "done" toast before the run completes.
    assert [t for t in rec.toasts if t[0] == "ok"] == []


def test_frp_wipe_variant_argv_and_confirmation(board):
    win, rec = board
    rec.frp_choice = "wipe"
    _run(win, "frp")

    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["qcom-frp-reset", "auto", "--wipe-data"]
    assert kw["device_key"] == KEY
    assert kw["timeout"] == 600
    assert rec.confirms and rec.confirms[0][3] == "wipe"
    assert "ERASES USER DATA" in rec.confirms[0][1]


def test_frp_with_adb_stays_on_adb_flow(board):
    win, rec = board
    rec.adb = True
    _run(win, "frp")

    assert rec.runs == []
    assert rec.confirms == []
    assert len(rec.flows) == 1
    assert rec.flows[0][0][2] == "adb_frp"


def test_frp_choice_cancel_runs_nothing(board):
    win, rec = board
    rec.frp_choice = None
    _run(win, "frp")

    _assert_no_run(rec)
    assert rec.confirms == []


def test_frp_confirm_cancel_runs_nothing(board):
    win, rec = board
    rec.confirm_ok = False
    _run(win, "frp")

    assert rec.runs == []
    assert len(rec.confirms) == 1


def test_frp_without_bundled_dir_still_runs_and_logs_note(board, monkeypatch):
    win, rec = board
    monkeypatch.setattr(qt_app.bridge, "bundled_qcom_dir", lambda: "")
    _run(win, "frp")

    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["qcom-frp-reset", "auto"]
    assert kw["device_key"] == KEY
    assert [t for t in rec.toasts if t[0] == "error"] == [], \
        "a missing bundle must not block the run (env resolver)"
    assert any("no bundled Qualcomm programmers" in line for line in rec.lines)


# ------------------------------------------------------------------ backup
def test_backup_uses_selected_key_and_output_dir(board):
    win, rec = board
    rec.pick_dir = "/tmp/qcom_backup_run"
    _run(win, "backup")

    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["qcom-backup", "auto", "/tmp/qcom_backup_run"]
    assert kw["timeout"] == 1800
    assert kw["device_key"] == KEY
    assert callable(kw.get("on_done")), "result path reported after the run"
    assert rec.confirms and rec.confirms[0][0] == f"{LABEL} · Backup Partitions"
    # The path is not reported as a finished result before the flow returns.
    assert not any("/tmp/qcom_backup_run" in line for line in rec.lines)
    kw["on_done"]("wrote partitions")
    assert any("/tmp/qcom_backup_run" in line for line in rec.lines)


def test_backup_dialog_cancel_runs_nothing(board):
    win, rec = board
    rec.pick_dir = ""
    _run(win, "backup")

    _assert_no_run(rec)
    assert rec.confirms == []


def test_backup_confirm_cancel_runs_nothing(board):
    win, rec = board
    rec.pick_dir = "/tmp/qcom_backup_run"
    rec.confirm_ok = False
    _run(win, "backup")

    assert rec.runs == []
    assert len(rec.confirms) == 1


# ------------------------------------------------------------------- flash
def test_flash_single_xml_runs_without_opening_workbench(board, tmp_path):
    win, rec = board
    fw = tmp_path / "firmware"
    fw.mkdir()
    (fw / "RawProgram_main.XML").write_text("<xml/>")  # case-insensitive
    (fw / "notes.txt").write_text("ignore me")
    rec.pick_dir = str(fw)

    _run(win, "flash")

    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["qcom-flash", "auto",
                    str(fw / "RawProgram_main.XML"), str(fw)]
    assert kw["timeout"] == 1800
    assert kw["device_key"] == KEY
    assert rec.sections == [], "flash must not open the Qualcomm workbench"
    assert rec.flash_routes == []
    assert rec.confirms and rec.confirms[0][0] == f"{LABEL} · Flash Firmware"
    assert "OVERWRITES" in rec.confirms[0][1]
    assert rec.confirms[0][3] == "flash"


def test_flash_ambiguous_xml_asks_and_uses_the_pick(board, tmp_path):
    win, rec = board
    fw = tmp_path / "firmware"
    fw.mkdir()
    (fw / "rawprogram0.xml").write_text("<xml/>")
    (fw / "rawprogram1.xml").write_text("<xml/>")
    rec.pick_dir = str(fw)
    rec.pick_file = str(fw / "rawprogram1.xml")

    _run(win, "flash")

    assert len(rec.runs) == 1
    argv, kw = rec.runs[0]
    assert argv == ["qcom-flash", "auto",
                    str(fw / "rawprogram1.xml"), str(fw)]
    assert kw["device_key"] == KEY


def test_flash_ambiguous_xml_pick_cancel_runs_nothing(board, tmp_path):
    win, rec = board
    fw = tmp_path / "firmware"
    fw.mkdir()
    (fw / "rawprogram0.xml").write_text("<xml/>")
    (fw / "rawprogram1.xml").write_text("<xml/>")
    rec.pick_dir = str(fw)
    rec.pick_file = ""

    _run(win, "flash")

    _assert_no_run(rec)
    assert rec.confirms == []


def test_flash_without_xml_errors_and_runs_nothing(board, tmp_path):
    win, rec = board
    fw = tmp_path / "firmware"
    fw.mkdir()
    (fw / "readme.txt").write_text("no xml here")
    rec.pick_dir = str(fw)

    _run(win, "flash")

    _assert_no_run(rec)
    assert rec.confirms == []
    errors = [t for t in rec.toasts if t[0] == "error"]
    assert errors, "no rawprogram XML must surface an error"
    assert "rawprogram*.xml" in errors[0][2]


def test_flash_dialog_cancel_runs_nothing(board):
    win, rec = board
    rec.pick_dir = ""
    _run(win, "flash")

    _assert_no_run(rec)
    assert rec.confirms == []


def test_flash_confirm_cancel_runs_nothing(board, tmp_path):
    win, rec = board
    fw = tmp_path / "firmware"
    fw.mkdir()
    (fw / "rawprogram0.xml").write_text("<xml/>")
    rec.pick_dir = str(fw)
    rec.confirm_ok = False

    _run(win, "flash")

    assert rec.runs == []
    assert len(rec.confirms) == 1


# -------------------------------------------------------------------- info
def test_info_routes_to_qcom_detect(board):
    win, rec = board
    _run(win, "info")

    assert rec.detected == 1, "Qualcomm info must run the EDL detect"
    assert rec.refreshed == 0, "the generic refresh must not intercept qcom"
    assert rec.runs == []
    assert rec.flows == []


def test_unknown_act_keeps_honest_guidance(board):
    win, rec = board
    _run(win, "carrier_unlock")

    _assert_no_run(rec)
    assert any(t[0] == "info" for t in rec.toasts)


# --------------------------------------------------------- bridge helper
def test_bundled_qcom_dir_reports_repo_payloads():
    d = bridge.bundled_qcom_dir()
    assert d == "" or d.endswith(os.path.join("payloads", "qcom"))


def test_bundled_qcom_dir_empty_when_absent(tmp_path, monkeypatch):
    fake = tmp_path / "python" / "core" / "bridge.py"
    monkeypatch.setattr(bridge, "__file__", str(fake))
    # An installed FlashPilot (/usr/lib, ~/.local) must not leak into the
    # "nothing bundled" case, so isolate every candidate root.
    monkeypatch.setattr(
        bridge,
        "qcom_payload_candidates",
        lambda here, home: (tmp_path / "absent",),
    )
    assert bridge.bundled_qcom_dir() == ""


def test_qcom_payload_candidates_prefer_dev_tree():
    here = os.path.join("/repo")
    home = os.path.join("/home", "someone")
    cands = [str(p) for p in bridge.qcom_payload_candidates(here, home)]
    assert cands[0] == os.path.join("/repo", "payloads", "qcom")
    assert cands[1] == "/usr/lib/flashpilot/payloads/qcom"
    assert cands[2] == os.path.join(home, ".local", "share", "flashpilot",
                                    "payloads", "qcom")
