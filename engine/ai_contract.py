"""Constants for the current AI evidence bundle contract."""

AI_CANONICAL_FILENAME = "ai_canonical.json"
AI_MANIFEST_FILENAME = "ai_manifest.json"
AI_VERIFICATION_KEYS_FILENAME = "verification_keys.json"

AI_OUTPUT_SCHEMA_VERSION = "ai_output_v1"
AI_OUTPUT_SCHEMA_FILENAME = "ai_output_v1.json"
AI_CANONICALIZATION = "json_sorted_keys_no_whitespace_utf8"

AI_MANIFEST_SCHEMA = "ai_pack_manifest_v1"
AI_MANIFEST_REQUIRED_FIELDS = (
    "schema",
    "ts_utc",
    "input_schema",
    "canonicalization",
    "ai_hash_sha256",
)
AI_MANIFEST_TS_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
