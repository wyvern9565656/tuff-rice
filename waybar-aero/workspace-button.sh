#!/usr/bin/env bash
set -u

workspace="${1:-}"
number_only="${2:-}"
if [[ ! "$workspace" =~ ^([1-9]|10)$ ]]; then
  exit 1
fi

runtime="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
socket="$runtime/hypr/${HYPRLAND_INSTANCE_SIGNATURE:-}/.socket2.sock"
if [[ ! -S "$socket" ]]; then
  exit 1
fi

publish_state() {
  local active="${1:-}" class=inactive
  if [[ -z "$active" ]]; then
    active="$(hyprctl -j activeworkspace 2>/dev/null | jq -r '.id // empty' 2>/dev/null || true)"
  fi
  [[ "$active" == "$workspace" ]] && class=active
  if [[ "$number_only" == "--number-only" ]]; then
    printf '{"text":"%s","tooltip":"Workspace %s","class":"%s"}\n' \
      "$workspace" "$workspace" "$class"
    return
  fi
  printf '{"text":"%s","tooltip":"Workspace %s","class":"%s"}\n' \
    "$workspace" "$workspace" "$class"
}

active="$(hyprctl -j activeworkspace 2>/dev/null | jq -r '.id // empty' 2>/dev/null || true)"
publish_state "$active"

while IFS= read -r event; do
  case "$event" in
    workspacev2\>\>*)
      payload="${event#*>>}"
      publish_state "${payload%%,*}"
      ;;
    focusedmonv2\>\>*)
      payload="${event#*>>}"
      publish_state "${payload##*,}"
      ;;
  esac
done < <(socat -u "UNIX-CONNECT:$socket" - 2>/dev/null)
