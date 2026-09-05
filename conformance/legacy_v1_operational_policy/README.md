# Legacy v1 Compatibility and Operational-Policy Corpus

**Status:** NORMATIVE-UNRELEASED

**Contract:** `aelitium-legacy-v1-operational-policy-conformance-v1`

**Operation contract:** `AELITIUM-LEGACY-V1-POLICY-OPERATION-1`

This separate 94-case corpus supplies language-neutral acceptance evidence for
[`aelitium-legacy-v1-compatibility-operational-policy-v1`](../../docs/LEGACY_V1_COMPATIBILITY_AND_OPERATIONAL_POLICY_V1.md).
It does not edit, renumber, reinterpret, or replace the existing 44-case result
contract, 30-case v1 canonicalization, or 114-case v2 canonicalization corpus.

The current Python verifier does not implement the new operational transport.
The runner here audits committed contract data; it deliberately does not call
the Python verification engine or claim that an independent verifier exists.

## Coverage

| Family | Cases | Scope |
|---|---:|---|
| `INTEGER_CAPABILITY` | 23 | 640/641/4300/4301/10000 and arbitrary limits, bounded/unlimited profiles, occurrence-wide conversion, dispatch isolation |
| `TIMESTAMP_COMPATIBILITY` | 16 | ASCII, frozen Unicode Nd membership, outside-table behavior, and exact final-LF structure |
| `DETERMINISTIC_LEGACY` | 12 | last-name-wins, non-finites, surrogate code units, Base64 pad bits, open members, empty trust input |
| `OPERATIONAL_LIMIT` | 12 | below/at/above file, aggregate, depth, and value-occurrence limits |
| `OPERATIONAL_RESOURCE` | 4 | deterministic injected exhaustion in dispatch and parsers |
| `FILESYSTEM_SNAPSHOT` | 24 | regular/non-regular inputs, no-follow behavior, I/O, instability, stable absence, immutable equivalence |
| `OPERATIONAL_TRANSPORT` | 3 | output/internal failure and unsupported-v1 dispatch |

## Frozen case form

[`cases.json`](cases.json) freezes every case identifier, exact configuration,
input recipe, source length and SHA-256, and expected policy checkpoint or full
operational tool result. Full operational results also freeze their exact RFC
8785 UTF-8 bytes plus one LF and SHA-256. Those results necessarily contain:

- `outcome` equal to `OPERATIONAL_OUTCOME`;
- rc 3;
- null `verification_result`;
- no assurance object;
- no semantic `INVALID` status or reason; and
- no comparison result.

`POLICY_CHECKPOINT` cases stop at the cross-cutting rule this policy owns. They
do not fabricate a complete verification result where G-04, G-05, G-06, or
G-08 must still publish field grammar or final reason/state construction.

## Operation registry

`AELITIUM-LEGACY-V1-POLICY-OPERATION-1` is a closed operation vocabulary. Each
case supplies all operands in `input`; a harness must not obtain additional
bytes, limits, profiles, environment facts, or expected decisions from the
Python implementation. Unknown operations are corpus errors.

| Operation | Exact harness action |
|---|---|
| `SELECT_CAPABILITY` | Authenticate the requested frozen profile before acquiring evidence and compare the resulting operational wrapper |
| `CLASSIFY_INTEGER_SOURCE` | Materialize the identified source, traverse integer occurrences in source order under its declared role/position, and apply policy section 5 at the recorded occurrence |
| `CLASSIFY_PROGRAMMATIC_INTEGER` | Treat the recipe bytes as the exact signed base-10 magnitude supplied by a non-source API and apply the declared conversion capability without binary64 narrowing |
| `DISPATCH_MANIFEST` | Materialize the original manifest bytes, run `AELITIUM-DISPATCH-JSON-1`, and consult only the selected route's capability after scanning completes |
| `VALIDATE_MANIFEST_TIMESTAMP` | Decode the standalone JSON-string source, verify the committed `decoded_code_points`, and apply policy section 6 with the selected timestamp profile |
| `APPLY_LEGACY_RULE` | Apply the section 7 rule named by the case and compare the complete committed checkpoint facts |
| `DECODE_LEGACY_BASE64` | Decode the committed standard-alphabet/padded spelling with the legacy unused-pad-bit rule and compare the exact decoded bytes and canonical re-encoding facts |
| `MEASURE_SOURCE_LIMIT` | Compare the materialized role's exact byte count with the effective per-file limit; equality is within limit |
| `MEASURE_SNAPSHOT_LIMIT` | Sum the exact bytes of every committed present role and compare with the effective aggregate limit; equality is within limit |
| `MEASURE_TRAVERSAL_LIMIT` | Traverse the materialized value left to right using the public depth/value definitions and stop at the first established crossing |
| `INJECT_RESOURCE_FAILURE` | At the exact named phase, make the next requested allocation/resource operation fail and compare the operational wrapper without semantic fallback |
| `ACQUIRE_SNAPSHOT` | Execute the closed synchronized filesystem recipe below under the direct-filesystem contract |
| `COMPARE_INPUT_MODES` | Build both committed role maps, freeze them, and compare role presence and exact bytes without semantic evaluation |
| `CLASSIFY_STABLE_ABSENCE` | Observe and recheck the named absent role during one acquisition interval, then compare its already-authorized absence checkpoint |
| `INJECT_OPERATIONAL_FAILURE` | Inject the named internal/output adapter event at its defined boundary and compare the complete operational wrapper |

A `POLICY_CHECKPOINT` comparison is exact over every committed member of
`expected`; it does not imply a missing downstream semantic result. An
`OPERATIONAL_TOOL_RESULT` comparison additionally validates the complete outer
object, exact RFC 8785-plus-LF bytes, and their SHA-256.

## `AELITIUM-BYTES-RECIPE-1`

Large boundary inputs are exact without embedding megabytes of repeated text.
The recipe language is closed and recursively deterministic:

| Operation | Fields | Exact bytes |
|---|---|---|
| `LITERAL_HEX` | `hex` | Bytes represented by even-length lowercase hexadecimal |
| `REPEAT_BYTE` | `byte_hex`, `count` | One byte repeated `count` times |
| `CONCAT` | `parts` | Child recipe byte strings concatenated in array order |
| `JSON_STRING_OF_SIZE` | `byte_length`, `fill_byte_hex` | quote, safe printable one-byte ASCII fill repeated `byte_length-2`, quote |
| `NESTED_ARRAY` | `depth`, `scalar_hex` | `depth` opening brackets, scalar bytes, `depth` closing brackets |
| `NULL_ARRAY` | `value_occurrences` | One root array containing `value_occurrences-1` exact `null` elements |

Counts are non-negative integers; a source descriptor freezes recipe, exact
byte length, and SHA-256. Hexadecimal is decoded as octets, never as host text.
All arithmetic is exact integer arithmetic. A consumer must reject unknown
operations or extra/missing recipe fields.

## Abstract filesystem recipes

Filesystem cases define synchronized behavior-level adapter operations rather
than OS-specific calls. The step vocabulary and operands are closed:

| Step | Required operands | Exact effect |
|---|---|---|
| `CREATE_REGULAR` | `role`, `source` | Make the role an unchanged regular file containing the materialized source |
| `CREATE_OBJECT` | `role`, `object_kind` | Make the role the exact non-regular/symlink kind named below; do not open content |
| `INJECT_FAILURE` | `role`, `event` | Cause the named metadata/open/read boundary to fail for that role |
| `WAIT_AT` | `role`, `point` | Block at the named deterministic acquisition barrier |
| `MUTATE_AT_POINT` | `role`, `event` | Perform the exact mutation while acquisition is blocked at that barrier |
| `CONTINUE` | none | Release the preceding barrier and finish acquisition checks |
| `LIMIT_READ_CHUNK` | `chunk_bytes` | Make every successful read return at most the positive byte count without creating EOF |
| `ACQUIRE_AND_FREEZE` | none | Complete acquisition/rechecks and freeze the role map |
| `OBSERVE_ABSENT` | `role` | Record the role as absent during initial observation |
| `RECHECK_ABSENT` | `role` | Confirm the same role remains absent at the final stability check |
| `REPLACE_AFTER_FREEZE` | `role`, `source` | Replace the external path only after freeze; captured bytes remain unchanged |

Roles are closed to `BUNDLE_DIRECTORY`, `AI_CANONICAL_JSON`,
`AI_MANIFEST_JSON`, `VERIFICATION_KEYS_JSON`, and `TRUST_STORE`. Object kinds
are `SYMLINK`, `DIRECTORY`, `FIFO`, `DEVICE`, and `SOCKET`.

The sole barrier point is `SOURCE_OPENED`: the no-follow source identity is
held and its initial metadata recorded, but byte acquisition and final
stability checks are not complete. Mutation events are
`REMOVE_REACHED_ENTRY`, `REPLACE_REACHED_ENTRY`, `INJECT_PREMATURE_EOF`,
`TRUNCATE_OPEN_FILE`, `APPEND_OPEN_FILE`, and `MUTATE_OPEN_FILE`. Injected I/O
events are `DENY_PERMISSION`, `FAIL_OPEN`, and `FAIL_READ`.
`WAIT_AT`/`MUTATE_AT_POINT` are synchronized barriers, never sleeps.

Object kinds that cannot safely be constructed on a platform are still
mandatory at the abstract adapter boundary. The public policy supplies the
meaning of regular-file, no-follow, stability, and immutable-byte outcomes.

## Frozen Unicode profiles

[`unicode/profiles.json`](unicode/profiles.json) and its three range files are
normative profile data. The range bytes, profile identifiers, source
provenance, counts, and SHA-256 values are audited without consulting the host
Unicode database. The derived data are distributed under
[`UNICODE_LICENSE.txt`](unicode/UNICODE_LICENSE.txt).

## Validation and maintenance

From the repository root:

```bash
python3 conformance/run_legacy_v1_operational_policy.py
python3 conformance/run_legacy_v1_operational_policy.py --json
python3 conformance/build_legacy_v1_operational_policy.py
python3 scripts/audit_unicode_nd_profiles.py
```

The corpus builder imports no AELITIUM runtime module. It reconstructs the
committed files only as a maintenance check; committed expectations remain the
oracle. To independently audit Unicode provenance, download the exact archives
whose URL and SHA-256 are frozen in `unicode/profiles.json`, then run:

```bash
python3 scripts/audit_unicode_nd_profiles.py \
  --ucd-zip 13.0.0=/path/to/UCD-13.0.0.zip \
  --ucd-zip 14.0.0=/path/to/UCD-14.0.0.zip \
  --ucd-zip 15.0.0=/path/to/UCD-15.0.0.zip
```

`--write` is reserved for an explicitly reviewed profile-data revision. The
script is an audit mechanism, not a normative source.

This corpus establishes verifier capability behavior only. It does not
establish provider execution, response causation, semantic truth, capture
completeness, historical occurrence, authorization, identity membership,
legal compliance, model drift, regression, or quality degradation.
