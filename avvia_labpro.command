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
sleep 2
open "http://localhost:$LABPRO_PORT"
wait "$server_pid"
