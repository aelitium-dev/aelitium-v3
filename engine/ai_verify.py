"""Canonical verification kernel for current AI evidence bundles."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ai_contract import (
    AI_CANONICAL_FILENAME,
    AI_MANIFEST_FILENAME,
    AI_MANIFEST_REQUIRED_FIELDS,
    AI_MANIFEST_SCHEMA,
    AI_MANIFEST_TS_PATTERN,
    AI_VERIFICATION_KEYS_FILENAME,
)


@dataclass(frozen=True)
class AIVerificationOptions:
    """Select the checks already performed by an existing v1 entrypoint."""

    required_manifest_fields: tuple[str, ...] = AI_MANIFEST_REQUIRED_FIELDS
    validate_manifest_timestamp: bool = True
    verify_signature: bool = True
    verify_binding: bool = True


@dataclass(frozen=True)
class AIVerificationResult:
    """Internal result used by the existing CLI compatibility surfaces."""

    valid: bool
    reason: str
    detail: str = ""
    error_message: str = ""
    ai_hash_sha256: str | None = None
    signature: str = "NONE"
    binding_hash: str = "NONE"
    canonical: Any = None
    manifest: Any = None


def _invalid(
    reason: str,
    detail: str = "",
    *,
    error_message: str = "",
    canonical: Any = None,
    manifest: Any = None,
) -> AIVerificationResult:
    return AIVerificationResult(
        valid=False,
        reason=reason,
        detail=detail,
        error_message=error_message,
        canonical=canonical,
        manifest=manifest,
    )


def verify_ai_bundle(
    bundle_dir: str | Path,
    *,
    options: AIVerificationOptions | None = None,
) -> AIVerificationResult:
    """Verify an AI evidence bundle using the selected existing v1 checks.

    The default options match ``aelitium verify-bundle`` and compare's former
    private verifier. Other entrypoints pass explicit compatibility options so
    this extraction does not tighten their accepted/rejected bundle behavior.
    """

    selected = options or AIVerificationOptions()
    outdir = Path(bundle_dir)
    canon_path = outdir / AI_CANONICAL_FILENAME
    manifest_path = outdir / AI_MANIFEST_FILENAME
    vk_path = outdir / AI_VERIFICATION_KEYS_FILENAME

    if not canon_path.exists():
        return _invalid("MISSING_CANONICAL", f"{AI_CANONICAL_FILENAME} not found")
    if not manifest_path.exists():
        return _invalid("MISSING_MANIFEST", f"{AI_MANIFEST_FILENAME} not found")

    try:
        canon_text = canon_path.read_text(encoding="utf-8")
        canonical = json.loads(canon_text)
    except Exception as exc:
        return _invalid(
            "CANONICAL_NOT_JSON",
            type(exc).__name__,
            error_message=str(exc),
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _invalid(
            "MANIFEST_NOT_JSON",
            type(exc).__name__,
            error_message=str(exc),
            canonical=canonical,
        )

    for field in selected.required_manifest_fields:
        if field not in manifest:
            return _invalid(
                "MANIFEST_MISSING_FIELD",
                field,
                canonical=canonical,
                manifest=manifest,
            )

    if manifest["schema"] != AI_MANIFEST_SCHEMA:
        return _invalid(
            "MANIFEST_BAD_SCHEMA",
            manifest["schema"],
            canonical=canonical,
            manifest=manifest,
        )

    if selected.validate_manifest_timestamp and not re.match(
        AI_MANIFEST_TS_PATTERN,
        manifest["ts_utc"],
    ):
        return _invalid(
            "MANIFEST_BAD_TS_UTC",
            manifest["ts_utc"],
            canonical=canonical,
            manifest=manifest,
        )

    actual_hash = hashlib.sha256(
        canon_text.rstrip("\n").encode("utf-8")
    ).hexdigest()
    if actual_hash != manifest["ai_hash_sha256"]:
        return _invalid(
            "HASH_MISMATCH",
            (
                f"expected={manifest['ai_hash_sha256'][:16]}... "
                f"got={actual_hash[:16]}..."
            ),
            canonical=canonical,
            manifest=manifest,
        )

    signature = "NONE"
    if selected.verify_signature and vk_path.exists():
        try:
            from .signing import verify_manifest_signature

            vk = json.loads(vk_path.read_text(encoding="utf-8"))
            verify_manifest_signature(manifest_path.read_bytes(), vk)
            signature = "VALID"
        except Exception as exc:
            return _invalid(
                "SIGNATURE_INVALID",
                str(exc),
                error_message=str(exc),
                canonical=canonical,
                manifest=manifest,
            )

    binding = "NONE"
    if selected.verify_binding:
        manifest_binding = manifest.get("binding_hash")
        if manifest_binding:
            meta = canonical.get("metadata", {})
            request_hash = meta.get("request_hash")
            response_hash = meta.get("response_hash")
            if not request_hash or not response_hash:
                return _invalid(
                    "BINDING_HASH_MISSING_SOURCES",
                    (
                        "manifest has binding_hash but canonical metadata lacks "
                        "request_hash/response_hash"
                    ),
                    canonical=canonical,
                    manifest=manifest,
                )

            payload = json.dumps(
                {"request_hash": request_hash, "response_hash": response_hash},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            computed = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if computed != manifest_binding:
                return _invalid(
                    "BINDING_HASH_MISMATCH",
                    (
                        f"expected={manifest_binding[:16]}... "
                        f"computed={computed[:16]}..."
                    ),
                    canonical=canonical,
                    manifest=manifest,
                )
            binding = manifest_binding

    return AIVerificationResult(
        valid=True,
        reason="OK",
        ai_hash_sha256=actual_hash,
        signature=signature,
        binding_hash=binding,
        canonical=canonical,
        manifest=manifest,
    )
