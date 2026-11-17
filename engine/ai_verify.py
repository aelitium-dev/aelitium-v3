"""Canonical verification kernel for current AI evidence bundles."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from .ai_canonical import AICanonicalError, canonicalize_ai_output
from .ai_contract import (
    AI_CANONICALIZATION,
    AI_CANONICALIZATION_IDENTIFIERS,
    AI_CANONICALIZATION_V2,
    AI_CANONICAL_FILENAME,
    AI_MANIFEST_FILENAME,
    AI_MANIFEST_REQUIRED_FIELDS,
    AI_MANIFEST_SCHEMA,
    AI_MANIFEST_TS_PATTERN,
    AI_OUTPUT_SCHEMA_VERSION,
    AI_VERIFICATION_KEYS_FILENAME,
)
from .canonical_v2 import V2CanonicalizationError, parse_json_v2
from .canonicalization import canonical_json_for_identifier
from .freshness import (
    FRESHNESS_POLICY_INVALID,
    FRESHNESS_TIMESTAMP_MALFORMED,
    FreshnessError,
    FreshnessOutcome,
    evaluate_freshness,
)
from .invocation import InvocationIdentityError, parse_invocation_identity
from .invocation_binding import InvocationBindingError, parse_invocation_binding
from .manifest_dispatch import DispatchScanError, scan_manifest_selector
from .signing import ManifestSignatureError
from .trust import (
    TrustStore,
    TrustStoreError,
    fingerprint_public_key,
    load_trust_store,
    load_trust_store_bytes,
    parse_trust_store,
)
from .verifier_capabilities import (
    ED25519_PORTABLE_STRICT_1,
    EffectiveVerifierRoute,
    PreparedVerifierCapabilities,
    V1_LEGACY_UNSUPPORTED,
    select_effective_route,
    select_signature_verification_profile,
)
from .verifier_json_limits import enforce_json_traversal_limits
from .verifier_snapshot import (
    InputRef,
    InputRole,
    OperationalCode,
    OperationalInputFailure,
    OperationalLimits,
    OperationalPhase,
    VerifierSnapshot,
)
from .verifier_v1_capability import (
    LegacyJsonSourceError,
    canonical_json_v1_profile,
    canonicalize_ai_output_v1_profile,
    parse_v1_json_source,
    validate_v1_manifest_timestamp,
)
from .verifier_diagnostics import describe_json_value
from .verifier_capabilities import V1CapabilityDeclaration, V1_FROZEN_LEGACY_COMPATIBILITY


class AssuranceState(str, Enum):
    """Closed vocabulary for individual assurance dimensions."""

    VALID = "VALID"
    INVALID = "INVALID"
    ABSENT = "ABSENT"
    UNESTABLISHED = "UNESTABLISHED"
    NOT_EVALUATED = "NOT_EVALUATED"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class AIVerificationOptions:
    """Select compatibility parsing and explicit evidence requirements.

    `trust_store_path` and `require_trusted_signer` are additive and both
    default to "no trust input" -- there is no ambient/default trust-store
    discovery (no environment variable, no default filesystem location).
    Trust is evaluated only when a trust store path is explicitly supplied.

    Freshness is likewise inactive unless both ``freshness_max_age_seconds``
    and ``freshness_reference_time_utc`` are explicitly supplied. The
    verifier never supplies an ambient current time.

    ``signature_verification_profile=None`` preserves the legacy unqualified
    Python API and its existing backend verification behavior. Explicit
    ``ED25519_PORTABLE_STRICT_1`` selects portable strict signature semantics.
    Omission does not select a portable profile, and this options object is not
    the complete outer verifier capability request.
    """

    validate_manifest_timestamp: bool = True
    require_signature: bool = False
    require_binding: bool = False
    trust_store_path: str | Path | None = None
    require_trusted_signer: bool = False
    freshness_max_age_seconds: int | None = None
    freshness_reference_time_utc: str | None = None
    signature_verification_profile: str | None = None


@dataclass(frozen=True)
class AIVerificationResult:
    """Structured assurance result for AI evidence bundle verification."""

    valid: bool
    reason: str
    detail: str = ""
    error_message: str = ""
    ai_hash_sha256: str | None = None
    signature: str = "NONE"
    binding_hash: str = "NONE"
    canonical: Any = None
    manifest: Any = None
    payload_integrity: AssuranceState = AssuranceState.NOT_EVALUATED
    binding_field_consistency: AssuranceState = AssuranceState.NOT_EVALUATED
    invocation_identity_consistency: AssuranceState = AssuranceState.NOT_EVALUATED
    invocation_binding_consistency: AssuranceState = AssuranceState.NOT_EVALUATED
    signature_validity: AssuranceState = AssuranceState.NOT_EVALUATED
    trusted_signer_identity: AssuranceState = AssuranceState.UNESTABLISHED
    trusted_signer_reason: str = ""
    freshness: AssuranceState = AssuranceState.NOT_EVALUATED
    authorization: AssuranceState = AssuranceState.NOT_EVALUATED

    def assurance_dict(self) -> dict[str, str]:
        """Return the additive public assurance detail fields."""

        return {
            "payload_integrity": self.payload_integrity.value,
            "binding_field_consistency": self.binding_field_consistency.value,
            "invocation_identity_consistency": self.invocation_identity_consistency.value,
            "invocation_binding_consistency": self.invocation_binding_consistency.value,
            "signature_validity": self.signature_validity.value,
            "trusted_signer_identity": self.trusted_signer_identity.value,
            "freshness": self.freshness.value,
            "authorization": self.authorization.value,
        }


def _invalid(
    reason: str,
    detail: str = "",
    *,
    error_message: str = "",
    ai_hash_sha256: str | None = None,
    signature: str = "NONE",
    binding_hash: str = "NONE",
    canonical: Any = None,
    manifest: Any = None,
    payload_integrity: AssuranceState = AssuranceState.NOT_EVALUATED,
    binding_field_consistency: AssuranceState = AssuranceState.NOT_EVALUATED,
    invocation_identity_consistency: AssuranceState = AssuranceState.NOT_EVALUATED,
    invocation_binding_consistency: AssuranceState = AssuranceState.NOT_EVALUATED,
    signature_validity: AssuranceState = AssuranceState.NOT_EVALUATED,
    trusted_signer_identity: AssuranceState = AssuranceState.UNESTABLISHED,
    trusted_signer_reason: str = "",
    freshness: AssuranceState = AssuranceState.NOT_EVALUATED,
) -> AIVerificationResult:
    return AIVerificationResult(
        valid=False,
        reason=reason,
        detail=detail,
        error_message=error_message,
        ai_hash_sha256=ai_hash_sha256,
        signature=signature,
        binding_hash=binding_hash,
        canonical=canonical,
        manifest=manifest,
        payload_integrity=payload_integrity,
        binding_field_consistency=binding_field_consistency,
        invocation_identity_consistency=invocation_identity_consistency,
        invocation_binding_consistency=invocation_binding_consistency,
        signature_validity=signature_validity,
        trusted_signer_identity=trusted_signer_identity,
        trusted_signer_reason=trusted_signer_reason,
        freshness=freshness,
    )


@dataclass(frozen=True)
class _BindingEvaluation:
    state: AssuranceState
    binding_hash: str = "NONE"
    reason: str = ""
    detail: str = ""


_SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_V2_MANIFEST_TS_PATTERN = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"
)


class _LegacyBackendJsonError(ValueError):
    """Deterministic rejection from the released CPython JSON boundary."""

    def __init__(self, source_error: ValueError | RecursionError) -> None:
        self.source_error = source_error
        super().__init__(str(source_error))


def _parse_legacy_backend_json(
    text: str,
    *,
    recursion_is_input_rejection: bool,
) -> Any:
    """Preserve the released unqualified parser's documented rejection set."""

    try:
        return json.loads(text)
    except RecursionError as exc:
        if not recursion_is_input_rejection:
            raise
        raise _LegacyBackendJsonError(exc) from exc
    except ValueError as exc:
        raise _LegacyBackendJsonError(exc) from exc


def _semantic_source_error(error: BaseException) -> tuple[str, str]:
    source_error = (
        error.source_error
        if isinstance(error, _LegacyBackendJsonError)
        else error
    )
    return type(source_error).__name__, str(source_error)


def _decode_v1_manifest_bytes(source: bytes) -> str:
    """Reproduce ``Path.read_text(encoding="utf-8")`` newline handling."""

    return source.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def _evaluate_binding_fields(
    canonical: Any,
    manifest: Any,
    *,
    canonicalization: str = AI_CANONICALIZATION,
) -> _BindingEvaluation:
    """Evaluate consistency among the four stored v1 binding hash fields.

    This does not reconstruct a request, provider invocation, action, or
    authorization decision.
    """

    metadata = canonical.get("metadata", {}) if isinstance(canonical, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}

    locations = (
        ("manifest.binding_hash", manifest, "binding_hash"),
        ("canonical.metadata.request_hash", metadata, "request_hash"),
        ("canonical.metadata.response_hash", metadata, "response_hash"),
        ("canonical.metadata.binding_hash", metadata, "binding_hash"),
    )
    present = {
        name: isinstance(container, dict) and key in container
        for name, container, key in locations
    }
    if not any(present.values()):
        return _BindingEvaluation(AssuranceState.ABSENT)

    missing = [name for name, is_present in present.items() if not is_present]
    if missing:
        return _BindingEvaluation(
            AssuranceState.INVALID,
            reason="BINDING_FIELDS_INCOMPLETE",
            detail=f"missing={','.join(missing)}",
        )

    values = {
        name: container[key]
        for name, container, key in locations
    }
    for name, value in values.items():
        if not isinstance(value, str) or not _SHA256_HEX_PATTERN.fullmatch(value):
            return _BindingEvaluation(
                AssuranceState.INVALID,
                reason="BINDING_FIELD_MALFORMED",
                detail=name,
            )

    request_hash = values["canonical.metadata.request_hash"]
    response_hash = values["canonical.metadata.response_hash"]
    manifest_binding = values["manifest.binding_hash"]
    metadata_binding = values["canonical.metadata.binding_hash"]

    payload = canonical_json_for_identifier(
        {"request_hash": request_hash, "response_hash": response_hash},
        canonicalization,
    )
    computed = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if computed != manifest_binding:
        return _BindingEvaluation(
            AssuranceState.INVALID,
            reason="BINDING_HASH_MISMATCH",
            detail=(
                f"expected={manifest_binding[:16]}... "
                f"computed={computed[:16]}..."
            ),
        )
    if metadata_binding != manifest_binding:
        return _BindingEvaluation(
            AssuranceState.INVALID,
            reason="BINDING_HASH_MISMATCH",
            detail=(
                f"manifest={manifest_binding[:16]}... "
                f"metadata={metadata_binding[:16]}..."
            ),
        )

    return _BindingEvaluation(
        AssuranceState.VALID,
        binding_hash=manifest_binding,
    )


@dataclass(frozen=True)
class _InvocationIdentityEvaluation:
    state: AssuranceState
    reason: str = ""
    detail: str = ""


def _evaluate_invocation_identity(
    canonical: Any,
    *,
    canonicalization: str = AI_CANONICALIZATION,
    qualified_v1: bool = False,
    source_route: EffectiveVerifierRoute | None = None,
) -> _InvocationIdentityEvaluation:
    """Evaluate the stored invocation-identity object, if present.

    `engine.invocation` is the sole authority for grammar, surface/mode
    validation, parameter allowlists, and hash recomputation -- this
    function never trusts a stored hash_sha256 on its own and never
    duplicates that primitive's logic; it only calls
    `parse_invocation_identity`, which always recomputes.

    VALID here means only: the stored invocation-identity object is
    structurally valid under its declared versioned format and its stored
    hash matches recomputation from its stored semantic fields. It does not
    mean the provider received or executed the request, provider identity,
    response causation, authorization, freshness, or historical occurrence.
    """

    metadata = canonical.get("metadata", {}) if isinstance(canonical, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}

    if "invocation_identity" not in metadata:
        return _InvocationIdentityEvaluation(AssuranceState.ABSENT)

    try:
        parse_invocation_identity(
            metadata["invocation_identity"],
            canonicalization=canonicalization,
            canonicalizer=canonical_json_v1_profile if qualified_v1 else None,
            source_route=source_route if qualified_v1 else None,
        )
    except InvocationIdentityError as exc:
        return _InvocationIdentityEvaluation(
            AssuranceState.INVALID,
            reason=exc.reason,
            detail=exc.detail,
        )

    return _InvocationIdentityEvaluation(AssuranceState.VALID)


@dataclass(frozen=True)
class _InvocationBindingEvaluation:
    state: AssuranceState
    reason: str = ""
    detail: str = ""


def _evaluate_invocation_binding(
    canonical: Any,
    invocation: _InvocationIdentityEvaluation,
    *,
    canonicalization: str = AI_CANONICALIZATION,
) -> _InvocationBindingEvaluation:
    """Evaluate the stored invocation-binding object, if present.

    `engine.invocation_binding` is the sole authority for the binding
    object's own grammar and hash recomputation -- this function never
    duplicates that logic; it only calls `parse_invocation_binding`, which
    always recomputes. That primitive has no knowledge of bundles, so this
    function additionally performs the cross-field comparison the primitive
    itself deliberately cannot: whether the binding's declared
    invocation_hash/response_hash actually match this same bundle's stored
    invocation_identity.hash_sha256 and metadata.response_hash.

    A binding cannot be VALID unless the invocation identity it references
    is itself VALID -- there is no such thing as a binding that is more
    trustworthy than what it binds.

    VALID here means only: the stored invocation-binding object is
    internally consistent under its declared versioned format AND its
    invocation_hash/response_hash fields match this same bundle's stored,
    already-VALID invocation identity and response hash. It does not mean
    the provider received or executed the request, provider identity,
    response causation, authorization, freshness, or historical occurrence.
    """

    metadata = canonical.get("metadata", {}) if isinstance(canonical, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}

    if "invocation_binding" not in metadata:
        return _InvocationBindingEvaluation(AssuranceState.ABSENT)

    try:
        binding = parse_invocation_binding(
            metadata["invocation_binding"],
            canonicalization=canonicalization,
        )
    except InvocationBindingError as exc:
        return _InvocationBindingEvaluation(
            AssuranceState.INVALID,
            reason=exc.reason,
            detail=exc.detail,
        )

    if invocation.state is AssuranceState.ABSENT:
        return _InvocationBindingEvaluation(
            AssuranceState.INVALID,
            reason="INVOCATION_BINDING_INPUT_MISSING",
            detail=(
                "invocation_binding is present but "
                "metadata.invocation_identity is absent"
            ),
        )
    if invocation.state is AssuranceState.INVALID:
        return _InvocationBindingEvaluation(
            AssuranceState.INVALID,
            reason="INVOCATION_BINDING_INPUT_INVALID",
            detail=(
                "invocation_binding references an invocation_identity "
                "that is itself invalid"
            ),
        )

    response_hash = metadata.get("response_hash")
    if not isinstance(response_hash, str) or not _SHA256_HEX_PATTERN.fullmatch(
        response_hash
    ):
        return _InvocationBindingEvaluation(
            AssuranceState.INVALID,
            reason="INVOCATION_BINDING_INPUT_MISSING",
            detail=(
                "invocation_binding is present but metadata.response_hash "
                "is missing or malformed"
            ),
        )

    identity_hash = metadata["invocation_identity"]["hash_sha256"]
    if binding.invocation_hash != identity_hash or binding.response_hash != response_hash:
        return _InvocationBindingEvaluation(
            AssuranceState.INVALID,
            reason="INVOCATION_BINDING_INPUT_MISMATCH",
            detail=(
                f"binding.invocation_hash={binding.invocation_hash[:16]}... "
                f"vs identity.hash_sha256={identity_hash[:16]}...; "
                f"binding.response_hash={binding.response_hash[:16]}... "
                f"vs metadata.response_hash={response_hash[:16]}..."
            ),
        )

    return _InvocationBindingEvaluation(AssuranceState.VALID)


@dataclass(frozen=True)
class _FreshnessEvaluation:
    state: AssuranceState
    reason: str = ""
    detail: str = ""


_FRESHNESS_POLICY_PROBE_TIMESTAMP = "2000-01-01T00:00:00Z"


def _validate_freshness_policy(
    options: AIVerificationOptions,
) -> _FreshnessEvaluation:
    """Validate verifier-supplied freshness options without bundle evidence."""

    maximum_age = options.freshness_max_age_seconds
    reference_time = options.freshness_reference_time_utc

    if maximum_age is None and reference_time is None:
        return _FreshnessEvaluation(AssuranceState.NOT_EVALUATED)
    if maximum_age is None or reference_time is None:
        return _FreshnessEvaluation(
            AssuranceState.UNESTABLISHED,
            reason=FRESHNESS_POLICY_INVALID,
            detail=(
                "freshness_max_age_seconds and freshness_reference_time_utc "
                "must be supplied together"
            ),
        )

    try:
        # The fixed evidence value is known-valid and its outcome is discarded.
        # This delegates strict policy parsing to the primitive without reading
        # or parsing canonical bundle evidence before integrity prerequisites.
        evaluate_freshness(
            evidence_timestamp=_FRESHNESS_POLICY_PROBE_TIMESTAMP,
            reference_timestamp=reference_time,
            maximum_age_seconds=maximum_age,
        )
    except FreshnessError as exc:
        if exc.reason != FRESHNESS_POLICY_INVALID:
            raise
        return _FreshnessEvaluation(
            AssuranceState.UNESTABLISHED,
            reason=exc.reason,
            detail=exc.detail,
        )

    return _FreshnessEvaluation(AssuranceState.NOT_EVALUATED)


def _freshness_policy_failure(
    options: AIVerificationOptions,
) -> AIVerificationResult | None:
    """Map option-only validation to the existing semantic result."""

    policy = _validate_freshness_policy(options)
    if policy.reason:
        return _invalid(policy.reason, policy.detail, freshness=policy.state)
    return None


def _evaluate_freshness(
    canonical: Any,
    options: AIVerificationOptions,
) -> _FreshnessEvaluation:
    """Evaluate canonical declared-time recency under explicit options.

    This helper is called only after canonical schema, byte, and payload-hash
    validation succeed. It delegates all timestamp and maximum-age semantics
    to ``engine.freshness`` and maps that primitive into verifier assurance
    states without consulting signature or trust results.
    """

    maximum_age = options.freshness_max_age_seconds
    reference_time = options.freshness_reference_time_utc

    if maximum_age is None and reference_time is None:
        return _FreshnessEvaluation(AssuranceState.NOT_EVALUATED)
    if maximum_age is None or reference_time is None:
        return _FreshnessEvaluation(
            AssuranceState.UNESTABLISHED,
            reason=FRESHNESS_POLICY_INVALID,
            detail=(
                "freshness_max_age_seconds and freshness_reference_time_utc "
                "must be supplied together"
            ),
        )

    try:
        result = evaluate_freshness(
            evidence_timestamp=canonical["ts_utc"],
            reference_timestamp=reference_time,
            maximum_age_seconds=maximum_age,
        )
    except FreshnessError as exc:
        if exc.reason == FRESHNESS_TIMESTAMP_MALFORMED:
            state = AssuranceState.INVALID
        elif exc.reason == FRESHNESS_POLICY_INVALID:
            state = AssuranceState.UNESTABLISHED
        else:  # The primitive's reason vocabulary is closed in P1.3 v1.
            raise
        return _FreshnessEvaluation(
            state,
            reason=exc.reason,
            detail=exc.detail,
        )

    state_by_outcome = {
        FreshnessOutcome.VALID: AssuranceState.VALID,
        FreshnessOutcome.FUTURE: AssuranceState.INVALID,
        FreshnessOutcome.STALE: AssuranceState.INVALID,
    }
    return _FreshnessEvaluation(
        state_by_outcome[result.outcome],
        reason=result.reason or "",
    )


class _SemanticInputSource(Protocol):
    """Role source used by the shared verification algorithm."""

    def is_present(self, role: InputRole) -> bool: ...

    def read_bytes(self, role: InputRole) -> bytes: ...

    def read_text(self, role: InputRole) -> str: ...


@dataclass(frozen=True)
class _DirectSemanticInputs:
    """Legacy path adapter preserving its existing lazy I/O behavior."""

    bundle_dir: Path

    def _path(self, role: InputRole) -> Path:
        filenames = {
            InputRole.AI_CANONICAL_JSON: AI_CANONICAL_FILENAME,
            InputRole.AI_MANIFEST_JSON: AI_MANIFEST_FILENAME,
            InputRole.VERIFICATION_KEYS_JSON: AI_VERIFICATION_KEYS_FILENAME,
        }
        return self.bundle_dir / filenames[role]

    def is_present(self, role: InputRole) -> bool:
        return self._path(role).exists()

    def read_bytes(self, role: InputRole) -> bytes:
        return self._path(role).read_bytes()

    def read_text(self, role: InputRole) -> str:
        return self._path(role).read_text(encoding="utf-8")


@dataclass(frozen=True)
class _SnapshotSemanticInputs:
    """Filesystem-free adapter over an already-established snapshot."""

    snapshot: VerifierSnapshot

    def is_present(self, role: InputRole) -> bool:
        return self.snapshot.bytes_for(role) is not None

    def read_bytes(self, role: InputRole) -> bytes:
        source = self.snapshot.bytes_for(role)
        if source is None:
            raise AssertionError("stable-absent role has no bytes")
        return source

    def read_text(self, role: InputRole) -> str:
        return _decode_v1_manifest_bytes(self.read_bytes(role))


def _raise_snapshot_parser_resource_failure(
    error: BaseException,
    *,
    operational_limits: OperationalLimits | None,
    phase: OperationalPhase,
    input_ref: InputRef,
) -> None:
    """Keep host parser exhaustion outside the semantic reason vocabulary."""

    if operational_limits is None:
        return

    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        if isinstance(current, (MemoryError, RecursionError)):
            raise OperationalInputFailure(
                OperationalCode.RESOURCE_EXHAUSTED,
                phase,
                input_ref,
                None,
                None,
            ) from error
        seen.add(id(current))
        current = current.__cause__ or current.__context__


def _invalid_trust_input(error: TrustStoreError) -> AIVerificationResult:
    return _invalid(
        "TRUST_STORE_INVALID",
        error.reason,
        error_message=str(error),
        trusted_signer_identity=AssuranceState.UNESTABLISHED,
        trusted_signer_reason="TRUST_STORE_INVALID",
    )


def _missing_required_trust_input() -> AIVerificationResult:
    return _invalid(
        "TRUST_INPUT_NOT_PROVIDED",
        "require_trusted_signer=True requires trust_store_path",
    )


def _legacy_auxiliary_route(
    capabilities: PreparedVerifierCapabilities | None,
) -> EffectiveVerifierRoute | None:
    """Select the legacy source profile shared by auxiliary JSON inputs."""

    if capabilities is None:
        return None
    declaration = capabilities.requested.v1
    if declaration.capability == V1_LEGACY_UNSUPPORTED:
        # A v2 bundle still uses the frozen legacy auxiliary format. An
        # unsupported *v1 bundle route* must not select ambient host JSON.
        declaration = V1CapabilityDeclaration(V1_FROZEN_LEGACY_COMPATIBILITY)
    return EffectiveVerifierRoute(
        AI_CANONICALIZATION,
        declaration,
        capabilities.named_timestamp_profile if declaration is capabilities.requested.v1 else None,
    )


def _parse_acquired_snapshot_trust(
    source: bytes,
    *,
    capabilities: PreparedVerifierCapabilities | None,
) -> TrustStore:
    """Validate acquired trust bytes before inspecting bundle content."""

    trust_route = _legacy_auxiliary_route(capabilities)
    if trust_route is None:
        return load_trust_store_bytes(source)

    trust_data = parse_v1_json_source(
        source,
        route=trust_route,
        role=InputRole.TRUST_STORE,
        phase=OperationalPhase.TRUST_INPUT,
        input_ref=InputRef.TRUST_STORE,
    )
    return parse_trust_store(trust_data)


def _verify_ai_semantic_source(
    source: _SemanticInputSource,
    *,
    selected: AIVerificationOptions,
    signature_verification_profile: str | None,
    trust_store: TrustStore | None,
    operational_limits: OperationalLimits | None = None,
    capabilities: PreparedVerifierCapabilities | None = None,
) -> AIVerificationResult:
    """Run the shared semantic algorithm over one role-oriented source."""

    policy_failure = _freshness_policy_failure(selected)
    if policy_failure is not None:
        return policy_failure

    signature_before_evaluation = (
        AssuranceState.NOT_EVALUATED
        if source.is_present(InputRole.VERIFICATION_KEYS_JSON)
        else AssuranceState.ABSENT
    )

    if not source.is_present(InputRole.AI_CANONICAL_JSON):
        return _invalid(
            "MISSING_CANONICAL",
            f"{AI_CANONICAL_FILENAME} not found",
            payload_integrity=AssuranceState.ABSENT,
            signature_validity=signature_before_evaluation,
        )
    if not source.is_present(InputRole.AI_MANIFEST_JSON):
        return _invalid(
            "MISSING_MANIFEST",
            f"{AI_MANIFEST_FILENAME} not found",
            payload_integrity=AssuranceState.ABSENT,
            signature_validity=signature_before_evaluation,
        )

    # AELITIUM-DISPATCH-JSON-1 is non-observable lookahead.  Every outcome
    # except an exact final v2 selector takes the complete frozen v1/error
    # route.  Scanner-derived nodes and values are discarded here and neither
    # version parser receives anything but the original bytes.
    try:
        manifest_bytes: bytes | None = source.read_bytes(InputRole.AI_MANIFEST_JSON)
    except OSError:
        manifest_bytes = None
        scanned_identifier = None
    else:
        try:
            scanned_identifier = scan_manifest_selector(
                manifest_bytes,
                registered_identifiers=AI_CANONICALIZATION_IDENTIFIERS,
            )
        except DispatchScanError:
            # A failed lookahead still hands the same immutable original bytes
            # to the legacy parser.  The scanner failure is not observable.
            scanned_identifier = None
    effective_route: EffectiveVerifierRoute | None = None
    if capabilities is None:
        canonicalization = (
            AI_CANONICALIZATION_V2
            if scanned_identifier == AI_CANONICALIZATION_V2
            else AI_CANONICALIZATION
        )
    else:
        effective_route = select_effective_route(
            capabilities,
            scanned_identifier,
        )
        canonicalization = effective_route.canonicalization_identifier

    try:
        canon_bytes = source.read_bytes(InputRole.AI_CANONICAL_JSON)
        if operational_limits is not None:
            enforce_json_traversal_limits(
                canon_bytes,
                limits=operational_limits,
                phase=OperationalPhase.CANONICAL_PARSE,
                input_ref=InputRef.AI_CANONICAL_JSON,
                allow_legacy_constants=(
                    canonicalization != AI_CANONICALIZATION_V2
                ),
            )
        if canonicalization == AI_CANONICALIZATION_V2:
            canonical = parse_json_v2(canon_bytes)
        elif effective_route is not None:
            canonical = parse_v1_json_source(
                canon_bytes,
                route=effective_route,
                role=InputRole.AI_CANONICAL_JSON,
                phase=OperationalPhase.CANONICAL_PARSE,
                input_ref=InputRef.AI_CANONICAL_JSON,
            )
        else:
            canon_text = canon_bytes.decode("utf-8")
            canonical = _parse_legacy_backend_json(
                canon_text,
                recursion_is_input_rejection=operational_limits is None,
            )
    except OperationalInputFailure:
        raise
    except (MemoryError, RecursionError) as exc:
        _raise_snapshot_parser_resource_failure(
            exc,
            operational_limits=operational_limits,
            phase=OperationalPhase.CANONICAL_PARSE,
            input_ref=InputRef.AI_CANONICAL_JSON,
        )
        raise
    except (
        _LegacyBackendJsonError,
        UnicodeDecodeError,
        LegacyJsonSourceError,
        V2CanonicalizationError,
    ) as exc:
        detail, error_message = _semantic_source_error(exc)
        return _invalid(
            "CANONICAL_NOT_JSON",
            detail,
            error_message=error_message,
            payload_integrity=AssuranceState.INVALID,
            signature_validity=signature_before_evaluation,
        )
    try:
        assert manifest_bytes is not None or operational_limits is None
        if operational_limits is not None:
            enforce_json_traversal_limits(
                manifest_bytes,
                limits=operational_limits,
                phase=OperationalPhase.MANIFEST_PARSE,
                input_ref=InputRef.AI_MANIFEST_JSON,
                allow_legacy_constants=(
                    canonicalization != AI_CANONICALIZATION_V2
                ),
            )
        if canonicalization == AI_CANONICALIZATION_V2:
            assert manifest_bytes is not None
            manifest = parse_json_v2(manifest_bytes)
        elif effective_route is not None:
            assert manifest_bytes is not None
            manifest = parse_v1_json_source(
                manifest_bytes,
                route=effective_route,
                role=InputRole.AI_MANIFEST_JSON,
                phase=OperationalPhase.MANIFEST_PARSE,
                input_ref=InputRef.AI_MANIFEST_JSON,
                validate_manifest_timestamp=selected.validate_manifest_timestamp,
            )
        else:
            if manifest_bytes is None:
                manifest = _parse_legacy_backend_json(
                    source.read_text(InputRole.AI_MANIFEST_JSON),
                    recursion_is_input_rejection=operational_limits is None,
                )
            else:
                manifest = _parse_legacy_backend_json(
                    _decode_v1_manifest_bytes(manifest_bytes),
                    recursion_is_input_rejection=operational_limits is None,
                )
    except OperationalInputFailure:
        raise
    except (MemoryError, RecursionError) as exc:
        _raise_snapshot_parser_resource_failure(
            exc,
            operational_limits=operational_limits,
            phase=OperationalPhase.MANIFEST_PARSE,
            input_ref=InputRef.AI_MANIFEST_JSON,
        )
        raise
    except (
        _LegacyBackendJsonError,
        UnicodeDecodeError,
        LegacyJsonSourceError,
        V2CanonicalizationError,
    ) as exc:
        detail, error_message = _semantic_source_error(exc)
        return _invalid(
            "MANIFEST_NOT_JSON",
            detail,
            error_message=error_message,
            canonical=canonical,
            payload_integrity=AssuranceState.INVALID,
            signature_validity=signature_before_evaluation,
        )

    if not isinstance(manifest, dict):
        return _invalid(
            "MANIFEST_NOT_OBJECT",
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.INVALID,
            signature_validity=signature_before_evaluation,
        )

    for field in AI_MANIFEST_REQUIRED_FIELDS:
        if field not in manifest:
            return _invalid(
                "MANIFEST_MISSING_FIELD",
                field,
                canonical=canonical,
                manifest=manifest,
                payload_integrity=AssuranceState.INVALID,
                signature_validity=signature_before_evaluation,
            )

    if manifest["schema"] != AI_MANIFEST_SCHEMA:
        return _invalid(
            "MANIFEST_BAD_SCHEMA",
            manifest["schema"],
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.INVALID,
            signature_validity=signature_before_evaluation,
        )

    if manifest["input_schema"] != AI_OUTPUT_SCHEMA_VERSION:
        return _invalid(
            "MANIFEST_BAD_INPUT_SCHEMA",
            manifest["input_schema"],
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.INVALID,
            signature_validity=signature_before_evaluation,
        )

    if manifest["canonicalization"] != canonicalization:
        return _invalid(
            "MANIFEST_BAD_CANONICALIZATION",
            manifest["canonicalization"],
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.INVALID,
            signature_validity=signature_before_evaluation,
        )

    if selected.validate_manifest_timestamp:
        manifest_timestamp = manifest["ts_utc"]
        if canonicalization == AI_CANONICALIZATION_V2:
            timestamp_valid = isinstance(
                manifest_timestamp, str
            ) and _V2_MANIFEST_TS_PATTERN.fullmatch(manifest_timestamp)
        elif effective_route is not None:
            timestamp_valid = validate_v1_manifest_timestamp(
                manifest_timestamp,
                route=effective_route,
            )
        else:
            timestamp_valid = re.match(
                AI_MANIFEST_TS_PATTERN,
                manifest_timestamp if isinstance(manifest_timestamp, str) else "",
            )
        if not timestamp_valid:
            return _invalid(
                "MANIFEST_BAD_TS_UTC",
                manifest_timestamp,
                canonical=canonical,
                manifest=manifest,
                payload_integrity=AssuranceState.INVALID,
                signature_validity=signature_before_evaluation,
            )

    manifest_hash = manifest["ai_hash_sha256"]
    if not isinstance(manifest_hash, str) or not _SHA256_HEX_PATTERN.fullmatch(
        manifest_hash
    ):
        return _invalid(
            "MANIFEST_BAD_AI_HASH_SHA256",
            describe_json_value(manifest_hash),
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.INVALID,
            signature_validity=signature_before_evaluation,
        )

    try:
        if effective_route is not None and canonicalization == AI_CANONICALIZATION:
            expected_canonical, actual_hash = canonicalize_ai_output_v1_profile(
                canonical
            )
        else:
            expected_canonical, actual_hash = canonicalize_ai_output(
                canonical, canonicalization
            )
    except AICanonicalError as exc:
        if str(exc) == "AI_OUTPUT_INVALID_UNICODE":
            return _invalid(
                "CANONICAL_NOT_JSON",
                str(exc),
                error_message=str(exc),
                canonical=canonical,
                manifest=manifest,
                payload_integrity=AssuranceState.INVALID,
                signature_validity=signature_before_evaluation,
            )
        return _invalid(
            "CANONICAL_SCHEMA_INVALID",
            str(exc),
            error_message=str(exc),
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.INVALID,
            signature_validity=signature_before_evaluation,
        )
    except V2CanonicalizationError as exc:
        return _invalid(
            "CANONICAL_NOT_JSON",
            str(exc),
            error_message=str(exc),
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.INVALID,
            signature_validity=signature_before_evaluation,
        )
    except (MemoryError, RecursionError) as exc:
        _raise_snapshot_parser_resource_failure(
            exc,
            operational_limits=operational_limits,
            phase=OperationalPhase.CANONICAL_PARSE,
            input_ref=InputRef.AI_CANONICAL_JSON,
        )
        raise

    expected_bytes = expected_canonical.encode("utf-8")
    if canon_bytes not in (expected_bytes, expected_bytes + b"\n"):
        return _invalid(
            "CANONICAL_BYTES_MISMATCH",
            "stored bytes are not canonical JSON with at most one terminal LF",
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.INVALID,
            signature_validity=signature_before_evaluation,
        )

    if actual_hash != manifest["ai_hash_sha256"]:
        return _invalid(
            "HASH_MISMATCH",
            (
                f"expected={manifest['ai_hash_sha256'][:16]}... "
                f"got={actual_hash[:16]}..."
            ),
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.INVALID,
            signature_validity=signature_before_evaluation,
        )

    signature = "NONE"
    signature_validity = AssuranceState.ABSENT
    signature_error = ""
    verified_signature = None
    if source.is_present(InputRole.VERIFICATION_KEYS_JSON):
        verification_keys_bytes: bytes | None = None
        if operational_limits is not None:
            verification_keys_bytes = source.read_bytes(
                InputRole.VERIFICATION_KEYS_JSON
            )
            enforce_json_traversal_limits(
                verification_keys_bytes,
                limits=operational_limits,
                phase=OperationalPhase.SIGNATURE_MATERIAL,
                input_ref=InputRef.VERIFICATION_KEYS_JSON,
                allow_legacy_constants=True,
            )
        try:
            if signature_verification_profile is None:
                from .signing import verify_manifest_signature as signature_verifier
            elif signature_verification_profile == ED25519_PORTABLE_STRICT_1:
                from .signing import (
                    verify_manifest_signature_portable_strict_1 as signature_verifier,
                )
            else:  # Selection above makes this unreachable without a code defect.
                raise AssertionError("unselected signature verification profile")

            keyring_route = _legacy_auxiliary_route(capabilities)
            if keyring_route is not None:
                assert verification_keys_bytes is not None
                vk = parse_v1_json_source(
                    verification_keys_bytes,
                    route=keyring_route,
                    role=InputRole.VERIFICATION_KEYS_JSON,
                    phase=OperationalPhase.SIGNATURE_MATERIAL,
                    input_ref=InputRef.VERIFICATION_KEYS_JSON,
                )
            else:
                vk = _parse_legacy_backend_json(
                    _decode_v1_manifest_bytes(verification_keys_bytes)
                    if verification_keys_bytes is not None
                    else source.read_text(InputRole.VERIFICATION_KEYS_JSON),
                    recursion_is_input_rejection=operational_limits is None,
                )
            verified_signature = signature_verifier(
                (
                    manifest_bytes
                    if manifest_bytes is not None
                    else source.read_bytes(InputRole.AI_MANIFEST_JSON)
                ),
                vk,
            )
            signature = "VALID"
            signature_validity = AssuranceState.VALID
        except OperationalInputFailure:
            raise
        except (MemoryError, RecursionError) as exc:
            _raise_snapshot_parser_resource_failure(
                exc,
                operational_limits=operational_limits,
                phase=OperationalPhase.SIGNATURE_MATERIAL,
                input_ref=InputRef.VERIFICATION_KEYS_JSON,
            )
            raise
        except (
            _LegacyBackendJsonError,
            UnicodeDecodeError,
            LegacyJsonSourceError,
            ManifestSignatureError,
        ) as exc:
            signature_validity = AssuranceState.INVALID
            signature_error = _semantic_source_error(exc)[1]

    trusted_signer_identity = AssuranceState.UNESTABLISHED
    trusted_signer_reason = ""
    if trust_store is not None and signature_validity is AssuranceState.VALID:
        fingerprint = fingerprint_public_key(verified_signature.public_key_bytes)
        if fingerprint in trust_store:
            trusted_signer_identity = AssuranceState.VALID
        else:
            trusted_signer_reason = "TRUSTED_SIGNER_NOT_FOUND"

    binding = _evaluate_binding_fields(
        canonical,
        manifest,
        canonicalization=canonicalization,
    )
    invocation = _evaluate_invocation_identity(
        canonical,
        canonicalization=canonicalization,
        qualified_v1=(
            capabilities is not None
            and canonicalization == AI_CANONICALIZATION
        ),
        source_route=effective_route,
    )
    invocation_binding = _evaluate_invocation_binding(
        canonical,
        invocation,
        canonicalization=canonicalization,
    )
    freshness = _evaluate_freshness(canonical, selected)

    if signature_error:
        return _invalid(
            "SIGNATURE_INVALID",
            signature_error,
            error_message=signature_error,
            ai_hash_sha256=actual_hash,
            binding_hash=binding.binding_hash,
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.VALID,
            binding_field_consistency=binding.state,
            invocation_identity_consistency=invocation.state,
            invocation_binding_consistency=invocation_binding.state,
            signature_validity=signature_validity,
            trusted_signer_identity=trusted_signer_identity,
            trusted_signer_reason=trusted_signer_reason,
            freshness=freshness.state,
        )
    if (
        selected.require_signature or selected.require_trusted_signer
    ) and signature_validity is AssuranceState.ABSENT:
        return _invalid(
            "SIGNATURE_REQUIRED",
            ai_hash_sha256=actual_hash,
            binding_hash=binding.binding_hash,
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.VALID,
            binding_field_consistency=binding.state,
            invocation_identity_consistency=invocation.state,
            invocation_binding_consistency=invocation_binding.state,
            signature_validity=signature_validity,
            trusted_signer_identity=trusted_signer_identity,
            trusted_signer_reason=trusted_signer_reason,
            freshness=freshness.state,
        )
    if binding.reason:
        return _invalid(
            binding.reason,
            binding.detail,
            ai_hash_sha256=actual_hash,
            signature=signature,
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.VALID,
            binding_field_consistency=binding.state,
            invocation_identity_consistency=invocation.state,
            invocation_binding_consistency=invocation_binding.state,
            signature_validity=signature_validity,
            trusted_signer_identity=trusted_signer_identity,
            trusted_signer_reason=trusted_signer_reason,
            freshness=freshness.state,
        )
    if selected.require_binding and binding.state is AssuranceState.ABSENT:
        return _invalid(
            "BINDING_REQUIRED",
            ai_hash_sha256=actual_hash,
            signature=signature,
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.VALID,
            binding_field_consistency=binding.state,
            invocation_identity_consistency=invocation.state,
            invocation_binding_consistency=invocation_binding.state,
            signature_validity=signature_validity,
            trusted_signer_identity=trusted_signer_identity,
            trusted_signer_reason=trusted_signer_reason,
            freshness=freshness.state,
        )
    if (
        selected.require_trusted_signer
        and trusted_signer_identity is not AssuranceState.VALID
    ):
        return _invalid(
            trusted_signer_reason,
            ai_hash_sha256=actual_hash,
            signature=signature,
            binding_hash=binding.binding_hash,
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.VALID,
            binding_field_consistency=binding.state,
            invocation_identity_consistency=invocation.state,
            invocation_binding_consistency=invocation_binding.state,
            signature_validity=signature_validity,
            trusted_signer_identity=trusted_signer_identity,
            trusted_signer_reason=trusted_signer_reason,
            freshness=freshness.state,
        )
    if invocation.state is AssuranceState.INVALID:
        return _invalid(
            invocation.reason,
            invocation.detail,
            ai_hash_sha256=actual_hash,
            signature=signature,
            binding_hash=binding.binding_hash,
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.VALID,
            binding_field_consistency=binding.state,
            invocation_identity_consistency=invocation.state,
            invocation_binding_consistency=invocation_binding.state,
            signature_validity=signature_validity,
            trusted_signer_identity=trusted_signer_identity,
            trusted_signer_reason=trusted_signer_reason,
            freshness=freshness.state,
        )
    if invocation_binding.state is AssuranceState.INVALID:
        return _invalid(
            invocation_binding.reason,
            invocation_binding.detail,
            ai_hash_sha256=actual_hash,
            signature=signature,
            binding_hash=binding.binding_hash,
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.VALID,
            binding_field_consistency=binding.state,
            invocation_identity_consistency=invocation.state,
            invocation_binding_consistency=invocation_binding.state,
            signature_validity=signature_validity,
            trusted_signer_identity=trusted_signer_identity,
            trusted_signer_reason=trusted_signer_reason,
            freshness=freshness.state,
        )
    if freshness.reason:
        return _invalid(
            freshness.reason,
            freshness.detail,
            ai_hash_sha256=actual_hash,
            signature=signature,
            binding_hash=binding.binding_hash,
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.VALID,
            binding_field_consistency=binding.state,
            invocation_identity_consistency=invocation.state,
            invocation_binding_consistency=invocation_binding.state,
            signature_validity=signature_validity,
            trusted_signer_identity=trusted_signer_identity,
            trusted_signer_reason=trusted_signer_reason,
            freshness=freshness.state,
        )

    return AIVerificationResult(
        valid=True,
        reason="OK",
        ai_hash_sha256=actual_hash,
        signature=signature,
        binding_hash=binding.binding_hash,
        canonical=canonical,
        manifest=manifest,
        payload_integrity=AssuranceState.VALID,
        binding_field_consistency=binding.state,
        invocation_identity_consistency=invocation.state,
        invocation_binding_consistency=invocation_binding.state,
        signature_validity=signature_validity,
        trusted_signer_identity=trusted_signer_identity,
        trusted_signer_reason=trusted_signer_reason,
        freshness=freshness.state,
    )


def verify_ai_bundle(
    bundle_dir: str | Path,
    *,
    options: AIVerificationOptions | None = None,
) -> AIVerificationResult:
    """Verify a path-oriented bundle with released-compatible I/O behavior."""

    selected = options or AIVerificationOptions()
    signature_verification_profile = select_signature_verification_profile(
        selected.signature_verification_profile
    )

    trust_store: TrustStore | None = None
    if selected.trust_store_path is None:
        if selected.require_trusted_signer:
            return _missing_required_trust_input()
    else:
        try:
            trust_store = load_trust_store(selected.trust_store_path)
        except TrustStoreError as exc:
            return _invalid_trust_input(exc)

    return _verify_ai_semantic_source(
        _DirectSemanticInputs(Path(bundle_dir)),
        selected=selected,
        signature_verification_profile=signature_verification_profile,
        trust_store=trust_store,
    )


def verify_ai_snapshot(
    snapshot: VerifierSnapshot,
    *,
    options: AIVerificationOptions | None = None,
    capabilities: PreparedVerifierCapabilities | None = None,
) -> AIVerificationResult:
    """Verify only immutable bytes and stable absence from ``snapshot``.

    This internal production primitive performs semantic verification over the
    frozen bytes after enforcing O2B1 traversal limits.  It does not acquire
    paths or produce the outer operational result that belongs to O3.  An
    explicitly prepared capability request enables post-dispatch route
    enforcement; omission preserves the existing internal compatibility path.
    The legacy ``trust_store_path`` option is ignored because trust presence
    and bytes are already fixed by the snapshot.
    """

    selected = options or AIVerificationOptions()
    if not isinstance(snapshot, VerifierSnapshot):
        raise TypeError("snapshot must be a VerifierSnapshot")
    if capabilities is not None and type(capabilities) is not PreparedVerifierCapabilities:
        raise TypeError("capabilities must be PreparedVerifierCapabilities or None")
    signature_verification_profile = (
        select_signature_verification_profile(selected.signature_verification_profile)
        if capabilities is None
        else capabilities.signature_verification_profile
    )

    trust_store: TrustStore | None = None
    trust_bytes = snapshot.bytes_for(InputRole.TRUST_STORE)
    if trust_bytes is None:
        if selected.require_trusted_signer:
            return _missing_required_trust_input()
    else:
        enforce_json_traversal_limits(
            trust_bytes,
            limits=snapshot.effective_limits,
            phase=OperationalPhase.TRUST_INPUT,
            input_ref=InputRef.TRUST_STORE,
            allow_legacy_constants=True,
        )
        try:
            trust_store = _parse_acquired_snapshot_trust(
                trust_bytes,
                capabilities=capabilities,
            )
        except OperationalInputFailure:
            raise
        except (MemoryError, RecursionError) as exc:
            _raise_snapshot_parser_resource_failure(
                exc,
                operational_limits=snapshot.effective_limits,
                phase=OperationalPhase.TRUST_INPUT,
                input_ref=InputRef.TRUST_STORE,
            )
            raise
        except TrustStoreError as exc:
            return _invalid_trust_input(exc)
        except LegacyJsonSourceError as exc:
            return _invalid_trust_input(
                TrustStoreError("TRUST_STORE_NOT_JSON", type(exc).__name__)
            )

    return _verify_ai_semantic_source(
        _SnapshotSemanticInputs(snapshot),
        selected=selected,
        signature_verification_profile=signature_verification_profile,
        trust_store=trust_store,
        operational_limits=snapshot.effective_limits,
        capabilities=capabilities,
    )
