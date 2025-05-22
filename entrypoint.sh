#!/bin/env bash

# Helper function to load secret or plain value
load_secret() {
  local var_name=$1
  local var_value=${!var_name}

  if [ -z "$var_value" ]; then
    log "Need to set $var_name"
    exit 1
  fi

  if [ -f "$var_value" ]; then
    export "$var_name"="$(<"$var_value")"
  fi
}

# Timestamped echo
log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') :: $*"
}

# Required secrets
load_secret DATABASE_PASSWORD
load_secret BW_CLIENTID
load_secret BW_CLIENTSECRET
load_secret BW_PASSWORD

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

# Bitwarden Auth
log "Begin Bitwarden authentication."
bw config server $BITWARDEN_URL >/dev/null
bw login --apikey >/dev/null
export BW_SESSION=$(bw unlock --passwordenv BW_PASSWORD | grep 'bw list items' | sed -e 's/.*session //') >/dev/null

if bw sync >/dev/null; then
  log "Logged in and synced to Bitwarden."
else
  log "Unable to log in to Bitwarden."
  exit 1
fi

# Backup original file if exists
if [ -f "$DATABASE_PATH" ]; then
  log "Made a backup of existing database."
  backup_path="${DATABASE_PATH}_$(date -u +%Y-%m-%dT%H:%M:%S%Z).bak"
  cp "$DATABASE_PATH" "$backup_path"
  check_owner "$backup_path"
fi

# Python output handler: strip original timestamp and INFO, add new timestamp
run_with_timestamp() {
  while IFS= read -r line; do
    cleaned=$(echo "$line" | sed -E 's/^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} :: INFO :: //')
    log "$cleaned"
  done
}

# Run the exporter unbuffered and process output
PYTHONUNBUFFERED=1 python3 /bitwarden-to-keepass/bitwarden-to-keepass.py --bw-path /usr/bin/bw 2>&1 | run_with_timestamp

# Cleanup
check_owner $DATABASE_PATH
bw lock >/dev/null
log $(bw logout)
