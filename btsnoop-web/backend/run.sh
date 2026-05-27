#!/usr/bin/env bash
# Start the btsnoop web parser backend server.
#
# Usage:
#   ./run.sh          - Start in development mode (with auto-reload)
#   ./run.sh prod     - Start in production mode (no reload)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-1}"

# Ensure dependencies are available
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "[run.sh] Installing dependencies..."
    pip install -r requirements.txt
fi

if [ "${1:-}" = "prod" ]; then
    echo "[run.sh] Starting production server on ${HOST}:${PORT} with ${WORKERS} worker(s)..."
    exec uvicorn server:app \
        --host "$HOST" \
        --port "$PORT" \
        --workers "$WORKERS" \
        --log-level info
else
    echo "[run.sh] Starting development server on ${HOST}:${PORT} (auto-reload enabled)..."
    exec uvicorn server:app \
        --host "$HOST" \
        --port "$PORT" \
        --reload \
        --log-level debug
fi
