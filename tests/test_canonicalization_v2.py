from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from engine.ai_contract import (
    AI_CANONICALIZATION_IDENTIFIERS,
    AI_CANONICALIZATION_V1,
    AI_CANONICALIZATION_V2,
)
from engine.ai_pack import ai_pack_from_obj, ai_pack_from_path
from engine.ai_verify import AssuranceState, verify_ai_bundle
from engine.canonical import sha256_hash
from engine.canonical_v2 import (
    MAX_SAFE_NUMBER,
    V2CanonicalizationError,
    canonical_json_v2,
    parse_json_v2,
)
from engine.canonicalization import canonical_json_for_identifier
from engine.invocation import (
    MODE_SYNC_NON_STREAMING,
    SURFACE_LITELLM_COMPLETION,
    build_invocation_identity,
)
from engine.invocation_binding import build_invocation_binding
from engine.manifest_dispatch import DispatchScanError, scan_manifest_selector
from engine.signing import build_verification_material


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "conformance" / "canonicalization_v2"
TEST_KEY = (ROOT / "tests/fixtures/ed25519_test_private_key.b64").read_text(
    encoding="utf-8"
).strip()
BASE_CANONICAL = (
    b'{"metadata":{},"model":"m","output":"o","prompt":"p",'
    b'"schema_version":"ai_output_v1",'
    b'"ts_utc":"2026-01-01T00:00:00Z"}'
)
BASE_CANONICAL_DIGEST = hashlib.sha256(BASE_CANONICAL).hexdigest().encode("ascii")


def _payload(metadata: dict | None = None) -> dict:
    return {
        "metadata": metadata or {},
        "model": "m",
        "output": "o",
        "prompt": "p",
        "schema_version": "ai_output_v1",
        "ts_utc": "2026-01-01T00:00:00Z",
    }


def _write_pack(bundle: Path, packed, *, manifest: dict | None = None) -> bytes:
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "ai_canonical.json").write_bytes(
        packed.canonical_json.encode("utf-8") + b"\n"
    )
    manifest_bytes = (
        json.dumps(manifest or packed.manifest, sort_keys=True) + "\n"
    ).encode("utf-8")
    (bundle / "ai_manifest.json").write_bytes(manifest_bytes)
    return manifest_bytes


def _deep_manifest(
    identifier: str,
    *,
    kind: str,
    depth: int,
    position: str,
    malformed: bool = False,
) -> bytes:
    closing_count = depth - (1 if malformed else 0)
    if kind == "array":
        extension_value = b"[" * depth + b"0" + b"]" * closing_count
    else:
        extension_value = b'{"x":' * depth + b"0" + b"}" * closing_count
    extension = b'"extension":' + extension_value + b","
    selector = b'"canonicalization":"' + identifier.encode("ascii") + b'",'
    middle = extension + selector if position == "before" else selector + extension
    return (
        b'{"schema":"ai_pack_manifest_v1",'
        b'"ts_utc":"2026-01-01T00:00:00Z",'
        b'"input_schema":"ai_output_v1",'
        + middle
        + b'"ai_hash_sha256":"'
        + BASE_CANONICAL_DIGEST
        + b'"}'
    )


def _verify_manifest_bytes(source: bytes):
    with tempfile.TemporaryDirectory() as directory:
        bundle = Path(directory)
        (bundle / "ai_canonical.json").write_bytes(BASE_CANONICAL)
        (bundle / "ai_manifest.json").write_bytes(source)
        return verify_ai_bundle(bundle)


class TestPortableV2Corpus(unittest.TestCase):
    def test_manifest_freezes_separate_114_case_corpus(self):
        manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
        vectors = json.loads((CORPUS / "vectors.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["case_count"], 114)
        self.assertEqual(vectors["case_count"], 114)
        self.assertEqual(len(vectors["vectors"]), 114)
        self.assertEqual(
            manifest["canonicalization_identifier"], AI_CANONICALIZATION_V2
        )
        self.assertEqual(
            manifest["existing_corpora_unchanged"],
            {"canonicalization_v1_cases": 30, "result_contract_cases": 44},
        )
        self.assertEqual(
            len({vector["case_id"] for vector in vectors["vectors"]}), 114
        )
        for vector in vectors["vectors"]:
            source = bytes.fromhex(vector["source_bytes_hex"])
            self.assertEqual(hashlib.sha256(source).hexdigest(), vector["source_sha256"])
            expected = vector["expected"]
            if expected["canonical_utf8_hex"] is not None:
                canonical = bytes.fromhex(expected["canonical_utf8_hex"])
                self.assertEqual(
                    hashlib.sha256(canonical).hexdigest(),
                    expected["canonical_sha256"],
                )

    def test_builder_is_independent_and_matches_frozen_files(self):
        builder = ROOT / "conformance/build_canonicalization_v2_vectors.py"
        text = builder.read_text(encoding="utf-8")
        self.assertNotIn("from engine", text)
        self.assertNotIn("import engine", text)
        completed = subprocess.run(
            [sys.executable, str(builder), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_runner_is_deterministic_and_passes(self):
        outputs = []
        runner = ROOT / "conformance/run_canonicalization_v2.py"
        for _ in range(2):
            completed = subprocess.run(
                [sys.executable, str(runner), "--json"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                completed.returncode, 0, completed.stdout + completed.stderr
            )
            outputs.append(completed.stdout)
        self.assertEqual(outputs[0], outputs[1])
        summary = json.loads(outputs[0])
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["cases"], 114)


class TestDispatchRecursionIsolation(unittest.TestCase):
    def test_valid_routing_straddles_old_scanner_boundaries(self):
        original_limit = sys.getrecursionlimit()
        try:
            for recursion_limit, depths in (
                (500, (240, 260)),
                (1000, (480, 520)),
            ):
                sys.setrecursionlimit(recursion_limit)
                for identifier in (
                    AI_CANONICALIZATION_V1,
                    AI_CANONICALIZATION_V2,
                ):
                    for kind in ("array", "object"):
                        for position in ("before", "after"):
                            for depth in depths:
                                with self.subTest(
                                    recursion_limit=recursion_limit,
                                    identifier=identifier,
                                    kind=kind,
                                    position=position,
                                    depth=depth,
                                ):
                                    source = _deep_manifest(
                                        identifier,
                                        kind=kind,
                                        depth=depth,
                                        position=position,
                                    )
                                    self.assertEqual(
                                        scan_manifest_selector(
                                            source,
                                            registered_identifiers=(
                                                AI_CANONICALIZATION_IDENTIFIERS
                                            ),
                                        ),
                                        identifier,
                                    )
                                    self.assertIsInstance(
                                        json.loads(source.decode("utf-8")), dict
                                    )
                                    self.assertIsInstance(parse_json_v2(source), dict)
                                    result = _verify_manifest_bytes(source)
                                    self.assertTrue(result.valid, result)
                                    self.assertEqual(result.reason, "OK")
        finally:
            sys.setrecursionlimit(original_limit)

    def test_deep_malformed_values_never_partially_dispatch(self):
        original_limit = sys.getrecursionlimit()
        try:
            for recursion_limit, depth in ((500, 260), (1000, 520)):
                sys.setrecursionlimit(recursion_limit)
                for kind in ("array", "object"):
                    for position in ("before", "after"):
                        with self.subTest(
                            recursion_limit=recursion_limit,
                            kind=kind,
                            position=position,
                        ):
                            source = _deep_manifest(
                                AI_CANONICALIZATION_V2,
                                kind=kind,
                                depth=depth,
                                position=position,
                                malformed=True,
                            )
                            with self.assertRaises(DispatchScanError):
                                scan_manifest_selector(
                                    source,
                                    registered_identifiers=(
                                        AI_CANONICALIZATION_IDENTIFIERS
                                    ),
                                )
                            with self.assertRaises(
                                (json.JSONDecodeError, RecursionError)
                            ):
                                json.loads(source.decode("utf-8"))
                            with self.assertRaises(V2CanonicalizationError) as raised:
                                parse_json_v2(source)
                            self.assertEqual(raised.exception.reason, "INVALID_JSON")
                            result = _verify_manifest_bytes(source)
                            self.assertFalse(result.valid)
                            self.assertEqual(result.reason, "MANIFEST_NOT_JSON")
        finally:
            sys.setrecursionlimit(original_limit)

    def test_depth_10000_v2_is_iterative_while_v1_behavior_is_unchanged(self):
        original_limit = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(500)
            v2_source = _deep_manifest(
                AI_CANONICALIZATION_V2,
                kind="array",
                depth=10_000,
                position="before",
            )
            self.assertEqual(
                scan_manifest_selector(
                    v2_source,
                    registered_identifiers=AI_CANONICALIZATION_IDENTIFIERS,
                ),
                AI_CANONICALIZATION_V2,
            )
            self.assertIsInstance(parse_json_v2(v2_source), dict)
            self.assertTrue(_verify_manifest_bytes(v2_source).valid)

            v1_source = _deep_manifest(
                AI_CANONICALIZATION_V1,
                kind="array",
                depth=10_000,
                position="before",
            )
            self.assertEqual(
                scan_manifest_selector(
                    v1_source,
                    registered_identifiers=AI_CANONICALIZATION_IDENTIFIERS,
                ),
                AI_CANONICALIZATION_V1,
            )
            with self.assertRaises(RecursionError):
                json.loads(v1_source.decode("utf-8"))
            v1_result = _verify_manifest_bytes(v1_source)
            self.assertFalse(v1_result.valid)
            self.assertEqual(v1_result.reason, "MANIFEST_NOT_JSON")
        finally:
            sys.setrecursionlimit(original_limit)


class TestPortableV2Dependency(unittest.TestCase):
    def test_dependency_version_python_support_and_license_metadata(self):
        distribution = importlib.metadata.distribution("rfc8785")
        self.assertEqual(distribution.version, "0.1.4")
        self.assertEqual(distribution.metadata["Requires-Python"], ">=3.8")
        classifiers = distribution.metadata.get_all("Classifier") or []
        self.assertIn("License :: OSI Approved :: Apache Software License", classifiers)
        license_files = [
            item for item in (distribution.files or []) if item.name == "LICENSE"
        ]
        self.assertTrue(license_files)
        license_text = distribution.locate_file(license_files[0]).read_text(
            encoding="utf-8"
        )
        self.assertIn("Apache License", license_text)
        self.assertIn("Version 2.0", license_text)

    def test_applicable_rfc_8785_appendix_b_number_vectors(self):
        # Appendix-B values outside the AELITIUM magnitude cap are tested as
        # rejections below; these are every listed finite value inside it.
        cases = {
            "0000000000000000": "0",
            "8000000000000000": "0",
            "0000000000000001": "5e-324",
            "8000000000000001": "-5e-324",
            "3eb0c6f7a0b5ed8c": "9.999999999999997e-7",
            "3eb0c6f7a0b5ed8d": "0.000001",
            "41b3de4355555553": "333333333.3333332",
            "41b3de4355555554": "333333333.33333325",
            "41b3de4355555555": "333333333.3333333",
            "41b3de4355555556": "333333333.3333334",
            "41b3de4355555557": "333333333.33333343",
            "becbf647612f3696": "-0.0000033333333333333333",
            "43143ff3c1cb0959": "1424953923781206.2",
        }
        for bits, expected in cases.items():
            with self.subTest(bits=bits):
                value = struct.unpack(">d", bytes.fromhex(bits))[0]
                self.assertEqual(canonical_json_v2(value), expected)

        for value in (
            float("nan"),
            float("inf"),
            -float("inf"),
            float(9_007_199_254_740_992),
        ):
            with self.subTest(value=value):
                with self.assertRaises(V2CanonicalizationError):
                    canonical_json_v2(value)


class TestPortableV2ProgrammaticDomain(unittest.TestCase):
    def test_safe_integer_boundaries_and_non_finite_values(self):
        self.assertEqual(canonical_json_v2(MAX_SAFE_NUMBER), str(MAX_SAFE_NUMBER))
        self.assertEqual(canonical_json_v2(-MAX_SAFE_NUMBER), str(-MAX_SAFE_NUMBER))
        for value in (
            MAX_SAFE_NUMBER + 1,
            -MAX_SAFE_NUMBER - 1,
            math.nan,
            math.inf,
            -math.inf,
        ):
            with self.subTest(value=value):
                with self.assertRaises(V2CanonicalizationError):
                    canonical_json_v2(value)

    def test_arbitrary_precision_and_host_coercions_are_rejected(self):
        cyclic: list[object] = []
        cyclic.append(cyclic)
        for value in (
            Decimal("1.25"),
            (1, 2),
            {1: "not a string key"},
            b"bytes",
            cyclic,
        ):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(V2CanonicalizationError):
                    canonical_json_v2(value)

    def test_noncharacters_reject_and_normalization_is_never_applied(self):
        with self.assertRaises(V2CanonicalizationError):
            canonical_json_v2({"value": "\ufdd0"})
        nfc = canonical_json_v2("é")
        nfd = canonical_json_v2("é")
        self.assertNotEqual(nfc, nfd)

    def test_path_parser_rejects_duplicates_before_map_collapse(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "payload.json"
            source.write_bytes(
                b'{"metadata":{"a":1,"a":2},"model":"m","output":"o",'
                b'"prompt":"p","schema_version":"ai_output_v1",'
                b'"ts_utc":"2026-01-01T00:00:00Z"}'
            )
            with self.assertRaises(V2CanonicalizationError) as raised:
                ai_pack_from_path(source, canonicalization=AI_CANONICALIZATION_V2)
        self.assertEqual(raised.exception.reason, "DUPLICATE_OBJECT_NAME")


class TestPortableV2BundleIntegration(unittest.TestCase):
    def test_all_bundle_hash_constructions_use_selected_v2(self):
        request = {
            "messages": [{"role": "user", "content": "p"}],
            "model": "m",
            "parameters": {"temperature": 1.0},
        }
        response = {"content": "o", "model": "m"}
        request_hash = sha256_hash(
            canonical_json_for_identifier(request, AI_CANONICALIZATION_V2)
        )
        response_hash = sha256_hash(
            canonical_json_for_identifier(response, AI_CANONICALIZATION_V2)
        )
        binding_hash = sha256_hash(
            canonical_json_for_identifier(
                {"request_hash": request_hash, "response_hash": response_hash},
                AI_CANONICALIZATION_V2,
            )
        )
        identity = build_invocation_identity(
            surface=SURFACE_LITELLM_COMPLETION,
            mode=MODE_SYNC_NON_STREAMING,
            model="m",
            messages=request["messages"],
            parameters=request["parameters"],
            canonicalization=AI_CANONICALIZATION_V2,
        ).to_stored_object()
        invocation_binding = build_invocation_binding(
            invocation_hash=identity["hash_sha256"],
            response_hash=response_hash,
            canonicalization=AI_CANONICALIZATION_V2,
        ).to_stored_object()
        metadata = {
            "request_hash": request_hash,
            "response_hash": response_hash,
            "binding_hash": binding_hash,
            "invocation_identity": identity,
            "invocation_binding": invocation_binding,
        }
        packed = ai_pack_from_obj(
            _payload(metadata), canonicalization=AI_CANONICALIZATION_V2
        )
        manifest = {**packed.manifest, "binding_hash": binding_hash}

        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _write_pack(bundle, packed, manifest=manifest)
            result = verify_ai_bundle(bundle)
        self.assertTrue(result.valid, result)
        self.assertEqual(result.payload_integrity, AssuranceState.VALID)
        self.assertEqual(result.binding_field_consistency, AssuranceState.VALID)
        self.assertEqual(result.invocation_identity_consistency, AssuranceState.VALID)
        self.assertEqual(result.invocation_binding_consistency, AssuranceState.VALID)

    def test_v1_invocation_hash_is_not_accepted_inside_v2_bundle(self):
        identity = build_invocation_identity(
            surface=SURFACE_LITELLM_COMPLETION,
            mode=MODE_SYNC_NON_STREAMING,
            model="m",
            messages=[{"role": "user", "content": "p"}],
            parameters={"temperature": 1.0},
            canonicalization=AI_CANONICALIZATION_V1,
        ).to_stored_object()
        packed = ai_pack_from_obj(
            _payload({"invocation_identity": identity}),
            canonicalization=AI_CANONICALIZATION_V2,
        )
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            _write_pack(bundle, packed)
            result = verify_ai_bundle(bundle)
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "INVOCATION_HASH_MISMATCH")

    def test_v2_signature_scope_is_exact_raw_manifest_bytes(self):
        packed = ai_pack_from_obj(
            _payload(), canonicalization=AI_CANONICALIZATION_V2
        )
        manifest_bytes = (
            b'{ "schema" : "ai_pack_manifest_v1", '
            b'"ts_utc":"2026-01-01T00:00:00Z",'
            b'"input_schema":"ai_output_v1",'
            b'"extension":{"valid":true},'
            b'"canonicalization":"aelitium_jcs_profile_v2",'
            b'"ai_hash_sha256":"'
            + packed.ai_hash_sha256.encode("ascii")
            + b'" }\n'
        )
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {"AEL_ED25519_PRIVKEY_B64": TEST_KEY, "AEL_ED25519_KEY_ID": "v2-test"},
            clear=False,
        ):
            bundle = Path(directory)
            bundle.mkdir(exist_ok=True)
            (bundle / "ai_canonical.json").write_bytes(
                packed.canonical_json.encode("utf-8") + b"\n"
            )
            (bundle / "ai_manifest.json").write_bytes(manifest_bytes)
            material = build_verification_material(manifest_bytes)
            (bundle / "verification_keys.json").write_text(
                json.dumps(material), encoding="utf-8"
            )

            valid = verify_ai_bundle(bundle)
            self.assertTrue(valid.valid, valid)
            self.assertEqual(valid.signature_validity, AssuranceState.VALID)

            (bundle / "ai_manifest.json").write_bytes(
                manifest_bytes.replace(b'{ "schema"', b'{  "schema"', 1)
            )
            changed = verify_ai_bundle(bundle)
        self.assertFalse(changed.valid)
        self.assertEqual(changed.reason, "SIGNATURE_INVALID")


if __name__ == "__main__":
    unittest.main()
