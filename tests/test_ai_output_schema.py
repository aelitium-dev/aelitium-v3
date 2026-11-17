import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestAIOutputSchema(unittest.TestCase):
    def test_fixture_loads(self):
        p = ROOT / "tests" / "fixtures" / "ai_output_min.json"
        obj = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(obj["schema_version"], "ai_output_v1")
        self.assertIn("model", obj)
        self.assertIn("prompt", obj)
        self.assertIn("output", obj)

if __name__ == "__main__":
    unittest.main()
