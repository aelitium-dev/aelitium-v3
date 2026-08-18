# Invocation Assurance

## Scope

This document describes the P1.2 invocation-assurance model:

- invocation identity (`metadata.invocation_identity`)
- invocation binding (`metadata.invocation_binding`)
- their verifier assurance dimensions (`invocation_identity_consistency`,
  `invocation_binding_consistency`)
- the explicit claim boundaries of each

It does not describe the base v1 evidence bundle contract, signing, or trust
store evaluation in detail — see [Trust boundary](TRUST_BOUNDARY.md) and
[Evidence Bundle Spec](EVIDENCE_BUNDLE_SPEC.md) for those.

## Two Different Binding Families

AELITIUM stores two distinct, independently versioned binding relationships
in the same bundle. Neither supersedes the other, and they are never
conflated.

**Existing v1 binding** (unchanged by P1.2):

```text
binding_hash =
  SHA256(canonical_json({
    "request_hash": request_hash,
    "response_hash": response_hash
  }))
```

This is the original commitment linking the recorded request to the
recorded response. It is not called "v2" and P1.2 does not touch its
formula, storage location, or semantics.

**Invocation binding** (P1.2d):

```text
invocation_binding =
  versioned binding of:
    invocation_identity.hash_sha256
    response_hash
```

This links the richer, versioned invocation-identity object (below) to the
same stored `response_hash` — a different relationship than the v1 binding,
expressed with its own format and its own stored object.

## Invocation Identity

Stored at:

```text
metadata.invocation_identity
```

Format:

```text
aelitium-invocation-v1
```

An invocation identity records the semantic invocation at the adapter's
provider/SDK call boundary — i.e. what was actually passed into the
provider SDK call, not a reconstruction of caller intent. Specifics:

- **Absent is not the same as explicit null.** A parameter the caller never
  supplied is omitted from the stored object; a parameter explicitly passed
  as `null`/`None` is stored as `null`.
- **Adapter-injected defaults that are emitted to the SDK call count.** For
  example, the Anthropic adapter's own default `max_tokens=1024` is part of
  what was actually sent, so it is recorded even when the caller never
  specified it.
- **Provider/SDK-side defaults applied after the call boundary do not
  count.** Only what the adapter itself emits into the call is in scope —
  nothing the provider does after receiving it.
- **No cross-provider parameter renaming.** Each parameter name is exactly
  the adapter-emitted field name for that surface; there is no normalized,
  provider-neutral parameter vocabulary.
- **LiteLLM omits the identity conservatively.** If a LiteLLM call includes
  any provider kwarg that the `aelitium-invocation-v1` grammar cannot fully
  represent (an unsupported kwarg, an unrepresentable value, or
  `stream=True`), no invocation identity is recorded at all, rather than a
  partial or misleading one. See "LiteLLM Conservative Absence" below.

This document does not expand the grammar beyond what is actually
implemented in `engine/invocation.py`.

## Invocation Identity Consistency

The verifier reports `invocation_identity_consistency` using the existing
`AssuranceState` vocabulary:

| State | Meaning |
| --- | --- |
| `ABSENT` | `metadata.invocation_identity` is not present in the bundle. |
| `VALID` | The stored object is structurally valid under `aelitium-invocation-v1` and its `hash_sha256` matches recomputation from its stored semantic fields. |
| `INVALID` | The stored object is present but fails structural validation or its stored hash does not match recomputation. |
| `NOT_EVALUATED` | Evaluation was never reached because payload integrity itself failed first. |

`VALID` means **only**: the stored invocation-identity object is internally
consistent with its own declared format and hash. It does **not** mean:

- the provider received the request
- the provider executed the request
- provider identity
- response causation
- historical occurrence
- authorization
- freshness
- semantic truth or correctness of the recorded fields

## Invocation Binding

Stored at:

```text
metadata.invocation_binding
```

Format:

```text
aelitium-invocation-binding-v1
```

It binds two stored hash values:

```text
invocation_identity.hash_sha256
response_hash
```

It does **not** bind provider execution, and it does not reconstruct or
re-derive either value from raw content — it only records that these two
specific stored hash strings were bound together under a declared format.

## Invocation Binding Consistency

The verifier reports `invocation_binding_consistency` using the same
`AssuranceState` vocabulary:

| State | Meaning |
| --- | --- |
| `ABSENT` | `metadata.invocation_binding` is not present in the bundle. |
| `VALID` | The stored binding object is internally valid AND its `invocation_hash`/`response_hash` fields match this same bundle's stored, already-`VALID` invocation identity and stored `response_hash`. |
| `INVALID` | The object is malformed, its own hash does not recompute, or it is internally valid but fails one of the bundle-local cross-field checks below. |
| `NOT_EVALUATED` | Evaluation was never reached because payload integrity itself failed first. |

A binding can never be `VALID` unless the invocation identity it references
is itself `VALID` — there is no such thing as a binding more trustworthy
than what it binds.

### Cross-field diagnostic vocabulary

Beyond the primitive's own structural reasons
(`INVOCATION_BINDING_BAD_FORMAT`, `INVOCATION_BINDING_BAD_STRUCTURE`,
`INVOCATION_BINDING_BAD_INVOCATION_HASH`,
`INVOCATION_BINDING_BAD_RESPONSE_HASH`, `INVOCATION_BINDING_BAD_HASH`,
`INVOCATION_BINDING_HASH_MISMATCH`), the verifier's bundle-local cross-field
check can report:

- `INVOCATION_BINDING_INPUT_MISSING` — the binding is present but
  `metadata.invocation_identity` is absent, or `metadata.response_hash` is
  absent/malformed.
- `INVOCATION_BINDING_INPUT_INVALID` — the binding is present and the
  identity is present, but the identity itself is `INVALID`.
- `INVOCATION_BINDING_INPUT_MISMATCH` — the binding object is internally
  valid on its own, but its `invocation_hash` does not match this bundle's
  `invocation_identity.hash_sha256`, or its `response_hash` does not match
  this bundle's stored `response_hash`.

### Root-cause precedence

When the invocation identity itself is invalid, the overall verification
failure reason is the identity's own reason (e.g. `INVOCATION_HASH_MISMATCH`,
`INVOCATION_BAD_HASH`, `INVOCATION_BAD_FORMAT`) — never
`INVOCATION_BINDING_INPUT_INVALID`. A dependent binding may simultaneously
report `invocation_binding_consistency = INVALID` in the same result, but the
overall reason always points at the root cause, not the derived diagnostic.

## Assurance Matrix

| Scenario | `invocation_identity_consistency` | `invocation_binding_consistency` |
| --- | --- | --- |
| Legacy bundle (no P1.2 fields) | `ABSENT` | `ABSENT` |
| P1.2 identity only | `VALID` | `ABSENT` |
| P1.2 full (identity + binding) | `VALID` | `VALID` |
| Invalid identity + dependent binding present | `INVALID` | `INVALID` |
| Valid identity + cross-field-mismatched binding | `VALID` | `INVALID` |
| Early payload failure | `NOT_EVALUATED` | `NOT_EVALUATED` |

`freshness` is always `NOT_EVALUATED` in the current system.
`authorization` is always `NOT_EVALUATED` in the current system.

## Consistency Is Not Historical Occurrence

This section is normative.

An unsigned bundle can be rewritten by anyone with write access to it. If an
attacker rewrites:

- the semantic invocation fields (e.g. `model`, `messages`)
- the invocation identity's own `hash_sha256`, recomputed with the same
  authoritative primitive a legitimate adapter uses
- the invocation binding, recomputed against the rewritten identity hash
- the outer canonical hash
- the manifest's `ai_hash_sha256`

the result is a new bundle that is internally self-consistent and will
verify `valid=True` with `invocation_identity_consistency=VALID` and
`invocation_binding_consistency=VALID`. This is demonstrated explicitly by
`TestAIInvocationAssuranceAdversarial.test_full_self_consistent_rewrite_remains_internally_valid`
in `tests/test_ai_verification.py`.

Therefore:

```text
consistency != historical occurrence
invocation binding consistency != response causation
```

`invocation_identity_consistency=VALID` and
`invocation_binding_consistency=VALID` **MUST NOT** be interpreted as proof
of provider receipt, provider execution, response causation, authorization,
freshness, or historical occurrence — for either a signed or unsigned
bundle. What detecting *this specific class of rewrite* requires is a
signature over the manifest (see below); even then, a signature proves the
manifest was signed by a given key, not that the underlying invocation was
historically executed by any provider.

## Signatures and Trust

Consistency dimensions, signature validity, and trusted signer identity are
kept strictly separate and are never conflated:

- `payload_integrity`, `invocation_identity_consistency`, and
  `invocation_binding_consistency` are deterministic, stored-field
  consistency checks. They do not depend on any signature.
- `signature_validity=VALID` proves only that the manifest bytes verify
  under the Ed25519 public key bundled in `verification_keys.json`. It does
  not by itself establish who controls that key.
- `trusted_signer_identity=VALID` additionally requires an explicit,
  externally supplied trust store whose fingerprint matches the verified
  signing key. It is never inferred from the bundle alone.

For an **unsigned** bundle, a fully self-consistent rewrite (see above) can
remain internally `VALID` across every deterministic consistency dimension.

For a **signed** bundle, rewriting canonical or manifest material without
producing a new, valid signature over the resulting bytes causes signature
verification to fail (`signature_validity=INVALID`, overall
`reason=SIGNATURE_INVALID`).

Even when `signature_validity=VALID` and `trusted_signer_identity=VALID`,
neither one automatically proves provider identity, provider execution,
response causation, authorization, or freshness.

## LiteLLM Conservative Absence

If a LiteLLM call receives any provider-call kwarg that
`aelitium-invocation-v1` cannot fully represent:

- provider call behavior is unchanged — the underlying `litellm.completion()`
  call still receives every kwarg exactly as passed
- existing v1 evidence capture (request/response/binding hashes) still
  proceeds normally
- `invocation_identity` is omitted from the bundle entirely
- `invocation_binding` is therefore also omitted (absence of identity always
  implies absence of binding — a partial or best-effort binding is never
  recorded)

The verifier cannot determine, and does not attempt to report, *why* a given
bundle lacks an invocation identity or binding — only that it does. Absence
is reported as `ABSENT`, nothing more specific.

## Current Non-Claims

At minimum, the following are explicitly **not** established by any
combination of the assurance dimensions described in this document:

- provider receipt
- provider execution
- provider identity
- response causation
- historical occurrence
- freshness
- authorization
- semantic truth or correctness
