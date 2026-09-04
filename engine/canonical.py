import json
import hashlib
from typing import Any


class CanonicalizationError(ValueError):
    """Input cannot be represented by the current canonical UTF-8 contract."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = f"{reason}: {detail}" if detail else reason
        super().__init__(message)


def validate_unicode_scalars(data: Any) -> None:
    """Reject unpaired UTF-16 surrogate code points in strings and keys.

    Python strings can contain surrogate code points even though strict UTF-8
    cannot encode them. The canonical contract hashes strict UTF-8, so such a
    value can never produce canonical bytes. Containers are traversed without
    changing the broader set of values delegated to ``json.dumps``.
    """

    seen_containers: set[int] = set()
    pending: list[tuple[Any, str]] = [(data, "$")]

    while pending:
        value, path = pending.pop()
        if isinstance(value, str):
            for index, character in enumerate(value):
                code_point = ord(character)
                if 0xD800 <= code_point <= 0xDFFF:
                    raise CanonicalizationError(
                        "INVALID_UNICODE_SCALAR",
                        f"{path}[{index}] is U+{code_point:04X}",
                    )
            continue

        if isinstance(value, dict):
            identity = id(value)
            if identity in seen_containers:
                continue
            seen_containers.add(identity)
            for index, (key, item) in enumerate(value.items()):
                if isinstance(key, str):
                    pending.append((key, f"{path}.<key:{index}>"))
                pending.append((item, f"{path}.<value:{index}>"))
            continue

        if isinstance(value, (list, tuple)):
            identity = id(value)
            if identity in seen_containers:
                continue
            seen_containers.add(identity)
            for index, item in enumerate(value):
                pending.append((item, f"{path}[{index}]"))


def canonical_json(data: Any) -> str:
    """
    Convert Python object to canonical JSON string:
    - Sorted keys
    - No whitespace
    - UTF-8 encoding
    """
    validate_unicode_scalars(data)
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
