#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: sign_tag_b.sh <vX.Y.Z-rcN>"
  exit 2
fi

TAG="$1"
LOG="governance/logs/EVIDENCE_LOG.md"
ALLOW="governance/authority/allowed_signers"

if [[ ! "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+-rc[0-9]+$ ]]; then
  echo "SIGN_STATUS=NO_GO reason=INVALID_TAG_FORMAT tag=$TAG"
  exit 2
fi

# Must be clean + synced
if [[ -n "$(git status --porcelain=v1)" ]]; then
  echo "SIGN_STATUS=NO_GO reason=DIRTY_GIT_TREE"
  exit 2
fi

git fetch origin main --quiet
LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse origin/main)"
if [[ "$LOCAL" != "$REMOTE" ]]; then
  echo "SIGN_STATUS=NO_GO reason=NOT_SYNCED local=$LOCAL remote=$REMOTE"
  exit 2
fi

# Tag must NOT exist anywhere
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  echo "SIGN_STATUS=NO_GO reason=TAG_ALREADY_EXISTS_LOCAL tag=$TAG"
  exit 2
fi
if git ls-remote --tags origin "refs/tags/$TAG" | grep -q .; then
  echo "SIGN_STATUS=NO_GO reason=TAG_ALREADY_EXISTS_REMOTE tag=$TAG"
  exit 2
fi

# Evidence must exist and validate for TAG
python3 scripts/validate_evidence_log.py --tag "$TAG" --log "$LOG" >/dev/null || {
  RC=$?
  echo "SIGN_STATUS=NO_GO reason=EVIDENCE_INVALID tag=$TAG rc=$RC"
  exit 2
}
echo "EVIDENCE_STATUS=PASS tag=$TAG"

# Enforce repo-provided allowed signers for ssh signature verification
git config --local gpg.format ssh
git config --local gpg.ssh.allowedSignersFile "$ALLOW"

# Require ssh-agent + key loaded (fail-closed)
ssh-add -l >/dev/null 2>&1 || {
  echo "SIGN_STATUS=NO_GO reason=SSH_AGENT_OR_KEY_MISSING"
  exit 2
}

# Create annotated signed tag (SSH)
git tag -s -a "$TAG" -m "AELITIUM release $TAG"

# Verify tag signature immediately
git tag -v "$TAG" >/dev/null
echo "TAG_SIGNATURE=PASS tag=$TAG"

# Push only the tag
git push origin "refs/tags/$TAG"
echo "SIGN_STATUS=GO tag=$TAG"
