# AELITIUM Trust Boundary Specification

Version: 1.0
Status: normative

## Purpose

This specification defines mandatory trust-boundary language for AELITIUM repositories.

Its purpose is to prevent claims that exceed what AELITIUM can verify or guarantee.

## Core principle

AELITIUM proves integrity within a defined verification scope.
AELITIUM does not prove semantic truth, model intent, exact timing certainty, or identity beyond the configured trust mode.

## Prohibited claims

The following claims are prohibited in public-facing or repository-scoped documentation unless explicitly allowed by an exception:

- "what the model actually said"
- "exactly when"
- "No API key"

## Preferred language

Use the following terms where applicable:

- "recorded response"
- "canonical request scope"
- "between verified captures"

## Exceptions

The phrase "No API key" may appear only in integration-oriented documentation where it describes local developer workflow and not a cryptographic or trust guarantee.

## Repository scope

This repository contains engine documentation and release-facing technical language.
Enforcement applies to README.md and documentation files within the configured scan scope.

## Enforcement semantics

Enforcement is fail-closed within the configured scan scope.

If a prohibited pattern is detected in scope:
- guardrail verification fails;
- CI fails;
- merge to main is blocked by required branch protection checks.

No implicit fallback is allowed.

## Non-guarantees

This specification does not guarantee:
- complete detection of all misleading language;
- semantic correctness of all repository statements;
- immutability of administrative repository settings.
