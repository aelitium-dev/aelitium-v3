# Security Policy

## Supported Versions

Support is stated against **released, tagged versions**. `v0.4.0` is the current
published release, so `0.4.x` is the supported line and `0.3.x` is superseded.

| Version | State | Released support |
|---------|-------|------------------|
| 0.4.x   | Current published line (latest release: `v0.4.0`) | ✅ |
| 0.3.x   | Superseded (latest release: `v0.3.0`) | ❌ |
| 0.2.x   | Superseded (latest release: `v0.2.4`) | ❌ |
| < 0.2   | Superseded | ❌ |

Patch releases within the current supported pre-1.0 line must not deliberately
introduce breaking changes to existing public assurance dimension names,
assurance states, or already-versioned public identifiers/contracts. See
[Release Process](docs/RELEASE_PROCESS.md#pre-10-stability-policy) for the scoped
compatibility policy.

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
