import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .ai_canonical import canonicalize_ai_output
from .ai_contract import (
    AI_CANONICALIZATION,
    AI_CANONICALIZATION_IDENTIFIERS,
    AI_CANONICALIZATION_V2,
    AI_MANIFEST_SCHEMA,
    AI_OUTPUT_SCHEMA_VERSION,
)
from .canonical_v2 import parse_json_v2

@dataclass(frozen=True)
class AIPackResult:
    canonical_json: str
    ai_hash_sha256: str
    manifest: Dict[str, Any]

def ai_pack_from_obj(
    obj: Any,
    *,
    canonicalization: str = AI_CANONICALIZATION,
) -> AIPackResult:
    if canonicalization not in AI_CANONICALIZATION_IDENTIFIERS:
        raise ValueError(f"unsupported canonicalization: {canonicalization}")
    canon, h = canonicalize_ai_output(obj, canonicalization)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "schema": AI_MANIFEST_SCHEMA,
        "ts_utc": ts,
        "input_schema": AI_OUTPUT_SCHEMA_VERSION,
        "canonicalization": canonicalization,
        "ai_hash_sha256": h,
    }
    return AIPackResult(canonical_json=canon, ai_hash_sha256=h, manifest=manifest)

def ai_pack_from_path(
    path: str | Path,
    *,
    canonicalization: str = AI_CANONICALIZATION,
) -> AIPackResult:
    p = Path(path)
    if canonicalization == AI_CANONICALIZATION_V2:
        obj = parse_json_v2(p.read_bytes())
    else:
        obj = json.loads(p.read_text(encoding="utf-8"))
    return ai_pack_from_obj(obj, canonicalization=canonicalization)
