#!/usr/bin/env bash
# One command to try Connect Suggests locally: venv + Fonecta's Yext mock + the ops console.
# Usage:  FONECTA_KIT=/path/to/FONECTA_CONNECT_SUGGESTS_2026 ./run.sh
# Optional: MOCK_PORT (default 8787), PORT (default 8800). Stop with Ctrl+C (stops both servers).
set -euo pipefail
cd "$(dirname "$0")"
KIT=${FONECTA_KIT:-../FONECTA_CONNECT_SUGGESTS_2026}
# The challenge pack arrives as a zip inside a zip: FONECTA_KIT may point at either zip, or at any folder holding the kit.
if [ -f "$KIT" ] && [[ "$KIT" == *.zip ]]; then
  OUT="$(dirname "$KIT")/$(basename "$KIT" .zip)"; mkdir -p "$OUT" && unzip -qo "$KIT" -d "$OUT"; KIT=$OUT
fi
find_kit() { find "$1" -maxdepth 4 -type d -name mock_api 2>/dev/null | head -1 | xargs -I{} dirname {}; }
if [ -d "$KIT" ] && [ ! -d "$KIT/mock_api" ]; then
  FOUND=$(find_kit "$KIT")
  if [ -z "$FOUND" ]; then
    INNER=$(find "$KIT" -maxdepth 3 -name 'FONECTA_CONNECT_SUGGESTS_2026*.zip' | head -1)
    [ -n "$INNER" ] && unzip -qo "$INNER" -d "$(dirname "$INNER")" && FOUND=$(find_kit "$KIT")
  fi
  [ -n "$FOUND" ] && KIT=$FOUND
fi
[ -d "$KIT/mock_api" ] || { echo "Starter kit not found at $KIT."
  echo "Set FONECTA_KIT to Fonecta's challenge pack (the zip, or the unzipped FONECTA_CONNECT_SUGGESTS_2026 folder): FONECTA_KIT=/path/to/kit ./run.sh"
  echo "No kit? The same flow runs in the browser, no login: https://demo.zahar.io"; exit 1; }
export FONECTA_KIT=$(cd "$KIT" && pwd)
MOCK_PORT=${MOCK_PORT:-8787}; PORT=${PORT:-8800}
for p in "$PORT" "$MOCK_PORT"; do
  (exec 3<>"/dev/tcp/127.0.0.1/$p") 2>/dev/null && { echo "Port $p is already in use (an earlier run still going?). Stop it, or pick others: PORT=8810 MOCK_PORT=8797 ./run.sh"; exit 1; }
done
if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null; then uv venv -q --python 3.12 .venv && VIRTUAL_ENV=.venv uv pip install -q -r requirements.txt
  else python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; fi
fi
.venv/bin/python -m unittest discover app/tests 2>&1 | tail -3 | grep -E "^(Ran|OK|FAILED)"
.venv/bin/python "$FONECTA_KIT/mock_api/server.py" --port "$MOCK_PORT" >/tmp/connect_mock.log 2>&1 &
MOCK=$!; trap 'kill $MOCK 2>/dev/null' EXIT
echo "Yext mock on :$MOCK_PORT. Console: http://localhost:$PORT  (presenter view /demo?eid=FI-D0001, decision log /log)"
echo "In the console: 1 · Run detection (takes about 25 s), then 3 · Send and Simulate owner on any business."
YEXT_BASE_URL=http://localhost:$MOCK_PORT .venv/bin/python -m uvicorn app.main:app --port "$PORT"
