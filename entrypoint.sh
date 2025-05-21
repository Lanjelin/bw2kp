#!/bin/env bash
# Required - var can be file, eg. /run/secrets
if [ -z "$DATABASE_PASSWORD" ]; then
  echo "Need to set DATABASE_PASSWORD"
  exit 1
else
  if [ -f "$DATABASE_PASSWORD" ]; then
    DATABASE_PASSWORD=$(<"$DATABASE_PASSWORD")
  fi
fi
if [ -z "$BW_CLIENTID" ]; then
  echo "Need to set BW_CLIENTID"
  exit 1
else
  if [ -f "$BW_CLIENTID" ]; then
    BW_CLIENTID=$(<"$BW_CLIENTID")
  fi
fi
if [ -z "$BW_CLIENTSECRET" ]; then
  echo "Need to set BW_CLIENTSECRET"
  exit 1
else
  if [ -f "$BW_CLIENTSECRET" ]; then
    BW_CLIENTSECRET=$(<"$BW_CLIENTSECRET")
  fi
fi
if [ -z "$BW_PASSWORD" ]; then
  echo "Need to set BW_PASSWORD"
  exit 1
else
  if [ -f "$BW_PASSWORD" ]; then
    BW_PASSWORD=$(<"$BW_PASSWORD")
  fi
fi
# Default values as fallback
[ -z "$DATABASE_PATH" ] && export DATABASE_PATH='/exports/bitwarden-export.kdbx'
[ -z "$BITWARDEN_URL" ] && export BITWARDEN_URL='https://bitwarden.com'
# Change owner of file, by setting PUID PGID
check_owner() {
  local filepath="$1"
  if [[ -n "$PUID" ]]; then
    chown "$PUID" "$filepath"
  fi
  if [[ -n "$PGID" ]]; then
    chgrp "$PGID" "$filepath"
  fi
}
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
  backup_path="${DATABASE_PATH}_$(date -u +%Y-%m-%dT%H:%M:%S%Z).bak"
  cp "$DATABASE_PATH" "$backup_path"
  check_owner "$backup_path"
fi
# Run the exporter
python3 /bitwarden-to-keepass/bitwarden-to-keepass.py --bw-path /usr/bin/bw
# Cleanup
check_owner $DATABASE_PATH
bw lock
echo ""
bw logout
