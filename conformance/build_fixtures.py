#!/usr/bin/env python3
"""Deterministically build the frozen public conformance artifacts.

The conformance runner never calls this script. Maintainers may use ``--check``
to prove that committed artifacts still match this recipe, or ``--write`` after
an intentional corpus update.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from engine.canonical import canonical_json, sha256_hash
from engine.invocation import (
    MODE_SYNC_NON_STREAMING,
    SURFACE_ANTHROPIC_MESSAGES,
    SURFACE_LITELLM_COMPLETION,
    build_invocation_identity,
)
from engine.invocation_binding import build_invocation_binding


ROOT = Path(__file__).resolve().parent
FIXED_TIME = "2026-01-15T12:00:00Z"
MANIFEST_TIME = "2026-01-15T12:00:01Z"
MESSAGES = (
    {"role": "system", "content": "Answer with one short sentence."},
    {"role": "user", "content": "What color is the clear daytime sky?"},
)
# Public deterministic fixture seeds, not secret or production key material.
LEGITIMATE_PRIVATE_KEY = bytes(range(32))
ATTACKER_PRIVATE_KEY = bytes(range(32, 64))


def _json_bytes(value: Any, *, compact: bool = False) -> bytes:
    separators = (",", ":") if compact else None
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=separators,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _base_bundle(
    *,
    output: str = "The clear daytime sky appears blue.",
    request_model: str = "fixture-request-model",
    response_model: str = "fixture-response-model",
    messages: tuple[dict[str, str], ...] = MESSAGES,
    parameters: dict[str, Any] | None = None,
    surface: str = SURFACE_LITELLM_COMPLETION,
    timestamp: str = FIXED_TIME,
    include_binding: bool = True,
    include_identity: bool = True,
    include_invocation_binding: bool = True,
) -> dict[str, bytes]:
    message_list = [dict(message) for message in messages]
    request_hash = sha256_hash(
        canonical_json({"messages": message_list, "model": request_model})
    )
    response_hash = sha256_hash(
        canonical_json({"content": output, "model": response_model})
    )
    binding_hash = sha256_hash(
        canonical_json(
            {"request_hash": request_hash, "response_hash": response_hash}
        )
    )

    metadata: dict[str, Any] = {}
    if include_binding:
        metadata.update(
            {
                "request_hash": request_hash,
                "response_hash": response_hash,
                "binding_hash": binding_hash,
            }
        )

    identity = None
    if include_identity:
        identity = build_invocation_identity(
            surface=surface,
            mode=MODE_SYNC_NON_STREAMING,
            model=request_model,
            messages=message_list,
            parameters=parameters,
        )
        metadata["invocation_identity"] = identity.to_stored_object()

    if include_invocation_binding:
        if identity is None or not include_binding:
            raise ValueError("invocation binding requires identity and response hash")
        metadata["invocation_binding"] = build_invocation_binding(
            invocation_hash=identity.hash_sha256,
            response_hash=response_hash,
        ).to_stored_object()

    canonical = {
        "schema_version": "ai_output_v1",
        "model": response_model,
        "prompt": "What color is the clear daytime sky?",
        "output": output,
        "ts_utc": timestamp,
        "metadata": metadata,
    }
    canonical_bytes = _json_bytes(canonical, compact=True)
    canonical_digest = hashlib.sha256(canonical_bytes[:-1]).hexdigest()
    manifest = {
        "schema": "ai_pack_manifest_v1",
        "ts_utc": MANIFEST_TIME,
        "input_schema": "ai_output_v1",
        "canonicalization": "json_sorted_keys_no_whitespace_utf8",
        "ai_hash_sha256": canonical_digest,
    }
    if include_binding:
        manifest["binding_hash"] = binding_hash
    return {
        "ai_canonical.json": canonical_bytes,
        "ai_manifest.json": _json_bytes(manifest),
    }


def _decoded(files: dict[str, bytes], name: str) -> Any:
    return json.loads(files[name].decode("utf-8"))


def _replace_canonical(
    files: dict[str, bytes],
    canonical: dict[str, Any],
    *,
    repair_manifest_digest: bool = True,
    compact: bool = True,
) -> None:
    canonical_bytes = _json_bytes(canonical, compact=compact)
    files["ai_canonical.json"] = canonical_bytes
    if repair_manifest_digest:
        manifest = _decoded(files, "ai_manifest.json")
        manifest["ai_hash_sha256"] = hashlib.sha256(
            canonical_json(canonical).encode("utf-8")
        ).hexdigest()
        files["ai_manifest.json"] = _json_bytes(manifest)


def _sign(files: dict[str, bytes], private_bytes: bytes) -> None:
    private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    signature = private_key.sign(files["ai_manifest.json"])
    files["verification_keys.json"] = _json_bytes(
        {
            "keyring_format": "ed25519-v1",
            "keys": [
                {
                    "key_id": "conformance-key",
                    "public_key_b64": base64.b64encode(public_bytes).decode("ascii"),
                }
            ],
            "signatures": [
                {
                    "key_id": "conformance-key",
                    "algorithm": "ed25519",
                    "scope": "manifest.json",
                    "sig_b64": base64.b64encode(signature).decode("ascii"),
                }
            ],
        }
    )


def _trust_store(private_bytes: bytes) -> bytes:
    private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _json_bytes(
        {
            "trust_store_format": "aelitium-trust-v1",
            "signers": [
                {
                    "algorithm": "ed25519",
                    "public_key_b64": base64.b64encode(public_bytes).decode("ascii"),
                    "label": "frozen conformance key",
                }
            ],
        }
    )


def build_files() -> dict[Path, bytes]:
    bundles: dict[str, dict[str, bytes]] = {}

    bundles["full_a"] = _base_bundle(parameters={"temperature": 0.0})
    bundles["full_b_changed_response"] = _base_bundle(
        output="The clear daytime sky often appears azure.",
        parameters={"temperature": 0.0},
    )
    bundles["temperature_changed"] = _base_bundle(parameters={"temperature": 1.0})
    bundles["model_changed"] = _base_bundle(
        request_model="fixture-request-model-v2",
        parameters={"temperature": 0.0},
    )
    bundles["system_instruction_changed"] = _base_bundle(
        messages=(
            {"role": "system", "content": "Answer with exactly one word."},
            MESSAGES[1],
        ),
        parameters={"temperature": 0.0},
    )
    bundles["adapter_surface_changed"] = _base_bundle(
        surface=SURFACE_ANTHROPIC_MESSAGES,
        parameters={"max_tokens": 1024},
    )
    bundles["legacy_a"] = _base_bundle(
        parameters={"temperature": 0.0},
        include_identity=False,
        include_invocation_binding=False,
    )
    bundles["legacy_b_changed_response"] = _base_bundle(
        output="The clear daytime sky often appears azure.",
        parameters={"temperature": 0.0},
        include_identity=False,
        include_invocation_binding=False,
    )
    bundles["legacy_request_changed"] = _base_bundle(
        request_model="different-request-model",
        include_identity=False,
        include_invocation_binding=False,
    )
    bundles["identity_only"] = _base_bundle(
        parameters={"temperature": 0.0},
        include_invocation_binding=False,
    )
    bundles["unbound"] = _base_bundle(
        include_binding=False,
        include_identity=False,
        include_invocation_binding=False,
    )
    bundles["malformed_timestamp"] = _base_bundle(
        parameters={"temperature": 0.0},
        timestamp="not-a-timestamp",
    )
    bundles["self_consistent_rewrite"] = _base_bundle(
        output="A replacement artifact can remain internally consistent.",
        request_model="rewritten-request-model",
        response_model="rewritten-response-model",
        parameters={"temperature": 0.75},
    )

    payload_tamper = dict(bundles["full_a"])
    payload_tamper["ai_canonical.json"] = payload_tamper[
        "ai_canonical.json"
    ].replace(b"appears blue", b"appears cyan", 1)
    bundles["payload_tamper"] = payload_tamper

    manifest_mismatch = dict(bundles["full_a"])
    manifest = _decoded(manifest_mismatch, "ai_manifest.json")
    manifest["ai_hash_sha256"] = "0" * 64
    manifest_mismatch["ai_manifest.json"] = _json_bytes(manifest)
    bundles["manifest_hash_mismatch"] = manifest_mismatch

    malformed_schema = dict(bundles["full_a"])
    canonical = _decoded(malformed_schema, "ai_canonical.json")
    canonical.pop("output")
    _replace_canonical(malformed_schema, canonical)
    bundles["malformed_schema"] = malformed_schema

    canonical_bytes_mismatch = dict(bundles["full_a"])
    canonical = _decoded(canonical_bytes_mismatch, "ai_canonical.json")
    _replace_canonical(canonical_bytes_mismatch, canonical, compact=False)
    bundles["canonical_bytes_mismatch"] = canonical_bytes_mismatch

    binding_mismatch = dict(bundles["full_a"])
    canonical = _decoded(binding_mismatch, "ai_canonical.json")
    canonical["metadata"]["request_hash"] = "f" * 64
    _replace_canonical(binding_mismatch, canonical)
    bundles["binding_mismatch"] = binding_mismatch

    malformed_invocation = dict(bundles["full_a"])
    canonical = _decoded(malformed_invocation, "ai_canonical.json")
    canonical["metadata"]["invocation_identity"]["hash_sha256"] = "f" * 64
    _replace_canonical(malformed_invocation, canonical)
    bundles["malformed_invocation"] = malformed_invocation

    binding_cross_mismatch = dict(bundles["full_a"])
    canonical = _decoded(binding_cross_mismatch, "ai_canonical.json")
    canonical["metadata"]["invocation_binding"] = build_invocation_binding(
        invocation_hash="e" * 64,
        response_hash=canonical["metadata"]["response_hash"],
    ).to_stored_object()
    _replace_canonical(binding_cross_mismatch, canonical)
    bundles["invocation_binding_mismatch"] = binding_cross_mismatch

    signed_valid = dict(bundles["full_a"])
    _sign(signed_valid, LEGITIMATE_PRIVATE_KEY)
    bundles["signed_valid"] = signed_valid

    signed_invalid = dict(signed_valid)
    verification_keys = _decoded(signed_invalid, "verification_keys.json")
    verification_keys["signatures"][0]["sig_b64"] = base64.b64encode(
        bytes(64)
    ).decode("ascii")
    signed_invalid["verification_keys.json"] = _json_bytes(verification_keys)
    bundles["signed_invalid"] = signed_invalid

    attacker_substitution = dict(bundles["full_a"])
    _sign(attacker_substitution, ATTACKER_PRIVATE_KEY)
    bundles["attacker_key_substitution"] = attacker_substitution

    files: dict[Path, bytes] = {}
    for bundle_name, bundle_files in bundles.items():
        for filename, content in bundle_files.items():
            files[Path("fixtures/bundles") / bundle_name / filename] = content
    files[Path("fixtures/trust/legitimate.json")] = _trust_store(
        LEGITIMATE_PRIVATE_KEY
    )
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--write", action="store_true")
    args = parser.parse_args()

    expected = build_files()
    mismatches: list[str] = []
    for relative, content in sorted(expected.items(), key=lambda item: str(item[0])):
        path = ROOT / relative
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        elif not path.exists() or path.read_bytes() != content:
            mismatches.append(str(relative))

    if mismatches:
        for mismatch in mismatches:
            print(f"MISMATCH {mismatch}")
        return 1
    print(f"FIXTURES={'WRITTEN' if args.write else 'MATCH'} files={len(expected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
