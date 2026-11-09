#!/usr/bin/env bash
set -euo pipefail

CONFIG="$HOME/.config"
DATA="$HOME/.local/share/ultimadesk"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}"
BACKUP=1
YES=0
DRY_RUN=0
BACKUP_DIR=""

usage() {
  cat <<'USAGE'
Uso: ./limpar.sh [opcoes]

Remove apenas os arquivos e blocos gerenciados pelo UltimaDesk.
Por padrao, cria backup e pede confirmacao.

Opcoes:
  --dry-run     Mostra o que seria removido, sem alterar arquivos ou processos
  --yes         Executa sem pedir confirmacao
  --no-backup   Nao cria backup (use com cuidado)
  -h, --help    Mostra esta ajuda
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --yes) YES=1 ;;
    --no-backup) BACKUP=0 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Opcao desconhecida: %s\n' "$arg" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$YES" -eq 0 && "$DRY_RUN" -eq 0 ]]; then
  if [[ ! -t 0 ]]; then
    echo "A limpeza precisa de confirmacao interativa; use --yes para confirmar explicitamente." >&2
    exit 2
  fi
  read -r -p "Remover somente os arquivos do UltimaDesk? O restante do Hyprland sera preservado [s/N] " answer
  [[ "$answer" =~ ^[sS]([iI][mM])?$ ]] || { echo "Limpeza cancelada."; exit 0; }
fi

path_exists() {
  [[ -e "$1" || -L "$1" ]]
}

backup_path() {
  local source="$1" relative="$2" destination
  [[ "$BACKUP" -eq 1 ]] || return 0
  if [[ -z "$BACKUP_DIR" ]]; then
    mkdir -p -- "$STATE/ultimadesk-backups"
    BACKUP_DIR="$(mktemp -d "$STATE/ultimadesk-backups/$(date +%Y%m%d-%H%M%S)-XXXXXX")"
  fi
  destination="$BACKUP_DIR/$relative"
  mkdir -p -- "$(dirname -- "$destination")"
  cp -a -- "$source" "$destination"
}

remove_path() {
  local source="$1" relative="$2"
  path_exists "$source" || return 0
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'Removeria: %s\n' "$source"
    return 0
  fi
  backup_path "$source" "$relative"
  rm -rf -- "$source"
  printf 'Removido: %s\n' "$source"
}

remove_managed_block() {
  local file="$1" relative="$2" start="$3" end="$4" temporary
  [[ -f "$file" ]] || return 0
  grep -Fqx -- "$start" "$file" || return 0
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'Removeria o bloco gerenciado em: %s\n' "$file"
    return 0
  fi
  backup_path "$file" "$relative"
  temporary="$(mktemp "${file}.XXXXXX")"
  if ! awk -v start="$start" -v end="$end" '
    $0 == start { if (inside) failed = 1; inside = 1; found = 1; next }
    $0 == end { if (!inside) failed = 1; inside = 0; next }
    !inside { print }
    END { if (inside || failed || !found) exit 2 }
  ' "$file" > "$temporary"; then
    rm -f -- "$temporary"
    printf 'Marcadores incompletos; arquivo preservado: %s\n' "$file" >&2
    return 1
  fi
  chmod --reference="$file" "$temporary"
  if grep -q '[^[:space:]]' "$temporary"; then
    mv -- "$temporary" "$file"
    printf 'Bloco removido, restante preservado: %s\n' "$file"
  else
    rm -f -- "$temporary" "$file"
    printf 'Arquivo gerenciado removido: %s\n' "$file"
  fi
}

remove_conf_source() {
  local file="$CONFIG/hypr/hyprland.conf" relative="config/hypr/hyprland.conf" temporary
  local source='source = ~/.config/hypr/ultimadesk.conf'
  [[ -f "$file" ]] || return 0
  grep -Fqx -- "$source" "$file" || return 0
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'Removeria a referencia do UltimaDesk em: %s\n' "$file"
    return 0
  fi
  backup_path "$file" "$relative"
  temporary="$(mktemp "${file}.XXXXXX")"
  awk -v source="$source" '
    {
      if (pending_comment) {
        if ($0 == source) { pending_comment = 0; next }
        print "# UltimaDesk"
        pending_comment = 0
      }
      if ($0 == "# UltimaDesk") { pending_comment = 1; next }
      if ($0 == source) next
      print
    }
    END { if (pending_comment) print "# UltimaDesk" }
  ' "$file" > "$temporary"
  chmod --reference="$file" "$temporary"
  mv -- "$temporary" "$file"
  printf 'Referencia removida, demais configuracoes preservadas: %s\n' "$file"
}

stop_ultimadesk_processes() {
  local script
  pkill -x globo-layer 2>/dev/null || true
  for script in aero-shell.py aero-launcher.py aero-workspaces.py aero-player.py; do
    pkill -f "^[^ ]*python[0-9.]* $DATA/$script([[:space:]]|$)" 2>/dev/null || true
  done
}

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Simulacao: nenhuma alteracao sera feita."
elif [[ "$BACKUP" -eq 1 ]]; then
  echo "Os arquivos modificados serao copiados para $STATE/ultimadesk-backups/."
fi

remove_managed_block "$CONFIG/hypr/ultimadesk.lua" "config/hypr/ultimadesk.lua" \
  "-- >>> UltimaDesk managed >>>" "-- <<< UltimaDesk managed <<<"
remove_managed_block "$CONFIG/hypr/hyprland.lua" "config/hypr/hyprland.lua" \
  "-- >>> UltimaDesk managed >>>" "-- <<< UltimaDesk managed <<<"
remove_managed_block "$CONFIG/hypr/ultimadesk.conf" "config/hypr/ultimadesk.conf" \
  "# >>> UltimaDesk managed >>>" "# <<< UltimaDesk managed <<<"
remove_conf_source
remove_path "$CONFIG/waybar-aero" "config/waybar-aero"
remove_path "$DATA" "local/share/ultimadesk"

if [[ "$DRY_RUN" -eq 0 ]]; then
  stop_ultimadesk_processes
  if [[ "$BACKUP" -eq 1 && -n "$BACKUP_DIR" ]]; then
    printf 'Backup criado em: %s\n' "$BACKUP_DIR"
  fi
  echo "Limpeza concluida. Configuracoes pessoais e ferramentas compartilhadas foram preservadas."
fi