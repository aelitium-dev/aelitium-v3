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
- Canonical public docs name all eight assurance dimensions exactly:
  `payload_integrity`, `binding_field_consistency`,
  `invocation_identity_consistency`, `invocation_binding_consistency`,
  `signature_validity`, `trusted_signer_identity`, `freshness`, and
  `authorization`.
- Freshness is `NOT_EVALUATED` without its complete explicit policy pair and is
  evaluated when both inputs are supplied; authorization is always
  `NOT_EVALUATED` in v0.3.0.
- Request identity is scoped to selected v1 fields.
- Signature validity is not presented as trusted signer identity.
- Invocation identity/binding consistency is not presented as provider execution
  or response causation, and technical `VALID` is not presented as a legal
  compliance determination.
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
- release-process tag authority is `release_commit_sha`, with an unsigned
  annotated tag sufficient for v0.3.0
- PyPI Trusted Publishing is preferred and has a human stop/checkpoint if it is
  unavailable
