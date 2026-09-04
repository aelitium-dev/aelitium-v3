"""AELITIUM-DISPATCH-JSON-1 lexical selector scanner.

The scanner recognizes the design's JSON-plus-legacy-constants union grammar
without converting JSON number tokens or applying either version's value
profile.  Its parsed nodes retain ordered children and original byte spans,
but no node or decoded comparison view is passed to a verifier.
"""

from __future__ import annotations

from dataclasses import dataclass, field


_WHITESPACE = frozenset(b" \t\n\r")
_HEX = frozenset(b"0123456789abcdefABCDEF")
_SHORT_ESCAPES = {
    ord('"'): '"',
    ord("\\"): "\\",
    ord("/"): "/",
    ord("b"): "\b",
    ord("f"): "\f",
    ord("n"): "\n",
    ord("r"): "\r",
    ord("t"): "\t",
}


class DispatchScanError(ValueError):
    """The source is outside AELITIUM-DISPATCH-JSON-1."""


@dataclass(frozen=True)
class _DispatchMember:
    name: "_DispatchNode"
    value: "_DispatchNode"


@dataclass(frozen=True)
class _DispatchNode:
    kind: str
    start: int
    end: int
    string_view: str | None = None
    members: tuple[_DispatchMember, ...] = ()
    items: tuple["_DispatchNode", ...] = ()


@dataclass
class _ObjectFrame:
    start: int
    members: list[_DispatchMember] = field(default_factory=list)
    state: str = "first_or_end"
    pending_name: _DispatchNode | None = None


@dataclass
class _ArrayFrame:
    start: int
    items: list[_DispatchNode] = field(default_factory=list)
    state: str = "first_or_end"


class _Scanner:
    def __init__(self, source: bytes) -> None:
        self.source = source
        self.length = len(source)
        self.position = 0

    def scan(self) -> _DispatchNode:
        self._skip_whitespace()
        stack: list[_ObjectFrame | _ArrayFrame] = []
        completed = self._start_value(stack)

        while True:
            if completed is not None:
                if not stack:
                    node = completed
                    break
                parent = stack[-1]
                if isinstance(parent, _ObjectFrame):
                    if parent.state != "value" or parent.pending_name is None:
                        raise DispatchScanError("invalid object scanner state")
                    parent.members.append(
                        _DispatchMember(parent.pending_name, completed)
                    )
                    parent.pending_name = None
                    parent.state = "comma_or_end"
                else:
                    if parent.state != "value":
                        raise DispatchScanError("invalid array scanner state")
                    parent.items.append(completed)
                    parent.state = "comma_or_end"
                completed = None
                continue

            if not stack:
                raise DispatchScanError("invalid scanner state")
            frame = stack[-1]
            self._skip_whitespace()

            if isinstance(frame, _ObjectFrame):
                if frame.state == "first_or_end":
                    if (
                        self.position < self.length
                        and self.source[self.position] == ord("}")
                    ):
                        self.position += 1
                        stack.pop()
                        completed = _DispatchNode(
                            "object", frame.start, self.position
                        )
                    else:
                        frame.state = "name"
                    continue

                if frame.state == "name":
                    if (
                        self.position >= self.length
                        or self.source[self.position] != ord('"')
                    ):
                        raise DispatchScanError("object name must be a string")
                    frame.pending_name = self._string()
                    frame.state = "colon"
                    continue

                if frame.state == "colon":
                    if (
                        self.position >= self.length
                        or self.source[self.position] != ord(":")
                    ):
                        raise DispatchScanError("object name separator expected")
                    self.position += 1
                    frame.state = "value"
                    continue

                if frame.state == "value":
                    completed = self._start_value(stack)
                    continue

                if frame.state != "comma_or_end":
                    raise DispatchScanError("invalid object scanner state")
                if self.position >= self.length:
                    raise DispatchScanError("unterminated object")
                delimiter = self.source[self.position]
                self.position += 1
                if delimiter == ord("}"):
                    stack.pop()
                    completed = _DispatchNode(
                        "object",
                        frame.start,
                        self.position,
                        members=tuple(frame.members),
                    )
                elif delimiter == ord(","):
                    frame.state = "name"
                else:
                    raise DispatchScanError("object delimiter expected")
                continue

            if frame.state == "first_or_end":
                if (
                    self.position < self.length
                    and self.source[self.position] == ord("]")
                ):
                    self.position += 1
                    stack.pop()
                    completed = _DispatchNode("array", frame.start, self.position)
                else:
                    frame.state = "value"
                continue

            if frame.state == "value":
                completed = self._start_value(stack)
                continue

            if frame.state != "comma_or_end":
                raise DispatchScanError("invalid array scanner state")
            if self.position >= self.length:
                raise DispatchScanError("unterminated array")
            delimiter = self.source[self.position]
            self.position += 1
            if delimiter == ord("]"):
                stack.pop()
                completed = _DispatchNode(
                    "array",
                    frame.start,
                    self.position,
                    items=tuple(frame.items),
                )
            elif delimiter == ord(","):
                frame.state = "value"
            else:
                raise DispatchScanError("array delimiter expected")

        self._skip_whitespace()
        if self.position != self.length:
            raise DispatchScanError("trailing data")
        return node

    def _skip_whitespace(self) -> None:
        while (
            self.position < self.length
            and self.source[self.position] in _WHITESPACE
        ):
            self.position += 1

    def _start_value(
        self, stack: list[_ObjectFrame | _ArrayFrame]
    ) -> _DispatchNode | None:
        self._skip_whitespace()
        if self.position >= self.length:
            raise DispatchScanError("value expected")
        byte = self.source[self.position]
        if byte == ord('"'):
            return self._string()
        if byte == ord("{"):
            start = self.position
            self.position += 1
            stack.append(_ObjectFrame(start))
            return None
        if byte == ord("["):
            start = self.position
            self.position += 1
            stack.append(_ArrayFrame(start))
            return None
        for literal, kind in (
            (b"false", "false"),
            (b"null", "null"),
            (b"true", "true"),
            (b"NaN", "legacy_constant"),
            (b"Infinity", "legacy_constant"),
            (b"-Infinity", "legacy_constant"),
        ):
            if self.source.startswith(literal, self.position):
                start = self.position
                self.position += len(literal)
                return _DispatchNode(kind, start, self.position)
        if byte == ord("-") or ord("0") <= byte <= ord("9"):
            return self._number()
        raise DispatchScanError("unrecognized value token")

    def _string(self) -> _DispatchNode:
        start = self.position
        self.position += 1
        comparison: list[str] = []
        while self.position < self.length:
            byte = self.source[self.position]
            if byte == ord('"'):
                self.position += 1
                return _DispatchNode(
                    "string", start, self.position, string_view="".join(comparison)
                )
            if byte == ord("\\"):
                self.position += 1
                if self.position >= self.length:
                    raise DispatchScanError("truncated string escape")
                escape = self.source[self.position]
                self.position += 1
                if escape in _SHORT_ESCAPES:
                    comparison.append(_SHORT_ESCAPES[escape])
                    continue
                if escape != ord("u"):
                    raise DispatchScanError("invalid string escape")
                code_point = self._unicode_escape_value()
                if 0xD800 <= code_point <= 0xDBFF and self._has_low_escape():
                    self.position += 2
                    low = self._unicode_escape_value()
                    comparison.append(
                        chr(
                            0x10000
                            + ((code_point - 0xD800) << 10)
                            + (low - 0xDC00)
                        )
                    )
                else:
                    # Scanner comparison intentionally retains unmatched
                    # surrogates as unmatched Python code points.
                    comparison.append(chr(code_point))
                continue
            if byte < 0x20:
                raise DispatchScanError("unescaped control in string")
            if byte < 0x80:
                comparison.append(chr(byte))
                self.position += 1
                continue
            width = self._utf8_width(byte)
            end = self.position + width
            if end > self.length:
                raise DispatchScanError("truncated UTF-8 in string")
            try:
                character = self.source[self.position:end].decode(
                    "utf-8", errors="strict"
                )
            except UnicodeDecodeError as exc:
                raise DispatchScanError("invalid UTF-8 in string") from exc
            if len(character) != 1:
                raise DispatchScanError("invalid UTF-8 scalar")
            comparison.append(character)
            self.position = end
        raise DispatchScanError("unterminated string")

    def _unicode_escape_value(self) -> int:
        end = self.position + 4
        if end > self.length:
            raise DispatchScanError("truncated Unicode escape")
        digits = self.source[self.position:end]
        if any(digit not in _HEX for digit in digits):
            raise DispatchScanError("invalid Unicode escape")
        self.position = end
        return int(digits.decode("ascii"), 16)

    def _has_low_escape(self) -> bool:
        if self.source[self.position : self.position + 2] != b"\\u":
            return False
        digits = self.source[self.position + 2 : self.position + 6]
        if len(digits) != 4 or any(digit not in _HEX for digit in digits):
            return False
        low = int(digits.decode("ascii"), 16)
        return 0xDC00 <= low <= 0xDFFF

    @staticmethod
    def _utf8_width(first: int) -> int:
        if 0xC2 <= first <= 0xDF:
            return 2
        if 0xE0 <= first <= 0xEF:
            return 3
        if 0xF0 <= first <= 0xF4:
            return 4
        raise DispatchScanError("invalid UTF-8 leading byte")

    def _number(self) -> _DispatchNode:
        start = self.position
        if self.source[self.position] == ord("-"):
            self.position += 1
            if self.position >= self.length:
                raise DispatchScanError("truncated number")

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
            raise DispatchScanError("invalid integer component")

        if self.position < self.length and self.source[self.position] == ord("."):
            self.position += 1
            fraction_start = self.position
            while (
                self.position < self.length
                and ord("0") <= self.source[self.position] <= ord("9")
            ):
                self.position += 1
            if self.position == fraction_start:
                raise DispatchScanError("fraction requires a digit")

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
                raise DispatchScanError("exponent requires a digit")

        return _DispatchNode("number", start, self.position)


def _parse_dispatch_tree(manifest_bytes: bytes) -> _DispatchNode:
    """Build the internal lossless tree; dispatch never exposes this value."""

    if type(manifest_bytes) is not bytes:
        raise DispatchScanError("manifest source must be bytes")
    return _Scanner(manifest_bytes).scan()


def scan_manifest_selector(
    manifest_bytes: bytes,
    *,
    registered_identifiers: frozenset[str],
) -> str | None:
    """Return the final registered root selector, or ``None``.

    A malformed scan raises ``DispatchScanError``.  Callers implementing the
    normative routing algorithm must treat that exactly like every other
    non-v2 outcome and enter the complete legacy error-resolution path.
    """

    root = _parse_dispatch_tree(manifest_bytes)
    if root.kind != "object":
        return None

    selector: _DispatchNode | None = None
    for member in root.members:
        if member.name.string_view == "canonicalization":
            selector = member.value
    if selector is None or selector.kind != "string":
        return None
    if selector.string_view not in registered_identifiers:
        return None
    return selector.string_view
