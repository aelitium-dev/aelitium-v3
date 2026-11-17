"""Version-aware canonicalization dispatch without changing the v1 primitive."""

from __future__ import annotations

from typing import Any

from .ai_contract import AI_CANONICALIZATION_V1, AI_CANONICALIZATION_V2
from .canonical import canonical_json, sha256_hash
from .canonical_v2 import canonical_json_v2


class UnsupportedCanonicalizationError(ValueError):
    """A caller requested an unregistered canonicalization contract."""


def canonical_json_for_identifier(data: Any, canonicalization: str) -> str:
    """Serialize ``data`` under one exact registered identifier."""

    if canonicalization == AI_CANONICALIZATION_V1:
        return canonical_json(data)
    if canonicalization == AI_CANONICALIZATION_V2:
        return canonical_json_v2(data)
    raise UnsupportedCanonicalizationError(canonicalization)


def canonicalize_and_hash_for_identifier(
    data: Any, canonicalization: str
) -> tuple[str, str]:
    """Serialize and hash under one exact registered identifier."""

    canonical = canonical_json_for_identifier(data, canonicalization)
    return canonical, sha256_hash(canonical)
