# AELITIUM Legacy v1 Compatibility and Operational Policy v1

**Status:** NORMATIVE-UNRELEASED

**Contract:** `aelitium-legacy-v1-compatibility-operational-policy-v1`

**Scope:** verifier capability, legacy-v1 portability, operational outcomes,
resource limits, direct-filesystem acquisition, and immutable input snapshots

This document closes independent-verifier gaps G-02 and G-09. It is a Level 1
contract under [`VERIFIER_PROTOCOL_V1.md`](VERIFIER_PROTOCOL_V1.md). It does
not change released AELITIUM v0.4.0 behavior, redefine
`json_sorted_keys_no_whitespace_utf8`, implement this contract in the Python
CLI, or assert that an independent verifier exists.

## 1. Normative interpretation and compatibility

The requirement words “must”, “must not”, “required”, “should”, and “may” are
normative. Contract identifiers, enum values, field names, algorithms, and
frozen data referenced here are case-sensitive.

This policy adds a qualification and transport around semantic verification;
it does not add a field to an evidence bundle and does not alter
`aelitium-verification-result-v1`. Its compatibility rules are:

- verifier capability is configuration and output metadata, never evidence;
- insufficient capability is not evidence invalidity;
- an operational inability to evaluate is not a semantic result;
- an operational condition must not be mapped to an AELITIUM semantic reason
  unless the verifier actually established that semantic condition;
- portable refusal does not narrow the set of artifacts that some released
  v0.4.0 runtime configuration can evaluate; and
- named compatibility reproduces an explicitly declared historical runtime
  profile without making that profile the universal meaning of v1.

The Python implementation, a host Unicode library, a host recursion limit, and
ambient machine resources are not normative inputs. An implementation-specific
failure discovered outside this contract is a specification or implementation
defect; it must not be copied as an unstated compatibility rule.

## 2. Semantic results and operational outcomes

### 2.1 Hard boundary

A **semantic result** exists only after the verifier has sufficient declared
capability, has acquired one stable immutable input snapshot, and has enough
resources to reach an AELITIUM decision under the selected contract and its
published precedence. The result is an unchanged
`aelitium-verification-result-v1` object with status `VALID` or `INVALID`.

An **operational outcome** means no AELITIUM semantic result was established.
It applies when the requested capability is unavailable, a reached value lies
outside the declared capability, input acquisition or snapshot stability
fails, an advertised operational limit is exceeded, or the implementation
cannot complete.

An operational outcome has all of these properties:

- it has no `VALID` or `INVALID` status;
- it has no AELITIUM semantic verification `reason`;
- `verification_result` is null;
- no assurance result or partial assurance object exists;
- no comparison result exists;
- it cannot be used as a verified input to comparison; and
- it cannot change dispatch selection or trigger a version retry.

In particular, operational inability must not be serialized as
`MANIFEST_NOT_JSON`, `SIGNATURE_INVALID`, `TRUST_STORE_INVALID`,
`HASH_MISMATCH`, or any other semantic reason. Malformed stable bytes are
different: when the applicable parser has sufficient capability and resources,
its authorized semantic reason applies.

Stable absence is also different. A stable snapshot may establish an existing
missing-artifact semantic reason. A path that is present and then disappears or
changes during acquisition is operational and cannot establish stable absence.

### 2.2 Boundary order

Checks occur at the boundary they protect:

1. Reject an unavailable explicitly requested capability before reading bundle
   content.
2. Apply explicit-input precedence that can be resolved before bundle
   acquisition, including required trust-input and Freshness-option structure.
3. Acquire a supplied trust input at its published precedence position.
4. Establish stable presence or absence for the known bundle roles.
5. Acquire every present role into one immutable operation snapshot.
6. Run `AELITIUM-DISPATCH-JSON-1` without numeric conversion.
7. Apply a selected parser's capability checks only as left-to-right traversal
   reaches the relevant token or decoded timestamp.
8. Return the first completely established semantic result, or the operational
   outcome that prevented that phase from completing.

When multiple conditions are observable at the same acquisition boundary,
order is deterministic: establish the bundle-root input mode first; acquire a
separately supplied trust store next; then process `AI_CANONICAL_JSON`,
`AI_MANIFEST_JSON`, and `VERIFICATION_KEYS_JSON` in that order within each
initial-observation/type pass, byte-acquisition pass, and final-stability pass.
Within one role, the first failed step of section 12.2 controls. Aggregate size
is evaluated after all present roles have passed initial type/length checks and
before their content is semantically evaluated.

This order does not move a later capability check ahead of an earlier semantic
failure. For example, an established malformed canonical payload retains its
precedence over an extreme integer that would only be reached later in a v1
manifest. Input acquisition failure can precede all content semantics because
no stable byte input exists.

## 3. Capability registry

Capability identifiers describe verifier ability. They do not negotiate or
change the evidence contract.

| Identifier | Exact capability | Portability | Outside-capability behavior |
|---|---|---|---|
| `V2_PORTABLE` | Complete `aelitium_jcs_profile_v2` semantics within effective operational limits | Portable | Operational limit/exhaustion; v2 profile violations remain semantic |
| `V1_RESTRICTED_PORTABLE` | The restricted v1 value domain in `CANONICALIZATION_SPEC.md`, integer magnitudes through 640 digits, and ASCII timestamp digits | Portable | `INPUT_OUTSIDE_DECLARED_CAPABILITY` |
| `V1_FROZEN_LEGACY_COMPATIBILITY` | Complete deterministic released-v1 behavior in section 7, including its legacy value forms, with the same 640-digit and ASCII-timestamp bounds | Portable | `INPUT_OUTSIDE_DECLARED_CAPABILITY` |
| `V1_NAMED_RUNTIME_COMPATIBILITY` | Deterministic legacy rules plus an explicit integer-conversion profile and one frozen Unicode `Nd` profile | Language-neutral emulation of the declared profile | Declared profile result or operational outcome as sections 5 and 6 require |
| `V1_LEGACY_UNSUPPORTED` | No legacy/error-resolution evaluator | No v1 coverage | `CAPABILITY_PROFILE_UNAVAILABLE` if dispatch reaches the legacy route |

The former design spelling `V1_CPYTHON_DIGIT_PROFILE(n)` is not a public
identifier because an integer limit alone omits timestamp and operational
parameters. The public replacement is a complete
`V1_NAMED_RUNTIME_COMPATIBILITY` declaration. The design's numeric value `0`
for a disabled guard is replaced by the explicit `UNLIMITED` object in section
4.2; the two have the same intended compatibility meaning.

A verifier should normally provide `V2_PORTABLE` and
`V1_FROZEN_LEGACY_COMPATIBILITY`. It may additionally provide the restricted,
named-runtime, or unsupported v1 declarations. It must never advertise an
unqualified “full v1” capability.

Capability belongs in explicit CLI/API configuration, a static verifier
capabilities declaration, every outer operation result, and the implementation's
conformance declaration. It must not be inferred from a language version,
environment variable, locale, host Unicode database, current memory, or stack
limit. It must not be placed inside an evidence bundle.

## 4. Exact capability declaration

### 4.1 Operation request

The `capability.requested` member of `aelitium-verifier-tool-result-v1` contains
exactly a dispatch identifier and one configured declaration for each route:

```json
{
  "dispatch": "AELITIUM-DISPATCH-JSON-1",
  "v1": {
    "capability": "V1_FROZEN_LEGACY_COMPATIBILITY",
    "integer_conversion": {
      "mode": "BOUNDED",
      "maximum_decimal_digits": 640
    },
    "timestamp_digit_profile": "ASCII",
    "timestamp_final_lf": "ACCEPT_ONE"
  },
  "v2": {
    "capability": "V2_PORTABLE"
  }
}
```

`V1_RESTRICTED_PORTABLE` has the same fixed integer and timestamp fields.
`V1_LEGACY_UNSUPPORTED` contains only its `capability` member.

For every semantic result and every operational result other than
`CAPABILITY_PROFILE_UNAVAILABLE`, `capability.effective` must be deeply equal to
`capability.requested`. `CAPABILITY_PROFILE_UNAVAILABLE` requires
`capability.effective=null`; the rejected request remains present. This
equality is a prose invariant because JSON Schema Draft 7 cannot compare two
arbitrary subtrees.

An implementation that cannot load or authenticate a requested frozen profile
returns `CAPABILITY_PROFILE_UNAVAILABLE` at `CAPABILITY_SELECTION` before
opening bundle content. `V1_LEGACY_UNSUPPORTED` is evaluated only after dispatch:
an exact v2 selector still uses `V2_PORTABLE`; a legacy/error-resolution route
returns `CAPABILITY_PROFILE_UNAVAILABLE` at `DISPATCH`.

### 4.2 Named-runtime declaration

`V1_NAMED_RUNTIME_COMPATIBILITY` contains exactly:

```json
{
  "capability": "V1_NAMED_RUNTIME_COMPATIBILITY",
  "integer_conversion": {
    "mode": "BOUNDED",
    "maximum_decimal_digits": 4300
  },
  "timestamp_digit_profile": {
    "profile_id": "AELITIUM_UCD_ND_15_0_0_1",
    "range_file_sha256": "0f10e369beb834ccee109f3ccc8d75f6ff8067871baf7109a106f1dac7430222",
    "unicode_version": "15.0.0"
  },
  "timestamp_final_lf": "ACCEPT_ONE"
}
```

The integer object is one of:

- `{"mode":"BOUNDED","maximum_decimal_digits":N}`, where `N` is an
  integer at least 640; or
- `{"mode":"UNLIMITED","maximum_decimal_digits":null}`.

`UNLIMITED` disables only the historical decimal conversion guard. It does not
promise unlimited file size, token storage, memory, occurrences, depth, or
execution time. A named profile is the complete parameter tuple, not the phrase
“CPython compatible”. A non-Python implementation reproduces it directly from
these published values and frozen data. Any runtime-family label outside this
object is descriptive only and cannot replace a field or digest.

## 5. G-02 integer compatibility

### 5.1 Measured token domain

An **integer-form token** is a legacy-route JSON number token with no fraction
and no exponent. Its magnitude-digit count is the count of ASCII decimal digits
in the token; an optional leading minus sign is excluded. RFC 8259's integer
grammar already excludes redundant leading zeroes. Fractional and exponent-form
tokens use the established v1 binary64 path and are not subject to this guard.

The source conversion/capability rule applies to every reached integer-form
occurrence before duplicate collapse or field semantics, including:

- governed values;
- ignored extension values;
- earlier values overwritten by a duplicate decoded member name;
- canonical payload, manifest, verification-key, and trust-store sources; and
- direct structured input/result integers when an interface accepts an exact
  arbitrary-precision value.

Dispatch is excluded. `AELITIUM-DISPATCH-JSON-1` skips numeric tokens lexically,
performs no conversion, and applies no digit limit.

### 5.2 Portable boundary

Every v1 portable capability must retain and convert exactly any reached
integer-form token containing at most 640 magnitude digits. A reached token of
641 or more digits is outside `V1_RESTRICTED_PORTABLE` and
`V1_FROZEN_LEGACY_COMPATIBILITY`. The operation returns
`INPUT_OUTSIDE_DECLARED_CAPABILITY` with limit name
`INTEGER_DECIMAL_DIGITS`; it must not emit `INVALID` or a source-specific JSON
reason.

The 640 boundary is a portable capability floor, not a semantic maximum for
`json_sorted_keys_no_whitespace_utf8`. More than 640 digits is not automatically
invalid evidence. A larger advertised byte/resource limit does not silently
expand portable-v1 semantics.

For a programmatic arbitrary-precision integer, apply the same count before
canonicalization or result serialization. An interface that cannot retain the
value exactly before this check does not provide the declared capability.

### 5.3 Named-runtime boundary

For a named `BOUNDED` profile at `N`:

- a token with at most `N` magnitude digits is converted exactly;
- a token with more than `N` reproduces the applicable legacy source-parse
  result at its published precedence position; and
- an actual allocation/resource failure while handling an in-profile token is
  `RESOURCE_EXHAUSTED`, not a source-parse result.

The profile-relative source mappings are:

| Reached source | Token has more than `N` digits | Existing named-profile result |
|---|---|---|
| `ai_canonical.json` | conversion guard rejects | `CANONICAL_NOT_JSON` |
| `ai_manifest.json`, after legacy routing | conversion guard rejects | `MANIFEST_NOT_JSON` |
| present `verification_keys.json` | conversion guard rejects | `SIGNATURE_INVALID` |
| supplied trust store | conversion guard rejects | `TRUST_STORE_INVALID` |

These are profile-qualified compatibility results. They are not portable claims
that the bytes are intrinsically invalid, and they may be exposed only inside
the outer transport containing the exact named profile. A bare inner result
must not be detached and presented as a universal v1 decision.

For `UNLIMITED`, every token within the effective byte/resource envelope is
converted exactly. For a direct language-level integer no source parse event
exists; a value above a bounded `N` is operationally outside capability rather
than one of the four source reasons.

The frozen boundary matrix is:

| Magnitude digits | Portable | Named 640 | Named 4300 | Named unlimited |
|---:|---|---|---|---|
| 640 | evaluate | evaluate | evaluate | evaluate |
| 641 | operational refusal | profile-relative parse failure | evaluate | evaluate |
| 4300 | operational refusal | profile-relative parse failure | evaluate | evaluate |
| 4301 | operational refusal | profile-relative parse failure | profile-relative parse failure | evaluate |
| 10000 | operational refusal | profile-relative parse failure | profile-relative parse failure | evaluate if effective resources suffice |

For arbitrary `N`, the boundary is exactly `N`/`N+1`. A final v2 selector always
selects v2 even when a 10,000-digit token occurs elsewhere in the manifest. The
fresh v2 parser applies the v2 number profile and never retries v1.

## 6. Timestamp compatibility and frozen Unicode data

### 6.1 Shared legacy shape

When manifest timestamp validation is enabled, the decoded v1 string must have
exactly this shape:

```text
DDDD-DD-DDTDD:DD:DDZ[LF]
```

There are fourteen `D` positions. The displayed ASCII separators are literal
and case-sensitive. `[LF]` means zero or one final decoded U+000A after `Z`.
A final U+000D, U+000D U+000A, two final U+000A characters, an embedded U+000A,
or any other suffix fails. A raw line feed remains illegal within JSON source;
the compatibility case is a decoded character, for example from `\n`.

This is lexical validation only. It does not enforce calendar ranges, leap
years, leap seconds, chronology, or historical occurrence. It does not close
Freshness G-11. With `validate_manifest_timestamp=false`, only the established
`ts_utc` member-presence rule remains; v1 performs no type/spelling check, while
source parsing and all other manifest rules still apply.

### 6.2 Portable ASCII profile

For portable v1 capabilities, every `D` is ASCII U+0030 through U+0039.
Evaluation order is:

1. require a string and validate length, separators, and zero-or-one final LF;
2. for each digit position, an ASCII non-digit is `MANIFEST_BAD_TS_UTC`;
3. a non-ASCII code point in a digit position is
   `INPUT_OUTSIDE_DECLARED_CAPABILITY`; and
4. ASCII digits pass the lexical timestamp check.

A non-ASCII character outside a digit position is a semantic separator/suffix
mismatch, not a digit-profile issue.

### 6.3 Named frozen `Nd` profiles

A named profile replaces only the digit-membership test with one immutable
Unicode General Category `Nd` table. It does not use the host regex engine or
Unicode library. A code point outside the selected frozen table produces the
profile-relative semantic result `MANIFEST_BAD_TS_UTC`.

The normative registry is
[`../conformance/legacy_v1_operational_policy/unicode/profiles.json`](../conformance/legacy_v1_operational_policy/unicode/profiles.json).
It publishes these exact tuples:

| Profile | Unicode version | Range-file SHA-256 | Code points |
|---|---|---|---:|
| `AELITIUM_UCD_ND_13_0_0_1` | 13.0.0 | `bf287074b61dbb4a03a10645580b5ae0d1e106d75aa6c26881a7a277712c4f8b` | 650 |
| `AELITIUM_UCD_ND_14_0_0_1` | 14.0.0 | `5a75c753790a222c430dbfc95adaa2c3ec6701862d1728eae92d9ed0e2df59c8` | 660 |
| `AELITIUM_UCD_ND_15_0_0_1` | 15.0.0 | `0f10e369beb834ccee109f3ccc8d75f6ff8067871baf7109a106f1dac7430222` | 680 |

`AELITIUM-UNICODE-ND-RANGES-1` is ASCII text with no BOM or CR. Each line is
exactly six uppercase hexadecimal digits, `..`, six uppercase hexadecimal
digits, and LF. Ranges are inclusive, ascending, non-overlapping, and maximally
coalesced; the final line has LF. SHA-256 covers the complete range-file bytes.
Membership means that the scalar code point lies in an inclusive range.

The source archives and extracted source-file digests in the registry are
provenance. The frozen range bytes and their public digest are normative. The
maintenance audit script is not normative authority and never consults the host
Unicode database. If a required range file is absent or its digest/metadata does
not match the selected tuple, the capability is unavailable; the verifier must
not silently substitute another Unicode version.

The derived data is redistributed under the included Unicode License v3. Later
Unicode versions or corrected property data do not change these profiles
automatically; adoption requires the update process in
`VERIFIER_PROTOCOL_V1.md` and a new profile identifier when membership changes.

## 7. Deterministic portable legacy rules

Host dependence is not a reason to refuse behavior that is reproducible
cross-language. `V1_FROZEN_LEGACY_COMPATIBILITY` and
`V1_NAMED_RUNTIME_COMPATIBILITY` implement these rules:

| Rule | Required compatibility behavior |
|---|---|
| Duplicate decoded object names | Process occurrences left to right and retain the final value before semantic field validation; exact and escaped-equivalent names are equal |
| Exact legacy constants | Accept only case-sensitive `NaN`, `Infinity`, and `-Infinity` tokens in the legacy source grammar and preserve their already-specified location/serialization consequences |
| Escaped unmatched surrogates | Retain opaque UTF-16 code units in legacy positions where the established contract permits them; do not manufacture Unicode scalar validity or v2 acceptance |
| Base64 unused pad bits | For established fixed legacy Base64 shapes, accept a standard-alphabet/padding spelling that decodes to the required length even when unused final quantum bits are non-zero; do not require encode-after-decode equality |
| Unknown/open members | Apply the location-specific G-04/G-05/G-06 policy after last-name-wins collapse; accepted unknown members acquire no verification, assurance, trust, or comparison meaning |
| Empty trust members | An empty `signers` array is a structurally valid trust store with no trust membership |
| Final timestamp LF | Accept exactly the zero-or-one decoded LF rule in section 6 |

`V1_RESTRICTED_PORTABLE` treats a reached legacy constant, permitted opaque
surrogate, or other value outside its published restricted domain as
`INPUT_OUTSIDE_DECLARED_CAPABILITY`. A surrogate spelling that the applicable
legacy contract already rejects is still a semantic source/value failure; only
a legacy-permitted opaque value is outside the restricted capability.

Rules in the table that do not expand the restricted value domain—decoded-name
last-wins processing, Base64 pad-bit aliases, accepted open members, empty trust
membership, and the final timestamp LF—also apply to
`V1_RESTRICTED_PORTABLE`. Values recursively contained in those structures
must still remain inside its scalar/finite/640-digit/ASCII-timestamp domain.
Thus the restricted and frozen profiles differ on excluded legacy value forms,
not on whether an ordinary in-domain duplicate or open member is silently
reinterpreted. These rules preserve accepted legacy input; they do not endorse
it as producer output. Exact field grammars and source positions remain
G-04/G-05/G-06 and are not duplicated here.

## 8. Operational result transport

### 8.1 Contract and schema

The outer contract is `aelitium-verifier-tool-result-v1`, defined by
[`../engine/schemas/verifier_tool_result_v1.json`](../engine/schemas/verifier_tool_result_v1.json).
It wraps one `VERIFY_BUNDLE` operation and contains exactly:

- `contract`;
- `operation`;
- `outcome`;
- `rc`;
- `input_mode`;
- `capability` with `requested` and `effective` declarations;
- `limits` with claimed, advertised, and effective values;
- `verification_result`, which is the unchanged existing semantic result or
  null; and
- `operational_result`, which is the operational object or null.

`SEMANTIC_RESULT` requires rc 0 or 2, a correspondingly valid/invalid
`aelitium-verification-result-v1`, and null `operational_result`.
`OPERATIONAL_OUTCOME` requires rc 3, null `verification_result`, and one
operational object. The strict schema has no assurance or comparison-result
slot outside the semantic verification object, making a fabricated partial
semantic result structurally invalid.

The schema's `$ref` value `aelitium-verification-result-v1` resolves to the
Level 1 schema with that exact `$id`. It does not copy or revise the inner
schema. The schema enforces the result branches, closed values, minimum-floor
claims, and its code/phase/ref/limit relations. This prose additionally
requires capability deep equality and `effective` limits no greater than their
corresponding `advertised` limits because Draft 7 cannot compare arbitrary
member values.

### 8.2 Machine-readable bytes

An outer-result byte mode serializes the schema-valid value using RFC 8785
section 3.2, then appends exactly one LF. All tool-result numbers are integers
within the portable-v2 safe range, and all tool-result strings must satisfy the
portable-v2 Unicode profile. The LF is a transport delimiter, not part of the
JSON value. Repeated evaluation of the same immutable inputs, configuration,
and injected operational event must emit identical bytes except for optional
non-normative `detail`; conformance vectors set `detail` to null.

An implementation may expose this as `--operation-json`. Existing inner
`--contract-json`/JSON surfaces must not emit counterfeit semantic JSON on an
operational outcome. Section 10 fixes their process/stderr behavior without
claiming the current Python CLI already implements it.

## 9. Closed operational registry

### 9.1 Operational codes

`operational_code` is exactly one of:

| Code | Exact use |
|---|---|
| `CAPABILITY_PROFILE_UNAVAILABLE` | Requested capability/profile or requested input mode is unimplemented, or required frozen profile data is absent or unauthenticated; also used after legacy dispatch when v1 is explicitly unsupported |
| `INPUT_OUTSIDE_DECLARED_CAPABILITY` | Reached content is outside the selected restricted capability, such as a 641-digit v1 integer or a non-ASCII timestamp digit under an ASCII profile |
| `RESOURCE_LIMIT_EXCEEDED` | A measured source, aggregate snapshot, structural depth, or value-occurrence property exceeds an effective advertised limit |
| `RESOURCE_EXHAUSTED` | Allocation, address space, stack, descriptor, or equivalent resource prevents completion before an advertised input limit |
| `INPUT_IO_ERROR` | Metadata, open, permission, or read operation fails without establishing a more specific type/stability outcome |
| `INPUT_NOT_REGULAR_FILE` | Direct bundle root is ineligible, or a direct input role is a symlink or non-regular file |
| `INPUT_CHANGED_DURING_SNAPSHOT` | Presence, identity, length, metadata, or content acquisition changes observably during the snapshot interval |
| `INTERNAL_OPERATION_ERROR` | Unexpected verifier defect prevents a semantic decision and no narrower operational code applies |
| `OUTPUT_IO_ERROR` | Completed outcome cannot be written to the selected output sink |

These strings are not semantic verification reasons and must not appear in an
inner result's `reason` field.

### 9.2 Phases and input roles

`phase` is one of:

```text
CAPABILITY_SELECTION
TRUST_INPUT
BUNDLE_SNAPSHOT
DISPATCH
CANONICAL_PARSE
MANIFEST_PARSE
SIGNATURE_MATERIAL
SEMANTIC_EVALUATION
OUTPUT
```

`input_ref` is null or one of:

```text
BUNDLE_DIRECTORY
AI_CANONICAL_JSON
AI_MANIFEST_JSON
VERIFICATION_KEYS_JSON
TRUST_STORE
EXPLICIT_INPUT
```

It identifies a role and must never contain a local path.

### 9.3 Limit facts

`limit` is null or contains exactly `name`, `unit`, `maximum`, and
`observed_at_least`. Names and required units are:

| `name` | `unit` | Meaning |
|---|---|---|
| `FILE_BYTES` | `BYTES` | Bytes in one immutable input role |
| `TOTAL_SNAPSHOT_BYTES` | `BYTES` | Sum of present known role bytes |
| `STRUCTURAL_DEPTH` | `LEVELS` | Simultaneously open object/array containers |
| `VALUE_OCCURRENCES` | `OCCURRENCES` | Root plus object-member values and array elements |
| `INTEGER_DECIMAL_DIGITS` | `DIGITS` | Integer magnitude digits, excluding a leading minus |
| `TIMESTAMP_DIGIT_PROFILE` | `PROFILE` | Selected timestamp repertoire identifier |

For `RESOURCE_LIMIT_EXCEEDED`, `limit` is required, `maximum` is the effective
integer ceiling, and `observed_at_least` is the first established value greater
than it. For `INPUT_OUTSIDE_DECLARED_CAPABILITY`, `limit` is required:
integer refusal uses integer values; timestamp refusal uses the selected
profile identifier as `maximum` and `U+` followed by four to six uppercase
hexadecimal digits as `observed_at_least`.

`RESOURCE_EXHAUSTED` may include a limit fact if meaningful; either value may
be null when exhaustion was not a measured ceiling. Other codes require null
unless a future version explicitly assigns a fact. `detail` is null or
non-normative human text. A consumer must never parse `detail` or branch on it.

### 9.4 Code boundary constraints

- Setup capability or input-mode failure uses phase `CAPABILITY_SELECTION`,
  null input, and null limit. Unsupported v1 reached after dispatch uses phase
  `DISPATCH`, input `AI_MANIFEST_JSON`, and null limit.
- Content-capability refusal uses the phase and role where traversal reached
  the value.
- Input type, I/O, and snapshot instability use `TRUST_INPUT` for a separate
  trust path or `BUNDLE_SNAPSHOT` for bundle roles.
- Output failure uses `OUTPUT`, null input, and null limit.
- `INTERNAL_OPERATION_ERROR` is a last-resort operational defect, never a
  substitute for an established semantic result.

## 10. Exit-code and stream contract

The relevant existing process codes remain unchanged:

| Surface/outcome | rc |
|---|---:|
| verify semantic `VALID` | 0 |
| verify semantic `INVALID` | 2 |
| compare `UNCHANGED` | 0 |
| compare `NOT_COMPARABLE` | 1 |
| compare `CHANGED` or `INVALID_BUNDLE` | 2 |
| operational inability during verify or a compare prerequisite | 3 |
| CLI invocation/argument syntax error (`TOOL_USAGE_ERROR`) | 64 |

Rc 3 was unused by every published semantic verify/compare outcome and is now
reserved for operational outcomes. Rc 64 is a tool-invocation code, not an
operational-result `operational_code` and not a semantic AELITIUM result. A CLI
must intercept argument-parser defaults as necessary to keep syntax error
distinct from rc 2 and rc 3.

In outer machine-readable mode, stdout contains exactly one outer result plus
one LF and the process code matches `rc`. Stderr is empty unless the output
channel fails. `OUTPUT_IO_ERROR` is reported best-effort on stderr and exits 3
because its JSON destination may be unavailable.

On legacy human/inner-result surfaces, an operational outcome emits no semantic
JSON, exits 3, and writes this stable first line to stderr:

```text
AELITIUM_OPERATIONAL <operational_code> <phase> <input_ref-or-NONE>
```

Optional explanatory stderr may follow and is non-normative. If verification
of either comparison input ends operationally, comparison does not run and no
comparison result is emitted; it exits 3 under the same rule. A future outer
comparison-result schema remains G-12 and is not invented here.

## 11. Resource and minimum capability envelope

### 11.1 Three layers

**Protocol semantic limits** are value rules already defined by the applicable
contract, such as v2's numeric magnitude and hash-string length. This policy
adds no semantic maximum file size, aggregate size, depth, occurrence count,
memory, or execution time.

**Minimum verifier conformance capability** is the simultaneous processing
floor named `AELITIUM_CLEANROOM_MINIMUM_1`:

| Limit | Minimum | Exact measurement |
|---|---:|---|
| Each known JSON input | 65,536 bytes | Raw bytes in one present role |
| Total operation snapshot | 262,144 bytes | Sum of present canonical, manifest, keyring, and supplied trust-store bytes |
| Structural depth | 1,024 | Simultaneously open objects/arrays; scalar root 0, root container 1 |
| JSON value occurrences | 65,536 | Root plus every object-member value and array element; duplicates included, member names excluded |

The floors were remeasured against the unchanged 44/30/114 corpora. The
largest frozen source is 10,248 bytes, maximum structural depth is 521 under
the definition above, and maximum value-occurrence count is 527. Separately,
the 44 result-contract operations contain 56 single-bundle verification
snapshots; their largest bundle-plus-supplied-trust snapshot is 2,036 bytes.
The published floors therefore retain conservative headroom and are not copied
as semantic maxima.

**Implementation-advertised operational limits** are the `advertised` values
in every outer result. The `effective` values are frozen when the operation
starts and may be caller-selected at or below those values. Claiming
`AELITIUM_CLEANROOM_MINIMUM_1` requires both advertised and effective values to
meet every floor simultaneously. A lower effective selection requires
`claimed_envelope=null`.

Exceeding means strictly greater than the effective value; equality remains
within limit. A conforming implementation may advertise higher ceilings. It
may not routinely exhaust below a claimed minimum; doing so is an
implementation conformance defect, and the particular operation still returns
`RESOURCE_EXHAUSTED` rather than semantic invalidity.

### 11.2 Token and traversal rules

There is no separate numeric-token ceiling below `max_file_bytes`. Dispatch
must skip every syntactically eligible number token within the effective byte
limit without conversion. Selected v1 integer tokens use section 5; v1
fraction/exponent tokens use the existing binary64 path; v2 tokens use the v2
semantic profile.

Every traversal within advertised depth must be independent of the host's
default recursion limit. Native recursion/stack failure is
`RESOURCE_EXHAUSTED`, never `*_NOT_JSON`. Dispatch exhaustion selects no route;
after v2 selection, exhaustion never retries v1.

Within a snapshotted source, deterministic left-to-right processing decides
between lexical failure and traversal ceiling. A syntax failure completely
established before the next value would cross a depth/occurrence limit retains
its semantic parse reason. If the traversal first proves that a limit would be
exceeded, the operation is operational because the remainder was not
evaluated. Per-file and aggregate byte limits are acquisition checks and
therefore precede content semantics.

## 12. Filesystem and immutable snapshot contract

### 12.1 Direct-filesystem eligibility

`DIRECT_FILESYSTEM` mode accepts a bundle root opened without resolving any
supplied path component through a symlink and established as a directory.
Against that held directory identity, it recognizes only
`ai_canonical.json`, `ai_manifest.json`, and `verification_keys.json`. Extra
entries are not enumerated, opened, validated, or counted. A separately
supplied trust-store path uses the same no-symlink-component acquisition rule.

Every present known role must be a regular file opened without following a
symlink. A symlink, directory, device, FIFO, or socket at a known role is
`INPUT_NOT_REGULAR_FILE` before content is opened. A hard link presenting as a
regular file is eligible but establishes no ownership or trust. A platform
that cannot enforce no-follow identity and regular-file behavior must declare
direct-filesystem mode unavailable and accept `IMMUTABLE_BYTES` instead. An
operation that nevertheless requests the unavailable mode returns
`CAPABILITY_PROFILE_UNAVAILABLE` at `CAPABILITY_SELECTION`; no path is opened.

Stable absence retains only an already-authorized semantic meaning:

- absent `ai_canonical.json` may establish `MISSING_CANONICAL`;
- absent `ai_manifest.json` may establish `MISSING_MANIFEST` at existing
  precedence;
- absent `verification_keys.json` produces signature evidence `ABSENT`; and
- no supplied trust input when membership is required may establish
  `TRUST_INPUT_NOT_PROVIDED`.

A supplied trust path that cannot be acquired is operational. Inaccessible
directories, permission/metadata/open/read failure, and inability to establish
initial state are `INPUT_IO_ERROR`. Present-then-missing or replaced input is
`INPUT_CHANGED_DURING_SNAPSHOT`.

### 12.2 Behavior-level acquisition algorithm

OS calls are implementation choices; these observable requirements are not:

1. Hold a no-follow identity for the bundle directory and, separately where
   needed, the supplied trust path's parent.
2. Observe every known role. Open each present role without following links,
   hold its source identity, establish regular-file type from that identity,
   and record length and available change metadata. Record absent roles for a
   later absence check.
3. Enforce per-file and aggregate byte limits while reading each held source
   from offset zero through EOF into a private buffer. Multiple short reads are
   accumulated; “one read” means one acquisition and no semantic reread.
4. An I/O error is `INPUT_IO_ERROR`. Premature EOF, growth, shrinkage, or
   disagreement with recorded length is `INPUT_CHANGED_DURING_SNAPSHOT`.
5. Recheck held identity, type, length, and available modification metadata;
   recheck that each directory entry still identifies the held source and each
   recorded-absent name remains absent. Any observable instability is
   `INPUT_CHANGED_DURING_SNAPSHOT`.
6. Freeze the complete role-to-bytes and role-to-absence map. Every semantic
   step uses only that map; no source is reopened or reread.

Dispatch, selected manifest parsing, raw-manifest signature verification, and
later manifest access receive the same captured manifest bytes. Canonical
parsing and hashing receive the same canonical bytes. Keyring and trust
evaluation use their respective captured bytes.

This establishes observable stability during one bounded acquisition interval.
It does not claim impossible atomicity among unrelated files, prove that the
files historically coexisted, or defeat undetectable hostile storage. Operators
needing stronger capture guarantees must supply a content-store/OS snapshot or
the immutable-bytes model. Hashes and bindings evaluate the captured data; they
do not prove filesystem atomicity.

### 12.3 Caller-provided immutable bytes

`IMMUTABLE_BYTES` is equivalent only when the caller fixes, before verification:

- presence or absence of every known bundle role;
- exact bytes for every present role;
- supplied trust-store bytes or explicit no-store state; and
- the complete map as one immutable operation input.

The verifier copies the map or obtains an equivalent immutability guarantee,
applies the same per-role/aggregate limits, and never invokes the filesystem
for those roles. A lazy stream, mutable slice, callback returning different
bytes, or one-role-at-a-time API without a frozen presence map is not
equivalent. The caller owns provenance and atomic capture; the verifier claims
only evaluation of the supplied immutable map.

## 13. Language-neutral conformance

The separate normative family is
[`../conformance/legacy_v1_operational_policy/manifest.json`](../conformance/legacy_v1_operational_policy/manifest.json).
It does not edit, renumber, or reinterpret the existing 44 result-contract, 30
v1 canonicalization, or 114 v2 cases.

Its JSON cases use closed byte recipes, exact source SHA-256 values, complete
capability/limit declarations, synchronized abstract filesystem operations,
and frozen expected policy checkpoints or complete operational wrapper bytes.
Expected operational objects always have outcome `OPERATIONAL_OUTCOME`, rc 3,
null verification result, no assurance object, no semantic invalid reason, and
no comparison result. Expected data are committed and are not generated by the
verifier under test.

The corpus includes:

- 640/641/4300/4301/10000 and arbitrary `N`/`N+1` integer cases in governed,
  ignored, overwritten, and programmatic positions;
- bounded 640/4300 and explicit unlimited profiles;
- final-v2 dispatch isolation from legacy conversion/resource logic;
- ASCII, frozen-`Nd`, outside-table, final-LF, separator, and embedded-LF
  timestamps;
- duplicates, non-finites, permitted surrogate units, Base64 pad-bit aliases,
  open members, and empty trust membership;
- below/at/above byte, aggregate, depth, and occurrence limits;
- injected allocation/resource exhaustion; and
- regular, symlink, directory, FIFO/device/socket abstraction, I/O,
  disappearance, replacement, mutation, short-read, stable-absence, and
  immutable-snapshot equivalence cases.

The maintenance builder and runner are non-normative aids. A clean-room
verifier consumes the committed JSON and frozen Unicode range files directly.
Platform-specific object creation may be skipped only where unsafe or
unavailable; equivalent abstract adapter cases remain mandatory. Mutations use
synchronization points, never timing sleeps.

## 14. Gap impact and independent-verifier readiness

Normative adoption closes the two policy gaps:

| Gap | Status | Basis |
|---|---|---|
| G-02 | **CLOSED** | Sections 3–7 publish the portable boundary, exact named profiles, frozen digit repertoires, and deterministic legacy rules. |
| G-09 | **CLOSED** | Sections 2 and 8–13 publish operational transport, rc/code registry, limits, snapshot behavior, and frozen conformance. |

This policy removes the cross-cutting compatibility blocker but does not close
Verifier Contract Closure Phase 2:

| Gap | Status | Work still required in Phase 2 |
|---|---|---|
| G-04 — manifest | **OPEN — UNBLOCKED_BY_POLICY** | Versioned schemas, exact v1/v2 source and field grammar, unknown members, validation order, and Phase 2 vectors |
| G-05 — verification keys | **OPEN — UNBLOCKED_BY_POLICY** | Exact schema/source profile, Base64/key domains, signature precedence, and Phase 2 vectors |
| G-06 — trust store | **OPEN — UNBLOCKED_BY_POLICY** | Exact schema/source profile, membership/fingerprint rules, precedence, and Phase 2 vectors |

G-01, G-03, and G-13 remain closed. G-07, G-08, G-10, and G-11 remain open.
G-12 remains deferred while comparison is excluded from the initial clean-room
scope.

Creating `aelitium-verifier-go` remains **NOT_READY**. The minimum gate still
lacks G-07 (invocation grammar/order), G-08 (exhaustive reason/state registry),
and G-10 (complete language-neutral end-to-end corpus operations/outputs).
Complete bundle verification also requires G-04/G-05/G-06. This document does
not authorize implementation or repository creation.

## 15. Explicit non-claims

Verifier capability describes only the verifier's declared ability to evaluate
an immutable input under a named contract. Neither capability, semantic
verification, operational success, snapshot stability, signatures, nor trust
membership establishes:

- provider execution;
- historical occurrence or historical non-modification;
- `trusted_signer_identity` from signature validity alone;
- authorization;
- response causation;
- semantic truth;
- capture completeness;
- legal compliance;
- model drift;
- regression; or
- quality degradation.

This contract adds no PKI, certificate, revocation, expiry, delegation, network
lookup, ambient trust, provider call, capture service, policy engine, or
cross-version comparison bridge.

## 16. Adoption verdict

LEGACY_COMPATIBILITY_OPERATIONAL_POLICY_ADOPTION_READY
