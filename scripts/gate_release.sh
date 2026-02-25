#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: gate_release.sh <release_tag> <input.json>"
  exit 2
fi

TAG="$1"
INPUT="$2"
OUTDIR="release_output"

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
cat > "$OUTDIR/release_metadata.json" <<EOF
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
EOF

# --- Create tag only after success ---

# --- Bundle determinism (mandatory) ---
./scripts/bundle_determinism_check.sh
RC_BUNDLE=$?
if [[ "$RC_BUNDLE" -ne 0 ]]; then
  echo "RELEASE_STATUS=NO_GO reason=NON_DETERMINISTIC_BUNDLE rc=$RC_BUNDLE"
  exit 2
fi

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  echo "TAG_STATUS=EXISTS tag=$TAG"
else
  git tag "$TAG"
  echo "TAG_STATUS=CREATED tag=$TAG"
fi

echo "RELEASE_STATUS=GO tag=$TAG"