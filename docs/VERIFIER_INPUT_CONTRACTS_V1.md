# AELITIUM Verifier Input Contracts v1

**Status:** NORMATIVE-UNRELEASED

**Contract identifier:** `aelitium-verifier-input-contracts-v1`

**Scope:** source, structural, and semantic contracts for `ai_manifest.json`,
`verification_keys.json`, and an explicitly supplied `aelitium-trust-v1`
trust store

## 1. Authority and interpretation

This document defines the language-neutral verifier-input rules that, together
with the four named schemas and the separate Phase 2 frozen conformance corpus,
close specification gaps G-04, G-05, and G-06. It also defines the portable
signature acceptance profile implemented by the current unreleased runtime,
including explicit capability selection and strict profile execution without
fallback. This document does not claim a release or independent-verifier
readiness.

The normative hierarchy and conflict rule are defined by
[`VERIFIER_PROTOCOL_V1.md`](VERIFIER_PROTOCOL_V1.md). The source and value
profiles referenced here are completed by
[`CANONICALIZATION_SPEC.md`](CANONICALIZATION_SPEC.md), and capability and
operational behavior is completed by
[`LEGACY_V1_COMPATIBILITY_AND_OPERATIONAL_POLICY_V1.md`](LEGACY_V1_COMPATIBILITY_AND_OPERATIONAL_POLICY_V1.md).
Trust meanings remain bounded by [`TRUST_BOUNDARY.md`](TRUST_BOUNDARY.md).

Python and every other implementation are non-normative. Observed runtime
behavior cannot settle an undocumented choice or override public prose.
Frozen conformance vectors are normative examples within their declared scope,
but cannot override Level 1 prose. A conflict between these sources blocks
conformance; an implementation must not choose whichever outcome matches its
host language.

The four JSON Schemas named in this document constrain parsed values only.
They do not define raw-source semantics, parsing, operational outcomes, or
public reason precedence. In particular, the first diagnostic emitted by a
generic JSON Schema validator is never an AELITIUM public reason.

## 2. Common source and operational boundary

An input source is an immutable byte sequence established under the adopted
operational policy. Filesystem paths, reads, snapshots, resource availability,
and capability selection are outside semantic JSON processing. An inability to
establish immutable input bytes produces the applicable operational outcome
and no semantic verification result or assurance result.

This boundary applies to every input in this contract. It is especially
observable for explicit trust input:

1. If external signing-key membership is required and no trust input was supplied,
   the authorized semantic result is `TRUST_INPUT_NOT_PROVIDED`.
2. If trust input was supplied but immutable bytes cannot be established,
   acquisition follows the operational policy. Outcomes include, where
   applicable, `INPUT_IO_ERROR`, `INPUT_NOT_REGULAR_FILE`,
   `INPUT_CHANGED_DURING_SNAPSHOT`, `INPUT_OUTSIDE_DECLARED_CAPABILITY`,
   `CAPABILITY_PROFILE_UNAVAILABLE`, `RESOURCE_LIMIT_EXCEEDED`, and
   `RESOURCE_EXHAUSTED`. No `TRUST_STORE_INVALID` or other semantic result
   exists at this boundary.
3. Only after immutable trust bytes have been established can an authorized
   source, profile, or semantic failure produce `TRUST_STORE_INVALID`.

The operational policy's explicit named-runtime compatibility results remain
profile-qualified semantic results in their stated source positions. They do
not convert general acquisition, capability, limit, or resource failures into
semantic invalidity.

Except where a v2 rule below says otherwise, JSON whitespace means exactly the
four RFC 8259 whitespace octets: space, horizontal tab, line feed, and carriage
return.

## 3. `ai_manifest.json` — G-04

### 3.1 Immutable bytes and routing

The input is the immutable raw byte sequence for the required filename
`ai_manifest.json`. `AELITIUM-DISPATCH-JSON-1` consumes that complete sequence
as non-observable lookahead. The selected parser starts again at byte zero and
receives the same immutable sequence. An exact final v2 selector chooses v2;
after that selection, a v2 failure never retries v1. Every other dispatch
outcome follows the published legacy/error-resolution route.

The identical raw manifest byte sequence is the later pure-Ed25519 signature
message. No decoding, newline conversion, member sorting, whitespace removal,
escape rewriting, or canonicalization changes those signed bytes.

Canonical payload parsing remains observably before manifest parsing. Dispatch
does not add a result reason or change that order.

### 3.2 Released legacy-v1 source profile

The identifier `json_sorted_keys_no_whitespace_utf8` selects the released
legacy profile. Its source rules are:

- the source is strict UTF-8 with no leading BOM;
- it contains exactly one complete legacy JSON value, surrounded only by JSON
  whitespace;
- the only non-RFC JSON constants are the exact, case-sensitive tokens `NaN`,
  `Infinity`, and `-Infinity`;
- object occurrences are processed left to right and the final decoded member
  name wins at every depth; escaped-equivalent names are equal;
- permitted escaped unmatched surrogate code units are retained as opaque
  legacy string elements rather than manufactured into Unicode scalars;
- every reached integer-form token, including one in an ignored or overwritten
  value, follows the capability-qualified rules in the operational policy;
- unknown members are accepted after source-map collapse, ignored
  semantically, and acquire no verification, assurance, trust, authorization,
  Freshness, or comparison meaning; and
- the collapsed root must be an object.

The applicable legacy capability still controls whether reached non-finite or
opaque-surrogate values are evaluated, refused operationally, or handled by an
exact named profile. This contract does not replace those capability rules with
strict RFC 8259, global duplicate rejection, scalar-only strings, or one
unqualified integer limit.

A source/profile failure is `MANIFEST_NOT_JSON`; a successfully parsed
non-object root is `MANIFEST_NOT_OBJECT`, at their published positions.

### 3.3 Portable-v2 source and value profile

The identifier `aelitium_jcs_profile_v2` selects a fresh parse from byte zero
under the complete profile in `CANONICALIZATION_SPEC.md`:

- exactly one RFC 8259 value encoded as strict shortest-form UTF-8, with no
  leading BOM and only JSON whitespace outside the value;
- duplicate decoded member names rejected recursively, including escaped-name
  duplicates and duplicates inside unknown extensions;
- strings and names restricted to Unicode scalar values excluding the complete
  v2 noncharacter set;
- valid surrogate pairs decoded to one scalar, and unmatched, reversed, or
  overlapping surrogate escapes rejected;
- the exact finite-binary64 magnitude and pre-narrowing mathematical
  integer-token profile;
- unknown members ignored semantically only after their complete recursive
  values pass the v2 profile; and
- an object root.

The manifest itself is not JCS-canonicalized. A v2 source/profile failure is
`MANIFEST_NOT_JSON`; a profile-valid non-object root is
`MANIFEST_NOT_OBJECT`. Unknown valid members acquire no verification,
assurance, trust, authorization, Freshness, or comparison meaning.

### 3.4 Required members and governed values

After source/profile processing and the object-root check, presence is tested
in exactly this order:

1. `schema`
2. `ts_utc`
3. `input_schema`
4. `canonicalization`
5. `ai_hash_sha256`

The first absent member returns `MANIFEST_MISSING_FIELD`. JSON Schema's
`required` keyword does not determine this order or reason.

The governed value checks are then performed in this order:

| Member | Required value | Failure |
|---|---|---|
| `schema` | string exactly `ai_pack_manifest_v1` | `MANIFEST_BAD_SCHEMA` |
| `input_schema` | string exactly `ai_output_v1` | `MANIFEST_BAD_INPUT_SCHEMA` |
| `canonicalization` | string exactly equal to the selected route identifier | `MANIFEST_BAD_CANONICALIZATION` |
| `ts_utc` | conditional rule in section 3.5, when enabled | `MANIFEST_BAD_TS_UTC` |
| `ai_hash_sha256` | string of exactly 64 ASCII lowercase hexadecimal characters matching `[0-9a-f]{64}` | `MANIFEST_BAD_AI_HASH_SHA256` |

A well-formed `ai_hash_sha256` that differs from SHA-256 of the established
canonical payload bytes fails later as `HASH_MISMATCH`.

`binding_hash` is optional. When the complete binding quartet is evaluated,
its type, spelling, and value retain the binding reasons and precedence in
`INDEPENDENT_VERIFIER_REQUIREMENTS.md`. Its optional schema constraint does not
move binding validation into manifest payload-integrity evaluation.

### 3.5 Manifest timestamp option

Manifest timestamp validation concerns `ai_manifest.json.ts_utc`. It is
separate from Freshness G-11, which concerns `ai_canonical.json.ts_utc` and an
explicit policy pair. Manifest validation does not parse a calendar, calculate
age, consult a clock, or establish historical time.

When `validate_manifest_timestamp=false`, `ts_utc` remains required, but no
timestamp type, spelling, component-range, or calendar check occurs. Under v2,
the value and all values nested within it still must satisfy the ordinary v2
source/value profile. Any v2-profile-valid JSON type can therefore satisfy the
presence requirement.

When validation is enabled on the v1 route, section 6 of the operational policy
governs the decoded value:

- the shape is `DDDD-DD-DDTDD:DD:DDZ[LF]`, with exactly fourteen digit
  positions, literal ASCII separators, and zero or one final decoded U+000A;
- a final U+000D, CRLF, two final LFs, an embedded LF, or any other suffix
  fails;
- `V1_RESTRICTED_PORTABLE` and `V1_FROZEN_LEGACY_COMPATIBILITY` use ASCII
  U+0030 through U+0039, with the policy's distinction between an ASCII
  non-digit semantic failure and a non-ASCII digit-position capability
  refusal;
- `V1_NAMED_RUNTIME_COMPATIBILITY` uses only the selected frozen Unicode `Nd`
  table, with an outside-table digit producing its exact profile-qualified
  result; and
- validation is lexical only and makes no component-range, calendar,
  leap-year, leap-second, chronology, or historical-occurrence claim.

When validation is enabled on the v2 route, the decoded value must be a string
matching this whole-string ASCII expression:

```text
[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z
```

It contains exactly 20 decoded characters. Every digit is U+0030 through
U+0039; separators are the displayed ASCII characters; no decoded LF or other
prefix/suffix is allowed. It has no Unicode `Nd` or host-database dependency.
This is also lexical only: impossible component or calendar values can match.

### 3.6 Manifest failure order

Subject to earlier explicit-input and canonical-payload parsing boundaries, the
observable manifest order is exactly:

1. `MANIFEST_NOT_JSON`
2. `MANIFEST_NOT_OBJECT`
3. `MANIFEST_MISSING_FIELD`
4. `MANIFEST_BAD_SCHEMA`
5. `MANIFEST_BAD_INPUT_SCHEMA`
6. `MANIFEST_BAD_CANONICALIZATION`
7. `MANIFEST_BAD_TS_UTC`, only when timestamp validation is enabled
8. `MANIFEST_BAD_AI_HASH_SHA256`
9. the already-published canonical schema, bytes, hash, signature, binding,
   trust-membership, invocation, and Freshness checks in their existing order

No new public reason is introduced.

### 3.7 Parsed-value schemas

The route-specific schemas are:

- [`ai_manifest_v1.json`](../engine/schemas/ai_manifest_v1.json)
- [`ai_manifest_v2.json`](../engine/schemas/ai_manifest_v2.json)

Both have open roots. Both leave `ts_utc` unconstrained because the verifier
option controls its field validation. Source-profile enforcement and public
reason selection remain procedural.

## 4. `verification_keys.json` — G-05

### 4.1 Presence and source profile

`verification_keys.json` is optional. Before payload integrity is established,
its stable presence distinguishes `signature_validity=NOT_EVALUATED` from
absence, which gives `signature_validity=ABSENT`. Its acquired bytes are parsed
and its signature is evaluated only after payload integrity succeeds.

Its only format is `ed25519-v1`, for both manifest routes. The manifest
canonicalization identifier does not apply the v2 source profile to this file.
The source uses the adopted legacy auxiliary profile:

When a v2 manifest is selected and the operation declares
`V1_LEGACY_UNSUPPORTED`, these auxiliary sources still use
`V1_FROZEN_LEGACY_COMPATIBILITY` (including its 640-digit integer ceiling).
`V1_LEGACY_UNSUPPORTED` disables evaluation of a v1 bundle; it does not
authorize ambient-host parsing of the independent `ed25519-v1` auxiliary
format. The same rule applies to a supplied `aelitium-trust-v1` store. The
outer requested/effective capability declaration remains unchanged.

- strict UTF-8, no leading BOM, and exactly one complete legacy JSON value
  surrounded only by JSON whitespace;
- the exact legacy constants and capability-qualified integer handling;
- final decoded member name wins at every object depth, including
  escaped-equivalent names and values later ignored or overwritten;
- permitted unmatched surrogate code units remain opaque legacy string
  elements; and
- root, key-entry, and signature-entry objects are open after collapse;
  unknown members are ignored and acquire no semantic meaning.

An implementation must not substitute v2 duplicate rejection, scalar-only
strings, or closed objects under `ed25519-v1`.

### 4.2 Structure and fields

The collapsed root must be an object containing:

- `keyring_format`, exactly the string `ed25519-v1`;
- `keys`, an array containing exactly one object; and
- `signatures`, an array containing exactly one object.

The key entry requires `key_id` and `public_key_b64`. The signature entry
requires `key_id`, `algorithm`, `scope`, and `sig_b64`.

Both `key_id` values must be non-empty legacy-decoded strings and exactly equal
as decoded legacy code-unit sequences. They are not trimmed or normalized;
whitespace-only and permitted opaque legacy strings are not narrowed. A
`key_id` is only an intra-file correlation label. It is not an identity,
fingerprint, authorization, certificate, or trust assertion.

`algorithm` is exactly the case-sensitive string `ed25519`. `scope` is exactly
the case-sensitive string `manifest.json`.

### 4.3 Base64 compatibility profile

The public-key spelling is exactly 44 characters and matches:

```text
^[A-Za-z0-9+/]{43}=$
```

It must decode under RFC 4648 section 4 to exactly 32 bytes.

The signature spelling is exactly 88 characters and matches:

```text
^[A-Za-z0-9+/]{86}==$
```

It must decode to exactly 64 bytes.

Only the standard alphabet is accepted. URL-specific `-` and `_`, any embedded
or surrounding whitespace, missing/extra/misplaced/leading padding, trailing
garbage, concatenated encodings, or an incorrect decoded length rejects the
material.

For compatibility, non-zero unused low pad bits are accepted: the low two bits
in the last alphabet character of a 32-byte key and the low four bits in the
last alphabet character of a 64-byte signature need not be zero. A verifier
must not require encode-after-decode equality. Producer recommendations to emit
canonical zero pad bits do not narrow verifier acceptance.

### 4.4 Signature-verification capability

`ed25519-v1` remains the keyring structural format, and the exact string
`ed25519` remains its primitive identifier. Neither selects the acceptance
rules for edge encodings and group elements. Those rules are selected by the
orthogonal verifier capability `signature_verification.profile`.

This contract defines exactly one portable profile:

```text
ED25519_PORTABLE_STRICT_1
```

The requested profile and effective profile must both be explicit and exactly
equal for every semantic verification result. There is no
implicit profile and no fallback. A verifier that does not implement the
requested profile returns the operational outcome
`CAPABILITY_PROFILE_UNAVAILABLE`; it produces no semantic verification result
or assurance result. The profile is verifier configuration and output
metadata, never evidence-bundle content.

A lexically well-formed but unsupported requested profile remains present
unchanged in the outer tool result's `capability.requested`; it does not become
effective. The requested identifier uses the ASCII `capability-identifier`
grammar in `LEGACY_V1_COMPATIBILITY_AND_OPERATIONAL_POLICY_V1.md`. Malformed
request syntax is a tool/API usage failure rather than a capability outcome.
This requested-value envelope does not broaden semantic results: both requested
and effective signature profiles in every semantic result remain exactly
`ED25519_PORTABLE_STRICT_1`.

The generic historical edge-case acceptance set of AELITIUM v0.4.0 cannot be
made a portable normative profile. Its implementation delegated verification
through an unpinned `cryptography>=41` dependency and an unpinned backend.
Neither that dependency family nor observed OpenSSL behavior is normative. A
future exact named-runtime profile may be specified separately, but no such
profile or silent compatibility fallback is defined here.

### 4.5 `ED25519_PORTABLE_STRICT_1`

The inputs are:

- `A_encoded`, the exact 32 bytes decoded from `public_key_b64`;
- `signature`, the exact 64 bytes decoded from `sig_b64`;
- `R_encoded = signature[0:32]`;
- `S_encoded = signature[32:64]`; and
- `M`, the exact immutable raw bytes acquired for `ai_manifest.json`.

The profile uses the Edwards25519 field prime
`p = 2^255 - 19`, prime subgroup order
`L = 2^252 + 27742317777372353535851937790883648493`, and base point `B`
defined for Ed25519 in RFC 8032 section 5.1. Its standard compressed encoding
of `B` is
`5866666666666666666666666666666666666666666666666666666666666666`.
SHA-512 is the function in FIPS PUB 180-4 as incorporated by
`VERIFIER_PROTOCOL_V1.md`. Its use and byte-to-integer interpretation are
exactly those in RFC 8032 section 5.1: digest and scalar encodings are
interpreted as unsigned little-endian integers.

Verification performs these steps in order:

1. Decode `A_encoded` exactly by RFC 8032 section 5.1.3 point decoding.
2. Decode `R_encoded` by the same rules.
3. For both encodings, require the decoded `y < p`; an encoding of `y >= p`
   is non-canonical and invalid.
4. Reject an encoding whose recovered `x = 0` while its encoded sign bit is 1.
5. Reject failed square-root recovery or any other invalid point encoding.
6. Reject `A` when it is the identity point.
7. Require `[L]A` to equal the identity point.
8. Require `[L]R` to equal the identity point.
9. Reject every non-identity small-order `A` or `R`. Identity `R` is not
   rejected merely for being identity; it proceeds to the remaining checks.
10. Interpret `S_encoded` as an unsigned little-endian integer `S` and
    require `0 <= S < L`.
11. Compute
    `k = little_endian_integer(SHA-512(R_encoded || A_encoded || M)) mod L`.
12. Accept only when the exact, **uncofactored** equation
    `[S]B = R + [k]A` holds.

No cofactored equation, backend-specific acceptance, retry, or fallback is
permitted. Any point-decoding, identity, subgroup, small-order, scalar, or
equation failure maps to `SIGNATURE_INVALID` and
`signature_validity=INVALID`; these internal causes do not create new public
reasons. `S = L - 1` passes only the scalar-range check and must still satisfy
the equation. `S = L` fails before the equation.

Ed25519 contexts, prehash mode, Ed448, certificates, and algorithm negotiation
are not part of this profile. Ordinary canonical Ed25519 signatures satisfying
these rules remain in the portable domain. The strict edge rules are selected
by the explicit profile and do not silently redefine the historical,
backend-dependent acceptance of released v0.4.0 runtimes.

### 4.6 Raw message and failure mapping

The message is the exact immutable raw byte sequence acquired for
`ai_manifest.json`. It includes member order, whitespace, unknown members,
escape spellings, line endings, and terminal bytes. It is never the parsed,
reserialized, or canonicalized manifest.

If acquired keyring bytes are present after payload integrity succeeds, any
source/profile, structure, required-member, identifier, Base64, decoded-length,
cross-entry-key, algorithm, scope, public-key, signature, or mathematical
verification failure sets `signature_validity=INVALID` and produces
`SIGNATURE_INVALID`. Lower-level diagnostics are non-normative detail.

An absent keyring yields `signature_validity=ABSENT`. After payload success,
absence while `require_signature` or external signing-key membership is required
produces `SIGNATURE_REQUIRED`. A valid signature sets
`signature_validity=VALID`, but by itself leaves
`trusted_signer_identity=UNESTABLISHED` and establishes no authorization,
provider execution, historical occurrence, or response causation.

Payload and manifest failures precede keyring semantic evaluation.
`SIGNATURE_INVALID` precedes `SIGNATURE_REQUIRED`, binding failures,
`BINDING_REQUIRED`, `TRUSTED_SIGNER_NOT_FOUND`, invocation failures, and
Freshness failures.

### 4.7 Parsed-value schema

[`verification_keys_v1.json`](../engine/schemas/verification_keys_v1.json) has
open root, key-entry, and signature-entry objects. Cross-entry equality,
decoding, decoded lengths, pad-bit semantics, and Ed25519 verification remain
procedural.

## 5. Explicit `aelitium-trust-v1` input — G-06

### 5.1 Presence, acquisition, and trust source

The trust store is an explicit verifier input for one operation. There is no
ambient path, environment-derived trust, network lookup, default trust store,
system certificate store, certificate-chain discovery, or provider lookup.

The three-part acquisition boundary in section 2 is mandatory. In particular,
an unavailable or unreadable supplied path is operational; it is not a
semantically invalid trust store. The following source rules begin only after
immutable trust bytes have been established:

- strict UTF-8, no leading BOM, and exactly one complete legacy JSON value
  surrounded only by JSON whitespace;
- exact legacy constants, opaque permitted legacy strings, and
  capability-qualified integer handling;
- final decoded member name wins at every object depth before semantic
  validation; and
- root and signer closedness is applied only after source-map collapse.

Thus a duplicate name is not rejected merely because it appeared in source.
Every reached value still undergoes source and capability processing before a
later duplicate overwrites it.

### 5.2 Closed semantic structure

After collapse, the root must be an object containing exactly:

- `trust_store_format`, the case-sensitive string `aelitium-trust-v1`; and
- `signers`, an array of zero or more entries.

An empty `signers` array is valid and represents an empty membership set.

Each signer must be an object containing exactly:

- required `algorithm`, the case-sensitive string `ed25519`;
- required `public_key_b64`, using the exact 32-byte Base64 compatibility
  profile in section 4.3; and
- optional `label`.

When present, `label` must be a non-empty legacy-decoded string. It is not
trimmed or normalized; a whitespace-only value and a permitted opaque legacy
string remain accepted. It is non-authoritative and never participates in
membership. Duplicate labels are allowed. No stored `fingerprint` member is
permitted.

### 5.3 Fingerprints and uniqueness

For each decoded 32-byte public key, derive:

```text
fingerprint = "ed25519:sha256:" || lowercase_hex(SHA256(raw_public_key_bytes))
```

The prefix is not part of the SHA-256 input. The suffix is exactly 64 lowercase
ASCII hexadecimal characters. The verifier derives this value; it never reads
a supplied fingerprint from the store.

Derived fingerprints must be unique within one valid store. Two entries that
decode to the same key are duplicates even if their labels differ or their
accepted Base64 spellings differ only in unused pad bits. Any such duplicate
makes the acquired store semantically invalid as `TRUST_STORE_INVALID`, subject
to the operational policy's capability and resource boundaries.

### 5.4 Membership and result semantics

Membership is evaluated only for a mathematically valid bundled signature.
The exact public-key bytes used in successful signature verification are
fingerprinted once and compared for exact membership in the explicit store's
derived fingerprint set.

| Situation | Signature/trust state and outcome |
|---|---|
| No store and membership optional | `trusted_signer_identity=UNESTABLISHED`; no trust failure |
| Membership required and no store supplied | `TRUST_INPUT_NOT_PROVIDED` before bundle inspection |
| Supplied store bytes cannot be established | Operational outcome only; no semantic or assurance result |
| Acquired store fails an authorized source/profile/semantic check | `TRUST_STORE_INVALID` before bundle inspection, whether membership is optional or required |
| Valid store and unsigned bundle, membership optional | `signature_validity=ABSENT`; trust remains `UNESTABLISHED` |
| Valid store and unsigned bundle, membership required | `SIGNATURE_REQUIRED` after payload integrity |
| Invalid bundled signature | `SIGNATURE_INVALID`; trust remains `UNESTABLISHED` |
| Valid signature and fingerprint present | `trusted_signer_identity=VALID` |
| Valid signature and fingerprint absent, membership optional | trust remains `UNESTABLISHED`; no trust failure |
| Valid signature and fingerprint absent, membership required | `TRUSTED_SIGNER_NOT_FOUND`, subject to earlier signature and binding precedence |

`TRUSTED_SIGNER_NOT_FOUND` requires both a valid store and a valid signature.
Trust membership is key membership only. It does not establish authorization,
human, legal, organizational, or provider identity, provider execution,
response causation, historical occurrence, trusted time, revocation status,
semantic truth, quality, or legal compliance.

### 5.5 Parsed-value schema

[`trust_store_v1.json`](../engine/schemas/trust_store_v1.json) closes the root
and signer objects after source-map collapse. It intentionally does not use
`uniqueItems`, because the contract's uniqueness relation is derived from
decoded public-key bytes rather than JSON structural equality.

## 6. Schema and procedural boundary

JSON Schema validation starts from an already parsed value. The schemas do not
replace, implement, or reorder these procedural requirements:

- immutable raw source bytes and exact filenames or explicit input roles;
- UTF-8 decoding, shortest-form validity, BOM handling, one-value consumption,
  and surrounding source whitespace;
- raw duplicate member names, decoded-name comparison, processing order,
  last-name-wins collapse, and v2 duplicate rejection;
- legacy constants, opaque surrogate handling, source number lexemes, and
  capability-qualified integer behavior;
- `AELITIUM-DISPATCH-JSON-1`, selected-parser restart at byte zero, and the
  prohibition on v2-to-v1 fallback;
- timestamp validation controlled by `validate_manifest_timestamp`;
- public reason and assurance-state precedence;
- Base64 decoding, unused pad-bit acceptance, and decoded key/signature length
  confirmation;
- cross-entry decoded `key_id` equality;
- the raw manifest signature message, signature-verification profile, strict
  point decoding, subgroup/scalar checks, and uncofactored Ed25519 equation;
- fingerprint derivation, derived-fingerprint uniqueness, and membership
  evaluation; and
- capability selection, input acquisition, snapshots, I/O, resources, limits,
  and every operational outcome.

The legacy evidence-input domain may be broader than the public outer-result
transport domain. In particular, accepting an opaque surrogate-bearing value
in an authorized legacy position does not authorize reproducing that value in
`aelitium-verifier-tool-result-v1`. Evidence-derived semantic detail is
projected at that public boundary: a nonempty exact string in the portable-v2
Unicode domain is preserved, and any other value is null. The established
semantic status, reason, and assurance states are unchanged.

The outer operation invocation boundary additionally requires each projected
verification flag to be an exact boolean, an optional
`freshness_max_age_seconds` to be an exact integer from 0 through
`9007199254740991`, and an optional `freshness_reference_time_utc` to be a
portable, calendar-valid exact `YYYY-MM-DDTHH:MM:SSZ` string. Violations are
request-validation failures before capability selection and input acquisition,
not Freshness semantic results. These restrictions do not narrow the
standalone legacy/inner Freshness primitive.

The schemas may report that a parsed value violates a structural constraint.
The verifier must still perform the ordered contract checks and emit only the
already-authorized AELITIUM result or operational outcome. Schema evaluation
order and validator-specific diagnostics have no public semantic authority.

## 7. Compatibility and remaining gaps

This contract preserves released v0.4.0 evidence formats and ordinary
canonical signatures under their existing identifiers. It preserves legacy
constants, decoded-name last-wins behavior, open manifest and `ed25519-v1`
objects, permitted opaque strings, capability-qualified integers, non-zero
Base64 pad-bit aliases, and trust-store closure only after source collapse. It
does not change canonical bytes, hashes, signature scope, membership, reasons,
assurance dimensions, comparison, or claim boundaries. Strict rejection of
backend-sensitive Ed25519 edge encodings applies only when
`ED25519_PORTABLE_STRICT_1` is explicitly requested and effective; it is not
a claim that every released backend rejected those inputs.

The exact v2 timestamp rule applies only to the unreleased portable-v2 route.
It does not rewrite v1 timestamp compatibility. The current unreleased
operation path implements the adopted no-follow immutable-snapshot and
trust-input acquisition boundary. Successfully acquired malformed trust bytes
remain semantic; inability to acquire those bytes remains operational. This
does not rewrite the released v0.4.0 interface or make Python normative.

Together with the four named input schemas and the expanded
[`verifier_contract_phase2`](../conformance/verifier_contract_phase2/manifest.json)
family, this contract closes G-04, G-05, and G-06 through
`PHASE2_NORMATIVE_INPUT_CONTRACTS_SCHEMAS_AND_CONFORMANCE` and the completed
unreleased runtime alignment. The frozen corpus manifest retains its
adoption-time G-05 status as historical metadata; it is not the live gap
registry. G-07, G-08, G-10, and G-11 remain open. G-12 remains deferred, and
the Go verifier remains `NOT_READY`.
