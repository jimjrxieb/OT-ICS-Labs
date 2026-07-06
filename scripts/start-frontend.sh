#!/usr/bin/env bash
# Start the synthetic hospital BAS front-end server on port 8001.
set -euo pipefail

SLOT3="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SLOT3"

if ! python3 -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "[start-frontend] Missing FastAPI/Uvicorn dependencies."
    echo "[start-frontend] Install explicitly with: pip install -r requirements.txt"
    exit 1
fi

echo "[start-frontend] Starting BAS front-end at http://localhost:8001"
echo "[start-frontend]   Metasys view : http://localhost:8001/metasys"
echo "[start-frontend]   Niagara view : http://localhost:8001/niagara"
echo "[start-frontend]   API docs     : http://localhost:8001/docs"
echo ""

python3 -m uvicorn frontend.bas_api:app --host 127.0.0.1 --port 8001 --reload
