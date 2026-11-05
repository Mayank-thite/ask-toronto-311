"""Claude models through the official Anthropic SDK, with the same .chat() shape as llm.LLM.

The agent sends one system message and a first user turn made of three parts:
schema context, retrieved examples, then the question. The schema context is the
same for every question, so it goes in its own content block with a cache marker.
Every question after the first reads it from the cache at a tenth of the price.

The adapter also keeps a running dollar total and stops the run before it passes
a budget, so an evaluation can never overspend.
"""
import os
import time

import anthropic

# USD per million tokens: (input, output). Cache writes cost 1.25x input, reads 0.1x.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}


class BudgetExceeded(RuntimeError):
    pass


def split_first_turn(text: str) -> tuple[str, str]:
    """Split the first user turn into (stable schema context, per-question tail)."""
    cut = min((i for i in (text.find("\n\nSolved examples"), text.find("\n\nQuestion: ")) if i >= 0),
              default=-1)
    if cut < 0:
        return "", text
    return text[:cut], text[cut + 2:]


def to_anthropic(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    """Convert OpenAI-style messages to Anthropic system blocks + messages."""
    system = [{"type": "text", "text": m["content"]} for m in messages if m["role"] == "system"]
    out = []
    for i, m in enumerate(m for m in messages if m["role"] != "system"):
        if i == 0 and m["role"] == "user":
            stable, tail = split_first_turn(m["content"])
            blocks = []
            if stable:
                blocks.append({"type": "text", "text": stable, "cache_control": {"type": "ephemeral"}})
            blocks.append({"type": "text", "text": tail})
            out.append({"role": "user", "content": blocks})
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return system, out


def cost_usd(model: str, usage) -> float:
    pin, pout = PRICES[model]
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    return (usage.input_tokens * pin + cache_write * pin * 1.25 + cache_read * pin * 0.1
            + usage.output_tokens * pout) / 1e6


def make_client():
    """Use ANTHROPIC_API_KEY when set. Otherwise send no key header, for setups where a
    proxy adds the x-api-key header on the way out (so the key never sits in the env)."""
    if os.getenv("ANTHROPIC_API_KEY"):
        return anthropic.Anthropic()
    return anthropic.Anthropic(default_headers={"Authorization": anthropic.Omit()})


class ClaudeLLM:
    def __init__(self, model: str = "claude-sonnet-5-5", effort: str = "low",
                 max_usd: float | None = None, client=None, max_output_tokens: int = 8000):
        if model not in PRICES:
            raise ValueError(f"no price for {model}; add it to PRICES")
        self.model = model
        self.effort = effort
        self.max_usd = max_usd if max_usd is not None else float(os.getenv("ASK311_MAX_USD", "inf"))
        self.client = client or make_client()
        self.max_output_tokens = max_output_tokens
        self.spent = 0.0
        self.totals = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}

    def chat(self, messages: list[dict], max_tokens: int = 400) -> dict:
        # max_tokens from the agent is sized for models without thinking; Claude's
        # adaptive thinking shares the output budget, so the adapter uses its own cap.
        if self.spent >= self.max_usd:
            raise BudgetExceeded(f"spent ${self.spent:.2f} of ${self.max_usd:.2f}")
        system, msgs = to_anthropic(messages)
        t0 = time.time()
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_output_tokens,
            system=system,
            messages=msgs,
            output_config={"effort": self.effort},
        )
        u = resp.usage
        self.spent += cost_usd(self.model, u)
        self.totals["input"] += u.input_tokens
        self.totals["cache_write"] += getattr(u, "cache_creation_input_tokens", 0) or 0
        self.totals["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
        self.totals["output"] += u.output_tokens
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return {
            "text": text,
            "prompt_tokens": u.input_tokens + (getattr(u, "cache_creation_input_tokens", 0) or 0)
                             + (getattr(u, "cache_read_input_tokens", 0) or 0),
            "completion_tokens": u.output_tokens,
            "seconds": time.time() - t0,
        }
