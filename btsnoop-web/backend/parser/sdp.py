"""
SDP (Service Discovery Protocol) decoder.

SDP runs over L2CAP PSM 0x0001. Decodes PDU types and service attributes.
"""

from __future__ import annotations

import struct
from typing import Optional

from .models import DecodedField, DecodedLayer


# SDP PDU IDs
SDP_PDUS = {
    0x01: "ErrorResponse",
    0x02: "ServiceSearchRequest",
    0x03: "ServiceSearchResponse",
    0x04: "ServiceAttributeRequest",
    0x05: "ServiceAttributeResponse",
    0x06: "ServiceSearchAttributeRequest",
    0x07: "ServiceSearchAttributeResponse",
}

# Common Bluetooth UUID16 service classes
SERVICE_CLASSES = {
    0x1101: "SerialPort",
    0x1102: "LANAccessUsingPPP",
    0x1103: "DialupNetworking",
    0x1104: "IrMCSync",
    0x1105: "OBEXObjectPush",
    0x1106: "OBEXFileTransfer",
    0x1108: "HSP_HS",
    0x110A: "AudioSource",
    0x110B: "AudioSink",
    0x110C: "A/V_RemoteControlTarget",
    0x110D: "AdvancedAudioDistribution",
    0x110E: "A/V_RemoteControl",
    0x110F: "A/V_RemoteControlController",
    0x1112: "HSP_AG",
    0x111E: "Handsfree",
    0x111F: "HandsfreeAudioGateway",
    0x1124: "HumanInterfaceDevice",
    0x112D: "SIM_Access",
    0x112F: "PhonebookAccessPCE",
    0x1130: "PhonebookAccessPSE",
    0x1132: "MessageAccessServer",
    0x1133: "MessageNotificationServer",
    0x1134: "MessageAccessProfile",
    0x1200: "PnPInformation",
}

# Common attribute IDs
ATTRIBUTE_IDS = {
    0x0000: "ServiceRecordHandle",
    0x0001: "ServiceClassIDList",
    0x0004: "ProtocolDescriptorList",
    0x0005: "BrowseGroupList",
    0x0006: "LanguageBaseAttributeIDList",
    0x0009: "BluetoothProfileDescriptorList",
    0x0100: "ServiceName",
    0x0200: "GroupID",
    0x0311: "SupportedFeatures",
}


def decode(data: bytes) -> DecodedLayer:
    """
    Decode an SDP PDU.

    Args:
        data: SDP PDU bytes from L2CAP payload on PSM 0x0001

    Returns:
        DecodedLayer with SDP decode info
    """
    fields = []

    if len(data) < 5:
        return DecodedLayer(
            protocol="SDP",
            summary="(truncated)",
            fields=[DecodedField(name="error", value="PDU too short")],
        )

    pdu_id = data[0]
    txn_id = struct.unpack(">H", data[1:3])[0]
    param_len = struct.unpack(">H", data[3:5])[0]

    pdu_name = SDP_PDUS.get(pdu_id, f"Unknown_0x{pdu_id:02X}")

    fields.append(DecodedField(name="pdu_id", value=f"0x{pdu_id:02X}", offset=0, length=1))
    fields.append(DecodedField(name="pdu_name", value=pdu_name, offset=0, length=1))
    fields.append(DecodedField(name="transaction_id", value=txn_id, offset=1, length=2))
    fields.append(DecodedField(name="param_length", value=param_len, offset=3, length=2))

    params = data[5:5 + param_len]

    # Decode based on PDU type
    extra_info = ""
    if pdu_id == 0x01:  # ErrorResponse
        if len(params) >= 2:
            err_code = struct.unpack(">H", params[0:2])[0]
            err_names = {
                0x0001: "Invalid SDP Version",
                0x0002: "Invalid Service Record Handle",
                0x0003: "Invalid Request Syntax",
                0x0004: "Invalid PDU Size",
                0x0005: "Invalid Continuation State",
            }
            err_name = err_names.get(err_code, f"0x{err_code:04X}")
            fields.append(DecodedField(name="error_code", value=err_name))
            extra_info = f" error={err_name}"

    elif pdu_id == 0x02:  # ServiceSearchRequest
        uuids = _extract_uuids(params)
        if uuids:
            extra_info = f" uuid={','.join(uuids)}"
            fields.append(DecodedField(name="uuids", value=",".join(uuids)))

    elif pdu_id == 0x03:  # ServiceSearchResponse
        if len(params) >= 4:
            total = struct.unpack(">H", params[0:2])[0]
            current = struct.unpack(">H", params[2:4])[0]
            fields.append(DecodedField(name="total_records", value=total))
            fields.append(DecodedField(name="current_records", value=current))
            extra_info = f" records={current}/{total}"

    elif pdu_id in (0x04, 0x06):  # ServiceAttributeRequest / ServiceSearchAttributeRequest
        if pdu_id == 0x04 and len(params) >= 4:
            handle = struct.unpack(">I", params[0:4])[0]
            fields.append(DecodedField(name="service_handle", value=f"0x{handle:08X}"))
            extra_info = f" handle=0x{handle:08X}"
        elif pdu_id == 0x06:
            uuids = _extract_uuids(params)
            if uuids:
                extra_info = f" uuid={','.join(uuids)}"

    elif pdu_id in (0x05, 0x07):  # ServiceAttributeResponse / ServiceSearchAttributeResponse
        if len(params) >= 2:
            attr_list_len = struct.unpack(">H", params[0:2])[0]
            fields.append(DecodedField(name="attr_list_byte_count", value=attr_list_len))
            extra_info = f" attrlen={attr_list_len}"

    summary = f"{pdu_name} txn={txn_id}{extra_info}"

    return DecodedLayer(
        protocol="SDP",
        summary=summary,
        fields=fields,
        payload_offset=5,
        payload=params,
    )


def _extract_uuids(data: bytes) -> list[str]:
    """Extract UUID values from a Data Element Sequence (best effort)."""
    uuids = []
    i = 0
    while i < len(data):
        if i + 1 >= len(data):
            break
        desc = data[i]
        dtype = (desc >> 3) & 0x1F
        size_idx = desc & 0x07

        i += 1

        if dtype == 3:  # UUID type
            if size_idx == 1 and i + 2 <= len(data):  # 2 bytes
                uuid16 = struct.unpack(">H", data[i:i + 2])[0]
                name = SERVICE_CLASSES.get(uuid16, f"0x{uuid16:04X}")
                uuids.append(name)
                i += 2
            elif size_idx == 2 and i + 4 <= len(data):  # 4 bytes
                uuid32 = struct.unpack(">I", data[i:i + 4])[0]
                uuids.append(f"0x{uuid32:08X}")
                i += 4
            elif size_idx == 4 and i + 16 <= len(data):  # 16 bytes
                uuid128 = data[i:i + 16].hex()
                uuids.append(uuid128)
                i += 16
            else:
                break
        elif dtype == 6 or dtype == 7:  # Data Element Sequence/Alternative
            if size_idx == 5 and i + 1 <= len(data):  # 1-byte length
                seq_len = data[i]
                i += 1
                # Recurse into sequence
                sub_uuids = _extract_uuids(data[i:i + seq_len])
                uuids.extend(sub_uuids)
                i += seq_len
            elif size_idx == 6 and i + 2 <= len(data):  # 2-byte length
                seq_len = struct.unpack(">H", data[i:i + 2])[0]
                i += 2
                sub_uuids = _extract_uuids(data[i:i + seq_len])
                uuids.extend(sub_uuids)
                i += seq_len
            else:
                break
        else:
            # Skip other types
            if size_idx == 0:
                i += 1
            elif size_idx == 1:
                i += 2
            elif size_idx == 2:
                i += 4
            elif size_idx == 3:
                i += 8
            elif size_idx == 4:
                i += 16
            elif size_idx == 5 and i < len(data):
                i += 1 + data[i]
            elif size_idx == 6 and i + 1 < len(data):
                skip = struct.unpack(">H", data[i:i + 2])[0]
                i += 2 + skip
            else:
                break

    return uuids
