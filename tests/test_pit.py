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
        """Parse a synthetic valid PIT and check field extraction."""
        def entry(name, fname, identifier, dev_type, block_size, block_count):
            e = bytearray(132)
            e[4:8] = (dev_type).to_bytes(4, "little")  # device_type
            e[8:12] = (identifier).to_bytes(4, "little")
            e[20:24] = (block_size).to_bytes(4, "little")
            e[24:28] = (block_count).to_bytes(4, "little")
            e[128:132] = (512).to_bytes(4, "little")  # file_size
            e[32:32 + len(name)] = name.encode()
            e[64:64 + len(fname)] = fname.encode()
            return e

        pit = bytearray(32 + 132 * 3)
        pit[0:4] = (0x12349876).to_bytes(4, "little")  # magic
        pit[4:8] = (3).to_bytes(4, "little")  # entry count
        pit[8:12] = (132).to_bytes(4, "little")  # entry size
        pit[12:16] = (0).to_bytes(4, "little")  # device type
        pit[16:20] = (0).to_bytes(4, "little")  # device type2
        pit[28:32] = (1).to_bytes(4, "little")  # block size
        pit[32:36] = (1).to_bytes(4, "little")  # block count
        for i, (n, f, ident, dt, bs, bc) in enumerate([
            ("bootloader", "preloader.img", 0, 0x50, 512, 8),
            ("system", "system.img", 1, 0x50, 512, 2048),
            ("sgpt", "sgpt.img", 2, 0x50, 512, 64),
        ]):
            pit[32 + i * 132:32 + (i + 1) * 132] = entry(n, f, ident, dt, bs, bc)

        entries = parse_pit(bytes(pit))
        assert len(entries) == 3
        e0 = entries[0]
        assert e0.name == "bootloader"
        assert e0.flash_filename == "preloader.img"
        assert e0.device_type == 0x50
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

    def test_junk_names_not_flashable(self):
        """Whitespace-only and dot-prefixed entries are padding, not partitions."""
        import struct
        for junk in ("   ", "..trash", "."):
            data = struct.pack("<8I", 1, 0x50, 0x100, 1, 1, 512, 10, 0)
            data += junk.encode() + b"\0" * (32 - len(junk))
            data += b"x.img\0" + b"\0" * 27
            data += b"\0" * 32
            data += struct.pack("<I", 0)
            assert not PitEntry(data, 0).is_flashable(), junk


class TestPITValidation:
    """Archive-vs-PIT compatibility checks (Odin-style sanitization)."""

    def _make_pit(self, names):
        import struct
        pit = bytearray(32 + 132 * max(1, len(names)))
        pit[0:4] = (0x12349876).to_bytes(4, "little")
        pit[4:8] = len(names).to_bytes(4, "little")
        for i, n in enumerate(names):
            e = bytearray(132)
            e[32:32 + len(n)] = n.encode()
            pit[32 + i * 132:32 + (i + 1) * 132] = e
        return bytes(pit)

    def test_archive_suffix_matches_pit(self):
        """'boot.img' in the archive must match PIT entry 'boot'."""
        from python.core.pit import validate_and_sanitize_pit
        pit = self._make_pit(["boot", "system", "cache"])
        ok, missing, extra, model = validate_and_sanitize_pit(
            pit, ["boot.img", "system.img", "cache.img"]
        )
        assert ok is True
        assert extra == []

    def test_case_insensitive_match(self):
        """Case-only differences ('BOOT' vs 'boot') must not flag."""
        from python.core.pit import validate_and_sanitize_pit
        pit = self._make_pit(["BOOT", "system"])
        ok, _, extra, _ = validate_and_sanitize_pit(pit, ["boot"])
        assert ok is True

    def test_genuinely_extra_partition_flags(self):
        """A partition truly absent from the PIT still flags incompatible."""
        from python.core.pit import validate_and_sanitize_pit
        pit = self._make_pit(["boot", "system"])
        ok, _, extra, _ = validate_and_sanitize_pit(pit, ["boot", "modembin"])
        assert ok is False
        assert extra == ["modembin"]

    def test_normalize_part_name(self):
        from python.core.pit import normalize_part_name
        assert normalize_part_name("Boot.IMG") == "boot"
        assert normalize_part_name(" modem.bin ") == "modem"
        assert normalize_part_name("vbmeta") == "vbmeta"
        # double suffix strips iteratively
        assert normalize_part_name("radio.img.lz4") == "radio"


class TestPITConstants:
    """Verify PIT constants match between Python and Rust."""

    def test_header_size(self):
        from python.core.pit import HEADER_SIZE, ENTRY_SIZE
        assert HEADER_SIZE == 32
        assert ENTRY_SIZE == 132

    def test_magic(self):
        from python.core.pit import PIT_MAGIC
        assert PIT_MAGIC == 0x12349876