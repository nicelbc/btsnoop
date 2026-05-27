"""
Shared fixtures for btsnoop-web backend tests.

Provides:
  - Sample btsnoop file data (valid headers, records)
  - Common HCI/L2CAP/ATT packet constructors
  - SessionState fixtures
"""

from __future__ import annotations

import struct
import io
from typing import Optional

import pytest

from parser.models import SessionState, Direction
from parser.btsnoop import (
    BTSNOOP_EPOCH_OFFSET,
    FILE_HEADER_SIZE,
    RECORD_HEADER_SIZE,
    MAGIC,
)


# ─── btsnoop file building helpers ───


def build_btsnoop_file_header(version: int = 1, datalink_type: int = 1002) -> bytes:
    """Build a valid 16-byte btsnoop file header."""
    return MAGIC + struct.pack(">II", version, datalink_type)


def build_btsnoop_record(
    data: bytes,
    flags: int = 0,
    drops: int = 0,
    timestamp_us: Optional[int] = None,
    orig_len: Optional[int] = None,
) -> bytes:
    """
    Build a btsnoop record (24-byte header + payload).

    Args:
        data: packet data
        flags: record flags (bit0=direction, bit1=cmd/evt)
        drops: cumulative drops
        timestamp_us: raw btsnoop timestamp (microseconds since epoch 0 AD).
                     If None, uses BTSNOOP_EPOCH_OFFSET (= 2000-01-01 00:00:00)
        orig_len: original length; defaults to len(data)
    """
    if timestamp_us is None:
        # Default to 2000-01-01 00:00:00.000000
        timestamp_us = BTSNOOP_EPOCH_OFFSET
    if orig_len is None:
        orig_len = len(data)
    incl_len = len(data)
    ts_hi = (timestamp_us >> 32) & 0xFFFFFFFF
    ts_lo = timestamp_us & 0xFFFFFFFF
    header = struct.pack(">IIIIII", orig_len, incl_len, flags, drops, ts_hi, ts_lo)
    return header + data


def build_btsnoop_file(records: list[tuple[bytes, int]], version: int = 1) -> bytes:
    """
    Build a complete btsnoop file from a list of (data, flags) tuples.
    """
    buf = build_btsnoop_file_header(version=version)
    for data, flags in records:
        buf += build_btsnoop_record(data, flags=flags)
    return buf


# ─── HCI packet builders ───


def build_hci_command(opcode: int, params: bytes = b"") -> bytes:
    """Build HCI Command packet: [0x01][opcode_le16][param_len][params]."""
    return struct.pack("<BHB", 0x01, opcode, len(params)) + params


def build_hci_event(event_code: int, params: bytes = b"") -> bytes:
    """Build HCI Event packet: [0x04][event_code][param_len][params]."""
    return struct.pack("BBB", 0x04, event_code, len(params)) + params


def build_hci_acl(handle: int, pb_flag: int, bc_flag: int, payload: bytes) -> bytes:
    """
    Build HCI ACL data packet.
    [0x02][handle_flags_le16][data_len_le16][payload]
    handle_flags = handle(12bit) | pb_flag(2bit) | bc_flag(2bit)
    """
    hf = (handle & 0x0FFF) | ((pb_flag & 0x03) << 12) | ((bc_flag & 0x03) << 14)
    return struct.pack("<BHH", 0x02, hf, len(payload)) + payload


# ─── L2CAP packet builders ───


def build_l2cap(cid: int, payload: bytes) -> bytes:
    """Build L2CAP basic frame: [length_le16][cid_le16][payload]."""
    return struct.pack("<HH", len(payload), cid) + payload


def build_l2cap_signaling(code: int, identifier: int, sig_data: bytes) -> bytes:
    """Build L2CAP signaling PDU: [code][id][length_le16][data]."""
    return struct.pack("<BBH", code, identifier, len(sig_data)) + sig_data


# ─── ATT packet builders ───


def build_att_exchange_mtu_req(mtu: int) -> bytes:
    """Build ATT Exchange MTU Request."""
    return struct.pack("<BH", 0x02, mtu)


def build_att_exchange_mtu_rsp(mtu: int) -> bytes:
    """Build ATT Exchange MTU Response."""
    return struct.pack("<BH", 0x03, mtu)


def build_att_read_by_group_type_req(
    start_handle: int, end_handle: int, uuid16: int
) -> bytes:
    """Build ATT Read By Group Type Request with UUID16."""
    return struct.pack("<BHHH", 0x10, start_handle, end_handle, uuid16)


def build_att_write_req(handle: int, value: bytes) -> bytes:
    """Build ATT Write Request."""
    return struct.pack("<BH", 0x12, handle) + value


def build_att_error_rsp(
    req_opcode: int, handle: int, error_code: int
) -> bytes:
    """Build ATT Error Response."""
    return struct.pack("<BBHB", 0x01, req_opcode, handle, error_code)


# ─── Fixtures ───


@pytest.fixture
def session_state():
    """Fresh SessionState for tests."""
    return SessionState()


@pytest.fixture
def valid_btsnoop_header():
    """Valid 16-byte btsnoop file header."""
    return build_btsnoop_file_header()


@pytest.fixture
def hci_reset_cmd():
    """HCI Reset command (opcode 0x0C03, no params)."""
    return build_hci_command(0x0C03)


@pytest.fixture
def hci_create_connection_cmd():
    """HCI Create_Connection command (opcode 0x0405) with BD_ADDR."""
    # BD_ADDR = aa:bb:cc:dd:ee:ff (stored little-endian in params)
    bd_addr = bytes([0xFF, 0xEE, 0xDD, 0xCC, 0xBB, 0xAA])
    # params: BD_ADDR(6) + packet_type(2) + page_scan_rep(1) + reserved(1) + clock_offset(2) + allow_role_switch(1)
    params = bd_addr + struct.pack("<HBBHB", 0xCC18, 0x02, 0x00, 0x0000, 0x01)
    return build_hci_command(0x0405, params)


@pytest.fixture
def hci_cmd_complete_event():
    """HCI Command Complete event for Reset (0x0E)."""
    # params: num_hci_cmd_packets(1) + opcode(2 LE) + status(1)
    params = struct.pack("<BHB", 0x01, 0x0C03, 0x00)
    return build_hci_event(0x0E, params)


@pytest.fixture
def hci_disconn_complete_event():
    """HCI Disconnection Complete event (0x05)."""
    # params: status(1) + handle(2 LE) + reason(1)
    params = struct.pack("<BHB", 0x00, 0x0040, 0x13)
    return build_hci_event(0x05, params)


@pytest.fixture
def sample_btsnoop_file():
    """A complete btsnoop file with a few packets."""
    reset_cmd = build_hci_command(0x0C03)
    cmd_complete = build_hci_event(0x0E, struct.pack("<BHB", 0x01, 0x0C03, 0x00))

    records = [
        (reset_cmd, 0x00),      # sent command
        (cmd_complete, 0x01),   # received event
    ]
    return build_btsnoop_file(records)
