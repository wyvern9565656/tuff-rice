#!/usr/bin/env bash
# Inicia as barras do UltimaDesk sem encerrar outros paineis do usuario.
pkill -x waybar 2>/dev/null || true
exec waybar -c "$HOME/.config/waybar-aero/config.jsonc" -s "$HOME/.config/waybar-aero/style.css"
