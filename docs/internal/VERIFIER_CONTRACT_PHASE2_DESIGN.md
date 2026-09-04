# Verifier Contract Closure Phase 2 — Design and Compatibility Audit

**Status:** DESIGN-AUDIT-NON-NORMATIVE

**Repository baseline:** `main` at
`15b15e0e832909923be6ff7ad27a4a17b2c38699`

**Scope:** G-04 (`ai_manifest.json`), G-05 (`verification_keys.json`), and
G-06 (`aelitium-trust-v1`) only

This document designs the public contracts, schemas, and frozen conformance
data that would be needed to close these three gaps. It does not itself close
them, modify a protocol, change a schema, change a corpus, or make an
implementation authoritative.

## 1. Executive decision

The three gaps cannot all be closed safely from the current public contract.
The intended structures and almost all semantic checks are recoverable, but
released-v1 acceptance contains unresolved host-dependent behavior at the
source boundary:

1. manifest timestamp validation uses an unspecified Unicode decimal-digit
   repertoire and an unspecified end-anchor behavior;
2. the released keyring is open and last-name-wins, so ignored or overwritten
   values can trigger the configurable CPython integer-conversion limit; and
3. the released trust-store parser is closed only after last-name-wins map
   collapse, creating the same issue in overwritten values.

There are also compatibility decisions, rather than mere drafting tasks,
around duplicate names, unmatched surrogate escapes, and non-zero Base64 pad
bits. Rejecting any input currently accepted in these categories would narrow
released v0.4.0 behavior. Copying current Python behavior would violate the
normative hierarchy and would still not define a portable contract.

| Gap | Design-audit status | Immediate blocker |
|---|---|---|
| G-04 | **NOT_READY_TO_CLOSE** | No fixed, language-neutral v1 timestamp digit repertoire; host-dependent integer behavior remains reachable in unknown or overwritten manifest values. |
| G-05 | **NOT_READY_TO_CLOSE** | Open/last-name-wins keyring source admits host-dependent ignored values; strict duplicate or canonical-Base64 rules would narrow released acceptance. |
| G-06 | **NOT_READY_TO_CLOSE** | The supposedly strict store is last-name-wins before closed-object validation; fixing duplicate, surrogate-label, or Base64 alias acceptance would narrow released input behavior. |

The smallest preliminary specification action is one reviewed compatibility
decision that freezes a language-neutral **legacy auxiliary JSON source
profile** and a fixed **legacy manifest timestamp profile**, with an explicit
statement of any divergence from supported v0.4.0 CPython configurations. If
exact released parity is required for every configuration, G-02 must first
provide a capability or operational-refusal contract usable at these source
positions. If stricter behavior is preferred, it requires new versioned
format identifiers rather than silently tightening existing ones.

## 2. Method and authority

The source hierarchy and conflict rules in
[`../VERIFIER_PROTOCOL_V1.md`](../VERIFIER_PROTOCOL_V1.md) govern this audit.
The following Level 1 sources were used before implementation inspection:

- [`../VERIFIER_PROTOCOL_V1.md`](../VERIFIER_PROTOCOL_V1.md);
- [`../INDEPENDENT_VERIFIER_REQUIREMENTS.md`](../INDEPENDENT_VERIFIER_REQUIREMENTS.md);
- [`../CANONICALIZATION_SPEC.md`](../CANONICALIZATION_SPEC.md);
- [`../TRUST_BOUNDARY.md`](../TRUST_BOUNDARY.md);
- [`../VERIFICATION_RESULT_V1.md`](../VERIFICATION_RESULT_V1.md);
- [`../ASSURANCE_RESULT_V1.md`](../ASSURANCE_RESULT_V1.md);
- the schemas currently named by those contracts; and
- the frozen data rooted at `conformance/manifest.json`,
  `conformance/canonicalization/manifest.json`, and
  `conformance/canonicalization_v2/manifest.json`.

The current schema inventory contains contracts for canonical payloads and
public result structures, but no schema for any of the three source artifacts
audited here. Frozen examples exercise some valid and invalid bundles, but do
not define the missing source-level behavior by themselves.

The Python implementation is not normative. Section 9 is deliberately labeled
**IMPLEMENTATION CROSS-CHECK** and records discrepancies only. A future
protocol change must state its own rules and compatibility basis; it must not
incorporate a Python file by reference.

## 3. Contract boundaries and evaluation pipeline

The future public closure should keep five boundaries distinct:

| Boundary | Input | Output | Must not do |
|---|---|---|---|
| Dispatch scanner | Immutable raw `ai_manifest.json` bytes | v2 route or legacy/error-resolution route | Parse semantic values for reuse, canonicalize, reject duplicates, or convert numbers |
| Manifest parser/profile | The same raw manifest bytes and selected route | Parsed manifest or manifest failure | Rewrite the raw signature message or borrow values from dispatch |
| Keyring parser | Raw optional `verification_keys.json` bytes | One candidate public key and signature, or signature-material failure | Treat bundled material as a trust anchor |
| Trust-store parser | Explicit external local file bytes | A set of derived Ed25519 fingerprints, or trust-input failure | Consult ambient/network trust or consume stored fingerprints |
| Signature/trust evaluation | Exact raw manifest bytes, parsed keyring, optional parsed trust store | `signature_validity` and `trusted_signer_identity` states | Equate mathematical signature validity with trust membership or authorization |

The canonicalization identifier governs the manifest parser and governed hash
canonicalizer. It does **not** silently change the source profile of
`verification_keys.json` or the external trust store. Any portable replacement
for those existing formats needs an explicit format version.

The observable order remains:

1. explicit trust and Freshness input validation;
2. required canonical and manifest file checks;
3. non-observable manifest dispatch;
4. canonical payload parse;
5. selected manifest parse and ordered manifest field checks;
6. canonical payload schema, exact bytes, and digest;
7. optional keyring parsing and signature mathematics;
8. binding, invocation, trust-membership, and Freshness result precedence as
   already published.

This phase does not define filesystem snapshots, limits, or operational error
serialization. Those remain G-09.

## 4. G-04 — `ai_manifest.json`

### 4.1 Input and dispatch

The manifest input is the immutable byte sequence read from the required file
`ai_manifest.json`. `AELITIUM-DISPATCH-JSON-1` in
[`../VERIFIER_PROTOCOL_V1.md`](../VERIFIER_PROTOCOL_V1.md) runs first as
non-observable lookahead. The selected parser receives the same bytes from byte
zero, and the same bytes later form the Ed25519 message.

The source profiles differ by route:

| Property | Released legacy route | Portable-v2 route |
|---|---|---|
| Encoding | Strict UTF-8 | Strict shortest-form UTF-8 |
| Leading BOM | Rejected as `MANIFEST_NOT_JSON` | Cannot select v2 because it is outside dispatch grammar; legacy/error resolution returns `MANIFEST_NOT_JSON` |
| Complete document | Exactly one value plus JSON whitespace; any other trailing byte rejects | Exactly one RFC 8259 value plus JSON whitespace; any other trailing byte rejects |
| Non-finite tokens | Exact `NaN`, `Infinity`, and `-Infinity` are source values | Rejected by the v2 profile as `MANIFEST_NOT_JSON` after exact v2 dispatch |
| Duplicate names | Last decoded name wins at every depth | Rejected at every depth after escape processing |
| Escaped unmatched surrogate | Retained by the legacy value model; may survive in an ignored extension | Rejected by the v2 profile |
| Unicode noncharacter | Accepted by the legacy parser | Rejected by the v2 profile |
| Numbers | Released arbitrary-integer/binary64 behavior, including G-02's host digit limit | Complete bounded binary64 and mathematical integer-token profile |
| Unknown members | Parsed, then ignored and given no semantics | Entire value must satisfy v2 recursively; valid members are then ignored and given no semantics |
| Root | Must be an object after parsing | Must be an object after parsing |

The legacy parser's accepted JSON whitespace includes space, horizontal tab,
line feed, and carriage return around the single value. Newline conversion by
a text-reading API must not affect signature scope: signature verification
always receives the original bytes.

### 4.2 Required and optional members

There are exactly five required manifest members and one currently interpreted
optional member. Any other member is an ignored extension.

| Presence order | Member | Presence | Value/domain when evaluated | Failure reason |
|---:|---|---|---|---|
| 1 | `schema` | Required | String exactly `ai_pack_manifest_v1` | Missing: `MANIFEST_MISSING_FIELD`; any other value/type: `MANIFEST_BAD_SCHEMA` |
| 2 | `ts_utc` | Required | Conditional timestamp profile in section 4.4 | Missing: `MANIFEST_MISSING_FIELD`; enabled invalid value: `MANIFEST_BAD_TS_UTC` |
| 3 | `input_schema` | Required | String exactly `ai_output_v1` | Missing: `MANIFEST_MISSING_FIELD`; any other value/type: `MANIFEST_BAD_INPUT_SCHEMA` |
| 4 | `canonicalization` | Required | Exact route identifier: `json_sorted_keys_no_whitespace_utf8` or `aelitium_jcs_profile_v2` | Missing: `MANIFEST_MISSING_FIELD`; otherwise unsupported after earlier checks: `MANIFEST_BAD_CANONICALIZATION` |
| 5 | `ai_hash_sha256` | Required | String of exactly 64 ASCII lowercase hexadecimal characters `[0-9a-f]` | Missing: `MANIFEST_MISSING_FIELD`; malformed: `MANIFEST_BAD_AI_HASH_SHA256`; well-formed but unequal digest: later `HASH_MISMATCH` |
| Later binding evaluation | `binding_hash` | Optional | When the binding quartet is complete, exactly 64 ASCII lowercase hexadecimal characters | Partial quartet: `BINDING_FIELDS_INCOMPLETE`; malformed complete quartet: `BINDING_FIELD_MALFORMED`; mismatch: `BINDING_HASH_MISMATCH` |

Presence checks are performed in the listed order and all missing-member cases
use `MANIFEST_MISSING_FIELD`. JSON Schema's unordered `required` keyword cannot
choose this public reason; the order must remain procedural.

The manifest `schema` remains `ai_pack_manifest_v1` for both canonicalization
routes. The proposed verifier schemas in section 4.6 describe route profiles;
they do not change that stored identifier.

Unknown valid members are allowed. They have no verification, assurance,
authorization, trust, Freshness, or comparison meaning. Closing the object
with `additionalProperties: false` would narrow v1 and contradict the v2
must-ignore rule.

### 4.3 Duplicate and extension behavior

For legacy v1, names are compared after JSON escape processing and the final
occurrence supplies the parsed value. This applies to required, optional, and
unknown members and to nested objects. An earlier malformed semantic value can
therefore be overwritten by a later valid occurrence, although every lexical
token is still processed by the source parser.

For portable v2, any duplicate decoded member name rejects the whole manifest
as `MANIFEST_NOT_JSON` before map collapse, including duplicates in unknown
extensions and duplicate selectors. A valid unknown extension remains
must-ignore only after the full recursive v2 profile succeeds.

### 4.4 Manifest timestamp contract and G-11 boundary

The public contract currently calls this a **syntactic**, not calendar or
time-authority, check. It must stay distinct from Freshness:

- manifest validation reads `ai_manifest.json.ts_utc`;
- Freshness reads `ai_canonical.json.ts_utc` under an explicit policy pair;
- manifest validation does not compute age, consult a clock, or establish
  historical time; and
- this phase must not decide G-11's calendar, year, or leap-second semantics
  for Freshness.

When `validate_manifest_timestamp=false`, only the `ts_utc` presence
requirement remains. Type, spelling, component range, and calendar validity are
not checked. Under v2 the value must still be a valid recursive v2 value, but
it need not be a string. Disabling this check does not skip `schema`,
`input_schema`, `canonicalization`, digest-shape, payload, signature, binding,
or any other verification rule.

When validation is enabled, the closure needs separate version rules:

| Route | Compatibility-safe description | Closure status |
|---|---|---|
| v1 | Four decimal-digit matches, `-`, two digit matches, `-`, two digit matches, `T`, two digit matches, `:`, two digit matches, `:`, two digit matches, `Z`, followed optionally by one decoded U+000A because of the released end-anchor behavior; no component or calendar range check | The end-anchor behavior is definable, but the Unicode decimal-digit repertoire varies with the host Unicode database and is not fixed by a Level 1/2 source |
| v2 | Recommended: exactly 20 Unicode scalar values using ASCII `[0-9]` in the fourteen digit positions and the exact ASCII separators; no trailing U+000A; no component or calendar range check | May be adopted as `UNRELEASED_V2_ONLY` after explicit review; it must not be retroactively applied to v1 |

A raw LF inside a JSON string is never valid source. The v1 anomaly is an
escaped `\n` that becomes a final U+000A in the parsed string. A final CR,
CRLF, or two LFs does not satisfy the observed legacy anchor behavior.

Values such as `0000-00-00T00:00:60Z` and
`9999-99-99T99:99:99Z` satisfy the lexical shape; accepting the lexical shape
does not assert that those are calendar timestamps. An ASCII-only,
whole-string rule is desirable for v2, but applying it to v1 is
`WOULD_NARROW_V1` because released verification accepts non-ASCII decimal
digits and one final decoded LF.

The unresolved digit repertoire makes G-04 not ready: defining digits by the
current host regex is not language-neutral, while pinning any Unicode version
or choosing ASCII changes at least one supported-runtime acceptance set. The
preliminary compatibility decision must choose and publish an exact code-point
set or a versioned legacy capability rule.

### 4.5 Ordered manifest failure mapping

After canonical payload parsing succeeds, manifest outcomes are ordered:

1. source/profile failure: `MANIFEST_NOT_JSON`;
2. parsed root is not an object: `MANIFEST_NOT_OBJECT`;
3. first missing required member in section 4.2 order:
   `MANIFEST_MISSING_FIELD`;
4. bad `schema`: `MANIFEST_BAD_SCHEMA`;
5. bad `input_schema`: `MANIFEST_BAD_INPUT_SCHEMA`;
6. route-inconsistent or unsupported `canonicalization`:
   `MANIFEST_BAD_CANONICALIZATION`;
7. enabled timestamp check fails: `MANIFEST_BAD_TS_UTC`;
8. digest spelling fails: `MANIFEST_BAD_AI_HASH_SHA256`;
9. later payload/schema/bytes/hash and optional-evidence checks retain their
   published order.

Dispatch failure is not itself a reason. A malformed source enters legacy
error resolution, and an exact final v2 selector never retries v1 after v2
failure.

### 4.6 Proposed schemas

Two route-specific schemas are the correct publication structure. A single
`oneOf` schema could describe the post-parse field alternatives, but would
obscure the fact that each branch has a different mandatory procedural source
profile. Neither structure can express duplicate-source behavior; that remains
normative prose.

#### `engine/schemas/ai_manifest_v1.json`

- Draft: JSON Schema Draft 7.
- Recommended `$id`: `aelitium://schemas/ai_manifest_v1.json`.
- Root: object.
- `required`: the five fields in section 4.2 (schema order is not reason
  order).
- `schema`: `const: "ai_pack_manifest_v1"`.
- `input_schema`: `const: "ai_output_v1"`.
- `canonicalization`: `const: "json_sorted_keys_no_whitespace_utf8"`.
- `ai_hash_sha256`: string, `minLength: 64`, `maxLength: 64`, pattern
  `^[0-9a-f]{64}$`.
- `ts_utc`: unconstrained in the option-independent schema; a `$comment`
  points to the procedural conditional rule.
- `binding_hash`: string with the same lowercase-hex length/pattern, while
  public reason selection remains deferred to binding evaluation.
- `additionalProperties: true`.

#### `engine/schemas/ai_manifest_v2.json`

The same structure, except:

- recommended `$id`: `aelitium://schemas/ai_manifest_v2.json`; and
- `canonicalization` is `const: "aelitium_jcs_profile_v2"`.

`additionalProperties` remains true. The v2 source/value profile, not JSON
Schema, rejects invalid extension values and duplicate names.

Neither schema can govern UTF-8, BOMs, whole-document consumption, raw
whitespace, duplicate source names, raw escape spelling, dispatch, source
number lexemes, signature bytes, or operational limits. Neither schema can
select an externally enabled timestamp rule or reproduce ordered reason
precedence. Those rules remain procedural and normative prose.

### 4.7 G-04 compatibility classification

| Proposed rule | Classification |
|---|---|
| Strict UTF-8, no leading BOM, one complete source value | `ALREADY_RELEASED_BEHAVIOR` |
| v1 exact non-finite tokens, last-name-wins names, and ignored unknown members | `ALREADY_RELEASED_BEHAVIOR` |
| Preserve host-configurable v1 integer-token acceptance in all parsed positions (not language-neutral) | `ALREADY_RELEASED_BEHAVIOR` |
| Replace that host-configurable integer acceptance with one fixed v1 acceptance rule | `REQUIRES_VERSIONED_CHANGE` |
| v1 global duplicate rejection or closed manifest object | `WOULD_NARROW_V1` |
| Complete recursive v2 profile and duplicate rejection | `UNRELEASED_V2_ONLY` |
| Required-field order, identifier values, and 64-lowercase-hex digest | `ALREADY_RELEASED_BEHAVIOR` |
| `validate_manifest_timestamp=false` skips type and spelling only | `SAFE_CLARIFICATION` |
| Preserve one final decoded LF in enabled v1 timestamp validation | `SAFE_CLARIFICATION` |
| ASCII-only, exact whole-string v1 timestamp | `WOULD_NARROW_V1` |
| ASCII-only, exact whole-string v2 timestamp | `UNRELEASED_V2_ONLY` |
| Pin a Unicode digit table for v1 without a compatibility decision | `REQUIRES_VERSIONED_CHANGE` |
| Optional `binding_hash` checked at the existing binding stage | `ALREADY_RELEASED_BEHAVIOR` |

## 5. G-05 — `verification_keys.json`

### 5.1 Presence and source profile

`verification_keys.json` is optional. Its presence is tested before payload
verification only to distinguish `ABSENT` from `NOT_EVALUATED`; its bytes are
parsed and its signature evaluated only after payload integrity succeeds.

The current format is `ed25519-v1` for both v1 and v2 bundles. The manifest's
canonicalization identifier does not switch this file to the v2 JSON profile.
The missing public source profile must decide these released behaviors:

- strict UTF-8; leading BOM rejected;
- exactly one complete JSON value with only JSON whitespace around it;
- the legacy JSON extensions and integer conversion behavior;
- last decoded member name wins at every object depth;
- unmatched surrogate escapes remain legacy string elements; and
- unknown members are accepted and ignored.

The last four points cannot be silently replaced with strict RFC 8259,
duplicate rejection, scalar-only strings, or closed objects. Doing so would
narrow existing signed bundle acceptance.

### 5.2 Exact container and field model

The stored structure is:

```json
{
  "keyring_format": "ed25519-v1",
  "keys": [
    {
      "key_id": "non-empty exact-match label",
      "public_key_b64": "<32 raw Ed25519 public-key bytes>"
    }
  ],
  "signatures": [
    {
      "key_id": "same exact label",
      "algorithm": "ed25519",
      "scope": "manifest.json",
      "sig_b64": "<64 raw Ed25519 signature bytes>"
    }
  ]
}
```

| Location | Required domain | Failure after payload integrity |
|---|---|---|
| root | Object | `SIGNATURE_INVALID` |
| `keyring_format` | Exact string `ed25519-v1` | `SIGNATURE_INVALID` |
| `keys` | Array of exactly one object | `SIGNATURE_INVALID` |
| `keys[0].key_id` | Non-empty legacy-decoded string | `SIGNATURE_INVALID` |
| `keys[0].public_key_b64` | Base64 profile in section 5.4, decoding to exactly 32 bytes | `SIGNATURE_INVALID` |
| `signatures` | Array of exactly one object | `SIGNATURE_INVALID` |
| `signatures[0].key_id` | Exact code-unit equality with `keys[0].key_id` | `SIGNATURE_INVALID` |
| `signatures[0].algorithm` | Exact case-sensitive string `ed25519` | `SIGNATURE_INVALID` |
| `signatures[0].scope` | Exact case-sensitive string `manifest.json` | `SIGNATURE_INVALID` |
| `signatures[0].sig_b64` | Base64 profile in section 5.4, decoding to exactly 64 bytes | `SIGNATURE_INVALID` |

`key_id` is a correlating label, not a trust identity. The released check does
not trim it, normalize it, require visible characters, or require a Unicode
scalar-only value. A whitespace-only non-empty value and an escaped unmatched
surrogate can satisfy the equality check. Tightening that domain requires a
new keyring format.

The root, key entry, and signature entry are open objects for `ed25519-v1`.
Unknown members are ignored and acquire no signature, trust, authorization, or
identity meaning. Source duplicates are last-name-wins after decoded-name
comparison. A future strict closed keyring must use a new format such as
`ed25519-v2`; it cannot reinterpret `ed25519-v1`.

### 5.3 Signature algorithm and message

The only algorithm is pure Ed25519 under RFC 8032 section 5.1. Ed25519ctx,
Ed25519ph, Ed448, certificates, key identifiers as identities, and algorithm
negotiation are absent.

The message is exactly the immutable raw `ai_manifest.json` byte sequence
used as verifier input. Member order, whitespace, unknown fields, escape
spellings, line endings, and terminal bytes are signed. The manifest is not
canonicalized for this purpose. The public key is the 32 decoded raw bytes;
the signature is the 64 decoded raw bytes.

### 5.4 Exact Base64 acceptance required for v1 compatibility

The closure cannot use the phrase “strict Base64” alone. The compatibility
profile observed for the two fixed lengths is:

| Material | Accepted lexical shape | Decoded length |
|---|---|---:|
| Ed25519 public key | Exactly 43 characters from `[A-Za-z0-9+/]`, followed by exactly one `=` | 32 bytes |
| Ed25519 signature | Exactly 86 characters from `[A-Za-z0-9+/]`, followed by exactly two `=` | 64 bytes |

Additional rules:

- only the RFC 4648 standard alphabet is accepted;
- `-` and `_` are rejected when they occur (an encoding made only of the
  shared alphabet is indistinguishable from standard Base64);
- embedded or surrounding whitespace is forbidden;
- missing, extra, leading, or non-terminal padding is forbidden;
- trailing characters or concatenated encodings are forbidden;
- decoded length is checked even when the lexical shape was checked; and
- the unused low two pad bits for a 32-byte key and low four pad bits for a
  64-byte signature are **not required to be zero** by released acceptance.

That final rule means multiple strings can decode to the same bytes. A verifier
must not enforce encode-after-decode equality for `ed25519-v1`; doing so would
narrow released behavior. Producers should emit the RFC 4648 canonical form
with zero pad bits, but producer output does not redefine verifier acceptance.
A new keyring format may require canonical pad bits.

### 5.5 Absence, malformed material, and precedence

- File absent: `signature_validity=ABSENT`.
- File present but payload integrity not established:
  `signature_validity=NOT_EVALUATED`; the payload/manifest reason wins.
- File present, payload valid, but any read, UTF-8, JSON, structure, field,
  identifier, Base64, length, or Ed25519 check fails:
  `signature_validity=INVALID` and top-level `SIGNATURE_INVALID`.
- File absent after payload success while `require_signature` or the explicit
  trust-membership requirement is enabled: `SIGNATURE_REQUIRED`.
- Valid signature: `signature_validity=VALID`; this alone leaves
  `trusted_signer_identity=UNESTABLISHED`.

`SIGNATURE_INVALID` precedes `SIGNATURE_REQUIRED`, binding failures,
trust-membership failure, invocation failures, and Freshness failures. A
payload/manifest failure precedes all signature evaluation.

### 5.6 Proposed schema

#### `engine/schemas/verification_keys_v1.json`

- Draft: JSON Schema Draft 7.
- Recommended `$id`: `aelitium://schemas/verification_keys_v1.json`.
- Root object required fields: `keyring_format`, `keys`, `signatures`.
- `keyring_format`: `const: "ed25519-v1"`.
- `keys`: array with `minItems: 1`, `maxItems: 1`; item object requires
  `key_id` and `public_key_b64`.
- `signatures`: array with `minItems: 1`, `maxItems: 1`; item object requires
  `key_id`, `algorithm`, `scope`, and `sig_b64`.
- Both `key_id` values: string with `minLength: 1`.
- `algorithm`: `const: "ed25519"`.
- `scope`: `const: "manifest.json"`.
- Public-key Base64: `minLength: 44`, `maxLength: 44`, pattern
  `^[A-Za-z0-9+/]{43}=$`.
- Signature Base64: `minLength: 88`, `maxLength: 88`, pattern
  `^[A-Za-z0-9+/]{86}==$`.
- `additionalProperties: true` at the root and both entry levels to preserve
  `ed25519-v1` behavior.

Exact cross-entry `key_id` equality, decoded lengths, Base64 decoding,
surrogate-aware legacy equality, and Ed25519 verification remain procedural.
JSON Schema cannot see duplicate source names, BOMs, or raw bytes.

### 5.7 G-05 compatibility classification

| Proposed rule | Classification |
|---|---|
| Optional file; exact one-key/one-signature structure and identifiers | `ALREADY_RELEASED_BEHAVIOR` |
| Strict UTF-8, no leading BOM, one complete source value plus JSON whitespace | `ALREADY_RELEASED_BEHAVIOR` |
| Open root/key/signature objects with ignored extensions | `SAFE_CLARIFICATION` |
| Last-name-wins duplicate members | `SAFE_CLARIFICATION` |
| Preserve legacy non-finites and escaped unmatched surrogates in ignored/opaque positions | `SAFE_CLARIFICATION` |
| Replace configurable integer conversion with a fixed acceptance rule under `ed25519-v1` | `REQUIRES_VERSIONED_CHANGE` |
| Close objects or reject source duplicates under `ed25519-v1` | `WOULD_NARROW_V1` |
| Any non-empty, untrimmed, exact-match `key_id` | `SAFE_CLARIFICATION` |
| Require scalar-only or non-whitespace `key_id` | `WOULD_NARROW_V1` |
| Standard alphabet, exact padding count, no whitespace/garbage, fixed decoded lengths | `ALREADY_RELEASED_BEHAVIOR` |
| Accept non-zero unused pad bits | `SAFE_CLARIFICATION` |
| Require canonical zero pad bits/re-encode equality | `WOULD_NARROW_V1` |
| Introduce a strict closed `ed25519-v2` format | `REQUIRES_VERSIONED_CHANGE` |

G-05 remains not ready because ignored and overwritten extension values still
pass through the configurable legacy integer conversion and because approving
the compatibility-sensitive rules above is a protocol decision, not a
documentation inference.

## 6. G-06 — `aelitium-trust-v1`

### 6.1 Input and source profile

The trust store is an explicit local file supplied for one verification
invocation. There is no ambient path, environment lookup, network lookup,
certificate store, or default trust.

The intended semantic object is closed, but the released source is decoded by
a legacy last-name-wins JSON parser before that closed-object check. The exact
source decision needed is therefore:

- strict UTF-8, no leading BOM;
- exactly one complete JSON value plus JSON whitespace;
- root must parse to an object;
- exact legacy handling of non-finite tokens, numbers, and unmatched
  surrogate escapes;
- final decoded member name wins before semantic validation; and
- closed top-level and signer objects are enforced only on the collapsed
  value.

Calling the resulting behavior “strict JSON” would be misleading. Rejecting
duplicates at source would reject stores that released parsing can accept.
As with G-05, overwritten integer tokens expose G-02's configurable digit
limit and prevent a language-neutral exact profile today.

### 6.2 Exact semantic shape

```json
{
  "trust_store_format": "aelitium-trust-v1",
  "signers": [
    {
      "algorithm": "ed25519",
      "public_key_b64": "<32 raw Ed25519 public-key bytes>",
      "label": "optional non-empty display text"
    }
  ]
}
```

| Location | Rule |
|---|---|
| root | Object with exactly `trust_store_format` and `signers` after map collapse |
| `trust_store_format` | Exact case-sensitive string `aelitium-trust-v1` |
| `signers` | Array; zero or more entries; empty is valid |
| signer | Object with exactly `algorithm`, `public_key_b64`, and optional `label` after map collapse |
| `algorithm` | Required exact string `ed25519` |
| `public_key_b64` | Required Base64 string under section 6.3, decoding to exactly 32 bytes |
| `label` | Optional non-empty string; not trimmed, normalized, or consulted |

An empty signer array is a valid trust store containing no trusted key. It
does not establish membership. Signer order has no effect on membership.
Duplicate labels are allowed because labels are non-authoritative.

The released label check admits whitespace-only strings, noncharacters, and
escaped unmatched surrogates because it tests only decoded-string type and
non-emptiness. A scalar-only or trimmed-label rule would narrow existing input
acceptance. A clean-room implementation can retain such a label as an opaque
legacy string because it never participates in a decision or result.

### 6.3 Base64, key length, and fingerprint

`public_key_b64` uses the 32-byte profile in section 5.4: exactly 43 standard
alphabet characters plus one `=`, no whitespace or garbage, exactly 32 decoded
bytes, with non-zero unused pad bits accepted for v1 compatibility.

The verifier derives, and never reads, the fingerprint:

```text
fingerprint = "ed25519:sha256:" || lowercase_hex(SHA256(raw_public_key))
```

The prefix is not part of the SHA-256 input. The hexadecimal portion is
exactly 64 lowercase ASCII hexadecimal characters. No fingerprint member is
permitted in the store.

Derived fingerprints must be unique. Two records with the same decoded key
are duplicates even if their labels or Base64 spellings differ. Such a store
is invalid. Exact duplicate signer objects, differently labeled copies, and
non-zero-pad-bit aliases are all caught by this one rule.

### 6.4 Trust-membership semantics

Membership is considered only for a mathematically valid bundled signature.
The verified key bytes from that signature are fingerprinted once and compared
for exact string membership in the explicit store's derived set.

| Situation | `trusted_signer_identity` | Top-level behavior |
|---|---|---|
| No store, membership not required | `UNESTABLISHED` | No trust failure |
| Membership required, no store | `UNESTABLISHED` | Immediate `TRUST_INPUT_NOT_PROVIDED` before bundle inspection |
| Supplied store unreadable, malformed, or semantically invalid | `UNESTABLISHED` | `TRUST_STORE_INVALID` before bundle inspection, whether membership is required or optional |
| Valid store, unsigned bundle, no requirement | `UNESTABLISHED` | Signature remains `ABSENT`; no trust failure |
| Valid store, unsigned bundle, membership required | `UNESTABLISHED` | `SIGNATURE_REQUIRED` after payload integrity |
| Invalid bundled signature | `UNESTABLISHED` | `SIGNATURE_INVALID` |
| Valid signature, fingerprint present | `VALID` | Trust membership satisfied |
| Valid signature, fingerprint absent, optional membership | `UNESTABLISHED` | No trust failure |
| Valid signature, fingerprint absent, required membership | `UNESTABLISHED` | `TRUSTED_SIGNER_NOT_FOUND`, subject to earlier signature/binding precedence |

`TRUSTED_SIGNER_NOT_FOUND` requires a valid store and a valid signature. It is
not used for absent or invalid signing material.

Mathematical signature validity does not establish
`trusted_signer_identity`. Trust membership does not establish authorization,
human/legal/organizational identity, provider identity, execution, response
causation, historical occurrence, trusted time, revocation status, or legal
compliance. This format adds no PKI, certificates, expiry, delegation,
revocation, key scope, network lookup, or ambient trust.

### 6.5 Proposed schema

#### `engine/schemas/trust_store_v1.json`

- Draft: JSON Schema Draft 7.
- Recommended `$id`: `aelitium://schemas/trust_store_v1.json`.
- Root object: `additionalProperties: false`; required exactly
  `trust_store_format` and `signers`.
- `trust_store_format`: `const: "aelitium-trust-v1"`.
- `signers`: array with `minItems: 0`; no protocol maximum in this phase.
- Signer object: `additionalProperties: false`; required `algorithm` and
  `public_key_b64`; optional `label`.
- `algorithm`: `const: "ed25519"`.
- `public_key_b64`: `minLength: 44`, `maxLength: 44`, pattern
  `^[A-Za-z0-9+/]{43}=$`.
- `label`: string with `minLength: 1`.
- Do not use `uniqueItems`: uniqueness is by derived fingerprint, not JSON
  structural equality.

Source duplicate handling, legacy string representation, Base64 decoding,
decoded length, fingerprint derivation, and fingerprint uniqueness remain
procedural. The schema cannot describe file encoding, BOMs, raw duplicate
names, or operational limits.

### 6.6 G-06 compatibility classification

| Proposed rule | Classification |
|---|---|
| Explicit local-only store; exact top-level and signer members after collapse | `ALREADY_RELEASED_BEHAVIOR` |
| Strict UTF-8, no leading BOM, one complete source value plus JSON whitespace | `ALREADY_RELEASED_BEHAVIOR` |
| Empty signer array is valid | `SAFE_CLARIFICATION` |
| Duplicate derived fingerprints invalidate the store | `ALREADY_RELEASED_BEHAVIOR` |
| Last-name-wins source duplicates before closed-object validation | `SAFE_CLARIFICATION` |
| Preserve legacy non-finites and escaped unmatched surrogates until collapsed semantic validation | `SAFE_CLARIFICATION` |
| Replace configurable integer conversion with a fixed acceptance rule under `aelitium-trust-v1` | `REQUIRES_VERSIONED_CHANGE` |
| Reject all source duplicates under `aelitium-trust-v1` | `WOULD_NARROW_V1` |
| Optional non-empty opaque label with no normalization | `ALREADY_RELEASED_BEHAVIOR` |
| Require scalar-only, trimmed, or non-whitespace label | `WOULD_NARROW_V1` |
| 32-byte Base64 profile accepting non-zero pad bits | `SAFE_CLARIFICATION` |
| Require canonical zero pad bits | `WOULD_NARROW_V1` |
| Add fingerprint, PKI, expiry, revocation, or delegation fields | `REQUIRES_VERSIONED_CHANGE` |
| Introduce strict duplicate-rejecting `aelitium-trust-v2` | `REQUIRES_VERSIONED_CHANGE` |

G-06 remains not ready until the legacy auxiliary source profile and the
duplicate/Base64 compatibility decisions are explicitly approved.

## 7. Cross-contract reason mapping and precedence

No new public verification reason is necessary for the designed closure.
Lower-level schema diagnostics remain non-normative detail.

| Condition | Existing public reason |
|---|---|
| Manifest source/profile invalid | `MANIFEST_NOT_JSON` |
| Manifest root not object | `MANIFEST_NOT_OBJECT` |
| Required manifest member absent | `MANIFEST_MISSING_FIELD` |
| Bad manifest schema identifier | `MANIFEST_BAD_SCHEMA` |
| Bad payload-schema identifier | `MANIFEST_BAD_INPUT_SCHEMA` |
| Bad/unsupported route identifier after legacy error resolution | `MANIFEST_BAD_CANONICALIZATION` |
| Enabled manifest timestamp syntax invalid | `MANIFEST_BAD_TS_UTC` |
| Manifest payload hash spelling invalid | `MANIFEST_BAD_AI_HASH_SHA256` |
| Present keyring fails any read/source/schema/semantic/cryptographic check | `SIGNATURE_INVALID` |
| Signature evidence absent while signature or membership is required | `SIGNATURE_REQUIRED` |
| Membership required with no supplied trust path | `TRUST_INPUT_NOT_PROVIDED` |
| Supplied trust store fails read/source/schema/semantic validation | `TRUST_STORE_INVALID` |
| Required membership absent for a valid signature and valid store | `TRUSTED_SIGNER_NOT_FOUND` |

The top-level ordering relevant to this phase is:

1. `TRUST_INPUT_NOT_PROVIDED`;
2. `TRUST_STORE_INVALID`;
3. Freshness policy-input failure;
4. missing canonical, then missing manifest;
5. canonical parsing;
6. selected manifest parsing/object/fields in section 4.5;
7. canonical schema/Unicode/bytes/hash;
8. `SIGNATURE_INVALID`;
9. `SIGNATURE_REQUIRED`;
10. binding failure, then required-binding absence;
11. `TRUSTED_SIGNER_NOT_FOUND`;
12. invocation and Freshness evidence failures.

This is a scoped precedence map, not closure of G-08's exhaustive reason and
assurance-state registry. Operational/resource failures remain G-09 and must
not be manufactured as semantic JSON or schema reasons.

## 8. Schema design summary

The future implementation phase should propose exactly these four files after
the compatibility blockers are resolved:

| File | Draft | `$id` | Object policy |
|---|---|---|---|
| `engine/schemas/ai_manifest_v1.json` | Draft 7 | `aelitium://schemas/ai_manifest_v1.json` | Open root; v1 source behavior procedural |
| `engine/schemas/ai_manifest_v2.json` | Draft 7 | `aelitium://schemas/ai_manifest_v2.json` | Open root; strict v2 profile procedural |
| `engine/schemas/verification_keys_v1.json` | Draft 7 | `aelitium://schemas/verification_keys_v1.json` | Open root and entries for released compatibility |
| `engine/schemas/trust_store_v1.json` | Draft 7 | `aelitium://schemas/trust_store_v1.json` | Closed root and signer entries after source map collapse |

The implementation must not run a generic whole-object schema validator and
use the validator's first error as the public reason. It must execute the
contract's ordered procedural checks and use schemas as structural constraints.

Rules necessarily outside JSON Schema include:

- source bytes, UTF-8, BOM, whole-document and whitespace rules;
- duplicate source names and decoded-name comparison;
- legacy non-finite, surrogate, and arbitrary-integer parsing;
- dispatch and original-byte handoff;
- timestamp validation controlled by an external option;
- public reason order;
- Base64 decoded length and current non-zero-pad-bit acceptance;
- cross-entry `key_id` equality;
- exact raw signature message and Ed25519 mathematics;
- derived fingerprint calculation and uniqueness; and
- filesystem, snapshot, recursion, allocation, and size-limit behavior.

## 9. IMPLEMENTATION CROSS-CHECK

**IMPLEMENTATION CROSS-CHECK — non-normative.** This inspection occurred only
after sections 2 through 8 were derived from public contracts and frozen data.
The files and probes below are evidence of specification gaps or compatibility
risk; they are not incorporated as protocol authority.

### 9.1 Manifest findings

- The manifest route in `engine/ai_verify.py` accepts unknown members without
  semantics.
- Legacy parsing uses `json.loads` after strict UTF-8 decoding and text-style
  CR/CRLF newline conversion. It accepts the three non-finite constants,
  collapses duplicate decoded names last-wins, and retains unmatched surrogate
  escapes.
- A bad earlier duplicate followed by valid `schema` verifies; a bad final
  duplicate returns `MANIFEST_BAD_SCHEMA`.
- A legacy unknown `NaN` or unmatched surrogate verifies when all governed
  fields are otherwise valid.
- BOM and trailing non-whitespace return `MANIFEST_NOT_JSON`; trailing JSON
  whitespace is accepted.
- The timestamp expression is
  `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$` evaluated with Python regex
  defaults. Probes accepted Arabic-Indic decimal digits, out-of-range
  components, year/month/day zero, second `60`, and exactly one final decoded
  LF. Final CR and two LFs failed.
- With timestamp validation disabled, a required `ts_utc` object value passed;
  only member presence remained.
- V2 parsing independently matches the already published recursive profile.

The Unicode `\d` set follows the host Unicode database. Because supported
Python versions need not use the same database, reproducing the regex spelling
is not a portable definition.

### 9.2 Keyring findings

- `verification_keys.json` is decoded with legacy `json.loads` independently
  of the manifest canonicalization route.
- Unknown root, key-entry, and signature-entry members are ignored.
- Duplicate decoded names collapse last-wins before signing checks.
- Whitespace-only and unmatched-surrogate `key_id` values verify when the two
  entries match and the signature is otherwise valid.
- The decoder is `base64.b64decode(..., validate=True)`. It rejects whitespace,
  URL-only alphabet characters, missing/extra padding, and trailing garbage,
  but accepts non-zero unused pad bits. Probes changed only those pad bits in a
  valid key or signature and cryptographic verification still succeeded.
- Every parse, structure, identifier, Base64, length, and mathematical failure
  is caught as top-level `SIGNATURE_INVALID` after payload integrity.

### 9.3 Trust-store findings

- Top-level and signer objects are closed only after ordinary `json.loads`
  map collapse. Exact and escaped duplicate names are therefore last-wins,
  despite the public description “strict”.
- An empty signer list is valid.
- Unknown top-level and signer fields are rejected after collapse.
- Labels are checked only for non-empty string type; an unmatched-surrogate
  label passed.
- The key decoder has the same non-zero-pad-bit acceptance as the keyring.
- Duplicate derived fingerprints are rejected even when the Base64 spellings
  differ only in unused pad bits.
- BOM is a JSON failure; trailing JSON whitespace is accepted; malformed UTF-8
  is normalized to the public `TRUST_STORE_INVALID` path.
- Store loading occurs before bundle-file inspection, and the public layer
  collapses every lower store reason to `TRUST_STORE_INVALID`.

### 9.4 Cross-check discrepancies requiring review

| Public wording/intention | Observed behavior | Why it cannot be copied silently |
|---|---|---|
| Manifest timestamp resembles an ASCII whole-string timestamp | Unicode decimal digits and one decoded final LF are accepted | Tightening narrows v1; copying `\d` leaves a host-version dependency |
| “Strict standard Base64” | Alphabet/padding are strict but unused pad bits need not be zero | Re-encode equality would reject released-compatible inputs |
| Keyring shape is described but closure is unspecified | All three object levels are open after last-name-wins parsing | Closing or duplicate rejection narrows signed bundles |
| Trust store is called strict and closed | It is closed only after last-name-wins map collapse | Source duplicate rejection narrows supplied trust inputs |
| Strings are assumed portable | Key IDs and labels can retain unmatched surrogate escapes | Scalar-only validation narrows inputs; Go needs an opaque legacy representation |
| JSON parsing is treated as a semantic failure | Overwritten/ignored huge integers can fail or pass according to CPython's configured digit limit | This is G-02/G-09-adjacent host behavior, not a deterministic grammar |

## 10. Future conformance design

The existing 44-, 30-, and 114-case corpora must remain unchanged. Add a
separate future corpus, for example:

```text
conformance/verifier_contract_phase2/
  manifest.json
  source_vectors.json
  schema_vectors.json
  semantic_vectors.json
  fixtures/
```

Every case should freeze original source bytes (hex), any companion artifact
bytes, selected dispatch route, options, expected parser/schema decision,
expected top-level reason, relevant assurance states, and exact raw signature
message digest. Expected bytes must not be generated at runtime by the
production parser.

### 10.1 Source-parsing vectors

Manifest families:

- v1 and v2 valid leading/trailing JSON whitespace;
- leading BOM, malformed UTF-8, trailing garbage, second top-level value;
- non-object roots;
- exact and escaped duplicate required names, with valid first/final variants;
- nested duplicates and duplicates in unknown extensions;
- exact legacy `NaN`, `Infinity`, `-Infinity` in unknown fields;
- malformed/lowercase/plus-sign non-finite spellings;
- valid surrogate pair, unmatched/reversed surrogate, and noncharacter in an
  unknown extension;
- large ignored and overwritten integer tokens under every supported legacy
  digit profile; and
- the same strict-invalid forms with an exact final v2 selector.

Keyring and trust-store source families:

- BOM, malformed UTF-8, JSON whitespace, trailing garbage, multiple values;
- root wrong type;
- exact and escaped duplicates at every object level;
- non-finite and unmatched-surrogate values in governed, ignored, and
  overwritten positions; and
- huge integers in ignored/overwritten positions under explicit digit-limit
  configurations.

### 10.2 Schema vectors

Manifest:

- each required field missing individually and multiple missing fields to
  freeze presence order;
- every required field with null, Boolean, number, array, and object values;
- bad exact identifiers;
- unknown valid fields;
- `ai_hash_sha256` at 63/64/65 characters, uppercase, non-hex, and non-string;
- optional `binding_hash` absent, valid, malformed, and partial quartet;
- enabled/disabled timestamp validation with non-string values; and
- timestamp spelling cases: ASCII exact, every separator wrong, Unicode
  decimal digits, component values `00`, `60`, and `99`, final decoded LF,
  CR, CRLF, two LF, prefix/suffix, and embedded LF.

Keyring:

- every required root/entry field missing;
- wrong root, array, entry, and field types;
- zero/two keys and zero/two signatures;
- unknown fields at all three object levels;
- empty, whitespace-only, non-BMP, and unmatched-surrogate key IDs;
- mismatched key IDs;
- bad algorithm and bad scope; and
- Base64 standard/URL alphabets, whitespace, padding positions/counts,
  non-zero pad bits, trailing garbage, and 31/32/33 or 63/64/65 decoded bytes.

Trust store:

- missing/extra top-level members and wrong format;
- signers wrong type, empty, one, and multiple;
- signer wrong type, missing required fields, extra fields, bad algorithm;
- label absent, empty, whitespace-only, non-BMP, noncharacter, and unmatched
  surrogate;
- the complete 32-byte Base64 matrix; and
- exact duplicate keys, differently labeled duplicates, pad-bit aliases, and
  distinct keys.

### 10.3 Semantic verification vectors

- a valid Ed25519 signature over exact raw manifest bytes;
- signature failure after changing only whitespace, order, escape spelling,
  terminal LF, public key, or signature;
- absent keyring with no requirement, signature requirement, and membership
  requirement;
- malformed keyring combined with payload/hash/binding failures to freeze
  precedence;
- valid store with present, absent, and invalid signatures;
- valid signature with matching and unknown store key, optional and required;
- no trust input while membership is required;
- missing/unreadable/malformed/invalid store, both optional and required;
- empty store with valid signature, optional and required;
- binding failure combined with unknown required signer to preserve binding
  precedence; and
- signature failure combined with invalid binding/Freshness to preserve
  signature precedence.

## 11. Compatibility decision gate

Before schemas or public protocol text are implemented, reviewers must decide
all of the following explicitly:

1. the exact v1 timestamp digit code-point set and whether to preserve its
   single-final-LF acceptance;
2. whether a fixed portable rule can replace host-dependent integer conversion
   in ignored/overwritten manifest, keyring, and trust-store values under the
   existing identifiers;
3. whether `ed25519-v1` remains open and last-name-wins or a new format is
   introduced;
4. whether `aelitium-trust-v1` preserves last-name-wins source duplicates or a
   new strict format is introduced;
5. whether non-zero unused Base64 pad bits remain accepted in the existing
   formats; and
6. whether unmatched-surrogate key IDs and labels remain opaque accepted
   legacy strings or require new format versions.

The compatibility-preserving recommendation is to document the current
open/last-name-wins object policies and Base64 alias acceptance under existing
identifiers, and reserve strict duplicate/scalar/canonical-Base64 rules for new
identifiers. That recommendation still cannot settle the host-dependent
integer and Unicode-digit domains without an explicit compatibility decision.

No new public reason is required. If reviewers choose an operational refusal
for a legacy host-dependent domain, that work belongs to G-02/G-09 and must not
be disguised as `MANIFEST_NOT_JSON`, `SIGNATURE_INVALID`, or
`TRUST_STORE_INVALID` without separate authorization.

## 12. Final gap status

- G-04: not ready; publish a fixed v1 timestamp/source compatibility rule
  before creating normative manifest schemas.
- G-05: not ready; approve the released open/duplicate/Base64 profile or
  version the keyring before creating its normative schema.
- G-06: not ready; approve the source duplicate/string/Base64 profile or
  version the trust store before creating its normative schema.

The proposed four schemas and three conformance families are otherwise
sufficient to implement the closure without using Python as an unstated
oracle once those decisions are made.

VERIFIER_CONTRACT_PHASE2_DESIGN_NOT_READY
