import json
import sys
import tempfile
import unittest
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENGINE_DIR))

from canonical import canonicalize_and_hash  # noqa: E402
from verify import RC_INVALID, RC_VALID, verify  # noqa: E402


class VerifyCanonicalizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workdir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_bundle(self, manifest: dict, evidence: dict):
        manifest_path = self.workdir / "manifest.json"
        evidence_path = self.workdir / "evidence_pack.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return str(manifest_path), str(evidence_path)

    def test_reordered_payload_still_valid(self):
        payload = {"name": "AELITIUM", "value": 42, "nested": {"a": 1, "b": 2}}
        _, digest = canonicalize_and_hash(payload)

        manifest = {
            "schema_version": "1.0",
            "hash_alg": "sha256",
            "input_schema": "input_v1",
            "input_hash": digest,
            "canonicalization": "json.dumps(sort_keys,separators,utf8)",
        }
        evidence = {
            "canonical_payload": '{\n  "value": 42,\n  "nested": { "b": 2, "a": 1 },\n  "name": "AELITIUM"\n}',
            "hash": digest,
        }

        manifest_path, evidence_path = self._write_bundle(manifest, evidence)
        self.assertEqual(verify(manifest_path, evidence_path), RC_VALID)

    def test_changed_value_is_invalid(self):
        payload = {"name": "AELITIUM", "value": 42}
        _, digest = canonicalize_and_hash(payload)
        tampered_payload = {"name": "AELITIUM", "value": 999}
        _, tampered_digest = canonicalize_and_hash(tampered_payload)

        manifest = {
            "schema_version": "1.0",
            "hash_alg": "sha256",
            "input_schema": "input_v1",
            "input_hash": digest,
            "canonicalization": "json.dumps(sort_keys,separators,utf8)",
        }
        evidence = {
            "canonical_payload": json.dumps(tampered_payload),
            "hash": tampered_digest,
        }

        manifest_path, evidence_path = self._write_bundle(manifest, evidence)
        self.assertEqual(verify(manifest_path, evidence_path), RC_INVALID)

    def test_malformed_json_is_invalid(self):
        payload = {"name": "AELITIUM", "value": 42}
        _, digest = canonicalize_and_hash(payload)

        manifest = {
            "schema_version": "1.0",
            "hash_alg": "sha256",
            "input_schema": "input_v1",
            "input_hash": digest,
            "canonicalization": "json.dumps(sort_keys,separators,utf8)",
        }
        evidence = {
            "canonical_payload": '{"name":"AELITIUM",,"value":42}',
            "hash": digest,
        }

        manifest_path, evidence_path = self._write_bundle(manifest, evidence)
        self.assertEqual(verify(manifest_path, evidence_path), RC_INVALID)

    def test_non_sha256_hash_alg_is_invalid(self):
        payload = {"name": "AELITIUM", "value": 42}
        canonical_payload, digest = canonicalize_and_hash(payload)

        manifest = {
            "schema_version": "1.0",
            "hash_alg": "sha512",
            "input_schema": "input_v1",
            "input_hash": digest,
            "canonicalization": "json.dumps(sort_keys,separators,utf8)",
        }
        evidence = {
            "canonical_payload": canonical_payload,
            "hash": digest,
        }

        manifest_path, evidence_path = self._write_bundle(manifest, evidence)
        self.assertEqual(verify(manifest_path, evidence_path), RC_INVALID)


if __name__ == "__main__":
    unittest.main()
