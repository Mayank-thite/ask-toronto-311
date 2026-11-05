"""Check model-written SQL before it touches the database.

Layer 1 (here): parse with sqlglot, allow exactly one read-only SELECT over known
tables, and cap the row count. Layer 2 (database): the agent logs in as agent_ro,
which only has SELECT grants, read-only transactions and a 15 second timeout.
"""
import re

import sqlglot
from sqlglot import exp

ALLOWED_TABLES = {"service_requests", "request_types", "wards", "v_requests"}
MAX_ROWS = 500
_FORBIDDEN = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter,
              exp.Command, exp.Merge, exp.TruncateTable, exp.Grant)


class UnsafeSQL(ValueError):
    pass


def extract_sql(text: str) -> str:
    """Pull the SQL out of a model reply (fenced block if present, else the whole text)."""
    m = re.search(r"```(?:sql|postgresql)?\s*(.*?)```", text, re.S | re.I)
    sql = m.group(1) if m else text
    return sql.strip().rstrip(";").strip()


def check(sql: str) -> str:
    """Return a safe, row-capped version of sql or raise UnsafeSQL with a reason the model can act on."""
    if not sql:
        raise UnsafeSQL("No SQL found in the reply.")
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.ParseError as e:
        raise UnsafeSQL(f"SQL does not parse: {str(e).splitlines()[0]}")
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise UnsafeSQL("Write exactly one SQL statement.")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise UnsafeSQL("Only SELECT queries are allowed.")
    if any(tree.find_all(*_FORBIDDEN)):
        raise UnsafeSQL("Only SELECT queries are allowed.")

    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        if name and name not in ALLOWED_TABLES and name not in cte_names:
            raise UnsafeSQL(f"Unknown table '{t.name}'. Use only: {', '.join(sorted(ALLOWED_TABLES))}.")

    limit = tree.args.get("limit")
    if limit is None:
        tree = tree.limit(MAX_ROWS)
    return tree.sql(dialect="postgres")
