#!/usr/bin/env bash
if ! command -v bluetoothctl >/dev/null 2>&1; then
  printf '{"text":"BT --","tooltip":"Bluetooth indisponivel"}\n'
  exit 0
fi

powered="$(bluetoothctl show 2>/dev/null | sed -n 's/^[[:space:]]*Powered: //p' | head -n 1)"
case "$powered" in
  yes)
    text=$'\uf293  Bluetooth'
    status="Ligado"
    ;;
  no)
    text=$'\uf293  Bluetooth off'
    status="Desligado"
    ;;
  *)
    text="Bluetooth indisponivel"
    status="Controlador indisponivel"
    ;;
esac

printf '{"text":"%s","tooltip":"Bluetooth: %s"}\n' "$text" "$status"