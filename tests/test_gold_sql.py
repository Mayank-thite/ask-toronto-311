"""Every gold answer must run and return rows. Skipped when no database is loaded."""
import pathlib

import pytest
import yaml

QUESTIONS = yaml.safe_load(open(pathlib.Path(__file__).parents[1] / "eval" / "questions.yaml"))


def _db():
    try:
        from ask311.db import run_query
        run_query("SELECT 1 FROM service_requests LIMIT 1")
        return run_query
    except Exception:
        return None


run_query = _db()


@pytest.mark.skipif(run_query is None, reason="database not loaded")
@pytest.mark.parametrize("q", QUESTIONS, ids=[q["id"] for q in QUESTIONS])
def test_gold_runs(q):
    cols, rows = run_query(q["sql"])
    assert rows, f"{q['id']} returned no rows"


def test_question_set_shape():
    assert len(QUESTIONS) == 100
    assert len({q["id"] for q in QUESTIONS}) == 100
    cats = {q["category"] for q in QUESTIONS}
    assert cats == {"simple", "time", "ranking", "semantics", "multi_step"}


@pytest.mark.skipif(run_query is None, reason="database not loaded")
def test_agent_role_is_read_only():
    with pytest.raises(Exception):
        run_query("DELETE FROM wards")
