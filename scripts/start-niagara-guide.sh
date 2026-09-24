#!/usr/bin/env bash
# Serve the standalone Niagara 4 study guide on localhost.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCS_DIR="$PROJECT_DIR/docs"
GUIDE_FILE="$DOCS_DIR/niagara-study-guide.html"
PORT="${1:-8080}"

if [[ ! -f "$GUIDE_FILE" ]]; then
    echo "[niagara-guide] Missing guide: $GUIDE_FILE" >&2
    exit 1
fi

if [[ ! "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
    echo "[niagara-guide] Invalid port: $PORT (expected 1-65535)" >&2
    echo "[niagara-guide] Usage: scripts/start-niagara-guide.sh [port]" >&2
    exit 2
fi

URL="http://localhost:$PORT/niagara-study-guide.html"

echo "[niagara-guide] Starting local study-guide server"
echo "[niagara-guide] Open in your Windows browser:"
echo "[niagara-guide]   $URL"
echo "[niagara-guide]"
echo "[niagara-guide] Press Ctrl+C to stop."
echo

exec python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$DOCS_DIR"
