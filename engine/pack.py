import json
import os
from canonical import canonicalize_and_hash


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

    # Real structure (no textual placeholders)
    verification_keys = {
        "keyring_format": "none",
        "keys": [],
    }

    with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    with open(os.path.join(output_dir, "evidence_pack.json"), "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False)

    with open(os.path.join(output_dir, "verification_keys.json"), "w", encoding="utf-8") as f:
        json.dump(verification_keys, f, indent=2, ensure_ascii=False)
