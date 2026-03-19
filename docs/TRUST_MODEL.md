# TRUST MODEL — AELITIUM

## Purpose

Define the trust boundaries, assumptions, and adversarial model
for the AELITIUM verification system.

This document constrains interpretation of verification results.

No guarantees exist outside the scope explicitly defined here.

---

## Object of Guarantee

The system guarantees:

- integrity of verified artifacts at byte level
- consistency between input, canonical form, and computed hash
- correctness of signature verification (if applicable)

The system does NOT guarantee:

- identity of the producer
- authority of the signer
- semantic correctness of content
- temporal validity (freshness)
- contextual correctness

---

## Trusted Components

The following are treated as trusted within scope:

- repository code at the specified commit
- Python runtime (within tested configuration)
- canonicalization logic as implemented
- hashing implementation (SHA-256)
- signature verification implementation (Ed25519)

Trusted means:

- assumed to behave as implemented
- not adversarially modified

---

## Untrusted Inputs

The following are always treated as untrusted:

- input requests
- model outputs
- bundles
- receipts
- transferred artifacts between machines
- storage layers
- transport mechanisms

Untrusted data must always be verified before use.

---

## Assumptions

### Cryptographic Assumptions

- SHA-256 is collision-resistant
- SHA-256 is second-preimage resistant
- Ed25519 is EUF-CMA secure
- private keys are not compromised
- public keys are correctly distributed

### Runtime Assumptions

- Python execution is correct
- file system returns consistent byte data
- canonicalization produces deterministic output

### Institutional Assumptions

- key ownership is managed externally
- key distribution is trusted out-of-band
- no guarantee of key revocation handling

---

## Canonicalization Boundary

All guarantees apply **after canonicalization and inclusion in a verifiable bundle (pack step)**.

The system assumes:

- canonicalization is deterministic
- identical inputs produce identical canonical form

The system does NOT guarantee:

- equivalence of different canonical forms
- detection of semantically equivalent inputs
- correctness of canonicalization beyond implementation

---

## Adversary Model

### Adversary Capabilities

An adversary may:

- modify any byte in a bundle
- reorder input structures
- alter encoding or formatting
- replay previously valid artifacts
- recombine artifacts across runs
- inject semantically equivalent representations

### Adversary Limitations

The adversary is assumed NOT to:

- break SHA-256
- forge Ed25519 signatures without the private key

The adversary model does NOT include compromise of the trusted runtime environment.
If this assumption does not hold, guarantees are void.

### Insider Case

If the adversary controls the signing key:

- signature verification alone cannot detect misuse
- identity and authority are NOT guaranteed

---

## Attack Classes Considered

The system is designed to detect:

- byte-level tampering
- hash mismatch
- signature invalidity
- inconsistency between artifacts

The system is NOT designed to detect:

- semantic equivalence attacks
- replay attacks
- context substitution
- identity spoofing
- time-based attacks

---

## Failure Semantics

The system is strictly fail-closed.

It MUST return INVALID if:

- hash mismatch occurs
- signature verification fails
- required data is missing
- parsing fails
- verification is incomplete

Additionally:

- ambiguous state → INVALID
- partial verification → INVALID
- unexpected structure → INVALID

No soft-fail behavior is permitted.

The verifier validates byte-level integrity and hash consistency of the packed artifact.

It does NOT validate full schema correctness of the canonical payload.
Unexpected but well-formed structures may still verify as VALID.

---

## Meaning of VALID

VALID means:

- verification rules accepted the artifact
- computed values match expected values

VALID does NOT mean:

- the artifact is trustworthy in a broader sense
- the producer is legitimate
- the artifact is current or fresh
- the artifact is safe or correct
- the capture process was honest

---

## Replay and Context

The system does NOT provide:

- replay protection
- temporal guarantees
- context binding

A valid artifact may be reused outside its original context without detection.
Mitigation requires external context binding or higher-level protocols.

---

## Reproducibility Scope

The system guarantees reproducibility only under:

- identical inputs
- identical canonicalization
- identical runtime conditions

Not guaranteed as a general property:

- cross-machine equivalence across arbitrary environments
- cross-OS equivalence
- cross-version equivalence

Reproducibility claims apply only to explicitly validated configurations
and documented procedures (see REPRO_CHECKLIST.md and EVIDENCE_LOG.md).

---

## Non-Goals

The system does NOT attempt to provide:

- identity verification
- organizational trust
- key lifecycle management
- semantic equivalence detection
- policy enforcement
- security beyond integrity verification

---

## Boundary of Interpretation

All verification results must be interpreted strictly within this model.

Any claim extending beyond:

- integrity
- consistency
- verification correctness

is out of scope and unsupported.

---

## Final Principle

Verification proves consistency, not truth.

Trust must be established outside this system.
