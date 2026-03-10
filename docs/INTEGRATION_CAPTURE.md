# AELITIUM Capture Layer

The capture layer closes the trust gap by intercepting LLM API calls directly, instead of relying on manually written JSON.

**Before capture layer:**
```
LLM → output → user writes JSON → aelitium pack → bundle
```

**With capture layer:**
```
LLM → capture_chat_completion() → bundle (automatic)
```

The bundle is created at call time, capturing the exact request and response hashes. No manual step. No trust gap.

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
aelitium verify --out ./evidence
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

### Trust boundary

The capture adapter proves:
- The output was captured at call time
- The bundle has not been altered since capture
- The request hash matches the messages that were sent

The capture adapter does **not** prove:
- That the model itself was not compromised
- That the `openai.OpenAI()` client was not intercepted upstream

For stronger provenance, combine with a signing authority (P3).

---

## What is not supported yet

- Streaming responses
- Tool / function calls
- Async clients
- Anthropic, Gemini, LiteLLM adapters

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
