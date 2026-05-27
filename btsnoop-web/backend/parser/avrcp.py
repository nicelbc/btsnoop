"""
AVCTP/AVRCP (Audio/Video Remote Control Protocol) decoder.

AVCTP header (for single packet):
  Byte 0: Transaction_Label(4 bits) | Packet_Type(2 bits) | C/R(1 bit) | IPID(1 bit)
  Bytes 1-2: PID (Profile ID, 2 bytes BE) - 0x110E for AVRCP

AV/C frame (within AVCTP payload):
  Byte 0: CType/Response(4 bits) | Subunit_Type(5 bits) | Subunit_ID(3 bits)
  Actually: Byte 0 = CType(4) | ... but the standard layout is:
  Byte 0: CType/Response (4 bits) | Subunit_Type (high 5 bits of next byte)
  Proper: ctype(1 byte first nibble) = cmd_type, subunit_type(5bits), subunit_id(3bits), opcode(1byte)

For AVRCP:
  - Opcode 0x7C = PASS THROUGH
  - Opcode 0x00 = VENDOR DEPENDENT (used for metadata, browsing)
"""

from __future__ import annotations

import struct
from typing import Optional

from .models import DecodedField, DecodedLayer

# ─── AVCTP Packet Types ───
AVCTP_PKT_TYPES = {
    0: "Single",
    1: "Start",
    2: "Continue",
    3: "End",
}

# ─── AV/C Command/Response Types ───
AVC_CTYPE = {
    0x00: "CONTROL",
    0x01: "STATUS",
    0x02: "SPECIFIC_INQUIRY",
    0x03: "NOTIFY",
    0x04: "GENERAL_INQUIRY",
    # Response codes
    0x08: "NOT_IMPLEMENTED",
    0x09: "ACCEPTED",
    0x0A: "REJECTED",
    0x0B: "IN_TRANSITION",
    0x0C: "STABLE",
    0x0D: "CHANGED",
    0x0F: "INTERIM",
}

# ─── AV/C Subunit Types ───
AVC_SUBUNIT_TYPES = {
    0x00: "Monitor",
    0x01: "Audio",
    0x02: "Printer",
    0x03: "Disc",
    0x04: "Tape_Recorder",
    0x05: "Tuner",
    0x06: "CA",
    0x07: "Camera",
    0x09: "Panel",
    0x0A: "Bulletin_Board",
    0x0B: "Camera_Storage",
    0x1C: "Vendor_Unique",
    0x1E: "Extended",
    0x1F: "Unit",
}

# ─── AVRCP Opcodes ───
AVC_OPCODES = {
    0x00: "VENDOR_DEPENDENT",
    0x7C: "PASS_THROUGH",
    0x30: "UNIT_INFO",
    0x31: "SUBUNIT_INFO",
}

# ─── AVRCP PDU IDs (within Vendor Dependent) ───
AVRCP_PDUS = {
    0x10: "GET_CAPABILITIES",
    0x11: "LIST_PLAYER_APP_SETTING_ATTR",
    0x12: "LIST_PLAYER_APP_SETTING_VALUES",
    0x13: "GET_CURRENT_PLAYER_APP_SETTING",
    0x14: "SET_PLAYER_APP_SETTING",
    0x15: "GET_PLAYER_APP_SETTING_ATTR_TEXT",
    0x16: "GET_PLAYER_APP_SETTING_VALUE_TEXT",
    0x17: "INFORM_DISPLAYABLE_CHAR_SET",
    0x18: "INFORM_BATTERY_STATUS",
    0x20: "GET_ELEMENT_ATTRIBUTES",
    0x30: "GET_PLAY_STATUS",
    0x31: "REGISTER_NOTIFICATION",
    0x32: "REQUEST_CONTINUING_RESPONSE",
    0x33: "ABORT_CONTINUING_RESPONSE",
    0x40: "SET_ABSOLUTE_VOLUME",
    0x48: "SET_ADDRESSED_PLAYER",
    0x50: "SET_BROWSED_PLAYER",
    0x71: "GET_FOLDER_ITEMS",
    0x72: "CHANGE_PATH",
    0x73: "GET_ITEM_ATTRIBUTES",
    0x74: "PLAY_ITEM",
    0x75: "GET_TOTAL_NUM_ITEMS",
    0x80: "SEARCH",
    0x90: "ADD_TO_NOW_PLAYING",
}

# ─── PASS THROUGH key operations ───
PASSTHROUGH_OPS = {
    0x41: "VOLUME_UP",
    0x42: "VOLUME_DOWN",
    0x43: "MUTE",
    0x44: "PLAY",
    0x45: "STOP",
    0x46: "PAUSE",
    0x47: "RECORD",
    0x48: "REWIND",
    0x49: "FAST_FORWARD",
    0x4B: "FORWARD",
    0x4C: "BACKWARD",
}

# ─── AVRCP Notification Event IDs ───
AVRCP_EVENTS = {
    0x01: "PLAYBACK_STATUS_CHANGED",
    0x02: "TRACK_CHANGED",
    0x03: "TRACK_REACHED_END",
    0x04: "TRACK_REACHED_START",
    0x05: "PLAYBACK_POS_CHANGED",
    0x06: "BATTERY_STATUS_CHANGED",
    0x07: "SYSTEM_STATUS_CHANGED",
    0x08: "PLAYER_APP_SETTING_CHANGED",
    0x09: "NOW_PLAYING_CONTENT_CHANGED",
    0x0A: "AVAILABLE_PLAYERS_CHANGED",
    0x0B: "ADDRESSED_PLAYER_CHANGED",
    0x0C: "UIDS_CHANGED",
    0x0D: "VOLUME_CHANGED",
}

# ─── Play Status Values ───
PLAY_STATUS = {
    0x00: "STOPPED",
    0x01: "PLAYING",
    0x02: "PAUSED",
    0x03: "FWD_SEEK",
    0x04: "REV_SEEK",
    0xFF: "ERROR",
}

# AVRCP BT SIG Company ID
BT_SIG_COMPANY_ID = 0x001958


def decode(payload: bytes) -> DecodedLayer:
    """
    Decode AVCTP/AVRCP packet.

    Args:
        payload: L2CAP payload for AVCTP channel (PSM 0x0017)

    Returns:
        DecodedLayer with AVRCP decode information
    """
    if len(payload) < 3:
        return DecodedLayer(protocol="AVRCP", summary="(truncated)", payload=b"")

    # AVCTP header
    hdr0 = payload[0]
    trans_label = (hdr0 >> 4) & 0x0F
    pkt_type = (hdr0 >> 2) & 0x03
    cr_flag = (hdr0 >> 1) & 0x01  # 0=Command, 1=Response
    ipid = hdr0 & 0x01  # Invalid Profile ID

    # PID (Profile Identifier) - 2 bytes big-endian
    pid = struct.unpack(">H", payload[1:3])[0]

    cr_str = "CMD" if cr_flag == 0 else "RSP"

    fields = [
        DecodedField("transaction_label", trans_label),
        DecodedField("packet_type", AVCTP_PKT_TYPES.get(pkt_type, str(pkt_type))),
        DecodedField("cr", cr_str),
        DecodedField("pid", f"0x{pid:04X}"),
    ]

    # For non-single packets, just provide basic info
    if pkt_type != 0:
        summary = f"AVRCP {cr_str} fragment ({AVCTP_PKT_TYPES.get(pkt_type, '?')}) label={trans_label}"
        return DecodedLayer(
            protocol="AVRCP",
            summary=summary,
            fields=fields,
            payload=payload[3:],
        )

    # AV/C frame starts at byte 3
    avc_data = payload[3:]
    if len(avc_data) < 3:
        summary = f"AVRCP {cr_str} label={trans_label} (short AV/C)"
        return DecodedLayer(protocol="AVRCP", summary=summary, fields=fields, payload=avc_data)

    # AV/C header
    ctype = avc_data[0] & 0x0F
    subunit_type = (avc_data[1] >> 3) & 0x1F
    subunit_id = avc_data[1] & 0x07
    opcode = avc_data[2]

    ctype_name = AVC_CTYPE.get(ctype, f"0x{ctype:02X}")
    subunit_name = AVC_SUBUNIT_TYPES.get(subunit_type, f"0x{subunit_type:02X}")
    opcode_name = AVC_OPCODES.get(opcode, f"0x{opcode:02X}")

    fields.extend([
        DecodedField("ctype", ctype_name),
        DecodedField("subunit_type", subunit_name),
        DecodedField("subunit_id", subunit_id),
        DecodedField("opcode", opcode_name),
    ])

    summary = f"AVRCP {cr_str} {opcode_name}"

    # PASS THROUGH (opcode 0x7C)
    if opcode == 0x7C and len(avc_data) >= 5:
        state_flag = (avc_data[3] >> 7) & 0x01  # 0=pressed, 1=released
        op_id = avc_data[3] & 0x7F
        op_name = PASSTHROUGH_OPS.get(op_id, f"0x{op_id:02X}")
        state_str = "released" if state_flag else "pressed"
        fields.append(DecodedField("operation", op_name))
        fields.append(DecodedField("state", state_str))
        summary = f"AVRCP {cr_str} PASS_THROUGH: {op_name} ({state_str})"

    # VENDOR DEPENDENT (opcode 0x00)
    elif opcode == 0x00 and len(avc_data) >= 9:
        # Company ID (3 bytes)
        company_id = (avc_data[3] << 16) | (avc_data[4] << 8) | avc_data[5]
        fields.append(DecodedField("company_id", f"0x{company_id:06X}"))

        if company_id == BT_SIG_COMPANY_ID:
            # AVRCP specific PDU
            pdu_id = avc_data[6]
            # packet_type in AVRCP vendor dependent
            avrcp_pkt_type = avc_data[7] & 0x03
            param_len = struct.unpack(">H", avc_data[8:10])[0] if len(avc_data) >= 10 else 0

            pdu_name = AVRCP_PDUS.get(pdu_id, f"PDU_0x{pdu_id:02X}")
            fields.append(DecodedField("pdu_id", f"0x{pdu_id:02X}"))
            fields.append(DecodedField("pdu_name", pdu_name))
            fields.append(DecodedField("param_length", param_len))

            summary = f"AVRCP {cr_str} {pdu_name}"

            params = avc_data[10 : 10 + param_len] if len(avc_data) >= 10 + param_len else avc_data[10:]

            # Register Notification
            if pdu_id == 0x31 and len(params) >= 1:
                event_id = params[0]
                event_name = AVRCP_EVENTS.get(event_id, f"0x{event_id:02X}")
                fields.append(DecodedField("event_id", event_name))
                summary += f" event={event_name}"

                # If response with volume changed
                if event_id == 0x0D and len(params) >= 2:
                    volume = params[1] & 0x7F
                    volume_pct = int(volume * 100 / 127)
                    fields.append(DecodedField("volume", f"{volume_pct}%"))
                    summary += f" vol={volume_pct}%"

                # If response with play status
                if event_id == 0x01 and len(params) >= 2:
                    play_st = params[1]
                    play_name = PLAY_STATUS.get(play_st, f"0x{play_st:02X}")
                    fields.append(DecodedField("play_status", play_name))
                    summary += f" status={play_name}"

            # Set Absolute Volume
            elif pdu_id == 0x40 and len(params) >= 1:
                volume = params[0] & 0x7F
                volume_pct = int(volume * 100 / 127)
                fields.append(DecodedField("volume", f"{volume_pct}%"))
                summary += f" vol={volume_pct}%"

            # Get Play Status Response
            elif pdu_id == 0x30 and ctype >= 0x08 and len(params) >= 9:
                song_len = struct.unpack(">I", params[0:4])[0]
                song_pos = struct.unpack(">I", params[4:8])[0]
                play_st = params[8]
                play_name = PLAY_STATUS.get(play_st, f"0x{play_st:02X}")
                fields.append(DecodedField("song_length_ms", song_len))
                fields.append(DecodedField("song_position_ms", song_pos))
                fields.append(DecodedField("play_status", play_name))
                summary += f" {play_name} pos={song_pos}ms/{song_len}ms"

            # Get Capabilities
            elif pdu_id == 0x10:
                if ctype < 0x08 and len(params) >= 1:
                    # Command
                    cap_id = params[0]
                    cap_names = {0x02: "CompanyID", 0x03: "EventsSupported"}
                    fields.append(DecodedField("capability_id", cap_names.get(cap_id, str(cap_id))))
                    summary += f" cap={cap_names.get(cap_id, str(cap_id))}"
                elif ctype >= 0x08 and len(params) >= 2:
                    # Response
                    cap_id = params[0]
                    cap_count = params[1]
                    cap_names = {0x02: "CompanyID", 0x03: "EventsSupported"}
                    fields.append(DecodedField("capability_id", cap_names.get(cap_id, str(cap_id))))
                    fields.append(DecodedField("capability_count", cap_count))
                    summary += f" cap={cap_names.get(cap_id, str(cap_id))} count={cap_count}"

            summary += f" [{ctype_name}]"
        else:
            summary = f"AVRCP {cr_str} VENDOR_DEP company=0x{company_id:06X}"

    return DecodedLayer(
        protocol="AVRCP",
        summary=summary,
        fields=fields,
        payload=avc_data,
    )
