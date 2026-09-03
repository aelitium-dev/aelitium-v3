# External validation in 10 minutes

This guide is for a first-time AELITIUM v0.4.0 tester on macOS, Linux, or
Windows Subsystem for Linux. You will install the published package, then use a
release checkout only for frozen fixtures. The six exercises need no API key
and make no network calls.

## 1. Install the public release

From a new working directory:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "aelitium==0.4.0"
```

## 2. Confirm the installation

```bash
python -c "import aelitium; print(aelitium.__version__)"
aelitium --help
aelitium compare --help
```

The version command should print `0.4.0`, and both help commands should exit
successfully.

## 3. Obtain only the frozen test material

Keep the virtual environment active:

```bash
git clone --branch v0.4.0 --depth 1 https://github.com/aelitium-dev/aelitium-v3.git
cd aelitium-v3
```

Do not install the checkout. It supplies fixtures and examples only. Every
command below must use the public `aelitium==0.4.0` distribution installed in
the active virtual environment, not repository-local source. From this point
onward, every exercise is offline.

### Exercise 1 — verify a known-valid bundle

```bash
aelitium verify-bundle examples/drift_demo/bundle_a
```

- **Expected:** `STATUS=VALID rc=0`.
- **Meaning:** The frozen bundle is internally consistent under the v0.4.0
  verifier contract, including its canonical payload, recorded hashes, and
  binding fields.
- **Does not prove:** Provider execution, response causation, output truth,
  capture completeness, or historical non-modification without an independent
  trusted anchor.

### Exercise 2 — compare identical evidence

```bash
aelitium compare examples/drift_demo/bundle_a examples/drift_demo/bundle_a
```

- **Expected:** `STATUS=UNCHANGED rc=0` and
  `COMPARISON_BASIS=REQUEST_HASH_V1_FALLBACK`.
- **Meaning:** Under the reported fallback basis, the selected request and
  response hashes match.
- **Does not prove:** That every real-world invocation detail or model behavior
  was unchanged.

### Exercise 3 — compare frozen changed evidence

```bash
aelitium compare examples/drift_demo/bundle_a examples/drift_demo/bundle_b
```

- **Expected:** `STATUS=CHANGED rc=2`,
  `COMPARISON_BASIS=REQUEST_HASH_V1_FALLBACK`, and
  `COMPARISON_REASON=RESPONSE_HASH_DIFFERENT`. Exit code 2 is the expected
  semantic result.
- **Meaning:** Under the reported basis, the selected request hashes match and
  the selected response hashes differ.
- **Does not prove:** Model drift as a cause, provider execution, causation, or
  which real-world event produced the difference.

### Exercise 4 — require invocation evidence from a legacy bundle

```bash
aelitium compare examples/drift_demo/bundle_a examples/drift_demo/bundle_a --require-invocation-evidence
```

- **Expected:** `STATUS=NOT_COMPARABLE rc=1`,
  `COMPARISON_MODE=STRICT_INVOCATION`, `COMPARISON_BASIS=NONE`, and
  `REQUIRED_COMPARISON_BASIS=INVOCATION_IDENTITY_V1`. Exit code 1 is expected.
- **Meaning:** Strict mode refuses the request-hash fallback because these
  frozen bundles predate invocation identity and invocation binding evidence.
- **Does not prove:** That either bundle is invalid or that the selected
  responses changed; no comparison conclusion is made.

### Exercise 5 — tamper with a temporary copy

```bash
(
  set -euo pipefail
  TAMPER_ROOT="$(mktemp -d)"
  trap 'rm -rf -- "$TAMPER_ROOT"' EXIT
  cp -R examples/drift_demo/bundle_a "$TAMPER_ROOT/tampered"
  python - "$TAMPER_ROOT/tampered/ai_canonical.json" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
original = path.read_text(encoding="utf-8")
changed = original.replace('"output":"The sky', '"output":"Tampered: the sky', 1)
if changed == original:
    raise SystemExit("expected fixture text not found")
path.write_text(changed, encoding="utf-8")
PY
  TAMPER_RC=0
  aelitium verify-bundle "$TAMPER_ROOT/tampered" || TAMPER_RC=$?
  test "$TAMPER_RC" -eq 2
)
```

- **Expected:** `STATUS=INVALID rc=2 reason=HASH_MISMATCH`. The subshell removes
  its temporary directory on exit.
- **Meaning:** Changing the copied canonical payload without updating its
  recorded manifest hash is detected.
- **Does not prove:** Who changed the copy, when it changed, or that a fully
  self-consistent replacement would be distinguishable without an independent
  trusted anchor.

### Exercise 6 — use valid invocation evidence

```bash
aelitium compare tests/fixtures/compare/v030_invocation_a tests/fixtures/compare/v030_invocation_b
```

- **Expected:** `STATUS=CHANGED rc=2`,
  `COMPARISON_CONTRACT=aelitium-compare-v1`, and
  `COMPARISON_BASIS=INVOCATION_IDENTITY_V1`. Both invocation identity and
  invocation binding consistency lines should be `VALID`. Exit code 2 is
  expected because the selected response hashes differ.
- **Meaning:** Both bundles contain usable, internally consistent invocation
  evidence, so the v0.4.0 comparison contract selects its invocation-identity
  basis.
- **Does not prove:** Full invocation completeness, provider execution,
  response causation, or output truth.

## Optional one-command run

The repository includes a deterministic runner for the same safe offline flow:

```bash
bash examples/external_validation/run.sh
```

The runner requires `python` and `aelitium` from the same active environment,
requires `aelitium` on `PATH`, reads the active distribution version with
`importlib.metadata`, and deliberately refuses any version other than `0.4.0`.
It has no repository-local CLI fallback. Before the exercises, it prints the
resolved executable and installed package version. It exits successfully only
when every expected status, basis, reason, and semantic return code is observed.

When reporting a problem, include the OS, Python version, AELITIUM version,
command that failed, and exact output.

## Feedback questions

1. Was installation obvious?
2. Did you understand what `STATUS=VALID` means?
3. Did you understand why compare reports its basis?
4. What was the first confusing step or term?
5. Would this evidence be useful in a real workflow you operate? If yes, where?
