"""
Tests for HCI layer decoding (parser/hci.py).

Tests:
  - HCI Command: Reset (0x0C03), Create_Connection (0x0405)
  - HCI Event: Command Complete (0x0E), Disconnection Complete (0x05)
  - ACL data packet decode
  - Unknown opcode/type handling
"""

from __future__ import annotations

import struct

import pytest

from parser.hci import (
    decode_hci_command,
    decode_hci_event,
    decode_hci_acl,
    decode_hci_sco,
    decode_hci_iso,
    decode,
    get_opcode_name,
    get_event_name,
)
from parser.models import DecodedLayer, HciType

from .conftest import build_hci_command, build_hci_event, build_hci_acl


class TestHciCommand:
    """Tests for HCI Command decoding."""

    def test_reset_command(self, hci_reset_cmd):
        """Decode HCI Reset command (0x0C03)."""
        layer = decode_hci_command(hci_reset_cmd)
        assert layer.protocol == "HCI_CMD"
        assert "Reset" in layer.summary
        assert "0x0C03" in layer.summary or "0x0c03" in layer.summary

        # Check fields
        field_names = [f.name for f in layer.fields]
        assert "opcode" in field_names
        assert "name" in field_names

        name_field = next(f for f in layer.fields if f.name == "name")
        assert name_field.value == "Reset"

    def test_create_connection_command(self, hci_create_connection_cmd):
        """Decode HCI Create_Connection command (0x0405) with BD_ADDR."""
        layer = decode_hci_command(hci_create_connection_cmd)
        assert layer.protocol == "HCI_CMD"
        assert "Create_Connection" in layer.summary

        # Should have bd_addr field
        field_names = [f.name for f in layer.fields]
        assert "bd_addr" in field_names
        addr_field = next(f for f in layer.fields if f.name == "bd_addr")
        # BD_ADDR stored as [0xFF, 0xEE, 0xDD, 0xCC, 0xBB, 0xAA] reversed to aa:bb:cc:dd:ee:ff
        assert addr_field.value == "aa:bb:cc:dd:ee:ff"

    def test_disconnect_command(self):
        """Decode HCI Disconnect command (0x0406)."""
        # params: handle(2 LE) + reason(1)
        params = struct.pack("<HB", 0x0040, 0x13)
        pkt = build_hci_command(0x0406, params)
        layer = decode_hci_command(pkt)
        assert "Disconnect" in layer.summary

        field_names = [f.name for f in layer.fields]
        assert "handle" in field_names
        assert "reason" in field_names

    def test_unknown_opcode(self):
        """Decode command with unrecognized opcode."""
        pkt = build_hci_command(0xFFFF, b"\x01\x02\x03")
        layer = decode_hci_command(pkt)
        assert layer.protocol == "HCI_CMD"
        # Should show hex opcode in summary
        assert "0xFFFF" in layer.summary or "0xffff" in layer.summary

    def test_truncated_command(self):
        """Handle truncated command gracefully."""
        # Only 2 bytes (need at least 4)
        layer = decode_hci_command(b"\x01\x03")
        assert layer.protocol == "HCI_CMD"
        assert "truncated" in layer.summary

    def test_ogf_ocf_extraction(self):
        """Verify OGF and OCF fields are correctly extracted."""
        # opcode 0x0C03: OGF=0x03, OCF=0x0003
        pkt = build_hci_command(0x0C03)
        layer = decode_hci_command(pkt)

        ogf_field = next(f for f in layer.fields if f.name == "ogf")
        ocf_field = next(f for f in layer.fields if f.name == "ocf")
        assert ogf_field.value == 3
        assert ocf_field.value == 3

    def test_le_command(self):
        """Decode LE Set Event Mask command (OGF=0x08)."""
        # LE_Set_Event_Mask: opcode 0x2001
        pkt = build_hci_command(0x2001, b"\x1f\x00\x00\x00\x00\x00\x00\x00")
        layer = decode_hci_command(pkt)
        assert "LE_Set_Event_Mask" in layer.summary


class TestHciEvent:
    """Tests for HCI Event decoding."""

    def test_command_complete_event(self, hci_cmd_complete_event):
        """Decode HCI Command Complete event (0x0E) for Reset."""
        layer = decode_hci_event(hci_cmd_complete_event)
        assert layer.protocol == "HCI_EVT"
        assert "Cmd_Complete" in layer.summary
        assert "Reset" in layer.summary

        # Check status field
        field_names = [f.name for f in layer.fields]
        assert "command_name" in field_names
        cmd_name = next(f for f in layer.fields if f.name == "command_name")
        assert cmd_name.value == "Reset"

    def test_disconnection_complete_event(self, hci_disconn_complete_event):
        """Decode HCI Disconnection Complete event (0x05)."""
        layer = decode_hci_event(hci_disconn_complete_event)
        assert layer.protocol == "HCI_EVT"
        assert "Disconn_Complete" in layer.summary
        assert "0x0040" in layer.summary
        assert "0x13" in layer.summary.lower()

        # Check fields
        field_names = [f.name for f in layer.fields]
        assert "handle" in field_names
        assert "reason" in field_names
        handle_field = next(f for f in layer.fields if f.name == "handle")
        assert handle_field.value == "0x0040"

    def test_command_status_event(self):
        """Decode Command Status event (0x0F)."""
        # params: status(1) + num_pkts(1) + opcode(2 LE)
        params = struct.pack("<BBH", 0x00, 0x01, 0x0405)
        pkt = build_hci_event(0x0F, params)
        layer = decode_hci_event(pkt)
        assert "Cmd_Status" in layer.summary
        assert "Create_Connection" in layer.summary

    def test_connection_complete_event(self):
        """Decode Connection Complete event (0x03)."""
        # params: status(1) + handle(2 LE) + bd_addr(6) + link_type(1) + encryption(1)
        params = struct.pack("<BH", 0x00, 0x0040)
        params += bytes([0xFF, 0xEE, 0xDD, 0xCC, 0xBB, 0xAA])  # BD_ADDR LE
        params += struct.pack("BB", 0x01, 0x00)  # link_type, encryption
        pkt = build_hci_event(0x03, params)
        layer = decode_hci_event(pkt)
        assert "Conn_Complete" in layer.summary
        assert "0x0040" in layer.summary

    def test_le_meta_event(self):
        """Decode LE Meta Event (0x3E)."""
        # Subevent 0x01 (LE Connection Complete) with enough data
        params = bytes([0x01])  # subevent
        params += struct.pack("<BH", 0x00, 0x0040)  # status, handle
        params += bytes([0x00])  # role
        params += bytes([0x01])  # addr_type
        params += bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF])  # addr
        params += struct.pack("<HHH", 0x0018, 0x0000, 0x01F4)  # interval, latency, timeout
        params += bytes([0x00])  # master_clock_accuracy
        pkt = build_hci_event(0x3E, params)
        layer = decode_hci_event(pkt)
        assert "LE_Meta" in layer.summary
        assert "LE_Conn_Complete" in layer.summary

    def test_num_completed_packets_event(self):
        """Decode Num Completed Packets event (0x13)."""
        # params: num_handles(1) + handle(2) + num_completed(2)
        params = struct.pack("<BHH", 1, 0x0040, 5)
        pkt = build_hci_event(0x13, params)
        layer = decode_hci_event(pkt)
        assert "Num_Completed_Pkts" in layer.summary

    def test_truncated_event(self):
        """Handle truncated event gracefully."""
        layer = decode_hci_event(b"\x04\x0E")
        assert "truncated" in layer.summary

    def test_unknown_event_code(self):
        """Handle unknown event code."""
        params = b"\x00\x01\x02\x03"
        pkt = build_hci_event(0xFE, params)
        layer = decode_hci_event(pkt)
        assert layer.protocol == "HCI_EVT"
        # Should contain event code in summary (case-insensitive check)
        assert "0xFE" in layer.summary or "0xfe" in layer.summary.lower()


class TestHciAcl:
    """Tests for HCI ACL data decoding."""

    def test_acl_basic(self):
        """Decode basic ACL packet."""
        payload = b"\x04\x00\x04\x00\x02\x00\x01\x00"  # L2CAP header
        pkt = build_hci_acl(0x0040, pb_flag=2, bc_flag=0, payload=payload)
        layer, handle, acl_payload = decode_hci_acl(pkt)
        assert layer.protocol == "ACL"
        assert handle == 0x0040
        assert acl_payload == payload
        assert "0x0040" in layer.summary

    def test_acl_handle_extraction(self):
        """Verify ACL handle bits are correctly extracted."""
        payload = b"\x00" * 8
        pkt = build_hci_acl(0x0ABC, pb_flag=1, bc_flag=0, payload=payload)
        layer, handle, _ = decode_hci_acl(pkt)
        assert handle == 0x0ABC

    def test_acl_pb_flag(self):
        """Verify PB flag extraction."""
        payload = b"\x00" * 4
        pkt = build_hci_acl(0x0001, pb_flag=2, bc_flag=0, payload=payload)
        layer, _, _ = decode_hci_acl(pkt)
        pb_field = next(f for f in layer.fields if f.name == "pb_flag")
        assert "First_Auto_Flush" in pb_field.value

    def test_acl_truncated(self):
        """Handle truncated ACL packet."""
        layer, handle, payload = decode_hci_acl(b"\x02\x40")
        assert "truncated" in layer.summary
        assert handle == 0
        assert payload == b""


class TestHciScoIso:
    """Tests for SCO and ISO packet decoding."""

    def test_sco_decode(self):
        """Decode SCO packet."""
        # [0x03][handle_flags_le16][data_len_u8][data]
        sco_data = b"\x01\x02\x03\x04\x05"
        pkt = struct.pack("<BHB", 0x03, 0x0040, len(sco_data)) + sco_data
        layer = decode_hci_sco(pkt)
        assert layer.protocol == "SCO"
        assert "0x0040" in layer.summary

    def test_iso_decode(self):
        """Decode ISO packet."""
        # [0x05][handle_flags_le16][data_load_len_le16][data]
        iso_data = b"\x01\x02\x03\x04"
        pkt = struct.pack("<BHH", 0x05, 0x0040, len(iso_data)) + iso_data
        layer = decode_hci_iso(pkt)
        assert layer.protocol == "ISO"
        assert "0x0040" in layer.summary


class TestHciTopLevelDecode:
    """Tests for the top-level decode() dispatch function."""

    def test_dispatch_command(self):
        """Top-level decode dispatches to command decoder."""
        pkt = build_hci_command(0x0C03)
        layer = decode(pkt)
        assert layer is not None
        assert layer.protocol == "HCI_CMD"

    def test_dispatch_event(self):
        """Top-level decode dispatches to event decoder."""
        pkt = build_hci_event(0x0E, struct.pack("<BHB", 1, 0x0C03, 0))
        layer = decode(pkt)
        assert layer is not None
        assert layer.protocol == "HCI_EVT"

    def test_dispatch_acl(self):
        """Top-level decode dispatches to ACL decoder."""
        pkt = build_hci_acl(0x0040, 2, 0, b"\x00" * 8)
        layer = decode(pkt)
        assert layer is not None
        assert layer.protocol == "ACL"

    def test_dispatch_unknown_type(self):
        """Top-level decode handles unknown packet type."""
        pkt = b"\xFF\x00\x01\x02"
        layer = decode(pkt)
        assert layer is not None
        assert layer.protocol == "UNKNOWN"

    def test_dispatch_empty(self):
        """Top-level decode returns None for empty data."""
        layer = decode(b"")
        assert layer is None


class TestOpcodeEventNameLookup:
    """Tests for name lookup helpers."""

    def test_known_opcode(self):
        assert get_opcode_name(0x0C03) == "Reset"
        assert get_opcode_name(0x0405) == "Create_Connection"

    def test_unknown_opcode(self):
        result = get_opcode_name(0x1234)
        assert "0x1234" in result.lower()

    def test_known_event(self):
        assert get_event_name(0x0E) == "Cmd_Complete"
        assert get_event_name(0x05) == "Disconn_Complete"

    def test_unknown_event(self):
        result = get_event_name(0xAB)
        assert "0xab" in result.lower() or "0xAB" in result
