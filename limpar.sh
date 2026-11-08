#!/usr/bin/env bash
set -euo pipefail

CONFIG="$HOME/.config"

echo "Removendo configuracoes do Hyprland e paineis/rice associados, sem backup..."

for process in globe globo-layer waybar quickshell eww ags hyprpanel swaync mako dunst hypridle swaybg; do
  pkill -x "$process" 2>/dev/null || true
done

config_dirs=(
  hypr hyprland hyprpaper hypridle hyprlock hyprsunset hyprshade hyprpicker hyprshot
  waybar waybar-aero eww ags astal quickshell hyprpanel wlogout swaync mako dunst
  wofi rofi fuzzel swayosd nwg-panel nwg-dock-hyprland nwg-drawer swappy matugen
  wal wallust illogical-impulse
)

for name in "${config_dirs[@]}"; do
  if [[ -e "$CONFIG/$name" || -L "$CONFIG/$name" ]]; then
    rm -rf -- "$CONFIG/$name"
    printf 'Removido: %s\n' "$CONFIG/$name"
  fi
done

for path in "$CONFIG/hyprland.conf" "$CONFIG/hyprland.lua" \
  "$HOME/.local/share/ultimadesk" "$HOME/.local/state/quickshell" "$HOME/.cache/quickshell"; do
  if [[ -e "$path" || -L "$path" ]]; then
    rm -rf -- "$path"
    printf 'Removido: %s\n' "$path"
  fi
done

echo "Limpeza concluida. Nenhum backup foi criado; o Hyprland precisara de uma nova configuracao para voltar a iniciar."