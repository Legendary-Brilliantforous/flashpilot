"""Tests for PIT parsing (pit.py).

Two real-world entry layouts exist (both 132 bytes): classic Loke/Exynos
(strings @36/68/100, obsolete fileSize@32) and Samsung-MTK DA-synthesized
(strings @32/64/96). Fixtures cover both plus the repo's real device dumps.
"""
import os
import struct

import pytest

from python.core.pit import (
    ENTRY_SIZE,
    HEADER_SIZE,
    PIT_MAGIC,
    PitEntry,
    detect_name_offset,
    find_overlaps,
    find_partition,
    human_size,
    normalize_part_name,
    parse_model,
    parse_pit,
    pit_layout,
    pit_report,
    validate_and_sanitize_pit,
)

PIT_DIR = os.path.join(os.path.dirname(__file__), "..", "pit")


def make_entry(name="", flash="", fota="", identifier=0, dev_type=0x50,
               binary_type=1, attributes=1, update_attributes=0,
               block_offset=0, block_count=0, name_off=32):
    e = bytearray(ENTRY_SIZE)
    struct.pack_into("<8I", e, 0, binary_type, dev_type, identifier,
                     attributes, update_attributes, block_offset, block_count, 0)
    if name_off == 36:
        struct.pack_into("<I", e, 32, 0)  # obsolete file size (classic only)
    e[name_off:name_off + len(name)] = name.encode()
    e[name_off + 32:name_off + 32 + len(flash)] = flash.encode()
    e[name_off + 64:name_off + 64 + len(fota)] = fota.encode()
    return bytes(e)


def make_pit(entries):
    """entries: list of kwargs dicts (or bytes) -> raw PIT."""
    pit = bytearray(HEADER_SIZE)
    pit[0:4] = PIT_MAGIC.to_bytes(4, "little")
    pit[4:8] = len(entries).to_bytes(4, "little")
    pit[8:8 + len("TESTMODEL")] = b"TESTMODEL"
    for i, spec in enumerate(entries):
        if isinstance(spec, (bytes, bytearray)):
            entry = bytes(spec)
        else:
            entry = make_entry(**spec)
        pit.extend(entry)
    return bytes(pit)


class TestPITParsing:
    """Test PIT binary parsing round-trips and edge cases."""

    def test_parse_model_from_firmware_pit(self):
        """Model string extraction matches Odin behavior."""
        raw = bytes.fromhex(
            "7698341239000000"  # magic + count=57
            "434f4d5f544152324d544b36373635000000000000000000"  # COM_TAR2MTK6765
        )
        assert parse_model(raw) == "COM_TAR2MTK6765"

    def test_parse_model_empty(self):
        assert parse_model(b"") == ""
        assert parse_model(b"x" * 31) == ""
        # Wrong magic
        raw = bytes.fromhex("0000000039000000" + "434f4d5f544152324d544b363736350000000000000000")
        assert parse_model(raw) == ""

    def test_parse_pit_valid(self):
        """Parse a synthetic valid PIT and check field extraction."""
        pit = make_pit([
            dict(name="bootloader", flash="preloader.img", identifier=0, block_count=8),
            dict(name="system", flash="system.img", identifier=1, block_count=2048),
            dict(name="sgpt", flash="sgpt.img", identifier=2, block_count=64),
        ])
        entries = parse_pit(pit)
        assert len(entries) == 3
        e0 = entries[0]
        assert e0.name == "bootloader"
        assert e0.flash_filename == "preloader.img"
        assert e0.device_type == 0x50
        e_last = entries[-1]
        assert e_last.name == "sgpt"
        assert e_last.flash_filename == "sgpt.img"

    def test_layout_autodetection(self):
        """Both real layouts must parse: MTK-DA (names@32) and classic
        Loke (names@36). Wrong-layout reads yield empty names, which is
        the silent failure mode this guards against."""
        mtk = make_pit([dict(name="boot", flash="boot.img"),
                        dict(name="cache", flash="cache.img")])
        assert pit_layout(mtk) == "mtk"
        entries = parse_pit(mtk)
        assert [e.name for e in entries] == ["boot", "cache"]

        classic = make_pit([
            dict(name="boot", flash="boot.img", name_off=36),
            dict(name="cache", flash="cache.img", name_off=36),
        ])
        assert pit_layout(classic) == "classic"
        entries = parse_pit(classic)
        assert [e.name for e in entries] == ["boot", "cache"]
        # classic layout carries the obsolete fileSize field at +32
        assert entries[0].file_size == 0

    def test_real_device_pits_in_repo(self):
        """Regression against actual device dumps shipped in pit/.

        A14M_MEA_OPEN.pit was dumped from a Samsung MTK device - it uses
        the MTK-DA layout. These tests fail if layout detection or entry
        parsing regresses.
        """
        path = os.path.join(PIT_DIR, "A14M_MEA_OPEN.pit")
        if not os.path.exists(path):
            pytest.skip("real PIT fixture not present")
        raw = open(path, "rb").read()
        assert pit_layout(raw) == "mtk"
        entries = parse_pit(raw)
        assert len(entries) > 10  # 57 declared in header
        first = find_partition(entries, "bootloader")
        assert first is not None
        assert first.flash_filename == "preloader.img"
        assert first.identifier == 2
        assert first.block_offset == 0x2000

    def test_real_device_pit_report_renders(self):
        for fname in ("A14M_MEA_OPEN.pit", "device_2_84.pit"):
            path = os.path.join(PIT_DIR, fname)
            if not os.path.exists(path):
                continue
            rep = pit_report(open(path, "rb").read())
            assert f"layout=mtk" in rep
            assert "bootloader" in rep
            assert "total:" in rep

    def test_parse_pit_invalid_magic(self):
        with pytest.raises(ValueError, match="bad PIT magic"):
            parse_pit(b"BADMAGIC" + b"\x00" * 28)

    def test_parse_pit_truncated(self):
        with pytest.raises(ValueError, match="PIT too short"):
            parse_pit(b"\x76\x98\x34\x12")

    def test_pit_entry_size_bytes(self):
        """Entry size is block_count * 512-byte sectors."""
        assert PitEntry(make_entry(name="test", block_count=10), 0).size_bytes() == 5120

    def test_pit_entry_is_flashable(self):
        assert not PitEntry(make_entry(name=""), 0).is_flashable()

    def test_junk_names_not_flashable(self):
        """Whitespace-only and dot-prefixed entries are padding, not partitions."""
        for junk in ("   ", "..trash", "."):
            entry = PitEntry(make_entry(name=junk, flash="x.img"), 0)
            assert not entry.is_flashable(), junk


class TestPITFlags:
    """Heimdall PrintPit flag semantics."""

    @staticmethod
    def _entry(**kw):
        return PitEntry(make_entry(**kw), 0)

    def test_readonly_vs_write(self):
        # attribute bit0 clear => Read-Only; set => Read/Write
        assert self._entry(attributes=0).is_read_only is True
        assert self._entry(attributes=1).is_read_only is False

    def test_stl_flag(self):
        assert self._entry(attributes=0x3).is_stl is True
        assert self._entry(attributes=0x1).is_stl is False

    def test_fota_and_secure(self):
        assert self._entry(update_attributes=1).has_fota is True
        assert self._entry(update_attributes=3).is_secure is True
        assert self._entry(update_attributes=0).has_fota is False

    def test_labels(self):
        ap = self._entry(binary_type=0, dev_type=2)
        cp = self._entry(binary_type=1, dev_type=0)
        assert ap.binary_type_label == "AP" and ap.device_type_label == "MMC"
        assert cp.binary_type_label == "CP" and cp.device_type_label == "OneNAND"


class TestPITValidation:
    """Archive-vs-PIT compatibility checks (Odin-style sanitization)."""

    def _make_pit(self, names):
        return make_pit([dict(name=n) for n in names])

    def test_archive_suffix_matches_pit(self):
        """'boot.img' in the archive must match PIT entry 'boot'."""
        ok, missing, extra, model = validate_and_sanitize_pit(
            self._make_pit(["boot", "system", "cache"]),
            ["boot.img", "system.img", "cache.img"],
        )
        assert ok is True
        assert extra == []

    def test_case_insensitive_match(self):
        pit = self._make_pit(["BOOT", "system"])
        ok, _, extra, _ = validate_and_sanitize_pit(pit, ["boot"])
        assert ok is True

    def test_genuinely_extra_partition_flags(self):
        pit = self._make_pit(["boot", "system"])
        ok, _, extra, _ = validate_and_sanitize_pit(pit, ["boot", "modembin"])
        assert ok is False
        assert extra == ["modembin"]

    def test_normalize_part_name(self):
        assert normalize_part_name("Boot.IMG") == "boot"
        assert normalize_part_name(" modem.bin ") == "modem"
        assert normalize_part_name("vbmeta") == "vbmeta"
        # double suffix strips iteratively
        assert normalize_part_name("radio.img.lz4") == "radio"


class TestPITTools:
    """find_partition / overlaps / report."""

    def test_find_partition_by_name_and_file(self):
        pit = make_pit([
            dict(name="boot", flash="boot.img", identifier=0),
            dict(name="modem", flash="modem.bin", identifier=1),
        ])
        assert find_partition(pit, "BOOT").identifier == 0
        assert find_partition(pit, "boot.img").identifier == 0
        assert find_partition(pit, "modem.bin").identifier == 1
        assert find_partition(pit, "nope") is None

    def test_find_overlaps_detects_collision(self):
        entries = parse_pit(make_pit([
            dict(name="a", block_offset=1024, block_count=512),
            dict(name="b", block_offset=1536, block_count=512),
            dict(name="c", block_offset=1400, block_count=64),  # collides with a
        ]))
        overlaps = find_overlaps(entries)
        assert ("a", "c", 64) in overlaps

    def test_find_overlaps_clean_chain(self):
        entries = parse_pit(make_pit([
            dict(name="a", block_offset=1024, block_count=512),
            dict(name="b", block_offset=1536, block_count=512),
        ]))
        assert find_overlaps(entries) == []

    def test_human_size(self):
        assert human_size(0) == "0 B"
        assert human_size(512) == "512 B"
        assert human_size(512 * 1024).endswith("KB")

    def test_pit_report_renders(self):
        pit = make_pit([
            dict(name="boot", flash="boot.img", identifier=1,
                 attributes=0, update_attributes=1, block_offset=1024,
                 block_count=16384),
            dict(name="cache", flash="cache.img", identifier=5,
                 attributes=1, block_offset=17408, block_count=8192),
        ])
        rep = pit_report(pit)
        assert "model=TESTMODEL" in rep
        assert "boot" in rep and "RO" in rep and "FOTA" in rep
        assert "RW" in rep
        assert "total:" in rep
        assert "overlapping" not in rep

    def test_pit_report_warns_on_overlap(self):
        pit = make_pit([
            dict(name="a", block_offset=1024, block_count=4096),
            dict(name="b", block_offset=2048, block_count=4096),
        ])
        rep = pit_report(pit)
        assert "WARNING" in rep and "overlapping" in rep


class TestPITConstants:
    """Verify PIT constants match between Python and Rust."""

    def test_header_size(self):
        assert HEADER_SIZE == 32
        assert ENTRY_SIZE == 132

    def test_magic(self):
        assert PIT_MAGIC == 0x12349876
