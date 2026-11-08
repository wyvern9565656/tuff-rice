#!/usr/bin/env bash
set -euo pipefail

DATA="$HOME/.local/share/ultimadesk"
AVATAR="$DATA/lock-avatar.png"
SOURCE="$AVATAR"

for candidate in "$HOME/.face" "$HOME/.face.icon" "/var/lib/AccountsService/icons/$USER"; do
  if [[ -r "$candidate" ]]; then
    SOURCE="$candidate"
    break
  fi
done

if [[ -r "$SOURCE" ]] && command -v magick >/dev/null 2>&1; then
  temporary_avatar="$(mktemp "$DATA/lock-avatar.XXXXXX.png")"
  trap 'rm -f "$temporary_avatar"' EXIT
  magick "$SOURCE" -auto-orient -thumbnail '256x256^' -gravity center -extent 256x256 \
    \( -size 256x256 xc:none -fill white -draw 'polygon 64,4 192,4 252,128 192,252 64,252 4,128' \) \
    -compose CopyOpacity -composite -fill none -stroke 'rgba(64,190,202,0.96)' \
    -strokewidth 9 -draw 'polygon 64,4 192,4 252,128 192,252 64,252 4,128' \
    -stroke 'rgba(255,255,255,0.98)' -strokewidth 3 \
    -draw 'polygon 64,4 192,4 252,128 192,252 64,252 4,128' "$temporary_avatar"
  mv -f "$temporary_avatar" "$AVATAR"
fi

"$DATA/lock-status.sh" cover >/dev/null 2>&1 || true
exec hyprlock --config "$HOME/.config/hypr/hyprlock.conf"