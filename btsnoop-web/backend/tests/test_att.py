"""
Tests for ATT (Attribute Protocol) decoding (parser/att.py).

Tests:
  - Exchange MTU Request/Response
  - Read By Group Type (GATT service discovery)
  - Write Request
  - Error Response
"""

from __future__ import annotations

import struct

import pytest

from parser.att import decode, format_uuid, ATT_OPCODES, ATT_ERRORS, GATT_UUIDS
from parser.models import DecodedLayer

from .conftest import (
    build_att_exchange_mtu_req,
    build_att_exchange_mtu_rsp,
    build_att_read_by_group_type_req,
    build_att_write_req,
    build_att_error_rsp,
)


class TestExchangeMtu:
    """Tests for Exchange MTU Request/Response."""

    def test_exchange_mtu_request(self):
        """Decode Exchange MTU Request with mtu=517."""
        payload = build_att_exchange_mtu_req(517)
        layer = decode(payload)
        assert layer.protocol == "ATT"
        assert "EXCHANGE_MTU_REQ" in layer.summary
        assert "517" in layer.summary

        mtu_field = next(f for f in layer.fields if f.name == "client_rx_mtu")
        assert mtu_field.value == 517

    def test_exchange_mtu_response(self):
        """Decode Exchange MTU Response with mtu=247."""
        payload = build_att_exchange_mtu_rsp(247)
        layer = decode(payload)
        assert layer.protocol == "ATT"
        assert "EXCHANGE_MTU_RSP" in layer.summary
        assert "247" in layer.summary

        mtu_field = next(f for f in layer.fields if f.name == "server_rx_mtu")
        assert mtu_field.value == 247

    def test_exchange_mtu_request_default(self):
        """Decode Exchange MTU Request with default BLE MTU=23."""
        payload = build_att_exchange_mtu_req(23)
        layer = decode(payload)
        assert "23" in layer.summary


class TestReadByGroupType:
    """Tests for Read By Group Type (GATT service discovery)."""

    def test_read_by_group_type_primary_service(self):
        """Decode Read By Group Type Request for Primary Service UUID (0x2800)."""
        payload = build_att_read_by_group_type_req(0x0001, 0xFFFF, 0x2800)
        layer = decode(payload)
        assert layer.protocol == "ATT"
        assert "READ_BY_GROUP_TYPE_REQ" in layer.summary
        assert "0x0001" in layer.summary
        assert "0xFFFF" in layer.summary or "0xffff" in layer.summary.lower()
        assert "2800" in layer.summary.lower()

        # Check UUID field contains Primary_Service label
        uuid_field = next(f for f in layer.fields if f.name == "uuid")
        assert "Primary_Service" in uuid_field.value or "2800" in uuid_field.value.upper()

    def test_read_by_group_type_response(self):
        """Decode Read By Group Type Response."""
        # opcode=0x11, length=6, attr_data (6 bytes per entry: start_handle, end_handle, uuid16)
        length = 6
        entry = struct.pack("<HHH", 0x0001, 0x0005, 0x1800)  # Generic Access
        payload = bytes([0x11, length]) + entry
        layer = decode(payload)
        assert "READ_BY_GROUP_TYPE_RSP" in layer.summary
        assert "len=6" in layer.summary
        assert "count=1" in layer.summary

    def test_read_by_group_type_multiple_entries(self):
        """Decode Read By Group Type Response with multiple entries."""
        length = 6
        entries = struct.pack("<HHH", 0x0001, 0x0005, 0x1800)
        entries += struct.pack("<HHH", 0x0006, 0x0009, 0x1801)
        payload = bytes([0x11, length]) + entries
        layer = decode(payload)
        assert "count=2" in layer.summary


class TestWriteRequest:
    """Tests for Write Request decoding."""

    def test_write_request_basic(self):
        """Decode Write Request to handle 0x0010 with value."""
        value = bytes([0x01, 0x00])  # Enable notifications
        payload = build_att_write_req(0x0010, value)
        layer = decode(payload)
        assert layer.protocol == "ATT"
        assert "WRITE_REQ" in layer.summary
        assert "0x0010" in layer.summary
        assert "len=2" in layer.summary

        handle_field = next(f for f in layer.fields if f.name == "handle")
        assert handle_field.value == "0x0010"

    def test_write_request_long_value(self):
        """Decode Write Request with longer value."""
        value = bytes(range(20))
        payload = build_att_write_req(0x0025, value)
        layer = decode(payload)
        assert "WRITE_REQ" in layer.summary
        assert "len=20" in layer.summary

    def test_write_response(self):
        """Decode Write Response (opcode 0x13, no params)."""
        payload = bytes([0x13])
        layer = decode(payload)
        assert "WRITE_RSP" in layer.summary

    def test_write_command(self):
        """Decode Write Command (opcode 0x52, no response expected)."""
        value = bytes([0x01, 0x00])
        payload = struct.pack("<BH", 0x52, 0x0010) + value
        layer = decode(payload)
        assert "WRITE_CMD" in layer.summary
        assert "0x0010" in layer.summary

        # Check command flag
        cmd_field = next((f for f in layer.fields if f.name == "command_flag"), None)
        assert cmd_field is not None
        assert cmd_field.value is True


class TestErrorResponse:
    """Tests for ATT Error Response."""

    def test_error_response_attribute_not_found(self):
        """Decode Error Response: Attribute Not Found."""
        payload = build_att_error_rsp(0x10, 0x0001, 0x0A)  # READ_BY_GROUP_TYPE_REQ, handle, Attribute_Not_Found
        layer = decode(payload)
        assert layer.protocol == "ATT"
        assert "ERROR_RSP" in layer.summary
        assert "Attribute_Not_Found" in layer.summary
        assert "0x0001" in layer.summary

    def test_error_response_invalid_handle(self):
        """Decode Error Response: Invalid Handle."""
        payload = build_att_error_rsp(0x0A, 0x0000, 0x01)  # READ_REQ, handle=0, Invalid_Handle
        layer = decode(payload)
        assert "Invalid_Handle" in layer.summary

    def test_error_response_read_not_permitted(self):
        """Decode Error Response: Read Not Permitted."""
        payload = build_att_error_rsp(0x0A, 0x0003, 0x02)
        layer = decode(payload)
        assert "Read_Not_Permitted" in layer.summary

    def test_error_response_request_not_supported(self):
        """Decode Error Response: Request Not Supported."""
        payload = build_att_error_rsp(0x02, 0x0000, 0x06)
        layer = decode(payload)
        assert "Request_Not_Supported" in layer.summary

    def test_error_response_shows_request_opcode(self):
        """Error response shows the failing request opcode name."""
        # Error on WRITE_REQ (0x12)
        payload = build_att_error_rsp(0x12, 0x0010, 0x03)
        layer = decode(payload)
        assert "WRITE_REQ" in layer.summary
        assert "Write_Not_Permitted" in layer.summary


class TestAttMisc:
    """Miscellaneous ATT decode tests."""

    def test_empty_payload(self):
        """Handle empty ATT payload."""
        layer = decode(b"")
        assert layer.protocol == "ATT"
        assert "empty" in layer.summary

    def test_handle_value_notification(self):
        """Decode Handle Value Notification (opcode 0x1B)."""
        value = bytes([0x64, 0x00])  # Battery level = 100
        payload = struct.pack("<BH", 0x1B, 0x0015) + value
        layer = decode(payload)
        assert "HANDLE_VALUE_NTF" in layer.summary
        assert "0x0015" in layer.summary

    def test_handle_value_indication(self):
        """Decode Handle Value Indication (opcode 0x1D)."""
        value = bytes([0x01, 0x02, 0x03])
        payload = struct.pack("<BH", 0x1D, 0x0020) + value
        layer = decode(payload)
        assert "HANDLE_VALUE_IND" in layer.summary

    def test_handle_value_confirmation(self):
        """Decode Handle Value Confirmation (opcode 0x1E)."""
        payload = bytes([0x1E])
        layer = decode(payload)
        assert "HANDLE_VALUE_CFM" in layer.summary

    def test_read_request(self):
        """Decode Read Request (opcode 0x0A)."""
        payload = struct.pack("<BH", 0x0A, 0x0003)
        layer = decode(payload)
        assert "READ_REQ" in layer.summary
        assert "0x0003" in layer.summary

    def test_read_response(self):
        """Decode Read Response (opcode 0x0B)."""
        value = bytes([0x42, 0x6C, 0x75, 0x65])  # "Blue"
        payload = bytes([0x0B]) + value
        layer = decode(payload)
        assert "READ_RSP" in layer.summary
        assert "len=4" in layer.summary

    def test_find_information_request(self):
        """Decode Find Information Request (opcode 0x04)."""
        payload = struct.pack("<BHH", 0x04, 0x0001, 0x0005)
        layer = decode(payload)
        assert "FIND_INFO_REQ" in layer.summary
        assert "0x0001" in layer.summary
        assert "0x0005" in layer.summary

    def test_unknown_opcode(self):
        """Handle unknown ATT opcode."""
        payload = bytes([0xFE, 0x01, 0x02, 0x03])
        layer = decode(payload)
        assert layer.protocol == "ATT"
        assert "0xfe" in layer.summary.lower()


class TestFormatUuid:
    """Tests for UUID formatting."""

    def test_uuid16_known(self):
        """Format known UUID16."""
        data = struct.pack("<H", 0x2800)
        result = format_uuid(data)
        assert "2800" in result.lower()
        assert "Primary_Service" in result

    def test_uuid16_unknown(self):
        """Format unknown UUID16."""
        data = struct.pack("<H", 0xABCD)
        result = format_uuid(data)
        assert "abcd" in result.lower()

    def test_uuid128(self):
        """Format 128-bit UUID."""
        # A standard 128-bit UUID in little-endian
        data = bytes(range(16))
        result = format_uuid(data)
        assert "-" in result  # Standard UUID format has dashes
        assert len(result) == 36  # 8-4-4-4-12 format

    def test_uuid_empty(self):
        """Format empty UUID data."""
        result = format_uuid(b"")
        assert result == ""
