#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: release_rc.sh <vX.Y.Z-rcN> <input.json>"
  exit 2
fi

TAG="$1"
INPUT="$2"

./scripts/authority_status.sh || exit 2

# hard rule: only rc tags here
if [[ ! "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+-rc[0-9]+$ ]]; then
  echo "RELEASE_STATUS=NO_GO reason=INVALID_TAG_FORMAT tag=$TAG"
  exit 2
fi

./scripts/gate_release.sh "$TAG" "$INPUT"

git push --tags
echo "RELEASE_RC_STATUS=GO tag=$TAG"
