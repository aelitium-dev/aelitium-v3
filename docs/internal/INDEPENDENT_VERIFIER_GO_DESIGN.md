# Independent clean-room verifier for Go

**Workstream:** design and audit only

**Proposed future repository:** `aelitium-dev/aelitium-verifier-go`

**AELITIUM source snapshot audited:**
`c4bd7613d3dacbaf6200facd3343eb1f96f721ba`

**Implementation status:** no Go repository or verifier exists as a result of
this document

## 1. Executive decision

A genuinely independent Go verifier is feasible, but the complete current
verification and assurance surface cannot yet be implemented solely from the
declared normative material and frozen vectors.

The portable-v2 value profile itself is sufficiently precise to implement in
Go. The hash formulas, raw-manifest signature scope, eight assurance dimension
names, state vocabularies, claim boundaries, and high-level failure precedence
are also substantially specified. Go 1.27 provides a strong standard-library
JCS strategy, so no external JCS package is required.

The blocker is specification closure around the surrounding protocol. The
current source set labels the independent-verifier requirements `RESEARCH`,
labels most result contracts `IMPLEMENTATION-ALIGNED`, places the complete
dispatch grammar in an internal design rather than the declared authoritative
public set, and explicitly defers part of the invocation grammar to Python
implementation code. There are also no complete source grammars for
`ai_manifest.json`, `verification_keys.json`, or the trust store; no
language-neutral definition of several corpus operations; no public
operational resource-error contract; and no portable outcome for the v1
integer domain above 640 magnitude digits.

Accordingly:

- a Go engineer can implement `aelitium_jcs_profile_v2` independently;
- a Go engineer can implement the documented closed portion of
  `json_sorted_keys_no_whitespace_utf8`, including the frozen legacy
  non-finite cases, but cannot claim the complete v0.4.0 input domain;
- the eight-dimensional result shape can be emitted, but exact end-to-end
  state and reason reproduction is blocked for undocumented edge cases; and
- repository creation and implementation should begin only after the minimum
  specification corrections in section 21 are published.

This conclusion does not reinterpret released v1 behavior and does not propose
using Python as an oracle.

## 2. Independence threat model

The clean-room claim is threatened by more than a direct Python import.

| Threat | Consequence | Required control |
|---|---|---|
| Translating `engine/*.py`, comments, helpers, or tests | The Go verifier becomes a port, not an independent derivation | Implementers receive a versioned specification package containing only approved documents, schemas, vectors, and standards |
| Calling the Python CLI or package | Python remains the real decision engine | No Python process, package, container, FFI, generated binding, or network oracle in build, tests, or runtime |
| Sharing producer runtime modules | Common defects can produce false agreement | Separate repository and module graph; no AELITIUM producer library dependency |
| Deriving expected bytes with the candidate | Self-confirming canonicalization tests | Read frozen expected bytes and digests directly; never regenerate them during acceptance |
| Resolving ambiguity by observing Python | Undocumented behavior becomes accidental protocol | Stop, file a specification gap, and obtain a published decision before coding that branch |
| Parser collapse before validation | Duplicates, number lexemes, and selector order can be lost | Token/occurrence-preserving parsing and an iterative dispatch scanner |
| Version downgrade or retry | A selected v2 failure can be misinterpreted as v1 | Immutable original bytes, single dispatch decision, fresh selected-version parse, no v2-to-v1 retry |
| Ambient trust, time, locale, or network | Results cease to be deterministic or explicit | All trust and Freshness inputs are explicit; no network, current clock, locale collation, or environment discovery |
| Filesystem time-of-check/time-of-use | Signature and parsing may consume different manifest bytes | Snapshot each relevant file once and use the same immutable manifest bytes for dispatch, parse, and signature verification |
| Resource exhaustion mapped to a semantic reason | A valid value can appear invalid or route differently | Typed operational failure outside the AELITIUM result vocabulary; iterative traversal; published resource policy |
| Dependency drift | JCS or schema behavior changes without a protocol change | Pin the Go toolchain and modules, retain `go.sum`, record licenses/SBOM, and rerun all frozen vectors on upgrades |
| Overstated claims | Internal consistency is presented as real-world proof | Emit the exact claim-boundary profiles and repeat the non-claims in user documentation |

The implementer may study RFCs, the approved public protocol package, JSON
Schemas, frozen corpora, and dependency documentation. The implementer must not
inspect Python decision code. A separate audit team may later run black-box
differential tests, but a difference must be resolved through the specification
and frozen data, never by copying Python behavior into Go.

## 3. Normative source hierarchy

### 3.1 Required future hierarchy

The future verifier should pin one immutable AELITIUM protocol snapshot and use
this precedence:

1. a stable, public AELITIUM verifier specification and identifier registry;
2. external standards incorporated by exact reference and errata policy:
   RFC 8259, RFC 7493 where incorporated, RFC 8785, RFC 4648, RFC 8032,
   SHA-256, UTF-8, and JSON Schema Draft 7;
3. published AELITIUM schemas for payloads, manifests, signatures, trust input,
   invocation records, assurance, verification, and comparison;
4. frozen conformance manifests, source bytes, expected bytes, digests,
   decisions, reasons, states, and routes; and
5. non-normative explanatory documentation.

If two sources at the same or different levels conflict, the candidate must
stop and report a specification defect. A corpus example must not silently
override normative prose, and prose must not silently rewrite already-frozen
bytes. The Python implementation is outside the hierarchy.

The proposed Go repository should vendor the approved documents, schemas, and
corpora under `spec/aelitium/<contract-snapshot>/`, accompanied by a manifest
of source repository commit, path, byte length, and SHA-256 for every file. It
should not vendor any Python source or generated interpretation of it.

### 3.2 Current audited source set

The declared public inputs are:

- `docs/CANONICALIZATION_SPEC.md`;
- `docs/INDEPENDENT_VERIFIER_REQUIREMENTS.md`;
- `docs/CANONICAL_REQUEST.md`;
- `docs/INVOCATION_ASSURANCE.md`;
- `docs/TRUST_BOUNDARY.md`;
- `docs/VERIFICATION_RESULT_V1.md`;
- `docs/ASSURANCE_RESULT_V1.md`;
- `docs/CLAIM_BOUNDARIES_V1.md`;
- `docs/COMPARE_RESULT_V1.md`;
- the schemas in `engine/schemas/`; and
- the frozen `conformance/` data.

`docs/internal/CANONICALIZATION_V2_PORTABLE_DESIGN.md` contains the only full
normative spelling of `AELITIUM-DISPATCH-JSON-1`, but it is absent from the
authoritative-public-input list and itself calls for public promotion of its
normative sections. It may inform this audit, but it is not an acceptable
unstated dependency for the clean-room implementer. The quarantined
`docs/EVIDENCE_BUNDLE_SPEC.md` and the legacy generic verifier documents are
not normative inputs for this verifier.

The current status labels do not yet establish the conflict rule required
above. This is specification gap G-01.

## 4. Proposed repository architecture

The future repository should be a standalone Go module with no producer code:

```text
aelitium-verifier-go/
  cmd/aelitium-verifier/       CLI only
  internal/bundleio/           immutable local-file snapshots
  internal/dispatch/           AELITIUM-DISPATCH-JSON-1 scanner
  internal/jsonvalue/          occurrence- and token-preserving value model
  internal/canonical/v1/       documented v1 compatibility serializer
  internal/canonical/v2/       v2 profile and JCS adapter
  internal/schema/             embedded, pinned schema compilation
  internal/hashmaterial/       governed projections and SHA-256
  internal/manifest/           selected-version manifest validation
  internal/signature/          Ed25519 bundled-material verification
  internal/trust/              explicit trust-store parsing and membership
  internal/binding/            original binding checks
  internal/invocation/         identity and invocation-binding checks
  internal/freshness/          explicit declared-time recency
  internal/assurance/          eight state machines and invariants
  internal/result/             closed verification result construction
  internal/comparison/         deferred comparison phase
  conformance/                 Go harness and Go-only additional vectors
  spec/aelitium/<snapshot>/    approved docs, schemas, corpora, digest manifest
  LICENSES/                    dependency notices
  SECURITY.md
  go.mod
  go.sum
```

Dependency direction must be one-way: parsing and primitives know nothing
about CLI formatting; assurance consumes primitive evaluations; result
construction consumes assurance; comparison consumes two completed verifier
results. No package may import producer or adapter code.

All protocol byte inputs should be represented as immutable byte slices owned
by a per-operation snapshot. Parsed views must never replace the raw manifest
used for signature verification. Internal errors should be typed as syntax,
profile, semantic, or operational; only a centralized mapper may turn the
first three into authorized public reasons.

## 5. CLI contract

The initial public command should verify first:

```text
aelitium-verifier verify-bundle BUNDLE \
  [--contract-json] \
  [--validate-manifest-timestamp=true|false] \
  [--require-signature] \
  [--require-binding] \
  [--trust-store PATH] \
  [--require-trust-membership] \
  [--freshness-max-age-seconds DECIMAL] \
  [--freshness-reference-time-utc YYYY-MM-DDTHH:MM:SSZ]
```

The canonicalization identifier is never supplied as an override. It is
selected only from the original manifest bytes. There is no ambient trust
store, current time, network lookup, provider call, default Freshness policy,
or environment-selected compatibility behavior.

For a completed verification operation, `--contract-json` emits one
`aelitium-verification-result-v1` object as strict UTF-8, compact separators,
lexicographically sorted ASCII field names, and exactly one terminal LF.
`VALID` exits 0 and `INVALID` exits 2. `detail` is required but
non-normative; the Go verifier may use null consistently rather than imitate
Python exception text.

Usage errors, unsupported legacy domains, I/O failures that lack an authorized
verification mapping, allocation failure, and configured resource ceilings
must not be forged into an AELITIUM semantic result. A provisional CLI would
write a separate tool-operational diagnostic to stderr and use a non-0/non-2
exit. Exact operational codes and envelope are blocked on G-09 and must be
approved before implementation.

Compatibility capabilities should be explicit, not hidden:

| Capability | Meaning |
|---|---|
| `V2_PORTABLE` | Complete `aelitium_jcs_profile_v2` support |
| `V1_RESTRICTED_PORTABLE` | Only the restricted subset already defined by the v1 specification |
| `V1_FROZEN_LEGACY_COMPATIBILITY` | The documented closed v1 behavior, including exact non-finite tokens and ignored-manifest surrogate behavior, but not a universal decision above 640 integer digits |
| `V1_CPYTHON_DIGIT_PROFILE(n)` | An explicitly declared conformance/emulation profile for 640, 4300, or disabled limits; not a new AELITIUM semantic |
| `V1_LEGACY_UNSUPPORTED` | Tool-level refusal because the input lies outside the declared v1 capability; never reported as bundle invalidity |

The closed verification-result schema currently has no place to declare these
capabilities. They therefore cannot become production flags until G-02 defines
how the selected compatibility profile is made visible without changing v1
meaning.

`compare` is deliberately deferred as described in section 17. A conformance
subcommand may run frozen data, but it must not expose a general producer or
canonicalization service.

## 6. Bundle input contract

The verifier accepts a local directory containing exact case-sensitive names:

| File | Presence | Use |
|---|---|---|
| `ai_canonical.json` | required | Governed `ai_output_v1` payload |
| `ai_manifest.json` | required | Version selection, identifiers, digest, timestamp spelling, and optional original binding hash |
| `verification_keys.json` | optional | One bundled Ed25519 public key and one signature over raw manifest bytes |

The trust store and Freshness values are verifier inputs, not bundle evidence.
Extra bundle files have no documented verification meaning. Whether they are
ignored, rejected, or merely reported must be specified before implementation.

The intended read model is:

1. validate explicit trust and Freshness inputs in the normative order;
2. determine presence of the three known bundle paths;
3. read each present regular file once into an immutable operation snapshot;
4. run dispatch on the raw manifest snapshot;
5. parse the canonical payload under the selected route before observably
   parsing the manifest;
6. reuse the same raw manifest snapshot for selected-version parsing and
   Ed25519 verification; and
7. never reuse scanner-derived values in version verification.

The current contract does not define symlink handling, non-regular files,
short reads, permission failures, path replacement during verification, size
limits, or extra files. These are operational gaps, not permission to map such
conditions to `CANONICAL_NOT_JSON` or `MANIFEST_NOT_JSON`.

## 7. Canonicalization v1 strategy

### 7.1 Portable extent

The complete identifier `json_sorted_keys_no_whitespace_utf8` is not portable
as one universal accept/reject relation. Integer magnitudes above 640 decimal
digits inherit a configurable CPython conversion guard. The same bytes can be
accepted at one configured limit and rejected at another. A Go verifier must
not choose one of those outcomes and call it the universal v1 contract.

The following behavior is nevertheless independently implementable from the
written rules and frozen bytes:

- strict UTF-8 and no BOM;
- standard JSON plus exact `NaN`, `Infinity`, and `-Infinity` tokens;
- last-name-wins parsing;
- acceptance of escaped unpaired surrogates in unused manifest extensions;
- rejection of governed payload surrogates as `CANONICAL_NOT_JSON`;
- Unicode scalar-value key ordering, with no normalization;
- the exact string escape table;
- exact integers through 640 magnitude digits using `math/big.Int`;
- direct decimal-to-binary64 conversion, including signed underflow;
- the specified shortest-round-trip digit choice and Python notation rules;
- exact non-finite spellings and v1 negative-zero behavior; and
- storage `C` or `C || LF`, hashing only `C`.

This covers all 30 frozen v1 vectors. Three accepted vectors are deliberately
outside the restricted portable subset but have closed, reproducible legacy
spellings. It does not close the unbounded integer domain.

### 7.2 Independent implementation design

Do not use `encoding/json` as the v1 parser or serializer. It does not provide
the required duplicate, surrogate, non-finite, scalar-order, or float-format
contract. Implement an iterative lexer/parser directly from the public v1
grammar, retaining number token class (`integer` versus fraction/exponent),
member order, and surrogate code units where legacy manifest behavior needs
them. Collapse duplicates only when entering the v1 value model, taking the
last occurrence.

Serialize objects by Unicode scalar-value order; arrays retain order. Render
integers exactly. Render finite binary64 values from the specification's
shortest-digit selection and its `-4 <= e < 16` notation boundary, exponent
padding, and `.0` rule. This small v1-specific renderer requires independent
review because no standard Go JSON serializer promises those Python-aligned
bytes. It must be derived from the prose algorithm and frozen vectors, not
from Python source.

Preflight integer magnitude lexically. At or below the declared capability,
parse with `math/big.Int`. Above it, return a tool-level legacy-domain refusal
unless an explicitly selected CPython digit profile defines the outcome. Such
a refusal is not `CANONICAL_NOT_JSON`, `MANIFEST_NOT_JSON`, or any other public
bundle judgment.

## 8. Canonicalization v2 strategy

The `aelitium_jcs_profile_v2` contract is implementable independently:

1. require bytes, strict UTF-8, no leading BOM, and exactly one RFC 8259 value;
2. retain object occurrences and number lexemes until profile checks finish;
3. reject decoded duplicate names at every depth;
4. reject surrogates, U+FDD0 through U+FDEF, and U+nFFFE/U+nFFFF for planes
   0 through 16, without normalization;
5. classify booleans separately from numbers;
6. for an integer-form token, compare its mathematical decimal magnitude with
   `9007199254740991` before conversion;
7. convert other number tokens directly to binary64, round-to-nearest
   ties-to-even, reject infinity and magnitude above the same bound, and retain
   permitted signed underflow/zero semantics;
8. serialize the validated value exactly as RFC 8785 JCS;
9. require canonical output `C` to be strict UTF-8 with no BOM or LF; and
10. accept stored payload bytes only as `C` or `C || LF`, hashing `C`.

The recommended JCS engine is Go 1.27's standard
`encoding/json/jsontext.Value.Canonicalize`, not ordinary `encoding/json` and
not a new AELITIUM serializer. Go 1.27 made `encoding/json/jsontext` a standard
package; its documented validation rejects invalid UTF-8, invalid decoded code
points, and duplicate names, and its canonicalizer applies JCS number
formatting and UTF-16 member ordering. The AELITIUM parser must still enforce
the narrower number and noncharacter profile before calling it.

Use an iterative, occurrence-preserving AELITIUM parser as the primary
validator. Pass either the original validated value bytes or a deterministic
raw encoding of constructed hash material to `jsontext.Value.Canonicalize`.
Then assert the output envelope and a fixed point. Pin the Go toolchain and
make every applicable RFC 8785 and AELITIUM vector a dependency-upgrade gate.

The standard canonicalizer has a finite nesting ceiling. A preceding iterative
depth scan must classify reaching that ceiling as operational, not semantic.
G-09 must define the supported limit and external behavior before the package
is used in production.

## 9. `AELITIUM-DISPATCH-JSON-1` implementation design

Implement a byte-indexed, iterative state machine with explicit object and
array frames. Its grammar is the exact published union of RFC 8259 JSON values
and the three case-sensitive legacy constants. It must:

- consume one complete value plus only JSON whitespace;
- validate JSON string lexical rules and strict raw UTF-8;
- accept every syntactically valid `\uXXXX` escape during dispatch, including
  unmatched surrogates and noncharacters;
- combine an adjacent escaped high/low surrogate pair only for selector
  comparison;
- consume an RFC 8259 number of any digit length without conversion;
- retain source ordering and nesting sufficiently to identify root members;
- compare root member names after legacy escape processing to exact ASCII
  `canonicalization`;
- remember only the final such root occurrence;
- accept escaped spellings of the selector name and registered string value;
- ignore nested occurrences for selection;
- perform no normalization, duplicate rejection, numeric narrowing, schema
  validation, or v2 profile validation; and
- validate the complete structure even after observing a possible selector.

On a complete scan with final exact v2, discard scanner views and reparse the
same original bytes from byte zero under v2. Never retry v1. On every other
semantic scan outcome, including exact v1, missing/non-string/unknown selector,
non-object root, or malformed scan, discard scanner views and enter the
complete v1/legacy-error-resolution path using the same bytes. That path still
performs canonical payload parsing before observable manifest parsing and
preserves the legacy required-field and identifier precedence.

Scanner syntax failure and scanner resource failure must be different Go error
types. Only syntax failure enters legacy error resolution. Allocation failure,
configured byte/depth/member ceilings, and other operational exhaustion must
abort without selecting v1 or manufacturing a public reason. No traversal may
depend on goroutine stack growth.

Conformance instrumentation should record the selected route and SHA-256 of
the exact bytes handed to the selected parser. It must equal the frozen source
digest.

## 10. Hash constructions

Let `C_id(x)` be canonical bytes for the identifier selected by the enclosing
manifest. Hash lowercase hexadecimal SHA-256 over exactly these bytes:

```text
ai_hash_sha256 = SHA256(C_id(ai_output_v1))

request_hash = SHA256(C_id(request_payload))

response_hash = SHA256(C_id(response_payload))

binding_hash = SHA256(C_id({
  "request_hash": request_hash,
  "response_hash": response_hash
}))

invocation_identity.hash_sha256 = SHA256(C_id({
  "format": "aelitium-invocation-v1",
  "surface": surface,
  "mode": mode,
  "request": normalized_request
}))

invocation_binding.hash_sha256 = SHA256(C_id({
  "format": "aelitium-invocation-binding-v1",
  "invocation_hash": invocation_hash,
  "response_hash": response_hash
}))
```

There is no identifier prefix, newline, BOM, NUL, length field, manifest byte,
or domain-separation prefix in these inputs. A v2 bundle uses v2 for every
construction above; it never mixes v1 and v2.

The verifier can independently recompute `ai_hash_sha256`, the original
`binding_hash`, invocation identity hash, and invocation-binding hash from
stored values. It cannot reconstruct `request_hash` or `response_hash` from
provider traffic because that traffic and the producer's selected request and
response projections are not in the verifier input. Those two hashes are
well-formed stored inputs to binding checks, not independently established
provider-event digests.

Only canonical `C` is hashed even when stored `ai_canonical.json` has its one
allowed LF. The manifest itself is never JCS-canonicalized for the signature.

## 11. Manifest verification

After dispatch and canonical-payload parsing, parse the immutable manifest
snapshot from byte zero under the selected rules.

For v1, preserve strict UTF-8, legacy JSON tokens, last-name-wins behavior,
ignored-extension surrogate behavior, and the selected CPython-compatible
integer capability. For v2, require strict RFC 8259 and the complete v2
profile recursively, including unknown extensions; reject duplicates before
map collapse.

The root must be an object. Check required fields in this exact order:

1. `schema`;
2. `ts_utc`;
3. `input_schema`;
4. `canonicalization`; and
5. `ai_hash_sha256`.

Then check exact `schema = ai_pack_manifest_v1`, exact
`input_schema = ai_output_v1`, and exact selected canonicalization identifier.
If enabled, apply the exact manifest timestamp spelling rule. Validate
`ai_hash_sha256` as 64 lowercase hexadecimal characters. Unknown valid fields
are must-ignore and acquire no verification, assurance, authorization, or
comparison meaning. `binding_hash`, when present, participates only in the
documented original binding check.

The manifest is not required to have canonical member order or whitespace.
Signature scope is always the exact raw snapshot, including whitespace,
unknown fields, member order, line endings, and terminal bytes.

A public manifest schema and exact timestamp language are missing. In
particular, disabling timestamp validation is not specified as to whether it
also waives the field's string type. This blocks exact independent behavior on
edge cases.

## 12. Signature verification

`verification_keys.json` is optional. If absent, `signature_validity=ABSENT`.
If present after payload integrity succeeds, the intended contract is:

- `keyring_format` is exactly `ed25519-v1`;
- `keys` is an array containing exactly one object;
- `signatures` is an array containing exactly one object;
- both entries carry the same non-empty string `key_id`;
- the key is strict standard Base64 encoding of exactly 32 raw bytes;
- `algorithm` is exactly `ed25519` (pure Ed25519, not Ed25519ph or Ed25519ctx);
- `scope` is exactly `manifest.json`;
- `sig_b64` is strict standard Base64 encoding of exactly 64 bytes; and
- `crypto/ed25519.Verify(publicKey, rawManifestBytes, signature)` succeeds.

Every parse, structure, encoding, length, identifier, scope, algorithm, or
cryptographic failure collapses to public `SIGNATURE_INVALID`. If material is
absent and either signature is required or the trust-membership requirement
is enabled, the public reason is
`SIGNATURE_REQUIRED` after payload integrity succeeds.

The bundled public key establishes mathematical validity only. The keyring is
not a trust anchor, is not itself signed by this mechanism, and establishes no
signer identity, authorization, provider identity, execution, causation, or
historical occurrence.

The documents do not define whether keyring objects are closed, how duplicate
JSON member names behave, which source JSON profile applies, or the exact
canonical/padding interpretation of “strict standard Base64.” A schema and
source profile are required before Go can match all accepted and rejected
inputs without consulting Python.

## 13. Trust-store handling

Trust is an explicit verification input. There is no default path, environment
variable, network fetch, key server, certificate chain, revocation, expiry,
delegation, or ambient signer policy.

The intended `aelitium-trust-v1` document is a closed object with exactly:

- `trust_store_format`, equal to `aelitium-trust-v1`; and
- `signers`, an array of signer objects.

Each signer permits exactly `algorithm`, `public_key_b64`, and optional
non-empty string `label`. `algorithm` is `ed25519`; the decoded key is exactly
32 bytes. Derive, never ingest, the identity:

```text
fingerprint = "ed25519:sha256:" || lowercase_hex(SHA256(raw_public_key))
```

Labels are non-authoritative. Duplicate derived fingerprints invalidate the
store. Membership is evaluated only for a mathematically valid bundled
signature. With no trust store, with an unsigned/invalid signature, or with an
unknown signing key, `trusted_signer_identity=UNESTABLISHED`. A valid signature
whose fingerprint appears in the explicit store yields `VALID`. Unknown
membership invalidates the bundle only when `trusted_signer_identity` was
required, using `TRUSTED_SIGNER_NOT_FOUND`.

Input precedence is: requiring trust without a store gives
`TRUST_INPUT_NOT_PROVIDED`; an unreadable, unparsable, or invalid supplied
store gives `TRUST_STORE_INVALID`; both precede bundle inspection. Lower-level
store diagnostics belong only in non-normative detail.

The source parsing rules for this “strict” store are not complete: duplicate
member handling, BOM, surrogate/noncharacter handling, non-finite tokens,
empty signer-list validity, and exact Base64 canonicality are not all fixed by
a schema or normative grammar. These choices must be published rather than
inferred.

## 14. Eight-dimensional assurance mapping

No ninth dimension, aggregate score, or policy conclusion is permitted.

| Order and dimension | Inputs and evaluation | Reachable states and absence/failure | Exact references | Claim boundaries |
|---|---|---|---|---|
| 1 `payload_integrity` | Required payload/manifest snapshots; selected parser; `ai_output_v1` schema; canonical storage; manifest identifiers and digest | `ABSENT` if a required artifact is absent; `INVALID` for an evaluated payload/manifest/canonical/hash failure; `VALID` after digest match; `NOT_EVALUATED` only before artifact inspection | evidence: `bundle:ai_canonical.json`, `bundle:ai_manifest.json`; no trust/policy refs | historical occurrence, historical non-modification, semantic truth, capture completeness not established |
| 2 `binding_field_consistency` | Manifest `binding_hash` and canonical metadata `request_hash`, `response_hash`, `binding_hash`; recomputed selected-version binding | all four absent -> `ABSENT`; partial/malformed/mismatch -> `INVALID`; complete match -> `VALID`; early payload failure -> `NOT_EVALUATED` | evidence: the four JSON locations; no trust/policy refs | response causation, provider execution, historical occurrence not established |
| 3 `invocation_identity_consistency` | `metadata.invocation_identity`, its exact grammar, normalized request, selected-version recomputation | member absent -> `ABSENT`; malformed or digest mismatch -> `INVALID`; exact valid object/match -> `VALID`; early payload failure -> `NOT_EVALUATED` | evidence: `bundle:ai_canonical.json#/metadata/invocation_identity`; no trust/policy refs | provider execution, complete invocation identity, response causation, historical occurrence not established |
| 4 `invocation_binding_consistency` | `metadata.invocation_binding`; own recomputation; valid identity; bundle response hash; cross-field linkage | absent -> `ABSENT`; malformed, mismatch, missing/invalid dependency, or cross-field mismatch -> `INVALID`; full linkage -> `VALID`; early payload failure -> `NOT_EVALUATED` | evidence: invocation binding, identity hash, response hash locations; no trust/policy refs | response causation, provider execution, historical occurrence not established |
| 5 `signature_validity` | Optional keyring and exact raw manifest snapshot | absent keyring -> `ABSENT`; present failed material/math -> `INVALID`; verified -> `VALID`; present but payload not established -> `NOT_EVALUATED` | evidence: `bundle:ai_manifest.json`, `bundle:verification_keys.json`; no trust/policy refs | signature validity does not establish `trusted_signer_identity`, authorization, or historical occurrence |
| 6 `trusted_signer_identity` | Valid signature key fingerprint and optional explicit trust store | exact membership -> `VALID`; every other condition -> `UNESTABLISHED`; never `ABSENT`, `INVALID`, or `NOT_EVALUATED` | evidence: `bundle:verification_keys.json`; trust ref only when supplied: `verification-input:trust-store`; no policy ref | authorization, provider execution, historical occurrence, trusted historical time not established |
| 7 `freshness` | Canonical payload `ts_utc` plus complete explicit maximum-age/reference-time pair | no policy -> `NOT_EVALUATED`; incomplete/invalid policy -> `UNESTABLISHED`; evaluated malformed/stale/future timestamp -> `INVALID`; inclusive window -> `VALID` | evidence: `bundle:ai_canonical.json#/ts_utc`; policy ref when either input supplied: `verification-input:freshness-policy`; no trust refs | trusted historical time, historical occurrence, historical non-modification, provider execution, response causation not established |
| 8 `authorization` | no evaluator and no input | always `NOT_EVALUATED` | no evidence, trust, or policy refs | authorization not established |

The exact stable bases are, in order:

1. `ai_output_v1_canonical_manifest_digest_consistency`;
2. `stored_request_response_binding_field_consistency`;
3. `aelitium-invocation-v1_recomputation`;
4. `aelitium-invocation-binding-v1_recomputation_and_bundle_linkage`;
5. `ed25519_manifest_signature_verification`;
6. `verified_ed25519_key_fingerprint_membership_in_explicit_aelitium-trust-v1`;
7. `declared_canonical_timestamp_recency_under_explicit_policy`; and
8. `not_implemented_in_v0.4-compatible_semantics`.

After payload integrity is valid, signature/trust, original binding,
invocation identity, invocation binding, and selected Freshness are all
evaluated so their states survive even when an earlier top-level reason wins.
Cross-dimension invariants include: `trusted_signer_identity=VALID` requires
`signature_validity=VALID` and an explicit trust input; invocation binding `VALID` requires
identity `VALID`; downstream checks cannot be evaluated before payload
integrity; and successful invocation pairs are only `ABSENT/ABSENT`,
`VALID/ABSENT`, or `VALID/VALID`.

The schemas fix many constants, but the current corpus does not enumerate the
complete early-failure state matrix. That missing matrix is part of G-07.

## 15. Claim-boundary mapping

Every verification outcome carries contract
`aelitium-claim-boundary-v1` and this exact operation-wide order:

1. `provider_execution_not_established`;
2. `response_causation_not_established`;
3. `semantic_truth_not_established`;
4. `capture_completeness_not_established`;
5. `historical_occurrence_not_established`;
6. `historical_non_modification_not_established`;
7. `authorization_not_established`;
8. `trusted_historical_time_not_established`;
9. `legal_compliance_not_established`; and
10. `complete_invocation_identity_not_established`.

The dimension-specific subsets are those in section 14. A non-claim means the
basis did not establish the proposition. It never asserts the proposition's
opposite. In particular, signature validity does not establish
`trusted_signer_identity`;
freshness is not trusted time; invocation consistency is not execution;
binding is not causation; and payload integrity is not historical
non-modification without an independently trusted anchor.

If comparison is later added, it carries, in order: model drift, regression,
quality degradation, semantic equivalence, response causation, provider fault,
provider execution, and complete invocation identity not established.

## 16. Failure precedence

The Go verifier must implement one centralized decision table. The documented
order is:

1. `TRUST_INPUT_NOT_PROVIDED`;
2. `TRUST_STORE_INVALID`;
3. invalid/incomplete Freshness policy -> `FRESHNESS_POLICY_INVALID`;
4. `MISSING_CANONICAL`;
5. `MISSING_MANIFEST`;
6. non-observable dispatch lookahead (only exact v2 branches; syntax failure
   enters legacy error resolution; operational failure does not);
7. canonical source parse/profile failure -> `CANONICAL_NOT_JSON`;
8. manifest source parse/profile failure -> `MANIFEST_NOT_JSON`;
9. non-object manifest -> `MANIFEST_NOT_OBJECT`;
10. missing manifest field, in the field order in section 11 ->
    `MANIFEST_MISSING_FIELD`;
11. `MANIFEST_BAD_SCHEMA`;
12. `MANIFEST_BAD_INPUT_SCHEMA`;
13. `MANIFEST_BAD_CANONICALIZATION`;
14. selected manifest timestamp spelling failure -> `MANIFEST_BAD_TS_UTC`;
15. malformed manifest payload digest -> `MANIFEST_BAD_AI_HASH_SHA256`;
16. payload schema failure -> `CANONICAL_SCHEMA_INVALID`;
17. v1 governed Unicode serialization failure -> `CANONICAL_NOT_JSON`;
18. stored byte-envelope failure -> `CANONICAL_BYTES_MISMATCH`;
19. payload digest mismatch -> `HASH_MISMATCH`;
20. evaluate every downstream dimension; then select the first applicable
    top-level reason in this order:
    `SIGNATURE_INVALID`, `SIGNATURE_REQUIRED`, original binding failure
    (`BINDING_FIELDS_INCOMPLETE`, `BINDING_FIELD_MALFORMED`, or
    `BINDING_HASH_MISMATCH`), `BINDING_REQUIRED`, required trust membership
    failure `TRUSTED_SIGNER_NOT_FOUND`, invocation-identity reason,
    invocation-binding reason, Freshness reason
    (`FRESHNESS_TIMESTAMP_MALFORMED`,
    `FRESHNESS_TIMESTAMP_IN_FUTURE`, `FRESHNESS_STALE`), then `OK`.

V2 payload profile failures map to `CANONICAL_NOT_JSON`; v2 manifest profile
failures map to `MANIFEST_NOT_JSON`; a valid v2 value with alternate storage
bytes maps to `CANONICAL_BYTES_MISMATCH`. Unknown/missing/malformed selectors
must retain legacy field-check precedence. No public reason may be invented for
an unsupported v1 domain or a host resource limit.

An exhaustive ordered registry for all invocation subreasons and all
early-failure assurance states still needs publication.

## 17. Comparison scope

The first independently reviewable release candidate should verify only.
Comparison should be a second phase after two verifier results are stable and
the remaining comparison-output gaps are closed. The initial candidate must
not claim 44/44 corpus completion while the 12 comparison cases are deferred.

When implemented, comparison must verify both bundles with default options
before inspecting a basis. Invalid verification or an impossible input state
returns `INVALID_BUNDLE`, basis `NONE`, and no response relationship.

For two valid bundles, a canonicalization identifier mismatch is checked
before all current bases and returns:

```text
status = NOT_COMPARABLE
comparison_basis = NONE
comparison_reason = CANONICALIZATION_IDENTIFIER_MISMATCH
response_relationship = null
```

Otherwise:

- `INVOCATION_FIRST` uses `INVOCATION_IDENTITY_V1` only when both identity and
  invocation-binding dimensions are `VALID` on both sides, and otherwise uses
  `REQUEST_HASH_V1_FALLBACK`;
- `STRICT_INVOCATION` uses invocation identity when available on both sides,
  otherwise `NONE` with required basis `INVOCATION_IDENTITY_V1` and reason
  `INVOCATION_EVIDENCE_UNAVAILABLE`; and
- `LEGACY_REQUEST_HASH_V1` uses `REQUEST_HASH_V1_LEGACY`.

Different selected identity hashes produce `NOT_COMPARABLE`; matching identity
and response hashes produce `UNCHANGED`; matching identity with different
response hashes produces `CHANGED`. Current statuses, bases, reasons,
exit-code equivalents, side verification summaries, and comparison claim
boundaries must be preserved. No result infers drift, regression, causality,
semantic equivalence, provider fault, or quality.

The schema permits compatibility fields whose exact presence and text are not
fully constructed in normative prose, and the selected timestamp diagnostic's
source/fallback is not specified. The phase must remain deferred until G-10 is
closed or the acceptance target is explicitly defined as semantic/schema
equivalence rather than byte-identical Python output.

## 18. Conformance strategy

### 18.1 Existing frozen corpora

The Go repository must consume unchanged copies and verify their source-file
digests before execution.

| Corpus | Composition | Go expectation |
|---|---|---|
| Result contract, 44 cases | 32 verification/assurance/trust/Freshness/invocation/compatibility operations and 12 comparisons | Phase 1 must pass the 32 verifier operations; the complete candidate must pass 44/44 after comparison. All referenced fixtures are within behavior that can be reproduced after the specification gaps are closed. |
| V1 canonicalization, 30 cases | 15 `CROSS_LANGUAGE_SAFE`, 3 accepted `LEGACY_PRESERVED_OUTSIDE_SUBSET`, 12 rejected | All 30 exact decisions/bytes/digests can be reproduced. Passing them does not claim universal behavior for integers above 640 digits. |
| Portable v2, 114 cases | 59 canonicalize, 5 hash material, 10 storage verify, 38 dispatch verify, 1 comparison, 1 v1 artifact | 110 have language-independent expectations. Four v1-route cases depend on an explicitly declared CPython digit-limit profile and are compatibility-emulation cases, not portable v1 decisions. The final candidate still exercises all 114 with that declaration. |

The four profile-dependent v2-corpus cases are:

- `v2.dispatch.integer_641_at_640`;
- `v2.dispatch.integer_4300_at_4300`;
- `v2.dispatch.integer_4301_at_4300`; and
- `v2.dispatch.integer_10000_disabled`.

The v2 case with a 10,000-digit integer and final v2 selector is portable: it
must route to v2 and fail the v2 number profile without numeric narrowing or a
v1 retry. The 640-digit v1 acceptance is inside the declared restricted bound.

The Go harness must not execute `conformance/run*.py`. It must interpret a
published language-neutral corpus-operation contract, read source hex and
expected bytes directly, construct only inputs whose exact recipes are
normatively frozen, and compare route, reason, states, bytes, digest, and
result fields. Existing vectors are never edited to make Go pass.

### 18.2 Additional verifier-specific vectors

Keep additional cases in a separately named Go-verifier corpus. They must not
renumber or change the 44, 30, or 114 cases. Additional vectors are required
for gaps not covered exhaustively today:

- complete expected verification-result objects, including all eight entries,
  references, bases, boundaries, and early-failure states;
- every invocation identity and invocation-binding grammar reason and
  precedence combination;
- keyring and trust-store duplicate names, unknown fields, malformed types,
  Base64 variants, lengths, empty lists, and mixed failures;
- manifest field types, timestamp lexical/calendar boundaries, validation
  disabled, and valid/invalid unknown extensions under both identifiers;
- signed/trusted v2 bundles with v2 original binding, invocation identity, and
  invocation binding recomputation;
- simultaneous signature, binding, invocation, and Freshness failures to prove
  top-level precedence while retaining all evaluated states;
- filesystem snapshot and operational resource behavior;
- no ambient clock, trust, network, locale, or environment input;
- deep iterative scanning/parsing on supported limits and explicit operational
  refusal outside them; and
- byte-stable result serialization and dependency-upgrade differentials.

## 19. External dependencies and licenses

The recommended initial dependency set is deliberately small.

| Component | Candidate | License | Assessment |
|---|---|---|---|
| Language/toolchain and JCS | Go 1.27.x standard library, especially `encoding/json/jsontext`, `crypto/ed25519`, `crypto/sha256`, `encoding/base64`, `math/big`, and `unicode/utf8` | BSD-3-Clause | Preferred. Go 1.27 promoted `jsontext`; its JCS path has UTF-16 ordering and binary64 formatting. Pin an exact toolchain patch and require RFC/AELITIUM vectors on every upgrade. |
| JSON Schema | `github.com/santhosh-tekuri/jsonschema/v6` at candidate pin `v6.0.3` | Apache-2.0 | Supports Draft 7 and precision-preserving `json.Number` input. It is mature and actively maintained. Compile only embedded local schemas; disable network loaders. Audit its behavior against AELITIUM schema fixtures. |
| Schema transitive dependency | `golang.org/x/text` at the version selected by the pinned schema module (currently `v0.14.0` in that module's `go.mod`) | BSD-3-Clause | Record in SBOM and `go.sum`; no runtime network access. Review on module upgrades. |

No external JCS dependency is recommended. The RFC-linked
`github.com/cyberphone/json-canonicalization` Go implementation and the
Apache-2.0 `github.com/gowebpki/jcs` fork were evaluated as fallbacks, but a
standard Go 1.27 package has lower supply-chain and maintenance risk. Ordinary
`encoding/json`, `json.Marshal`, map-key sorting, or `strconv.FormatFloat`
alone are not an RFC 8785 strategy.

Before adoption, freeze a dependency review recording tag/commit, license,
supported Go version, transitive modules, vulnerability scan, upstream RFC
tests, AELITIUM tests, and reproducible-build checks. A dependency's JCS claim
does not substitute for passing the 114-case corpus.

Dependency-review sources for this design are the [Go 1.27 release
notes](https://go.dev/doc/go1.27), the official [`jsontext` package
documentation](https://pkg.go.dev/encoding/json/jsontext@go1.27.0), [RFC
8785](https://www.rfc-editor.org/rfc/rfc8785.html), and the upstream
[`jsonschema/v6` v6.0.3 release](https://github.com/santhosh-tekuri/jsonschema/releases/tag/v6.0.3)
and [package documentation](https://pkg.go.dev/github.com/santhosh-tekuri/jsonschema/v6@v6.0.3).
License review must use the exact source tags selected for the build, not these
links as a substitute for vendored license files.

## 20. Cross-language portability risks

| Risk | Go-specific control |
|---|---|
| `encoding/json` historically accepts duplicate names and invalid UTF-8 | Do not use it as the protocol parser; use the occurrence-preserving parser and vetted `jsontext` operations |
| Go maps discard occurrence order | Detect duplicates and final selectors before any map construction |
| Go strings cannot faithfully represent a legacy unmatched surrogate as a Unicode scalar | Retain legacy escape/code-unit form in the v1 manifest parser; never emit it as UTF-8 canonical payload data |
| Go lexical/string ordering is not automatically JCS UTF-16 order | Delegate v2 serialization to JCS and test BMP/non-BMP inversions; use scalar order only for v1 |
| `int` width varies and `float64` loses large integers | Keep number lexemes; use `math/big.Int` for v1; perform v2 mathematical integer checks before float conversion |
| `strconv` formatting is not the v1 Python notation contract | Implement the documented v1 digit/notation algorithm separately |
| Underflow, overflow, negative zero, and tie rounding differ across parsers | Freeze binary64 bit patterns and output bytes; parse directly to float64 and inspect sign/finite status |
| Go's time package admits years/normalizations that may differ from Python | Use a contract-specific calendar parser after the timestamp grammar is published |
| Regex `\d` and end anchors vary across engines | Publish ASCII/code-point classes and exact whole-string rules; do not port regex text blindly |
| Base64 decoders differ on whitespace, padding, and non-zero pad bits | Publish exact RFC 4648 acceptance and require re-encode equality if canonical encoding is intended |
| JSON Schema libraries represent `integer` and number equality differently | Pin Draft 7 and library version; preserve numeric tokens and run schema differential vectors |
| Standard JCS implementations impose depth limits | Preclassify the ceiling as operational; never return a JSON/profile reason for it |
| Result serialization through maps may drift | Use a closed result model, deterministic field encoding, sorted keys, strict UTF-8, and one LF |
| Filesystem semantics differ across platforms | Define regular-file/symlink/snapshot rules and test Linux, macOS, and Windows where supported |

## 21. Specification gaps

These gaps prevent an implementer from choosing exact behavior without an
unstated oracle.

| ID | Gap and impact | Smallest correction required |
|---|---|---|
| G-01 | Normative authority is unsettled: core documents are `RESEARCH` or `IMPLEMENTATION-ALIGNED`, some call Python authoritative, and there is no conflict rule. | Publish a stable verifier-contract snapshot and identifier registry; declare the hierarchy in section 3 and remove implementation-as-authority language. |
| G-02 | Complete v1 has no portable decision above 640 integer digits, and the public result cannot declare a compatibility profile or an out-of-domain refusal. | Standardize an explicit verifier capability/legacy digit profile and a non-semantic operational refusal, or introduce a separately versioned portable-v1 rule. Do not redefine the released identifier. |
| G-03 | The full dispatch grammar and algorithm live in an internal design absent from the authoritative public list. | Promote the complete `AELITIUM-DISPATCH-JSON-1` grammar, escape comparison, routing, byte handoff, and resource distinction into a stable public normative specification. |
| G-04 | There is no `ai_manifest.json` schema/source grammar. Exact types, unknown-field policy boundaries, timestamp-disabled behavior, and timestamp character/anchor rules are incomplete. | Publish a manifest schema plus ordered procedural checks for each identifier, including exact timestamp code points and validation-disabled behavior. |
| G-05 | `verification_keys.json` has no schema or full JSON/Base64 acceptance grammar. Unknown/duplicate fields and lexical edge cases are undecided. | Publish a closed or explicitly open keyring schema, selected JSON source profile, duplicate rule, exact RFC 4648 encoding rule, and exhaustive malformed-material vectors. |
| G-06 | The trust store is described as strict but lacks a source grammar/schema for duplicates, Unicode, BOM, non-finites, empty signers, and exact Base64. | Publish `aelitium-trust-v1` JSON Schema plus lexical/profile rules and vectors. |
| G-07 | `INVOCATION_ASSURANCE.md` explicitly says it does not expand the grammar beyond what is implemented in `engine/invocation.py`. Parameter value domains and the complete ordered identity/binding reason mapping are not independently normative. | Publish schemas and an ordered validation/reason table for both invocation objects, including recursive value rules, empty-parameter normalization, and cross-field precedence. |
| G-08 | The result reason field is open and no single exhaustive public reason registry maps every validation branch and early failure to all eight states. | Publish a closed reason registry and a complete reason/state transition table; retain `detail` as non-normative. |
| G-09 | Resource exhaustion and filesystem/I/O failures must not become semantic invalidity, but no operational envelope, exit code, supported size/depth, symlink, or snapshot contract exists. | Publish operational error semantics outside the verification-result vocabulary and minimum supported limits; define regular-file and immutable-snapshot rules. |
| G-10 | Corpus operation semantics are not self-contained. Python runners synthesize base canonical payloads/manifests, set CPython limits, and select fields not completely frozen in the vector format. The 44 cases check only selected result fields. | Publish a language-neutral corpus format/harness contract and freeze every synthesized byte input and full expected stable output. Annotate the four CPython-profile cases without changing them. |
| G-11 | Freshness says “calendar-valid” but does not fix year zero, Gregorian convention, leap seconds, maximum-age numeric range, or cross-language parser behavior. | Publish an exact timestamp ABNF/calendar domain and numeric input domain, with boundary vectors including year 0000/0001/9999 and second 60. |
| G-12 | Comparison prose does not fully fix presence/text of compatibility fields or timestamp diagnostic fallback; exact-output versus semantic-output parity is unclear. | Before comparison work, publish a complete construction table or explicitly scope conformance to schema/stable semantic fields and freeze full expected objects. |
| G-13 | RFC incorporation does not state an errata snapshot or protect the v2 identifier from later ECMAScript output changes. | Pin RFC 8259/7493/8785 references and reviewed errata; state that the identifier follows the incorporated RFC 8785 algorithm, not future silent language changes. |

### IMPLEMENTATION CROSS-CHECK

This subsection is non-normative. Python was inspected only after the contract
above had been derived, solely to test whether the gaps are observable. The
findings are evidence that decisions are missing; they are not instructions to
copy Python behavior.

- The invocation implementation contains validation order and recursive value
  acceptance that the invocation document explicitly withholds.
- Manifest timestamp checking uses host-regex behaviors that accept Unicode
  decimal digits and a final newline inside the string; the prose appears to
  imply a stricter ASCII whole-string spelling.
- Bundled keyring parsing accepts unknown members and inherits last-name-wins
  JSON parsing, while the public requirements do not say whether either is
  allowed. Trust-store validation is closed only after the same map collapse.
- Base64 behavior is inherited from a particular library call rather than an
  exact published canonical encoding rule.
- Several file read/type failures collapse into payload, manifest, signature,
  or trust reasons according to where a host exception occurs; those mappings
  are not specified.
- The v1 and v2 corpus runners construct companion manifest/payload bytes in
  Python rather than reading all of them from frozen vector data.
- Comparison constructs some compatibility diagnostics and timestamp fallback
  behavior not fully described by the comparison contract.

The clean-room team must not reproduce any item in this list until AELITIUM
chooses and publishes the intended rule.

## 22. Clean-room development rules

1. Do not create the Go repository until G-01, G-03, G-07, G-08, G-09, and
   G-10 are closed and the remaining gaps are either closed or explicitly
   excluded from the first milestone.
2. Publish a spec-only archive/digest manifest. The implementation team uses
   that archive, not a checkout containing `engine/`.
3. Record every implementer's allowed-source attestation and every dependency's
   provenance and license.
4. Do not view, copy, translate, generate from, import, invoke, or vendor
   AELITIUM Python verification/canonicalization code.
5. Do not use Python corpus runners; write a Go harness against frozen data and
   the language-neutral corpus contract.
6. Do not create expected bytes with the code under test. Review frozen bytes
   independently and verify their corruption hashes.
7. Treat every ambiguity as a specification issue. No “match Python” patch is
   acceptable without a public normative correction and vector.
8. Keep dispatch, v1, and v2 parsers isolated. Scanner nodes cannot enter a
   verifier path; a v2 error cannot retry as v1.
9. Keep operational errors typed and outside AELITIUM semantic reason mapping.
10. Permit no runtime network, ambient trust, implicit clock, provider SDK, or
    producer dependency.
11. Require two-person review of canonicalization, hash projections, signature
    scope, assurance invariants, and failure precedence.
12. Run fuzzing for lexer/parser state machines, duplicates, deep nesting,
    Unicode, number boundaries, and malformed truncations.
13. After independent conformance, a separate auditor may compare black-box
    outputs. Differences return to specification review; Python never becomes
    the tie-breaker.

## 23. Proposed implementation phases

### Phase 0 — specification closure

Resolve section 21 in `aelitium-v3`, publish a spec-only snapshot, add the
language-neutral harness contract and verifier-specific frozen vectors, and
obtain review. This phase creates no Go repository.

### Phase 1 — repository and independence controls

Create the separate repository only after approval. Pin Go 1.27.x, add the
spec snapshot/digests, license inventory, no-Python CI checks, threat model,
and empty package boundaries. No verification claim yet.

### Phase 2 — parsers, dispatch, and canonicalization

Implement the iterative union scanner, strict v2 parser/profile, standard JCS
adapter, and v1 declared-capability parser/serializer. Pass scanner-only,
30-case v1, and canonicalization/hash/storage portions of the 114-case corpus.

### Phase 3 — bundle integrity and schemas

Implement immutable file snapshots, selected-version manifest parsing,
`ai_output_v1` Draft 7 validation, canonical storage, SHA-256, and exact payload
failure precedence.

### Phase 4 — signatures, trust, and binding

Implement keyring parsing, Ed25519 over raw manifest bytes, explicit trust
store and fingerprint membership, original binding, and all malformed-input
vectors.

### Phase 5 — invocation, Freshness, assurance, and results

Implement invocation identity/binding after their normative grammar is
published, Freshness, all eight state machines, invariant validation, exact
refs/bases/boundaries, and deterministic result JSON. Pass the 32 verification
operations in the 44-case corpus plus the new full-result corpus.

### Phase 6 — comparison

After G-12 closes, implement verify-first comparison, all modes/bases/outcomes,
identifier mismatch refusal, side summaries, and comparison boundaries. Pass
44/44 and the comparison operation in the v2 corpus.

### Phase 7 — independent audit and release decision

Perform provenance review, dependency audit, fuzz/race/static analysis,
cross-platform builds, repeated-output tests, complete corpus run, and a
black-box cross-language report. A separate approval decides whether the
repository may be published or released; implementation completion alone does
not authorize those actions.

## 24. Acceptance criteria

A candidate is conforming only when all of the following are true:

- the normative source snapshot is stable, public, digest-pinned, and contains
  no implementation-only decision dependency;
- the repository, Go module graph, build, tests, and runtime contain no Python
  package, Python process, AELITIUM producer module, or shared decision code;
- exact dispatch route and original-byte handoff pass every vector, including
  deep nesting and huge numbers, without host-recursion routing changes;
- v2 passes every applicable RFC 8785 vector and all portable-v2 byte/profile
  cases with the pinned Go toolchain;
- the 30-case v1 corpus passes exactly, while the >640-digit limitation remains
  explicitly declared and never mislabeled as semantic invalidity;
- the four CPython-profile cases run only under an explicit compatibility
  declaration and do not become a universal Go-v1 claim;
- the complete candidate passes the existing 44/44 and 114/114 unchanged;
- every emitted verification, assurance, and comparison object validates
  against its embedded pinned schema and satisfies cross-field invariants;
- repeated executions over identical byte snapshots and explicit inputs are
  byte-identical;
- all hash inputs have independent byte-level tests and contain no unapproved
  prefix or storage LF;
- signature tests prove the exact manifest snapshot, and trust tests prove
  separation of mathematical validity from explicit identity membership;
- all eight assurance dimensions, absence rules, failures, refs, bases,
  policy/trust refs, and boundaries pass the complete decision matrix;
- authorization remains `NOT_EVALUATED` and no ninth dimension exists;
- operational exhaustion cannot emit a semantic JSON/profile/manifest reason
  or change version routing;
- no network, implicit current time, ambient trust, locale, provider, or hidden
  policy input is observed;
- fuzzing, race detection, static analysis, dependency/license/vulnerability
  review, and reproducible build checks pass; and
- documentation states the precise v1 capability, v2 capability, and all
  non-claims without asserting an independent verifier before evidence exists.

## 25. Explicit non-claims

This design and any future verifier do not establish:

- provider receipt, provider execution, provider identity, or response
  causation;
- semantic truth, correctness, safety, quality, or equivalence;
- capture completeness;
- historical occurrence or historical non-modification without an independent
  anchor;
- trusted historical time from a declared timestamp;
- signer identity, role, authorization, revocation status, or legal identity
  from mathematical signature validity alone;
- authorization under the current eight-dimensional contract;
- legal or regulatory compliance;
- model drift, regression, quality degradation, or provider fault;
- complete invocation identity;
- cross-version v1/v2 comparability;
- complete portability of the released v1 arbitrary-integer domain;
- that RFC 8785 applies to v1;
- that a Go implementation, repository, release, or independent validation
  already exists; or
- that passing frozen tests proves correctness outside their specified
  contract and capability boundary.

## 26. Final verdict

INDEPENDENT_VERIFIER_DESIGN_NOT_READY
