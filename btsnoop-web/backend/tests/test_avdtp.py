"""
Tests for AVDTP layer decoding (parser/avdtp.py).

Tests:
  - DISCOVER command/response
  - SET_CONFIGURATION with SBC codec
  - Codec capability parsing (SBC parameters)
"""

from __future__ import annotations

import struct

import pytest

from parser.avdtp import (
    decode,
    parse_sbc_config,
    parse_capabilities,
    parse_codec_capability,
    AVDTP_SIGS,
    AVDTP_MSG_TYPES,
)
from parser.models import DecodedLayer


def build_avdtp_single(
    trans_label: int, msg_type: int, sig_id: int, payload: bytes = b""
) -> bytes:
    """
    Build a single-packet AVDTP signaling frame.

    Header byte 0: trans_label(4) | packet_type=0(2) | msg_type(2)
    Header byte 1: RFA(2) | signal_id(6)
    """
    hdr0 = ((trans_label & 0x0F) << 4) | ((0 & 0x03) << 2) | (msg_type & 0x03)
    hdr1 = sig_id & 0x3F
    return bytes([hdr0, hdr1]) + payload


class TestAvdtpDiscover:
    """Tests for AVDTP DISCOVER signal."""

    def test_discover_command(self):
        """Decode DISCOVER command (sig_id=0x01, msg_type=CMD=0)."""
        pkt = build_avdtp_single(trans_label=1, msg_type=0, sig_id=0x01)
        layer = decode(pkt)
        assert layer.protocol == "AVDTP"
        assert "DISCOVER" in layer.summary
        assert "CMD" in layer.summary

    def test_discover_response_single_seid(self):
        """Decode DISCOVER response with one SEID info element."""
        # SEID info: 2 bytes per SEID
        # Byte 0: SEID(6 bits, shifted left 2) | in_use(1) | RFA(1)
        # Byte 1: media_type(4 bits, upper nibble) | tsep(1) | RFA(3)
        seid = 1
        in_use = 0
        media_type = 0  # Audio
        tsep = 0  # SRC
        b0 = (seid << 2) | (in_use << 1) | 0
        b1 = (media_type << 4) | (tsep << 3) | 0
        seid_payload = bytes([b0, b1])

        pkt = build_avdtp_single(
            trans_label=1, msg_type=2, sig_id=0x01, payload=seid_payload
        )
        layer = decode(pkt)
        assert "DISCOVER" in layer.summary
        assert "RSP_ACCEPT" in layer.summary
        assert "1(Audio/SRC)" in layer.summary

    def test_discover_response_multiple_seids(self):
        """Decode DISCOVER response with multiple SEID info elements."""
        seids_payload = b""
        for seid, media, tsep, in_use in [(1, 0, 0, 0), (2, 0, 1, 0)]:
            b0 = (seid << 2) | (in_use << 1)
            b1 = (media << 4) | (tsep << 3)
            seids_payload += bytes([b0, b1])

        pkt = build_avdtp_single(
            trans_label=2, msg_type=2, sig_id=0x01, payload=seids_payload
        )
        layer = decode(pkt)
        assert "1(Audio/SRC)" in layer.summary
        assert "2(Audio/SNK)" in layer.summary


class TestAvdtpSetConfiguration:
    """Tests for AVDTP SET_CONFIGURATION with codec caps."""

    def test_set_config_sbc(self):
        """Decode SET_CONFIGURATION CMD with SBC codec capability."""
        # Payload: ACP_SEID(1) + INT_SEID(1) + capabilities
        acp_seid = 1
        int_seid = 2

        # Build SBC codec capability:
        # Category=MEDIA_CODEC(0x07), length=6
        # media_type_codec_type: (Audio<<4)|SBC = 0x00
        # SBC specific (4 bytes): freq|ch, blocks|subbands|alloc, min_bitpool, max_bitpool
        sbc_config = bytes([
            0x21,  # 44100Hz (0x20) | Joint Stereo (0x01)
            0x15,  # 16 blocks (0x10) | 8 subbands (0x04) | Loudness (0x01)
            2,     # min bitpool
            53,    # max bitpool
        ])
        codec_cap = bytes([0x07, 2 + len(sbc_config), 0x00, 0x00]) + sbc_config

        # Also add MEDIA_TRANSPORT capability
        media_transport_cap = bytes([0x01, 0x00])

        capabilities = media_transport_cap + codec_cap
        payload = bytes([(acp_seid << 2), (int_seid << 2)]) + capabilities

        pkt = build_avdtp_single(
            trans_label=3, msg_type=0, sig_id=0x03, payload=payload
        )
        layer = decode(pkt)
        assert "SET_CONFIGURATION" in layer.summary
        assert "CMD" in layer.summary
        assert "ACP=1" in layer.summary
        assert "INT=2" in layer.summary
        assert "SBC" in layer.summary

    def test_set_config_with_delay_reporting(self):
        """Decode SET_CONFIGURATION with DELAY_REPORTING capability."""
        acp_seid = 1
        int_seid = 2

        # MEDIA_TRANSPORT + DELAY_REPORTING
        capabilities = bytes([0x01, 0x00, 0x08, 0x00])
        payload = bytes([(acp_seid << 2), (int_seid << 2)]) + capabilities

        pkt = build_avdtp_single(
            trans_label=3, msg_type=0, sig_id=0x03, payload=payload
        )
        layer = decode(pkt)
        assert "DelayReport" in layer.summary


class TestSbcConfigParsing:
    """Tests for SBC codec configuration parsing."""

    def test_sbc_44100_joint_stereo(self):
        """Parse SBC config: 44100Hz, Joint Stereo, 16 blocks, 8 subbands, Loudness."""
        data = bytes([
            0x21,  # 44100Hz (0x20) | Joint (0x01)
            0x15,  # 16 blocks (0x10) | 8 subbands (0x04) | Loudness (0x01)
            2,     # min bitpool
            53,    # max bitpool
        ])
        result = parse_sbc_config(data)
        assert "44100" in result
        assert "Joint" in result
        assert "16" in result  # blocks
        assert "8" in result   # subbands
        assert "Loudness" in result
        assert "2-53" in result  # bitpool range

    def test_sbc_48000_stereo(self):
        """Parse SBC config: 48000Hz, Stereo."""
        data = bytes([
            0x12,  # 48000Hz (0x10) | Stereo (0x02)
            0x15,  # 16 blocks (0x10) | 8 subbands (0x04) | Loudness (0x01)
            2,
            51,
        ])
        result = parse_sbc_config(data)
        assert "48000" in result
        assert "Stereo" in result
        assert "2-51" in result

    def test_sbc_short_data(self):
        """Handle short SBC config data."""
        result = parse_sbc_config(b"\x21\x15")
        # Should return hex or partial parse, not crash
        assert isinstance(result, str)

    def test_sbc_empty_data(self):
        """Handle empty SBC config data."""
        result = parse_sbc_config(b"")
        assert result == ""


class TestCapabilitiesParsing:
    """Tests for AVDTP capabilities list parsing."""

    def test_media_transport_only(self):
        """Parse capabilities with only MEDIA_TRANSPORT."""
        data = bytes([0x01, 0x00])  # cat_id=0x01, len=0
        caps = parse_capabilities(data)
        assert "MediaTransport" in caps

    def test_codec_sbc(self):
        """Parse capabilities with MEDIA_CODEC (SBC)."""
        sbc_config = bytes([0x21, 0x15, 2, 53])
        # category=0x07, length=2+4=6, media_type=0x00, codec_type=0x00 (SBC)
        data = bytes([0x07, 2 + len(sbc_config), 0x00, 0x00]) + sbc_config
        caps = parse_capabilities(data)
        assert len(caps) == 1
        assert "Codec=" in caps[0]
        assert "SBC" in caps[0]

    def test_delay_reporting(self):
        """Parse capabilities with DELAY_REPORTING."""
        data = bytes([0x08, 0x00])
        caps = parse_capabilities(data)
        assert "DelayReport" in caps

    def test_content_protection_scmst(self):
        """Parse capabilities with CONTENT_PROTECTION (SCMS-T)."""
        # category=0x04, length=2, cp_type=0x0002 (SCMS-T, LE)
        data = bytes([0x04, 0x02, 0x02, 0x00])
        caps = parse_capabilities(data)
        assert len(caps) == 1
        assert "CP=SCMS-T" in caps[0]

    def test_multiple_capabilities(self):
        """Parse a list with multiple capabilities."""
        data = bytes([
            0x01, 0x00,           # MEDIA_TRANSPORT
            0x08, 0x00,           # DELAY_REPORTING
            0x07, 0x06, 0x00, 0x00, 0x21, 0x15, 0x02, 0x35,  # MEDIA_CODEC (SBC)
        ])
        caps = parse_capabilities(data)
        assert len(caps) == 3
        assert "MediaTransport" in caps[0]
        assert "DelayReport" in caps[1]
        assert "SBC" in caps[2]


class TestAvdtpMisc:
    """Miscellaneous AVDTP decode tests."""

    def test_open_command(self):
        """Decode OPEN command (sig_id=0x06)."""
        seid = 1
        payload = bytes([(seid << 2)])
        pkt = build_avdtp_single(trans_label=4, msg_type=0, sig_id=0x06, payload=payload)
        layer = decode(pkt)
        assert "OPEN" in layer.summary
        assert "SEID=1" in layer.summary

    def test_start_command(self):
        """Decode START command (sig_id=0x07)."""
        seid = 1
        payload = bytes([(seid << 2)])
        pkt = build_avdtp_single(trans_label=5, msg_type=0, sig_id=0x07, payload=payload)
        layer = decode(pkt)
        assert "START" in layer.summary

    def test_suspend_command(self):
        """Decode SUSPEND command (sig_id=0x09)."""
        seid = 2
        payload = bytes([(seid << 2)])
        pkt = build_avdtp_single(trans_label=6, msg_type=0, sig_id=0x09, payload=payload)
        layer = decode(pkt)
        assert "SUSPEND" in layer.summary
        assert "SEID=2" in layer.summary

    def test_delay_report_command(self):
        """Decode DELAY_REPORT command (sig_id=0x0D)."""
        seid = 1
        delay_100ms = 1000  # 100.0 ms in 1/10 ms units
        payload = bytes([(seid << 2)]) + struct.pack(">H", delay_100ms)
        pkt = build_avdtp_single(trans_label=7, msg_type=0, sig_id=0x0D, payload=payload)
        layer = decode(pkt)
        assert "DELAY_REPORT" in layer.summary
        assert "100.0" in layer.summary

    def test_truncated_avdtp(self):
        """Handle truncated AVDTP data."""
        layer = decode(b"\x00")
        assert "truncated" in layer.summary

    def test_rsp_accept_no_payload(self):
        """Decode a response accept for OPEN (no extra payload)."""
        pkt = build_avdtp_single(trans_label=4, msg_type=2, sig_id=0x06)
        layer = decode(pkt)
        assert "OPEN" in layer.summary
        assert "RSP_ACCEPT" in layer.summary

    def test_transaction_label_in_summary(self):
        """Verify transaction label appears in summary."""
        pkt = build_avdtp_single(trans_label=7, msg_type=0, sig_id=0x01)
        layer = decode(pkt)
        assert "label=7" in layer.summary
