#!/usr/bin/env bash
set -euo pipefail

REQUEST=/var/lib/noisemeter/update.request
STATUS=/var/lib/noisemeter/update-status.json
LOCK=/run/lock/noisemeter-update.lock
exec 9>"$LOCK"
flock -n 9 || exit 0
rm -f "$REQUEST"
printf '{"state":"running","message":"Update wird installiert"}\n' > "$STATUS"
chown noisemeter:noisemeter "$STATUS"

WORK_DIR=$(mktemp -d /tmp/noisemeter-update.XXXXXX)
cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

REPOSITORY=https://github.com/therepro21/noisemeter-pro.git
LATEST_TAG=$(git ls-remote --tags --refs "$REPOSITORY" 'refs/tags/v*' | awk -F/ '{print $3}' | sort -V | tail -1)
if [[ -z "$LATEST_TAG" ]]; then
  printf '{"state":"failed","message":"Kein veröffentlichtes Release gefunden"}\n' > "$STATUS"
  chown noisemeter:noisemeter "$STATUS"
  exit 1
fi

if git clone --depth 1 --branch "$LATEST_TAG" "$REPOSITORY" "$WORK_DIR/repository" &&
   bash "$WORK_DIR/repository/installer/install.sh"; then
  VERSION=$(grep -o 'VERSION = "[^"]*"' "$WORK_DIR/repository/backend/app.py" | head -1 | cut -d'"' -f2)
  printf '{"state":"complete","installed_version":"%s","message":"Update erfolgreich installiert"}\n' "$VERSION" > "$STATUS"
else
  printf '{"state":"failed","message":"Update fehlgeschlagen; Details in journalctl -u noisemeter-update"}\n' > "$STATUS"
  chown noisemeter:noisemeter "$STATUS"
  exit 1
fi
chown noisemeter:noisemeter "$STATUS"
