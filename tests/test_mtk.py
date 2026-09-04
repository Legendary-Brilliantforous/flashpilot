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
