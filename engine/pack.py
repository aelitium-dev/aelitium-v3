import json
import os
from canonical import canonicalize_and_hash


def pack(input_path: str, output_dir: str):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    canonical, digest = canonicalize_and_hash(data)

    os.makedirs(output_dir, exist_ok=True)

    manifest = {
        "schema_version": "1.0",
        "input_hash": digest,
    }

    evidence = {
        "canonical_payload": canonical,
        "hash": digest,
    }

    with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    with open(os.path.join(output_dir, "evidence_pack.json"), "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)
