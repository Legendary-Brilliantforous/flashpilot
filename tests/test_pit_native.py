"""Cross-implementation equivalence: native Rust PIT engine vs local Python.

The public `pit.*` API prefers the bridge and falls back locally when the
binary is absent. These tests pin both paths together so shared rules
(suffix table, meta sets, overlap geometry, messages) can never drift:
real dumps, synthetic edge cases, and error mapping, compared exactly.
"""

import os
import struct
import tempfile

import pytest

from python.core import bridge
from python.core import pit

DUMP_DIR = os.path.join(os.path.dirname(__file__), "..", "build", "pit")
BRIDGE_OK = bridge.BRIDGE.exists()

needs_bridge = pytest.mark.skipif(not BRIDGE_OK, reason="bridge not built")


def make_entry(name="", flash="", fota="", identifier=0, dev_type=0x50,
               binary_type=1, attributes=1, update_attributes=0,
               block_offset=0, block_count=0):
    e = bytearray(pit.ENTRY_SIZE)
    struct.pack_into("<9I", e, 0, binary_type, dev_type, identifier,
                     attributes, update_attributes, block_offset,
                     block_count, 0, 0)
    struct.pack_into("<I", e, 32, 0)
    e[36:36 + len(name)] = name.encode()
    e[68:68 + len(flash)] = flash.encode()
    e[100:100 + len(fota)] = fota.encode()
    return bytes(e)


def make_pit(entries):
    out = bytearray(pit.HEADER_SIZE)
    out[0:4] = pit.PIT_MAGIC.to_bytes(4, "little")
    out[4:8] = len(entries).to_bytes(4, "little")
    out[8:16] = b"COM_TAR2"
    out[16:24] = b"MTK6765\x00"
    for spec in entries:
        out.extend(spec if isinstance(spec, (bytes, bytearray)) else make_entry(**spec))
    return bytes(out)


def dump_paths():
    if not os.path.isdir(DUMP_DIR):
        return []
    return sorted(
        os.path.join(DUMP_DIR, f) for f in os.listdir(DUMP_DIR) if f.endswith(".pit")
    )


def entry_key(e):
    if isinstance(e, dict):
        return (e["name"], e["identifier"], e["block_size"], e["block_count"],
                e["flash_filename"], e["binary_type"], e["device_type"],
                e["attributes"], e["update_attributes"])
    return (e.name, e.identifier, e.block_size, e.block_count,
            e.flash_filename, e.binary_type, e.device_type,
            e.attributes, e.update_attributes)


@needs_bridge
@pytest.mark.parametrize("fname", ["A14M_MEA_OPEN.pit", "device_2_82.pit", "device_2_84.pit"])
def test_entries_match_on_dumps(fname):
    path = os.path.join(DUMP_DIR, fname)
    if not os.path.isfile(path):
        pytest.skip(f"real PIT fixture not present: {fname}")
    raw = open(path, "rb").read()
    native = bridge.pit_parse(path)["entries"]
    local = pit._parse_pit_local(raw)
    assert [entry_key(e) for e in native] == [entry_key(e) for e in local]
    assert bridge.pit_model(path)["model"] == pit._parse_header_local(raw)[0]


@needs_bridge
@pytest.mark.parametrize("fname", ["A14M_MEA_OPEN.pit", "device_2_82.pit", "device_2_84.pit"])
def test_health_matches_on_dumps(fname):
    path = os.path.join(DUMP_DIR, fname)
    if not os.path.isfile(path):
        pytest.skip(f"real PIT fixture not present: {fname}")
    raw = open(path, "rb").read()
    assert bridge.pit_health(path) == pit._pit_health_local(raw)


@needs_bridge
def test_find_matches_on_dumps():
    paths = dump_paths()
    if not paths:
        pytest.skip("real PIT fixtures not present")
    raw = open(paths[0], "rb").read()
    local_entries = pit._parse_pit_local(raw)
    for name in ["bootloader", "BOOT", "boot.img", "preloader.img", "nope"]:
        with tempfile.NamedTemporaryFile(suffix=".pit", delete=False) as tf:
            tf.write(raw)
            tmppath = tf.name
        try:
            nd = bridge.pit_find(tmppath, name)
            ld = pit._find_in(local_entries, name)
        finally:
            os.unlink(tmppath)
        if ld is None:
            assert nd is None
        else:
            assert nd is not None and entry_key(nd) == entry_key(ld)


@needs_bridge
def test_suffix_table_matches():
    """Every normalize suffix, both cases, through find on both engines."""
    raws = [
        ("Boot.IMG", "boot.img"),
        ("MODEM.BIN", "modem.bin"),
        ("abl.elf", "abl.elf"),
        ("radio.img.lz4", "radio.img"),
        ("system.zst", "system.zst"),
        ("cache.zstd", "cache.zstd"),
        ("persist.raw", "persist.raw"),
        ("x.mbn", "x.mbn"),
        ("dtbo.ext4", "dtbo.ext4"),
    ]
    specs = [dict(name=f"part{i}", flash=flash, identifier=100 + i,
                  block_offset=i * 100, block_count=10)
             for i, (_, flash) in enumerate(raws)]
    raw = make_pit(specs)
    with tempfile.NamedTemporaryFile(suffix=".pit", delete=False) as tf:
        tf.write(raw)
        tmppath = tf.name
    try:
        local_entries = pit._parse_pit_local(raw)
        for query, _ in raws:
            nd = bridge.pit_find(tmppath, query)
            ld = pit._find_in(local_entries, query)
            assert (nd is None) == (ld is None)
            if ld is not None:
                assert entry_key(nd) == entry_key(ld)
    finally:
        os.unlink(tmppath)


@needs_bridge
def test_meta_and_error_findings_match():
    """Duplicate/zero ids, junk names, meta containment — exact findings."""
    junk = make_entry(name="", flash="", identifier=0)  # filtered (not flashable)
    junk_name = bytearray(make_entry(name="ok", identifier=5, block_offset=0, block_count=10))
    junk_name[36:40] = b"\xff\xfeAB"  # non-printable -> INVALID_NAME
    specs = [
        dict(name="bootloader", identifier=80, block_offset=0, block_count=1000),
        dict(name="pgpt", identifier=70, block_offset=0, block_count=34),
        dict(name="dup_a", identifier=9, block_offset=2000, block_count=10),
        dict(name="dup_b", identifier=9, block_offset=3000, block_count=10),
        dict(name="zeroid", identifier=0, block_offset=4000, block_count=10),
        bytes(junk_name),
        junk,
    ]
    raw = make_pit(specs)
    with tempfile.NamedTemporaryFile(suffix=".pit", delete=False) as tf:
        tf.write(raw)
        tmppath = tf.name
    try:
        assert bridge.pit_health(tmppath) == pit._pit_health_local(raw)
    finally:
        os.unlink(tmppath)


@needs_bridge
def test_overlap_geometry_matches():
    raw = make_pit([
        dict(name="system", identifier=20, block_offset=2000, block_count=500),
        dict(name="vendor", identifier=21, block_offset=2200, block_count=500),
        dict(name="cache", identifier=22, block_offset=5000, block_count=100),
    ])
    with tempfile.NamedTemporaryFile(suffix=".pit", delete=False) as tf:
        tf.write(raw)
        tmppath = tf.name
    try:
        rust = bridge.pit_overlaps(tmppath)
    finally:
        os.unlink(tmppath)
    local_entries = pit._parse_pit_local(raw)
    assert [tuple(x) for x in rust["all"]] == list(pit.find_overlaps(local_entries))
    assert [tuple(x) for x in rust["significant"]] == list(pit.significant_overlaps(local_entries))


@needs_bridge
def test_error_mapping_matches():
    import tempfile
    cases = [
        (b"BADMAGIC" + b"\x00" * 28, "bad PIT magic", "parse"),
        (b"\x76\x98\x34\x12", "PIT too short", "parse"),
        (b"", None, "find-none"),
        (b"x" * 27, "", "model"),
    ]
    for raw, expect, kind in cases:
        with tempfile.NamedTemporaryFile(suffix=".pit", delete=False) as tf:
            tf.write(raw)
            tmppath = tf.name
        try:
            if kind == "parse":
                try:
                    bridge.pit_parse(tmppath)
                    raise AssertionError("expected BridgeError")
                except bridge.BridgeError as e:
                    assert expect in str(e)
                try:
                    pit._parse_pit_local(raw)
                    raise AssertionError("expected ValueError")
                except ValueError as e:
                    assert expect in str(e)
            elif kind == "find-none":
                assert bridge.pit_find(tmppath, "boot") is None
                assert pit.find_partition(raw, "boot") is None
            elif kind == "model":
                assert bridge.pit_model(tmppath)["model"] == ""
                assert pit.parse_model(raw) == ""
        finally:
            os.unlink(tmppath)
