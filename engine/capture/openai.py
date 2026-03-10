"""
AELITIUM capture adapter for OpenAI chat completions.

Closes the trust gap by intercepting the API call directly,
instead of relying on the user to write JSON by hand.

Scope (v2):
- chat.completions.create (synchronous, non-streaming)
- chat.completions.create (streaming)
- optional Ed25519 signing at capture time

Not in scope:
- tool calls, async, retries, function calling
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..canonical import canonical_json, sha256_hash
from ..ai_pack import ai_pack_from_obj


@dataclass(frozen=True)
class CaptureResult:
    """Result of a captured OpenAI call."""
    response: Any          # original OpenAI response object (unmodified)
    bundle_dir: Path       # directory containing ai_canonical.json + ai_manifest.json
    ai_hash_sha256: str    # deterministic hash of the evidence bundle
    signed: bool = False   # True if verification_keys.json was written


def _extract_content(response: Any) -> str:
    """Extract text content from a chat completion response."""
    choices = getattr(response, "choices", None)
    if not choices:
        raise ValueError("Cannot extract output: response.choices is empty or missing")
    message = getattr(choices[0], "message", None)
    if message is None:
        raise ValueError("Cannot extract output: choices[0].message is missing")
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif hasattr(item, "type") and getattr(item, "type") == "text":
                parts.append(getattr(item, "text", ""))
        result = "".join(parts)
        if result:
            return result
    raise ValueError("Cannot extract output: choices[0].message.content is None or unsupported format")


def _try_sign(out_path: Path) -> bool:
    """Attempt to sign the manifest. Returns True if signed, False otherwise."""
    if not (os.environ.get("AEL_ED25519_PRIVKEY_B64") or os.environ.get("AEL_ED25519_PRIVKEY_PATH")):
        return False
    try:
        from ..signing import build_verification_material
        manifest_bytes = (out_path / "ai_manifest.json").read_bytes()
        vk = build_verification_material(manifest_bytes)
        (out_path / "verification_keys.json").write_text(
            json.dumps(vk, sort_keys=True) + "\n", encoding="utf-8"
        )
        return True
    except Exception:
        return False


def capture_chat_completion(
    client: Any,
    model: str,
    messages: List[Dict[str, str]],
    out_dir: str | Path,
    metadata: Optional[Dict[str, Any]] = None,
) -> CaptureResult:
    """
    Call OpenAI chat completions and pack the result into a tamper-evident bundle.

    Args:
        client:   An openai.OpenAI() instance (or compatible mock).
        model:    Model name, e.g. "gpt-4o".
        messages: List of {"role": ..., "content": ...} dicts.
        out_dir:  Directory where the bundle will be written.
        metadata: Optional extra fields merged into bundle metadata.

    Returns:
        CaptureResult with the original response, bundle path, hash, and signed flag.

    The bundle is written to:
        <out_dir>/ai_canonical.json
        <out_dir>/ai_manifest.json
        <out_dir>/verification_keys.json  (if signing key is configured)

    Trust boundary:
        This adapter proves that the output was captured at call time and
        has not been altered since. It does NOT prove the model is correct
        or that the client itself was not compromised.
    """
    # 1. Hash the request before sending — records what was asked
    request_payload = {"messages": messages, "model": model}
    request_hash = sha256_hash(canonical_json(request_payload))

    # 2. Call the API
    response = client.chat.completions.create(model=model, messages=messages)

    # 3. Extract output text
    output_text = _extract_content(response)

    # 4. Hash the response — records what the model returned
    response_data = {"content": output_text, "model": response.model}
    response_hash = sha256_hash(canonical_json(response_data))

    # 5. Binding hash — single proof linking request↔response
    binding_hash = sha256_hash(canonical_json({"request_hash": request_hash, "response_hash": response_hash}))

    # 6. Provider metadata
    choices = getattr(response, "choices", [])

    def _safe_str(val: Any) -> Optional[str]:
        """Return value only if it's a str, else None."""
        return val if isinstance(val, str) else None

    def _safe_int(val: Any) -> Optional[int]:
        """Return value only if it's an int, else None."""
        return val if isinstance(val, int) else None

    usage_obj = getattr(response, "usage", None)
    if usage_obj is not None and not callable(usage_obj):
        raw_prompt = getattr(usage_obj, "prompt_tokens", None)
        raw_completion = getattr(usage_obj, "completion_tokens", None)
        raw_total = getattr(usage_obj, "total_tokens", None)
        # Only include usage dict if at least one token count is a real int
        if any(isinstance(v, int) for v in (raw_prompt, raw_completion, raw_total)):
            usage: Any = {
                "prompt_tokens": _safe_int(raw_prompt),
                "completion_tokens": _safe_int(raw_completion),
                "total_tokens": _safe_int(raw_total),
            }
        else:
            usage = None
    else:
        usage = None

    finish_reason = None
    if choices:
        raw_fr = getattr(choices[0], "finish_reason", None)
        finish_reason = _safe_str(raw_fr)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prompt_str = canonical_json(messages)

    capture_meta: Dict[str, Any] = {
        "provider": "openai",
        "sdk": "openai-python",
        "request_hash": request_hash,
        "response_hash": response_hash,
        "binding_hash": binding_hash,
        "response_id": _safe_str(getattr(response, "id", None)),
        "provider_created_at": _safe_int(getattr(response, "created", None)),
        "finish_reason": finish_reason,
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


def capture_chat_completion_stream(
    client: Any,
    model: str,
    messages: List[Dict[str, str]],
    out_dir: str | Path,
    metadata: Optional[Dict[str, Any]] = None,
) -> CaptureResult:
    """
    Call OpenAI chat completions with streaming and pack the accumulated result
    into a tamper-evident bundle.

    Args:
        client:   An openai.OpenAI() instance (or compatible mock).
        model:    Model name, e.g. "gpt-4o".
        messages: List of {"role": ..., "content": ...} dicts.
        out_dir:  Directory where the bundle will be written.
        metadata: Optional extra fields merged into bundle metadata.

    Returns:
        CaptureResult with response=None (no single response object for streams),
        bundle path, hash, and signed flag.
    """
    # 1. Hash request before calling
    request_payload = {"messages": messages, "model": model}
    request_hash = sha256_hash(canonical_json(request_payload))

    # 2. Call API with stream=True and accumulate
    stream = client.chat.completions.create(model=model, messages=messages, stream=True)
    output_parts = []
    finish_reason = None
    for chunk in stream:
        choices = getattr(chunk, "choices", [])
        if choices:
            delta = getattr(choices[0], "delta", None)
            if delta:
                text = getattr(delta, "content", None)
                if text:
                    output_parts.append(text)
            fr = getattr(choices[0], "finish_reason", None)
            if fr:
                finish_reason = fr
    output_text = "".join(output_parts)
    if not output_text:
        raise ValueError("Cannot extract output: stream produced no content")

    # 3. response_hash over accumulated content
    response_data = {"content": output_text, "model": model}
    response_hash = sha256_hash(canonical_json(response_data))

    # 4. binding_hash
    binding_hash = sha256_hash(canonical_json({"request_hash": request_hash, "response_hash": response_hash}))

    # 5. Build payload
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prompt_str = canonical_json(messages)
    capture_meta: Dict[str, Any] = {
        "provider": "openai",
        "sdk": "openai-python",
        "request_hash": request_hash,
        "response_hash": response_hash,
        "binding_hash": binding_hash,
        "finish_reason": finish_reason,
        "captured_at_utc": ts,
        "streaming": True,
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

    result = ai_pack_from_obj(payload)
    manifest_with_binding = {**result.manifest, "binding_hash": binding_hash}

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    (out_path / "ai_canonical.json").write_text(result.canonical_json + "\n", encoding="utf-8")
    (out_path / "ai_manifest.json").write_text(json.dumps(manifest_with_binding, sort_keys=True) + "\n", encoding="utf-8")

    # Optional signing
    signed = _try_sign(out_path)

    # For streaming there is no single response object — return None as response
    return CaptureResult(response=None, bundle_dir=out_path, ai_hash_sha256=result.ai_hash_sha256, signed=signed)
