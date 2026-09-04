# Independent Verifier Requirements

**Status:** RESEARCH
**Target:** a future clean-room implementation of the released v1 and
unreleased portable-v2 AELITIUM bundle verification and comparison contracts

No second verifier is implemented on this branch. The existing Python
standalone wrapper imports the same Python verification kernel and therefore is
not an independent implementation.

This document defines the later acceptance gate. A candidate verifier must be
implementable from published schemas, contract documents, and frozen vectors;
it must not import AELITIUM Python modules, invoke the Python CLI as its decision
engine, translate Python objects at runtime, or copy private implementation
state.

## Required scope

A clean-room candidate must reproduce:

1. default and option-selected verification of an AI evidence bundle;
2. all eight assurance dimensions with their exact reachable states;
3. `aelitium-verification-result-v1` and embedded
   `aelitium-assurance-result-v1` structure;
4. the `aelitium-claim-boundary-v1` code profiles;
5. verification-before-comparison behavior;
6. all `aelitium-compare-v1` modes, bases, reasons, outcomes, and exit-code
   equivalents; and
7. deterministic refusal for malformed, unverifiable, or non-comparable input.

It must not add an authorization decision, trust score, external policy engine,
runtime capture service, provider call, network lookup, or external-receipt
mapping.

## Authoritative public inputs

The candidate must be written against these repository artifacts:

- [`engine/schemas/ai_output_v1.json`](../engine/schemas/ai_output_v1.json)
- [`engine/schemas/verification_result_v1.json`](../engine/schemas/verification_result_v1.json)
- [`engine/schemas/assurance_result_v1.json`](../engine/schemas/assurance_result_v1.json)
- [`engine/schemas/compare_result_v1.json`](../engine/schemas/compare_result_v1.json)
- [`CANONICALIZATION_SPEC.md`](CANONICALIZATION_SPEC.md)
- [`CANONICAL_REQUEST.md`](CANONICAL_REQUEST.md)
- [`INVOCATION_ASSURANCE.md`](INVOCATION_ASSURANCE.md)
- [`TRUST_BOUNDARY.md`](TRUST_BOUNDARY.md)
- [`VERIFICATION_RESULT_V1.md`](VERIFICATION_RESULT_V1.md)
- [`ASSURANCE_RESULT_V1.md`](ASSURANCE_RESULT_V1.md)
- [`CLAIM_BOUNDARIES_V1.md`](CLAIM_BOUNDARIES_V1.md)
- [`COMPARE_RESULT_V1.md`](COMPARE_RESULT_V1.md)
- [`conformance/manifest.json`](../conformance/manifest.json) and every frozen
  artifact it references

Python source remains useful for auditing this requirements document while the
contract is being stabilized, but it cannot be a runtime dependency or the only
definition available to the candidate implementer.

## Bundle inputs

The verification input is a local directory. The current artifact names are:

| File | Presence | Role |
|---|---|---|
| `ai_canonical.json` | required | Governed `ai_output_v1` canonical payload |
| `ai_manifest.json` | required | Manifest identifiers, payload digest, timestamp spelling, and optional original binding hash |
| `verification_keys.json` | optional | One Ed25519 public key and one signature over the raw manifest bytes |

Explicit verifier inputs are:

- `validate_manifest_timestamp`, default true;
- `require_signature`, default false;
- `require_binding`, default false;
- optional local `aelitium-trust-v1` JSON;
- `require_trusted_signer`, default false;
- optional `freshness_max_age_seconds`; and
- optional `freshness_reference_time_utc`.

There is no ambient trust input, current clock, environment-derived time,
network access, provider lookup, or default policy.

## Required verification order and reason precedence

Order is observable because it selects the top-level `reason` and determines
which dimensions have been evaluated.

### 1. Validate explicit inputs

1. If external signing-key membership is required but no trust store was
   supplied, return `TRUST_INPUT_NOT_PROVIDED`.
2. If a supplied trust store cannot be read or strictly parsed, return
   `TRUST_STORE_INVALID`; its lower-level trust-store reason may appear only in
   non-normative detail.
3. With neither Freshness value, leave `freshness=NOT_EVALUATED`.
4. With only one value, a negative/non-integer maximum age, or a malformed
   reference time, return `FRESHNESS_POLICY_INVALID` with
   `freshness=UNESTABLISHED`.

### 2. Establish payload integrity

Apply checks in this order and stop at the first failure:

1. required file presence: `MISSING_CANONICAL`, then `MISSING_MANIFEST`;
2. canonical UTF-8/JSON parsing: `CANONICAL_NOT_JSON`;
3. manifest UTF-8/JSON parsing and object type: `MANIFEST_NOT_JSON`, then
   `MANIFEST_NOT_OBJECT`;
4. manifest required fields in this order: `schema`, `ts_utc`, `input_schema`,
   `canonicalization`, `ai_hash_sha256`; absence returns
   `MANIFEST_MISSING_FIELD`;
5. exact identifiers: `MANIFEST_BAD_SCHEMA`, `MANIFEST_BAD_INPUT_SCHEMA`, then
   `MANIFEST_BAD_CANONICALIZATION`;
6. when selected, manifest timestamp spelling against
   `YYYY-MM-DDTHH:MM:SSZ`: `MANIFEST_BAD_TS_UTC`; this check is syntactic, not a
   calendar or time-authority check;
7. manifest digest shape, exactly 64 lowercase hexadecimal characters:
   `MANIFEST_BAD_AI_HASH_SHA256`;
8. canonical payload validation against `ai_output_v1`:
   `CANONICAL_SCHEMA_INVALID`;
9. Unicode scalar validation for canonical serialization: an unpaired
   surrogate in an otherwise processable canonical payload returns
   `CANONICAL_NOT_JSON` rather than raising an encoding exception;
10. exact stored canonical bytes: the canonical byte string with either no
   suffix or exactly one terminal LF; any other spelling returns
   `CANONICAL_BYTES_MISMATCH`; and
11. SHA-256 of the canonical bytes without that optional LF against the
    manifest value: `HASH_MISMATCH`.

After step 11 succeeds, `payload_integrity=VALID` and the
`canonical_payload_digest` can be emitted. Earlier structural failures map
payload integrity to `ABSENT` only when a required artifact is absent;
otherwise it is `INVALID`. Downstream states remain `NOT_EVALUATED`, except
that absent optional signature material is distinguishable from present but
not-yet-evaluated material.

### 3. Evaluate dimensions after payload integrity

Once payload integrity is valid, evaluate the optional bundled signature,
trusted signing-key membership, original binding fields, invocation identity,
invocation binding, and selected Freshness window. Their dimension states are
independent even though the top-level failure has one precedence position.

Return the first applicable top-level reason in this order:

1. `SIGNATURE_INVALID`;
2. `SIGNATURE_REQUIRED`;
3. a binding failure: `BINDING_FIELDS_INCOMPLETE`,
   `BINDING_FIELD_MALFORMED`, or `BINDING_HASH_MISMATCH`;
4. `BINDING_REQUIRED`;
5. `TRUSTED_SIGNER_NOT_FOUND` when external membership was required;
6. an invocation-identity grammar or recomputation reason;
7. an invocation-binding grammar, recomputation, missing-input,
   invalid-input, or cross-field-mismatch reason;
8. `FRESHNESS_TIMESTAMP_MALFORMED`,
   `FRESHNESS_TIMESTAMP_IN_FUTURE`, or `FRESHNESS_STALE`; or
9. `OK` with overall status `VALID`.

The candidate must preserve evaluated dimension states even when an earlier
item in this final precedence list selects the top-level reason.

## Canonicalization and hashing

### Released v0.4.0 / v1

The current identifier is `json_sorted_keys_no_whitespace_utf8`. The hash input
is UTF-8 encoding of JSON with recursively sorted object keys, array order
preserved, no insignificant whitespace, and non-ASCII characters emitted
directly. No Unicode normalization occurs. SHA-256 outputs are lowercase
hexadecimal.

The following constructions must be reproduced byte-for-byte:

```text
ai_hash_sha256 = SHA256(UTF8(canonical(ai_output_v1)))

binding_hash = SHA256(UTF8(canonical({
  "request_hash": request_hash,
  "response_hash": response_hash
})))

invocation_identity.hash_sha256 = SHA256(UTF8(canonical({
  "format": "aelitium-invocation-v1",
  "surface": surface,
  "mode": mode,
  "request": normalized_request
})))

invocation_binding.hash_sha256 = SHA256(UTF8(canonical({
  "format": "aelitium-invocation-binding-v1",
  "invocation_hash": invocation_hash,
  "response_hash": response_hash
})))
```

The verifier does not reconstruct `request_hash` or `response_hash` from source
provider traffic. It checks the stored binding formula and the invocation
object's own selected fields.

### Unreleased portable v2

The current branch additionally implements the exact identifier
`aelitium_jcs_profile_v2`. A clean-room verifier must implement the complete
`AELITIUM-DISPATCH-JSON-1` lexical router before either manifest parser. The
router scans original bytes, performs no number conversion, profile validation,
duplicate rejection, or normalization, uses only the final top-level selector,
and never supplies parsed values to a version verifier.

Structural traversal must not depend on the host call stack. Exhausting a host
recursion limit is not a malformed-selector outcome and must not redirect v2 to
the v1/error-resolution path. The Python implementation uses iterative stacks
for selector traversal, its fresh strict-v2 parse, and profile validation while
leaving the released v1 parser unchanged.

An exact final v1 selector re-enters the complete CPython-aligned path. An
exact final v2 selector reparses from byte zero under strict UTF-8 RFC 8259,
rejects duplicates and the complete v2 Unicode/number profile recursively,
and never retries v1. Missing, malformed, non-string, unknown, and non-object
outcomes use legacy error resolution so existing field-check precedence is
unchanged.

V2 canonical output is exact RFC 8785 / JCS for the profiled value domain:
Unicode scalars excluding noncharacters, no normalization, UTF-16 key order,
finite binary64 numbers of magnitude at most `2^53 - 1`, and a mathematical
pre-narrowing check for integer-form tokens in that same inclusive range.
Canonical bytes `C` contain no BOM or newline; storage permits only `C` or
`C || LF`; every hash consumes `C` alone.

The enclosing identifier governs the payload, request, response, original
binding, invocation identity, and invocation binding constructions. Semantic
field selection does not change, and no identifier/prefix bytes are added.
The strict profile applies throughout a v2 manifest, including ignored
extensions, while signatures remain over exact raw manifest bytes.

The normative byte corpus is
[`conformance/canonicalization_v2/manifest.json`](../conformance/canonicalization_v2/manifest.json).
Its 114 frozen cases include applicable RFC 8785 Appendix B values, AELITIUM
profile boundaries, storage, exact hash inputs, dispatch and CPython digit-limit
isolation, manifest extensions, cross-version refusal, and v1 preservation.
This corpus supplements and does not renumber either existing corpus.

### Cross-language closure gate

No independent implementation exists. The current readiness gate is:

| Cross-language issue | Status | Required behavior |
|---|---|---|
| Floating-point parsing, exponent thresholds, rounding, and rendering | **CLOSED** | IEEE 754 binary64 conversion and the exact shortest-round-trip formatting rule in `CANONICALIZATION_SPEC.md`; reproduce the frozen boundary vectors. |
| Exact `NaN`, `Infinity`, and `-Infinity` legacy tokens | **CLOSED legacy behavior** | Preserve their exact case-sensitive acceptance and output in unrestricted metadata. Do not call them standard JSON and do not infer native invocation assurance from them. |
| Unicode object-key ordering | **CLOSED** | Lexicographic Unicode scalar-value order, not UTF-8-byte or UTF-16-code-unit order. |
| Unicode escaping and non-BMP output | **CLOSED** | Apply the exact escape table, emit other scalars literally as strict UTF-8, and perform no normalization. |
| Duplicate names in the canonical payload | **CLOSED** | Parse left to right with the last value retained; the raw duplicate spelling then fails exact canonical-byte equality as `CANONICAL_BYTES_MISMATCH`. |
| Duplicate names in the manifest | **CLOSED legacy behavior** | Preserve last-value parsing. A global rejection would change v0.4.0 behavior. |
| Ill-formed UTF-8 and unpaired surrogate payload data | **CLOSED** | Reject at the existing `CANONICAL_NOT_JSON` stage. A valid surrogate pair decodes to one scalar, but its escaped source form is not canonical. |
| Unpaired surrogates in ignored manifest extensions | **CLOSED legacy behavior** | Preserve acceptance of the escaped form when the extension is not used by a manifest check. The manifest is not canonicalized; exclude this case from the restricted subset. |
| Canonical whitespace, arrays, literals, and terminal newline | **CLOSED** | Compact recursive encoding, preserved array order, exact lowercase literals, and stored bytes equal to `C` or `C || 0A`, hashing only `C`. |
| Integer magnitudes of at most 640 decimal digits | **RESTRICTED SUBSET** | Parse and emit exact signed base-10 integers without binary64 conversion in canonical metadata, manifest extensions, explicit inputs, and result output. |
| Integer magnitudes above 640 decimal digits | **OPEN** | Released v0.4.0 delegates source conversion to a configurable CPython decimal-conversion guard, while direct API values can already be Python integers, so the complete accepted and serializable domain cannot be determined portably from the identifier alone. |

The dedicated corpus is
[`conformance/canonicalization/manifest.json`](../conformance/canonicalization/manifest.json)
and its 30 vectors. Every vector freezes source bytes, source digest, exact
accept/reject result, existing verifier reason, and canonical bytes/digest when
accepted. The runner compares the implementation to those committed values; it
does not create expected canonical bytes with the canonicalizer under test.

### Exact restricted domain

A candidate may implement and accurately label this restricted subset:

- strict UTF-8 without BOM, with every parsed string and object-member name in
  every bundle JSON file limited to Unicode scalar values;
- JSON objects with canonical stored bytes (therefore no duplicate stored
  member spellings), arrays in order, strings containing only Unicode scalar
  values, `null`, and booleans;
- finite IEEE 754 binary64 numbers serialized by the closed rule; and
- integer magnitudes containing at most 640 decimal digits.

The subset excludes `NaN`, `Infinity`, `-Infinity`, and integer magnitudes over
640 digits. Exclusion from the subset is not a new AELITIUM verifier rejection:
the three non-finite tokens remain accepted legacy behavior, and some v0.4.0
runtimes accept larger integers.

A candidate limited to this domain must report **RESTRICTED SUBSET** and must
refuse out-of-subset evidence without claiming it is invalid under every
v0.4.0 runtime. A candidate cannot claim the complete current surface while the
extreme-integer row remains **OPEN**. Closing it requires a separately versioned
rule or evidence that a restriction changes no accepted v0.4.0 artifact; this
task provides neither.

## Signature and external signing-key membership

When `verification_keys.json` is absent, `signature_validity=ABSENT`. When it is
present after payload validation, require:

- `keyring_format` exactly `ed25519-v1`;
- exactly one object in `keys` and exactly one object in `signatures`;
- a non-empty string `key_id` shared by both entries;
- strict standard Base64 public key and signature encodings;
- 32 decoded public-key bytes and 64 decoded signature bytes;
- signature algorithm exactly `ed25519`;
- signature scope exactly `manifest.json`; and
- Ed25519 verification over the raw bytes of `ai_manifest.json`, including any
  terminal newline.

Bundled public-key material is not an independent trust input.
`trusted_signer_identity=VALID` requires a valid bundled signature and a
matching fingerprint in an explicitly supplied `aelitium-trust-v1` file. The
fingerprint is `ed25519:sha256:` followed by SHA-256 of the 32 raw public-key
bytes in lowercase hexadecimal. Trust-store labels never participate in the
decision. The store is a closed object with exactly `trust_store_format` and
`signers`; every signer permits only `algorithm`, `public_key_b64`, and optional
non-empty `label`; duplicate derived fingerprints are invalid.

## Binding and invocation grammar

Original binding evidence is `ABSENT` only when all four fields are absent:

- `ai_manifest.json.binding_hash`;
- `ai_canonical.json.metadata.request_hash`;
- `ai_canonical.json.metadata.response_hash`; and
- `ai_canonical.json.metadata.binding_hash`.

Partial presence is `INVALID`. All four values must be 64 lowercase
hexadecimal characters. Both stored binding values must equal the binding
formula above.

An `aelitium-invocation-v1` stored object has exactly `format`, `surface`,
`mode`, `request`, and `hash_sha256`. Its request has exactly required `model`
and `messages`, plus optional `parameters`. Model is non-empty, messages is an
array of JSON values, parameter names are surface-specific, and non-finite
floating-point values are rejected by this primitive.

| Surface | Allowed modes | Allowed parameters |
|---|---|---|
| `openai.chat.completions` | `sync_non_streaming`, `sync_streaming` | none |
| `anthropic.messages` | `sync_non_streaming` | `max_tokens` |
| `litellm.completion` | `sync_non_streaming` | `temperature`, `max_tokens`, `top_p`, `seed`, `stop` |

An empty `parameters` object is normalized away for hashing. Unknown structure,
surface, mode, request keys, or parameters is invalid. The stored digest is
always recomputed.

An `aelitium-invocation-binding-v1` object has exactly `format`,
`invocation_hash`, `response_hash`, and `hash_sha256`. The three hashes are
strict lowercase SHA-256 spellings. Its own digest is recomputed, then its
invocation and response values are compared with the same bundle's already
valid invocation identity and stored response hash. A binding can never become
`VALID` when invocation identity is absent or invalid.

## Freshness

The complete policy pair selects declared-time recency. Both timestamps use
exact calendar-valid `YYYY-MM-DDTHH:MM:SSZ` UTC whole-second syntax. Maximum age
is a non-negative integer and Boolean values are not integers for this purpose.

```text
age_seconds = reference_time - ai_canonical.json.ts_utc
```

Zero and the maximum age are inclusive `VALID` boundaries. Negative age is
`INVALID` with `FRESHNESS_TIMESTAMP_IN_FUTURE`; age above the maximum is
`INVALID` with `FRESHNESS_STALE`. This state does not use the manifest
timestamp, system clock, signature result, or external signing-key membership.

## Assurance-result requirements

The candidate must emit the eight entries in the exact order and with the
dimension-specific states, bases, references, and boundaries in
[`ASSURANCE_RESULT_V1.md`](ASSURANCE_RESULT_V1.md). It must enforce the
cross-dimension invariants there before serialization. It must not emit a ninth
dimension or any aggregate score.

The ordered names are `payload_integrity`, `binding_field_consistency`,
`invocation_identity_consistency`, `invocation_binding_consistency`,
`signature_validity`, `trusted_signer_identity`, `freshness`, and
`authorization`.

`authorization` must remain `NOT_EVALUATED`. `ABSENT`, `UNESTABLISHED`,
`NOT_EVALUATED`, and `INVALID` are never interchangeable.

## Comparison requirements

The candidate comparator must verify both inputs with default verification
options before selecting a basis. It must reproduce the exact mode/basis table,
decision table, comparison-input invariants, side summaries, and claim
boundaries in [`COMPARE_RESULT_V1.md`](COMPARE_RESULT_V1.md).

In particular:

- invalid input yields `INVALID_BUNDLE`, not fallback;
- strict mode with insufficient usable invocation evidence yields
  `NOT_COMPARABLE`, basis `NONE`, and required basis
  `INVOCATION_IDENTITY_V1`;
- different selected identities yield `NOT_COMPARABLE` and no response
  relationship;
- two valid bundles with different canonicalization identifiers yield
  `NOT_COMPARABLE`, basis `NONE`, reason
  `CANONICALIZATION_IDENTIFIER_MISMATCH`, and no response relationship before
  any current comparison basis is applied; and
- `NOT_COMPARABLE` is a semantic result that must not be turned into an
  exception or negative equality claim.

## Result serialization

A byte-comparable CLI mode should emit UTF-8 JSON with keys sorted
lexicographically, compact separators, and one terminal LF. Semantic conformance
requires schema-valid equivalent values; byte conformance additionally requires
the exact serialization. Local paths must not appear in artifact, trust, or
policy references.

## Conformance and acceptance gate

A candidate is not accepted as independent until all of these pass:

1. every committed conformance vector, without invoking AELITIUM Python;
2. schema validation for every emitted result;
3. byte-stable repeated output under identical explicit inputs;
4. mutation tests for each integrity, signature, trust, Freshness, invocation,
   comparison, and legacy boundary;
5. impossible-state tests, including valid external signing-key membership
   after failed signature verification and valid invocation binding after
   invalid invocation identity;
6. all four comparison outcomes and every current mode/basis route;
7. explicit confirmation that no network, ambient time, or ambient trust input
   was read;
8. all 30 released-v1 cross-language canonicalization vectors, with any
   restricted implementation explicitly refusing and labelling out-of-subset
   inputs;
9. all 114 portable-v2 vectors, including dispatch under CPython integer digit
   limits 640, 4300, and disabled; and
10. a provenance review demonstrating that the decision engine neither imports
   nor shells out to AELITIUM Python.

The present Python conformance runner is an implementation-aligned oracle and
corpus exerciser. It is not evidence that a second implementation exists.

As of this document revision, the portable-v2 Python implementation and frozen
corpus are present, but no independent implementation exists. The
complete-surface readiness verdict remains
**NOT_READY_FOR_CLEAN_ROOM_VERIFIER** because the accepted domain for integer
magnitudes above 640 decimal digits remains dependent on the configured Python
runtime. The restricted subset is specified and testable, but it is not the
complete v0.4.0 surface.
