#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: gate_release.sh <release_tag> <input.json>"
  exit 2
fi

TAG="$1"
INPUT="$2"
OUTDIR="release_output"
EVIDENCE_LOG_PATH="${AEL_EVIDENCE_LOG_PATH:-governance/logs/EVIDENCE_LOG.md}"

if [[ -z "${TAG:-}" ]]; then
  echo "RELEASE_STATUS=NO_GO reason=EMPTY_TAG"
  exit 2
fi

if [[ -z "${INPUT:-}" || ! -f "$INPUT" ]]; then
  echo "RELEASE_STATUS=NO_GO reason=INPUT_MISSING input=$INPUT"
  exit 2
fi

# --- Evidence log enforcement (fail-closed, pre-tag) ---
python3 scripts/validate_evidence_log.py --tag "$TAG" --log "$EVIDENCE_LOG_PATH" || {
  echo "RELEASE_STATUS=NO_GO reason=EVIDENCE_INVALID tag=$TAG log=$EVIDENCE_LOG_PATH"
  exit 2
}

rm -rf "$OUTDIR"
mkdir -p "$OUTDIR"

# --- Clean Git check (fail-closed) ---
if [[ -n "$(git status --porcelain=v1)" ]]; then
  echo "RELEASE_STATUS=NO_GO reason=DIRTY_GIT_TREE"
  exit 2
fi

# --- Machine fingerprint ---
HOSTNAME="$(hostname 2>/dev/null || echo unknown)"
KERNEL="$(uname -sr 2>/dev/null || echo unknown)"
MACHINE_ID="$(cat /etc/machine-id 2>/dev/null || echo unknown)"
TS_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# --- Run governed pipeline ---
python3 engine/cli.py pack --input "$INPUT" --out "$OUTDIR"
python3 engine/cli.py verify \
  --manifest "$OUTDIR/manifest.json" \
  --evidence "$OUTDIR/evidence_pack.json"
python3 engine/cli.py repro --input "$INPUT"

# --- Hashes ---
INPUT_SHA="$(sha256sum "$INPUT" | awk '{print $1}')"
MANIFEST_SHA="$(sha256sum "$OUTDIR/manifest.json" | awk '{print $1}')"
EVIDENCE_SHA="$(sha256sum "$OUTDIR/evidence_pack.json" | awk '{print $1}')"
VK_SHA="$(sha256sum "$OUTDIR/verification_keys.json" | awk '{print $1}')"
GIT_SHA="$(git rev-parse HEAD)"

# --- Generate release metadata artifact ---
cat > "$OUTDIR/release_metadata.json" <<EOF_JSON
{
  "tag": "$TAG",
  "ts_utc": "$TS_UTC",
  "git_commit": "$GIT_SHA",
  "hostname": "$HOSTNAME",
  "kernel": "$KERNEL",
  "machine_id": "$MACHINE_ID",
  "input_path": "$INPUT",
  "input_sha256": "$INPUT_SHA",
  "manifest_sha256": "$MANIFEST_SHA",
  "evidence_pack_sha256": "$EVIDENCE_SHA",
  "verification_keys_sha256": "$VK_SHA",
  "decision": "GO"
}
EOF_JSON

# --- Bundle determinism (mandatory) ---
./scripts/bundle_determinism_check.sh || {
  RC_BUNDLE=$?
  echo "RELEASE_STATUS=NO_GO reason=NON_DETERMINISTIC_BUNDLE rc=$RC_BUNDLE"
  exit 2
}

# --- Signed tag enforcement (SSH signing, fail-closed) ---
SIGNINGKEY_PUB="$(git config --global --get user.signingkey || true)"
ALLOWED_SIGNERS="$(git config --global --get gpg.ssh.allowedSignersFile || true)"
GPG_FORMAT="$(git config --global --get gpg.format || true)"

if [[ "$GPG_FORMAT" != "ssh" ]]; then
  echo "RELEASE_STATUS=NO_GO reason=GPG_FORMAT_NOT_SSH"
  exit 2
fi

if [[ -z "$SIGNINGKEY_PUB" || ! -f "$SIGNINGKEY_PUB" ]]; then
  echo "RELEASE_STATUS=NO_GO reason=SIGNINGKEY_PUB_MISSING path=$SIGNINGKEY_PUB"
  exit 2
fi

if [[ -z "$ALLOWED_SIGNERS" || ! -f "$ALLOWED_SIGNERS" ]]; then
  echo "RELEASE_STATUS=NO_GO reason=ALLOWED_SIGNERS_MISSING path=$ALLOWED_SIGNERS"
  exit 2
fi

if [[ -z "${SSH_AUTH_SOCK:-}" ]]; then
  echo "RELEASE_STATUS=NO_GO reason=SSH_AGENT_NOT_RUNNING hint='eval \"\$(ssh-agent -s)\"; ssh-add ~/.ssh/aelitium_release_signing'"
  exit 2
fi

if ! ssh-add -l >/dev/null 2>&1; then
  echo "RELEASE_STATUS=NO_GO reason=SSH_AGENT_NO_KEYS hint='ssh-add ~/.ssh/aelitium_release_signing'"
  exit 2
fi

REQ_KEY="$(awk '{print $1" "$2}' "$SIGNINGKEY_PUB")"
if ! ssh-add -L 2>/dev/null | awk '{print $1" "$2}' | grep -Fxq "$REQ_KEY"; then
  echo "RELEASE_STATUS=NO_GO reason=SIGNING_KEY_NOT_LOADED key=$SIGNINGKEY_PUB"
  exit 2
fi

if git show-ref --tags --quiet --verify "refs/tags/$TAG"; then
  echo "RELEASE_STATUS=NO_GO reason=TAG_ALREADY_EXISTS_LOCAL tag=$TAG"
  exit 2
fi

if git ls-remote --tags origin "refs/tags/$TAG" | grep -q .; then
  echo "RELEASE_STATUS=NO_GO reason=TAG_ALREADY_EXISTS_REMOTE tag=$TAG"
  exit 2
fi

TARGET_COMMIT="$(git rev-parse HEAD)"
if [[ ! "$TARGET_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "RELEASE_STATUS=NO_GO reason=INVALID_TARGET_COMMIT_SHA"
  exit 2
fi

git tag -s -a "$TAG" -m "AELITIUM release $TAG" "$TARGET_COMMIT"
git tag -v "$TAG" >/dev/null 2>&1 || {
  echo "RELEASE_STATUS=NO_GO reason=TAG_SIGNATURE_INVALID tag=$TAG"
  exit 2
}

git push origin "$TAG"
echo "TAG_SIGN_STATUS=OK tag=$TAG commit=$TARGET_COMMIT"

echo "RELEASE_STATUS=GO tag=$TAG"
