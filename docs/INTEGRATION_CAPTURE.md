# AELITIUM Capture Layer

The capture layer reduces the manual handoff gap by intercepting LLM API calls directly, instead of relying on manually written JSON.

**Before capture layer:**
```
LLM → output → user writes JSON → aelitium pack → bundle
```

**With capture layer:**
```
LLM → capture_chat_completion() → bundle (automatic)
```

The bundle is created in the adapter-controlled call path without a manual JSON
handoff. The v1 hashes cover selected recorded request and response fields; they
do not represent every provider invocation parameter or eliminate the need for
external trust anchors.

---

## OpenAI adapter

### Install

```bash
pip install aelitium openai
```

### Usage

```python
import openai
from engine.capture.openai import capture_chat_completion

client = openai.OpenAI()

result = capture_chat_completion(
    client=client,
    model="gpt-4o",
    messages=[{"role": "user", "content": "Explain quantum computing."}],
    out_dir="./evidence",
)

print(result.ai_hash_sha256)   # deterministic hash
print(result.bundle_dir)       # path to bundle files
print(result.response)         # original OpenAI response (unmodified)
```

### Return value

`CaptureResult` with:

| Field | Type | Description |
|-------|------|-------------|
| `response` | OpenAI response object | Original API response, unmodified |
| `bundle_dir` | `Path` | Directory containing the evidence bundle |
| `ai_hash_sha256` | `str` | 64-char hex SHA-256 of the canonical bundle |

### Bundle contents

```
./evidence/
├── ai_canonical.json    ← canonicalized payload (verifiable)
└── ai_manifest.json     ← schema, timestamp, hash
```

### Verify offline

```bash
aelitium verify-bundle ./evidence
# STATUS=VALID rc=0
# AI_HASH_SHA256=<hash>
```

### What is captured

| Field | Source |
|-------|--------|
| `model` | from call arguments |
| `prompt` | canonical JSON of `messages` list |
| `output` | `response.choices[0].message.content` |
| `ts_utc` | local timestamp at capture time |
| `metadata.provider` | `"openai"` |
| `metadata.sdk` | `"openai-python"` |
| `metadata.request_hash` | SHA-256 of canonical `{model, messages}` |
| `metadata.response_hash` | SHA-256 of canonical `{model, content}` |

Extra metadata can be passed via the `metadata` argument:

```python
result = capture_chat_completion(
    client, model, messages, out_dir,
    metadata={"run_id": "abc-123", "env": "production"},
)
```

Caller metadata may add unrelated custom fields. Every key present in the
adapter-owned base metadata for that invocation is reserved. A collision fails
with `CAPTURE_METADATA_RESERVED_KEY_COLLISION`; the adapter does not silently
overwrite or discard either value. The reserved set is invocation-specific rather
than one universal static list shared by all adapters.

### Trust boundary

What the capture adapter supports:
- The request and response were recorded during the adapter-controlled call path
- The v1 request identity covers the recorded model and messages selected by the adapter
- Verification can check the current bundle's schema, canonical representation, hashes, and stored binding fields for internal consistency

The capture adapter does **not** prove:
- That the model itself was not compromised
- That the `openai.OpenAI()` client was not intercepted upstream
- That every behavior-affecting invocation parameter is represented in `request_hash`
- That a self-consistent bundle was not replaced without an independently trusted anchor

For stronger provenance, combine with a signing authority (P3).

---

## What is not supported yet

- Streaming responses (OpenAI streaming is supported; LiteLLM/Anthropic streaming is not)
- Tool / function calls
- Async clients
- Gemini adapter

These are planned for future releases.

---

## Running the tests

No API key required — tests use a mock client.

```bash
python -m unittest tests/test_capture_openai.py -v
```

---

## Running the example

```bash
export OPENAI_API_KEY=sk-...
python examples/capture_openai.py
```

---

## New in v0.2: Provider metadata

Every capture bundle now includes:

| Field | Description |
|---|---|
| `metadata.binding_hash` | Commitment over the stored request/response hash pair |
| `metadata.response_id` | Provider's response ID (e.g. OpenAI `id`) |
| `metadata.provider_created_at` | Unix timestamp from provider |
| `metadata.finish_reason` | e.g. `stop`, `end_turn` |
| `metadata.usage` | Token usage: prompt, completion, total |
| `metadata.captured_at_utc` | Local capture timestamp (ISO8601) |

The `binding_hash` is a **cryptographic commitment** over the stored pair
`(request_hash, response_hash)` —
`sha256(canonical({"request_hash": ..., "response_hash": ...}))`. Current v1
verification checks consistency among the stored request, response, and binding
fields. It does not independently reconstruct source request or response material
or prove that a real-world provider invocation produced the recorded response.

## Operator signing (optional)

Set environment variables to sign every bundle at capture time:

```bash
export AEL_ED25519_PRIVKEY_B64=<your-32-byte-key-base64>
```

When set, every `capture_chat_completion()` call writes `verification_keys.json`
alongside the bundle. The `CaptureResult.signed` field is `True`.

This supports mathematical Ed25519 signature verification. Because the public key
is packaged with the artifact, a valid signature does not establish an externally
trusted signer identity; `trusted_signer_identity` remains `UNESTABLISHED`.
Unsigned bundles remain valid by default. Use `--require-signature` when absence
must fail. Binding evidence is likewise optional by default; use
`--require-binding` when it is required.

## Chain of custody (EvidenceLog)

```python
from engine.capture.log import EvidenceLog

log = EvidenceLog("./evidence_log")

result = capture_chat_completion(client, model, messages, "./evidence/run-1")
log.append(result.bundle_dir, result.ai_hash_sha256)

# Later: verify chain
log2 = EvidenceLog("./evidence_log")
assert log2.verify_chain(), "Chain tampered!"
```

## Compliance export

```python
from engine.compliance import export_eu_ai_act_art12

record = export_eu_ai_act_art12("./evidence/run-1")
# record["log_entry"] contains fields for EU AI Act Art. 12 audit
```

Or via CLI:
```bash
aelitium export --bundle ./evidence/run-1 --format eu-ai-act-art12 --json
```

## Standalone verification

No aelitium installation required:

```bash
python scripts/aelitium_verify_standalone.py --bundle ./evidence/run-1
```

## Streaming

```python
from engine.capture.openai import capture_chat_completion_stream

result = capture_chat_completion_stream(client, model, messages, "./evidence/stream-1")
print(result.ai_hash_sha256)  # hash of full accumulated content
```

## Anthropic

```python
from engine.capture.anthropic import capture_message

result = capture_message(anthropic_client, "claude-3-5-sonnet-20241022", messages, "./evidence/run-1")
print(result.ai_hash_sha256)
```

---

## LiteLLM

LiteLLM routes calls to multiple providers through a unified interface. The
AELITIUM adapter captures at that LiteLLM boundary and emits the same provider-
neutral v1 evidence contract. Repository unit tests exercise the adapter boundary;
they are not conformance results for every provider supported by LiteLLM.

### Install

```bash
pip install aelitium[litellm]
# or: pip install aelitium litellm
```

### Usage

```python
from engine.capture.litellm import capture_completion

result = capture_completion(
    model="openai/gpt-4o",           # LiteLLM model string (provider/model)
    messages=[{"role": "user", "content": "What is 2+2?"}],
    out_dir="./evidence",
)

print(result.ai_hash_sha256)   # deterministic hash of the evidence bundle
print(result.bundle_dir)       # path to bundle files
print(result.response)         # original LiteLLM response (unmodified)
```

Examples of provider routes exposed by LiteLLM include:

```python
# Anthropic via LiteLLM
capture_completion("anthropic/claude-3-5-sonnet-20241022", messages, "./evidence")

# AWS Bedrock via LiteLLM
capture_completion("bedrock/anthropic.claude-3-sonnet-20240229-v1:0", messages, "./evidence")
```

### Model string in the bundle

LiteLLM model strings include a provider prefix (`"openai/gpt-4o"`). The bundle records both:

| Field | Value | What it represents |
|-------|-------|--------------------|
| `metadata.model_requested` | `"openai/gpt-4o"` | Model string passed to LiteLLM |
| `metadata.model_confirmed` | `"gpt-4o"` | Model name returned by the provider |

`request_hash` uses `model_requested` together with messages as the current v1
selected-field request identity. Forwarded behavior parameters such as
`temperature` and `max_tokens` are not represented in that hash. `response_hash`
uses `model_confirmed` with recorded response content.

### Scope (v1)

- `litellm.completion()` — synchronous, non-streaming
- Optional Ed25519 signing (same as OpenAI/Anthropic adapters)

Not in scope for v1: streaming, async (`litellm.acompletion`), tool calls.
