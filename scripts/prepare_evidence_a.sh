#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: prepare_evidence_a.sh <vX.Y.Z-rcN> <input.json>"
  exit 2
fi

TAG="$1"
INPUT="$2"
LOG="governance/logs/EVIDENCE_LOG.md"

# Validator must exist (fail-closed)
if [[ ! -f "scripts/validate_evidence_log.py" ]]; then
  echo "PREP_STATUS=NO_GO reason=VALIDATOR_MISSING path=scripts/validate_evidence_log.py"
  exit 2
fi
OUTDIR="release_output"

# Hard rules
if [[ ! "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+-rc[0-9]+$ ]]; then
  echo "PREP_STATUS=NO_GO reason=INVALID_TAG_FORMAT tag=$TAG"
  exit 2
fi

if [[ -z "$INPUT" || ! -f "$INPUT" ]]; then
  echo "PREP_STATUS=NO_GO reason=INPUT_MISSING input=$INPUT"
  exit 2
fi

# Must be clean + synced
if [[ -n "$(git status --porcelain=v1)" ]]; then
  echo "PREP_STATUS=NO_GO reason=DIRTY_GIT_TREE"
  exit 2
fi

git fetch origin main --quiet
LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse origin/main)"
if [[ "$LOCAL" != "$REMOTE" ]]; then
  echo "PREP_STATUS=NO_GO reason=NOT_SYNCED local=$LOCAL remote=$REMOTE"
  exit 2
fi

# Tag must NOT exist anywhere (A never tags)
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  echo "PREP_STATUS=NO_GO reason=TAG_ALREADY_EXISTS_LOCAL tag=$TAG"
  exit 2
fi
if git ls-remote --tags origin "refs/tags/$TAG" | grep -q .; then
  echo "PREP_STATUS=NO_GO reason=TAG_ALREADY_EXISTS_REMOTE tag=$TAG"
  exit 2
fi

# Run governed pipeline (A prepares evidence only; no tag operations here)
rm -rf "$OUTDIR"
mkdir -p "$OUTDIR"
python3 engine/cli.py pack --input "$INPUT" --out "$OUTDIR"
python3 engine/cli.py verify --manifest "$OUTDIR/manifest.json" --evidence "$OUTDIR/evidence_pack.json" >/dev/null
python3 engine/cli.py repro --input "$INPUT" >/dev/null

DET_OUT="$(./scripts/test_determinism.sh "$INPUT")"
RUN1_SHA="$(printf '%s\n' "$DET_OUT" | awk -F= '/^BUNDLE_SHA_RUN1=/{print $2}' | tail -n1)"
RUN2_SHA="$(printf '%s\n' "$DET_OUT" | awk -F= '/^BUNDLE_SHA_RUN2=/{print $2}' | tail -n1)"
if [[ -z "${RUN1_SHA:-}" || -z "${RUN2_SHA:-}" ]]; then
  echo "PREP_STATUS=NO_GO reason=DETERMINISM_HASH_PARSE_FAILED"
  exit 2
fi

TAMP_OUT="$(./scripts/test_tamper.sh "$INPUT")"
TAMPER_RC="$(printf '%s\n' "$TAMP_OUT" | awk -F= '/^TAMPER_RC=/{print $2}' | tail -n1)"
if [[ "$TAMPER_RC" != "2" ]]; then
  echo "PREP_STATUS=NO_GO reason=TAMPER_TEST_FAILED rc=${TAMPER_RC:-NA}"
  exit 2
fi

# Collect required hashes from release_output
TS_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
INPUT_SHA="$(sha256sum "$INPUT" | awk "{print \$1}")"
MANIFEST_SHA="$(sha256sum "$OUTDIR/manifest.json" | awk "{print \$1}")"
EVIDENCE_SHA="$(sha256sum "$OUTDIR/evidence_pack.json" | awk "{print \$1}")"
KEYS_SHA="$(sha256sum "$OUTDIR/verification_keys.json" | awk "{print \$1}")"

# Machine identity (A)
HN="$(hostname 2>/dev/null || echo unknown)"
MID="$(tr -d '\n' </etc/machine-id 2>/dev/null || echo unknown)"
MACHINE_ID="A|$HN|$MID"

cat >> "$LOG" <<EOF_ENTRY

## EVIDENCE_ENTRY v1 | tag=$TAG
\`\`\`json
{
  "schema": "evidence_entry_v1",
  "tag": "$TAG",
  "ts_utc": "$TS_UTC",
  "input_sha256": "$INPUT_SHA",
  "manifest_sha256": "$MANIFEST_SHA",
  "evidence_sha256": "$EVIDENCE_SHA",
  "verification_keys_sha256": "$KEYS_SHA",
  "bundle_sha_run1": "$RUN1_SHA",
  "bundle_sha_run2": "$RUN2_SHA",
  "verify_rc": 0,
  "repro_rc": 0,
  "tamper_rc": 2,
  "machine_role": "A",
  "machine_id": "$MACHINE_ID",
  "sync_mode": "remote",
  "bundle_sha256": null,
  "x_tag_sig_fpr": null
}
\`\`\`
EOF_ENTRY

python3 scripts/validate_evidence_log.py \
  --tag "$TAG" \
  --log "$LOG" \
  --required-machine-role A >/dev/null
echo "PREP_EVIDENCE=PASS tag=$TAG"

git add "$LOG"
git commit -m "governance: evidence for $TAG"
git push origin main

echo "PREP_STATUS=GO tag=$TAG"
