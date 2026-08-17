"""Tests for PIT parsing (pit.py)."""
import pytest
from python.core.pit import parse_pit, parse_model, PitEntry


class TestPITParsing:
    """Test PIT binary parsing round-trips and edge cases."""

    def test_parse_model_from_firmware_pit(self):
        """Model string extraction matches Odin behavior."""
        raw = bytes.fromhex(
            "7698341239000000"  # magic + count=57
            "434f4d5f544152324d544b36373635000000000000000000"  # COM_TAR2MTK6765 (16 + 8 nulls = 24B)
        )
        model = parse_model(raw)
        assert model == "COM_TAR2MTK6765"

    def test_parse_model_empty(self):
        """Empty/invalid PIT returns empty string."""
        assert parse_model(b"") == ""
        assert parse_model(b"x" * 31) == ""
        # Wrong magic
        raw = bytes.fromhex("0000000039000000" + "434f4d5f544152324d544b363736350000000000000000")
        assert parse_model(raw) == ""

    def test_parse_pit_valid(self):
        """Parse the real firmware PIT (A14M_MEA_OPEN.pit)."""
        import os
        pit_path = os.path.expanduser("~/Downloads/CSC_OJM_A145POJMCDZE3_MQB110285214_REV00_user_low_ship_MULTI_CERT.tar.md5")
        # Extract PIT from tar if not already extracted
        import tarfile, tempfile
        with tempfile.TemporaryDirectory() as td:
            with tarfile.open(pit_path, "r") as tf:
                for m in tf.getmembers():
                    if m.name.endswith(".pit"):
                        tf.extract(m, td)
                        raw = open(os.path.join(td, m.name), "rb").read()
                        break
        entries = parse_pit(raw)
        assert len(entries) == 57
        # Check first entry (bootloader)
        e0 = entries[0]
        assert e0.name == "bootloader"
        assert e0.flash_filename == "preloader.img"
        assert e0.device_type == 0x50
        # Check last entry (sgpt)
        e_last = entries[-1]
        assert e_last.name == "sgpt"
        assert e_last.flash_filename == "sgpt.img"

    def test_parse_pit_invalid_magic(self):
        """Bad magic raises ValueError."""
        with pytest.raises(ValueError, match="bad PIT magic"):
            parse_pit(b"BADMAGIC" + b"\x00" * 24)

    def test_parse_pit_truncated(self):
        """Truncated PIT raises ValueError."""
        with pytest.raises(ValueError, match="PIT too short"):
            parse_pit(b"\x76\x98\x34\x12")

    def test_pit_entry_size_bytes(self):
        """Entry size calculation matches block_size * block_count."""
        # Create minimal valid entry: 8 u32 header + name + flash_filename + fota_filename + file_size
        import struct
        data = struct.pack("<8I", 1, 0x50, 0x100, 1, 1, 512, 10, 0)  # block_size=512, block_count=10
        data += b"test\0" + b"\0" * 28  # name (32 bytes)
        data += b"test.img\0" + b"\0" * 24  # flash_filename (32 bytes)
        data += b"\0" * 32  # fota_filename (32 bytes)
        data += struct.pack("<I", 0)  # file_size (4 bytes) -> 132 total
        entry = PitEntry(data, 0)
        assert entry.size_bytes() == 5120

    def test_pit_entry_is_flashable(self):
        """Empty name entries are not flashable."""
        import struct
        data = struct.pack("<8I", 1, 0x50, 0x100, 1, 1, 512, 10, 0)
        data += b"\0" * 32  # empty name
        data += b"test.img\0" + b"\0" * 24
        data += b"\0" * 32
        data += struct.pack("<I", 0)  # file_size (4 bytes) -> 132 total
        entry = PitEntry(data, 0)
        assert not entry.is_flashable()


class TestPITConstants:
    """Verify PIT constants match between Python and Rust."""

    def test_header_size(self):
        from python.core.pit import HEADER_SIZE, ENTRY_SIZE
        assert HEADER_SIZE == 32
        assert ENTRY_SIZE == 132

    def test_magic(self):
        from python.core.pit import PIT_MAGIC
        assert PIT_MAGIC == 0x12349876