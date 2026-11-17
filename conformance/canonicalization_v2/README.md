# Portable Canonicalization V2 Corpus

**Status:** IMPLEMENTATION-ALIGNED-UNRELEASED

This separate corpus freezes 114 cases for
`aelitium_jcs_profile_v2`. It does not modify or renumber the existing
44-case result-contract corpus or 30-case
`json_sorted_keys_no_whitespace_utf8` corpus.

The cases cover strict UTF-8 and BOM handling, duplicate names at every depth,
Unicode scalars and noncharacters, normalization identity, JCS UTF-16 name
ordering and escaping, the complete AELITIUM binary64/safe-number profile,
rounding and underflow, the two-form storage envelope, exact governed hash
inputs, recursive manifest validation, raw-byte routing, legacy CPython integer
digit limits, v1 isolation, and v1/v2 comparison refusal.
Six focused routing cases additionally freeze deeply nested arrays/objects
before and after v1/v2 selectors, malformed deep values, and execution under
Python recursion limits 500 and 1000.

Every vector freezes its source bytes as hexadecimal, a source SHA-256
corruption check, exact decision/error category, canonical bytes and SHA-256
where applicable, and routing target where applicable. Expected canonical
bytes are explicit recipes in the maintenance builder; the builder imports no
production module. The runtime runner reads committed expectations and tests
the implementation, including canonical fixed points.

Run from the repository root:

```bash
python3 conformance/run_canonicalization_v2.py
python3 conformance/run_canonicalization_v2.py --json
python3 conformance/build_canonicalization_v2_vectors.py --check
```

The Python serializer dependency exercised by the corpus is pinned as
`rfc8785==0.1.4` (Apache-2.0). Passing this implementation-aligned corpus is
not evidence that an independent verifier exists. No Go, Rust, or other
second-language verifier is implemented here, and no cross-language validation
claim follows from this runner alone.

Canonicalization establishes deterministic representation and hashing only.
It does not establish semantic truth, provider execution, response causation,
capture completeness, historical occurrence, historical non-modification,
authorization, legal compliance, or cross-version semantic equivalence.
