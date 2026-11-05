import pytest

from ask311.guard import UnsafeSQL, check, extract_sql


def test_extracts_fenced_sql():
    assert extract_sql("Here you go:\n```sql\nSELECT 1;\n```") == "SELECT 1"


def test_adds_row_cap():
    assert "LIMIT 500" in check("SELECT * FROM v_requests")


def test_keeps_existing_limit():
    assert check("SELECT * FROM v_requests LIMIT 5").endswith("LIMIT 5")


@pytest.mark.parametrize("sql", [
    "DELETE FROM service_requests",
    "DROP TABLE wards",
    "UPDATE wards SET ward_name = 'x'",
    "INSERT INTO wards VALUES (99, 'x')",
    "SELECT 1; DROP TABLE wards",
    "SELECT * FROM pg_shadow",
    "SELECT * FROM v_requests WHERE",
    "",
])
def test_rejects_unsafe_or_broken(sql):
    with pytest.raises(UnsafeSQL):
        check(sql)


def test_allows_ctes():
    check("WITH c AS (SELECT ward_id FROM service_requests) SELECT COUNT(*) FROM c")
