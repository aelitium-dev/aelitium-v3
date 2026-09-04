# Canonicalization Specification

**Version:** 1.1 clarification (UNRELEASED)

**Status:** IMPLEMENTATION-ALIGNED

**Current manifest identifier:** `json_sorted_keys_no_whitespace_utf8`

## Purpose and compatibility boundary

This document fixes the byte-level behavior of the canonicalization identifier
already used by AELITIUM v0.4.0. It does not introduce a new identifier and
does not change the meaning of an existing valid bundle.

This is an AELITIUM-specific, Python-aligned contract. It is not RFC 8785/JCS,
does not claim universal JSON canonicalization, and must not be presented as
equivalent to another canonicalization standard. In particular, its
floating-point formatting, Unicode key order, and preserved non-finite tokens
differ from rules used by some other canonicalizers.

The cross-language closure status and restricted subset are stated explicitly
below. Values outside that subset do not acquire an interoperability claim.

## Scope

The identifier governs value-to-byte conversion used by:

- `engine/canonical.py` and `engine/ai_canonical.py`;
- the `ai_output_v1` payload digest;
- request, response, and original binding hashes produced by capture adapters;
- `aelitium-invocation-v1` and
  `aelitium-invocation-binding-v1` hash material; and
- bundle verification when it reconstructs canonical payload bytes.

This specification distinguishes three layers:

1. **source parsing**, which turns UTF-8 source bytes into values;
2. **canonical serialization**, which turns those values into canonical bytes;
   and
3. **stored-payload acceptance**, which permits the canonical bytes with either
   no suffix or one terminal LF.

The terminal LF is a storage allowance only. It is never part of a canonical
value or a digest input.

## Source-byte and value domain

### Encoding and lexical grammar

Governed source is decoded as strict UTF-8. Ill-formed UTF-8 and a leading
UTF-8 BOM are rejected. After decoding, the accepted lexical grammar is the
standard JSON grammar plus exactly these three case-sensitive, unquoted legacy
number tokens:

```text
NaN
Infinity
-Infinity
```

No other spelling is equivalent. For example, `nan`, `inf`, `+Infinity`, and
`-infinity` are parse errors. This legacy extension is preserved because
v0.4.0 accepts self-consistent bundle metadata containing those exact tokens;
it is not a claim that they are JSON numbers.

Standard JSON whitespace is accepted by the parsing layer. It is not emitted
by canonical serialization and, except for the one storage LF described below,
causes stored canonical payload bytes to be rejected.

### Canonicalized values

The value model subject to canonical serialization contains:

- `null`;
- booleans;
- strings made only of Unicode scalar values;
- arrays in source order;
- objects whose member names are strings;
- signed base-10 integers; and
- IEEE 754 binary64 values, including positive zero, negative zero, finite
  values, and the three preserved non-finite values.

`ai_output_v1` further requires an object with its published top-level schema.
Its `metadata` object permits additional values recursively. Result-contract
schemas are closed and do not broaden this domain.

The manifest is parsed but is not itself canonicalized. Released v0.4.0 also
accepts an escaped unpaired surrogate in an unknown, otherwise ignored manifest
extension because that value is never serialized or used by a manifest check.
That Python-aligned legacy behavior is preserved, but such a manifest is
outside the cross-language-safe restricted subset. Ill-formed raw UTF-8 is
still rejected while reading the manifest.

### Duplicate member names

Source parsing processes object members left to right. When a name occurs more
than once, the last occurrence supplies the parsed value. Canonical
serialization emits that name once.

Consequences are deliberately separated:

- a source document supplied to a canonicalization command can be normalized
  from duplicate names to the last values;
- an `ai_canonical.json` file containing duplicate names cannot equal its
  reconstructed canonical bytes and is rejected as
  `CANONICAL_BYTES_MISMATCH`; and
- `ai_manifest.json` is parsed but not canonicalized, so released v0.4.0
  behavior keeps the last value and may accept a duplicate manifest member
  when that final value satisfies the manifest checks.

A verifier must reproduce those consequences. Globally rejecting duplicate
manifest names would invalidate inputs accepted by v0.4.0 and is not authorized
under this identifier.

### Unicode scalar validity

A Unicode scalar value is U+0000..U+D7FF or U+E000..U+10FFFF. U+D800..U+DFFF
are surrogate code points, not scalar values.

- A valid `\u` high-surrogate/low-surrogate pair in source is decoded to its
  single non-BMP scalar value.
- An unpaired surrogate escape in governed canonical payload data cannot be
  encoded as canonical UTF-8. For an otherwise processable bundle it is
  rejected as `CANONICAL_NOT_JSON` at the former hashing failure point.
- A UTF-8 byte sequence that attempts to encode a surrogate is ill-formed UTF-8
  and is also rejected as `CANONICAL_NOT_JSON`.

This rejection closes a previous uncaught encoding-error path. It does not
invalidate an artifact that could complete v0.4.0 hashing or verification, and
it does not move ahead of manifest or payload-schema errors that v0.4.0 already
returned. It applies to values governed by canonical serialization, not to
ignored manifest extensions under the legacy parser behavior described above.

## Canonical serialization

The rules in this section are recursive. Their result is a Unicode string made
only of scalar values, then encoded as strict UTF-8.

### Objects and key order

Objects emit `{`, zero or more member pairs separated by `,`, and `}`. A member
pair is the serialized name, `:`, and serialized value. No whitespace is
added.

Names are ordered lexicographically by Unicode scalar-value sequence:

1. compare the numeric scalar value at the first differing position;
2. the smaller scalar value sorts first; and
3. if one sequence is an exact prefix of the other, the shorter sequence sorts
   first.

Ordering is not based on UTF-8 bytes, locale, normalized text, or UTF-16 code
units. This distinction is observable for keys such as U+E000 and U+1F600:
U+E000 sorts first here.

### Arrays

Arrays emit `[`, elements separated by `,`, and `]`. Input order is preserved.
No element sorting or semantic normalization occurs.

### Strings and escaping

Strings emit surrounding U+0022 quotation marks. Unicode normalization is not
performed. Valid non-ASCII scalar values, including non-BMP values, are emitted
literally and become their ordinary UTF-8 sequences.

Within a string, escaping is exactly:

| Scalar | Output |
|---|---|
| U+0022 quotation mark | `\"` |
| U+005C reverse solidus | `\\` |
| U+0008 backspace | `\b` |
| U+0009 horizontal tab | `\t` |
| U+000A line feed | `\n` |
| U+000C form feed | `\f` |
| U+000D carriage return | `\r` |
| other U+0000..U+001F controls | `\u00xx`, with lowercase hexadecimal digits |
| every other scalar | literal scalar |

U+002F solidus is not escaped. U+2028 and U+2029 are emitted literally. An
ASCII or non-ASCII scalar written with a source `\u` escape therefore becomes
literal when that is the rule above; the escaped source spelling is not an
accepted stored canonical spelling.

### Null and booleans

The exact tokens are lowercase `null`, `true`, and `false`.

### Integers

Integer values emit their ordinary base-10 magnitude with an optional leading
`-`. There is no leading `+`, no leading zero except for the value zero, no
decimal point, and no exponent. Integer negative zero has value zero and emits
`0`.

The payload schema does not bound metadata integer magnitude. The verifier also
accepts unknown manifest extension members, and the verification-result schema
does not bound `policy_inputs[].maximum_age_seconds`. CPython 3.10+ integers are
arbitrary precision, but patched runtimes apply a configurable decimal
conversion guard: its default is 4,300 digits, its minimum nonzero setting is
640 digits, and it can be disabled. Because released v0.4.0 delegates source
conversion to that runtime, the full extreme-integer acceptance boundary is
**OPEN** and must not be guessed by an independent implementation.

The cross-language-safe restricted subset includes integer magnitudes of at
most 640 decimal digits in every parsed input and serialized result location.
This is a subset declaration, not a new verifier rejection rule. Existing
implementations may accept larger values.

### Finite binary64 values

A source number containing `.` or `e`/`E` is converted to the nearest IEEE 754
binary64 value using round-to-nearest, ties-to-even. The sign of an underflowed
or lexical zero is preserved. Decimal overflow produces the corresponding
infinity value under the preserved parser behavior.

For the magnitude of a finite, nonzero binary64 value `x`, define a decimal
candidate by a digit string `D` and integer exponent `e`:

```text
value(D, e) = integer(D) * 10 ** (e - (length(D) - 1))
```

`D` has no leading zero and no removable trailing zero. A candidate qualifies
when converting `value(D, e)` by the binary64 rule above produces exactly
`abs(x)`. Choose candidates in this order:

1. smallest `length(D)`;
2. smallest exact mathematical distance between `value(D, e)` and `x`; and
3. for an exact distance tie, the candidate whose final digit is even.

This uniquely selects the shortest-round-trip decimal used by supported
CPython 3.10–3.12 `float.__repr__`.

Using the selected `D` and `e`:

- when `-4 <= e < 16`, emit fixed notation;
- otherwise emit scientific notation with lowercase `e`, an explicit exponent
  sign, and at least two exponent digits;
- in fixed notation, append `.0` when the result would otherwise look like an
  integer; and
- in scientific notation, do not add `.0` solely to mark the binary64 type.

Fixed notation places the decimal point after `e + 1` digits, adding leading or
trailing zero digits as required. When the point would follow all significant
digits, append enough zero digits and then `.0`. Scientific notation emits the
first digit, then `.` and the remaining digits when any remain, followed by
`e`, the exponent sign, and `abs(e)` padded to at least two digits.

Negative values prepend `-`. Positive zero emits `0.0`; negative zero emits
`-0.0`.

Examples at observable boundaries are:

```text
0.0001                    -> 0.0001
0.00001                   -> 1e-05
1000000000000000.0        -> 1000000000000000.0
10000000000000000.0       -> 1e+16
0.30000000000000004       -> 0.30000000000000004
-0.0                      -> -0.0
```

### Non-finite binary64 values

The preserved spellings are exact:

```text
positive infinity -> Infinity
negative infinity -> -Infinity
NaN               -> NaN
```

NaN sign and payload are not preserved. These values are outside the
cross-language-safe restricted subset even though the current identifier and
v0.4.0 verifier accept their exact stored spellings in otherwise unrestricted
metadata. `aelitium-invocation-v1` separately rejects every non-finite value as
`INVOCATION_BAD_VALUE`.

## Stored canonical payload bytes

Let `C` be the strict UTF-8 result of canonical serialization. The only valid
stored `ai_canonical.json` byte sequences are:

```text
C
C || 0A
```

The second form has exactly one terminal LF. The accepted forms do not include
CRLF, multiple LFs, leading or trailing space, indentation, a BOM, alternate
key order, alternate number spelling, or source escapes where literal scalars
are required.

The digest is always:

```text
lowercase_hex(SHA-256(C))
```

The optional LF is never hashed. Thus both accepted storage forms have the same
digest.

## Hash constructions

```text
ai_hash_sha256 = SHA256(UTF8(canonical(ai_output_v1)))

request_hash = SHA256(UTF8(canonical(request_payload)))

response_hash = SHA256(UTF8(canonical(response_payload)))

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

## Verifier failure mapping and precedence

This clarification does not add a result-contract reason or move a check:

1. strict UTF-8 failure or JSON lexical failure returns `CANONICAL_NOT_JSON`;
2. existing manifest checks retain their published positions;
3. an invalid `ai_output_v1` value returns `CANONICAL_SCHEMA_INVALID`;
4. after those checks, an unpaired surrogate in an otherwise processable
   canonical payload returns `CANONICAL_NOT_JSON` instead of raising an
   encoding exception;
5. valid parsed content with noncanonical stored bytes returns
   `CANONICAL_BYTES_MISMATCH`; and
6. only after exact bytes pass can a different manifest digest return
   `HASH_MISMATCH`.

All other verification order, assurance states, and exit codes remain as
documented in `INDEPENDENT_VERIFIER_REQUIREMENTS.md`.

## Cross-language closure status

| Area | Status | Boundary |
|---|---|---|
| UTF-8, whitespace, arrays, null, booleans, terminal LF | **CLOSED** | Exact rules above and frozen vectors apply. |
| Unicode scalar validation, escaping, normalization, key order | **CLOSED** | Only scalar values; code-point order; exact escape table. |
| Unpaired surrogates in ignored manifest extensions | **CLOSED legacy behavior** | The manifest is not canonicalized; preserve acceptance when an escaped value is not used by a manifest check, but exclude it from the restricted subset. |
| Duplicate canonical-payload names | **CLOSED** | Last-value parse followed by exact-byte rejection. |
| Duplicate manifest names | **CLOSED legacy behavior** | Last value wins; no new rejection under v0.4 semantics. |
| Finite binary64 parsing and rendering | **CLOSED** | IEEE conversion plus the shortest-round-trip and notation rules above. |
| Non-finite values | **CLOSED legacy behavior** | Three exact tokens are preserved but excluded from the restricted subset. |
| Integers of at most 640 magnitude digits | **RESTRICTED SUBSET** | Exact base-10 arbitrary-precision behavior. |
| Integers above 640 magnitude digits | **OPEN** | CPython conversion guard is configurable. |

The frozen corpus is `conformance/canonicalization/vectors.json`. It contains
source bytes, acceptance decisions, canonical bytes, digests, and rejection
reasons. Expected bytes and digests are data in the corpus; the runner does not
derive them with AELITIUM's canonicalizer.

## Manifest identifier and versioning

Manifests continue to use:

```json
{
  "canonicalization": "json_sorted_keys_no_whitespace_utf8"
}
```

This clarification preserves existing value-to-byte behavior. A future rule
that rejects currently accepted non-finite values, globally rejects duplicate
manifest names, imposes a new extreme-integer limit, normalizes Unicode, or
changes float formatting must use a new identifier and an explicit
compatibility plan.

## Non-guarantees

Canonicalization establishes only deterministic bytes and hashes within its
stated domain. It does not establish semantic equivalence, semantic truth,
provider execution, response causation, capture completeness, historical
occurrence, historical non-modification, authorization, legal compliance, or
equivalence with another canonicalization standard.
