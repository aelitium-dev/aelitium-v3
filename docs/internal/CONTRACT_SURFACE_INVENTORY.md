# Contract Surface Inventory

**Status:** NON-NORMATIVE
**Baseline:** AELITIUM `v0.4.0` at
`37646ad6a2d64f6f82e9942c324da2a5940912c7`
**Purpose:** internal reconciliation record for the contract-conformance work;
this file does not itself change a released contract.

## Reconciliation conclusion

The proposed result-contract work can be additive without changing the semantic
meaning of the released `v0.4.0` verifier or comparison decisions. The safe
implementation is a projection of the existing authoritative
`AIVerificationResult` and `aelitium-compare-v1` data, exposed through a new
opt-in verification JSON surface. Existing verification `--json` behavior,
human-readable output, exit codes, evidence schemas, hashing, signing, trust,
freshness, invocation, and comparison-basis selection must remain unchanged.

The existing `aelitium-compare-v1` identifier is already authoritative. This
work must harden its JSON representation additively; it must not create a
renamed or competing comparison contract.

## CURRENT IMPLEMENTED SEMANTICS

### Authoritative verification path

`engine.ai_verify.verify_ai_bundle` is the shared AI-bundle verification kernel
used by `verify`, `verify-bundle`, compare prevalidation, and the Python
standalone wrapper. Its operation order is material:

1. parse an explicitly supplied trust store, if any;
2. validate the explicitly supplied Freshness policy pair, if any;
3. load and validate canonical and manifest artifacts;
4. enforce `ai_output_v1`, governed canonical bytes, manifest identifiers, and
   `ai_hash_sha256` consistency;
5. verify bundled Ed25519 material when present;
6. evaluate stored v1 binding fields, invocation identity, invocation binding,
   explicit trust-store membership, and declared-time Freshness;
7. apply optional signature, binding, and external key-membership requirements with the
   existing failure precedence.

The verifier evaluates only local files and explicit caller inputs. It has no
network dependency, ambient trust-store discovery, or ambient current time.

### Current assurance dimensions and reachable states

The closed state vocabulary is `VALID`, `INVALID`, `ABSENT`, `UNESTABLISHED`,
and `NOT_EVALUATED`, but reachability is dimension-specific:

| Dimension | Reachable states in `v0.4.0` | Existing meaning of `VALID` |
|---|---|---|
| `payload_integrity` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | schema, governed canonical bytes, manifest identifiers, and canonical payload digest are consistent |
| `binding_field_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | the four stored v1 request/response/binding fields are complete, well formed, and mutually consistent |
| `invocation_identity_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | the stored `aelitium-invocation-v1` object is structurally valid and its hash recomputes from its stored selected fields |
| `invocation_binding_consistency` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | the stored `aelitium-invocation-binding-v1` object recomputes and links this bundle's already-valid invocation identity hash to its stored response hash |
| `signature_validity` | `VALID`, `INVALID`, `ABSENT`, `NOT_EVALUATED` | bundled Ed25519 material mathematically verifies the manifest bytes |
| `trusted_signer_identity` | `VALID`, `UNESTABLISHED` | the verified signing key fingerprint occurs in the independently supplied `aelitium-trust-v1` store |
| `freshness` | `VALID`, `INVALID`, `UNESTABLISHED`, `NOT_EVALUATED` | declared `ai_canonical.json.ts_utc` lies in the inclusive window defined by the complete explicit policy pair |
| `authorization` | `NOT_EVALUATED` only | not applicable: no authorization evaluator exists |

The implementation already enforces important impossible-state relationships:

- `trusted_signer_identity=VALID` requires `signature_validity=VALID` and an
  explicit matching trust input;
- `invocation_binding_consistency=VALID` requires
  `invocation_identity_consistency=VALID`;
- a malformed present optional field is `INVALID`, never treated as absence or
  as a comparison fallback;
- a successful verification has `payload_integrity=VALID` and cannot contain
  an `INVALID` evaluated assurance dimension;
- `authorization` cannot leave `NOT_EVALUATED`.

These invariants need explicit validation at the new serialization boundary so
synthetic or future caller-created result objects cannot emit impossible
machine-readable combinations.

### Existing evidence and identity scopes

- `ai_hash_sha256` is the digest of the complete governed canonical AI payload;
  it is not a digest of the bundle directory.
- `request_hash` v1 selects recorded `model` and `messages`. It excludes other
  invocation fields and is not complete invocation identity.
- `response_hash` selects recorded response `content` and model identifier.
- the original `binding_hash` commits to the stored `request_hash` and
  `response_hash` pair.
- `aelitium-invocation-v1` selects its declared surface, mode, model, messages,
  and only the surface-specific parameter allowlist implemented in
  `engine/invocation.py`.
- `aelitium-invocation-binding-v1` binds the invocation-identity hash to the
  stored response hash. It does not establish real-world causation.
- canonicalization is Python `json.dumps(..., sort_keys=True,
  separators=(",", ":"), ensure_ascii=False)` encoded as UTF-8. It is not
  RFC 8785/JCS.

### Existing comparison decision contract

`aelitium-compare-v1` verifies both bundles before basis selection. Its modes
and bases are already implemented and must remain recognizable:

| Mode | Basis selection |
|---|---|
| `INVOCATION_FIRST` | `INVOCATION_IDENTITY_V1` only when both sides have valid identity and valid invocation binding; otherwise `REQUEST_HASH_V1_FALLBACK` for valid inputs |
| `STRICT_INVOCATION` | `INVOCATION_IDENTITY_V1` when usable on both sides; otherwise `NONE` with required basis `INVOCATION_IDENTITY_V1` |
| `LEGACY_REQUEST_HASH_V1` | always selects `REQUEST_HASH_V1_LEGACY` after input verification |

Matching selected identities permit a response-hash relationship of
`UNCHANGED` or `CHANGED`; different or unavailable required identities produce
`NOT_COMPARABLE`; failed or internally impossible inputs produce
`INVALID_BUNDLE` with basis `NONE`. `NOT_COMPARABLE` is an expected semantic
result with exit code `1`, not a verifier crash.

### Current scan/coverage facts

`scan`/`check` are static Python source heuristics over known regex patterns.
Their counts and percentage concern detected sites only and may have false
positives or false negatives. They do not establish runtime capture or a
defensible denominator for all AI interactions. Coverage is separate from
artifact validity. No new coverage-validity dimension or coverage contract is
justified by the current runtime.

## CURRENT PUBLIC CONTRACT

The current public contract is distributed across `README.md`,
`FEATURE_MATRIX.md`, `docs/TRUST_BOUNDARY.md`,
`docs/MESSAGING_GUARDRAILS.md`, `docs/INVOCATION_ASSURANCE.md`,
`docs/CANONICAL_REQUEST.md`, `docs/CANONICALIZATION_SPEC.md`, and the released
`CHANGELOG.md` entry. The controlling boundaries are:

- internal consistency is not historical occurrence or historical
  non-modification without an independently trusted anchor;
- signature validity is separate from external signing-key membership;
- invocation identity consistency is not provider receipt or execution;
- invocation binding consistency is not response causation;
- Freshness is declared-time recency, not trusted historical time;
- `CHANGED` identifies a selected recorded hash relationship, not model drift,
  regression, quality degradation, provider fault, or cause;
- hash equality is not semantic equivalence;
- static scan findings are not universal capture completeness;
- technical verification does not determine legal compliance, authorization,
  output truth, or safety.

The public CLI contracts that must be preserved include status-first key/value
output, verification exit codes `0`/`2`, comparison exit codes `0`/`1`/`2`, and
all existing compare modes, bases, reasons, diagnostics, and legacy keys.

Existing `verify` and `verify-bundle --json` produce JSON only for successful
verification. Invalid verification intentionally retains key/value output.
Changing that behavior under the existing flag would be a compatibility break.

## LEGACY COMPATIBILITY

- Pre-invocation bundles remain valid when their governed v1 artifacts are
  consistent; both invocation dimensions report `ABSENT`.
- Unsigned and unbound bundles remain valid unless the matching explicit
  requirement is selected.
- `REQUEST_HASH_V1_FALLBACK` remains visible in default comparison whenever one
  or both valid inputs lack usable invocation evidence.
- `--legacy-request-hash-v1` preserves v0.3.x request-hash decisions through
  `REQUEST_HASH_V1_LEGACY` even when invocation evidence is present.
- `--require-invocation-evidence` remains fail-closed with basis `NONE` when
  usable invocation evidence is unavailable.
- Existing evidence schemas, canonicalization identifier, request/response and
  binding formulas, normal text output, existing `--json` keys, and exit codes
  remain unchanged.
- The Python standalone wrapper shares the Python verification kernel; it is not
  a clean-room independent verifier.

## PROPOSED NEW MACHINE-READABLE SURFACE

The smallest compatible addition is:

1. `aelitium-assurance-result-v1`: an ordered eight-dimension projection of the
   existing states. Each entry carries its dimension-specific basis, local
   evidence references, applicable explicit trust/policy references, and stable
   non-claim codes. No aggregate score or ninth dimension is permitted.
2. `aelitium-verification-result-v1`: overall `VALID`/`INVALID`, existing reason,
   canonical-payload digest when established, artifact component references,
   explicit verification/trust/policy inputs, and an embedded assurance result.
3. `aelitium-claim-boundary-v1`: a small closed vocabulary embedded by reference
   in result documents. A separate standalone claim object adds no current
   evidence semantics, so the contract identifier plus code arrays are the
   stable representation.
4. A new mutually exclusive `--contract-json` option on `verify` and
   `verify-bundle`. It emits the versioned result for both success and failure
   while leaving the existing `--json` and text behavior untouched.
5. Additive hardening fields in existing `compare --json`: stable left/right
   evidence references, per-side verification summaries and all eight assurance
   states, a distinct comparability result, applicable response relationship,
   and claim-boundary codes. Existing fields and decisions remain present.
6. Strict JSON Schemas and serialization invariant checks for all new result
   structures. Contract construction must reject impossible assurance
   combinations rather than serialize them.
7. A frozen, deterministic public adversarial corpus and runner. Vectors will
   cite concrete artifacts, expected status/reason/state/basis, and applicable
   expected non-claims.
8. A deterministic no-network demonstration that writes the three result
   documents and renders only bounded interpretations.

The new output identifies `ai_hash_sha256` accurately as a canonical-payload
digest, not as a digest of an entire directory or proof of historical identity.
Trust-store filesystem paths will not be embedded; machine results use stable
local input references and state only whether an explicit input was supplied.

## RESEARCH ONLY / NOT IMPLEMENTED

- No ninth assurance dimension, aggregate trust score, policy decision, legal
  compliance decision, evaluation metric, benchmark, receipt platform,
  observability backend, runtime gateway, proxy, or generic scanner.
- No claim of complete invocation identity, provider execution, response
  causation, historical occurrence, semantic truth, capture completeness,
  trusted historical time, model drift, or provider fault.
- No `aelitium-coverage-context-v1` in this branch unless later evidence shows
  that current scan facts can be represented without suggesting universal or
  runtime completeness. Current inspection does not justify it.
- Tool declarations are not selected by the current invocation grammar.
  Provider routing beyond the declared adapter surface is not established.
  These scenarios must be marked `RESEARCH_GAP`, not represented as supported
  comparisons.
- A clean-room Go/Rust verifier is deferred. The requirements document will
  specify reproducible inputs, algorithms, precedence, state invariants, and
  vectors without treating the Python standalone wrapper as independent.
- One external evidence family will be pinned and mapped conservatively only
  after its exact published version is established. If its signature,
  serialization, or evidence semantics cannot be mapped without invention, the
  implementation will stop at an `EXPERIMENTAL` profile document and explicit
  blocker.

## Exact implementation plan

1. Add a result-contract module containing identifiers, the claim-boundary
   vocabulary, dimension metadata, invariant validation, and deterministic
   serializers; add strict packaged schemas and focused unit tests.
2. Add `--contract-json` to both AI bundle verification commands, mutually
   exclusive with legacy `--json`; preserve all old output and return codes.
3. Extend only compare JSON objects with nested side summaries, evidence
   references, comparability/response fields, and bounded non-claims; preserve
   existing JSON keys, text output, modes, bases, reasons, and exits.
4. Run the full existing suite and release/claims gates before corpus work.
5. Add 30–50 frozen adversarial vectors across verification, assurance,
   comparison, trust, Freshness, and compatibility, plus a deterministic runner
   and corpus documentation; run the full gates again.
6. Research and pin one external profile, document exact supported and
   unsupported mappings and external trust assumptions, and implement an import
   only if source evidence can map without granting AELITIUM-native assurance.
7. Add the no-API end-to-end demo, result-contract documentation, independent
   verifier requirements, documentation index updates, and any strictly
   additive public-claims checks needed for the new surfaces.
8. Run the full suite, end-to-end matrix, claims guardrail, release audit,
   external-validation runner, and conformance runner; report all changes and
   leave the branch unmerged, untagged, and unreleased.
