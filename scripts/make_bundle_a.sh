#!/usr/bin/env bash
set -euo pipefail
OUT_WIN="/mnt/c/Users/CATARINA-AELITIUM/Desktop"
BUNDLE="$OUT_WIN/aelitium-v3.bundle"
SHA="$OUT_WIN/aelitium-v3.bundle.sha256"

cd "$(dirname "$0")/.."

git bundle create "$BUNDLE" --all
sha256sum "$BUNDLE" | tee "$SHA"
echo "OK: bundle written to Desktop with sha256"
