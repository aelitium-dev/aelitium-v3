"""Canonical verification kernel for current AI evidence bundles."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .ai_canonical import AICanonicalError, canonicalize_ai_output
from .ai_contract import (
    AI_CANONICALIZATION,
    AI_CANONICAL_FILENAME,
    AI_MANIFEST_FILENAME,
    AI_MANIFEST_REQUIRED_FIELDS,
    AI_MANIFEST_SCHEMA,
    AI_MANIFEST_TS_PATTERN,
    AI_OUTPUT_SCHEMA_VERSION,
    AI_VERIFICATION_KEYS_FILENAME,
)
from .trust import TrustStore, TrustStoreError, fingerprint_public_key, load_trust_store


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
    """

    validate_manifest_timestamp: bool = True
    require_signature: bool = False
    require_binding: bool = False
    trust_store_path: str | Path | None = None
    require_trusted_signer: bool = False


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
    signature_validity: AssuranceState = AssuranceState.NOT_EVALUATED,
    trusted_signer_identity: AssuranceState = AssuranceState.UNESTABLISHED,
    trusted_signer_reason: str = "",
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
        signature_validity=signature_validity,
        trusted_signer_identity=trusted_signer_identity,
        trusted_signer_reason=trusted_signer_reason,
    )


@dataclass(frozen=True)
class _BindingEvaluation:
    state: AssuranceState
    binding_hash: str = "NONE"
    reason: str = ""
    detail: str = ""


_SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _evaluate_binding_fields(canonical: Any, manifest: Any) -> _BindingEvaluation:
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

    payload = json.dumps(
        {"request_hash": request_hash, "response_hash": response_hash},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
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


def verify_ai_bundle(
    bundle_dir: str | Path,
    *,
    options: AIVerificationOptions | None = None,
) -> AIVerificationResult:
    """Verify a v1 AI evidence bundle and report distinct assurance states."""

    selected = options or AIVerificationOptions()

    trust_store: TrustStore | None = None
    if selected.trust_store_path is None:
        if selected.require_trusted_signer:
            return _invalid(
                "TRUST_INPUT_NOT_PROVIDED",
                "require_trusted_signer=True requires trust_store_path",
            )
    else:
        try:
            trust_store = load_trust_store(selected.trust_store_path)
        except TrustStoreError as exc:
            return _invalid(
                "TRUST_STORE_INVALID",
                exc.reason,
                error_message=str(exc),
                trusted_signer_identity=AssuranceState.UNESTABLISHED,
                trusted_signer_reason="TRUST_STORE_INVALID",
            )

    outdir = Path(bundle_dir)
    canon_path = outdir / AI_CANONICAL_FILENAME
    manifest_path = outdir / AI_MANIFEST_FILENAME
    vk_path = outdir / AI_VERIFICATION_KEYS_FILENAME
    signature_before_evaluation = (
        AssuranceState.NOT_EVALUATED
        if vk_path.exists()
        else AssuranceState.ABSENT
    )

    if not canon_path.exists():
        return _invalid(
            "MISSING_CANONICAL",
            f"{AI_CANONICAL_FILENAME} not found",
            payload_integrity=AssuranceState.ABSENT,
            signature_validity=signature_before_evaluation,
        )
    if not manifest_path.exists():
        return _invalid(
            "MISSING_MANIFEST",
            f"{AI_MANIFEST_FILENAME} not found",
            payload_integrity=AssuranceState.ABSENT,
            signature_validity=signature_before_evaluation,
        )

    try:
        canon_bytes = canon_path.read_bytes()
        canon_text = canon_bytes.decode("utf-8")
        canonical = json.loads(canon_text)
    except Exception as exc:
        return _invalid(
            "CANONICAL_NOT_JSON",
            type(exc).__name__,
            error_message=str(exc),
            payload_integrity=AssuranceState.INVALID,
            signature_validity=signature_before_evaluation,
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _invalid(
            "MANIFEST_NOT_JSON",
            type(exc).__name__,
            error_message=str(exc),
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

    if manifest["canonicalization"] != AI_CANONICALIZATION:
        return _invalid(
            "MANIFEST_BAD_CANONICALIZATION",
            manifest["canonicalization"],
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.INVALID,
            signature_validity=signature_before_evaluation,
        )

    if selected.validate_manifest_timestamp and not re.match(
        AI_MANIFEST_TS_PATTERN,
        manifest["ts_utc"] if isinstance(manifest["ts_utc"], str) else "",
    ):
        return _invalid(
            "MANIFEST_BAD_TS_UTC",
            manifest["ts_utc"],
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
            str(manifest_hash),
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.INVALID,
            signature_validity=signature_before_evaluation,
        )

    try:
        expected_canonical, actual_hash = canonicalize_ai_output(canonical)
    except AICanonicalError as exc:
        return _invalid(
            "CANONICAL_SCHEMA_INVALID",
            str(exc),
            error_message=str(exc),
            canonical=canonical,
            manifest=manifest,
            payload_integrity=AssuranceState.INVALID,
            signature_validity=signature_before_evaluation,
        )

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
    if vk_path.exists():
        try:
            from .signing import verify_manifest_signature

            vk = json.loads(vk_path.read_text(encoding="utf-8"))
            verified_signature = verify_manifest_signature(
                manifest_path.read_bytes(), vk
            )
            signature = "VALID"
            signature_validity = AssuranceState.VALID
        except Exception as exc:
            signature_validity = AssuranceState.INVALID
            signature_error = str(exc)

    trusted_signer_identity = AssuranceState.UNESTABLISHED
    trusted_signer_reason = ""
    if trust_store is not None and signature_validity is AssuranceState.VALID:
        fingerprint = fingerprint_public_key(verified_signature.public_key_bytes)
        if fingerprint in trust_store:
            trusted_signer_identity = AssuranceState.VALID
        else:
            trusted_signer_reason = "TRUSTED_SIGNER_NOT_FOUND"

    binding = _evaluate_binding_fields(canonical, manifest)

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
            signature_validity=signature_validity,
            trusted_signer_identity=trusted_signer_identity,
            trusted_signer_reason=trusted_signer_reason,
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
            signature_validity=signature_validity,
            trusted_signer_identity=trusted_signer_identity,
            trusted_signer_reason=trusted_signer_reason,
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
            signature_validity=signature_validity,
            trusted_signer_identity=trusted_signer_identity,
            trusted_signer_reason=trusted_signer_reason,
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
            signature_validity=signature_validity,
            trusted_signer_identity=trusted_signer_identity,
            trusted_signer_reason=trusted_signer_reason,
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
            signature_validity=signature_validity,
            trusted_signer_identity=trusted_signer_identity,
            trusted_signer_reason=trusted_signer_reason,
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
        signature_validity=signature_validity,
        trusted_signer_identity=trusted_signer_identity,
        trusted_signer_reason=trusted_signer_reason,
    )
