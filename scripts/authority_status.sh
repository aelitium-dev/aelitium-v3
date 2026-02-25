#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
export TZ=UTC

echo "DISTRO=${WSL_DISTRO_NAME:-NA}"
echo "MACHINE=${AEL_MACHINE:-}"

# must be B
if [[ "${AEL_MACHINE:-}" != "B" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=NOT_MACHINE_B"
  exit 2
fi

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 2

HEAD="$(git rev-parse --short HEAD 2>/dev/null || echo NA)"
TREE="$(git status --porcelain=v1 | wc -l | tr -d ' ')"
echo "HEAD=$HEAD"
echo "TREE=$TREE"

if [[ "$TREE" != "0" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=DIRTY_TREE"
  exit 2
fi

GIT_SSH_COMMAND="ssh -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=5 -i $HOME/.ssh/id_ed25519"

REMOTE_MAIN_SHA="$(GIT_SSH_COMMAND="$GIT_SSH_COMMAND" git ls-remote origin refs/heads/main 2>/dev/null | awk '{print substr($1,1,7)}')"
RC_REMOTE=$?
echo "REMOTE_MAIN=$REMOTE_MAIN_SHA rc=$RC_REMOTE"

if [[ "$RC_REMOTE" -ne 0 || -z "${REMOTE_MAIN_SHA:-}" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=REMOTE_UNREACHABLE"
  exit 2
fi

if [[ "$REMOTE_MAIN_SHA" != "$HEAD" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=REMOTE_HEAD_MISMATCH local=$HEAD remote=$REMOTE_MAIN_SHA"
  exit 2
fi

echo "AUTHORITY_STATUS=GO"
