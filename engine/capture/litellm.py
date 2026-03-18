"""
AELITIUM capture adapter for LiteLLM.

LiteLLM is a proxy/router that exposes an OpenAI-compatible interface
over multiple providers (OpenAI, Anthropic, Bedrock, Cohere, etc.).

This adapter intercepts litellm.completion() calls and packs the
request+response into a tamper-evident bundle, using the same
evidence model as the OpenAI and Anthropic adapters.

Scope (v1):
- litellm.completion() (synchronous, non-streaming)
- optional Ed25519 signing at capture time

Not in scope:
- streaming (litellm.completion(..., stream=True))
- async (litellm.acompletion)
- tool calls, function calling, retries
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..canonical import canonical_json, sha256_hash
from ..ai_pack import ai_pack_from_obj
from .openai import CaptureResult, _try_sign


def capture_completion(
    model: str,
    messages: List[Dict[str, str]],
    out_dir: str | Path,
    metadata: Optional[Dict[str, Any]] = None,
    _pre_response: Optional[Any] = None,
    **litellm_kwargs: Any,
) -> CaptureResult:
    """
    Call litellm.completion() and pack the result into a tamper-evident bundle.

    Args:
        model:           LiteLLM model string, e.g. "openai/gpt-4o",
                         "anthropic/claude-3-5-sonnet-20241022", "bedrock/...".
        messages:        List of {"role": ..., "content": ...} dicts.
        out_dir:         Directory where the bundle will be written.
        metadata:        Optional extra fields merged into bundle metadata.
        **litellm_kwargs: Additional kwargs forwarded to litellm.completion()
                          (e.g. temperature, max_tokens). These do not affect
                          request_hash — they are sampling parameters.

    Returns:
        CaptureResult with the original response, bundle path, hash, and signed flag.

    The bundle is written to:
        <out_dir>/ai_canonical.json
        <out_dir>/ai_manifest.json
        <out_dir>/verification_keys.json  (if signing key is configured)

    Trust boundary:
        request_hash covers the model string as passed (including provider prefix)
        and the exact messages list. response_hash covers the provider-confirmed
        model name and the extracted content. binding_hash links the two.

        This adapter records request/response data in the same process boundary as the call path and then packs a tamper-evident bundle.
        It supports tamper-evident verification from packing onward.
        It does NOT prove that the underlying provider is honest or that the model output is correct.

    Note on model string:
        LiteLLM model strings include a provider prefix (e.g. "openai/gpt-4o").
        request_hash uses the model string exactly as passed — this is what was
        asked for. response_hash uses response.model (provider-confirmed) — this
        is what was returned. The two may differ; both are recorded in metadata.
    """
    try:
        import litellm as _litellm
    except ImportError:
        raise ImportError(
            "LiteLLM adapter requires the 'litellm' package. "
            "Install it with: pip install aelitium[litellm]"
        )

    # 1. Hash the request before sending — records exactly what was asked
    request_payload = {"messages": messages, "model": model}
    request_hash = sha256_hash(canonical_json(request_payload))

    # 2. Call LiteLLM (or use pre-obtained response — avoids double LLM call in enable())
    if _pre_response is not None:
        response = _pre_response
    else:
        response = _litellm.completion(model=model, messages=messages, **litellm_kwargs)

    # 3. Extract output text (OpenAI-compatible response)
    choices = getattr(response, "choices", None)
    if not choices:
        raise ValueError("Cannot extract output: response.choices is empty or missing")
    message = getattr(choices[0], "message", None)
    if message is None:
        raise ValueError("Cannot extract output: choices[0].message is missing")
    content = getattr(message, "content", None)
    if not isinstance(content, str) or not content:
        raise ValueError("Cannot extract output: choices[0].message.content is None or empty")
    output_text = content

    # 4. Hash the response — use provider-confirmed model name
    confirmed_model = getattr(response, "model", model)
    response_data = {"content": output_text, "model": confirmed_model}
    response_hash = sha256_hash(canonical_json(response_data))

    # 5. Binding hash — single proof linking request↔response
    binding_hash = sha256_hash(canonical_json({
        "request_hash": request_hash,
        "response_hash": response_hash,
    }))

    # 6. Provider metadata
    def _safe_str(val: Any) -> Optional[str]:
        return val if isinstance(val, str) else None

    def _safe_int(val: Any) -> Optional[int]:
        return val if isinstance(val, int) else None

    finish_reason = None
    if choices:
        finish_reason = _safe_str(getattr(choices[0], "finish_reason", None))

    usage_obj = getattr(response, "usage", None)
    usage = None
    if usage_obj is not None and not callable(usage_obj):
        raw_prompt = getattr(usage_obj, "prompt_tokens", None)
        raw_completion = getattr(usage_obj, "completion_tokens", None)
        raw_total = getattr(usage_obj, "total_tokens", None)
        if any(isinstance(v, int) for v in (raw_prompt, raw_completion, raw_total)):
            usage = {
                "prompt_tokens": _safe_int(raw_prompt),
                "completion_tokens": _safe_int(raw_completion),
                "total_tokens": _safe_int(raw_total),
            }

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prompt_str = canonical_json(messages)

    capture_meta: Dict[str, Any] = {
        "provider": "litellm",
        "sdk": "litellm",
        "model_requested": model,           # as passed (may include provider prefix)
        "model_confirmed": confirmed_model,  # provider-confirmed (may differ)
        "request_hash": request_hash,
        "response_hash": response_hash,
        "binding_hash": binding_hash,
        "response_id": _safe_str(getattr(response, "id", None)),
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


def enable(
    out_dir: str | Path = "./aelitium/bundles",
    strict: bool = False,
    verbose: bool = False,
) -> None:
    """
    Patch litellm.completion() globally to auto-capture evidence bundles.

    Invariants:
      - wrapped(*args, **kwargs) returns identical response to original
      - side-effect: bundle written to <out_dir>/<binding_hash>/
      - LLM call errors always propagate (never swallowed)
      - streaming calls (stream=True) pass through without capture
      - bundle capture errors: warn (default) or raise if strict=True

    Args:
        out_dir:  Base directory for bundles. Each call writes to a subdirectory
                  named by ai_hash_sha256 (content-addressed).
        strict:   If True, capture failures raise RuntimeError instead of warning.
                  Also raises if streaming=True (which cannot be captured).
        verbose:  If True, prints one line per captured call:
                  AELITIUM: bundle → <path>  binding_hash=<hash>

    Removing the call to enable() must restore exactly the original behaviour.
    This function is a capture convenience layer — it does not alter the
    evidence model, verification semantics, or trust boundary.
    """
    import shutil
    import uuid
    import warnings

    try:
        import litellm as _litellm
    except ImportError:
        raise ImportError(
            "LiteLLM adapter requires the 'litellm' package. "
            "Install it with: pip install aelitium[litellm]"
        )

    base_out_dir = Path(out_dir)
    original = _litellm.completion

    def _wrapped(*args, **kwargs):
        # Streaming: cannot hash incremental chunks — pass through
        if kwargs.get("stream", False):
            if strict:
                raise RuntimeError(
                    "AELITIUM [strict]: stream=True is not supported — "
                    "bundle cannot be captured. Remove strict=True or disable streaming."
                )
            warnings.warn(
                "AELITIUM: streaming call detected — bundle not captured.",
                stacklevel=2,
            )
            return original(*args, **kwargs)

        # Normalise positional and keyword args
        _args = list(args)
        try:
            model = _args.pop(0) if _args else kwargs.pop("model")
            messages = _args.pop(0) if _args else kwargs.pop("messages")
        except KeyError:
            if strict:
                raise RuntimeError(
                    "AELITIUM [strict]: cannot extract model/messages from call signature"
                )
            warnings.warn(
                "AELITIUM: cannot extract model/messages — bundle not captured.",
                stacklevel=2,
            )
            return original(*args, **kwargs)

        # kwargs now contains only extra params (temperature, max_tokens, …)
        extra_kwargs = kwargs

        # Step 1: call original LLM — errors always propagate unchanged
        response = original(model=model, messages=messages, **extra_kwargs)

        # Step 2: pack + write — isolated from LLM call so a disk/packing
        # failure cannot suppress or alter the response the caller receives
        tmp_dir = base_out_dir / f"_tmp_{uuid.uuid4().hex}"
        try:
            result = capture_completion(
                model=model,
                messages=messages,
                out_dir=tmp_dir,
                _pre_response=response,
            )
            manifest = json.loads((tmp_dir / "ai_manifest.json").read_text())
            binding_hash = manifest["binding_hash"]
            final_dir = base_out_dir / binding_hash
            if tmp_dir.exists():
                tmp_dir.rename(final_dir)
            if verbose:
                print(
                    f"AELITIUM: bundle → {final_dir}"
                    f"  binding_hash={binding_hash}"
                )
        except Exception as exc:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)
            if strict:
                raise
            warnings.warn(
                f"AELITIUM: bundle capture failed ({exc!r}) — "
                "LLM response returned without evidence.",
                stacklevel=2,
            )

        return response

    _litellm.completion = _wrapped
