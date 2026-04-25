#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${1:-dist/AiNiee.app}"
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
DMG_PATH="${2:-dist/AiNiee-macOS-${ARCH}.dmg}"
VOLUME_NAME="${VOLUME_NAME:-AiNiee}"
TMP_ROOT="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"

if [[ ! -d "$APP_PATH" ]]; then
  echo "App bundle not found: $APP_PATH" >&2
  exit 1
fi

detach_existing_volume() {
  local volume_path="/Volumes/${VOLUME_NAME}"
  if [[ -d "$volume_path" ]]; then
    hdiutil detach "$volume_path" -force >/dev/null 2>&1 || true
  fi
}

STAGING_DIR="$(mktemp -d "${TMP_ROOT%/}/AiNiee-dmg.XXXXXX")"
STAGING_APP_PATH="$STAGING_DIR/$(basename "$APP_PATH")"

cleanup() {
  rm -rf "$STAGING_DIR"
}
trap cleanup EXIT

mkdir -p "$(dirname "$DMG_PATH")"
ditto "$APP_PATH" "$STAGING_APP_PATH"
ln -s /Applications "$STAGING_DIR/Applications"

detach_existing_volume
rm -f "$DMG_PATH"
if ! hdiutil create \
    -volname "$VOLUME_NAME" \
    -srcfolder "$STAGING_DIR" \
    -fs HFS+ \
    -ov \
    -format UDZO \
    "$DMG_PATH"; then
  detach_existing_volume
  sleep 2
  rm -f "$DMG_PATH"
  hdiutil create \
    -volname "$VOLUME_NAME" \
    -srcfolder "$STAGING_DIR" \
    -fs HFS+ \
    -ov \
    -format UDZO \
    "$DMG_PATH"
fi

echo "$DMG_PATH"
