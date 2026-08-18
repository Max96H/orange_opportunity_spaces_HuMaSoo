import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq()

models = client.models.list()
print("Available Model IDs on your Groq account:")
for m in models.data:
    print(f" - {m.id}")

"""
Available Model IDs on your Groq account:
 - allam-2-7b
 - openai/gpt-oss-20b
 - openai/gpt-oss-120b
 - canopylabs/orpheus-arabic-saudi
 - whisper-large-v3
 - openai/gpt-oss-safeguard-20b
 - meta-llama/llama-prompt-guard-2-22m
 - groq/compound-mini
 - whisper-large-v3-turbo
 - qwen/qwen3.6-27b
 - groq/compound
 - canopylabs/orpheus-v1-english
 - meta-llama/llama-prompt-guard-2-86m
"""