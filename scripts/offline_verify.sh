#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: offline_verify.sh <release_output_dir | bundle.zip>"
  exit 2
fi

SRC="$1"
WORK=""
WORK_OWNED=0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ENGINE_CLI=""
EXPECTED_BUNDLE_FILES=(
  "evidence_pack.json"
  "manifest.json"
  "verification_keys.json"
)

for candidate in \
  "$SCRIPT_DIR/../engine/cli.py" \
  "$SCRIPT_DIR/engine/cli.py"
do
  if [[ -f "$candidate" ]]; then
    ENGINE_CLI="$candidate"
    break
  fi
done

if [[ -z "$ENGINE_CLI" ]]; then
  echo "VERIFY_STATUS=NO_GO reason=ENGINE_CLI_NOT_FOUND"
  exit 2
fi

make_workdir() {
  local cwd

  WORK="$(mktemp -d)"
  WORK_OWNED=1
  cwd="$(pwd -P)"

  if [[ -z "$WORK" || ! -d "$WORK" || "$WORK" == "/" || "$WORK" == "$cwd" ]]; then
    echo "VERIFY_STATUS=NO_GO reason=UNSAFE_WORKDIR path=${WORK:-<empty>}"
    exit 2
  fi
}

cleanup() {
  local target="${WORK:-}"
  local cwd

  if [[ "${WORK_OWNED:-0}" != "1" ]]; then
    return
  fi
  if [[ -z "$target" || ! -d "$target" ]]; then
    return
  fi

  cwd="$(pwd -P)"
  if [[ "$target" == "/" || "$target" == "$cwd" ]]; then
    echo "VERIFY_STATUS=NO_GO reason=UNSAFE_CLEANUP path=$target" >&2
    return
  fi

  rm -rf -- "$target"
}
trap cleanup EXIT

if [[ -d "$SRC" ]]; then
  make_workdir
  if ! cp -a "$SRC"/. "$WORK"/; then
    echo "VERIFY_STATUS=NO_GO reason=COPY_FAILED path=$SRC"
    exit 2
  fi
elif [[ -f "$SRC" ]]; then
  make_workdir
  case "$SRC" in
    *.zip)
      if ! python3 - "$SRC" "$WORK" <<'PY'
import sys
import zipfile
from pathlib import PurePosixPath

src = sys.argv[1]
dst = sys.argv[2]

try:
    with zipfile.ZipFile(src) as zf:
        for info in zf.infolist():
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts:
                raise SystemExit(f"ZIP_PATH_INVALID:{info.filename}")
        zf.extractall(dst)
except SystemExit:
    raise
except Exception as exc:
    raise SystemExit(f"ZIP_EXTRACT_FAILED:{exc}")

print("EXTRACT=OK")
PY
      then
        echo "VERIFY_STATUS=NO_GO reason=ZIP_EXTRACT_FAILED path=$SRC"
        exit 2
      fi
      ;;
    *)
      echo "VERIFY_STATUS=NO_GO reason=UNSUPPORTED_BUNDLE_FORMAT path=$SRC"
      exit 2
      ;;
  esac
else
  echo "VERIFY_STATUS=NO_GO reason=NOT_FOUND path=$SRC"
  exit 2
fi

MANIFEST="$WORK/manifest.json"
EVIDENCE="$WORK/evidence_pack.json"
VK="$WORK/verification_keys.json"

mapfile -t bundle_entries < <(find "$WORK" -mindepth 1 -maxdepth 1 -printf '%P\n' | LC_ALL=C sort)
if [[ "${#bundle_entries[@]}" -ne "${#EXPECTED_BUNDLE_FILES[@]}" ]]; then
  echo "VERIFY_STATUS=NO_GO reason=BUNDLE_LAYOUT_INVALID"
  exit 2
fi

for i in "${!EXPECTED_BUNDLE_FILES[@]}"; do
  if [[ "${bundle_entries[$i]}" != "${EXPECTED_BUNDLE_FILES[$i]}" ]]; then
    echo "VERIFY_STATUS=NO_GO reason=BUNDLE_LAYOUT_INVALID"
    exit 2
  fi
done

for f in "$MANIFEST" "$EVIDENCE" "$VK"; do
  if [[ ! -f "$f" ]]; then
    echo "VERIFY_STATUS=NO_GO reason=MISSING_FILE file=$f"
    exit 2
  fi
done

# hashes for audit (offline)
echo "MANIFEST_SHA256=$(sha256sum "$MANIFEST" | awk "{print \$1}")"
echo "EVIDENCE_SHA256=$(sha256sum "$EVIDENCE" | awk "{print \$1}")"
echo "VK_SHA256=$(sha256sum "$VK" | awk "{print \$1}")"

# deterministic verify (fail-closed)
python3 "$ENGINE_CLI" verify \
  --manifest "$MANIFEST" \
  --evidence "$EVIDENCE"

echo "VERIFY_STATUS=GO"
