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
        """Known PIDs map to correct stages."""
        assert pid_stage(0x2000) == "brom"
        assert pid_stage(0x0003) == "preloader"
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