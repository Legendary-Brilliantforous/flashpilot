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
        from python.core import frp
        assert "mtk_brom_backup" in frp.FLOWS
        flow = frp.FLOWS["mtk_brom_backup"]()
        assert "backup" in flow.name.lower()
        assert "bootloader" in flow.name.lower()

    def test_registered_under_read_device_info_mtk_brom(self):
        from python.core import frp
        assert "mtk_brom_backup" in frp.JOBS["Read device info"]["MTK BROM"]
        assert "mtk_brom_backup" in frp.JOBS["Read device info"]["MTK"]

    def test_requires_da(self, monkeypatch):
        from python.core import frp
        monkeypatch.setattr(frp, "_find_mtk_da", lambda: "")
        import io
        buf = io.StringIO()
        with pytest.raises(RuntimeError, match="DA binary required"):
            frp.FLOWS["mtk_brom_backup"]().run({}, buf.write)

    def test_waits_for_device_and_reports_bootloop_hint(self, monkeypatch):
        from python.core import frp
        monkeypatch.setattr(frp, "_find_mtk_da", lambda: "/tmp/da.bin")
        monkeypatch.setattr(frp, "_wait_mtk_brom_target", lambda log, timeout=120: (None, None))
        import io
        buf = io.StringIO()
        with pytest.raises(RuntimeError, match="no MediaTek BROM/preloader"):
            frp.FLOWS["mtk_brom_backup"]().run({}, buf.write)
        out = buf.getvalue()
        assert "Boot-looping" in out
        assert "Waiting for a MediaTek BROM / preloader device" in out

    def test_mtk_retry_waits_for_next_window_after_device_loss(self, monkeypatch):
        """If a bridge op loses the device mid-run, the retry waits for the
        next preloader window and calls fn again."""
        from python.core import frp
        import io
        buf = io.StringIO()
        calls = []
        monkeypatch.setattr(
            frp.mtk, "find_mtk",
            lambda: [{"vid": 0x0e8d, "pid": 0x0003, "bus": 1, "address": 2}],
        )
        monkeypatch.setattr(
            frp.bridge, "BridgeError", Exception,
        )

        def flaky(target):
            calls.append(target)
            if len(calls) == 1:
                raise Exception("device disappeared")
            return "ok"

        result = frp._mtk_retry(buf.write, "flaky op", flaky, timeout=10)
        assert result == "ok"
        assert len(calls) == 2
        assert "attempt 2" in buf.getvalue()

    def test_mtk_retry_aborts_on_permanent_failure(self, monkeypatch):
        """'partition not found' style errors must not retry for the full
        timeout - they abort immediately."""
        from python.core import frp
        import io
        buf = io.StringIO()
        monkeypatch.setattr(
            frp.mtk, "find_mtk",
            lambda: [{"vid": 0x0e8d, "pid": 0x0003, "bus": 1, "address": 2}],
        )
        monkeypatch.setattr(frp.bridge, "BridgeError", Exception)

        def fail(target):
            raise Exception("partition 'tee' not found in device GPT")

        with pytest.raises(Exception, match="not found"):
            frp._mtk_retry(buf.write, "read", fail, timeout=10,
                           abort_on=("not found",))
        assert "attempt 1" in buf.getvalue()
        assert "attempt 2" not in buf.getvalue()
