# Messaging Guardrails

## Purpose

This document defines how trust-boundary language policy is enforced in this repository.

The normative language policy is defined in:

- `docs/policy/AELITIUM_TRUST_BOUNDARY_SPEC.md`

## Enforcement scope

Guardrail enforcement applies only within the configured scan scope for this repository.

Current scope:
- `README.md`
- documentation files included by the repository guardrail script

## Enforcement behavior

Verification is fail-closed within the configured scan scope.

If a prohibited pattern is detected:
- the guardrail exits non-zero;
- CI fails;
- merge to `main` is blocked by required branch protection checks.

No implicit fallback is allowed.

## Implementation note

This document does not redefine policy terms, exceptions, or guarantees.
Those remain canonical in:

- `docs/policy/AELITIUM_TRUST_BOUNDARY_SPEC.md`
