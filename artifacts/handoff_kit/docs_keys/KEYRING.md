# Keyring (Release Signing) - minisign

This file defines the trusted minisign public keys used to verify AELITIUM release artifacts.

## Active key

- key_id: rel-2026-01
- created_at: 2026-01-10
- status: active
- algorithm: Ed25519
- pubkey_path: docs/keys/minisign_pubkey.txt
- fingerprint (-P): RWR5dYT3kDAq1qgwXfTIkbtT+LOZt3KlpNUTYqUABVW6jkqzOMINAGVd

## Key history

| key_id | created_at | status | fingerprint (-P) | notes |
|-------|------------|--------|------------------|------|
| rel-2026-01 | 2026-01-10 | active | RWR5dYT3kDAq1qgwXfTIkbtT+LOZt3KlpNUTYqUABVW6jkqzOMINAGVd | current |

## Key status definitions

- active -> used for current releases
- retired -> no longer used for new releases; still trusted for old releases
- revoked -> compromised or invalid; must not be trusted

## Rotation policy (v1.1)

- Rotation: publish new pubkey, mark old as `retired`, keep verification of old releases.
- Keys may be rotated annually or upon role change.

## Revocation policy

If a release key is compromised:

1. Mark key status as `revoked`.
2. Publish incident notice in release notes.
3. Generate a new release key.
4. Re-sign current release artifacts.
5. Update public key material in repository and release notes.

## Public key distribution

The release public key is published in:

- docs/keys/minisign_pubkey.txt
- GitHub release notes
- Website (optional)

Users must verify they are using the correct public key before validating artifacts.

## Incident handling

- If private key is lost: rotate (retire old, activate new).
- If private key is suspected compromised: revoke immediately.

## Threat model scope

Release signing protects against:

- Artifact substitution
- Malicious mirror tampering
- CDN corruption
- MITM during distribution

It does not protect against:

- Compromised release maintainer machine
- Malicious code signed intentionally
