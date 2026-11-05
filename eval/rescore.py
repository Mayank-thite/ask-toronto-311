"""Re-score saved runs without calling the model again (used after changing compare.py).

Re-runs each saved predicted query and the gold query against the database.
"""
import json
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run_eval import ROOT, summarize  # noqa: E402

from ask311.compare import is_ordered, results_match  # noqa: E402
from ask311.db import run_query  # noqa: E402

questions = {q["id"]: q for q in yaml.safe_load(open(ROOT / "eval" / "questions.yaml"))}

for summ_path in sorted((ROOT / "eval" / "results").glob("*.summary.json")):
    name = summ_path.name.replace(".summary.json", "")
    meta = {k: v for k, v in json.loads(summ_path.read_text()).items() if k in ("name", "model", "schema", "examples", "retries", "example_guard")}
    recs = [json.loads(line) for line in (ROOT / "eval" / "results" / f"{name}.jsonl").open()]
    for r in recs:
        if r["error"] is None and r["pred_sql"]:
            q = questions[r["id"]]
            _, gold_rows = run_query(q["sql"])
            _, pred_rows = run_query(r["pred_sql"])
            r["correct"] = results_match(gold_rows, pred_rows, is_ordered(q["sql"], len(gold_rows)), q.get("answer_cols"), q.get("order_col"))
            if r["correct"]:
                r["outcome"] = "correct"
            elif r["outcome"] == "correct":
                r["outcome"] = "wrong_result" if pred_rows else "empty_result"
            elif r["outcome"] == "wrong_result" and not pred_rows:
                r["outcome"] = "empty_result"
            r["fixed_by_retry"] = r["correct"] and r["attempts"] > 1
    with (ROOT / "eval" / "results" / f"{name}.jsonl").open("w") as f:
        for r in recs:
            f.write(json.dumps(r, default=str) + "\n")
    s = summarize(recs, meta)
    summ_path.write_text(json.dumps(s, indent=2))
    print(name, s["accuracy"], s["by_category"])
