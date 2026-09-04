# Portable canonicalization v2 design

**Status:** DESIGN ONLY — NOT IMPLEMENTED

**Audit baseline:** `7b3d7c040d749cc73bb2d481a7b67c5a9f9490b6`

**Current v1 identifier (unchanged):**
`json_sorted_keys_no_whitespace_utf8`

**Proposed v2 identifier:** `aelitium_jcs_profile_v2`

The capitalized requirement words in this document describe the proposed v2
contract. They do not change the current runtime, schemas, bundle formats,
verification results, assurance results, comparison results, or any released
artifact.

## 1. Executive decision

Adopt **RFC 8785 / JCS with an explicit AELITIUM input and envelope profile**.
Do not adopt unrestricted JCS, and do not create a new AELITIUM serialization
algorithm.

The profile is intentionally small:

- input is strict UTF-8 JSON with no BOM and no duplicate object names;
- strings are I-JSON strings, are not normalized, and contain neither
  surrogates nor Unicode noncharacters;
- JCS serialization is used without byte-level modification;
- native JSON numbers have the IEEE 754 binary64 value model, MUST be finite,
  and MUST have absolute value at most `9007199254740991` (`2^53 - 1`);
- integer-valued numbers therefore have the exact inclusive range
  `[-9007199254740991, 9007199254740991]`;
- values needing larger integers or exact decimal semantics are represented by
  schema-defined strings, not by an expanded canonicalizer number type;
- the canonical output is the RFC 8785 byte sequence `C`; SHA-256 hashes exactly
  `C`, never a storage newline; and
- stored `ai_canonical.json` may be exactly `C` or `C || 0A`, preserving a
  narrowly specified storage envelope without making LF part of JCS.

Finite native floats remain allowed. Existing AELITIUM evidence records
fractional `temperature` and `top_p` values in invocation parameters, including
values such as `0.2`, `0.75`, and `0.9`. Removing native floats would prevent a
future bundle from faithfully recording those existing semantic inputs unless
another evidence grammar were changed. Non-finite values have no corresponding
JSON value and are rejected.

This decision is based on the concrete fit between AELITIUM data and the
standard, not on the existence of a standard alone. JCS supplies the hardest
portable component—binary64-to-decimal rendering—and has implementations for
the target language families. The AELITIUM profile closes matters JCS alone
does not decide for this protocol: the smaller numeric domain, source bytes,
BOM handling, manifest parsing, storage LF, hash scope, version dispatch, and
cross-version comparison.

V1 remains permanently interpreted under
`json_sorted_keys_no_whitespace_utf8`. V2 is an opt-in future contract; it is
not a correction or reinterpretation of v1.

## 2. Current v1 blockers

PR #34 made most v1 behavior describable, but it did not make the complete v1
domain portable. One issue remains formally open, and several compatibility
quirks make a clean implementation substantially harder than a new contract
needs to be.

| Area | V1 behavior | Portability or security consequence | V2 disposition |
|---|---|---|---|
| Arbitrary-size integers | Python integers are unbounded in principle, while decimal conversion above a runtime-configurable threshold can fail. `ai_output_v1.metadata`, legacy `input_v1.payload`, and `verification_result_v1.policy_inputs[].maximum_age_seconds` do not provide a common canonicalization bound. | Acceptance above 640 magnitude digits varies by CPython configuration. Go, JavaScript, Java, Rust, and C# also choose different default number types and overflow behavior. This is the remaining complete-domain blocker. | Reject all native numbers outside the safe-number magnitude; use schema-defined strings for larger exact values. |
| Python integer/float distinction | `1` emits `1`, while `1.0` emits `1.0`; the distinction originates in Python object type or the lexical source form. | JSON has one number production. JavaScript cannot retain this type distinction through `JSON.parse`, and other parsers select types differently. | All numbers have the binary64 model. `1`, `1.0`, and `1e0` serialize as the same JCS number. |
| `NaN`, `Infinity`, `-Infinity` | Exact non-JSON tokens are accepted in broad metadata and re-emitted. | Many JSON parsers reject them; payloads are not RFC 8259 JSON; NaN identity and payload semantics differ by runtime. | Reject lexically and reject programmatic non-finite values. |
| Duplicate object names | Parsing retains the last value. Duplicate payload names later fail byte equality, but duplicate manifest names can be accepted when the final value passes. | Parsers variously reject, keep first, keep last, or expose every occurrence. Security decisions can be made over different values. | Reject every duplicate after unescaping, in payloads, manifests, and unknown extensions. |
| Unicode scalar validity | Governed payload strings reject unpaired surrogates, but an escaped surrogate in an ignored manifest extension remains accepted for v0.4.0 compatibility. | UTF-8-native and UTF-16-native runtimes expose different failure and string-length behavior. The manifest exception is deliberately Python-aligned. | Require the I-JSON string domain everywhere under v2, including ignored extensions. |
| Unicode normalization | No normalization is performed. Canonically equivalent NFC/NFD strings remain distinct. | This is portable only when stated explicitly. Adding implicit normalization would introduce Unicode-version dependencies and could create duplicate names. | Continue to perform no normalization, as JCS requires. |
| Object-key ordering | Python string order is lexicographic Unicode scalar-value order. | JavaScript, Java, and C# naturally expose UTF-16 code units; JCS uses UTF-16 order. V1 differs for some BMP/non-BMP pairs, such as U+E000 and U+1F600. | Use the exact RFC 8785 UTF-16-code-unit ordering. |
| String escaping | Behavior is inherited from `json.dumps(..., ensure_ascii=False)`, then documented as an exact table. | Default encoders differ on solidus, HTML-sensitive characters, non-ASCII, U+2028/U+2029, short control escapes, and hex case. | Use the exact JCS escape rules, which happen to match most v1 string bytes for valid shared-domain strings. |
| Binary64 parsing | Decimal fractions and exponents are converted by CPython to binary64 using its parser. | A parser using decimal, arbitrary precision, or a lossy intermediate can obtain another value. | Mandate direct correctly rounded decimal-to-binary64 conversion, round-to-nearest ties-to-even. |
| Binary64 rendering | V1 follows CPython shortest-round-trip digits with Python notation thresholds, exponent padding, and `.0` type marking. | Standard serializers in the six target languages do not all produce these bytes. | Use the RFC 8785 / ECMAScript rendering algorithm and its frozen vectors. |
| Negative zero | Integer `-0` becomes `0`; binary64 `-0.0` emits `-0.0`. | Some runtimes preserve negative zero, some serializers collapse it, and JSON applications rarely assign it distinct semantics. | Accept binary64 negative zero but serialize it as `0`, exactly as JCS; v2 declares the signs equivalent for hashing. |
| Numeric lexical aliases | Whitespace, exponent spellings, redundant fraction digits, and integer negative zero can parse to one value, while only Python's selected spelling is canonical storage. | Source parsing and stored-byte validation can be confused, and different number parsers may collapse different aliases. | Keep the parse/serialize distinction, but make the value conversion and unique JCS output normative. |
| Source parsing versus serialization | V1 combines standard JSON parsing, three legacy non-finite tokens, last-name-wins behavior, Python value types, and a later canonical-byte comparison. | Reimplementing only `json.dumps` is insufficient; parser behavior changes verification. | Define a duplicate-aware, token-aware v2 parser independently from serialization. |
| Terminal newline | Canonical bytes have no LF, while stored payload accepts zero or one terminal LF. | Hashing the file directly disagrees with hashing the canonical value. | Retain the explicit two-form storage envelope and always hash `C`. |
| Manifest parsing | The manifest is parsed with Python JSON, is not canonicalized, and its raw bytes are signature input. | Duplicate names and ignored invalid-scalar extensions differ from payload behavior. A generic map parse can lose evidence needed to reject ambiguity. | Apply the v2 source profile to the entire manifest, while continuing to sign its exact raw bytes. |
| Forward-compatible manifest fields | Unknown fields are accepted and ignored, with recursively unconstrained JSON values. | Unknown values import the broadest parser behavior even though they have no verification semantics. | Continue must-ignore semantics, but require every unknown name and value to be valid v2-profile JSON. |
| Exact hash input | The identifier governs the outer payload, selected request and response objects, original binding, invocation identity, and invocation binding. | A partial port can accidentally use a different serializer for an inner hash while the outer payload still verifies. | The enclosing manifest identifier selects one canonicalizer for every declared canonical JSON hash construction in that bundle. |
| Compatibility with released bundles | Non-finites, duplicate-manifest last-wins behavior, Python float bytes, and runtime-dependent large integers cannot be narrowed under the existing identifier. | Redefining v1 would invalidate or reinterpret released evidence. | Leave v1 untouched and introduce an exact new identifier. |
| Comparison | Current bases compare hashes constructed under v1 rules and do not carry a cross-canonicalization equivalence rule. | Equal-looking parsed values do not prove equivalent source semantics; equal digests under different identifiers do not establish a common basis. | Different identifiers are not comparable under current bases. A future bridge must be explicitly basis-specific. |

The schema and manifest audit locates the broad domains precisely.
`ai_output_v1` closes its top level but permits arbitrary recursive values under
`metadata`; legacy `input_v1` requires only that `payload` be an object; result
schemas are otherwise closed but the Freshness policy integer is unbounded.
There is no packaged JSON Schema for `ai_manifest.json`: required fields and
identifier checks are code-defined, while unknown fields are accepted. Those
facts mean a portable canonicalization profile must be enforced in addition to
schema validation and must cover unknown manifest extensions.

The PR #34-era compatibility tests also freeze why v1 cannot be repaired in
place: released fixture digests remain exact, duplicate manifest names retain
last-value behavior, an ignored manifest surrogate remains accepted, prior
error precedence remains fixed, and the verification/assurance/comparison
contract artifacts remain byte-unchanged.

### 2.1 Pre-dispatch compatibility audit

The released v0.4.0 manifest-loading and identifier-checking path is unchanged
at this audit baseline. It decodes the manifest with strict UTF-8 and then uses
CPython's default `json.loads` behavior. Focused probes against that path gave
the following results. In every positive probe, the final top-level
`canonicalization` member appeared after the value under test.

| Manifest source condition | Released v1 result |
|---|---|
| Unknown extension value `NaN` | `OK` |
| Unknown extension value `Infinity` | `OK` |
| Unknown extension value `-Infinity` | `OK` |
| Unknown extension value `"\ud800"` | `OK` |
| Earlier `canonicalization` selects v2, final occurrence selects v1 | `OK`; the final occurrence wins |
| Duplicate unrelated member with two different values | `OK`; the final occurrence wins |
| All three non-finite tokens, an unpaired surrogate escape, and an unrelated duplicate before the final v1 selector | `OK` |
| Selector name and selector value containing equivalent `\uXXXX` escapes | `OK`; comparison occurs after escape processing |

The integer-conversion probes make the dispatch constraint especially clear:

| CPython `int` digit limit | Unknown extension integer token | Released v1 result |
|---:|---:|---|
| 640 | 640 digits | `OK` |
| 640 | 641 digits | `MANIFEST_NOT_JSON` |
| 4300 | 4300 digits | `OK` |
| 4300 | 4301 digits | `MANIFEST_NOT_JSON` |
| disabled (`0`) | 4301 digits | `OK` |
| disabled (`0`) | 10000 digits | `OK` |

These are manifest parser outcomes, even though the values are ignored
extensions. A selector-discovery operation must therefore scan an unbounded
RFC 8259 number token lexically and defer the configured integer conversion to
the selected v1 path. It must neither reject the token at 640 or 4300 digits
nor convert it in a wider type and thereby make the v1 path accept it.

Existing reason precedence was also reconfirmed: a top-level array produces
`MANIFEST_NOT_OBJECT`; a missing selector produces `MANIFEST_MISSING_FIELD`;
an unknown selector with an earlier missing required field still produces
`MANIFEST_MISSING_FIELD`; an unknown selector with a bad schema produces
`MANIFEST_BAD_SCHEMA`; and only an otherwise acceptable manifest reaches
`MANIFEST_BAD_CANONICALIZATION`. A non-string selector reaches that same final
reason when all earlier checks pass.

Consequently, a strict RFC 8259 pre-dispatch parse is **not compatible** with
v1: RFC 8259 excludes the three legacy non-finite tokens. Applying I-JSON or
v2 profile checks at that stage would additionally reject the accepted
surrogate and duplicate cases. Using an ordinary numeric parser could also
reject according to a new host limit before the legacy parser is selected.
Section 4.5 therefore defines a non-validating, lossless selector scanner over
a deliberately specified union grammar. It is not an RFC 8259 parser and its
token tree is never used as the parsed manifest.

Language-specific audit consequences are:

| Language | V1 clean-room obstacle | V2 implementation requirement |
|---|---|---|
| Python | `int` conversion guard, distinct `int`/`float`, Python `repr` notation, permissive non-finite parsing | Reject duplicates through an object-pairs/token-aware parser, enforce the profile before serialization, and use a conforming JCS renderer rather than `json.dumps`. |
| Go | `encoding/json` defaults numbers to `float64`, other modes expose `json.Number`, and stock output is not a v1 float renderer | Preserve number tokens until profile validation, detect duplicates before building a map, then use an audited JCS implementation. |
| Rust | `serde_json::Number` capabilities and map ordering depend on configuration/features | Use a visitor or lossless parser that rejects duplicates, apply the numeric profile explicitly, and use a JCS formatter with ECMAScript-compatible number output. |
| JavaScript/TypeScript | Only binary64 `Number` exists; integers above `2^53 - 1` are not all exact; `JSON.parse` hides duplicates | Use a duplicate-aware parser for hostile source. Native number semantics fit v2, but stock `JSON.stringify` does not recursively sort keys. |
| Java | Parsers may choose `long`, `BigInteger`, `BigDecimal`, or `double`; `Double.toString` and default escaping are not v1 | Configure duplicate detection, convert governed numbers exactly to binary64, enforce the bound, and use JCS serialization. |
| C# | `System.Text.Json` exposes several number access paths; default escaping and dictionary order are not v1 | Enumerate and reject duplicate properties, apply binary64/profile checks, and use JCS UTF-16 ordering and escaping. |

No target language's stock “parse into a map, then serialize” path is sufficient
for hostile input. Duplicate detection must occur before a map discards member
occurrences.

## 3. Options considered

The standards referenced here are [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259.html),
[RFC 7493](https://www.rfc-editor.org/rfc/rfc7493.html), and
[RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html). RFC 8785 is
Informational rather than Standards Track, but it is an exact published
serialization contract with multi-language implementations and test material.

| Criterion | A. AELITIUM-specific restricted JSON | B. Unprofiled RFC 8785 / JCS | C. RFC 8785 + AELITIUM profile | D. Deterministic CBOR |
|---|---|---|---|---|
| Cross-language reproducibility | Can be excellent if the domain excludes floats or completely specifies them; AELITIUM owns all proof | Strong for JCS-conforming values; external vectors and implementations exist | Strongest fit: JCS bytes plus an enforceable domain and envelope | Strong for a carefully defined CBOR application profile, not for “CBOR” generically |
| Implementation complexity | Low with safe integers and no floats; rises sharply if AELITIUM specifies binary64 rendering | Number output and UTF-16 sorting are nontrivial but already specified | Profile validation is small; hard rendering is delegated unchanged to JCS | Requires new parser, data model, deterministic encoding profile, and JSON/CBOR mapping |
| Numeric semantics | Entirely selectable; a no-float design is simplest but cannot faithfully carry current fractional invocation parameters | All numbers are binary64; safe integer interoperability is recommended, not an AELITIUM-enforced bound | Finite binary64 retained, magnitude capped at `2^53 - 1`, exact larger/decimal values use strings | Distinguishes integers and floats and supports bignum tags, but those choices themselves need a protocol profile |
| Unicode semantics | AELITIUM must define scalar validity, noncharacters, normalization, escaping, and key order | I-JSON strings, no normalization, JCS escaping, UTF-16 key order | Same as JCS, made explicit for every bundle JSON file | UTF-8 text exists, but validation and map-key policy still need application rules |
| Duplicate names/keys | Can reject, but every parser integration must be specified | I-JSON/JCS prohibits duplicate names | Reject globally and test payload/manifest/unknown-extension cases | Duplicate CBOR map keys are invalid/ambiguous and still require detection before map materialization |
| Library ecosystem | No existing conforming libraries; generic JSON pieces only | JCS implementations are published for Python, Go, Rust, JS, Java, and .NET/C# | Same JCS ecosystem plus a small AELITIUM validator | Mature CBOR libraries exist, but deterministic modes and tag support vary |
| Security ambiguity | Small if rigorously specified; risk is omissions in a new home-grown standard | Removes many JSON ambiguities but leaves AELITIUM source/envelope/version policy unstated | Closes those protocol gaps and rejects lossy integer magnitudes | Richer type/tag space increases profile and downgrade questions |
| Compatibility/migration | Always a new identifier; likely largest byte divergence if escaping/order are custom | Always a new identifier; v1 Python float/key bytes can differ | Always a new identifier; shared string/literal cases often coincide, but no compatibility depends on that | Requires a different stored representation and therefore changes the bundle format |
| Independent-verifier suitability | Good only after AELITIUM authors an exhaustive normative algorithm and corpus | Good for canonicalization, incomplete for the surrounding evidence protocol | Good: an implementer reads this profile, RFC 8785, schemas, and frozen vectors—not Python | Poor for this task because it expands clean-room scope beyond current JSON bundles |
| Long-term maintenance | AELITIUM owns algorithms, errata, libraries, and test evolution | Standard ownership is external, but unrestricted numeric acceptance is wider than needed | AELITIUM maintains only a narrow immutable profile and integration corpus | AELITIUM must maintain a CBOR application profile and parallel tooling |

### Option A — bespoke restricted JSON

A bespoke no-float, safe-integer contract would have the smallest serializer.
It was not selected because native fractional values are present in current
invocation evidence, and silently changing those values to strings would change
the recorded invocation. A bespoke contract that retained floats would recreate
the most difficult part of JCS and give every target ecosystem a new algorithm
to implement and maintain.

### Option B — unprofiled RFC 8785 / JCS

Unprofiled JCS was not selected. It intentionally uses the full binary64 value
space and does not make `2^53 - 1` a mandatory application integer bound. It
also starts from I-JSON-compatible data; it does not by itself define
AELITIUM's raw-source BOM policy, manifest handling, optional storage LF, hash
constructions, error mapping, version negotiation, or comparison policy.

### Option C — RFC 8785 with an AELITIUM profile

This is the recommendation. The profile **narrows JCS input and defines the
AELITIUM envelope; it does not alter JCS serialization**. Consequently, an
audited RFC 8785 implementation can be used after a profile-validating parser.
The RFC-linked reference project lists implementations in all six target
language families, but no dependency is trusted by name alone: each must pass
the AELITIUM corpus.

### Option D — another standards-based representation

[RFC 8949 deterministic CBOR](https://www.rfc-editor.org/rfc/rfc8949.html) was
considered because it has explicit integer and floating-point types and
deterministic encoding rules. It is rejected for v2. It would change the bundle
representation, require a normative JSON-to-CBOR data-model mapping, introduce
tag and preferred-number choices, and reduce direct inspectability. It solves a
broader problem than this task and violates the constraint to keep bundle
formats unchanged.

## 4. Recommended v2 design

### 4.1 Contract layers

After manifest dispatch under section 4.5 has selected v2, v2 processing has
four separate layers. Implementations MUST NOT collapse them into an
unspecified host JSON operation.

1. **Post-dispatch source decoding and parsing.** Re-read the original bytes
   from the beginning, decode strict UTF-8, and parse exactly one RFC 8259 JSON
   text while retaining every object-member occurrence and every number token
   long enough to enforce the profile.
2. **Profile validation and value construction.** Reject duplicate names,
   invalid string code points, non-finite/out-of-range numbers, and non-JSON
   host values. Construct the exact value domain in section 5.
3. **Canonical serialization.** Serialize the validated value exactly as RFC
   8785. The output byte string is `C`.
4. **Evidence envelope.** Apply the application schema and existing verification
   ordering, compare a stored canonical payload with only `C` or `C || 0A`, and
   compute or compare SHA-256 over `C` alone.

Schema validation and canonicalization-domain validation are independent. A
value can be valid v2 JSON but invalid `ai_output_v1`, and a value can satisfy a
schema's broad `number` or `integer` keyword while being outside the v2 numeric
domain. Both checks are required.

### 4.2 Scope inside a v2 bundle

The exact `canonicalization` value in the enclosing manifest selects v2 for:

- the `ai_output_v1` canonical payload and `ai_hash_sha256`;
- selected request and response payload hashes created for that bundle;
- the original request/response `binding_hash`;
- `aelitium-invocation-v1` hash material when embedded in that bundle; and
- `aelitium-invocation-binding-v1` hash material when embedded in that bundle.

A producer or verifier MUST NOT mix v1 and v2 canonicalizers within those
constructions. The semantic field selections and assurance meanings do not
change. The enclosing manifest is the version-negotiation context for embedded
hash-bearing objects. An object extracted without that context is not enough to
select a canonicalization contract; a future standalone exchange format would
need to carry its own context and is outside this design.

No other AELITIUM artifact silently changes canonicalization. A format without
an explicit v2 selection continues to use its already defined behavior.

### 4.3 Manifest behavior

The v2 manifest remains `ai_manifest.json`; no new file or field is required.
After the selector scanner has selected v2, the unchanged original manifest
bytes are handled as follows:

- decode as strict UTF-8 with no leading BOM;
- parse exactly one RFC 8259 JSON text as an object;
- reject duplicate names at any nesting depth after JSON escape processing;
- enforce the complete v2 string and number domain recursively, including in
  unknown members;
- apply existing required-field, identifier, timestamp, and digest checks;
- ignore an otherwise valid unknown member and give it no verification,
  assurance, authorization, or comparison meaning; and
- when signatures are evaluated, verify the signature over the exact raw
  manifest bytes, including all whitespace, member order, unknown members, and
  terminal bytes, exactly as the existing signature scope requires.

Unknown fields implement a must-ignore extension policy. An extension that
must change verification meaning cannot be introduced as an ordinary unknown
field; it requires an explicitly versioned manifest or contract. This prevents
an old verifier from silently ignoring a security-critical instruction.

The manifest is not JCS-canonicalized for signature verification. Its raw-byte
signature and the canonical payload digest remain distinct mechanisms.

### 4.4 Post-dispatch v2 parser and rejection behavior

A conforming v2 source parser MUST:

- expose duplicate member occurrences or reject them itself;
- expose number tokens or otherwise demonstrate the exact binary64 conversion
  and integer-bound checks in section 5;
- reject invalid UTF-8, overlong sequences, UTF-8 encodings of surrogates,
  truncated sequences, and a leading BOM;
- reject comments, trailing commas, multiple top-level values, and trailing
  non-whitespace data;
- reject lone surrogate escapes and Unicode noncharacters after escape
  processing; and
- avoid an intermediate `float32`, host-width integer, locale-sensitive
  parser, or decimal-to-string round trip.

Stock parsers may be used only when configured or wrapped to meet all of these
requirements. In particular, plain `JSON.parse` followed by object inspection
cannot prove that source names were unique.

Rejection is fail-closed and produces no canonical bytes or digest. Under the
existing result vocabulary and precedence:

- malformed UTF-8/JSON or a v2 profile violation in the canonical payload maps
  to `CANONICAL_NOT_JSON`;
- a valid v2 value stored with noncanonical spelling maps to
  `CANONICAL_BYTES_MISMATCH`;
- a v2 manifest UTF-8/JSON/profile violation maps to `MANIFEST_NOT_JSON`;
- an unsupported identifier maps to `MANIFEST_BAD_CANONICALIZATION`; and
- schema, hash-shape, hash-mismatch, signature, assurance, and comparison
  outcomes retain their existing meanings and order.

The implementation plan must preserve the current check precedence. The only
pre-dispatch processing is the selector scanner in section 4.5. V2-specific
syntax, uniqueness, Unicode, number, or profile rejection MUST NOT be applied
to a v1 bundle. V1 continues to use its complete legacy parser,
last-name-wins behavior, host integer-conversion limit, and manifest-extension
behavior.

Programmatic APIs accept only values in section 5. Host values such as tuples,
sets, byte arrays, `BigInt`, `BigDecimal`, `Decimal`, arbitrary objects, maps
with non-string keys, or integers outside the bound MUST be rejected rather
than coerced.

### 4.5 Normative pre-dispatch selector scanner

This subsection is normative. The selector scanner is a structural lexical
router, not a version-specific manifest-value parser, canonicalizer, schema
validator, or source normalizer. Its sole successful output is the identity of
the final top-level `canonicalization` selector, if that selector names a
registered contract. Nothing parsed or decoded by the scanner may be reused as
the manifest value given to either version-specific verifier.

After the existing ordered option checks and required-file presence checks
have established that both bundle files exist, the scanner may read
`ai_manifest.json` as non-observable lookahead. It operates on the original
manifest byte string and keeps that byte string immutable. The selected
version path then begins its content checks and preserves the existing
observable order: canonical-payload parsing precedes manifest parsing and any
manifest failure. A scanner outcome is never itself a verification result and
cannot override an earlier canonical-payload result.

#### 4.5.1 Dispatch grammar

The scanner recognizes exactly one complete value in the following
`AELITIUM-DISPATCH-JSON-1` grammar. The notation below is case-sensitive and
uses the RFC 8259 definitions of the JSON structural characters, `string`,
`digit`, `digit-1-9`, and hexadecimal digit:

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
ws                = *( U+0020 / U+0009 / U+000A / U+000D )
```

`false`, `null`, `true`, `NaN`, and `Infinity` in that grammar are the exact
lower- or upper-case ASCII spellings shown. The grammar does not accept a
leading plus, `-NaN`, `+Infinity`, lower-case non-finite aliases, comments,
trailing commas, or concatenated top-level values. A token must occur where a
complete value is expected; the spelling `NaN` inside a longer token is not a
match.

Strings use the RFC 8259 lexical grammar: an unescaped quotation mark, reverse
solidus, or U+0000 through U+001F is forbidden; the only short escapes are
`\"`, `\\`, `\/`, `\b`, `\f`, `\n`, `\r`, and `\t`; and `\u` is followed by
exactly four hexadecimal digits. At scanner time every syntactically valid
`\uXXXX` escape is accepted independently. In particular, the scanner MUST NOT
reject an unpaired, reversed, or otherwise invalid surrogate sequence.
Unicode noncharacters are also accepted at this stage.

Outside strings, every structural character and literal is ASCII. Unescaped
non-ASCII string content must be well-formed shortest-form UTF-8 for Unicode
scalar values. Ill-formed UTF-8, a raw UTF-8 encoding of a surrogate, and a
leading UTF-8 BOM are not in the dispatch grammar. This does not narrow v1:
the released path already rejects each while decoding or parsing the manifest.
A U+FEFF encoded inside a string is ordinary string content.

The `number` production has no digit-count limit. The scanner MUST consume it
lexically without converting it to a host integer, decimal, binary32, or
binary64 value. In particular, it MUST NOT invoke CPython's integer-conversion
guard or an equivalent host-width/implementation limit. General process
resource exhaustion is not a JSON syntax result; a numeric token's length
alone cannot be reclassified by this scanner as `MANIFEST_NOT_JSON`.

This grammar is intentionally not RFC 8259. It is the union needed here:
strict v2 JSON is a subset, and every manifest text that released v1 can parse
is included before v1's host-dependent numeric conversion. No other legacy
extension is implied.

#### 4.5.2 Lossless retention and selector equality

For a successful scan, the scanner MUST retain, conceptually or concretely:

- the original byte span and raw lexeme for every string, RFC 8259 number, and
  legacy constant;
- every object member in source order, including all duplicate occurrences;
  and
- array order and object/array nesting, so that only members of the root object
  can participate in selection.

It MUST NOT collapse an object into a map, discard an earlier occurrence,
normalize Unicode, canonicalize escapes, convert a number, validate the v2
numeric or string domain, enforce a schema, or reject a duplicate. Retention is
for correct scanning and conformance diagnostics only; the original byte
string, not retained tokens, is passed onward.

To recognize the selector, the scanner forms a comparison view of each
top-level member name using legacy JSON escape processing. Short escapes map
to their named character. A `\uXXXX` high surrogate immediately followed by a
`\uXXXX` low surrogate maps to the corresponding non-BMP scalar; an unmatched
surrogate remains an unmatched code point in this comparison view. No
normalization or scalar-validity check is performed. A member is a selector
only when that view is exactly the 16 ASCII characters
`canonicalization`. This rule recognizes spellings such as
`"\u0063anonicalization"`, as the released parser does.

The scanner considers every such root-member occurrence from left to right and
uses only the final occurrence. Nested members named `canonicalization` are
irrelevant. If the final selector value is a string, the same escape-processing
algorithm forms its comparison view. Only an exact, case-sensitive comparison
with a registered identifier selects a version. The raw key and value lexemes
remain unchanged.

#### 4.5.3 Dispatch and error-resolution algorithm

The required routing algorithm is:

1. Attempt one complete `AELITIUM-DISPATCH-JSON-1` scan of the original
   manifest bytes. A scan failure MUST NOT itself emit a new verification
   reason or partially dispatch on a selector seen before the failure.
2. If the complete root value is an object, find the final top-level selector
   as specified above. A non-object has no selector for dispatch purposes.
3. If the final selector is exactly
   `aelitium_jcs_profile_v2`, discard all scanner-derived views and enter the
   v2 verification path. When that path reaches its manifest-parse step, it
   re-reads the original bytes from byte zero with the strict v2 parser and
   applies the entire v2 profile to the entire manifest. It rejects every
   duplicate at every depth, including any duplicate `canonicalization`, and
   never retries under v1 after a v2 failure.
4. For every other outcome—including exact v1, a missing/non-string/unknown
   selector, a non-object root, or scanner failure—discard all scanner-derived
   views and enter the complete frozen v1 verification path. When that path
   reaches its manifest-parse step, it receives the original bytes from byte
   zero. An exact v1 selector can therefore complete v1 verification. Other
   outcomes fail at the same parse, object, required-field, schema,
   input-schema, or canonicalization check that released v1 reaches; they are
   not treated as successful v1 selections.

Step 4 is the legacy error-resolution route as well as the v1 route. It is
necessary to preserve existing observable precedence. The scanner MUST NOT
return `MANIFEST_BAD_CANONICALIZATION` merely because it observed an unknown
value: for example, an earlier missing `schema` must still return
`MANIFEST_MISSING_FIELD`, and an earlier bad schema must still return
`MANIFEST_BAD_SCHEMA`. Likewise, scanner failure delegates to the legacy path,
which returns `MANIFEST_NOT_JSON` only if the released parser does so.

Selection of v2 is the sole versioned additive branch. Once selected, strict
v2 manifest parsing is performed at the manifest-parse stage and may therefore
return `MANIFEST_NOT_JSON` for a duplicate, non-finite token, invalid scalar,
out-of-profile number, or other v2 violation before the ordinary manifest field
checks. Missing, malformed, and unknown selectors receive no such v2 profile
validation.

This algorithm has no pre-dispatch normalization. A v1 manifest containing
`NaN`, infinities, unpaired surrogate escapes, duplicates, or arbitrarily long
integer tokens reaches the unchanged v1 parser byte-for-byte. The v1 parser's
then-configured integer-conversion limit remains the only source of its legacy
large-integer acceptance or `MANIFEST_NOT_JSON` result.

## 5. Exact normative value domain

Let:

```text
MAX_SAFE_NUMBER = 9007199254740991 = 2^53 - 1
MIN_SAFE_NUMBER = -9007199254740991 = -(2^53 - 1)
```

The v2 value domain contains exactly the following recursive values.

### 5.1 Null and booleans

JSON `null`, `true`, and `false` are allowed. Booleans are not numbers; an API
MUST NOT accept `true` where an integer or binary64 value is required merely
because its host language models Boolean as an integer subtype.

### 5.2 Strings and object names

A string is a finite sequence of Unicode scalar values, excluding Unicode
noncharacters. Therefore it excludes:

- every surrogate code point U+D800 through U+DFFF;
- U+FDD0 through U+FDEF; and
- U+FFFE and U+FFFF in every plane, equivalently U+nFFFE and U+nFFFF for
  hexadecimal plane `n` from `0` through `10`.

A valid source surrogate-pair escape represents its single non-BMP scalar.
Unpaired, reversed, or overlapping surrogate escapes are rejected. U+FEFF is
allowed inside a string; only the leading UTF-8 BOM byte sequence before the
JSON text is prohibited.

No Unicode normalization, case folding, locale transformation, grapheme
segmentation, or confusable mapping occurs. NFC `"é"` and NFD `"e\u0301"` are
distinct strings and distinct object names.

### 5.3 Numbers

There is one canonicalization number model: IEEE 754 binary64.

For source JSON:

1. the token MUST match the RFC 8259 number grammar;
2. it MUST be converted directly to the nearest binary64 value using
   round-to-nearest, ties-to-even;
3. the result MUST be finite; and
4. its absolute value MUST be at most `MAX_SAFE_NUMBER`.

Correctly rounded underflow of a nonzero fraction/exponent token may produce
positive or negative binary64 zero; that is an allowed parsed value and emits
`0`. Overflow produces infinity and is rejected. Applications that cannot
accept binary64 rounding, including underflow, must use a schema-defined exact
decimal string instead of a JSON number.

For an integer-form token (no fraction and no exponent), its mathematical
integer value MUST additionally be checked before any narrowing conversion and
MUST be in the inclusive range
`[-9007199254740991, 9007199254740991]`. This prevents a parser from first
rounding an out-of-range integer into an apparently acceptable value. Lexical
`-0` is accepted, may create binary64 negative zero, and serializes as `0`.

For programmatic input, every integer MUST be in that same inclusive range.
Every floating value MUST be a binary64 value, MUST be finite, and MUST have
absolute value at most `MAX_SAFE_NUMBER`. An implementation with wider native
floats MUST reject or exactly convert to binary64 before canonicalization; it
MUST NOT serialize wider precision directly.

The magnitude cap applies to all native JSON numbers, not only integral ones.
That single rule is easy to audit, is closed under JCS serialization, avoids a
token-dependent large-number loophole, and covers current AELITIUM numeric use:
token counts, seeds, maximum ages, and provider sampling parameters. AELITIUM
has no current evidence requirement for native numeric magnitudes above the
JavaScript exact-integer boundary.

The bound is not arbitrary:

- RFC 8259 identifies `[-(2^53)+1, (2^53)-1]` as the integer range in which
  implementations agree exactly;
- RFC 7493 warns that a receiver cannot be expected to preserve larger integer
  values and specifically recommends strings for 64-bit integers when exact
  interchange matters;
- JavaScript/TypeScript represents JSON numbers as binary64 and cannot exactly
  represent every signed 64-bit integer;
- Python, Go, Rust, Java, and C# all represent every integer in the selected
  range exactly; and
- current AELITIUM timestamps and digests are strings, while counts and
  invocation parameters fit comfortably inside the range.

Signed 64-bit native integers were rejected as the v2 bound because they would
require special parsing/types in JavaScript and would still be silently rounded
by common JSON ecosystems. Arbitrary-size native integers were rejected because
they recreate v1's portability problem. Restricting all numbers to integers was
rejected because it would lose current fractional invocation values.

Values requiring arbitrary precision use schema-defined strings. Canonicalization
treats such a string only as text. The owning schema MUST define its syntax,
sign, leading/trailing-zero policy, exponent policy, units, and maximum length;
canonicalization MUST NOT infer that an arbitrary string is a number. A future
arbitrary integer field should normally use a string matching a field-specific
canonical decimal grammar such as `0` or `-?[1-9][0-9]*`, with an explicit
schema length bound. Exact decimals should likewise receive a field-specific,
single-spelling string grammar rather than reuse binary64.

`NaN`, positive infinity, and negative infinity are never in the domain.
Their unquoted spellings are JSON syntax errors. Programmatic occurrences and
decimal overflow to infinity are profile errors.

Binary64 negative zero is allowed but is not distinct from positive zero in
canonical bytes: both serialize as `0`. Any application that needs signed-zero
semantics must use a versioned string field; v2 JSON numbers do not carry that
distinction into a hash.

### 5.4 Arrays

An array is a finite ordered sequence of v2 values. Element order is preserved
and significant. Arrays are never sorted, deduplicated, or treated as sets.

### 5.5 Objects

An object is a finite set of name/value pairs where each name is a valid v2
string, each value is a v2 value, and names are unique after source escape
processing. Uniqueness is exact code-point-sequence equality; normalization is
not performed before the comparison. Thus NFC and NFD names may coexist, while
`"a"` and `"\u0061"` are duplicates and are rejected.

Only string names are allowed. Host maps with numeric, Boolean, null, byte, or
composite keys are rejected.

### 5.6 Top-level application values

The generic canonicalizer can serialize any one v2 value. AELITIUM application
schemas remain authoritative about their root type. In particular,
`ai_canonical.json` remains an `ai_output_v1` object and `ai_manifest.json`
remains an object. V2 does not broaden either schema.

## 6. Exact serialization rules

For every value admitted by section 5, canonical serialization is **exactly the
RFC 8785 serialization**. The AELITIUM profile makes no alternate byte choices.

### 6.1 Literals, arrays, and objects

- null and booleans emit exactly `null`, `true`, and `false`;
- arrays emit `[` then serialized elements in input order separated by `,`,
  then `]`;
- objects emit `{` then sorted member pairs separated by `,`, then `}`;
- each pair is the serialized name, `:`, and serialized value; and
- no insignificant whitespace is emitted anywhere.

Object names are sorted recursively by lexicographic order of their unescaped
UTF-16 code-unit sequences, treating each code unit as an unsigned 16-bit
integer and using shorter-prefix-first ordering. A BMP scalar contributes its
single code unit. A non-BMP scalar contributes its standard high-surrogate then
low-surrogate pair for sorting only. No locale or normalization is involved.

This intentionally differs from v1 scalar-value order. For example, under JCS,
U+1F600 sorts before U+E000 because the emoji's first UTF-16 code unit is
U+D83D, which is less than U+E000.

### 6.2 Strings

Strings and names are enclosed in U+0022 quotation marks. Emit:

| Input scalar | Exact emitted characters |
|---|---|
| U+0022 quotation mark | `\"` |
| U+005C reverse solidus | `\\` |
| U+0008 | `\b` |
| U+0009 | `\t` |
| U+000A | `\n` |
| U+000C | `\f` |
| U+000D | `\r` |
| Other U+0000..U+001F | `\u00xx` using lowercase hexadecimal |
| Every other admitted scalar | The scalar itself |

Solidus U+002F is not escaped. U+2028 and U+2029 are emitted literally.
Non-ASCII and non-BMP scalars are emitted literally and later encoded as
strict UTF-8. Source escape spelling is not retained.

### 6.3 Numbers

Numbers are rendered by RFC 8785 section 3.2.2.3: ECMAScript's binary64
`Number::toString` / JSON serialization algorithm, including its shortest
round-tripping decimal selection. Implementers MUST use that algorithm or a
demonstrably byte-equivalent implementation; host `repr`, `toString`, `%g`,
`BigDecimal`, or generic JSON output is not assumed equivalent.

Observable consequences include:

- no leading `+` and no unnecessary leading or trailing zero;
- lowercase `e` with an explicit `+` only for a nonnegative scientific
  exponent;
- no zero-padding of the exponent (`1e-7`, not v1's `1e-07`);
- fixed notation at `1e-6` and scientific notation below it;
- scientific notation at `1e21` in unrestricted JCS, although the AELITIUM
  magnitude profile rejects values that large;
- integral binary64 values emit without `.0` (`1.0` becomes `1`); and
- positive and negative zero both emit `0`.

The frozen corpus MUST include RFC 8785 Appendix B cases that are inside the
AELITIUM magnitude profile plus AELITIUM boundary cases. The RFC, rather than
the current Python implementation, is normative when a prose example and an
implementation disagree.

### 6.4 UTF-8 output and fixed point

Encode the serialized scalar sequence using strict UTF-8. The canonical byte
sequence `C` contains no BOM and no terminal newline. It is a fixed point: a
conforming parser and serializer applied to `C` MUST return exactly `C`.

### 6.5 Source aliases and stored bytes

A canonicalization API may accept profile-valid source whitespace, member
order, source string escapes, number aliases, and a JSON trailing whitespace
sequence, then produce `C`. Those spellings are not canonical storage.

For v2 `ai_canonical.json`, the only accepted stored byte sequences are:

```text
C
C || 0A
```

The optional single LF is an AELITIUM file-envelope allowance, not JCS output.
CRLF, more than one LF, leading/trailing space, indentation, BOM, alternate
member order, alternate escapes, and alternate number spellings are rejected
as `CANONICAL_BYTES_MISMATCH` after successful profile and schema validation.

### 6.6 Hash input

Hash exactly `C` with SHA-256 and encode the digest as 64 lowercase hexadecimal
characters:

```text
ai_hash_sha256 = lowercase_hex(SHA-256(C_v2(ai_output_v1)))

request_hash = lowercase_hex(SHA-256(C_v2(request_payload)))

response_hash = lowercase_hex(SHA-256(C_v2(response_payload)))

binding_hash = lowercase_hex(SHA-256(C_v2({
  "request_hash": request_hash,
  "response_hash": response_hash
})))

invocation_identity.hash_sha256 = lowercase_hex(SHA-256(C_v2({
  "format": "aelitium-invocation-v1",
  "surface": surface,
  "mode": mode,
  "request": normalized_request
})))

invocation_binding.hash_sha256 = lowercase_hex(SHA-256(C_v2({
  "format": "aelitium-invocation-binding-v1",
  "invocation_hash": invocation_hash,
  "response_hash": response_hash
})))
```

There is no newline, BOM, length prefix, identifier prefix, NUL separator, or
manifest data in these hash inputs. The required manifest identifier supplies
the interpretation context. Digest equality across different identifiers is
only equality of the resulting byte digest; it is not a cross-version semantic
comparison basis.

## 7. Identifier/versioning proposal

The exact identifier is:

```text
aelitium_jcs_profile_v2
```

A future manifest opts in only with the exact case-sensitive member:

```json
{"canonicalization":"aelitium_jcs_profile_v2"}
```

The identifier is an opaque, immutable registry key for all rules in sections
4 through 6. Implementations MUST NOT infer negotiable features from its words
and MUST NOT accept aliases, case variants, prefixes, or “closest supported”
versions.

The `v2` suffix versions the AELITIUM canonicalization contract; it does not
rename `ai_output_v1`, `ai_pack_manifest_v1`, or any bundle file. A
canonicalization change alone therefore needs no bundle-format or schema
change. If a later design changes any accepted value, parser rule, JCS rule,
numeric bound, normalization rule, storage envelope, or hash input, it MUST use
a new identifier.

Version dispatch is exact:

| Manifest value | Required action |
|---|---|
| Final selector is `json_sorted_keys_no_whitespace_utf8` | Re-read the original bytes and execute the complete frozen v1 behavior, including its compatibility cases and open large-integer boundary |
| Final selector is `aelitium_jcs_profile_v2` | Re-read the original bytes and execute only the strict v2 rules in this document; any duplicate selector is rejected during that parse |
| Selector is missing | Enter the legacy error-resolution route so existing object/required-field precedence is preserved; never infer a default |
| Final selector is non-string or any other value | Enter the legacy error-resolution route; if all earlier legacy checks pass, refuse it with `MANIFEST_BAD_CANONICALIZATION` and never try a version heuristically |

A dual-version verifier must not use a v2-strict parser to decide whether a
manifest is v1. It MUST use the exact `AELITIUM-DISPATCH-JSON-1` scanner and
routing algorithm in section 4.5. In particular, an RFC 8259-only parse is not
a conforming substitute because it rejects legacy non-finite tokens, and a
host value parse is not a conforming substitute because it can apply integer
limits before dispatch. Thus no accepted v2 manifest has last-name-wins
semantics, while no v2 parse or normalization narrows an old v1 manifest.

Support for v2 is an additive verifier capability. A v1-only verifier correctly
refuses it rather than mis-verifying it.

## 8. v1/v2 coexistence and migration

### 8.1 Coexistence

- Every v0.4.0/v1 bundle remains verified only under its recorded
  `json_sorted_keys_no_whitespace_utf8` identifier.
- The v1 parser, serializer, 30-case corpus, legacy non-finite behavior,
  duplicate-manifest last-wins behavior, ignored-manifest-surrogate behavior,
  and >640-digit OPEN boundary remain untouched.
- A new bundle uses v2 only by explicitly recording
  `aelitium_jcs_profile_v2` when it is built.
- A verifier supporting both contracts performs only the non-validating
  selector scan before dispatch, reparses the unchanged original bytes under
  the selected version, and never retries under another identifier after a v2
  failure.

### 8.2 Migration requires rebuilding evidence

V1-to-v2 migration is not an in-place metadata edit. It requires a new evidence
build that:

1. obtains the intended source values rather than treating old parsed Python
   objects as an authoritative cross-language model;
2. validates that every governed value, including metadata and embedded
   invocation material, is in the v2 domain;
3. canonicalizes every governed hash input with v2;
4. recomputes the payload, request, response, binding, invocation, and
   invocation-binding hashes that are present;
5. writes a manifest selecting v2; and
6. produces new signature material if signing is desired, because the raw
   manifest bytes changed.

Non-finite values, out-of-range numbers, Unicode noncharacters, invalid scalar
values, or other out-of-domain values make that source ineligible for v2. They
are not silently dropped, clamped, normalized, rounded from arbitrary precision,
or converted to strings by the canonicalizer.

There is no authorized general operation that “converts” old evidence while
preserving its evidence identity or hashes. Some shared-domain values can
coincidentally produce identical canonical bytes and SHA-256 values under both
identifiers. That coincidence does not make an edited manifest an original v2
artifact, does not preserve a signature over the manifest, and does not create
a cross-version comparison basis. The old bundle must be retained unchanged;
any v2 rebuild is a distinct artifact with its own creation and trust history.

## 9. Comparison implications

V1 and v2 cross-comparison is **basis-dependent in principle and disallowed by
every current comparison basis**.

The current `INVOCATION_IDENTITY_V1`, `REQUEST_HASH_V1_FALLBACK`, and
`REQUEST_HASH_V1_LEGACY` bases compare values whose bytes were constructed under
the bundle's canonicalization context. They define no equivalence relation
between contexts. Therefore, after independently verifying each input under its
recorded identifier, a current-contract comparison of different identifiers
MUST return:

```text
status: NOT_COMPARABLE
comparison_basis: NONE
comparison_reason: CANONICALIZATION_IDENTIFIER_MISMATCH
response_relationship: null
```

`CANONICALIZATION_IDENTIFIER_MISMATCH` is the exact stable reason for this new
input combination when v2 support is implemented. This result is not `CHANGED`,
is not `INVALID_BUNDLE` when both bundles verify, and makes no claim that the
responses differ.

None of the following authorizes cross-comparison:

- equal parsed JSON values;
- equal visible prompts or outputs;
- equal canonical payload bytes;
- equal payload, request, response, binding, or invocation digest strings; or
- the fact that one value lies in the intersection of the v1 and v2 domains.

A future cross-version comparison may be allowed only by a new, explicitly
named basis that defines all of the following normatively:

- which v1 and v2 identifiers it accepts;
- the exact field projection and type model compared;
- how numbers, negative zero, Unicode names, and absent/unknown fields are
  handled;
- whether it compares reconstructed values or a newly domain-separated digest;
- how both inputs must first verify under their own identifier; and
- the unchanged claim boundaries and `NOT_COMPARABLE` conditions.

Such a basis is not part of canonicalization v2. The existing verification,
assurance, comparison, and claim-boundary meanings remain intact.

## 10. Clean-room verifier readiness criteria

This design being implementation-ready is not authorization to claim a second
verifier. Before a Go, Rust, or other clean-room verifier can be called
conforming, all of the following must exist.

### 10.1 Normative publication set

1. A public normative specification containing sections 4 through 7 without
   relying on AELITIUM Python source.
2. Exact normative references to RFC 8259, RFC 7493, and RFC 8785, with reviewed
   errata handling and a statement that later ECMAScript output changes do not
   silently alter this identifier.
3. An identifier registry entry fixing `aelitium_jcs_profile_v2` and the exact
   hash-construction scope.
4. A complete integration specification for bundle parsing, the exact
   `AELITIUM-DISPATCH-JSON-1` grammar and routing algorithm, validation order,
   result reasons, signature raw-byte scope, and comparison refusal.
5. Published schemas plus an explicit statement that the v2 value profile is
   an additional constraint where a schema otherwise allows broader numbers or
   metadata.

### 10.2 Frozen corpus and runner

The v2 corpus must be immutable, reviewable data rather than values regenerated
by the production canonicalizer. Each case must contain:

- a stable case identifier and prose purpose;
- exact source bytes as hexadecimal or Base64 and their SHA-256 corruption
  check;
- source role (`canonical_payload`, `manifest`, or generic hash material);
- exact accept/reject decision and stable error category;
- exact canonical UTF-8 bytes and SHA-256 for accepted cases;
- whether zero or one storage LF is being tested; and
- any expected version-dispatch or comparison outcome.

The runner must not import the AELITIUM production canonicalizer to derive
expected results. It must test fixed-point behavior as well as one-shot output.

### 10.3 Version negotiation and refusal

Tests must prove exact dispatch for v1, v2, missing, malformed, non-string,
case-variant, and unknown selectors. There is no default, alias, prefix
negotiation, or best-effort version parse. An unsupported selector must never
complete verification; after the frozen earlier checks have passed, it fails
with `MANIFEST_BAD_CANONICALIZATION`. V2 profile rules must never be applied to
v1 artifacts.

The frozen corpus must test the scanner separately from both version parsers
and must prove all of the following using exact manifest bytes:

- each of `NaN`, `Infinity`, and `-Infinity` in an unknown extension before a
  final v1 selector is scanned and delivered unchanged to v1, which accepts it;
- an escaped unpaired high surrogate and an escaped unpaired low surrogate in
  unknown extensions before a final v1 selector reach v1 unchanged;
- a duplicate top-level selector whose final occurrence is v1 uses v1 legacy
  last-occurrence behavior, while a duplicate whose final occurrence is v2
  selects v2 and is then rejected by the fresh strict parse;
- duplicate unrelated members, including nested duplicates, remain available
  to v1 last-occurrence behavior but are rejected after v2 selection;
- selector names and identifier values expressed with equivalent JSON escapes
  are recognized, while case variants, prefixes, and nested selector names are
  not;
- 640-, 641-, 4300-, 4301-, and at least 10000-digit RFC 8259 integer tokens
  before the selector are scanned without numeric conversion; the v1 result is
  then checked with CPython limits 640, 4300, and disabled, reproducing the
  selected legacy parser rather than the scanner's host;
- a single manifest containing all legacy value forms before the final v1
  selector still reaches v1 and verifies when its configured digit limit
  permits;
- changing only the final selector in each legacy-form manifest to v2 causes a
  full strict reparse from byte zero and the appropriate v2 rejection, with no
  v1 retry;
- malformed UTF-8, BOM, truncated strings/escapes, trailing data, and malformed
  values cannot cause partial dispatch based on an earlier selector; and
- non-object, missing, non-string, and unknown-selector cases reproduce the
  existing `MANIFEST_NOT_OBJECT`, ordered `MANIFEST_MISSING_FIELD`,
  `MANIFEST_BAD_SCHEMA`, `MANIFEST_BAD_INPUT_SCHEMA`, and
  `MANIFEST_BAD_CANONICALIZATION` precedence as applicable.

Every case must assert both the selected route and the SHA-256 of the bytes
received by that version parser. For a v1 route, that digest must equal the
SHA-256 of the original manifest source. This makes byte preservation, not
merely the final reason string, a conformance property.

### 10.4 Required independent implementations

Before authorizing work on a full second-language verifier, the frozen
canonicalization corpus should be reproduced by:

- the future AELITIUM producer implementation;
- one independent JavaScript/TypeScript implementation, exercising the
  normative ECMAScript number behavior; and
- one independent UTF-8-native Go or Rust implementation, exercising explicit
  UTF-16 key-order conversion.

Those implementations must not share canonicalization decision code and must
agree byte-for-byte. Before making a six-language portability claim, the same
corpus must also pass independent Python, Go, Rust, JavaScript/TypeScript, Java,
and C# implementations. Every dependency version and test provenance must be
recorded. Passing upstream JCS vectors is necessary but not sufficient; the
AELITIUM profile, manifest, storage, hashing, and version vectors must pass too.

A full clean-room verifier must then pass the existing verification, assurance,
trust, Freshness, invocation, comparison, compatibility, and claim-boundary
corpora without importing, invoking, or translating through the Python decision
engine. Its v1 limitations must be labelled honestly if it implements only the
v1 restricted subset. V2 conformance does not manufacture complete v1
conformance.

## 11. Proposed conformance corpus

The corpus should contain at least the following families. Boundary neighbors
are mandatory; one happy-path vector per topic is insufficient.

| Family | Required positive cases | Required negative or alternate cases |
|---|---|---|
| Baseline values | null, both booleans, empty/nonempty string, empty arrays/objects, deeply nested mixed value | unsupported host types for programmatic API |
| Source encoding | ASCII and multi-byte UTF-8 | leading BOM, invalid continuation, overlong form, truncated sequence, UTF-8 surrogate encoding, trailing non-whitespace data, multiple top-level values |
| Object names | recursive sorting, empty/prefix names, escaped names | exact duplicate, duplicate through `\u` escape, duplicate nested in array/object, duplicate known and unknown manifest names |
| JCS key order | ASCII; BMP; non-BMP; U+1F600 versus U+E000; prefix ordering | a v1-ordered but not JCS-ordered stored payload |
| Unicode identity | NFC and NFD retained distinctly, valid surrogate pair, U+FEFF inside string, U+2028/U+2029 literal | lone high/low surrogate, reversed pair, U+FDD0/U+FDEF, U+FFFE/U+FFFF, plane-ending noncharacters |
| String escaping | quote, reverse solidus, five short controls, every remaining control class, solidus literal, non-ASCII literal | uppercase or unnecessary `\u` escape and escaped solidus as noncanonical storage |
| Safe integers | `0`, `-0`, `1`, `-1`, both inclusive `2^53 - 1` bounds | both `2^53` neighbors, very long integer token, leading zero, leading plus |
| Binary64 basics | `0.0`, `1.0`, `0.1`, current `temperature`/`top_p` examples, lexical aliases producing one value | non-finite programmatic values and non-JSON `NaN`/infinity tokens |
| Binary64 rendering | RFC rounding-sensitive samples inside the magnitude cap, `1e-6`, `1e-7`, minimum positive subnormal, exponent sign/case, negative zero | v1 `.0`, exponent padding, or v1 notation threshold as noncanonical storage |
| Binary64 parsing | exact halfway/ties-to-even cases, shortest-round-trip neighbors, smallest subnormal, underflow behavior fixed by expected bytes | decimal overflow to infinity, rounded result outside the magnitude cap, float32-intermediate trap |
| Arrays | preserved order and duplicate values | reordered stored array produces a different digest rather than normalization |
| Whitespace/storage | arbitrary legal source whitespace canonicalizes; exact `C`; exact `C || 0A` | leading/trailing space in stored payload, CRLF, two LF, pretty print, BOM |
| Hash input | exact canonical hex and SHA-256; identical digest for the two permitted storage envelopes | raw-file hash with LF does not match; any alternate canonical byte changes the digest |
| Manifest | valid v2 selector, valid ignored scalar/array/object extension, raw signature includes extension and whitespace | duplicate at any depth, invalid Unicode/number in unknown extension, malformed/unknown identifier, BOM |
| Pre-dispatch scanner | escaped selector name/value; final v1 after `NaN`, both infinities, surrogate escapes, duplicates, and 640/641/4300/4301/10000-digit tokens; exact original-byte handoff | partial selector before malformed suffix, selector only at nested depth, alias/case/prefix, scanner numeric conversion, duplicate final-v2 selector accepted by the scanner but rejected by the strict v2 reparse |
| Version isolation | released v0.4.0 fixtures and all adversarial legacy manifests still reach v1; shared-domain v1/v2 outputs may be observed | any v2 restriction applied before final-v1 dispatch; any changed v1 reason under each tested CPython digit limit; v1 retry after v2 failure |
| Comparison | same-identifier current bases retain existing outcomes | valid v1 versus valid v2 is `NOT_COMPARABLE`/`NONE`; equal visible JSON or digest does not override |

Numeric vectors should include both decimal source text and the expected
binary64 bit pattern where relevant. Unicode vectors should contain exact bytes,
not source-language string literals alone. Negative vectors must prove that the
parser detects the violation before a lossy map or number conversion hides it.

The corpus must import applicable upstream RFC 8785 cases but freeze copies of
their expected bytes and provenance so future upstream movement cannot change
this identifier silently.

## 12. Compatibility/non-claims

This design:

- does not modify or reinterpret `json_sorted_keys_no_whitespace_utf8`;
- does not place RFC 8259, I-JSON, v2 duplicate, v2 Unicode, v2 numeric, or a
  new integer-conversion restriction in front of the released v1 manifest
  parser;
- does not invalidate any v0.4.0/v1 artifact;
- does not change any current runtime code, schema, bundle filename, manifest
  shape, signature scope, hash algorithm, verification order, assurance state,
  comparison outcome meaning, or claim boundary;
- does not claim that old evidence was originally produced under v2;
- does not authorize hash-preserving migration or silent identifier rewriting;
- does not claim unprofiled JCS acceptance: the accepted domain is a strict
  AELITIUM profile, although every accepted value's output is RFC 8785 JCS;
- does not claim support for arbitrary JSON numbers, arbitrary-precision
  integers, arbitrary-precision decimals, non-finite values, signed-zero
  distinction, Unicode normalization, or duplicate names;
- does not claim that a particular JCS library is conforming without the frozen
  AELITIUM tests;
- does not authorize a Go, Rust, or other independent verifier yet; and
- establishes only deterministic representation and hashing, not semantic
  truth, provider execution, response causation, capture completeness,
  historical occurrence, historical non-modification, trusted time,
  authorization, legal compliance, or semantic equivalence.

The optional storage LF does not weaken the canonical byte definition because
it is excluded from `C` and every hash. Unknown manifest fields do not acquire
semantics merely because they are accepted or signed.

## 13. Open questions

There are no unresolved normative design blockers.

The pre-dispatch compatibility blocker is resolved normatively by section 4.5:
selector discovery uses the explicit legacy-plus-v2 union grammar without
value conversion, and every non-v2 route re-enters the frozen v1 path with the
original bytes. Readiness still requires implementing and independently
proving that rule; implementation evidence is a release gate, not an omitted
design decision.

The following are implementation and release-gate choices, not permission to
change this contract:

- select and pin candidate JCS libraries per language after corpus evaluation;
- implement the selector scanner and pass the v1-isolation matrix in sections
  10.3 and 11 without applying a host numeric conversion;
- define implementation resource ceilings and a distinct operational
  resource-exhaustion report without reclassifying a valid value as
  semantically invalid;
- build and independently review the proposed frozen corpus;
- decide which Go or Rust implementation team performs the eventual clean-room
  work; and
- define field-specific decimal-string schemas only if a future evidence use
  case actually needs them.

If implementation work discovers that an accepted value cannot be reproduced
under the rules above, the design returns to review and receives a new
identifier if the normative contract changes. The v2 identifier must not drift
to accommodate an implementation.

## 14. Final verdict

V2_DESIGN_READY_FOR_IMPLEMENTATION
