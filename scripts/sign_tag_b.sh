#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: sign_tag_b.sh <vX.Y.Z-rcN>"
  exit 2
fi

TAG="$1"
LOG="governance/logs/EVIDENCE_LOG.md"
ALLOW="governance/authority/allowed_signers"

# Tag format
if [[ ! "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+-rc[0-9]+$ ]]; then
  echo "SIGN_STATUS=NO_GO reason=INVALID_TAG_FORMAT tag=$TAG"
  exit 2
fi

# Clean tree
if [[ -n "$(git status --porcelain=v1)" ]]; then
  echo "SIGN_STATUS=NO_GO reason=DIRTY_GIT_TREE"
  exit 2
fi

# Synced with origin/main
git fetch origin main --quiet
LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse origin/main)"
if [[ "$LOCAL" != "$REMOTE" ]]; then
  echo "SIGN_STATUS=NO_GO reason=NOT_SYNCED local=$LOCAL remote=$REMOTE"
  exit 2
fi

# Authority material must exist
if [[ ! -f "$ALLOW" ]]; then
  echo "SIGN_STATUS=NO_GO reason=ALLOWLIST_MISSING path=$ALLOW"
  exit 2
fi

# Tag must not exist (local or remote)
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  echo "SIGN_STATUS=NO_GO reason=TAG_ALREADY_EXISTS_LOCAL tag=$TAG"
  exit 2
fi
if git ls-remote --tags origin "refs/tags/$TAG" | grep -q .; then
  echo "SIGN_STATUS=NO_GO reason=TAG_ALREADY_EXISTS_REMOTE tag=$TAG"
  exit 2
fi

# Evidence must exist and validate for TAG (fail-closed)
python3 scripts/validate_evidence_log.py --tag "$TAG" --log "$LOG" >/dev/null || {
  RC=$?
  echo "SIGN_STATUS=NO_GO reason=EVIDENCE_INVALID tag=$TAG rc=$RC"
  exit 2
}

# Enforce repo-provided allowed signers for ssh signature verification (Machine B local config)
git config --local gpg.format ssh
git config --local gpg.ssh.allowedSignersFile "$ALLOW"

# Require ssh-agent + key loaded (fail-closed)
ssh-add -l >/dev/null 2>&1 || {
  echo "SIGN_STATUS=NO_GO reason=SSH_AGENT_OR_KEY_MISSING"
  exit 2
}

# Create annotated signed tag (SSH signing via git's ssh signing)
git tag -s -a "$TAG" -m "AELITIUM release $TAG"

# Verify tag signature immediately (offline)
git tag -v "$TAG" >/dev/null

# Push only the tag
git push origin "refs/tags/$TAG"

echo "SIGN_STATUS=GO tag=$TAG"
