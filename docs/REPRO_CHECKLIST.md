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

### PASS
- STATUS=VALID rc=0

### Non-goal
- RECEIPT_ID does not need to match

---

## Check 7 — verify-receipt (invalid)

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
