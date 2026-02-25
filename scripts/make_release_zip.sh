#!/usr/bin/env bash
set -euo pipefail
umask 022
export LC_ALL=C
export TZ=UTC

ROOT="1000 4 24 27 30 46 100 1000cd "1000 4 24 27 30 46 100 1000dirname "")/.." && pwd)"
OUTDIR="/dist"

ROOT="1000 4 24 27 30 46 100 1000pwd)"
OUTDIR="/dist"
ZIP_NAME="release_output.zip"
META_NAME="release_metadata.json"
LIST_NAME="zip_file_list.txt"

FIXED_TOUCH_TS="200001010000.00"
CREATED_UTC_FIXED="2000-01-01T00:00:00Z"

PAYLOAD_DIR="release_output"
VERIFIER_SCRIPT="scripts/offline_verify.sh"

if [[ ! -d "$PAYLOAD_DIR" ]]; then
  echo "ZIP_STATUS=NO_GO reason=PAYLOAD_DIR_MISSING dir=$PAYLOAD_DIR"
  exit 2
fi
if [[ ! -f "$VERIFIER_SCRIPT" ]]; then
  echo "ZIP_STATUS=NO_GO reason=VERIFIER_MISSING path=$VERIFIER_SCRIPT"
  exit 2
fi

rm -rf "$OUTDIR"
mkdir -p "$OUTDIR"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/offline_verifier" "$STAGE/payload"

# Copy verifier + payload
cp -a "$VERIFIER_SCRIPT" "$STAGE/offline_verifier/"
cp -a "$PAYLOAD_DIR/." "$STAGE/payload/"

# Remove common junk (fail-closed safe; deletions are deterministic)
find "$STAGE" -type f \( -name ".DS_Store" -o -name "Thumbs.db" -o -name "*.pyc" -o -name "*.pyo" \) -delete || true
find "$STAGE" -type d \( -name "__pycache__" -o -name ".pytest_cache" \) -prune -exec rm -rf {} + || true

# Normalize timestamps
find "$STAGE" -print0 | xargs -0 touch -t "$FIXED_TOUCH_TS"

# Deterministic per-file manifest (audit)
(
  cd "$STAGE"
  find . -type f -print0 \
    | sort -z \
    | xargs -0 sha256sum
) > "$OUTDIR/inputs_manifest.sha256"

INPUTS_MANIFEST_SHA256="$(sha256sum "$OUTDIR/inputs_manifest.sha256" | awk '{print $1}')"

# Deterministic file list (relative paths, no leading ./)
(
  cd "$STAGE"
  find . -type f -print0 \
    | sort -z \
    | python3 - <<'PY'
import sys
data = sys.stdin.buffer.read().split(b"\x00")
paths = [p.decode("utf-8") for p in data if p]
# strip leading "./"
paths = [p[2:] if p.startswith("./") else p for p in paths]
for p in paths:
    print(p)
PY
) > "$OUTDIR/$LIST_NAME"

# Build zip deterministically from list (no shell word-splitting)
(
  cd "$STAGE"
  python3 - <<'PY'
import os, zipfile, time

outdir = os.environ["OUTDIR"]
zip_name = os.environ["ZIP_NAME"]
list_name = os.environ["LIST_NAME"]

# Fixed DOS datetime: 2000-01-01 00:00:00
fixed_dt = (2000, 1, 1, 0, 0, 0)

zip_path = os.path.join(outdir, zip_name)
files = [line.rstrip("\n") for line in open(os.path.join(outdir, list_name), "r", encoding="utf-8") if line.strip()]

# Create ZIP with deterministic metadata:
# - fixed timestamps (ZipInfo.date_time)
# - stable permissions (0o644 for files)
# - no extra fields we control
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for rel in files:
        src = rel  # rel path within stage
        zi = zipfile.ZipInfo(rel, date_time=fixed_dt)
        # set Unix file perms: -rw-r--r--
        zi.external_attr = (0o644 & 0xFFFF) << 16
        with open(src, "rb") as f:
            z.writestr(zi, f.read())
print("ZIP_BUILD=OK")
PY
)

ZIP_SHA256="$(sha256sum "$OUTDIR/$ZIP_NAME" | awk '{print $1}')"

cat > "$OUTDIR/$META_NAME" <<EOF_META
{
  "zip_filename": "$ZIP_NAME",
  "zip_sha256": "$ZIP_SHA256",
  "created_utc": "$CREATED_UTC_FIXED",
  "inputs_manifest_sha256": "$INPUTS_MANIFEST_SHA256",
  "deterministic": true,
  "signed": false,
  "verifier": {
    "type": "aelitium-offline",
    "command": "./offline_verifier/offline_verify.sh payload"
  }
}
EOF_META

echo "ZIP_STATUS=GO"
echo "ZIP_PATH=$OUTDIR/$ZIP_NAME"
echo "ZIP_SHA256=$ZIP_SHA256"
echo "META_PATH=$OUTDIR/$META_NAME"
