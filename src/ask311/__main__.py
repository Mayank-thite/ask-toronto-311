"""Command line: python -m ask311 "Which ward had the most noise complaints in 2025?" """
import argparse
import pathlib

from .agent import Agent, AgentConfig
from .chart import save_chart


def main():
    p = argparse.ArgumentParser(description="Ask a question about Toronto 311 data in plain English.")
    p.add_argument("question")
    p.add_argument("--chart", default="answer.png", help="where to save a chart, if one fits")
    p.add_argument("--show-attempts", action="store_true")
    p.add_argument("--claude", metavar="MODEL", nargs="?", const="claude-haiku-5-5", default=None,
                   help="use Claude through the Anthropic API instead of a local model "
                        "(needs ANTHROPIC_API_KEY; default model claude-haiku-5-5)")
    a = p.parse_args()

    llm = None
    if a.claude:
        from .claude_llm import ClaudeLLM
        llm = ClaudeLLM(model=a.claude)
    ans = Agent(llm=llm, config=AgentConfig()).ask(a.question)
    if a.show_attempts:
        for i, s in enumerate(ans.attempts, 1):
            outcome = s["error"] or f"{s['row_count']} rows"
            print(f"--- attempt {i} ---\n{s['sql']}\n{outcome}")
    if not ans.ok:
        print(f"Could not answer: {ans.error}")
        return
    print(ans.sql, "\n")
    widths = [max(len(str(c)), *(len(str(r[i])) for r in ans.rows[:20])) for i, c in enumerate(ans.columns)]
    print("  ".join(str(c).ljust(w) for c, w in zip(ans.columns, widths)))
    for r in ans.rows[:20]:
        print("  ".join(str(v).ljust(w) for v, w in zip(r, widths)))
    if len(ans.rows) > 20:
        print(f"... {len(ans.rows) - 20} more rows")
    kind = save_chart(ans.columns, ans.rows, pathlib.Path(a.chart), a.question)
    if kind in ("bar", "line"):
        print(f"\n{kind} chart saved to {a.chart}")
    print(f"\n{ans.seconds:.1f}s, {len(ans.attempts)} attempt(s)")


if __name__ == "__main__":
    main()
