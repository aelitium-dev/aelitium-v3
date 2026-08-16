# AELITIUM — Release Audit Checklist

Purpose: ensure all public-facing surfaces remain aligned with the canonical trust boundary.

---

## 0. Context validation (MUST RUN FIRST)

hostname
pwd
git rev-parse --show-toplevel
git status --short

---

## 1. Canonical overclaim scan

```bash
./scripts/guardrail_public_claims.sh
```

Expected: required conceptual/legacy quarantine markers pass and no affirmative
current-product overclaim is reported. The executable guardrail is the single
phrase-pattern authority; do not duplicate its patterns in this checklist.

---

## 2. Human semantic review

- Current product surfaces describe internal consistency, not historical
  non-modification without an independently trusted anchor.
- Request identity is scoped to selected v1 fields.
- Signature validity is not presented as trusted signer identity.
- Conceptual and legacy documents retain their required quarantine markers.

`aelitium verify --out <dir>` is valid current CLI syntax and is not forbidden by
the public-claims guardrail.

---

## 3. CLI help validation

```bash
env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests/test_ai_cli_help.py
python3 -m engine.ai_cli --help
python3 -m engine.ai_cli verify --help
python3 -m engine.ai_cli verify-bundle --help
```

Review wording only; runtime output and exit-code compatibility are governed by
their existing tests.

---

## 4. Release audit flow

```bash
env PYTHONDONTWRITEBYTECODE=1 bash scripts/audit_release.sh
```

---

## Pass criteria

- quarantine markers present
- public-claims guardrail passes
- human semantic review completed
- CLI help contract passes
- trust boundary preserved
