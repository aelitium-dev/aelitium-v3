# Comparing Recorded Responses Across Runs with AELITIUM

When outputs differ across runs, AELITIUM compares selected v1 request and response
hashes from internally consistent recorded evidence.

---

## The problem

Recorded outputs can differ across repeated calls even when the selected model
identifier (`gpt-4o`, `claude-3-5-sonnet`) remains the same. Provider changes,
invocation parameters, routing, client configuration, execution context, and
other factors can all be relevant.

If your system records the same selected v1 request fields today and different
selected response fields than last week:

- Is it your code?
- Is it your prompt?
- Is it the model?

Without cryptographic evidence, this question is hard to evaluate reliably. With AELITIUM, you can at least verify whether the recorded request and response artifacts differ.

---

## How it works

The capture adapter records three v1 hashes in its controlled call path:

| Hash | What it covers |
|------|---------------|
| `request_hash` | SHA256 of the selected v1 request fields (model + messages) |
| `response_hash` | SHA256 of the selected recorded response fields |
| `binding_hash` | SHA256 commitment over the stored request/response hash pair |

These are written to the evidence bundle and checked for stored-field consistency.
A fully self-consistent replacement can still verify without an independently
trusted external anchor.

---

## Detecting a change

**Comparison basis in v0.3.x: `request_hash` v1.** Current 0.3.x comparison
does not use `invocation_identity` as its comparison basis. That separate
identity records a broader call surface when present, but it is not necessarily
complete for every provider call.

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

The bundles have the same selected v1 `request_hash` and the same
`response_hash` over selected recorded response fields. This does not establish
that every invocation parameter, mode, provider route, client configuration, or
execution context was unchanged.

### Same selected request hash, different response hash

```
STATUS=CHANGED rc=2
REQUEST_HASH=SAME
RESPONSE_HASH=DIFFERENT
BINDING_HASH=DIFFERENT
INTERPRETATION=Same request_hash with different response_hash observed
```

The bundles have the same selected v1 `request_hash` and different selected
`response_hash` values. This status does not by itself establish model drift or
explain causation.

### Different selected request hashes

```
STATUS=NOT_COMPARABLE rc=1
REQUEST_HASH=DIFFERENT
INTERPRETATION=Requests differ — bundles are not comparable
```

The selected v1 request identities differ, so comparison reports
`NOT_COMPARABLE`. Missing required `request_hash` capture metadata also
produces this status. An invalid bundle is reported separately as
`INVALID_BUNDLE`. Comparison does not establish full invocation equivalence or
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

Exit codes: `0` = `UNCHANGED`, `1` = `NOT_COMPARABLE`, and `2` = `CHANGED`
or `INVALID_BUNDLE`.

---

## Use in CI/CD

```yaml
- name: Capture AI inference
  run: python3 infer.py --out ./evidence_today

- name: Compare against baseline
  run: |
    aelitium compare ./evidence_baseline ./evidence_today
    if [ $? -eq 2 ]; then
      echo "Compare returned CHANGED or INVALID_BUNDLE — inspect STATUS before drawing a conclusion"
      exit 1
    fi
```

---

## Baseline management

Store one bundle per request type as your selected-hash baseline.
Run `aelitium compare` against it in every CI run.

For valid bundles with the same selected v1 request hash, a different selected
response hash produces `STATUS=CHANGED rc=2` and reports:

- the selected v1 request hash fields
- what was recorded before (previous response hash)
- what is recorded now (new response hash)
- whether the selected v1 request identity changed

This is offline comparison of selected hashes in recorded evidence, not full
invocation comparison, provider attribution, or a causal explanation.

---

## Related

- [Capture layer](INTEGRATION_CAPTURE.md) — native OpenAI and Anthropic capture plus LiteLLM capture
- [Evidence Bundle Spec](EVIDENCE_BUNDLE_SPEC.md) — bundle format and field definitions
- [Trust boundary](TRUST_BOUNDARY.md) — current assurance scope and limitations
