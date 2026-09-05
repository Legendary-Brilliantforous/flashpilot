"""Tests for MTK chip detection and mapping (mtk.py)."""
import pytest
from python.core.mtk import chip_name, stage_label, pid_stage, CHIP_NAMES, BOOT_STAGE


class TestMTKChipNames:
    """Test MediaTek hw_code to chip name mapping."""

    def test_known_chips(self):
        """All known hw_codes resolve to expected names."""
        assert chip_name(0x0769) == "MT6768/MT6769 (Helio G80 / G85 - used in Galaxy A05/A06)"
        assert chip_name(0x0833) == "MT6833 (Dimensity 700 / 810)"
        assert chip_name(0x0766) == "MT6765 (Helio G25 / G35 / G36 / G37)"

    def test_unknown_chip(self):
        """Unknown hw_code returns generic format."""
        assert chip_name(0xFFFF) == "MediaTek SoC (hw code 0xFFFF)"


class TestMTKBootStages:
    """Test PID to boot stage mapping."""

    def test_pid_stages(self):
        """Known PIDs map to correct stages (mtkclient convention:
        0003=BootROM, 2000=preloader - verified live against an
        'MT65xx Preloader' 0e8d:2000 device)."""
        assert pid_stage(0x0003) == "brom"
        assert pid_stage(0x2000) == "preloader"
        assert pid_stage(0x0004) == "da"
        assert pid_stage(0x1004) == "da"
        assert pid_stage(0x0a0a) == "mtk-adb"
        assert pid_stage(0x1234) == "other"

    def test_stage_labels(self):
        """Stage labels contain expected descriptions."""
        name, note = stage_label("brom")
        assert name == "MediaTek BootROM (held state)"
        assert "first code" in note.lower()
        name, note = stage_label("preloader")
        assert name == "MediaTek Preloader"
        assert "Download Agent" in note
        name, note = stage_label("da")
        assert name == "MediaTek Download Agent (DA)"
        assert "flashing stage" in note.lower()
        name, note = stage_label("mtk-adb")
        assert name == "MediaTek ADB composite"
        assert "Android" in note


class TestMTKConstants:
    """Verify constant dictionaries are complete."""

    def test_chip_names_not_empty(self):
        assert len(CHIP_NAMES) >= 10

    def test_boot_stage_not_empty(self):
        assert len(BOOT_STAGE) == 4

class TestMtkBromBackup:
    """The BROM backup flow registration + safety behavior."""

    def test_registered_in_flows(self):
        from python.core import core
        assert "mtk_brom_backup" in core.FLOWS
        flow = core.FLOWS["mtk_brom_backup"]()
        assert "backup" in flow.name.lower()
        assert "bootloader" in flow.name.lower()

    def test_registered_under_read_device_info_mtk_brom(self):
        from python.core import core
        assert "mtk_brom_backup" in core.JOBS["Read Device Info"]["MTK BROM"]
        assert "mtk_brom_backup" in core.JOBS["Read Device Info"]["MTK"]

    def test_requires_da(self, monkeypatch):
        from python.core import core
        monkeypatch.setattr(core, "_find_mtk_da", lambda: "")
        import io
        buf = io.StringIO()
        with pytest.raises(RuntimeError, match="DA binary required"):
            core.FLOWS["mtk_brom_backup"]().run({}, buf.write)

    def test_waits_for_device_and_reports_bootloop_hint(self, monkeypatch):
        from python.core import core
        monkeypatch.setattr(core, "_find_mtk_da", lambda: "/tmp/da.bin")
        monkeypatch.setattr(core, "_wait_mtk_brom_target", lambda log, timeout=120: (None, None))
        import io
        buf = io.StringIO()
        with pytest.raises(RuntimeError, match="no MediaTek BROM/preloader"):
            core.FLOWS["mtk_brom_backup"]().run({}, buf.write)
        out = buf.getvalue()
        assert "Boot-looping" in out
        assert "Waiting for a MediaTek BROM / preloader device" in out

    def test_mtk_retry_waits_for_next_window_after_device_loss(self, monkeypatch):
        """If a bridge op loses the device mid-run, the retry waits for the
        next preloader window and calls fn again."""
        from python.core import core
        import io
        buf = io.StringIO()
        calls = []
        monkeypatch.setattr(
            core.mtk, "find_mtk",
            lambda: [{"vid": 0x0e8d, "pid": 0x0003, "bus": 1, "address": 2}],
        )
        monkeypatch.setattr(
            core.bridge, "BridgeError", Exception,
        )

        def flaky(target):
            calls.append(target)
            if len(calls) == 1:
                raise Exception("device disappeared")
            return "ok"

        result = core._mtk_retry(buf.write, "flaky op", flaky, timeout=10)
        assert result == "ok"
        assert len(calls) == 2
        assert "attempt 2" in buf.getvalue()

    def test_mtk_retry_aborts_on_permanent_failure(self, monkeypatch):
        """'partition not found' style errors must not retry for the full
        timeout - they abort immediately."""
        from python.core import core
        import io
        buf = io.StringIO()
        monkeypatch.setattr(
            core.mtk, "find_mtk",
            lambda: [{"vid": 0x0e8d, "pid": 0x0003, "bus": 1, "address": 2}],
        )
        monkeypatch.setattr(core.bridge, "BridgeError", Exception)

        def fail(target):
            raise Exception("partition 'tee' not found in device GPT")

        with pytest.raises(Exception, match="not found"):
            core._mtk_retry(buf.write, "read", fail, timeout=10,
                           abort_on=("not found",))
        assert "attempt 1" in buf.getvalue()
        assert "attempt 2" not in buf.getvalue()


class TestWaitMtkBromTarget:
    """The waiter prefers the stable held BROM over the preloader window."""

    def test_prefers_brom_over_preloader(self, monkeypatch):
        from python.core import core
        import io
        buf = io.StringIO()
        monkeypatch.setattr(
            core.mtk, "find_mtk",
            lambda: [
                {"vid": 0x0e8d, "pid": 0x2000, "bus": 1, "address": 5},
                {"vid": 0x0e8d, "pid": 0x0003, "bus": 1, "address": 2},
            ],
        )
        target, stage = core._wait_mtk_brom_target(buf.write, timeout=5)
        assert target == "1:2"
        assert stage == "brom"

    def test_falls_back_to_preloader(self, monkeypatch):
        from python.core import core
        import io
        buf = io.StringIO()
        monkeypatch.setattr(
            core.mtk, "find_mtk",
            lambda: [{"vid": 0x0e8d, "pid": 0x2000, "bus": 1, "address": 5}],
        )
        target, stage = core._wait_mtk_brom_target(buf.write, timeout=5)
        assert target == "1:5"
        assert stage == "preloader"


class TestMtkCrashBrom:
    """Crash-preloader-into-BROM flow registration + behavior."""

    def test_registered_in_flows_and_jobs(self):
        from python.core import core
        assert "mtk_crash_brom" in core.FLOWS
        assert "BROM" in core.FLOWS["mtk_crash_brom"]().name
        assert "mtk_crash_brom" in core.JOBS["Read Device Info"]["MTK BROM"]
        assert "mtk_crash_brom" in core.JOBS["Detect Devices"]["MTK BROM"]

    def test_noop_when_already_in_brom(self, monkeypatch):
        from python.core import core
        import io
        buf = io.StringIO()
        monkeypatch.setattr(
            core.mtk, "find_mtk",
            lambda: [{"vid": 0x0e8d, "pid": 0x0003, "bus": 1, "address": 2}],
        )
        result = core.FLOWS["mtk_crash_brom"]().run({}, buf.write)
        assert result == [True]
        assert "Already in held BROM" in buf.getvalue()


class TestMtkAuthFlash:
    """Auth-bypass flash flow: DA gating, bypass fallback order, flash dispatch."""

    def _brom(self, monkeypatch):
        from python.core import core
        monkeypatch.setattr(
            core.mtk, "find_mtk",
            lambda: [{"vid": 0x0e8d, "pid": 0x0003, "bus": 1, "address": 2}],
        )

    def test_registered_in_flows_and_flash_job(self):
        from python.core import core
        assert "mtk_auth_flash" in core.FLOWS
        assert "auth" in core.FLOWS["mtk_auth_flash"]().name.lower()
        assert "mtk_auth_flash" in core.JOBS["Flash Firmware"]["MTK"]
        assert "mtk_auth_flash" in core.JOBS["Flash Firmware"]["MTK BROM"]

    def test_requires_da(self, monkeypatch):
        from python.core import core
        import io
        monkeypatch.setenv("MTK_DA", "")
        monkeypatch.setattr(core, "_find_mtk_da", lambda: "")
        buf = io.StringIO()
        with pytest.raises(RuntimeError, match="DA binary required"):
            core.FLOWS["mtk_auth_flash"]().run({}, buf.write)

    def test_auto_falls_through_to_working_mode_then_flashes(self, monkeypatch, tmp_path):
        from python.core import core
        import io
        da = tmp_path / "MTK_AllInOne_DA.bin"
        da.write_bytes(b"D" * 2048)
        fw = tmp_path / "fw"
        fw.mkdir()
        scat = tmp_path / "MT6768_Android_scatter.txt"
        scat.write_text("scatter")
        monkeypatch.setenv("MTK_DA", str(da))
        monkeypatch.setenv("MTK_SCATTER", str(scat))
        monkeypatch.setenv("MTK_FW_DIR", str(fw))
        monkeypatch.delenv("MTK_BYPASS_MODE", raising=False)
        monkeypatch.delenv("MTK_FRP_ONLY", raising=False)
        self._brom(monkeypatch)
        calls = []

        def fake_run(args, timeout=60):
            calls.append(args)
            if args[0] == "mtk-bypass" and args[3] == "brom_exploit":
                raise core.bridge.BridgeError("auth reject")
            return "ok"

        monkeypatch.setattr(core.bridge, "_run", fake_run)
        monkeypatch.setattr(core.bridge, "BridgeError", Exception)
        buf = io.StringIO()
        assert core.FLOWS["mtk_auth_flash"]().run({}, buf.write) == [True]
        bypass_modes = [a[3] for a in calls if a[0] == "mtk-bypass"]
        assert bypass_modes[0] == "brom_exploit"
        assert "sla_bypass" in bypass_modes  # fell through after first failure
        flash_calls = [a for a in calls if a[0] == "mtk-flash"]
        assert len(flash_calls) == 1
        assert flash_calls[0][2:5] == [str(da), str(scat), str(fw)]

    def test_frp_only_uses_gpt_wipe(self, monkeypatch, tmp_path):
        from python.core import core
        import io
        da = tmp_path / "MTK_AllInOne_DA.bin"
        da.write_bytes(b"D" * 2048)
        monkeypatch.setenv("MTK_DA", str(da))
        monkeypatch.setenv("MTK_BYPASS_MODE", "standard")
        monkeypatch.setenv("MTK_FRP_ONLY", "1")
        self._brom(monkeypatch)
        calls = []
        monkeypatch.setattr(core.bridge, "_run", lambda a, timeout=60: calls.append(a) or "ok")
        monkeypatch.setattr(core.bridge, "BridgeError", Exception)
        buf = io.StringIO()
        assert core.FLOWS["mtk_auth_flash"]().run({}, buf.write) == [True]
        assert [a[0] for a in calls] == ["mtk-bypass", "mtk-frp-gpt"]

    def test_all_modes_fail_aborts(self, monkeypatch, tmp_path):
        from python.core import core
        import io
        da = tmp_path / "MTK_AllInOne_DA.bin"
        da.write_bytes(b"D" * 2048)
        monkeypatch.setenv("MTK_DA", str(da))
        monkeypatch.delenv("MTK_BYPASS_MODE", raising=False)
        monkeypatch.delenv("MTK_FRP_ONLY", raising=False)
        self._brom(monkeypatch)
        monkeypatch.setattr(
            core.bridge, "_run",
            lambda a, timeout=60: (_ for _ in ()).throw(core.bridge.BridgeError("nope")),
        )
        monkeypatch.setattr(core.bridge, "BridgeError", Exception)
        buf = io.StringIO()
        with pytest.raises(RuntimeError, match="auth bypass failed"):
            core.FLOWS["mtk_auth_flash"]().run({}, buf.write)


class TestMtkVerify:
    def test_registered(self):
        from python.core import core
        assert "mtk_verify" in core.FLOWS
        assert "mtk_verify" in core.JOBS["Read Device Info"]["MTK BROM"]
        assert "qcom_verify" in core.FLOWS
        assert "qcom_verify" in core.JOBS["Read Device Info"]["EDL"]

    def test_parse_part_entries(self):
        from python.core import core
        assert core._parse_part_entries("frp=/tmp/a.img, nvdata=/tmp/b.img") == [
            ("frp", "/tmp/a.img"), ("nvdata", "/tmp/b.img")]
        assert core._parse_part_entries("  , bad , = ,x=") == []
        assert core._parse_part_entries("") == []

    def test_mtk_verify_flow_calls_bridge(self, monkeypatch, tmp_path):
        from python.core import core
        import io
        da = tmp_path / "da.bin"
        da.write_bytes(b"D" * 2048)
        monkeypatch.setenv("MTK_DA", str(da))
        monkeypatch.setenv("MTK_VERIFY_PARTS", "frp=/tmp/frp.img")
        monkeypatch.setattr(
            core.mtk, "find_mtk",
            lambda: [{"vid": 0x0e8d, "pid": 0x0003, "bus": 1, "address": 2}],
        )
        calls = []
        monkeypatch.setattr(core.bridge, "_run", lambda a, timeout=60: calls.append(a) or "verify: 1 partition(s) MATCH")
        monkeypatch.setattr(core.bridge, "BridgeError", Exception)
        buf = io.StringIO()
        assert core.FLOWS["mtk_verify"]().run({}, buf.write) == [True]
        assert calls[0][:3] == ["mtk-verify-part", "1:2", str(da)]
        assert calls[0][3] == "frp=/tmp/frp.img"

    def test_mtk_verify_requires_parts(self, monkeypatch, tmp_path):
        from python.core import core
        import io
        da = tmp_path / "da.bin"
        da.write_bytes(b"D" * 2048)
        monkeypatch.setenv("MTK_DA", str(da))
        monkeypatch.delenv("MTK_VERIFY_PARTS", raising=False)
        buf = io.StringIO()
        with pytest.raises(RuntimeError, match="MTK_VERIFY_PARTS"):
            core.FLOWS["mtk_verify"]().run({}, buf.write)

    def test_simlock_patch_verifies_write(self, monkeypatch, tmp_path):
        from python.core import core
        import io
        recipe = {"partition": "nvdata", "offset": 8,
                  "lock_bytes": b"\x01\x00\x00\x00",
                  "unlocked_bytes": b"\x00\x00\x00\x00"}
        monkeypatch.setattr(core, "_MTK_SIMLOCK_RECIPES", {"SM-A065F": dict(recipe)})
        monkeypatch.setenv("MTK_SIMLOCK_PATCH", "1")
        img = tmp_path / "nvdata.img"
        img.write_bytes(b"\x00" * 8 + b"\x01\x00\x00\x00" + b"\x00" * 16)
        calls = []
        monkeypatch.setattr(core.bridge, "_run", lambda a, timeout=60: calls.append(a) or "ok")
        monkeypatch.setattr(core.bridge, "BridgeError", Exception)
        monkeypatch.setattr(core.bridge, "mtk_verify_part", lambda *a, **k: calls.append(("verify",) + a) or "MATCH")
        logs = []
        core._mtk_simlock_patch({"model": "SM-A065F"}, logs.append, "auto", "auto",
                                [("nvdata", str(img))])
        kinds = [c[0] if isinstance(c, tuple) else c[0] for c in calls]
        assert "mtk-flash-part" in kinds
        assert "verify" in kinds

    def test_simlock_patch_aborts_on_verify_mismatch(self, monkeypatch, tmp_path):
        from python.core import core
        import io
        recipe = {"partition": "nvdata", "offset": 8,
                  "lock_bytes": b"\x01\x00\x00\x00",
                  "unlocked_bytes": b"\x00\x00\x00\x00"}
        monkeypatch.setattr(core, "_MTK_SIMLOCK_RECIPES", {"SM-A065F": dict(recipe)})
        monkeypatch.setenv("MTK_SIMLOCK_PATCH", "1")
        img = tmp_path / "nvdata.img"
        img.write_bytes(b"\x00" * 8 + b"\x01\x00\x00\x00" + b"\x00" * 16)

        def boom(a, timeout=60):
            if a[0] == "mtk-flash-part":
                return "ok"
            raise Exception("MISMATCH")

        monkeypatch.setattr(core.bridge, "_run", boom)
        monkeypatch.setattr(core.bridge, "BridgeError", Exception)

        def boom_verify(*a, **k):
            raise core.bridge.BridgeError("MISMATCH at offset 0x8")

        monkeypatch.setattr(core.bridge, "mtk_verify_part", boom_verify)
        with pytest.raises(RuntimeError, match="VERIFY FAILED"):
            core._mtk_simlock_patch({"model": "SM-A065F"}, lambda m: None, "auto", "auto",
                                    [("nvdata", str(img))])
