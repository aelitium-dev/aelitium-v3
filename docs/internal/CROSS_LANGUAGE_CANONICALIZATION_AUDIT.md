# Cross-Language Canonicalization Audit

**Status:** IMPLEMENTATION-ALIGNED
**Baseline:** `73cf5b094a8699e2b7b0f90e9a78d1d07d102d0d`
**Scope:** pre-implementation audit for
`json_sorted_keys_no_whitespace_utf8`

This is an internal compatibility audit, not a new canonicalization contract.
It records the behavior that must be preserved before the public specification
or conformance corpus is strengthened. No claim of RFC 8785/JCS equivalence is
made.

## Compatibility decision

The identifier cannot safely be narrowed to standards-only JSON:

- an `ai_output_v1.metadata` value containing an exact `NaN`, `Infinity`, or
  `-Infinity` token can pass the released v0.4.0 verifier when the manifest
  digest matches;
- the schema places no numeric bounds on metadata integers, manifests accept
  unknown extension values, and the verification-result policy integer is
  unbounded, while CPython's decimal-integer conversion guard is runtime
  configurable; and
- manifest parsing currently keeps the last value for a duplicate member name,
  so some manifests containing duplicate names pass verification.

Rejecting any of those previously accepted inputs under the existing identifier
would change v0.4.0 semantics. Those restrictions are therefore **BLOCKED** for
this task. Phase 2 may document the exact preserved behavior and define a
cross-language-safe restricted subset, but it must not make the current verifier
reject those artifacts.

One compatibility-preserving restriction is available: an unpaired UTF-16
surrogate escape in the governed canonical payload currently reaches a
`UnicodeEncodeError` and cannot complete hashing or verification. Converting
that crash into deterministic rejection changes no accepted artifact.

## Audited surfaces

The following authoritative paths were inspected:

- `engine/canonical.py`;
- `engine/ai_canonical.py` and the canonical-payload path in
  `engine/ai_verify.py`;
- `engine/invocation.py`;
- `engine/invocation_binding.py`;
- `engine/schemas/ai_output_v1.json` and `input_v1.json`;
- all three result-contract schemas;
- `docs/CANONICALIZATION_SPEC.md`;
- `docs/INDEPENDENT_VERIFIER_REQUIREMENTS.md`;
- `docs/VERIFICATION_RESULT_V1.md`; and
- the 44-case `conformance/` corpus, runner, and deterministic builders.

`ai_output_v1.metadata` is the governed bundle-schema location with
unconstrained additional JSON values. The manifest has no packaged JSON Schema
and its verifier accepts unknown members, so ignored manifest extensions can
also contain broad JSON values. `input_v1.payload` is broad but belongs to the
legacy generic input surface rather than the AI bundle verifier. The result
contracts do not admit arbitrary metadata; however,
`verification_result_v1.policy_inputs[].maximum_age_seconds` is an unbounded
integer and shares the extreme-integer portability concern when that result is
serialized.

## Findings by closure area

| Area | Audit classification | Current behavior | Proposed closure | Changes a currently valid v0.4.0 artifact? |
|---|---|---|---|---|
| Floating-point rendering | **ambiguous in current contract**; **Python-specific behavior**; **requires additional normative rule** | JSON numbers containing `.` or an exponent are parsed as IEEE 754 binary64 by CPython and emitted using CPython's shortest round-tripping `repr` spelling. Fixed/scientific thresholds, exponent padding, rounding ties, and `-0.0` are not fully stated. | Specify binary64 conversion and the exact shortest-decimal formatting rule; freeze exponent and rounding boundary vectors. | **No.** The rule describes existing bytes. |
| Non-finite numbers | **Python-specific behavior**; **requires additional normative rule** | Exact tokens `NaN`, `Infinity`, and `-Infinity` are accepted by `json.loads`, retained in unrestricted metadata, emitted with the same spellings, and can verify. Decimal overflow such as `1e400` parses to infinity but is not canonical because it re-emits as `Infinity`. Invocation identity independently rejects non-finite values. | Preserve and explicitly delimit the three legacy tokens for the existing identifier. Exclude them from any standards-JSON claim. A rejection rule is blocked. | **No** for documentation. **Yes** if they were rejected, so rejection is prohibited here. |
| Unicode key ordering | **ambiguous in current contract**; **requires additional normative rule** | `sort_keys=True` compares Python strings lexicographically by Unicode code point. This differs from UTF-8-byte and UTF-16-code-unit ordering for some keys. | Specify lexicographic Unicode scalar-value order, recursively, with shorter-prefix-first behavior; freeze BMP/non-BMP ordering vectors. | **No.** |
| Unicode escaping | **Python-specific behavior**; **requires additional normative rule** | `ensure_ascii=False` emits valid non-ASCII scalars literally, escapes quote and reverse solidus, does not escape solidus, uses short escapes for BS/HT/LF/FF/CR, and uses lowercase `\u00xx` for the other U+0000..U+001F controls. No normalization occurs. | State the exact table and freeze literal-versus-escaped, control, non-ASCII, and non-BMP vectors. | **No.** |
| Duplicate object keys | **ambiguous in current contract**; **Python-specific behavior**; **requires additional normative rule** | Parsing keeps the last member value. A governed canonical payload containing a duplicate name then fails exact-byte comparison with `CANONICAL_BYTES_MISMATCH`. Manifests are not canonicalized, so duplicate required members can pass when the last value is valid. | State last-occurrence parsing and the different payload/manifest consequences. Do not add a global duplicate-key rejection under v0.4 semantics. | **No** for documentation. **Yes** for manifest-wide rejection, so that restriction is prohibited here. |
| Invalid Unicode scalar sequences | **ambiguous in current contract**; **Python-specific behavior**; **requires compatibility-preserving restriction** | Ill-formed UTF-8 is rejected as `CANONICAL_NOT_JSON`. A valid surrogate pair escape decodes to one non-BMP scalar, but its escaped payload spelling is noncanonical. An unpaired surrogate escape in the canonical payload parses, then raises during UTF-8 hashing instead of returning a verifier result. An escaped unpaired surrogate in an unknown, ignored manifest extension can pass because the manifest is parsed but not canonicalized. | Require scalar-value strings for governed canonical data and deterministically reject unpaired surrogate payload escapes as `CANONICAL_NOT_JSON`. Preserve raw UTF-8 strictness, valid-pair decoding, and ignored-manifest-extension acceptance; exclude the latter from the restricted subset. | **No.** An unpaired-surrogate canonical payload cannot currently complete verification, while the accepted manifest-extension case remains accepted. |
| Terminal newline | **already unambiguous** | The canonical hash input has no newline. Stored `ai_canonical.json` accepts exactly the canonical bytes or those bytes followed by one LF. CRLF, two LFs, and other surrounding whitespace fail with `CANONICAL_BYTES_MISMATCH`. | Consolidate the existing rule and add frozen variants. | **No.** |
| Integer/number edges | **Python-specific behavior**; **ambiguous in current contract**; **requires compatibility-preserving restriction** for complete closure | Integer tokens are parsed as Python integers and emitted in ordinary base-10 form. Canonical metadata and ignored manifest extensions have no bounds; verification policy output also permits an unbounded integer. CPython's decimal conversion guard defaults to 4,300 digits, can be configured down to 640 or disabled, and therefore makes the extreme accepted domain host-dependent. | Freeze representative exact integers and define the portable restricted subset as integers whose magnitude has at most 640 decimal digits in every parsed or serialized location. Values beyond that subset remain **OPEN** under this identifier. A new global cap is blocked. | **No** for a subset declaration. **Yes** if imposed on all v0.4 artifacts, so no runtime cap may be added here. |

## Other serialization rules

These areas are already implementation-aligned but should be consolidated in
the public specification:

- source bytes are decoded as strict UTF-8 and a UTF-8 BOM is not accepted;
- objects and arrays use `{}`, `[]`, comma, and colon with no insignificant
  whitespace;
- array order is preserved;
- `null`, `true`, and `false` use those exact lowercase spellings;
- integer `-0` parses as integer zero and canonicalizes as `0`, while binary64
  negative zero canonicalizes as `-0.0`;
- object member names are JSON strings; and
- the SHA-256 input is the canonical byte sequence without the optional stored
  terminal LF.

## Compatibility probes

The baseline implementation was exercised directly with self-consistent
temporary bundles:

| Input characteristic | Baseline result |
|---|---|
| metadata `NaN` | `VALID / OK` |
| metadata `Infinity` | `VALID / OK` |
| metadata `-Infinity` | `VALID / OK` |
| metadata lexical `1e400` | `INVALID / CANONICAL_BYTES_MISMATCH` |
| duplicate metadata member | `INVALID / CANONICAL_BYTES_MISMATCH` |
| duplicate manifest member, last value valid | `VALID / OK` |
| literal non-BMP scalar | `VALID / OK` |
| escaped non-BMP scalar pair | `INVALID / CANONICAL_BYTES_MISMATCH` |
| unpaired surrogate escape in canonical payload | uncaught `UnicodeEncodeError` |
| unpaired surrogate escape in ignored manifest extension | `VALID / OK` |
| ill-formed UTF-8 surrogate bytes | `INVALID / CANONICAL_NOT_JSON` |
| no terminal LF | `VALID / OK` |
| one terminal LF | `VALID / OK` |
| two terminal LFs | `INVALID / CANONICAL_BYTES_MISMATCH` |

These probes agree with the released v0.4.0 source at tag commit
`3506a4fdd8adc6a4c4aec25799cd2add2b2a1f73`: its canonicalizer and relevant
verification path are byte-for-byte the same as the baseline implementation.

## Phase 2 implementation boundary

Safe work after this audit is limited to:

1. documenting the exact existing value-to-byte rule without claiming JCS or
   universal JSON behavior;
2. adding deterministic rejection for unpaired surrogate escapes in governed
   canonical payloads at the former hashing failure point, after preserving
   already-returned manifest and payload-schema reason precedence;
3. freezing positive and negative vectors, including the preserved non-finite
   legacy tokens;
4. declaring integer inputs above the 640-digit interoperable subset **OPEN**;
   and
5. leaving the identifier, hashes, result contracts, verification order,
   reasons for all currently returned cases, and exit codes unchanged.

Complete cross-language closure of every value admitted by broad metadata is
not safe under the existing identifier because the extreme integer domain is
runtime-dependent. The smallest safe alternative is an explicit restricted
subset plus a future, separately versioned decision about extreme integers. No
second verifier is authorized by this audit.
