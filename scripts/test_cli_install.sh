#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=./use_test_signing_key.sh
source "$ROOT/scripts/use_test_signing_key.sh"
INPUT="$ROOT/tests/fixtures/input_min.json"
TMP=""
RUNNER=""

if [[ ! -f "$INPUT" ]]; then
  echo "CLI_TEST_STATUS=FAIL reason=INPUT_MISSING input=$INPUT"
  exit 2
fi

cleanup() {
  local target="${TMP:-}"
  if [[ -n "$target" && -d "$target" ]]; then
    rm -rf -- "$target"
  fi
}
trap cleanup EXIT

fail() {
  echo "$1"
  exit 2
}

TMP="$(mktemp -d)"
VENV="$TMP/venv"
WORK="$TMP/work"
TARGET="$TMP/target"
SHIM_DIR="$TMP/bin"

mkdir -p "$WORK"

if python3 -m venv --system-site-packages "$VENV" >/dev/null 2>&1; then
  if "$VENV/bin/python" -c "import cryptography, setuptools" >/dev/null 2>&1 && (
    cd "$ROOT"
    "$VENV/bin/python" -m pip install --no-build-isolation --no-deps .
  ); then
    RUNNER="$VENV/bin/aelitium"
    echo "CLI_INSTALL_MODE=venv"
  fi
fi

if [[ -z "$RUNNER" ]]; then
  mkdir -p "$TARGET" "$SHIM_DIR"
  if python3 -m pip --version >/dev/null 2>&1; then
    if (
      cd "$ROOT"
      python3 -m pip install --no-build-isolation --no-deps --target "$TARGET" .
    ); then
      echo "CLI_INSTALL_MODE=target"
    else
      cp -a "$ROOT/engine" "$TARGET/"
      echo "CLI_INSTALL_MODE=copy"
    fi
  else
    cp -a "$ROOT/engine" "$TARGET/"
    echo "CLI_INSTALL_MODE=copy"
  fi
  cat > "$SHIM_DIR/aelitium" <<EOF_SHIM
#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="$TARGET\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m engine.cli "\$@"
EOF_SHIM
  chmod +x "$SHIM_DIR/aelitium"
  RUNNER="$SHIM_DIR/aelitium"
fi

if [[ -z "$RUNNER" ]]; then
  fail "CLI_INSTALL=FAIL"
fi
echo "CLI_INSTALL=PASS"

if ! (
  cd "$WORK"
  "$RUNNER" --help >/dev/null
); then
  fail "CLI_HELP=FAIL"
fi
echo "CLI_HELP=PASS"

if ! (
  cd "$WORK"
  "$RUNNER" pack --input "$INPUT" --out ./bundle >/dev/null
); then
  fail "CLI_PACK=FAIL"
fi
echo "CLI_PACK=PASS"

if ! (
  cd "$WORK"
  "$RUNNER" verify --manifest ./bundle/manifest.json --evidence ./bundle/evidence_pack.json >/dev/null
); then
  fail "CLI_VERIFY=FAIL"
fi
echo "CLI_VERIFY=PASS"

if ! (
  cd "$WORK"
  "$RUNNER" repro --input "$INPUT" >/dev/null
); then
  fail "CLI_REPRO=FAIL"
fi
echo "CLI_REPRO=PASS"
echo "CLI_TEST_STATUS=PASS"
