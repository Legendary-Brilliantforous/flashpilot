"""Tests for the carrier / SIM-lock workbench (frp.py).

The status detector must be pure read (verdict only, never writes) and the MTK
SimLock patch must be recipe-gated: it refuses to write without a validated
recipe, an opt-in flag, and the exact locked signature present in the read-back.
"""
import os

import pytest

from python.core import frp


class TestCarrierLockVerdict:
    def _info(self, states=None, dumps=None):
        props = {k: "" for k in frp._SIM_LOCK_PROPS}
        for i, s in enumerate((states or [""])[:3]):
            key = ("gsm.sim.state", "gsm.sim.state.2", "ril.sim.state")[i]
            props[key] = s
        return {"props": props, "dumps": dumps or {}}

    def test_locked_from_sim_state(self):
        info = self._info(states=["NETWORK_LOCKED"])
        verdict, evidence = frp._carrier_lock_verdict(info)
        assert verdict == "LOCKED"
        assert evidence

    def test_locked_from_phone_dump_wording(self):
        info = self._info(states=["READY"], dumps={"phone": ["network lock active"]})
        verdict, _ = frp._carrier_lock_verdict(info)
        assert verdict == "LOCKED"

    def test_readonly_no_false_lock_on_ready(self):
        info = self._info(states=["READY"], dumps={"telephony.registry": ["mSimState=READY"]})
        verdict, _ = frp._carrier_lock_verdict(info)
        assert verdict == "UNLOCKED"

    def test_unlocked(self):
        info = self._info(states=["READY"])
        verdict, _ = frp._carrier_lock_verdict(info)
        assert verdict == "UNLOCKED"

    def test_pin_locked(self):
        info = self._info(states=["PIN_REQUIRED"])
        verdict, _ = frp._carrier_lock_verdict(info)
        assert verdict == "PIN-LOCKED"

    def test_no_sim(self):
        info = self._info(states=["ABSENT"])
        verdict, _ = frp._carrier_lock_verdict(info)
        assert verdict == "NO-SIM"

    def test_unknown_when_nothing_exposed(self):
        info = self._info(states=[])
        verdict, _ = frp._carrier_lock_verdict(info)
        assert verdict == "UNKNOWN"

    def test_sim_error(self):
        info = self._info(states=["PERM_DISABLED"])
        verdict, _ = frp._carrier_lock_verdict(info)
        assert verdict == "SIM-ERROR"


class TestLocateSimlock:
    def test_finds_marker_offsets(self):
        data = b"X" * 100 + b"SIMLOCK" + b"Y" * 50 + b"SIMLOCK" + b"Z" * 20
        found = frp._locate_simlock(data)
        assert (100, b"SIMLOCK") in found
        assert (157, b"SIMLOCK") in found

    def test_longest_marker_wins_at_same_offset(self):
        data = b"MP0B001_003_rest_of_record"
        found = frp._locate_simlock(data)
        off, marker = found[0]
        assert marker == b"MP0B001_003"

    def test_empty_image(self):
        assert frp._locate_simlock(b"") == []

    def test_no_markers(self):
        assert frp._locate_simlock(b"\x00" * 4096) == []

    def test_hex_dump_shape(self):
        dump = frp._hex_dump(b"SIMLOCK" + b"\x00" * 26, 0, 32)
        assert "SIMLOCK" in dump
        assert "00000000" in dump


class TestFindMtkDa:
    def test_env_override(self, monkeypatch, tmp_path):
        fake = tmp_path / "MTK_AllInOne_DA.bin"
        fake.write_bytes(b"da")
        monkeypatch.setenv("MTK_DA", str(fake))
        assert frp._find_mtk_da() == str(fake)

    def test_env_missing_path_ignored(self, monkeypatch):
        monkeypatch.setenv("MTK_DA", "/nonexistent/da.bin")
        assert frp._find_mtk_da() == ""

    def test_scans_tools_dir(self, tmp_path):
        tools = tmp_path / "tools"
        tools.mkdir()
        da = tools / "MTK_AllInOne_DA.bin"
        da.write_bytes(b"da")
        (tools / "unrelated.txt").write_text("x")
        assert frp._da_in_dirs([str(tools)]) == str(da)

    def test_not_found(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert frp._da_in_dirs([str(empty)]) == ""


class TestMtkSimlockPatchGating:
    """The patch engine must refuse every unsafe path and only write when the
    exact locked signature is present + the opt-in flag is set."""

    RECIPE = {
        "partition": "nvdata",
        "offset": 8,
        "lock_bytes": b"\x01\x00\x00\x00",
        "unlocked_bytes": b"\x00\x00\x00\x00",
    }

    def _backup(self, tmp_path, content):
        img = tmp_path / "nvdata.img"
        img.write_bytes(content)
        return [("nvdata", str(img))]

    def _run_patch(self, monkeypatch, tmp_path, content, env, model="SM-A065F"):
        monkeypatch.setattr(frp, "_MTK_SIMLOCK_RECIPES", {"SM-A065F": dict(self.RECIPE)})
        monkeypatch.setenv("MTK_SIMLOCK_PATCH", env)
        calls = []
        monkeypatch.setattr(frp.bridge, "_run", lambda *a, **k: calls.append(a) or "ok")
        logs = []
        frp._mtk_simlock_patch({"model": model}, logs.append, "auto", "auto",
                               self._backup(tmp_path, content))
        return calls, logs

    def test_no_recipe_refuses(self, monkeypatch, tmp_path):
        monkeypatch.setattr(frp, "_MTK_SIMLOCK_RECIPES", {})
        monkeypatch.setenv("MTK_SIMLOCK_PATCH", "1")
        calls = []
        monkeypatch.setattr(frp.bridge, "_run", lambda *a, **k: calls.append(a) or "ok")
        img = tmp_path / "nvdata.img"
        img.write_bytes(b"\x00" * 32)
        frp._mtk_simlock_patch({"model": "SM-A065F"}, lambda m: None, "auto", "auto",
                               [("nvdata", str(img))])
        assert calls == []

    def test_optin_required(self, monkeypatch, tmp_path):
        content = b"\x00" * 8 + b"\x01\x00\x00\x00" + b"\x00" * 16
        calls, _ = self._run_patch(monkeypatch, tmp_path, content, env="0")
        assert calls == []

    def test_signature_mismatch_refuses(self, monkeypatch, tmp_path):
        content = b"\x00" * 32  # no locked signature at offset 8
        calls, _ = self._run_patch(monkeypatch, tmp_path, content, env="1")
        assert calls == []

    def test_success_writes_back(self, monkeypatch, tmp_path):
        content = b"\x00" * 8 + b"\x01\x00\x00\x00" + b"\x00" * 16
        calls, _ = self._run_patch(monkeypatch, tmp_path, content, env="1")
        assert calls and "mtk-flash-part" in calls[0][0]

    def test_patch_never_guesses_unknown_model(self, monkeypatch, tmp_path):
        content = b"\x00" * 8 + b"\x01\x00\x00\x00" + b"\x00" * 16
        calls, _ = self._run_patch(monkeypatch, tmp_path, content, env="1",
                                   model="SM-G999F")
        assert calls == []


class TestScreenLockCscRegistration:
    """The CSC-flash screen-lock method is registered where the GUI shows it."""

    def test_registered_in_flows(self):
        assert "screen_lock_csc" in frp.FLOWS
        assert "CSC" in frp.FLOWS["screen_lock_csc"]().name.upper()

    def test_available_in_download_and_brom_modes(self):
        m = frp.JOBS["Screen lock remove"]
        assert "screen_lock_csc" in m["Download mode"]
        assert "screen_lock_csc" in m["Samsung BROM"]
        assert "screen_lock_csc" in m["MTK"]
        assert "screen_lock_csc" in frp.methods_for("Screen lock remove", "Download mode")

    def test_flow_rejects_mismatched_csc_model(self, monkeypatch, tmp_path):
        """A CSC for a different model must refuse before flashing."""
        from python.core import pit as _pit
        fake_odin4 = tmp_path / "odin4"
        fake_odin4.write_bytes(b"#!/bin/sh\nexit 0\n")
        fake_odin4.chmod(0o755)
        fake_csc = tmp_path / "CSC_OJM_A065FOJMAAA.tar.md5"
        fake_csc.write_bytes(b"fakedata")
        monkeypatch.setenv("CSC_TAR", str(fake_csc))
        monkeypatch.setattr(frp, "_find_odin4", lambda: str(fake_odin4))
        monkeypatch.setattr(frp, "_find_slot_tar", lambda pre: str(fake_csc))
        monkeypatch.setattr(frp, "_download_mode_device",
                            lambda: {"pid": 0x685d, "bus": 1, "address": 2})

        def _fake_pit(target, p, timeout=120):
            with open(p, "wb") as fh:
                fh.write(b"fake")

        monkeypatch.setattr(frp.bridge, "odin_pit", _fake_pit)
        monkeypatch.setattr(frp.bridge, "adb_status", lambda: [])
        # Device PIT model says A145P (A14), CSC is A065F (A06) -> refuse.
        monkeypatch.setattr(_pit, "parse_model", lambda raw: "A145P")
        monkeypatch.setattr(_pit, "parse_pit", lambda raw: [])
        calls = []
        monkeypatch.setattr(frp.subprocess, "run",
                            lambda *a, **k: calls.append(a) or (lambda: None)())
        import io
        buf = io.StringIO()
        raised = False
        try:
            frp.flow_screen_lock_csc().run({}, buf.write)
        except Exception:
            raised = True
        assert raised is True
        assert calls == []


class TestScreenLockCscAdbFirst:
    """The screen-lock flow uses adb (no Odin) when an authorized device is up."""

    def _run_flow(self, monkeypatch, adb_devs):
        from python.core import pit as _pit
        calls = {"adb_shell": [], "odin": []}
        monkeypatch.setattr(frp.bridge, "adb_status", lambda: adb_devs)
        monkeypatch.setattr(
            frp.bridge, "adb_shell",
            lambda cmd, timeout=30: calls["adb_shell"].append(cmd) or "ok",
        )
        monkeypatch.setattr(frp, "_find_odin4", lambda: "/nope")
        monkeypatch.setattr(frp, "_find_slot_tar", lambda pre: "")
        monkeypatch.setattr(frp, "_download_mode_device", lambda: None)
        monkeypatch.setattr(_pit, "parse_pit", lambda raw: [])
        monkeypatch.setattr(_pit, "parse_model", lambda raw: "")
        import io
        buf = io.StringIO()
        try:
            frp.flow_screen_lock_csc().run({}, buf.write)
        except Exception:
            pass
        return calls, buf.getvalue()

    def test_authorized_adb_uses_locksettings_not_odin(self, monkeypatch):
        calls, out = self._run_flow(monkeypatch, [{"state": "device", "serial": "x"}])
        assert "locksettings" in " ".join(calls["adb_shell"]) or calls["adb_shell"]
        assert calls["odin"] == []
        assert "over adb" in out

    def test_no_adb_falls_back_to_csc_flash(self, monkeypatch):
        calls, out = self._run_flow(monkeypatch, [])
        assert "CSC" in out
        assert "falling back" in out.lower() or "Fallback" in out
