import struct

PIT_MAGIC = 0x12349876
HEADER_SIZE = 32
ENTRY_SIZE = 132
NAME_OFF = 32
FLASH_OFF = 64
FOTA_OFF = 96


class PitEntry:
    def __init__(self, data, index):
        self.index = index
        (
            self.binary_type,
            self.device_type,
            self.identifier,
            self.attributes,
            self.update_attributes,
            self.block_size,
            self.block_count,
            self.file_offset,
        ) = struct.unpack_from("<8I", data, 0)
        self.file_size = struct.unpack_from("<I", data, 128)[0]
        self.name = _str_at(data, NAME_OFF)
        self.flash_filename = _str_at(data, FLASH_OFF)
        self.fota_filename = _str_at(data, FOTA_OFF)

    def size_bytes(self):
        return self.block_size * self.block_count

    def is_flashable(self):
        return len(self.name) > 0

    def __repr__(self):
        return (
            f"PitEntry({self.index}: name={self.name!r} "
            f"file={self.flash_filename!r} device_type={self.device_type:#x} "
            f"size={self.size_bytes()})"
        )


def _str_at(data, offset):
    end = data.find(b"\x00", offset)
    if end == -1 or end > offset + 32:
        end = offset + 32
    return data[offset:end].decode("ascii", errors="replace")


def parse_pit(raw: bytes):
    if len(raw) < HEADER_SIZE:
        raise ValueError("PIT too short")
    magic = struct.unpack_from("<I", raw, 0)[0]
    if magic != PIT_MAGIC:
        raise ValueError(f"bad PIT magic: {magic:#x}")
    count = struct.unpack_from("<I", raw, 4)[0]
    entries = []
    for i in range(count):
        off = HEADER_SIZE + i * ENTRY_SIZE
        if off + ENTRY_SIZE > len(raw):
            break
        entry = PitEntry(raw[off : off + ENTRY_SIZE], i)
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


def validate_and_sanitize_pit(pit_raw: bytes, archive_part_names: list) -> tuple:
    """Compare firmware archive partitions against device PIT entries.
    Returns (is_compatible: bool, missing_in_pit: list, extra_in_archive: list, model: str).
    """
    try:
        entries = parse_pit(pit_raw)
        model = parse_model(pit_raw)
        device_parts = {e.name.lower() for e in entries}
        archive_parts = {p.lower() for p in archive_part_names}

        extra_in_archive = sorted(list(archive_parts - device_parts))
        missing_in_pit = sorted(list(device_parts - archive_parts))

        is_compatible = len(extra_in_archive) == 0
        return is_compatible, missing_in_pit, extra_in_archive, model
    except Exception:
        return True, [], [], ""


def hex_to_bytes(h):
    return bytes.fromhex(h)
