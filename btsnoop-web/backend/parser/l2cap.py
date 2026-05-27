"""
L2CAP (Logical Link Control and Adaptation Protocol) decoder.

L2CAP basic header (4 bytes):
  - length (2 bytes LE): payload length
  - CID (2 bytes LE): channel identifier

Fixed CIDs:
  0x0001 - L2CAP Signaling (BR/EDR)
  0x0002 - Connectionless Reception
  0x0003 - AMP Manager
  0x0004 - ATT (Attribute Protocol)
  0x0005 - LE L2CAP Signaling
  0x0006 - SMP (Security Manager Protocol)

Dynamic CIDs (0x0040+) are mapped to PSMs via L2CAP signaling.
"""

from __future__ import annotations

import struct
from typing import Optional

from .models import DecodedField, DecodedLayer, SessionState

# ─── Fixed L2CAP CID names ───
L2CAP_CIDS = {
    0x0001: "L2CAP_SIG",
    0x0002: "Connectionless",
    0x0003: "AMP_Manager",
    0x0004: "ATT",
    0x0005: "LE_L2CAP_SIG",
    0x0006: "SMP",
}

# ─── L2CAP PSM values ───
L2CAP_PSMS = {
    0x0001: "SDP",
    0x0003: "RFCOMM",
    0x000F: "BNEP",
    0x0011: "HID_Control",
    0x0013: "HID_Interrupt",
    0x0017: "AVCTP",
    0x0019: "AVDTP",
    0x001B: "AVCTP_Browsing",
    0x001F: "ATT",  # dynamic ATT over BR/EDR
    0x0025: "EATT",
}

# ─── L2CAP Signaling Command Codes ───
L2CAP_SIG_CODES = {
    0x01: "CMD_REJECT",
    0x02: "CONN_REQ",
    0x03: "CONN_RSP",
    0x04: "CONFIG_REQ",
    0x05: "CONFIG_RSP",
    0x06: "DISCONN_REQ",
    0x07: "DISCONN_RSP",
    0x08: "ECHO_REQ",
    0x09: "ECHO_RSP",
    0x0A: "INFO_REQ",
    0x0B: "INFO_RSP",
    0x0C: "CREATE_CHANNEL_REQ",
    0x0D: "CREATE_CHANNEL_RSP",
    0x0E: "MOVE_CHANNEL_REQ",
    0x0F: "MOVE_CHANNEL_RSP",
    0x10: "MOVE_CHANNEL_CONFIRM",
    0x11: "MOVE_CHANNEL_CONFIRM_RSP",
    0x12: "CONN_PARAM_UPDATE_REQ",
    0x13: "CONN_PARAM_UPDATE_RSP",
    0x14: "LE_CREDIT_BASED_CONN_REQ",
    0x15: "LE_CREDIT_BASED_CONN_RSP",
    0x16: "FLOW_CONTROL_CREDIT",
    0x17: "CREDIT_BASED_CONN_REQ",
    0x18: "CREDIT_BASED_CONN_RSP",
    0x19: "CREDIT_BASED_RECONFIG_REQ",
    0x1A: "CREDIT_BASED_RECONFIG_RSP",
}

# Connection Response result codes
CONN_RSP_RESULTS = {
    0: "Success",
    1: "Pending",
    2: "PSM_Not_Supported",
    3: "Security_Block",
    4: "No_Resources",
    6: "Invalid_Source_CID",
    7: "Source_CID_Already_Allocated",
}


def get_psm_name(psm: int) -> str:
    """Get a human-readable name for a PSM value."""
    return L2CAP_PSMS.get(psm, f"0x{psm:04X}")


def get_cid_name(cid: int) -> str:
    """Get a human-readable name for a fixed CID."""
    return L2CAP_CIDS.get(cid, f"CID=0x{cid:04X}")


def decode_signaling(payload: bytes, session: SessionState) -> DecodedLayer:
    """
    Decode L2CAP Signaling channel data.
    Signaling PDU: code(1) + identifier(1) + length(2 LE) + data...
    """
    if len(payload) < 4:
        return DecodedLayer(protocol="L2CAP_SIG", summary="(truncated)", payload=b"")

    code = payload[0]
    identifier = payload[1]
    sig_len = struct.unpack("<H", payload[2:4])[0]
    sig_data = payload[4 : 4 + sig_len] if len(payload) >= 4 + sig_len else payload[4:]
    code_name = L2CAP_SIG_CODES.get(code, f"code=0x{code:02X}")

    fields = [
        DecodedField("code", f"0x{code:02X}"),
        DecodedField("code_name", code_name),
        DecodedField("identifier", identifier),
        DecodedField("length", sig_len),
    ]

    summary = f"{code_name} id={identifier}"

    # Connection Request (0x02)
    if code == 0x02 and len(sig_data) >= 4:
        psm = struct.unpack("<H", sig_data[0:2])[0]
        scid = struct.unpack("<H", sig_data[2:4])[0]
        psm_name = get_psm_name(psm)
        fields.append(DecodedField("psm", f"0x{psm:04X}"))
        fields.append(DecodedField("psm_name", psm_name))
        fields.append(DecodedField("source_cid", f"0x{scid:04X}"))
        summary = f"CONN_REQ PSM={psm_name} SCID=0x{scid:04X}"
        # Track CID mapping
        session.map_cid_to_psm(scid, psm)

    # Connection Response (0x03)
    elif code == 0x03 and len(sig_data) >= 8:
        dcid = struct.unpack("<H", sig_data[0:2])[0]
        scid = struct.unpack("<H", sig_data[2:4])[0]
        result = struct.unpack("<H", sig_data[4:6])[0]
        status = struct.unpack("<H", sig_data[6:8])[0]
        result_name = CONN_RSP_RESULTS.get(result, str(result))
        fields.append(DecodedField("dest_cid", f"0x{dcid:04X}"))
        fields.append(DecodedField("source_cid", f"0x{scid:04X}"))
        fields.append(DecodedField("result", result_name))
        fields.append(DecodedField("status", status))
        summary = f"CONN_RSP DCID=0x{dcid:04X} SCID=0x{scid:04X} {result_name}"
        # Propagate PSM mapping to the new DCID
        psm = session.get_psm_for_cid(scid)
        if psm is not None:
            session.map_cid_to_psm(dcid, psm)

    # Configuration Request (0x04)
    elif code == 0x04 and len(sig_data) >= 4:
        dcid = struct.unpack("<H", sig_data[0:2])[0]
        flags = struct.unpack("<H", sig_data[2:4])[0]
        fields.append(DecodedField("dest_cid", f"0x{dcid:04X}"))
        fields.append(DecodedField("flags", f"0x{flags:04X}"))
        summary = f"CONFIG_REQ DCID=0x{dcid:04X}"

    # Configuration Response (0x05)
    elif code == 0x05 and len(sig_data) >= 6:
        scid = struct.unpack("<H", sig_data[0:2])[0]
        flags = struct.unpack("<H", sig_data[2:4])[0]
        result = struct.unpack("<H", sig_data[4:6])[0]
        config_results = {0: "Success", 1: "Unacceptable_Params", 2: "Rejected", 3: "Unknown_Options"}
        fields.append(DecodedField("source_cid", f"0x{scid:04X}"))
        fields.append(DecodedField("result", config_results.get(result, str(result))))
        summary = f"CONFIG_RSP SCID=0x{scid:04X} result={config_results.get(result, str(result))}"

    # Disconnection Request (0x06)
    elif code == 0x06 and len(sig_data) >= 4:
        dcid = struct.unpack("<H", sig_data[0:2])[0]
        scid = struct.unpack("<H", sig_data[2:4])[0]
        fields.append(DecodedField("dest_cid", f"0x{dcid:04X}"))
        fields.append(DecodedField("source_cid", f"0x{scid:04X}"))
        summary = f"DISCONN_REQ DCID=0x{dcid:04X} SCID=0x{scid:04X}"

    # Disconnection Response (0x07)
    elif code == 0x07 and len(sig_data) >= 4:
        dcid = struct.unpack("<H", sig_data[0:2])[0]
        scid = struct.unpack("<H", sig_data[2:4])[0]
        fields.append(DecodedField("dest_cid", f"0x{dcid:04X}"))
        fields.append(DecodedField("source_cid", f"0x{scid:04X}"))
        summary = f"DISCONN_RSP DCID=0x{dcid:04X} SCID=0x{scid:04X}"

    # Information Request (0x0A)
    elif code == 0x0A and len(sig_data) >= 2:
        info_type = struct.unpack("<H", sig_data[0:2])[0]
        info_types = {1: "Connectionless_MTU", 2: "Extended_Features", 3: "Fixed_Channels"}
        fields.append(DecodedField("info_type", info_types.get(info_type, str(info_type))))
        summary = f"INFO_REQ type={info_types.get(info_type, str(info_type))}"

    # Information Response (0x0B)
    elif code == 0x0B and len(sig_data) >= 4:
        info_type = struct.unpack("<H", sig_data[0:2])[0]
        result = struct.unpack("<H", sig_data[2:4])[0]
        info_types = {1: "Connectionless_MTU", 2: "Extended_Features", 3: "Fixed_Channels"}
        fields.append(DecodedField("info_type", info_types.get(info_type, str(info_type))))
        fields.append(DecodedField("result", "Success" if result == 0 else "Not_Supported"))
        summary = f"INFO_RSP type={info_types.get(info_type, str(info_type))}"

    return DecodedLayer(
        protocol="L2CAP_SIG",
        summary=summary,
        fields=fields,
        payload_offset=4 + sig_len,
        payload=sig_data,
    )


def decode(
    data: bytes, session: SessionState
) -> tuple[DecodedLayer, Optional[str], bytes]:
    """
    Decode L2CAP basic header and determine upper protocol.

    Args:
        data: raw L2CAP data (starting with length field)
        session: session state for CID-PSM tracking

    Returns:
        (layer, upper_protocol_name, upper_payload)
        upper_protocol_name is one of: "L2CAP_SIG", "ATT", "SMP", "AVDTP", "AVCTP", "SDP", "RFCOMM", None
    """
    if len(data) < 4:
        return (
            DecodedLayer(protocol="L2CAP", summary="(truncated)", payload=b""),
            None,
            b"",
        )

    l2cap_len, cid = struct.unpack("<HH", data[0:4])
    l2cap_payload = data[4 : 4 + l2cap_len] if len(data) >= 4 + l2cap_len else data[4:]

    fields = [
        DecodedField("length", l2cap_len),
        DecodedField("cid", f"0x{cid:04X}"),
    ]

    # Determine upper protocol from CID
    upper_protocol: Optional[str] = None

    if cid == 0x0001:
        # BR/EDR L2CAP Signaling
        fields.append(DecodedField("channel", "L2CAP_Signaling"))
        layer = DecodedLayer(
            protocol="L2CAP",
            summary=f"L2CAP_SIG len={l2cap_len}",
            fields=fields,
            payload_offset=4,
            payload=l2cap_payload,
        )
        return layer, "L2CAP_SIG", l2cap_payload

    elif cid == 0x0004:
        # ATT
        fields.append(DecodedField("channel", "ATT"))
        upper_protocol = "ATT"

    elif cid == 0x0005:
        # LE L2CAP Signaling
        fields.append(DecodedField("channel", "LE_L2CAP_SIG"))
        upper_protocol = "LE_L2CAP_SIG"

    elif cid == 0x0006:
        # SMP
        fields.append(DecodedField("channel", "SMP"))
        upper_protocol = "SMP"

    else:
        # Dynamic CID - look up PSM
        psm = session.get_psm_for_cid(cid)
        if psm is not None:
            psm_name = get_psm_name(psm)
            fields.append(DecodedField("psm", f"0x{psm:04X}"))
            fields.append(DecodedField("psm_name", psm_name))

            if psm == 0x0019:
                upper_protocol = "AVDTP"
            elif psm == 0x0017:
                upper_protocol = "AVCTP"
            elif psm == 0x001B:
                upper_protocol = "AVCTP_BROWSING"
            elif psm == 0x0001:
                upper_protocol = "SDP"
            elif psm == 0x0003:
                upper_protocol = "RFCOMM"
            elif psm == 0x000F:
                upper_protocol = "BNEP"
            elif psm == 0x0011 or psm == 0x0013:
                upper_protocol = "HID"
            else:
                upper_protocol = psm_name
        else:
            cid_name = L2CAP_CIDS.get(cid, f"CID=0x{cid:04X}")
            fields.append(DecodedField("channel", cid_name))

    protocol_label = upper_protocol or get_cid_name(cid)
    layer = DecodedLayer(
        protocol="L2CAP",
        summary=f"{protocol_label} len={l2cap_len}",
        fields=fields,
        payload_offset=4,
        payload=l2cap_payload,
    )
    return layer, upper_protocol, l2cap_payload
