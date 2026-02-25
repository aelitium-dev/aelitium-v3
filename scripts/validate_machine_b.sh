#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p "${HOME}/machine_b/logs"

./scripts/gate_release.sh v3.0.0-rc3 tests/fixtures/input_min.json |& tee "${HOME}/machine_b/logs/gate_rc3.txt"
echo "RC_GATE=${PIPESTATUS[0]}" | tee -a "${HOME}/machine_b/logs/gate_rc3.txt"

./scripts/bundle_determinism_check.sh |& tee "${HOME}/machine_b/logs/bundle_determinism.txt"
echo "RC_BUNDLE=${PIPESTATUS[0]}" | tee -a "${HOME}/machine_b/logs/bundle_determinism.txt"
