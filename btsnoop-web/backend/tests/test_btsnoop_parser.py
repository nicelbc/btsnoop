"""
Tests for btsnoop file format parsing (parser/btsnoop.py).

Tests:
  - Valid file header parse
  - Invalid magic bytes rejection
  - Record parsing with known data
  - Timestamp conversion correctness
  - Iterator behavior (BtSnoopReader)
"""

from __future__ import annotations

import io
import struct
import datetime

import pytest

from parser.btsnoop import (
    BtSnoopReader,
    BtSnoopFileHeader,
    BtSnoopRecord,
    BTSNOOP_EPOCH_OFFSET,
    FILE_HEADER_SIZE,
    RECORD_HEADER_SIZE,
    MAGIC,
    parse_file_header,
    parse_record_header,
    parse_bytes,
    timestamp_to_str,
    timestamp_to_datetime,
)
from parser.models import Direction

from .conftest import (
    build_btsnoop_file_header,
    build_btsnoop_record,
    build_btsnoop_file,
    build_hci_command,
    build_hci_event,
)


class TestFileHeader:
    """Tests for btsnoop file header parsing."""

    def test_valid_header_default(self, valid_btsnoop_header):
        """Parse a valid file header with default version=1, datalink=1002."""
        hdr = parse_file_header(valid_btsnoop_header)
        assert isinstance(hdr, BtSnoopFileHeader)
        assert hdr.version == 1
        assert hdr.datalink_type == 1002

    def test_valid_header_custom_version(self):
        """Parse a header with non-default version."""
        data = build_btsnoop_file_header(version=2, datalink_type=1003)
        hdr = parse_file_header(data)
        assert hdr.version == 2
        assert hdr.datalink_type == 1003

    def test_invalid_magic_bytes(self):
        """Reject data that doesn't start with btsnoop magic."""
        bad_data = b"notsnoop" + struct.pack(">II", 1, 1002)
        with pytest.raises(ValueError, match="Not a valid btsnoop file"):
            parse_file_header(bad_data)

    def test_header_too_short(self):
        """Reject data that is too short."""
        with pytest.raises(ValueError, match="too short"):
            parse_file_header(b"btsnoop\x00\x00")

    def test_partial_magic(self):
        """Reject data with partial magic."""
        with pytest.raises(ValueError, match="too short"):
            parse_file_header(b"btsno")

    def test_wrong_null_terminator(self):
        """Reject btsnoop without null terminator in magic."""
        bad = b"btsnoop\x01" + struct.pack(">II", 1, 1002)
        with pytest.raises(ValueError, match="magic mismatch"):
            parse_file_header(bad)


class TestRecordHeader:
    """Tests for btsnoop record header parsing."""

    def test_parse_record_header_basic(self):
        """Parse a record header with known values."""
        orig_len = 10
        incl_len = 10
        flags = 0x01  # received
        drops = 0
        ts = BTSNOOP_EPOCH_OFFSET + 1000000  # +1 second from epoch
        ts_hi = (ts >> 32) & 0xFFFFFFFF
        ts_lo = ts & 0xFFFFFFFF
        data = struct.pack(">IIIIII", orig_len, incl_len, flags, drops, ts_hi, ts_lo)

        result = parse_record_header(data)
        assert result == (orig_len, incl_len, flags, drops, ts)

    def test_parse_record_header_too_short(self):
        """Reject record header that is too short."""
        with pytest.raises(ValueError, match="too short"):
            parse_record_header(b"\x00" * 20)

    def test_record_flags_direction(self):
        """Verify flags bit 0 indicates direction."""
        data_sent = struct.pack(">IIIIII", 5, 5, 0, 0, 0, 0)
        data_recv = struct.pack(">IIIIII", 5, 5, 1, 0, 0, 0)

        _, _, flags_sent, _, _ = parse_record_header(data_sent)
        _, _, flags_recv, _, _ = parse_record_header(data_recv)

        assert flags_sent & 1 == 0  # sent
        assert flags_recv & 1 == 1  # received


class TestTimestamp:
    """Tests for timestamp conversion functions."""

    def test_timestamp_at_epoch(self):
        """Timestamp at exactly the btsnoop epoch offset = 2000-01-01 00:00:00."""
        ts = BTSNOOP_EPOCH_OFFSET
        result = timestamp_to_str(ts)
        assert result == "00:00:00.000"

    def test_timestamp_one_second_after_epoch(self):
        """Timestamp 1 second after epoch."""
        ts = BTSNOOP_EPOCH_OFFSET + 1_000_000
        result = timestamp_to_str(ts)
        assert result == "00:00:01.000"

    def test_timestamp_with_milliseconds(self):
        """Timestamp with fractional seconds."""
        ts = BTSNOOP_EPOCH_OFFSET + 1_234_567  # 1.234567 seconds
        result = timestamp_to_str(ts)
        assert result == "00:00:01.234"

    def test_timestamp_to_datetime_basic(self):
        """Convert timestamp to datetime object."""
        ts = BTSNOOP_EPOCH_OFFSET
        dt = timestamp_to_datetime(ts)
        assert dt is not None
        assert dt.year == 2000
        assert dt.month == 1
        assert dt.day == 1
        assert dt.hour == 0
        assert dt.minute == 0
        assert dt.second == 0

    def test_timestamp_to_datetime_specific(self):
        """Convert a specific known timestamp."""
        # 2000-01-01 12:30:45.000
        offset = (12 * 3600 + 30 * 60 + 45) * 1_000_000
        ts = BTSNOOP_EPOCH_OFFSET + offset
        dt = timestamp_to_datetime(ts)
        assert dt is not None
        assert dt.hour == 12
        assert dt.minute == 30
        assert dt.second == 45

    def test_timestamp_overflow_returns_placeholder(self):
        """Overflowed timestamp returns placeholder string."""
        result = timestamp_to_str(0)
        # Should not crash; either returns valid string or placeholder
        assert isinstance(result, str)


class TestBtSnoopReader:
    """Tests for BtSnoopReader iterator behavior."""

    def test_read_empty_file(self):
        """Reader with only file header yields no records."""
        data = build_btsnoop_file_header()
        reader = BtSnoopReader(io.BytesIO(data))
        records = list(reader)
        assert records == []

    def test_read_single_record(self):
        """Reader yields exactly one record from a single-record file."""
        pkt = build_hci_command(0x0C03)  # Reset
        file_data = build_btsnoop_file([(pkt, 0x00)])
        reader = BtSnoopReader(io.BytesIO(file_data))
        records = list(reader)
        assert len(records) == 1
        assert records[0].data == pkt
        assert records[0].flags == 0
        assert records[0].direction == Direction.SENT

    def test_read_multiple_records(self):
        """Reader yields all records in order."""
        pkt1 = build_hci_command(0x0C03)
        pkt2 = build_hci_event(0x0E, struct.pack("<BHB", 1, 0x0C03, 0))
        pkt3 = build_hci_command(0x0405, b"\x00" * 13)

        file_data = build_btsnoop_file([
            (pkt1, 0x00),
            (pkt2, 0x01),
            (pkt3, 0x00),
        ])
        reader = BtSnoopReader(io.BytesIO(file_data))
        records = list(reader)
        assert len(records) == 3
        assert records[0].data == pkt1
        assert records[1].data == pkt2
        assert records[2].data == pkt3

    def test_reader_direction_flags(self):
        """Reader correctly identifies direction from flags."""
        pkt = build_hci_command(0x0C03)
        file_data = build_btsnoop_file([
            (pkt, 0x00),  # sent (bit0=0)
            (pkt, 0x01),  # received (bit0=1)
        ])
        reader = BtSnoopReader(io.BytesIO(file_data))
        records = list(reader)
        assert records[0].direction == Direction.SENT
        assert records[1].direction == Direction.RECEIVED

    def test_reader_properties(self):
        """Reader exposes version and datalink_type from file header."""
        file_data = build_btsnoop_file_header(version=1, datalink_type=1002)
        reader = BtSnoopReader(io.BytesIO(file_data))
        assert reader.version == 1
        assert reader.datalink_type == 1002

    def test_reader_truncated_record_header(self):
        """Reader stops gracefully if record header is truncated."""
        file_data = build_btsnoop_file_header()
        file_data += b"\x00" * 10  # Partial record header
        reader = BtSnoopReader(io.BytesIO(file_data))
        records = list(reader)
        assert records == []

    def test_reader_truncated_payload(self):
        """Reader stops if record payload is truncated."""
        file_data = build_btsnoop_file_header()
        # Record header says 100 bytes of payload, but we only provide 5
        ts = BTSNOOP_EPOCH_OFFSET
        ts_hi = (ts >> 32) & 0xFFFFFFFF
        ts_lo = ts & 0xFFFFFFFF
        rec_hdr = struct.pack(">IIIIII", 100, 100, 0, 0, ts_hi, ts_lo)
        file_data += rec_hdr + b"\x00" * 5
        reader = BtSnoopReader(io.BytesIO(file_data))
        records = list(reader)
        assert records == []

    def test_reader_invalid_file_header_raises(self):
        """Reader raises ValueError if file header is invalid."""
        with pytest.raises(ValueError):
            BtSnoopReader(io.BytesIO(b"notsnoop12345678"))

    def test_record_timestamp_str(self):
        """BtSnoopRecord.timestamp_str property works."""
        pkt = build_hci_command(0x0C03)
        ts = BTSNOOP_EPOCH_OFFSET + 5_500_000  # 5.5 seconds
        file_data = build_btsnoop_file_header()
        file_data += build_btsnoop_record(pkt, timestamp_us=ts)
        reader = BtSnoopReader(io.BytesIO(file_data))
        records = list(reader)
        assert len(records) == 1
        assert records[0].timestamp_str == "00:00:05.500"


class TestParseBytes:
    """Tests for parse_bytes() function."""

    def test_parse_bytes_basic(self):
        """parse_bytes yields records from raw bytes."""
        pkt = build_hci_command(0x0C03)
        raw = build_btsnoop_file([(pkt, 0x00)])
        records = list(parse_bytes(raw))
        assert len(records) == 1
        assert records[0].data == pkt

    def test_parse_bytes_too_short(self):
        """parse_bytes raises on too-short data."""
        with pytest.raises(ValueError):
            list(parse_bytes(b"\x00" * 10))

    def test_parse_bytes_multiple_records(self):
        """parse_bytes handles multiple records."""
        pkt1 = build_hci_command(0x0C03)
        pkt2 = build_hci_event(0x0E, b"\x01\x03\x0C\x00")
        raw = build_btsnoop_file([(pkt1, 0), (pkt2, 1)])
        records = list(parse_bytes(raw))
        assert len(records) == 2
