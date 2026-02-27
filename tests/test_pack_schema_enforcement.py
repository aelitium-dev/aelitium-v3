import json
import sys
import tempfile
import unittest
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENGINE_DIR))

from pack import pack  # noqa: E402


class PackSchemaEnforcementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workdir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _run_pack(self, input_data: dict, out_name: str = "out"):
        input_path = self.workdir / "input.json"
        out_dir = self.workdir / out_name
        input_path.write_text(json.dumps(input_data), encoding="utf-8")
        pack(str(input_path), str(out_dir))
        return out_dir

    def test_extra_input_field_fails(self):
        with self.assertRaises(ValueError):
            self._run_pack(
                {"schema_version": "input_v1", "payload": {}, "extra": "x"},
                out_name="extra",
            )
        self.assertFalse((self.workdir / "extra").exists())

    def test_missing_schema_version_fails(self):
        with self.assertRaises(ValueError):
            self._run_pack({"payload": {}}, out_name="missing_schema")
        self.assertFalse((self.workdir / "missing_schema").exists())

    def test_missing_payload_fails(self):
        with self.assertRaises(ValueError):
            self._run_pack({"schema_version": "input_v1"}, out_name="missing_payload")
        self.assertFalse((self.workdir / "missing_payload").exists())

    def test_schema_version_value_is_enforced(self):
        with self.assertRaises(ValueError):
            self._run_pack(
                {"schema_version": "input_v2", "payload": {}}, out_name="bad_schema"
            )
        self.assertFalse((self.workdir / "bad_schema").exists())

    def test_payload_must_be_object(self):
        with self.assertRaises(ValueError):
            self._run_pack(
                {"schema_version": "input_v1", "payload": ["not", "an", "object"]},
                out_name="bad_payload",
            )
        self.assertFalse((self.workdir / "bad_payload").exists())

    def test_valid_input_generates_bundle(self):
        out_dir = self._run_pack({"schema_version": "input_v1", "payload": {}})
        self.assertTrue((out_dir / "manifest.json").is_file())
        self.assertTrue((out_dir / "evidence_pack.json").is_file())
        self.assertTrue((out_dir / "verification_keys.json").is_file())


if __name__ == "__main__":
    unittest.main()
