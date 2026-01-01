#!/bin/bash

set -e
exec 2>&1

CONFIG_FILE="/app/config.json"
LOG_LEVEL=${LOG_LEVEL:-info}
export TZ="${TZ:-Europe/Berlin}"

if [[ -z "$UGREEN_NAS_API_SCHEME" ]]; then
  printf "%s | --- Starting up with config.json. ---\n" "$(date +'%m.%d %H:%M:%S')"
  export UGREEN_NAS_API_SCHEME="$(jq -r '.options.UGREEN_NAS_API_SCHEME' "$CONFIG_FILE")"
  export UGREEN_NAS_API_IP="$(jq -r '.options.UGREEN_NAS_API_IP' "$CONFIG_FILE")"
  export UGREEN_NAS_API_PORT="$(jq -r '.options.UGREEN_NAS_API_PORT' "$CONFIG_FILE")"
  export UGREEN_NAS_API_VERIFY_SSL="$(jq -r '.options.UGREEN_NAS_API_VERIFY_SSL' "$CONFIG_FILE")"
else
  printf "%s | --- Starting up with docker-compose. ---\n" "$(date +'%m.%d %H:%M:%S')"
fi

printf "%s | Settings: %s://%s:%s verify_ssl=%s\n" \
  "$(date +'%m.%d %H:%M:%S')" \
  "${UGREEN_NAS_API_SCHEME}" \
  "${UGREEN_NAS_API_IP:-<auto>}" \
  "${UGREEN_NAS_API_PORT}" \
  "${UGREEN_NAS_API_VERIFY_SSL}"

exec uvicorn main:app \
  --host 0.0.0.0 \
  --port 4115 \
  --log-config /app/logging.yaml \
  --log-level $LOG_LEVEL
