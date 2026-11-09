#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BAR="$ROOT/waybar-aero"
HOME_CONFIG="$HOME/.config"
HYPR="$HOME_CONFIG/hypr"
CONFIG="$HOME_CONFIG/waybar-aero"
DATA="$HOME/.local/share/ultimadesk"
MODE=lua
INSTALL_OPTIONAL_APPS=false
PLAN_ONLY=false

usage() {
  cat <<'USAGE'
Uso: ./install.sh [opcoes]

Opcoes:
  --install-optional-apps  Instala Firefox, Kitty e Thunar
  --hypr-mode MODE         Usa lua (padrao) ou conf legado (Hyprland < 0.57)
  --plan                   Mostra pacotes e servicos sem fazer alteracoes
  -h, --help               Mostra esta ajuda

Sem --install-optional-apps, os aplicativos de usuario nao sao instalados.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-optional-apps)
      INSTALL_OPTIONAL_APPS=true
      shift
      ;;
    --plan)
      PLAN_ONLY=true
      shift
      ;;
    --hypr-mode)
      if [[ $# -lt 2 ]]; then
        echo "Falta o valor de --hypr-mode (lua ou conf)." >&2
        exit 2
      fi
      MODE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Opcao desconhecida: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$MODE" != lua && "$MODE" != conf ]]; then
  echo "Modo Hyprland invalido: $MODE (use lua ou conf)." >&2
  exit 2
fi

if [[ "$EUID" -eq 0 ]]; then
  echo "Execute como usuario normal; o instalador usa sudo quando necessario."
  exit 1
fi
if ! command -v pacman >/dev/null 2>&1; then
  echo "Este instalador requer Arch Linux ou uma derivada com pacman."
  exit 1
fi

required_packages=(
  base-devel brightnessctl bluez bluez-utils cliphist curl dunst gcc grim gtk3 hypridle imagemagick \
  hyprlock libnotify networkmanager pipewire pipewire-pulse playerctl \
  jq pkgconf python-gobject python-pillow rofi-wayland slurp socat swaybg ttf-jetbrains-mono-nerd \
  ttf-opensans waybar wayland wayland-protocols wlr-protocols wl-clipboard wireplumber xdg-utils
)
optional_apps=(firefox kitty thunar)
packages=("${required_packages[@]}")
if [[ "$INSTALL_OPTIONAL_APPS" == true ]]; then
  packages+=("${optional_apps[@]}")
  echo "Aplicativos opcionais selecionados: ${optional_apps[*]}"
else
  echo "Aplicativos opcionais nao selecionados: ${optional_apps[*]}"
fi

mapfile -t installed_package_names < <(pacman -Qq)
declare -A installed_package_set=()
for package in "${installed_package_names[@]}"; do
  installed_package_set["$package"]=1
done
installed_packages=()
missing_packages=()
for package in "${packages[@]}"; do
  if [[ -n "${installed_package_set[$package]:-}" ]]; then
    installed_packages+=("$package")
  else
    missing_packages+=("$package")
  fi
done

print_package_list() {
  local heading="$1"
  shift
  printf '%s (%d):\n' "$heading" "$#"
  if [[ "$#" -eq 0 ]]; then
    echo "  nenhum"
  else
    printf '  %s\n' "$@"
  fi
}

service_plan() {
  local scope="$1" unit="$2" active enabled active_status enabled_status action
  local -a systemctl_command=(systemctl)
  if [[ "$scope" == user ]]; then
    systemctl_command+=(--user)
  fi
  active="$("${systemctl_command[@]}" is-active "$unit" 2>/dev/null || true)"
  enabled="$("${systemctl_command[@]}" is-enabled "$unit" 2>/dev/null || true)"
  if [[ "$active" == active ]]; then
    active_status="ativo"
  else
    active_status="inativo"
  fi
  if [[ "$enabled" == enabled || "$enabled" == enabled-runtime ]]; then
    enabled_status="habilitado"
  else
    enabled_status="desabilitado/indisponivel"
  fi
  if [[ "$active" == active && ( "$enabled" == enabled || "$enabled" == enabled-runtime ) ]]; then
    action="sem alteracao"
  else
    action="sera habilitado e iniciado"
  fi
  printf '  %s (%s): %s, %s; %s\n' "$unit" "$scope" "$active_status" "$enabled_status" "$action"
}

echo "==> Resumo antes de alterar o sistema (modo Hyprland: $MODE)..."
print_package_list "Pacotes ja instalados" "${installed_packages[@]}"
print_package_list "Pacotes que faltam" "${missing_packages[@]}"
echo "Servicos que serao verificados/ativados apos instalar os pacotes:"
service_plan system NetworkManager.service
service_plan system bluetooth.service
service_plan user pipewire.socket
service_plan user pipewire-pulse.socket
service_plan user wireplumber.service
if [[ "$PLAN_ONLY" == true ]]; then
  echo "Plano concluido; nenhuma instalacao, ativacao de servico ou alteracao de arquivo foi feita."
  exit 0
fi

echo "==> Instalando dependencias do rice e controles..."
sudo pacman -S --needed --noconfirm "${packages[@]}"

echo "==> Ativando NetworkManager, Bluetooth e audio..."
sudo systemctl enable --now NetworkManager.service bluetooth.service
systemctl --user enable --now pipewire.socket pipewire-pulse.socket wireplumber.service || \
  echo "Aviso: nao consegui ativar os sockets do PipeWire nesta sessao."

mkdir -p "$CONFIG" "$HYPR" "$DATA"

echo "==> Instalando centro de controle e configuracao Waybar..."
backup_if_custom() {
  local source="$1" target="$2"
  if [[ -f "$target" ]] && ! cmp -s "$source" "$target"; then
    cp -p "$target" "$target.backup-$(date +%Y%m%d-%H%M%S)"
  fi
}
backup_if_custom "$BAR/waybar/config.jsonc" "$CONFIG/config.jsonc"
backup_if_custom "$BAR/waybar/style.css" "$CONFIG/style.css"
install -Dm644 "$BAR/waybar/config.jsonc" "$CONFIG/config.jsonc"
install -Dm644 "$BAR/waybar/style.css" "$CONFIG/style.css"
install -Dm644 "$BAR/rofi.rasi" "$DATA/rofi.rasi"
install -Dm755 "$BAR/aero-launcher.sh" "$CONFIG/aero-launcher.sh"
install -Dm755 "$BAR/aero-control.sh" "$CONFIG/aero-control.sh"
install -Dm755 "$BAR/aero-player.sh" "$CONFIG/aero-player.sh"
install -Dm755 "$BAR/player-control.sh" "$CONFIG/player-control.sh"
install -Dm755 "$BAR/bluetooth-status.sh" "$CONFIG/bluetooth-status.sh"
install -Dm755 "$BAR/notification-status.sh" "$CONFIG/notification-status.sh"
install -Dm755 "$BAR/start-waybar.sh" "$CONFIG/start-waybar.sh"
install -Dm755 "$BAR/workspace-button.sh" "$CONFIG/workspace-button.sh"
install -Dm755 "$BAR/start-wallpaper.sh" "$CONFIG/start-wallpaper.sh"
install -Dm755 "$BAR/wallpaper-carousel.sh" "$CONFIG/wallpaper-carousel.sh"
install -Dm755 "$BAR/globo-layer/start-globo.sh" "$CONFIG/start-globo.sh"
install -Dm755 "$BAR/start-shortcuts.sh" "$CONFIG/start-shortcuts.sh"
install -Dm755 "$BAR/start-rice.sh" "$CONFIG/start-rice.sh"
install -Dm755 "$BAR/power-menu.sh" "$CONFIG/power-menu.sh"
install -Dm755 "$BAR/screenshot-menu.sh" "$CONFIG/screenshot-menu.sh"
install -Dm755 "$BAR/lock-screen.sh" "$CONFIG/lock-screen.sh"
install -Dm755 "$ROOT/aero-shell.py" "$DATA/aero-shell.py"
install -Dm755 "$ROOT/aero-launcher.py" "$DATA/aero-launcher.py"
install -Dm755 "$ROOT/aero-workspaces.py" "$DATA/aero-workspaces.py"
install -Dm755 "$BAR/wallpaper-carousel.py" "$DATA/wallpaper-carousel.py"
install -Dm755 "$ROOT/waybar-aero/aero-player.py" "$DATA/aero-player.py"
install -Dm644 "$ROOT/aero_window.py" "$DATA/aero_window.py"
install -Dm644 "$ROOT/aero_backend.py" "$DATA/aero_backend.py"
install -Dm644 "$ROOT/aero_css.py" "$DATA/aero_css.py"
install -Dm644 "$BAR/dunstrc" "$DATA/dunstrc"
install -Dm644 "$BAR/hypridle.conf" "$DATA/hypridle.conf"
install -Dm644 "$BAR/lock-avatar.png" "$DATA/lock-avatar.png"
install -Dm644 "$BAR/lock-cover.png" "$DATA/lock-cover.png"
install -Dm755 "$BAR/lock-status.sh" "$DATA/lock-status.sh"
backup_if_custom "$BAR/hyprlock.conf" "$HYPR/hyprlock.conf"
install -Dm644 "$BAR/hyprlock.conf" "$HYPR/hyprlock.conf"

echo "==> Gerando papel de parede Frutiger Aero..."
WALLPAPER_EXISTS=false
for extension in png jpg jpeg webp; do
  if [[ -f "$CONFIG/wallpaper.$extension" ]]; then
    WALLPAPER_EXISTS=true
    break
  fi
done
if [[ "$WALLPAPER_EXISTS" == false ]]; then
  python3 "$BAR/render_globe.py" --bg-only "$CONFIG/wallpaper.png"
else
  echo "Wallpaper existente preservado."
fi

echo "==> Compilando o globo interativo..."
GLOBE="$DATA/globo-layer"
mkdir -p "$GLOBE"
install -Dm644 "$BAR/globo-layer/main.c" "$GLOBE/main.c"
install -Dm644 "$BAR/globo-layer/render.c" "$GLOBE/render.c"
install -Dm644 "$BAR/globo-layer/render.h" "$GLOBE/render.h"
install -Dm755 "$BAR/globo-layer/make_mask.py" "$GLOBE/make_mask.py"
XDG_XML="$(find /usr/share/wayland-protocols -name xdg-shell.xml -print -quit 2>/dev/null || true)"
WLR_XML="$(find /usr/share/wlr-protocols -name wlr-layer-shell-unstable-v1.xml -print -quit 2>/dev/null || true)"
if [[ -z "$XDG_XML" || -z "$WLR_XML" ]]; then
  echo "Aviso: protocolos Wayland nao encontrados; o globo interativo sera ignorado."
elif (
  cd "$GLOBE"
  wayland-scanner client-header "$XDG_XML" xdg-shell-client-protocol.h &&
  wayland-scanner private-code "$XDG_XML" xdg-shell-protocol.c &&
  wayland-scanner client-header "$WLR_XML" wlr-layer-shell-unstable-v1-client-protocol.h &&
  wayland-scanner private-code "$WLR_XML" wlr-layer-shell-unstable-v1-protocol.c &&
  python3 make_mask.py ne_110m_admin_0_countries.geojson mask.bin &&
  gcc -O2 -Wall -o globo-layer main.c render.c xdg-shell-protocol.c \
    wlr-layer-shell-unstable-v1-protocol.c $(pkg-config --cflags --libs wayland-client cairo) -lm
); then
  echo "Globo compilado em $GLOBE/globo-layer."
else
  echo "Aviso: nao consegui gerar/compilar o globo; barras, controles e wallpaper continuam ativos."
fi

write_managed_block() {
  local target="$1" start="$2" end="$3" block="$4" temp
  temp="$(mktemp "${target}.XXXXXX")"
  if [[ -f "$target" ]]; then
    if ! awk -v start="$start" -v end="$end" '
      $0 == start { inside = 1; next }
      $0 == end { inside = 0; next }
      !inside { print }
      END { if (inside) exit 2 }
    ' "$target" > "$temp"; then
      rm -f "$temp"
      echo "Bloco gerenciado incompleto em $target; arquivo preservado."
      return 1
    fi
    chmod --reference="$target" "$temp"
  else
    : > "$temp"
    chmod 644 "$temp"
  fi
  printf '\n%s\n' "$block" >> "$temp"
  mv "$temp" "$target"
}

if [[ "$MODE" == conf ]]; then
  MONITOR_RULES="$(kscreen-doctor -o 2>/dev/null | sed -E 's/\x1B\[[0-9;]*[[:alpha:]]//g' | awk '
    /^Output:/ { name = $3 }
    /Modes:/ {
      for (i = 1; i <= NF; i++) {
        if (index($i, "*!") > 0) {
          mode = $i
          sub(/^[0-9]+:/, "", mode)
          sub(/\*![[:space:]]*$/, "", mode)
          printf "monitor = %s, %s, auto, 1\n", name, mode
        }
      }
    }
  ')"
  if [[ -z "$MONITOR_RULES" ]]; then
    MONITOR_RULES="monitor = , preferred, auto, 1"
  fi
  WORKSPACE_RULES="$(for workspace in {1..10}; do printf 'workspace = %s, persistent:true\n' "$workspace"; done)"
  HYPR_BLOCK="$(cat <<HYPRCONF
# >>> UltimaDesk managed >>>
${MONITOR_RULES}
${WORKSPACE_RULES}
decoration {
  rounding = 18
}
exec-once = $HOME/.config/waybar-aero/start-rice.sh
windowrule = match:class ^aero-shell[.]py$, float = true
windowrule = match:class ^aero-shell[.]py$, border_size 0
windowrule = float on, match:class ^aero-launcher[.]py$
windowrule = border_size 0, match:class ^aero-launcher[.]py$
windowrule = match:class ^aero-workspaces[.]py$, float = true
windowrule = match:class ^aero-workspaces[.]py$, border_size 0
windowrule = float on, match:class ^aero-player[.]py$
windowrule = match:class ^aero-player[.]py$, border_size 0
windowrule = match:title ^UltimaDesk$, size 420 340
windowrule = match:title ^UltimaDesk Wi-Fi$, size 420 420
windowrule = match:title ^UltimaDesk Bluetooth$, size 420 420
windowrule = match:title ^UltimaDesk Audio$, size 420 400
windowrule = match:title ^Centro de controle$, size 460 520
windowrule = match:title ^Notificacoes$, size 480 560
windowrule = match:title ^Calendario$, size 366 410
windowrule = match:title ^UltimaDesk Player$, size 342 470
# <<< UltimaDesk managed <<<
HYPRCONF
)"
  if [[ -f "$HYPR/ultimadesk.conf" ]] && ! grep -Fq '# >>> UltimaDesk managed >>>' "$HYPR/ultimadesk.conf"; then
    mv "$HYPR/ultimadesk.conf" "$HYPR/ultimadesk.conf.backup-$(date +%Y%m%d-%H%M%S)"
  fi
  write_managed_block "$HYPR/ultimadesk.conf" \
    "# >>> UltimaDesk managed >>>" "# <<< UltimaDesk managed <<<" "$HYPR_BLOCK"
  touch "$HYPR/hyprland.conf"
  if ! grep -Fq 'source = ~/.config/hypr/ultimadesk.conf' "$HYPR/hyprland.conf"; then
    printf '\n# UltimaDesk\nsource = ~/.config/hypr/ultimadesk.conf\n' >> "$HYPR/hyprland.conf"
  fi
else
  LUA_BLOCK="$(<"$BAR/hypr/ultimadesk.lua")"
  MAIN_LUA_BLOCK="$(<"$BAR/hypr/hyprland.lua")"
  if [[ -f "$HYPR/ultimadesk.lua" ]] && ! grep -Fq -- '-- >>> UltimaDesk managed >>>' "$HYPR/ultimadesk.lua"; then
    mv "$HYPR/ultimadesk.lua" "$HYPR/ultimadesk.lua.backup-$(date +%Y%m%d-%H%M%S)"
  fi
  if [[ -f "$HYPR/hyprland.lua" ]] && ! grep -Fq -- '-- >>> UltimaDesk managed >>>' "$HYPR/hyprland.lua"; then
    cp -p "$HYPR/hyprland.lua" "$HYPR/hyprland.lua.backup-$(date +%Y%m%d-%H%M%S)"
  fi
  write_managed_block "$HYPR/ultimadesk.lua" \
    "-- >>> UltimaDesk managed >>>" "-- <<< UltimaDesk managed <<<" "$LUA_BLOCK"
  write_managed_block "$HYPR/hyprland.lua" \
    "-- >>> UltimaDesk managed >>>" "-- <<< UltimaDesk managed <<<" "$MAIN_LUA_BLOCK"
fi

echo
echo "Instalacao concluida. O rice iniciara na proxima sessao Hyprland."
echo "Centro de controle: Super+I | Aplicativos: Super+D | Terminal: Super+Enter (Kitty opcional)"
echo "Arquivos: Super+E (Thunar opcional)"
echo "Wi-Fi, Bluetooth, audio, brilho, clipboard, captura e bloqueio estao no painel/atalhos."
if [[ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]]; then
  "$CONFIG/start-rice.sh" >/dev/null 2>&1 &
  echo "Rice iniciado tambem na sessao Hyprland atual."
fi