import datetime
import decimal

import psycopg

from .config import AGENT_DSN


def _clean(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    return v


def run_query(sql: str, dsn: str = AGENT_DSN) -> tuple[list[str], list[tuple]]:
    """Run a query as the read-only agent role. Returns (columns, rows)."""
    with psycopg.connect(dsn, autocommit=True) as con:
        cur = con.execute(sql)
        cols = [d.name for d in cur.description] if cur.description else []
        rows = [tuple(_clean(v) for v in r) for r in cur.fetchall()]
    return cols, rows
