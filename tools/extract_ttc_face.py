"""Extract a single face from a TrueType Collection (.ttc) as a standalone
TrueType Font (.ttf), preserving every byte of every table — no fontTools
serializer, no hinting loss.

Usage:  python3 tools/extract_ttc_face.py src.ttc [face_number] [dst.ttf]
"""

import math
import struct
import sys
from pathlib import Path


def extract_face(src_path: str, face: int = 0, dst_path: str | None = None) -> Path:
    """Extract *face* from the TTC at *src_path*, write it to *dst_path*.

    Returns the path to the extracted TTF.
    """
    src = Path(src_path)
    if dst_path is None:
        dst_path = str(src.with_suffix(f".face{face}.ttf"))
    dst = Path(dst_path)

    data = src.read_bytes()

    # --- TTC Header ---
    magic = data[0:4]
    if magic != b"ttcf":
        raise ValueError(f"{src} is not a TrueType Collection (magic: {magic!r})")

    _version, num_fonts = struct.unpack_from(">II", data, 4)
    if face >= num_fonts:
        raise ValueError(f"Face {face} out of range (TTC has {num_fonts} fonts)")

    offsets = struct.unpack_from(f">{num_fonts}I", data, 12)
    dir_offset = offsets[face]

    # --- Face table directory ---
    sf_version = struct.unpack_from(">I", data, dir_offset)[0]
    num_tables = struct.unpack_from(">H", data, dir_offset + 4)[0]

    TTF_HEADER_SIZE = 12
    RECORD_SIZE = 16
    records_start = dir_offset + 12

    tables: list[tuple[str, int, int, int]] = []  # (tag, checksum, offset, length)
    for i in range(num_tables):
        off = records_start + i * RECORD_SIZE
        tag = data[off : off + 4].decode("ascii", errors="replace")
        checksum, table_offset, length = struct.unpack_from(">III", data, off + 4)
        tables.append((tag, checksum, table_offset, length))

    # Sort alphabetically by tag — required by TrueType spec for binary search
    tables.sort(key=lambda t: t[0])

    # --- Compute output layout ---
    data_start = TTF_HEADER_SIZE + num_tables * RECORD_SIZE
    cumulative = 0
    new_records: list[tuple[str, int, int, int]] = []  # (tag, checksum, new_offset, length)
    for tag, checksum, _old_offset, length in tables:
        if cumulative % 4 != 0:
            cumulative += 4 - (cumulative % 4)
        new_records.append((tag, checksum, cumulative, length))
        cumulative += length

    # --- Binary search parameters ---
    power = 1
    while power <= num_tables:
        power <<= 1
    power >>= 1
    search_range = power * 16
    entry_selector = int(math.log2(power)) if power > 0 else 0
    range_shift = num_tables * 16 - search_range

    # --- Write output ---
    with dst.open("wb") as out:
        # Offset table
        out.write(struct.pack(">I", sf_version))
        out.write(struct.pack(">H", num_tables))
        out.write(struct.pack(">H", search_range))
        out.write(struct.pack(">H", entry_selector))
        out.write(struct.pack(">H", range_shift))

        # Table records
        for tag, checksum, new_offset, length in new_records:
            out.write(tag.encode("ascii"))
            out.write(struct.pack(">I", checksum))
            out.write(struct.pack(">I", data_start + new_offset))
            out.write(struct.pack(">I", length))

        # Table data (byte-for-byte from original TTC)
        written = 0
        for tag, _checksum, new_offset, length in new_records:
            while written < new_offset:
                out.write(b"\x00")
                written += 1
            # Find original table bytes
            for t_tag, _t_cs, t_offset, t_length in tables:
                if t_tag == tag:
                    out.write(data[t_offset : t_offset + t_length])
                    written += length
                    break

    return dst


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    face = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    dst = sys.argv[3] if len(sys.argv) > 3 else None
    result = extract_face(src, face, dst)
    print(f"{result} ({result.stat().st_size:,} bytes)")
