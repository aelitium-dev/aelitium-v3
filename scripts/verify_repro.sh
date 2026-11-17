#!/usr/bin/env bash
# verify_repro.sh — reproducibility check for AELITIUM
#
# Runs the full pipeline from a clean venv:
#   1. create venv + install
#   2. run test suite
#   3. pack examples/ai_output_min.json twice
#   4. verify both bundles produce the same hash
#
# Exit 0 = all checks passed
# Exit 1 = failure (with message)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

VENV_DIR=".venv_repro"
INPUT="examples/ai_output_min.json"
OUT1="/tmp/aelitium_repro_run1"
OUT2="/tmp/aelitium_repro_run2"

cleanup() {
    rm -rf "$VENV_DIR" "$OUT1" "$OUT2"
}
trap cleanup EXIT

echo "=== AELITIUM reproducibility check ==="
echo "Repo: $REPO_ROOT"
echo ""

# --- 1. venv + install ---
echo "[1/4] Creating clean venv..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install -e . -q
echo "      OK"

# --- 2. test suite ---
echo "[2/4] Running test suite..."
python3 -m unittest discover -s tests -q 2>&1 | tail -2
echo "      OK"

# --- 3. pack twice ---
echo "[3/4] Packing '$INPUT' (run 1 + run 2)..."
python3 -m engine.ai_cli pack --input "$INPUT" --out "$OUT1" --json > /tmp/repro_r1.json
python3 -m engine.ai_cli pack --input "$INPUT" --out "$OUT2" --json > /tmp/repro_r2.json

HASH1=$(python3 -c "import json,sys; print(json.load(open('/tmp/repro_r1.json'))['ai_hash_sha256'])")
HASH2=$(python3 -c "import json,sys; print(json.load(open('/tmp/repro_r2.json'))['ai_hash_sha256'])")
echo "      Run 1: $HASH1"
echo "      Run 2: $HASH2"

# --- 4. compare ---
echo "[4/4] Comparing hashes..."
if [ "$HASH1" = "$HASH2" ]; then
    echo "      MATCH ✓"
else
    echo "      MISMATCH ✗ — build is not reproducible"
    exit 1
fi

echo ""
echo "=== RESULT: PASS ==="
echo "AI_HASH_SHA256=$HASH1"
