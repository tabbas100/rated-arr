#!/usr/bin/env bash
# A throwaway test CA and a certificate for this Mac's LAN address, so the debug app can reach the
# local test gateway over HTTPS. The CA's private key stays in .local/; only its public certificate
# goes into the debug build (app/src/debug/res/raw/test_ca.pem). Release builds never trust it.
set -euo pipefail

cd "$(dirname "$0")/.."
HOST_IP="${HOST_IP:-$(ipconfig getifaddr en0)}"
DIR=.local/tls
mkdir -p "$DIR" app/src/debug/res/raw
chmod 700 .local "$DIR"

if [[ ! -f "$DIR/ca.key" ]]; then
  openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 30 \
    -subj "/CN=Fetch throwaway test CA" -keyout "$DIR/ca.key" -out "$DIR/ca.pem" 2>/dev/null
fi
openssl req -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -subj "/CN=$HOST_IP" \
  -keyout "$DIR/server.key" -out "$DIR/server.csr" 2>/dev/null
printf 'subjectAltName=IP:%s\nextendedKeyUsage=serverAuth\n' "$HOST_IP" > "$DIR/server.ext"
openssl x509 -req -in "$DIR/server.csr" -CA "$DIR/ca.pem" -CAkey "$DIR/ca.key" -CAcreateserial \
  -days 30 -extfile "$DIR/server.ext" -out "$DIR/server.pem" 2>/dev/null
chmod 600 "$DIR"/*.key
cp "$DIR/ca.pem" app/src/debug/res/raw/test_ca.pem
echo "test CA and certificate for $HOST_IP ready"
