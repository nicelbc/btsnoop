"""
ATT (Attribute Protocol) / GATT decoder for BLE.

ATT PDU format:
  Byte 0: Opcode (method + command flag + auth signature flag)
  Bytes 1+: Parameters (depending on opcode)

The opcode encodes:
  - Bits 5-0: Method
  - Bit 6: Command Flag (1 = no response expected)
  - Bit 7: Authentication Signature Flag
"""

from __future__ import annotations

import struct
from typing import Optional

from .models import DecodedField, DecodedLayer

# ─── ATT Opcodes ───
ATT_OPCODES = {
    0x01: "ERROR_RSP",
    0x02: "EXCHANGE_MTU_REQ",
    0x03: "EXCHANGE_MTU_RSP",
    0x04: "FIND_INFORMATION_REQ",
    0x05: "FIND_INFORMATION_RSP",
    0x06: "FIND_BY_TYPE_VALUE_REQ",
    0x07: "FIND_BY_TYPE_VALUE_RSP",
    0x08: "READ_BY_TYPE_REQ",
    0x09: "READ_BY_TYPE_RSP",
    0x0A: "READ_REQ",
    0x0B: "READ_RSP",
    0x0C: "READ_BLOB_REQ",
    0x0D: "READ_BLOB_RSP",
    0x0E: "READ_MULTIPLE_REQ",
    0x0F: "READ_MULTIPLE_RSP",
    0x10: "READ_BY_GROUP_TYPE_REQ",
    0x11: "READ_BY_GROUP_TYPE_RSP",
    0x12: "WRITE_REQ",
    0x13: "WRITE_RSP",
    0x16: "PREPARE_WRITE_REQ",
    0x17: "PREPARE_WRITE_RSP",
    0x18: "EXECUTE_WRITE_REQ",
    0x19: "EXECUTE_WRITE_RSP",
    0x1B: "HANDLE_VALUE_NTF",
    0x1D: "HANDLE_VALUE_IND",
    0x1E: "HANDLE_VALUE_CFM",
    0x20: "READ_MULTIPLE_VARIABLE_REQ",
    0x21: "READ_MULTIPLE_VARIABLE_RSP",
    0x23: "MULTIPLE_HANDLE_VALUE_NTF",
    0x52: "WRITE_CMD",
    0xD2: "SIGNED_WRITE_CMD",
}

# ─── ATT Error Codes ───
ATT_ERRORS = {
    0x01: "Invalid_Handle",
    0x02: "Read_Not_Permitted",
    0x03: "Write_Not_Permitted",
    0x04: "Invalid_PDU",
    0x05: "Insufficient_Authentication",
    0x06: "Request_Not_Supported",
    0x07: "Invalid_Offset",
    0x08: "Insufficient_Authorization",
    0x09: "Prepare_Queue_Full",
    0x0A: "Attribute_Not_Found",
    0x0B: "Attribute_Not_Long",
    0x0C: "Insufficient_Encryption_Key_Size",
    0x0D: "Invalid_Attribute_Value_Length",
    0x0E: "Unlikely_Error",
    0x0F: "Insufficient_Encryption",
    0x10: "Unsupported_Group_Type",
    0x11: "Insufficient_Resources",
}

# ─── Common GATT UUID16 values ───
GATT_UUIDS = {
    0x1800: "Generic_Access",
    0x1801: "Generic_Attribute",
    0x180A: "Device_Information",
    0x180F: "Battery_Service",
    0x1812: "HID",
    0x2800: "Primary_Service",
    0x2801: "Secondary_Service",
    0x2802: "Include",
    0x2803: "Characteristic",
    0x2900: "Char_Extended_Properties",
    0x2901: "Char_User_Description",
    0x2902: "Client_Char_Config",
    0x2903: "Server_Char_Config",
    0x2904: "Char_Presentation_Format",
    0x2A00: "Device_Name",
    0x2A01: "Appearance",
    0x2A02: "Peripheral_Privacy_Flag",
    0x2A04: "Peripheral_Preferred_Conn_Params",
    0x2A05: "Service_Changed",
    0x2A19: "Battery_Level",
    0x2A29: "Manufacturer_Name",
    0x2A24: "Model_Number",
    0x2A25: "Serial_Number",
    0x2A26: "Firmware_Revision",
    0x2A27: "Hardware_Revision",
    0x2A28: "Software_Revision",
}


def format_uuid(data: bytes) -> str:
    """Format a UUID from raw bytes (2, 4, or 16 bytes)."""
    if len(data) == 2:
        uuid16 = struct.unpack("<H", data)[0]
        name = GATT_UUIDS.get(uuid16, "")
        if name:
            return f"0x{uuid16:04X} ({name})"
        return f"0x{uuid16:04X}"
    elif len(data) == 4:
        uuid32 = struct.unpack("<I", data)[0]
        return f"0x{uuid32:08X}"
    elif len(data) == 16:
        # Full 128-bit UUID in little-endian
        b = data[::-1]  # reverse to big-endian for display
        return (
            f"{b[0:4].hex()}-{b[4:6].hex()}-{b[6:8].hex()}-"
            f"{b[8:10].hex()}-{b[10:16].hex()}"
        )
    return data.hex()


def decode(payload: bytes) -> DecodedLayer:
    """
    Decode ATT (Attribute Protocol) PDU.

    Args:
        payload: L2CAP payload for ATT channel (CID 0x0004)

    Returns:
        DecodedLayer with ATT/GATT decode information
    """
    if len(payload) < 1:
        return DecodedLayer(protocol="ATT", summary="(empty)", payload=b"")

    opcode = payload[0]
    is_command = bool(opcode & 0x40)
    is_signed = bool(opcode & 0x80)
    method = opcode & 0x3F

    opcode_name = ATT_OPCODES.get(opcode, f"0x{opcode:02X}")

    fields = [
        DecodedField("opcode", f"0x{opcode:02X}"),
        DecodedField("method", opcode_name),
    ]

    if is_command:
        fields.append(DecodedField("command_flag", True))
    if is_signed:
        fields.append(DecodedField("auth_signature", True))

    summary = opcode_name
    params = payload[1:]

    # Error Response
    if opcode == 0x01 and len(params) >= 4:
        req_opcode = params[0]
        handle = struct.unpack("<H", params[1:3])[0]
        error_code = params[3]
        error_name = ATT_ERRORS.get(error_code, f"0x{error_code:02X}")
        req_name = ATT_OPCODES.get(req_opcode, f"0x{req_opcode:02X}")
        fields.extend([
            DecodedField("request_opcode", req_name),
            DecodedField("handle", f"0x{handle:04X}"),
            DecodedField("error_code", error_name),
        ])
        summary = f"ERROR_RSP: {req_name} handle=0x{handle:04X} {error_name}"

    # Exchange MTU Request
    elif opcode == 0x02 and len(params) >= 2:
        client_mtu = struct.unpack("<H", params[0:2])[0]
        fields.append(DecodedField("client_rx_mtu", client_mtu))
        summary = f"EXCHANGE_MTU_REQ mtu={client_mtu}"

    # Exchange MTU Response
    elif opcode == 0x03 and len(params) >= 2:
        server_mtu = struct.unpack("<H", params[0:2])[0]
        fields.append(DecodedField("server_rx_mtu", server_mtu))
        summary = f"EXCHANGE_MTU_RSP mtu={server_mtu}"

    # Find Information Request
    elif opcode == 0x04 and len(params) >= 4:
        start_handle = struct.unpack("<H", params[0:2])[0]
        end_handle = struct.unpack("<H", params[2:4])[0]
        fields.extend([
            DecodedField("start_handle", f"0x{start_handle:04X}"),
            DecodedField("end_handle", f"0x{end_handle:04X}"),
        ])
        summary = f"FIND_INFO_REQ handles=0x{start_handle:04X}-0x{end_handle:04X}"

    # Find Information Response
    elif opcode == 0x05 and len(params) >= 2:
        fmt = params[0]
        uuid_len = 2 if fmt == 1 else 16
        fields.append(DecodedField("format", "UUID-16" if fmt == 1 else "UUID-128"))
        info_data = params[1:]
        count = len(info_data) // (2 + uuid_len)
        fields.append(DecodedField("count", count))
        summary = f"FIND_INFO_RSP format={'UUID-16' if fmt == 1 else 'UUID-128'} count={count}"

    # Read By Type Request
    elif opcode == 0x08 and len(params) >= 4:
        start_handle = struct.unpack("<H", params[0:2])[0]
        end_handle = struct.unpack("<H", params[2:4])[0]
        uuid_data = params[4:]
        uuid_str = format_uuid(uuid_data) if uuid_data else "?"
        fields.extend([
            DecodedField("start_handle", f"0x{start_handle:04X}"),
            DecodedField("end_handle", f"0x{end_handle:04X}"),
            DecodedField("uuid", uuid_str),
        ])
        summary = f"READ_BY_TYPE_REQ handles=0x{start_handle:04X}-0x{end_handle:04X} uuid={uuid_str}"

    # Read By Type Response
    elif opcode == 0x09 and len(params) >= 2:
        length = params[0]
        attr_data = params[1:]
        count = len(attr_data) // length if length > 0 else 0
        fields.extend([
            DecodedField("length", length),
            DecodedField("count", count),
        ])
        summary = f"READ_BY_TYPE_RSP len={length} count={count}"

    # Read Request
    elif opcode == 0x0A and len(params) >= 2:
        handle = struct.unpack("<H", params[0:2])[0]
        fields.append(DecodedField("handle", f"0x{handle:04X}"))
        summary = f"READ_REQ handle=0x{handle:04X}"

    # Read Response
    elif opcode == 0x0B:
        fields.append(DecodedField("value_length", len(params)))
        if len(params) <= 8:
            fields.append(DecodedField("value", params.hex()))
        summary = f"READ_RSP len={len(params)}"

    # Read Blob Request
    elif opcode == 0x0C and len(params) >= 4:
        handle = struct.unpack("<H", params[0:2])[0]
        offset = struct.unpack("<H", params[2:4])[0]
        fields.extend([
            DecodedField("handle", f"0x{handle:04X}"),
            DecodedField("offset", offset),
        ])
        summary = f"READ_BLOB_REQ handle=0x{handle:04X} offset={offset}"

    # Read By Group Type Request
    elif opcode == 0x10 and len(params) >= 4:
        start_handle = struct.unpack("<H", params[0:2])[0]
        end_handle = struct.unpack("<H", params[2:4])[0]
        uuid_data = params[4:]
        uuid_str = format_uuid(uuid_data) if uuid_data else "?"
        fields.extend([
            DecodedField("start_handle", f"0x{start_handle:04X}"),
            DecodedField("end_handle", f"0x{end_handle:04X}"),
            DecodedField("uuid", uuid_str),
        ])
        summary = f"READ_BY_GROUP_TYPE_REQ handles=0x{start_handle:04X}-0x{end_handle:04X} uuid={uuid_str}"

    # Read By Group Type Response
    elif opcode == 0x11 and len(params) >= 2:
        length = params[0]
        attr_data = params[1:]
        count = len(attr_data) // length if length > 0 else 0
        fields.extend([
            DecodedField("length", length),
            DecodedField("count", count),
        ])
        summary = f"READ_BY_GROUP_TYPE_RSP len={length} count={count}"

    # Write Request
    elif opcode == 0x12 and len(params) >= 2:
        handle = struct.unpack("<H", params[0:2])[0]
        value = params[2:]
        fields.extend([
            DecodedField("handle", f"0x{handle:04X}"),
            DecodedField("value_length", len(value)),
        ])
        if len(value) <= 8:
            fields.append(DecodedField("value", value.hex()))
        summary = f"WRITE_REQ handle=0x{handle:04X} len={len(value)}"

    # Write Response
    elif opcode == 0x13:
        summary = "WRITE_RSP"

    # Write Command (no response)
    elif opcode == 0x52 and len(params) >= 2:
        handle = struct.unpack("<H", params[0:2])[0]
        value = params[2:]
        fields.extend([
            DecodedField("handle", f"0x{handle:04X}"),
            DecodedField("value_length", len(value)),
        ])
        if len(value) <= 8:
            fields.append(DecodedField("value", value.hex()))
        summary = f"WRITE_CMD handle=0x{handle:04X} len={len(value)}"

    # Handle Value Notification
    elif opcode == 0x1B and len(params) >= 2:
        handle = struct.unpack("<H", params[0:2])[0]
        value = params[2:]
        fields.extend([
            DecodedField("handle", f"0x{handle:04X}"),
            DecodedField("value_length", len(value)),
        ])
        if len(value) <= 8:
            fields.append(DecodedField("value", value.hex()))
        summary = f"HANDLE_VALUE_NTF handle=0x{handle:04X} len={len(value)}"

    # Handle Value Indication
    elif opcode == 0x1D and len(params) >= 2:
        handle = struct.unpack("<H", params[0:2])[0]
        value = params[2:]
        fields.extend([
            DecodedField("handle", f"0x{handle:04X}"),
            DecodedField("value_length", len(value)),
        ])
        summary = f"HANDLE_VALUE_IND handle=0x{handle:04X} len={len(value)}"

    # Handle Value Confirmation
    elif opcode == 0x1E:
        summary = "HANDLE_VALUE_CFM"

    # Prepare Write Request
    elif opcode == 0x16 and len(params) >= 4:
        handle = struct.unpack("<H", params[0:2])[0]
        offset = struct.unpack("<H", params[2:4])[0]
        value = params[4:]
        fields.extend([
            DecodedField("handle", f"0x{handle:04X}"),
            DecodedField("offset", offset),
            DecodedField("value_length", len(value)),
        ])
        summary = f"PREPARE_WRITE_REQ handle=0x{handle:04X} offset={offset}"

    # Execute Write Request
    elif opcode == 0x18 and len(params) >= 1:
        exec_flags = params[0]
        fields.append(DecodedField("flags", "Write" if exec_flags else "Cancel"))
        summary = f"EXECUTE_WRITE_REQ {'Write' if exec_flags else 'Cancel'}"

    return DecodedLayer(
        protocol="ATT",
        summary=summary,
        fields=fields,
        payload=params,
    )
