#!/usr/bin/env bash
set -euo pipefail
IN_WIN="/mnt/c/Users/CATARINA-AELITIUM/Desktop"
BUNDLE="$IN_WIN/aelitium-v3.bundle"
SHA="$IN_WIN/aelitium-v3.bundle.sha256"

cd "$(dirname "$0")/.."

sha256sum -c "$SHA"
git fetch "$BUNDLE" --tags
git checkout main
git reset --hard FETCH_HEAD
echo "OK: Machine B now matches bundle state"
