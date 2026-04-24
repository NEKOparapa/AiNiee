#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${1:-dist/AiNiee_MacOS.app}"
DMG_PATH="${2:-dist/AiNiee_MacOS-arm64.dmg}"
VOLUME_NAME="${VOLUME_NAME:-AiNiee MacOS}"

if [[ ! -d "$APP_PATH" ]]; then
  echo "App bundle not found: $APP_PATH" >&2
  exit 1
fi

rm -f "$DMG_PATH"
hdiutil create \
  -volname "$VOLUME_NAME" \
  -srcfolder "$APP_PATH" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "$DMG_PATH"
