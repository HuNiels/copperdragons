#!/usr/bin/env bash
# Run on the master (cde@copperdragons3).
# Usage:
#   ./send-test.sh fireball        # start a spell
#   ./send-test.sh void
#   ./send-test.sh stop            # stop
#   ./send-test.sh status          # what's currently running
#   ./send-test.sh spells          # list known spells
#
# Override slave/port with env vars:
#   SLAVE=raspberrypi PORT=8765 ./send-test.sh fireball
# Optional auth:
#   DISPLAY_API_KEY=... ./send-test.sh fireball

set -euo pipefail
SLAVE="${SLAVE:-raspberrypi}"
PORT="${PORT:-8765}"
BASE="http://${SLAVE}:${PORT}"

hdr=(-H "Content-Type: application/json")
if [[ -n "${DISPLAY_API_KEY:-}" ]]; then
  hdr+=(-H "X-API-Key: ${DISPLAY_API_KEY}")
fi

cmd="${1:-status}"
case "$cmd" in
  status)  curl -sS "${hdr[@]}" "$BASE/status" ;;
  spells)  curl -sS "${hdr[@]}" "$BASE/spells" ;;
  stop)    curl -sS "${hdr[@]}" -X POST "$BASE/stop" ;;
  *)
    curl -sS "${hdr[@]}" -X POST "$BASE/spell" \
      --data "$(python3 -c "import json,sys;print(json.dumps({'spell':sys.argv[1]}))" "$cmd")"
    ;;
esac
echo
