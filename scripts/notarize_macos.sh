#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${APP_PATH:-dist/AiNiee.app}"
ARCH="${AINIEE_MACOS_ARCH:-$(uname -m)}"
case "$ARCH" in
  arm64|aarch64)
    ARCH="arm64"
    ;;
  x86_64|amd64|x64)
    ARCH="x86_64"
    ;;
  *)
    echo "Unsupported macOS architecture: $ARCH" >&2
    exit 1
    ;;
esac
DMG_PATH="${DMG_PATH:-dist/AiNiee-macOS-${ARCH}.dmg}"
ENTITLEMENTS="${ENTITLEMENTS:-Packaging/macOS/entitlements.plist}"

: "${CODESIGN_IDENTITY:?CODESIGN_IDENTITY is required}"
: "${APPLE_ID:?APPLE_ID is required}"
: "${APPLE_TEAM_ID:?APPLE_TEAM_ID is required}"
: "${APPLE_APP_SPECIFIC_PASSWORD:?APPLE_APP_SPECIFIC_PASSWORD is required}"

# 先对 .app 做 hardened runtime 签名，再打包 DMG 并提交公证。
codesign \
  --force \
  --deep \
  --options runtime \
  --entitlements "$ENTITLEMENTS" \
  --sign "$CODESIGN_IDENTITY" \
  "$APP_PATH"

scripts/package_dmg.sh "$APP_PATH" "$DMG_PATH"

xcrun notarytool submit "$DMG_PATH" \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD" \
  --wait

xcrun stapler staple "$DMG_PATH"
spctl --assess --type open --context context:primary-signature --verbose "$DMG_PATH"
