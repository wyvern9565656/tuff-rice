#!/usr/bin/env bash
# Coleta informacoes pra diagnostico. Rode DENTRO da sessao Hyprland (num terminal de la).
OUT="$HOME/diagnostico-aero.txt"
{
echo "== sessao =="; echo "desktop=$XDG_CURRENT_DESKTOP session=$XDG_SESSION_TYPE hypr_sig=${HYPRLAND_INSTANCE_SIGNATURE:-<vazio>}"
echo; echo "== processos =="; pgrep -a -f 'quickshell|waybar|swaybg|mpvpaper|dunst|hypridle|hyprlock|eww|ags|hyprpanel|plasmashell' || echo "(nenhum)"
echo; echo "== ~/.config/hypr =="; ls -la ~/.config/hypr
echo; echo "== onde o UltimaDesk e carregado =="; grep -n -i 'ultimadesk' ~/.config/hypr/*.lua ~/.config/hypr/*.conf 2>/dev/null || echo "(nenhuma referencia)"
echo; echo "== versoes =="; hyprctl version 2>&1 | head -3; waybar --version 2>&1 | head -1
echo; echo "== camadas (barras/papel de parede) =="; hyprctl layers 2>&1 | head -40
echo; echo "== workspaces =="; hyprctl workspaces 2>&1 | head -20
echo; echo "== waybar (4 s de log) =="; timeout 4 waybar -c ~/.config/waybar-aero/config.jsonc -s ~/.config/waybar-aero/style.css -l warning 2>&1 | head -40
} 2>&1 | tee "$OUT"
echo; echo "Salvo em $OUT"
