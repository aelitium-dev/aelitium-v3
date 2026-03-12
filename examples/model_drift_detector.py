from openai import OpenAI
from engine.capture.openai import capture_chat_completion
import subprocess

client = OpenAI()

messages = [
    {"role": "user", "content": "Explain why the sky is blue in one sentence."}
]

print("Running capture 1...")
capture_chat_completion(client, "gpt-4o-mini", messages, "./run1")

print("Running capture 2...")
capture_chat_completion(client, "gpt-4o-mini", messages, "./run2")

print("Comparing bundles...\n")

subprocess.run([
    "aelitium",
    "compare",
    "./run1",
    "./run2"
])
