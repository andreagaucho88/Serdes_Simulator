#!/bin/zsh
# Avvio del simulatore didattico SerDes + link ottico (doppio click su macOS)
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || command -v python)}"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Python not found. Activate the project environment and retry."
  exit 1
fi
"$PYTHON_BIN" -m streamlit run app/main.py
