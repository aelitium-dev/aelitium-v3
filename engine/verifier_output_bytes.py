"""Independent byte recognizer for closed tool results, not a JCS serializer."""


def require_canonical_result_bytes(data: bytes, value: object) -> None:
    """Check RFC8785+LF after JSON/domain/schema/invariant validation.

    ``value`` must be the strict parse of these bytes, preserving member order.
    The closed result schemas have ASCII keys: their order is also UTF-16 order.
    Policy 8.2 numbers are safe integers, below ECMAScript's exponential-format
    threshold. JSON syntax plus the earlier rejection of fraction/exponent
    tokens leaves only negative zero as an alternative integer spelling.

    For portable scalar Unicode, JCS permits only quote/backslash escapes,
    short b/t/n/f/r control escapes, and lowercase hex for the remaining U+0000
    through U+001F controls. Every other scalar is literal UTF-8. Recognize
    these spellings directly; never call the normal canonicalizer or the
    emergency JSON encoder. Unicode validity and semantic fidelity are separate
    checks. This function does not accept or canonicalize arbitrary JSON inputs.
    """
    if type(data) is not bytes or not data.endswith(b"\n") or data.count(b"\n") != 1:
        raise ValueError("result must have one terminal LF")
    pending = [value]
    while pending:
        member = pending.pop()
        if type(member) is dict:
            keys = list(member)
            if any(type(key) is not str or not key.isascii() for key in keys):
                raise ValueError("result property names must be ASCII")
            if keys != sorted(keys):
                raise ValueError("result properties are not in canonical order")
            pending.extend(member.values())
        elif type(member) is list:
            pending.extend(member)
        elif type(member) is int:
            if abs(member) > 9007199254740991:
                raise ValueError("result number must be a safe integer")
        elif member is not None and type(member) not in (str, bool):
            raise ValueError("unexpected result value type")

    quoted, index, end = False, 0, len(data) - 1
    while index < end:
        byte = data[index]
        if byte == 34:  # quote, when not consumed as part of an escape
            quoted = not quoted
        elif quoted and byte == 92:  # backslash
            escape = data[index + 1]
            if escape in b'"\\btnfr':
                index += 1
            elif escape == 117:  # u: only controls lacking a short escape
                digits = data[index + 2:index + 6]
                if (len(digits) != 4 or any(c not in b'0123456789abcdef' for c in digits)
                        or not 0 <= int(digits, 16) < 32
                        or int(digits, 16) in (8, 9, 10, 12, 13)):
                    raise ValueError("noncanonical Unicode escape")
                index += 5
            else:
                raise ValueError("noncanonical string escape")
        elif not quoted:
            if byte in b' \t\r\n':
                raise ValueError("noncanonical whitespace")
            if byte == 45 and data[index + 1:index + 2] == b'0':
                raise ValueError("noncanonical negative zero")
        index += 1
