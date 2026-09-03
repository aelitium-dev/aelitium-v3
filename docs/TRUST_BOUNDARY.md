# AELITIUM — Trust Boundary

## What AELITIUM v1 verification establishes

A `STATUS=VALID` result establishes the internal consistency of the AI evidence
bundle being inspected. Specifically, current v1 verification can establish:

- the payload satisfies `ai_output_v1`
- `ai_canonical.json` uses the governed canonical serialization
- the manifest identifiers and lowercase SHA-256 fields satisfy the v1 contract
- `ai_hash_sha256` matches the independently reconstructed canonical payload
- stored request, response, and binding hash fields are consistent when binding
  evidence is present
- stored versioned invocation identity fields are internally consistent when
  invocation evidence is present
- stored invocation binding fields consistently link the invocation identity hash
  to the stored response hash when invocation binding evidence is present
- bundled Ed25519 verification material is mathematically valid when present

This result does not, by itself, prove that the inspected artifact is historically
unchanged. A fully self-consistent replacement can verify unless the verifier has
an independently trusted external hash, key identity, receipt, or equivalent
anchor.

The assurance dimensions must be interpreted separately:

| Dimension | Reachable states in v0.4.0 | Current v1 interpretation |
|---|---|---|
| `payload_integrity` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Payload/schema/canonical/manifest/hash consistency |
| `binding_field_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Stored v1 request/response/binding field consistency |
| `invocation_identity_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Stored versioned invocation identity consistency; not provider execution |
| `invocation_binding_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Stored invocation-to-response binding consistency; not provider execution or causation |
| `signature_validity` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | Mathematical signature result for bundled material |
| `trusted_signer_identity` | `VALID`, `UNESTABLISHED` | Match against an explicitly supplied external trust store |
| `freshness` | `VALID`, `INVALID`, `UNESTABLISHED`, `NOT_EVALUATED` | Declared-time recency under the explicit policy pair defined below |
| `authorization` | `NOT_EVALUATED` only | No authorization decision is implemented in v0.4.0 |

Unsigned and unbound bundles remain valid by default. `--require-signature` and
`--require-binding` let callers reject absence for their verification context.

---

## `freshness`: declared-time recency

Freshness v1 is a deterministic evaluation of one declared timestamp under
two explicit verifier-supplied policy inputs. Its source is
`ai_canonical.json.ts_utc`. The policy inputs are
`freshness_max_age_seconds` and `freshness_reference_time_utc`, exposed by
the verification CLI as `--freshness-max-age-seconds` and
`--freshness-reference-time-utc`. Both policy inputs must be supplied to
activate evaluation.

**Freshness `VALID` means only:** under the verifier-supplied maximum age
and explicit UTC reference time, the declared canonical
`ai_canonical.json.ts_utc` is a valid strict UTC whole-second timestamp and
lies within the inclusive interval:

```text
[reference_time - maximum_age, reference_time]
```

This is **declared-time recency**. It is not trusted historical time.

The v1 state mapping is:

| Condition | `freshness` state |
|---|---|
| Neither policy input supplied | `NOT_EVALUATED` |
| Selected canonical timestamp is valid and inside the inclusive window | `VALID` |
| Selected canonical timestamp is stale, future, or malformed | `INVALID` |
| Verifier policy is incomplete or invalid | `UNESTABLISHED` |
| Canonical `ts_utc` is missing | Overall reason `CANONICAL_SCHEMA_INVALID`; `freshness = NOT_EVALUATED` |

`authorization = NOT_EVALUATED` in every P1.3 v1 case. Freshness does not
implement or imply authorization policy.

### Time sources outside P1.3 v1

P1.3 v1 uses no implicit system clock or implicit "now". It also does not
use any of the following as its Freshness source or time authority:

- `ai_manifest.json.ts_utc`
- `metadata.captured_at_utc`
- `provider_created_at`
- provider timestamps generally
- receipt timestamps
- EvidenceLog timestamps
- signer timestamp authority
- RFC3161 or another external timestamp authority
- transparency-log time
- certificate or key expiry
- authorization-policy time

Those concepts are not declared invalid generally; they are outside the
P1.3 v1 evaluation. The manifest timestamp continues to have its separate
bundle-contract validation semantics, but it is not the Freshness source.

### Freshness claim boundary

`freshness = VALID` does **not** establish:

- trusted historical time
- historical occurrence
- historical non-modification
- provider receipt
- provider execution
- response causation
- trusted provider identity
- authorization
- legal or regulatory compliance
- semantic truth or correctness

A self-consistent rewrite of the declared canonical timestamp, accompanied
by consistent canonical and manifest hashes, can remain
`freshness = VALID`. This demonstrates the verifier's declared-time
semantics and absence of historical-time authentication; it does not prove
that the rewritten timestamp historically occurred.

Freshness is independent from `signature_validity` and
`trusted_signer_identity`. These states may legitimately coexist:

```text
signature_validity = ABSENT
trusted_signer_identity = UNESTABLISHED
freshness = VALID
```

or:

```text
signature_validity = VALID
trusted_signer_identity = VALID
freshness = INVALID
```

The canonical `ai_canonical.json.ts_utc` does not become a trusted time
authority merely because signer identity is trusted. A valid signature
authenticates the signed bytes under the existing signature semantics; it
does not prove that a timestamp inside those bytes is historically true.

The assurance distinctions remain:

```text
payload integrity != historical non-modification
signature validity alone does not establish signer identity as trusted
invocation consistency != provider execution
invocation binding consistency != response causation
Freshness VALID != trusted historical occurrence
```

Freshness evidence may support a governance or compliance process, but
`freshness = VALID` does not itself establish legal or regulatory
compliance.

---

## `trusted_signer_identity`: explicit external trust store

`trusted_signer_identity` is evaluated only when a caller explicitly supplies
a local trust store for that verification invocation. There is no ambient,
default, or environment-variable trust-store discovery.

**Core property:** given a valid Ed25519 signature over the bundle manifest,
and an explicitly supplied external local trust store, AELITIUM can establish
that the signature corresponds to a public key explicitly trusted by that
verifier invocation.

`trusted_signer_identity = VALID` means the verified signature's public-key
fingerprint is present in the external trust store supplied to this
verification invocation. It does not mean verified human identity, verified
legal identity, verified organizational employment or role, authorization,
freshness, revocation status, provider identity, or model execution proof.

### Bundled key vs. external trust store

A bundled public key in `verification_keys.json` alone can establish
mathematical signature validity. It cannot, by itself, establish trusted
signer identity, and `verification_keys.json` is not a trust anchor.
`trusted_signer_identity` reaches `VALID` only through comparison against a
trust store supplied independently of the inspected bundle.

### Trust-store contract (`aelitium-trust-v1`)

An explicit local JSON path, supplied per invocation. Records contain
`algorithm` (`ed25519`), `public_key_b64` (raw public-key bytes), and an
optional, non-authoritative `label`. The verifier derives the fingerprint
from the raw public-key bytes — `ed25519:sha256:<64 lowercase hex>` — never
from a stored fingerprint field, since none exists in this format. The
current contract does not include a signer_id, revocation, expiry,
delegation, remote distribution, or ambient/default discovery.

### Optional vs. required evaluation

Supplying a trust store alone performs evaluation without requiring
membership: a validly signed bundle whose key is absent from the supplied
trust store remains `STATUS=VALID` with
`trusted_signer_identity=UNESTABLISHED`. A bundle is not made invalid merely
because the caller did not additionally require this dimension.

A bundle cannot report `trusted_signer_identity=VALID` under
`--require-trusted-signer` without an exact fingerprint match, and cannot
pass verification under that flag at all without a trust store being
supplied:

| Failure reason | Meaning |
|---|---|
| `TRUST_INPUT_NOT_PROVIDED` | `--require-trusted-signer` was requested but no trust store was supplied |
| `TRUST_STORE_INVALID` | the explicitly supplied trust store could not be read, parsed, or validated |
| `TRUSTED_SIGNER_NOT_FOUND` | a valid trust store and a valid signature exist, but the verified key is not in it |
| `SIGNATURE_REQUIRED` | `trusted_signer_identity` enforcement was required but the bundle is unsigned |
| `SIGNATURE_INVALID` | signature material exists but cryptographic verification failed |

These are distinct failure reasons and are never collapsed into one generic
trust failure.

### Self-consistent rewrite: a boundary this mechanism does not cross

`payload_integrity=VALID` means the stored canonical payload is consistent
with the manifest/hash contract currently being verified. It does not
establish that the artifact is historically unchanged from an earlier
external state, that a specific provider produced the payload, that the
payload is truthful, or that an attacker could not construct a new
internally-consistent artifact and sign it with a key of their own choosing.
Requiring an exact fingerprint match, as described above, can reject such a
self-consistent rewrite when it is signed by a key absent from the supplied
trust store, but this still does not create an independent historical
timestamp or anchor — see "Levels of provenance" below for what would.

---

## What AELITIUM does not prove

### The model actually produced the output

The core pack/verifier accepts the valid `ai_output_v1` object it is given. Native
OpenAI and Anthropic adapters and a LiteLLM adapter can reduce the manual handoff,
but they do not authenticate model execution. If the capture or packing process is
compromised, a bundle can faithfully record compromised input.

**Mitigation:** pack immediately after generation, in the same trust boundary as the model call. See [INTEGRATION_PYTHON.md](INTEGRATION_PYTHON.md) for fail-closed pipeline patterns.

### The output is correct or safe

AELITIUM evaluates evidence consistency, not quality. A consistently represented
record of a hallucination is still a hallucination.

**Mitigation:** combine AELITIUM with model evaluation and guardrails. These are orthogonal concerns.

### The stored hash hasn't been substituted

If an attacker controls both the evidence bundle and the location where `ai_hash_sha256` is stored, they can substitute a different valid bundle and hash consistently.

**Mitigation:** store hashes in a system the attacker cannot modify — a separate append-only database, an immutable log, or a signed receipt from a P3 authority (see below).

---

## Levels of provenance

| Level | What it provides | How |
|-------|-----------------|-----|
| **Hash only** (P2) | Internal consistency; historical tamper-evidence given a trusted stored hash | `aelitium pack` + store hash in separate DB |
| **Authority receipt** (P3) | Tamper-evidence + timestamp attestation by a signing authority | `POST /v1/sign` → `receipt_v1` with Ed25519 signature |
| **Hardware attestation** (future) | Binding to a specific execution environment | TEE / HSM / remote attestation |

Each level answers a stronger question:

- **P2**: *"Is this payload consistent with the independently trusted hash?"*
- **P3**: *"Did a trusted authority see this hash at this time?"*
- **Hardware**: *"Was this output produced in this specific environment?"*

---

## Integrity vs completeness

These are different properties:

- **Integrity**: the inspected payload, contract, and recorded hashes are internally consistent. Historical non-modification additionally requires a trusted anchor.
- **Completeness**: all events that should have been captured were captured. AELITIUM does not provide this.

If a logging agent selectively omits events before they reach the capture layer, no cryptographic mechanism can detect the omission — there is nothing to hash. This is a well-known property of tamper-evident logs in distributed systems: proving nothing was omitted is harder than proving nothing was altered.

**Implication for agent systems:** if the agent controls its own logging, it can omit entries without detection. An observer-based capture pattern — where an independent process intercepts LLM calls, rather than the agent calling the capture function — provides stronger completeness guarantees. This is the architectural direction for `aelitium.capture` in multi-agent deployments.

---

## Canonical threat model

| Threat | P2 with independently trusted hash | P3 (signed receipt) |
|--------|-----------|---------------------|
| Output tampered in storage | ✅ detected | ✅ detected |
| Manifest hash field altered | ✅ detected | ✅ detected |
| Both bundle and stored hash replaced consistently | ❌ not detected | ✅ detected (signature covers hash) |
| Bundle packed before/after the real generation | ❌ not detected | ✅ timestamp in receipt |
| Manually crafted bundle with valid hashes | ❌ not detected | ✅ requires authority to have seen hash at packing time |
| Packing process compromised | ❌ not detected | ❌ not detected |
| Agent omits events before capture | ❌ not detected | ❌ not detected |
| Model or prompt compromised before generation | ❌ out of scope | ❌ out of scope |

---

## Artifact forgery

Any party able to construct a complete valid `ai_output_v1` object can produce a
self-consistent bundle. Selected request and response material is sufficient to
reproduce the v1 binding fields, while timestamps and metadata also contribute to
the complete canonical payload hash. This is a known property of hash-based
consistency systems, not a bug.

**Why this is expected behavior:**

An evidence bundle establishes that its current payload and recorded evidence are
internally consistent. It does not prove that packing happened during the original
model call, that the artifact was never replaced, or that no other party could
have produced a self-consistent bundle. Deterministic hashing is a design goal,
not a producer-authentication mechanism.

**Consequence:** a bundle alone cannot prove that the person who packed it is the
same person who made the API call. A party that knows the selected request and
response material can produce self-consistent v1 hashes and evidence; timestamps
or other metadata may still make the complete bundle bytes differ.

**Mitigations, in increasing strength:**

| Mitigation | What it adds |
|-----------|-------------|
| Capture adapter (P2) | Records selected v1 request and response fields in the adapter-controlled call path; verification checks their stored hash consistency |
| Operator signing (P2+) | Ed25519 material in `verification_keys.json` can establish mathematical signature validity; bundled key material alone does not establish trusted signer identity |
| Operator signing + external trust store | An explicitly supplied local trust store lets a matching verified key reach `trusted_signer_identity=VALID`; a bundle cannot reach that state under stricter enforcement without a match against it |
| Authority receipt (P3) | External timestamp and signature prove the authority saw this hash at a specific time — forgery would require the authority's private key |
| Observer-based capture | Independent process intercepts the API call; the agent cannot forge what it did not control |

**Practical implication:** P2 hash-only bundles can support internal comparison and
audit workflows when the expected hash is independently protected. Bundle-only
verification, including declared-time Freshness evaluation, does not establish
origin, authorization, trusted historical time, or historical non-modification.

---

## Practical guidance

### When P2 (hash only) is sufficient

- Internal audit trails where the hash DB is access-controlled separately from the evidence storage
- Pipelines where tamper-detection is needed but non-repudiation is not
- Debugging and reproducibility verification

### When P3 (signed receipt) adds value

- Third-party audits where the auditor needs independent attestation
- Regulatory contexts requiring a trusted timestamp from a named authority
- Dispute resolution where the chain of custody must be externally verifiable

### When neither is sufficient

- Proving that a model with specific parameters generated the output (requires model-level attestation)
- Proving the output is factually correct (requires evaluation, not integrity)
- Preventing adversarial prompt injection before generation

---

## Summary

AELITIUM is best understood as an **evidence-consistency layer**, not a trust oracle.

It answers: *"Are the inspected bundle fields internally consistent under the
documented contract and explicitly supplied policies?"*

It does not answer: *"Should you trust what was recorded?"*

For the latter, you need provenance — which is the direction of P3 and beyond.
