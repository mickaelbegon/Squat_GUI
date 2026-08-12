#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVE_PATH="${1:-$ROOT_DIR/outputs/release_candidate_20260812_0.2.0/Squat_GUI-0.2.0-macOS-arm64.zip}"
EXPECTED_VERSION="${2:-0.2.0}"
INCLUDE_BIORBD="${SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS:-1}"

if [[ ! -f "$ARCHIVE_PATH" ]]; then
  echo "Archive introuvable: $ARCHIVE_PATH" >&2
  exit 1
fi

WORK_DIR="$(mktemp -d /tmp/squat-gui-macos-recette.XXXXXX)"
trap 'rm -rf "$WORK_DIR"' EXIT
mkdir -p "$WORK_DIR/home" "$WORK_DIR/extracted"

ditto -x -k "$ARCHIVE_PATH" "$WORK_DIR/extracted"
APP_PATH="$WORK_DIR/extracted/Squat GUI.app"
EXECUTABLE="$APP_PATH/Contents/MacOS/Squat GUI"
PLIST="$APP_PATH/Contents/Info.plist"

test -x "$EXECUTABLE"
ACTUAL_VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$PLIST")"
if [[ "$ACTUAL_VERSION" != "$EXPECTED_VERSION" ]]; then
  echo "Version inattendue: $ACTUAL_VERSION (attendu: $EXPECTED_VERSION)" >&2
  exit 1
fi
/usr/bin/file "$EXECUTABLE" | grep -q 'arm64'
codesign --verify --deep --strict "$APP_PATH"

env -u SQUAT_GUI_NODE -u SQUAT_GUI_NODE_MODULES \
  HOME="$WORK_DIR/home" \
  PATH=/usr/bin:/bin \
  SQUAT_GUI_SMOKE_TEST=1 \
  SQUAT_GUI_INCLUDE_OPTIONAL_BACKENDS="$INCLUDE_BIORBD" \
  "$EXECUTABLE"

echo "Recette macOS réussie: Squat GUI $ACTUAL_VERSION, arm64, profil vierge."
