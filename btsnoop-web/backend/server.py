"""
FastAPI server for btsnoop online parser web tool.

Endpoints:
  POST   /api/upload                          - Upload btsnoop file, parse and store
  GET    /api/sessions/{session_id}/packets   - REST fallback: paginated packet list
  GET    /api/sessions/{session_id}/packets/{index} - Get full decode for one packet
  WS     /ws/{session_id}                     - Stream packets with filtering
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Parser imports
from parser.btsnoop import BtSnoopReader
from parser.models import PacketSummary, DecodedLayer, SessionState, Direction
from parser import parse_packet

# Local imports
from session import Session, SessionManager
from filter_engine import compile_filter, validate_filter, FilterParseError


# --- Application lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown lifecycle."""
    # Startup: begin session cleanup loop
    await session_manager.start_cleanup_loop(interval=60.0)
    print("[Server] Started session cleanup loop")
    yield
    # Shutdown: stop cleanup
    await session_manager.stop_cleanup_loop()
    print("[Server] Stopped session cleanup loop")


# --- App & session manager ---

app = FastAPI(
    title="BtSnoop Online Parser",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: allow all origins in dev mode
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global session manager (30 min inactivity timeout)
session_manager = SessionManager(max_inactive_seconds=1800.0)

# Max upload size: 100 MB
MAX_UPLOAD_SIZE = 100 * 1024 * 1024


# --- REST Endpoints ---


@app.post("/api/upload")
async def upload_btsnoop(file: UploadFile = File(...)):
    """
    Upload a btsnoop file for parsing.

    Reads the entire file, parses all packets, stores them in a session,
    and returns the session_id plus basic stats.
    """
    # Validate content length if available
    if file.size and file.size > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)}MB",
        )

    # Read file content
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)}MB",
        )

    if len(content) < 16:
        raise HTTPException(status_code=400, detail="File too small to be a valid btsnoop file")

    # Parse the btsnoop file
    try:
        reader = BtSnoopReader(io.BytesIO(content))
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=400, detail=f"Invalid btsnoop file: {str(e)}")

    # Create session
    session = session_manager.create_session()
    state = session.session_state

    # Parse all records
    packet_index = 0
    for record in reader:
        # Decode packet
        layers = parse_packet(record.data, record.flags, state)

        # Determine top-level protocol and summary
        protocol = "HCI"
        summary_text = ""
        if layers:
            protocol = layers[-1].protocol  # deepest decoded layer
            summary_text = layers[-1].summary

        # Build PacketSummary
        pkt_summary = PacketSummary(
            index=packet_index,
            timestamp_us=record.timestamp_us,
            timestamp_str=record.timestamp_str,
            direction=record.direction,
            protocol=protocol,
            summary=summary_text,
            layers=layers,
            raw_length=record.original_length,
            included_length=record.included_length,
        )

        session.add_packet(record.data, record.flags, pkt_summary)
        packet_index += 1

    return JSONResponse(
        content={
            "session_id": session.session_id,
            "total_packets": session.total_packets,
            "datalink_type": reader.datalink_type,
            "filename": file.filename or "unknown",
        }
    )


@app.get("/api/sessions/{session_id}/packets")
async def get_packets(
    session_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    filter_expr: Optional[str] = Query(default=None, alias="filter"),
):
    """
    Get paginated packet list for a session.

    Query params:
      - offset: Start index (default 0)
      - limit: Max packets to return (default 100, max 1000)
      - filter: Optional Wireshark-style filter expression
    """
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Apply filter if provided
    if filter_expr:
        error = validate_filter(filter_expr)
        if error:
            raise HTTPException(status_code=400, detail=f"Invalid filter: {error}")
        filter_func = compile_filter(filter_expr)

        # Filter all packets, then paginate
        filtered = []
        for i, summary in enumerate(session.summaries):
            raw = session.get_raw_packet(i)
            if filter_func(summary, raw or b""):
                filtered.append(summary)

        total = len(filtered)
        page = filtered[offset : offset + limit]
    else:
        total = session.total_packets
        page = session.get_summaries(offset, limit)

    return JSONResponse(
        content={
            "session_id": session_id,
            "total": total,
            "offset": offset,
            "limit": limit,
            "packets": [p.to_dict() for p in page],
        }
    )


@app.get("/api/sessions/{session_id}/packets/{index}")
async def get_packet_detail(session_id: str, index: int):
    """
    Get full decode detail for a single packet by index.
    """
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    summary = session.get_summary(index)
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail=f"Packet index {index} not found (total: {session.total_packets})",
        )

    raw = session.get_raw_packet(index)
    flags = session.get_flags(index)

    return JSONResponse(
        content={
            "packet": summary.to_dict(),
            "raw_hex": raw.hex() if raw else "",
            "raw_length": len(raw) if raw else 0,
            "flags": flags,
        }
    )


# --- WebSocket Endpoint ---


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for streaming parsed packets to frontend.

    Server -> Client messages:
      - {"type": "packet_batch", "packets": [...]}  -- batch of PacketSummary dicts
      - {"type": "packet_detail", "packet": {...}, "raw_hex": "...", "flags": N}
      - {"type": "error", "message": "..."}
      - {"type": "filter_applied", "expression": "...", "matched": N}

    Client -> Server messages:
      - {"action": "get_detail", "index": N}
      - {"action": "set_filter", "expression": "..."}
      - {"action": "get_packets", "offset": N, "limit": N}
    """
    session = session_manager.get_session(session_id)
    if session is None:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()

    # Send initial batch of packets
    try:
        await _send_packet_batches(websocket, session, filter_func=None)
    except WebSocketDisconnect:
        return

    # Message loop
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {"type": "error", "message": "Invalid JSON message"}
                )
                continue

            action = msg.get("action")
            session.touch()

            if action == "get_detail":
                await _handle_get_detail(websocket, session, msg)
            elif action == "set_filter":
                await _handle_set_filter(websocket, session, msg)
            elif action == "get_packets":
                await _handle_get_packets(websocket, session, msg)
            else:
                await websocket.send_json(
                    {"type": "error", "message": f"Unknown action: {action}"}
                )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json(
                {"type": "error", "message": f"Internal error: {str(e)}"}
            )
        except Exception:
            pass


async def _send_packet_batches(
    websocket: WebSocket,
    session: Session,
    filter_func=None,
    offset: int = 0,
    limit: Optional[int] = None,
):
    """
    Send packets in batches via WebSocket.
    Batches up to 100 packets or sends every 50ms, whichever comes first.
    """
    BATCH_SIZE = 100
    BATCH_INTERVAL_MS = 50

    packets_to_send = []
    total = session.total_packets
    end = total if limit is None else min(offset + limit, total)

    for i in range(offset, end):
        summary = session.summaries[i]
        if filter_func is not None:
            raw = session.get_raw_packet(i) or b""
            if not filter_func(summary, raw):
                continue
        packets_to_send.append(summary)

    # Send in batches
    for batch_start in range(0, len(packets_to_send), BATCH_SIZE):
        batch = packets_to_send[batch_start : batch_start + BATCH_SIZE]
        await websocket.send_json(
            {
                "type": "packet_batch",
                "packets": [p.to_dict() for p in batch],
                "total": len(packets_to_send),
                "batch_offset": batch_start,
            }
        )
        # Yield control to allow other tasks / throttle
        if batch_start + BATCH_SIZE < len(packets_to_send):
            await asyncio.sleep(BATCH_INTERVAL_MS / 1000.0)


async def _handle_get_detail(websocket: WebSocket, session: Session, msg: dict):
    """Handle get_detail request: send full packet decode."""
    index = msg.get("index")
    if index is None or not isinstance(index, int):
        await websocket.send_json(
            {"type": "error", "message": "get_detail requires integer 'index'"}
        )
        return

    summary = session.get_summary(index)
    if summary is None:
        await websocket.send_json(
            {"type": "error", "message": f"Packet index {index} not found"}
        )
        return

    raw = session.get_raw_packet(index)
    flags = session.get_flags(index)

    await websocket.send_json(
        {
            "type": "packet_detail",
            "packet": summary.to_dict(),
            "raw_hex": raw.hex() if raw else "",
            "flags": flags,
        }
    )


async def _handle_set_filter(websocket: WebSocket, session: Session, msg: dict):
    """Handle set_filter request: re-stream filtered packets."""
    expression = msg.get("expression", "")

    if expression:
        error = validate_filter(expression)
        if error:
            await websocket.send_json(
                {"type": "error", "message": f"Invalid filter: {error}"}
            )
            return
        filter_func = compile_filter(expression)
    else:
        filter_func = None

    # Count matches and stream filtered results
    matched = 0
    if filter_func:
        for i in range(session.total_packets):
            raw = session.get_raw_packet(i) or b""
            if filter_func(session.summaries[i], raw):
                matched += 1
    else:
        matched = session.total_packets

    await websocket.send_json(
        {
            "type": "filter_applied",
            "expression": expression,
            "matched": matched,
            "total": session.total_packets,
        }
    )

    # Stream filtered packets
    await _send_packet_batches(websocket, session, filter_func=filter_func)


async def _handle_get_packets(websocket: WebSocket, session: Session, msg: dict):
    """Handle get_packets request with optional pagination."""
    offset = msg.get("offset", 0)
    limit = msg.get("limit", 100)
    expression = msg.get("filter", "")

    filter_func = None
    if expression:
        error = validate_filter(expression)
        if error:
            await websocket.send_json(
                {"type": "error", "message": f"Invalid filter: {error}"}
            )
            return
        filter_func = compile_filter(expression)

    await _send_packet_batches(
        websocket, session, filter_func=filter_func, offset=offset, limit=limit
    )


# --- Live ADB Streaming ---

from adb_stream import LiveSession, check_adb_device, start_live_capture

live_sessions: dict[str, LiveSession] = {}


@app.get("/api/live/devices")
async def list_adb_devices():
    """List available ADB devices."""
    from adb_stream import _run_adb
    rc, stdout, stderr = _run_adb(["devices"])
    if rc != 0:
        return {"devices": [], "error": stderr}

    lines = stdout.strip().split('\n')[1:]
    devices = []
    for line in lines:
        parts = line.split('\t')
        if len(parts) >= 2 and parts[1] == 'device':
            devices.append(parts[0])
    return {"devices": devices}


@app.post("/api/live/start")
async def start_live(serial: Optional[str] = None):
    """Start live ADB capture. Returns session_id for WebSocket connection."""
    ok, info = check_adb_device(serial)
    if not ok:
        raise HTTPException(status_code=400, detail=info)

    device_serial = info  # actual device serial
    import uuid
    session_id = str(uuid.uuid4())
    live_session = LiveSession(session_id=session_id, serial=device_serial)
    live_sessions[session_id] = live_session

    # Start capture task
    task = asyncio.create_task(start_live_capture(live_session))
    live_session._task = task

    return {
        "session_id": session_id,
        "device": device_serial,
        "status": "capturing",
    }


@app.post("/api/live/stop/{session_id}")
async def stop_live(session_id: str):
    """Stop live ADB capture."""
    live_session = live_sessions.get(session_id)
    if not live_session:
        raise HTTPException(status_code=404, detail="Live session not found")

    live_session.is_running = False
    if live_session._task:
        live_session._task.cancel()
        try:
            await live_session._task
        except asyncio.CancelledError:
            pass

    return {
        "session_id": session_id,
        "total_packets": live_session.total_packets,
        "status": "stopped",
    }


@app.get("/api/live/status/{session_id}")
async def live_status(session_id: str):
    """Get live capture status."""
    live_session = live_sessions.get(session_id)
    if not live_session:
        raise HTTPException(status_code=404, detail="Live session not found")

    return {
        "session_id": session_id,
        "is_running": live_session.is_running,
        "total_packets": live_session.total_packets,
        "error": live_session.error,
    }


@app.websocket("/ws/live/{session_id}")
async def websocket_live(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for live packet streaming."""
    live_session = live_sessions.get(session_id)
    if not live_session:
        await websocket.close(code=4004, reason="Live session not found")
        return

    await websocket.accept()

    # Send existing packets first
    BATCH_SIZE = 100
    for batch_start in range(0, live_session.total_packets, BATCH_SIZE):
        batch = live_session.summaries[batch_start:batch_start + BATCH_SIZE]
        await websocket.send_json({
            "type": "packet_batch",
            "packets": [p.to_dict() for p in batch],
            "total": live_session.total_packets,
            "batch_offset": batch_start,
        })

    # Subscribe to new packets
    queue = live_session.subscribe()
    try:
        while True:
            # Wait for new packets (with timeout to check for disconnect)
            try:
                batch = []
                pkt = await asyncio.wait_for(queue.get(), timeout=0.1)
                batch.append(pkt)
                # Drain up to BATCH_SIZE more
                while len(batch) < BATCH_SIZE:
                    try:
                        pkt = queue.get_nowait()
                        batch.append(pkt)
                    except asyncio.QueueEmpty:
                        break

                await websocket.send_json({
                    "type": "packet_batch",
                    "packets": [p.to_dict() for p in batch],
                    "total": live_session.total_packets,
                    "batch_offset": live_session.total_packets - len(batch),
                    "live": True,
                })
            except asyncio.TimeoutError:
                # Check if capture ended
                if not live_session.is_running and queue.empty():
                    await websocket.send_json({
                        "type": "live_stopped",
                        "total_packets": live_session.total_packets,
                        "error": live_session.error,
                    })
                    break

            # Handle incoming messages (get_detail, set_filter)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                msg = json.loads(data)
                if msg.get("action") == "get_detail":
                    idx = msg.get("index", 0)
                    if 0 <= idx < live_session.total_packets:
                        summary = live_session.summaries[idx]
                        raw = live_session.raw_packets[idx]
                        flags = live_session.flags_list[idx]
                        await websocket.send_json({
                            "type": "packet_detail",
                            "packet": summary.to_dict(),
                            "raw_hex": raw.hex(),
                            "flags": flags,
                        })
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass

    except WebSocketDisconnect:
        pass
    finally:
        live_session.unsubscribe(queue)



# --- Export Endpoints ---


@app.get("/api/sessions/{session_id}/export/json")
async def export_json(
    session_id: str,
    filter_expr: Optional[str] = Query(default=None, alias="filter"),
):
    """
    Export all packets (or filtered) as a JSON file download.
    """
    from fastapi.responses import StreamingResponse

    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Determine which packets to export
    if filter_expr:
        error = validate_filter(filter_expr)
        if error:
            raise HTTPException(status_code=400, detail=f"Invalid filter: {error}")
        filter_func = compile_filter(filter_expr)

        packets = []
        for i, summary in enumerate(session.summaries):
            raw = session.get_raw_packet(i) or b""
            if filter_func(summary, raw):
                packets.append(summary.to_dict())
    else:
        packets = [s.to_dict() for s in session.summaries]

    def generate():
        yield json.dumps({"total": len(packets), "packets": packets}, indent=2)

    return StreamingResponse(
        generate(),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="btsnoop_export_{session_id[:8]}.json"'
        },
    )


@app.get("/api/sessions/{session_id}/export/csv")
async def export_csv(
    session_id: str,
    filter_expr: Optional[str] = Query(default=None, alias="filter"),
):
    """
    Export all packets (or filtered) as a CSV file download.
    Columns: index, timestamp, direction, protocol, length, summary
    """
    import csv as csv_module
    from fastapi.responses import StreamingResponse

    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Determine which packets to export
    if filter_expr:
        error = validate_filter(filter_expr)
        if error:
            raise HTTPException(status_code=400, detail=f"Invalid filter: {error}")
        filter_func = compile_filter(filter_expr)

        summaries = []
        for i, summary in enumerate(session.summaries):
            raw = session.get_raw_packet(i) or b""
            if filter_func(summary, raw):
                summaries.append(summary)
    else:
        summaries = list(session.summaries)

    def generate():
        output = io.StringIO()
        writer = csv_module.writer(output)
        # Header
        writer.writerow(["index", "timestamp", "direction", "protocol", "length", "summary"])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        # Data rows
        for s in summaries:
            d = s.to_dict()
            writer.writerow([
                d.get("index", ""),
                d.get("timestamp_str", ""),
                d.get("direction", ""),
                d.get("protocol", ""),
                d.get("raw_length", ""),
                d.get("summary", ""),
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="btsnoop_export_{session_id[:8]}.csv"'
        },
    )


# --- Statistics Endpoint ---


@app.get("/api/sessions/{session_id}/stats")
async def get_session_stats(session_id: str):
    """
    Return statistics for a session:
    - total_packets
    - protocols: count per protocol
    - directions: sent vs received
    - duration_ms: time from first to last packet
    - packets_per_second: average rate
    """
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    protocols: dict[str, int] = {}
    directions: dict[str, int] = {"sent": 0, "received": 0}
    first_ts: Optional[int] = None
    last_ts: Optional[int] = None

    for summary in session.summaries:
        # Protocol counts
        proto = summary.protocol
        protocols[proto] = protocols.get(proto, 0) + 1

        # Direction counts
        direction_str = summary.direction
        if direction_str in ("sent", "Sent", "SENT"):
            directions["sent"] += 1
        else:
            directions["received"] += 1

        # Timestamps (microseconds)
        ts = summary.timestamp_us
        if ts is not None:
            if first_ts is None or ts < first_ts:
                first_ts = ts
            if last_ts is None or ts > last_ts:
                last_ts = ts

    # Duration in milliseconds
    if first_ts is not None and last_ts is not None:
        duration_ms = (last_ts - first_ts) // 1000
    else:
        duration_ms = 0

    # Packets per second
    if duration_ms > 0:
        packets_per_second = round(session.total_packets / (duration_ms / 1000.0), 2)
    else:
        packets_per_second = 0

    return JSONResponse(
        content={
            "total_packets": session.total_packets,
            "protocols": protocols,
            "directions": directions,
            "duration_ms": duration_ms,
            "packets_per_second": packets_per_second,
        }
    )


# --- pcapng Export ---


@app.get("/api/sessions/{session_id}/export/pcapng")
async def export_pcapng(session_id: str):
    """Export session as pcapng file (Wireshark compatible)."""
    from pcapng_export import generate_pcapng
    from fastapi.responses import StreamingResponse

    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    def stream():
        for chunk in generate_pcapng(
            session.raw_packets, session.flags_list, session.summaries
        ):
            yield chunk

    return StreamingResponse(
        stream(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="btsnoop_{session_id[:8]}.pcapng"'
        },
    )


# --- Health check ---


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "active_sessions": session_manager.active_sessions,
    }


# --- Static file serving (production mode) ---

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.isdir(FRONTEND_DIST):
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        """Serve frontend static files in production mode."""
        file_path = os.path.join(FRONTEND_DIST, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


# --- Main entry point ---

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    reload = os.environ.get("ENV", "dev") == "dev"

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        log_level="info",
    )
