import json
import unittest
from pathlib import Path

from engine.ai_pack import ai_pack_from_obj, ai_pack_from_path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ai_output_min.json"

class TestAIPackPure(unittest.TestCase):
    def test_pack_is_deterministic_same_obj(self):
        obj = json.loads(FIXTURE.read_text(encoding="utf-8"))
        r1 = ai_pack_from_obj(obj)
        r2 = ai_pack_from_obj(obj)
        self.assertEqual(r1.canonical_json, r2.canonical_json)
        self.assertEqual(r1.ai_hash_sha256, r2.ai_hash_sha256)
        self.assertEqual(r1.manifest["ai_hash_sha256"], r1.ai_hash_sha256)

    def test_key_order_does_not_change_hash(self):
        obj = json.loads(FIXTURE.read_text(encoding="utf-8"))
        # re-create dict with different insertion order
        obj2 = {k: obj[k] for k in reversed(list(obj.keys()))}
        r1 = ai_pack_from_obj(obj)
        r2 = ai_pack_from_obj(obj2)
        self.assertEqual(r1.ai_hash_sha256, r2.ai_hash_sha256)

    def test_pack_from_path(self):
        r = ai_pack_from_path(FIXTURE)
        self.assertEqual(r.manifest["schema"], "ai_pack_manifest_v1")
        self.assertEqual(len(r.ai_hash_sha256), 64)
