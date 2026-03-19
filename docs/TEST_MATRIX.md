# TEST MATRIX — AELITIUM

Scope: determinism, tamper detection, offline verification, comparison semantics, and receipt verification for the current implemented surface.

Rule: if a test does not have observable output and explicit PASS/FAIL criteria, it is not claimed here.

---

## Preconditions

- Run commands from the repository root.
- Commands below use the current local source tree.
- `python3` must be available.
- Receipt verification requires the test fixture key already present in `tests/fixtures/ed25519_test_private_key.b64`.

---

## Test 1 — Same input, same binding hash

- Objective:
  Verify deterministic `binding_hash` generation for identical captured request/response inputs.

- Command:

```bash
python3 -m unittest tests.test_capture_litellm.TestCaptureLiteLLM.test_binding_hash_deterministic -v
```

- Input:
  The deterministic LiteLLM capture test fixture in `tests/test_capture_litellm.py`.

- Expected result:
  The test exits successfully and reports `ok`.

- Pass criteria:
  The unittest process exits `0`.

- Evidence generated:
  Unittest output showing the deterministic binding-hash test passed.

- Non-goal:
  Does not prove identical model outputs across real provider runs.

---

## Test 2 — Tamper => INVALID

- Objective:
  Verify that modifying bundle contents after packing causes bundle verification to fail.

- Command:

```bash
TMPDIR=$(mktemp -d)
cp -R examples/drift_demo/bundle_a "$TMPDIR/bundle"
python3 -m engine.ai_cli verify-bundle "$TMPDIR/bundle"
sed -i 's/sky is blue/SKY IS BLUE/' "$TMPDIR/bundle/ai_canonical.json"
python3 -m engine.ai_cli verify-bundle "$TMPDIR/bundle"
```

- Input:
  `examples/drift_demo/bundle_a`

- Expected result:
  The first verification returns `STATUS=VALID rc=0`.
  The second verification returns `STATUS=INVALID rc=2`.

- Pass criteria:
  The second verification output includes `reason=HASH_MISMATCH`.

- Evidence generated:
  CLI output for both verification runs.

- Non-goal:
  Does not prove anything about the original model output beyond the bundle contents.

---

## Test 3 — Offline verify-bundle

- Objective:
  Verify that a valid bundle can be checked offline using local bundle files only.

- Command:

```bash
python3 -m engine.ai_cli verify-bundle examples/drift_demo/bundle_a
```

- Input:
  `examples/drift_demo/bundle_a`

- Expected result:
  `STATUS=VALID rc=0`

- Pass criteria:
  Output includes:
  - `STATUS=VALID rc=0`
  - `AI_HASH_SHA256=`
  - `BINDING_HASH=`

- Evidence generated:
  CLI verification output.

- Non-goal:
  Does not prove when the bundle was generated.

---

## Test 4 — Compare => UNCHANGED / CHANGED

- Objective:
  Verify the observable comparison outcomes for unchanged and changed bundle pairs.

- Command:

```bash
python3 -m engine.ai_cli compare examples/drift_demo/bundle_a examples/drift_demo/bundle_a
python3 -m engine.ai_cli compare examples/drift_demo/bundle_a examples/drift_demo/bundle_b || true
```

- Input:
  `examples/drift_demo/bundle_a`
  `examples/drift_demo/bundle_b`

- Expected result:
  First command returns `STATUS=UNCHANGED rc=0`.
  Second command returns `STATUS=CHANGED rc=2`.

- Pass criteria:
  Output includes:
  - `REQUEST_HASH=SAME`
  - `RESPONSE_HASH=SAME` for the unchanged case
  - `RESPONSE_HASH=DIFFERENT` for the changed case

- Evidence generated:
  CLI comparison output for both runs.

- Non-goal:
  Does not explain why a change occurred.

---

## Test 5 — Receipt verification

- Objective:
  Verify that a signed receipt can be checked offline with the current receipt verifier.

- Command:

```bash
TMPDIR=$(mktemp -d)
export AEL_ED25519_PRIVKEY_B64="$(tr -d '\n' < tests/fixtures/ed25519_test_private_key.b64)"
export TMPDIR
python3 - <<'PY'
import json
import os
from pathlib import Path
from p3.server.signing import authority_public_key_b64, sign_receipt

tmp = Path(os.environ["TMPDIR"])
receipt = sign_receipt(subject_hash="b" * 64, subject_type="ai_output_v1")
(tmp / "receipt.json").write_text(json.dumps(receipt) + "\n", encoding="utf-8")
(tmp / "pubkey.b64").write_text(authority_public_key_b64(), encoding="utf-8")
PY
python3 -m engine.ai_cli verify-receipt \
  --receipt "$TMPDIR/receipt.json" \
  --pubkey "$TMPDIR/pubkey.b64" \
  --hash "$(python3 - <<'PY'
print('b' * 64)
PY
)"
```

- Input:
  The test fixture private key in `tests/fixtures/ed25519_test_private_key.b64`

- Expected result:
  `STATUS=VALID rc=0`

- Pass criteria:
  Output includes:
  - `STATUS=VALID rc=0`
  - `SUBJECT_HASH_SHA256=`
  - `RECEIPT_ID=`

- Evidence generated:
  `receipt.json`, `pubkey.b64`, and CLI verification output.

- Non-goal:
  Does not establish a real-world timeline beyond the receipt contents.

---

## Test 6 — Receipt verification => INVALID signature

- Objective:
  Verify that receipt verification fails when a signed receipt is modified after signing.

- Command:

```bash
TMPDIR=$(mktemp -d)
export AEL_ED25519_PRIVKEY_B64="$(tr -d '\n' < tests/fixtures/ed25519_test_private_key.b64)"
export TMPDIR
python3 - <<'PY'
import json
import os
from pathlib import Path
from p3.server.signing import authority_public_key_b64, sign_receipt

tmp = Path(os.environ["TMPDIR"])
receipt = sign_receipt(subject_hash="b" * 64, subject_type="ai_output_v1")
receipt["subject_hash_sha256"] = "c" * 64
(tmp / "receipt.json").write_text(json.dumps(receipt) + "\n", encoding="utf-8")
(tmp / "pubkey.b64").write_text(authority_public_key_b64(), encoding="utf-8")
PY
python3 -m engine.ai_cli verify-receipt \
  --receipt "$TMPDIR/receipt.json" \
  --pubkey "$TMPDIR/pubkey.b64" \
  --hash "$(python3 - <<'PY'
print('c' * 64)
PY
)"
```

- Input:
  Modified signed receipt based on the test fixture key.

- Expected result:
  `STATUS=INVALID rc=2`

- Pass criteria:
  The verifier exits non-zero and reports `reason=SIGNATURE_INVALID`.

- Evidence generated:
  Modified `receipt.json`, `pubkey.b64`, and CLI verification output.

- Non-goal:
  Does not prove anything beyond signature verification failure for the modified receipt.
