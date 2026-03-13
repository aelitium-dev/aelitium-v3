"""
AELITIUM capture adapter for Anthropic Messages API.

Closes the trust gap by intercepting the API call directly.

Scope:
- messages.create (synchronous, non-streaming)
"""

import anthropic as _anthropic_sdk  # noqa: F401 — validates install at import time
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..canonical import canonical_json, sha256_hash
from ..ai_pack import ai_pack_from_obj
from .openai import CaptureResult, _try_sign


def capture_message(
    client: Any,
    model: str,
    messages: List[Dict[str, str]],
    out_dir: str | Path,
    metadata: Optional[Dict[str, Any]] = None,
    max_tokens: int = 1024,
) -> CaptureResult:
    """
    Call Anthropic Messages API and pack the result into a tamper-evident bundle.

    Args:
        client:     An anthropic.Anthropic() instance (or compatible mock).
        model:      Model name, e.g. "claude-3-5-sonnet-20241022".
        messages:   List of {"role": ..., "content": ...} dicts.
        out_dir:    Directory where the bundle will be written.
        metadata:   Optional extra fields merged into bundle metadata.
        max_tokens: Maximum tokens for the response (required by Anthropic API).

    Returns:
        CaptureResult with the original response, bundle path, hash, and signed flag.

    The bundle is written to:
        <out_dir>/ai_canonical.json
        <out_dir>/ai_manifest.json
        <out_dir>/verification_keys.json  (if signing key is configured)
    """
    # 1. Hash the request before sending
    request_payload = {"messages": messages, "model": model}
    request_hash = sha256_hash(canonical_json(request_payload))

    # 2. Call the API
    response = client.messages.create(model=model, messages=messages, max_tokens=max_tokens)

    # 3. Extract output text from Anthropic response
    content_blocks = getattr(response, "content", None)
    output_text = None
    if content_blocks:
        first = content_blocks[0]
        if hasattr(first, "text"):
            candidate = getattr(first, "text", None)
            if isinstance(candidate, str):
                output_text = candidate
    if output_text is None:
        raise ValueError("Cannot extract output from Anthropic response")

    # 4. Hash the response
    response_data = {"content": output_text, "model": model}
    response_hash = sha256_hash(canonical_json(response_data))

    # 5. Binding hash
    binding_hash = sha256_hash(canonical_json({"request_hash": request_hash, "response_hash": response_hash}))

    # 6. Provider metadata
    usage_obj = getattr(response, "usage", None)
    if usage_obj is not None:
        usage = {
            "input_tokens": getattr(usage_obj, "input_tokens", None),
            "output_tokens": getattr(usage_obj, "output_tokens", None),
        }
    else:
        usage = None

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prompt_str = canonical_json(messages)

    capture_meta: Dict[str, Any] = {
        "provider": "anthropic",
        "sdk": "anthropic-python",
        "request_hash": request_hash,
        "response_hash": response_hash,
        "binding_hash": binding_hash,
        "response_id": getattr(response, "id", None),
        "finish_reason": getattr(response, "stop_reason", None),
        "usage": usage,
        "captured_at_utc": ts,
    }
    if metadata:
        capture_meta.update(metadata)

    payload = {
        "metadata": capture_meta,
        "model": model,
        "output": output_text,
        "prompt": prompt_str,
        "schema_version": "ai_output_v1",
        "ts_utc": ts,
    }

    # 7. Pack into evidence bundle
    result = ai_pack_from_obj(payload)

    # 8. Add binding_hash to manifest
    manifest_with_binding = {**result.manifest, "binding_hash": binding_hash}

    # 9. Write bundle to disk
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    (out_path / "ai_canonical.json").write_text(
        result.canonical_json + "\n", encoding="utf-8"
    )
    (out_path / "ai_manifest.json").write_text(
        json.dumps(manifest_with_binding, sort_keys=True) + "\n", encoding="utf-8"
    )

    # 10. Optional signing
    signed = _try_sign(out_path)

    return CaptureResult(
        response=response,
        bundle_dir=out_path,
        ai_hash_sha256=result.ai_hash_sha256,
        signed=signed,
    )
