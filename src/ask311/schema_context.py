"""Build the database description the model sees.

"bare" gives only tables and columns, which is what most text-to-SQL demos do.
"notes" adds a small semantic layer: real column values, what they mean, and the
traps in this dataset. The evaluation measures how much each layer helps.
"""
import functools

from .db import run_query

TABLES = ["v_requests", "service_requests", "request_types", "wards"]

NOTES = """\
Notes about the data (read these, they matter):
- Prefer the view v_requests. It already joins ward_name and topic onto every request.
- One row = one 311 request. Count requests with COUNT(*).
- Data covers {min_date} to {max_date} (calendar years 2024 and 2025 only). "Last year" means 2025.
- Seasons: winter = December, January, February; spring = March to May; summer = June to August; fall = September to November.
- Use EXTRACT(YEAR FROM created_at), EXTRACT(MONTH FROM created_at), EXTRACT(DOW FROM created_at) (0 = Sunday), EXTRACT(HOUR FROM created_at), or DATE_TRUNC('month', created_at).
- topic groups 800+ raw request types into plain themes. Use topic for broad questions ("potholes", "noise", "trees").
  The city renamed many request types between 2024 and 2025, so filtering on one request_type usually misses half the data.
  Topics: {topics}.
- Use request_type only when the question names a specific type; match it with ILIKE '%...%'.
- status values: {statuses}. 'Completed' and 'Closed' both mean finished. "Open" or "unresolved" means status IN ('New', 'In Progress').
- division values: {divisions}.
  Forestry moved divisions: it was 'Parks, Forestry & Recreation' in 2024 and 'Environment, Climate & Forestry' in 2025.
- Wards: ward_id 1 to 25 with ward_name, e.g. {ward_examples}. ward_id is NULL when the ward is unknown; leave those out of ward rankings.
- postal_fsa is the first 3 characters of a postal code (e.g. 'M4C'). It is NULL when the request was logged at an intersection;
  then intersection_street_1 (and sometimes intersection_street_2) hold the street names.
- For percentages use ROUND(100.0 * part / total, 1). For averages use ROUND(..., 1).
- When you rank wards, return ward_name (not just ward_id).
"""


@functools.lru_cache(maxsize=None)
def _columns() -> dict[str, list[tuple[str, str]]]:
    cols, rows = run_query(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' ORDER BY table_name, ordinal_position"
    )
    out: dict[str, list[tuple[str, str]]] = {}
    for t, c, d in rows:
        out.setdefault(t, []).append((c, d))
    return out


@functools.lru_cache(maxsize=None)
def _values() -> dict:
    def col(sql):
        return [r[0] for r in run_query(sql)[1]]
    return {
        "min_date": col("SELECT MIN(created_at)::date FROM service_requests")[0],
        "max_date": col("SELECT MAX(created_at)::date FROM service_requests")[0],
        "topics": ", ".join(f"'{t}'" for t in col("SELECT DISTINCT topic FROM request_types ORDER BY 1")),
        "statuses": ", ".join(f"'{s}'" for s in col("SELECT DISTINCT status FROM service_requests ORDER BY 1")),
        "divisions": ", ".join(f"'{s}'" for s in col("SELECT DISTINCT division FROM service_requests ORDER BY 1")),
        "ward_examples": ", ".join(f"{i} = '{n}'" for i, n in run_query("SELECT ward_id, ward_name FROM wards ORDER BY 1 LIMIT 4")[1]),
    }


def describe(level: str = "notes") -> str:
    cols = _columns()
    lines = ["PostgreSQL tables:"]
    for t in TABLES:
        lines.append(f"- {t}(" + ", ".join(f"{c} {d}" for c, d in cols.get(t, [])) + ")")
    text = "\n".join(lines)
    if level == "notes":
        text += "\n\n" + NOTES.format(**_values())
    return text
