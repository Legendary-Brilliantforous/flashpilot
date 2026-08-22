"""Samsung PIT (Partition Information Table) parsing.

Two entry layouts coexist in the wild (both 132 bytes):

* Classic Loke/Exynos PITs - documented by Heimdall libpit.h: five u32s,
  blockSizeOrOffset@20, blockCount@24, obsolete fileOffset@28, obsolete
  fileSize@32, then strings at +36 (name) / +68 (flash) / +100 (fota).
* Samsung-MTK DA-synthesized PITs (A14/A06 class, dumped from real devices
  in pit/A14M_MEA_OPEN.pit): the fileSize field is absent, so strings sit
  four bytes earlier at +32 / +64 / +96.

Reading a PIT with the wrong layout yields empty or garbage partition names
(silent total failure). parse_pit() therefore scores both layouts against
the actual bytes and picks the one that decodes valid names.
"""

import struct

PIT_MAGIC = 0x12349876
HEADER_SIZE = 32   # kHeaderDataSize
ENTRY_SIZE = 132   # kDataSize
SECTOR_SIZE = 512  # eMMC sector size used for block->byte math

# Entry field offsets shared by both layouts
BINARY_TYPE_OFF = 0
DEVICE_TYPE_OFF = 4
IDENTIFIER_OFF = 8
ATTRIBUTES_OFF = 12
UPDATE_ATTRIBUTES_OFF = 16
BLOCK_OFFSET_OFF = 20      # "Partition Block Size/Offset" in Heimdall
BLOCK_COUNT_OFF = 24
FILE_OFFSET_OFF = 28       # obsolete (classic)
FILE_SIZE_OFF = 32         # obsolete - only present in the classic layout

# String-field offsets per layout
NAME_OFF_CLASSIC = 36      # classic Loke/Exynos (fileSize@32 present)
NAME_OFF_MTK = 32          # Samsung-MTK DA-synthesized (no fileSize field)

BINARY_TYPES = {0: "AP", 1: "CP"}
DEVICE_TYPES = {0: "OneNAND", 1: "File/FAT", 2: "MMC", 3: "All"}

ATTR_WRITE = 0x1   # set => Read/Write, clear => Read-Only
ATTR_STL = 0x2
UPD_FOTA = 0x1
UPD_SECURE = 0x2


class PitEntry:
    def __init__(self, data, index, name_off=NAME_OFF_MTK):
        self.index = index
        self.name_off = name_off
        (
            self.binary_type,
            self.device_type,
            self.identifier,
            self.attributes,
            self.update_attributes,
            self.block_size,     # blockSizeOrOffset: start block / byte offset
            self.block_count,
            self.file_offset,    # obsolete
        ) = struct.unpack_from("<8I", data, BINARY_TYPE_OFF)
        if name_off == NAME_OFF_CLASSIC:
            self.file_size = struct.unpack_from("<I", data, FILE_SIZE_OFF)[0]
        else:
            self.file_size = 0
        self.name = _str_at(data, name_off)
        self.flash_filename = _str_at(data, name_off + 32)
        self.fota_filename = _str_at(data, name_off + 64)

    # ---- semantic helpers -------------------------------------------------
    @property
    def block_offset(self):
        """Alias for the 'block size or offset' field - on eMMC PITs this is
        the partition's start block (entries chain start+count -> next)."""
        return self.block_size

    def size_bytes(self):
        return self.block_count * SECTOR_SIZE

    def human_size(self):
        return human_size(self.size_bytes())

    def is_flashable(self):
        # Odin flags whitespace-only or dot-prefixed entries as flashable
        # partitions; treat them as padding/metadata instead.
        n = self.name.strip()
        return bool(n) and not n.startswith(".")

    # ---- decoded flag properties (Heimdall PrintPit semantics) ------------
    @property
    def is_read_only(self):
        return not (self.attributes & ATTR_WRITE)

    @property
    def is_stl(self):
        return bool(self.attributes & ATTR_STL)

    @property
    def has_fota(self):
        return bool(self.update_attributes & UPD_FOTA)

    @property
    def is_secure(self):
        return bool(self.update_attributes & UPD_SECURE)

    @property
    def binary_type_label(self):
        return BINARY_TYPES.get(self.binary_type, "Unknown")

    @property
    def device_type_label(self):
        return DEVICE_TYPES.get(self.device_type, "Unknown")

    def __repr__(self):
        return (
            f"PitEntry({self.index}: name={self.name!r} "
            f"file={self.flash_filename!r} device_type={self.device_type:#x} "
            f"size={self.size_bytes()})"
        )


def human_size(n):
    """Bytes -> compact human string (Heimdall-style)."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024.0


def _str_at(data, offset):
    end = data.find(b"\x00", offset)
    if end == -1 or end > offset + 32:
        end = offset + 32
    return data[offset:end].decode("ascii", errors="replace")


def _clean_name_at(data, off):
    """Decode a 32-byte NUL-padded string field; return the text only when it
    is non-empty printable ASCII terminated by NUL or the field end."""
    if off + 32 > len(data):
        return ""
    raw = data[off : off + 32]
    end = raw.find(b"\x00")
    if end <= 0:
        return "" if end == 0 else raw.decode("ascii", errors="replace")
    text = raw[:end]
    if all(0x20 <= b < 0x7F for b in text):
        return text.decode("ascii")
    return ""


def detect_name_offset(raw: bytes) -> int:
    """Score both known string layouts against the actual PIT bytes and
    return the name-field offset (32 = MTK-DA, 36 = classic Loke) that
    decodes valid partition names. Ties go to the classic layout.
    """
    if len(raw) < HEADER_SIZE + ENTRY_SIZE:
        return NAME_OFF_MTK
    count = struct.unpack_from("<I", raw, 4)[0]
    scores = {NAME_OFF_MTK: 0, NAME_OFF_CLASSIC: 0}
    for off in scores:
        good = 0
        for i in range(min(count, 512)):
            base = HEADER_SIZE + i * ENTRY_SIZE
            if base + ENTRY_SIZE > len(raw):
                break
            if _clean_name_at(raw, base + off):
                good += 1
        scores[off] = good
    return (
        NAME_OFF_CLASSIC
        if scores[NAME_OFF_CLASSIC] >= scores[NAME_OFF_MTK] and scores[NAME_OFF_CLASSIC] > 0
        else NAME_OFF_MTK
    )


def pit_layout(raw: bytes):
    """'mtk' | 'classic' - which entry variant detect_name_offset picked."""
    return "classic" if detect_name_offset(raw) == NAME_OFF_CLASSIC else "mtk"


def parse_pit(raw: bytes, name_off=None):
    if len(raw) < HEADER_SIZE:
        raise ValueError("PIT too short")
    magic = struct.unpack_from("<I", raw, 0)[0]
    if magic != PIT_MAGIC:
        raise ValueError(f"bad PIT magic: {magic:#x}")
    count = struct.unpack_from("<I", raw, 4)[0]
    if name_off is None:
        name_off = detect_name_offset(raw)
    entries = []
    for i in range(count):
        off = HEADER_SIZE + i * ENTRY_SIZE
        if off + ENTRY_SIZE > len(raw):
            break
        entry = PitEntry(raw[off : off + ENTRY_SIZE], i, name_off=name_off)
        if entry.is_flashable():
            entries.append(entry)
    return entries


def parse_model(raw: bytes):
    """Read the model string from the PIT header (offset 8), as Odin does."""
    if len(raw) < HEADER_SIZE:
        return ""
    end = raw.find(b"\x00", 8)
    if end == -1 or end > 64:
        end = 64
    return raw[8:end].decode("ascii", errors="replace").strip()


# Suffixes firmware archives put on image files that must not take part in
# partition-name matching (Odin and most commercial tools compare raw names
# and wrongly flag e.g. "boot.img" as missing from the PIT).
_IMG_SUFFIXES = (".img", ".bin", ".mbn", ".elf", ".lz4", ".ext4", ".raw")


def normalize_part_name(name: str):
    """Lowercase, strip common image suffixes and whitespace so archive
    entries match their PIT partition ('boot.img' -> 'boot')."""
    n = name.strip().lower()
    changed = True
    while changed and n:
        changed = False
        for suf in _IMG_SUFFIXES:
            if n.endswith(suf):
                n = n[: -len(suf)]
                changed = True
    return n


def validate_and_sanitize_pit(pit_raw: bytes, archive_part_names: list) -> tuple:
    """Compare firmware archive partitions against device PIT entries.

    Names are matched with normalize_part_name() so 'boot.img', 'BOOT' and
    'boot' all match the PIT entry 'boot' - raw comparisons flag perfectly
    flashable archives as incompatible (an Odin/commercial-tool complaint).

    Returns (is_compatible: bool, missing_in_pit: list,
             extra_in_archive: list, model: str).
    """
    try:
        entries = parse_pit(pit_raw)
        model = parse_model(pit_raw)
        device_parts = {normalize_part_name(e.name) for e in entries}
        device_parts.discard("")
        archive_parts = {normalize_part_name(p) for p in archive_part_names}
        archive_parts.discard("")

        extra_in_archive = sorted(list(archive_parts - device_parts))
        missing_in_pit = sorted(list(device_parts - archive_parts))

        is_compatible = len(extra_in_archive) == 0
        return is_compatible, missing_in_pit, extra_in_archive, model
    except Exception:
        return True, [], [], ""


def find_partition(entries_or_raw, name: str):
    """Find a PIT entry by partition or flash-file name (normalized).
    Accepts a parsed entry list or raw PIT bytes. Returns PitEntry or None.
    """
    if isinstance(entries_or_raw, (bytes, bytearray)):
        try:
            entries = parse_pit(bytes(entries_or_raw))
        except ValueError:
            return None
    else:
        entries = entries_or_raw
    want = normalize_part_name(name)
    for e in entries:
        if normalize_part_name(e.name) == want:
            return e
    for e in entries:  # second pass: flash filename only
        if e.flash_filename and normalize_part_name(e.flash_filename) == want:
            return e
    return None


def find_overlaps(entries):
    """Detect partitions whose block ranges collide - a corrupt or foreign
    PIT indicator that Odin happily flashes anyway (brick risk).

    Entries with zero block_count are skipped. Returns a list of
    (name_a, name_b, overlap_blocks) tuples.
    """
    ranges = []
    for e in entries:
        if e.block_count == 0:
            continue
        ranges.append((e.name, e.block_offset, e.block_offset + e.block_count))
    ranges.sort(key=lambda r: r[1])
    out = []
    for i in range(1, len(ranges)):
        prev_name, prev_start, prev_end = ranges[i - 1]
        name, start, end = ranges[i]
        if start < prev_end:
            overlap = min(prev_end, end) - start
            out.append((prev_name, name, overlap))
    return out


def pit_report(raw: bytes):
    """Human-readable PIT table in the spirit of Heimdall's print-pit /
    Odin's Print button. Raises ValueError on bad magic (parse_pit rules).
    """
    entries = parse_pit(raw)
    model = parse_model(raw)
    lines = []
    header = f"PIT: {len(entries)} partitions  layout={pit_layout(raw)}"
    if model:
        header += f"  model={model}"
    lines.append(header)
    overlaps = find_overlaps(entries)
    if overlaps:
        lines.append(
            "WARNING: overlapping partitions (corrupt/foreign PIT): "
            + ", ".join(f"{a}<->{b} ({o} blocks)" for a, b, o in overlaps)
        )
    hdr = f"{'idx':>3}  {'name':<24} {'ident':>5}  {'start':>9}  {'blocks':>8}  {'size':>10}  flags  flash file"
    lines.append(hdr)
    for e in entries:
        flags = []
        if e.is_read_only:
            flags.append("RO")
        if e.is_stl:
            flags.append("STL")
        if e.has_fota:
            flags.append("FOTA")
        if e.is_secure:
            flags.append("SEC")
        if not flags:
            flags.append("RW")
        lines.append(
            f"{e.index:>3}  {e.name:<24.24} {e.identifier:>5}  "
            f"{e.block_offset:>9}  {e.block_count:>8}  {e.human_size():>10}  "
            f"{','.join(flags):<6} {e.flash_filename}"
        )
    total = sum(e.block_count for e in entries) * SECTOR_SIZE
    lines.append(f"total: {human_size(total)} across {len(entries)} partitions")
    return "\n".join(lines)


def hex_to_bytes(h):
    return bytes.fromhex(h)
