import json
from pathlib import Path
from typing import Any, Tuple

from jsonschema import Draft7Validator

from .ai_contract import (
    AI_CANONICALIZATION,
    AI_CANONICALIZATION_V2,
    AI_OUTPUT_SCHEMA_FILENAME,
    AI_OUTPUT_SCHEMA_VERSION,
)
from .canonical import CanonicalizationError, canonical_json, sha256_hash
from .canonical_v2 import canonical_json_v2


class AICanonicalError(ValueError):
    pass


_AI_OUTPUT_SCHEMA_PATH = Path(__file__).with_name("schemas") / AI_OUTPUT_SCHEMA_FILENAME
_AI_OUTPUT_SCHEMA = json.loads(_AI_OUTPUT_SCHEMA_PATH.read_text(encoding="utf-8"))
Draft7Validator.check_schema(_AI_OUTPUT_SCHEMA)
_AI_OUTPUT_VALIDATOR = Draft7Validator(_AI_OUTPUT_SCHEMA)


def validate_ai_output(obj: Any) -> None:
    """Validate an object against the authoritative ai_output_v1 schema."""

    if not isinstance(obj, dict):
        raise AICanonicalError("AI_OUTPUT_NOT_OBJECT")

    if obj.get("schema_version") != AI_OUTPUT_SCHEMA_VERSION:
        raise AICanonicalError("AI_OUTPUT_BAD_SCHEMA_VERSION")

    if next(_AI_OUTPUT_VALIDATOR.iter_errors(obj), None) is not None:
        raise AICanonicalError("AI_OUTPUT_SCHEMA_INVALID")


def canonicalize_ai_output(
    obj: Any,
    canonicalization: str = AI_CANONICALIZATION,
) -> Tuple[str, str]:
    """
    Canonicalize an ai_output_v1 object into deterministic JSON bytes (as str)
    and return (canonical_json_str, sha256_hex).

    Fail-closed:
    - must be a dict
    - schema_version must be "ai_output_v1"
    """
    validate_ai_output(obj)

    try:
        if canonicalization == AI_CANONICALIZATION:
            # This is the complete frozen v1 operation.
            canonical = canonical_json(obj)
        elif canonicalization == AI_CANONICALIZATION_V2:
            canonical = canonical_json_v2(obj)
        else:
            raise ValueError(f"unsupported canonicalization: {canonicalization}")
    except CanonicalizationError as exc:
        raise AICanonicalError("AI_OUTPUT_INVALID_UNICODE") from exc
    digest = sha256_hash(canonical)
    return canonical, digest
