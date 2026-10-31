#!/usr/bin/env bash
# Runs fetchd on this Mac against the Docker test servers (tools/test-servers.sh up).
# Usage: tools/local-gateway.sh [port]     (default 28700, loopback only)
set -euo pipefail

cd "$(dirname "$0")/.."
PORT="${1:-28700}"
SERVERS=test-servers.local.properties
value() { grep "^$1=" "$SERVERS" | cut -d= -f2-; }
localhost_url() { value "$1" | sed -E 's#//[^:/]+#//127.0.0.1#'; }

export FETCHD_RADARR_URL="$(localhost_url radarr.url)" FETCHD_RADARR_KEY="$(value radarr.api_key)"
export FETCHD_SONARR_URL="$(localhost_url sonarr.url)" FETCHD_SONARR_KEY="$(value sonarr.api_key)"
cd gateway
exec python3 -m fetchd --data ../.local/fetchd serve --port "$PORT"
