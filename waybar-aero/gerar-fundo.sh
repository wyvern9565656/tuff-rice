#!/usr/bin/env bash
# Gera o papel de parede Frutiger Aero (ceu, nuvens, bolhas, colinas) em ~/.config/waybar-aero/wallpaper.png
# Para usar sua propria imagem, basta copiar ela pra la com o nome wallpaper.png (ou .jpg).
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
sudo pacman -S --needed --noconfirm python-pillow
python3 "$HERE/render_globe.py" --bg-only "$HOME/.config/waybar-aero/wallpaper.png" "$@"
echo "Agora reinicie o papel de parede:  ~/.config/waybar-aero/start-wallpaper.sh &"
