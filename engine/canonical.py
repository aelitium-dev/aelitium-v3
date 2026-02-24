import json
import hashlib
from typing import Any


def canonical_json(data: Any) -> str:
    """
    Convert Python object to canonical JSON string:
    - Sorted keys
    - No whitespace
    - UTF-8 encoding
    """
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_hash(data: str) -> str:
    """
    Compute SHA256 hash of canonical string.
    """
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def canonicalize_and_hash(data: Any) -> tuple[str, str]:
    """
    Return canonical JSON string and its SHA256 hash.
    """
    canonical = canonical_json(data)
    digest = sha256_hash(canonical)
    return canonical, digest
