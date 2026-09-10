"""SPD/UNISOC PAC format — parser + extract + pack (experimental).

PAC layout (YGDP, reverse-engineered from public parsers; canonical engine
is now `src/pac.rs`, shared with the `spd-readback` writer):
  header 2124 bytes: magic 0xD3 LE u32 @0, version u16@4, hdrlen 2116 @6,
                     MCT_DOWNLOAD_HEADER @8, count u32 @0x60, flash-size u32 @0x848
  entries: one 2560-byte slot per file:
                     name[512] utf16le @0, size u32 @0x30C, is_nv u32 @0x310, checksum 0x5433 @0x318
  then payloads concatenated, then footer 3076 zero bytes.

Public functions prefer the native engine and fall back to the pure-Python
implementations (`_*_local`) only when the bridge binary is absent — same
pattern as `pit.py`. Shared rules (name codec, sanitize, messages) are
pinned by cross-implementation equivalence tests.
"""

import os
import struct
from typing import Dict, List, Tuple

from . import bridge
from .flow import Flow, Step

PAC_HEADER_SIZE = 2124
PAC_ENTRY_SIZE = 2560
PAC_FOOTER_SIZE = 3076
PAC_MAGIC = 0xD3
PAC_HEADER_MAGIC_OFFSET = 0
PAC_PRODUCT_OFFSET = 0x20
PAC_PRODUCT_LEN = 64
PAC_COUNT_OFFSET = 0x60
PAC_FLASH_SIZE_OFFSET = 0x848
PAC_ENTRY_NAME_SIZE = 512
PAC_ENTRY_SIZE_OFFSET = 0x30C
PAC_ENTRY_IS_NV_OFFSET = 0x310
PAC_ENTRY_CHECKSUM_OFFSET = 0x318
PAC_ENTRY_CHECKSUM = 0x5433


def _read_utf16le(buf: bytes) -> str:
    # up to 512 bytes, utf16le, nul-terminated
    try:
        text = buf.decode("utf-16le", errors="ignore")
        return text.split("\x00")[0].strip()
    except Exception:
        return ""


def _write_utf16le(buf: bytearray, s: str, max_bytes: int = 512):
    data = s.encode("utf-16le")
    n = min(len(data), max_bytes - 2)
    buf[:n] = data[:n]


def _parse_pac_local(pac_path: str) -> Dict:
    """Pure-Python parse (fallback + unit-test path)."""
    with open(pac_path, "rb") as f:
        hdr = f.read(PAC_HEADER_SIZE)
        if len(hdr) < PAC_HEADER_SIZE:
            raise ValueError(f"PAC too short: {len(hdr)} < {PAC_HEADER_SIZE}")
        magic = struct.unpack("<I", hdr[0:4])[0]
        if magic != PAC_MAGIC:
            raise ValueError(f"Bad PAC magic 0x{magic:x} expected 0x{PAC_MAGIC:x}")
        count = struct.unpack("<I", hdr[PAC_COUNT_OFFSET : PAC_COUNT_OFFSET + 4])[0]
        if count == 0 or count > 500:
            raise ValueError(f"Suspicious PAC count {count}")
        flash_size = struct.unpack("<I", hdr[PAC_FLASH_SIZE_OFFSET : PAC_FLASH_SIZE_OFFSET + 4])[0]

        entries: List[Dict] = []
        data_offset = PAC_HEADER_SIZE + count * PAC_ENTRY_SIZE
        for i in range(count):
            slot = f.read(PAC_ENTRY_SIZE)
            if len(slot) < PAC_ENTRY_SIZE:
                raise ValueError(f"Truncated PAC entry {i}")
            name = _read_utf16le(slot[0:512])
            size = struct.unpack("<I", slot[PAC_ENTRY_SIZE_OFFSET : PAC_ENTRY_SIZE_OFFSET + 4])[0]
            is_nv = struct.unpack("<I", slot[PAC_ENTRY_IS_NV_OFFSET : PAC_ENTRY_IS_NV_OFFSET + 4])[0]
            chk = struct.unpack("<H", slot[PAC_ENTRY_CHECKSUM_OFFSET : PAC_ENTRY_CHECKSUM_OFFSET + 2])[0]
            entries.append(
                {
                    "index": i,
                    "name": name or f"part_{i}",
                    "size": size,
                    "is_nv": bool(is_nv),
                    "checksum": chk,
                    "data_offset": data_offset,
                }
            )
            data_offset += size

        # Footer not parsed, just integrity check
        return {
            "path": pac_path,
            "count": count,
            "flash_size": flash_size,
            "entries": entries,
            "total_payload": sum(e["size"] for e in entries),
        }


def _need_file(path: str):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"no such PAC file: {path}")


def _need_dir(path: str):
    if not os.path.isdir(path):
        raise FileNotFoundError(f"no such directory: {path}")


def parse_pac(pac_path: str) -> Dict:
    """Parse PAC header + entry table, return dict with entries + offsets.
    Native engine first; local fallback when the bridge is absent. Raises
    ValueError on bad magic/truncation either way."""
    _need_file(pac_path)
    try:
        return bridge.pac_parse(pac_path)
    except bridge.BinaryNotFoundError:
        return _parse_pac_local(pac_path)
    except bridge.BridgeError as e:
        raise ValueError(str(e))


def extract_pac(pac_path: str, out_dir: str) -> List[str]:
    """Extract PAC payloads to out_dir, return list of written files.
    Native engine first; local fallback when the bridge is absent."""
    _need_file(pac_path)
    try:
        return bridge.pac_extract(pac_path, out_dir)
    except bridge.BinaryNotFoundError:
        return _extract_pac_local(pac_path, out_dir)
    except bridge.BridgeError as e:
        raise ValueError(str(e))


def _extract_pac_local(pac_path: str, out_dir: str) -> List[str]:
    """Pure-Python extract (fallback + unit-test path)."""
    info = _parse_pac_local(pac_path)
    os.makedirs(out_dir, exist_ok=True)
    written: List[str] = []
    with open(pac_path, "rb") as f:
        for e in info["entries"]:
            off = e["data_offset"]
            size = e["size"]
            if size == 0:
                continue
            # sanitize name
            safe = e["name"].replace("/", "_").replace("\\", "_").strip() or f"part_{e['index']}"
            out_path = os.path.join(out_dir, safe)
            # ensure not overwriting with dir
            if os.path.isdir(out_path):
                out_path += ".img"
            f.seek(off)
            data = f.read(size)
            # allow truncated read (some PACs have sparse footers)
            if len(data) < size:
                # pad with zeros? just write what we got
                pass
            with open(out_path, "wb") as out:
                out.write(data)
            written.append(out_path)
    return written


def pack_pac(in_dir: str, out_pac: str, product: str = "") -> str:
    """Pack every file in in_dir (non-recursive, sorted) into a PAC.
    Native engine first; local fallback when the bridge is absent."""
    _need_dir(in_dir)
    try:
        return bridge.pac_pack(in_dir, out_pac, product)
    except bridge.BinaryNotFoundError:
        return _pack_pac_local(in_dir, out_pac, product)
    except bridge.BridgeError as e:
        raise ValueError(str(e))


def _pack_pac_local(in_dir: str, out_pac: str, product: str = "") -> str:
    """Pure-Python pack (fallback + unit-test path).

    Layout: header 2124 + entries 2560*count + payloads + footer 3076.
    """
    files = sorted(
        [
            os.path.join(in_dir, n)
            for n in os.listdir(in_dir)
            if os.path.isfile(os.path.join(in_dir, n))
        ]
    )
    if not files:
        raise ValueError(f"No files in {in_dir}")
    entries = [(os.path.basename(p), os.path.getsize(p)) for p in files]
    total = sum(s for _, s in entries)
    for name, size in entries:
        if size > 0xFFFFFFFF:
            raise ValueError(f"file too large for PAC: {name} ({size} bytes exceeds u32)")
    if total > 0xFFFFFFFF:
        raise ValueError(f"PAC payload too large: {total} bytes exceeds u32 flash-size")

    with open(out_pac, "wb") as out:
        hdr = bytearray(PAC_HEADER_SIZE)
        struct.pack_into("<I", hdr, 0, PAC_MAGIC)
        struct.pack_into("<H", hdr, 4, 1)  # version
        struct.pack_into("<H", hdr, 6, 2116)  # hdrlen
        hdr[8 : 8 + len(b"MCT_DOWNLOAD_HEADER")] = b"MCT_DOWNLOAD_HEADER"
        if product:
            # NOTE: write into hdr directly — _write_utf16le(hdr[a:b], ...)
            # would mutate a slice *copy* and silently drop the product.
            enc = product.encode("utf-16le")[: PAC_PRODUCT_LEN - 2]
            hdr[0x20 : 0x20 + len(enc)] = enc
        struct.pack_into("<I", hdr, PAC_COUNT_OFFSET, len(entries))
        struct.pack_into("<I", hdr, PAC_FLASH_SIZE_OFFSET, total)
        out.write(hdr)

        for name, size in entries:
            slot = bytearray(PAC_ENTRY_SIZE)
            _write_utf16le(slot, name, 512)
            struct.pack_into("<I", slot, PAC_ENTRY_SIZE_OFFSET, size)
            struct.pack_into("<I", slot, PAC_ENTRY_IS_NV_OFFSET, 0)
            struct.pack_into("<H", slot, PAC_ENTRY_CHECKSUM_OFFSET, PAC_ENTRY_CHECKSUM)
            out.write(slot)

        for fp in files:
            with open(fp, "rb") as f:
                while True:
                    chunk = f.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)

        out.write(b"\x00" * PAC_FOOTER_SIZE)

    return out_pac


# Helper to list entries without extracting
def list_pac(pac_path: str) -> List[Tuple[str, int, bool]]:
    info = parse_pac(pac_path)
    return [(e["name"], e["size"], e["is_nv"]) for e in info["entries"]]


def flow_pac_extract():
    """SPD PAC extract: unpack a .pac firmware container to a folder.

    File-only operation (no device needed): PAC_FILE env/ctx in, extracted
    images out. Mirrors the ofp flow's input convention."""

    def _run(ctx, log):
        import tempfile as _tf

        log("=" * 60)
        log("SPD PAC EXTRACT (file -> folder, no device needed)")
        log("=" * 60)
        src = (os.environ.get("PAC_FILE", "").strip() or ctx.get("pac_file", ""))
        if not src or not os.path.isfile(src):
            raise RuntimeError("Set PAC_FILE=/path/to/firmware.pac (or pass pac_file=)")
        log(f"  File: {src} ({os.path.getsize(src) >> 20} MB)")
        try:
            info = parse_pac(src)
        except ValueError as e:
            raise RuntimeError(f"not a PAC container: {e}")
        log(f"  Entries: {info['count']}  payload={info['total_payload'] >> 20} MB")
        out_dir = (os.environ.get("PAC_OUT_DIR", "").strip()
                   or os.path.join(_tf.gettempdir(), "pac_out"))
        files = extract_pac(src, out_dir)
        log(f"  Extracted {len(files)} file(s) -> {out_dir}")
        for f in files[:20]:
            log(f"    {os.path.basename(f)}")
        if len(files) > 20:
            log(f"    ... and {len(files) - 20} more")
        ctx["pac_out_dir"] = out_dir
        return True

    return Flow("SPD PAC extract (file to folder)", [Step("pac_extract", _run)])


def flow_pac_pack():
    """SPD PAC pack: build a .pac container from a folder of images.

    File-only operation (no device needed): PAC_IN_DIR env/ctx in, .pac out.
    The archive restores with `spd-flash` or any YGDP-compatible tool."""

    def _run(ctx, log):
        log("=" * 60)
        log("SPD PAC PACK (folder -> file, no device needed)")
        log("=" * 60)
        in_dir = (os.environ.get("PAC_IN_DIR", "").strip() or ctx.get("pac_in_dir", ""))
        if not in_dir or not os.path.isdir(in_dir):
            raise RuntimeError("Set PAC_IN_DIR=/path/to/images/ (or pass pac_in_dir=)")
        out_pac = (os.environ.get("PAC_OUT", "").strip() or ctx.get("pac_out", "")
                   or os.path.join(in_dir, "packed.pac"))
        product = (os.environ.get("PAC_PRODUCT", "").strip() or ctx.get("pac_product", ""))
        try:
            pack_pac(in_dir, out_pac, product)
        except ValueError as e:
            raise RuntimeError(str(e))
        log(f"  Packed -> {out_pac} ({os.path.getsize(out_pac) >> 20} MB)")
        ctx["pac_out"] = out_pac
        return True

    return Flow("SPD PAC pack (folder to file)", [Step("pac_pack", _run)])
