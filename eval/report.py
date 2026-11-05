"""Turn eval/results/*.json into charts, eval/REPORT.md and the docs/ results page."""
import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ask311.chart import save_chart  # noqa: E402
from stats import mcnemar_exact, wilson  # noqa: E402
from ask311.db import run_query  # noqa: E402

RES, IMG = ROOT / "eval" / "results", ROOT / "docs" / "img"
INK, MUTED, ACCENT, SOFT = "#1f2933", "#7b8794", "#2563eb", "#bfd3fb"
LADDER = [("3b-A-bare", "Tables only"), ("3b-B-notes", "+ data notes"),
          ("3b-C-notes-ex", "+ 3 similar examples"), ("3b-D-full", "+ self-correction"),
          ("3b-E-guard", "+ \"don't copy filters\" line")]
BEST = "7b-D-full"
DEMOS = ["t06", "r02", "m04", "x16", "x07"]
MODELS = [("1.5b-D-full", "Qwen2.5-Coder 1.5B"), ("3b-D-full", "Qwen2.5-Coder 3B"), ("7b-D-full", "Qwen2.5-Coder 7B")]
CATS = [("simple", "Simple"), ("time", "Time"), ("ranking", "Ranking"), ("semantics", "Data traps"), ("multi_step", "Multi-step")]


def load(name):
    p = RES / f"{name}.summary.json"
    return json.loads(p.read_text()) if p.exists() else None


def records(name):
    p = RES / f"{name}.jsonl"
    return [json.loads(line) for line in p.open()] if p.exists() else []


def correct_map(name):
    return {r["id"]: r["correct"] for r in records(name)}


def ladder_stats():
    """[(label, summary, ci, (gained, lost, p) vs previous rung or None)]"""
    out, prev = [], None
    for name, label in LADDER:
        s = load(name)
        if not s:
            continue
        cur = correct_map(name)
        k = sum(cur.values())
        test = None
        if prev is not None:
            lost, gained, p = mcnemar_exact(prev, cur)
            test = (gained, lost, p)
        out.append((label, s, wilson(k, len(cur)), test))
        prev = cur
    return out


def model_stats():
    out, prev = [], None
    for name, label in MODELS:
        s = load(name)
        if not s:
            continue
        cur = correct_map(name)
        test = None
        if prev is not None:
            lost, gained, p = mcnemar_exact(prev, cur)
            test = (gained, lost, p)
        out.append((label, s, wilson(sum(cur.values()), len(cur)), test))
        prev = cur
    return out


def fmt_p(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.2f}" if p >= 0.01 else f"p = {p:.3f}"


def error_taxonomy():
    import yaml
    labels = yaml.safe_load(open(ROOT / "eval" / "error_labels.yaml"))
    return [(cause, len(items), items) for cause, items in sorted(labels.items(), key=lambda kv: -len(kv[1]))]


def style(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=INK, labelsize=9, left=False)
    ax.set_xlim(0, 100)
    ax.xaxis.grid(True, color="#e4e7eb")
    ax.set_axisbelow(True)


def hbar(items, path, title, highlight_last=True, cis=None):
    labels, vals = [i[0] for i in items], [i[1] for i in items]
    fig, ax = plt.subplots(figsize=(7.5, 0.55 * len(items) + 1.1), dpi=160)
    top = max(vals)
    colors = [ACCENT if v == top else SOFT for v in vals] if highlight_last else [ACCENT] * len(vals)
    ax.barh(labels[::-1], vals[::-1], color=colors[::-1], height=0.6)
    if cis:
        lo = [v - c[0] for v, c in zip(vals, cis)][::-1]
        hi = [c[1] - v for v, c in zip(vals, cis)][::-1]
        ax.errorbar(vals[::-1], range(len(vals)), xerr=[lo, hi], fmt="none", ecolor=MUTED, elinewidth=1, capsize=3)
    for y, (v, c) in enumerate(zip(vals[::-1], (cis or [None] * len(vals))[::-1])):
        ax.text((c[1] if c else v) + 1.5, y, f"{v:.0f}%", va="center", fontsize=9, color=INK)
    style(ax)
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def categories_chart(summaries, path):
    fig, ax = plt.subplots(figsize=(7.5, 3.6), dpi=160)
    width = 0.8 / len(summaries)
    shades = ["#bfd3fb", "#7aa5f5", "#2563eb", "#173f99"][-len(summaries):]
    for i, (label, s) in enumerate(summaries):
        xs = [c + i * width for c in range(len(CATS))]
        ax.bar(xs, [s["by_category"].get(k, 0) for k, _ in CATS], width=width * 0.92, color=shades[i], label=label)
    ax.set_xticks([c + width * (len(summaries) - 1) / 2 for c in range(len(CATS))], [n for _, n in CATS])
    ax.set_ylim(0, 100)
    ax.set_ylabel("% correct", color=MUTED)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.yaxis.grid(True, color="#e4e7eb")
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, ncol=len(summaries), loc="upper center", bbox_to_anchor=(0.5, 1.15))
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fmt(v):
    return int(v) if isinstance(v, float) and v.is_integer() else v


def table(rows, cols, limit=8):
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(fmt(v)))}</td>" for v in r) + "</tr>" for r in rows[:limit])
    more = f"<p class=muted>{len(rows) - limit} more rows</p>" if len(rows) > limit else ""
    return f"<table><tr>{head}</tr>{body}</table>{more}"


def main():
    IMG.mkdir(parents=True, exist_ok=True)
    ladder = [(label, load(n)) for n, label in LADDER if load(n)]
    models = [(label, load(n)) for n, label in MODELS if load(n)]
    ls, ms = ladder_stats(), model_stats()
    hbar([(l, s["accuracy"]) for l, s, _, _ in ls], IMG / "ladder.png",
         "Questions answered correctly (of 100), Qwen2.5-Coder 3B, with 95% CI", cis=[c for _, _, c, _ in ls])
    if models:
        hbar([(l, s["accuracy"]) for l, s, _, _ in ms], IMG / "models.png",
             "Same agent, three model sizes, with 95% CI", highlight_last=False, cis=[c for _, _, c, _ in ms])
    categories_chart([(l, s) for l, s in ladder if l in ("Tables only", "+ data notes", "+ self-correction")], IMG / "categories.png")

    md = ["# Evaluation results", "", "100 questions with hand-checked answers, scored by execution accuracy "
          "(the query's result must match the gold result). Generated by `eval/report.py`.", "",
          "## Ablation: what each layer adds (Qwen2.5-Coder 3B)", "",
          "Each row adds one component to the row above. Same 100 questions, greedy decoding (temperature 0). "
          "95% Wilson intervals. The last column is an exact McNemar test against the row above: "
          "questions newly answered right / newly answered wrong, and the two-sided p-value.", "",
          "| Setup | Correct | 95% CI | Simple | Time | Ranking | Data traps | Multi-step | vs previous row |",
          "|---|---|---|---|---|---|---|---|---|"]
    for label, s, ci, t in ladder_stats():
        vs = f"+{t[0]} / -{t[1]}, {fmt_p(t[2])}" if t else ""
        md.append(f"| {label} | **{s['accuracy']:.0f}** | {ci[0]:.0f}-{ci[1]:.0f} | " + " | ".join(f"{s['by_category'].get(k, 0):.0f}" for k, _ in CATS) + f" | {vs} |")
    md += ["", "## Model size (full agent: notes + 3 examples + self-correction)", "",
           "| Model | Correct | 95% CI | Data traps | Multi-step | Median s | p90 s | vs smaller model |", "|---|---|---|---|---|---|---|---|"]
    for label, s, ci, t in model_stats():
        vs = f"+{t[0]} / -{t[1]}, {fmt_p(t[2])}" if t else ""
        md.append(f"| {label} | **{s['accuracy']:.0f}** | {ci[0]:.0f}-{ci[1]:.0f} | {s['by_category'].get('semantics', 0):.0f} | "
                  f"{s['by_category'].get('multi_step', 0):.0f} | {s['median_seconds']} | {s['p90_seconds']} | {vs} |")
    md += ["", "## Error analysis (7B, hand-labelled, one primary cause per miss)", "", "| Cause | Misses | Questions |", "|---|---|---|"]
    for cause, n, items in error_taxonomy():
        md.append(f"| {cause.replace('_', ' ')} | {n} | " + "; ".join(f"{k}: {v}" for k, v in items.items()) + " |")
    md += ["", f"## How the 7B agent failed ({BEST})", "", "| Outcome | Count |", "|---|---|"]
    full = load(BEST)
    if full:
        md += [f"| {k.replace('_', ' ')} | {v} |" for k, v in full["outcomes"].items()]
    md += ["", f"## Every question ({BEST})", "", "| id | category | question | result |", "|---|---|---|---|"]
    for r in records(BEST):
        md.append(f"| {r['id']} | {r['category']} | {r['question']} | {'correct' if r['correct'] else r['outcome'].replace('_', ' ')} |")
    (ROOT / "eval" / "REPORT.md").write_text("\n".join(md) + "\n")
    print("wrote eval/REPORT.md")
    write_page(ladder, models)


def write_page(ladder, models):
    import yaml
    qs = {q["id"]: q for q in yaml.safe_load(open(ROOT / "eval" / "questions.yaml"))}
    recs = {r["id"]: r for r in records(BEST)}
    best = load(BEST)
    demos = []
    for qid in DEMOS:
        r = recs.get(qid)
        if not r or not r["pred_sql"]:
            continue
        cols, rows = run_query(r["pred_sql"])
        img = ""
        kind = save_chart(cols, rows, IMG / f"demo-{qid}.png", r["question"])
        if kind in ("bar", "line"):
            img = f'<img src="img/demo-{qid}.png" alt="Chart of the answer">'
        verdict = "Correct" if r["correct"] else "Wrong: " + r["outcome"].replace("_", " ")
        demos.append(f"""<article class=demo><h3>{html.escape(r['question'])}</h3>
<pre>{html.escape(r['pred_sql'])}</pre>{table(rows, cols)}{img}
<p class="verdict {'ok' if r['correct'] else 'bad'}">{verdict} · {r['seconds']:.1f}s on a 4-core CPU</p></article>""")
    def vs(t):
        return f"+{t[0]} / &minus;{t[1]}<br><span class=muted>{html.escape(fmt_p(t[2]))}</span>" if t else "&nbsp;"
    ladder_rows = "".join(
        f"<tr><td>{html.escape(l)}</td><td><b>{s['accuracy']:.0f}</b></td><td>{ci[0]:.0f}&ndash;{ci[1]:.0f}</td>"
        + "".join(f"<td>{s['by_category'].get(k, 0):.0f}</td>" for k, _ in CATS) + f"<td>{vs(t)}</td></tr>"
        for l, s, ci, t in ladder_stats())
    model_rows = "".join(
        f"<tr><td>{html.escape(l)}</td><td><b>{s['accuracy']:.0f}</b></td><td>{ci[0]:.0f}&ndash;{ci[1]:.0f}</td>"
        f"<td>{s['median_seconds']}s</td><td>{s['p90_seconds']}s</td><td>{vs(t)}</td></tr>"
        for l, s, ci, t in model_stats())
    error_rows = "".join(
        f"<tr><td>{html.escape(c.replace('_', ' ').capitalize())}</td><td><b>{n}</b></td><td>"
        + "<br>".join(f"<code>{k}</code> {html.escape(v)}" for k, v in items.items()) + "</td></tr>"
        for c, n, items in error_taxonomy())
    page = (ROOT / "docs" / "template.html").read_text()
    page = (page.replace("{{LADDER_ROWS}}", ladder_rows).replace("{{MODEL_ROWS}}", model_rows).replace("{{ERROR_ROWS}}", error_rows)
                .replace("{{DEMOS}}", "\n".join(demos)).replace("{{BEST_ACC}}", f"{best['accuracy']:.0f}")
                .replace("{{BASE_ACC}}", f"{ladder[0][1]['accuracy']:.0f}"))
    (ROOT / "docs" / "index.html").write_text(page)
    print("wrote docs/index.html")


if __name__ == "__main__":
    main()
