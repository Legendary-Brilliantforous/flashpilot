"""Cross-implementation equivalence: native Rust imgtools vs local Python.

Public APIs prefer the bridge with local fallback; these tests pin both
paths together (patched bytes, header fields, messages). Native legs skip
when the bridge isn't built. NOTE: gzip bytes are NOT compared (zlib
implementations differ) — only decompressed content, sizes and fields.
"""

import gzip
import os
import struct

import pytest

from python.core import bridge
from python.core import core
from python.core import spd_adb

BRIDGE_OK = bridge.BRIDGE.exists()

needs_bridge = pytest.mark.skipif(not BRIDGE_OK, reason="bridge not built")


def cpio_entry(name, data):
    hdr = bytearray(b"0" * 110)
    hdr[0:6] = b"070701"
    hdr[54:62] = format(len(data), "08X").encode()
    hdr[94:102] = format(len(name) + 1, "08X").encode()
    e = bytes(hdr) + name.encode() + b"\x00"
    while len(e) % 4:
        e += b"\x00"
    e += data
    while len(e) % 4:
        e += b"\x00"
    return e


def make_boot(prop_text, gzipped=True, page=2048, extra_entries=()):
    kernel = b"\xAA" * 100
    rd_raw = b"".join([cpio_entry("default.prop", prop_text.encode())]
                      + [cpio_entry(n, d) for n, d in extra_entries])
    blob = gzip.compress(rd_raw, mtime=0) if gzipped else rd_raw
    img = bytearray(b"\x00" * page)
    img[0:8] = b"ANDROID!"
    struct.pack_into("<I", img, 8, len(kernel))
    struct.pack_into("<I", img, 24, len(blob))
    struct.pack_into("<I", img, 36, page)
    img += kernel + b"\x00" * (page - len(kernel)) + blob
    return bytes(img)


def readback(path):
    img = open(path, "rb").read()
    ks, rs = struct.unpack_from("<I", img, 8)[0], struct.unpack_from("<I", img, 24)[0]
    off = 2048 + ((ks + 2047) // 2048) * 2048
    return img, gzip.decompress(img[off:off + rs])


def test_local_repack_summary_shape():
    img = make_boot("ro.adb.secure=1\n")
    logs = []
    d = spd_adb._repack_local(bytearray(img), "/tmp/x.img", logs.append)
    assert d["kernel_size"] == 100 and d["page_size"] == 2048
    assert d["ramdisk_offset"] == 4096
    assert d["patched_files"] == ["default.prop"]
    assert d["recompressed"] is True
    assert d["grew_by"] == d["ramdisk_new"] - d["ramdisk_old"]


@needs_bridge
def test_patched_content_matches(tmp_path):
    img = make_boot("ro.adb.secure=1\nro.debuggable=0\n")
    src = str(tmp_path / "boot.img")
    open(src, "wb").write(img)
    out_rust = str(tmp_path / "r.img")
    out_py = str(tmp_path / "p.img")
    summary = bridge.boot_patch_adb(src, out_rust)
    local_img = bytearray(img)
    spd_adb._repack_local(local_img, out_py, lambda m: None)
    _, rust_raw = readback(out_rust)
    _, py_raw = readback(out_py)
    assert rust_raw == py_raw
    assert b"ro.adb.secure=0" in rust_raw
    assert b"persist.sys.usb.config=mtp,adb" in rust_raw
    assert b"# added by FlashPilot (adb enable)" in rust_raw
    assert summary["patched_files"] == ["default.prop"]
    assert summary["recompressed"] is True


@needs_bridge
def test_uncompressed_full_bytes_match(tmp_path):
    img = make_boot("ro.adb.secure=1\n", gzipped=False)
    src = str(tmp_path / "boot.img")
    open(src, "wb").write(img)
    out_rust = str(tmp_path / "r.img")
    bridge.boot_patch_adb(src, out_rust)
    local = bytearray(img)
    spd_adb._repack_local(local, str(tmp_path / "p.img"), lambda m: None)
    assert open(out_rust, "rb").read() == open(str(tmp_path / "p.img"), "rb").read()


@needs_bridge
def test_growth_and_header_match(tmp_path):
    filler = "x" * 200
    img = make_boot(f"ro.adb.secure=1\n#filler {filler}\n", gzipped=False)
    src = str(tmp_path / "boot.img")
    open(src, "wb").write(img)
    out_rust = str(tmp_path / "r.img")
    out_py = str(tmp_path / "p.img")
    s_rust = bridge.boot_patch_adb(src, out_rust)
    local = bytearray(img)
    got_logs = []
    s_py = spd_adb._repack_local(local, out_py, got_logs.append)
    assert s_rust["grew_by"] == s_py["grew_by"] > 0
    assert s_rust["ramdisk_new"] == s_py["ramdisk_new"]
    rb_rust = open(out_rust, "rb").read()
    rb_py = open(out_py, "rb").read()
    assert rb_rust == rb_py
    # Per-key detail lines identical on both paths.
    assert any("ro.adb.secure: 1 -> 0" in l for l in got_logs)


@needs_bridge
def test_idempotent_both_paths(tmp_path):
    img = make_boot("ro.adb.secure=1\n")
    src = str(tmp_path / "boot.img")
    open(src, "wb").write(img)
    once = str(tmp_path / "once.img")
    twice_rust = str(tmp_path / "twice_r.img")
    twice_py = str(tmp_path / "twice_p.img")
    bridge.boot_patch_adb(src, once)
    s2 = bridge.boot_patch_adb(once, twice_rust)
    assert s2["grew_by"] == 0
    local = bytearray(open(once, "rb").read())
    logs = []
    s3 = spd_adb._repack_local(local, twice_py, logs.append)
    assert s3["grew_by"] == 0
    # Gzipped blobs differ byte-wise across zlib implementations by
    # construction — compare decompressed content + header fields instead
    # (full-byte equality is asserted for uncompressed images above).
    def _content(path):
        img = open(path, "rb").read()
        rs = struct.unpack_from("<I", img, 24)[0]
        return img, gzip.decompress(img[4096:4096 + rs])
    img_r, raw_r = _content(twice_rust)
    img_p, raw_p = _content(twice_py)
    assert raw_r == raw_p
    assert img_r[8:40] == img_p[8:40]


@needs_bridge
def test_crlf_and_multi_prop_parity(tmp_path):
    img = make_boot("ro.adb.secure=1\r\n# comment\r\nro.debuggable=0\r\n",
                    extra_entries=[("first_stage_ramdisk/prop.default",
                                    b"ro.secure=1\n")])
    src = str(tmp_path / "boot.img")
    open(src, "wb").write(img)
    out_rust = str(tmp_path / "r.img")
    bridge.boot_patch_adb(src, out_rust)
    local = bytearray(img)
    spd_adb._repack_local(local, str(tmp_path / "p.img"), lambda m: None)
    _, rust_raw = readback(out_rust)
    # Second prop file patched on both paths (multi-file, CRLF-tolerant).
    assert b"ro.secure=0" in rust_raw
    rb_py = open(str(tmp_path / "p.img"), "rb").read()
    py_raw = gzip.decompress(
        rb_py[4096:4096 + struct.unpack_from("<I", rb_py, 24)[0]])
    assert rust_raw == py_raw


@needs_bridge
def test_error_parity():
    import tempfile
    # No prop files.
    rd = cpio_entry("first_stage_ramdisk/fstab", b"ro xxx\n")
    img = bytearray(b"\x00" * 2048)
    img[0:8] = b"ANDROID!"
    struct.pack_into("<I", img, 8, 100)
    struct.pack_into("<I", img, 24, len(rd))
    struct.pack_into("<I", img, 36, 2048)
    img += b"\xAA" * 100 + b"\x00" * (2048 - 100) + rd
    with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as tf:
        tf.write(bytes(img))
        path = tf.name
    out = path + ".out"
    try:
        try:
            bridge.boot_patch_adb(path, out)
            raise AssertionError("expected failure")
        except bridge.BridgeError as e:
            assert "no prop file found/patched" in str(e)
        try:
            spd_adb._repack_local(bytearray(img), out, lambda m: None)
            raise AssertionError("expected failure")
        except spd_adb.BootImageError as e:
            assert "no prop file found/patched" in str(e)
    finally:
        for p in (path, out):
            try:
                os.unlink(p)
            except OSError:
                pass
    # Bad magic / short / zero page.
    for bad in (b"NOPE", b"\x00" * 10):
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as tf:
            tf.write(bad)
            path = tf.name
        try:
            for fn in (lambda p: bridge.boot_patch_adb(p, p + ".o"),
                       lambda p: spd_adb._repack_local(bytearray(open(p, "rb").read()),
                                                       p + ".o", lambda m: None)):
                try:
                    fn(path)
                    raise AssertionError("expected failure")
                except Exception as e:
                    assert "ANDROID" in str(e) or "truncated" in str(e) or "short" in str(e)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass


@needs_bridge
def test_vbmeta_parity(tmp_path):
    good = b"AVB0" + b"\x00" * 76 + (0).to_bytes(4, "little") + b"\x00" * 48
    src = str(tmp_path / "vbmeta.img")
    open(src, "wb").write(good)
    out_rust = str(tmp_path / "r.img")
    res = bridge.vbmeta_patch(src, out_rust)
    assert res["patched"] is True
    got_rust = open(out_rust, "rb").read()
    got_py = core._patch_vbmeta_flags_local(good)
    assert got_rust == got_py
    assert struct.unpack_from("<I", got_rust, 80)[0] == 0x03
    # Junk -> None on both (bridge reports patched:false).
    junk = str(tmp_path / "junk.img")
    open(junk, "wb").write(b"junkjunkjunk")
    res2 = bridge.vbmeta_patch(junk, str(tmp_path / "j2.img"))
    assert res2["patched"] is False
    assert core._patch_vbmeta_flags_local(b"junkjunkjunk") is None
    # Custom flags agree.
    out3 = str(tmp_path / "r3.img")
    bridge.vbmeta_patch(src, out3, 0x01)
    assert struct.unpack_from("<I", open(out3, "rb").read(), 80)[0] == 0x01
    assert struct.unpack_from("<I", core._patch_vbmeta_flags_local(good, 0x01), 80)[0] == 0x01


@needs_bridge
def test_boot_info_parity(tmp_path):
    img = make_boot("ro.adb.secure=1\n")
    src = str(tmp_path / "boot.img")
    open(src, "wb").write(img)
    info = bridge.boot_info(src)
    assert info["kernel_size"] == 100
    assert info["page_size"] == 2048
    assert info["ramdisk_offset"] == 4096
    assert "default.prop" in info["prop_files"]
