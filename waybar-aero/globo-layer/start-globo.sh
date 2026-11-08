#!/usr/bin/env bash
# Inicia o globo interativo (camada de fundo do Hyprland).
D="$HOME/.local/share/ultimadesk/globo-layer"
pkill -x globo-layer 2>/dev/null
[ -x "$D/globo-layer" ] || { echo "globo-layer nao compilado: rode globo-layer/build.sh"; exit 1; }
exec "$D/globo-layer" --cx 80 --mask "$D/mask.bin" --countries "$D/countries.tsv" "$@"
