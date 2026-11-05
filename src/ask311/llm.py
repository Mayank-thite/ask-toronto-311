"""Minimal client for any OpenAI-compatible /chat/completions endpoint."""
import time

import requests

from . import config


class LLM:
    def __init__(self, base_url=None, model=None, api_key=None, timeout=300):
        self.base_url = (base_url or config.LLM_BASE_URL).rstrip("/")
        self.model = model or config.LLM_MODEL
        self.api_key = api_key or config.LLM_API_KEY
        self.timeout = timeout

    def chat(self, messages: list[dict], max_tokens: int = 400) -> dict:
        t0 = time.time()
        r = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages, "temperature": 0,
                  "max_tokens": max_tokens},
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        usage = data.get("usage") or {}
        return {
            "text": data["choices"][0]["message"]["content"] or "",
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "seconds": time.time() - t0,
        }
