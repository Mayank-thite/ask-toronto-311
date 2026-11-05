"""Run the agent on every test question and score it.

    python eval/run_eval.py --name full-3b --model qwen3b
    python eval/run_eval.py --name bare --schema bare --examples 0 --retries 0
"""
import argparse
import json
import pathlib
import statistics
import sys
import time

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ask311.agent import Agent, AgentConfig  # noqa: E402
from ask311.compare import is_ordered, results_match  # noqa: E402
from ask311.db import run_query  # noqa: E402
from ask311.llm import LLM  # noqa: E402


def classify(ans, correct):
    if correct:
        return "correct"
    if ans.error and ans.error.startswith("Rejected"):
        return "invalid_sql"
    if ans.error:
        return "runtime_error"
    if not ans.rows:
        return "empty_result"
    return "wrong_result"


def summarize(records, meta):
    acc = sum(r["correct"] for r in records) / len(records)
    return {
        **meta, "n": len(records), "accuracy": round(100 * acc, 1),
        "by_category": {c: round(100 * statistics.mean(r["correct"] for r in records if r["category"] == c), 1)
                        for c in sorted({r["category"] for r in records})},
        "outcomes": {o: sum(r["outcome"] == o for r in records) for o in
                     ["correct", "wrong_result", "empty_result", "runtime_error", "invalid_sql"]},
        "fixed_by_retry": sum(r["fixed_by_retry"] for r in records),
        "median_seconds": round(statistics.median(r["seconds"] for r in records), 1),
        "p90_seconds": round(sorted(r["seconds"] for r in records)[int(0.9 * (len(records) - 1))], 1),
        "avg_prompt_tokens": round(statistics.mean(r["prompt_tokens"] for r in records)),
        "finished_at": time.strftime("%Y-%m-%d %H:%M"),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--model", default=None)
    p.add_argument("--base-url", default=None)
    p.add_argument("--schema", default="notes", choices=["bare", "notes"])
    p.add_argument("--examples", type=int, default=3)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--example-guard", action="store_true",
                   help="add the don't-copy-filters line (added after the first round of results)")
    p.add_argument("--only", default=None, help="comma-separated question ids")
    p.add_argument("--provider", default="openai", choices=["openai", "claude"],
                   help="openai = any OpenAI-compatible endpoint (local models); claude = Anthropic SDK")
    p.add_argument("--effort", default="low", help="Claude effort level (low | medium | high)")
    p.add_argument("--max-usd", type=float, default=None, help="stop a Claude run before it spends more")
    a = p.parse_args()

    cfg = AgentConfig(schema_level=a.schema, k_examples=a.examples, max_retries=a.retries,
                      retry_on_empty=a.retries > 0, example_guard=a.example_guard)
    if a.provider == "claude":
        from ask311.claude_llm import ClaudeLLM
        llm = ClaudeLLM(model=a.model or "claude-sonnet-5-5", effort=a.effort, max_usd=a.max_usd)
    else:
        llm = LLM(base_url=a.base_url, model=a.model)
    agent = Agent(llm, cfg)
    questions = yaml.safe_load(open(ROOT / "eval" / "questions.yaml"))
    if a.only:
        keep = set(a.only.split(","))
        questions = [q for q in questions if q["id"] in keep]

    out_path = ROOT / "eval" / "results" / f"{a.name}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = {}
    if out_path.exists():                      # resume a run that was interrupted
        for line in out_path.open():
            r = json.loads(line)
            done[r["id"]] = r
    records = []
    with out_path.open("a") as f:
        for q in questions:
            if q["id"] in done:
                records.append(done[q["id"]])
                continue
            _, gold_rows = run_query(q["sql"])
            spent_before = getattr(agent.llm, "spent", 0.0)
            ans = agent.ask(q["question"])
            correct = ans.ok and results_match(gold_rows, ans.rows, is_ordered(q["sql"], len(gold_rows)), q.get("answer_cols"), q.get("order_col"))
            rec = {
                "id": q["id"], "category": q["category"], "question": q["question"],
                "outcome": classify(ans, correct), "correct": correct,
                "attempts": len(ans.attempts), "fixed_by_retry": correct and len(ans.attempts) > 1,
                "pred_sql": ans.sql or (ans.attempts[-1]["sql"] if ans.attempts else None),
                "error": ans.error, "pred_rows": ans.rows[:5], "gold_rows": gold_rows[:5],
                "examples_used": ans.examples_used, "seconds": round(ans.seconds, 2),
                "prompt_tokens": ans.prompt_tokens, "completion_tokens": ans.completion_tokens,
            }
            if hasattr(agent.llm, "spent"):
                rec["cost_usd"] = round(agent.llm.spent - spent_before, 5)
            f.write(json.dumps(rec, default=str) + "\n")
            f.flush()
            records.append(rec)
            print(f"{q['id']:>4} {'OK ' if correct else 'XX '} {rec['outcome']:<14} {ans.seconds:5.1f}s  {q['question'][:60]}", flush=True)

    summary = summarize(records, {"name": a.name, "model": agent.llm.model, "schema": a.schema,
                                  "examples": a.examples, "retries": a.retries,
                                  "example_guard": a.example_guard and a.examples > 0})
    if hasattr(agent.llm, "spent"):
        summary["provider"] = "claude"
        summary["effort"] = a.effort
        summary["cost_usd"] = round(sum(r.get("cost_usd", 0) for r in records), 4)
        summary["cost_per_correct_usd"] = round(summary["cost_usd"] / max(1, sum(r["correct"] for r in records)), 5)
        summary["token_totals_this_session"] = agent.llm.totals
    (ROOT / "eval" / "results" / f"{a.name}.summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
