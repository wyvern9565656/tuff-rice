#!/usr/bin/env bash
set -u

find_music_player() {
  local playing_player="" paused_player="" candidate state
  while IFS= read -r candidate; do
    case "${candidate,,}" in
      firefox*|chromium*|chrome*|google-chrome*|brave*|vivaldi*|microsoft-edge*|opera*) continue ;;
    esac
    state="$(playerctl -p "$candidate" status 2>/dev/null || true)"
    if [[ "$state" == Playing ]]; then
      playing_player="$candidate"
      break
    elif [[ "$state" == Paused && -z "$paused_player" ]]; then
      paused_player="$candidate"
    fi
  done < <(playerctl -l 2>/dev/null || true)

  if [[ -n "$playing_player" ]]; then
    printf '%s' "$playing_player"
  elif [[ -n "$paused_player" ]]; then
    printf '%s' "$paused_player"
  else
    return 1
  fi
}

case "${1:-}" in
  session)
    uptime -p 2>/dev/null | sed 's/^up /Ativo ha /' || printf 'Sessao iniciada'
    ;;
  battery)
    battery='Ligado na tomada'
    for capacity in /sys/class/power_supply/BAT*/capacity; do
      if [[ -r "$capacity" ]]; then
        battery="Bateria  $(<"$capacity")%%"
        break
      fi
    done
    printf '%s\n' "$battery"
    ;;
  cpu)
    usage="$(LC_ALL=C top -bn1 2>/dev/null | awk -F, '/Cpu\(s\)/ { idle=$4; gsub(/[^0-9.]/, "", idle); if (idle != "") printf "%.0f", 100-idle }')"
    printf 'CPU  %s%%' "${usage:---}"
    ;;
  memory)
    used="$(LC_ALL=C free -h 2>/dev/null | awk '/^Mem:/ { print $3 }')"
    total="$(LC_ALL=C free -h 2>/dev/null | awk '/^Mem:/ { print $2 }')"
    printf 'RAM\n%s / %s' "${used:---}" "${total:---}"
    ;;
  media)
    selected_player="$(find_music_player 2>/dev/null || true)"
    if [[ -n "$selected_player" ]]; then
      title="$(playerctl -p "$selected_player" metadata --format '{{title}}' 2>/dev/null | cut -c1-18 || true)"
      artist="$(playerctl -p "$selected_player" metadata --format '{{artist}}' 2>/dev/null | cut -c1-18 || true)"
      if [[ -n "$title" ]]; then
        printf '%s\n%s' "$title" "$artist"
      else
        printf 'Nada tocando agora'
      fi
    else
      printf 'Nada tocando agora'
    fi
    ;;
  cover)
    selected_player="$(find_music_player 2>/dev/null || true)"
    [[ -n "$selected_player" ]] || exit 0
    art_url="$(playerctl -p "$selected_player" metadata --format '{{mpris:artUrl}}' 2>/dev/null || true)"
    [[ -n "$art_url" ]] || exit 0

    data_dir="$HOME/.local/share/ultimadesk"
    source_image="$(mktemp "$data_dir/lock-cover-source.XXXXXX")"
    output_image="$(mktemp "$data_dir/lock-cover.XXXXXX.png")"
    trap 'rm -f "$source_image" "$output_image"' EXIT
    case "$art_url" in
      file://*)
        art_path="$(python3 -c 'from urllib.parse import unquote, urlparse; import sys; print(unquote(urlparse(sys.argv[1]).path))' "$art_url")"
        [[ -r "$art_path" ]] && cp -- "$art_path" "$source_image" || exit 0
        ;;
      http://*|https://*)
        curl -fsSL --connect-timeout 2 --max-time 5 --max-filesize 12000000 "$art_url" -o "$source_image" || exit 0
        ;;
      *)
        exit 0
        ;;
    esac

    if magick "$source_image" -auto-orient -thumbnail '256x256^' -gravity center -extent 256x256 -strip "$output_image"; then
      mv -f "$output_image" "$data_dir/lock-cover.png"
    fi
    ;;
  notifications)
    if command -v dunstctl >/dev/null 2>&1; then
      count="$(dunstctl count waiting 2>/dev/null || printf '0')"
      if [[ "$count" == 0 ]]; then
        printf 'Tudo em dia\nSem notificacoes'
      else
        printf '%s notificacao(oes)\nAguardando' "$count"
      fi
    else
      printf 'Sem notificacoes pendentes'
    fi
    ;;
  *)
    exit 2
    ;;
esac