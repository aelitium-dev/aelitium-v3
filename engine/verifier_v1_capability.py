"""Capability-qualified legacy-v1 source and timestamp execution.

This module is intentionally separate from capability declaration preparation
and from the operation-wide JSON resource scanner.  It implements the selected
legacy parser profile over immutable source bytes without consulting CPython's
ambient decimal conversion guard or its Unicode character database.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from json.decoder import scanstring
from typing import Any, Final, NoReturn

from .ai_canonical import AICanonicalError, validate_ai_output
from .canonical import CanonicalizationError, validate_unicode_scalars
from .verifier_capabilities import (
    ASCII_TIMESTAMP_DIGIT_PROFILE,
    BOUNDED,
    EffectiveVerifierRoute,
    V1_FROZEN_LEGACY_COMPATIBILITY,
    V1_NAMED_RUNTIME_COMPATIBILITY,
    V1_RESTRICTED_PORTABLE,
)
from .verifier_snapshot import (
    InputRef,
    InputRole,
    LimitFact,
    LimitName,
    LimitUnit,
    OperationalCode,
    OperationalInputFailure,
    OperationalPhase,
)


_JSON_WHITESPACE: Final = frozenset(" \t\n\r")
_MANIFEST_GOVERNED_MEMBERS: Final = frozenset(
    {
        "schema",
        "ts_utc",
        "input_schema",
        "canonicalization",
        "ai_hash_sha256",
        "binding_hash",
    }
)
_KEYRING_ROOT_MEMBERS: Final = frozenset(
    {"keyring_format", "keys", "signatures"}
)
_KEY_ENTRY_MEMBERS: Final = frozenset({"key_id", "public_key_b64"})
_SIGNATURE_ENTRY_MEMBERS: Final = frozenset(
    {"key_id", "algorithm", "scope", "sig_b64"}
)
_TIMESTAMP_DIGIT_POSITIONS: Final = (
    0,
    1,
    2,
    3,
    5,
    6,
    8,
    9,
    11,
    12,
    14,
    15,
    17,
    18,
)
_TIMESTAMP_SEPARATORS: Final = {
    4: "-",
    7: "-",
    10: "T",
    13: ":",
    16: ":",
    19: "Z",
}
_DECIMAL_CHUNK_DIGITS: Final = 9
_DECIMAL_CHUNK_BASE: Final = 1_000_000_000


class LegacyJsonSourceError(ValueError):
    """The source cannot be converted under the selected named v1 profile."""


class LegacyIntegerConversionError(LegacyJsonSourceError):
    """A named bounded profile reproduced its legacy conversion refusal."""


@dataclass(frozen=True, slots=True)
class _ValueContext:
    path: tuple[str | int, ...]
    opaque_extension: bool = False


@dataclass(slots=True)
class _ObjectFrame:
    context: _ValueContext
    members: list[tuple[str, Any]] = field(default_factory=list)
    state: str = "first_or_end"
    pending_name: str | None = None


@dataclass(slots=True)
class _ArrayFrame:
    context: _ValueContext
    items: list[Any] = field(default_factory=list)
    state: str = "first_or_end"


def _has_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _portable_integer_refusal(
    *,
    phase: OperationalPhase,
    input_ref: InputRef,
    maximum: int,
    observed: int,
) -> NoReturn:
    raise OperationalInputFailure(
        OperationalCode.INPUT_OUTSIDE_DECLARED_CAPABILITY,
        phase,
        input_ref,
        LimitFact(
            LimitName.INTEGER_DECIMAL_DIGITS,
            LimitUnit.DIGITS,
            maximum,
            observed,
        ),
        None,
    )


def _categorical_refusal(
    *, phase: OperationalPhase, input_ref: InputRef
) -> NoReturn:
    raise OperationalInputFailure(
        OperationalCode.INPUT_OUTSIDE_DECLARED_CAPABILITY,
        phase,
        input_ref,
        None,
        None,
    )


def _integer_from_decimal_digits(digits: str, *, negative: bool) -> int:
    """Convert arbitrary decimal digits without a host-wide digit setting."""

    first_width = len(digits) % _DECIMAL_CHUNK_DIGITS
    if first_width == 0:
        first_width = _DECIMAL_CHUNK_DIGITS
    value = int(digits[:first_width])
    for start in range(first_width, len(digits), _DECIMAL_CHUNK_DIGITS):
        value = value * _DECIMAL_CHUNK_BASE + int(
            digits[start : start + _DECIMAL_CHUNK_DIGITS]
        )
    return -value if negative else value


def integer_to_decimal(value: int) -> str:
    """Render an arbitrary Python integer without its ambient digit guard."""

    if type(value) is not int:
        raise TypeError("value must be an integer")
    if value == 0:
        return "0"
    negative = value < 0
    magnitude = -value if negative else value
    chunks: list[int] = []
    while magnitude:
        magnitude, remainder = divmod(magnitude, _DECIMAL_CHUNK_BASE)
        chunks.append(remainder)
    rendered = str(chunks.pop())
    while chunks:
        rendered += f"{chunks.pop():09d}"
    return "-" + rendered if negative else rendered


def _is_key_entry_path(path: tuple[str | int, ...]) -> bool:
    return len(path) == 2 and path[0] == "keys" and type(path[1]) is int


def _is_signature_entry_path(path: tuple[str | int, ...]) -> bool:
    return (
        len(path) == 2
        and path[0] == "signatures"
        and type(path[1]) is int
    )


def _child_context(
    role: InputRole,
    parent: _ValueContext,
    component: str | int,
) -> _ValueContext:
    path = parent.path + (component,)
    opaque = parent.opaque_extension
    if not opaque and type(component) is str:
        if role is InputRole.AI_MANIFEST_JSON and not parent.path:
            opaque = component not in _MANIFEST_GOVERNED_MEMBERS
        elif role is InputRole.VERIFICATION_KEYS_JSON:
            if not parent.path:
                opaque = component not in _KEYRING_ROOT_MEMBERS
            elif _is_key_entry_path(parent.path):
                opaque = component not in _KEY_ENTRY_MEMBERS
            elif _is_signature_entry_path(parent.path):
                opaque = component not in _SIGNATURE_ENTRY_MEMBERS
    return _ValueContext(path, opaque)


def _surrogate_is_legacy_permitted(
    role: InputRole, context: _ValueContext
) -> bool:
    if context.opaque_extension:
        return True
    path = context.path
    if role is InputRole.VERIFICATION_KEYS_JSON:
        return bool(path) and path[-1] == "key_id" and (
            _is_key_entry_path(path[:-1])
            or _is_signature_entry_path(path[:-1])
        )
    if role is InputRole.TRUST_STORE:
        return (
            len(path) == 3
            and path[0] == "signers"
            and type(path[1]) is int
            and path[2] == "label"
        )
    return False


class _LegacyParser:
    def __init__(
        self,
        source: bytes,
        *,
        route: EffectiveVerifierRoute,
        role: InputRole,
        phase: OperationalPhase,
        input_ref: InputRef,
        validate_manifest_timestamp: bool,
    ) -> None:
        if type(source) is not bytes:
            raise TypeError("source must be bytes")
        try:
            self.text = source.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise LegacyJsonSourceError("invalid UTF-8") from exc
        self.length = len(self.text)
        self.position = 0
        self.route = route
        self.role = role
        self.phase = phase
        self.input_ref = input_ref
        self.validate_manifest_timestamp = validate_manifest_timestamp

    @property
    def restricted(self) -> bool:
        return self.route.capability == V1_RESTRICTED_PORTABLE

    def _opaque_surrogate_is_outside_restricted_domain(
        self, context: _ValueContext
    ) -> bool:
        # This predicate applies equally to member names and string values.
        # Optional timestamp semantics cannot turn a legacy-permitted opaque
        # subtree into a wider restricted source domain.
        return _surrogate_is_legacy_permitted(self.role, context) or (
            self.role is InputRole.AI_MANIFEST_JSON
            and not self.validate_manifest_timestamp
            and context.path[:1] == ("ts_utc",)
        )

    def parse(self) -> Any:
        self._skip_whitespace()
        stack: list[_ObjectFrame | _ArrayFrame] = []
        completed = self._start_value(stack, _ValueContext(()))

        while True:
            if completed is not _NO_VALUE:
                if not stack:
                    root = completed
                    break
                parent = stack[-1]
                if isinstance(parent, _ObjectFrame):
                    if parent.state != "value" or parent.pending_name is None:
                        raise LegacyJsonSourceError("invalid object parser state")
                    parent.members.append((parent.pending_name, completed))
                    parent.pending_name = None
                    parent.state = "comma_or_end"
                else:
                    if parent.state != "value":
                        raise LegacyJsonSourceError("invalid array parser state")
                    parent.items.append(completed)
                    parent.state = "comma_or_end"
                completed = _NO_VALUE
                continue

            if not stack:
                raise LegacyJsonSourceError("invalid parser state")
            frame = stack[-1]
            self._skip_whitespace()

            if isinstance(frame, _ObjectFrame):
                if frame.state == "first_or_end":
                    if self._consume_if("}"):
                        stack.pop()
                        completed = self._collapse_object(frame.members)
                    else:
                        frame.state = "name"
                    continue
                if frame.state == "name":
                    if self.position >= self.length or self.text[self.position] != '"':
                        raise LegacyJsonSourceError("object name must be a string")
                    name = self._string()
                    name_context = _child_context(
                        self.role, frame.context, name
                    )
                    if (
                        self.restricted
                        and _has_surrogate(name)
                        and self._opaque_surrogate_is_outside_restricted_domain(
                            name_context
                        )
                    ):
                        _categorical_refusal(
                            phase=self.phase, input_ref=self.input_ref
                        )
                    frame.pending_name = name
                    frame.state = "colon"
                    continue
                if frame.state == "colon":
                    if not self._consume_if(":"):
                        raise LegacyJsonSourceError("object name separator expected")
                    frame.state = "value"
                    continue
                if frame.state == "value":
                    assert frame.pending_name is not None
                    context = _child_context(
                        self.role, frame.context, frame.pending_name
                    )
                    completed = self._start_value(stack, context)
                    continue
                if frame.state != "comma_or_end":
                    raise LegacyJsonSourceError("invalid object parser state")
                if self._consume_if("}"):
                    stack.pop()
                    completed = self._collapse_object(frame.members)
                elif self._consume_if(","):
                    frame.state = "name"
                else:
                    raise LegacyJsonSourceError("object delimiter expected")
                continue

            if frame.state == "first_or_end":
                if self._consume_if("]"):
                    stack.pop()
                    completed = frame.items
                else:
                    frame.state = "value"
                continue
            if frame.state == "value":
                context = _child_context(
                    self.role, frame.context, len(frame.items)
                )
                completed = self._start_value(stack, context)
                continue
            if frame.state != "comma_or_end":
                raise LegacyJsonSourceError("invalid array parser state")
            if self._consume_if("]"):
                stack.pop()
                completed = frame.items
            elif self._consume_if(","):
                frame.state = "value"
            else:
                raise LegacyJsonSourceError("array delimiter expected")

        self._skip_whitespace()
        if self.position != self.length:
            raise LegacyJsonSourceError("trailing data")
        return root

    def _skip_whitespace(self) -> None:
        while (
            self.position < self.length
            and self.text[self.position] in _JSON_WHITESPACE
        ):
            self.position += 1

    def _consume_if(self, expected: str) -> bool:
        if self.position < self.length and self.text[self.position] == expected:
            self.position += 1
            return True
        return False

    @staticmethod
    def _collapse_object(members: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, value in members:
            result[name] = value
        return result

    def _start_value(
        self,
        stack: list[_ObjectFrame | _ArrayFrame],
        context: _ValueContext,
    ) -> Any:
        self._skip_whitespace()
        if self.position >= self.length:
            raise LegacyJsonSourceError("value expected")
        character = self.text[self.position]
        if character == '"':
            value = self._string()
            # Disabling the optional timestamp check leaves a legacy-accepted
            # opaque ts_utc value in the source domain. It does not extend the
            # restricted capability to that value or any nested member of it.
            if (
                self.restricted
                and _has_surrogate(value)
                and self._opaque_surrogate_is_outside_restricted_domain(context)
            ):
                _categorical_refusal(phase=self.phase, input_ref=self.input_ref)
            return value
        if character == "{":
            self.position += 1
            stack.append(_ObjectFrame(context))
            return _NO_VALUE
        if character == "[":
            self.position += 1
            stack.append(_ArrayFrame(context))
            return _NO_VALUE
        for literal, value in (
            ("false", False),
            ("null", None),
            ("true", True),
            ("NaN", math.nan),
            ("Infinity", math.inf),
            ("-Infinity", -math.inf),
        ):
            if self.text.startswith(literal, self.position):
                self.position += len(literal)
                if self.restricted and isinstance(value, float):
                    _categorical_refusal(
                        phase=self.phase, input_ref=self.input_ref
                    )
                return value
        if character == "-" or "0" <= character <= "9":
            return self._number(context)
        raise LegacyJsonSourceError("unrecognized value token")

    def _string(self) -> str:
        try:
            value, end = scanstring(self.text, self.position + 1, True)
        except (UnicodeDecodeError, ValueError) as exc:
            raise LegacyJsonSourceError("invalid string") from exc
        self.position = end
        return value

    def _number(self, context: _ValueContext) -> int | float:
        start = self.position
        negative = self._consume_if("-")
        if self.position >= self.length:
            raise LegacyJsonSourceError("truncated number")

        magnitude_start = self.position
        if self.text[self.position] == "0":
            self.position += 1
        elif "1" <= self.text[self.position] <= "9":
            self.position += 1
            while (
                self.position < self.length
                and "0" <= self.text[self.position] <= "9"
            ):
                self.position += 1
        else:
            raise LegacyJsonSourceError("invalid integer component")
        magnitude_end = self.position

        integer_form = True
        if self.position < self.length and self.text[self.position] == ".":
            integer_form = False
            self.position += 1
            fraction_start = self.position
            while (
                self.position < self.length
                and "0" <= self.text[self.position] <= "9"
            ):
                self.position += 1
            if self.position == fraction_start:
                raise LegacyJsonSourceError("fraction requires a digit")

        if self.position < self.length and self.text[self.position] in "eE":
            integer_form = False
            self.position += 1
            if self.position < self.length and self.text[self.position] in "+-":
                self.position += 1
            exponent_start = self.position
            while (
                self.position < self.length
                and "0" <= self.text[self.position] <= "9"
            ):
                self.position += 1
            if self.position == exponent_start:
                raise LegacyJsonSourceError("exponent requires a digit")

        token = self.text[start : self.position]
        if not integer_form:
            value = float(token)
            if self.restricted and not math.isfinite(value):
                _categorical_refusal(phase=self.phase, input_ref=self.input_ref)
            return value

        digits = self.text[magnitude_start:magnitude_end]
        maximum = self._integer_maximum()
        if maximum is not None and len(digits) > maximum:
            if self.route.capability in {
                V1_RESTRICTED_PORTABLE,
                V1_FROZEN_LEGACY_COMPATIBILITY,
            }:
                _portable_integer_refusal(
                    phase=self.phase,
                    input_ref=self.input_ref,
                    maximum=maximum,
                    observed=len(digits),
                )
            raise LegacyIntegerConversionError(
                f"integer magnitude exceeds named bound {maximum}"
            )
        return _integer_from_decimal_digits(digits, negative=negative)

    def _integer_maximum(self) -> int | None:
        declaration = self.route.declaration
        if self.route.capability in {
            V1_RESTRICTED_PORTABLE,
            V1_FROZEN_LEGACY_COMPATIBILITY,
        }:
            return 640
        if self.route.capability != V1_NAMED_RUNTIME_COMPATIBILITY:
            raise AssertionError("legacy parser received a non-v1 route")
        conversion = declaration.integer_conversion
        if conversion is None:
            raise AssertionError("prepared named route has no integer profile")
        if conversion.mode == BOUNDED:
            assert conversion.maximum_decimal_digits is not None
            return conversion.maximum_decimal_digits
        return None


_NO_VALUE = object()


def parse_v1_json_source(
    source: bytes,
    *,
    route: EffectiveVerifierRoute,
    role: InputRole,
    phase: OperationalPhase,
    input_ref: InputRef,
    validate_manifest_timestamp: bool = True,
) -> Any:
    """Parse one reached immutable legacy source under an effective route."""

    if route.capability not in {
        V1_RESTRICTED_PORTABLE,
        V1_FROZEN_LEGACY_COMPATIBILITY,
        V1_NAMED_RUNTIME_COMPATIBILITY,
    }:
        raise TypeError("route must select an executable v1 capability")
    return _LegacyParser(
        source,
        route=route,
        role=role,
        phase=phase,
        input_ref=input_ref,
        validate_manifest_timestamp=validate_manifest_timestamp,
    ).parse()


def _scalar_json(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if type(value) is int:
        return integer_to_decimal(value)
    if isinstance(value, (str, float)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


@dataclass(slots=True)
class _SerializationFrame:
    values: list[Any]
    index: int
    closing: str
    object_items: bool


def canonical_json_v1_profile(data: Any) -> str:
    """Serialize exact v1 JSON without ambient integer-to-string limits."""

    validate_unicode_scalars(data)
    output: list[str] = []
    stack: list[_SerializationFrame] = []
    current: Any = data

    while True:
        if isinstance(current, dict):
            items = sorted(current.items(), key=lambda item: item[0])
            if any(type(name) is not str for name, _ in items):
                raise TypeError("JSON object names must be strings")
            output.append("{")
            if items:
                stack.append(_SerializationFrame(items, 0, "}", True))
                name, current = items[0]
                output.append(_scalar_json(name))
                output.append(":")
                continue
            output.append("}")
        elif isinstance(current, (list, tuple)):
            values = list(current)
            output.append("[")
            if values:
                stack.append(_SerializationFrame(values, 0, "]", False))
                current = values[0]
                continue
            output.append("]")
        else:
            output.append(_scalar_json(current))

        while stack:
            frame = stack[-1]
            frame.index += 1
            if frame.index == len(frame.values):
                output.append(frame.closing)
                stack.pop()
                continue
            output.append(",")
            if frame.object_items:
                name, current = frame.values[frame.index]
                output.append(_scalar_json(name))
                output.append(":")
            else:
                current = frame.values[frame.index]
            break
        else:
            return "".join(output)


def canonicalize_ai_output_v1_profile(data: Any) -> tuple[str, str]:
    """Validate, serialize, and hash a capability-qualified v1 payload."""

    validate_ai_output(data)
    try:
        canonical = canonical_json_v1_profile(data)
    except CanonicalizationError as exc:
        raise AICanonicalError("AI_OUTPUT_INVALID_UNICODE") from exc
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return canonical, digest


def _profile_contains(
    ranges: tuple[tuple[int, int], ...], code_point: int
) -> bool:
    low = 0
    high = len(ranges)
    while low < high:
        middle = (low + high) // 2
        start, end = ranges[middle]
        if code_point < start:
            high = middle
        elif code_point > end:
            low = middle + 1
        else:
            return True
    return False


def validate_v1_manifest_timestamp(
    value: Any,
    *,
    route: EffectiveVerifierRoute,
) -> bool:
    """Apply the exact selected v1 timestamp lexical capability."""

    if not isinstance(value, str):
        return False
    if len(value) == 21:
        if value[20] != "\n":
            return False
        lexical = value[:20]
    elif len(value) == 20:
        lexical = value
    else:
        return False
    for position, expected in _TIMESTAMP_SEPARATORS.items():
        if lexical[position] != expected:
            return False

    portable = route.capability in {
        V1_RESTRICTED_PORTABLE,
        V1_FROZEN_LEGACY_COMPATIBILITY,
    }
    if portable:
        profile_name = route.declaration.timestamp_digit_profile
        if profile_name != ASCII_TIMESTAMP_DIGIT_PROFILE:
            raise AssertionError("prepared portable route has a non-ASCII profile")
        for position in _TIMESTAMP_DIGIT_POSITIONS:
            character = lexical[position]
            if "0" <= character <= "9":
                continue
            code_point = ord(character)
            if code_point < 0x80 or 0xD800 <= code_point <= 0xDFFF:
                return False
            raise OperationalInputFailure(
                OperationalCode.INPUT_OUTSIDE_DECLARED_CAPABILITY,
                OperationalPhase.MANIFEST_PARSE,
                InputRef.AI_MANIFEST_JSON,
                LimitFact(
                    LimitName.TIMESTAMP_DIGIT_PROFILE,
                    LimitUnit.PROFILE,
                    ASCII_TIMESTAMP_DIGIT_PROFILE,
                    f"U+{code_point:04X}",
                ),
                None,
            )
        return True

    if route.capability != V1_NAMED_RUNTIME_COMPATIBILITY:
        raise TypeError("route must select an executable v1 capability")
    profile = route.named_timestamp_profile
    if profile is None:
        raise AssertionError("prepared named route has no timestamp profile")
    return all(
        _profile_contains(profile.ranges, ord(lexical[position]))
        for position in _TIMESTAMP_DIGIT_POSITIONS
    )
