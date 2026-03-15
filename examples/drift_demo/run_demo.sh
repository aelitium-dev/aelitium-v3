#!/usr/bin/env bash
# AELITIUM drift demo — no API key required
# Demonstrates: same request, different model response, proved by hashes.
#
# Usage:
#   cd /path/to/aelitium-v3
#   pip install -e .          # or: source .venv/bin/activate
#   bash examples/drift_demo/run_demo.sh

set -euo pipefail

# Activate venv if present and aelitium not already on PATH
if ! command -v aelitium &>/dev/null; then
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
    source "$REPO_ROOT/.venv/bin/activate"
  fi
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_A="$SCRIPT_DIR/bundle_a"
BUNDLE_B="$SCRIPT_DIR/bundle_b"

# Generate bundles if they don't exist yet
if [[ ! -d "$BUNDLE_A" ]] || [[ ! -d "$BUNDLE_B" ]]; then
  echo "Generating demo bundles (one-time setup)..."
  python3 "$SCRIPT_DIR/generate_bundles.py"
  echo ""
fi

echo "Prompt: \"Explain in one sentence why the sky is blue.\""
echo ""
echo "Run A — bundle_a:"
cat "$BUNDLE_A/ai_canonical.json" | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print('  ' + d.get('output',''))"
echo ""
echo "Run B — bundle_b:"
cat "$BUNDLE_B/ai_canonical.json" | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print('  ' + d.get('output',''))"
echo ""
echo "--- aelitium compare ---"
echo ""
aelitium compare "$BUNDLE_A" "$BUNDLE_B" || true
echo ""
echo "Same request. Different output. The change came from the model, not your code."
