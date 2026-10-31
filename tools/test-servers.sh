#!/usr/bin/env bash
# Throwaway Radarr, Sonarr v4 and Sonarr v3 in Docker for Fetch's end-to-end tests. They have no
# indexers or download clients, so adding a title never downloads anything.
#
# Usage: tools/test-servers.sh up     start them and write test-servers.local.properties
#        tools/test-servers.sh down   remove them
set -euo pipefail

cd "$(dirname "$0")/.."
OUT=test-servers.local.properties
HOST_IP="${HOST_IP:-$(ipconfig getifaddr en0 2>/dev/null || hostname -I | cut -d' ' -f1)}"
SERVERS=(
  "radarr fetch-test-radarr 7878 lscr.io/linuxserver/radarr:latest /movies"
  "sonarr fetch-test-sonarr 8989 lscr.io/linuxserver/sonarr:latest /tv"
  "sonarr3 fetch-test-sonarr3 8990 lscr.io/linuxserver/sonarr:3.0.10 /tv"
)

start_server() {
  local name="$1" container="$2" port="$3" image="$4"
  docker inspect "$container" >/dev/null 2>&1 && return
  docker run -d --name "$container" -p "$port:${port/8990/8989}" \
    -e PUID=1000 -e PGID=1000 -e TZ=Europe/Berlin "$image" >/dev/null
}

api_key() {
  docker exec "$1" sh -c "grep -o '<ApiKey>[^<]*' /config/config.xml 2>/dev/null | cut -d'>' -f2"
}

wait_ready() {
  local container="$1" port="$2" key
  for _ in $(seq 1 60); do
    key="$(api_key "$container" || true)"
    if [[ -n "$key" ]] && curl -fsS -H "X-Api-Key: $key" "http://localhost:$port/api/v3/system/status" >/dev/null 2>&1; then
      return
    fi
    sleep 2
  done
  echo "$container did not start" >&2
  exit 1
}

add_root_folder() {
  local container="$1" port="$2" folder="$3" key
  key="$(api_key "$container")"
  docker exec "$container" sh -c "mkdir -p $folder && chown abc:abc $folder"
  if ! curl -fsS -H "X-Api-Key: $key" "http://localhost:$port/api/v3/rootfolder" | grep -q "\"path\": *\"$folder\""; then
    curl -fsS -H "X-Api-Key: $key" -H "Content-Type: application/json" \
      -d "{\"path\":\"$folder\"}" "http://localhost:$port/api/v3/rootfolder" >/dev/null
  fi
}

up() {
  : > "$OUT"
  for spec in "${SERVERS[@]}"; do
    read -r name container port image folder <<< "$spec"
    start_server "$name" "$container" "$port" "$image"
    wait_ready "$container" "$port"
    add_root_folder "$container" "$port" "$folder"
    printf '%s.url=http://%s:%s\n%s.api_key=%s\n' "$name" "$HOST_IP" "$port" "$name" "$(api_key "$container")" >> "$OUT"
    echo "ready: $name on port $port"
  done
}

down() {
  for spec in "${SERVERS[@]}"; do
    read -r _ container _ <<< "$spec"
    docker rm -f "$container" >/dev/null 2>&1 || true
  done
  rm -f "$OUT"
}

case "${1:-}" in
  up) up ;;
  down) down ;;
  *) echo "Usage: $0 up|down" >&2; exit 2 ;;
esac
