"""Iterative JSON source traversal for verifier operational limits.

This scanner is a resource-boundary mechanism, not a semantic JSON parser.
It walks immutable source bytes from left to right, counts source occurrences
before object-member collapse, and deliberately leaves every syntax/profile
decision to the selected production parser.  A syntax boundary reached before
an excess simply ends the boundary scan; a limit already proved first remains
an operational failure even if unevaluated bytes later would be malformed.
"""

from __future__ import annotations

from dataclasses import dataclass

from .verifier_snapshot import (
    InputRef,
    LimitFact,
    LimitName,
    LimitUnit,
    OperationalCode,
    OperationalInputFailure,
    OperationalLimits,
    OperationalPhase,
)


_WHITESPACE = frozenset(b" \t\n\r")
_HEX = frozenset(b"0123456789abcdefABCDEF")
_SHORT_ESCAPES = frozenset(b'"\\/bfnrt')


class _SourceBoundary(ValueError):
    """Internal marker for syntax encountered before a traversal excess."""


@dataclass(frozen=True, slots=True)
class JsonTraversal:
    """Measurements established before the scan completed or met syntax."""

    maximum_structural_depth: int
    value_occurrences: int
    source_was_lexically_complete: bool


@dataclass(frozen=True, slots=True)
class JsonTraversalLimitExceeded(RuntimeError):
    """The first traversal measurement proven greater than its ceiling."""

    name: LimitName
    unit: LimitUnit
    maximum: int
    observed_at_least: int

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.name.value)


@dataclass(slots=True)
class _ObjectFrame:
    state: str = "first_or_end"


@dataclass(slots=True)
class _ArrayFrame:
    state: str = "first_or_end"


_Frame = _ObjectFrame | _ArrayFrame


class _Scanner:
    def __init__(
        self,
        source: bytes,
        limits: OperationalLimits,
        *,
        allow_legacy_constants: bool,
    ) -> None:
        self.source = source
        self.length = len(source)
        self.position = 0
        self.limits = limits
        self.allow_legacy_constants = allow_legacy_constants
        self.maximum_structural_depth = 0
        self.value_occurrences = 0

    def scan(self) -> JsonTraversal:
        try:
            self._skip_whitespace()
            stack: list[_Frame] = []
            completed = self._start_value(stack)

            while True:
                if completed:
                    if not stack:
                        break
                    parent = stack[-1]
                    if parent.state != "value":
                        raise AssertionError("invalid JSON limit scanner state")
                    parent.state = "comma_or_end"
                    completed = False
                    continue

                if not stack:
                    raise AssertionError("invalid JSON limit scanner state")
                frame = stack[-1]
                self._skip_whitespace()

                if isinstance(frame, _ObjectFrame):
                    completed = self._scan_object_frame(frame, stack)
                else:
                    completed = self._scan_array_frame(frame, stack)

            self._skip_whitespace()
            if self.position != self.length:
                raise _SourceBoundary("trailing data")
        except _SourceBoundary:
            return JsonTraversal(
                self.maximum_structural_depth,
                self.value_occurrences,
                False,
            )

        return JsonTraversal(
            self.maximum_structural_depth,
            self.value_occurrences,
            True,
        )

    def _scan_object_frame(
        self,
        frame: _ObjectFrame,
        stack: list[_Frame],
    ) -> bool:
        if frame.state == "first_or_end":
            if self._take_if(ord("}")):
                stack.pop()
                return True
            frame.state = "name"
            return False

        if frame.state == "name":
            if self.position >= self.length or self.source[self.position] != ord('"'):
                raise _SourceBoundary("object name must be a string")
            self._string()
            frame.state = "colon"
            return False

        if frame.state == "colon":
            if not self._take_if(ord(":")):
                raise _SourceBoundary("object name separator expected")
            frame.state = "value"
            return False

        if frame.state == "value":
            return self._start_value(stack)

        if frame.state != "comma_or_end":
            raise AssertionError("invalid JSON limit scanner state")
        if self.position >= self.length:
            raise _SourceBoundary("unterminated object")
        delimiter = self.source[self.position]
        self.position += 1
        if delimiter == ord("}"):
            stack.pop()
            return True
        if delimiter == ord(","):
            frame.state = "name"
            return False
        raise _SourceBoundary("object delimiter expected")

    def _scan_array_frame(
        self,
        frame: _ArrayFrame,
        stack: list[_Frame],
    ) -> bool:
        if frame.state == "first_or_end":
            if self._take_if(ord("]")):
                stack.pop()
                return True
            frame.state = "value"
            return False

        if frame.state == "value":
            return self._start_value(stack)

        if frame.state != "comma_or_end":
            raise AssertionError("invalid JSON limit scanner state")
        if self.position >= self.length:
            raise _SourceBoundary("unterminated array")
        delimiter = self.source[self.position]
        self.position += 1
        if delimiter == ord("]"):
            stack.pop()
            return True
        if delimiter == ord(","):
            frame.state = "value"
            return False
        raise _SourceBoundary("array delimiter expected")

    def _start_value(self, stack: list[_Frame]) -> bool:
        self._skip_whitespace()
        if self.position >= self.length:
            raise _SourceBoundary("value expected")

        byte = self.source[self.position]
        if byte == ord('"'):
            self._string()
            self._record_value()
            return True
        if byte == ord("{"):
            self._record_value()
            self._open_container(stack, _ObjectFrame())
            return False
        if byte == ord("["):
            self._record_value()
            self._open_container(stack, _ArrayFrame())
            return False

        literals = (b"false", b"null", b"true")
        if self.allow_legacy_constants:
            literals += (b"NaN", b"Infinity", b"-Infinity")
        for literal in literals:
            if self.source.startswith(literal, self.position):
                self.position += len(literal)
                self._record_value()
                return True

        if byte == ord("-") or ord("0") <= byte <= ord("9"):
            self._number()
            self._record_value()
            return True
        raise _SourceBoundary("unrecognized value token")

    def _record_value(self) -> None:
        observed = self.value_occurrences + 1
        if observed > self.limits.max_value_occurrences:
            raise JsonTraversalLimitExceeded(
                LimitName.VALUE_OCCURRENCES,
                LimitUnit.OCCURRENCES,
                self.limits.max_value_occurrences,
                observed,
            )
        self.value_occurrences = observed

    def _open_container(self, stack: list[_Frame], frame: _Frame) -> None:
        observed = len(stack) + 1
        if observed > self.limits.max_structural_depth:
            raise JsonTraversalLimitExceeded(
                LimitName.STRUCTURAL_DEPTH,
                LimitUnit.LEVELS,
                self.limits.max_structural_depth,
                observed,
            )
        self.maximum_structural_depth = max(
            self.maximum_structural_depth,
            observed,
        )
        self.position += 1
        stack.append(frame)

    def _skip_whitespace(self) -> None:
        while (
            self.position < self.length
            and self.source[self.position] in _WHITESPACE
        ):
            self.position += 1

    def _take_if(self, expected: int) -> bool:
        if self.position < self.length and self.source[self.position] == expected:
            self.position += 1
            return True
        return False

    def _string(self) -> None:
        self.position += 1
        while self.position < self.length:
            byte = self.source[self.position]
            if byte == ord('"'):
                self.position += 1
                return
            if byte == ord("\\"):
                self.position += 1
                if self.position >= self.length:
                    raise _SourceBoundary("truncated string escape")
                escape = self.source[self.position]
                self.position += 1
                if escape in _SHORT_ESCAPES:
                    continue
                if escape != ord("u"):
                    raise _SourceBoundary("invalid string escape")
                end = self.position + 4
                if end > self.length or any(
                    digit not in _HEX for digit in self.source[self.position : end]
                ):
                    raise _SourceBoundary("invalid Unicode escape")
                self.position = end
                continue
            if byte < 0x20:
                raise _SourceBoundary("unescaped control in string")
            if byte < 0x80:
                self.position += 1
                continue

            width = self._utf8_width(byte)
            end = self.position + width
            if end > self.length:
                raise _SourceBoundary("truncated UTF-8 in string")
            try:
                character = self.source[self.position : end].decode(
                    "utf-8",
                    errors="strict",
                )
            except UnicodeDecodeError as exc:
                raise _SourceBoundary("invalid UTF-8 in string") from exc
            if len(character) != 1:
                raise _SourceBoundary("invalid UTF-8 scalar")
            self.position = end
        raise _SourceBoundary("unterminated string")

    @staticmethod
    def _utf8_width(first: int) -> int:
        if 0xC2 <= first <= 0xDF:
            return 2
        if 0xE0 <= first <= 0xEF:
            return 3
        if 0xF0 <= first <= 0xF4:
            return 4
        raise _SourceBoundary("invalid UTF-8 leading byte")

    def _number(self) -> None:
        if self.source[self.position] == ord("-"):
            self.position += 1
            if self.position >= self.length:
                raise _SourceBoundary("truncated number")

        if self.source[self.position] == ord("0"):
            self.position += 1
        elif ord("1") <= self.source[self.position] <= ord("9"):
            self.position += 1
            while (
                self.position < self.length
                and ord("0") <= self.source[self.position] <= ord("9")
            ):
                self.position += 1
        else:
            raise _SourceBoundary("invalid integer component")

        if self.position < self.length and self.source[self.position] == ord("."):
            self.position += 1
            fraction_start = self.position
            while (
                self.position < self.length
                and ord("0") <= self.source[self.position] <= ord("9")
            ):
                self.position += 1
            if self.position == fraction_start:
                raise _SourceBoundary("fraction requires a digit")

        if self.position < self.length and self.source[self.position] in b"eE":
            self.position += 1
            if self.position < self.length and self.source[self.position] in b"+-":
                self.position += 1
            exponent_start = self.position
            while (
                self.position < self.length
                and ord("0") <= self.source[self.position] <= ord("9")
            ):
                self.position += 1
            if self.position == exponent_start:
                raise _SourceBoundary("exponent requires a digit")


def scan_json_limits(
    source: bytes,
    *,
    limits: OperationalLimits,
    allow_legacy_constants: bool,
) -> JsonTraversal:
    """Measure one immutable source or raise its first proven limit excess.

    A returned ``source_was_lexically_complete=False`` is intentionally not a
    semantic diagnosis.  The selected parser receives the unchanged bytes and
    remains the only authority for source/profile validity.
    """

    if type(source) is not bytes:
        raise TypeError("source must be bytes")
    if not isinstance(limits, OperationalLimits):
        raise TypeError("limits must be OperationalLimits")
    return _Scanner(
        source,
        limits,
        allow_legacy_constants=allow_legacy_constants,
    ).scan()


def enforce_json_traversal_limits(
    source: bytes,
    *,
    limits: OperationalLimits,
    phase: OperationalPhase,
    input_ref: InputRef,
    allow_legacy_constants: bool,
) -> JsonTraversal:
    """Apply traversal ceilings and map excess/exhaustion operationally."""

    try:
        return scan_json_limits(
            source,
            limits=limits,
            allow_legacy_constants=allow_legacy_constants,
        )
    except JsonTraversalLimitExceeded as exc:
        raise OperationalInputFailure(
            OperationalCode.RESOURCE_LIMIT_EXCEEDED,
            phase,
            input_ref,
            LimitFact(
                exc.name,
                exc.unit,
                exc.maximum,
                exc.observed_at_least,
            ),
            None,
        ) from exc
    except (MemoryError, RecursionError) as exc:
        raise OperationalInputFailure(
            OperationalCode.RESOURCE_EXHAUSTED,
            phase,
            input_ref,
            None,
            None,
        ) from exc


__all__ = [
    "JsonTraversal",
    "JsonTraversalLimitExceeded",
    "enforce_json_traversal_limits",
    "scan_json_limits",
]
