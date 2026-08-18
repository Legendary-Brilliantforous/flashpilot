"""Tests for the Samsung flashing safety gates (frp.py)."""
import hashlib
import os

import pytest

from python.core.frp import (
    ODIN4_SHA256,
    _bl_rev_from_bootloader,
    _bl_rev_from_name,
    _env_flag,
    _is_nv_partition,
    _model_from_firmware_name,
    _normalize_model,
    _odin4_allow_unknown,
    _odin4_hash_ok,
    _odin4_reboot,
    _odin4_redownload,
    _odin4_verbose,
    _reboot_redownload_flags,
    _tar_md5_valid,
    _verified_odin4,
    _write_zeroes,
)


class TestOdin4FlagDefaults:
    """The unsafe flags must be OFF by default and opt-in only."""

    def test_allow_unknown_off_by_default(self, monkeypatch):
        monkeypatch.delenv("ODIN4_ALLOW_UNKNOWN", raising=False)
        assert _odin4_allow_unknown() == []

    def test_allow_unknown_opt_in(self, monkeypatch):
        monkeypatch.setenv("ODIN4_ALLOW_UNKNOWN", "1")
        assert _odin4_allow_unknown() == ["--allow-unknown"]

    def test_allow_unknown_explicit_off(self, monkeypatch):
        monkeypatch.setenv("ODIN4_ALLOW_UNKNOWN", "0")
        assert _odin4_allow_unknown() == []

    def test_reboot_off_by_default(self, monkeypatch):
        monkeypatch.delenv("ODIN4_REBOOT", raising=False)
        assert _odin4_reboot() == []

    def test_reboot_opt_in(self, monkeypatch):
        monkeypatch.setenv("ODIN4_REBOOT", "on")
        assert _odin4_reboot() == ["--reboot"]


class TestOdin4AdvancedFlags:
    """Re-download, verbose and generic env-flag helpers are opt-in only."""

    def test_redownload_off_by_default(self, monkeypatch):
        monkeypatch.delenv("ODIN4_REDOWNLOAD", raising=False)
        assert _odin4_redownload() == []

    def test_redownload_opt_in(self, monkeypatch):
        monkeypatch.setenv("ODIN4_REDOWNLOAD", "1")
        assert _odin4_redownload() == ["--redownload"]

    def test_verbose_off_by_default(self, monkeypatch):
        monkeypatch.delenv("ODIN4_VERBOSE", raising=False)
        assert _odin4_verbose() == []

    def test_verbose_opt_in(self, monkeypatch):
        monkeypatch.setenv("ODIN4_VERBOSE", "true")
        assert _odin4_verbose() == ["--verbose"]

    def test_env_flag_defaults_false(self, monkeypatch):
        monkeypatch.delenv("ODIN4_X", raising=False)
        assert _env_flag("ODIN4_X") is False

    def test_env_flag_truthy(self, monkeypatch):
        monkeypatch.setenv("ODIN4_X", "YES")
        assert _env_flag("ODIN4_X") is True

    def test_reboot_redownload_mutually_exclusive(self, monkeypatch):
        monkeypatch.setenv("ODIN4_REBOOT", "1")
        monkeypatch.setenv("ODIN4_REDOWNLOAD", "1")
        with pytest.raises(RuntimeError, match="mutually exclusive"):
            _reboot_redownload_flags(lambda m: None)

    def test_reboot_redownload_neither(self, monkeypatch):
        monkeypatch.delenv("ODIN4_REBOOT", raising=False)
        monkeypatch.delenv("ODIN4_REDOWNLOAD", raising=False)
        assert _reboot_redownload_flags(lambda m: None) == []

    def test_reboot_redownload_redownload_wins_solo(self, monkeypatch):
        monkeypatch.delenv("ODIN4_REBOOT", raising=False)
        monkeypatch.setenv("ODIN4_REDOWNLOAD", "1")
        assert _reboot_redownload_flags(lambda m: None) == ["--redownload"]


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


class TestOdin4BinaryVerification:
    """The bundled odin4 binary must match the pinned SHA-256."""

    @staticmethod
    def bundled_path():
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(here, "root", "tools", "odin4")

    def test_pinned_hash_matches_bundled_binary(self):
        with open(self.bundled_path(), "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == ODIN4_SHA256

    def test_bundled_binary_verified(self):
        assert _odin4_hash_ok(self.bundled_path()) is True

    def test_foreign_binary_rejected(self, tmp_path):
        bad = tmp_path / "odin4"
        bad.write_bytes(b"\x7fELF not the real thing" + b"\0" * 64)
        assert _odin4_hash_ok(str(bad)) is False

    def test_foreign_binary_raises_unless_trusted(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ODIN4_SKIP_HASH", raising=False)
        bad = tmp_path / "odin4"
        bad.write_bytes(b"\x7fELF junk")
        with pytest.raises(RuntimeError, match="SHA-256"):
            _verified_odin4(str(bad))
        monkeypatch.setenv("ODIN4_SKIP_HASH", "1")
        assert _verified_odin4(str(bad)) == str(bad)

    def test_missing_binary_not_ok(self, tmp_path):
        assert _odin4_hash_ok(str(tmp_path / "nope")) is False


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

    def test_bl_rev_from_name(self):
        assert _bl_rev_from_name("BL_SM-A145P_REV00_user_low_ship.tar.md5") == 0
        assert _bl_rev_from_name("BL_SM-A145P_REV07_user_low_ship.tar") == 7
        assert _bl_rev_from_name("no_rev_here.tar") is None

    def test_bl_rev_from_bootloader(self):
        assert _bl_rev_from_bootloader("A145PXXU1BWB1") == 1
        assert _bl_rev_from_bootloader("A145PXXU7BWB1") == 7
        assert _bl_rev_from_bootloader("garbage") is None
        assert _bl_rev_from_bootloader("") is None


class TestTarMd5Verification:
    """Samsung .tar.md5 embedded-checksum validation."""

    def _make(self, tmp_path, body, corrupt=False):
        md5 = hashlib.md5(body).hexdigest().encode()
        if corrupt:
            md5 = b"f" * 32
        data = body + md5 + b" " + b"AP_SM-A145P_123.tar.md5"
        p = tmp_path / "fw.tar.md5"
        p.write_bytes(data)
        return str(p)

    def test_valid_checksum(self, tmp_path):
        ok, msg = _tar_md5_valid(self._make(tmp_path, b"hello tar bytes"))
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
