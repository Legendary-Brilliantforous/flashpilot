"""Cross-implementation equivalence: native Rust PAC engine vs local Python.

Public `pac.*` prefers the bridge with local fallback; these tests pin both
paths together (entries, bytes, messages, sanitize, errors) so the shared
rules can never drift. Native legs skip when the bridge isn't built.
"""

import os

import pytest

from python.core import bridge
from python.core import pac

BRIDGE_OK = bridge.BRIDGE.exists()

needs_bridge = pytest.mark.skipif(not BRIDGE_OK, reason="bridge not built")


def make_files(in_dir, spec):
    """spec: {name: bytes} -> write files, return sorted paths."""
    os.makedirs(in_dir, exist_ok=True)
    for name, data in spec.items():
        dest = os.path.join(in_dir, name)
        parent = os.path.dirname(dest)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
    return sorted(os.path.join(in_dir, n) for n in spec)


SAMPLE = {
    "boot.img": bytes(range(256)) * 4,
    "system.img": b"\x00\xff" * 3000 + b"tail",
    "empty.bin": b"",
}


def entry_key(e):
    return (e["name"], e["size"], e["is_nv"], e["checksum"], e["data_offset"])


@needs_bridge
def test_pack_parse_roundtrip_both_directions(tmp_path):
    src = str(tmp_path / "src")
    make_files(src, SAMPLE)
    # Rust pack -> Python-local parse.
    rust_pac = str(tmp_path / "rust.pac")
    assert bridge.pac_pack(src, rust_pac, "TestProduct") == rust_pac
    local_info = pac._parse_pac_local(rust_pac)
    assert local_info["count"] == 3
    # Python-local pack -> Rust parse.
    py_pac = str(tmp_path / "py.pac")
    assert pac._pack_pac_local(src, py_pac, "TestProduct") == py_pac
    rust_info = bridge.pac_parse(py_pac)
    assert [entry_key(e) for e in rust_info["entries"]] == [
        entry_key(e) for e in local_info["entries"]
    ]
    assert rust_info["count"] == local_info["count"] == 3
    assert rust_info["total_payload"] == local_info["total_payload"]
    assert rust_info["flash_size"] == local_info["flash_size"]
    # Product string survives both ways.
    assert "TestProduct" in open(py_pac, "rb").read()[0x20:0x60].decode("utf-16le")
    assert "TestProduct" in open(rust_pac, "rb").read()[0x20:0x60].decode("utf-16le")


@needs_bridge
def test_extract_bytes_identical(tmp_path):
    src = str(tmp_path / "src")
    make_files(src, SAMPLE)
    pac_path = str(tmp_path / "t.pac")
    bridge.pac_pack(src, pac_path, "")
    out_rust = str(tmp_path / "out_rust")
    out_py = str(tmp_path / "out_py")
    got_rust = bridge.pac_extract(pac_path, out_rust)
    got_py = pac._extract_pac_local(pac_path, out_py)
    assert [os.path.basename(p) for p in got_rust] == [
        os.path.basename(p) for p in got_py
    ]
    for name in ("boot.img", "system.img"):
        assert open(os.path.join(out_rust, name), "rb").read() == SAMPLE[name]
        assert open(os.path.join(out_py, name), "rb").read() == SAMPLE[name]
    # size-0 entry skipped by both.
    assert not any(p.endswith("empty.bin") for p in got_rust)
    assert not any(p.endswith("empty.bin") for p in got_py)


def make_synthetic_pac(path, entries):
    """entries: [(name, data)] -> write a PAC with LITERAL entry names
    (slashes and all — impossible via pack-from-folder on Linux, but legal
    from foreign tools; this is exactly what extract sanitize must handle)."""
    import struct as _st
    total = sum(len(d) for _, d in entries)
    hdr = bytearray(2124)
    _st.pack_into("<I", hdr, 0, 0xD3)
    _st.pack_into("<H", hdr, 4, 1)
    _st.pack_into("<H", hdr, 6, 2116)
    hdr[8:8 + 19] = b"MCT_DOWNLOAD_HEADER"
    _st.pack_into("<I", hdr, 0x60, len(entries))
    _st.pack_into("<I", hdr, 0x848, total)
    with open(path, "wb") as f:
        f.write(hdr)
        for name, data in entries:
            slot = bytearray(2560)
            enc = name.encode("utf-16le")[:510]
            slot[:len(enc)] = enc
            _st.pack_into("<I", slot, 0x30C, len(data))
            _st.pack_into("<I", slot, 0x310, 0)
            _st.pack_into("<H", slot, 0x318, 0x5433)
            f.write(slot)
        for _, data in entries:
            f.write(data)
        f.write(b"\x00" * 3076)


@needs_bridge
def test_sanitize_parity(tmp_path):
    pac_path = str(tmp_path / "evil.pac")
    make_synthetic_pac(pac_path, [
        ("a/b", b"1"), ("c\\d", b"22"), ("   ", b"333"), ("", b"4444"),
    ])
    # Plus a directory colliding with an entry name at extract time.
    out_rust = str(tmp_path / "or")
    out_py = str(tmp_path / "op")
    os.makedirs(os.path.join(out_rust, "a_b"))
    os.makedirs(os.path.join(out_py, "a_b"))
    got_rust = [os.path.basename(p) for p in bridge.pac_extract(pac_path, out_rust)]
    got_py = [os.path.basename(p) for p in pac._extract_pac_local(pac_path, out_py)]
    assert got_rust == got_py
    assert "a_b.img" in got_rust  # dir collision -> .img suffix, both engines
    assert "part_3" in got_rust  # empty name -> part_N, both engines
    for base, expect in (("a_b.img", b"1"), ("c_d", b"22")):
        assert open(os.path.join(out_rust, base), "rb").read() == expect
        assert open(os.path.join(out_py, base), "rb").read() == expect


@needs_bridge
def test_error_mapping_matches(tmp_path):
    short = str(tmp_path / "short.pac")
    open(short, "wb").write(b"\x00" * 100)
    for fn in (bridge.pac_parse, pac._parse_pac_local):
        try:
            fn(short)
            raise AssertionError("expected failure")
        except Exception as e:
            assert "PAC too short" in str(e)
    bad = str(tmp_path / "bad.pac")
    open(bad, "wb").write(b"\x00" * 5000)
    for fn in (bridge.pac_parse, pac._parse_pac_local):
        try:
            fn(bad)
            raise AssertionError("expected failure")
        except Exception as e:
            assert "Bad PAC magic" in str(e)
    empty = str(tmp_path / "empty")
    os.makedirs(empty)
    for fn in (lambda p: bridge.pac_pack(p, str(tmp_path / "x.pac"), ""),
               lambda p: pac._pack_pac_local(p, str(tmp_path / "y.pac"), "")):
        try:
            fn(empty)
            raise AssertionError("expected failure")
        except Exception as e:
            assert "No files in" in str(e)
    # Missing inputs raise FileNotFoundError on both paths.
    missing = str(tmp_path / "nope.pac")
    try:
        pac.parse_pac(missing)
        raise AssertionError("expected failure")
    except FileNotFoundError:
        pass
    try:
        pac.pack_pac(str(tmp_path / "nodir"), str(tmp_path / "o.pac"))
        raise AssertionError("expected failure")
    except FileNotFoundError:
        pass


def test_list_pac_uses_parse(tmp_path):
    src = str(tmp_path / "src")
    make_files(src, {"a.img": b"1234"})
    pac_path = str(tmp_path / "t.pac")
    pac.pack_pac(src, pac_path, "")
    assert pac.list_pac(pac_path) == [("a.img", 4, False)]


def test_flows_validate_inputs(tmp_path):
    logs = []
    try:
        pac.flow_pac_extract().run({}, logs.append)
        raise AssertionError("expected failure")
    except RuntimeError as e:
        assert "PAC_FILE" in str(e)
    try:
        pac.flow_pac_pack().run({}, logs.append)
        raise AssertionError("expected failure")
    except RuntimeError as e:
        assert "PAC_IN_DIR" in str(e)


@needs_bridge
def test_flow_extract_end_to_end(tmp_path, monkeypatch):
    src = str(tmp_path / "src")
    make_files(src, SAMPLE)
    pac_path = str(tmp_path / "t.pac")
    out_dir = str(tmp_path / "out")
    pac.pack_pac(src, pac_path, "")
    monkeypatch.setenv("PAC_FILE", pac_path)
    monkeypatch.setenv("PAC_OUT_DIR", out_dir)
    logs = []
    assert pac.flow_pac_extract().run({}, logs.append) == [True]
    assert open(os.path.join(out_dir, "boot.img"), "rb").read() == SAMPLE["boot.img"]
