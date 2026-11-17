"""Detached invocation metadata at the result-construction trust boundary.

This is not a second verifier. Preparation establishes selection; these small
records bind subsequent construction and emission to that historical fact.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields, is_dataclass, replace

from .result_contracts import ResultContractError, VerifierLimitState, VerifierToolResult
from .verifier_capabilities import VerifierCapabilityRequest
from .verifier_snapshot import InputMode, LimitFact, OperationalCode, OperationalInputFailure


def _typed_fields(value):
    """Compare fixed metadata without numeric coercion or public projection."""
    if is_dataclass(value):
        return type(value), tuple(_typed_fields(getattr(value, f.name)) for f in fields(value))
    if type(value) is tuple:
        return tuple, tuple(_typed_fields(item) for item in value)
    return type(value), value


def _metadata_record_ids(value):
    # Only the fixed, acyclic dataclass metadata tree has mutable identities.
    if not is_dataclass(value):
        return set()
    return {id(value)}.union(*(
        _metadata_record_ids(getattr(value, field.name)) for field in fields(value)
    ))


def _copy_invocation_metadata(value):
    """Authenticate the existing normal copy before promoting it to evidence.

    Isolation alone is insufficient. Take the value/type witness from the
    validated origin before deepcopy runs, then check fidelity and isolation
    separately. Leaves in this bounded metadata tree are immutable scalars.
    """
    original = _typed_fields(value)
    identities = _metadata_record_ids(value)
    copied = deepcopy(value)
    if (_typed_fields(copied) != original
            or identities.intersection(_metadata_record_ids(copied))):
        # This is an internal copy defect, not a malformed caller envelope.
        raise RuntimeError("VERIFIER_INVOCATION_COPY_MISMATCH")
    return copied


def copy_recovery_metadata(value):
    """Copy only the already validated, bounded metadata records.

    No deepcopy protocol, normal constructors, arguments() or projections run
    here. The input is the fixed acyclic capability/limit dataclass structure
    with immutable scalar leaves, never arbitrary caller/evidence JSON.
    """
    if not is_dataclass(value):
        return value
    copied = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(copied, field.name, copy_recovery_metadata(getattr(value, field.name)))
    return copied


@dataclass(frozen=True, slots=True)
class VerifierInvocationFacts:
    input_mode: InputMode
    requested_capability: VerifierCapabilityRequest
    effective_capability: VerifierCapabilityRequest | None
    limits: VerifierLimitState

    @classmethod
    def capture(cls, *, input_mode, requested_capability, limits):
        # The reference shares no dataclass instances with callers or builders.
        return cls(input_mode, deepcopy(requested_capability), None, deepcopy(limits))

    def after_selection(self):
        # Call only after the preparation postcondition has succeeded.
        return replace(self, effective_capability=deepcopy(self.requested_capability))

    def without_selection(self):
        return replace(self, effective_capability=None)

    def arguments(self):
        # Never hand the builder (or the returned result) our reference objects.
        return {f.name: deepcopy(getattr(self, f.name)) for f in fields(self)}

    def validate_result(self, result: VerifierToolResult) -> None:
        if type(result) is not VerifierToolResult or any(
            _typed_fields(getattr(result, f.name)) != _typed_fields(getattr(self, f.name))
            for f in fields(self)
        ):
            raise ResultContractError("VERIFIER_TOOL_RESULT_INVOCATION_MISMATCH")

    @classmethod
    def from_authenticated_result(cls, result: VerifierToolResult):
        """Compatibility helper for callers already holding an authenticated result.

        The operation and CLI do not use this as a source of invocation facts.
        A correct type alone does not establish this method's precondition.
        """
        if type(result) is not VerifierToolResult:
            raise TypeError("result must be VerifierToolResult")
        return cls(**{f.name: deepcopy(getattr(result, f.name)) for f in fields(cls)})


@dataclass(frozen=True, slots=True)
class EstablishedOperationalFailure:
    """Only the controlling, public fields; no exception or mutable limit alias."""

    code: object
    phase: object
    input_ref: object
    limit: tuple | None

    @classmethod
    def capture(cls, failure: OperationalInputFailure):
        limit = failure.limit
        return cls(failure.operational_code, failure.phase, failure.input_ref,
                   None if limit is None else (
                       limit.name, limit.unit, limit.maximum, limit.observed_at_least,
                   ))

    @classmethod
    def retain(cls, failure: OperationalInputFailure, *, normal_capture: bool = True):
        """Keep the established decision before the normal capture can fail.

        The recovery reference is this bounded tuple of immutable public
        fields, not the output of capture(). Neither a capture exception nor
        a false return establishes a new operational decision. The bypass
        below uses only basic allocation/field assignment and never retries
        capture or its constructor. An already authenticated API result needs
        only this bounded field snapshot (normal_capture=False), so handing it
        to the standalone emitter cannot retry a failed operation capture.
        """
        limit = failure.limit
        original = (failure.operational_code, failure.phase, failure.input_ref,
                    None if limit is None else (
                        limit.name, limit.unit, limit.maximum, limit.observed_at_least,
                    ))
        if normal_capture:
            try:
                copied = cls.capture(failure)
                if type(copied) is cls and _typed_fields((
                    copied.code, copied.phase, copied.input_ref, copied.limit,
                )) == _typed_fields(original):
                    return copied
            except Exception:
                # The earlier typed decision controls, including when recording
                # it fails with MemoryError or RecursionError.
                pass
        retained = object.__new__(cls)
        for name, value in zip(("code", "phase", "input_ref", "limit"), original):
            object.__setattr__(retained, name, value)
        return retained

    def restore(self) -> OperationalInputFailure:
        # The typed failure already existed. Recreate its bounded public fields
        # without retrying OperationalInputFailure.__post_init__ or a builder.
        failure = RuntimeError.__new__(OperationalInputFailure)
        for name, value in (("operational_code", self.code), ("phase", self.phase),
                            ("input_ref", self.input_ref),
                            ("limit", None if self.limit is None else LimitFact(*self.limit)),
                            ("detail", None)):
            object.__setattr__(failure, name, value)
        RuntimeError.__init__(failure, self.code.value)
        return failure

    def validate_result(self, result: VerifierToolResult) -> None:
        actual = result.operational_result
        if (actual is None or result.verification_result is not None
                or result.rc != 3 or result.outcome != "OPERATIONAL_OUTCOME"):
            raise ResultContractError("VERIFIER_TOOL_RESULT_FAILURE_MISMATCH")
        # Validation reads the representation; it must not recapture it with
        # the normal helper whose failure may have required the retained view.
        failure, limit = actual.failure, actual.failure.limit
        represented = (failure.operational_code, failure.phase, failure.input_ref,
                       None if limit is None else (
                           limit.name, limit.unit, limit.maximum, limit.observed_at_least,
                       ))
        if _typed_fields((self.code, self.phase, self.input_ref, self.limit)) != _typed_fields(represented):
            raise ResultContractError("VERIFIER_TOOL_RESULT_FAILURE_MISMATCH")


class VerifierOperationEvidence:
    """Prior invocation and decision, explicitly retained through CLI emission.

    Both metadata views are detached before normal processing. The selected
    view is not authoritative until the preparation postcondition returns and
    the operation sets selected=True. That transition performs no copying.
    Neither view nor the failure record is handed to the result builder.
    """

    def __init__(self, *, input_mode, requested_capability, limits):
        request, limits = _copy_invocation_metadata(requested_capability), _copy_invocation_metadata(limits)
        self._before = VerifierInvocationFacts(input_mode, request, None, limits)
        self._after = VerifierInvocationFacts(input_mode, request, request, limits)
        self.selected = False
        self.failure: EstablishedOperationalFailure | None = None

    @property
    def facts(self) -> VerifierInvocationFacts:
        if self.failure is not None and self.failure.code is OperationalCode.CAPABILITY_PROFILE_UNAVAILABLE:
            return self._before
        return self._after if self.selected else self._before

    def establish_failure(self, failure: OperationalInputFailure) -> None:
        if self.failure is None:
            self.failure = EstablishedOperationalFailure.retain(failure)

    def validate_result(self, result: VerifierToolResult) -> None:
        self.facts.validate_result(result)
        if self.failure is not None:
            self.failure.validate_result(result)
