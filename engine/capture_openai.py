"""
Minimal OpenAI capture adapter for chat completion responses.

This adapter accepts a response object already returned by the OpenAI SDK
(or an equivalent dict), converts it into ai_output_v1, and writes the same
bundle artifacts produced by the existing pack logic.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .ai_pack import ai_pack_from_obj


@dataclass(frozen=True)
class OpenAICaptureResult:
    """Result of packing an OpenAI chat completion response."""

    bundle_dir: Path
    ai_hash_sha256: str
    ai_output: Dict[str, Any]


def _get_field(value: Any, field: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(field)
    return getattr(value, field, None)


def _normalize_output_text(content: Any) -> Optional[str]:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue

            if isinstance(item, Mapping):
                text = item.get("text")
            else:
                text = getattr(item, "text", None)

            if isinstance(text, str):
                parts.append(text)

        merged = "".join(parts)
        if merged:
            return merged

    return None


def _extract_output_text(response: Any) -> str:
    choices = _get_field(response, "choices")
    try:
        first_choice = choices[0]
    except Exception as exc:  # noqa: BLE001 - provide domain error below
        raise ValueError(
            "Could not extract output text from response: missing choices[0]"
        ) from exc

    message = _get_field(first_choice, "message")
    if message is None:
        raise ValueError(
            "Could not extract output text from response: missing choices[0].message"
        )

    content = _get_field(message, "content")
    output_text = _normalize_output_text(content)
    if output_text is None:
        raise ValueError(
            "Could not extract output text from response: missing "
            "choices[0].message.content"
        )
    return output_text


def _extract_model(response: Any) -> Optional[str]:
    model = _get_field(response, "model")
    if isinstance(model, str) and model.strip():
        return model
    return None


def pack_openai_chat_completion(
    response: Any,
    *,
    prompt: str,
    out_dir: str | Path,
    model: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> OpenAICaptureResult:
    """
    Convert an OpenAI chat completion response into ai_output_v1 and pack it.

    Args:
        response: OpenAI SDK response object or dict equivalent.
        prompt: Original prompt string.
        out_dir: Output directory for ai_canonical.json and ai_manifest.json.
        model: Optional explicit model override.
        metadata: Optional metadata object merged as-is.
    """
    if not isinstance(prompt, str):
        raise TypeError("prompt must be a string")
    if metadata is not None and not isinstance(metadata, Mapping):
        raise TypeError("metadata must be a dict-like object when provided")

    output_text = _extract_output_text(response)

    model_name = model if model is not None else _extract_model(response)
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError(
            "Could not determine model from response. Pass model='...'."
        )

    payload: Dict[str, Any] = {
        "schema_version": "ai_output_v1",
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": model_name,
        "prompt": prompt,
        "output": output_text,
        "metadata": dict(metadata or {}),
    }

    packed = ai_pack_from_obj(payload)

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    (out_path / "ai_canonical.json").write_text(
        packed.canonical_json + "\n", encoding="utf-8"
    )
    (out_path / "ai_manifest.json").write_text(
        json.dumps(packed.manifest, sort_keys=True) + "\n", encoding="utf-8"
    )

    return OpenAICaptureResult(
        bundle_dir=out_path,
        ai_hash_sha256=packed.ai_hash_sha256,
        ai_output=payload,
    )

