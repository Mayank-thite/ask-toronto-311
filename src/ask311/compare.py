"""Decide whether a predicted result answers the question the same way the gold result does.

Execution accuracy, with the usual allowances:
- only the columns the question asks for are checked (see answer_cols);
- column names don't matter, and extra columns in the prediction are fine
  (returning ward_id next to ward_name is not wrong);
- row order only matters when the gold query sorts more than one row;
- numbers match after rounding to 2 decimals, so 3 and 3.0 and 3.004 are equal;
- when every gold month falls in one year, month numbers (1 to 12) are accepted in
  place of month dates, since "2025-02-01" and 2 say the same thing once the year is fixed.
"""
import re

_MONTH_START = re.compile(r"^(\d{4})-(\d{2})-01$")


def _norm(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    if isinstance(v, str):
        s = v.strip()
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return s[:10]               # '2025-02-01T00:00:00' == '2025-02-01'
        return s
    return v


def _col(rows, j):
    return [_norm(r[j]) for r in rows]


def _variants(values):
    """Equivalent ways to write a gold column."""
    out = [values]
    ms = [_MONTH_START.match(v) if isinstance(v, str) else None for v in values]
    if values and all(ms) and len({m.group(1) for m in ms}) == 1:
        out.append([float(int(m.group(2))) for m in ms])
    return out


def results_match(gold_rows, pred_rows, ordered: bool, answer_cols=None, order_col=None) -> bool:
    """answer_cols: indexes of the gold columns the question actually asks for
    ("Which ward..." asks for the ward; the count beside it is context).
    order_col: for sorted answers with ties, only this gold column's sequence must
    match; rows that tie on it may come in any order."""
    if ordered and order_col is not None:
        if not results_match(gold_rows, pred_rows, False, answer_cols):
            return False
        g = _col(gold_rows, order_col)
        return any(_col(pred_rows, k) == g for k in range(len(pred_rows[0]))) if pred_rows else not g
    if answer_cols is not None:
        gold_rows = [tuple(r[i] for i in answer_cols) for r in gold_rows]
    if len(gold_rows) != len(pred_rows):
        return False
    if not gold_rows:
        return True
    n_gold, n_pred = len(gold_rows[0]), len(pred_rows[0])
    if n_pred < n_gold:
        return False

    def same(a, b):
        return a == b if ordered else sorted(map(repr, a)) == sorted(map(repr, b))

    # Map every gold column to a distinct predicted column holding the same values.
    used, mapping, gold_cols = set(), [], []
    for j in range(n_gold):
        found = None
        for g in _variants(_col(gold_rows, j)):
            k = next((k for k in range(n_pred) if k not in used and same(g, _col(pred_rows, k))), None)
            if k is not None:
                found = (k, g)
                break
        if found is None:
            return False
        used.add(found[0])
        mapping.append(found[0])
        gold_cols.append(found[1])

    # Columns can match one by one but pair up differently across rows; check whole rows too.
    gold = list(zip(*gold_cols))
    pred = [tuple(_norm(r[k]) for k in mapping) for r in pred_rows]
    return gold == pred if ordered else sorted(map(repr, gold)) == sorted(map(repr, pred))


def is_ordered(gold_sql: str, n_rows: int) -> bool:
    return n_rows > 1 and "ORDER BY" in gold_sql.upper().split(")")[-1]
