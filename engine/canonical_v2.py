"""Portable canonicalization under ``aelitium_jcs_profile_v2``.

RFC 8785 supplies the serialization algorithm.  This module supplies the
AELITIUM source and value profile around it: strict UTF-8 JSON, duplicate-name
rejection, the smaller numeric domain, Unicode noncharacter rejection, and
programmatic-input validation.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

from .manifest_dispatch import DispatchScanError, _parse_dispatch_tree


MAX_SAFE_NUMBER = 9_007_199_254_740_991
MIN_SAFE_NUMBER = -MAX_SAFE_NUMBER


class V2CanonicalizationError(ValueError):
    """A source or host value is outside the immutable v2 profile."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = f"{reason}: {detail}" if detail else reason
        super().__init__(message)


def _validate_string(value: str, path: str) -> None:
    for index, character in enumerate(value):
        code_point = ord(character)
        if 0xD800 <= code_point <= 0xDFFF:
            raise V2CanonicalizationError(
                "INVALID_UNICODE_SCALAR",
                f"{path}[{index}] is U+{code_point:04X}",
            )
        if 0xFDD0 <= code_point <= 0xFDEF or (code_point & 0xFFFF) in {
            0xFFFE,
            0xFFFF,
        }:
            raise V2CanonicalizationError(
                "UNICODE_NONCHARACTER",
                f"{path}[{index}] is U+{code_point:04X}",
            )


def validate_v2_value(data: Any) -> None:
    """Require exactly the recursive host-value domain admitted by v2.

    Exact builtin types are intentional.  In particular, tuples, arbitrary
    mappings/sequences, Decimal values, integer/float subclasses, byte arrays,
    and other objects are not silently coerced by the JCS dependency.
    """

    active_containers: set[int] = set()
    work: list[tuple[str, Any, str]] = [("visit", data, "$")]

    while work:
        action, value, path = work.pop()
        if action == "exit":
            active_containers.remove(value)
            continue
        if action == "key":
            if type(value) is not str:
                raise V2CanonicalizationError(
                    "NON_STRING_OBJECT_NAME",
                    f"{path} has type {type(value).__name__}",
                )
            _validate_string(value, path)
            continue

        value_type = type(value)
        if value is None or value_type is bool:
            continue
        if value_type is str:
            _validate_string(value, path)
            continue
        if value_type is int:
            if value < MIN_SAFE_NUMBER or value > MAX_SAFE_NUMBER:
                raise V2CanonicalizationError(
                    "NUMBER_OUT_OF_RANGE",
                    f"{path} is outside [{MIN_SAFE_NUMBER}, {MAX_SAFE_NUMBER}]",
                )
            continue
        if value_type is float:
            if not math.isfinite(value):
                raise V2CanonicalizationError(
                    "NUMBER_NOT_FINITE", f"{path} is not finite"
                )
            if abs(value) > MAX_SAFE_NUMBER:
                raise V2CanonicalizationError(
                    "NUMBER_OUT_OF_RANGE",
                    f"{path} has magnitude greater than {MAX_SAFE_NUMBER}",
                )
            continue
        if value_type not in (list, dict):
            raise V2CanonicalizationError(
                "UNSUPPORTED_VALUE_TYPE",
                f"{path} has type {value_type.__name__}",
            )

        identity = id(value)
        if identity in active_containers:
            raise V2CanonicalizationError(
                "CYCLIC_VALUE", f"{path} contains a container cycle"
            )
        active_containers.add(identity)
        work.append(("exit", identity, ""))
        if value_type is list:
            for index in range(len(value) - 1, -1, -1):
                work.append(("visit", value[index], f"{path}[{index}]"))
        else:
            items = list(value.items())
            for index in range(len(items) - 1, -1, -1):
                key, item = items[index]
                work.append(("visit", item, f"{path}.<value:{index}>"))
                work.append(("key", key, f"{path}.<key:{index}>"))


def _parse_integer_token(token: str) -> int:
    negative = token.startswith("-")
    magnitude = token[1:] if negative else token
    maximum = str(MAX_SAFE_NUMBER)
    if len(magnitude) > len(maximum) or (
        len(magnitude) == len(maximum) and magnitude > maximum
    ):
        raise V2CanonicalizationError(
            "NUMBER_OUT_OF_RANGE", f"integer token {token[:32]!r} is out of range"
        )
    # The bound check occurs before conversion.  At most 16 digits reach int(),
    # so CPython's configurable decimal-digit guard cannot affect v2.
    return int(token)


def _parse_fractional_token(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise V2CanonicalizationError(
            "NUMBER_NOT_FINITE", f"number token {token[:32]!r} overflows binary64"
        )
    if abs(value) > MAX_SAFE_NUMBER:
        raise V2CanonicalizationError(
            "NUMBER_OUT_OF_RANGE", f"number token {token[:32]!r} is out of range"
        )
    return value


def _reject_constant(token: str) -> None:
    raise V2CanonicalizationError(
        "NON_JSON_NUMBER", f"{token} is not an RFC 8259 number"
    )


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise V2CanonicalizationError(
                "DUPLICATE_OBJECT_NAME", f"duplicate name {name!r}"
            )
        result[name] = value
    return result


def _materialize_v2_value(root: Any, source: bytes) -> Any:
    """Build a strict v2 host value from a fresh iterative lexical parse."""

    values: dict[int, Any] = {}
    work: list[tuple[Any, bool]] = [(root, False)]

    while work:
        node, expanded = work.pop()
        if node.kind in {"array", "object"} and not expanded:
            work.append((node, True))
            children = (
                node.items
                if node.kind == "array"
                else tuple(member.value for member in node.members)
            )
            for child in reversed(children):
                work.append((child, False))
            continue

        if node.kind == "null":
            value: Any = None
        elif node.kind == "false":
            value = False
        elif node.kind == "true":
            value = True
        elif node.kind == "string":
            if node.string_view is None:
                raise V2CanonicalizationError(
                    "INVALID_JSON", "string node has no decoded value"
                )
            value = node.string_view
        elif node.kind == "number":
            token = source[node.start : node.end].decode("ascii")
            if any(marker in token for marker in ".eE"):
                value = _parse_fractional_token(token)
            else:
                value = _parse_integer_token(token)
        elif node.kind == "legacy_constant":
            _reject_constant(source[node.start : node.end].decode("ascii"))
            raise AssertionError("unreachable")
        elif node.kind == "array":
            value = [values[id(item)] for item in node.items]
        elif node.kind == "object":
            pairs: list[tuple[str, Any]] = []
            for member in node.members:
                if member.name.string_view is None:
                    raise V2CanonicalizationError(
                        "INVALID_JSON", "object name has no decoded value"
                    )
                pairs.append(
                    (member.name.string_view, values[id(member.value)])
                )
            value = _reject_duplicates(pairs)
        else:
            raise V2CanonicalizationError(
                "INVALID_JSON", f"unexpected lexical node {node.kind!r}"
            )
        values[id(node)] = value

    return values[id(root)]


def parse_json_v2(source: bytes) -> Any:
    """Parse one strict UTF-8 RFC 8259 value under the complete v2 profile."""

    if type(source) is not bytes:
        raise V2CanonicalizationError(
            "SOURCE_NOT_BYTES", f"source has type {type(source).__name__}"
        )
    if source.startswith(b"\xef\xbb\xbf"):
        raise V2CanonicalizationError("LEADING_BOM", "UTF-8 BOM is prohibited")
    try:
        source.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise V2CanonicalizationError("INVALID_UTF8", str(exc)) from exc

    try:
        # This is a new parse from byte zero.  No tree or decoded value from
        # the pre-dispatch selector scan is supplied to the v2 path.
        root = _parse_dispatch_tree(source)
    except DispatchScanError as exc:
        raise V2CanonicalizationError("INVALID_JSON", str(exc)) from exc

    value = _materialize_v2_value(root, source)
    validate_v2_value(value)
    return value


def canonical_json_v2_bytes(data: Any) -> bytes:
    """Serialize a programmatic v2 value to exact RFC 8785 UTF-8 bytes."""

    validate_v2_value(data)
    try:
        # Keep the released v1 import path usable from a source checkout even
        # before the new, mandatory package dependency has been installed.
        # An installed distribution always receives the exact pyproject pin.
        import rfc8785
    except ImportError as exc:
        raise V2CanonicalizationError(
            "JCS_SERIALIZATION_FAILED", "rfc8785 dependency is unavailable"
        ) from exc
    try:
        canonical = rfc8785.dumps(data)
    except rfc8785.CanonicalizationError as exc:
        raise V2CanonicalizationError("JCS_SERIALIZATION_FAILED", str(exc)) from exc
    if canonical.startswith(b"\xef\xbb\xbf") or canonical.endswith(b"\n"):
        raise V2CanonicalizationError(
            "JCS_SERIALIZATION_FAILED", "serializer violated the v2 byte envelope"
        )
    return canonical


def canonical_json_v2(data: Any) -> str:
    """Serialize a programmatic v2 value to the exact JCS Unicode string."""

    return canonical_json_v2_bytes(data).decode("utf-8", errors="strict")


def canonicalize_v2_and_hash(data: Any) -> tuple[str, str]:
    """Return exact JCS text and lowercase SHA-256 over its UTF-8 bytes."""

    canonical_bytes = canonical_json_v2_bytes(data)
    return (
        canonical_bytes.decode("utf-8", errors="strict"),
        hashlib.sha256(canonical_bytes).hexdigest(),
    )
