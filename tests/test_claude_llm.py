"""Claude adapter tests with a fake client: no network, no key needed."""
from types import SimpleNamespace as NS

import pytest

from ask311.claude_llm import BudgetExceeded, ClaudeLLM, cost_usd, split_first_turn, to_anthropic


class FakeClient:
    def __init__(self):
        self.calls = []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        usage = NS(input_tokens=100, cache_creation_input_tokens=0, cache_read_input_tokens=800, output_tokens=50)
        return NS(usage=usage, content=[NS(type="thinking", thinking=""),
                                        NS(type="text", text="```sql\nSELECT 1\n```")])


FIRST = "Tables:\nx\n\nNotes:\ny\n\nSolved examples:\nQuestion: a\n\nQuestion: how many?"


def test_split_keeps_schema_as_cacheable_prefix():
    stable, tail = split_first_turn(FIRST)
    assert stable == "Tables:\nx\n\nNotes:\ny"
    assert tail.startswith("Solved examples:") and tail.endswith("how many?")


def test_split_without_examples():
    stable, tail = split_first_turn("Tables:\nx\n\nQuestion: q")
    assert (stable, tail) == ("Tables:\nx", "Question: q")


def test_conversion_marks_only_schema_block_for_cache():
    system, msgs = to_anthropic([{"role": "system", "content": "S"}, {"role": "user", "content": FIRST},
                                 {"role": "assistant", "content": "bad"}, {"role": "user", "content": "fix"}])
    assert system == [{"type": "text", "text": "S"}]
    first = msgs[0]["content"]
    assert first[0]["cache_control"] == {"type": "ephemeral"} and "cache_control" not in first[1]
    assert msgs[1:] == [{"role": "assistant", "content": "bad"}, {"role": "user", "content": "fix"}]


def test_chat_returns_text_and_tracks_cost():
    fake = FakeClient()
    llm = ClaudeLLM(model="claude-sonnet-5-5", effort="low", client=fake)
    out = llm.chat([{"role": "system", "content": "S"}, {"role": "user", "content": FIRST}])
    assert out["text"] == "```sql\nSELECT 1\n```"
    assert out["prompt_tokens"] == 900 and out["completion_tokens"] == 50
    assert fake.calls[0]["output_config"] == {"effort": "low"}
    assert "temperature" not in fake.calls[0]
    assert llm.spent == pytest.approx((100 * 2 + 800 * 0.2 + 50 * 10) / 1e6)


def test_budget_stops_the_run():
    llm = ClaudeLLM(model="claude-haiku-5-5", client=FakeClient(), max_usd=0.0)
    with pytest.raises(BudgetExceeded):
        llm.chat([{"role": "user", "content": "Question: q"}])


def test_cost_formula_cache_write():
    u = NS(input_tokens=0, cache_creation_input_tokens=1_000_000, cache_read_input_tokens=0, output_tokens=0)
    assert cost_usd("claude-opus-5-5", u) == pytest.approx(5.0)
