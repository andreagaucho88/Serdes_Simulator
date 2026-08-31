#!/bin/zsh
# SerDes Optical Lab PRO — interfaccia a pannelli con acquisizione continua
cd "$(dirname "$0")"
python -m labpro.server --port 8640 &
sleep 2
open "http://localhost:8640"
wait
