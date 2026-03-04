import json
from typing import Any, Tuple

from .canonical import sha256_hash


class AICanonicalError(ValueError):
    pass


def canonicalize_ai_output(obj: Any) -> Tuple[str, str]:
    """
    Canonicalize an ai_output_v1 object into deterministic JSON bytes (as str)
    and return (canonical_json_str, sha256_hex).

    Fail-closed:
    - must be a dict
    - schema_version must be "ai_output_v1"
    """
    if not isinstance(obj, dict):
        raise AICanonicalError("AI_OUTPUT_NOT_OBJECT")

    if obj.get("schema_version") != "ai_output_v1":
        raise AICanonicalError("AI_OUTPUT_BAD_SCHEMA_VERSION")

    # Canonical JSON: sorted keys, UTF-8, no whitespace
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = sha256_hash(canonical)
    return canonical, digest
