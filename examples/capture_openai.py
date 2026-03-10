"""
AELITIUM capture adapter — OpenAI example.

This example shows how to capture an OpenAI chat completion and pack it
into a tamper-evident evidence bundle automatically.

No manual JSON writing required.

Prerequisites:
    pip install aelitium openai
    export OPENAI_API_KEY=sk-...

Run:
    python examples/capture_openai.py
"""

import os
from pathlib import Path

# Requires: pip install openai
import openai

from engine.capture.openai import capture_chat_completion


def main() -> None:
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    messages = [
        {"role": "user", "content": "Explain why deterministic AI outputs matter for compliance."},
    ]

    result = capture_chat_completion(
        client=client,
        model="gpt-4o",
        messages=messages,
        out_dir="./evidence_capture",
        metadata={"run_id": "demo-001", "env": "production"},
    )

    print(f"STATUS=OK")
    print(f"AI_HASH_SHA256={result.ai_hash_sha256}")
    print(f"BUNDLE_DIR={result.bundle_dir}")
    print(f"OUTPUT={result.response.choices[0].message.content[:80]}...")

    # Verify the bundle (offline, no network required)
    import subprocess
    verify = subprocess.run(
        ["python", "-m", "engine.ai_cli", "verify", "--out", str(result.bundle_dir)],
        capture_output=True, text=True
    )
    print(verify.stdout.strip())


if __name__ == "__main__":
    main()
