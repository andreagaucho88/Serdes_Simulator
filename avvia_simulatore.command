#!/bin/zsh
# Avvio del simulatore didattico SerDes + link ottico (doppio click su macOS)
cd "$(dirname "$0")"
python -m streamlit run app/main.py
