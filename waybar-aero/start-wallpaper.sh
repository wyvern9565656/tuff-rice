#!/usr/bin/env bash
# O wallpaper pessoal tem prioridade; os arquivos do rice sao fallback.
D="$HOME/.config/waybar-aero"
pkill -x swaybg 2>/dev/null
SELECTED="${XDG_STATE_HOME:-$HOME/.local/state}/ultimadesk/wallpaper-selected"
if [[ -f "$SELECTED" ]]; then
  WALLPAPER="$(<"$SELECTED")"
  if [[ "$WALLPAPER" == "$HOME/Imagens/wallpapers/"* && -f "$WALLPAPER" ]]; then
    exec swaybg -i "$WALLPAPER" -m fill
  fi
fi
if [[ -f "$HOME/Imagens/aero.png" ]]; then
  exec swaybg -i "$HOME/Imagens/aero.png" -m fill
fi
for f in "$D"/wallpaper.png "$D"/wallpaper.jpg "$D"/wallpaper.jpeg "$D"/wallpaper.webp; do
  if [ -f "$f" ]; then exec swaybg -i "$f" -m fill; fi
done
exec swaybg -c "#7fc8f0"
