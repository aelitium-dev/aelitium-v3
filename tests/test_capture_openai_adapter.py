import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from engine.capture_openai import OpenAICaptureResult, pack_openai_chat_completion

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "engine.ai_cli"]


class TestCaptureOpenAIAdapter(unittest.TestCase):
    def test_response_dict_simple(self):
        response = {
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "message": {
                        "content": "Paris is the capital of France.",
                    }
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = pack_openai_chat_completion(
                response,
                prompt="What is the capital of France?",
                out_dir=tmp,
                metadata={"source": "openai-sdk"},
            )

            self.assertIsInstance(result, OpenAICaptureResult)
            self.assertEqual(result.bundle_dir, Path(tmp))
            self.assertEqual(len(result.ai_hash_sha256), 64)

            canonical = json.loads((Path(tmp) / "ai_canonical.json").read_text(encoding="utf-8"))
            self.assertEqual(canonical["schema_version"], "ai_output_v1")
            self.assertEqual(canonical["model"], "gpt-4o-mini")
            self.assertEqual(canonical["prompt"], "What is the capital of France?")
            self.assertEqual(canonical["output"], "Paris is the capital of France.")
            self.assertEqual(canonical["metadata"]["source"], "openai-sdk")

    def test_response_mock_choices_message_content(self):
        response = SimpleNamespace(
            model="gpt-4o-mini",
            choices=[SimpleNamespace(message=SimpleNamespace(content="Lisbon."))],
        )

        with tempfile.TemporaryDirectory() as tmp:
            result = pack_openai_chat_completion(
                response,
                prompt="What is the capital of Portugal?",
                out_dir=tmp,
            )
            canonical = json.loads((Path(tmp) / "ai_canonical.json").read_text(encoding="utf-8"))
            manifest = json.loads((Path(tmp) / "ai_manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(canonical["output"], "Lisbon.")
            self.assertEqual(manifest["ai_hash_sha256"], result.ai_hash_sha256)

    def test_error_when_output_cannot_be_extracted(self):
        bad_response = {
            "model": "gpt-4o-mini",
            "choices": [{"message": {"content": None}}],
        }

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Could not extract output text"):
                pack_openai_chat_completion(
                    bad_response,
                    prompt="Test prompt",
                    out_dir=tmp,
                )

    def test_bundle_is_created_and_verifiable(self):
        response = {
            "model": "gpt-4o-mini",
            "choices": [{"message": {"content": "4"}}],
        }

        with tempfile.TemporaryDirectory() as tmp:
            result = pack_openai_chat_completion(
                response,
                prompt="What is 2+2?",
                out_dir=tmp,
            )

            self.assertTrue((Path(tmp) / "ai_canonical.json").exists())
            self.assertTrue((Path(tmp) / "ai_manifest.json").exists())

            verify = subprocess.run(
                CLI + ["verify", "--out", str(tmp), "--json"],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)
            verify_json = json.loads(verify.stdout.strip())
            self.assertEqual(verify_json["status"], "VALID")
            self.assertEqual(verify_json["ai_hash_sha256"], result.ai_hash_sha256)


if __name__ == "__main__":
    unittest.main()

