#!/bin/env bash
# Required
[ -z "$DATABASE_PASSWORD" ] && echo "Need to set DATABASE_PASSWORD" && exit 1
[ -z "$BW_CLIENTID" ] && echo "Need to set BW_CLIENTID" && exit 1
[ -z "$BW_CLIENTSECRET" ] && echo "Need to set BW_CLIENTSECRET" && exit 1
[ -z "$BW_PASSWORD" ] && echo "Need to set BW_PASSWORD" && exit 1
# Default values as fallback
[ -z "$DATABASE_PATH" ] && export DATABASE_PATH='/exports/bitwarden-export.kdbx'
[ -z "$BITWARDEN_URL" ] && export BITWARDEN_URL='https://bitwarden.com'
# Start Bitwarden Authentication
echo "Begin Bitwarden authentication."
bw config server $BITWARDEN_URL >/dev/null
bw login --apikey >/dev/null
export BW_SESSION=$(bw unlock --passwordenv BW_PASSWORD | grep 'bw list items' | sed -e 's/.*session //') >/dev/null
if bw sync >/dev/null; then
  echo "Logged in and synced to Bitwarden."
else
  echo "Unable to log in to Bitwarden."
  exit 1
fi
# Backup original file if exists
if [ -f "$DATABASE_PATH" ]; then
  echo "Made a backup of existing database."
  cp "$DATABASE_PATH" "$DATABASE_PATH"_$(date -u +%Y-%m-%dT%H:%M:%S%Z).bak
fi
# Run the exporter
python3 /bitwarden-to-keepass/bitwarden-to-keepass.py --bw-path /usr/bin/bw
# Cleanup
bw lock
echo ""
bw logout
