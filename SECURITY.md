# Security Policy

## Supported Versions

Support is stated against **released, tagged versions**. An unreleased
development line is not a supported release.

| Version | State | Supported |
|---------|-------|-----------|
| 0.3.x   | Unreleased development line — no `v0.3.0` tag or release exists | ❌ (not yet released) |
| 0.2.x   | Current released line (latest release: `v0.2.4`) | ✅ |
| < 0.2   | Superseded | ❌ |

### Pending decision at 0.3.0 release

This repository does not define a support-transition or end-of-life policy. When
`v0.3.0` is released, the support status of the 0.2.x line must be decided
explicitly and recorded here. That decision has **not** been made and is not
implied by this table: 0.2.x remains supported until it is superseded by an
explicit decision.

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
