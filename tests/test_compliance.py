import json
import tempfile
import unittest
from pathlib import Path

from engine.capture.openai import capture_chat_completion
from engine.compliance import export_eu_ai_act_art12
from unittest.mock import MagicMock
from types import SimpleNamespace


def _make_bundle(tmp_dir):
    response = SimpleNamespace(
        model="gpt-4o",
        id="resp_123",
        created=1700000000,
        choices=[SimpleNamespace(message=SimpleNamespace(content="Paris."), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )
    client = MagicMock()
    client.chat.completions.create.return_value = response
    capture_chat_completion(client, "gpt-4o", [{"role": "user", "content": "Capital of France?"}], tmp_dir)


class TestComplianceExport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _make_bundle(self.tmp)

    def test_export_eu_ai_act_returns_dict(self):
        result = export_eu_ai_act_art12(Path(self.tmp))
        self.assertIsInstance(result, dict)

    def test_export_has_required_fields(self):
        result = export_eu_ai_act_art12(Path(self.tmp))
        self.assertEqual(result["regulation"], "EU AI Act")
        self.assertEqual(result["article"], "Art. 12 - Record-keeping")
        self.assertIn("log_entry", result)
        self.assertIn("verification", result)

    def test_export_log_entry_has_hashes(self):
        result = export_eu_ai_act_art12(Path(self.tmp))
        entry = result["log_entry"]
        self.assertIsNotNone(entry["output_hash"])
        self.assertEqual(len(entry["output_hash"]), 64)
        self.assertEqual(entry["model"], "gpt-4o")

    def test_export_binding_hash_if_present(self):
        result = export_eu_ai_act_art12(Path(self.tmp))
        entry = result["log_entry"]
        # binding_hash should be present since we used capture_chat_completion
        self.assertIsNotNone(entry.get("binding_hash"))
