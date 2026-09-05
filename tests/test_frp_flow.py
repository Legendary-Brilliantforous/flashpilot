"""Tests for Flow/Step framework and cancellation (frp.py)."""
import pytest
import time
from python.core.core import Flow, Step, request_cancel, clear_cancel, cancel_requested, FlowCancelled


class TestFlowCancellation:
    """Test cooperative cancellation flow."""

    def test_cancel_requested_flow(self):
        clear_cancel()
        assert not cancel_requested()
        request_cancel()
        assert cancel_requested()
        clear_cancel()
        assert not cancel_requested()

    def test_step_cancelled_before_run(self):
        clear_cancel()
        request_cancel()
        step = Step("test", lambda ctx, log: "should not run")
        with pytest.raises(FlowCancelled, match="cancelled before step test"):
            step.run({}, lambda m: None)

    def test_step_cancelled_during_run(self):
        clear_cancel()
        def slow_step(ctx, log):
            time.sleep(0.1)
            request_cancel()
            return "done"
        step = Step("slow", slow_step)
        # Should not raise during run (checks at start and end)
        result = step.run({}, lambda m: None)
        assert result == "done"

    def test_flow_cancelled_between_steps(self):
        clear_cancel()
        results = []
        def step1(ctx, log):
            results.append("1")
            request_cancel()
            return "1"
        def step2(ctx, log):
            results.append("2")
            return "2"
        flow = Flow("test", [Step("s1", step1), Step("s2", step2)])
        with pytest.raises(FlowCancelled):
            flow.run({}, lambda m: None)
        assert results == ["1"]  # step2 never runs

    def test_flow_normal_completion(self):
        clear_cancel()
        results = []
        flow = Flow("test", [
            Step("a", lambda ctx, log: results.append("a")),
            Step("b", lambda ctx, log: results.append("b")),
        ])
        flow.run({}, lambda m: None)
        assert results == ["a", "b"]


class TestFlowContext:
    """Test context passing through flows."""

    def test_context_mutable(self):
        clear_cancel()
        ctx = {"counter": 0}
        def inc(ctx, log):
            ctx["counter"] += 1
        flow = Flow("test", [Step("inc", inc), Step("inc2", inc)])
        flow.run(ctx, lambda m: None)
        assert ctx["counter"] == 2


class TestRunGuard:
    """The GUI run-guard serializes operations PER DEVICE: two flows on the
    same phone can never overlap (so two destructive writes can't collide
    and a second clear_cancel() can't discard the in-flight cancel
    request), while different phones may run in parallel."""

    def test_second_flow_blocked_while_first_runs(self):
        from python.gui.qt_app import _flow_start, _flow_end, _flow_busy_msg
        assert _flow_start("Odin flash", destructive=True)
        assert not _flow_start("MTK flash", destructive=True)
        assert "still running" in _flow_busy_msg()
        _flow_end()

    def test_lock_released_after_end(self):
        from python.gui.qt_app import _flow_start, _flow_end
        assert _flow_start("op", destructive=False)
        _flow_end()
        assert _flow_start("op2", destructive=False)
        _flow_end()

    def test_busy_msg_mentions_blocking_flow(self):
        from python.gui.qt_app import _flow_start, _flow_end, _flow_busy_msg
        assert _flow_start("Carrier lock check", destructive=False)
        assert "Carrier lock check" in _flow_busy_msg()
        _flow_end()

    def test_different_devices_run_in_parallel(self):
        from python.gui.qt_app import _flow_start, _flow_end, _flows_running
        assert _flow_start("Flash A", destructive=True, key="adb:AAA")
        assert _flow_start("Flash B", destructive=True, key="adb:BBB")
        assert _flows_running() == 2
        assert not _flow_start("Flash A2", destructive=True, key="adb:AAA")
        _flow_end(key="adb:AAA")
        assert _flow_start("Flash A3", destructive=True, key="adb:AAA")
        _flow_end(key="adb:AAA")
        _flow_end(key="adb:BBB")
        assert _flows_running() == 0

    def test_busy_msg_names_same_device_op(self):
        from python.gui.qt_app import _flow_start, _flow_end, _flow_busy_msg
        assert _flow_start("Odin flash", destructive=True, key="adb:AAA")
        assert "Odin flash" in _flow_busy_msg(key="adb:AAA")
        _flow_end(key="adb:AAA")

class TestNewSecurityFrpPack:
    """QR provisioning + Alliance Shield registration and behavior."""

    def test_registered_in_flows_and_frp_job(self):
        from python.core import core
        for key in ("frp_qr_provision", "frp_alliance"):
            assert key in core.FLOWS
        assert "frp_qr_provision" in core.JOBS["Remove FRP"]["ADB"]
        assert "frp_alliance" in core.JOBS["Remove FRP"]["ADB"]
        assert "QR" in core.FLOWS["frp_qr_provision"]().name
        assert "Alliance" in core.FLOWS["frp_alliance"]().name

    def test_qr_provision_generates_files(self, tmp_path, monkeypatch):
        from python.core import core
        import io
        out = tmp_path / "frp_qr"
        out.mkdir()
        monkeypatch.setenv("FRP_QR_OUT_DIR", str(out))
        monkeypatch.setattr(core.bridge, "adb_status", lambda: [])
        buf = io.StringIO()
        core.FLOWS["frp_qr_provision"]().run({}, buf.write)
        pngs = list(out.rglob("provisioning_qr_*.png"))
        assert pngs, buf.getvalue()
        assert any("frp_testdpc" in p.name for p in pngs)

    def test_alliance_uses_adb_when_authorized(self, monkeypatch):
        from python.core import core
        import io
        monkeypatch.setattr(
            core.bridge, "adb_status",
            lambda: [{"serial": "X", "state": "device", "extra": ""}],
        )
        calls = []
        monkeypatch.setattr(
            core.bridge, "adb_shell",
            lambda cmd, timeout=30: calls.append(cmd) or "ok",
        )
        buf = io.StringIO()
        core.FLOWS["frp_alliance"]().run({}, buf.write)
        assert any("setupwizard" in c for c in calls)


class TestQcnInspectors:
    """NV browser + EFS explorer registration and offline behavior."""

    def test_registered(self):
        from python.core import core
        for key in ("qcn_nv_browser", "qcn_efs_explorer"):
            assert key in core.FLOWS
            assert key in core.JOBS["QCN / Modem"]["ADB"]
            assert key in core.JOBS["QCN / Modem"]["EDL"]

    def test_nv_browser_finds_ascii_imei(self, tmp_path, monkeypatch):
        from python.core import core
        import io
        (tmp_path / "modemst1.img").write_bytes(
            b"\x00" * 64 + b"356938035643809" + b"\x00" * 64)
        monkeypatch.setenv("QCN_BACKUP_DIR", str(tmp_path))
        monkeypatch.delenv("TARGET_IMEI", raising=False)
        buf = io.StringIO()
        core.FLOWS["qcn_nv_browser"]().run({}, buf.write)
        assert "356938035643809" in buf.getvalue()
        assert "0x40" in buf.getvalue()

    def test_nv_browser_requires_backup_dir(self, tmp_path, monkeypatch):
        from python.core import core
        import io
        monkeypatch.setenv("QCN_BACKUP_DIR", str(tmp_path / "missing"))
        buf = io.StringIO()
        with pytest.raises(RuntimeError, match="QCN_BACKUP_DIR"):
            core.FLOWS["qcn_nv_browser"]().run({}, buf.write)

    def test_efs_explorer_lists_and_extracts(self, tmp_path, monkeypatch):
        import tarfile
        from python.core import core
        import io
        tgz = tmp_path / "efs.tgz"
        with tarfile.open(tgz, "w:gz") as tf:
            import io as _io
            data = b"mps_code=OJM\n"
            ti = tarfile.TarInfo("mps_code.dat")
            ti.size = len(data)
            tf.addfile(ti, _io.BytesIO(data))
        monkeypatch.setenv("QCN_EFS_TAR", str(tgz))
        monkeypatch.delenv("QCN_EFS_EXTRACT", raising=False)
        buf = io.StringIO()
        core.FLOWS["qcn_efs_explorer"]().run({}, buf.write)
        assert "mps_code.dat" in buf.getvalue()
        out = tmp_path / "out"
        out.mkdir()
        monkeypatch.setenv("QCN_EFS_OUT", str(out))
        monkeypatch.setenv("QCN_EFS_EXTRACT", "mps_code.dat")
        buf = io.StringIO()
        core.FLOWS["qcn_efs_explorer"]().run({}, buf.write)
        assert (out / "mps_code.dat").read_bytes() == b"mps_code=OJM\n"


class TestQcnRestoreVerify:
    def test_restore_verifies_each_partition(self, tmp_path, monkeypatch):
        from python.core import core
        import io
        from python.core import qcn as _qcn
        src = tmp_path / "qcn"
        src.mkdir()
        (src / "modemst1.img").write_bytes(b"M" * 4096)
        prog = tmp_path / "prog.mbn"
        prog.write_bytes(b"P" * 128)
        monkeypatch.setenv("QCN_BACKUP_DIR", str(src))
        monkeypatch.setenv("QCOM_PROGRAMMER", str(prog))
        calls = []
        monkeypatch.setattr(core.bridge, "qcom_flash_one",
                            lambda t, n, f, s, c: calls.append(("flash", n)) or "ok")
        monkeypatch.setattr(core.bridge, "qcom_verify_part",
                            lambda t, e, timeout=900: calls.append(("verify", e[0][0])) or "MATCH")
        monkeypatch.setattr(core.bridge, "BridgeError", Exception)
        buf = io.StringIO()
        _qcn.flow_qcn_restore().run({"experimental_ack": True}, buf.write)
        assert ("flash", "modemst1") in calls
        assert ("verify", "modemst1") in calls
        # verify follows its flash
        fi = calls.index(("flash", "modemst1"))
        vi = calls.index(("verify", "modemst1"))
        assert vi == fi + 1

    def test_restore_aborts_on_verify_mismatch(self, tmp_path, monkeypatch):
        from python.core import core
        import io
        from python.core import qcn as _qcn
        src = tmp_path / "qcn"
        src.mkdir()
        (src / "modemst1.img").write_bytes(b"M" * 4096)
        prog = tmp_path / "prog.mbn"
        prog.write_bytes(b"P" * 128)
        monkeypatch.setenv("QCN_BACKUP_DIR", str(src))
        monkeypatch.setenv("QCOM_PROGRAMMER", str(prog))
        monkeypatch.setattr(core.bridge, "qcom_flash_one", lambda t, n, f, s, c: "ok")

        def boom(t, e, timeout=900):
            raise core.bridge.BridgeError("MISMATCH at offset 0x0")

        monkeypatch.setattr(core.bridge, "qcom_verify_part", boom)
        monkeypatch.setattr(core.bridge, "BridgeError", Exception)
        buf = io.StringIO()
        with pytest.raises(RuntimeError, match="VERIFY FAILED"):
            _qcn.flow_qcn_restore().run({"experimental_ack": True}, buf.write)
