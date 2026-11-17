import copy
import unittest

from engine.capture.common import (
    CaptureMetadataCollisionError,
    merge_capture_metadata,
)


class TestMergeCaptureMetadata(unittest.TestCase):
    def test_no_collision_returns_merged_copy(self):
        base = {"provider": "openai", "request_hash": "base-hash"}
        caller = {"run_id": "run-123"}

        merged = merge_capture_metadata(base, caller)

        self.assertEqual(
            merged,
            {
                "provider": "openai",
                "request_hash": "base-hash",
                "run_id": "run-123",
            },
        )
        self.assertIsNot(merged, base)
        self.assertIsNot(merged, caller)

    def test_one_collision_raises_stable_error(self):
        with self.assertRaises(CaptureMetadataCollisionError) as context:
            merge_capture_metadata(
                {"provider": "openai"},
                {"provider": "caller"},
            )

        self.assertEqual(context.exception.offending_keys, ("provider",))
        self.assertEqual(
            str(context.exception),
            "CAPTURE_METADATA_RESERVED_KEY_COLLISION: provider",
        )

    def test_multiple_collisions_are_sorted(self):
        with self.assertRaises(CaptureMetadataCollisionError) as context:
            merge_capture_metadata(
                {
                    "provider": "openai",
                    "binding_hash": "base-binding",
                    "request_hash": "base-request",
                },
                {
                    "request_hash": "caller-request",
                    "provider": "caller",
                    "binding_hash": "caller-binding",
                },
            )

        self.assertEqual(
            context.exception.offending_keys,
            ("binding_hash", "provider", "request_hash"),
        )
        self.assertEqual(
            str(context.exception),
            "CAPTURE_METADATA_RESERVED_KEY_COLLISION: "
            "binding_hash,provider,request_hash",
        )

    def test_inputs_are_not_mutated(self):
        base = {"provider": "openai", "usage": {"total_tokens": 3}}
        caller = {"run": {"id": "run-123"}}
        base_before = copy.deepcopy(base)
        caller_before = copy.deepcopy(caller)

        merge_capture_metadata(base, caller)

        self.assertEqual(base, base_before)
        self.assertEqual(caller, caller_before)


if __name__ == "__main__":
    unittest.main()
