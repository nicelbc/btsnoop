"""
Session manager for btsnoop web tool.

Manages parsed btsnoop sessions with auto-cleanup after inactivity.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from parser.models import PacketSummary, SessionState, DecodedLayer


@dataclass
class Session:
    """
    Holds parsed btsnoop data for a single upload session.

    Attributes:
        session_id: Unique session identifier.
        raw_packets: List of raw packet bytes for each record.
        flags_list: List of btsnoop flags for each record.
        summaries: List of PacketSummary objects (one per packet).
        session_state: Connection state tracker (CID->PSM, handle->addr).
        created_at: Session creation timestamp (monotonic).
        last_access: Last access timestamp (monotonic) for cleanup.
    """
    session_id: str
    raw_packets: list[bytes] = field(default_factory=list)
    flags_list: list[int] = field(default_factory=list)
    summaries: list[PacketSummary] = field(default_factory=list)
    session_state: SessionState = field(default_factory=SessionState)
    created_at: float = field(default_factory=time.monotonic)
    last_access: float = field(default_factory=time.monotonic)
    total_packets: int = 0

    def touch(self):
        """Update last access time."""
        self.last_access = time.monotonic()

    def add_packet(self, raw: bytes, flags: int, summary: PacketSummary):
        """Add a parsed packet to the session."""
        self.raw_packets.append(raw)
        self.flags_list.append(flags)
        self.summaries.append(summary)
        self.total_packets += 1

    def get_summary(self, index: int) -> Optional[PacketSummary]:
        """Get packet summary by index (0-based)."""
        if 0 <= index < len(self.summaries):
            self.touch()
            return self.summaries[index]
        return None

    def get_summaries(
        self, offset: int = 0, limit: int = 100
    ) -> list[PacketSummary]:
        """Get a page of summaries."""
        self.touch()
        return self.summaries[offset : offset + limit]

    def get_raw_packet(self, index: int) -> Optional[bytes]:
        """Get raw packet data by index."""
        if 0 <= index < len(self.raw_packets):
            return self.raw_packets[index]
        return None

    def get_flags(self, index: int) -> Optional[int]:
        """Get packet flags by index."""
        if 0 <= index < len(self.flags_list):
            return self.flags_list[index]
        return None


class SessionManager:
    """
    Manages multiple sessions with automatic cleanup.

    Sessions are automatically removed after max_inactive_seconds of inactivity.
    """

    def __init__(self, max_inactive_seconds: float = 1800.0):
        """
        Args:
            max_inactive_seconds: Seconds of inactivity before session cleanup.
                                  Default is 30 minutes (1800s).
        """
        self._sessions: dict[str, Session] = {}
        self._max_inactive = max_inactive_seconds
        self._cleanup_task: Optional[asyncio.Task] = None

    def create_session(self) -> Session:
        """Create a new session and return it."""
        session_id = str(uuid.uuid4())
        session = Session(session_id=session_id)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID, updating its last_access time."""
        session = self._sessions.get(session_id)
        if session is not None:
            session.touch()
        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if it existed."""
        return self._sessions.pop(session_id, None) is not None

    @property
    def active_sessions(self) -> int:
        """Number of active sessions."""
        return len(self._sessions)

    def cleanup_expired(self) -> int:
        """
        Remove expired sessions.
        Returns number of sessions removed.
        """
        now = time.monotonic()
        expired = [
            sid
            for sid, session in self._sessions.items()
            if (now - session.last_access) > self._max_inactive
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)

    async def start_cleanup_loop(self, interval: float = 60.0):
        """Start periodic cleanup in background."""
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop(interval)
        )

    async def _cleanup_loop(self, interval: float):
        """Background task that periodically cleans up expired sessions."""
        try:
            while True:
                await asyncio.sleep(interval)
                removed = self.cleanup_expired()
                if removed > 0:
                    print(f"[SessionManager] Cleaned up {removed} expired session(s)")
        except asyncio.CancelledError:
            pass

    async def stop_cleanup_loop(self):
        """Stop the background cleanup task."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
