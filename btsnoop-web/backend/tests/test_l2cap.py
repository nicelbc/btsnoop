"""
Tests for L2CAP layer decoding (parser/l2cap.py).

Tests:
  - Basic L2CAP header parsing
  - Signaling channel (CONN_REQ, CONN_RSP)
  - Fixed CID identification (ATT=0x0004, SMP=0x0006)
  - CID-to-PSM mapping updates
"""

from __future__ import annotations

import struct

import pytest

from parser.l2cap import (
    decode,
    decode_signaling,
    get_psm_name,
    get_cid_name,
    L2CAP_CIDS,
    L2CAP_PSMS,
)
from parser.models import SessionState, DecodedLayer

from .conftest import build_l2cap, build_l2cap_signaling


class TestL2capBasicHeader:
    """Tests for basic L2CAP header parsing."""

    def test_basic_header_parse(self, session_state):
        """Parse basic L2CAP header: length and CID."""
        payload = b"\x01\x02\x03\x04"
        data = build_l2cap(0x0040, payload)
        layer, upper_proto, upper_payload = decode(data, session_state)

        assert layer.protocol == "L2CAP"
        # Check length field
        length_field = next(f for f in layer.fields if f.name == "length")
        assert length_field.value == 4
        # Check CID field
        cid_field = next(f for f in layer.fields if f.name == "cid")
        assert cid_field.value == "0x0040"

    def test_truncated_header(self, session_state):
        """Handle truncated L2CAP data (<4 bytes)."""
        layer, proto, payload = decode(b"\x04\x00", session_state)
        assert "truncated" in layer.summary
        assert proto is None
        assert payload == b""

    def test_empty_payload(self, session_state):
        """Handle L2CAP frame with zero-length payload."""
        data = build_l2cap(0x0040, b"")
        layer, _, upper_payload = decode(data, session_state)
        assert layer.protocol == "L2CAP"
        assert upper_payload == b""


class TestFixedCids:
    """Tests for fixed CID identification."""

    def test_att_cid(self, session_state):
        """CID 0x0004 is identified as ATT."""
        att_payload = b"\x02\x17\x00"  # Exchange MTU Request
        data = build_l2cap(0x0004, att_payload)
        layer, upper_proto, upper_payload = decode(data, session_state)

        assert upper_proto == "ATT"
        assert upper_payload == att_payload
        # Check channel field
        channel_field = next(f for f in layer.fields if f.name == "channel")
        assert channel_field.value == "ATT"

    def test_smp_cid(self, session_state):
        """CID 0x0006 is identified as SMP."""
        smp_payload = b"\x01\x03\x00\x01\x10\x07\x07"  # Pairing Request
        data = build_l2cap(0x0006, smp_payload)
        layer, upper_proto, upper_payload = decode(data, session_state)

        assert upper_proto == "SMP"
        assert upper_payload == smp_payload

    def test_signaling_cid(self, session_state):
        """CID 0x0001 is identified as L2CAP Signaling."""
        sig_payload = build_l2cap_signaling(0x02, 0x01, b"\x19\x00\x40\x00")
        data = build_l2cap(0x0001, sig_payload)
        layer, upper_proto, upper_payload = decode(data, session_state)

        assert upper_proto == "L2CAP_SIG"
        assert upper_payload == sig_payload

    def test_le_signaling_cid(self, session_state):
        """CID 0x0005 is identified as LE L2CAP Signaling."""
        sig_payload = build_l2cap_signaling(0x12, 0x01, b"\x00" * 8)
        data = build_l2cap(0x0005, sig_payload)
        layer, upper_proto, upper_payload = decode(data, session_state)

        assert upper_proto == "LE_L2CAP_SIG"


class TestSignaling:
    """Tests for L2CAP Signaling channel decoding."""

    def test_conn_req(self, session_state):
        """Decode Connection Request (code=0x02)."""
        # sig_data: PSM(2 LE) + SCID(2 LE)
        psm = 0x0019  # AVDTP
        scid = 0x0040
        sig_data = struct.pack("<HH", psm, scid)
        payload = build_l2cap_signaling(0x02, 0x01, sig_data)

        layer = decode_signaling(payload, session_state)
        assert layer.protocol == "L2CAP_SIG"
        assert "CONN_REQ" in layer.summary
        assert "AVDTP" in layer.summary
        assert "0x0040" in layer.summary

        # Verify CID-PSM mapping was stored
        assert session_state.get_psm_for_cid(scid) == psm

    def test_conn_rsp_success(self, session_state):
        """Decode Connection Response (code=0x03) with success result."""
        # First set up the SCID->PSM mapping (as would happen with CONN_REQ)
        session_state.map_cid_to_psm(0x0040, 0x0019)

        # sig_data: DCID(2 LE) + SCID(2 LE) + result(2 LE) + status(2 LE)
        dcid = 0x0041
        scid = 0x0040
        sig_data = struct.pack("<HHHH", dcid, scid, 0x0000, 0x0000)
        payload = build_l2cap_signaling(0x03, 0x01, sig_data)

        layer = decode_signaling(payload, session_state)
        assert "CONN_RSP" in layer.summary
        assert "Success" in layer.summary
        assert "0x0041" in layer.summary

        # DCID should now also be mapped to AVDTP PSM
        assert session_state.get_psm_for_cid(dcid) == 0x0019

    def test_conn_rsp_rejected(self, session_state):
        """Decode Connection Response with PSM Not Supported."""
        sig_data = struct.pack("<HHHH", 0x0000, 0x0040, 0x0002, 0x0000)
        payload = build_l2cap_signaling(0x03, 0x01, sig_data)

        layer = decode_signaling(payload, session_state)
        assert "CONN_RSP" in layer.summary
        assert "PSM_Not_Supported" in layer.summary

    def test_config_req(self, session_state):
        """Decode Configuration Request (code=0x04)."""
        sig_data = struct.pack("<HH", 0x0041, 0x0000)  # DCID + flags
        payload = build_l2cap_signaling(0x04, 0x02, sig_data)

        layer = decode_signaling(payload, session_state)
        assert "CONFIG_REQ" in layer.summary
        assert "0x0041" in layer.summary

    def test_config_rsp(self, session_state):
        """Decode Configuration Response (code=0x05)."""
        sig_data = struct.pack("<HHH", 0x0040, 0x0000, 0x0000)  # SCID + flags + result
        payload = build_l2cap_signaling(0x05, 0x02, sig_data)

        layer = decode_signaling(payload, session_state)
        assert "CONFIG_RSP" in layer.summary
        assert "Success" in layer.summary

    def test_disconn_req(self, session_state):
        """Decode Disconnection Request (code=0x06)."""
        sig_data = struct.pack("<HH", 0x0041, 0x0040)  # DCID + SCID
        payload = build_l2cap_signaling(0x06, 0x03, sig_data)

        layer = decode_signaling(payload, session_state)
        assert "DISCONN_REQ" in layer.summary

    def test_info_req(self, session_state):
        """Decode Information Request (code=0x0A)."""
        sig_data = struct.pack("<H", 0x0002)  # Extended Features
        payload = build_l2cap_signaling(0x0A, 0x01, sig_data)

        layer = decode_signaling(payload, session_state)
        assert "INFO_REQ" in layer.summary
        assert "Extended_Features" in layer.summary

    def test_truncated_signaling(self, session_state):
        """Handle truncated signaling data."""
        layer = decode_signaling(b"\x02\x01", session_state)
        assert "truncated" in layer.summary


class TestCidToPsmMapping:
    """Tests for dynamic CID-to-PSM mapping."""

    def test_dynamic_cid_avdtp(self, session_state):
        """Dynamic CID mapped to AVDTP PSM produces AVDTP upper protocol."""
        session_state.map_cid_to_psm(0x0040, 0x0019)
        avdtp_payload = b"\x00\x01"  # minimal AVDTP
        data = build_l2cap(0x0040, avdtp_payload)
        layer, upper_proto, _ = decode(data, session_state)

        assert upper_proto == "AVDTP"

    def test_dynamic_cid_avctp(self, session_state):
        """Dynamic CID mapped to AVCTP PSM."""
        session_state.map_cid_to_psm(0x0042, 0x0017)
        data = build_l2cap(0x0042, b"\x00\x01\x02\x03")
        layer, upper_proto, _ = decode(data, session_state)

        assert upper_proto == "AVCTP"

    def test_dynamic_cid_sdp(self, session_state):
        """Dynamic CID mapped to SDP PSM."""
        session_state.map_cid_to_psm(0x0043, 0x0001)
        data = build_l2cap(0x0043, b"\x00\x01\x02\x03")
        layer, upper_proto, _ = decode(data, session_state)

        assert upper_proto == "SDP"

    def test_dynamic_cid_rfcomm(self, session_state):
        """Dynamic CID mapped to RFCOMM PSM."""
        session_state.map_cid_to_psm(0x0044, 0x0003)
        data = build_l2cap(0x0044, b"\x00\x01\x02\x03")
        layer, upper_proto, _ = decode(data, session_state)

        assert upper_proto == "RFCOMM"

    def test_unknown_dynamic_cid(self, session_state):
        """Dynamic CID with no PSM mapping."""
        data = build_l2cap(0x0050, b"\x01\x02\x03\x04")
        layer, upper_proto, _ = decode(data, session_state)

        assert upper_proto is None

    def test_psm_name_lookup(self):
        """Verify PSM name lookup for known values."""
        assert get_psm_name(0x0019) == "AVDTP"
        assert get_psm_name(0x0017) == "AVCTP"
        assert get_psm_name(0x0001) == "SDP"
        assert "0x" in get_psm_name(0x9999)  # unknown

    def test_cid_name_lookup(self):
        """Verify CID name lookup for known fixed CIDs."""
        assert get_cid_name(0x0001) == "L2CAP_SIG"
        assert get_cid_name(0x0004) == "ATT"
        assert get_cid_name(0x0006) == "SMP"
        assert "CID=" in get_cid_name(0x0099)  # unknown
