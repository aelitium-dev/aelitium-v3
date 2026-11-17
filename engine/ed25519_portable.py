"""Portable Ed25519 verification for ``ED25519_PORTABLE_STRICT_1``.

This module implements deterministic verification semantics directly instead
of delegating acceptance to a cryptographic backend.  Its inputs are public
verification material.  The straightforward arithmetic below is variable
time; it performs no secret-key operation and makes no secret-key timing
side-channel claim.
"""

from hashlib import sha512
from typing import Optional, Tuple


_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)

# RFC 8032 section 5.1 Edwards25519 base point coordinates.
_BASE_X = (
    15112221349535400772501151409588531511454012693041857206046113283949847762202
)
_BASE_Y = (
    46316835694926478169428394003475163141307993866256225615783033603165251855960
)

# Extended Edwards coordinates (X, Y, Z, T), where x=X/Z, y=Y/Z, and XY=ZT.
_Point = Tuple[int, int, int, int]
_IDENTITY: _Point = (0, 1, 1, 0)
_BASE_POINT: _Point = (_BASE_X, _BASE_Y, 1, (_BASE_X * _BASE_Y) % _P)


def _from_affine(x: int, y: int) -> _Point:
    return x, y, 1, (x * y) % _P


def _decode_point(encoded: bytes) -> Optional[_Point]:
    """Decode the strict RFC 8032 section 5.1.3 point representation."""

    if len(encoded) != 32:
        return None

    encoded_integer = int.from_bytes(encoded, "little")
    sign = encoded_integer >> 255
    y = encoded_integer & ((1 << 255) - 1)
    if y >= _P:
        return None

    y_squared = (y * y) % _P
    denominator = (_D * y_squared + 1) % _P
    if denominator == 0:
        return None
    x_squared = ((y_squared - 1) * pow(denominator, _P - 2, _P)) % _P

    x = pow(x_squared, (_P + 3) // 8, _P)
    if (x * x - x_squared) % _P != 0:
        x = (x * _SQRT_M1) % _P
    if (x * x - x_squared) % _P != 0:
        return None

    # RFC 8032 rejects this non-canonical sign choice before parity selection.
    if x == 0 and sign == 1:
        return None
    if (x & 1) != sign:
        x = _P - x

    return _from_affine(x, y)


def _point_add(left: _Point, right: _Point) -> _Point:
    """Add two Edwards25519 points using complete extended-coordinate formulas."""

    x1, y1, z1, t1 = left
    x2, y2, z2, t2 = right
    a = ((y1 - x1) * (y2 - x2)) % _P
    b = ((y1 + x1) * (y2 + x2)) % _P
    c = (2 * _D * t1 * t2) % _P
    d = (2 * z1 * z2) % _P
    e = (b - a) % _P
    f = (d - c) % _P
    g = (d + c) % _P
    h = (b + a) % _P
    return (e * f) % _P, (g * h) % _P, (f * g) % _P, (e * h) % _P


def _scalar_multiply(scalar: int, point: _Point) -> _Point:
    result = _IDENTITY
    addend = point
    while scalar:
        if scalar & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        scalar >>= 1
    return result


def _points_equal(left: _Point, right: _Point) -> bool:
    x1, y1, z1, _ = left
    x2, y2, z2, _ = right
    return (
        (x1 * z2 - x2 * z1) % _P == 0
        and (y1 * z2 - y2 * z1) % _P == 0
    )


def _is_identity(point: _Point) -> bool:
    return _points_equal(point, _IDENTITY)


def _is_in_prime_order_subgroup(point: _Point) -> bool:
    # This also excludes every non-identity small-order point because L is odd.
    return _is_identity(_scalar_multiply(_L, point))


def _verify_equation(
    public_key: _Point,
    r_point: _Point,
    scalar: int,
    challenge: int,
) -> bool:
    left = _scalar_multiply(scalar, _BASE_POINT)
    right = _point_add(r_point, _scalar_multiply(challenge, public_key))
    return _points_equal(left, right)


def verify_ed25519_portable_strict_1(
    public_key_bytes: bytes,
    signature_bytes: bytes,
    message: bytes,
) -> bool:
    """Return the exact ``ED25519_PORTABLE_STRICT_1`` acceptance decision."""

    if not isinstance(public_key_bytes, bytes) or len(public_key_bytes) != 32:
        return False
    if not isinstance(signature_bytes, bytes) or len(signature_bytes) != 64:
        return False
    if not isinstance(message, bytes):
        return False

    r_encoded = signature_bytes[:32]
    s_encoded = signature_bytes[32:]

    public_key = _decode_point(public_key_bytes)
    r_point = _decode_point(r_encoded)
    if public_key is None or r_point is None:
        return False
    if _is_identity(public_key):
        return False

    if not _is_in_prime_order_subgroup(public_key):
        return False
    if not _is_in_prime_order_subgroup(r_point):
        return False

    scalar = int.from_bytes(s_encoded, "little")
    if scalar >= _L:
        return False

    challenge = int.from_bytes(
        sha512(r_encoded + public_key_bytes + message).digest(),
        "little",
    ) % _L
    return _verify_equation(public_key, r_point, scalar, challenge)
