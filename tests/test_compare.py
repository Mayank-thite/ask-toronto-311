from ask311.compare import is_ordered, results_match


def test_extra_columns_and_names_ignored():
    assert results_match([("York Centre", 10)], [(6, "York Centre", 10)], ordered=False)


def test_numbers_normalised():
    assert results_match([(3,)], [(3.0,)], ordered=False)
    assert results_match([(14.5,)], [(14.499,)], ordered=False)


def test_dates_normalised():
    assert results_match([("2025-02-01", 5)], [("2025-02-01T00:00:00", 5)], ordered=False)


def test_order_matters_only_when_sorted():
    gold, pred = [("a", 2), ("b", 1)], [("b", 1), ("a", 2)]
    assert results_match(gold, pred, ordered=False)
    assert not results_match(gold, pred, ordered=True)


def test_wrong_value_fails():
    assert not results_match([(36174,)], [(70377,)], ordered=False)


def test_rows_must_pair_up():
    gold = [("a", 1), ("b", 2)]
    pred = [("a", 2), ("b", 1)]          # same column values, wrong pairing
    assert not results_match(gold, pred, ordered=False)


def test_is_ordered():
    assert is_ordered("SELECT x FROM t ORDER BY x", 3)
    assert not is_ordered("SELECT x FROM t ORDER BY x LIMIT 1", 1)
    assert not is_ordered("SELECT COUNT(*) FROM (SELECT x FROM t ORDER BY x) s", 1)


def test_month_numbers_accepted_within_one_year():
    gold = [("2025-01-01", 5), ("2025-02-01", 7)]
    assert results_match(gold, [(1.0, 5), (2.0, 7)], ordered=True)
    # across two years a bare month number is ambiguous, so it doesn't count
    gold2 = [("2024-12-01", 5), ("2025-01-01", 7)]
    assert not results_match(gold2, [(12.0, 5), (1.0, 7)], ordered=True)


def test_answer_cols_ignore_context_count():
    assert results_match([("Beaches-East York", 51544)], [("Beaches-East York",)], ordered=False, answer_cols=[0])
    assert not results_match([("Beaches-East York", 51544)], [("Davenport",)], ordered=False, answer_cols=[0])


def test_ties_may_come_in_any_order():
    gold = [("a", 5.0), ("b", 3.0), ("c", 3.0)]
    pred = [("a", 5.0), ("c", 3.0), ("b", 3.0)]
    assert results_match(gold, pred, ordered=True, order_col=1)
    assert not results_match(gold, [("b", 3.0), ("a", 5.0), ("c", 3.0)], ordered=True, order_col=1)
