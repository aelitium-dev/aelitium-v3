"""Immutable verifier capability preparation and route selection.

Capability declarations are operation configuration, never evidence content.
This module validates the complete explicit request before input acquisition,
authenticates packaged frozen Unicode profile data, and selects the effective
semantic route only after AELITIUM-DISPATCH-JSON-1 has run.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from importlib import resources
from types import MappingProxyType
from typing import Final, Mapping, NoReturn

from .ai_contract import AI_CANONICALIZATION, AI_CANONICALIZATION_V2
from .verifier_snapshot import (
    InputRef,
    OperationalCode,
    OperationalInputFailure,
    OperationalPhase,
)


AELITIUM_DISPATCH_JSON_1: Final = "AELITIUM-DISPATCH-JSON-1"

V2_PORTABLE: Final = "V2_PORTABLE"
V1_RESTRICTED_PORTABLE: Final = "V1_RESTRICTED_PORTABLE"
V1_FROZEN_LEGACY_COMPATIBILITY: Final = "V1_FROZEN_LEGACY_COMPATIBILITY"
V1_NAMED_RUNTIME_COMPATIBILITY: Final = "V1_NAMED_RUNTIME_COMPATIBILITY"
V1_LEGACY_UNSUPPORTED: Final = "V1_LEGACY_UNSUPPORTED"

ED25519_PORTABLE_STRICT_1: Final = "ED25519_PORTABLE_STRICT_1"

BOUNDED: Final = "BOUNDED"
UNLIMITED: Final = "UNLIMITED"
ASCII_TIMESTAMP_DIGIT_PROFILE: Final = "ASCII"
ACCEPT_ONE_TIMESTAMP_FINAL_LF: Final = "ACCEPT_ONE"

_MAX_PORTABLE_INTEGER: Final = 9_007_199_254_740_991
_CAPABILITY_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
_UNICODE_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){2}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_RANGE_LINE = re.compile(rb"[0-9A-F]{6}\.\.[0-9A-F]{6}\n")


class CapabilityProfileUnavailable(RuntimeError):
    """A legacy direct-API signature profile cannot be selected.

    This compatibility exception remains separate because the unqualified
    released-style API predates ``OperationalInputFailure``. Capability-
    qualified operation preparation below uses the shared operational type.
    """

    operational_code = "CAPABILITY_PROFILE_UNAVAILABLE"
    phase = "CAPABILITY_SELECTION"
    effective_profile = None

    def __init__(self, requested_profile: str) -> None:
        self.requested_profile = requested_profile
        super().__init__(
            f"signature verification profile unavailable: {requested_profile!r}"
        )


class CapabilityRequestValidationError(ValueError):
    """A capability request is not inside the structural request grammar."""


@dataclass(frozen=True, slots=True)
class DispatchCapabilityDeclaration:
    """Requested dispatch implementation identifier."""

    dispatch: str


@dataclass(frozen=True, slots=True)
class IntegerConversionDeclaration:
    """Explicit legacy integer-conversion profile declaration."""

    mode: str
    maximum_decimal_digits: int | None


@dataclass(frozen=True, slots=True)
class TimestampDigitProfileDeclaration:
    """Complete named frozen Unicode ``Nd`` profile tuple."""

    profile_id: str
    range_file_sha256: str
    unicode_version: str


@dataclass(frozen=True, slots=True)
class V1CapabilityDeclaration:
    """One exact v1 route declaration before availability validation."""

    capability: str
    integer_conversion: IntegerConversionDeclaration | None = None
    timestamp_digit_profile: str | TimestampDigitProfileDeclaration | None = None
    timestamp_final_lf: str | None = None


@dataclass(frozen=True, slots=True)
class V2CapabilityDeclaration:
    """One exact v2 route declaration."""

    capability: str


@dataclass(frozen=True, slots=True)
class SignatureVerificationDeclaration:
    """Orthogonal signature-verification capability declaration."""

    profile: str


@dataclass(frozen=True, slots=True)
class VerifierCapabilityRequest:
    """Complete capability-qualified operation request."""

    dispatch: DispatchCapabilityDeclaration
    v1: V1CapabilityDeclaration
    v2: V2CapabilityDeclaration
    signature_verification: SignatureVerificationDeclaration


@dataclass(frozen=True, slots=True)
class FrozenUnicodeProfileMetadata:
    """Production registry record for one normative frozen range file."""

    profile_id: str
    unicode_version: str
    range_file: str
    range_file_sha256: str
    range_count: int
    code_point_count: int


FROZEN_UNICODE_PROFILES: Final[tuple[FrozenUnicodeProfileMetadata, ...]] = (
    FrozenUnicodeProfileMetadata(
        "AELITIUM_UCD_ND_13_0_0_1",
        "13.0.0",
        "nd-13.0.0.txt",
        "bf287074b61dbb4a03a10645580b5ae0d1e106d75aa6c26881a7a277712c4f8b",
        61,
        650,
    ),
    FrozenUnicodeProfileMetadata(
        "AELITIUM_UCD_ND_14_0_0_1",
        "14.0.0",
        "nd-14.0.0.txt",
        "5a75c753790a222c430dbfc95adaa2c3ec6701862d1728eae92d9ed0e2df59c8",
        62,
        660,
    ),
    FrozenUnicodeProfileMetadata(
        "AELITIUM_UCD_ND_15_0_0_1",
        "15.0.0",
        "nd-15.0.0.txt",
        "0f10e369beb834ccee109f3ccc8d75f6ff8067871baf7109a106f1dac7430222",
        64,
        680,
    ),
)

_FROZEN_UNICODE_PROFILE_BY_ID: Final[
    Mapping[str, FrozenUnicodeProfileMetadata]
] = MappingProxyType({profile.profile_id: profile for profile in FROZEN_UNICODE_PROFILES})


@dataclass(frozen=True, slots=True)
class PreparedUnicodeProfile:
    """Authenticated immutable production representation for O2B2B."""

    metadata: FrozenUnicodeProfileMetadata
    ranges: tuple[tuple[int, int], ...]
    actual_range_file_sha256: str


@dataclass(frozen=True, slots=True)
class PreparedVerifierCapabilities:
    """A complete request whose profiles are available and authenticated."""

    requested: VerifierCapabilityRequest
    named_timestamp_profile: PreparedUnicodeProfile | None

    @property
    def signature_verification_profile(self) -> str:
        return self.requested.signature_verification.profile


@dataclass(frozen=True, slots=True)
class EffectiveVerifierRoute:
    """Explicit v1 or v2 route selected after manifest dispatch."""

    canonicalization_identifier: str
    declaration: V1CapabilityDeclaration | V2CapabilityDeclaration
    named_timestamp_profile: PreparedUnicodeProfile | None

    @property
    def capability(self) -> str:
        return self.declaration.capability


def _raise_capability_unavailable(
    *,
    phase: OperationalPhase = OperationalPhase.CAPABILITY_SELECTION,
    input_ref: InputRef | None = None,
) -> NoReturn:
    raise OperationalInputFailure(
        OperationalCode.CAPABILITY_PROFILE_UNAVAILABLE,
        phase,
        input_ref,
        None,
        None,
    )


def _invalid_request(message: str) -> NoReturn:
    raise CapabilityRequestValidationError(message)


def _validate_identifier(value: object, *, label: str) -> None:
    if type(value) is not str or _CAPABILITY_IDENTIFIER.fullmatch(value) is None:
        _invalid_request(f"{label} is not a capability identifier")


def _validate_requested_integer_conversion(
    declaration: IntegerConversionDeclaration | None,
) -> None:
    if type(declaration) is not IntegerConversionDeclaration:
        _invalid_request("integer_conversion must be a complete declaration")
    _validate_identifier(declaration.mode, label="integer_conversion.mode")
    maximum = declaration.maximum_decimal_digits
    if maximum is None:
        return
    if (
        type(maximum) is not int
        or maximum < 0
        or maximum > _MAX_PORTABLE_INTEGER
    ):
        _invalid_request(
            "integer_conversion.maximum_decimal_digits must be null or a "
            "portable non-negative integer"
        )


def _validate_requested_timestamp_profile(
    declaration: TimestampDigitProfileDeclaration | None,
) -> None:
    if type(declaration) is not TimestampDigitProfileDeclaration:
        _invalid_request("timestamp_digit_profile must be a complete declaration")
    _validate_identifier(
        declaration.profile_id,
        label="timestamp_digit_profile.profile_id",
    )
    if (
        type(declaration.range_file_sha256) is not str
        or _SHA256.fullmatch(declaration.range_file_sha256) is None
    ):
        _invalid_request(
            "timestamp_digit_profile.range_file_sha256 must be lowercase SHA-256"
        )
    if (
        type(declaration.unicode_version) is not str
        or _UNICODE_VERSION.fullmatch(declaration.unicode_version) is None
    ):
        _invalid_request(
            "timestamp_digit_profile.unicode_version must be a three-part version"
        )


def _validate_requested_v1(declaration: V1CapabilityDeclaration) -> None:
    _validate_identifier(declaration.capability, label="v1.capability")
    capability = declaration.capability

    if capability == V1_LEGACY_UNSUPPORTED:
        if (
            declaration.integer_conversion is not None
            or declaration.timestamp_digit_profile is not None
            or declaration.timestamp_final_lf is not None
        ):
            _invalid_request("V1_LEGACY_UNSUPPORTED has no subordinate members")
        return

    if capability in {
        V1_RESTRICTED_PORTABLE,
        V1_FROZEN_LEGACY_COMPATIBILITY,
    }:
        _validate_requested_integer_conversion(declaration.integer_conversion)
        _validate_identifier(
            declaration.timestamp_digit_profile,
            label="v1.timestamp_digit_profile",
        )
        _validate_identifier(
            declaration.timestamp_final_lf,
            label="v1.timestamp_final_lf",
        )
        return

    if capability == V1_NAMED_RUNTIME_COMPATIBILITY:
        _validate_requested_integer_conversion(declaration.integer_conversion)
        _validate_requested_timestamp_profile(declaration.timestamp_digit_profile)
        _validate_identifier(
            declaration.timestamp_final_lf,
            label="v1.timestamp_final_lf",
        )
        return

    if (
        declaration.integer_conversion is not None
        or declaration.timestamp_digit_profile is not None
        or declaration.timestamp_final_lf is not None
    ):
        _invalid_request("unknown v1 capability has uninterpretable members")


def validate_verifier_capability_request(
    request: VerifierCapabilityRequest,
) -> None:
    """Validate request syntax without consulting capability availability.

    Successful return establishes only the N2 structural and portability
    envelope.  Registry support, fixed-value equality, and frozen profile
    availability remain the responsibility of :func:`prepare_verifier_capabilities`.
    """

    if type(request) is not VerifierCapabilityRequest:
        _invalid_request("request must be VerifierCapabilityRequest")
    if type(request.dispatch) is not DispatchCapabilityDeclaration:
        _invalid_request("dispatch must be DispatchCapabilityDeclaration")
    if type(request.v1) is not V1CapabilityDeclaration:
        _invalid_request("v1 must be V1CapabilityDeclaration")
    if type(request.v2) is not V2CapabilityDeclaration:
        _invalid_request("v2 must be V2CapabilityDeclaration")
    if type(request.signature_verification) is not SignatureVerificationDeclaration:
        _invalid_request(
            "signature_verification must be SignatureVerificationDeclaration"
        )

    _validate_identifier(request.dispatch.dispatch, label="dispatch")
    _validate_requested_v1(request.v1)
    _validate_identifier(request.v2.capability, label="v2.capability")
    _validate_identifier(
        request.signature_verification.profile,
        label="signature_verification.profile",
    )


def _validate_dispatch(declaration: DispatchCapabilityDeclaration) -> None:
    if (
        type(declaration.dispatch) is not str
        or declaration.dispatch != AELITIUM_DISPATCH_JSON_1
    ):
        _raise_capability_unavailable()


def _validate_v2(declaration: V2CapabilityDeclaration) -> None:
    if type(declaration.capability) is not str or declaration.capability != V2_PORTABLE:
        _raise_capability_unavailable()


def _validate_signature(
    declaration: SignatureVerificationDeclaration,
) -> None:
    if (
        type(declaration.profile) is not str
        or declaration.profile != ED25519_PORTABLE_STRICT_1
    ):
        _raise_capability_unavailable()


def _fixed_portable_v1_is_exact(declaration: V1CapabilityDeclaration) -> bool:
    return (
        type(declaration.integer_conversion) is IntegerConversionDeclaration
        and type(declaration.integer_conversion.mode) is str
        and declaration.integer_conversion.mode == BOUNDED
        and type(declaration.integer_conversion.maximum_decimal_digits) is int
        and declaration.integer_conversion.maximum_decimal_digits == 640
        and type(declaration.timestamp_digit_profile) is str
        and declaration.timestamp_digit_profile == ASCII_TIMESTAMP_DIGIT_PROFILE
        and type(declaration.timestamp_final_lf) is str
        and declaration.timestamp_final_lf == ACCEPT_ONE_TIMESTAMP_FINAL_LF
    )


def _validate_named_integer(
    declaration: IntegerConversionDeclaration | None,
) -> None:
    if type(declaration) is not IntegerConversionDeclaration:
        _raise_capability_unavailable()
    if type(declaration.mode) is not str:
        _raise_capability_unavailable()
    if declaration.mode == BOUNDED:
        maximum = declaration.maximum_decimal_digits
        if (
            type(maximum) is not int
            or maximum < 640
            or maximum > _MAX_PORTABLE_INTEGER
        ):
            _raise_capability_unavailable()
        return
    if declaration.mode == UNLIMITED and declaration.maximum_decimal_digits is None:
        return
    _raise_capability_unavailable()


def _validate_v1(
    declaration: V1CapabilityDeclaration,
) -> TimestampDigitProfileDeclaration | None:
    capability = declaration.capability
    if type(capability) is not str:
        _raise_capability_unavailable()
    if capability in {
        V1_RESTRICTED_PORTABLE,
        V1_FROZEN_LEGACY_COMPATIBILITY,
    }:
        if not _fixed_portable_v1_is_exact(declaration):
            _raise_capability_unavailable()
        return None

    if capability == V1_LEGACY_UNSUPPORTED:
        if (
            declaration.integer_conversion is not None
            or declaration.timestamp_digit_profile is not None
            or declaration.timestamp_final_lf is not None
        ):
            _raise_capability_unavailable()
        return None

    if capability == V1_NAMED_RUNTIME_COMPATIBILITY:
        _validate_named_integer(declaration.integer_conversion)
        if type(declaration.timestamp_digit_profile) is not TimestampDigitProfileDeclaration:
            _raise_capability_unavailable()
        if (
            type(declaration.timestamp_final_lf) is not str
            or declaration.timestamp_final_lf != ACCEPT_ONE_TIMESTAMP_FINAL_LF
        ):
            _raise_capability_unavailable()
        return declaration.timestamp_digit_profile

    _raise_capability_unavailable()


def parse_unicode_nd_ranges(source: bytes) -> tuple[tuple[int, int], ...]:
    """Parse exact ``AELITIUM-UNICODE-ND-RANGES-1`` bytes iteratively."""

    if type(source) is not bytes:
        raise TypeError("source must be bytes")
    if not source or not source.endswith(b"\n") or b"\r" in source:
        raise ValueError("range data must be non-empty LF-terminated ASCII")

    ranges: list[tuple[int, int]] = []
    previous_end: int | None = None
    for line in source.splitlines(keepends=True):
        if _RANGE_LINE.fullmatch(line) is None:
            raise ValueError("invalid frozen Unicode range line")
        start = int(line[0:6], 16)
        end = int(line[8:14], 16)
        if start > end or end > 0x10FFFF:
            raise ValueError("invalid Unicode range bounds")
        if previous_end is not None and start <= previous_end + 1:
            raise ValueError("ranges must be ascending and maximally coalesced")
        ranges.append((start, end))
        previous_end = end
    return tuple(ranges)


def _read_packaged_profile_bytes(range_file: str) -> bytes:
    """Read a frozen profile through installation-safe package resources."""

    return (
        resources.files("engine")
        .joinpath("data", "unicode", range_file)
        .read_bytes()
    )


def _prepare_unicode_profile(
    declaration: TimestampDigitProfileDeclaration,
) -> PreparedUnicodeProfile:
    if (
        type(declaration.profile_id) is not str
        or type(declaration.unicode_version) is not str
        or type(declaration.range_file_sha256) is not str
    ):
        _raise_capability_unavailable()
    metadata = _FROZEN_UNICODE_PROFILE_BY_ID.get(declaration.profile_id)
    if metadata is None:
        _raise_capability_unavailable()
    if (
        declaration.unicode_version != metadata.unicode_version
        or declaration.range_file_sha256 != metadata.range_file_sha256
    ):
        _raise_capability_unavailable()

    try:
        source = _read_packaged_profile_bytes(metadata.range_file)
    except OSError:
        _raise_capability_unavailable()
    actual_digest = hashlib.sha256(source).hexdigest()
    if actual_digest != metadata.range_file_sha256:
        _raise_capability_unavailable()

    try:
        ranges = parse_unicode_nd_ranges(source)
    except ValueError:
        _raise_capability_unavailable()
    if len(ranges) != metadata.range_count or sum(
        end - start + 1 for start, end in ranges
    ) != metadata.code_point_count:
        _raise_capability_unavailable()

    return PreparedUnicodeProfile(metadata, ranges, actual_digest)


def prepare_verifier_capabilities(
    request: VerifierCapabilityRequest,
) -> PreparedVerifierCapabilities:
    """Validate and authenticate a complete request before bundle acquisition."""

    validate_verifier_capability_request(request)
    _validate_dispatch(request.dispatch)
    named_profile = _validate_v1(request.v1)
    _validate_v2(request.v2)
    _validate_signature(request.signature_verification)
    prepared_profile = (
        _prepare_unicode_profile(named_profile) if named_profile is not None else None
    )
    return PreparedVerifierCapabilities(request, prepared_profile)


def validate_prepared_verifier_capabilities(
    candidate: PreparedVerifierCapabilities,
    requested: VerifierCapabilityRequest,
) -> None:
    """Check the complete preparation postcondition before effective selection.

    No preparation or resource read is repeated. In particular, authenticate
    the executable ranges themselves, not just the claimed digest. Invalid
    returns are implementation defects; resource exceptions retain their type.
    """

    if type(candidate) is not PreparedVerifierCapabilities or candidate.requested != requested:
        raise RuntimeError("invalid capability preparation result")
    try:
        validate_verifier_capability_request(candidate.requested)
        _validate_dispatch(requested.dispatch)
        declaration = _validate_v1(requested.v1)
        _validate_v2(requested.v2)
        _validate_signature(requested.signature_verification)
        profile = candidate.named_timestamp_profile
        if declaration is None:
            if profile is not None:
                raise ValueError("unexpected executable timestamp profile")
            return
        metadata = _FROZEN_UNICODE_PROFILE_BY_ID.get(declaration.profile_id)
        if (
            type(profile) is not PreparedUnicodeProfile
            or metadata is None
            or type(profile.metadata) is not FrozenUnicodeProfileMetadata
            or profile.metadata != metadata
            or declaration.unicode_version != metadata.unicode_version
            or declaration.range_file_sha256 != metadata.range_file_sha256
            or type(profile.actual_range_file_sha256) is not str
            or profile.actual_range_file_sha256 != metadata.range_file_sha256
            or type(profile.ranges) is not tuple
        ):
            raise ValueError("inconsistent executable timestamp profile")
        previous = -2
        count = 0
        digest = hashlib.sha256()
        for pair in profile.ranges:
            if type(pair) is not tuple or len(pair) != 2:
                raise ValueError("invalid executable range")
            start, end = pair
            if (type(start) is not int or type(end) is not int
                    or not 0 <= start <= end <= 0x10FFFF or start <= previous + 1):
                raise ValueError("invalid executable range")
            digest.update(f"{start:06X}..{end:06X}\n".encode("ascii"))
            count += end - start + 1
            previous = end
        if (len(profile.ranges) != metadata.range_count
                or count != metadata.code_point_count
                or digest.hexdigest() != metadata.range_file_sha256):
            raise ValueError("unauthenticated executable ranges")
    except (OperationalInputFailure, ValueError, TypeError, AttributeError) as error:
        raise RuntimeError("invalid capability preparation result") from error


def select_effective_route(
    prepared: PreparedVerifierCapabilities,
    dispatched_canonicalization_identifier: str | None,
) -> EffectiveVerifierRoute:
    """Select the configured route after exact manifest dispatch."""

    if type(prepared) is not PreparedVerifierCapabilities:
        raise TypeError("prepared must be PreparedVerifierCapabilities")
    if (
        type(dispatched_canonicalization_identifier) is str
        and dispatched_canonicalization_identifier == AI_CANONICALIZATION_V2
    ):
        return EffectiveVerifierRoute(
            AI_CANONICALIZATION_V2,
            prepared.requested.v2,
            None,
        )

    declaration = prepared.requested.v1
    if declaration.capability == V1_LEGACY_UNSUPPORTED:
        _raise_capability_unavailable(
            phase=OperationalPhase.DISPATCH,
            input_ref=InputRef.AI_MANIFEST_JSON,
        )
    return EffectiveVerifierRoute(
        AI_CANONICALIZATION,
        declaration,
        prepared.named_timestamp_profile,
    )


def select_signature_verification_profile(requested: str | None) -> str | None:
    """Select an explicit signature profile without aliases or fallback."""

    if requested is None:
        return None
    if requested == ED25519_PORTABLE_STRICT_1:
        return ED25519_PORTABLE_STRICT_1
    raise CapabilityProfileUnavailable(requested)


__all__ = [
    "ACCEPT_ONE_TIMESTAMP_FINAL_LF",
    "AELITIUM_DISPATCH_JSON_1",
    "ASCII_TIMESTAMP_DIGIT_PROFILE",
    "BOUNDED",
    "CapabilityProfileUnavailable",
    "CapabilityRequestValidationError",
    "DispatchCapabilityDeclaration",
    "ED25519_PORTABLE_STRICT_1",
    "EffectiveVerifierRoute",
    "FROZEN_UNICODE_PROFILES",
    "FrozenUnicodeProfileMetadata",
    "IntegerConversionDeclaration",
    "PreparedUnicodeProfile",
    "PreparedVerifierCapabilities",
    "SignatureVerificationDeclaration",
    "TimestampDigitProfileDeclaration",
    "UNLIMITED",
    "V1CapabilityDeclaration",
    "V1_FROZEN_LEGACY_COMPATIBILITY",
    "V1_LEGACY_UNSUPPORTED",
    "V1_NAMED_RUNTIME_COMPATIBILITY",
    "V1_RESTRICTED_PORTABLE",
    "V2CapabilityDeclaration",
    "V2_PORTABLE",
    "VerifierCapabilityRequest",
    "parse_unicode_nd_ranges",
    "prepare_verifier_capabilities",
    "select_effective_route",
    "select_signature_verification_profile",
    "validate_verifier_capability_request",
    "validate_prepared_verifier_capabilities",
]
