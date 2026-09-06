# V2 Manifest Timestamp Policy — Decision and Compatibility Audit

**Status:** DESIGN-DECISION-NON-NORMATIVE

**Audit date:** 2026-09-06

**Repository baseline:** `main` at
`468347011d6c21f64caf9895f3f899ea709d5da5`

**Scope:** the enabled/disabled `ai_manifest.json.ts_utc` check after exact
`aelitium_jcs_profile_v2` dispatch; the timestamp decision blocking G-04

This record selects the policy for later public specification review and
publication. It does not amend a Level 1 contract, close G-04, implement the
decision, or claim that the current Python verifier conforms to it. Phase 2
normative adoption and runtime alignment remain separate future workstreams.

## 1. Problem and source authority

Phase 2 adoption stopped because the public sources did not fully specify the
v2 manifest timestamp digit repertoire or decoded final-LF behavior. The
historical Phase 2 design recommended ASCII-only whole-string validation but
made that recommendation conditional on explicit review. The subsequently
adopted legacy policy defines v1 timestamp capability profiles; it does not
assign those profiles to v2.

The selected policy resolves that missing decision with one intrinsic v2
field rule. Its authority must come from future public publication, rather
than from the current Python regex or this internal record.

Sources audited under the existing hierarchy:

| Source | Role in this decision |
|---|---|
| [Verifier Protocol v1](../VERIFIER_PROTOCOL_V1.md), sections 2–6 | Normative hierarchy, implementation exclusion, compatibility/update rule, dispatch, and incorporated standards |
| [Canonicalization specification](../CANONICALIZATION_SPEC.md), portable-v2 sections | Strict recursive source/value profile, canonical bytes, unchanged hash inputs, and raw-manifest signature scope |
| [Legacy compatibility and operational policy](../LEGACY_V1_COMPATIBILITY_AND_OPERATIONAL_POLICY_V1.md), sections 3–6 | V1-specific timestamp profiles, fixed `V2_PORTABLE` declaration, and behavior of `V1_LEGACY_UNSUPPORTED` |
| [Independent verifier requirements](../INDEPENDENT_VERIFIER_REQUIREMENTS.md), verification order | Existing timestamp failure position and reason; clean-room requirements |
| [Phase 2 design](VERIFIER_CONTRACT_PHASE2_DESIGN.md), section 4.4 | Historical, non-normative ASCII/no-LF recommendation and disabled-validation analysis |
| [Independent Go design](INDEPENDENT_VERIFIER_GO_DESIGN.md), sections 11 and 21 | Historical missing timestamp grammar and the remaining implementation gate |
| [Portable-v2 design](CANONICALIZATION_V2_PORTABLE_DESIGN.md), section 4.3 | Non-normative design history preserving required fields and the timestamp-check position |
| [Frozen v2 corpus](../../conformance/canonicalization_v2/manifest.json) | Existing 114-case acceptance evidence; no replacement of prose by runner behavior |

Python observations appear only in section 7, labeled IMPLEMENTATION
CROSS-CHECK. No implementation is a normative oracle.

## 2. Selected enabled-validation rule

After exact v2 dispatch, successful source/profile parsing, manifest-object
validation, required-member checks, and identifier checks, apply the following
rule when `validate_manifest_timestamp=true`:

1. `ts_utc` must be a JSON string.
2. Its decoded value must consist of exactly 20 ASCII characters.
3. The complete decoded value must match:

   ```text
   [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z
   ```

4. Each digit must be U+0030 through U+0039. Separators and `T`/`Z` are the
   exact displayed ASCII characters.
5. No character may precede or follow that sequence. In particular, one or
   more decoded U+000A characters after `Z` are rejected. CR, CRLF, spaces,
   tabs, offsets, fractions, lowercase separators, and other suffixes are
   also rejected.

This is a whole-value rule, not a dependency on any regex engine's anchors or
character classes. An equivalent language-neutral test uses these zero-based
positions:

| Positions | Required decoded characters |
|---|---|
| 0–3, 5–6, 8–9, 11–12, 14–15, 17–18 | ASCII digits U+0030..U+0039 |
| 4, 7 | `-` |
| 10 | `T` |
| 13, 16 | `:` |
| 19 | `Z` |

No trimming, normalization, Unicode digit conversion, locale lookup, Unicode
`Nd` table, or ambient runtime rule is applied. A regex implementation must
enforce full consumption and ASCII digits explicitly; copying `\d` or
relying on `$` alone is insufficient.

The 20-character requirement concerns the decoded string, not its JSON source
byte length. A source escape such as `\u0032` can decode to an accepted ASCII
digit. A source `\n` or `\u000A` after `Z` decodes to a forbidden suffix.
Such escapes are not stripped, and the original manifest bytes are preserved.

### Failure classification and precedence

If this reached field check fails, the semantic result is
`MANIFEST_BAD_TS_UTC` under the existing verification contract. A non-ASCII
digit is a field-syntax failure under v2, not
`INPUT_OUTSIDE_DECLARED_CAPABILITY`. No new semantic or operational reason is
needed.

Existing earlier failures retain precedence: canonical parsing, manifest
source/profile parsing, root type, missing required fields, and bad manifest
identifiers. The timestamp check remains before manifest digest-shape and
subsequent payload-integrity checks. It does not move to dispatch or signature
verification. A resource/acquisition failure still follows G-09 and cannot be
converted to a timestamp failure.

### Lexical scope only

The rule does not validate component ranges, a calendar, leap years, leap
seconds, chronology, or historical time. Both
`0000-00-00T00:00:60Z` and `9999-99-99T99:99:99Z` pass this lexical rule.
That does not establish that either denotes real calendar time. No datetime
parser or RFC 3339 validation is introduced.

## 3. Disabled validation

When `validate_manifest_timestamp=false`:

- `ts_utc` remains required at the existing required-member position;
- no manifest timestamp type, spelling, range, or calendar check occurs;
- a v2-valid non-string value, including `{}`, `null`, a boolean, an array,
  or an in-profile number, can satisfy this member-presence requirement; and
- every source and recursively contained value still has to satisfy the
  ordinary v2 JSON/value profile.

Disabling the field check cannot admit malformed UTF-8/JSON, duplicate names,
unmatched surrogates, excluded noncharacters, non-finite values, or out-of-range
v2 numbers. Those remain source/profile failures at their established
positions. A missing `ts_utc` remains `MANIFEST_MISSING_FIELD`; it does not
become optional. Other manifest fields and later checks are unaffected.

An otherwise processable bundle with `ts_utc="not-a-timestamp\n"` may pass
with validation disabled. This is the intentional existing option boundary,
not a second timestamp profile.

## 4. Capability and dispatch independence

The rule is intrinsic to `aelitium_jcs_profile_v2` / `V2_PORTABLE`. All
conforming implementations evaluate the same enabled syntax and disabled
behavior within their declared operational limits.

It does not depend on `V1_RESTRICTED_PORTABLE`,
`V1_FROZEN_LEGACY_COMPATIBILITY`, `V1_NAMED_RUNTIME_COMPATIBILITY`, a frozen
Unicode `Nd` profile, or the host Unicode database. No v1 profile is borrowed
as an implicit default for v2, and no timestamp-profile parameter is added to
the `v2` capability object.

With `v1.capability=V1_LEGACY_UNSUPPORTED`, successful exact v2 dispatch still
uses this same rule. Unsupported v1 produces its existing operational outcome
only if dispatch selects the legacy/error-resolution route. Rejected v2
timestamps never cause a v1 retry. Unavailable explicitly requested setup
capabilities still obey the existing capability-selection prerequisite; this
decision does not waive that prerequisite or promise that the whole verifier
implements unrequested legacy functionality.

`AELITIUM-DISPATCH-JSON-1` remains structural/lexical only. It consumes the
complete immutable manifest, considers only the final decoded top-level
selector, and does no timestamp validation. Valid source containing Arabic-
Indic digits or an escaped final LF still routes to v2 when the selector is
exact v2; the later enabled field check then rejects it. Parser output is
never borrowed from dispatch.

## 5. Separation from other contracts

### JSON, JCS, source profile, and schemas

[RFC 8259, December 2017, sections 2 and 7](https://www.rfc-editor.org/rfc/rfc8259.html#section-7)
defines JSON source/string syntax, not the application meaning of `ts_utc`.
An escaped LF and Arabic-Indic characters may be valid JSON string content
while failing this specific enabled field rule.

[RFC 8785, June 2020, section 3.2](https://www.rfc-editor.org/rfc/rfc8785.html#section-3.2)
governs canonical serialization, including string escaping and property order.
This decision changes none of those operations. The exact editions, subsets,
and errata policy in `VERIFIER_PROTOCOL_V1.md` remain authoritative. No new
external standard is incorporated.

The full v2 scalar/noncharacter, number, duplicate, and UTF-8 profile remains
unchanged. Ordinary v2 strings elsewhere do not become ASCII-only. Manifests
retain `schema="ai_pack_manifest_v1"`; no new evidence member is introduced.

Phase 2 should keep `ts_utc` required but unconstrained in the option-independent
manifest schema, with the conditional type/spelling rule in procedural prose.
A validation-enabled schema view, if later provided, must combine string type,
length exactly 20, and the ASCII pattern. An unconditional timestamp string
constraint would wrongly narrow disabled validation. JSON Schema cannot
replace source-level validation or choose public error precedence.

### Freshness G-11

The field governed here is `ai_manifest.json.ts_utc`. Freshness uses the
separate `ai_canonical.json.ts_utc` and explicit Freshness inputs. Neither
manifest lexical acceptance nor disabling this manifest check changes
Freshness, supplies a clock, computes age, or establishes calendar validity.
G-11 remains OPEN.

### Three different newline locations

| Location | Effect of this decision |
|---|---|
| Decoded `ai_manifest.json.ts_utc` string | With validation enabled, no LF after `Z` is accepted |
| Whitespace outside strings in the raw manifest JSON text | Existing source grammar remains; allowed terminal whitespace is still included in raw-manifest signature scope |
| End of stored `ai_canonical.json` | Existing storage allowance remains exactly `C` or `C || LF`; only `C` is hashed |

There is no rule to strip the raw manifest's terminal LF or to remove any
signed bytes. Signatures still cover the identical immutable raw manifest
used for dispatch/parsing. Canonical payload bytes, governed hash inputs,
comparison bases, and assurance meanings are unchanged by this field decision.

## 6. Compatibility, identifiers, and hierarchy review

The selected classification is **UNRELEASED IMPLEMENTATION DISCREPANCY**:
the current Python v2 checker admits host-Unicode digits and one decoded final
LF beyond the selected portable field rule. That acceptance is recorded as
implementation evidence, not adopted as normative v2 compatibility behavior.

Choosing the current regex as authority would leave independent implementations
dependent on an unspecified host database and anchor behavior. Importing v1's
named profiles would instead add an unrequested v2 negotiation mechanism and
leave v2 dependent on a v1 capability that may be disabled. Neither is the
selected policy.

The Level 1 requirement for a syntactic `YYYY-MM-DDTHH:MM:SSZ` check and the
portable-v2 text preserving existing required fields and ordered checks do
not pin a Unicode digit repertoire or a permissive end anchor. Under the
protocol's implementation-exclusion rule, those phrases cannot implicitly
incorporate Python's regex. The historical ASCII recommendation is Level 4;
it supplies design context, not a competing public contract.

| Question | Determination and basis |
|---|---|
| A. Change released v0.4.0 behavior? | **No.** Released artifacts use the v1 identifier. The v1 runtime path, compatibility profiles, Unicode tables, final-LF rule, and timestamp-disabled behavior are outside this change. |
| B. Change only unreleased v2 behavior? | **Yes, on future alignment.** Enabled v2 verification will reject currently accepted non-ASCII digits and a single final decoded LF at the existing timestamp stage. Disabled validation and unrelated checks retain their meanings. This design file itself changes no runtime. |
| C. Require a new canonicalization identifier? | **No for this decision.** It resolves an unclosed application-field grammar without changing the specified JSON/JCS algorithm, source/value profile, hash material, or raw signature scope. No identified normative v2 rule or frozen expectation promises the disputed acceptance. `aelitium_jcs_profile_v2` is retained through explicit specification publication and separate correction of its unreleased checker. |
| D. Require a new capability identifier? | **No.** The complete intrinsic v2 field check belongs to the existing `V2_PORTABLE` capability; there are no alternate v2 timestamp behaviors to advertise. |
| E. Require a v2 timestamp-profile field? | **No.** The existing `v2` declaration remains `{"capability":"V2_PORTABLE"}`. Timestamp-profile parameters remain confined to their already-defined v1 uses. |

Keeping identifiers is not justified merely by the word “unreleased” or by
unchanged canonical bytes. Protocol section 3 still requires an explicit,
reviewed specification revision, compatibility statement, and conformance
impact analysis. Future publication must identify the narrower acceptance
relative to current Python, preserve the legacy contract, and explicitly
qualify any implementation-alignment claims. This is not an assertion that
current v2 runtime acceptance is unchanged.

The frozen 114-case v2 data was inspected without generating expectations or
importing production code: all source digests matched; all 114 IDs were unique;
38 sources had role `manifest`. Thirty-three were decodable object sources for
timestamp extraction, each stored timestamp occurrence being
`2026-01-01T00:00:00Z`. The other five were malformed sources or a non-object
root with earlier outcomes. No frozen case requires v2 acceptance of a
Unicode-digit or final-decoded-LF timestamp. This is a conformance-impact
finding, not proof of a new implementation passing the corpus. Existing
44/30/114/94 expected results must remain unchanged.

The review therefore identifies no higher-level contradiction. This record
does not override the protocol's conflict rule or grant a general exception to
identifier stability: a contradictory normative promise, if found during
publication, must be resolved explicitly before proceeding.

## 7. IMPLEMENTATION CROSS-CHECK

**IMPLEMENTATION CROSS-CHECK — non-normative, read-only.** At the audited
baseline, [the shared constant](../../engine/ai_contract.py) is:

```text
^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$
```

[The current verifier](../../engine/ai_verify.py) applies it with `re.match`
after either selected manifest parse. A non-string is tested as an empty
string when validation is enabled. With validation disabled, this check is
skipped. The shared check is why v2 inherits host-Unicode digit membership and
the special final-LF behavior; these observations are not a source of truth
for the selected policy.

Probes were repeated with `.venv/bin/python -B`, Python **3.12.3**, host Unicode
database **15.0.0**. Host version is observation metadata only. They reused the
unchanged unsigned/unbound fixture in `conformance/fixtures/bundles/unbound/`,
replaced only manifest `canonicalization` and `ts_utc` in memory, and intercepted
manifest byte reads for that invocation. No runtime file or fixture was edited.
The ordinary verifier, dispatcher, parsers, and timestamp check were unchanged.
All probes used default options except the stated validation boolean.

Every v2 probe was confirmed to dispatch to `aelitium_jcs_profile_v2`, and its
manifest passed the strict v2 source/value parser before field validation.
`\n` in this table means one decoded U+000A, represented by a JSON escape in
the input. `T` and `Z` remain ASCII in the digit-substitution probes.

| Probe | Validation | Current Python result | Selected rule for an otherwise valid bundle |
|---|---|---|---|
| `2026-01-15T12:00:01Z` | enabled | `VALID / OK` | `VALID / OK` |
| Same ASCII timestamp plus `\n` | enabled | `VALID / OK` | `INVALID / MANIFEST_BAD_TS_UTC` |
| Same digits replaced by Arabic-Indic U+0660..U+0669 | enabled | `VALID / OK` | `INVALID / MANIFEST_BAD_TS_UTC` |
| Same ASCII timestamp plus `\n\n` | enabled | `INVALID / MANIFEST_BAD_TS_UTC` | Same failure |
| `2026-01-15T12:00:01Z` | disabled | `VALID / OK` | `VALID / OK` |
| `{}` | disabled | `VALID / OK` | `VALID / OK` |
| Same digits replaced by fullwidth U+FF10..U+FF19 | enabled | `VALID / OK` | `INVALID / MANIFEST_BAD_TS_UTC` |
| `9999-99-99T99:99:99Z` | enabled | `VALID / OK` | `VALID / OK`; lexical only |
| `not-a-timestamp\n` | disabled | `VALID / OK` | `VALID / OK` |

The nine probes were also run with the exact v1 selector; their current results
were identical to the current-result column. Those are controls for later v1
non-impact testing, not a change to the adopted v1 capability policy. Portable
v1 refusal versus named-profile Unicode evaluation continues to follow that
separate policy.

The current runtime has no implementation of the adopted capability-selection
transport. An exact-v2 operation with `V1_LEGACY_UNSUPPORTED` is therefore a
future contract/harness test, not an executed Python capability test here.

## 8. Minimum future conformance design

These are planned tests, not added or frozen vectors. Except for explicit
source/profile/precedence controls, use otherwise valid unsigned/unbound
bundles, exact v2 dispatch, and no Freshness policy. Freeze complete input bytes,
options, selected capability, and stable expected reason/state when the
future corpus is created; never generate expectations with the checker under
test.

| Family | Minimum inputs and future expectation |
|---|---|
| Ordinary ASCII | Exact 20-character value passes; JSON-escaped ASCII digits decode to the same accepted value |
| Unicode digits | Arabic-Indic U+0660..U+0669 and fullwidth U+FF10..U+FF19 each fail enabled validation with `MANIFEST_BAD_TS_UTC`; test literal UTF-8 and escaped JSON spellings |
| Decoded final LF | One LF and two LFs each fail with `MANIFEST_BAD_TS_UTC`; cover `\n` and `\u000A` |
| Other shape errors | Malformed separators, lowercase `t`/`z`, leading/trailing whitespace, 19/21-character values, CR/CRLF, offsets, and fractions fail at the timestamp stage |
| Lexical/calendar separation | `0000-00-00T00:00:60Z` and `9999-99-99T99:99:99Z` pass lexical validation without a calendar claim |
| Disabled string | Ordinary timestamp and a malformed timestamp string, including a decoded LF, pass this field check |
| Disabled non-string | V2-valid `{}` and `null` pass the presence-only check; with validation enabled they fail `MANIFEST_BAD_TS_UTC` |
| Required/profile controls | Missing `ts_utc` still fails `MANIFEST_MISSING_FIELD` in both option states; source/profile-invalid content remains subject to the existing earlier failure in both states |
| Precedence | Earlier canonical-parse, manifest-source/profile, root-type, required-member, and identifier errors win; a reached bad timestamp wins over a bad digest or later signature/binding error |
| V1 non-impact | Replay released v1 behavior and the existing portable/named-profile timestamp matrix unchanged, including its final-LF rule and integer isolation; do not apply v2's ASCII rejection to v1 |
| V1 independence | Repeat exact-v2 cases with each valid v1 capability declaration, including `V1_LEGACY_UNSUPPORTED`, varying named v1 Unicode profiles; enabled/disabled v2 outcomes must be identical and there must be no legacy retry |
| Newline and signature boundaries | Valid timestamp with raw manifest terminal whitespace retains existing acceptance and exact signature scope; stored canonical `C` and `C || LF` retain their existing digest behavior |

The unsupported-v1 case must test both a valid timestamp and a bad timestamp;
the latter proves that failure remains `MANIFEST_BAD_TS_UTC` rather than a
legacy capability outcome. It must not simulate an unavailable v1 profile
setup failure and then incorrectly expect that prerequisite to be bypassed.

All existing frozen corpora stay unchanged. A separate future set must expose
the presently failing v2 expectations without treating the existing Python
acceptance column as the oracle.

## 9. Required future work and readiness impact

### Public adoption and runtime alignment

After review, Phase 2 can publish the exact rule, conditional schema/procedural
boundary, compatibility statement, and new frozen cases. That specification
work must record the discrepancy and must not claim that Python already
implements the newly precise v2 verifier surface.

A **separate guarded runtime-alignment workstream** is required before any
future v2 release or claim of complete implementation alignment. It must:

1. pin and verify its own repository baseline and approved scope;
2. align only the reached v2 manifest timestamp check with sections 2 and 3;
3. retain the complete v1 path, existing public reasons and precedence,
   dispatch behavior, disabled-validation behavior, hashes, and raw signatures;
4. test the future cases, released-v1 compatibility matrix, existing frozen
   corpora, and repository validation gates; and
5. report the acceptance difference and remaining verifier gaps honestly.

This record does not authorize starting that implementation, adding CLI
capability support, implementing operational transport, or acquiring filesystem
snapshots. Those broader runtime contracts remain outside this focused fix.

### Gap effects

G-04_TIMESTAMP_BLOCKER_RESOLVED_BY_DECISION

This is resolution of the timestamp policy choice only. G-04 itself remains
**OPEN — UNBLOCKED_BY_POLICY** until the complete manifest contract, schemas,
ordered checks, and frozen Phase 2 evidence are published. This record supplies
enough precision for a later Phase 2 readiness audit to resume; it does not
resume that workstream or assert that no other issue can be discovered.

G-05 and G-06 remain **OPEN — UNBLOCKED_BY_POLICY**, unchanged by this decision.
It assigns no source, Base64, signature, keyring, trust-store, or membership
semantics to either gap. G-01/G-02/G-03/G-09/G-13 remain CLOSED;
G-07/G-08/G-10/G-11 remain OPEN; G-12 remains DEFERRED. Historical design
verdicts are not rewritten.

Creating or implementing `aelitium-verifier-go` remains **NOT_READY**. The
existing minimum gate still requires G-07, G-08, and G-10 closure, and complete
bundle verification still needs G-04/G-05/G-06. This decision does not establish
an independent verifier, provider execution, historical occurrence, semantic
truth, trusted time, or any additional assurance claim.

## 10. Decision verdict

The selected semantics are exact and language-neutral, introduce no host
Unicode dependency or unstated runtime oracle, preserve released v1, and have
an explicit public-adoption and separate runtime-alignment path. No unresolved
timestamp policy choice remains in this record. Readiness here concerns the
decision, not completion of Phase 2 or runtime conformance.

V2_MANIFEST_TIMESTAMP_POLICY_DECISION_READY
