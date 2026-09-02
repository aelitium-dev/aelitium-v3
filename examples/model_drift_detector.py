"""Live-capture example for selected-hash comparison.

The historical filename is retained for compatibility. A CHANGED result means
that selected response hashes differ for the same selected v1 request hash; it
does not establish model drift or causation.
"""

from openai import OpenAI
from aelitium import capture_openai
import subprocess

client = OpenAI()

messages = [
    {"role": "user", "content": "Explain why the sky is blue in one sentence."}
]

print("Running capture 1...")
capture_openai(client, "gpt-4o-mini", messages, "./run1")

print("Running capture 2...")
capture_openai(client, "gpt-4o-mini", messages, "./run2")

print("Comparing selected request/response hashes...\n")

subprocess.run([
    "aelitium",
    "compare",
    "./run1",
    "./run2"
])
