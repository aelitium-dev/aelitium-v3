"""
Compliance export utilities for AELITIUM evidence bundles.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def export_eu_ai_act_art12(bundle_dir: Path | str) -> Dict[str, Any]:
    """
    Read ai_canonical.json + ai_manifest.json and return EU AI Act Article 12 format.
    """
    bundle_dir = Path(bundle_dir)
    canonical = json.loads((bundle_dir / "ai_canonical.json").read_text(encoding="utf-8"))
    manifest = json.loads((bundle_dir / "ai_manifest.json").read_text(encoding="utf-8"))

    metadata = canonical.get("metadata", {})
    prompt = canonical.get("prompt", "")

    # hash the prompt to avoid exposing content
    import hashlib
    input_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    return {
        "regulation": "EU AI Act",
        "article": "Art. 12 - Record-keeping",
        "schema_version": "aelitium-compliance-v1",
        "ts_generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "system_identifier": "aelitium-evidence-bundle",
        "log_entry": {
            "ts_utc": canonical.get("ts_utc"),
            "model": canonical.get("model"),
            "input_hash": input_hash,
            "output_hash": manifest.get("ai_hash_sha256"),
            "binding_hash": manifest.get("binding_hash"),
            "provider_created_at": metadata.get("provider_created_at"),
            "response_id": metadata.get("response_id"),
            "finish_reason": metadata.get("finish_reason"),
        },
        "verification": {
            "bundle_dir": str(bundle_dir.resolve()),
            "manifest_schema": "ai_pack_manifest_v1",
            "canonicalization": "json_sorted_keys_no_whitespace_utf8",
        },
    }
