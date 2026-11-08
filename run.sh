#!/usr/bin/env bash
# One command to try Connect Suggests locally: venv + Fonecta's Yext mock + the ops console.
# Usage:  FONECTA_KIT=/path/to/FONECTA_CONNECT_SUGGESTS_2026 ./run.sh
# Optional: MOCK_PORT (default 8787), PORT (default 8800). Stop with Ctrl+C (stops both servers).
set -euo pipefail
cd "$(dirname "$0")"
KIT=${FONECTA_KIT:-../FONECTA_CONNECT_SUGGESTS_2026}
[ -d "$KIT/mock_api" ] || { echo "Set FONECTA_KIT to Fonecta's starter kit folder (FONECTA_CONNECT_SUGGESTS_2026)."; exit 1; }
export FONECTA_KIT=$(cd "$KIT" && pwd)
MOCK_PORT=${MOCK_PORT:-8787}; PORT=${PORT:-8800}
if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null; then uv venv -q --python 3.12 .venv && VIRTUAL_ENV=.venv uv pip install -q -r requirements.txt
  else python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; fi
fi
.venv/bin/python -m unittest discover app/tests 2>&1 | tail -1
.venv/bin/python "$FONECTA_KIT/mock_api/server.py" --port "$MOCK_PORT" >/tmp/connect_mock.log 2>&1 &
MOCK=$!; trap 'kill $MOCK 2>/dev/null' EXIT
echo "Yext mock on :$MOCK_PORT. Console: http://localhost:$PORT  (presenter view /demo?eid=FI-D0001, decision log /log)"
echo "In the console: 1 · Run detection, then 3 · Send and Simulate owner on any business."
YEXT_BASE_URL=http://localhost:$MOCK_PORT .venv/bin/python -m uvicorn app.main:app --port "$PORT"
