# Security Policy

## Supported Versions

Support is stated against **released, tagged versions**. Before `v0.3.0` is
released, `0.2.x` remains the current supported line and the `0.3.x` source line
is not a supported release.

| Version | State | Supported |
|---------|-------|-----------|
| 0.3.x   | Unreleased development line — no `v0.3.0` tag or release exists | ❌ (not yet released) |
| 0.2.x   | Current released line (latest release: `v0.2.4`) | ✅ |
| < 0.2   | Superseded | ❌ |

Upon an actual `v0.3.0` release, `0.3.x` becomes the supported line and `0.2.x`
becomes superseded. Merged release documentation, green CI, or a source version
of `0.3.0` does not trigger that transition; the release must exist.

Within the future `0.3.x` released line, patch releases must not deliberately
introduce breaking changes to existing public assurance dimension names,
assurance states, or already-versioned public identifiers/contracts. See
[Release Process](docs/RELEASE_PROCESS.md#pre-10-stability-policy) for the scoped
pre-1.0 compatibility policy.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately to: **secure@aelitium.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Impact assessment if known

We aim to acknowledge within **72 hours** and provide a resolution timeline within **7 days**.

## Scope

This policy covers:
- `engine/` — canonicalization, signing, pack/verify/repro
- `engine/ai_cli.py` — CLI surface
- Cryptographic guarantees (Ed25519 signing, SHA-256 integrity)

Out of scope: demo fixtures, test files, documentation errors.

## Cryptographic primitives

- Signing: Ed25519 via Python `cryptography` library
- Hashing: SHA-256 (stdlib `hashlib`)
- Canonicalization: deterministic JSON (sorted keys, UTF-8, no whitespace)
