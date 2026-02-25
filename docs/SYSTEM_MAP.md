# AELITIUM v3 — SYSTEM_MAP (Threat + Trust Model)

## Scope
This document defines: trust boundaries, deterministic guarantees, verification semantics, and failure behavior.

## Machines / Roles
- Machine A (dev): untrusted build environment. May be compromised.
- Machine B (authority): release authority. Must be hardened. Holds signing capability / governance execution.

## Trust Modes
- Strict mode: verification keys resolved from trusted channel / explicit config. No network fallback.
- Embedded mode: verification keys embedded in bundle/manifest. Integrity only, not identity.

## Trust Boundaries
- Inputs (JSON): untrusted.
- Repo working tree on A: untrusted.
- Repo state on B: trusted only after `gate_release.sh` passes with clean tree + reproducibility + determinism checks.
- Tags: treated as claims. Valid only if created by authority gate and point to HEAD.

## Determinism Guarantees (What is guaranteed)
- Canonicalization: deterministic serialization for any signed/hashed artifact.
- `pack` produces identical bundle bytes given identical input + repo commit + toolchain.
- `bundle_determinism_check.sh` enforces byte-identical bundles across consecutive runs.
- `verify` is fail-closed: any mismatch -> NO_GO.

## Non-Guarantees (Explicit)
- Identity of embedded keys (embedded mode) is not an identity guarantee.
- Confidentiality of inputs is not guaranteed.
- Compromise of Machine B breaks authority; detection depends on external controls.

## Attack Surface / Threats
- Supply-chain changes between A and B.
- Dirty working tree / uncommitted changes.
- Tag re-pointing / tag collision.
- Non-deterministic packaging (timestamps, file order, locale).
- Key substitution (strict vs embedded).
- Repo history rewriting.

## Controls (Enforced)
- `gate_release.sh`: clean tree required; governed pipeline; determinism check mandatory; tag only after success; tag integrity check.
- Evidence artifacts written to release_output/ and hashed.
- Fail-closed: any non-zero RC => NO_GO.

## Evidence / Audit
- release_output/manifest.json
- release_output/evidence_pack.json
- release_output/verification_keys.json
- release_output/release_metadata.json
- Git tag + commit hash

