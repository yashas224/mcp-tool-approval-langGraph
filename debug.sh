#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

cleanup() {
    echo "Stopping services..."
    kill "$WEBSERVER_PID" "$API_PID" "$STREAMLIT_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

uv run mcp-servers/websearchserver.py &
WEBSERVER_PID=$!

uv run --with debugpy python -m debugpy --listen 5678 --wait-for-client \
  -m uvicorn --app-dir mcp-client client:app --host 127.0.0.1 --port 8000 \
  --log-level debug &
API_PID=$!

uv run streamlit run streamlit_app.py &
STREAMLIT_PID=$!

wait