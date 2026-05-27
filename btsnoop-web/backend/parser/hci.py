"""
HCI (Host Controller Interface) layer decoder.

HCI packet types:
  0x01 - Command
  0x02 - ACL Data
  0x03 - SCO Data
  0x04 - Event
  0x05 - ISO Data (BT 5.2+)
"""

from __future__ import annotations

import struct
from typing import Optional

from .models import DecodedField, DecodedLayer, HciType

# ─── HCI Packet Types ───
HCI_TYPES = {
    0x01: "HCI_CMD",
    0x02: "ACL",
    0x03: "SCO",
    0x04: "HCI_EVT",
    0x05: "ISO",
}

# ─── HCI Command Opcodes (BT Core Spec + common vendor) ───
HCI_CMDS = {
    # Link Control (OGF=0x01)
    0x0401: "Inquiry",
    0x0402: "Inquiry_Cancel",
    0x0403: "Periodic_Inquiry",
    0x0404: "Exit_Periodic_Inquiry",
    0x0405: "Create_Connection",
    0x0406: "Disconnect",
    0x0407: "Add_SCO_Connection",
    0x0408: "Accept_Connection",
    0x0409: "Reject_Connection",
    0x040B: "Link_Key_Reply",
    0x040C: "Link_Key_Neg_Reply",
    0x040D: "PIN_Code_Reply",
    0x0411: "Authentication_Requested",
    0x0413: "Change_Conn_Pkt_Type",
    0x0419: "Remote_Name_Cancel",
    0x041A: "Remote_Name_Request",
    0x041B: "Read_Remote_Features",
    0x041C: "Read_Remote_Ext_Features",
    0x041D: "Read_Remote_Version",
    0x0428: "Setup_Sync_Conn",
    0x0429: "Accept_Sync_Conn",
    0x042B: "IO_Capability_Reply",
    0x042C: "User_Confirm_Reply",
    0x042D: "User_Confirm_Neg_Reply",
    0x0434: "IO_Capability_Neg_Reply",
    # Link Policy (OGF=0x02)
    0x0801: "Hold_Mode",
    0x0803: "Sniff_Mode",
    0x0804: "Exit_Sniff",
    0x080D: "Write_Link_Policy",
    0x080F: "Write_Default_Link_Policy",
    0x0811: "Sniff_Subrating",
    # Controller & Baseband (OGF=0x03)
    0x0C01: "Set_Event_Mask",
    0x0C03: "Reset",
    0x0C05: "Set_Event_Filter",
    0x0C08: "Flush",
    0x0C13: "Change_Local_Name",
    0x0C14: "Read_Local_Name",
    0x0C1A: "Write_Scan_Enable",
    0x0C1C: "Write_Page_Scan_Activity",
    0x0C1E: "Write_Inquiry_Scan_Activity",
    0x0C20: "Write_Authentication_Enable",
    0x0C24: "Write_Class_of_Device",
    0x0C25: "Read_Voice_Setting",
    0x0C26: "Write_Voice_Setting",
    0x0C28: "Write_Auto_Flush_Timeout",
    0x0C2D: "Read_Transmit_Power",
    0x0C33: "Host_Buffer_Size",
    0x0C35: "Read_Link_Supervision_TO",
    0x0C37: "Write_Link_Supervision_TO",
    0x0C39: "Read_Num_Broadcast_Retrans",
    0x0C45: "Write_Inquiry_Mode",
    0x0C47: "Read_Page_Scan_Type",
    0x0C52: "Write_EIR",
    0x0C55: "Read_Simple_Pairing",
    0x0C56: "Write_Simple_Pairing",
    0x0C58: "Read_Inquiry_Rsp_TX",
    0x0C5B: "Read_Default_Erroneous",
    0x0C60: "Read_LE_Host_Support",
    0x0C6D: "Write_LE_Host_Support",
    0x0C63: "Set_Event_Mask_Page2",
    0x0C7A: "Write_Secure_Conn_Support",
    0x0C84: "Set_Min_Encryption_Key_Size",
    # Informational (OGF=0x04)
    0x1001: "Read_Local_Version",
    0x1002: "Read_Local_Commands",
    0x1003: "Read_Local_Features",
    0x1004: "Read_Local_Ext_Features",
    0x1005: "Read_Buffer_Size",
    0x1009: "Read_BD_Addr",
    0x100B: "Read_Data_Block_Size",
    # Status (OGF=0x05)
    0x1403: "Read_RSSI",
    # LE Controller (OGF=0x08)
    0x2001: "LE_Set_Event_Mask",
    0x2002: "LE_Read_Buffer_Size",
    0x2003: "LE_Read_Local_Features",
    0x2005: "LE_Set_Random_Addr",
    0x2006: "LE_Set_Adv_Params",
    0x2008: "LE_Set_Adv_Data",
    0x200A: "LE_Set_Adv_Enable",
    0x200C: "LE_Set_Scan_Params",
    0x200D: "LE_Set_Scan_Enable",
    0x200E: "LE_Create_Connection",
    0x200F: "LE_Read_White_List_Size",
    0x201C: "LE_Read_Supported_States",
    0x2023: "LE_Read_Max_Data_Length",
    0x202A: "LE_Read_Num_Adv_Sets",
    0x202F: "LE_Read_TX_Power",
    0x203A: "LE_Read_RF_Path_Compensation",
    0x203B: "LE_Write_RF_Path_Compensation",
    0x204A: "LE_Read_Buffer_Size_V2",
    0x2060: "LE_Set_Host_Feature",
    # Vendor Specific
    0xFC17: "VS_MTK_Init",
    0xFD5D: "VS_A2DP_Opcode",
    0xFD95: "VS_Codec_State",
    0xFD53: "VS_MTK_Config",
}

# ─── HCI Event Codes ───
HCI_EVTS = {
    0x01: "Inquiry_Complete",
    0x02: "Inquiry_Result",
    0x03: "Conn_Complete",
    0x04: "Conn_Request",
    0x05: "Disconn_Complete",
    0x06: "Auth_Complete",
    0x07: "Remote_Name_Complete",
    0x08: "Encrypt_Change",
    0x09: "Change_Conn_Link_Key_Complete",
    0x0B: "Read_Remote_Features_Complete",
    0x0C: "Read_Remote_Version_Complete",
    0x0E: "Cmd_Complete",
    0x0F: "Cmd_Status",
    0x10: "Hardware_Error",
    0x12: "Role_Change",
    0x13: "Num_Completed_Pkts",
    0x14: "Mode_Change",
    0x17: "Link_Key_Notification",
    0x18: "Loopback_Command",
    0x1B: "Max_Slots_Change",
    0x1C: "Read_Clock_Offset_Complete",
    0x1D: "Conn_Pkt_Type_Changed",
    0x20: "Page_Scan_Repetition_Mode_Change",
    0x22: "Inquiry_Result_With_RSSI",
    0x2F: "Extended_Inquiry_Result",
    0x30: "Encryption_Key_Refresh",
    0x31: "IO_Capability_Request",
    0x32: "IO_Capability_Response",
    0x33: "User_Confirm_Request",
    0x34: "User_Passkey_Request",
    0x35: "Remote_OOB_Data_Request",
    0x36: "Simple_Pairing_Complete",
    0x38: "Link_Supervision_TO_Changed",
    0x3E: "LE_Meta",
    0xFF: "Vendor_Specific",
}

# ─── LE Meta Subevent codes ───
LE_META_SUBEVENTS = {
    0x01: "LE_Conn_Complete",
    0x02: "LE_Adv_Report",
    0x03: "LE_Conn_Update_Complete",
    0x04: "LE_Read_Remote_Features_Complete",
    0x05: "LE_Long_Term_Key_Request",
    0x07: "LE_Data_Length_Change",
    0x08: "LE_Read_Local_P256_Public_Key_Complete",
    0x09: "LE_Generate_DHKey_Complete",
    0x0A: "LE_Enhanced_Conn_Complete",
    0x0B: "LE_Directed_Advertising_Report",
    0x0C: "LE_PHY_Update_Complete",
    0x0D: "LE_Extended_Adv_Report",
    0x0E: "LE_Periodic_Adv_Sync_Established",
    0x0F: "LE_Periodic_Adv_Report",
    0x19: "LE_CIS_Established",
    0x1A: "LE_CIS_Request",
}

# Mode names for Mode_Change event
MODE_NAMES = {0: "Active", 1: "Hold", 2: "Sniff", 3: "Park"}


def get_opcode_name(opcode: int) -> str:
    """Look up a human-readable name for an HCI command opcode."""
    return HCI_CMDS.get(opcode, f"0x{opcode:04X}")


def get_event_name(evt_code: int) -> str:
    """Look up a human-readable name for an HCI event code."""
    return HCI_EVTS.get(evt_code, f"0x{evt_code:02X}")


def decode_hci_command(data: bytes) -> DecodedLayer:
    """
    Decode an HCI Command packet.
    data[0] = 0x01 (packet type indicator, already consumed or present)
    Format: opcode(2 LE) + param_length(1) + params...
    """
    if len(data) < 4:
        return DecodedLayer(
            protocol="HCI_CMD",
            summary="(truncated)",
            payload=b"",
        )

    opcode = struct.unpack("<H", data[1:3])[0]
    param_len = data[3]
    ogf = (opcode >> 10) & 0x3F
    ocf = opcode & 0x03FF
    name = get_opcode_name(opcode)

    fields = [
        DecodedField("opcode", f"0x{opcode:04X}", offset=1, length=2, raw=data[1:3]),
        DecodedField("ogf", ogf, offset=1, length=2),
        DecodedField("ocf", ocf, offset=1, length=2),
        DecodedField("name", name, offset=1, length=2),
        DecodedField("param_length", param_len, offset=3, length=1),
    ]

    # Decode specific commands
    params = data[4 : 4 + param_len] if len(data) >= 4 + param_len else data[4:]

    if opcode == 0x0405 and len(params) >= 6:
        # Create_Connection: BD_ADDR(6) + ...
        addr = ":".join(f"{b:02x}" for b in reversed(params[0:6]))
        fields.append(DecodedField("bd_addr", addr, offset=4, length=6))

    elif opcode == 0x0406 and len(params) >= 3:
        # Disconnect: handle(2) + reason(1)
        handle = struct.unpack("<H", params[0:2])[0]
        reason = params[2]
        fields.append(DecodedField("handle", f"0x{handle:04X}", offset=4, length=2))
        fields.append(DecodedField("reason", f"0x{reason:02X}", offset=6, length=1))

    summary = f"{name} (0x{opcode:04X}) plen={param_len}"
    return DecodedLayer(
        protocol="HCI_CMD",
        summary=summary,
        fields=fields,
        payload_offset=4 + param_len,
        payload=params,
    )


def decode_hci_event(data: bytes) -> DecodedLayer:
    """
    Decode an HCI Event packet.
    data[0] = 0x04 (packet type indicator)
    Format: event_code(1) + param_length(1) + params...
    """
    if len(data) < 3:
        return DecodedLayer(
            protocol="HCI_EVT",
            summary="(truncated)",
            payload=b"",
        )

    evt_code = data[1]
    param_len = data[2]
    evt_name = get_event_name(evt_code)
    params = data[3 : 3 + param_len] if len(data) >= 3 + param_len else data[3:]

    fields = [
        DecodedField("event_code", f"0x{evt_code:02X}", offset=1, length=1),
        DecodedField("name", evt_name, offset=1, length=1),
        DecodedField("param_length", param_len, offset=2, length=1),
    ]

    summary = f"{evt_name} plen={param_len}"

    # Command Complete (0x0E)
    if evt_code == 0x0E and len(params) >= 4:
        num_pkts = params[0]
        cc_opcode = struct.unpack("<H", params[1:3])[0]
        cc_name = get_opcode_name(cc_opcode)
        status = params[3]
        fields.append(DecodedField("num_hci_command_packets", num_pkts))
        fields.append(DecodedField("command_opcode", f"0x{cc_opcode:04X}"))
        fields.append(DecodedField("command_name", cc_name))
        fields.append(DecodedField("status", status))
        st_str = f" status={status}" if status > 0 else ""
        summary = f"Cmd_Complete: {cc_name}{st_str}"

    # Command Status (0x0F)
    elif evt_code == 0x0F and len(params) >= 4:
        status = params[0]
        num_pkts = params[1]
        cs_opcode = struct.unpack("<H", params[2:4])[0]
        cs_name = get_opcode_name(cs_opcode)
        fields.append(DecodedField("status", status))
        fields.append(DecodedField("command_opcode", f"0x{cs_opcode:04X}"))
        fields.append(DecodedField("command_name", cs_name))
        summary = f"Cmd_Status: {cs_name} status={status}"

    # Connection Complete (0x03)
    elif evt_code == 0x03 and len(params) >= 11:
        status = params[0]
        handle = struct.unpack("<H", params[1:3])[0]
        addr = ":".join(f"{b:02x}" for b in reversed(params[3:9]))
        link_type = params[9]
        encryption = params[10]
        fields.append(DecodedField("status", status))
        fields.append(DecodedField("handle", f"0x{handle:04X}"))
        fields.append(DecodedField("bd_addr", addr))
        fields.append(DecodedField("link_type", link_type))
        fields.append(DecodedField("encryption", encryption))
        summary = f"Conn_Complete handle=0x{handle:04X} addr={addr} st={status}"

    # Disconnection Complete (0x05)
    elif evt_code == 0x05 and len(params) >= 4:
        status = params[0]
        handle = struct.unpack("<H", params[1:3])[0]
        reason = params[3]
        fields.append(DecodedField("status", status))
        fields.append(DecodedField("handle", f"0x{handle:04X}"))
        fields.append(DecodedField("reason", f"0x{reason:02X}"))
        summary = f"Disconn_Complete handle=0x{handle:04X} reason=0x{reason:02X}"

    # Mode Change (0x14)
    elif evt_code == 0x14 and len(params) >= 4:
        status = params[0]
        handle = struct.unpack("<H", params[1:3])[0]
        mode = params[3]
        mode_name = MODE_NAMES.get(mode, str(mode))
        fields.append(DecodedField("status", status))
        fields.append(DecodedField("handle", f"0x{handle:04X}"))
        fields.append(DecodedField("mode", mode_name))
        summary = f"Mode_Change: {mode_name} handle=0x{handle:04X}"

    # Num Completed Packets (0x13)
    elif evt_code == 0x13 and len(params) >= 1:
        num = params[0]
        fields.append(DecodedField("num_handles", num))
        summary = f"Num_Completed_Pkts n={num}"

    # LE Meta Event (0x3E)
    elif evt_code == 0x3E and len(params) >= 1:
        subevent = params[0]
        sub_name = LE_META_SUBEVENTS.get(subevent, f"sub=0x{subevent:02X}")
        fields.append(DecodedField("subevent", f"0x{subevent:02X}"))
        fields.append(DecodedField("subevent_name", sub_name))
        summary = f"LE_Meta: {sub_name}"

        # LE Connection Complete
        if subevent == 0x01 and len(params) >= 19:
            status = params[1]
            handle = struct.unpack("<H", params[2:4])[0]
            role = params[4]
            addr_type = params[5]
            addr = ":".join(f"{b:02x}" for b in reversed(params[6:12]))
            fields.append(DecodedField("status", status))
            fields.append(DecodedField("handle", f"0x{handle:04X}"))
            fields.append(DecodedField("role", "Central" if role == 0 else "Peripheral"))
            fields.append(DecodedField("peer_addr", addr))
            summary = f"LE_Meta: LE_Conn_Complete handle=0x{handle:04X} addr={addr}"

        # LE Enhanced Connection Complete
        elif subevent == 0x0A and len(params) >= 31:
            status = params[1]
            handle = struct.unpack("<H", params[2:4])[0]
            role = params[4]
            addr_type = params[5]
            addr = ":".join(f"{b:02x}" for b in reversed(params[6:12]))
            fields.append(DecodedField("status", status))
            fields.append(DecodedField("handle", f"0x{handle:04X}"))
            fields.append(DecodedField("peer_addr", addr))
            summary = f"LE_Meta: LE_Enhanced_Conn_Complete handle=0x{handle:04X} addr={addr}"

    # Encrypt Change (0x08)
    elif evt_code == 0x08 and len(params) >= 4:
        status = params[0]
        handle = struct.unpack("<H", params[1:3])[0]
        enabled = params[3]
        fields.append(DecodedField("status", status))
        fields.append(DecodedField("handle", f"0x{handle:04X}"))
        fields.append(DecodedField("encryption_enabled", enabled))
        summary = f"Encrypt_Change handle=0x{handle:04X} enabled={enabled}"

    return DecodedLayer(
        protocol="HCI_EVT",
        summary=summary,
        fields=fields,
        payload_offset=3 + param_len,
        payload=params,
    )


def decode_hci_acl(data: bytes) -> tuple[DecodedLayer, int, bytes]:
    """
    Decode the HCI ACL header.
    data[0] = 0x02
    Format: handle_flags(2 LE) + data_length(2 LE) + payload

    Returns: (layer, connection_handle, l2cap_payload)
    """
    if len(data) < 5:
        return (
            DecodedLayer(protocol="ACL", summary="(truncated)", payload=b""),
            0,
            b"",
        )

    hf = struct.unpack("<H", data[1:3])[0]
    handle = hf & 0x0FFF
    pb_flag = (hf >> 12) & 0x03
    bc_flag = (hf >> 14) & 0x03
    acl_len = struct.unpack("<H", data[3:5])[0]

    pb_names = {0: "First_Non_Flush", 1: "Continuing", 2: "First_Auto_Flush", 3: "Complete"}
    bc_names = {0: "Point-to-Point", 1: "Active_Broadcast", 2: "Piconet_Broadcast"}

    fields = [
        DecodedField("handle", f"0x{handle:04X}"),
        DecodedField("pb_flag", pb_names.get(pb_flag, str(pb_flag))),
        DecodedField("bc_flag", bc_names.get(bc_flag, str(bc_flag))),
        DecodedField("data_length", acl_len),
    ]

    payload = data[5 : 5 + acl_len] if len(data) >= 5 + acl_len else data[5:]

    layer = DecodedLayer(
        protocol="ACL",
        summary=f"handle=0x{handle:04X} len={acl_len}",
        fields=fields,
        payload_offset=5,
        payload=payload,
    )
    return layer, handle, payload


def decode_hci_sco(data: bytes) -> DecodedLayer:
    """
    Decode HCI SCO packet.
    data[0] = 0x03
    Format: handle_flags(2 LE) + data_length(1) + payload
    """
    if len(data) < 4:
        return DecodedLayer(protocol="SCO", summary="(truncated)", payload=b"")

    hf = struct.unpack("<H", data[1:3])[0]
    handle = hf & 0x0FFF
    sco_len = data[3]

    fields = [
        DecodedField("handle", f"0x{handle:04X}"),
        DecodedField("data_length", sco_len),
    ]

    payload = data[4 : 4 + sco_len] if len(data) >= 4 + sco_len else data[4:]

    return DecodedLayer(
        protocol="SCO",
        summary=f"handle=0x{handle:04X} len={sco_len}",
        fields=fields,
        payload_offset=4,
        payload=payload,
    )


def decode_hci_iso(data: bytes) -> DecodedLayer:
    """
    Decode HCI ISO packet (BT 5.2+).
    data[0] = 0x05
    Format: handle_flags(2 LE) + data_load_length(2 LE) + payload
    """
    if len(data) < 5:
        return DecodedLayer(protocol="ISO", summary="(truncated)", payload=b"")

    hf = struct.unpack("<H", data[1:3])[0]
    handle = hf & 0x0FFF
    pb_flag = (hf >> 12) & 0x03
    ts_flag = (hf >> 14) & 0x01
    iso_len = struct.unpack("<H", data[3:5])[0] & 0x3FFF

    fields = [
        DecodedField("handle", f"0x{handle:04X}"),
        DecodedField("pb_flag", pb_flag),
        DecodedField("ts_flag", ts_flag),
        DecodedField("data_load_length", iso_len),
    ]

    payload = data[5 : 5 + iso_len] if len(data) >= 5 + iso_len else data[5:]

    return DecodedLayer(
        protocol="ISO",
        summary=f"handle=0x{handle:04X} len={iso_len}",
        fields=fields,
        payload_offset=5,
        payload=payload,
    )


def decode(data: bytes) -> Optional[DecodedLayer]:
    """
    Top-level HCI decode entry point.
    Dispatches to the appropriate decoder based on the packet type indicator byte.
    Returns a DecodedLayer or None if the packet type is unknown.
    """
    if len(data) < 1:
        return None

    pkt_type = data[0]

    if pkt_type == HciType.COMMAND.value:
        return decode_hci_command(data)
    elif pkt_type == HciType.EVENT.value:
        return decode_hci_event(data)
    elif pkt_type == HciType.ACL.value:
        layer, handle, payload = decode_hci_acl(data)
        return layer
    elif pkt_type == HciType.SCO.value:
        return decode_hci_sco(data)
    elif pkt_type == HciType.ISO.value:
        return decode_hci_iso(data)
    else:
        return DecodedLayer(
            protocol="UNKNOWN",
            summary=f"type=0x{pkt_type:02X} len={len(data)}",
            payload=data[1:],
        )
