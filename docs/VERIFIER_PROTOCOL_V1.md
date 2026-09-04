# AELITIUM Verifier Protocol v1

**Status:** IMPLEMENTATION-ALIGNED-UNRELEASED

**Scope:** normative source hierarchy, canonicalization-version registry,
pre-dispatch routing, and external-standards registry for AELITIUM bundle
verification

This document is a public protocol contract for the current unreleased
verifier surface. It closes specification gaps G-01, G-03, and G-13 from the
independent Go-verifier readiness audit. It does not close the other gaps in
that audit, change released v0.4.0 behavior, or assert that an independent
verifier exists.

## 1. Purpose and interpretation

An independent implementer needs a stable answer to three questions before
implementing any verification rule:

1. which sources define AELITIUM behavior;
2. how the manifest selects the released legacy or unreleased portable
   canonicalization path; and
3. which exact editions and portions of external standards are incorporated.

This document supplies those answers. The words “must”, “must not”, “required”,
“should”, and “may” state protocol requirements in this document. Examples and
implementation notes do not acquire authority merely by resembling normative
text.

## 2. Normative source hierarchy

The hierarchy is ordered by role. A lower level cannot override a higher
level. A contradiction between normative sources is a specification defect,
not permission to select a convenient outcome.

Document status labels record release, alignment, or readiness state; they do
not alter the normative role assigned here. In particular, an
`IMPLEMENTATION-ALIGNED` label does not make implementation code authoritative,
and the `RESEARCH` label on the acceptance requirements records remaining
readiness gaps rather than delegating specified behavior to Python.

### Level 1 — AELITIUM protocol contracts

Level 1 consists of the applicable versioned AELITIUM prose contracts and
schemas:

- this [`VERIFIER_PROTOCOL_V1.md`](VERIFIER_PROTOCOL_V1.md) integration
  contract;
- [`CANONICALIZATION_SPEC.md`](CANONICALIZATION_SPEC.md);
- [`CANONICAL_REQUEST.md`](CANONICAL_REQUEST.md);
- [`INVOCATION_ASSURANCE.md`](INVOCATION_ASSURANCE.md), within its explicitly
  documented scope and limitations;
- [`TRUST_BOUNDARY.md`](TRUST_BOUNDARY.md);
- [`VERIFICATION_RESULT_V1.md`](VERIFICATION_RESULT_V1.md);
- [`ASSURANCE_RESULT_V1.md`](ASSURANCE_RESULT_V1.md);
- [`CLAIM_BOUNDARIES_V1.md`](CLAIM_BOUNDARIES_V1.md);
- [`COMPARE_RESULT_V1.md`](COMPARE_RESULT_V1.md);
- the acceptance requirements in
  [`INDEPENDENT_VERIFIER_REQUIREMENTS.md`](INDEPENDENT_VERIFIER_REQUIREMENTS.md);
  and
- the applicable versioned schemas:
  [`ai_output_v1.json`](../engine/schemas/ai_output_v1.json),
  [`verification_result_v1.json`](../engine/schemas/verification_result_v1.json),
  [`assurance_result_v1.json`](../engine/schemas/assurance_result_v1.json), and
  [`compare_result_v1.json`](../engine/schemas/compare_result_v1.json).

A schema is normative only for the contract that explicitly names it. The
absence of a schema does not delegate a decision to an implementation. A prose
contract and its named schema are required to agree. If they do not, contract
review must stop until the conflict is resolved by a versioned specification
change.

Links from these documents to Python files describe implementation alignment
or audit evidence only. Such links do not promote source code into Level 1.

### Level 2 — incorporated external standards

Only the exact documents, editions, and portions listed in section 6 are
incorporated. An external standard has authority only for the use and subset
stated in that registry. AELITIUM profiles may explicitly narrow an external
standard's input domain or add an envelope rule; an unstated difference is a
specification defect.

Transitive references, later editions, replacement standards, living-standard
changes, and published errata do not automatically enter this level.

### Level 3 — frozen AELITIUM conformance data

Level 3 consists of the frozen data referenced by:

- [`conformance/manifest.json`](../conformance/manifest.json), currently 44
  result-contract cases;
- [`conformance/canonicalization/manifest.json`](../conformance/canonicalization/manifest.json),
  currently 30 released-v1 canonicalization cases; and
- [`conformance/canonicalization_v2/manifest.json`](../conformance/canonicalization_v2/manifest.json),
  currently 114 unreleased portable-v2 cases.

Frozen source bytes, expected bytes, digests, decisions, reasons, states, and
routes are normative examples and acceptance evidence within their declared
scope. Runner code is not normative. A vector must not silently redefine
contradictory Level 1 prose or a Level 2 algorithm. Such a contradiction blocks
conformance and requires specification review; an implementer must not choose
whichever side matches an existing implementation.

### Level 4 — explanatory and non-normative material

Architecture notes, tutorials, design histories, audits, demonstrations,
roadmaps, dependency recommendations, internal documents, and quarantined or
explicitly non-normative documents are Level 4. They may explain a contract but
cannot add, remove, or override a verification requirement.

In particular,
[`internal/CANONICALIZATION_V2_PORTABLE_DESIGN.md`](internal/CANONICALIZATION_V2_PORTABLE_DESIGN.md)
records the approved design history, and
[`internal/INDEPENDENT_VERIFIER_GO_DESIGN.md`](internal/INDEPENDENT_VERIFIER_GO_DESIGN.md)
records a readiness audit. Neither is required to implement the public
dispatch contract in section 5.

## 3. Implementation exclusion, conflicts, and updates

The Python implementation is not a normative source. A Go, Rust, or other
implementation is also not a normative source. No implementation may resolve
an undocumented choice by importing, translating, observing, or copying
another implementation's private decision path.

Behavior discovered outside the published contract must be reported as a
specification defect. During maintenance, a separately labeled implementation
cross-check may show that prose and deployed behavior differ; that observation
does not itself change the protocol. In particular, an implementer must not
choose whichever outcome matches Python.

When any two Level 1 sources conflict, or when a Level 1 rule cannot be
reconciled with an incorporated Level 2 requirement, specification review must
fail closed. Level 3 data cannot break the tie. Level 4 text and implementation
behavior have no tie-breaking authority.

A normative update requires all of the following that apply:

1. an explicit, reviewed, versioned AELITIUM specification change;
2. a compatibility statement describing whether accepted inputs, rejected
   inputs, canonical bytes, hashes, reasons, assurance states, comparison
   outcomes, or claim boundaries change;
3. an update to affected schemas and frozen conformance data; and
4. a new identifier or contract version whenever behavior changes incompatibly.

There is no silent semantic drift under an existing canonicalization or result
identifier. A clarification may retain an identifier only when its compatibility
statement establishes that the governed behavior is unchanged. A
behavior-changing standards update, security correction, parser rule, or
serialization change requires versioned review and conformance-impact analysis.

## 4. Canonicalization-version registry

The manifest member name is exactly `canonicalization`. The currently
recognized values are:

| Identifier | Status | Selected behavior |
|---|---|---|
| `json_sorted_keys_no_whitespace_utf8` | Released legacy identifier used by v0.4.0 | Complete frozen v1 behavior in `CANONICALIZATION_SPEC.md`, including its documented compatibility limits |
| `aelitium_jcs_profile_v2` | Portable identifier implemented in the unreleased repository state | Complete portable-v2 profile in `CANONICALIZATION_SPEC.md` |

Identifiers are opaque and case-sensitive. There are no aliases, prefixes,
case folding, filename negotiation, payload-content negotiation, heuristic
fallbacks, or “closest supported” versions. The payload cannot override the
enclosing manifest. An unknown identifier never selects a version by
similarity.

## 5. `AELITIUM-DISPATCH-JSON-1`

### 5.1 Purpose and input

`AELITIUM-DISPATCH-JSON-1` is a non-observable structural lexical lookahead.
Its sole purpose is to decide whether the manifest must enter the portable-v2
path without narrowing the released v1 path.

The input is the original immutable byte sequence read from
`ai_manifest.json`. The scanner does not receive a decoded string, parsed
object, normalized form, or reconstructed file. Required option and file
presence checks that precede content processing remain outside this scanner.

A scanner result is not a verification result and cannot override an earlier
observable canonical-payload result. Version-specific verification retains its
documented order; canonical-payload parsing remains observable before manifest
parsing.

### 5.2 Union grammar

The scanner recognizes exactly one complete value in this case-sensitive
grammar. The notation uses the RFC 8259 definition of `string`; `digit` means
ASCII `%x30-39`, `digit-1-9` means ASCII `%x31-39`, and hexadecimal digits are
ASCII `0-9`, `A-F`, or `a-f`. `%xNN` below denotes the single octet whose
hexadecimal value is `NN`.

```text
dispatch-text     = ws dispatch-value ws
dispatch-value    = false / null / true / dispatch-object /
                    dispatch-array / number / string / legacy-constant
dispatch-object   = begin-object
                    [ dispatch-member *( value-separator dispatch-member ) ]
                    end-object
dispatch-member   = string name-separator dispatch-value
dispatch-array    = begin-array
                    [ dispatch-value *( value-separator dispatch-value ) ]
                    end-array
legacy-constant   = "NaN" / "Infinity" / "-Infinity"
number            = [ "-" ] int [ frac ] [ exp ]
int               = "0" / ( digit-1-9 *digit )
frac              = "." 1*digit
exp               = ( "e" / "E" ) [ "+" / "-" ] 1*digit
begin-array       = ws %x5B ws
begin-object      = ws %x7B ws
end-array         = ws %x5D ws
end-object        = ws %x7D ws
name-separator    = ws %x3A ws
value-separator   = ws %x2C ws
ws                = *( %x20 / %x09 / %x0A / %x0D )
```

The literal spellings are exact ASCII. The grammar does not admit a leading
plus, `-NaN`, `+Infinity`, lowercase non-finite aliases, comments, trailing
commas, concatenated top-level values, or a literal embedded in a longer token.
The union grammar is intentionally broader than RFC 8259 only by the three
listed legacy constants. It adds no other v1 extension.

Strings use the RFC 8259 lexical grammar. Raw quotation mark, reverse solidus,
and U+0000 through U+001F are forbidden inside a string. The only short escapes
are `\"`, `\\`, `\/`, `\b`, `\f`, `\n`, `\r`, and `\t`; `\u` must be followed
by exactly four hexadecimal digits.

Every individually well-formed `\uXXXX` escape is admitted during dispatch,
including an unmatched or reversed surrogate escape and a Unicode
noncharacter. Unescaped non-ASCII string content must be shortest-form UTF-8
for a Unicode scalar value. Ill-formed UTF-8, an encoded surrogate, and a
leading UTF-8 BOM are outside the grammar. U+FEFF inside a string is ordinary
content.

A number has no digit-count or host-width limit at this stage. It is consumed
as a token and is never converted to an integer, decimal, binary32, binary64,
or other host number.

### 5.3 Scanner requirements

The scanner must use iterative structural traversal with explicit frames; its
routing result must not depend on a host-language recursion limit. It must
consume the complete source, allowing only the four `ws` octets outside
values. Seeing a possible selector does not permit early success: every later
member, nested value, closing delimiter, and trailing octet must still be
scanned.

The scanner performs structural and lexical routing only. It must not:

- convert a number or apply an integer digit limit;
- validate a schema;
- reject duplicate member names;
- collapse member occurrences into a map;
- canonicalize any value or rewrite any source byte;
- normalize Unicode;
- apply scalar/noncharacter rules to escaped code units;
- apply any portable-v2 number, string, object, or extension profile; or
- reuse a scanner-derived value in either version parser.

The scanner retains, conceptually or concretely, the original byte span and raw
lexeme for every string, number, and legacy constant; every object-member
occurrence in source order, including duplicates; array order; and enough
array/object nesting to distinguish root members from nested members. This
retention exists only for correct scanning and conformance diagnostics. Nested
members named `canonicalization` never select a version.

### 5.4 Selector comparison

For each root member name, create a comparison view only. Short JSON escapes
map to their represented character. A `\uXXXX` high surrogate immediately
followed by a `\uXXXX` low surrogate maps to the corresponding non-BMP scalar.
An unmatched surrogate remains an unmatched comparison element and is not
rejected by the scanner. No normalization or scalar-validity check occurs.

A root name is a selector occurrence only when its comparison view is exactly
the 16 ASCII characters `canonicalization`. Thus escaped forms such as
`"\u0063anonicalization"` are recognized. The raw member-name bytes are not
changed.

Process every selector occurrence from left to right and retain the final one,
even when earlier occurrences have different types or values. If the final
value is a string, form its comparison view by the same escape rules. Only an
exact case-sensitive comparison with a registry value can select that value.
The final root occurrence controls routing.

### 5.5 Routing algorithm

Apply these steps exactly:

1. Scan the original manifest bytes as one complete
   `AELITIUM-DISPATCH-JSON-1` value. Do not partially dispatch from a selector
   observed before the end of the source.
2. If the complete root is an object, identify the final root selector under
   sections 5.3 and 5.4. A non-object root has no selector.
3. If and only if the final selector is a string whose comparison view equals
   `aelitium_jcs_profile_v2`, select portable v2. Discard every scanner-derived
   view. When verification reaches manifest parsing, re-read and reparse the
   original bytes from byte zero under the complete v2 rules. A v2 parse or
   profile failure never retries under v1.
4. Every other successfully scanned selector outcome enters the complete
   frozen legacy/error-resolution route using the original bytes. This
   includes exact v1, a missing selector, an unknown string, a non-string final
   selector, and a non-object root. Exact v1 can complete v1 verification;
   other outcomes are not deemed valid v1 selections.
5. A lexical or structural syntax failure also enters the frozen
   legacy/error-resolution route using the original bytes. Malformed dispatch
   syntax is not described as valid v1. The legacy verifier determines the
   public reason at its existing parse, object, required-field, schema,
   input-schema, or canonicalization step and thereby preserves failure
   precedence.

The scanner must not emit `MANIFEST_BAD_CANONICALIZATION` merely because it
observed a missing, unknown, or non-string value. For example, an earlier
missing `schema` remains `MANIFEST_MISSING_FIELD`, and an earlier bad schema
remains `MANIFEST_BAD_SCHEMA`, when the legacy route reaches those checks.

The only additive version-selection branch is exact portable v2. There is no
heuristic version retry.

### 5.6 Byte preservation and signature scope

The scanner must not rewrite, normalize, re-encode, truncate, or append to the
manifest byte sequence. Both selected version paths receive exactly the
original source bytes from byte zero. Scanner lexemes and comparison views are
never parser output.

When signature verification is evaluated, it uses the same immutable raw
manifest bytes, including member order, whitespace, unknown fields, escape
spellings, line endings, and terminal bytes. The manifest is not
JCS-canonicalized for signature scope.

### 5.7 Syntax failure versus operational failure

Scanner syntax failure and operational or resource failure are distinct.
Syntax failure follows step 5 above so that the legacy route resolves the
public semantic reason. Allocation failure, an implementation resource
ceiling, input-size exhaustion, or another operational failure must not select
v1, must not change a previously observed selector, and must not become
`MANIFEST_NOT_JSON`, `MANIFEST_BAD_CANONICALIZATION`, or another AELITIUM
semantic result.

This document intentionally does not define the external representation,
minimum supported limits, exit status, or recovery behavior for an operational
failure. That contract remains specification gap G-09. Until G-09 is closed,
an implementation must keep such failures on a separately typed operational
path and must not manufacture a protocol result.

## 6. External-standards registry

### 6.1 Incorporation rule

The following table is exhaustive for external standards incorporated by this
verifier protocol. “Subset” means that only the stated clauses or concepts are
authoritative. A reference inside one of these documents is not independently
incorporated unless this registry names it.

“Errata adopted” is exhaustive. `None` means the cited base publication text
only. Later revisions never apply automatically.

The exact title and document/version identifier, rather than the mutable
presentation of a linked website, identifies each incorporated publication.

| Standard | Exact document/version | AELITIUM use and incorporated scope | Whole or subset | Later revisions | Errata adopted |
|---|---|---|---|---|---|
| JSON | [RFC 8259, *The JavaScript Object Notation (JSON) Data Interchange Format*, December 2017, STD 90](https://www.rfc-editor.org/rfc/rfc8259.html) | JSON structural, literal, string, number, and whitespace grammar where a Level 1 contract invokes RFC 8259; parser limits do not override AELITIUM dispatch requirements | Subset: grammar and encoding requirements used by the relevant AELITIUM source profile | No | None |
| UTF-8 | [RFC 3629, *UTF-8, a transformation format of ISO 10646*, November 2003, STD 63](https://www.rfc-editor.org/rfc/rfc3629.html) | Valid shortest-form UTF-8 octet sequences and the U+0000..U+10FFFF encoding range; AELITIUM separately fixes BOM, scalar, and noncharacter rules | Subset: UTF-8 syntax and validity | No | None |
| JSON Canonicalization Scheme | [RFC 8785, *JSON Canonicalization Scheme (JCS)*, June 2020](https://www.rfc-editor.org/rfc/rfc8785.html) | Portable-v2 canonical serialization `C`: whitespace, literals, strings, binary64 number rendering, recursive UTF-16 property ordering, array-order preservation, and UTF-8 generation | Subset: section 3.2; AELITIUM supplies the source/value profile, storage envelope, and hash scope | No | Erratum 6292 only, as a non-behavioral section-reference correction; erratum 7920 is expressly not adopted |
| ECMAScript number conversion to string | [ECMA-262, 10th edition, *ECMAScript 2019 Language Specification*, June 2019](https://262.ecma-international.org/10.0/) | The binary64 number-to-decimal algorithm referenced by RFC 8785 section 3.2.2.3, specifically section 7.1.12.1 including Note 2 | Subset only | No | None |
| Binary floating point | [IEEE Std 754-2019, *IEEE Standard for Floating-Point Arithmetic*](https://standards.ieee.org/ieee/754/6210/) | The binary64 format and round-to-nearest, ties-to-even conversion required by the v1 and v2 canonicalization contracts | Subset only | No | None |
| SHA-256 | [FIPS PUB 180-4, *Secure Hash Standard (SHS)*, August 2015 update](https://doi.org/10.6028/NIST.FIPS.180-4) | SHA-256 calculation over the exact byte inputs selected by Level 1 contracts; AELITIUM defines lowercase hexadecimal output separately | Subset: SHA-256 only | No | None |
| Base64 | [RFC 4648, *The Base16, Base32, and Base64 Data Encodings*, October 2006](https://www.rfc-editor.org/rfc/rfc4648.html) | Standard Base64 for encoded verification keys and signatures and for public keys in explicit trust input | Subset: section 4; exact artifact lexical acceptance remains G-05/G-06 | No | None |
| Ed25519 | [RFC 8032, *Edwards-Curve Digital Signature Algorithm (EdDSA)*, January 2017](https://www.rfc-editor.org/rfc/rfc8032.html) | Pure Ed25519 verification of the exact raw manifest message with a 32-octet public key and 64-octet signature | Subset: the Ed25519 instance and verification rules in section 5.1; not Ed25519ctx, Ed25519ph, or Ed448 | No | None |
| JSON Schema Draft 7 Core | [draft-handrews-json-schema-01, *JSON Schema: A Media Type for Describing JSON Documents*, 19 March 2018](https://json-schema.org/draft-07/draft-handrews-json-schema-01) | Core processing for applicable schemas whose `$schema` is `http://json-schema.org/draft-07/schema#` | Subset exercised by the named Level 1 schemas | No | None |
| JSON Schema Draft 7 Validation | [draft-handrews-json-schema-validation-01, *JSON Schema Validation: A Vocabulary for Structural Validation of JSON*, 19 March 2018](https://json-schema.org/draft-07/draft-handrews-json-schema-validation-01) | Validation keywords used by those same named schemas | Subset exercised by the named Level 1 schemas | No | None |

The AELITIUM value contracts directly define a Unicode scalar value as a code
point in U+0000..U+D7FF or U+E000..U+10FFFF and directly enumerate the v2
noncharacter exclusions. They perform no normalization. Consequently, no
version-varying Unicode character database, assigned-character table,
normalization data set, locale data, or grapheme algorithm is incorporated.
RFC 3629 supplies the required UTF-8 encoding reference; RFC 8785 supplies the
UTF-16 ordering operation used only by portable-v2 JCS serialization.

The Draft 2020-12 declaration in `engine/schemas/input_v1.json` concerns a
producer input schema outside this verifier protocol's named schema set. It is
not incorporated here.

### 6.2 Explicit non-incorporation

- RFC 7493, *The I-JSON Message Format*, informed the portable-v2 design but
  is not a freestanding verifier authority. The Level 1 AELITIUM v2 profile
  directly states all applicable input restrictions, and this protocol
  incorporates RFC 8785 section 3.2 rather than RFC 8785 section 3.1.
- RFC 3339 is not incorporated. AELITIUM timestamp spelling and calendar
  semantics are contract-specific; their remaining edge-domain closure is
  G-11.
- Later ECMAScript editions and the ECMA-262 living specification are not
  incorporated. They cannot alter portable-v2 number bytes.
- A library, package, runtime, language specification, or implementation
  claiming support for JSON, JCS, Base64, Ed25519, SHA-256, UTF-8, binary64, or
  JSON Schema is not itself a normative standard.

### 6.3 Errata and replacement policy

Published errata do not silently alter an existing AELITIUM identifier or
contract. An editorial, security, or clarification erratum may be adopted only
by an explicit AELITIUM specification revision or compatibility note. An
erratum that can change accepted inputs, rejected inputs, canonical bytes,
hashes, signature results, reasons, states, or comparisons requires versioned
review and conformance-impact analysis. Where compatibility cannot be
established, a new AELITIUM identifier or contract version is required.

RFC 8785 [erratum 6292](https://www.rfc-editor.org/errata/eid6292) corrects
only the ECMA-262 string-section citation and is adopted without changing
bytes. RFC 8785 [erratum 7920](https://www.rfc-editor.org/errata/eid7920)
recommends rejecting negative-zero input; it is not incorporated because the existing
`aelitium_jcs_profile_v2` contract accepts negative zero and serializes it as
`0`. Adopting that recommendation would require a new canonicalization
identifier and new conformance review.

Future RFCs, standards editions, replacement publications, amendments,
corrigenda, library upgrades, or living-standard revisions do not supersede a
cited version automatically. AELITIUM adopts them only through the update
process in section 3.

## 7. Independent-verifier gap status

This Phase 1 specification closes only the three authorized readiness gaps.
The remaining findings retain their prior identifiers and continue to block a
complete clean-room implementation.

| Gap | Status after Phase 1 | Basis |
|---|---|---|
| G-01 | **CLOSED** | Sections 2 and 3 publish the hierarchy, conflict rule, implementation exclusion, and update process. |
| G-02 | **OPEN** | The complete v1 integer domain remains dependent on configurable CPython behavior. |
| G-03 | **CLOSED** | Sections 4 and 5 publicly define the registry and complete dispatch contract. |
| G-04 | **OPEN** | A complete manifest grammar/schema remains unpublished. |
| G-05 | **OPEN** | The verification-key artifact grammar and exact Base64 acceptance remain unspecified. |
| G-06 | **OPEN** | The explicit trust-input grammar/schema remains incomplete. |
| G-07 | **OPEN** | Invocation grammar and ordered reason mapping remain incomplete. |
| G-08 | **OPEN** | An exhaustive reason and assurance-state transition registry remains unpublished. |
| G-09 | **OPEN** | The operational/resource and filesystem error contract remains unspecified; section 5.7 only prevents semantic misclassification. |
| G-10 | **OPEN** | Corpus operations and complete expected outputs are not yet language-neutral and self-contained. |
| G-11 | **OPEN** | Timestamp calendar and Freshness edge semantics remain incomplete. |
| G-12 | **DEFERRED** | Complete comparison-output construction remains a later closure phase. |
| G-13 | **CLOSED** | Section 6 pins exact standards, subsets, editions, errata handling, and non-supersession. |

Closing these three gaps does not change the historical
`INDEPENDENT_VERIFIER_DESIGN_NOT_READY` verdict. No independent verifier is
implemented or claimed by this document.

## 8. Compatibility and non-claims

This protocol publication:

- does not change or narrow `json_sorted_keys_no_whitespace_utf8`;
- does not change `aelitium_jcs_profile_v2`;
- does not change parser, hash, signature, assurance, verification, comparison,
  or claim-boundary meaning;
- does not make v1 universally portable;
- does not create cross-version comparison;
- does not close G-02, G-04 through G-12;
- does not implement or release an independent verifier; and
- does not establish provider execution, response causation, semantic truth,
  capture completeness, historical occurrence, historical non-modification,
  authorization, trusted historical time, legal compliance, or complete
  invocation identity.
