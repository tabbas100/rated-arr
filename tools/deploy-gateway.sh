#!/usr/bin/env bash
# Installs or updates the Fetch gateway on the Whatbox over SSH and keeps it running with cron
# (at boot and every 5 minutes it starts the gateway if it is not running). Cron also replaces downloads
# stuck for a day (hourly) and searches for everything missing (Sundays).
# It listens on 127.0.0.1 only; Whatbox's HTTPS proxy (the Domain page) is the only way in.
# Undo: tools/deploy-gateway.sh --remove
set -euo pipefail

cd "$(dirname "$0")/.."
setting() { grep "^$1=" fetch.properties | cut -d= -f2-; }
TARGET="$(setting ssh.target)"
PORT="$(setting gateway.port)"
PLEX_PORT="$(setting plex.port)"

if [[ "${1:-}" == "--remove" ]]; then
  ssh "$TARGET" 'crontab -l 2>/dev/null | grep -v "# fetchd" | crontab -; pkill -u "$(id -u)" -f "[f]etchd serve" || true; rm -rf "$HOME/fetch"; echo "Fetch gateway removed (paired devices in ~/.config/fetchd kept)."'
  exit
fi

ssh "$TARGET" "mkdir -p fetch && chmod 700 fetch"
rsync -a --delete --exclude __pycache__ gateway/fetchd/ "$TARGET:fetch/fetchd/"

ssh "$TARGET" "PORT=$PORT PLEX_PORT=$PLEX_PORT bash -s" <<'REMOTE'
set -euo pipefail
umask 077
PLEX_URL="${PLEX_PORT:+http://127.0.0.1:$PLEX_PORT}"
cat > "$HOME/fetch/run.sh" <<RUN
#!/usr/bin/env bash
# Starts the Fetch gateway unless it is already running. cron runs this at boot and every 5 minutes.
set -euo pipefail
LOG="\$HOME/fetch/fetchd.log"
pgrep -u "\$(id -u)" -f "[f]etchd serve --port $PORT" >/dev/null && exit 0
if [[ -f "\$LOG" && \$(stat -c %s "\$LOG") -gt 5000000 ]]; then mv "\$LOG" "\$LOG.1"; fi
umask 077
cd "\$HOME/fetch"
PYTHONPATH="\$HOME/fetch" nohup python3 -P -s -m fetchd serve --port $PORT --plex-url "$PLEX_URL" >> "\$LOG" 2>&1 &
RUN
chmod -R go= "$HOME/fetch"
chmod 700 "$HOME/fetch/run.sh"
(crontab -l 2>/dev/null | grep -v '# fetchd' || true; \
  echo "@reboot \$HOME/fetch/run.sh # fetchd"; \
  echo "*/5 * * * * \$HOME/fetch/run.sh # fetchd"; \
  echo "23 * * * * cd \$HOME/fetch && PYTHONPATH=\$HOME/fetch python3 -P -s -m fetchd replace-dead >> \$HOME/fetch/fetchd.log 2>&1 # fetchd"; \
  echo "40 4 * * 0 cd \$HOME/fetch && PYTHONPATH=\$HOME/fetch python3 -P -s -m fetchd search-missing >> \$HOME/fetch/fetchd.log 2>&1 # fetchd") | crontab -
pkill -u "$(id -u)" -f "[f]etchd serve --port" || true
sleep 1
"$HOME/fetch/run.sh"
sleep 2
curl -sS -m 5 "http://127.0.0.1:$PORT/v1/health"; echo
tail -1 "$HOME/fetch/fetchd.log"
REMOTE
