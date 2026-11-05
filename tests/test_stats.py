import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "eval"))
from stats import mcnemar_exact, wilson  # noqa: E402


def test_wilson_contains_point_estimate():
    lo, hi = wilson(83, 100)
    assert lo < 83 < hi and 74 < lo < 76 and 89 < hi < 91


def test_mcnemar():
    a = {i: i < 10 for i in range(20)}
    b = {i: False for i in range(20)}
    only_a, only_b, p = mcnemar_exact(a, b)
    assert (only_a, only_b) == (10, 0) and p < 0.01
    assert mcnemar_exact(a, a)[2] == 1.0
