"""Live-capture example for invocation-first comparison.

The historical filename is retained for compatibility. Current capture bundles
normally provide validated invocation identity and binding evidence, so v0.4
default comparison reports its invocation-first basis. A CHANGED result means
selected comparison identity hashes match and selected response hashes differ
under the reported basis; it does not establish model drift or causation.
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

print("Comparing validated recorded evidence (basis shown in output)...\n")

subprocess.run([
    "aelitium",
    "compare",
    "./run1",
    "./run2"
])
