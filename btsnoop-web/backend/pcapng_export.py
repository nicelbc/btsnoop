"""
pcapng export module.

Converts btsnoop session data to pcapng format that Wireshark can open.
Uses LINKTYPE_BLUETOOTH_HCI_H4 (187) for HCI UART transport.
"""

from __future__ import annotations

import struct
import time
from typing import Generator

from parser.models import PacketSummary, Direction
from parser.btsnoop import BTSNOOP_EPOCH_OFFSET


# pcapng constants
PCAPNG_BYTE_ORDER_MAGIC = 0x1A2B3C4D
PCAPNG_SHB_TYPE = 0x0A0D0D0A  # Section Header Block
PCAPNG_IDB_TYPE = 0x00000001  # Interface Description Block
PCAPNG_EPB_TYPE = 0x00000006  # Enhanced Packet Block

# Link types
LINKTYPE_BLUETOOTH_HCI_H4 = 187
LINKTYPE_BLUETOOTH_HCI_H4_WITH_PHDR = 201


def _pad4(length: int) -> int:
    """Pad to 4-byte boundary."""
    return (4 - (length % 4)) % 4


def generate_pcapng(
    raw_packets: list[bytes],
    flags_list: list[int],
    summaries: list[PacketSummary],
) -> Generator[bytes, None, None]:
    """
    Generate pcapng file data as a stream of bytes chunks.

    Uses LINKTYPE_BLUETOOTH_HCI_H4_WITH_PHDR which includes a 4-byte
    direction pseudo-header before each HCI packet.
    """
    # Section Header Block (SHB)
    shb_options = b""
    # Option: shb_userappl
    app_name = b"btsnoop-web"
    opt = struct.pack("<HH", 4, len(app_name)) + app_name + b"\x00" * _pad4(len(app_name))
    shb_options += opt
    # End of options
    shb_options += struct.pack("<HH", 0, 0)

    shb_body = struct.pack("<IHH", PCAPNG_BYTE_ORDER_MAGIC, 1, 0) + struct.pack("<q", -1) + shb_options
    shb_total_len = 12 + len(shb_body) + 4  # type(4) + len(4) + body + trailing_len(4)
    yield struct.pack("<II", PCAPNG_SHB_TYPE, shb_total_len) + shb_body + struct.pack("<I", shb_total_len)

    # Interface Description Block (IDB)
    idb_options = b""
    # Option: if_name
    if_name = b"btsnoop_hci"
    opt = struct.pack("<HH", 2, len(if_name)) + if_name + b"\x00" * _pad4(len(if_name))
    idb_options += opt
    # Option: if_tsresol (microsecond resolution = 6)
    opt = struct.pack("<HH", 9, 1) + b"\x06" + b"\x00" * 3
    idb_options += opt
    # End of options
    idb_options += struct.pack("<HH", 0, 0)

    idb_body = struct.pack("<HH", LINKTYPE_BLUETOOTH_HCI_H4_WITH_PHDR, 0) + struct.pack("<I", 0) + idb_options
    idb_total_len = 12 + len(idb_body)
    yield struct.pack("<II", PCAPNG_IDB_TYPE, idb_total_len) + idb_body + struct.pack("<I", idb_total_len)

    # Enhanced Packet Blocks (EPB)
    for i, (raw, flags, summary) in enumerate(zip(raw_packets, flags_list, summaries)):
        # Direction pseudo-header (4 bytes): 0=sent, 1=received
        direction = 0x01 if (flags & 1) else 0x00
        phdr = struct.pack("<I", direction)
        packet_data = phdr + raw

        # Timestamp: convert btsnoop timestamp to microseconds since Unix epoch
        ts_us = summary.timestamp_us - BTSNOOP_EPOCH_OFFSET
        # pcapng timestamp is in units of if_tsresol (microseconds)
        ts_high = (ts_us >> 32) & 0xFFFFFFFF
        ts_low = ts_us & 0xFFFFFFFF

        captured_len = len(packet_data)
        original_len = len(phdr) + summary.raw_length
        padding = b"\x00" * _pad4(captured_len)

        epb_body = struct.pack("<IIIII",
            0,  # interface ID
            ts_high,
            ts_low,
            captured_len,
            original_len,
        ) + packet_data + padding
        # No options
        epb_total_len = 12 + len(epb_body)
        yield struct.pack("<II", PCAPNG_EPB_TYPE, epb_total_len) + epb_body + struct.pack("<I", epb_total_len)
