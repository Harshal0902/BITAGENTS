"""
Quick LLM connectivity check for hosted Ollama.

Usage:
  cd agent/new
  python test_hosted_llm.py
"""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from hosted_llm import (
    HOSTED_OLLAMA_BASE_URL,
    HOSTED_OLLAMA_MODEL,
    llm_provider,
    ping_hosted_ollama,
    use_hosted_ollama,
)


def main() -> None:
    print(f"provider: {llm_provider()}")
    print(f"url:      {HOSTED_OLLAMA_BASE_URL}")
    print(f"model:    {HOSTED_OLLAMA_MODEL}")
    print(f"key set:  {use_hosted_ollama()}")
    print()
    result = ping_hosted_ollama()
    print(json.dumps(result, indent=2))
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
