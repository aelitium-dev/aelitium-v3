# Comparing Recorded Responses Across Runs with AELITIUM

When outputs differ across runs, AELITIUM compares selected v1 request and response
hashes from internally consistent recorded evidence.

---

## The problem

AI providers update models continuously. These updates are often silent — the model endpoint
(`gpt-4o`, `claude-3-5-sonnet`) stays the same, but behavior changes.

If your system sends the same request today and gets a different answer than last week:

- Is it your code?
- Is it your prompt?
- Is it the model?

Without cryptographic evidence, this question is hard to evaluate reliably. With AELITIUM, you can at least verify whether the recorded request and response artifacts differ.

---

## How it works

The capture adapter records three v1 hashes in its controlled call path:

| Hash | What it covers |
|------|---------------|
| `request_hash` | SHA256 of the recorded request payload (model + messages) |
| `response_hash` | SHA256 of the recorded response artifact |
| `binding_hash` | SHA256 commitment over the stored request/response hash pair |

These are written to the evidence bundle and checked for stored-field consistency.
A fully self-consistent replacement can still verify without an independently
trusted external anchor.

---

## Detecting a change

```bash
# Bundle from a previous run (e.g. last week)
aelitium compare ./bundle_baseline ./bundle_today
```

### Same selected request and response hashes

```
STATUS=UNCHANGED rc=0
REQUEST_HASH=SAME
RESPONSE_HASH=SAME
BINDING_HASH=SAME
INTERPRETATION=Same request_hash and response_hash observed
```

The selected v1 request and response hashes are unchanged. Other unbound invocation
parameters or metadata may still differ.

### Same selected request hash, different response hash

```
STATUS=CHANGED rc=2
REQUEST_HASH=SAME
RESPONSE_HASH=DIFFERENT
BINDING_HASH=DIFFERENT
INTERPRETATION=Same request_hash with different response_hash observed
```

The compared bundles have the same `request_hash` and different `response_hash` values.
This shows a changed recorded response for the same hashed request. It does not attribute the cause.

### Different selected request hashes

```
STATUS=NOT_COMPARABLE rc=1
REQUEST_HASH=DIFFERENT
INTERPRETATION=Requests differ — bundles are not comparable
```

The selected v1 request identities differ, so comparison reports
`NOT_COMPARABLE`. This does not establish full invocation equivalence or
inequality.

---

## Machine-readable output

```bash
aelitium compare ./baseline ./today --json
```

```json
{
  "status": "CHANGED",
  "rc": 2,
  "request_hash": "SAME",
  "response_hash": "DIFFERENT",
  "binding_hash": "DIFFERENT",
  "interpretation": "Same request_hash with different response_hash observed"
}
```

Exit codes: `0` = unchanged, `1` = not comparable, `2` = changed or invalid.

---

## Use in CI/CD

```yaml
- name: Capture AI inference
  run: python3 infer.py --out ./evidence_today

- name: Compare against baseline
  run: |
    aelitium compare ./evidence_baseline ./evidence_today
    if [ $? -eq 2 ]; then
      echo "Recorded response changed for the same request hash — review before merge"
      exit 1
    fi
```

---

## Baseline management

Store one bundle per request type as your behavioral baseline.
Run `aelitium compare` against it in every CI run.

If the recorded response hash changes, the pipeline fails with
`STATUS=CHANGED rc=2` and reports:

- the selected v1 request hash fields
- what was recorded before (previous response hash)
- what is recorded now (new response hash)
- whether the selected v1 request identity changed

This is offline comparison of recorded evidence, not provider attribution.

---

## Related

- [Capture layer](INTEGRATION_CAPTURE.md) — native OpenAI and Anthropic capture plus LiteLLM capture
- [Evidence Bundle Spec](EVIDENCE_BUNDLE_SPEC.md) — bundle format and field definitions
- [Trust boundary](TRUST_BOUNDARY.md) — current assurance scope and limitations
