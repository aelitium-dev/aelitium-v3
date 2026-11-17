"""Machine-readable projections of the existing AELITIUM assurance semantics.

The serializers in this module do not perform verification. They project an
already-computed :class:`engine.ai_verify.AIVerificationResult` into versioned
result documents and reject combinations that the v0.4-compatible verifier
cannot emit.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .ai_contract import (
    AI_CANONICAL_FILENAME,
    AI_MANIFEST_SCHEMA,
    AI_MANIFEST_FILENAME,
    AI_OUTPUT_SCHEMA_VERSION,
    AI_VERIFICATION_KEYS_FILENAME,
)
from .ai_verify import AIVerificationOptions, AIVerificationResult, AssuranceState
from .canonical_v2 import V2CanonicalizationError, validate_v2_value
from .trust import TRUST_STORE_FORMAT
from .verifier_capabilities import (
    IntegerConversionDeclaration,
    TimestampDigitProfileDeclaration,
    V1CapabilityDeclaration,
    VerifierCapabilityRequest,
)
from .verifier_snapshot import (
    AELITIUM_MIN_MAX_FILE_BYTES,
    AELITIUM_MIN_MAX_STRUCTURAL_DEPTH,
    AELITIUM_MIN_MAX_TOTAL_SNAPSHOT_BYTES,
    AELITIUM_MIN_MAX_VALUE_OCCURRENCES,
    InputMode,
    LimitFact,
    OperationalCode,
    OperationalInputFailure,
    OperationalLimits,
    OperationalPhase,
)


VERIFICATION_RESULT_CONTRACT = "aelitium-verification-result-v1"
ASSURANCE_RESULT_CONTRACT = "aelitium-assurance-result-v1"
CLAIM_BOUNDARY_CONTRACT = "aelitium-claim-boundary-v1"
VERIFIER_TOOL_RESULT_CONTRACT = "aelitium-verifier-tool-result-v1"
VERIFY_BUNDLE_OPERATION = "VERIFY_BUNDLE"
AELITIUM_CLEANROOM_MINIMUM_1 = "AELITIUM_CLEANROOM_MINIMUM_1"

TRUST_INPUT_REF = "verification-input:trust-store"
FRESHNESS_POLICY_REF = "verification-input:freshness-policy"
MAX_PORTABLE_INTEGER = 9_007_199_254_740_991


class ClaimBoundary:
    """Closed code vocabulary for non-claims made by result contracts."""

    AUTHORIZATION_NOT_ESTABLISHED = "authorization_not_established"
    CAPTURE_COMPLETENESS_NOT_ESTABLISHED = "capture_completeness_not_established"
    COMPLETE_INVOCATION_IDENTITY_NOT_ESTABLISHED = (
        "complete_invocation_identity_not_established"
    )
    HISTORICAL_NON_MODIFICATION_NOT_ESTABLISHED = (
        "historical_non_modification_not_established"
    )
    HISTORICAL_OCCURRENCE_NOT_ESTABLISHED = (
        "historical_occurrence_not_established"
    )
    LEGAL_COMPLIANCE_NOT_ESTABLISHED = "legal_compliance_not_established"
    MODEL_DRIFT_NOT_ESTABLISHED = "model_drift_not_established"
    PROVIDER_EXECUTION_NOT_ESTABLISHED = "provider_execution_not_established"
    PROVIDER_FAULT_NOT_ESTABLISHED = "provider_fault_not_established"
    QUALITY_DEGRADATION_NOT_ESTABLISHED = "quality_degradation_not_established"
    REGRESSION_NOT_ESTABLISHED = "regression_not_established"
    RESPONSE_CAUSATION_NOT_ESTABLISHED = "response_causation_not_established"
    SEMANTIC_EQUIVALENCE_NOT_ESTABLISHED = (
        "semantic_equivalence_not_established"
    )
    SEMANTIC_TRUTH_NOT_ESTABLISHED = "semantic_truth_not_established"
    TRUSTED_HISTORICAL_TIME_NOT_ESTABLISHED = (
        "trusted_historical_time_not_established"
    )
    TRUSTED_SIGNER_IDENTITY_NOT_ESTABLISHED_BY_SIGNATURE = (
        "trusted_signer_identity_not_established_by_signature"
    )


CLAIM_BOUNDARY_VOCABULARY = frozenset(
    value
    for name, value in vars(ClaimBoundary).items()
    if name.isupper() and isinstance(value, str)
)


VERIFICATION_CLAIM_BOUNDARIES = (
    ClaimBoundary.PROVIDER_EXECUTION_NOT_ESTABLISHED,
    ClaimBoundary.RESPONSE_CAUSATION_NOT_ESTABLISHED,
    ClaimBoundary.SEMANTIC_TRUTH_NOT_ESTABLISHED,
    ClaimBoundary.CAPTURE_COMPLETENESS_NOT_ESTABLISHED,
    ClaimBoundary.HISTORICAL_OCCURRENCE_NOT_ESTABLISHED,
    ClaimBoundary.HISTORICAL_NON_MODIFICATION_NOT_ESTABLISHED,
    ClaimBoundary.AUTHORIZATION_NOT_ESTABLISHED,
    ClaimBoundary.TRUSTED_HISTORICAL_TIME_NOT_ESTABLISHED,
    ClaimBoundary.LEGAL_COMPLIANCE_NOT_ESTABLISHED,
    ClaimBoundary.COMPLETE_INVOCATION_IDENTITY_NOT_ESTABLISHED,
)

COMPARISON_CLAIM_BOUNDARIES = (
    ClaimBoundary.MODEL_DRIFT_NOT_ESTABLISHED,
    ClaimBoundary.REGRESSION_NOT_ESTABLISHED,
    ClaimBoundary.QUALITY_DEGRADATION_NOT_ESTABLISHED,
    ClaimBoundary.SEMANTIC_EQUIVALENCE_NOT_ESTABLISHED,
    ClaimBoundary.RESPONSE_CAUSATION_NOT_ESTABLISHED,
    ClaimBoundary.PROVIDER_FAULT_NOT_ESTABLISHED,
    ClaimBoundary.PROVIDER_EXECUTION_NOT_ESTABLISHED,
    ClaimBoundary.COMPLETE_INVOCATION_IDENTITY_NOT_ESTABLISHED,
)


@dataclass(frozen=True)
class _DimensionDefinition:
    states: frozenset[AssuranceState]
    basis: str
    evidence_refs: tuple[str, ...]
    claim_boundaries: tuple[str, ...]


_CANONICAL_REF = f"bundle:{AI_CANONICAL_FILENAME}"
_MANIFEST_REF = f"bundle:{AI_MANIFEST_FILENAME}"
_VERIFICATION_KEYS_REF = f"bundle:{AI_VERIFICATION_KEYS_FILENAME}"


_DIMENSIONS: dict[str, _DimensionDefinition] = {
    "payload_integrity": _DimensionDefinition(
        states=frozenset(
            {
                AssuranceState.VALID,
                AssuranceState.INVALID,
                AssuranceState.ABSENT,
                AssuranceState.NOT_EVALUATED,
            }
        ),
        basis="ai_output_v1_canonical_manifest_digest_consistency",
        evidence_refs=(_CANONICAL_REF, _MANIFEST_REF),
        claim_boundaries=(
            ClaimBoundary.HISTORICAL_OCCURRENCE_NOT_ESTABLISHED,
            ClaimBoundary.HISTORICAL_NON_MODIFICATION_NOT_ESTABLISHED,
            ClaimBoundary.SEMANTIC_TRUTH_NOT_ESTABLISHED,
            ClaimBoundary.CAPTURE_COMPLETENESS_NOT_ESTABLISHED,
        ),
    ),
    "binding_field_consistency": _DimensionDefinition(
        states=frozenset(
            {
                AssuranceState.VALID,
                AssuranceState.INVALID,
                AssuranceState.ABSENT,
                AssuranceState.NOT_EVALUATED,
            }
        ),
        basis="stored_request_response_binding_field_consistency",
        evidence_refs=(
            f"{_CANONICAL_REF}#/metadata/request_hash",
            f"{_CANONICAL_REF}#/metadata/response_hash",
            f"{_CANONICAL_REF}#/metadata/binding_hash",
            f"{_MANIFEST_REF}#/binding_hash",
        ),
        claim_boundaries=(
            ClaimBoundary.RESPONSE_CAUSATION_NOT_ESTABLISHED,
            ClaimBoundary.PROVIDER_EXECUTION_NOT_ESTABLISHED,
            ClaimBoundary.HISTORICAL_OCCURRENCE_NOT_ESTABLISHED,
        ),
    ),
    "invocation_identity_consistency": _DimensionDefinition(
        states=frozenset(
            {
                AssuranceState.VALID,
                AssuranceState.INVALID,
                AssuranceState.ABSENT,
                AssuranceState.NOT_EVALUATED,
            }
        ),
        basis="aelitium-invocation-v1_recomputation",
        evidence_refs=(f"{_CANONICAL_REF}#/metadata/invocation_identity",),
        claim_boundaries=(
            ClaimBoundary.PROVIDER_EXECUTION_NOT_ESTABLISHED,
            ClaimBoundary.COMPLETE_INVOCATION_IDENTITY_NOT_ESTABLISHED,
            ClaimBoundary.RESPONSE_CAUSATION_NOT_ESTABLISHED,
            ClaimBoundary.HISTORICAL_OCCURRENCE_NOT_ESTABLISHED,
        ),
    ),
    "invocation_binding_consistency": _DimensionDefinition(
        states=frozenset(
            {
                AssuranceState.VALID,
                AssuranceState.INVALID,
                AssuranceState.ABSENT,
                AssuranceState.NOT_EVALUATED,
            }
        ),
        basis="aelitium-invocation-binding-v1_recomputation_and_bundle_linkage",
        evidence_refs=(
            f"{_CANONICAL_REF}#/metadata/invocation_binding",
            f"{_CANONICAL_REF}#/metadata/invocation_identity/hash_sha256",
            f"{_CANONICAL_REF}#/metadata/response_hash",
        ),
        claim_boundaries=(
            ClaimBoundary.RESPONSE_CAUSATION_NOT_ESTABLISHED,
            ClaimBoundary.PROVIDER_EXECUTION_NOT_ESTABLISHED,
            ClaimBoundary.HISTORICAL_OCCURRENCE_NOT_ESTABLISHED,
        ),
    ),
    "signature_validity": _DimensionDefinition(
        states=frozenset(
            {
                AssuranceState.VALID,
                AssuranceState.INVALID,
                AssuranceState.ABSENT,
                AssuranceState.NOT_EVALUATED,
            }
        ),
        basis="ed25519_manifest_signature_verification",
        evidence_refs=(_MANIFEST_REF, _VERIFICATION_KEYS_REF),
        claim_boundaries=(
            ClaimBoundary.TRUSTED_SIGNER_IDENTITY_NOT_ESTABLISHED_BY_SIGNATURE,
            ClaimBoundary.AUTHORIZATION_NOT_ESTABLISHED,
            ClaimBoundary.HISTORICAL_OCCURRENCE_NOT_ESTABLISHED,
        ),
    ),
    "trusted_signer_identity": _DimensionDefinition(
        states=frozenset(
            {AssuranceState.VALID, AssuranceState.UNESTABLISHED}
        ),
        basis=(
            "verified_ed25519_key_fingerprint_membership_in_explicit_"
            "aelitium-trust-v1"
        ),
        evidence_refs=(_VERIFICATION_KEYS_REF,),
        claim_boundaries=(
            ClaimBoundary.AUTHORIZATION_NOT_ESTABLISHED,
            ClaimBoundary.PROVIDER_EXECUTION_NOT_ESTABLISHED,
            ClaimBoundary.HISTORICAL_OCCURRENCE_NOT_ESTABLISHED,
            ClaimBoundary.TRUSTED_HISTORICAL_TIME_NOT_ESTABLISHED,
        ),
    ),
    "freshness": _DimensionDefinition(
        states=frozenset(
            {
                AssuranceState.VALID,
                AssuranceState.INVALID,
                AssuranceState.UNESTABLISHED,
                AssuranceState.NOT_EVALUATED,
            }
        ),
        basis="declared_canonical_timestamp_recency_under_explicit_policy",
        evidence_refs=(f"{_CANONICAL_REF}#/ts_utc",),
        claim_boundaries=(
            ClaimBoundary.TRUSTED_HISTORICAL_TIME_NOT_ESTABLISHED,
            ClaimBoundary.HISTORICAL_OCCURRENCE_NOT_ESTABLISHED,
            ClaimBoundary.HISTORICAL_NON_MODIFICATION_NOT_ESTABLISHED,
            ClaimBoundary.PROVIDER_EXECUTION_NOT_ESTABLISHED,
            ClaimBoundary.RESPONSE_CAUSATION_NOT_ESTABLISHED,
        ),
    ),
    "authorization": _DimensionDefinition(
        states=frozenset({AssuranceState.NOT_EVALUATED}),
        basis="not_implemented_in_v0.4-compatible_semantics",
        evidence_refs=(),
        claim_boundaries=(ClaimBoundary.AUTHORIZATION_NOT_ESTABLISHED,),
    ),
}

ASSURANCE_DIMENSIONS = tuple(_DIMENSIONS)
ASSURANCE_REACHABLE_STATES = {
    name: tuple(state.value for state in AssuranceState if state in definition.states)
    for name, definition in _DIMENSIONS.items()
}

_SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ResultContractError(ValueError):
    """Raised when a result cannot be represented without semantic invention."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


def _project_portable_detail(value: Any) -> str | None:
    """Preserve an exact public diagnostic only inside the portable domain."""

    if type(value) is not str or value == "":
        return None
    try:
        validate_v2_value(value)
    except V2CanonicalizationError:
        return None
    return value


def _validate_outer_portable_value(value: Any) -> None:
    """Enforce the portable value domain before an outer result can exist."""

    try:
        validate_v2_value(value)
    except V2CanonicalizationError as error:
        raise ResultContractError(
            "VERIFIER_TOOL_RESULT_NOT_PORTABLE",
            "outer result is outside the portable value domain",
        ) from error

    # The outer schemas authorize integer-valued numbers only.  The shared v2
    # validator admits finite binary64 values for v2 bundle canonicalization,
    # so exclude floats here with an iterative, host-recursion-independent pass.
    work = [value]
    while work:
        member = work.pop()
        if type(member) is float:
            raise ResultContractError(
                "VERIFIER_TOOL_RESULT_NOT_PORTABLE",
                "outer result is outside the portable value domain",
            )
        if type(member) is list:
            work.extend(member)
        elif type(member) is dict:
            work.extend(member.values())


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze_json(member) for key, member in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_json(member) for member in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(member) for key, member in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(member) for member in value]
    return value


@dataclass(frozen=True, slots=True)
class VerifierLimitState:
    """Claimed, advertised, and enforced limits for one operation."""

    claimed_envelope: str | None
    advertised: OperationalLimits
    effective: OperationalLimits

    def __post_init__(self) -> None:
        if self.claimed_envelope not in {AELITIUM_CLEANROOM_MINIMUM_1, None}:
            raise ValueError("unsupported verifier limit envelope")
        if type(self.advertised) is not OperationalLimits:
            raise TypeError("advertised must be OperationalLimits")
        if type(self.effective) is not OperationalLimits:
            raise TypeError("effective must be OperationalLimits")

        names = (
            "max_file_bytes",
            "max_total_snapshot_bytes",
            "max_structural_depth",
            "max_value_occurrences",
        )
        if any(
            getattr(self.effective, name) > getattr(self.advertised, name)
            for name in names
        ):
            raise ValueError("effective limits must not exceed advertised limits")

        if self.claimed_envelope == AELITIUM_CLEANROOM_MINIMUM_1:
            floors = {
                "max_file_bytes": AELITIUM_MIN_MAX_FILE_BYTES,
                "max_total_snapshot_bytes": AELITIUM_MIN_MAX_TOTAL_SNAPSHOT_BYTES,
                "max_structural_depth": AELITIUM_MIN_MAX_STRUCTURAL_DEPTH,
                "max_value_occurrences": AELITIUM_MIN_MAX_VALUE_OCCURRENCES,
            }
            for limits in (self.advertised, self.effective):
                if any(
                    getattr(limits, name) < minimum
                    for name, minimum in floors.items()
                ):
                    raise ValueError(
                        "claimed minimum envelope requires every advertised "
                        "and effective minimum"
                    )


@dataclass(frozen=True, slots=True)
class VerifierOperationalResult:
    """Typed public projection of one operational failure."""

    failure: OperationalInputFailure

    def __post_init__(self) -> None:
        if type(self.failure) is not OperationalInputFailure:
            raise TypeError("failure must be OperationalInputFailure")


@dataclass(frozen=True, slots=True)
class VerifierToolResult:
    """Immutable branch selection for one verifier tool result.

    ``to_json_value`` is the single conversion point to the closed public JSON
    shape.  Nested semantic result data is copied on every projection so callers
    cannot mutate the operation record through the returned JSON value.
    """

    input_mode: InputMode
    requested_capability: VerifierCapabilityRequest
    effective_capability: VerifierCapabilityRequest | None
    limits: VerifierLimitState
    verification_result: Mapping[str, Any] | None
    operational_result: VerifierOperationalResult | None

    @staticmethod
    def _null_effective_allowed(failure: OperationalInputFailure) -> bool:
        if failure.operational_code is OperationalCode.CAPABILITY_PROFILE_UNAVAILABLE:
            return True
        return (
            failure.operational_code in {
                OperationalCode.INTERNAL_OPERATION_ERROR,
                OperationalCode.RESOURCE_EXHAUSTED,
            }
            and failure.phase in {
                OperationalPhase.CAPABILITY_SELECTION,
                OperationalPhase.OUTPUT,
            }
        )

    @classmethod
    def emergency_operational(
        cls,
        *,
        input_mode: InputMode,
        requested_capability: VerifierCapabilityRequest,
        effective_capability: VerifierCapabilityRequest | None,
        limits: VerifierLimitState,
        failure: OperationalInputFailure,
    ) -> VerifierToolResult:
        """Construct a closed operational record without normal projection.

        Callers have already validated the operation envelope. This narrow
        constructor is used only after the normal constructor or an output
        preflight has failed; invoking ``__post_init__`` here would repeat the
        projection that may have caused the failure.
        """

        if (
            type(input_mode) is not InputMode
            or type(requested_capability) is not VerifierCapabilityRequest
            or type(limits) is not VerifierLimitState
            or type(failure) is not OperationalInputFailure
        ):
            raise TypeError("invalid emergency operation envelope")
        if effective_capability is None:
            if not cls._null_effective_allowed(failure):
                raise ValueError("failure does not permit an unselected capability")
        elif (
            type(effective_capability) is not VerifierCapabilityRequest
            or effective_capability != requested_capability
            or failure.operational_code is OperationalCode.CAPABILITY_PROFILE_UNAVAILABLE
        ):
            raise ValueError("invalid selected emergency capability")

        record = object.__new__(cls)
        object.__setattr__(record, "input_mode", input_mode)
        object.__setattr__(record, "requested_capability", requested_capability)
        object.__setattr__(record, "effective_capability", effective_capability)
        object.__setattr__(record, "limits", limits)
        object.__setattr__(record, "verification_result", None)
        operational = object.__new__(VerifierOperationalResult)
        object.__setattr__(operational, "failure", failure)
        object.__setattr__(record, "operational_result", operational)
        return record

    def __post_init__(self) -> None:
        if type(self.input_mode) is not InputMode:
            raise TypeError("input_mode must be InputMode")
        if type(self.requested_capability) is not VerifierCapabilityRequest:
            raise TypeError("requested_capability must be VerifierCapabilityRequest")
        if self.effective_capability is not None and (
            type(self.effective_capability) is not VerifierCapabilityRequest
        ):
            raise TypeError(
                "effective_capability must be VerifierCapabilityRequest or None"
            )
        if type(self.limits) is not VerifierLimitState:
            raise TypeError("limits must be VerifierLimitState")

        if self.verification_result is not None:
            if not isinstance(self.verification_result, Mapping):
                raise TypeError("verification_result must be a JSON object or None")
            object.__setattr__(
                self,
                "verification_result",
                _freeze_json(dict(self.verification_result)),
            )

        semantic = self.verification_result is not None
        operational = self.operational_result is not None
        if semantic == operational:
            raise ValueError(
                "exactly one verification_result or operational_result is required"
            )
        if semantic:
            if self.effective_capability != self.requested_capability:
                raise ValueError(
                    "semantic results require requested/effective deep equality"
                )
            if self.verification_result.get("status") not in {"VALID", "INVALID"}:
                raise ValueError("semantic result status must be VALID or INVALID")
        else:
            assert self.operational_result is not None
            failure = self.operational_result.failure
            if self._null_effective_allowed(failure):
                if self.effective_capability is None:
                    pass
                elif failure.operational_code is OperationalCode.CAPABILITY_PROFILE_UNAVAILABLE:
                    raise ValueError("unavailable capability requires effective capability null")
                elif self.effective_capability != self.requested_capability:
                    raise ValueError("selected capability must equal requested capability")
            elif self.effective_capability != self.requested_capability:
                raise ValueError(
                    "operational results require requested/effective deep equality"
                )

        _validate_outer_portable_value(self.to_json_value())

    @property
    def outcome(self) -> str:
        return (
            "SEMANTIC_RESULT"
            if self.verification_result is not None
            else "OPERATIONAL_OUTCOME"
        )

    @property
    def rc(self) -> int:
        if self.operational_result is not None:
            return 3
        assert self.verification_result is not None
        return 0 if self.verification_result["status"] == "VALID" else 2

    def to_json_value(self) -> dict[str, Any]:
        """Return a fresh JSON value matching the strict outer schema."""

        return {
            "contract": VERIFIER_TOOL_RESULT_CONTRACT,
            "operation": VERIFY_BUNDLE_OPERATION,
            "outcome": self.outcome,
            "rc": self.rc,
            "input_mode": self.input_mode.value,
            "capability": {
                "requested": project_capability_request(
                    self.requested_capability
                ),
                "effective": (
                    project_capability_request(self.effective_capability)
                    if self.effective_capability is not None
                    else None
                ),
            },
            "limits": project_verifier_limit_state(self.limits),
            "verification_result": _thaw_json(self.verification_result),
            "operational_result": (
                project_operational_result(self.operational_result.failure)
                if self.operational_result is not None
                else None
            ),
        }


def _project_integer_conversion(
    declaration: IntegerConversionDeclaration,
) -> dict[str, Any]:
    return {
        "mode": declaration.mode,
        "maximum_decimal_digits": declaration.maximum_decimal_digits,
    }


def _project_v1_capability(
    declaration: V1CapabilityDeclaration,
) -> dict[str, Any]:
    projected: dict[str, Any] = {"capability": declaration.capability}
    if declaration.integer_conversion is not None:
        projected["integer_conversion"] = _project_integer_conversion(
            declaration.integer_conversion
        )
    if isinstance(
        declaration.timestamp_digit_profile,
        TimestampDigitProfileDeclaration,
    ):
        projected["timestamp_digit_profile"] = {
            "profile_id": declaration.timestamp_digit_profile.profile_id,
            "range_file_sha256": (
                declaration.timestamp_digit_profile.range_file_sha256
            ),
            "unicode_version": declaration.timestamp_digit_profile.unicode_version,
        }
    elif declaration.timestamp_digit_profile is not None:
        projected["timestamp_digit_profile"] = declaration.timestamp_digit_profile
    if declaration.timestamp_final_lf is not None:
        projected["timestamp_final_lf"] = declaration.timestamp_final_lf
    return projected


def project_capability_request(
    request: VerifierCapabilityRequest,
) -> dict[str, Any]:
    """Project an explicit request without interpreting the selected route."""

    if type(request) is not VerifierCapabilityRequest:
        raise TypeError("request must be VerifierCapabilityRequest")
    return {
        "dispatch": request.dispatch.dispatch,
        "v1": _project_v1_capability(request.v1),
        "v2": {"capability": request.v2.capability},
        "signature_verification": {
            "profile": request.signature_verification.profile,
        },
    }


def _project_limits(limits: OperationalLimits) -> dict[str, int]:
    return {
        "max_file_bytes": limits.max_file_bytes,
        "max_total_snapshot_bytes": limits.max_total_snapshot_bytes,
        "max_structural_depth": limits.max_structural_depth,
        "max_value_occurrences": limits.max_value_occurrences,
    }


def project_verifier_limit_state(state: VerifierLimitState) -> dict[str, Any]:
    """Project exactly the configuration used by the operation."""

    if type(state) is not VerifierLimitState:
        raise TypeError("state must be VerifierLimitState")
    return {
        "claimed_envelope": state.claimed_envelope,
        "advertised": _project_limits(state.advertised),
        "effective": _project_limits(state.effective),
    }


def _project_limit_fact(fact: LimitFact | None) -> dict[str, Any] | None:
    if fact is None:
        return None
    return {
        "name": fact.name.value,
        "unit": fact.unit.value,
        "maximum": fact.maximum,
        "observed_at_least": fact.observed_at_least,
    }


def project_operational_result(
    failure: OperationalInputFailure,
) -> dict[str, Any]:
    """Project stable operational facts and discard non-normative host detail."""

    if type(failure) is not OperationalInputFailure:
        raise TypeError("failure must be OperationalInputFailure")
    return {
        "operational_code": failure.operational_code.value,
        "phase": failure.phase.value,
        "input_ref": failure.input_ref.value if failure.input_ref is not None else None,
        "limit": _project_limit_fact(failure.limit),
        "detail": None,
    }


def _state(result: AIVerificationResult, dimension: str) -> AssuranceState:
    value = getattr(result, dimension, None)
    if not isinstance(value, AssuranceState):
        raise ResultContractError(
            "ASSURANCE_STATE_TYPE_INVALID",
            f"{dimension} must be an AssuranceState",
        )
    if value not in _DIMENSIONS[dimension].states:
        raise ResultContractError(
            "ASSURANCE_STATE_UNREACHABLE",
            f"{dimension}={value.value}",
        )
    return value


def validate_assurance_invariants(
    result: AIVerificationResult,
    *,
    trust_store_provided: bool,
) -> None:
    """Reject state combinations unreachable from the v0.4-compatible kernel."""

    states = {name: _state(result, name) for name in ASSURANCE_DIMENSIONS}

    if (
        states["trusted_signer_identity"] is AssuranceState.VALID
        and states["signature_validity"] is not AssuranceState.VALID
    ):
        raise ResultContractError(
            "ASSURANCE_INVARIANT_FAILED",
            "trusted_signer_identity=VALID requires signature_validity=VALID",
        )
    if (
        states["trusted_signer_identity"] is AssuranceState.VALID
        and not trust_store_provided
    ):
        raise ResultContractError(
            "ASSURANCE_INVARIANT_FAILED",
            "trusted_signer_identity=VALID requires an explicit trust input",
        )
    if (
        states["invocation_binding_consistency"] is AssuranceState.VALID
        and states["invocation_identity_consistency"] is not AssuranceState.VALID
    ):
        raise ResultContractError(
            "ASSURANCE_INVARIANT_FAILED",
            "invocation_binding_consistency=VALID requires "
            "invocation_identity_consistency=VALID",
        )

    payload = states["payload_integrity"]
    evaluated_after_payload = (
        "binding_field_consistency",
        "invocation_identity_consistency",
        "invocation_binding_consistency",
        "freshness",
    )
    if payload is not AssuranceState.VALID:
        for name in evaluated_after_payload:
            if states[name] in {AssuranceState.VALID, AssuranceState.INVALID}:
                raise ResultContractError(
                    "ASSURANCE_INVARIANT_FAILED",
                    f"{name} cannot be evaluated before payload_integrity=VALID",
                )
        if states["signature_validity"] in {
            AssuranceState.VALID,
            AssuranceState.INVALID,
        }:
            raise ResultContractError(
                "ASSURANCE_INVARIANT_FAILED",
                "signature_validity cannot be evaluated before "
                "payload_integrity=VALID",
            )
        if (
            payload is AssuranceState.NOT_EVALUATED
            and states["signature_validity"] is not AssuranceState.NOT_EVALUATED
        ):
            raise ResultContractError(
                "ASSURANCE_INVARIANT_FAILED",
                "signature_validity must remain NOT_EVALUATED when input "
                "validation precedes artifact inspection",
            )

        for name in (
            "binding_field_consistency",
            "invocation_identity_consistency",
            "invocation_binding_consistency",
        ):
            if states[name] is not AssuranceState.NOT_EVALUATED:
                raise ResultContractError(
                    "ASSURANCE_INVARIANT_FAILED",
                    f"{name} must remain NOT_EVALUATED before "
                    "payload_integrity=VALID",
                )
        if (
            payload is not AssuranceState.NOT_EVALUATED
            and states["freshness"] is not AssuranceState.NOT_EVALUATED
        ):
            raise ResultContractError(
                "ASSURANCE_INVARIANT_FAILED",
                "freshness must remain NOT_EVALUATED after an artifact-level "
                "payload failure",
            )
    else:
        for name in (
            "binding_field_consistency",
            "invocation_identity_consistency",
            "invocation_binding_consistency",
            "signature_validity",
        ):
            if states[name] is AssuranceState.NOT_EVALUATED:
                raise ResultContractError(
                    "ASSURANCE_INVARIANT_FAILED",
                    f"{name} cannot remain NOT_EVALUATED after "
                    "payload_integrity=VALID",
                )
        if states["freshness"] is AssuranceState.UNESTABLISHED:
            raise ResultContractError(
                "ASSURANCE_INVARIANT_FAILED",
                "freshness=UNESTABLISHED is an input-policy failure that "
                "precedes payload evaluation",
            )

    if result.valid:
        if result.reason != "OK":
            raise ResultContractError(
                "VERIFICATION_RESULT_INVARIANT_FAILED",
                "successful verification requires reason=OK",
            )
        required_success_states = {
            "payload_integrity": {AssuranceState.VALID},
            "binding_field_consistency": {
                AssuranceState.VALID,
                AssuranceState.ABSENT,
            },
            "invocation_identity_consistency": {
                AssuranceState.VALID,
                AssuranceState.ABSENT,
            },
            "invocation_binding_consistency": {
                AssuranceState.VALID,
                AssuranceState.ABSENT,
            },
            "signature_validity": {AssuranceState.VALID, AssuranceState.ABSENT},
            "trusted_signer_identity": {
                AssuranceState.VALID,
                AssuranceState.UNESTABLISHED,
            },
            "freshness": {AssuranceState.VALID, AssuranceState.NOT_EVALUATED},
            "authorization": {AssuranceState.NOT_EVALUATED},
        }
        for name, allowed in required_success_states.items():
            if states[name] not in allowed:
                raise ResultContractError(
                    "ASSURANCE_INVARIANT_FAILED",
                    f"successful verification cannot contain "
                    f"{name}={states[name].value}",
                )

        invocation_pair = (
            states["invocation_identity_consistency"],
            states["invocation_binding_consistency"],
        )
        if invocation_pair not in {
            (AssuranceState.ABSENT, AssuranceState.ABSENT),
            (AssuranceState.VALID, AssuranceState.ABSENT),
            (AssuranceState.VALID, AssuranceState.VALID),
        }:
            raise ResultContractError(
                "ASSURANCE_INVARIANT_FAILED",
                "successful verification has an impossible invocation state pair",
            )
    elif result.reason == "OK":
        raise ResultContractError(
            "VERIFICATION_RESULT_INVARIANT_FAILED",
            "invalid verification cannot use reason=OK",
        )

    if states["payload_integrity"] is AssuranceState.VALID and (
        not isinstance(result.ai_hash_sha256, str)
        or not _SHA256_HEX_PATTERN.fullmatch(result.ai_hash_sha256)
    ):
        raise ResultContractError(
            "VERIFICATION_RESULT_INVARIANT_FAILED",
            "payload_integrity=VALID requires a lowercase SHA-256 payload digest",
        )
    if (
        states["payload_integrity"] is not AssuranceState.VALID
        and result.ai_hash_sha256 is not None
    ):
        raise ResultContractError(
            "VERIFICATION_RESULT_INVARIANT_FAILED",
            "a canonical-payload digest cannot be emitted before "
            "payload_integrity=VALID",
        )


def build_artifact_ref(result: AIVerificationResult) -> dict[str, Any]:
    """Reference bundle components without claiming a directory digest."""

    digest = None
    if result.ai_hash_sha256 is not None:
        digest = {
            "algorithm": "sha256",
            "scope": "canonical_payload",
            "value": result.ai_hash_sha256,
        }
    return {
        "artifact_type": "ai_evidence_bundle",
        "expected_payload_schema": AI_OUTPUT_SCHEMA_VERSION,
        "expected_manifest_schema": AI_MANIFEST_SCHEMA,
        "canonical_ref": _CANONICAL_REF,
        "manifest_ref": _MANIFEST_REF,
        "canonical_payload_digest": digest,
    }


def build_assurance_result(
    result: AIVerificationResult,
    *,
    options: AIVerificationOptions | None = None,
    trust_store_provided: bool | None = None,
) -> dict[str, Any]:
    """Build ``aelitium-assurance-result-v1`` from a verified result."""

    selected = options or AIVerificationOptions()
    if (
        trust_store_provided is not None
        and type(trust_store_provided) is not bool
    ):
        raise TypeError("trust_store_provided must be bool or None")
    explicit_trust = (
        selected.trust_store_path is not None
        if trust_store_provided is None
        else trust_store_provided
    )
    validate_assurance_invariants(
        result,
        trust_store_provided=explicit_trust,
    )
    freshness_policy_provided = (
        selected.freshness_max_age_seconds is not None
        or selected.freshness_reference_time_utc is not None
    )

    dimensions = []
    for name, definition in _DIMENSIONS.items():
        trust_refs = (
            [TRUST_INPUT_REF]
            if name == "trusted_signer_identity" and explicit_trust
            else []
        )
        policy_ref = (
            FRESHNESS_POLICY_REF
            if name == "freshness" and freshness_policy_provided
            else None
        )
        dimensions.append(
            {
                "dimension": name,
                "state": _state(result, name).value,
                "basis": definition.basis,
                "evidence_refs": list(definition.evidence_refs),
                "trust_input_refs": trust_refs,
                "policy_ref": policy_ref,
                "claim_boundaries": list(definition.claim_boundaries),
            }
        )

    return {
        "contract": ASSURANCE_RESULT_CONTRACT,
        "dimensions": dimensions,
        "claim_boundary_contract": CLAIM_BOUNDARY_CONTRACT,
        "claim_boundaries": list(VERIFICATION_CLAIM_BOUNDARIES),
    }


def _trust_inputs(trust_store_provided: bool) -> list[dict[str, Any]]:
    if not trust_store_provided:
        return []
    return [
        {
            "ref": TRUST_INPUT_REF,
            "format": TRUST_STORE_FORMAT,
            "source": "explicit_local_file",
        }
    ]


def _policy_inputs(options: AIVerificationOptions) -> list[dict[str, Any]]:
    if (
        options.freshness_max_age_seconds is None
        and options.freshness_reference_time_utc is None
    ):
        return []
    return [
        {
            "ref": FRESHNESS_POLICY_REF,
            "kind": "declared_time_freshness_v1",
            "maximum_age_seconds": options.freshness_max_age_seconds,
            "reference_time_utc": options.freshness_reference_time_utc,
        }
    ]


def build_verification_result(
    result: AIVerificationResult,
    *,
    options: AIVerificationOptions | None = None,
    trust_store_provided: bool | None = None,
) -> dict[str, Any]:
    """Build ``aelitium-verification-result-v1`` deterministically."""

    selected = options or AIVerificationOptions()
    if (
        trust_store_provided is not None
        and type(trust_store_provided) is not bool
    ):
        raise TypeError("trust_store_provided must be bool or None")
    explicit_trust = (
        selected.trust_store_path is not None
        if trust_store_provided is None
        else trust_store_provided
    )
    assurance = build_assurance_result(
        result,
        options=selected,
        trust_store_provided=explicit_trust,
    )
    return {
        "contract": VERIFICATION_RESULT_CONTRACT,
        "artifact": build_artifact_ref(result),
        "status": "VALID" if result.valid else "INVALID",
        "rc": 0 if result.valid else 2,
        "reason": result.reason,
        "detail": _project_portable_detail(result.detail),
        "assurance": assurance,
        "verification_inputs": {
            "validate_manifest_timestamp": selected.validate_manifest_timestamp,
            "require_signature": selected.require_signature,
            "require_binding": selected.require_binding,
            "require_trusted_signer": selected.require_trusted_signer,
        },
        "trust_inputs": _trust_inputs(explicit_trust),
        "policy_inputs": _policy_inputs(selected),
        "claim_boundary_contract": CLAIM_BOUNDARY_CONTRACT,
        "claim_boundaries": list(VERIFICATION_CLAIM_BOUNDARIES),
    }


def build_verifier_tool_result(
    *,
    input_mode: InputMode,
    requested_capability: VerifierCapabilityRequest,
    effective_capability: VerifierCapabilityRequest | None,
    limits: VerifierLimitState,
    verification: AIVerificationResult | None = None,
    operational_failure: OperationalInputFailure | None = None,
    options: AIVerificationOptions | None = None,
    trust_store_provided: bool = False,
) -> VerifierToolResult:
    """Build exactly one semantic or operational outer result branch."""

    if (verification is None) == (operational_failure is None):
        raise ValueError(
            "exactly one verification or operational_failure is required"
        )
    if type(trust_store_provided) is not bool:
        raise TypeError("trust_store_provided must be bool")
    verification_value = (
        build_verification_result(
            verification,
            options=options,
            trust_store_provided=trust_store_provided,
        )
        if verification is not None
        else None
    )
    operational_value = (
        VerifierOperationalResult(operational_failure)
        if operational_failure is not None
        else None
    )
    return VerifierToolResult(
        input_mode=input_mode,
        requested_capability=requested_capability,
        effective_capability=effective_capability,
        limits=limits,
        verification_result=verification_value,
        operational_result=operational_value,
    )


def serialize_verifier_tool_result(result: VerifierToolResult) -> bytes:
    """Serialize one outer result as RFC 8785 canonical JSON plus one LF."""

    if type(result) is not VerifierToolResult:
        raise TypeError("result must be VerifierToolResult")
    try:
        import rfc8785
    except ModuleNotFoundError as error:
        raise ResultContractError(
            "VERIFIER_TOOL_RESULT_SERIALIZATION_UNAVAILABLE",
            "rfc8785 dependency is unavailable",
        ) from error
    try:
        canonical = rfc8785.dumps(result.to_json_value())
    except rfc8785.CanonicalizationError as error:
        raise ResultContractError(
            "VERIFIER_TOOL_RESULT_NOT_PORTABLE",
            "outer result cannot be represented by RFC 8785",
        ) from error
    return canonical + b"\n"


def build_verification_summary(result: AIVerificationResult) -> dict[str, Any]:
    """Build the bounded per-side summary embedded by compare JSON."""

    states: dict[str, str] = {}
    for name in ASSURANCE_DIMENSIONS:
        value = getattr(result, name, AssuranceState.NOT_EVALUATED)
        states[name] = value.value if isinstance(value, AssuranceState) else str(value)
    return {
        "status": "VALID" if result.valid else "INVALID",
        "reason": result.reason,
        "assurance_states": states,
    }


def build_comparison_contract_fields(
    *,
    result_a: AIVerificationResult,
    result_b: AIVerificationResult,
    status: str,
    response_relationship: str | None,
) -> dict[str, Any]:
    """Return additive fields for the existing ``aelitium-compare-v1`` JSON."""

    comparable_statuses = {"UNCHANGED", "CHANGED", "NOT_COMPARABLE"}
    if status not in comparable_statuses | {"INVALID_BUNDLE"}:
        raise ResultContractError(
            "COMPARISON_STATUS_INVALID",
            status,
        )
    expected_relationship = {
        "UNCHANGED": "SAME",
        "CHANGED": "DIFFERENT",
        "NOT_COMPARABLE": None,
        "INVALID_BUNDLE": None,
    }[status]
    if response_relationship != expected_relationship:
        raise ResultContractError(
            "COMPARISON_RESULT_INVARIANT_FAILED",
            f"{status} requires response_relationship="
            f"{expected_relationship or 'null'}",
        )

    return {
        "comparability_result": status if status in comparable_statuses else None,
        "response_relationship": response_relationship,
        "left": {
            "evidence_ref": build_artifact_ref(result_a),
            "verification": build_verification_summary(result_a),
        },
        "right": {
            "evidence_ref": build_artifact_ref(result_b),
            "verification": build_verification_summary(result_b),
        },
        "claim_boundary_contract": CLAIM_BOUNDARY_CONTRACT,
        "claim_boundaries": list(COMPARISON_CLAIM_BOUNDARIES),
    }
