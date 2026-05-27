"""
AVDTP (Audio/Video Distribution Transport Protocol) and A2DP decoder.

AVDTP signaling header:
  Byte 0: Transaction_Label(4 bits) | Packet_Type(2 bits) | Message_Type(2 bits)
  Byte 1 (single packet): RFA(2 bits) | Signal_Identifier(6 bits)

Includes codec capability parsing for: SBC, AAC, LDAC, LHDC, aptX family.
"""

from __future__ import annotations

import struct
from typing import Optional

from .models import DecodedField, DecodedLayer

# ─── AVDTP Signal Identifiers ───
AVDTP_SIGS = {
    0x01: "DISCOVER",
    0x02: "GET_CAPABILITIES",
    0x03: "SET_CONFIGURATION",
    0x04: "GET_CONFIGURATION",
    0x05: "RECONFIGURE",
    0x06: "OPEN",
    0x07: "START",
    0x08: "CLOSE",
    0x09: "SUSPEND",
    0x0A: "ABORT",
    0x0B: "SECURITY_CONTROL",
    0x0C: "GET_ALL_CAPABILITIES",
    0x0D: "DELAY_REPORT",
}

# ─── AVDTP Message Types ───
AVDTP_MSG_TYPES = {
    0: "CMD",
    1: "GEN_REJECT",
    2: "RSP_ACCEPT",
    3: "RSP_REJECT",
}

# ─── AVDTP Packet Types ───
AVDTP_PKT_TYPES = {
    0: "Single",
    1: "Start",
    2: "Continue",
    3: "End",
}

# ─── Service Category IDs ───
AVDTP_CATEGORIES = {
    0x01: "MEDIA_TRANSPORT",
    0x02: "REPORTING",
    0x03: "RECOVERY",
    0x04: "CONTENT_PROTECTION",
    0x05: "HEADER_COMPRESSION",
    0x06: "MULTIPLEXING",
    0x07: "MEDIA_CODEC",
    0x08: "DELAY_REPORTING",
}

# ─── A2DP Codec Types ───
A2DP_CODECS = {
    0x00: "SBC",
    0x01: "MPEG-1,2",
    0x02: "AAC",
    0x04: "ATRAC",
    0xFF: "Vendor",
}

# ─── Known Vendor Codecs (vendor_id, codec_id) → name ───
VENDOR_CODECS = {
    (0x0000004F, 0x0001): "aptX",
    (0x000000D7, 0x0024): "aptX-HD",
    (0x0000012D, 0x00AA): "LDAC",
    (0x0000053A, 0x4C32): "LHDC2.0",
    (0x0000053A, 0x4C33): "LHDC3.0/4.0",
    (0x0000053A, 0x4C35): "LHDC-V",
    (0x0000053A, 0x4C48): "LHDC",
    (0x0000000A, 0x0001): "Samsung-SSC",
    (0x00000075, 0x0102): "aptX-Adaptive",
    (0x00000075, 0x0103): "aptX-Lossless",
}

# ─── SBC Configuration Tables ───
SBC_SAMPLE_FREQS = {0x80: "16000", 0x40: "32000", 0x20: "44100", 0x10: "48000"}
SBC_CHANNELS = {0x08: "Mono", 0x04: "DualCh", 0x02: "Stereo", 0x01: "Joint"}
SBC_BLOCKS = {0x80: "4", 0x40: "8", 0x20: "12", 0x10: "16"}
SBC_SUBBANDS = {0x08: "4", 0x04: "8"}
SBC_ALLOC = {0x02: "SNR", 0x01: "Loudness"}

# ─── AAC Configuration Tables ───
AAC_OBJ_TYPES = {0x80: "MPEG2-LC", 0x40: "MPEG4-LC", 0x20: "MPEG4-LTP", 0x10: "MPEG4-Scalable"}
AAC_SAMPLE_FREQS = {
    0x8000: "8000", 0x4000: "11025", 0x2000: "12000", 0x1000: "16000",
    0x0800: "22050", 0x0400: "24000", 0x0200: "32000", 0x0100: "44100",
    0x0080: "48000", 0x0040: "64000", 0x0020: "88200", 0x0010: "96000",
}

# ─── LHDC Bitrate Tables ───
LHDC_MAX_BITRATE = {0b00: "900kbps", 0b01: "500kbps", 0b10: "400kbps", 0b11: "Reserved"}
LHDC_MIN_BITRATE_V4 = {0b1: "320kbps", 0b0: "default"}
LHDCV_MAX_BITRATE = {0b00: "NoLimit", 0b01: "400kbps", 0b10: "600kbps", 0b11: "900kbps"}
LHDCV_MIN_BITRATE = {0b00: "NoLimit", 0b01: "128kbps", 0b10: "256kbps", 0b11: "400kbps"}
LHDCV_VERSION = {0b0001: "V5.0", 0b0010: "V5.1", 0b0100: "V5.2", 0b1000: "V5.3"}

# Content Protection types
CP_TYPES = {0x01: "DTCP", 0x02: "SCMS-T"}


def parse_sbc_config(data: bytes) -> str:
    """Parse SBC codec specific information element."""
    if len(data) < 4:
        return data.hex() if data else ""
    parts = []
    # Byte 0: sampling frequency (upper nibble) + channel mode (lower nibble)
    freq_byte = data[0] & 0xF0
    for mask, val in SBC_SAMPLE_FREQS.items():
        if freq_byte & mask:
            parts.append(f"{val}Hz")
            break
    ch_byte = data[0] & 0x0F
    for mask, val in SBC_CHANNELS.items():
        if ch_byte & mask:
            parts.append(val)
            break
    # Byte 1: block length (upper nibble) + subbands (bits 3-2) + alloc (bits 1-0)
    block_byte = data[1] & 0xF0
    for mask, val in SBC_BLOCKS.items():
        if block_byte & mask:
            parts.append(f"blk={val}")
            break
    sub_byte = data[1] & 0x0C
    for mask, val in SBC_SUBBANDS.items():
        if sub_byte & mask:
            parts.append(f"sub={val}")
            break
    alloc_byte = data[1] & 0x03
    for mask, val in SBC_ALLOC.items():
        if alloc_byte & mask:
            parts.append(val)
            break
    # Bytes 2-3: min/max bitpool
    parts.append(f"bitpool={data[2]}-{data[3]}")
    return " ".join(parts)


def parse_aac_config(data: bytes) -> str:
    """Parse AAC codec specific information element."""
    if len(data) < 6:
        return data.hex() if data else ""
    parts = []
    # Object type (byte 0)
    for mask, val in AAC_OBJ_TYPES.items():
        if data[0] & mask:
            parts.append(val)
            break
    # Sample frequency (byte 1 + upper nibble of byte 2)
    freq_bits = (data[1] << 4) | ((data[2] >> 4) & 0x0F)
    for mask, val in AAC_SAMPLE_FREQS.items():
        if freq_bits & mask:
            parts.append(f"{val}Hz")
            break
    # Channels (bits 3-2 of byte 2)
    ch = (data[2] >> 2) & 0x03
    if ch == 0x02:
        parts.append("Stereo")
    elif ch == 0x01:
        parts.append("Mono")
    # VBR flag + bitrate
    vbr = (data[3] >> 7) & 0x01
    bitrate = ((data[3] & 0x7F) << 16) | (data[4] << 8) | data[5]
    if vbr:
        parts.append("VBR")
    if bitrate > 0:
        parts.append(f"{bitrate // 1000}kbps")
    return " ".join(parts)


def parse_ldac_config(data: bytes) -> str:
    """Parse LDAC codec specific information."""
    if len(data) < 2:
        return f"LDAC [{data.hex()}]" if data else "LDAC"
    parts = ["LDAC"]
    # LDAC specific: sampling rate + channel mode
    sr = data[0]
    freqs = []
    if sr & 0x20:
        freqs.append("44.1K")
    if sr & 0x10:
        freqs.append("48K")
    if sr & 0x08:
        freqs.append("88.2K")
    if sr & 0x04:
        freqs.append("96K")
    if freqs:
        parts.append("/".join(freqs))
    ch = data[1]
    chs = []
    if ch & 0x04:
        chs.append("Mono")
    if ch & 0x02:
        chs.append("DualCh")
    if ch & 0x01:
        chs.append("Stereo")
    if chs:
        parts.append("/".join(chs))
    return " ".join(parts)


def parse_lhdc_v234_config(codec_id: int, data: bytes) -> str:
    """Parse LHDC 2.0/3.0/4.0 codec specific info."""
    parts = []
    if codec_id == 0x4C32:
        parts.append("LHDC2.0")
    else:
        parts.append("LHDC3.0/4.0")

    if len(data) < 2:
        return " ".join(parts)

    # Octet 6 (data[0]): LHDC-AR|JAS|16bit|24bit|44.1K|48K|Rsvd|96K
    b6 = data[0]
    freqs = []
    if b6 & 0x08:
        freqs.append("44.1K")
    if b6 & 0x04:
        freqs.append("48K")
    if b6 & 0x01:
        freqs.append("96K")
    bits = []
    if b6 & 0x20:
        bits.append("16bit")
    if b6 & 0x10:
        bits.append("24bit")
    features = []
    if b6 & 0x80:
        features.append("AR")
    if b6 & 0x40:
        features.append("JAS")

    if freqs:
        parts.append("/".join(freqs))
    if bits:
        parts.append("/".join(bits))

    # Octet 7 (data[1]): LLAC|LHDC-LL|MaxBitrate(2)|VersionNumber(4)
    b7 = data[1]
    if b7 & 0x80:
        features.append("LLAC")
    if b7 & 0x40:
        features.append("LL")
    max_br = (b7 >> 4) & 0x03
    parts.append(f"max={LHDC_MAX_BITRATE.get(max_br, '?')}")
    version = b7 & 0x0F
    if version == 1:
        parts.append("ver=2.0")

    # Octet 8 (data[2], V4 only)
    if len(data) >= 3:
        b8 = data[2]
        if b8 & 0x80:
            features.append("V4.0")
        if b8 & 0x40:
            features.append("LARC")
        min_br = (b8 >> 4) & 0x03
        if min_br:
            parts.append("min=320kbps")
        if b8 & 0x08:
            features.append("3rdParty")
        comp_fmt = b8 & 0x07
        if comp_fmt == 1:
            features.append("SplitTWS")
        elif comp_fmt == 2:
            features.append("SplitPreLR")

    if features:
        parts.append(f"[{','.join(features)}]")
    return " ".join(parts)


def parse_lhdc_v_config(data: bytes) -> str:
    """Parse LHDC-V (V5.x) codec specific info."""
    parts = ["LHDC-V"]

    if len(data) < 3:
        if data:
            parts.append(f"[{data.hex()}]")
        return " ".join(parts)

    # Octet 6 (data[0]): Rsvd|Rsvd|44.1K|48K|Rsvd|96K|Rsvd|192K
    b6 = data[0]
    freqs = []
    if b6 & 0x20:
        freqs.append("44.1K")
    if b6 & 0x10:
        freqs.append("48K")
    if b6 & 0x04:
        freqs.append("96K")
    if b6 & 0x01:
        freqs.append("192K")
    if freqs:
        parts.append("/".join(freqs))

    # Octet 7 (data[1]): MinBitrate(2)|MaxBitrate(2)|Rsvd|16bit|24bit|32bit
    b7 = data[1]
    min_br = (b7 >> 6) & 0x03
    max_br = (b7 >> 4) & 0x03
    parts.append(f"max={LHDCV_MAX_BITRATE.get(max_br, '?')}")
    parts.append(f"min={LHDCV_MIN_BITRATE.get(min_br, '?')}")
    bits = []
    if b7 & 0x04:
        bits.append("16bit")
    if b7 & 0x02:
        bits.append("24bit")
    if b7 & 0x01:
        bits.append("32bit")
    if bits:
        parts.append("/".join(bits))

    # Octet 8 (data[2]): Rsvd|Rsvd|Rsvd|5ms|VersionNumber(4)
    b8 = data[2]
    frame_5ms = (b8 >> 4) & 0x01
    if frame_5ms:
        parts.append("5ms")
    version = b8 & 0x0F
    ver_name = LHDCV_VERSION.get(version, f"v?({version})")
    parts.append(ver_name)

    # Octet 9 (data[3]): Lossless|LL|Rsvd|Rsvd|Rsvd|Meta|JAS|AR
    features = []
    if len(data) >= 4:
        b9 = data[3]
        if b9 & 0x80:
            features.append("Lossless")
        if b9 & 0x40:
            features.append("LL")
        if b9 & 0x04:
            features.append("Meta")
        if b9 & 0x02:
            features.append("JAS")
        if b9 & 0x01:
            features.append("AR")

    if features:
        parts.append(f"[{','.join(features)}]")
    return " ".join(parts)


def parse_vendor_config(data: bytes) -> str:
    """Parse Vendor-specific codec info (vendor_id=4bytes, codec_id=2bytes + specific)."""
    if len(data) < 6:
        return data.hex() if data else ""
    vendor_id = struct.unpack("<I", data[0:4])[0]
    codec_id = struct.unpack("<H", data[4:6])[0]
    codec_specific = data[6:]

    # LHDC family (Savitech, vendor_id=0x053A)
    if vendor_id == 0x0000053A:
        if codec_id in (0x4C32, 0x4C33):
            return parse_lhdc_v234_config(codec_id, codec_specific)
        elif codec_id == 0x4C35:
            return parse_lhdc_v_config(codec_specific)

    # LDAC (Sony, vendor_id=0x012D)
    if vendor_id == 0x0000012D and codec_id == 0x00AA:
        return parse_ldac_config(codec_specific)

    # General vendor codec
    name = VENDOR_CODECS.get(
        (vendor_id, codec_id), f"Vendor(0x{vendor_id:08X}:0x{codec_id:04X})"
    )
    if codec_specific:
        return f"{name} [{codec_specific.hex()}]"
    return name


def parse_codec_capability(media_type: int, codec_type: int, codec_data: bytes) -> str:
    """Parse a media codec capability/configuration element."""
    if codec_type == 0x00:  # SBC
        detail = parse_sbc_config(codec_data)
        return f"SBC {detail}"
    elif codec_type == 0x02:  # AAC
        detail = parse_aac_config(codec_data)
        return f"AAC {detail}"
    elif codec_type == 0xFF:  # Vendor
        return parse_vendor_config(codec_data)
    else:
        codec_name = A2DP_CODECS.get(codec_type, f"0x{codec_type:02X}")
        return f"{codec_name} [{codec_data.hex() if codec_data else ''}]"


def parse_capabilities(data: bytes) -> list[str]:
    """
    Parse AVDTP capabilities list (sequence of Service Capability elements).
    Returns a list of human-readable capability strings.
    """
    caps = []
    i = 0
    while i + 1 < len(data):
        cat_id = data[i]
        cat_len = data[i + 1]
        cat_data = data[i + 2 : i + 2 + cat_len]

        if cat_id == 0x07 and cat_len >= 2:
            # MEDIA_CODEC
            media_type = (cat_data[0] >> 4) & 0x0F
            codec_type = cat_data[1]
            codec_data = cat_data[2:]
            codec_info = parse_codec_capability(media_type, codec_type, codec_data)
            caps.append(f"Codec={codec_info}")
        elif cat_id == 0x04 and cat_len >= 2:
            # CONTENT_PROTECTION
            cp_type = struct.unpack("<H", cat_data[0:2])[0]
            cp_name = CP_TYPES.get(cp_type, f"0x{cp_type:04X}")
            caps.append(f"CP={cp_name}")
        elif cat_id == 0x08:
            # DELAY_REPORTING
            caps.append("DelayReport")
        elif cat_id == 0x01:
            # MEDIA_TRANSPORT
            caps.append("MediaTransport")
        else:
            cat_name = AVDTP_CATEGORIES.get(cat_id, f"0x{cat_id:02X}")
            caps.append(cat_name)

        i += 2 + cat_len
    return caps


def decode(payload: bytes) -> DecodedLayer:
    """
    Decode AVDTP signaling packet.

    Args:
        payload: L2CAP payload for an AVDTP signaling channel

    Returns:
        DecodedLayer with AVDTP decode information
    """
    if len(payload) < 2:
        return DecodedLayer(protocol="AVDTP", summary="(truncated)", payload=b"")

    # AVDTP header byte 0
    hdr0 = payload[0]
    trans_label = (hdr0 >> 4) & 0x0F
    pkt_type = (hdr0 >> 2) & 0x03
    msg_type = hdr0 & 0x03

    fields = [
        DecodedField("transaction_label", trans_label),
        DecodedField("packet_type", AVDTP_PKT_TYPES.get(pkt_type, str(pkt_type))),
        DecodedField("message_type", AVDTP_MSG_TYPES.get(msg_type, str(msg_type))),
    ]

    # Signal ID (only in single or start packets)
    sig_id = 0
    if pkt_type == 0:  # Single packet
        if len(payload) < 2:
            return DecodedLayer(protocol="AVDTP", summary="(truncated)", fields=fields, payload=b"")
        sig_id = payload[1] & 0x3F
    elif pkt_type == 1:  # Start packet
        if len(payload) < 3:
            return DecodedLayer(protocol="AVDTP", summary="(truncated)", fields=fields, payload=b"")
        # num_signaling_packets = payload[1]
        sig_id = payload[2] & 0x3F

    sig_name = AVDTP_SIGS.get(sig_id, f"SIG_0x{sig_id:02X}")
    msg_name = AVDTP_MSG_TYPES.get(msg_type, str(msg_type))

    fields.append(DecodedField("signal_id", f"0x{sig_id:02X}"))
    fields.append(DecodedField("signal_name", sig_name))

    summary = f"{sig_name} {msg_name} label={trans_label}"

    # Decode based on signal + message type
    if sig_id in (0x06, 0x07, 0x08, 0x09, 0x0A) and msg_type == 0 and len(payload) >= 3:
        # OPEN/START/CLOSE/SUSPEND/ABORT CMD: SEID
        seid = (payload[2] >> 2) & 0x3F
        fields.append(DecodedField("acp_seid", seid))
        summary += f" SEID={seid}"

    elif sig_id == 0x03 and msg_type == 0 and len(payload) > 4:
        # SET_CONFIGURATION CMD: ACP_SEID(1) + INT_SEID(1) + capabilities
        acp_seid = (payload[2] >> 2) & 0x3F
        int_seid = (payload[3] >> 2) & 0x3F
        fields.append(DecodedField("acp_seid", acp_seid))
        fields.append(DecodedField("int_seid", int_seid))
        summary += f" ACP={acp_seid} INT={int_seid}"
        cap_data = payload[4:]
        caps = parse_capabilities(cap_data)
        if caps:
            summary += f" [{', '.join(caps)}]"

    elif sig_id == 0x05 and msg_type == 0 and len(payload) > 3:
        # RECONFIGURE CMD: ACP_SEID(1) + capabilities
        acp_seid = (payload[2] >> 2) & 0x3F
        fields.append(DecodedField("acp_seid", acp_seid))
        summary += f" SEID={acp_seid}"
        cap_data = payload[3:]
        caps = parse_capabilities(cap_data)
        if caps:
            summary += f" [{', '.join(caps)}]"

    elif sig_id in (0x02, 0x0C) and msg_type == 2 and len(payload) > 2:
        # GET_CAPABILITIES / GET_ALL_CAPABILITIES RSP_ACCEPT: capabilities
        cap_data = payload[2:]
        caps = parse_capabilities(cap_data)
        if caps:
            summary += f" [{', '.join(caps)}]"

    elif sig_id == 0x01 and msg_type == 2 and len(payload) > 2:
        # DISCOVER RSP_ACCEPT: SEID info elements (2 bytes each)
        seids = []
        i = 2
        while i + 1 < len(payload):
            seid = (payload[i] >> 2) & 0x3F
            in_use = (payload[i] >> 1) & 0x01
            media_type = (payload[i + 1] >> 4) & 0x0F
            tsep = (payload[i + 1] >> 3) & 0x01
            media_names = {0: "Audio", 1: "Video", 2: "Multimedia"}
            tsep_names = {0: "SRC", 1: "SNK"}
            seid_str = "{}({}/{}{})" .format(
                seid,
                media_names.get(media_type, "?"),
                tsep_names.get(tsep, "?"),
                ",InUse" if in_use else "",
            )
            seids.append(seid_str)
            fields.append(DecodedField(f"seid_{seid}", seid_str))
            i += 2
        if seids:
            summary += f" [{' '.join(seids)}]"

    elif sig_id == 0x0D and msg_type == 0 and len(payload) >= 5:
        # DELAY_REPORT CMD: SEID + delay(2 bytes, unit = 1/10 ms)
        seid = (payload[2] >> 2) & 0x3F
        delay = struct.unpack(">H", payload[3:5])[0]
        fields.append(DecodedField("acp_seid", seid))
        fields.append(DecodedField("delay_ms", delay / 10.0))
        summary += f" SEID={seid} delay={delay / 10.0:.1f}ms"

    return DecodedLayer(
        protocol="AVDTP",
        summary=summary,
        fields=fields,
        payload_offset=len(payload),
        payload=b"",
    )
