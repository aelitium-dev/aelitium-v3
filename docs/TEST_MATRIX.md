# AELITIUM — Test Matrix

Last updated: 2026-03-10
Total: **129 tests, all PASS**

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

### Core engine

| Suite | File | Tests | What it covers |
|-------|------|-------|----------------|
| AI CLI | `test_ai_cli.py` | 2 | CLI smoke tests |
| AI CLI canonicalize | `test_ai_cli_canonicalize.py` | 7 | Canonicalization via CLI |
| AI CLI help | `test_ai_cli_help.py` | 1 | Help output |
| AI CLI pack | `test_ai_cli_pack.py` | 1 | Pack command |
| AI CLI pack contract | `test_ai_cli_pack_contract.py` | 19 | Pack output contract |
| AI CLI validate | `test_ai_cli_validate.py` | 2 | Validate command |
| AI CLI validate contract | `test_ai_cli_validate_contract.py` | 8 | Validate contract |
| AI CLI verify contract | `test_ai_cli_verify_contract.py` | 16 | Verify command contract + signature enforcement |
| AI CLI verify-receipt contract | `test_ai_cli_verify_receipt_contract.py` | 10 | Receipt verification |
| AI output jsonschema | `test_ai_output_jsonschema.py` | 2 | JSON schema validation |
| AI output schema | `test_ai_output_schema.py` | 1 | Schema enforcement |
| AI pack pure | `test_ai_pack_pure.py` | 3 | Pack determinism, path |
| Bundle contract | `test_bundle_contract.py` | 5 | Bundle schema contract |
| Signature | `test_signature.py` | 4 | Ed25519 sign/verify |
| Evidence log validator | `test_validate_evidence_log.py` | 11 | Governance log format (EVIDENCE_ENTRY v1) |

### Capture layer

| Suite | File | Tests | What it covers |
|-------|------|-------|----------------|
| Capture OpenAI | `test_capture_openai.py` | 19 | OpenAI adapter — happy path, determinism, tamper detection |
| Capture OpenAI adapter | `test_capture_openai_adapter.py` | 4 | Legacy adapter (`pack_openai_chat_completion`) |
| Capture Anthropic | `test_capture_anthropic.py` | 6 | Anthropic adapter — happy path, binding hash, provider metadata |
| Evidence log chain | `test_evidence_log.py` | 4 | Append-only JSONL chain, tamper detection, prev_hash linkage |
| Compliance export | `test_compliance.py` | 4 | EU AI Act Art.12 export format |

---

### `test_capture_openai.py` — breakdown

**TestCaptureOpenAI (10 tests) — happy path**

| Test | What it proves |
|------|----------------|
| `test_returns_capture_result` | Returns correct type |
| `test_bundle_files_written` | Both bundle files created on disk |
| `test_hash_is_64_hex_chars` | Hash format valid |
| `test_canonical_json_is_valid_json` | Bundle payload is valid JSON with correct schema |
| `test_metadata_contains_capture_fields` | provider, sdk, request_hash, response_hash, binding_hash present |
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

**TestVerifySignatureEnforcement (4 tests) — Sprint 1.1**

| Test | What it proves |
|------|----------------|
| `test_signed_bundle_verify_returns_signature_valid` | Signed bundle: verify returns `signature=VALID` |
| `test_unsigned_bundle_verify_returns_signature_none` | Unsigned bundle: verify returns `signature=NONE` |
| `test_tampered_verification_keys_gives_signature_invalid` | Tampered keys: verify returns `SIGNATURE_INVALID` |
| `test_tampered_manifest_with_valid_keys_gives_signature_invalid` | Manifest tampered after signing: SIGNATURE_INVALID |

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
| Capture: streaming responses | Implemented; unit test coverage minimal |
| Capture: tool/function calls | Not in scope (v1) |
| Capture: async client | Not in scope (v1) |
| Capture: LangChain adapter | Planned |
| Capture: LiteLLM adapter | Planned |
| P3 signing authority | Planned |
| Machine B cross-machine capture hash | Validated manually; not yet automated |
