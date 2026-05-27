"""
HFP (Hands-Free Profile) decoder.

HFP runs over RFCOMM and uses AT commands for call control.
This decoder parses AT commands and responses in RFCOMM UIH payloads.
"""

from __future__ import annotations

from .models import DecodedField, DecodedLayer


# Common HFP AT commands
HFP_AT_COMMANDS = {
    "BRSF": "Supported Features",
    "CIND": "Indicator Status",
    "CMER": "Event Reporting",
    "CHLD": "Call Hold/Multiparty",
    "BIND": "HF Indicators",
    "BIEV": "HF Indicator Value",
    "COPS": "Operator Selection",
    "CLCC": "Current Calls List",
    "CLIP": "Calling Line ID",
    "CCWA": "Call Waiting",
    "CMEE": "Extended Error",
    "VGS": "Speaker Volume",
    "VGM": "Microphone Volume",
    "BVRA": "Voice Recognition",
    "NREC": "Noise Reduction/EC",
    "BINP": "Phone Number Input",
    "BTRH": "Response and Hold",
    "BIA": "Indicator Activation",
    "BCS": "Codec Selection",
    "BAC": "Available Codecs",
    "IPHONEACCEV": "iPhone Accessory",
    "XAPL": "Apple Extension",
    "XEVENT": "Extended Event",
    "ATD": "Dial",
    "ATA": "Answer",
    "CHUP": "Hang Up",
    "VTS": "DTMF",
}

# HFP codec IDs
HFP_CODECS = {
    1: "CVSD",
    2: "mSBC",
    3: "LC3-SWB",
}

# BRSF feature bits (AG side)
AG_FEATURES = {
    0: "3-Way",
    1: "EC/NR",
    2: "VoiceRecog",
    3: "InBandRing",
    4: "VoiceTag",
    5: "RejectCall",
    6: "EnhancedCallStatus",
    7: "EnhancedCallControl",
    8: "ExtendedError",
    9: "CodecNeg",
    10: "HF_Indicators",
    11: "eSCO_S4",
}

# BRSF feature bits (HF side)
HF_FEATURES = {
    0: "EC/NR",
    1: "3-Way",
    2: "CLI",
    3: "VoiceRecog",
    4: "RemoteVolume",
    5: "EnhancedCallStatus",
    6: "EnhancedCallControl",
    7: "CodecNeg",
    8: "HF_Indicators",
    9: "eSCO_S4",
}


def decode(data: bytes) -> DecodedLayer:
    """
    Decode HFP AT command/response from RFCOMM payload.

    Args:
        data: RFCOMM UIH information payload (text AT commands)

    Returns:
        DecodedLayer with HFP decode info
    """
    fields = []

    try:
        text = data.decode('utf-8', errors='replace').strip()
    except Exception:
        text = data.hex()

    if not text:
        return DecodedLayer(protocol="HFP", summary="(empty)", fields=fields)

    fields.append(DecodedField("raw_text", text, offset=0, length=len(data)))

    # Parse AT command or response
    if text.startswith("AT+"):
        return _decode_at_command(text, fields)
    elif text.startswith("AT"):
        return _decode_at_basic(text, fields)
    elif text.startswith("+"):
        return _decode_at_response(text, fields)
    elif text == "OK":
        fields.append(DecodedField("type", "Response"))
        return DecodedLayer(protocol="HFP", summary="OK", fields=fields)
    elif text == "ERROR":
        fields.append(DecodedField("type", "Error"))
        return DecodedLayer(protocol="HFP", summary="ERROR", fields=fields)
    elif text == "RING":
        fields.append(DecodedField("type", "Unsolicited"))
        return DecodedLayer(protocol="HFP", summary="RING (来电)", fields=fields)
    else:
        return DecodedLayer(protocol="HFP", summary=f"AT: {text[:60]}", fields=fields)


def _decode_at_command(text: str, fields: list[DecodedField]) -> DecodedLayer:
    """Decode AT+XXX command."""
    fields.append(DecodedField("type", "Command"))

    # AT+CMD=value or AT+CMD? or AT+CMD
    cmd_part = text[3:]  # remove "AT+"

    if "=" in cmd_part:
        cmd_name, value = cmd_part.split("=", 1)
        cmd_name = cmd_name.upper()
        desc = HFP_AT_COMMANDS.get(cmd_name, cmd_name)
        fields.append(DecodedField("command", cmd_name))
        fields.append(DecodedField("description", desc))
        fields.append(DecodedField("value", value))

        # Special decoding
        extra = _decode_special_cmd(cmd_name, value)
        if extra:
            fields.append(DecodedField("decoded", extra))
            return DecodedLayer(protocol="HFP", summary=f"AT+{cmd_name}={value} ({extra})", fields=fields)

        return DecodedLayer(protocol="HFP", summary=f"AT+{cmd_name}={value}", fields=fields)

    elif cmd_part.endswith("?"):
        cmd_name = cmd_part[:-1].upper()
        desc = HFP_AT_COMMANDS.get(cmd_name, cmd_name)
        fields.append(DecodedField("command", cmd_name))
        fields.append(DecodedField("description", desc))
        fields.append(DecodedField("query", True))
        return DecodedLayer(protocol="HFP", summary=f"AT+{cmd_name}? ({desc})", fields=fields)

    else:
        cmd_name = cmd_part.upper()
        desc = HFP_AT_COMMANDS.get(cmd_name, cmd_name)
        fields.append(DecodedField("command", cmd_name))
        fields.append(DecodedField("description", desc))
        return DecodedLayer(protocol="HFP", summary=f"AT+{cmd_name} ({desc})", fields=fields)


def _decode_at_basic(text: str, fields: list[DecodedField]) -> DecodedLayer:
    """Decode basic AT commands (ATD, ATA, etc.)."""
    fields.append(DecodedField("type", "Command"))
    cmd = text[2:]  # remove "AT"

    if cmd.startswith("D"):
        number = cmd[1:].rstrip(";")
        fields.append(DecodedField("command", "ATD"))
        fields.append(DecodedField("number", number))
        return DecodedLayer(protocol="HFP", summary=f"ATD{number} (拨号)", fields=fields)
    elif cmd == "A":
        fields.append(DecodedField("command", "ATA"))
        return DecodedLayer(protocol="HFP", summary="ATA (接听)", fields=fields)
    else:
        return DecodedLayer(protocol="HFP", summary=f"AT{cmd}", fields=fields)


def _decode_at_response(text: str, fields: list[DecodedField]) -> DecodedLayer:
    """Decode +XXX: response or unsolicited result."""
    fields.append(DecodedField("type", "Response"))

    if ":" in text:
        indicator, value = text.split(":", 1)
        indicator = indicator[1:].upper()  # remove leading '+'
        value = value.strip()
        desc = HFP_AT_COMMANDS.get(indicator, indicator)
        fields.append(DecodedField("indicator", indicator))
        fields.append(DecodedField("description", desc))
        fields.append(DecodedField("value", value))

        extra = _decode_special_cmd(indicator, value)
        if extra:
            fields.append(DecodedField("decoded", extra))
            return DecodedLayer(protocol="HFP", summary=f"+{indicator}: {value} ({extra})", fields=fields)

        return DecodedLayer(protocol="HFP", summary=f"+{indicator}: {value}", fields=fields)
    else:
        return DecodedLayer(protocol="HFP", summary=text, fields=fields)


def _decode_special_cmd(cmd: str, value: str) -> str:
    """Decode specific command values into human-readable strings."""
    if cmd == "BRSF":
        try:
            features_int = int(value)
            feats = []
            for bit, name in HF_FEATURES.items():
                if features_int & (1 << bit):
                    feats.append(name)
            if feats:
                return ",".join(feats)
        except ValueError:
            pass

    elif cmd == "BCS":
        try:
            codec_id = int(value)
            return HFP_CODECS.get(codec_id, f"codec_{codec_id}")
        except ValueError:
            pass

    elif cmd == "VGS" or cmd == "VGM":
        try:
            vol = int(value)
            return f"{vol}/15 ({int(vol/15*100)}%)"
        except ValueError:
            pass

    elif cmd == "CIND":
        if "," in value:
            return "indicators=" + value

    elif cmd == "BAC":
        try:
            codecs = [HFP_CODECS.get(int(c.strip()), c.strip()) for c in value.split(",")]
            return ",".join(codecs)
        except (ValueError, AttributeError):
            pass

    return ""
