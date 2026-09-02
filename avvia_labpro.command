#!/bin/zsh
# SerDes Optical Lab PRO — interfaccia a pannelli con acquisizione continua
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || command -v python)}"
LABPRO_PORT="${LABPRO_PORT:-8640}"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Python not found. Activate the project environment and retry."
  exit 1
fi
"$PYTHON_BIN" -m labpro.server --port "$LABPRO_PORT" &
server_pid=$!

cleanup_server() {
  if kill -0 "$server_pid" 2>/dev/null; then
    kill -TERM "$server_pid" 2>/dev/null
    wait "$server_pid" 2>/dev/null
  fi
}
interrupted() {
  trap - INT TERM
  cleanup_server
  exit 130
}
trap cleanup_server EXIT
trap interrupted INT TERM

# Wait for Tornado itself to report readiness. A fixed sleep was unreliable on
# cold environments and opened a blank/error page when startup failed.
ready=0
for attempt in {1..80}; do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    wait "$server_pid"
    exit $?
  fi
  if /usr/bin/curl --silent --fail --max-time 1 \
      "http://127.0.0.1:$LABPRO_PORT/api/health" >/dev/null; then
    ready=1
    break
  fi
  sleep 0.25
done
if [[ "$ready" -ne 1 ]]; then
  echo "Lab PRO did not become ready on port $LABPRO_PORT."
  kill "$server_pid" 2>/dev/null
  wait "$server_pid" 2>/dev/null
  exit 1
fi
open "http://localhost:$LABPRO_PORT"
wait "$server_pid"
