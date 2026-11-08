#!/usr/bin/env bash
set -u

CONFIG="$HOME/.config/waybar-aero"
DATA="$HOME/.local/share/ultimadesk"
LOGS="${XDG_STATE_HOME:-$HOME/.local/state}/ultimadesk"
mkdir -p "$LOGS"

for process in globe globo-layer quickshell eww ags hyprpanel; do
  pkill -x "$process" 2>/dev/null || true
done

"$CONFIG/start-wallpaper.sh" >>"$LOGS/wallpaper.log" 2>&1 &
"$CONFIG/start-waybar.sh" >>"$LOGS/waybar.log" 2>&1 &
if ! pgrep -f "^python3 $DATA/aero-shell.py --prewarm$" >/dev/null 2>&1; then
  nice -n 10 python3 "$DATA/aero-shell.py" --prewarm >>"$LOGS/control-center.log" 2>&1 &
fi
if ! pgrep -f "^python3 $DATA/aero-player.py --prewarm$" >/dev/null 2>&1; then
  nice -n 10 python3 "$DATA/aero-player.py" --prewarm >>"$LOGS/player.log" 2>&1 &
fi
if [[ -x "$DATA/globo-layer/globo-layer" ]]; then
  "$CONFIG/start-globo.sh" >>"$LOGS/globo.log" 2>&1 &
fi
if ! pgrep -x dunst >/dev/null 2>&1; then
  dunst --config "$DATA/dunstrc" >/dev/null 2>&1 &
fi
if ! pgrep -x hypridle >/dev/null 2>&1; then
  hypridle --config "$DATA/hypridle.conf" >/dev/null 2>&1 &
fi
if command -v wl-paste >/dev/null 2>&1 && command -v cliphist >/dev/null 2>&1 && ! pgrep -x wl-paste >/dev/null 2>&1; then
  wl-paste --watch cliphist store >/dev/null 2>&1 &
fi
