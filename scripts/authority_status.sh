#!/usr/bin/env bash
set -euo pipefail

echo "DISTRO=${WSL_DISTRO_NAME:-NA}"
echo "MACHINE=${AEL_MACHINE:-NA}"
echo "HEAD=$(git rev-parse --short HEAD)"
echo "TREE=$(git status --porcelain=v1 | wc -l | tr -d ' ')"
GIT_SSH_COMMAND="ssh -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=5 -i $HOME/.ssh/id_ed25519"
REMOTE_MAIN="$(GIT_SSH_COMMAND="$GIT_SSH_COMMAND" git ls-remote origin refs/heads/main 2>/dev/null | awk '{print substr($1,1,7)}')"
echo "REMOTE_MAIN=$REMOTE_MAIN"

if [[ -z "${REMOTE_MAIN:-}" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=REMOTE_UNREACHABLE"
  exit 2
fi

if [[ "${AEL_MACHINE:-}" != "B" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=NOT_MACHINE_B"
  exit 2
fi

if [[ "$(git status --porcelain=v1 | wc -l | tr -d ' ')" != "0" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=DIRTY_TREE"
  exit 2
fi

echo "AUTHORITY_STATUS=GO"
