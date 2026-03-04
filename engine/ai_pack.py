import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

from .canonical import canonical_json  # já existe no core
from .canonical import sha256_hash     # já existe no core

@dataclass(frozen=True)
class AIPackResult:
    canonical_json: str
    ai_hash_sha256: str
    manifest: Dict[str, Any]

def ai_pack_from_obj(obj: Dict[str, Any]) -> AIPackResult:
    # canonical JSON (sorted keys, no whitespace)
    canon = canonical_json(obj)
    h = sha256_hash(canon)  # expects str
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "schema": "ai_pack_manifest_v1",
        "ts_utc": ts,
        "input_schema": obj.get("schema_version", None),
        "canonicalization": "json_sorted_keys_no_whitespace_utf8",
        "ai_hash_sha256": h,
    }
    return AIPackResult(canonical_json=canon, ai_hash_sha256=h, manifest=manifest)

def ai_pack_from_path(path: str | Path) -> AIPackResult:
    p = Path(path)
    obj = json.loads(p.read_text(encoding="utf-8"))
    return ai_pack_from_obj(obj)
