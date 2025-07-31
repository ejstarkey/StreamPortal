#!/bin/bash

MODE="$1"
IFACE="wlp9s0"
SUP_CONF="/etc/wpa_supplicant/wpa_supplicant-wlp9s0.conf"
SUP_UNIT="wpa_supplicant@${IFACE}.service"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root."
  exit 1
fi

log() {
  echo "[wifi_toggle] $1"
}

stop_all_wifi_services() {
  log "Stopping hostapd, wpa_supplicant, and killing leftovers..."
  systemctl stop hostapd 2>/dev/null
  systemctl stop "$SUP_UNIT" 2>/dev/null
  systemctl stop wpa_supplicant 2>/dev/null
  pkill -f wpa_supplicant
  pkill -f hostapd
}

set_interface_type() {
  TYPE=$1
  log "Bringing down $IFACE and setting type to $TYPE..."
  ip link set "$IFACE" down
  iw dev "$IFACE" set type "$TYPE"
  ip link set "$IFACE" up
}

start_ap_mode() {
  stop_all_wifi_services
  set_interface_type "__ap"
  log "Starting hostapd (AP mode)..."
  systemctl restart hostapd
}

start_sta_mode() {
  stop_all_wifi_services
  set_interface_type "managed"
  log "Starting wpa_supplicant (STA mode)..."
  if [[ -f "$SUP_CONF" ]]; then
    systemctl restart "$SUP_UNIT"
  else
    log "ERROR: $SUP_CONF not found. Cannot start STA mode."
    exit 1
  fi
}

case "$MODE" in
  ap)
    start_ap_mode
    ;;
  sta)
    start_sta_mode
    ;;
  *)
    echo "Usage: $0 [ap|sta]"
    exit 1
    ;;
esac
