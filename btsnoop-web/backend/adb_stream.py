"""
ADB real-time btsnoop streaming module.

Connects to an Android device via ADB, pulls btsnoop_hci.log incrementally,
and streams parsed packets in real-time.

Usage flow:
  1. Client calls POST /api/live/start to begin ADB capture
  2. Server starts an async task that reads btsnoop data from device
  3. Client connects to WebSocket and receives packets in real-time
  4. Client calls POST /api/live/stop to end capture
"""

from __future__ import annotations

import asyncio
import io
import os
import struct
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Optional, Set

from parser.btsnoop import BtSnoopReader, BTSNOOP_EPOCH_OFFSET, FILE_HEADER_SIZE, RECORD_HEADER_SIZE
from parser import parse_packet
from parser.models import SessionState, PacketSummary, DecodedLayer

# btsnoop file paths on Android
BTSNOOP_PATHS = [
    "/data/misc/bluetooth/logs/btsnoop_hci.log",
    "/data/misc/bluetooth/logs/btsnoop_hci_current.log",
    "/sdcard/btsnoop_hci.log",
]


@dataclass
class LiveSession:
    """A live ADB streaming session."""
    session_id: str
    serial: Optional[str] = None
    is_running: bool = False
    raw_packets: list[bytes] = field(default_factory=list)
    flags_list: list[int] = field(default_factory=list)
    summaries: list[PacketSummary] = field(default_factory=list)
    session_state: SessionState = field(default_factory=SessionState)
    total_packets: int = 0
    _task: Optional[asyncio.Task] = field(default=None, repr=False)
    _subscribers: Set[asyncio.Queue] = field(default_factory=set, repr=False)
    error: Optional[str] = None

    def add_packet(self, raw: bytes, flags: int, summary: PacketSummary):
        self.raw_packets.append(raw)
        self.flags_list.append(flags)
        self.summaries.append(summary)
        self.total_packets += 1
        for q in self._subscribers:
            try:
                q.put_nowait(summary)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subscribers.discard(q)


def _run_adb(args: list[str], serial: Optional[str] = None, timeout: float = 10) -> tuple[int, str, str]:
    """Run an adb command and return (returncode, stdout, stderr)."""
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except FileNotFoundError:
        return -1, "", "adb not found"


def check_adb_device(serial: Optional[str] = None) -> tuple[bool, str]:
    """Check if ADB device is available."""
    rc, stdout, stderr = _run_adb(["devices"], timeout=5)
    if rc != 0:
        return False, f"adb error: {stderr}"

    lines = stdout.strip().split('\n')[1:]  # skip header
    devices = [l.split('\t')[0] for l in lines if '\tdevice' in l]

    if not devices:
        return False, "没有连接的设备"

    if serial and serial not in devices:
        return False, f"设备 {serial} 未找到，可用设备: {', '.join(devices)}"

    return True, devices[0] if not serial else serial


def find_btsnoop_path(serial: Optional[str] = None) -> Optional[str]:
    """Find the btsnoop file path on the device."""
    for path in BTSNOOP_PATHS:
        rc, stdout, stderr = _run_adb(["shell", f"ls {path}"], serial=serial, timeout=5)
        if rc == 0 and path in stdout:
            return path
    return None


async def start_live_capture(live_session: LiveSession):
    """
    Main async loop: pull btsnoop data from device incrementally.
    Uses `adb shell cat <path>` with incremental reading.
    """
    serial = live_session.serial
    live_session.is_running = True
    live_session.error = None

    # Find btsnoop path
    btsnoop_path = find_btsnoop_path(serial)
    if not btsnoop_path:
        live_session.error = "未找到 btsnoop 文件，请确认已开启蓝牙 HCI 日志"
        live_session.is_running = False
        return

    # Strategy: use adb pull to temp file, then tail for new data
    tmpdir = tempfile.mkdtemp(prefix="btsnoop_live_")
    tmpfile = os.path.join(tmpdir, "btsnoop_hci.log")

    try:
        last_size = 0
        header_parsed = False
        session = live_session.session_state
        packet_index = 0

        while live_session.is_running:
            # Pull the file
            cmd = ["adb"]
            if serial:
                cmd += ["-s", serial]
            cmd += ["pull", btsnoop_path, tmpfile]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            if not os.path.exists(tmpfile):
                await asyncio.sleep(1)
                continue

            cur_size = os.path.getsize(tmpfile)
            if cur_size <= last_size:
                await asyncio.sleep(0.5)
                continue

            # Parse new data
            with open(tmpfile, 'rb') as f:
                if not header_parsed:
                    # First read: parse header
                    try:
                        reader = BtSnoopReader(f)
                        header_parsed = True
                    except ValueError as e:
                        live_session.error = f"无效的 btsnoop 文件: {e}"
                        await asyncio.sleep(1)
                        continue

                    # Parse all current records
                    for rec in reader:
                        layers = parse_packet(rec.data, rec.flags, session)
                        protocol = layers[-1].protocol if layers else "HCI"
                        summary_text = layers[-1].summary if layers else ""
                        pkt = PacketSummary(
                            index=packet_index,
                            timestamp_us=rec.timestamp_us,
                            timestamp_str=rec.timestamp_str,
                            direction=rec.direction,
                            protocol=protocol,
                            summary=summary_text,
                            layers=layers,
                            raw_length=rec.original_length,
                            included_length=rec.included_length,
                        )
                        live_session.add_packet(rec.data, rec.flags, pkt)
                        packet_index += 1
                else:
                    # Incremental: seek to last position and read new records
                    f.seek(last_size)
                    while True:
                        rec_hdr = f.read(RECORD_HEADER_SIZE)
                        if len(rec_hdr) < RECORD_HEADER_SIZE:
                            break
                        orig_len, incl_len, flags, drops = struct.unpack(">IIII", rec_hdr[:16])
                        ts_hi, ts_lo = struct.unpack(">II", rec_hdr[16:24])
                        ts = (ts_hi << 32) | ts_lo
                        pkt_data = f.read(incl_len)
                        if len(pkt_data) < incl_len:
                            break

                        layers = parse_packet(pkt_data, flags, session)
                        protocol = layers[-1].protocol if layers else "HCI"
                        summary_text = layers[-1].summary if layers else ""

                        from parser.btsnoop import timestamp_to_str
                        from parser.models import Direction
                        direction = Direction.RECEIVED if (flags & 1) else Direction.SENT

                        pkt = PacketSummary(
                            index=packet_index,
                            timestamp_us=ts,
                            timestamp_str=timestamp_to_str(ts),
                            direction=direction,
                            protocol=protocol,
                            summary=summary_text,
                            layers=layers,
                            raw_length=orig_len,
                            included_length=incl_len,
                        )
                        live_session.add_packet(pkt_data, flags, pkt)
                        packet_index += 1

            last_size = cur_size
            await asyncio.sleep(0.5)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        live_session.error = str(e)
    finally:
        live_session.is_running = False
        # Cleanup temp files
        try:
            os.unlink(tmpfile)
            os.rmdir(tmpdir)
        except OSError:
            pass
