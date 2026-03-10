# AELITIUM — Test Matrix

Last updated: 2026-03-10
Total: **100 tests, all PASS**

---

## How to run

```bash
# All tests (from repo root)
python3 -m unittest discover -s tests -q

# Capture adapter only
python3 -m unittest tests/test_capture_openai.py -v

# Reproducibility (cross-machine)
bash scripts/verify_repro.sh
```

No API keys required. All external calls are mocked.

---

## Test suites

### Core engine (86 tests)

| Suite | File | Tests | What it covers |
|-------|------|-------|----------------|
| AI CLI | `test_ai_cli.py` | — | CLI integration |
| AI CLI canonicalize | `test_ai_cli_canonicalize.py` | — | Canonicalization via CLI |
| AI CLI help | `test_ai_cli_help.py` | — | Help output |
| AI CLI pack | `test_ai_cli_pack.py` | — | Pack command |
| AI CLI pack contract | `test_ai_cli_pack_contract.py` | — | Pack output contract |
| AI CLI validate | `test_ai_cli_validate.py` | — | Validate command |
| AI CLI validate contract | `test_ai_cli_validate_contract.py` | — | Validate contract |
| AI CLI verify contract | `test_ai_cli_verify_contract.py` | — | Verify command contract |
| AI CLI verify-receipt contract | `test_ai_cli_verify_receipt_contract.py` | — | Receipt verification |
| AI output jsonschema | `test_ai_output_jsonschema.py` | — | JSON schema validation |
| AI output schema | `test_ai_output_schema.py` | — | Schema enforcement |
| AI pack pure | `test_ai_pack_pure.py` | — | Pack determinism, path |
| Bundle contract | `test_bundle_contract.py` | — | Bundle schema contract |
| Signature | `test_signature.py` | — | Ed25519 sign/verify |
| Evidence log | `test_validate_evidence_log.py` | — | Governance log format |

### Capture layer (14 tests)

| Suite | File | Tests | What it covers |
|-------|------|-------|----------------|
| Capture OpenAI | `test_capture_openai.py` | 14 | See below |

#### `test_capture_openai.py` — breakdown

**TestCaptureOpenAI (10 tests) — happy path**

| Test | What it proves |
|------|----------------|
| `test_returns_capture_result` | Returns correct type |
| `test_bundle_files_written` | Both bundle files created on disk |
| `test_hash_is_64_hex_chars` | Hash format valid |
| `test_canonical_json_is_valid_json` | Bundle payload is valid JSON with correct schema |
| `test_metadata_contains_capture_fields` | provider, sdk, request_hash, response_hash present |
| `test_extra_metadata_merged` | User metadata merged without overwriting capture fields |
| `test_manifest_schema_field` | Manifest schema and hash fields correct |
| `test_deterministic_for_same_input` | Two runs both produce valid hashes |
| `test_original_response_returned` | OpenAI response object returned unmodified |
| `test_api_called_with_correct_args` | API called with correct model and messages |

**TestCaptureDeterminism (4 tests) — EPIC: capture determinism**

| Test | What it proves |
|------|----------------|
| `test_same_payload_same_request_hash` | Same model+messages → same request_hash always |
| `test_same_payload_same_response_hash` | Same model+content → same response_hash always |
| `test_different_content_different_response_hash` | Different output → different response_hash |
| `test_tampered_canonical_fails_verify` | Modifying bundle after pack → hash mismatch (INVALID) |

---

## Cross-machine reproducibility

The reproducibility check (`scripts/verify_repro.sh`) validates that:
- same input → same `AI_HASH_SHA256` on any machine
- hash matches between Machine A (dev) and Machine B (authority)

Reference hash (demo bundle):
```
AI_HASH_SHA256=8b647717b14ad030fe8a641a9dcd63202e70aca170071d96040908e8354ef842
```

---

## What is not tested yet

| Area | Status |
|------|--------|
| Capture: streaming responses | Not in scope (v1) |
| Capture: tool/function calls | Not in scope (v1) |
| Capture: async client | Not in scope (v1) |
| Capture: Anthropic adapter | Planned |
| Capture: LangChain adapter | Planned |
| P3 signing authority | Planned |
| Machine B cross-machine capture hash | To be validated |
