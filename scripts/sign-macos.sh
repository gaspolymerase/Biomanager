#!/usr/bin/env bash
# Sign dist/BioManager.app with a Developer ID, notarise it with Apple and
# staple the ticket, so it opens without the "unidentified developer"
# warning. The release workflow runs this when the secrets exist:
#
#   MACOS_CERT_P12       the "Developer ID Application" certificate and key, exported as .p12, base64
#   MACOS_CERT_PASSWORD  that export's password
#   APPLE_ID             the Apple ID of the developer account
#   APPLE_TEAM_ID        its team ID (10 characters)
#   APPLE_APP_PASSWORD   an app-specific password for that Apple ID (appleid.apple.com)
set -euo pipefail
APP="dist/BioManager.app"
[ -d "$APP" ] || { echo "no $APP"; exit 1; }

KEYCHAIN="$RUNNER_TEMP/signing.keychain-db"
KEYCHAIN_PASSWORD="$(openssl rand -hex 16)"
echo "$MACOS_CERT_P12" | base64 --decode > "$RUNNER_TEMP/cert.p12"
security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security set-keychain-settings -lut 21600 "$KEYCHAIN"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security import "$RUNNER_TEMP/cert.p12" -P "$MACOS_CERT_PASSWORD" -A -t cert -f pkcs12 -k "$KEYCHAIN"
security set-key-partition-list -S apple-tool:,apple: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN" > /dev/null
security list-keychains -d user -s "$KEYCHAIN" $(security list-keychains -d user | tr -d '"')
rm -f "$RUNNER_TEMP/cert.p12"
IDENTITY="$(security find-identity -v -p codesigning "$KEYCHAIN" | awk -F'"' '/Developer ID Application/ {print $2; exit}')"
[ -n "$IDENTITY" ] || { echo "no Developer ID Application identity in the certificate"; exit 1; }
echo "Signing as $IDENTITY"

sign() { codesign --force --timestamp --options runtime --entitlements desktop/entitlements.plist --sign "$IDENTITY" "$@"; }
# Inside out: every library and executable, then the app itself.
find "$APP/Contents" -type f \( -name "*.dylib" -o -name "*.so" -o -perm -u+x \) -print0 | while IFS= read -r -d '' f; do
  if file "$f" | grep -q "Mach-O"; then sign "$f"; fi
done
find "$APP/Contents" -type d -name "*.framework" -print0 | while IFS= read -r -d '' f; do sign "$f"; done
sign "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

# Notarise: Apple checks it and issues a ticket, stapled to the app.
ditto -c -k --keepParent "$APP" "$RUNNER_TEMP/notarise.zip"
xcrun notarytool submit "$RUNNER_TEMP/notarise.zip" --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_PASSWORD" --wait --timeout 30m
xcrun stapler staple "$APP"
spctl --assess --type execute --verbose "$APP"
security delete-keychain "$KEYCHAIN"
