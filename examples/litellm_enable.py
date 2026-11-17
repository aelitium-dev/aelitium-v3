"""
litellm_enable.py — minimal example of enable_litellm()

Shows the zero-config path: one line added, existing LiteLLM code unchanged.

Requirements:
    pip install aelitium litellm
    export OPENAI_API_KEY=...   # or any provider key LiteLLM supports

Run:
    python examples/litellm_enable.py
"""

from aelitium import enable_litellm
import litellm

# One line: all subsequent litellm.completion() calls write evidence bundles.
enable_litellm(out_dir="./aelitium/bundles", verbose=True)

response = litellm.completion(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "Say hello in one sentence."}],
)

print(response.choices[0].message.content)
print("\nBundle written to: ./aelitium/bundles/")
print("Inspect with:      ls ./aelitium/bundles/")
print("Verify with:       aelitium verify-bundle ./aelitium/bundles/<binding_hash>/")
