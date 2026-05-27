"""
SMP (Security Manager Protocol) decoder for BLE pairing.

SMP PDU format:
  Byte 0: Code (SMP command code)
  Bytes 1+: Parameters

Transported over L2CAP fixed channel CID 0x0006.
"""

from __future__ import annotations

import struct
from typing import Optional

from .models import DecodedField, DecodedLayer

# ─── SMP Command Codes ───
SMP_CODES = {
    0x01: "PAIRING_REQUEST",
    0x02: "PAIRING_RESPONSE",
    0x03: "PAIRING_CONFIRM",
    0x04: "PAIRING_RANDOM",
    0x05: "PAIRING_FAILED",
    0x06: "ENCRYPTION_INFORMATION",
    0x07: "CENTRAL_IDENTIFICATION",
    0x08: "IDENTITY_INFORMATION",
    0x09: "IDENTITY_ADDRESS_INFORMATION",
    0x0A: "SIGNING_INFORMATION",
    0x0B: "SECURITY_REQUEST",
    0x0C: "PAIRING_PUBLIC_KEY",
    0x0D: "PAIRING_DHKEY_CHECK",
    0x0E: "PAIRING_KEYPRESS_NOTIFICATION",
}

# ─── SMP Pairing Failed Reason Codes ───
SMP_FAIL_REASONS = {
    0x01: "Passkey_Entry_Failed",
    0x02: "OOB_Not_Available",
    0x03: "Authentication_Requirements",
    0x04: "Confirm_Value_Failed",
    0x05: "Pairing_Not_Supported",
    0x06: "Encryption_Key_Size",
    0x07: "Command_Not_Supported",
    0x08: "Unspecified_Reason",
    0x09: "Repeated_Attempts",
    0x0A: "Invalid_Parameters",
    0x0B: "DHKey_Check_Failed",
    0x0C: "Numeric_Comparison_Failed",
    0x0D: "BR_EDR_Pairing_In_Progress",
    0x0E: "Cross_Transport_Key_Not_Allowed",
    0x0F: "Key_Rejected",
}

# ─── IO Capability values ───
IO_CAPABILITIES = {
    0x00: "DisplayOnly",
    0x01: "DisplayYesNo",
    0x02: "KeyboardOnly",
    0x03: "NoInputNoOutput",
    0x04: "KeyboardDisplay",
}

# ─── OOB Data Flag ───
OOB_FLAGS = {
    0x00: "Not_Present",
    0x01: "Present",
}

# ─── AuthReq bonding flags ───
BONDING_FLAGS = {
    0x00: "No_Bonding",
    0x01: "Bonding",
}

# ─── Keypress Notification Types ───
KEYPRESS_TYPES = {
    0x00: "Passkey_Entry_Started",
    0x01: "Passkey_Digit_Entered",
    0x02: "Passkey_Digit_Erased",
    0x03: "Passkey_Cleared",
    0x04: "Passkey_Entry_Completed",
}


def _parse_auth_req(auth_req: int) -> list[str]:
    """Parse AuthReq byte into flag strings."""
    flags = []
    bonding = auth_req & 0x03
    if bonding:
        flags.append("Bonding")
    if auth_req & 0x04:
        flags.append("MITM")
    if auth_req & 0x08:
        flags.append("SC")
    if auth_req & 0x10:
        flags.append("Keypress")
    if auth_req & 0x20:
        flags.append("CT2")
    return flags


def _parse_key_dist(key_dist: int) -> list[str]:
    """Parse Key Distribution byte into flag strings."""
    keys = []
    if key_dist & 0x01:
        keys.append("EncKey")
    if key_dist & 0x02:
        keys.append("IdKey")
    if key_dist & 0x04:
        keys.append("Sign")
    if key_dist & 0x08:
        keys.append("LinkKey")
    return keys


def decode(payload: bytes) -> DecodedLayer:
    """
    Decode SMP (Security Manager Protocol) PDU.

    Args:
        payload: L2CAP payload for SMP channel (CID 0x0006)

    Returns:
        DecodedLayer with SMP decode information
    """
    if len(payload) < 1:
        return DecodedLayer(protocol="SMP", summary="(empty)", payload=b"")

    code = payload[0]
    code_name = SMP_CODES.get(code, f"0x{code:02X}")

    fields = [
        DecodedField("code", f"0x{code:02X}"),
        DecodedField("command", code_name),
    ]

    summary = code_name
    params = payload[1:]

    # Pairing Request / Response (0x01, 0x02)
    if code in (0x01, 0x02) and len(params) >= 6:
        io_cap = params[0]
        oob = params[1]
        auth_req = params[2]
        max_key_size = params[3]
        init_key_dist = params[4]
        resp_key_dist = params[5]

        io_name = IO_CAPABILITIES.get(io_cap, f"0x{io_cap:02X}")
        auth_flags = _parse_auth_req(auth_req)
        init_keys = _parse_key_dist(init_key_dist)
        resp_keys = _parse_key_dist(resp_key_dist)

        fields.extend([
            DecodedField("io_capability", io_name),
            DecodedField("oob_data_flag", OOB_FLAGS.get(oob, str(oob))),
            DecodedField("auth_req", f"0x{auth_req:02X}"),
            DecodedField("auth_flags", ",".join(auth_flags) if auth_flags else "None"),
            DecodedField("max_encryption_key_size", max_key_size),
            DecodedField("initiator_key_distribution", ",".join(init_keys) if init_keys else "None"),
            DecodedField("responder_key_distribution", ",".join(resp_keys) if resp_keys else "None"),
        ])

        auth_str = ",".join(auth_flags) if auth_flags else "None"
        summary = f"{code_name} IO={io_name} Auth=[{auth_str}] MaxKey={max_key_size}"

    # Pairing Confirm (0x03)
    elif code == 0x03 and len(params) >= 16:
        confirm_value = params[0:16]
        fields.append(DecodedField("confirm_value", confirm_value.hex()))
        summary = f"PAIRING_CONFIRM value={confirm_value[:4].hex()}..."

    # Pairing Random (0x04)
    elif code == 0x04 and len(params) >= 16:
        random_value = params[0:16]
        fields.append(DecodedField("random_value", random_value.hex()))
        summary = f"PAIRING_RANDOM value={random_value[:4].hex()}..."

    # Pairing Failed (0x05)
    elif code == 0x05 and len(params) >= 1:
        reason = params[0]
        reason_name = SMP_FAIL_REASONS.get(reason, f"0x{reason:02X}")
        fields.append(DecodedField("reason", reason_name))
        summary = f"PAIRING_FAILED: {reason_name}"

    # Encryption Information (0x06) - LTK
    elif code == 0x06 and len(params) >= 16:
        ltk = params[0:16]
        fields.append(DecodedField("ltk", ltk.hex()))
        summary = f"ENCRYPTION_INFO LTK={ltk[:4].hex()}..."

    # Central Identification (0x07) - EDIV + Rand
    elif code == 0x07 and len(params) >= 10:
        ediv = struct.unpack("<H", params[0:2])[0]
        rand = params[2:10]
        fields.extend([
            DecodedField("ediv", f"0x{ediv:04X}"),
            DecodedField("rand", rand.hex()),
        ])
        summary = f"CENTRAL_IDENTIFICATION EDIV=0x{ediv:04X}"

    # Identity Information (0x08) - IRK
    elif code == 0x08 and len(params) >= 16:
        irk = params[0:16]
        fields.append(DecodedField("irk", irk.hex()))
        summary = f"IDENTITY_INFO IRK={irk[:4].hex()}..."

    # Identity Address Information (0x09)
    elif code == 0x09 and len(params) >= 7:
        addr_type = params[0]
        addr = ":".join(f"{b:02x}" for b in reversed(params[1:7]))
        addr_type_name = "Public" if addr_type == 0 else "Random"
        fields.extend([
            DecodedField("addr_type", addr_type_name),
            DecodedField("bd_addr", addr),
        ])
        summary = f"IDENTITY_ADDR_INFO {addr_type_name} {addr}"

    # Signing Information (0x0A) - CSRK
    elif code == 0x0A and len(params) >= 16:
        csrk = params[0:16]
        fields.append(DecodedField("csrk", csrk.hex()))
        summary = f"SIGNING_INFO CSRK={csrk[:4].hex()}..."

    # Security Request (0x0B)
    elif code == 0x0B and len(params) >= 1:
        auth_req = params[0]
        auth_flags = _parse_auth_req(auth_req)
        fields.append(DecodedField("auth_req", f"0x{auth_req:02X}"))
        fields.append(DecodedField("auth_flags", ",".join(auth_flags) if auth_flags else "None"))
        summary = f"SECURITY_REQUEST Auth=[{','.join(auth_flags)}]"

    # Pairing Public Key (0x0C)
    elif code == 0x0C and len(params) >= 64:
        pub_key_x = params[0:32]
        pub_key_y = params[32:64]
        fields.extend([
            DecodedField("public_key_x", pub_key_x[:4].hex() + "..."),
            DecodedField("public_key_y", pub_key_y[:4].hex() + "..."),
        ])
        summary = f"PAIRING_PUBLIC_KEY X={pub_key_x[:4].hex()}..."

    # Pairing DHKey Check (0x0D)
    elif code == 0x0D and len(params) >= 16:
        check = params[0:16]
        fields.append(DecodedField("dhkey_check", check.hex()))
        summary = f"PAIRING_DHKEY_CHECK value={check[:4].hex()}..."

    # Keypress Notification (0x0E)
    elif code == 0x0E and len(params) >= 1:
        notification_type = params[0]
        type_name = KEYPRESS_TYPES.get(notification_type, f"0x{notification_type:02X}")
        fields.append(DecodedField("notification_type", type_name))
        summary = f"KEYPRESS_NOTIFICATION: {type_name}"

    return DecodedLayer(
        protocol="SMP",
        summary=summary,
        fields=fields,
        payload=params,
    )
