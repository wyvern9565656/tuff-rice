#!/usr/bin/env bash
set -u

runtime_dir="${XDG_RUNTIME_DIR:-/tmp}"
if [[ -e "$runtime_dir/ultimadesk-player-expanded" ]]; then
  printf '{"text":""}\n'
  exit 0
fi

case "${1:-}" in
  previous) icon='\uf04a' ;;
  next) icon='\uf04e' ;;
  toggle)
    status="$(playerctl status 2>/dev/null)" || exit 1
    if [[ "$status" == "Playing" ]]; then
      icon='\uf04c'
    else
      icon='\uf04b'
    fi
    ;;
  *) exit 2 ;;
esac
printf '{"text":"%s"}\n' "$icon"
