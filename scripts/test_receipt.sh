#!/usr/bin/env bash
# test_receipt.sh — authority receipt demo on the canonical CLI path (ai_cli.py)
#
# Flow:
#   1. generate ephemeral Ed25519 key pair
#   2. issue a receipt_v1 signed by that key
#   3. verify intact receipt — must pass (rc=0)
#   4. tamper receipt (flip subject_hash_sha256)
#   5. verify tampered receipt — must fail (rc!=0)
#
# Exit codes:
#   0  RECEIPT_STATUS=PASS
#   2  RECEIPT_STATUS=FAIL

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$REPO_ROOT"

TMPDIR_LOCAL="$(mktemp -d /tmp/aelitium_receipt_XXXXXX)"

cleanup() {
    python3 - "$TMPDIR_LOCAL" <<'PY'
import sys, shutil, os
p = sys.argv[1]
if os.path.isdir(p):
    shutil.rmtree(p)
PY
}
trap cleanup EXIT

RECEIPT_FILE="$TMPDIR_LOCAL/receipt.json"
PUBKEY_FILE="$TMPDIR_LOCAL/authority_pub.b64"
TAMPERED_FILE="$TMPDIR_LOCAL/receipt_tampered.json"

# 1+2. generate key pair and issue a signed receipt_v1
python3 - "$RECEIPT_FILE" "$PUBKEY_FILE" <<'PY'
import base64, hashlib, json, os, sys, uuid
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

receipt_path, pubkey_path = sys.argv[1], sys.argv[2]

# ephemeral key pair
priv = Ed25519PrivateKey.generate()
pub_bytes = priv.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw
)
pub_b64 = base64.b64encode(pub_bytes).decode("ascii")

# subject: a plausible ai_output hash
subject_hash = hashlib.sha256(b"example ai output for receipt demo").hexdigest()

receipt = {
    "schema_version": "receipt_v1",
    "receipt_id": str(uuid.uuid4()),
    "ts_signed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "subject_hash_sha256": subject_hash,
    "subject_type": "ai_output_v1",
    "authority_fingerprint": hashlib.sha256(pub_bytes).hexdigest()[:16],
    "authority_signature": "",
}

# sign canonical receipt with empty signature field
canon = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
sig = priv.sign(canon.encode("utf-8"))
receipt["authority_signature"] = base64.b64encode(sig).decode("ascii")

open(receipt_path, "w").write(json.dumps(receipt, sort_keys=True, indent=2))
open(pubkey_path, "w").write(pub_b64)
PY

# 3. verify intact receipt — must pass
set +e
INTACT_OUTPUT="$(python3 -m engine.ai_cli verify-receipt --receipt "$RECEIPT_FILE" --pubkey "$PUBKEY_FILE" 2>&1)"
INTACT_RC=$?
set -e

if [[ "$INTACT_RC" -ne 0 ]]; then
    echo "RECEIPT_STATUS=FAIL reason=INTACT_RECEIPT_FAILED_VERIFY rc=$INTACT_RC"
    echo "DETAIL=$INTACT_OUTPUT"
    exit 2
fi

RECEIPT_ID="$(echo "$INTACT_OUTPUT" | grep -oP 'RECEIPT_ID=\S+' | head -1)"
SUBJECT_HASH="$(echo "$INTACT_OUTPUT" | grep -oP 'SUBJECT_HASH_SHA256=\S+' | head -1)"

# 4. tamper: flip subject_hash_sha256 in the receipt
python3 - "$RECEIPT_FILE" "$TAMPERED_FILE" <<'PY'
import json, sys
obj = json.loads(open(sys.argv[1]).read())
obj["subject_hash_sha256"] = "f" * 64
open(sys.argv[2], "w").write(json.dumps(obj, sort_keys=True, indent=2))
PY

# 5. verify tampered receipt — must fail
set +e
TAMPER_OUTPUT="$(python3 -m engine.ai_cli verify-receipt --receipt "$TAMPERED_FILE" --pubkey "$PUBKEY_FILE" 2>&1)"
TAMPER_RC=$?
set -e

if [[ "$TAMPER_RC" -eq 0 ]]; then
    echo "RECEIPT_STATUS=FAIL reason=TAMPER_NOT_DETECTED rc=$TAMPER_RC"
    echo "DETAIL=$TAMPER_OUTPUT"
    exit 2
fi

if ! echo "$TAMPER_OUTPUT" | grep -qE "SIGNATURE_INVALID|INVALID|MISMATCH"; then
    echo "RECEIPT_STATUS=FAIL reason=UNEXPECTED_FAILURE_REASON rc=$TAMPER_RC"
    echo "DETAIL=$TAMPER_OUTPUT"
    exit 2
fi

echo "RECEIPT_STATUS=PASS"
echo "RECEIPT_OK_RC=0"
echo "RECEIPT_TAMPER_RC=$TAMPER_RC"
echo "$RECEIPT_ID"
echo "$SUBJECT_HASH"
echo "FAILURE_REASON=$(echo "$TAMPER_OUTPUT" | grep -oP 'reason=\S+' | head -1)"
