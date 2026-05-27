"""
End-to-end integration tests.

These tests verify the FULL flow:
  1. Upload btsnoop file via HTTP
  2. Connect WebSocket to session
  3. Receive parsed packet data
  4. Request packet detail via WebSocket
  5. Verify static file serving doesn't break API/WS routes

These tests catch routing conflicts, middleware issues, and
serialization bugs that unit tests miss.
"""

from __future__ import annotations

import io
import json
import struct

import pytest
from fastapi.testclient import TestClient

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server import app
from tests.conftest import build_btsnoop_file, build_hci_command, build_hci_event


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_btsnoop_bytes():
    """Build a btsnoop file with multiple packet types."""
    reset_cmd = build_hci_command(0x0C03)
    cmd_complete = build_hci_event(0x0E, struct.pack("<BHB", 0x01, 0x0C03, 0x00))

    # ACL with L2CAP ATT Exchange MTU
    handle_flags = struct.pack("<H", 0x2001)  # handle=1, PB=10b
    att_payload = bytes([0x02]) + struct.pack("<H", 517)
    l2cap_hdr = struct.pack("<HH", len(att_payload), 0x0004)
    acl = bytes([0x02]) + handle_flags + struct.pack("<H", len(l2cap_hdr + att_payload)) + l2cap_hdr + att_payload

    records = [
        (reset_cmd, 0x00),       # sent command
        (cmd_complete, 0x01),    # received event
        (acl, 0x00),             # sent ACL/ATT
    ]
    return build_btsnoop_file(records)


class TestUploadAndWebSocket:
    """Test the complete upload → WebSocket → receive packets flow."""

    def test_upload_then_websocket_receives_packets(self, client, sample_btsnoop_bytes):
        """Upload file, connect WS, verify packets arrive."""
        # Step 1: Upload
        resp = client.post(
            "/api/upload",
            files={"file": ("test.btsnoop", io.BytesIO(sample_btsnoop_bytes), "application/octet-stream")},
        )
        assert resp.status_code == 200
        data = resp.json()
        session_id = data["session_id"]
        assert data["total_packets"] == 3

        # Step 2: Connect WebSocket
        with client.websocket_connect(f"/ws/{session_id}") as ws:
            # Step 3: Should receive packet_batch
            msg = ws.receive_json()
            assert msg["type"] == "packet_batch"
            assert len(msg["packets"]) == 3

            # Verify packet content
            pkt0 = msg["packets"][0]
            assert pkt0["protocol"] == "HCI_CMD"
            assert "Reset" in pkt0["summary"]
            assert pkt0["direction"] == "sent"
            assert pkt0["index"] == 0

            pkt1 = msg["packets"][1]
            assert pkt1["protocol"] == "HCI_EVT"
            assert pkt1["direction"] == "received"

            pkt2 = msg["packets"][2]
            assert pkt2["protocol"] == "ATT"
            assert pkt2["direction"] == "sent"

    def test_websocket_get_detail(self, client, sample_btsnoop_bytes):
        """Request packet detail via WebSocket."""
        # Upload
        resp = client.post(
            "/api/upload",
            files={"file": ("test.btsnoop", io.BytesIO(sample_btsnoop_bytes), "application/octet-stream")},
        )
        session_id = resp.json()["session_id"]

        # Connect and drain initial batch
        with client.websocket_connect(f"/ws/{session_id}") as ws:
            ws.receive_json()  # drain packet_batch

            # Request detail for packet 2 (ATT)
            ws.send_json({"action": "get_detail", "index": 2})
            msg = ws.receive_json()

            assert msg["type"] == "packet_detail"
            assert msg["packet"]["protocol"] == "ATT"
            assert "raw_hex" in msg
            assert len(msg["raw_hex"]) > 0
            assert msg["flags"] == 0

    def test_websocket_set_filter(self, client, sample_btsnoop_bytes):
        """Apply filter via WebSocket, receive filtered results."""
        resp = client.post(
            "/api/upload",
            files={"file": ("test.btsnoop", io.BytesIO(sample_btsnoop_bytes), "application/octet-stream")},
        )
        session_id = resp.json()["session_id"]

        with client.websocket_connect(f"/ws/{session_id}") as ws:
            ws.receive_json()  # drain initial batch

            # Set filter
            ws.send_json({"action": "set_filter", "expression": "direction == sent"})

            # Should get filter_applied then packet_batch
            msg = ws.receive_json()
            assert msg["type"] == "filter_applied"
            assert msg["matched"] == 2  # 2 sent packets

            msg = ws.receive_json()
            assert msg["type"] == "packet_batch"
            assert all(p["direction"] == "sent" for p in msg["packets"])

    def test_websocket_invalid_session(self, client):
        """WebSocket to non-existent session should close."""
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/nonexistent-session-id") as ws:
                ws.receive_json()

    def test_websocket_invalid_action(self, client, sample_btsnoop_bytes):
        """Invalid WebSocket action returns error."""
        resp = client.post(
            "/api/upload",
            files={"file": ("test.btsnoop", io.BytesIO(sample_btsnoop_bytes), "application/octet-stream")},
        )
        session_id = resp.json()["session_id"]

        with client.websocket_connect(f"/ws/{session_id}") as ws:
            ws.receive_json()  # drain
            ws.send_json({"action": "invalid_thing"})
            msg = ws.receive_json()
            assert msg["type"] == "error"


class TestRouteConflicts:
    """Ensure API and WebSocket routes are not intercepted by other handlers."""

    def test_api_health_accessible(self, client):
        """Health endpoint works regardless of static file state."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_api_upload_accessible(self, client, sample_btsnoop_bytes):
        """Upload endpoint works."""
        resp = client.post(
            "/api/upload",
            files={"file": ("test.btsnoop", io.BytesIO(sample_btsnoop_bytes), "application/octet-stream")},
        )
        assert resp.status_code == 200

    def test_websocket_not_intercepted_by_catchall(self, client, sample_btsnoop_bytes):
        """WebSocket path /ws/* is NOT captured by static file handler."""
        resp = client.post(
            "/api/upload",
            files={"file": ("test.btsnoop", io.BytesIO(sample_btsnoop_bytes), "application/octet-stream")},
        )
        session_id = resp.json()["session_id"]

        # This must NOT return HTTP 200 (which would mean catch-all intercepted it)
        # It must successfully upgrade to WebSocket
        with client.websocket_connect(f"/ws/{session_id}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "packet_batch"

    def test_export_endpoints_accessible(self, client, sample_btsnoop_bytes):
        """Export endpoints work after upload."""
        resp = client.post(
            "/api/upload",
            files={"file": ("test.btsnoop", io.BytesIO(sample_btsnoop_bytes), "application/octet-stream")},
        )
        session_id = resp.json()["session_id"]

        # JSON export
        resp = client.get(f"/api/sessions/{session_id}/export/json")
        assert resp.status_code == 200

        # CSV export
        resp = client.get(f"/api/sessions/{session_id}/export/csv")
        assert resp.status_code == 200

        # pcapng export
        resp = client.get(f"/api/sessions/{session_id}/export/pcapng")
        assert resp.status_code == 200

    def test_stats_endpoint_accessible(self, client, sample_btsnoop_bytes):
        """Stats endpoint returns valid data."""
        resp = client.post(
            "/api/upload",
            files={"file": ("test.btsnoop", io.BytesIO(sample_btsnoop_bytes), "application/octet-stream")},
        )
        session_id = resp.json()["session_id"]

        resp = client.get(f"/api/sessions/{session_id}/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["total_packets"] == 3
        assert "HCI_CMD" in stats["protocols"]


class TestDataIntegrity:
    """Verify packet data integrity through the full pipeline."""

    def test_packet_layers_have_correct_structure(self, client, sample_btsnoop_bytes):
        """Each packet's layers array matches expected frontend structure."""
        resp = client.post(
            "/api/upload",
            files={"file": ("test.btsnoop", io.BytesIO(sample_btsnoop_bytes), "application/octet-stream")},
        )
        session_id = resp.json()["session_id"]

        resp = client.get(f"/api/sessions/{session_id}/packets/2")
        assert resp.status_code == 200
        data = resp.json()

        # Verify structure matches frontend types
        pkt = data["packet"]
        assert "index" in pkt
        assert "timestamp" in pkt
        assert "direction" in pkt
        assert "protocol" in pkt
        assert "summary" in pkt
        assert "layers" in pkt
        assert "raw_length" in pkt

        # Verify layers structure
        for layer in pkt["layers"]:
            assert "protocol" in layer
            assert "summary" in layer
            assert "fields" in layer
            for field in layer["fields"]:
                assert "name" in field
                assert "value" in field
                assert "offset" in field
                assert "length" in field

    def test_raw_hex_matches_packet_length(self, client, sample_btsnoop_bytes):
        """raw_hex in detail response is consistent with packet length."""
        resp = client.post(
            "/api/upload",
            files={"file": ("test.btsnoop", io.BytesIO(sample_btsnoop_bytes), "application/octet-stream")},
        )
        session_id = resp.json()["session_id"]

        resp = client.get(f"/api/sessions/{session_id}/packets/0")
        data = resp.json()
        raw_hex = data["raw_hex"]
        raw_length = data["raw_length"]

        assert len(raw_hex) == raw_length * 2  # hex is 2 chars per byte
