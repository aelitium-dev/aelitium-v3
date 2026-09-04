# Cross-Language Canonicalization Corpus

**Status:** IMPLEMENTATION-ALIGNED

This corpus freezes 30 source-byte cases for the existing
`json_sorted_keys_no_whitespace_utf8` identifier. It is a byte-level supplement
to the unchanged 44-case verification, assurance, trust, Freshness, invocation,
comparison, and compatibility corpus.

Each vector contains:

- the exact source bytes as lowercase hexadecimal;
- SHA-256 of those source bytes as a corruption check;
- exact `ACCEPT` or `REJECT`;
- the existing verifier reason;
- exact canonical UTF-8 bytes and their SHA-256 for accepted cases; and
- whether the accepted value is inside the cross-language-safe restricted
  subset or is preserved legacy behavior outside it.

The expected bytes and digests are committed data. The runner does not generate
them with AELITIUM's canonicalizer. The maintenance builder uses explicit byte
recipes, imports no `engine` module, and exists only to detect unintended edits.

Run from the repository root:

```bash
python3 conformance/run_canonicalization.py
python3 conformance/run_canonicalization.py --json
python3 conformance/build_canonicalization_vectors.py --check
```

The vectors intentionally preserve exact `NaN`, `Infinity`, and `-Infinity`
acceptance in otherwise unrestricted metadata because rejecting those spellings
would change v0.4.0 behavior. They do not claim those tokens are standard JSON.

The invalid-Unicode source vectors exercise canonical payload data. A separate
compatibility test preserves v0.4.0 acceptance of an escaped unpaired surrogate
in an unknown, ignored manifest extension; that legacy parser case is outside
the restricted subset because the manifest is not canonicalized.

Integer magnitudes above 640 decimal digits remain `OPEN`: the released Python
path delegates to a configurable CPython conversion guard. No vector invents a
portable result for that range, and passing this corpus is not sufficient to
claim complete equivalence with every v0.4.0 runtime configuration.

This corpus establishes no semantic truth, provider execution, response
causation, capture completeness, historical occurrence, historical
non-modification, authorization, or legal compliance.
