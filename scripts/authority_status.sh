#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
export TZ=UTC

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IDENTITY_PATH="${AEL_AUTHORITY_IDENTITY_PATH:-$ROOT/governance/authority/machine_b.identity.json}"
MACHINE_ID_PATH="${AEL_MACHINE_ID_PATH:-/etc/machine-id}"

echo "DISTRO=${WSL_DISTRO_NAME:-NA}"
echo "MACHINE_ENV=${AEL_MACHINE:-UNKNOWN}"
echo "IDENTITY_PATH=$IDENTITY_PATH"

if [[ ! -f "$IDENTITY_PATH" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=IDENTITY_POLICY_MISSING path=$IDENTITY_PATH"
  exit 2
fi

if [[ ! -r "$MACHINE_ID_PATH" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=MACHINE_ID_UNREADABLE path=$MACHINE_ID_PATH"
  exit 2
fi

# Identity parsing is strict and fail-closed.
if ! readarray -t IDENTITY < <(python3 - "$IDENTITY_PATH" <<'PY'
import json
import re
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

required = {"schema", "machine_role", "machine_id_sha256"}
if set(data.keys()) != required:
    raise SystemExit("IDENTITY_SCHEMA_KEYS_INVALID")
if data["schema"] != "aelitium_authority_identity_v1":
    raise SystemExit("IDENTITY_SCHEMA_INVALID")
if data["machine_role"] != "B":
    raise SystemExit("IDENTITY_ROLE_INVALID")
if not re.fullmatch(r"[0-9a-f]{64}", data["machine_id_sha256"]):
    raise SystemExit("IDENTITY_MACHINE_ID_SHA_INVALID")

print(data["machine_role"])
print(data["machine_id_sha256"])
PY
); then
  echo "AUTHORITY_STATUS=NO_GO reason=IDENTITY_POLICY_INVALID path=$IDENTITY_PATH"
  exit 2
fi

EXPECTED_ROLE="${IDENTITY[0]}"
EXPECTED_MACHINE_ID_SHA="${IDENTITY[1]}"
ACTUAL_MACHINE_ID_SHA="$(tr -d '\n' < "$MACHINE_ID_PATH" | sha256sum | awk '{print $1}')"

echo "EXPECTED_ROLE=$EXPECTED_ROLE"
echo "ACTUAL_MACHINE_ID_SHA=$ACTUAL_MACHINE_ID_SHA"

if [[ "$EXPECTED_ROLE" != "B" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=NOT_MACHINE_B"
  exit 2
fi

if [[ "$ACTUAL_MACHINE_ID_SHA" != "$EXPECTED_MACHINE_ID_SHA" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=MACHINE_ID_HASH_MISMATCH"
  exit 2
fi

cd "$ROOT" || exit 2

HEAD="$(git rev-parse HEAD 2>/dev/null || echo NA)"
TREE="$(git status --porcelain=v1 | wc -l | tr -d ' ')"
echo "HEAD=$HEAD"
echo "TREE=$TREE"

if [[ ! "$HEAD" =~ ^[0-9a-f]{40}$ ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=INVALID_LOCAL_HEAD_SHA"
  exit 2
fi

if [[ "$TREE" != "0" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=DIRTY_TREE"
  exit 2
fi

# non-interactive ssh for git (no hang)
GIT_SSH_COMMAND="ssh -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=5 -i $HOME/.ssh/id_ed25519"

# IMPORTANT: disable -e just for remote probe, or bash may exit before printing status
set +e
REMOTE_MAIN_SHA="$(GIT_SSH_COMMAND="$GIT_SSH_COMMAND" git ls-remote origin refs/heads/main 2>/dev/null | awk '{print $1}')"
RC_REMOTE=$?
set -e

echo "REMOTE_MAIN=$REMOTE_MAIN_SHA rc=$RC_REMOTE"

if [[ "$RC_REMOTE" -ne 0 || -z "${REMOTE_MAIN_SHA:-}" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=REMOTE_UNREACHABLE"
  exit 2
fi

if [[ ! "$REMOTE_MAIN_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=INVALID_REMOTE_MAIN_SHA"
  exit 2
fi

if [[ "$REMOTE_MAIN_SHA" != "$HEAD" ]]; then
  echo "AUTHORITY_STATUS=NO_GO reason=REMOTE_HEAD_MISMATCH local=$HEAD remote=$REMOTE_MAIN_SHA"
  exit 2
fi

echo "AUTHORITY_STATUS=GO"
