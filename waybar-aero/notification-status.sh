#!/usr/bin/env bash
set -u

waiting="$(dunstctl count waiting 2>/dev/null || printf '0')"
paused="$(dunstctl is-paused 2>/dev/null || printf 'false')"
history="$(dunstctl count history 2>/dev/null || printf '0')"
class=""
tooltip="Sem notificacoes novas"

if [[ "$paused" == true ]]; then
  class="paused"
  tooltip="Nao perturbe ativo; $history no historico"
elif [[ "$waiting" =~ ^[0-9]+$ ]] && (( waiting > 0 )); then
  class="has-waiting"
  tooltip="$waiting notificacao(oes) aguardando; $history no historico"
fi

jq -cn --arg text '' --arg tooltip "$tooltip" --arg class "$class" \
  '{text:$text,tooltip:$tooltip,class:$class}'