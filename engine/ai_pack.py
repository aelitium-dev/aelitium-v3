import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .ai_canonical import canonicalize_ai_output
from .ai_contract import (
    AI_CANONICALIZATION,
    AI_MANIFEST_SCHEMA,
    AI_OUTPUT_SCHEMA_VERSION,
)

@dataclass(frozen=True)
class AIPackResult:
    canonical_json: str
    ai_hash_sha256: str
    manifest: Dict[str, Any]

def ai_pack_from_obj(obj: Any) -> AIPackResult:
    canon, h = canonicalize_ai_output(obj)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "schema": AI_MANIFEST_SCHEMA,
        "ts_utc": ts,
        "input_schema": AI_OUTPUT_SCHEMA_VERSION,
        "canonicalization": AI_CANONICALIZATION,
        "ai_hash_sha256": h,
    }
    return AIPackResult(canonical_json=canon, ai_hash_sha256=h, manifest=manifest)

def ai_pack_from_path(path: str | Path) -> AIPackResult:
    p = Path(path)
    obj = json.loads(p.read_text(encoding="utf-8"))
    return ai_pack_from_obj(obj)
