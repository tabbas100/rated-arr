#!/usr/bin/env bash
# Creates Fetch's release signing key once: ~/.android-keys/fetch-release.jks (owner-only), with a
# random password kept only in the macOS Keychain (service "fetch-release-keystore"). The build
# reads it from there. Back the .jks file up somewhere safe: without it, updates need a reinstall.
set -euo pipefail

DIR="$HOME/.android-keys"
KEYSTORE="$DIR/fetch-release.jks"
SERVICE=fetch-release-keystore
KEYTOOL="${JAVA_HOME:-/opt/homebrew/opt/openjdk@17}/bin/keytool"

if [[ -f "$KEYSTORE" ]]; then
  echo "Release key already exists at $KEYSTORE"
  exit 0
fi
mkdir -p "$DIR" && chmod 700 "$DIR"

FETCH_KEY_PASSWORD="$(openssl rand -base64 33 | tr -d '\n/+=' | cut -c1-40)"
export FETCH_KEY_PASSWORD
security add-generic-password -U -s "$SERVICE" -a fetch -w "$FETCH_KEY_PASSWORD" -T /usr/bin/security
"$KEYTOOL" -genkeypair -keystore "$KEYSTORE" -storetype PKCS12 -alias fetch -keyalg RSA -keysize 4096 \
  -validity 10950 -dname "CN=Fetch for Android TV" \
  -storepass:env FETCH_KEY_PASSWORD -keypass:env FETCH_KEY_PASSWORD >/dev/null
unset FETCH_KEY_PASSWORD
chmod 600 "$KEYSTORE"
echo "Release key created at $KEYSTORE; password stored in the Keychain as $SERVICE."
