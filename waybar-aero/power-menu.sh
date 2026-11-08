#!/usr/bin/env bash
set -euo pipefail

THEME="$HOME/.local/share/ultimadesk/rofi.rasi"
choice="$(printf '%s\n' 'Bloquear sessao' 'Suspender' 'Encerrar Hyprland' 'Reiniciar computador' 'Desligar computador' | rofi -dmenu -i -p 'Energia' -theme "$THEME")"

case "$choice" in
  'Bloquear sessao') "$HOME/.config/waybar-aero/lock-screen.sh" ;;
  Suspender) systemctl suspend ;;
  'Encerrar Hyprland') hyprctl dispatch exit ;;
  'Reiniciar computador'|'Desligar computador')
    confirm="$(printf '%s\n' 'Cancelar' 'Confirmar' | rofi -dmenu -i -p "$choice?" -theme "$THEME")"
    [[ "$confirm" == Confirmar ]] || exit 0
    if [[ "$choice" == 'Reiniciar computador' ]]; then
      systemctl reboot
    else
      systemctl poweroff
    fi
    ;;
esac