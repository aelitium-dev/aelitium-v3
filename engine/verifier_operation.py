"""Capability-qualified verifier operation core.

The operation boundary prepares explicit capabilities before touching caller
inputs, acquires one immutable snapshot, delegates semantic work to the
snapshot verifier, and returns the closed outer tool-result model. Expected
failures retain their typed classification; unexpected implementation defects
are contained across preparation, acquisition, evaluation, and construction.
This module performs no output I/O.
"""

from __future__ import annotations

from .ai_verify import (
    AIVerificationOptions,
    _freshness_policy_failure,
    _missing_required_trust_input,
    verify_ai_snapshot,
)
from .canonical_v2 import V2CanonicalizationError, validate_v2_value
from .freshness import FreshnessError, evaluate_freshness
from .verifier_invocation_facts import VerifierOperationEvidence, copy_recovery_metadata
from .verifier_emergency_output import recovery_failure
from .result_contracts import (
    MAX_PORTABLE_INTEGER,
    VerifierLimitState,
    VerifierToolResult,
    build_verifier_tool_result,
)
from .verifier_capabilities import (
    VerifierCapabilityRequest,
    prepare_verifier_capabilities,
    validate_verifier_capability_request,
    validate_prepared_verifier_capabilities,
)
from .verifier_snapshot import (
    DirectFilesystemInputs,
    ImmutableBytesInputs,
    InputMode,
    InputRole,
    OperationalCode,
    OperationalInputFailure,
    OperationalPhase,
    SnapshotRequest,
    acquire_verifier_snapshot,
)


def _input_mode(inputs: SnapshotRequest) -> InputMode:
    if type(inputs) is DirectFilesystemInputs:
        return InputMode.DIRECT_FILESYSTEM
    if type(inputs) is ImmutableBytesInputs:
        return InputMode.IMMUTABLE_BYTES
    raise TypeError("inputs must be DirectFilesystemInputs or ImmutableBytesInputs")


def _trust_input_was_supplied(inputs: SnapshotRequest) -> bool:
    if type(inputs) is DirectFilesystemInputs:
        return inputs.trust_store_path is not None
    if type(inputs) is ImmutableBytesInputs:
        return inputs.trust_store is not None
    raise TypeError("inputs must be DirectFilesystemInputs or ImmutableBytesInputs")


def validate_verifier_operation_options(options: AIVerificationOptions) -> None:
    """Validate caller-controlled options in the outer operation envelope."""

    if type(options) is not AIVerificationOptions:
        raise TypeError("options must be AIVerificationOptions")

    for name in (
        "validate_manifest_timestamp",
        "require_signature",
        "require_binding",
        "require_trusted_signer",
    ):
        if type(getattr(options, name)) is not bool:
            raise ValueError(f"{name} must be bool")

    maximum_age = options.freshness_max_age_seconds
    if maximum_age is not None and (
        type(maximum_age) is not int
        or maximum_age < 0
        or maximum_age > MAX_PORTABLE_INTEGER
    ):
        raise ValueError(
            "freshness_max_age_seconds must be an integer in "
            f"[0, {MAX_PORTABLE_INTEGER}]"
        )

    reference_time = options.freshness_reference_time_utc
    if reference_time is not None:
        if type(reference_time) is not str:
            raise ValueError(
                "freshness_reference_time_utc must be a portable calendar-valid "
                "YYYY-MM-DDTHH:MM:SSZ string"
            )
        try:
            validate_v2_value(reference_time)
            evaluate_freshness(
                evidence_timestamp=reference_time,
                reference_timestamp=reference_time,
                maximum_age_seconds=0,
            )
        except (V2CanonicalizationError, FreshnessError) as error:
            raise ValueError(
                "freshness_reference_time_utc must be a portable calendar-valid "
                "YYYY-MM-DDTHH:MM:SSZ string"
            ) from error


def verify_bundle_operation(
    inputs: SnapshotRequest,
    *,
    capability_request: VerifierCapabilityRequest,
    limits: VerifierLimitState,
    options: AIVerificationOptions | None = None,
    _evidence: VerifierOperationEvidence | None = None,
) -> VerifierToolResult:
    """Run one explicit ``VERIFY_BUNDLE`` operation without output transport.

    Capability availability is established before snapshot acquisition.  After
    acquisition, only the snapshot is passed to semantic verification, and the
    exact effective limits reported in the result are the limits enforced by
    both acquisition and JSON traversal.
    """

    # Reject malformed programmatic envelopes without inventing a result.
    # Derive the recovery mode independently of the fallible entry helper.
    if type(inputs) not in (DirectFilesystemInputs, ImmutableBytesInputs):
        raise TypeError("inputs must be DirectFilesystemInputs or ImmutableBytesInputs")
    input_mode = inputs.input_mode
    if type(limits) is not VerifierLimitState:
        raise TypeError("limits must be VerifierLimitState")
    if options is not None and type(options) is not AIVerificationOptions:
        raise TypeError("options must be AIVerificationOptions or None")
    try:
        input_mode = _input_mode(inputs)
        selected_options = options if options is not None else AIVerificationOptions()
        validate_verifier_operation_options(selected_options)
        validate_verifier_capability_request(capability_request)
        if _evidence is None:
            _evidence = VerifierOperationEvidence(
                input_mode=input_mode, requested_capability=capability_request, limits=limits,
            )
    except (TypeError, ValueError):
        raise
    except Exception as error:
        failure = recovery_failure(
            OperationalCode.RESOURCE_EXHAUSTED
            if isinstance(error, (MemoryError, RecursionError))
            else OperationalCode.INTERNAL_OPERATION_ERROR,
            OperationalPhase.CAPABILITY_SELECTION,
        )
        if _evidence is not None:
            _evidence.establish_failure(failure)
        return VerifierToolResult.emergency_operational(
            input_mode=input_mode,
            requested_capability=capability_request,
            effective_capability=None,
            limits=limits,
            failure=failure,
        )

    phase = OperationalPhase.CAPABILITY_SELECTION
    trust_store_provided = False
    prepared = None

    def finish(*, verification=None, failure=None) -> VerifierToolResult:
        if failure is not None:
            _evidence.establish_failure(failure)
        established = _evidence.facts
        try:
            result = build_verifier_tool_result(
                **established.arguments(),
                verification=verification,
                operational_failure=failure,
                options=selected_options,
                trust_store_provided=trust_store_provided,
            )
            _evidence.validate_result(result)
            return result
        except (MemoryError, RecursionError):
            code = OperationalCode.RESOURCE_EXHAUSTED
        except Exception:
            code = OperationalCode.INTERNAL_OPERATION_ERROR
        # A typed operational failure was established before construction
        # failed. Preserve it, especially an unavailable capability: an
        # unsupported request can never be projected as effective.
        if _evidence.failure is None:
            _evidence.establish_failure(recovery_failure(code, phase))
        return VerifierToolResult.emergency_operational(
            input_mode=established.input_mode,
            requested_capability=copy_recovery_metadata(established.requested_capability),
            effective_capability=copy_recovery_metadata(established.effective_capability),
            limits=copy_recovery_metadata(established.limits),
            failure=_evidence.failure.restore(),
        )

    try:
        candidate = prepare_verifier_capabilities(capability_request)
        validate_prepared_verifier_capabilities(candidate, capability_request)
        _evidence.selected = True
        phase = OperationalPhase.TRUST_INPUT
        prepared = candidate
        # Selection is complete. Failures in the following explicit-trust
        # checks belong to the next lifecycle stage and retain that selection.
        trust_supplied = _trust_input_was_supplied(inputs)
        if selected_options.require_trusted_signer and not trust_supplied:
            return finish(verification=_missing_required_trust_input())

        if not trust_supplied:
            # Policy §2.2: resolve explicit options before bundle acquisition.
            # Supplied trust must retain its earlier acquisition/validation
            # precedence in verify_ai_snapshot; it cannot be skipped here.
            phase = OperationalPhase.SEMANTIC_EVALUATION
            policy_failure = _freshness_policy_failure(selected_options)
            if policy_failure is not None:
                return finish(verification=policy_failure)

        phase = (
            OperationalPhase.TRUST_INPUT
            if trust_supplied
            else OperationalPhase.BUNDLE_SNAPSHOT
        )
        snapshot = acquire_verifier_snapshot(inputs, limits=limits.effective)
        trust_store_provided = snapshot.bytes_for(InputRole.TRUST_STORE) is not None
        phase = OperationalPhase.SEMANTIC_EVALUATION
        verification = verify_ai_snapshot(
            snapshot,
            options=selected_options,
            capabilities=prepared,
        )
        return finish(verification=verification)
    except OperationalInputFailure as failure:
        return finish(failure=failure)
    except (MemoryError, RecursionError):
        code = OperationalCode.RESOURCE_EXHAUSTED
    except Exception:
        code = OperationalCode.INTERNAL_OPERATION_ERROR
    return finish(failure=recovery_failure(code, phase))


__all__ = ["validate_verifier_operation_options", "verify_bundle_operation"]
