"""
Tests for FastAPI server endpoints (server.py).

Tests:
  - POST /api/upload with a valid btsnoop file
  - GET /api/sessions/{id}/packets
  - GET /api/sessions/{id}/packets/{index}
  - Health check
"""

from __future__ import annotations

import struct
import io

import pytest
from fastapi.testclient import TestClient

from server import app, session_manager
from .conftest import (
    build_btsnoop_file,
    build_btsnoop_file_header,
    build_hci_command,
    build_hci_event,
    build_hci_acl,
    build_l2cap,
    build_att_exchange_mtu_req,
)


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_sessions():
    """Clean up sessions after each test."""
    yield
    # Clear all sessions
    session_manager._sessions.clear()


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_ok(self, client):
        """Health endpoint returns ok status."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "active_sessions" in data

    def test_health_shows_session_count(self, client):
        """Health endpoint shows correct session count."""
        response = client.get("/api/health")
        data = response.json()
        assert data["active_sessions"] == 0


class TestUpload:
    """Tests for POST /api/upload endpoint."""

    def test_upload_valid_btsnoop(self, client):
        """Upload a valid btsnoop file with HCI packets."""
        reset_cmd = build_hci_command(0x0C03)
        cmd_complete = build_hci_event(0x0E, struct.pack("<BHB", 1, 0x0C03, 0))
        file_data = build_btsnoop_file([
            (reset_cmd, 0x00),
            (cmd_complete, 0x01),
        ])

        response = client.post(
            "/api/upload",
            files={"file": ("test.log", io.BytesIO(file_data), "application/octet-stream")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["total_packets"] == 2
        assert data["datalink_type"] == 1002

    def test_upload_empty_btsnoop(self, client):
        """Upload a btsnoop file with no records."""
        file_data = build_btsnoop_file_header()
        response = client.post(
            "/api/upload",
            files={"file": ("empty.log", io.BytesIO(file_data), "application/octet-stream")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_packets"] == 0

    def test_upload_invalid_file(self, client):
        """Upload an invalid file returns 400."""
        response = client.post(
            "/api/upload",
            files={"file": ("bad.log", io.BytesIO(b"not a btsnoop file!!"), "application/octet-stream")},
        )
        assert response.status_code == 400

    def test_upload_too_small(self, client):
        """Upload a file that is too small."""
        response = client.post(
            "/api/upload",
            files={"file": ("tiny.log", io.BytesIO(b"\x00\x01"), "application/octet-stream")},
        )
        assert response.status_code == 400

    def test_upload_preserves_filename(self, client):
        """Upload response includes the filename."""
        file_data = build_btsnoop_file_header()
        response = client.post(
            "/api/upload",
            files={"file": ("my_capture.log", io.BytesIO(file_data), "application/octet-stream")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "my_capture.log"

    def test_upload_with_att_packets(self, client):
        """Upload btsnoop with ACL/L2CAP/ATT packet."""
        att_payload = build_att_exchange_mtu_req(517)
        l2cap_data = build_l2cap(0x0004, att_payload)
        acl_pkt = build_hci_acl(0x0040, pb_flag=2, bc_flag=0, payload=l2cap_data)

        file_data = build_btsnoop_file([(acl_pkt, 0x00)])
        response = client.post(
            "/api/upload",
            files={"file": ("att.log", io.BytesIO(file_data), "application/octet-stream")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_packets"] == 1


class TestGetPackets:
    """Tests for GET /api/sessions/{id}/packets endpoint."""

    def _upload_sample(self, client) -> str:
        """Upload a sample file and return session_id."""
        reset_cmd = build_hci_command(0x0C03)
        cmd_complete = build_hci_event(0x0E, struct.pack("<BHB", 1, 0x0C03, 0))
        disconn = build_hci_event(0x05, struct.pack("<BHB", 0, 0x0040, 0x13))
        file_data = build_btsnoop_file([
            (reset_cmd, 0x00),
            (cmd_complete, 0x01),
            (disconn, 0x01),
        ])
        response = client.post(
            "/api/upload",
            files={"file": ("test.log", io.BytesIO(file_data), "application/octet-stream")},
        )
        return response.json()["session_id"]

    def test_get_packets_basic(self, client):
        """Get packet list for a valid session."""
        session_id = self._upload_sample(client)
        response = client.get(f"/api/sessions/{session_id}/packets")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["packets"]) == 3
        assert data["session_id"] == session_id

    def test_get_packets_pagination(self, client):
        """Get packets with offset and limit."""
        session_id = self._upload_sample(client)
        response = client.get(
            f"/api/sessions/{session_id}/packets",
            params={"offset": 1, "limit": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["packets"]) == 1
        assert data["packets"][0]["index"] == 1

    def test_get_packets_invalid_session(self, client):
        """Request packets for non-existent session returns 404."""
        response = client.get("/api/sessions/nonexistent-id/packets")
        assert response.status_code == 404

    def test_get_packets_with_filter(self, client):
        """Filter packets by protocol."""
        session_id = self._upload_sample(client)
        response = client.get(
            f"/api/sessions/{session_id}/packets",
            params={"filter": "protocol == HCI_CMD"},
        )
        assert response.status_code == 200
        data = response.json()
        # Only the Reset command should match
        assert data["total"] == 1
        assert data["packets"][0]["protocol"] == "HCI_CMD"

    def test_get_packets_with_invalid_filter(self, client):
        """Invalid filter expression returns 400."""
        session_id = self._upload_sample(client)
        response = client.get(
            f"/api/sessions/{session_id}/packets",
            params={"filter": "!! invalid syntax"},
        )
        assert response.status_code == 400

    def test_get_packets_structure(self, client):
        """Verify packet structure in response."""
        session_id = self._upload_sample(client)
        response = client.get(f"/api/sessions/{session_id}/packets")
        data = response.json()
        pkt = data["packets"][0]
        assert "index" in pkt
        assert "timestamp" in pkt
        assert "direction" in pkt
        assert "protocol" in pkt
        assert "summary" in pkt
        assert "layers" in pkt


class TestGetPacketDetail:
    """Tests for GET /api/sessions/{id}/packets/{index} endpoint."""

    def _upload_sample(self, client) -> str:
        """Upload a sample file and return session_id."""
        reset_cmd = build_hci_command(0x0C03)
        file_data = build_btsnoop_file([(reset_cmd, 0x00)])
        response = client.post(
            "/api/upload",
            files={"file": ("test.log", io.BytesIO(file_data), "application/octet-stream")},
        )
        return response.json()["session_id"]

    def test_get_packet_detail(self, client):
        """Get detail for a specific packet."""
        session_id = self._upload_sample(client)
        response = client.get(f"/api/sessions/{session_id}/packets/0")
        assert response.status_code == 200
        data = response.json()
        assert "packet" in data
        assert "raw_hex" in data
        assert "flags" in data
        assert data["packet"]["index"] == 0

    def test_get_packet_detail_out_of_range(self, client):
        """Request packet beyond range returns 404."""
        session_id = self._upload_sample(client)
        response = client.get(f"/api/sessions/{session_id}/packets/999")
        assert response.status_code == 404

    def test_get_packet_detail_invalid_session(self, client):
        """Request detail for non-existent session returns 404."""
        response = client.get("/api/sessions/bad-id/packets/0")
        assert response.status_code == 404

    def test_packet_detail_has_raw_hex(self, client):
        """Packet detail includes raw hex dump."""
        session_id = self._upload_sample(client)
        response = client.get(f"/api/sessions/{session_id}/packets/0")
        data = response.json()
        # HCI Reset command raw hex should start with "01" (cmd type) + "030c" (opcode LE)
        assert data["raw_hex"].startswith("01030c")

    def test_packet_detail_layers(self, client):
        """Packet detail includes decoded layers."""
        session_id = self._upload_sample(client)
        response = client.get(f"/api/sessions/{session_id}/packets/0")
        data = response.json()
        layers = data["packet"]["layers"]
        assert len(layers) >= 1
        assert layers[0]["protocol"] == "HCI_CMD"
        assert "Reset" in layers[0]["summary"]
