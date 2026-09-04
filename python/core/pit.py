"""Samsung PIT (Partition Information Table) parsing.

Layout below is the single true format, cross-verified between Heimdall
libpit.h/cpp, TheAirBlow/Thor's extended PIT parser, and FlashPilot's own
real device dumps (pit/A14M_MEA_OPEN.pit, pit/device_2_84.pit):

Header - 28 bytes:
    magic u32   @0   = 0x12349876
    entryCount  @4
    Unknown[8]  @8    } model/project string ("COM_TAR2" + "MTK6765")
    Project[8]  @16   }
    Reserved u32@24

Entry - 132 bytes each, starting at offset 28:
    binaryType        u32  @+0   (0=AP, 1=CP)
    deviceType        u32  @+4
    identifier        u32  @+8
    attributes        u32  @+12
    updateAttributes  u32  @+16
    blockSizeOrOffset u32  @+20  ("start block" on new-style PITs)
    blockCount        u32  @+24
    fileOffset        u32  @+28  (obsolete)
    fileSize          u32  @+32  (obsolete)
    partitionName[32]     @+36
    flashFileName[32]     @+68
    deltaFileName[32]     @+100

Earlier revisions of this parser used a 32-byte header, which shifted every
numeric field one slot late (deviceType read as binaryType, etc.) while the
partition names happened to still land correctly - masking the bug.
"""

import struct

PIT_MAGIC = 0x12349876
HEADER_SIZE = 28   # magic + count + Unknown[8] + Project[8] + Reserved
ENTRY_SIZE = 132   # kDataSize
SECTOR_SIZE = 512  # eMMC sector size used for block->byte math

# Header offsets
HDR_MAGIC_OFF = 0
HDR_COUNT_OFF = 4
HDR_UNKNOWN_OFF = 8    # 8-byte string
HDR_PROJECT_OFF = 16   # 8-byte string
HDR_RESERVED_OFF = 24

# Entry field offsets (relative to the start of each 132-byte entry)
BINARY_TYPE_OFF = 0
DEVICE_TYPE_OFF = 4
IDENTIFIER_OFF = 8
ATTRIBUTES_OFF = 12
UPDATE_ATTRIBUTES_OFF = 16
BLOCK_OFFSET_OFF = 20      # blockSizeOrOffset - "start block" on new-style PITs
BLOCK_COUNT_OFF = 24
FILE_OFFSET_OFF = 28       # obsolete
FILE_SIZE_OFF = 32         # obsolete
NAME_OFF = 36              # partitionName[32]
FLASH_OFF = 68             # flashFileName[32]
DELTA_OFF = 100            # deltaFileName[32]

# Well-known identifiers reserved by Samsung platform tables
RESERVED_IDENTIFIERS = {70: "pgpt", 71: "pit", 72: "md5hdr"}

# Partition-table metadata regions. On real MTK-synthesized PITs the
# 'bootloader' entry spans the whole preloader area and CONTAINS pgpt/pit/
# md5hdr - overlap with these meta partitions is normal, not corruption.
META_PART_NAMES = {"pgpt", "gpt", "pit", "md5hdr"}
META_IDENTIFIERS = set(RESERVED_IDENTIFIERS)

BINARY_TYPES = {0: "AP", 1: "CP"}
DEVICE_TYPES = {0: "OneNAND", 1: "File/FAT", 2: "MMC", 3: "All"}

ATTR_WRITE = 0x1   # old-style: set => Read/Write, clear => Read-Only
ATTR_STL = 0x2     # old-style: STL flag
UPD_FOTA = 0x1     # old-style updateAttributes bits
UPD_SECURE = 0x2


class PitEntry:
    def __init__(self, data, index):
        self.index = index
        (
            self.binary_type,
            self.device_type,
            self.identifier,
            self.attributes,
            self.update_attributes,
            self.block_size,     # blockSizeOrOffset: start block (new-style)
            self.block_count,
            self.file_offset,    # obsolete
        ) = struct.unpack_from("<8I", data, BINARY_TYPE_OFF)
        self.file_size = struct.unpack_from("<I", data, FILE_SIZE_OFF)[0]
        self.name = _str_at(data, NAME_OFF)
        self.flash_filename = _str_at(data, FLASH_OFF)
        self.delta_filename = _str_at(data, DELTA_OFF)

    # Historical alias: third string was widely documented as the FOTA name;
    # Thor identified it as the delta filename. Same field.
    @property
    def fota_filename(self):
        return self.delta_filename

    # ---- semantic helpers -------------------------------------------------
    @property
    def block_offset(self):
        """Alias for blockSizeOrOffset - on new-style PITs this chains as the
        partition's start block."""
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

    # ---- decoded flag properties (Heimdall PrintPit semantics; these map to
    # the OLD-style attribute bitmasks - see pit_style()) ---------------
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
            f"identifier={self.identifier} size={self.size_bytes()})"
        )


def human_size(n):
    """Bytes -> compact human string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024.0


def _str_at(data, offset):
    end = data.find(b"\x00", offset)
    if end == -1 or end > offset + 32:
        end = offset + 32
    return data[offset:end].decode("ascii", errors="replace")


def _clean_str_at(data, offset):
    """Decode a NUL-padded 32-byte string field; non-empty printable ASCII
    only (used by validation)."""
    if offset + 32 > len(data):
        return ""
    raw = data[offset : offset + 32]
    end = raw.find(b"\x00")
    if end <= 0:
        return ""
    text = raw[:end]
    if all(0x20 <= b < 0x7F for b in text):
        return text.decode("ascii")
    return ""


def parse_header(raw: bytes):
    """Return (model, unknown, project, reserved) from the 28-byte header."""
    if len(raw) < HEADER_SIZE:
        return "", "", "", 0
    unknown = _str_at(raw[:HEADER_SIZE], HDR_UNKNOWN_OFF)[:8]
    project = _str_at(raw[:HEADER_SIZE], HDR_PROJECT_OFF)[:8]
    reserved = struct.unpack_from("<I", raw, HDR_RESERVED_OFF)[0]
    model = (unknown + project).strip("\x00").strip()
    return model, unknown.rstrip("\x00"), project.rstrip("\x00"), reserved


def parse_model(raw: bytes):
    """Model/project string from the PIT header ('COM_TAR2MTK6765')."""
    return parse_header(raw)[0]


def parse_pit(raw: bytes):
    if len(raw) < HEADER_SIZE:
        raise ValueError("PIT too short")
    magic = struct.unpack_from("<I", raw, HDR_MAGIC_OFF)[0]
    if magic != PIT_MAGIC:
        raise ValueError(f"bad PIT magic: {magic:#x}")
    count = struct.unpack_from("<I", raw, HDR_COUNT_OFF)[0]
    entries = []
    for i in range(count):
        off = HEADER_SIZE + i * ENTRY_SIZE
        if off + ENTRY_SIZE > len(raw):
            break
        entry = PitEntry(raw[off : off + ENTRY_SIZE], i)
        if entry.is_flashable():
            entries.append(entry)
    return entries


# Suffixes firmware archives put on image files that must not take part in
# partition-name matching (Odin and most commercial tools compare raw names
# and wrongly flag e.g. "boot.img" as missing from the PIT).
# Dual support: lz4 legacy + zstd preferred (.zst / .zstd)
_IMG_SUFFIXES = (".img", ".bin", ".mbn", ".elf", ".lz4", ".zst", ".zstd", ".ext4", ".raw")


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


def is_meta_entry(entry):
    """True for partition-table metadata regions (pgpt/pit/md5hdr)."""
    return (
        entry.name.strip().lower() in META_PART_NAMES
        or entry.identifier in META_IDENTIFIERS
    )


def find_overlaps(entries):
    """Detect partitions whose block ranges collide - a corrupt or foreign
    PIT indicator that Odin happily flashes anyway (brick risk).

    Entries with zero block_count are skipped. Returns a list of
    (name_a, name_b, overlap_blocks) tuples, including meta-partition
    containment (which is normal) - use significant_overlaps() for the
    corruption-relevant subset.
    """
    ranges = []
    for e in entries:
        if e.block_count == 0:
            continue
        ranges.append((e, e.block_offset, e.block_offset + e.block_count))
    ranges.sort(key=lambda r: r[1])
    out = []
    for i in range(1, len(ranges)):
        prev_e, prev_start, prev_end = ranges[i - 1]
        cur_e, start, end = ranges[i]
        if start < prev_end:
            overlap = min(prev_end, end) - start
            out.append((prev_e.name, cur_e.name, overlap))
    return out


def significant_overlaps(entries):
    """Overlaps that indicate real corruption: collisions where NEITHER side
    is a known metadata region (pgpt/pit/md5hdr)."""
    by_name = {e.name: e for e in entries}
    out = []
    for a, b, blocks in find_overlaps(entries):
        ea, eb = by_name.get(a), by_name.get(b)
        if ea is None or eb is None:
            out.append((a, b, blocks))
            continue
        if not (is_meta_entry(ea) or is_meta_entry(eb)):
            out.append((a, b, blocks))
    return out


def pit_report(raw: bytes):
    """Human-readable PIT table in the spirit of Heimdall's print-pit /
    Odin's Print button. Raises ValueError on bad magic (parse_pit rules).
    """
    entries = parse_pit(raw)
    model = parse_model(raw)
    lines = []
    header = f"PIT: {len(entries)} partitions"
    if model:
        header += f"  model={model}"
    lines.append(header)
    overlaps = significant_overlaps(entries)
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


# ---------------------------------------------------------------------------
# Intelligence layer: forensic validation, style detection, diff, map.
# ---------------------------------------------------------------------------

MAX_SANE_ENTRIES = 512


def validate_pit(raw: bytes):
    """Forensic PIT validation - the odin4 checklist plus FlashPilot's own
    chain analysis. Returns:

        { 'verdict': 'ok'|'warn'|'fail',
          'findings': [ {'severity','code','message'}, ... ],
          'stats': {...} }

    odin4 rejects devices/archives on the FAIL-level findings; FlashPilot
    surfaces them before anything is written instead of after.
    """
    findings = []

    def add(sev, code, msg):
        findings.append({"severity": sev, "code": code, "message": msg})

    stats = {"declared_count": 0, "parsed_count": 0, "model": "",
             "style": "unknown", "total_bytes": 0}

    if len(raw) < HEADER_SIZE:
        add("fail", "PIT_TOO_SHORT", f"PIT too small ({len(raw)} bytes)")
        return _health_result(findings, stats)
    magic = struct.unpack_from("<I", raw, HDR_MAGIC_OFF)[0]
    if magic != PIT_MAGIC:
        add("fail", "BAD_MAGIC", f"PIT file identifier mismatch: 0x{magic:08x}")
        return _health_result(findings, stats)

    model, unknown, project, reserved = parse_header(raw)
    declared = struct.unpack_from("<I", raw, HDR_COUNT_OFF)[0]
    stats["declared_count"] = declared
    stats["model"] = model

    if declared == 0:
        add("warn", "NO_ENTRIES", "PIT declares zero entries")
    elif declared > MAX_SANE_ENTRIES:
        add("fail", "COUNT_INSANE",
            f"Invalid PIT entry count: {declared} (>{MAX_SANE_ENTRIES})")

    # Truncation check (odin4: "PIT truncated: expected at least N bytes")
    needed = HEADER_SIZE + declared * ENTRY_SIZE
    if len(raw) < needed:
        add("fail", "TRUNCATED",
            f"PIT truncated: expected at least {needed} bytes, got {len(raw)}")

    try:
        all_entries = []
        for i in range(min(declared, MAX_SANE_ENTRIES)):
            off = HEADER_SIZE + i * ENTRY_SIZE
            if off + ENTRY_SIZE > len(raw):
                break
            all_entries.append(PitEntry(raw[off : off + ENTRY_SIZE], i))
    except Exception as e:  # pragma: no cover - defensive
        add("fail", "PARSE_ERROR", f"PIT parse error: {e}")
        return _health_result(findings, stats)

    stats["parsed_count"] = len(all_entries)
    flashable = [e for e in all_entries if e.is_flashable()]

    seen_ids = {}
    for e in flashable:
        if not e.name.strip():
            add("fail", "EMPTY_NAME",
                f"PIT entry {e.index} has an empty partition name")
        elif _clean_str_at(raw, HEADER_SIZE + e.index * ENTRY_SIZE + NAME_OFF) != e.name:
            add("fail", "INVALID_NAME",
                f"PIT entry {e.index} has an invalid partition name: {e.name!r}")
        if e.identifier == 0:
            add("fail", "IDENTIFIER_ZERO",
                f"PIT entry '{e.name}' has an invalid identifier (0)")
        if e.identifier in seen_ids:
            add("fail", "DUPLICATE_IDENTIFIER",
                f"PIT contains duplicate partition identifier "
                f"{e.identifier}: '{seen_ids[e.identifier]}' and '{e.name}'")
        else:
            seen_ids[e.identifier] = e.name

    sig = significant_overlaps(flashable)
    for a, b, blocks in sig[:8]:
        add("fail", "OVERLAP",
            f"partitions '{a}' and '{b}' overlap by {blocks} blocks "
            f"({blocks * SECTOR_SIZE} bytes) - corrupt or foreign table")

    meta_pairs = [p for p in find_overlaps(flashable)
                  if p not in {(x[0], x[1], x[2]) for x in sig}]
    for a, b, blocks in meta_pairs[:4]:
        add("info", "META_CONTAINMENT",
            f"'{b}' is contained in '{a}' ({blocks} blocks) - normal for "
            f"platform tables")

    stats["total_bytes"] = sum(e.block_count for e in flashable) * SECTOR_SIZE
    stats["style"] = pit_style(raw)
    return _health_result(findings, stats)


def _health_result(findings, stats):
    verdict = "ok"
    if any(f["severity"] == "fail" for f in findings):
        verdict = "fail"
    elif any(f["severity"] == "warn" for f in findings):
        verdict = "warn"
    return {"verdict": verdict, "findings": findings, "stats": stats}


def pit_style(raw):
    """Thor's old/new PIT semantic detection.

    'new': blockSizeOrOffset varies between entries -> it carries START
           BLOCKS (partition geometry present).
    'old': uniform value -> legacy 'block size' semantics (RO/RW/STL +
           FOTA/Secure bitmasks apply cleanly to attributes).
    """
    prev = None
    for e in parse_pit(raw):
        if e.block_size == 0 and e.block_count == 0:
            continue  # placeholder rows carry no geometry
        if prev is not None and e.block_size != prev:
            return "new"
        prev = e.block_size
    return "old"


def pit_health(raw: bytes):
    """One-call health check used by flows/GUI: verdict + style + summary."""
    result = validate_pit(raw)
    stats = result["stats"]
    result["summary"] = (
        f"PIT {result['verdict'].upper()}: {stats['parsed_count']}/"
        f"{stats['declared_count']} entries, style={stats['style']}, "
        f"{human_size(stats['total_bytes'])} accounted"
        + (f", model={stats['model']}" if stats["model"] else "")
    )
    return result


def pit_map(raw: bytes, width: int = 46):
    """ASCII storage-map bar with meta regions dimmed and overlaps marked.

    Example:
        storage map (new-style, 16.2 GB in table):
        [pppppppp][iiiiiii][mmmmmmmmmm][BBBBBBBBBBBBBBBB>........]
         pgpt 34B   pit 32B   md5hdr 8126B  bootloader ...
    """
    try:
        entries = [e for e in parse_pit(raw) if e.block_count > 0]
    except ValueError as e:
        return f"storage map: unavailable ({e})"
    style = pit_style(raw)
    if not entries:
        return "storage map: no sized partitions"

    max_end = max(e.block_offset + e.block_count for e in entries)
    total = sum(e.block_count for e in entries) * SECTOR_SIZE

    def char_at(pos):
        best = None
        for e in entries:
            if e.block_offset <= pos < e.block_offset + e.block_count:
                span = e.block_count
                if best is None or span < best[1]:
                    best = (e, span)
        if best is None:
            return "."
        e = best[0]
        if is_meta_entry(e):
            c = e.name.strip()[:1].lower() or "?"
        else:
            c = e.name.strip()[:1].upper() or "#"
        return c

    bar = "".join(char_at(i * max_end // width) for i in range(width))

    legend = []
    for e in sorted(entries, key=lambda x: -x.block_count)[:6]:
        mark = "*" if is_meta_entry(e) else " "
        legend.append(
            f"{mark}{e.name:<14} start={e.block_offset:<9} "
            f"{e.human_size():>9}"
        )

    lines = [
        f"storage map ({style}-style, {human_size(total)} in table):",
        f"[{bar}]",
    ]
    lines.extend(f"  {l}" for l in legend)
    sig = significant_overlaps(entries)
    if sig:
        lines.append(
            "  !! overlapping data partitions: "
            + ", ".join(f"{a}<->{b}" for a, b, _ in sig)
        )
    return "\n".join(lines)


def pit_diff(old_raw: bytes, new_raw: bytes):
    """Diff two PITs by normalized partition name (identifier fallback).

    Returns {'added': [...], 'removed': [...], 'changed': [...],
             'unchanged': int}. Changed entries list which of
    identifier/start/count/attributes/update_attributes moved.
    """
    def table(raw):
        out = {}
        for e in parse_pit(raw):
            key = normalize_part_name(e.name) or f"id{e.identifier}"
            out.setdefault(key, []).append(e)
        flat = {k: v[0] for k, v in out.items()}
        return flat

    old_t, new_t = table(old_raw), table(new_raw)
    added = sorted(set(new_t) - set(old_t))
    removed = sorted(set(old_t) - set(new_t))
    changed = []
    unchanged = 0
    for key in sorted(set(old_t) & set(new_t)):
        o, n = old_t[key], new_t[key]
        deltas = {}
        for field in ("identifier", "block_offset", "block_count",
                      "binary_type", "device_type", "attributes",
                      "update_attributes"):
            ov, nv = getattr(o, field), getattr(n, field)
            if ov != nv:
                deltas[field] = (ov, nv)
        if deltas:
            changed.append({"name": key, "changes": deltas})
        else:
            unchanged += 1
    return {"added": added, "removed": removed,
            "changed": changed, "unchanged": unchanged}


def pit_diff_report(old_raw: bytes, new_raw: bytes):
    """Human-readable diff ('no changes' when identical)."""
    d = pit_diff(old_raw, new_raw)
    lines = []
    if not (d["added"] or d["removed"] or d["changed"]):
        lines.append("PIT diff: no changes")
        return "\n".join(lines)
    if d["added"]:
        lines.append("added:   " + ", ".join(d["added"]))
    if d["removed"]:
        lines.append("removed: " + ", ".join(d["removed"]))
    for c in d["changed"]:
        parts = ", ".join(
            f"{f} {ov}->{nv}" for f, (ov, nv) in c["changes"].items()
        )
        lines.append(f"changed: {c['name']}: {parts}")
    lines.append(f"unchanged: {d['unchanged']} partitions")
    return "\n".join(lines)
