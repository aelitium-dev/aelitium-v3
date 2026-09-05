# Legacy v1 Compatibility and Operational Policy — Design/Audit

**Status:** DESIGN-AUDIT-NON-NORMATIVE

**Repository baseline:** `main` at
`b87134356bee012ef5b7580381161d4ce29a7bca`

**Scope:** G-02 (legacy-v1 capability and portability boundary) and G-09
(operational, resource, filesystem, and snapshot behavior) only

This document designs a compatibility-safe policy for an independent verifier.
It does not change released v0.4.0, publish a protocol, alter an evidence or
result identifier, implement a refusal path, or create an independent verifier.
All names marked **PROPOSED** remain design names until a later normative review.

## 1. Executive decision

G-02 and G-09 have a coherent design that can be published without treating
Python as an oracle and without turning insufficient verifier capability into
bundle invalidity:

- preserve `json_sorted_keys_no_whitespace_utf8` exactly;
- define portable and named legacy-compatibility verifier capabilities outside
  the evidence bundle;
- evaluate every deterministic legacy rule that can be reproduced
  cross-language, even when the rule is inelegant;
- return a separately typed operational outcome when the selected verifier
  cannot evaluate an input under its declared capability or resource envelope;
- permit a CPython-compatible result only under a fully declared, language-
  neutral profile that fixes the decimal-integer limit and Unicode decimal-
  digit table; and
- snapshot regular input files into immutable byte buffers before semantic
  evaluation and never reread them for dispatch, parsing, hashing, or signature
  verification.

The design does not claim that v1 has one universal accept/reject relation.
It instead makes the qualification visible and prevents an out-of-domain
artifact from acquiring `INVALID` or a semantic reason merely because one
verifier declined it.

| Gap | Design-audit verdict | Closure supplied by this design |
|---|---|---|
| G-02 | **READY_TO_CLOSE** | Explicit portable and named-runtime capability profiles, exhaustive integer/timestamp behavior, and profile-bound result transport |
| G-09 | **READY_TO_CLOSE** | Separate operational outcome, exit mapping, advertised limits, minimum envelope, regular-file snapshot algorithm, and operational conformance model |

No new public **semantic verification reason** is required. The operational
codes proposed here occupy a different contract and vocabulary.

## 2. Source basis and method

The hierarchy and conflict rules in
[`../VERIFIER_PROTOCOL_V1.md`](../VERIFIER_PROTOCOL_V1.md) govern this audit.
The policy was derived first from the following inputs, with each retaining
the authority assigned by that hierarchy:

- [`../CANONICALIZATION_SPEC.md`](../CANONICALIZATION_SPEC.md);
- [`../INDEPENDENT_VERIFIER_REQUIREMENTS.md`](../INDEPENDENT_VERIFIER_REQUIREMENTS.md);
- [`../VERIFICATION_RESULT_V1.md`](../VERIFICATION_RESULT_V1.md);
- [`../ASSURANCE_RESULT_V1.md`](../ASSURANCE_RESULT_V1.md);
- [`../CLAIM_BOUNDARIES_V1.md`](../CLAIM_BOUNDARIES_V1.md);
- [`../COMPARE_RESULT_V1.md`](../COMPARE_RESULT_V1.md);
- [`INDEPENDENT_VERIFIER_GO_DESIGN.md`](INDEPENDENT_VERIFIER_GO_DESIGN.md);
- [`VERIFIER_CONTRACT_PHASE2_DESIGN.md`](VERIFIER_CONTRACT_PHASE2_DESIGN.md);
- the 44-case result-contract corpus;
- the 30-case released-v1 canonicalization corpus; and
- the 114-case portable-v2 canonicalization corpus.

The public contracts occupy their published Level 1 roles, the frozen corpora
are Level 3 acceptance evidence, and the two internal design/audit documents
are Level 4 historical analysis only. Neither internal document can override a
public contract or frozen expected result.

The 30-case corpus marks integer magnitudes above 640 decimal digits `OPEN`.
The v2 corpus separately freezes five profile-dependent v1 routes at limits
640, 4300, and disabled, plus one final-v2 isolation case and other portable
dispatch cases. These data are examples and acceptance evidence; they do not
silently create a universal v1 rule.

Python is not normative. Section 14 is labeled **IMPLEMENTATION CROSS-CHECK**
and was performed only after sections 1 through 13 were independently derived.
Its observations identify compatibility or operational defects; they are not
incorporated by reference.

## 3. Precise problem taxonomy

The five requested categories are distinct:

- **A — portable and fully specified:** the published bytes and decision can be
  reproduced without a host-specific profile.
- **B — deterministic but unusual legacy:** the behavior is portable once its
  already-established compatibility rule is stated explicitly; aesthetic
  strictness is not a reason to refuse it.
- **C — explicit runtime profile:** more than one released runtime
  configuration legitimately produces different outcomes, so a profile must
  qualify the result.
- **D — resource availability:** the algorithm is known, but the operation
  could not complete within a declared or actually available operational
  envelope.
- **E — currently underspecified:** Level 1 prose and frozen data do not yet
  determine the behavior. A reviewed specification choice is required.

### 3.1 Inventory

| Behavior | Current category | Selected closure treatment |
|---|---|---|
| Strict UTF-8, BOM rejection, JSON whitespace, v1 scalar key order, escaping, arrays, booleans, null, finite-binary64 conversion/rendering, and canonical storage envelope | A | Evaluate semantically under every v1-capable profile |
| Integer-form tokens with magnitude length at most 640 decimal digits | A | Required portable minimum in every parsed source position |
| Integer-form tokens with more than 640 digits | C | Portable profiles refuse operationally; a named runtime profile may evaluate them under an explicit decimal digit limit |
| Configurable CPython decimal integer conversion guard | C | Represent as a language-neutral profile parameter, never as ambient runtime discovery |
| Manifest timestamp Unicode `\d` repertoire | C and E | Restricted profile accepts only ASCII digits; named profile pins one Unicode `Nd` table by version and digest |
| One final decoded U+000A accepted after manifest timestamp `Z` | B | Preserve exactly; it is independent of the Unicode digit table |
| Last decoded duplicate object name wins under v1 | B | Reproduce with occurrence-preserving parsing before map collapse |
| Escaped unmatched-surrogate legacy strings in locations where they are not canonically serialized | B | Retain code units in an opaque legacy string representation and apply the location-specific rule |
| Exact `NaN`, `Infinity`, and `-Infinity` tokens | B | Reproduce exact case-sensitive parsing and v1 serialization where the published value domain permits them |
| Non-zero unused Base64 pad bits accepted in fixed-length key and signature encodings | B and E | Preserve in the Phase 2 source profile; do not impose encode-after-decode equality under existing formats |
| Open/unknown keyring members, ignored manifest extensions, post-collapse closed trust objects, and empty trust-store signer arrays | B and E | Preserve the Phase 2 compatibility design and freeze it in the later G-04/G-05/G-06 closure |
| Deep nesting beyond an advertised structural limit | D | Operational limit; never a JSON/profile reason solely because the host stack or configured depth was exhausted |
| Input-file size, total snapshot size, node/member count, or allocation exhaustion | D | Advertised operational limit or resource exhaustion |
| Permission, open, read, short-read, disappearing-path, and similar I/O failure | D | Operational input-acquisition outcome unless stable absence has already established an authorized semantic missing-file result |
| Symlink, directory, device, FIFO, or socket at an expected file path | E, resolved here as D | Refuse before opening content as an unsupported input type; never follow or block on it |
| Concurrent mutation, path replacement, and cross-read inconsistency | E, resolved here as D | Snapshot through held regular-file descriptors; any detected instability is operational |
| Absolute atomicity of unrelated files on a general filesystem | D | Not claimed; use one immutable operation snapshot and rely on bundle consistency checks, or accept a caller-provided atomic snapshot |

The classification is about cause, not file location. A 641-digit integer and
a permission failure are not the same problem. A duplicate name and a stack
overflow are not the same problem. The policy must keep those distinctions
visible.

## 4. Semantic result versus operational outcome

### 4.1 Hard boundary

A **semantic result** exists only when the verifier had sufficient declared
capability, acquired a stable input snapshot, and had enough operational
resources to reach the applicable AELITIUM decision under the selected
contract and public precedence.

An **operational outcome** means no AELITIUM semantic result was established
because the requested capability was unavailable, the reached input lay
outside the declared capability, input acquisition failed, snapshot stability
was not established, an advertised operational ceiling was exceeded, or the
implementation could not complete.

Consequently an operational outcome:

- has no `VALID` or `INVALID` verification status;
- has no AELITIUM semantic `reason`;
- has no assurance dimensions or partial assurance object;
- must not be serialized as `MANIFEST_NOT_JSON`, `SIGNATURE_INVALID`,
  `TRUST_STORE_INVALID`, `HASH_MISMATCH`, or another semantic condition;
- must not cause dispatch to choose or retry a version; and
- cannot be used as a comparison input.

Stable absence is different. If a stable existing bundle-directory snapshot
shows that `ai_canonical.json` or `ai_manifest.json` does not exist, the
contract can establish `MISSING_CANONICAL` or `MISSING_MANIFEST`. If a path was
present but disappeared or changed while it was being snapshotted, that is an
operational outcome, not stable absence.

Malformed bytes are also different. Once bytes have been successfully
snapshotted and the applicable parser has sufficient capability/resources, a
syntax or profile violation produces its authorized semantic result. The fact
that the parser uses memory does not turn every parse rejection into a resource
event.

### 4.2 Evaluation and precedence

Capability and operational checks occur at the boundary they protect:

1. reject an unavailable requested capability operationally before inspecting
   bundle content;
2. apply semantic explicit-input precedence that can be decided without bundle
   acquisition, including required trust input and Freshness option structure;
3. acquire and, where applicable, semantically validate an explicit trust
   input in its published position;
4. establish stable presence for the three known bundle paths;
5. snapshot the present known files into immutable byte buffers;
6. run dispatch without numeric conversion;
7. apply content-capability checks only when the corresponding selected parser
   reaches that source; and
8. return the first fully established semantic result or the operational
   outcome that prevented that phase from completing.

This preserves meaningful precedence. For example, a malformed canonical
payload can still establish `CANONICAL_NOT_JSON` before a 641-digit integer in
a v1 manifest becomes relevant. A huge number in dispatch cannot select v1 by
exhausting the scanner. A keyring capability issue is not evaluated before
payload integrity because keyring semantics occur later.

Input snapshot failure may precede semantic content evaluation because no
stable byte input exists. It must not manufacture a partial semantic result to
simulate what might have happened had acquisition succeeded.

### 4.3 Proposed tool-result transport

The existing closed `aelitium-verification-result-v1` schema contains only
semantic `VALID`/`INVALID` results with CLI equivalents 0/2. It must not gain
operational fields.

The future verifier should add a separate **PROPOSED** outer transport:

```text
contract = aelitium-verifier-tool-result-v1
operation = VERIFY_BUNDLE
outcome = SEMANTIC_RESULT | OPERATIONAL_OUTCOME
rc = 0 | 2 | 3
capability = { requested: exact declaration, effective: declaration | null }
verification_result = aelitium-verification-result-v1 object | null
operational = operational object | null
```

Cross-field rules are exact:

- `SEMANTIC_RESULT` carries one unmodified verification result, sets
  `operational=null`, and copies that result's CLI-equivalent `rc` 0 or 2;
- `OPERATIONAL_OUTCOME` sets `verification_result=null`, carries one
  operational object, and uses `rc=3`;
- `capability.requested` records the explicit or documented-default request;
  `capability.effective` repeats the exact selected declaration in every
  semantic and ordinary operational outcome;
- only `CAPABILITY_PROFILE_UNAVAILABLE` sets `capability.effective=null`, while
  retaining the rejected request so the refusal is unambiguous;
- local filesystem paths are never emitted; and
- the wrapper uses strict UTF-8, sorted object names, compact separators, and
  exactly one terminal LF in its machine-readable mode.

The operational object contains exactly:

```text
operational_code
phase
input_ref              # bounded role reference or null
limit                  # structured limit facts or null
detail                 # null or non-normative text
```

This is a proposed new tool transport, not a verification-result revision.
No schema is created in this workstream. A future `--operation-json` flag may
select it. Under existing `--contract-json`, an operational failure must emit
no counterfeit verification object; it may emit a stable stderr diagnostic and
exit 3. A profile-dependent semantic result must use the outer transport so
its qualification cannot be silently detached.

## 5. Proposed v1 capability model

The following names are **PROPOSED capability names**, not evidence identifiers
and not yet public protocol values.

### 5.1 Capability classes

| Capability | Input domain and guarantee | Portable | Released-v1 reproduction | Outside-domain behavior |
|---|---|---:|---|---|
| `V2_PORTABLE` | Complete `aelitium_jcs_profile_v2` semantics within the advertised operational envelope | Yes | Not a v1 claim | Resource/operational outcome only; v2 semantic profile violations remain semantic |
| `V1_RESTRICTED_PORTABLE` | The already-published restricted subset: scalar strings, finite values, integers at most 640 magnitude digits in every reached source/result position, and ASCII manifest timestamp digits | Yes | Only the declared subset | `INPUT_OUTSIDE_DECLARED_CAPABILITY` |
| `V1_FROZEN_LEGACY_COMPATIBILITY` | `V1_RESTRICTED_PORTABLE` plus the deterministic portable legacy rules in section 8, still bounded to 640 integer digits and ASCII manifest timestamp digits | Yes | All deterministic released behavior in this bounded domain; not the complete v1 surface | `INPUT_OUTSIDE_DECLARED_CAPABILITY` |
| `V1_NAMED_RUNTIME_COMPATIBILITY` | Frozen legacy rules plus an exact decimal-integer digit limit and exact Unicode `Nd` table; results are explicitly profile-relative | Yes as an emulation specification | Reproduces the named released-runtime profile within advertised resources, not every v0.4.0 configuration | Profile rule where fully specified; otherwise operational |
| `V1_LEGACY_UNSUPPORTED` | No legacy/error-resolution path is implemented | N/A | None | `CAPABILITY_PROFILE_UNAVAILABLE` after non-v2 dispatch, never bundle invalidity |

`V1_CPYTHON_DIGIT_PROFILE(n)` is not sufficient as a standalone capability:
it says nothing about the timestamp Unicode database or operational envelope.
The useful replacement is the composite `V1_NAMED_RUNTIME_COMPATIBILITY`
descriptor below. Likewise, an unparameterized claim of “full v1” is forbidden.

An independent verifier should normally implement `V2_PORTABLE` and
`V1_FROZEN_LEGACY_COMPATIBILITY`. The narrower restricted profile remains
useful to consumers that deliberately exclude legacy non-finites and opaque
surrogate strings.

### 5.2 Exact capability declaration

Every operation declaration contains:

```json
{
  "v1_capability": "V1_FROZEN_LEGACY_COMPATIBILITY",
  "integer_decimal_digit_limit": 640,
  "timestamp_digit_profile": "ASCII",
  "timestamp_final_lf": "ACCEPT_ONE",
  "operational_envelope": "AELITIUM_CLEANROOM_MINIMUM_1",
  "limits": {
    "max_file_bytes": 65536,
    "max_total_snapshot_bytes": 262144,
    "max_structural_depth": 1024,
    "max_value_occurrences": 65536
  }
}
```

For `V1_NAMED_RUNTIME_COMPATIBILITY`, the declaration instead requires:

```text
integer_decimal_digit_limit = 0 or an integer >= 640
timestamp_digit_profile = UCD-Nd-<exact-version>-<table-sha256>
timestamp_final_lf = ACCEPT_ONE
```

`0` means the compatibility profile has no decimal conversion guard; it does
not mean infinite memory or unadvertised file/token support. An exact UCD table
is data, not a call to the host's current Unicode library. A later normative
registry should initially pin the UCD 13.0.0, 14.0.0, and 15.0.0 `Nd` tables
needed to describe the supported CPython 3.10–3.12 family, including immutable
table digests and the existing external-standard non-supersession policy.

### 5.3 Visibility and selection

Capability information belongs in all of these places:

- explicit CLI/API configuration when more than one v1 profile is available;
- a machine-readable static verifier-capabilities document;
- the proposed outer tool result for every operation;
- the conformance implementation declaration; and
- audit logs maintained by the operator outside the evidence bundle.

It must not be inferred from an installed Python version, environment variable,
locale, current Unicode database, or machine memory. Defaults must be documented
and deterministic. It must never be stored in or negotiated by the evidence
bundle, because verifier capability is not evidence and cannot change the
meaning of `json_sorted_keys_no_whitespace_utf8`.

The inner verification result remains byte-for-byte within its existing
contract. Consumers of a profile-dependent result must retain the outer
capability declaration; stripping it and asserting universal v1 invalidity is
non-conforming.

## 6. Extreme-integer policy — G-02 core

### 6.1 What the limit measures

For this policy, an **integer-form token** is a JSON number token with no
fraction and no exponent. Its decimal-digit count is the count of ASCII digits
in the token; an optional leading minus sign is excluded. RFC 8259 already
forbids redundant leading zeroes, so no separate significant-digit rule is
needed. Fractional and exponent-form tokens follow the established v1
binary64 path and are not subject to this decimal-integer conversion guard.

The guard applies to every integer-form token that the selected legacy parser
must convert, not merely to a field that later acquires meaning. It therefore
applies before map collapse and includes:

- governed values;
- ignored extension values;
- earlier values overwritten by a duplicate decoded member name;
- manifest values;
- `verification_keys.json` values;
- trust-store values;
- canonical-payload values; and
- direct structured inputs and result values when those interfaces accept a
  language-level integer rather than source bytes.

This occurrence-wide rule is necessary for legacy compatibility. Skipping an
ignored or overwritten token would accept an input that the relevant released
runtime profile could fail while converting the source.

### 6.2 Portable profile

`V1_RESTRICTED_PORTABLE` and `V1_FROZEN_LEGACY_COMPATIBILITY` guarantee exact
integer conversion for tokens containing at most 640 magnitude digits. A
reached integer-form token of 641 or more digits is outside those declared
capabilities. The tool returns the operational code
`INPUT_OUTSIDE_DECLARED_CAPABILITY`; it does not emit `INVALID` or a source-
specific JSON reason.

The 640 boundary is a portable minimum, not a new semantic maximum for
`json_sorted_keys_no_whitespace_utf8`. An implementation may advertise a
larger resource ceiling, but it may not silently turn that larger ceiling into
a different v1 accept/reject contract.

For programmatic arbitrary-precision integers, the same magnitude-digit test
is performed before canonicalization or result serialization. If an interface
cannot retain the integer exactly before that test, the implementation does
not provide the declared capability.

### 6.3 Named-runtime compatibility profile

A `V1_NAMED_RUNTIME_COMPATIBILITY` declaration fixes
`integer_decimal_digit_limit` to either `0` or an integer `n >= 640`:

- when `n > 0`, conversion of a token with at most `n` digits proceeds and a
  token with more than `n` digits reproduces the source-specific legacy parse
  failure at the point established by existing precedence;
- when `n = 0`, the compatibility conversion guard is disabled, but file,
  token, memory, node, and other advertised operational limits still apply;
- the guard value is selected explicitly and recorded in the outer tool
  result; it is never inferred from the host; and
- a result produced under one `n` does not make a claim about any other
  released runtime configuration.

The profile-relative legacy parse mappings are:

| Reached source | More than configured nonzero `n` | Existing semantic mapping in that named profile |
|---|---|---|
| `ai_canonical.json` | conversion guard rejects | `CANONICAL_NOT_JSON` |
| `ai_manifest.json` after the legacy route is selected | conversion guard rejects | `MANIFEST_NOT_JSON` |
| present `verification_keys.json` | conversion guard rejects | `SIGNATURE_INVALID` |
| supplied trust store | conversion guard rejects | `TRUST_STORE_INVALID` |

Those are compatibility-emulation results, not portable declarations that the
same bytes are intrinsically invalid. They may be exposed only in the outer
transport carrying the complete named profile. A bare v1 verification result
must not be used to detach or erase this qualification. A verifier that does
not implement named-runtime emulation uses the portable operational refusal
instead.

The source-specific table does not apply to a language-level integer supplied
without JSON source. No legacy parse condition exists in that case. A
programmatic integer above a named profile's nonzero `n` is
`INPUT_OUTSIDE_DECLARED_CAPABILITY` before semantic evaluation or result
serialization; it must not manufacture `CANONICAL_NOT_JSON` or another source
reason. Profile `0` evaluates it only when the advertised resource envelope
can retain and emit it exactly.

The dispatch scanner remains outside this conversion model: it consumes an
integer token lexically with no digit limit. A final v2 selector always selects
v2, even if a 10,000-digit legacy-looking token occurs before it. The fresh v2
parse then applies the v2 number profile and produces its specified semantic
result; it must never fall back to the v1 capability route.

### 6.4 Frozen and arbitrary boundaries

| Token magnitude | Portable profile | Named profile 640 | Named profile 4300 | Named profile 0 |
|---:|---|---|---|---|
| 640 digits | evaluate | evaluate | evaluate | evaluate |
| 641 digits | operational refusal | profile-relative parse failure | evaluate | evaluate |
| 4,300 digits | operational refusal | profile-relative parse failure | evaluate | evaluate |
| 4,301 digits | operational refusal | profile-relative parse failure | profile-relative parse failure | evaluate |
| 10,000 digits | operational refusal | profile-relative parse failure | profile-relative parse failure | evaluate if advertised resources suffice |

For any other configured `n`, the boundary is exactly `n`/`n + 1`. An
allocation failure while handling an otherwise in-profile token is
`RESOURCE_EXHAUSTED`, not the named profile's parse failure. This prevents an
incidental memory or stack ceiling from masquerading as the declared decimal
conversion rule.

## 7. Manifest timestamp host-dependence

### 7.1 Shared deterministic legacy shape

When manifest timestamp validation is enabled, the v1 value must have this
decoded-string shape:

```text
DDDD-DD-DDTDD:DD:DDZ[LF]
```

Each `D` is a member of the selected timestamp digit repertoire. `[LF]` means
zero or one final U+000A. There are exactly fourteen digit positions and the
displayed ASCII separators are literal and case-sensitive. A final U+000D,
U+000D U+000A, two U+000A values, embedded U+000A, or any other suffix fails.
A raw LF remains illegal inside JSON source; the accepted final LF is a
decoded character such as the result of `\n`.

This is lexical validation only. It imposes no month, day, hour, minute,
second, leap-year, leap-second, calendar, chronology, or historical-occurrence
rule. Thus digit-shaped values such as zero components or `99` components are
not rejected for range. This section does not define or close Freshness G-11.

When `validate_manifest_timestamp=false`, only the existing `ts_utc` member-
presence rule remains: v1 does not perform a type or spelling check. The
selected source parser and all other manifest rules still apply.

### 7.2 Portable and named repertoires

The portable v1 profiles define `D` as ASCII U+0030 through U+0039. If all
fourteen digit positions are ASCII, the verifier evaluates the timestamp
semantically, including the single-final-LF rule. If the decoded string has the
right separators and length but any digit position is a non-ASCII character,
the portable profile returns `INPUT_OUTSIDE_DECLARED_CAPABILITY`, not
`MANIFEST_BAD_TS_UTC`.

Evaluation order is fixed. First require a string and check its total length,
literal separator positions, and permitted zero-or-one final LF. A failure at
that stage is `MANIFEST_BAD_TS_UTC`. Then inspect the fourteen digit positions:
an ASCII non-digit is `MANIFEST_BAD_TS_UTC`; a non-ASCII character is outside
the portable profile; and an ASCII digit is accepted. A named profile replaces
only that final repertoire test with membership in its frozen `Nd` table.

An unmistakably wrong portable spelling remains semantic. Examples include a
wrong separator, too few positions, an ASCII letter in a digit position, an
embedded LF, or two final LFs. A non-ASCII character outside a digit position
is likewise an established separator/suffix mismatch, not an ambiguity about
the digit table.

A named-runtime profile defines `D` by an immutable table of code points whose
Unicode General Category is `Nd` in one exact Unicode Character Database
version. The declaration carries a stable profile name and table SHA-256; the
verifier uses the bundled frozen table, never its host regex or Unicode
library. Under this profile, a code point outside the selected table produces
the ordinary profile-relative `MANIFEST_BAD_TS_UTC` result when timestamp
validation is enabled.

This is option A plus B from the audit question: a frozen `Nd` table expresses
the compatibility profile, while the runtime-family label explains which
released environment it emulates. The portable profile implements option C.
The normative follow-up must publish the actual tables and digests rather than
relying on a Unicode version name alone.

### 7.3 Compatibility classification

| Rule | Classification |
|---|---|
| ASCII digit timestamp with exact separators | `PORTABLE_LEGACY_RULE` |
| Zero or one decoded final LF after `Z` | `PORTABLE_LEGACY_RULE` |
| Non-ASCII digit recognition against a pinned UCD `Nd` table | `PROFILE_DEPENDENT_RULE` |
| Recognition against whatever Unicode database happens to be installed | `SPECIFICATION_GAP` and forbidden implementation strategy |
| Resource failure while decoding or validating the string | `OPERATIONAL_LIMIT` |

## 8. Deterministic legacy behavior

Host dependence must not be used as an excuse to refuse legacy behavior that
is independently reproducible. The future normative policy should adopt these
rules under the existing relevant v1 formats:

| Behavior | Classification | Required treatment |
|---|---|---|
| Duplicate decoded object names | `PORTABLE_LEGACY_RULE` | Parse occurrences left to right and retain the final value before semantic validation; this includes exact and escaped-equivalent names |
| Exact tokens `NaN`, `Infinity`, `-Infinity` | `PORTABLE_LEGACY_RULE` | Accept only these case-sensitive legacy tokens in legacy sources and preserve the already-documented location and serialization consequences |
| Escaped unmatched surrogate code units | `PORTABLE_LEGACY_RULE` | Preserve in an opaque UTF-16-code-unit-capable legacy string representation where released rules permit them; never manufacture scalar Unicode or v2 acceptance |
| Base64 non-zero unused pad bits | `PORTABLE_LEGACY_RULE` | Accept the fixed legacy alphabet/padding shapes when they decode to the required length; do not require encode-after-decode equality |
| Unknown/open object members | `PORTABLE_LEGACY_RULE` | Apply the location-specific Phase 2 open/closed policy after last-name-wins collapse; unknown accepted members acquire no meaning |
| Empty `signers` array | `PORTABLE_LEGACY_RULE` | Accept as a valid trust store containing no trust members |
| One final decoded LF in enabled v1 manifest timestamp validation | `PORTABLE_LEGACY_RULE` | Accept exactly as section 7 defines |
| More than 640 integer digits | `PROFILE_DEPENDENT_RULE` | Portable refusal or named-profile evaluation as section 6 defines |
| Non-ASCII timestamp decimal digits | `PROFILE_DEPENDENT_RULE` | Portable refusal or pinned-UCD evaluation as section 7 defines |
| Structural depth, source size, nodes, memory, and stack | `OPERATIONAL_LIMIT` | Advertise and report separately from semantic JSON validity |
| Input type and snapshot stability | `SPECIFICATION_GAP` resolved by this design as an operational acquisition contract | Apply section 9; never collapse acquisition failure into a semantic reason |

These rules reproduce released acceptance rather than endorsing the values as
good producer output. They do not create trust, authorization, provider
identity, execution proof, or historical occurrence.

## 9. Resource and operational envelope — G-09 core

### 9.1 Three distinct limit layers

The normative policy must keep these layers separate:

**A. Protocol semantic limits.** The protocol's existing value rules remain
semantic—for example, v2's binary64/safe-magnitude profile and the exact shape
of fixed-length hashes. There is no new protocol-wide maximum file size,
nesting depth, value count, or memory use in this design. Exceeding a verifier
ceiling does not make an otherwise admissible bundle invalid.

**B. Minimum verifier conformance capability.** A verifier claiming the
proposed `AELITIUM_CLEANROOM_MINIMUM_1` envelope must be able to acquire and
process, with all limits available simultaneously:

| Limit | Minimum required capability | Exact measurement |
|---|---:|---|
| Each known JSON input | 65,536 bytes | Raw bytes in that one file or immutable input item |
| Total operation snapshot | 262,144 bytes | Sum of present `ai_canonical.json`, `ai_manifest.json`, `verification_keys.json`, and supplied trust-store bytes; extra directory entries are not read or counted |
| Structural depth | 1,024 | Number of simultaneously open object/array containers; a scalar root has depth 0 and a root container has depth 1 |
| JSON value occurrences | 65,536 | One for the root plus one for every object-member value and array element, including overwritten duplicates; an object name is not a second value occurrence |

These proposed floors are not arbitrary semantic maxima. At this baseline the
largest frozen source is 10,248 bytes and the frozen deep-routing vectors reach
depth 520; the floors deliberately round above the existing 44-, 30-, and
114-case evidence and provide headroom for a common interoperability target.
The normative adoption PR must remeasure the frozen files and may only raise a
floor if that measurement changes. A capability claim fails conformance if an
input at or below every floor cannot be evaluated because of an ordinary
implementation limit.

**C. Implementation-advertised operational limits.** Each verifier publishes
and repeats in the operation result its effective `max_file_bytes`,
`max_total_snapshot_bytes`, `max_structural_depth`, and
`max_value_occurrences`. Each must meet or exceed the minimum when that
envelope is claimed. Implementations may offer higher named envelopes or a
caller-selected lower local envelope, but a lower selection cannot claim
`AELITIUM_CLEANROOM_MINIMUM_1`.

The effective values are frozen when an operation starts. Crossing one returns
`RESOURCE_LIMIT_EXCEEDED` with limit facts. Unexpected allocator, address-
space, stack, or similar exhaustion before an advertised ceiling returns
`RESOURCE_EXHAUSTED` and makes that operation non-semantic; recurring failure
inside a claimed minimum is also a conformance defect.

### 9.2 Token, traversal, and exhaustion rules

There is no separate numeric-token resource ceiling below `max_file_bytes`.
The dispatch scanner must skip any syntactically eligible number token within
the advertised source-size bound without conversion. After routing:

- v1 integer-form tokens use section 6's capability/profile rule;
- v1 fractional and exponent tokens use the established binary64 path;
- v2 number tokens use the published v2 semantic profile; and
- actual allocation failure remains operational regardless of token kind.

All source traversals that can reach the advertised depth must be independent
of the host language's default recursion limit. An implementation may use an
explicit stack or safely provision its own, but a native stack overflow or
recursion exception is `RESOURCE_EXHAUSTED`, never `*_NOT_JSON`. Dispatch
exhaustion must not choose v1, and selected v2 exhaustion must not retry v1.

Within a snapshotted source, deterministic left-to-right processing decides
between an already-established lexical error and a later traversal limit. If a
syntax error is completely established before the traversal first needs to
cross an advertised depth or occurrence ceiling, the authorized semantic
parse reason applies. If the ceiling is reached first, the outcome is
operational because the remainder was not evaluated. A file-size or aggregate
snapshot ceiling is checked during acquisition and therefore precedes content
semantics.

### 9.3 Eligible filesystem inputs

Direct filesystem mode accepts exactly:

- a bundle root whose supplied path resolves without following a symlink to a
  directory handle; and
- each present known input as a regular file opened relative to that held
  directory handle, without following a symlink.

A separately supplied trust-store path is subject to the same no-follow and
regular-file rule. Expected bundle names are exactly `ai_canonical.json`,
`ai_manifest.json`, and `verification_keys.json`. Other directory entries are
ignored: the verifier does not enumerate, open, validate, or count them.

A symlink, directory, block/character device, FIFO, or socket at a known file
role returns `INPUT_NOT_REGULAR_FILE` before content is opened for reading.
This prevents aliasing and blocking behavior. A hard link that presents as a
regular file is eligible; eligibility establishes neither ownership nor trust.
If a platform cannot enforce no-follow traversal and regular-file identity, it
must declare direct filesystem mode unavailable and accept a caller-provided
immutable snapshot instead.

Stable absence retains only already-authorized semantic meaning:

- stable absence of `ai_canonical.json` may establish `MISSING_CANONICAL`;
- stable absence of `ai_manifest.json` may establish `MISSING_MANIFEST` after
  existing precedence;
- stable absence of `verification_keys.json` is signature evidence `ABSENT`;
- no trust-store option when membership is required may establish
  `TRUST_INPUT_NOT_PROVIDED`; but
- a trust-store path that was supplied and cannot be acquired is operational,
  not the same as no trust input.

An inaccessible directory, permission denial, failing `stat`/open/read, I/O
error, or path whose initial state cannot be established returns
`INPUT_IO_ERROR`. A known path observed present and then disappearing or being
replaced during acquisition returns `INPUT_CHANGED_DURING_SNAPSHOT`, not a
missing-file reason. These outcomes must never be collapsed into
`MANIFEST_NOT_JSON`, `SIGNATURE_INVALID`, or `TRUST_STORE_INVALID`.

### 9.4 Immutable snapshot and TOCTOU procedure

The direct-filesystem acquisition algorithm is normative at the behavior
level; platform system calls are implementation choices:

1. Open and retain a no-follow handle for the bundle directory. Establish that
   it is a directory. Perform the equivalent separately for a supplied trust
   path's parent.
2. Against the held directory handle, observe every known name. Open every
   present one without following links, retain its descriptor, and establish
   from the descriptor that it is a regular file. Record stable identity,
   length, and available change metadata. Record absent names for a second
   absence check.
3. Apply advertised per-file and aggregate byte ceilings. Read each retained
   descriptor from offset zero through EOF into a private buffer. Multiple
   low-level reads are allowed; “read once” means one acquisition through that
   descriptor and no later source reread.
4. A short low-level read is not itself failure; continue until EOF. An I/O
   error is `INPUT_IO_ERROR`. Premature EOF, growth, shrinkage, or length
   disagreement relative to the recorded regular-file state is
   `INPUT_CHANGED_DURING_SNAPSHOT`.
5. Recheck descriptor identity, file type, length, and available modification/
   change metadata; recheck that each directory entry still denotes the held
   identity and each recorded-absent name is still absent. Any observable
   change, disappearance, or path replacement is
   `INPUT_CHANGED_DURING_SNAPSHOT`.
6. Freeze the role-to-byte-buffer and role-to-absence map. Close filesystem
   handles only after the checks. From this point, perform every semantic step
   exclusively from those buffers.

In particular, dispatch, the selected manifest parse, raw-manifest signature
verification, and any later manifest access receive the same immutable
`ai_manifest.json` bytes. Canonical parsing and hashing use the same canonical
buffer. Keyring and trust evaluation likewise do not reopen their sources.

The policy requires observable-stability detection, not impossible atomicity
across unrelated files on a general filesystem. Holding all present
descriptors creates one bounded acquisition interval, but does not prove that
the files coexisted historically in that state. A hostile filesystem capable
of undetectable in-place mutation is outside direct-filesystem guarantees; use
an OS/content-store snapshot or the immutable-bytes input mode. Existing
bundle hashes and bindings evaluate the captured bytes but do not prove
cross-file filesystem atomicity.

### 9.5 Equivalent caller-provided snapshot

An API may accept one caller-provided immutable operation snapshot instead of
paths. It is equivalent only when, before verification begins, it fixes:

- the presence or absence of each known bundle role;
- the exact byte string for every present role;
- the optional trust-store byte string or explicit no-store state; and
- one input mode declaration, `IMMUTABLE_BYTES`.

The verifier copies or otherwise obtains an immutability guarantee for the
complete map, applies the same byte/total limits, and never invokes the
filesystem for those roles. The caller then owns provenance and atomic capture;
the verifier claims only to have evaluated that immutable map. A lazy stream,
mutable slice, callback that can return different bytes, or one-file-at-a-time
API without a frozen presence map is not equivalent.

## 10. Operational codes and exit codes

### 10.1 Existing exit-space audit

The published verify result binds `VALID` to exit 0 and `INVALID` to exit 2.
The published compare result uses exit 0 for `UNCHANGED`, exit 1 for
`NOT_COMPARABLE`, and exit 2 for `CHANGED` or `INVALID_BUNDLE`. No relevant
published verify or compare semantic result uses exit 3. Therefore exit 3 is
collision-free for the proposed tool-level operational outcome, provided the
future CLI reserves it and does not also use it for argument syntax.

This is **PROPOSED**, not a modification of the existing CLI contracts:

| Operation outcome | Exit code |
|---|---:|
| Semantic valid/success result | Existing 0 |
| Semantic comparison refusal | Existing 1 where the comparison contract defines it |
| Semantic invalid/changed result | Existing 2 according to the selected contract |
| Operational outcome | **3** |

An invocation that cannot be parsed has not started an operation and remains a
tool-usage concern; the future CLI must give it a documented code other than 0,
1, 2, or 3. This design does not assign that out-of-operation usage code.

### 10.2 Closed proposed operational-code vocabulary

The first operational transport should permit exactly these codes:

| `operational_code` | Exact use |
|---|---|
| `CAPABILITY_PROFILE_UNAVAILABLE` | The requested verifier capability/profile is not implemented or its required frozen table is unavailable |
| `INPUT_OUTSIDE_DECLARED_CAPABILITY` | Reached input is outside a selected restricted profile, such as a 641-digit v1 integer or non-ASCII timestamp digit under the portable profile |
| `RESOURCE_LIMIT_EXCEEDED` | A measured input property crosses an advertised file, aggregate, depth, or occurrence ceiling |
| `RESOURCE_EXHAUSTED` | Allocation, address space, stack, descriptor, or equivalent operational resource prevents completion before an advertised input ceiling |
| `INPUT_IO_ERROR` | Initial filesystem state, metadata, open, permission, or read operation fails without establishing a more specific stability/type outcome |
| `INPUT_NOT_REGULAR_FILE` | A direct input role is a symlink or is not a regular file, or the bundle root is not an eligible direct directory |
| `INPUT_CHANGED_DURING_SNAPSHOT` | A present/absent state, identity, length, metadata, or content acquisition changes observably during the snapshot interval |
| `INTERNAL_OPERATION_ERROR` | An unexpected verifier defect prevents a semantic decision and no narrower operational code applies |
| `OUTPUT_IO_ERROR` | The completed outcome cannot be written to the selected output sink |

The distinctions are actionable and implementable: capability can be changed,
a configured limit can be raised, transient exhaustion can be retried, I/O can
be repaired, file type can be corrected, and an unstable snapshot can be
reacquired. Permission failures do not need their own public code; they are
`INPUT_IO_ERROR`. Disappearance, replacement, premature EOF, and in-place
mutation do not need separate codes; they are one snapshot-stability failure.
None of these strings is an AELITIUM verification `reason`.

### 10.3 Closed supporting vocabularies

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

It is a role, never a local path. `limit` is null except when useful for
`RESOURCE_LIMIT_EXCEEDED`, `RESOURCE_EXHAUSTED`, or an outside-capability
boundary. When present it contains exactly:

```text
name                 # FILE_BYTES | TOTAL_SNAPSHOT_BYTES |
                     # STRUCTURAL_DEPTH | VALUE_OCCURRENCES |
                     # INTEGER_DECIMAL_DIGITS | TIMESTAMP_DIGIT_PROFILE
unit                 # BYTES | LEVELS | OCCURRENCES | DIGITS | PROFILE
maximum              # nonnegative integer, profile string, or null
observed_at_least    # nonnegative integer, profile string, or null
```

For a configured ceiling, `maximum` is required. `observed_at_least` may be
used when processing stopped at the first proof of excess; it need not reveal
or compute the final size. For unexpected allocation failure both numeric
values may be null. `detail` is null or non-normative human text. Consumers
must branch only on the closed fields and must not parse `detail`.

### 10.4 Output behavior

In the proposed `--operation-json` mode, stdout contains exactly one outer
tool-result object and one final LF for every semantic or operational outcome,
and the process exits according to that object's `rc`. Stderr is empty unless
the output channel itself fails. An `OUTPUT_IO_ERROR` is reported best-effort
on stderr and exits 3 because its JSON wrapper may be unwritable.

Existing human, `--json`, and `--contract-json` verify modes cannot represent
an operational outcome. They must emit no fake success/failure JSON and no
`INVALID`; they exit 3 and write one stable diagnostic line to stderr:

```text
AELITIUM_OPERATIONAL <operational_code> <phase> <input_ref-or-NONE>
```

Optional prose may follow on a second stderr line and is non-normative. This
keeps old semantic result schemas unchanged while giving scripts a stable
operational signal. Comparison must likewise stop operationally if verifying
either input produced no semantic result.

## 11. Future conformance model

### 11.1 Separate corpus and harness

Do not edit, renumber, or reinterpret the existing 44-case result-contract,
30-case v1 canonicalization, or 114-case v2 corpus. A later normative PR
should add a separate frozen family, provisionally:

```text
conformance/legacy_v1_operational_policy/
  manifest.json
  cases.json
  sources/
  expected/
  filesystem_recipes/
```

Each source case freezes exact bytes and SHA-256, selected capability including
all profile parameters, advertised limits, input mode, operation options, and
either the full expected semantic wrapper/result or full expected operational
wrapper. Expected output must not be generated at test time by the verifier
under test.

Filesystem and injected-resource cases additionally use language-neutral
recipes made of closed operations such as `CREATE_REGULAR`, `CREATE_SYMLINK`,
`CREATE_DIRECTORY`, `OPEN_REACHED`, `REPLACE_ENTRY`, `TRUNCATE_OPEN_FILE`, and
`FAIL_NEXT_ALLOCATION`. Synchronization points, not sleeps, trigger mutations.
The harness records whether a platform supplies each safely testable object
kind; the abstract input-adapter tests remain mandatory even where a host
cannot create a device or socket fixture.

Every implementation declaration states which proposed capability profiles it
implements. It must replay all applicable existing vectors unchanged. The five
114-corpus v1-route cases with an explicit CPython digit limit are run as
named-runtime compatibility cases; this preserves their frozen decisions
without claiming that those decisions are universal v1 semantics. The sixth
limit-annotated case retains its final-v2 isolation role.

### 11.2 Portable-v1 and named-profile cases

The future cases must cover all reached JSON-source positions—governed,
ignored, and overwritten—including canonical payload, manifest, keyring, and
trust store:

| Family | Required cases and assertions |
|---|---|
| Integer boundaries | Exact positive and negative 640-, 641-, 4,300-, 4,301-, and 10,000-digit tokens; profiles configured to 640, 4300, and 0; arbitrary `n`/`n+1`; portable cases at 640 produce semantic evaluation and above 640 produce `INPUT_OUTSIDE_DECLARED_CAPABILITY`; named cases follow section 6 |
| Programmatic integers | The same boundaries supplied as exact arbitrary-precision values, proving no silent binary64 coercion; values above a portable or named nonzero limit are operationally outside capability, while profile 0 evaluates them subject to resources |
| Dispatch isolation | Huge tokens before and after final v1 and v2 selectors; final v2 never falls back to v1; scanner traversal never applies the v1 digit guard |
| Timestamp ASCII | Exact shape, zero/out-of-range components, wrong separator, embedded LF, one final decoded LF, and two final decoded LFs |
| Timestamp profiles | At least one non-ASCII `Nd` code point accepted by a pinned table; one digit outside the selected table; the same spelling under portable and named profiles; table digest mismatch makes the requested capability unavailable |
| Deterministic duplicates | Exact and escaped-equivalent names with invalid-first/valid-final and valid-first/invalid-final values, proving last-name-wins and occurrence-wide integer conversion |
| Non-finites | Exact `NaN`, `Infinity`, and `-Infinity` in every applicable governed/ignored/overwritten location, plus near-miss spellings |
| Legacy strings | Permitted escaped unmatched high and low surrogates in ignored manifest extensions, matching key IDs, and labels; governed canonical rejection remains unchanged |
| Base64 aliases | Canonical and non-zero-unused-pad-bit encodings of the same 32-byte key and 64-byte signature, plus already-invalid alphabet/padding/length controls |
| Open-object behavior | Unknown fields at each accepted manifest/keyring level and rejected post-collapse trust-store unknowns according to the Phase 2 design |
| Empty trust | Empty `signers` array is structurally valid and establishes no membership |

For every outside-capability case, the expected object has
`outcome=OPERATIONAL_OUTCOME`, `rc=3`, `verification_result=null`, and no
assurance object. A paired named-profile case demonstrates the applicable
qualified semantic result. This proves that portable refusal is not serialized
as `INVALID`.

### 11.3 Operational-limit cases

For each advertised numeric ceiling, freeze valid sources immediately below,
exactly at, and immediately above it:

- structural depth, using section 9's container definition;
- per-source raw byte length;
- aggregate snapshot byte length; and
- total JSON value occurrences, including duplicates.

Below and at the ceiling must reach their semantic result. Above it must return
`RESOURCE_LIMIT_EXCEEDED` with the exact phase, role, limit name, maximum, and
minimum observed value. Add paired malformed sources whose first conclusive
syntax error is before versus after the first exceeded traversal boundary to
freeze section 9.2's order.

An injected allocator/stack adapter must fail at deterministic points in
dispatch, canonical parse, manifest parse, and signature-material parse. Each
returns `RESOURCE_EXHAUSTED`, never a JSON/signature/trust reason. At least one
case runs within all advertised minimums and is marked a conformance failure if
the implementation routinely exhausts there.

### 11.4 Filesystem and immutable-snapshot cases

The harness must prove:

- stable required-file absence retains the authorized missing reason, while
  stable optional keyring absence is signature `ABSENT`;
- a symlink and directory at every known file role are
  `INPUT_NOT_REGULAR_FILE` and are never followed/read;
- FIFO, device, and socket roles are rejected from metadata without opening
  content where safely constructible, with mandatory equivalent adapter tests;
- a permission failure and injected open, metadata, and read failures are
  `INPUT_IO_ERROR`;
- arbitrarily short successful read chunks are accumulated correctly;
- premature EOF, disappearance, directory-entry replacement, truncation,
  growth, and observable in-place mutation during synchronized acquisition are
  `INPUT_CHANGED_DURING_SNAPSHOT`;
- replacement after the immutable map is frozen does not alter the operation;
- manifest dispatch, manifest parsing, signature checking, and later access
  receive one byte-identical captured buffer, verified with read-call counters;
- caller-provided immutable bytes produce the same semantic result as the
  equivalent eligible file snapshot; and
- no operational case contains `status=INVALID`, an AELITIUM semantic reason,
  an assurance object, or a comparison result.

Add size/depth/resource cases with a final v2 selector. When acquisition or
dispatch cannot complete, the result is operational and no route is claimed;
when dispatch completes and selects v2, later v1 digit/profile logic is never
consulted and v2 failure never retries v1.

## 12. Effect on Verifier Contract Closure Phase 2

The statuses below mean “the policy blocker is resolved if this design is
published normatively”; they do not close the Phase 2 gaps or replace their
required schemas, grammar prose, and vectors.

| Gap | Impact | What this policy resolves | What Phase 2 still must publish |
|---|---|---|---|
| G-04 — `ai_manifest.json` | **UNBLOCKED_BY_POLICY** | Occurrence-wide integer handling, portable versus pinned-UCD timestamp digits, exact final-LF compatibility, deterministic last-name-wins/surrogate behavior, and I/O/resource separation | Versioned manifest schemas, complete v1/v2 source and field grammar, unknown-member policy, procedural validation order, and frozen cases |
| G-05 — `verification_keys.json` | **UNBLOCKED_BY_POLICY** | Huge ignored/overwritten integer behavior, last-name-wins source handling, opaque legacy strings, noncanonical unused pad bits, open members, and acquisition failure | Exact keyring schema/source profile, field domains, Base64 grammar, signature precedence, and frozen cases |
| G-06 — `aelitium-trust-v1` | **UNBLOCKED_BY_POLICY** | Huge overwritten integer behavior, post-collapse closure, opaque labels, Base64 aliases, empty signer list, duplicate-fingerprint behavior, and acquisition failure | Exact trust-store schema/source profile, membership/fingerprint rules, precedence, and frozen cases |

No new public semantic reason is needed for these closures. The operational
transport remains separate, and the exhaustive semantic reason/state registry
still belongs to G-08.

## 13. Effect on independent Go-verifier readiness

After this design—but before its normative adoption—the gap ledger is:

| Gap | Status after this design audit |
|---|---|
| G-01 | **CLOSED** |
| G-02 | **READY_TO_CLOSE**, still publicly OPEN until the policy PR is adopted |
| G-03 | **CLOSED** |
| G-04 | **OPEN**, policy blocker removed but Phase 2 closure unpublished |
| G-05 | **OPEN**, policy blocker removed but Phase 2 closure unpublished |
| G-06 | **OPEN**, policy blocker removed but Phase 2 closure unpublished |
| G-07 | **OPEN** — invocation grammar and ordered outcomes |
| G-08 | **OPEN** — exhaustive reason/assurance-state registry |
| G-09 | **READY_TO_CLOSE**, still publicly OPEN until the policy PR is adopted |
| G-10 | **OPEN** — self-contained language-neutral corpus operations/full outputs |
| G-11 | **OPEN** — Freshness calendar and timestamp edge semantics |
| G-12 | **DEFERRED** — complete comparison-output construction |
| G-13 | **CLOSED** |

Creating `aelitium-verifier-go` is **not appropriate after this design alone**.
The previously established minimum gate requires G-01, G-03, G-07, G-08,
G-09, and G-10 to be closed; G-07, G-08, and G-10 remain open, and G-09 is not
closed until this design is published. Complete bundle verification also needs
the G-04/G-05/G-06 Phase 2 contract. Deferring repository creation preserves
the clean-room rule rather than using implementation behavior to fill those
gaps. G-12 may remain deferred only while comparison is excluded from the
initial verifier scope.

## 14. IMPLEMENTATION CROSS-CHECK

This section is non-normative. It records observations at the stated baseline
only. The policy in sections 1–13 was derived first; none of the following code
is incorporated as protocol authority.

| Observed baseline behavior | Why it is not normative | Proposed boundary that contains it |
|---|---|---|
| The published/main verify CLI returns 0 for valid and 2 for invalid; compare additionally uses 1. No relevant command result reserves 3. Argument-parser errors may also use process-level conventions. | Process implementation and parser defaults cannot define protocol results. | Section 10 reserves proposed rc 3 only in a future tool transport and requires a distinct usage code. |
| Bundle checks use `Path.exists()`, `read_bytes()`, and `read_text()`; these follow ordinary path resolution, including symlinks, and do not reject non-regular input before opening. | Host path APIs and their defaults are implementation conveniences. | Sections 9.3–9.4 require no-follow regular-file acquisition or immutable bytes. |
| The manifest is initially read for dispatch, but an initial read error can lead to a later text read; signature checking can also reread the manifest on that fallback path. Keyring presence is checked separately from its later read. | Repeated reads can observe different bytes and are not an evidence semantic. | One held-descriptor snapshot supplies every later consumer; acquisition failure is operational. |
| There is no operation-wide immutable snapshot or cross-read mutation check. | Absence of a mechanism does not authorize claims of stable capture. | Section 9 defines observable stability and expressly disclaims cross-file atomicity. |
| The dispatch/v2 traversals were made iterative, but legacy `json.loads` remains recursion-sensitive; a current deep-v1 regression test expects a caught `RecursionError` to become `MANIFEST_NOT_JSON`. Broad parse catches can also absorb some resource exceptions. | Python stack depth is a host resource, not JSON grammar; a regression test cannot override Level 1 prose. | Recursion/stack exhaustion is `RESOURCE_EXHAUSTED`; advertised-depth conformance prevents routing or semantic reclassification. |
| Read/decode/parse operations use broad exception normalization: canonical read failures can become `CANONICAL_NOT_JSON`, manifest failures `MANIFEST_NOT_JSON`, keyring failures `SIGNATURE_INVALID`, and trust-store loading failures `TRUST_STORE_INVALID`. | An I/O or allocation failure does not establish the named semantic condition. | `INPUT_IO_ERROR`, `RESOURCE_EXHAUSTED`, and snapshot codes remain outside verification reasons. |
| Legacy integer conversion inherits `sys.set_int_max_str_digits`/interpreter configuration: the frozen probes demonstrate 640, 4300, and disabled profiles, and all occurrences are converted before ordinary map use. | An ambient CPython setting is neither a portable grammar nor an AELITIUM identifier parameter. | Section 6 provides portable operational refusal and explicit named-profile emulation. |
| The manifest timestamp uses Python regex `\d`; its accepted non-ASCII set follows the interpreter's Unicode database, while `$` accepts one final decoded LF. | A host Unicode database and regex anchor behavior are not language-neutral external references. | Section 7 freezes ASCII portable behavior, pinned UCD `Nd` tables, and the deterministic final-LF rule. |
| Current direct filesystem reads have no advertised file, aggregate, depth, or value-occurrence ceiling and do not distinguish dynamic exhaustion. | Undocumented machine capacity cannot be a semantic validity boundary. | Section 9 separates minimum conformance, advertised ceilings, and actual exhaustion. |

These discrepancies are reasons to publish the policy, not instructions to
copy current Python helpers. In particular, a future clean-room implementation
must not reproduce an accidental semantic mapping when the cause was
operational.

## 15. G-02 and G-09 verdicts

### G-02

**READY_TO_CLOSE**

The next normative PR can state, without an unstated oracle:

- the exact 640-digit portable domain;
- operational refusal outside that domain;
- the parameters and qualification required for named-runtime emulation;
- occurrence-wide handling of governed, ignored, and overwritten integers;
- ASCII versus frozen-UCD timestamp capability; and
- the deterministic portable legacy rules that must be reproduced.

This preserves the released identifier and does not turn verifier incapability
into universal bundle invalidity.

### G-09

**READY_TO_CLOSE**

The next normative PR can publish a separate operational transport, proposed
rc 3 and closed codes, exact limit layers and minimum envelope, traversal
semantics, and regular-file/immutable-snapshot behavior. No filesystem,
allocation, recursion, or resource decision remains dependent on Python as an
unstated oracle.

The next PR still must review and adopt the proposed names, schema the outer
transport, freeze the UCD tables and conformance operations, and update the
public gap ledger. Those are execution steps for a specified design, not
unresolved policy choices. If review declines either profile-qualified legacy
results or the separate operational envelope, G-02/G-09 must remain open; it
must not substitute semantic invalidity.

## 16. Final verdict

LEGACY_COMPATIBILITY_OPERATIONAL_POLICY_DESIGN_READY
