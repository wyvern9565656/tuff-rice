#!/usr/bin/env bash
set -euo pipefail

THEME="$HOME/.local/share/ultimadesk/rofi.rasi"
choice="${1:-}"
if [[ -z "$choice" ]]; then
  choice="$(printf '%s\n' 'Area para clipboard' 'Area para arquivo' 'Tela inteira para clipboard' 'Tela inteira para arquivo' | rofi -dmenu -i -p 'Captura' -theme "$THEME")"
fi
[[ -n "$choice" ]] || exit 0

mkdir -p "$HOME/Pictures/Screenshots"
target="$HOME/Pictures/Screenshots/$(date +%Y-%m-%d_%H-%M-%S).png"
area=""
case "$choice" in
  'Area para clipboard'|'Area para arquivo')
    area="$(slurp)" || exit 0
    [[ -n "$area" ]] || exit 0
    ;;
esac

case "$choice" in
  'Area para clipboard') grim -g "$area" - | wl-copy --type image/png ;;
  'Area para arquivo') grim -g "$area" "$target" ;;
  'Tela inteira para clipboard') grim - | wl-copy --type image/png ;;
  'Tela inteira para arquivo') grim "$target" ;;
  *) exit 0 ;;
esac

if [[ "$choice" == *arquivo ]]; then
  notify-send 'Captura salva' "$target"
else
  notify-send 'Captura copiada' 'Imagem enviada para a area de transferencia.'
fi