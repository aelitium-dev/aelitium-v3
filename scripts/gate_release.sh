#!/usr/bin/env bash
set -euo pipefail

INPUT=$1
OUTDIR="release_output"

rm -rf "$OUTDIR"

python3 engine/cli.py pack --input "$INPUT" --out "$OUTDIR"
python3 engine/cli.py verify \
  --manifest "$OUTDIR/manifest.json" \
  --evidence "$OUTDIR/evidence_pack.json"

python3 engine/cli.py repro --input "$INPUT"

echo "RELEASE_STATUS=GO"
