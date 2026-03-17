# Detecting AI Model Behavior Change with AELITIUM

When an AI provider silently updates a model, your outputs can change without any change to your code.
AELITIUM makes this detectable and provable.

---

## The problem

AI providers update models continuously. These updates are often silent — the model endpoint
(`gpt-4o`, `claude-3-5-sonnet`) stays the same, but behavior changes.

If your system sends the same request today and gets a different answer than last week:

- Is it your code?
- Is it your prompt?
- Is it the model?

Without cryptographic evidence, this question is unanswerable. With AELITIUM, it is not.

---

## How it works

The capture adapter records three hashes at call time:

| Hash | What it covers |
|------|---------------|
| `request_hash` | SHA256 of the exact request sent (model + messages) |
| `response_hash` | SHA256 of the exact response received |
| `binding_hash` | SHA256 linking request↔response as a single event |

These are written to the evidence bundle and cannot be altered without breaking verification.

---

## Detecting a change

```bash
# Bundle from a previous run (e.g. last week)
aelitium compare ./bundle_baseline ./bundle_today
```

### Same request, same response

```
STATUS=UNCHANGED rc=0
REQUEST_HASH=SAME
RESPONSE_HASH=SAME
BINDING_HASH=SAME
INTERPRETATION=Same request produced the same response
```

Nothing changed.

### Same request, different response

```
STATUS=CHANGED rc=2
REQUEST_HASH=SAME
RESPONSE_HASH=DIFFERENT
BINDING_HASH=DIFFERENT
INTERPRETATION=Same request produced a different response
```

The request did not change. The response did.
**The change came from the model, not your code.**

### Different requests

```
STATUS=NOT_COMPARABLE rc=1
REQUEST_HASH=DIFFERENT
INTERPRETATION=Requests differ — bundles are not comparable
```

The requests differ — comparison is not meaningful.

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
  "interpretation": "Same request produced a different response"
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
      echo "Model behavior changed — review before merge"
      exit 1
    fi
```

---

## Baseline management

Store one bundle per request type as your behavioral baseline.
Run `aelitium compare` against it in every CI run.

If the model changes, the pipeline fails with `STATUS=CHANGED rc=2` and you have cryptographic proof:

- what was asked (exact request)
- what response content was recorded before (previous response hash)
- what response content is recorded now (new response hash)
- that the request itself did not change

This is AI provider accountability: verifiable, offline, no third-party trust required.

---

## Related

- [Capture layer](INTEGRATION_CAPTURE.md) — how to capture bundles from OpenAI and Anthropic
- [Evidence Bundle Spec](EVIDENCE_BUNDLE_SPEC.md) — bundle format and field definitions
- [Trust boundary](TRUST_BOUNDARY.md) — what AELITIUM proves and what it does not
