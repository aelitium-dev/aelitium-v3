#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE="$ROOT/scripts/gate_release.sh"
INPUT="$ROOT/inputs/minimal_input_v1.json"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

BIN="$TMP/bin"
OUT_INVALID="$TMP/out_invalid.txt"
OUT_VALID="$TMP/out_valid.txt"
GIT_MARK="$TMP/git_called.txt"
mkdir -p "$BIN"

cat > "$BIN/git" <<EOF_GIT
#!/usr/bin/env bash
echo "git-called" >> "$GIT_MARK"
exit 99
EOF_GIT
chmod +x "$BIN/git"

run_gate() {
  local tag="$1"
  local out="$2"
  set +e
  (
    cd "$ROOT"
    PATH="$BIN:$PATH" "$GATE" "$tag" "$INPUT"
  ) >"$out" 2>&1
  RUN_RC=$?
  set -e
}

# Case 1: missing evidence entry for tag => must fail with rc=2 before git is touched.
run_gate "v9.9.9" "$OUT_INVALID"
if [[ "${RUN_RC:-}" -eq 0 ]]; then
  echo "SELFTEST=FAIL reason=INVALID_TAG_UNEXPECTED_SUCCESS"
  exit 2
fi
if [[ "${RUN_RC:-}" -ne 2 ]]; then
  echo "SELFTEST=FAIL reason=INVALID_TAG_WRONG_RC rc=${RUN_RC:-NA}"
  exit 2
fi
if [[ -f "$GIT_MARK" ]]; then
  echo "SELFTEST=FAIL reason=GIT_CALLED_BEFORE_EVIDENCE_BLOCK"
  exit 2
fi
if ! grep -q "RELEASE_STATUS=NO_GO reason=EVIDENCE_INVALID" "$OUT_INVALID"; then
  echo "SELFTEST=FAIL reason=MISSING_EVIDENCE_INVALID_MESSAGE"
  exit 2
fi

# Case 2: valid evidence tag should pass evidence gate and then hit git (stub exits 99).
run_gate "v0.1.0" "$OUT_VALID"
if [[ "${RUN_RC:-}" -eq 0 ]]; then
  echo "SELFTEST=FAIL reason=VALID_TAG_UNEXPECTED_SUCCESS"
  exit 2
fi
if [[ "${RUN_RC:-}" -eq 2 ]]; then
  echo "SELFTEST=FAIL reason=VALID_TAG_FAILED_ON_EVIDENCE"
  exit 2
fi
if [[ ! -f "$GIT_MARK" ]]; then
  echo "SELFTEST=FAIL reason=GIT_NOT_REACHED_AFTER_EVIDENCE_PASS"
  exit 2
fi

echo "SELFTEST=PASS"
