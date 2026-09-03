# Comparing Recorded Responses Across Runs with AELITIUM

When outputs differ across runs, AELITIUM compares selected identity and response
hashes from internally consistent recorded evidence under an explicitly reported
comparison basis.

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

## Historical v0.3.x comparison

**Comparison basis in v0.3.x: `request_hash` v1.** The v0.3.x comparison
does not use `invocation_identity` as its comparison basis. That separate
identity records a broader call surface when present, but it is not necessarily
complete for every provider call.

The v0.3.x status contract remains documented and can be selected explicitly in
v0.4.0 with `--legacy-request-hash-v1`.

## Invocation-first comparison in v0.4.0

**Comparison contract in v0.4.0: `aelitium-compare-v1`.** The default
mode is `INVOCATION_FIRST`.

Both bundles are verified before a basis is selected. A bundle has usable
invocation evidence only when both `invocation_identity_consistency` and
`invocation_binding_consistency` are `VALID`:

- If both bundles have usable evidence, the basis is
  `INVOCATION_IDENTITY_V1`. Different invocation-identity hashes produce
  `NOT_COMPARABLE`; matching hashes allow selected response hashes to be
  compared.
- If one or both valid bundles do not have usable invocation evidence, the
  basis is `REQUEST_HASH_V1_FALLBACK`. This visible fallback also applies to
  asymmetric and legacy-bundle comparisons.
- `--require-invocation-evidence` selects strict mode and disables fallback.
- `--legacy-request-hash-v1` selects the v0.3.x request-hash decisions even
  when validated invocation evidence is present.
- Invalid bundles fail before comparison with basis `NONE`; invalid invocation
  evidence never causes fallback.

```bash
# Bundle from a previous run (e.g. last week)
aelitium compare ./bundle_baseline ./bundle_today
```

### Matching selected identity and response hashes

```
STATUS=UNCHANGED rc=0
COMPARISON_CONTRACT=aelitium-compare-v1
COMPARISON_MODE=INVOCATION_FIRST
COMPARISON_BASIS=INVOCATION_IDENTITY_V1
COMPARISON_REASON=RESPONSE_HASH_SAME
INVOCATION_IDENTITY_HASH=SAME
REQUEST_HASH=SAME
RESPONSE_HASH=SAME
BINDING_HASH=SAME
```

Under the reported comparison basis, the selected comparison identity hashes
and selected `response_hash` values match. This does not establish unchanged
invocation configuration or unchanged model behavior.

### Matching selected identity, different response hash

```
STATUS=CHANGED rc=2
COMPARISON_CONTRACT=aelitium-compare-v1
COMPARISON_MODE=INVOCATION_FIRST
COMPARISON_BASIS=INVOCATION_IDENTITY_V1
COMPARISON_REASON=RESPONSE_HASH_DIFFERENT
INVOCATION_IDENTITY_HASH=SAME
REQUEST_HASH=SAME
RESPONSE_HASH=DIFFERENT
BINDING_HASH=DIFFERENT
```

Under the reported comparison basis, the selected comparison identity hashes
match and selected `response_hash` values differ. This status does not identify
a cause.

### Different selected invocation-identity hashes

```
STATUS=NOT_COMPARABLE rc=1
COMPARISON_BASIS=INVOCATION_IDENTITY_V1
COMPARISON_REASON=INVOCATION_IDENTITY_HASH_DIFFERENT
INVOCATION_IDENTITY_HASH=DIFFERENT
```

No response-change conclusion is made. Under fallback or legacy basis, different
selected v1 request hashes likewise produce `NOT_COMPARABLE`; a missing required
request hash reports reason `REQUEST_HASH_UNAVAILABLE`. An invalid bundle is
reported separately as `INVALID_BUNDLE` with basis `NONE`.

### Strict mode with unavailable evidence

```bash
aelitium compare baseline today --require-invocation-evidence
```

```text
STATUS=NOT_COMPARABLE rc=1
COMPARISON_MODE=STRICT_INVOCATION
COMPARISON_BASIS=NONE
REQUIRED_COMPARISON_BASIS=INVOCATION_IDENTITY_V1
COMPARISON_REASON=INVOCATION_EVIDENCE_UNAVAILABLE
```

---

## Machine-readable output

```bash
aelitium compare ./baseline ./today --json
```

```json
{
  "status": "CHANGED",
  "rc": 2,
  "comparison_contract": "aelitium-compare-v1",
  "comparison_mode": "INVOCATION_FIRST",
  "comparison_basis": "INVOCATION_IDENTITY_V1",
  "required_comparison_basis": null,
  "comparison_reason": "RESPONSE_HASH_DIFFERENT",
  "invocation_identity_hash": "SAME",
  "invocation_identity_consistency_a": "VALID",
  "invocation_binding_consistency_a": "VALID",
  "invocation_identity_consistency_b": "VALID",
  "invocation_binding_consistency_b": "VALID",
  "request_hash": "SAME",
  "response_hash": "DIFFERENT",
  "binding_hash": "DIFFERENT"
}
```

JSON also includes the full, untruncated per-side request, response, and
invocation-identity hashes plus timestamps and a bounded interpretation. Raw
invocation hashes are not emitted after bundle verification failure.

Exit codes: `0` = `UNCHANGED`, `1` = `NOT_COMPARABLE`, and `2` = `CHANGED`
or `INVALID_BUNDLE`.

### Migration from v0.3.x

The numeric exit codes are unchanged, but the v0.4 default can intentionally
change a decision: bundles with matching v1 request hashes and different
validated invocation-identity hashes now report `NOT_COMPARABLE` instead of
reaching response-hash comparison. CI must continue inspecting `STATUS` because
exit code `2` remains shared by `CHANGED` and `INVALID_BUNDLE`.

Text output retains `STATUS` as its first line and retains the request, response,
legacy binding, timestamps, and interpretation diagnostics, with new contract,
mode, basis, reason, invocation-hash, and assurance-state lines. Successful JSON
output retains its existing keys and adds the versioned comparison fields; JSON
consumers should tolerate additive keys and read `comparison_basis` before
interpreting a status.

Use `--legacy-request-hash-v1` during migration when a workflow must reproduce
v0.3.x request-hash decisions. Use `--require-invocation-evidence` when fallback
is unacceptable. The flags are mutually exclusive and using both is an argparse
usage error with exit code `2`, not a comparison result.

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

Store one bundle per recorded comparison case as your selected-hash baseline.
Run `aelitium compare` against it in every CI run.

For valid bundles whose identity hashes match under the reported basis, a
different selected response hash produces `STATUS=CHANGED rc=2` and reports:

- the selected v1 request hash fields
- what was recorded before (previous response hash)
- what is recorded now (new response hash)
- which comparison basis and reason were applied

Equality of validated `aelitium-invocation-v1` hashes describes only fields
selected by that recorded identity format; it does not establish a complete
real-world invocation. Fallback request-hash equality covers selected canonical
model and messages fields, not every invocation parameter, mode, route, client
configuration, or execution context.

AELITIUM establishes internal consistency of recorded evidence on the validated
surface. It does not establish provider execution, causation, full invocation
completeness, model drift, output truth, authorization, or legal compliance.

---

## Related

- [Capture layer](INTEGRATION_CAPTURE.md) — native OpenAI and Anthropic capture plus LiteLLM capture
- [Evidence Bundle Spec](EVIDENCE_BUNDLE_SPEC.md) — bundle format and field definitions
- [Trust boundary](TRUST_BOUNDARY.md) — current assurance scope and limitations
