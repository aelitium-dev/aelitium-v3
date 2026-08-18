import unittest

from engine.invocation_binding import (
    INVOCATION_BINDING_FORMAT,
    InvocationBinding,
    InvocationBindingError,
    build_invocation_binding,
    parse_invocation_binding,
)

# Golden vector -- independently derived outside this codebase's
# implementation (cross-checked with `sha256sum` on the exact raw JSON
# bytes below; NOT produced by calling build_invocation_binding,
# parse_invocation_binding, canonical_json, or sha256_hash):
#
#   raw = {"format":"aelitium-invocation-binding-v1","invocation_hash":
#          "1111...1111","response_hash":"2222...2222"}
#   $ printf '%s' "$raw" | sha256sum
#   7541d410b59bcff64141ab89b0ea119017c67d5caa66601a8a7cd80eee6e43b7
_GOLDEN_INVOCATION_HASH = "1111111111111111111111111111111111111111111111111111111111111111"
_GOLDEN_RESPONSE_HASH = "2222222222222222222222222222222222222222222222222222222222222222"
_GOLDEN_DIGEST = (
    "7541d410b59bcff64141ab89b0ea119017c67d5caa66601a8a7cd80eee6e43b7"
)

_VALID_INVOCATION_HASH = "a" * 64
_VALID_RESPONSE_HASH = "b" * 64


def _valid_stored_object() -> dict:
    return build_invocation_binding(
        invocation_hash=_VALID_INVOCATION_HASH,
        response_hash=_VALID_RESPONSE_HASH,
    ).to_stored_object()


class TestBuildInvocationBinding(unittest.TestCase):
    # A. valid construction
    def test_valid_construction(self):
        binding = build_invocation_binding(
            invocation_hash=_VALID_INVOCATION_HASH,
            response_hash=_VALID_RESPONSE_HASH,
        )
        self.assertIsInstance(binding, InvocationBinding)
        self.assertEqual(binding.format, INVOCATION_BINDING_FORMAT)
        self.assertEqual(binding.invocation_hash, _VALID_INVOCATION_HASH)
        self.assertEqual(binding.response_hash, _VALID_RESPONSE_HASH)
        self.assertRegex(binding.hash_sha256, r"^[0-9a-f]{64}$")

    # B. exact stored object keys
    def test_stored_object_has_exact_keys(self):
        stored = _valid_stored_object()
        self.assertEqual(
            set(stored.keys()),
            {"format", "invocation_hash", "response_hash", "hash_sha256"},
        )
        self.assertEqual(stored["format"], INVOCATION_BINDING_FORMAT)

    # C. deterministic construction: same inputs -> same hash
    def test_deterministic_construction(self):
        a = build_invocation_binding(
            invocation_hash=_VALID_INVOCATION_HASH,
            response_hash=_VALID_RESPONSE_HASH,
        )
        b = build_invocation_binding(
            invocation_hash=_VALID_INVOCATION_HASH,
            response_hash=_VALID_RESPONSE_HASH,
        )
        self.assertEqual(a.hash_sha256, b.hash_sha256)

    # D. domain/input separation: different invocation_hash -> different hash
    def test_different_invocation_hash_changes_digest(self):
        a = build_invocation_binding(
            invocation_hash=_VALID_INVOCATION_HASH,
            response_hash=_VALID_RESPONSE_HASH,
        )
        b = build_invocation_binding(
            invocation_hash="c" * 64,
            response_hash=_VALID_RESPONSE_HASH,
        )
        self.assertNotEqual(a.hash_sha256, b.hash_sha256)

    # E. response separation: different response_hash -> different hash
    def test_different_response_hash_changes_digest(self):
        a = build_invocation_binding(
            invocation_hash=_VALID_INVOCATION_HASH,
            response_hash=_VALID_RESPONSE_HASH,
        )
        b = build_invocation_binding(
            invocation_hash=_VALID_INVOCATION_HASH,
            response_hash="d" * 64,
        )
        self.assertNotEqual(a.hash_sha256, b.hash_sha256)

    # F. golden vector
    def test_golden_vector(self):
        binding = build_invocation_binding(
            invocation_hash=_GOLDEN_INVOCATION_HASH,
            response_hash=_GOLDEN_RESPONSE_HASH,
        )
        self.assertEqual(binding.hash_sha256, _GOLDEN_DIGEST)
        self.assertEqual(binding.to_stored_object()["hash_sha256"], _GOLDEN_DIGEST)

    # G. round trip: build -> to_stored_object -> parse
    def test_round_trip(self):
        built = build_invocation_binding(
            invocation_hash=_VALID_INVOCATION_HASH,
            response_hash=_VALID_RESPONSE_HASH,
        )
        stored = built.to_stored_object()
        parsed = parse_invocation_binding(stored)
        self.assertEqual(built, parsed)

    # H. parse recomputes and accepts valid hash
    def test_parse_accepts_valid_stored_object(self):
        stored = _valid_stored_object()
        parsed = parse_invocation_binding(stored)
        self.assertEqual(parsed.invocation_hash, _VALID_INVOCATION_HASH)
        self.assertEqual(parsed.response_hash, _VALID_RESPONSE_HASH)
        self.assertEqual(parsed.hash_sha256, stored["hash_sha256"])


class TestParseInvocationBindingTamper(unittest.TestCase):
    # I. semantic tamper: change invocation_hash without updating hash_sha256
    def test_invocation_hash_tamper_gives_hash_mismatch(self):
        stored = _valid_stored_object()
        stored["invocation_hash"] = "c" * 64
        with self.assertRaises(InvocationBindingError) as ctx:
            parse_invocation_binding(stored)
        self.assertEqual(ctx.exception.reason, "INVOCATION_BINDING_HASH_MISMATCH")

    # J. response tamper: change response_hash without updating hash_sha256
    def test_response_hash_tamper_gives_hash_mismatch(self):
        stored = _valid_stored_object()
        stored["response_hash"] = "d" * 64
        with self.assertRaises(InvocationBindingError) as ctx:
            parse_invocation_binding(stored)
        self.assertEqual(ctx.exception.reason, "INVOCATION_BINDING_HASH_MISMATCH")


class TestParseInvocationBindingStructure(unittest.TestCase):
    # K. bad format
    def test_bad_format(self):
        stored = _valid_stored_object()
        stored["format"] = "aelitium-invocation-binding-v2"
        with self.assertRaises(InvocationBindingError) as ctx:
            parse_invocation_binding(stored)
        self.assertEqual(ctx.exception.reason, "INVOCATION_BINDING_BAD_FORMAT")

    # L. missing key
    def test_missing_key(self):
        stored = _valid_stored_object()
        del stored["response_hash"]
        with self.assertRaises(InvocationBindingError) as ctx:
            parse_invocation_binding(stored)
        self.assertEqual(ctx.exception.reason, "INVOCATION_BINDING_BAD_STRUCTURE")

    # M. extra key
    def test_extra_key(self):
        stored = _valid_stored_object()
        stored["unexpected"] = "value"
        with self.assertRaises(InvocationBindingError) as ctx:
            parse_invocation_binding(stored)
        self.assertEqual(ctx.exception.reason, "INVOCATION_BINDING_BAD_STRUCTURE")

    # N. non-dict stored object
    def test_non_dict_stored_object(self):
        for bad in (None, [], "not-a-dict", 123, 1.5, True):
            with self.subTest(bad=bad):
                with self.assertRaises(InvocationBindingError) as ctx:
                    parse_invocation_binding(bad)
                self.assertEqual(
                    ctx.exception.reason, "INVOCATION_BINDING_BAD_STRUCTURE"
                )

    # O. bad invocation hash: uppercase, short, non-hex, non-string
    def test_bad_invocation_hash_matrix(self):
        cases = {
            "uppercase": "A" * 64,
            "short": "a" * 63,
            "long": "a" * 65,
            "non_hex": "g" * 64,
            "non_string": 12345,
            "whitespace_padded": " " + "a" * 63,
            "none": None,
        }
        for label, bad_value in cases.items():
            with self.subTest(case=label):
                stored = _valid_stored_object()
                stored["invocation_hash"] = bad_value
                with self.assertRaises(InvocationBindingError) as ctx:
                    parse_invocation_binding(stored)
                self.assertEqual(
                    ctx.exception.reason,
                    "INVOCATION_BINDING_BAD_INVOCATION_HASH",
                )

    # P. bad response hash: same representative malformed cases
    def test_bad_response_hash_matrix(self):
        cases = {
            "uppercase": "B" * 64,
            "short": "b" * 63,
            "long": "b" * 65,
            "non_hex": "z" * 64,
            "non_string": 12345,
            "whitespace_padded": "b" * 63 + " ",
            "none": None,
        }
        for label, bad_value in cases.items():
            with self.subTest(case=label):
                stored = _valid_stored_object()
                stored["response_hash"] = bad_value
                with self.assertRaises(InvocationBindingError) as ctx:
                    parse_invocation_binding(stored)
                self.assertEqual(
                    ctx.exception.reason,
                    "INVOCATION_BINDING_BAD_RESPONSE_HASH",
                )

    # Q. bad stored hash: uppercase, short, non-hex, non-string
    def test_bad_stored_hash_matrix(self):
        cases = {
            "uppercase": "C" * 64,
            "short": "c" * 63,
            "long": "c" * 65,
            "non_hex": "k" * 64,
            "non_string": 12345,
            "whitespace_padded": "c" * 63 + " ",
            "none": None,
        }
        for label, bad_value in cases.items():
            with self.subTest(case=label):
                stored = _valid_stored_object()
                stored["hash_sha256"] = bad_value
                with self.assertRaises(InvocationBindingError) as ctx:
                    parse_invocation_binding(stored)
                self.assertEqual(ctx.exception.reason, "INVOCATION_BINDING_BAD_HASH")


class TestBuildInvocationBindingRejectsBadInput(unittest.TestCase):
    def test_build_rejects_uppercase_invocation_hash(self):
        with self.assertRaises(InvocationBindingError) as ctx:
            build_invocation_binding(
                invocation_hash="A" * 64,
                response_hash=_VALID_RESPONSE_HASH,
            )
        self.assertEqual(
            ctx.exception.reason, "INVOCATION_BINDING_BAD_INVOCATION_HASH"
        )

    def test_build_rejects_short_response_hash(self):
        with self.assertRaises(InvocationBindingError) as ctx:
            build_invocation_binding(
                invocation_hash=_VALID_INVOCATION_HASH,
                response_hash="b" * 63,
            )
        self.assertEqual(
            ctx.exception.reason, "INVOCATION_BINDING_BAD_RESPONSE_HASH"
        )

    def test_build_rejects_non_string_invocation_hash(self):
        with self.assertRaises(InvocationBindingError) as ctx:
            build_invocation_binding(
                invocation_hash=b"a" * 64,
                response_hash=_VALID_RESPONSE_HASH,
            )
        self.assertEqual(
            ctx.exception.reason, "INVOCATION_BINDING_BAD_INVOCATION_HASH"
        )

    def test_build_does_not_normalize_case(self):
        # No coercion/normalization: uppercase input must be rejected, not
        # lowercased and accepted.
        with self.assertRaises(InvocationBindingError):
            build_invocation_binding(
                invocation_hash="A" * 64,
                response_hash=_VALID_RESPONSE_HASH,
            )


class TestInvocationBindingImmutability(unittest.TestCase):
    # R. immutability: validated result cannot be mutated normally
    def test_result_is_frozen(self):
        binding = build_invocation_binding(
            invocation_hash=_VALID_INVOCATION_HASH,
            response_hash=_VALID_RESPONSE_HASH,
        )
        with self.assertRaises(Exception):
            binding.invocation_hash = "z" * 64

    # S. fresh to_stored_object: mutating returned dict does not mutate
    # validated object
    def test_to_stored_object_returns_fresh_dict(self):
        binding = build_invocation_binding(
            invocation_hash=_VALID_INVOCATION_HASH,
            response_hash=_VALID_RESPONSE_HASH,
        )
        stored_first = binding.to_stored_object()
        stored_first["invocation_hash"] = "z" * 64
        stored_second = binding.to_stored_object()
        self.assertEqual(stored_second["invocation_hash"], _VALID_INVOCATION_HASH)
        self.assertEqual(binding.invocation_hash, _VALID_INVOCATION_HASH)


class TestBuildParseErrorParity(unittest.TestCase):
    # T. parser/build error parity where applicable
    def test_bad_invocation_hash_reason_matches_across_build_and_parse(self):
        with self.assertRaises(InvocationBindingError) as build_ctx:
            build_invocation_binding(
                invocation_hash="not-hex",
                response_hash=_VALID_RESPONSE_HASH,
            )

        stored = _valid_stored_object()
        stored["invocation_hash"] = "not-hex"
        with self.assertRaises(InvocationBindingError) as parse_ctx:
            parse_invocation_binding(stored)

        self.assertEqual(build_ctx.exception.reason, parse_ctx.exception.reason)
        self.assertEqual(
            build_ctx.exception.reason, "INVOCATION_BINDING_BAD_INVOCATION_HASH"
        )

    def test_bad_response_hash_reason_matches_across_build_and_parse(self):
        with self.assertRaises(InvocationBindingError) as build_ctx:
            build_invocation_binding(
                invocation_hash=_VALID_INVOCATION_HASH,
                response_hash="not-hex",
            )

        stored = _valid_stored_object()
        stored["response_hash"] = "not-hex"
        with self.assertRaises(InvocationBindingError) as parse_ctx:
            parse_invocation_binding(stored)

        self.assertEqual(build_ctx.exception.reason, parse_ctx.exception.reason)
        self.assertEqual(
            build_ctx.exception.reason, "INVOCATION_BINDING_BAD_RESPONSE_HASH"
        )


if __name__ == "__main__":
    unittest.main()
