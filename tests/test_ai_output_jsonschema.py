import json
import unittest
from pathlib import Path

try:
    import jsonschema
except Exception as exc:
    jsonschema = None
    _IMPORT_ERR = exc
else:
    _IMPORT_ERR = None

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "engine" / "schemas" / "ai_output_v1.json"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "ai_output_min.json"


class TestAIOutputJsonSchema(unittest.TestCase):
    def test_jsonschema_available(self):
        if jsonschema is None:
            self.fail(f"jsonschema import failed: {_IMPORT_ERR}")

    def test_fixture_validates(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        obj = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(instance=obj, schema=schema)


if __name__ == "__main__":
    unittest.main()
