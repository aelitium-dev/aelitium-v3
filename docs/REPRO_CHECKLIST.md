# REPRO CHECKLIST — AELITIUM

Scope: cross-machine reproducibility checks for the currently validated surface.

Rule: only observable checks are included. No broader reproducibility claim is made.

---

## Preconditions

- Same repository commit on both machines
- Commands run from repo root
- python3 available
- Same bundles and fixtures used

---

## Check 1 — Repository parity

### Command
pwd
git rev-parse HEAD
python3 --version

### PASS
- commit hash identical

### Non-goal
- does not prove identical environments

---

## Check 2 — Deterministic binding-hash

### Command
python3 -m unittest tests.test_capture_litellm.TestCaptureLiteLLM.test_binding_hash_deterministic -v

### PASS
- exits 0
- output contains "OK"

### Non-goal
- does not expose hash values

---

## Check 3 — verify-bundle (offline)

### Command
python3 -m engine.ai_cli verify-bundle examples/drift_demo/bundle_a

### PASS
- STATUS=VALID rc=0
- AI_HASH_SHA256 identical across machines
- BINDING_HASH identical across machines

### Non-goal
- does not prove generation time

---

## Check 4 — compare (unchanged)

### Command
python3 -m engine.ai_cli compare examples/drift_demo/bundle_a examples/drift_demo/bundle_a

### PASS
- STATUS=UNCHANGED rc=0
- REQUEST_HASH=SAME
- RESPONSE_HASH=SAME

---

## Check 5 — compare (changed)

### Command
python3 -m engine.ai_cli compare examples/drift_demo/bundle_a examples/drift_demo/bundle_b || true

### PASS
- STATUS=CHANGED rc=2
- REQUEST_HASH=SAME
- RESPONSE_HASH=DIFFERENT

---

## Check 6 — verify-receipt (valid)

### Command
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

### PASS
- STATUS=VALID rc=0

### Non-goal
- RECEIPT_ID does not need to match

---

## Check 7 — verify-receipt (invalid)

### Command
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

### PASS
- STATUS=INVALID rc=2
- reason=SIGNATURE_INVALID

---

## Final result

PASS only if all checks pass and required values match.

FAIL if any check diverges.

---

## Global non-goals

- no claim of full environment equivalence
- no claim of identical timing
- no claim beyond validated surface
