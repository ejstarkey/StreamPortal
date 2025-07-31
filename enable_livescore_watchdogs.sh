#!/bin/bash

CONFIG="/home/cornerpins/portal/streams_config.json"

if [ ! -f "$CONFIG" ]; then
  echo "Missing config file at $CONFIG"
  exit 1
fi

ENABLED=0

for i in $(seq 0 11); do
  ENABLED_FLAG=$(jq -r ".lane_pairs[$i].enabled" "$CONFIG")
  TYPE=$(jq -r ".lane_pairs[$i].scoring_type" "$CONFIG")
  CENTRE=$(jq -r ".lane_pairs[$i].centre" "$CONFIG")

  if [ "$ENABLED_FLAG" == "true" ] && [ "$TYPE" == "livescores" ] && [ "$CENTRE" != "null" ] && [ -n "$CENTRE" ]; then
    echo "Activating lane pair $i..."
    sudo systemctl enable --now poll-livescores@$i.service
    ((ENABLED++))
  fi
done

echo "$ENABLED lane pair services started."
