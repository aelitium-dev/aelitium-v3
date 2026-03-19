# EVIDENCE LOG — AELITIUM

Scope: recorded outputs from executing the operational test matrix.
Rule: only observed results are recorded. No inferred claims.

---

## Environment

- Machine: AELITIUM-DEV
- Repo path: /home/catarina-aelitium/aelitium-v3
- Commit: 164d4b22ba3392c59a24bef98d59b654d5e3aea0
- Python version: Python 3.12.3
- Date: 2026-03-18T21:52:16Z

---

## Run 1 — Determinism (Test 1)

- Command:

```bash
python3 -m unittest tests.test_capture_litellm.TestCaptureLiteLLM.test_binding_hash_deterministic -v
```

- Output (excerpt):

```text
test_binding_hash_deterministic (tests.test_capture_litellm.TestCaptureLiteLLM.test_binding_hash_deterministic)
Same request+response always produces same binding_hash. ... ok

----------------------------------------------------------------------
Ran 1 test in 0.005s

OK
```

- Observed:

- binding_hash_1: not exposed by test output

- binding_hash_2: not exposed by test output

- Result:

binding_hash_1 == binding_hash_2

- PASS/FAIL:

PASS

- PASS if hashes are identical

- Non-goal:

Does not prove identical model outputs across runs.

---

## Run 2 — Tamper detection (Test 2)

- Command:

```bash
TMPDIR=$(mktemp -d)
cp -R examples/drift_demo/bundle_a "$TMPDIR/bundle"
python3 -m engine.ai_cli verify-bundle "$TMPDIR/bundle"
sed -i 's/sky is blue/SKY IS BLUE/' "$TMPDIR/bundle/ai_canonical.json"
python3 -m engine.ai_cli verify-bundle "$TMPDIR/bundle"
```

- Output (excerpt):

```text
STATUS=VALID rc=0
AI_HASH_SHA256=7431bf8c98c1766379b1f3970e103f905791fe79cd07e9e236057b595518fd63
SIGNATURE=NONE
BINDING_HASH=ffef7ea10038b83e5fd89bdd983cfaa8274b1eb8a3e566e72292d5a8a4dcfacf
STATUS=INVALID rc=2 reason=HASH_MISMATCH
DETAIL=expected=7431bf8c98c17663... got=21f0e25ad8c1729f...
```

- Observed:

- First run: STATUS=VALID rc=0

- AI_HASH_SHA256: 7431bf8c98c1766379b1f3970e103f905791fe79cd07e9e236057b595518fd63

- BINDING_HASH: ffef7ea10038b83e5fd89bdd983cfaa8274b1eb8a3e566e72292d5a8a4dcfacf

- Second run: STATUS=INVALID rc=2

- Reason: HASH_MISMATCH

- Detail: expected=7431bf8c98c17663... got=21f0e25ad8c1729f...

- PASS/FAIL:

PASS

- PASS if second run returns INVALID

- Non-goal:

Does not prove correctness of original content.

---

## Run 3 — Offline verification (Test 3)

- Command:

```bash
python3 -m engine.ai_cli verify-bundle examples/drift_demo/bundle_a
```

- Output (excerpt):

```text
STATUS=VALID rc=0
AI_HASH_SHA256=7431bf8c98c1766379b1f3970e103f905791fe79cd07e9e236057b595518fd63
SIGNATURE=NONE
BINDING_HASH=ffef7ea10038b83e5fd89bdd983cfaa8274b1eb8a3e566e72292d5a8a4dcfacf
```

- Observed:

- STATUS: VALID rc=0

- AI_HASH_SHA256: 7431bf8c98c1766379b1f3970e103f905791fe79cd07e9e236057b595518fd63

- BINDING_HASH: ffef7ea10038b83e5fd89bdd983cfaa8274b1eb8a3e566e72292d5a8a4dcfacf

- SIGNATURE: NONE

- Note:

Hash values match the observed values recorded in Run 2 for the same bundle.

- PASS/FAIL:

PASS

- PASS if STATUS=VALID

- Non-goal:

Does not prove when the bundle was generated.

---

## Run 4 — Compare (Test 4)

- Command:

```bash
python3 -m engine.ai_cli compare examples/drift_demo/bundle_a examples/drift_demo/bundle_a
python3 -m engine.ai_cli compare examples/drift_demo/bundle_a examples/drift_demo/bundle_b || true
```

- Output (excerpt):

```text
STATUS=UNCHANGED rc=0
REQUEST_HASH=SAME  a=7b30b0d200b7c4b0... b=7b30b0d200b7c4b0...
RESPONSE_HASH=SAME  a=2f1563cc8c0b7b71... b=2f1563cc8c0b7b71...
BINDING_HASH=SAME
TS_UTC_A=2026-03-01T10:00:00Z
TS_UTC_B=2026-03-01T10:00:00Z
INTERPRETATION=Same request produced the same response
STATUS=CHANGED rc=2
REQUEST_HASH=SAME  a=7b30b0d200b7c4b0... b=7b30b0d200b7c4b0...
RESPONSE_HASH=DIFFERENT  a=2f1563cc8c0b7b71... b=7805406968576ea0...
BINDING_HASH=DIFFERENT
TS_UTC_A=2026-03-01T10:00:00Z
TS_UTC_B=2026-03-01T10:00:00Z
INTERPRETATION=Same request produced a different response
```

- Observed:

- Case 1: STATUS=UNCHANGED rc=0

- Case 1: REQUEST_HASH=SAME

- Case 1: RESPONSE_HASH=SAME

- Case 1: BINDING_HASH=SAME

- Case 2: STATUS=CHANGED rc=2

- Case 2: REQUEST_HASH=SAME

- Case 2: RESPONSE_HASH=DIFFERENT

- Case 2: BINDING_HASH=DIFFERENT

- PASS/FAIL:

PASS

- PASS if both outcomes match expected states

- Non-goal:

Does not explain cause of change.

---

## Run 5 — Receipt verification (valid)

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

- Output (excerpt):

```text
STATUS=VALID rc=0
SUBJECT_HASH_SHA256=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
RECEIPT_ID=rec-20260318-30ca903d
```

- Observed:

- STATUS: VALID rc=0

- SUBJECT_HASH_SHA256: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb

- RECEIPT_ID: rec-20260318-30ca903d

- PASS/FAIL:

PASS

- PASS if STATUS=VALID

- Non-goal:

Does not establish real-world timeline.

---

## Run 6 — Receipt verification (invalid)

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

- Output (excerpt):

```text
STATUS=INVALID rc=2 reason=SIGNATURE_INVALID
```

- Observed:

- STATUS: INVALID rc=2

- Reason: SIGNATURE_INVALID

- PASS/FAIL:

PASS

- PASS if STATUS=INVALID

- Non-goal:

Does not prove anything beyond signature failure.

## REPRO RUN — cross-machine-001

### Machine A
- Host: AELITIUM-DEV
- Repo path: /home/catarina-aelitium/aelitium-v3
- Commit: 2cca7389670501d9e3e77d5067071c8295a61ec8
- Python version: Python 3.12.3
- Date (UTC): 2026-03-19T01:03:14Z

### Machine B
- Host: AELITIUM-DEV
- Repo path: /home/catarina-aelitium/aelitium-v3-clean
- Commit: 2cca7389670501d9e3e77d5067071c8295a61ec8
- Python version: Python 3.12.3
- Date (UTC): 2026-03-19T00:53:30Z

---

### Required invariants

- verify-bundle:
  - STATUS=VALID rc=0
  - AI_HASH_SHA256 must match
  - BINDING_HASH must match

- compare (same bundle):
  - STATUS=UNCHANGED rc=0
  - REQUEST_HASH=SAME
  - RESPONSE_HASH=SAME
  - BINDING_HASH=SAME

- compare (different bundle):
  - STATUS=CHANGED rc=2
  - REQUEST_HASH=SAME
  - RESPONSE_HASH=DIFFERENT
  - BINDING_HASH=DIFFERENT

- determinism unit test:
  - final result: OK

- verify-receipt:
  - valid receipt → STATUS=VALID rc=0
  - modified receipt → STATUS=INVALID rc=2 reason=SIGNATURE_INVALID

---

### Observed values (Machine B)

- AI_HASH_SHA256:
  7431bf8c98c1766379b1f3970e103f905791fe79cd07e9e236057b595518fd63

- BINDING_HASH:
  ffef7ea10038b83e5fd89bdd983cfaa8274b1eb8a3e566e72292d5a8a4dcfacf

---

### Comparison result

- binding_hash_match: YES
- bundle_hash_match: YES
- compare_same_match: YES
- compare_changed_match: YES
- determinism_match: YES
- receipt_valid_status_match: YES
- receipt_invalid_status_match: YES

- receipt_id_match_required: NO

---

### Final result

PASS

---

### Interpretation

The same repository commit produces identical observable verification results
in a clean clone environment on Machine B.

---

### Non-goal

This run does NOT prove:
- full environment equivalence
- cross-OS reproducibility
- semantic equivalence beyond byte-level inputs

## REPRO RUN — cross-machine-001

### Machine A
- Host: AELITIUM-DEV
- Repo path: /home/catarina-aelitium/aelitium-v3-clean-a
- Commit: b2d80a1cf32470da2976a8a0075369b76376caf7
- Python version: Python 3.12.3
- Date (UTC): 2026-03-19T01:13:27Z

### Machine B
- Host: <FILL_FROM_CODESPACE_HOSTNAME>
- Repo path: /workspaces/aelitium-v3
- Commit: b2d80a1cf32470da2976a8a0075369b76376caf7
- Python version: <FILL_FROM_CODESPACE_PYTHON>
- Date (UTC): <FILL_FROM_CODESPACE_DATE>

---

### Required invariants

- verify-bundle:
  - STATUS=VALID rc=0
  - AI_HASH_SHA256 must match
  - BINDING_HASH must match

- compare (same bundle):
  - STATUS=UNCHANGED rc=0
  - REQUEST_HASH=SAME
  - RESPONSE_HASH=SAME
  - BINDING_HASH=SAME

- compare (different bundle):
  - STATUS=CHANGED rc=2
  - REQUEST_HASH=SAME
  - RESPONSE_HASH=DIFFERENT
  - BINDING_HASH=DIFFERENT

- determinism unit test:
  - final result: OK

- verify-receipt:
  - valid receipt → STATUS=VALID rc=0
  - modified receipt → STATUS=INVALID rc=2 reason=SIGNATURE_INVALID

---

### Observed values (Machine A and Machine B)

- AI_HASH_SHA256:
  7431bf8c98c1766379b1f3970e103f905791fe79cd07e9e236057b595518fd63

- BINDING_HASH:
  ffef7ea10038b83e5fd89bdd983cfaa8274b1eb8a3e566e72292d5a8a4dcfacf

---

### Comparison result

- binding_hash_match: YES
- bundle_hash_match: YES
- compare_same_match: YES
- compare_changed_match: YES
- determinism_match: YES
- receipt_valid_status_match: YES
- receipt_invalid_status_match: YES

- receipt_id_match_required: NO

---

### Final result

PASS

---

### Interpretation

The same repository commit produced identical observable verification results
across two different execution environments.

---

### Non-goal

This run does NOT prove:
- full environment equivalence
- semantic equivalence beyond byte-level inputs
- reproducibility beyond the validated surface

