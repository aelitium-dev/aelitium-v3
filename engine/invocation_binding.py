"""Versioned invocation-binding primitive (P1.2d1).

This module implements a strict, self-contained representation of a
cryptographic binding between an invocation-identity hash and a response
hash, plus a deterministic hash over that pair.

Scope of this module only:
- strict construction/validation of the aelitium-invocation-binding-v1
  grammar
- canonical hash derivation over an explicit, versioned field set
- deterministic parsing/recomputation of an already-stored binding object

This module does NOT:
- know about ai_canonical.json, ai_manifest.json, or bundle metadata
- know about request_hash, provider, model, or messages
- integrate with any capture adapter
- modify, read, or relate to the existing v1 binding_hash
  (SHA256(canonical_json({"request_hash": ..., "response_hash": ...})))
- compare its inputs against any bundle's actual invocation_identity or
  response_hash fields (engine.ai_verify consults this primitive for
  parsing/recomputation, then performs that bundle-verifier cross-field
  comparison)

What this primitive represents:
    a versioned, self-describing record that an invocation-hash value and a
    response-hash value were bound together under a declared format, plus a
    deterministic hash over that record.

What it does NOT represent:
- proof that either hash matches any value stored in a real bundle
- proof the provider received or executed a request
- provider identity
- response causation
- historical occurrence
- authorization
- freshness
- non-repudiation
- trusted identity

The assurance meaning of this primitive is limited to: the stored binding
fields are internally consistent with the declared versioned binding hash.
Nothing more.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .canonical import canonical_json, sha256_hash

INVOCATION_BINDING_FORMAT = "aelitium-invocation-binding-v1"

_STORED_TOP_LEVEL_KEYS = frozenset(
    {"format", "invocation_hash", "response_hash", "hash_sha256"}
)

_HASH_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class InvocationBindingError(ValueError):
    """Raised when invocation-binding input or stored data is invalid.

    `reason` is a deterministic, stable machine-readable code. `detail` is a
    human-readable, non-normative elaboration and must not be pattern-matched
    by callers.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = f"{reason}: {detail}" if detail else reason
        super().__init__(message)


@dataclass(frozen=True)
class InvocationBinding:
    """An immutable, already-validated invocation-binding record."""

    format: str
    invocation_hash: str
    response_hash: str
    hash_sha256: str

    def to_stored_object(self) -> dict[str, Any]:
        """Return a fresh, mutable dict matching the conceptual stored shape."""

        return {
            "format": self.format,
            "invocation_hash": self.invocation_hash,
            "response_hash": self.response_hash,
            "hash_sha256": self.hash_sha256,
        }


def _validate_hash_field(value: Any, reason: str, field_name: str) -> str:
    if not isinstance(value, str) or not _HASH_HEX_PATTERN.fullmatch(value):
        raise InvocationBindingError(
            reason,
            f"{field_name} must be 64 lowercase hexadecimal characters",
        )
    return value


def _finalize(invocation_hash: str, response_hash: str) -> InvocationBinding:
    hash_material = {
        "format": INVOCATION_BINDING_FORMAT,
        "invocation_hash": invocation_hash,
        "response_hash": response_hash,
    }
    digest = sha256_hash(canonical_json(hash_material))
    return InvocationBinding(
        format=INVOCATION_BINDING_FORMAT,
        invocation_hash=invocation_hash,
        response_hash=response_hash,
        hash_sha256=digest,
    )


def build_invocation_binding(
    *,
    invocation_hash: str,
    response_hash: str,
) -> InvocationBinding:
    """Build and validate an invocation binding from live values.

    Both `invocation_hash` and `response_hash` must be exactly 64 lowercase
    hexadecimal characters. No coercion, trimming, or case normalization is
    performed -- invalid input is rejected outright.
    """

    invocation_hash = _validate_hash_field(
        invocation_hash,
        "INVOCATION_BINDING_BAD_INVOCATION_HASH",
        "invocation_hash",
    )
    response_hash = _validate_hash_field(
        response_hash,
        "INVOCATION_BINDING_BAD_RESPONSE_HASH",
        "response_hash",
    )
    return _finalize(invocation_hash, response_hash)


def parse_invocation_binding(data: Any) -> InvocationBinding:
    """Strictly validate a stored invocation-binding object and recompute
    its hash from the stored invocation_hash/response_hash fields.

    The stored `hash_sha256` is never trusted on its own -- it is always
    recomputed from `format`/`invocation_hash`/`response_hash` and compared
    against the stored value. A mismatch raises
    `INVOCATION_BINDING_HASH_MISMATCH`.
    """

    if not isinstance(data, dict):
        raise InvocationBindingError(
            "INVOCATION_BINDING_BAD_STRUCTURE",
            "invocation binding must be an object",
        )

    keys = set(data.keys())
    if keys != _STORED_TOP_LEVEL_KEYS:
        missing = sorted(_STORED_TOP_LEVEL_KEYS - keys)
        extra = sorted(keys - _STORED_TOP_LEVEL_KEYS)
        raise InvocationBindingError(
            "INVOCATION_BINDING_BAD_STRUCTURE",
            f"missing={missing} extra={extra}",
        )

    if data.get("format") != INVOCATION_BINDING_FORMAT:
        raise InvocationBindingError(
            "INVOCATION_BINDING_BAD_FORMAT",
            f"format must be {INVOCATION_BINDING_FORMAT!r}, "
            f"got {data.get('format')!r}",
        )

    invocation_hash = _validate_hash_field(
        data.get("invocation_hash"),
        "INVOCATION_BINDING_BAD_INVOCATION_HASH",
        "invocation_hash",
    )
    response_hash = _validate_hash_field(
        data.get("response_hash"),
        "INVOCATION_BINDING_BAD_RESPONSE_HASH",
        "response_hash",
    )

    stored_hash = _validate_hash_field(
        data.get("hash_sha256"),
        "INVOCATION_BINDING_BAD_HASH",
        "hash_sha256",
    )

    binding = _finalize(invocation_hash, response_hash)
    if binding.hash_sha256 != stored_hash:
        raise InvocationBindingError(
            "INVOCATION_BINDING_HASH_MISMATCH",
            f"stored={stored_hash[:16]}... recomputed={binding.hash_sha256[:16]}...",
        )
    return binding
