#!/usr/bin/env bash
# test_tamper_ai.sh — tamper detection demo on the canonical CLI path (ai_cli.py)
#
# Flow:
#   1. pack a bundle via python3 -m engine.ai_cli pack
#   2. verify intact bundle — must pass (rc=0)
#   3. tamper ai_canonical.json (flip output field)
#   4. verify-bundle — must fail with HASH_MISMATCH (rc=2)
#
# Exit codes:
#   0  AI_TAMPER_STATUS=PASS
#   2  AI_TAMPER_STATUS=FAIL

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$REPO_ROOT"

INPUT_FILE="$(mktemp /tmp/aelitium_test_input_XXXXXX.json)"
BUNDLE_DIR="$(mktemp -d /tmp/aelitium_test_bundle_XXXXXX)"

cleanup() {
    python3 - "$INPUT_FILE" "$BUNDLE_DIR" <<'PY'
import sys, shutil, os
for p in sys.argv[1:]:
    if os.path.isdir(p):
        shutil.rmtree(p)
    elif os.path.isfile(p):
        os.remove(p)
PY
}
trap cleanup EXIT

# 1. create minimal ai_output_v1 input
python3 - "$INPUT_FILE" <<'PY'
import json, sys
json.dump({
    "schema_version": "ai_output_v1",
    "ts_utc": "2026-01-01T00:00:00Z",
    "model": "gpt-4o",
    "prompt": "What is the capital of France?",
    "output": "The capital of France is Paris."
}, open(sys.argv[1], "w"), sort_keys=True)
PY

# 2. pack
python3 -m engine.ai_cli pack --input "$INPUT_FILE" --out "$BUNDLE_DIR" > /dev/null

# 3. verify intact bundle — must pass
set +e
python3 -m engine.ai_cli verify-bundle "$BUNDLE_DIR" > /dev/null 2>&1
INTACT_RC=$?
set -e

if [[ "$INTACT_RC" -ne 0 ]]; then
    echo "AI_TAMPER_STATUS=FAIL reason=INTACT_BUNDLE_FAILED_VERIFY rc=$INTACT_RC"
    exit 2
fi

# 4. tamper: replace output content inside ai_canonical.json
python3 - "$BUNDLE_DIR/ai_canonical.json" <<'PY'
import json, sys
path = sys.argv[1]
obj = json.loads(open(path).read())
obj["output"] = "TAMPERED OUTPUT"
open(path, "w").write(json.dumps(obj, sort_keys=True, separators=(",", ":")))
PY

# 5. verify-bundle on tampered bundle — must fail
set +e
VERIFY_OUTPUT="$(python3 -m engine.ai_cli verify-bundle "$BUNDLE_DIR" 2>&1)"
TAMPER_RC=$?
set -e

if [[ "$TAMPER_RC" -eq 0 ]]; then
    echo "AI_TAMPER_STATUS=FAIL reason=TAMPER_NOT_DETECTED rc=$TAMPER_RC"
    echo "DETAIL=$VERIFY_OUTPUT"
    exit 2
fi

if ! echo "$VERIFY_OUTPUT" | grep -qE "HASH_MISMATCH|INVALID|mismatch"; then
    echo "AI_TAMPER_STATUS=FAIL reason=UNEXPECTED_FAILURE_REASON rc=$TAMPER_RC"
    echo "DETAIL=$VERIFY_OUTPUT"
    exit 2
fi

echo "AI_TAMPER_STATUS=PASS"
echo "AI_TAMPER_RC=$TAMPER_RC"
echo "FAILURE_REASON=$(echo "$VERIFY_OUTPUT" | grep -oP 'reason=\S+' | head -1)"
