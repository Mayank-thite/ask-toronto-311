"""The agent loop: question -> prompt -> SQL -> guard -> run -> (fix and retry) -> result.

Each step can be switched off so the evaluation can measure what it adds:
    schema_level  "bare" (tables and columns only) or "notes" (plus the semantic notes)
    k_examples    how many similar solved examples to retrieve (0 = none)
    max_retries   how many times the model may fix its own failed query (0 = one shot)
"""
import time
from dataclasses import dataclass, field

from . import guard, schema_context
from .db import run_query
from .llm import LLM
from .retrieval import ExampleIndex

SYSTEM = (
    "You write PostgreSQL queries that answer questions about Toronto 311 service requests. "
    "Reply with exactly one SQL query inside a ```sql code block and nothing else."
)


@dataclass
class AgentConfig:
    schema_level: str = "notes"
    k_examples: int = 3
    max_retries: int = 2
    retry_on_empty: bool = True
    # Tried after the first evaluation: small models copied filters (years, topics)
    # from retrieved examples. A one-line warning did not help (71% vs 73%), so it is off.
    example_guard: bool = False


@dataclass
class Answer:
    question: str
    sql: str | None = None
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    error: str | None = None
    attempts: list = field(default_factory=list)
    examples_used: list = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None


class Agent:
    def __init__(self, llm: LLM | None = None, config: AgentConfig | None = None):
        self.llm = llm or LLM()
        self.config = config or AgentConfig()
        self.index = ExampleIndex() if self.config.k_examples else None

    def _first_prompt(self, question: str, examples: list[dict]) -> str:
        parts = [schema_context.describe(self.config.schema_level)]
        if examples:
            header = "Solved examples:"
            if self.config.example_guard:
                header = ("Solved examples. They show SQL patterns only. Do not copy their filters "
                          "(years, topics, wards, statuses) unless the new question asks for them:")
            parts.append(header + "\n" + "\n\n".join(
                f"Question: {e['question']}\n```sql\n{e['sql'].strip()}\n```" for e in examples))
        parts.append(f"Question: {question}")
        return "\n\n".join(parts)

    def ask(self, question: str) -> Answer:
        t0 = time.time()
        cfg = self.config
        examples = self.index.search(question, cfg.k_examples) if self.index else []
        ans = Answer(question=question, examples_used=[e["question"] for e in examples])
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": self._first_prompt(question, examples)}]
        asked_about_empty = False

        for attempt in range(cfg.max_retries + 1):
            reply = self.llm.chat(messages)
            ans.prompt_tokens += reply["prompt_tokens"]
            ans.completion_tokens += reply["completion_tokens"]
            raw_sql = guard.extract_sql(reply["text"])
            step = {"sql": raw_sql, "error": None, "row_count": None}
            ans.attempts.append(step)
            feedback = None
            try:
                safe_sql = guard.check(raw_sql)
                cols, rows = run_query(safe_sql)
                ans.sql, ans.columns, ans.rows, ans.error = safe_sql, cols, rows, None
                step["row_count"] = len(rows)
                if rows or not cfg.retry_on_empty or asked_about_empty:
                    break
                asked_about_empty = True
                feedback = ("The query ran but returned no rows. Check every filter value against the notes "
                            "(exact spelling and case, the date range, topic names). If no rows is truly the "
                            "right answer, repeat the same query.")
            except guard.UnsafeSQL as e:
                step["error"] = ans.error = f"Rejected: {e}"
                feedback = f"That query was rejected: {e} Fix it."
            except Exception as e:                         # database error
                msg = str(e).strip().splitlines()[0]
                step["error"] = ans.error = f"Database error: {msg}"
                feedback = f"PostgreSQL returned an error: {msg}\nFix the query."
            messages += [{"role": "assistant", "content": reply["text"]},
                         {"role": "user", "content": feedback + " Reply with the corrected SQL only."}]
        ans.seconds = time.time() - t0
        return ans
