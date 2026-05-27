"""
btsnoop file format parser.

File format:
  - 16-byte file header: "btsnoop\0" (8 bytes) + version (4 bytes BE) + datalink type (4 bytes BE)
  - Records: each record has a 24-byte header followed by packet data

Record header (24 bytes, all fields big-endian):
  - original_length (4 bytes)
  - included_length (4 bytes)
  - flags (4 bytes): bit 0 = direction (0=sent, 1=received), bits 1-31 reserved
  - cumulative_drops (4 bytes)
  - timestamp (8 bytes): microseconds since 2000-01-01 00:00:00 UTC

Timestamp conversion:
  The btsnoop timestamp epoch is 2000-01-01 00:00:00.
  Offset from Unix epoch: 0x00dcddb30f2f8000 microseconds.
"""

from __future__ import annotations

import datetime
import struct
from dataclasses import dataclass
from typing import BinaryIO, Generator, Optional

from .models import Direction


# btsnoop timestamp offset: microseconds between 0 AD and 2000-01-01
BTSNOOP_EPOCH_OFFSET = 0x00DCDDB30F2F8000

FILE_HEADER_SIZE = 16
RECORD_HEADER_SIZE = 24
MAGIC = b"btsnoop\x00"


@dataclass
class BtSnoopFileHeader:
    """Parsed btsnoop file header."""
    version: int
    datalink_type: int


@dataclass
class BtSnoopRecord:
    """A single btsnoop record."""
    original_length: int
    included_length: int
    flags: int
    cumulative_drops: int
    timestamp_us: int  # raw microsecond timestamp
    data: bytes

    @property
    def direction(self) -> Direction:
        """Packet direction from flags bit 0."""
        if self.flags & 1:
            return Direction.RECEIVED
        return Direction.SENT

    @property
    def timestamp_str(self) -> str:
        """Human-readable timestamp string (HH:MM:SS.mmm)."""
        return timestamp_to_str(self.timestamp_us)


def timestamp_to_str(ts_us: int) -> str:
    """
    Convert btsnoop raw timestamp (microseconds) to readable time string.
    The timestamp counts microseconds since 0000-01-01 00:00:00.
    We subtract the epoch offset to get microseconds since 2000-01-01,
    then convert to a datetime.
    """
    try:
        dt = datetime.datetime(2000, 1, 1) + datetime.timedelta(
            microseconds=ts_us - BTSNOOP_EPOCH_OFFSET
        )
        return dt.strftime("%H:%M:%S.%f")[:-3]
    except (OverflowError, ValueError, OSError):
        return "??:??:??.???"


def timestamp_to_datetime(ts_us: int) -> Optional[datetime.datetime]:
    """
    Convert btsnoop raw timestamp to a datetime object.
    Returns None on error.
    """
    try:
        return datetime.datetime(2000, 1, 1) + datetime.timedelta(
            microseconds=ts_us - BTSNOOP_EPOCH_OFFSET
        )
    except (OverflowError, ValueError, OSError):
        return None


def parse_file_header(data: bytes) -> BtSnoopFileHeader:
    """
    Parse the 16-byte btsnoop file header.
    Raises ValueError if the magic number doesn't match.
    """
    if len(data) < FILE_HEADER_SIZE:
        raise ValueError(f"File header too short: {len(data)} bytes (need {FILE_HEADER_SIZE})")
    if data[:8] != MAGIC:
        raise ValueError("Not a valid btsnoop file (magic mismatch)")
    version, datalink_type = struct.unpack(">II", data[8:16])
    return BtSnoopFileHeader(version=version, datalink_type=datalink_type)


def parse_record_header(data: bytes) -> tuple[int, int, int, int, int]:
    """
    Parse a 24-byte record header.
    Returns: (original_length, included_length, flags, cumulative_drops, timestamp_us)
    """
    if len(data) < RECORD_HEADER_SIZE:
        raise ValueError(f"Record header too short: {len(data)} bytes")
    orig_len, incl_len, flags, drops, ts_hi, ts_lo = struct.unpack(">IIIIII", data)
    timestamp_us = (ts_hi << 32) | ts_lo
    return orig_len, incl_len, flags, drops, timestamp_us


def parse_record(header_data: bytes, payload_data: bytes) -> BtSnoopRecord:
    """Parse a complete record from header bytes and payload bytes."""
    orig_len, incl_len, flags, drops, ts_us = parse_record_header(header_data)
    return BtSnoopRecord(
        original_length=orig_len,
        included_length=incl_len,
        flags=flags,
        cumulative_drops=drops,
        timestamp_us=ts_us,
        data=payload_data[:incl_len],
    )


class BtSnoopReader:
    """
    Iterator-based btsnoop file reader.
    Reads the file header on construction, then yields records.
    """

    def __init__(self, fileobj: BinaryIO):
        self._f = fileobj
        self._offset = 0
        # Read and validate file header
        hdr_data = self._f.read(FILE_HEADER_SIZE)
        self.header = parse_file_header(hdr_data)
        self._offset = FILE_HEADER_SIZE

    @property
    def version(self) -> int:
        return self.header.version

    @property
    def datalink_type(self) -> int:
        return self.header.datalink_type

    def read_record(self) -> Optional[BtSnoopRecord]:
        """Read the next record. Returns None at EOF."""
        rec_hdr = self._f.read(RECORD_HEADER_SIZE)
        if len(rec_hdr) < RECORD_HEADER_SIZE:
            return None
        orig_len, incl_len, flags, drops, ts_us = parse_record_header(rec_hdr)
        payload = self._f.read(incl_len)
        if len(payload) < incl_len:
            return None
        self._offset += RECORD_HEADER_SIZE + incl_len
        return BtSnoopRecord(
            original_length=orig_len,
            included_length=incl_len,
            flags=flags,
            cumulative_drops=drops,
            timestamp_us=ts_us,
            data=payload,
        )

    def __iter__(self) -> Generator[BtSnoopRecord, None, None]:
        """Iterate over all records in the file."""
        while True:
            record = self.read_record()
            if record is None:
                return
            yield record

    @property
    def offset(self) -> int:
        """Current file offset."""
        return self._offset


def parse_bytes(raw: bytes) -> Generator[BtSnoopRecord, None, None]:
    """
    Parse btsnoop records from a raw bytes buffer.
    Yields BtSnoopRecord objects.
    """
    if len(raw) < FILE_HEADER_SIZE:
        raise ValueError("Data too short for btsnoop file header")
    _ = parse_file_header(raw[:FILE_HEADER_SIZE])
    pos = FILE_HEADER_SIZE
    while pos + RECORD_HEADER_SIZE <= len(raw):
        orig_len, incl_len, flags, drops, ts_us = parse_record_header(
            raw[pos : pos + RECORD_HEADER_SIZE]
        )
        pos += RECORD_HEADER_SIZE
        if pos + incl_len > len(raw):
            break
        payload = raw[pos : pos + incl_len]
        pos += incl_len
        yield BtSnoopRecord(
            original_length=orig_len,
            included_length=incl_len,
            flags=flags,
            cumulative_drops=drops,
            timestamp_us=ts_us,
            data=payload,
        )
