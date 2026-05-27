"""
Data models for btsnoop packet parsing results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Direction(Enum):
    """Packet direction."""
    SENT = "sent"  # Host → Controller
    RECEIVED = "received"  # Controller → Host


class HciType(Enum):
    """HCI packet type indicators."""
    COMMAND = 0x01
    ACL = 0x02
    SCO = 0x03
    EVENT = 0x04
    ISO = 0x05


@dataclass
class DecodedField:
    """A single decoded field within a protocol layer."""
    name: str
    value: Any
    offset: int = 0
    length: int = 0
    raw: Optional[bytes] = None
    description: str = ""
    children: list['DecodedField'] = field(default_factory=list)

    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "value": self.value,
            "offset": self.offset,
            "length": self.length,
        }
        if self.description:
            result["description"] = self.description
        if self.raw is not None:
            result["raw"] = self.raw.hex()
        if self.children:
            result["children"] = [c.to_dict() for c in self.children]
        return result


@dataclass
class DecodedLayer:
    """
    A single decoded protocol layer.
    Each layer in the stack produces one of these.
    """
    protocol: str
    summary: str
    fields: list[DecodedField] = field(default_factory=list)
    payload_offset: int = 0  # offset where next layer's data starts
    payload: bytes = b""  # remaining payload for the next layer
    sublayers: list[DecodedLayer] = field(default_factory=list)

    def to_dict(self) -> dict:
        result = {
            "protocol": self.protocol,
            "summary": self.summary,
            "fields": [f.to_dict() for f in self.fields],
        }
        if self.sublayers:
            result["sublayers"] = [s.to_dict() for s in self.sublayers]
        return result


@dataclass
class PacketSummary:
    """
    Top-level summary for a single btsnoop packet record.
    """
    index: int
    timestamp_us: int
    timestamp_str: str
    direction: Direction
    protocol: str
    summary: str
    layers: list[DecodedLayer] = field(default_factory=list)
    raw_length: int = 0
    included_length: int = 0

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp_us": self.timestamp_us,
            "timestamp": self.timestamp_str,
            "direction": self.direction.value,
            "protocol": self.protocol,
            "summary": self.summary,
            "layers": [l.to_dict() for l in self.layers],
            "raw_length": self.raw_length,
            "included_length": self.included_length,
        }


@dataclass
class SessionState:
    """
    Maintains connection state across packets.
    Tracks CID-to-PSM mappings, connection handles, and L2CAP fragment reassembly.
    """
    # Maps L2CAP CID → PSM for dynamic channels
    cid_to_psm: dict[int, int] = field(default_factory=dict)
    # Maps connection handle → remote BD_ADDR
    handle_to_addr: dict[int, str] = field(default_factory=dict)
    # L2CAP fragment reassembly: handle → (expected_total_len, accumulated_data)
    l2cap_fragments: dict[int, tuple[int, bytes]] = field(default_factory=dict)
    # Packet counter
    packet_count: int = 0

    def reset(self):
        """Reset all state (e.g. when btsnoop file resets)."""
        self.cid_to_psm.clear()
        self.handle_to_addr.clear()
        self.l2cap_fragments.clear()
        self.packet_count = 0

    def map_cid_to_psm(self, cid: int, psm: int):
        """Record a CID → PSM mapping."""
        self.cid_to_psm[cid] = psm

    def get_psm_for_cid(self, cid: int) -> Optional[int]:
        """Look up the PSM for a given CID."""
        return self.cid_to_psm.get(cid)

    def next_index(self) -> int:
        """Get next packet index and increment counter."""
        self.packet_count += 1
        return self.packet_count
