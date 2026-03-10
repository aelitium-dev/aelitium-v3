"""
AELITIUM capture adapter for OpenAI chat completions.

Closes the trust gap by intercepting the API call directly,
instead of relying on the user to write JSON by hand.

Scope (v1):
- chat.completions.create (synchronous, non-streaming)
- happy path only

Not in scope:
- streaming, tool calls, async, retries, function calling
"""

import json
from dataclasses import dataclass
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
        CaptureResult with the original response, bundle path, and hash.

    The bundle is written to:
        <out_dir>/ai_canonical.json
        <out_dir>/ai_manifest.json

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
    output_text = response.choices[0].message.content

    # 4. Hash the response — records what the model returned
    #    We use a stable subset: model name + content (avoids unstable fields
    #    like usage tokens or system fingerprint that vary per call)
    response_data = {"content": output_text, "model": response.model}
    response_hash = sha256_hash(canonical_json(response_data))

    # 5. Build ai_output_v1 payload
    #    prompt is serialized as canonical JSON of the messages list,
    #    so it is deterministic regardless of insertion order.
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prompt_str = canonical_json(messages)

    capture_meta: Dict[str, Any] = {
        "provider": "openai",
        "request_hash": request_hash,
        "response_hash": response_hash,
        "sdk": "openai-python",
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

    # 6. Pack into evidence bundle
    result = ai_pack_from_obj(payload)

    # 7. Write bundle to disk
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    (out_path / "ai_canonical.json").write_text(
        result.canonical_json + "\n", encoding="utf-8"
    )
    (out_path / "ai_manifest.json").write_text(
        json.dumps(result.manifest, sort_keys=True) + "\n", encoding="utf-8"
    )

    return CaptureResult(
        response=response,
        bundle_dir=out_path,
        ai_hash_sha256=result.ai_hash_sha256,
    )
