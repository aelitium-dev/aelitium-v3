"""Local trusted-signer store primitive (P1.1a).

This module implements strict parsing of an externally supplied local trust
root (a JSON "trust store" file) and canonical Ed25519 public-key fingerprint
derivation.

Scope of this module only:
- strict parsing of the aelitium-trust-v1 trust-store format
- canonical public-key fingerprint derivation
- deterministic, fingerprint-keyed lookup data

This module does NOT establish trusted signer identity by itself, and does
not evaluate any evidence bundle. It provides the data structures a future
verification step can consult. It does not prove human identity,
organizational role, authorization, freshness, or revocation status, and it
carries no notion of key revocation, expiry, or scope.

Trust is always derived from the raw public-key bytes (via
`fingerprint_public_key`), never from a fingerprint string or a label read
out of the trust-store file.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TRUST_STORE_FORMAT = "aelitium-trust-v1"
SUPPORTED_ALGORITHM = "ed25519"
ED25519_PUBLIC_KEY_LENGTH = 32

_TRUST_STORE_TOP_LEVEL_KEYS = frozenset({"trust_store_format", "signers"})
_SIGNER_ENTRY_KEYS = frozenset({"algorithm", "public_key_b64", "label"})


class TrustStoreError(ValueError):
    """Raised when a trust-store file or its contents are invalid.

    `reason` is a deterministic, stable machine-readable code. `detail` is a
    human-readable, non-normative elaboration and must not be pattern-matched
    by callers.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = f"{reason}: {detail}" if detail else reason
        super().__init__(message)


def _decode_b64_strict(value: str, reason: str, detail: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except Exception as exc:
        raise TrustStoreError(reason, f"{detail} ({type(exc).__name__})") from exc


def fingerprint_public_key(public_key_bytes: bytes) -> str:
    """Return the canonical display fingerprint for raw Ed25519 public-key bytes.

    Format: ``ed25519:sha256:<64 lowercase hex>``. The identity anchor is the
    SHA-256 digest of the raw key bytes; the ``ed25519:sha256:`` prefix is
    display metadata only, not part of the digest input.
    """

    if not isinstance(public_key_bytes, (bytes, bytearray)):
        raise TrustStoreError(
            "TRUST_STORE_BAD_PUBLIC_KEY",
            "public_key_bytes must be bytes",
        )
    if len(public_key_bytes) != ED25519_PUBLIC_KEY_LENGTH:
        raise TrustStoreError(
            "TRUST_STORE_BAD_PUBLIC_KEY",
            f"expected {ED25519_PUBLIC_KEY_LENGTH} bytes, got {len(public_key_bytes)}",
        )
    digest = hashlib.sha256(bytes(public_key_bytes)).hexdigest()
    return f"ed25519:sha256:{digest}"


@dataclass(frozen=True)
class TrustedSigner:
    """A single trusted-signer record.

    `label` is an optional, non-authoritative display string. It is never
    consulted for trust decisions; only `fingerprint` (derived from
    `public_key_bytes`) is.
    """

    algorithm: str
    public_key_bytes: bytes
    fingerprint: str
    label: str | None = None


@dataclass(frozen=True)
class TrustStore:
    """A parsed, validated aelitium-trust-v1 trust store.

    Lookup is by cryptographic key fingerprint only. Record order is
    preserved for display/audit purposes but never affects lookup results.
    """

    format: str
    signers: tuple[TrustedSigner, ...]

    def find_by_fingerprint(self, fingerprint: str) -> TrustedSigner | None:
        for signer in self.signers:
            if signer.fingerprint == fingerprint:
                return signer
        return None

    def __contains__(self, fingerprint: str) -> bool:
        return self.find_by_fingerprint(fingerprint) is not None

    def fingerprints(self) -> frozenset[str]:
        return frozenset(signer.fingerprint for signer in self.signers)


def _parse_signer_entry(entry: Any, index: int) -> TrustedSigner:
    if not isinstance(entry, dict):
        raise TrustStoreError(
            "TRUST_STORE_BAD_SIGNER",
            f"signers[{index}] must be an object",
        )

    unknown = set(entry.keys()) - _SIGNER_ENTRY_KEYS
    if unknown:
        raise TrustStoreError(
            "TRUST_STORE_BAD_SIGNER",
            f"signers[{index}] has unknown field(s): {sorted(unknown)}",
        )

    algorithm = entry.get("algorithm")
    if algorithm != SUPPORTED_ALGORITHM:
        raise TrustStoreError(
            "TRUST_STORE_BAD_SIGNER",
            f"signers[{index}].algorithm must be {SUPPORTED_ALGORITHM!r}, got {algorithm!r}",
        )

    public_key_b64 = entry.get("public_key_b64")
    if not isinstance(public_key_b64, str) or not public_key_b64:
        raise TrustStoreError(
            "TRUST_STORE_BAD_SIGNER",
            f"signers[{index}].public_key_b64 is required and must be a non-empty string",
        )

    public_key_bytes = _decode_b64_strict(
        public_key_b64,
        "TRUST_STORE_BAD_PUBLIC_KEY",
        f"signers[{index}].public_key_b64 is not valid base64",
    )
    if len(public_key_bytes) != ED25519_PUBLIC_KEY_LENGTH:
        raise TrustStoreError(
            "TRUST_STORE_BAD_PUBLIC_KEY",
            f"signers[{index}] decoded key is {len(public_key_bytes)} bytes, "
            f"expected {ED25519_PUBLIC_KEY_LENGTH}",
        )

    label: str | None = None
    if "label" in entry:
        raw_label = entry["label"]
        if not isinstance(raw_label, str) or not raw_label:
            raise TrustStoreError(
                "TRUST_STORE_BAD_SIGNER",
                f"signers[{index}].label must be a non-empty string if present",
            )
        label = raw_label

    fingerprint = fingerprint_public_key(public_key_bytes)

    return TrustedSigner(
        algorithm=algorithm,
        public_key_bytes=public_key_bytes,
        fingerprint=fingerprint,
        label=label,
    )


def parse_trust_store(data: Any) -> TrustStore:
    """Parse and strictly validate an already-decoded trust-store object.

    Raises `TrustStoreError` on any structural or content violation.
    """

    if not isinstance(data, dict):
        raise TrustStoreError(
            "TRUST_STORE_BAD_STRUCTURE",
            "trust store must be a JSON object",
        )

    keys = set(data.keys())
    if keys != _TRUST_STORE_TOP_LEVEL_KEYS:
        missing = sorted(_TRUST_STORE_TOP_LEVEL_KEYS - keys)
        extra = sorted(keys - _TRUST_STORE_TOP_LEVEL_KEYS)
        raise TrustStoreError(
            "TRUST_STORE_BAD_STRUCTURE",
            f"missing={missing} extra={extra}",
        )

    if data.get("trust_store_format") != TRUST_STORE_FORMAT:
        raise TrustStoreError(
            "TRUST_STORE_BAD_FORMAT",
            f"trust_store_format must be {TRUST_STORE_FORMAT!r}, "
            f"got {data.get('trust_store_format')!r}",
        )

    raw_signers = data.get("signers")
    if not isinstance(raw_signers, list):
        raise TrustStoreError(
            "TRUST_STORE_BAD_STRUCTURE",
            "signers must be a list",
        )

    signers: list[TrustedSigner] = []
    seen_fingerprints: dict[str, int] = {}
    for index, raw_entry in enumerate(raw_signers):
        signer = _parse_signer_entry(raw_entry, index)
        if signer.fingerprint in seen_fingerprints:
            raise TrustStoreError(
                "TRUST_STORE_DUPLICATE_KEY",
                f"signers[{index}] duplicates signers[{seen_fingerprints[signer.fingerprint]}] "
                f"(fingerprint={signer.fingerprint})",
            )
        seen_fingerprints[signer.fingerprint] = index
        signers.append(signer)

    return TrustStore(format=data["trust_store_format"], signers=tuple(signers))


def load_trust_store_text(text: str) -> TrustStore:
    """Parse a trust store from raw JSON text."""

    try:
        data = json.loads(text)
    except Exception as exc:
        raise TrustStoreError("TRUST_STORE_NOT_JSON", type(exc).__name__) from exc
    return parse_trust_store(data)


def load_trust_store(path: str | Path) -> TrustStore:
    """Load and strictly validate a trust store from a local file path."""

    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise TrustStoreError(
            "TRUST_STORE_IO_ERROR",
            f"could not read {path!s} as UTF-8 text ({type(exc).__name__})",
        ) from exc

    return load_trust_store_text(text)
