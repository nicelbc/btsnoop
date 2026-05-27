"""
btsnoop packet parser module.

This module provides a complete parsing pipeline for btsnoop HCI log files:
  btsnoop record -> HCI -> L2CAP -> upper protocol (AVDTP, AVRCP, ATT, SMP, SDP)

Main entry points:
  - parse_packet(data, flags, session) -> list[DecodedLayer]
  - parse_file(fileobj) -> Generator[PacketSummary]
  - SessionState: maintains CID-PSM mapping across packets

Example usage:
    from backend.parser import parse_packet, SessionState, BtSnoopReader
    from backend.parser.models import Direction

    session = SessionState()
    with open('btsnoop_hci.log', 'rb') as f:
        reader = BtSnoopReader(f)
        for record in reader:
            layers = parse_packet(record.data, record.flags, session)
            for layer in layers:
                print(f"  {layer.protocol}: {layer.summary}")
"""

from __future__ import annotations

import struct
from typing import BinaryIO, Generator, List, Optional

from .models import (
    DecodedField,
    DecodedLayer,
    Direction,
    HciType,
    PacketSummary,
    SessionState,
)
from .btsnoop import (
    BtSnoopFileHeader,
    BtSnoopRecord,
    BtSnoopReader,
    parse_bytes,
    parse_file_header,
    timestamp_to_str,
    timestamp_to_datetime,
)
from . import hci
from . import l2cap
from . import avdtp
from . import avrcp
from . import att
from . import smp


def parse_packet(
    data: bytes, flags: int, session: Optional[SessionState] = None
) -> List[DecodedLayer]:
    """
    Parse a single btsnoop packet through all protocol layers.

    Args:
        data: raw packet data from a btsnoop record
        flags: record flags (bit 0 = direction)
        session: optional SessionState for CID-PSM tracking; if None, a temporary one is used

    Returns:
        List of DecodedLayer objects, one per protocol layer decoded
    """
    if session is None:
        session = SessionState()

    try:
        return _parse_packet_inner(data, flags, session)
    except Exception as e:
        return [DecodedLayer(
            protocol="ERROR",
            summary=f"Decode error: {e}",
            fields=[DecodedField(name="raw_type", value=f"0x{data[0]:02x}" if data else "empty")],
        )]


def _parse_packet_inner(
    data: bytes, flags: int, session: SessionState
) -> List[DecodedLayer]:
    """Internal parse implementation (may raise on malformed data)."""
    layers: List[DecodedLayer] = []

    if len(data) < 1:
        layers.append(DecodedLayer(protocol="UNKNOWN", summary="(empty)"))
        return layers

    pkt_type = data[0]

    # --- HCI Command ---
    if pkt_type == HciType.COMMAND.value:
        layer = hci.decode_hci_command(data)
        layers.append(layer)
        return layers

    # --- HCI Event ---
    elif pkt_type == HciType.EVENT.value:
        layer = hci.decode_hci_event(data)
        layers.append(layer)

        # Track connection handles from Connection Complete events
        if len(data) > 1 and data[1] == 0x03 and len(data) >= 14:
            status = data[3]
            if status == 0:
                handle = struct.unpack("<H", data[4:6])[0]
                addr = ":".join(f"{b:02x}" for b in reversed(data[6:12]))
                session.handle_to_addr[handle] = addr

        return layers

    # --- HCI ACL Data ---
    elif pkt_type == HciType.ACL.value:
        acl_layer, handle, acl_payload = hci.decode_hci_acl(data)
        layers.append(acl_layer)

        # Decode L2CAP
        if len(acl_payload) >= 4:
            l2cap_layer, upper_proto, upper_payload = l2cap.decode(acl_payload, session)
            layers.append(l2cap_layer)

            # Decode upper protocol
            if upper_proto == "L2CAP_SIG":
                sig_layer = l2cap.decode_signaling(upper_payload, session)
                layers.append(sig_layer)

            elif upper_proto == "LE_L2CAP_SIG":
                sig_layer = l2cap.decode_signaling(upper_payload, session)
                sig_layer.protocol = "LE_L2CAP_SIG"
                layers.append(sig_layer)

            elif upper_proto == "AVDTP":
                if len(upper_payload) >= 2:
                    avdtp_layer = avdtp.decode(upper_payload)
                    layers.append(avdtp_layer)

            elif upper_proto == "AVCTP" or upper_proto == "AVCTP_BROWSING":
                if len(upper_payload) >= 3:
                    avrcp_layer = avrcp.decode(upper_payload)
                    layers.append(avrcp_layer)

            elif upper_proto == "ATT":
                if len(upper_payload) >= 1:
                    att_layer = att.decode(upper_payload)
                    layers.append(att_layer)

            elif upper_proto == "SMP":
                if len(upper_payload) >= 1:
                    smp_layer = smp.decode(upper_payload)
                    layers.append(smp_layer)

            elif upper_proto == "SDP":
                layers.append(DecodedLayer(
                    protocol="SDP",
                    summary=f"SDP len={len(upper_payload)}",
                    payload=upper_payload,
                ))

            elif upper_proto == "RFCOMM":
                layers.append(DecodedLayer(
                    protocol="RFCOMM",
                    summary=f"RFCOMM len={len(upper_payload)}",
                    payload=upper_payload,
                ))

        return layers

    # --- HCI SCO ---
    elif pkt_type == HciType.SCO.value:
        layer = hci.decode_hci_sco(data)
        layers.append(layer)
        return layers

    # --- HCI ISO ---
    elif pkt_type == HciType.ISO.value:
        layer = hci.decode_hci_iso(data)
        layers.append(layer)
        return layers

    # --- Unknown ---
    else:
        layers.append(DecodedLayer(
            protocol="UNKNOWN",
            summary=f"type=0x{pkt_type:02X} len={len(data)}",
            payload=data[1:],
        ))
        return layers


def get_packet_protocol(layers: List[DecodedLayer]) -> str:
    """
    Determine the highest-level (most specific) protocol from a layer stack.
    Returns the protocol name of the topmost layer.
    """
    if not layers:
        return "UNKNOWN"
    return layers[-1].protocol


def get_packet_summary(layers: List[DecodedLayer]) -> str:
    """
    Get the most informative summary from the layer stack.
    Usually this is the topmost layer's summary.
    """
    if not layers:
        return ""
    return layers[-1].summary


def parse_file(
    fileobj: BinaryIO, session: Optional[SessionState] = None
) -> Generator[PacketSummary, None, None]:
    """
    Parse an entire btsnoop file, yielding PacketSummary objects.

    Args:
        fileobj: file-like object opened in binary mode
        session: optional SessionState; if None, a new one is created

    Yields:
        PacketSummary objects for each record in the file
    """
    if session is None:
        session = SessionState()

    reader = BtSnoopReader(fileobj)

    for record in reader:
        idx = session.next_index()
        layers = parse_packet(record.data, record.flags, session)

        direction = Direction.RECEIVED if (record.flags & 1) else Direction.SENT
        protocol = get_packet_protocol(layers)
        summary_text = get_packet_summary(layers)

        yield PacketSummary(
            index=idx,
            timestamp_us=record.timestamp_us,
            timestamp_str=record.timestamp_str,
            direction=direction,
            protocol=protocol,
            summary=summary_text,
            layers=layers,
            raw_length=record.original_length,
            included_length=record.included_length,
        )


# Export key names at package level
__all__ = [
    "parse_packet",
    "parse_file",
    "get_packet_protocol",
    "get_packet_summary",
    "SessionState",
    "PacketSummary",
    "DecodedLayer",
    "DecodedField",
    "Direction",
    "HciType",
    "BtSnoopReader",
    "BtSnoopRecord",
    "BtSnoopFileHeader",
    "parse_bytes",
    "parse_file_header",
    "timestamp_to_str",
    "timestamp_to_datetime",
]
