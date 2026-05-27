"""
RFCOMM protocol decoder.

RFCOMM provides serial port emulation over L2CAP (PSM 0x0003).
Frame format: Address(1) + Control(1) + Length(1-2) + Data(N) + FCS(1)
"""

from __future__ import annotations

import struct
from typing import Optional

from .models import DecodedField, DecodedLayer


# RFCOMM frame types (control field with P/F bit masked out)
FRAME_TYPES = {
    0x2F: "SABM",   # Set Async Balanced Mode
    0x63: "UA",     # Unnumbered Acknowledgement
    0x0F: "DM",     # Disconnected Mode
    0x43: "DISC",   # Disconnect
    0xEF: "UIH",    # Unnumbered Info with Header check
    0x03: "UI",     # Unnumbered Info
}

# Modem status signals
MODEM_SIGNALS = {
    0x01: "FC",   # Flow Control
    0x02: "RTC",  # Ready to Communicate
    0x04: "RTR",  # Ready to Receive
    0x08: "IC",   # Incoming Call
    0x40: "DV",   # Data Valid
}

# Multiplexer commands
MUX_CMDS = {
    0x20: "PN",    # Parameter Negotiation
    0x08: "PSC",   # Power Saving Control
    0x10: "CLD",   # Close Down
    0x38: "MSC",   # Modem Status Command
    0x04: "TEST",  # Test
    0x24: "FCON",  # Flow Control On
    0x14: "FCOFF", # Flow Control Off
    0x28: "RPN",   # Remote Port Negotiation
    0x30: "RLS",   # Remote Line Status
    0x34: "SNC",   # Service Negotiation Command
}


def decode(data: bytes) -> DecodedLayer:
    """
    Decode an RFCOMM frame.

    Args:
        data: RFCOMM frame bytes (from L2CAP payload on PSM 0x0003)

    Returns:
        DecodedLayer with RFCOMM decode info
    """
    fields = []

    if len(data) < 3:
        return DecodedLayer(
            protocol="RFCOMM",
            summary="(truncated)",
            fields=[DecodedField(name="error", value="frame too short")],
        )

    # Address byte
    addr = data[0]
    ea = addr & 0x01        # Extension bit (should be 1)
    cr = (addr >> 1) & 0x01  # Command/Response
    dlci = (addr >> 2) & 0x3F
    direction = (dlci >> 0) & 0x01
    server_channel = dlci >> 1

    fields.append(DecodedField(name="address", value=f"0x{addr:02X}", offset=0, length=1))
    fields.append(DecodedField(name="dlci", value=dlci, offset=0, length=1))
    fields.append(DecodedField(name="server_channel", value=server_channel, offset=0, length=1))
    fields.append(DecodedField(name="c/r", value=cr, offset=0, length=1))

    # Control byte
    ctrl = data[1]
    pf = (ctrl >> 4) & 0x01  # Poll/Final bit
    frame_type_val = ctrl & ~0x10  # mask out P/F bit
    frame_type = FRAME_TYPES.get(frame_type_val, f"0x{ctrl:02X}")

    fields.append(DecodedField(name="control", value=f"0x{ctrl:02X}", offset=1, length=1))
    fields.append(DecodedField(name="frame_type", value=frame_type, offset=1, length=1))
    fields.append(DecodedField(name="p/f", value=pf, offset=1, length=1))

    # Length
    len_byte = data[2]
    ea_len = len_byte & 0x01
    if ea_len:
        # 7-bit length
        info_len = len_byte >> 1
        info_offset = 3
    else:
        # 15-bit length
        if len(data) < 4:
            return DecodedLayer(
                protocol="RFCOMM",
                summary=f"{frame_type} DLCI={dlci} (truncated length)",
                fields=fields,
            )
        info_len = (len_byte >> 1) | (data[3] << 7)
        info_offset = 4

    fields.append(DecodedField(name="length", value=info_len, offset=2, length=info_offset - 2))

    # Build summary
    if dlci == 0:
        # Multiplexer control channel
        summary = _decode_mux(data[info_offset:info_offset + info_len], fields)
        if not summary:
            summary = f"{frame_type} MUX len={info_len}"
    else:
        summary = f"{frame_type} DLCI={dlci} ch={server_channel} len={info_len}"

    # Credits (for UIH with credit-based flow control)
    if frame_type == "UIH" and pf and dlci > 0:
        if info_offset < len(data):
            credits = data[info_offset]
            fields.append(DecodedField(name="credits", value=credits))
            summary += f" credits={credits}"

    return DecodedLayer(
        protocol="RFCOMM",
        summary=summary,
        fields=fields,
        payload_offset=info_offset,
        payload=data[info_offset:info_offset + info_len] if info_offset + info_len <= len(data) else b"",
    )


def _decode_mux(data: bytes, fields: list[DecodedField]) -> Optional[str]:
    """Decode multiplexer command on DLCI 0."""
    if len(data) < 2:
        return None

    cmd_type = data[0]
    cr = (cmd_type >> 1) & 0x01
    cmd_id = cmd_type & ~0x03  # mask EA and C/R
    cmd_name = MUX_CMDS.get(cmd_id, f"MUX_0x{cmd_id:02X}")

    length = data[1] >> 1

    fields.append(DecodedField(name="mux_cmd", value=cmd_name))
    fields.append(DecodedField(name="mux_cr", value="CMD" if cr else "RSP"))

    if cmd_id == 0x38 and length >= 2:
        # MSC - Modem Status Command
        dlci = data[2] >> 2
        if length >= 3:
            signals = data[3]
            sig_names = [n for bit, n in MODEM_SIGNALS.items() if signals & bit]
            fields.append(DecodedField(name="msc_dlci", value=dlci))
            fields.append(DecodedField(name="msc_signals", value=",".join(sig_names) if sig_names else "none"))
            return f"MSC {'CMD' if cr else 'RSP'} DLCI={dlci} signals={','.join(sig_names)}"
        return f"MSC {'CMD' if cr else 'RSP'} DLCI={dlci}"

    elif cmd_id == 0x20 and length >= 8:
        # PN - Parameter Negotiation
        dlci = data[2] & 0x3F
        cl = data[3] & 0x0F
        priority = data[4]
        mtu = struct.unpack("<H", data[6:8])[0] if len(data) >= 8 else 0
        fields.append(DecodedField(name="pn_dlci", value=dlci))
        fields.append(DecodedField(name="pn_mtu", value=mtu))
        fields.append(DecodedField(name="pn_priority", value=priority))
        return f"PN {'CMD' if cr else 'RSP'} DLCI={dlci} MTU={mtu}"

    return f"{cmd_name} {'CMD' if cr else 'RSP'} len={length}"
