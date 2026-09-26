"""Bounded, host-independent descriptions of capability-parsed JSON values."""

from __future__ import annotations

import hashlib
import math
from typing import Any


def describe_json_value(value: Any) -> str:
    """Describe an invalid field without decimalizing an unbounded integer.

    The digest is over the integer's magnitude in big-endian binary form. It
    distinguishes large values without depending on Python's decimal guard or
    producing an unbounded machine-result diagnostic.
    """

    if type(value) is int:
        if value.bit_length() <= 2_000:
            return str(value)
        magnitude = abs(value)
        raw = magnitude.to_bytes((magnitude.bit_length() + 7) // 8, "big")
        return (
            f"<integer sign={'-' if value < 0 else '+'} "
            f"bits={magnitude.bit_length()} sha256={hashlib.sha256(raw).hexdigest()}>"
        )
    if type(value) is str:
        if len(value) <= 160:
            return repr(value)
        digest = hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()
        return f"<string length={len(value)} sha256={digest}>"
    if type(value) is float:
        return repr(value) if math.isfinite(value) else "<nonfinite number>"
    if type(value) is list:
        return f"<array length={len(value)}>"
    if type(value) is dict:
        return f"<object members={len(value)}>"
    return repr(value)
