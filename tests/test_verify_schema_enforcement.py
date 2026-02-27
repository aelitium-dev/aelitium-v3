import json
import sys
import tempfile
import unittest
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENGINE_DIR))

from pack import pack  # noqa: E402
from verify import RC_INVALID, RC_VALID, verify  # noqa: E402


class VerifySchemaEnforcementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workdir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _create_valid_bundle(self):
        input_path = self.workdir / "input.json"
        out_dir = self.workdir / "bundle"
        input_path.write_text(
            json.dumps(
                {
                    "schema_version": "input_v1",
                    "payload": {"name": "AELITIUM", "value": 42},
                }
            ),
            encoding="utf-8",
        )
        pack(str(input_path), str(out_dir))
        return out_dir / "manifest.json", out_dir / "evidence_pack.json"

    def _read_json(self, path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: dict):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_control_valid_bundle_is_valid(self):
        manifest_path, evidence_path = self._create_valid_bundle()
        self.assertEqual(verify(str(manifest_path), str(evidence_path)), RC_VALID)

    def test_manifest_extra_field_is_invalid(self):
        manifest_path, evidence_path = self._create_valid_bundle()
        manifest = self._read_json(manifest_path)
        manifest["unexpected"] = "extra"
        self._write_json(manifest_path, manifest)
        self.assertEqual(verify(str(manifest_path), str(evidence_path)), RC_INVALID)

    def test_evidence_extra_field_is_invalid(self):
        manifest_path, evidence_path = self._create_valid_bundle()
        evidence = self._read_json(evidence_path)
        evidence["unexpected"] = "extra"
        self._write_json(evidence_path, evidence)
        self.assertEqual(verify(str(manifest_path), str(evidence_path)), RC_INVALID)

    def test_manifest_wrong_type_is_invalid(self):
        manifest_path, evidence_path = self._create_valid_bundle()
        manifest = self._read_json(manifest_path)
        manifest["input_hash"] = {"not": "string"}
        self._write_json(manifest_path, manifest)
        self.assertEqual(verify(str(manifest_path), str(evidence_path)), RC_INVALID)

    def test_evidence_wrong_type_is_invalid(self):
        manifest_path, evidence_path = self._create_valid_bundle()
        evidence = self._read_json(evidence_path)
        evidence["canonical_payload"] = {"not": "string"}
        self._write_json(evidence_path, evidence)
        self.assertEqual(verify(str(manifest_path), str(evidence_path)), RC_INVALID)


if __name__ == "__main__":
    unittest.main()
