"""Tests for PIT parsing (pit.py).

Fixtures use the single true layout (verified against Heimdall libpit,
Thor's extended parser and the repo's real device dumps):
  header = 28 bytes: magic@0 count@4 Unknown[8]@8 Project[8]@16 Reserved@24
  entry  = 132 bytes: binType devType ident attr updAttr blockSizeOrOffset@20
           blockCount@24 fileOffset@28 fileSize@32 name@36 flash@68 delta@100
"""
import os
import struct

import pytest

from python.core.pit import (
    ENTRY_SIZE,
    HEADER_SIZE,
    PIT_MAGIC,
    PitEntry,
    find_overlaps,
    find_partition,
    human_size,
    normalize_part_name,
    parse_header,
    parse_model,
    parse_pit,
    pit_diff,
    pit_diff_report,
    pit_health,
    pit_map,
    pit_report,
    pit_style,
    significant_overlaps,
    validate_and_sanitize_pit,
    validate_pit,
)

PIT_DIR = os.path.join(os.path.dirname(__file__), "..", "pit")


def make_entry(name="", flash="", fota="", identifier=0, dev_type=0x50,
               binary_type=1, attributes=1, update_attributes=0,
               block_offset=0, block_count=0):
    e = bytearray(ENTRY_SIZE)
    struct.pack_into("<9I", e, 0, binary_type, dev_type, identifier,
                     attributes, update_attributes, block_offset,
                     block_count, 0, 0)  # 8 fields + obsolete fileOffset + fileSize
    struct.pack_into("<I", e, 32, 0)  # obsolete fileSize
    e[36:36 + len(name)] = name.encode()
    e[68:68 + len(flash)] = flash.encode()
    e[100:100 + len(fota)] = fota.encode()
    return bytes(e)


def make_pit(entries):
    """entries: list of kwargs dicts (or raw 132-byte entries) -> raw PIT."""
    pit = bytearray(HEADER_SIZE)
    pit[0:4] = PIT_MAGIC.to_bytes(4, "little")
    pit[4:8] = len(entries).to_bytes(4, "little")
    pit[8:16] = b"COM_TAR2"
    pit[16:24] = b"MTK6765\x00"
    for spec in entries:
        if isinstance(spec, (bytes, bytearray)):
            entry = bytes(spec)
        else:
            entry = make_entry(**spec)
        pit.extend(entry)
    return bytes(pit)


class TestPITParsing:
    """Test PIT binary parsing round-trips and edge cases."""

    def test_parse_header(self):
        model, unknown, project, reserved = parse_header(make_pit([]))
        assert model == "COM_TAR2MTK6765"
        assert unknown == "COM_TAR2"
        assert project == "MTK6765"
        assert reserved == 0

    def test_parse_model_from_firmware_pit(self):
        """Model string extraction matches Odin behavior."""
        raw = bytes.fromhex(
            "7698341239000000"  # magic + count=57
            "434f4d5f544152324d544b36373635000000000000000000"  # COM_TAR2MTK6765
        )
        assert parse_model(raw) == "COM_TAR2MTK6765"

    def test_parse_model_empty(self):
        # Too-short input (< 28-byte header)
        assert parse_model(b"") == ""
        assert parse_model(b"x" * 27) == ""
        # No magic validation in parse_model - it just reads the string area
        raw = bytes.fromhex("0000000039000000" + "434f4d5f544152324d544b363736350000000000000000")
        assert parse_model(raw) == "COM_TAR2MTK6765"

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

    def test_true_layout_field_positions(self):
        """Regression: numeric fields must decode unshifted.

        The old parser used a 32-byte header, shifting every int one field
        late while names still landed correctly - masking the bug.
        """
        entry = make_entry(name="boot", flash="boot.img", identifier=80,
                           binary_type=0, dev_type=2, block_offset=0,
                           block_count=8192)
        parsed = PitEntry(entry, 0)
        assert parsed.binary_type == 0
        assert parsed.device_type == 2
        assert parsed.identifier == 80
        assert parsed.block_offset == 0
        assert parsed.block_count == 8192
        assert parsed.size_bytes() == 8192 * 512

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
    """Heimdall PrintPit flag semantics (old-style attribute bitmasks)."""

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


class TestRealDevicePITs:
    """Regressions on actual device dumps shipped in the repo."""

    def _load(self, fname):
        path = os.path.join(PIT_DIR, fname)
        if not os.path.exists(path):
            pytest.skip(f"real PIT fixture not present: {fname}")
        return open(path, "rb").read()

    def test_a14m_bootloader_decodes_correctly(self):
        """The A14M dump must yield REAL field values, not shifted ones."""
        raw = self._load("A14M_MEA_OPEN.pit")
        entries = parse_pit(raw)
        assert len(entries) > 10  # 57 declared in header
        first = find_partition(entries, "bootloader")
        assert first is not None
        assert first.flash_filename == "preloader.img"
        # True values (old shifted parser reported bt=2 dt=0x50 id=2)
        assert first.binary_type == 0      # AP
        assert first.device_type == 2      # MMC/eMMC
        assert first.identifier == 80
        assert first.block_offset == 0     # start block
        assert first.block_count == 8192   # 4 MB preloader region
        assert first.size_bytes() == 4 * 1024 * 1024

    def test_partitions_chain_without_overlap(self):
        """pgpt+pit+md5hdr chain contiguously; only meta containment overlaps.

        On real MTK dumps the 'bootloader' entry spans the whole preloader
        area and legitimately CONTAINS pgpt/pit/md5hdr - that must not be
        flagged as corruption.
        """
        from python.core.pit import significant_overlaps
        raw = self._load("A14M_MEA_OPEN.pit")
        entries = parse_pit(raw)
        assert significant_overlaps(entries) == []
        by_name = {e.name: e for e in entries}
        pgpt, pitt = by_name["pgpt"], by_name["pit"]
        md5 = by_name["md5hdr"]
        assert (pgpt.block_offset, pgpt.block_count) == (0, 34)
        assert pitt.block_offset == pgpt.block_offset + pgpt.block_count
        assert md5.block_offset == pitt.block_offset + pitt.block_count

    def test_report_renders_real_dumps(self):
        for fname in ("A14M_MEA_OPEN.pit", "device_2_84.pit"):
            rep = pit_report(self._load(fname))
            assert "model=COM_TAR2MTK6765" in rep
            assert "bootloader" in rep
            assert "total:" in rep
            assert "overlapping" not in rep


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
        assert "model=COM_TAR2MTK6765" in rep
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
        """28-byte header per Heimdall kHeaderDataSize / Thor's parser."""
        assert HEADER_SIZE == 28
        assert ENTRY_SIZE == 132

    def test_magic(self):
        assert PIT_MAGIC == 0x12349876


class TestPITIntelligence:
    """Forensic validation, style detection, diff and storage map."""

    def test_validate_healthy_pit_is_ok(self):
        pit = make_pit([
            dict(name="boot", flash="boot.img", identifier=1,
                 block_offset=1024, block_count=512),
            dict(name="system", flash="system.img", identifier=2,
                 block_offset=1536, block_count=4096),
        ])
        h = validate_pit(pit)
        assert h["verdict"] == "ok"
        codes = {f["code"] for f in h["findings"]}
        assert "OVERLAP" not in codes and "DUPLICATE_IDENTIFIER" not in codes

    def test_validate_bad_magic_fails(self):
        h = validate_pit(b"BADMAGIC" + b"\0" * 24)
        assert h["verdict"] == "fail"
        assert any(f["code"] == "BAD_MAGIC" for f in h["findings"])

    def test_validate_truncated_fails(self):
        raw = make_pit([dict(name=f"p{i}", identifier=i + 1) for i in range(4)])
        h = validate_pit(raw[:60])  # cut mid-entries
        assert any(f["code"] == "TRUNCATED" for f in h["findings"])

    def test_validate_identifier_zero_and_duplicates_fail(self):
        pit = make_pit([
            dict(name="a", identifier=0),
            dict(name="b", identifier=7),
            dict(name="c", identifier=7),
        ])
        codes = {f["code"] for f in validate_pit(pit)["findings"]}
        assert "IDENTIFIER_ZERO" in codes
        assert "DUPLICATE_IDENTIFIER" in codes

    def test_validate_data_overlap_fails_meta_ok(self):
        # data-vs-data overlap -> fail
        bad = make_pit([
            dict(name="a", identifier=1, block_offset=1024, block_count=512),
            dict(name="b", identifier=2, block_offset=1280, block_count=512),
        ])
        h = validate_pit(bad)
        assert h["verdict"] == "fail"
        assert any(f["code"] == "OVERLAP" for f in h["findings"])

        # bootloader containing meta regions -> info only (real MTK dumps)
        ok = make_pit([
            dict(name="bootloader", identifier=80, block_offset=0, block_count=8192),
            dict(name="pgpt", identifier=70, block_offset=0, block_count=34),
            dict(name="pit", identifier=71, block_offset=34, block_count=32),
        ])
        h2 = validate_pit(ok)
        assert h2["verdict"] == "ok"
        assert not any(f["code"] == "OVERLAP" for f in h2["findings"])

    def test_style_detection(self):
        # varying start blocks -> new-style (like real MTK dumps)
        new_pit = make_pit([
            dict(name="pgpt", identifier=70, block_offset=0, block_count=34),
            dict(name="efs", identifier=1, block_offset=34, block_count=100),
        ])
        assert pit_style(new_pit) == "new"
        # uniform blockSizeOrOffset -> old-style
        old_pit = make_pit([
            dict(name="a", identifier=1, block_offset=512, block_count=10),
            dict(name="b", identifier=2, block_offset=512, block_count=20),
        ])
        assert pit_style(old_pit) == "old"

    def test_health_summary(self):
        raw = self_real_dump()
        if raw is None:
            pytest.skip("real PIT fixture not present")
        h = pit_health(raw)
        assert h["verdict"] in ("ok", "warn")
        assert "style=new" in h["summary"]
        assert h["stats"]["parsed_count"] > 10

    def test_map_renders_with_legend(self):
        pit = make_pit([
            dict(name="boot", identifier=1, block_offset=0, block_count=512),
            dict(name="cache", identifier=2, block_offset=512, block_count=256),
        ])
        m = pit_map(pit)
        assert "[BBB" in m and "CCC" in m  # uppercase initials, meta = lowercase
        assert "boot" in m and "cache" in m

    def test_diff_added_removed_changed(self):
        old = make_pit([
            dict(name="boot", identifier=1, block_offset=0, block_count=512),
            dict(name="oldpart", identifier=9, block_offset=512, block_count=64),
        ])
        new = make_pit([
            dict(name="boot", identifier=1, block_offset=0, block_count=1024),  # resized
            dict(name="vendor", identifier=5, block_offset=512, block_count=64),  # added
        ])
        d = pit_diff(old, new)
        assert d["added"] == ["vendor"]
        assert d["removed"] == ["oldpart"]
        assert len(d["changed"]) == 1
        assert d["changed"][0]["name"] == "boot"
        assert "block_count" in d["changed"][0]["changes"]
        rep = pit_diff_report(old, new)
        assert "added:" in rep and "removed:" in rep and "changed: boot" in rep

    def test_diff_identical(self):
        pit = make_pit([dict(name="boot", identifier=1)])
        assert "no changes" in pit_diff_report(pit, pit)


def self_real_dump():
    """Load the repo's real A14M dump if present."""
    path = os.path.join(PIT_DIR, "A14M_MEA_OPEN.pit")
    if os.path.exists(path):
        return open(path, "rb").read()
    return None
