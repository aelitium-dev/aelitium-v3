# AELITIUM Contract Conformance Corpus

**Status:** IMPLEMENTATION-ALIGNED

This public corpus contains 44 distinct deterministic executable cases for the
machine-readable verification, assurance, and existing `aelitium-compare-v1`
contracts. It is adversarial test material, not evidence that a historical
event occurred and not a certification suite or industry standard.

A separate 30-case byte corpus under [`canonicalization/`](canonicalization/)
closes the documented Unicode, binary64, non-finite-token, duplicate-name,
whitespace, and terminal-LF behavior of the existing canonicalization
identifier. It also marks the host-dependent extreme-integer range as `OPEN`.
Those 30 cases supplement rather than renumber or alter the 44 result-contract
cases.

## Layout

| Category | Cases | Focus |
|---|---:|---|
| `verification` | 5 | valid evidence, payload edits, manifest mismatch, schema failure, self-consistent replacement |
| `assurance` | 4 | distinct state meanings, evaluation precedence, authorization non-evaluation |
| `trust` | 7 | unsigned, mathematical signatures, explicit trust input, invalid and substituted keys |
| `freshness` | 7 | absent, complete, stale, future, malformed, and incomplete policy cases |
| `invocation` | 5 | identity presence/absence/malformed data and binding cross-field checks |
| `comparison` | 12 | all outcomes, every basis family, strict/legacy behavior, and deceptive similarity |
| `compatibility` | 4 | legacy, unsigned, unbound, and explicit-requirement behavior |

Each vector contains concrete artifact references, CLI inputs, exact status and
reason, all eight expected assurance states, comparison basis where applicable,
and non-claim codes that must be present in the result.

Every case has a distinct operation/input tuple, every committed bundle and
trust fixture is referenced, and repeated fixtures across comparison pairs are
intentional. The runner rejects duplicate executable inputs as well as duplicate
case identifiers.

Two requested scenarios cannot be represented honestly by the current
invocation grammar. They are recorded as `RESEARCH_GAP` entries in
`comparison/research_gaps.json`: tool-declaration changes and provider-route
changes. The executable adapter-surface case is deliberately named as such and
must not be broadened into a provider-route claim.

## Run

From the repository root:

```bash
python3 conformance/run.py
python3 conformance/run.py --json
python3 conformance/run_canonicalization.py
python3 conformance/run_canonicalization.py --json
```

The runner uses frozen files and explicit fixed Freshness reference times. It
does not call a provider, read the system clock for a decision, use the network,
or regenerate its inputs. Expected `CHANGED`, `NOT_COMPARABLE`, and
`INVALID_BUNDLE` semantic exits are handled as vector results; a successful
corpus run exits `0` only after checking all 44 cases.

## Deterministic maintenance checks

The committed fixture and vector builders are maintenance aids, not runtime
prerequisites:

```bash
python3 conformance/build_fixtures.py --check
python3 conformance/build_vectors.py --check
python3 conformance/build_canonicalization_vectors.py --check
```

They reconstruct expected bytes in memory and compare them with the committed
files. `--write` is reserved for intentional corpus updates. Consumers and a
future clean-room verifier can read `manifest.json` and the category vector
files without importing AELITIUM Python internals.

## Interpretation boundary

A passing case means the observed result matches this implementation-aligned
contract vector. In particular:

- a self-consistent replacement is expected to verify as internally `VALID`;
- mathematical signature validity remains separate from explicit signing-key
  trust input;
- Freshness remains declared-time recency, not trusted historical time;
- invocation consistency does not establish provider execution or causation;
- `CHANGED` does not establish model drift, regression, quality degradation, or
  provider fault;
- static or corpus coverage does not establish completeness of recorded AI
  interactions or legal compliance.
