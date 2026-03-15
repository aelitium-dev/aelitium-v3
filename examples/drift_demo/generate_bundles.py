"""
Generate two evidence bundles for the drift demo.

Same request, different responses — simulates model drift.
No API key required. Uses the AELITIUM engine directly.

Run once:
    python examples/drift_demo/generate_bundles.py

Then run the demo:
    bash examples/drift_demo/run_demo.sh
"""

import json
import sys
from pathlib import Path

# Allow running from repo root or from examples/drift_demo/
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from engine.ai_pack import ai_pack_from_obj
from engine.canonical import canonical_json, sha256_hash

PROMPT = "Explain in one sentence why the sky is blue."
MODEL = "gpt-4o"

RESPONSE_A = "The sky appears blue because molecules in the atmosphere scatter shorter blue wavelengths of sunlight more than longer red wavelengths."
RESPONSE_B = "Sunlight scatters off nitrogen and oxygen molecules, and blue light scatters more than red, making the sky look blue."

def make_bundle(response_text: str, out_dir: Path) -> str:
    messages = [{"role": "user", "content": PROMPT}]

    request_payload = {"messages": messages, "model": MODEL}
    request_hash = sha256_hash(canonical_json(request_payload))

    response_data = {"content": response_text, "model": MODEL}
    response_hash = sha256_hash(canonical_json(response_data))

    binding_hash = sha256_hash(
        canonical_json({"request_hash": request_hash, "response_hash": response_hash})
    )

    payload = {
        "metadata": {
            "provider": "demo",
            "request_hash": request_hash,
            "response_hash": response_hash,
            "binding_hash": binding_hash,
        },
        "model": MODEL,
        "output": response_text,
        "prompt": canonical_json(messages),
        "schema_version": "ai_output_v1",
        "ts_utc": "2026-03-01T10:00:00Z",
    }

    result = ai_pack_from_obj(payload)
    manifest = {**result.manifest, "binding_hash": binding_hash}

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ai_canonical.json").write_text(result.canonical_json + "\n", encoding="utf-8")
    (out_dir / "ai_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result.ai_hash_sha256


if __name__ == "__main__":
    base = Path(__file__).parent
    hash_a = make_bundle(RESPONSE_A, base / "bundle_a")
    hash_b = make_bundle(RESPONSE_B, base / "bundle_b")
    print(f"bundle_a: {hash_a}")
    print(f"bundle_b: {hash_b}")
    print("Done. Run: bash examples/drift_demo/run_demo.sh")
