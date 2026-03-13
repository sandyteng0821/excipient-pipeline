"""
診斷腳本：確認 API key 有效 + 列出可用的 flash models
在 excipient_pipeline/ 目錄下執行：
    python check_api.py
"""

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("❌ GEMINI_API_KEY not found in .env")
    exit(1)

print(f"✅ API key found: {api_key[:8]}...")

client = genai.Client(api_key=api_key)

print("\n── Available flash models ──────────────")
try:
    for m in client.models.list():
        if "flash" in m.name.lower() or "gemini" in m.name.lower():
            print(f"  {m.name}")
except Exception as e:
    print(f"❌ Failed to list models: {e}")
    exit(1)

print("\n── Quick test call ─────────────────────")
try:
    from google.genai import types
    resp = client.models.generate_content(
        model="gemini-1.5-flash",       # fallback to 1.5
        contents="Reply with: ok",
        config=types.GenerateContentConfig(temperature=0),
    )
    print(f"✅ gemini-1.5-flash works: {resp.text.strip()}")
except Exception as e:
    print(f"❌ gemini-1.5-flash failed: {e}")

try:
    from google.genai import types
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Reply with: ok",
        config=types.GenerateContentConfig(temperature=0),
    )
    print(f"✅ gemini-2.0-flash works: {resp.text.strip()}")
except Exception as e:
    print(f"❌ gemini-2.0-flash failed: {e}")