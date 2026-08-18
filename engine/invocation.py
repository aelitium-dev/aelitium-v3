"""Versioned invocation-identity primitive (P1.2a).

This module implements a strict, provider-neutral representation of the
semantic invocation an AELITIUM capture adapter emits into its provider/SDK
call boundary, plus a deterministic hash over that representation.

Scope of this module only:
- strict construction/validation of the aelitium-invocation-v1 grammar
- canonical hash derivation over an explicit, versioned field set
- deterministic parsing/recomputation of an already-stored identity object

This module does NOT:
- integrate with any capture adapter (openai/anthropic/litellm)
- modify, read, or relate to request_hash, response_hash, or binding_hash
- bind an invocation identity to a response
- get consulted by engine.ai_verify, the CLI, or the standalone verifier

What this primitive represents:
    the semantic invocation emitted by an AELITIUM capture adapter into its
    provider/SDK call boundary.

What it does NOT represent:
- a provider-confirmed or provider-normalized request
- proof the provider received the request
- proof the model executed it
- complete invocation identity
- provider identity
- response causation

The eventual assurance meaning (once a future verifier consults this, which
this slice does not implement) is limited to: the stored invocation fields
are internally consistent with the declared versioned invocation hash.
Nothing more.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any

from .canonical import canonical_json, sha256_hash

INVOCATION_FORMAT = "aelitium-invocation-v1"

SURFACE_OPENAI_CHAT_COMPLETIONS = "openai.chat.completions"
SURFACE_ANTHROPIC_MESSAGES = "anthropic.messages"
SURFACE_LITELLM_COMPLETION = "litellm.completion"

MODE_SYNC_NON_STREAMING = "sync_non_streaming"
MODE_SYNC_STREAMING = "sync_streaming"

_ALL_MODES = frozenset({MODE_SYNC_NON_STREAMING, MODE_SYNC_STREAMING})

# Valid surface -> allowed mode set. Only combinations current adapters
# actually exercise; no async, no tool-specific surfaces in this slice.
_VALID_SURFACE_MODES: dict[str, frozenset[str]] = {
    SURFACE_OPENAI_CHAT_COMPLETIONS: frozenset(
        {MODE_SYNC_NON_STREAMING, MODE_SYNC_STREAMING}
    ),
    SURFACE_ANTHROPIC_MESSAGES: frozenset({MODE_SYNC_NON_STREAMING}),
    SURFACE_LITELLM_COMPLETION: frozenset({MODE_SYNC_NON_STREAMING}),
}

# Deliberately minimal: only parameters current adapter code already
# supports or forwards, and which are clearly behaviorally relevant.
# No cross-provider renaming -- each name is exactly the adapter-emitted
# field name for that surface.
_PARAMETER_ALLOWLIST: dict[str, frozenset[str]] = {
    SURFACE_OPENAI_CHAT_COMPLETIONS: frozenset(),
    SURFACE_ANTHROPIC_MESSAGES: frozenset({"max_tokens"}),
    SURFACE_LITELLM_COMPLETION: frozenset(
        {"temperature", "max_tokens", "top_p", "seed", "stop"}
    ),
}

_REQUEST_TOP_LEVEL_KEYS = frozenset({"model", "messages", "parameters"})
_STORED_TOP_LEVEL_KEYS = frozenset(
    {"format", "surface", "mode", "request", "hash_sha256"}
)

_HASH_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class InvocationIdentityError(ValueError):
    """Raised when invocation-identity input or stored data is invalid.

    `reason` is a deterministic, stable machine-readable code. `detail` is a
    human-readable, non-normative elaboration and must not be pattern-matched
    by callers.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = f"{reason}: {detail}" if detail else reason
        super().__init__(message)


@dataclass(frozen=True)
class InvocationIdentity:
    """An immutable, already-validated invocation-identity record.

    `request_canonical_json` is the canonical JSON encoding of the `request`
    object alone -- the exact bytes folded (alongside `format`/`surface`/
    `mode`) into `hash_sha256` at construction time. It is the authoritative
    representation. `to_stored_object()` returns a fresh, disposable dict on
    every call: mutating that dict can never change this identity's fixed
    hash. Obtaining a different identity requires building a new one.
    """

    format: str
    surface: str
    mode: str
    hash_sha256: str
    request_canonical_json: str

    def to_stored_object(self) -> dict[str, Any]:
        """Return a fresh, mutable dict matching the conceptual stored shape."""

        return {
            "format": self.format,
            "surface": self.surface,
            "mode": self.mode,
            "request": json.loads(self.request_canonical_json),
            "hash_sha256": self.hash_sha256,
        }


def _validate_json_value(value: Any, path: str) -> None:
    """Recursively require deterministic, JSON-compatible data.

    Accepts null, bool, str, int, finite float, list, and dict-with-string-
    keys. Everything else (NaN/Infinity floats, bytes, set, tuple, arbitrary
    objects, non-string-keyed mappings) is rejected explicitly rather than
    relying on json.dumps to reject or silently coerce it.
    """

    if value is None:
        return
    if isinstance(value, bool):
        return
    if isinstance(value, str):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise InvocationIdentityError(
                "INVOCATION_BAD_VALUE", f"{path}: non-finite float"
            )
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise InvocationIdentityError(
                    "INVOCATION_BAD_VALUE", f"{path}: non-string key {key!r}"
                )
            _validate_json_value(item, f"{path}.{key}")
        return
    raise InvocationIdentityError(
        "INVOCATION_BAD_VALUE",
        f"{path}: unsupported type {type(value).__name__}",
    )


def _validate_surface_mode(surface: Any, mode: Any) -> tuple[str, str]:
    if not isinstance(surface, str) or surface not in _VALID_SURFACE_MODES:
        raise InvocationIdentityError(
            "INVOCATION_BAD_SURFACE", f"unsupported surface: {surface!r}"
        )
    if not isinstance(mode, str) or mode not in _ALL_MODES:
        raise InvocationIdentityError(
            "INVOCATION_BAD_MODE", f"unsupported mode: {mode!r}"
        )
    if mode not in _VALID_SURFACE_MODES[surface]:
        raise InvocationIdentityError(
            "INVOCATION_BAD_MODE",
            f"mode {mode!r} is not valid for surface {surface!r}",
        )
    return surface, mode


def _validate_request(surface: str, request: Any) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise InvocationIdentityError(
            "INVOCATION_BAD_REQUEST", "request must be an object"
        )

    unknown = set(request.keys()) - _REQUEST_TOP_LEVEL_KEYS
    if unknown:
        raise InvocationIdentityError(
            "INVOCATION_BAD_REQUEST",
            f"unknown request field(s): {sorted(unknown)}",
        )
    if "model" not in request:
        raise InvocationIdentityError(
            "INVOCATION_BAD_REQUEST", "missing required field: model"
        )
    if "messages" not in request:
        raise InvocationIdentityError(
            "INVOCATION_BAD_REQUEST", "missing required field: messages"
        )

    model = request["model"]
    if not isinstance(model, str) or not model:
        raise InvocationIdentityError(
            "INVOCATION_BAD_REQUEST", "model must be a non-empty string"
        )

    messages = request["messages"]
    if not isinstance(messages, list):
        raise InvocationIdentityError(
            "INVOCATION_BAD_REQUEST", "messages must be a list"
        )
    _validate_json_value(messages, "request.messages")

    normalized: dict[str, Any] = {"model": model, "messages": messages}

    if "parameters" in request:
        parameters = request["parameters"]
        if not isinstance(parameters, dict):
            raise InvocationIdentityError(
                "INVOCATION_BAD_REQUEST", "parameters must be an object"
            )
        allowed = _PARAMETER_ALLOWLIST.get(surface, frozenset())
        unknown_params = set(parameters.keys()) - allowed
        if unknown_params:
            raise InvocationIdentityError(
                "INVOCATION_BAD_PARAMETER",
                f"unsupported parameter(s) for surface {surface!r}: "
                f"{sorted(unknown_params)}",
            )
        _validate_json_value(parameters, "request.parameters")
        # An empty parameters object carries the same meaning as omitting
        # parameters entirely (no parameters specified) -- normalize away
        # the distinction so the two forms produce the same identity.
        if parameters:
            normalized["parameters"] = parameters

    return normalized


def _finalize(surface: str, mode: str, request: dict[str, Any]) -> InvocationIdentity:
    hash_material = {
        "format": INVOCATION_FORMAT,
        "surface": surface,
        "mode": mode,
        "request": request,
    }
    digest = sha256_hash(canonical_json(hash_material))
    return InvocationIdentity(
        format=INVOCATION_FORMAT,
        surface=surface,
        mode=mode,
        hash_sha256=digest,
        request_canonical_json=canonical_json(request),
    )


def build_invocation_identity(
    *,
    surface: str,
    mode: str,
    model: str,
    messages: Any,
    parameters: dict[str, Any] | None = None,
) -> InvocationIdentity:
    """Build and validate an invocation identity from live adapter values.

    `parameters`, if given, must contain only names in the surface's
    allowlist (see `_PARAMETER_ALLOWLIST`); every other semantic field,
    routing field, transport field, and secret is rejected or simply has no
    way to enter this function's signature.
    """

    surface, mode = _validate_surface_mode(surface, mode)
    raw_request: dict[str, Any] = {"model": model, "messages": messages}
    if parameters:
        raw_request["parameters"] = dict(parameters)
    normalized_request = _validate_request(surface, raw_request)
    return _finalize(surface, mode, normalized_request)


def parse_invocation_identity(data: Any) -> InvocationIdentity:
    """Strictly validate a stored invocation-identity object and recompute
    its hash from the stored semantic fields.

    The stored `hash_sha256` is never trusted on its own -- it is always
    recomputed from `format`/`surface`/`mode`/`request` and compared against
    the stored value. A mismatch raises `INVOCATION_HASH_MISMATCH`.
    """

    if not isinstance(data, dict):
        raise InvocationIdentityError(
            "INVOCATION_BAD_STRUCTURE", "invocation identity must be an object"
        )

    keys = set(data.keys())
    if keys != _STORED_TOP_LEVEL_KEYS:
        missing = sorted(_STORED_TOP_LEVEL_KEYS - keys)
        extra = sorted(keys - _STORED_TOP_LEVEL_KEYS)
        raise InvocationIdentityError(
            "INVOCATION_BAD_STRUCTURE", f"missing={missing} extra={extra}"
        )

    if data.get("format") != INVOCATION_FORMAT:
        raise InvocationIdentityError(
            "INVOCATION_BAD_FORMAT",
            f"format must be {INVOCATION_FORMAT!r}, got {data.get('format')!r}",
        )

    surface, mode = _validate_surface_mode(data.get("surface"), data.get("mode"))
    normalized_request = _validate_request(surface, data.get("request"))

    stored_hash = data.get("hash_sha256")
    if not isinstance(stored_hash, str) or not _HASH_HEX_PATTERN.fullmatch(
        stored_hash
    ):
        raise InvocationIdentityError(
            "INVOCATION_BAD_HASH",
            "hash_sha256 must be 64 lowercase hexadecimal characters",
        )

    identity = _finalize(surface, mode, normalized_request)
    if identity.hash_sha256 != stored_hash:
        raise InvocationIdentityError(
            "INVOCATION_HASH_MISMATCH",
            f"stored={stored_hash[:16]}... recomputed={identity.hash_sha256[:16]}...",
        )
    return identity
