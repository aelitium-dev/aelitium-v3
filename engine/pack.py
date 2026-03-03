import json
import os
from pathlib import Path

if __package__ in (None, ""):
    from canonical import canonicalize_and_hash
    from signing import build_verification_material
else:
    from .canonical import canonicalize_and_hash
    from .signing import build_verification_material

BUNDLE_SCHEMA = "1.1"


def _load_input(input_path: str) -> dict:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Minimal schema validation (fail-closed)
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    if data.get("schema_version") != "input_v1":
        raise ValueError("schema_version must be input_v1")
    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    return data


def pack(input_path: str, output_dir: str):
    data = _load_input(input_path)
    payload = data["payload"]

    canonical, digest = canonicalize_and_hash(payload)

    os.makedirs(output_dir, exist_ok=True)

    manifest = {
        "bundle_schema": BUNDLE_SCHEMA,
        "schema_version": "1.0",
        "input_schema": data["schema_version"],
        "input_hash": digest,
        "hash_alg": "sha256",
        "canonicalization": "json.dumps(sort_keys,separators,utf8)",
    }

    evidence = {
        "canonical_payload": canonical,
        "hash": digest,
    }

    manifest_path = Path(output_dir) / "manifest.json"
    evidence_path = Path(output_dir) / "evidence_pack.json"
    verification_keys_path = Path(output_dir) / "verification_keys.json"

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    with evidence_path.open("w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False)

    verification_keys = build_verification_material(manifest_path.read_bytes())

    with verification_keys_path.open("w", encoding="utf-8") as f:
        json.dump(verification_keys, f, indent=2, ensure_ascii=False)
