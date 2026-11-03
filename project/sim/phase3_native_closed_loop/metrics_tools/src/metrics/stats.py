"""Small, explicit statistics for the Phase 3 metrics (Phase 3 S8 candidate).

Rules (fixed, so every report states the same thing):
  * percentiles are NEAREST-RANK (no interpolation): P_q = the ceil(q/100 * n)-th smallest value;
  * a percentile is only reported when the sample is large enough for it to be a real order
    statistic of the tail: P50 needs n >= 1, P90 n >= 10, P95 n >= 20, P99 n >= 100; otherwise the
    value is the string "INSUFFICIENT_SAMPLES (n=<n>, need <k>)";
  * no data at all -> "NOT_MEASURED";
  * rates are k / n with the exact counts next to them, and a Wilson 95 % interval only when n >= 1.
Nothing here invents, smooths or extrapolates a value.
"""

from __future__ import annotations

import math
from typing import Sequence

NOT_MEASURED = "NOT_MEASURED"
MIN_N = {50: 1, 90: 10, 95: 20, 99: 100}


def insufficient(n: int, need: int) -> str:
    return f"INSUFFICIENT_SAMPLES (n={n}, need {need})"


def nearest_rank(sorted_values: Sequence[float], q: float) -> float:
    n = len(sorted_values)
    k = max(1, math.ceil(q / 100.0 * n))
    return sorted_values[k - 1]


def distribution(values: Sequence[float], unit: str) -> dict:
    vals = sorted(float(v) for v in values)
    n = len(vals)
    if n == 0:
        return {"n": 0, "unit": unit, "status": NOT_MEASURED}
    out = {"n": n, "unit": unit, "min": vals[0], "max": vals[-1], "mean": sum(vals) / n}
    for q, need in MIN_N.items():
        out[f"p{q}"] = nearest_rank(vals, q) if n >= need else insufficient(n, need)
    return out


def rate(k: int, n: int) -> dict:
    if n == 0:
        return {"k": 0, "n": 0, "status": NOT_MEASURED}
    p = k / n
    z = 1.959963984540054
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    lo = 0.0 if k == 0 else max(0.0, centre - half)          # exact end points (no rounding residue)
    hi = 1.0 if k == n else min(1.0, centre + half)
    return {"k": k, "n": n, "rate": p, "wilson95": [lo, hi]}
