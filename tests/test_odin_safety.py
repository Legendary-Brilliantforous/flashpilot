"""Tests for the Samsung flashing safety gates (core.py)."""
import hashlib
import os

import pytest

import python.core.core as core
from python.core.core import (
    _bl_rev_from_bootloader,
    _bl_rev_from_name,
    _env_flag,
    _enforce_bl_downgrade_gate,
    _is_device_model,
    _is_nv_partition,
    _model_from_firmware_name,
    _models_match,
    _normalize_model,
    _tar_md5_valid,
    _write_zeroes,
)


class TestNvPartitionErase:
    """NVRAM/NVDATA partition detection and zero-fill streaming."""

    def test_is_nv_partition(self):
        for name in ("nvram", "nvdata", "nvcfg", "nvbackup", "NVRAM", "NV_DATA"):
            assert _is_nv_partition(name), name
        for name in ("vendor", "super", "boot", "system", "modem", "persist", "protect1", ""):
            assert not _is_nv_partition(name), name

    def test_write_zeroes_exact_length(self, tmp_path):
        import io
        buf = io.BytesIO()
        _write_zeroes(buf, 10 * 1024 * 1024 + 7, chunk=1 << 20)
        data = buf.getvalue()
        assert len(data) == 10 * 1024 * 1024 + 7
        assert data == b"\0" * len(data)

    def test_write_zeroes_empty(self):
        import io
        buf = io.BytesIO()
        _write_zeroes(buf, 0)
        assert buf.getvalue() == b""


class TestModelParsing:
    """Model and bootloader-revision extraction helpers."""

    def test_normalize_model(self):
        assert _normalize_model("SM-A145P") == "A145P"
        assert _normalize_model("sm-a145p") == "A145P"
        assert _normalize_model("A145P_XXX") == "A145PXXX"

    def test_model_from_firmware_name(self):
        assert _model_from_firmware_name("AP_SM-A145P_OJM_12345.tar.md5") == "SM-A145P"
        assert _model_from_firmware_name("BL_SM-A146B_1.tar") == "SM-A146B"
        assert _model_from_firmware_name("random.bin") == ""

    def test_model_from_real_firmware_no_sm_prefix(self):
        # Real archives omit the SM- prefix; the old regex wrongly picked
        # 'B1102' out of 'MQB110285214' for these files.
        assert _model_from_firmware_name(
            "AP_A145PXXSCDZE3_A145PXXSCDZE3_MQB110285214_REV00_"
            "user_low_ship_MULTI_CERT_meta_OS15.tar.md5"
        ) == "A145P"
        assert _model_from_firmware_name(
            "CSC_OJM_A145POJMCDZE3_MQB110285214_REV00_"
            "user_low_ship_MULTI_CERT.tar.md5"
        ) == "A145P"
        assert _model_from_firmware_name(
            "BL_A145PXXSCDZE3_A145PXXSCDZE3_MQB110285214_REV00_"
            "user_low_ship_MULTI_CERT.tar.md5"
        ) == "A145P"
        assert _model_from_firmware_name(
            "HOME_CSC_OJM_A145POJMCDZE3_MQB110285214_REV00_"
            "user_low_ship_MULTI_CERT.tar.md5"
        ) == "A145P"
        assert _model_from_firmware_name(
            "COMBINATION_A065F_U1_123456.tar.md5"
        ) == "A065F"

    def test_model_extraction_never_picks_sloppy_match(self):
        assert _model_from_firmware_name("MQB110285214_REV00.tar") == ""

    def test_is_device_model(self):
        assert _is_device_model("A145P") is True
        assert _is_device_model("SM-A145P") is True
        assert _is_device_model("A065F") is True
        assert _is_device_model("COM_TAR2MTK6765") is False
        assert _is_device_model("") is False

    def test_models_match(self):
        assert _models_match("SM-A145P", "A145P") is True
        assert _models_match("A145P", "a145p") is True
        assert _models_match("A145P", "A065F") is False
        # Combo PIT header labels are not verifiable device models.
        assert _models_match("A145P", "COM_TAR2MTK6765") is None
        assert _models_match("A145P", "") is None
        assert _models_match("", "A145P") is None

    def test_bl_rev_from_name(self):
        assert _bl_rev_from_name("BL_SM-A145P_REV00_user_low_ship.tar.md5") == 0
        assert _bl_rev_from_name("BL_SM-A145P_REV07_user_low_ship.tar") == 7
        assert _bl_rev_from_name("no_rev_here.tar") is None

    def test_bl_rev_from_build_id_digit(self):
        # Samsung's binary rev is the digit in the build ID; it can disagree
        # with the '_REV00_' package label (the AWC1 factory build is binary 1).
        assert _bl_rev_from_name("BL_A145PXXU1AWC1_A145PXXU1AWC1_MQB63426860_REV00_user_low_ship_MULTI_CERT.tar.md5") == 1
        assert _bl_rev_from_name("AP_A145PXXS2AWC1_meta_OS13.tar.md5") == 2
        # No build-ID digit -> falls back to the _REVxx_ label.
        assert _bl_rev_from_name("BL_A145PXXSCDZE3_A145PXXSCDZE3_MQB110285214_REV00_user_low_ship.tar.md5") == 0

    def test_bl_rev_from_bootloader(self):
        assert _bl_rev_from_bootloader("A145PXXU1BWB1") == 1
        assert _bl_rev_from_bootloader("A145PXXU7BWB1") == 7
        assert _bl_rev_from_bootloader("garbage") is None
        assert _bl_rev_from_bootloader("") is None


class TestTarMd5Verification:
    """Samsung .tar.md5 embedded-checksum validation."""

    def _make(self, tmp_path, body, corrupt=False, two_space=True, newline=True):
        md5 = hashlib.md5(body).hexdigest().encode()
        if corrupt:
            md5 = b"f" * 32
        sep = b"  " if two_space else b" "
        tail = b"\n" if newline else b""
        data = body + md5 + sep + b"AP_SM-A145P_123.tar.md5" + tail
        p = tmp_path / "fw.tar.md5"
        p.write_bytes(data)
        return str(p)

    def test_valid_checksum(self, tmp_path):
        ok, msg = _tar_md5_valid(self._make(tmp_path, b"hello tar bytes"))
        assert ok is True
        assert msg == "checksum OK"

    def test_valid_checksum_md5sum_format(self, tmp_path):
        ok, msg = _tar_md5_valid(
            self._make(tmp_path, b"hello tar bytes", two_space=True, newline=True)
        )
        assert ok is True
        assert msg == "checksum OK"

    def test_valid_checksum_single_space_no_newline(self, tmp_path):
        ok, msg = _tar_md5_valid(
            self._make(tmp_path, b"hello tar bytes", two_space=False, newline=False)
        )
        assert ok is True
        assert msg == "checksum OK"

    def test_corrupt_checksum(self, tmp_path):
        ok, msg = _tar_md5_valid(self._make(tmp_path, b"hello tar bytes", corrupt=True))
        assert ok is False
        assert "checksum mismatch" in msg

    def test_plain_tar_skips(self, tmp_path):
        p = tmp_path / "fw.tar"
        p.write_bytes(b"not an md5 archive")
        ok, msg = _tar_md5_valid(str(p))
        assert ok is True
        assert "not a .md5 archive" in msg

    def test_too_small(self, tmp_path):
        p = tmp_path / "x.tar.md5"
        p.write_bytes(b"short")
        ok, msg = _tar_md5_valid(str(p))
        assert ok is False


class TestEnforceBlDowngradeGate:
    """The native multi-partition flash BL-downgrade gate must block lower-rev
    bootloader writes unless ODIN4_FORCE_BL=1."""

    def test_no_bl_partition_skips(self):
        logs = []
        specs = [("boot", "/tmp/boot.img"), ("recovery", "/tmp/recovery.img")]
        _enforce_bl_downgrade_gate({}, logs.append, specs)
        assert logs == []

    def test_same_or_higher_rev_ok(self, monkeypatch):
        logs = []
        specs = [("bootloader", "/tmp/BL_SM-A145P_REV01_xxx.tar.md5")]
        _enforce_bl_downgrade_gate({"bl_rev": 1}, logs.append, specs)
        assert any("BL check: REV01 >= device REV01" in l for l in logs)

    def test_lower_rev_blocked_without_override(self, monkeypatch):
        monkeypatch.delenv("ODIN4_FORCE_BL", raising=False)
        logs = []
        specs = [("bootloader", "/tmp/BL_SM-A145P_REV00_xxx.tar.md5")]
        with pytest.raises(RuntimeError, match="BLOCKED"):
            _enforce_bl_downgrade_gate({"bl_rev": 1}, logs.append, specs)

    def test_lower_rev_allowed_with_override(self, monkeypatch):
        monkeypatch.setenv("ODIN4_FORCE_BL", "1")
        logs = []
        specs = [("bootloader", "/tmp/BL_SM-A145P_REV00_xxx.tar.md5")]
        _enforce_bl_downgrade_gate({"bl_rev": 1}, logs.append, specs)
        assert any("BL DOWNGRADE OVERRIDDEN" in l for l in logs)


class TestSendPitMtkRefusal:
    """Sending a PIT to a MediaTek (combo-label) device is refused up front -
    MTK Samsungs use a GPT table and their download agent has no PIT_SET flow."""

    def _combo_pit(self, tmp_path, model="COM_TAR2MTK6765"):
        hdr = bytearray(32)
        hdr[0:4] = (0x12349876).to_bytes(4, "little")
        hdr[8 : 8 + len(model)] = model.encode("ascii")
        p = tmp_path / "pit.pit"
        p.write_bytes(bytes(hdr))
        return str(p)

    def _dev(self):
        return {"pid": 0x685D, "bus": 1, "address": 2}

    def test_refuses_combo_pit_before_send(self, tmp_path, monkeypatch):
        from python.core import core

        monkeypatch.setattr(core, "_download_mode_device", lambda: self._dev())
        sent = []
        monkeypatch.setattr(
            core.bridge, "odin_send_pit",
            lambda *a, **k: sent.append(a) or '{"sent": 32}',
        )
        flow = core.flow_odin_send_pit()
        with pytest.raises(RuntimeError, match="not supported on MediaTek"):
            flow.run({"pit_file": self._combo_pit(tmp_path)}, lambda *a: None)
        assert sent == [], "bridge.odin_send_pit must not be called for MTK PITs"

    def test_real_device_model_pit_proceeds(self, tmp_path, monkeypatch):
        from python.core import core

        monkeypatch.setattr(core, "_download_mode_device", lambda: self._dev())
        sent = []
        monkeypatch.setattr(
            core.bridge, "odin_send_pit",
            lambda *a, **k: sent.append(a) or '{"sent": 32}',
        )
        flow = core.flow_odin_send_pit()
        flow.run({"pit_file": self._combo_pit(tmp_path, model="A145P")}, lambda *a: None)
        assert sent, "a real-device-model PIT should reach the actual send"


class TestOdin4TarStripping:
    """The two-space/newline .tar.md5 trailer is stripped for odin4."""

    def _make(self, tmp_path, trailer_name="BL_SM-A145P_REV01.tar"):
        body = b"\x00" * 4096
        dig = hashlib.md5(body).hexdigest()
        raw = body + f"{dig}  {trailer_name}\n".encode()
        p = tmp_path / f"{trailer_name}.md5"
        p.write_bytes(raw)
        return str(p), body

    def test_strips_trailer_to_plain_tar(self, tmp_path, monkeypatch):
        from python.core import core

        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        (tmp_path / "home" / "flashpilot").mkdir(parents=True)
        tar, body = self._make(tmp_path)
        out = core._strip_odin4_md5_trailer(tar)
        assert out.endswith(".tar")
        assert not out.endswith(".md5")
        with open(out, "rb") as f:
            assert f.read() == body

    def test_plain_tar_passthrough(self, tmp_path):
        from python.core import core

        p = tmp_path / "firmware.tar"
        p.write_bytes(b"not a real tar")
        assert core._strip_odin4_md5_trailer(str(p)) == str(p)


class TestOdin4ExactSlots:
    """GUI-triggered flashes must use ONLY the files picked in the slots -
    the ~/Downloads auto-discovery fallback is disabled (ODIN4_EXACT_SLOTS)."""

    def test_exact_mode_disables_auto_discovery(self, tmp_path, monkeypatch):
        from python.core import core

        monkeypatch.setenv("ODIN4_EXACT_SLOTS", "1")
        monkeypatch.setenv("HOME", str(tmp_path))
        d = tmp_path / "Downloads"
        d.mkdir()
        (d / "AP_test.tar").write_bytes(b"junk")
        # explicit slots win
        ap = tmp_path / "chosen.tar"
        ap.write_bytes(b"real")
        monkeypatch.setenv("AP_TAR", str(ap))
        assert core._find_slot_tar("AP") == str(ap)
        # empty slot must NOT auto-grab the newest tar in Downloads
        monkeypatch.delenv("BL_TAR", raising=False)
        assert core._find_slot_tar("BL") == ""
        assert core._find_firmware_tar() == ""

    def test_non_exact_mode_keeps_discovery(self, tmp_path, monkeypatch):
        from python.core import core

        monkeypatch.delenv("ODIN4_EXACT_SLOTS", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        d = tmp_path / "Downloads"
        d.mkdir()
        newest = d / "AP_latest.tar"
        newest.write_bytes(b"x")
        older = d / "AP_older.tar"
        older.write_bytes(b"y")
        import os
        os.utime(str(older), (1_600_000_000, 1_600_000_000))
        os.utime(str(newest), (1_700_000_000, 1_700_000_000))
        assert core._find_slot_tar("AP") == str(newest)

    def test_exact_mode_missing_slot_raises_in_flash(self, tmp_path, monkeypatch):
        from python.core import core

        monkeypatch.setenv("ODIN4_EXACT_SLOTS", "1")
        monkeypatch.setenv("HOME", str(tmp_path))
        d = tmp_path / "Downloads"
        d.mkdir()
        (d / "AP_unselected.tar").write_bytes(b"junk")
        monkeypatch.delenv("AP_TAR", raising=False)
        monkeypatch.delenv("BL_TAR", raising=False)
        monkeypatch.delenv("CP_TAR", raising=False)
        monkeypatch.delenv("CSC_TAR", raising=False)
        monkeypatch.delenv("HOME_CSC_TAR", raising=False)
        monkeypatch.delenv("USERDATA_TAR", raising=False)
        assert core._find_slot_tar("AP") == ""
        assert core._find_slot_tar("BL") == ""
        assert core._find_slot_tar("CSC") == ""
        assert core._find_slot_tar("USERDATA") == ""


class TestEnforceFlashGatesMtk:
    """The model gate reads ctx['device_model'] (never a live Odin probe, which
    wedges MTK download agents); non-device-model values skip the gate."""

    def _run(self, tmp_path, monkeypatch, dev_model):
        from python.core import core

        monkeypatch.setenv("ODIN4_EXACT_SLOTS", "1")
        fw = tmp_path / "AP_A145PXXU1AWC1_meta_OS13.tar.md5"
        fw.write_bytes(b"x")
        monkeypatch.setenv("FIRMWARE_TAR", str(fw))
        logs = []
        d = {"pid": 0x685D, "bus": 2, "address": 90}
        core._enforce_flash_gates({"device_model": dev_model}, logs.append, d)
        return logs

    def test_garbage_model_skipped(self, tmp_path, monkeypatch):
        logs = self._run(tmp_path, monkeypatch, dev_model="d")
        assert any("is not a device model" in l for l in logs)

    def test_combo_model_skipped(self, tmp_path, monkeypatch):
        logs = self._run(tmp_path, monkeypatch, dev_model="COM_TAR2MTK6765")
        assert any("is not a device model" in l for l in logs)

    def test_missing_model_skipped(self, tmp_path, monkeypatch):
        logs = self._run(tmp_path, monkeypatch, dev_model="")
        assert any("device model unavailable" in l for l in logs)

    def test_real_mismatch_still_blocked(self, tmp_path, monkeypatch):
        with pytest.raises(RuntimeError, match="MODEL MISMATCH"):
            self._run(tmp_path, monkeypatch, dev_model="A065F")
