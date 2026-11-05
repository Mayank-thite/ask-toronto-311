"""Small, dependency-free statistics for comparing runs on the same 100 questions."""
import math


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion, in percent."""
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * (c - h), 1), round(100 * (c + h), 1)


def mcnemar_exact(a: dict, b: dict) -> tuple[int, int, float]:
    """Paired test on the same questions. a, b map question id -> correct (bool).

    Returns (only_a_right, only_b_right, two-sided exact p-value). Questions both runs
    got right or both got wrong carry no information about which setup is better.
    """
    only_a = sum(a[k] and not b[k] for k in a)
    only_b = sum(b[k] and not a[k] for k in a)
    n, k = only_a + only_b, min(only_a, only_b)
    if n == 0:
        return only_a, only_b, 1.0
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return only_a, only_b, min(1.0, p)
