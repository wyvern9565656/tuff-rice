#!/usr/bin/env bash
# Somente LEITURA: lista o que sobrou do rice antigo. Nao altera nada.
# Salva uma copia em ~/inventario-rice.txt
CFG="$HOME/.config"

{
echo "== 1. Pastas de rice/Hyprland em ~/.config (tamanho) =="
for d in hypr waybar eww ags astal quickshell hyprpanel wlogout swaync mako dunst wofi rofi fuzzel \
         swayosd nwg-panel nwg-dock-hyprland nwg-drawer nwg-look swappy hyprshot cava fastfetch \
         kitty alacritty foot wezterm ghostty starship matugen wallust wal; do
  if [ -e "$CFG/$d" ]; then du -sh "$CFG/$d" 2>/dev/null; fi
done

echo
echo "== 2. 25 itens de ~/.config mexidos mais recentemente =="
ls -lt --time-style=long-iso "$CFG" 2>/dev/null | head -26

echo
echo "== 3. Servicos de usuario habilitados =="
systemctl --user list-unit-files --state=enabled 2>/dev/null | head -40

echo
echo "== 4. Autostart (XDG) =="
ls "$CFG/autostart" 2>/dev/null || echo "(vazio)"

echo
echo "== 5. Pacotes relacionados =="
if command -v pacman >/dev/null 2>&1; then
  pacman -Qq | grep -iE '^(hypr|waybar|eww|ags|aylurs|astal|quickshell|swww|swaybg|wlogout|swaync|mako|dunst|wofi|rofi|fuzzel|cliphist|grim|slurp|swappy|brightnessctl|playerctl|python-pywal|wallust|matugen|nwg|cava|fastfetch|xdg-desktop-portal-hyprland)' || echo "(nenhum)"
  echo
  echo "-- Pacotes de fora dos repositorios oficiais (AUR etc.) --"
  pacman -Qm
fi

echo
echo "== 6. Linhas de shell que citam o rice =="
grep -nEi 'hypr|waybar|eww|ags |pywal|wallust|matugen|fastfetch|neofetch' \
  "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.config/fish/config.fish" "$HOME/.profile" "$HOME/.zprofile" 2>/dev/null \
  || echo "(nenhuma)"

echo
echo "== 7. Scripts pessoais =="
ls "$HOME/.local/bin" "$HOME/bin" "$HOME/scripts" "$HOME/Scripts" 2>/dev/null || echo "(nenhum encontrado)"
} 2>&1 | tee "$HOME/inventario-rice.txt"

echo
echo "Copia salva em ~/inventario-rice.txt"
