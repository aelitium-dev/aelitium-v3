#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: gate_release.sh <release_tag> <input.json>"
  exit 2
fi

TAG="$1"
INPUT="$2"
OUTDIR="release_output"
LOGDIR="governance/logs"
EVIDENCE_LOG="$LOGDIR/EVIDENCE_LOG.md"

mkdir -p "$LOGDIR"
rm -rf "$OUTDIR"

# --- A) Git hygiene gate (fail-closed) ---
if [[ -n "$(git status --porcelain=v1)" ]]; then
  echo "RELEASE_STATUS=NO_GO reason=DIRTY_GIT_TREE"
  exit 2
fi

# --- Machine fingerprint (C) ---
HOSTNAME="$(hostname 2>/dev/null || echo unknown)"
KERNEL="$(uname -sr 2>/dev/null || echo unknown)"
MACHINE_ID="$(cat /etc/machine-id 2>/dev/null || echo unknown)"

# --- Run governed pipeline ---
python3 engine/cli.py pack --input "$INPUT" --out "$OUTDIR"
python3 engine/cli.py verify --manifest "$OUTDIR/manifest.json" --evidence "$OUTDIR/evidence_pack.json"
python3 engine/cli.py repro --input "$INPUT"

# --- Hashes for evidence log (C) ---
INPUT_SHA="$(sha256sum "$INPUT" | awk '{print $1}')"
MANIFEST_SHA="$(sha256sum "$OUTDIR/manifest.json" | awk '{print $1}')"
EVIDENCE_SHA="$(sha256sum "$OUTDIR/evidence_pack.json" | awk '{print $1}')"
VK_SHA="$(sha256sum "$OUTDIR/verification_keys.json" | awk '{print $1}')"
GIT_SHA="$(git rev-parse HEAD)"

TS_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# --- B) Tag the release (fail if tag exists) ---
git tag "$TAG"

# --- C) Append Evidence Log entry ---
{
  echo
  echo "## $TAG"
  echo "- ts_utc: $TS_UTC"
  echo "- git_commit: $GIT_SHA"
  echo "- hostname: $HOSTNAME"
  echo "- kernel: $KERNEL"
  echo "- machine_id: $MACHINE_ID"
  echo "- input_path: $INPUT"
  echo "- input_sha256: $INPUT_SHA"
  echo "- manifest_sha256: $MANIFEST_SHA"
  echo "- evidence_pack_sha256: $EVIDENCE_SHA"
  echo "- verification_keys_sha256: $VK_SHA"
  echo "- decision: GO"
} >> "$EVIDENCE_LOG"

echo "RELEASE_STATUS=GO tag=$TAG"
