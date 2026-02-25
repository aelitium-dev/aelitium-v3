#!/usr/bin/env bash
set -euo pipefail

echo "DISTRO=${WSL_DISTRO_NAME:-NA}"
echo "MACHINE=${AEL_MACHINE:-NA}"
echo "HEAD=$(git rev-parse --short HEAD)"
echo "TREE=$(git status --porcelain=v1 | wc -l | tr -d ' ')"
echo "REMOTE_MAIN=$(git ls-remote origin refs/heads/main | awk "{print substr(\$1,1,7)}")"

if [[ "${AEL_MACHINE:-}" != "B" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=NOT_MACHINE_B"
  exit 2
fi

if [[ "$(git status --porcelain=v1 | wc -l | tr -d ' ')" != "0" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=DIRTY_TREE"
  exit 2
fi

echo "AUTHORITY_STATUS=GO"
