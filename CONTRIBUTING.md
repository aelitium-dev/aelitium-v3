# Contributing to AELITIUM

Thank you for your interest in contributing.

AELITIUM builds deterministic, verifiable infrastructure for AI outputs and software releases. Contributions should preserve the core guarantees: determinism, offline verification, fail-closed design, and cryptographic auditability.

---

## Development setup

```bash
git clone https://github.com/aelitium-dev/aelitium-v3.git
cd aelitium-v3

python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run the full test suite:

```bash
python3 -m unittest discover -s tests -q
# Ran 76 tests ... OK
```

All tests must pass before submitting a pull request.

---

## Pull request guidelines

- Keep PRs focused and minimal — one concern per PR
- Include tests for any new functionality
- **Do not change existing CLI contracts** (`STATUS=`, `AI_HASH_SHA256=`, exit codes) without prior discussion — downstream pipelines depend on them
- Ensure deterministic behavior: same input must produce the same output on any machine
- Run `python3 -m unittest discover -s tests -q` locally before opening a PR

---

## Commit style

```
<area>: <short description>

<optional body>
```

Examples:
```
product2: add aelitium-ai verify + 10 contract tests
engine: fix canonical hash for non-ASCII output
docs: update 5-minute demo prerequisites
```

Areas: `engine`, `product2`, `docs`, `tests`, `scripts`, `governance`, `legal`, `chore`

---

## Reporting issues

Open a GitHub issue with:

- OS and Python version (`python3 --version`)
- Command executed (full invocation)
- Full stdout/stderr output
- Expected vs actual behavior

Security vulnerabilities: see [SECURITY.md](SECURITY.md) — do not open public issues.

---

## Design principles

All changes must respect:

| Principle | Meaning |
|-----------|---------|
| **Deterministic** | Same input → same output, always, on any machine |
| **Offline-first** | Verification must never require network access |
| **Fail-closed** | Any error returns `rc=2`; no silent failures |
| **Auditable** | Every pack produces a manifest; nothing is implicit |
| **Pipeline-friendly** | All CLI output is parseable (`STATUS=`, exit codes) |

If a proposed change weakens any of these, it will be declined or redesigned.
