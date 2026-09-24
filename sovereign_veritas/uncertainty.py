from __future__ import annotations

from typing import Any


def normalize_uncertainty(
    *,
    prediction_value: Any = None,
    interval: list[float] | tuple[float, float] | None = None,
    method: str = "unspecified",
    coverage_target: float | None = None,
    nonconformity: float | None = None,
    extra: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], float]:
    """Produce a structured uncertainty dict and a coarse evidence_quality score.

    This is intentionally dependency-free. Real conformal predictors should
    supply interval / nonconformity; this helper only normalizes and scores.

    Quality heuristic (deterministic, explicit, not a statistical claim):
    - base 0.5
    - +0.2 if a finite interval is supplied
    - +0.2 if coverage_target is in (0, 1]
    - +0.1 if nonconformity is provided and finite
    Clamped to [0.0, 1.0].
    """
    uncertainty: dict[str, Any] = {
        "method": method,
        "prediction_value": prediction_value,
    }
    if interval is not None:
        uncertainty["interval"] = list(interval)
    if coverage_target is not None:
        uncertainty["coverage_target"] = coverage_target
    if nonconformity is not None:
        uncertainty["nonconformity"] = nonconformity
    if extra:
        uncertainty.update(extra)

    quality = 0.5
    if interval is not None and len(interval) >= 2:
        try:
            lo, hi = float(interval[0]), float(interval[1])
            if lo <= hi and all(map(lambda x: x == x, (lo, hi))):  # finite
                quality += 0.2
        except (TypeError, ValueError):
            pass
    if coverage_target is not None:
        try:
            ct = float(coverage_target)
            if 0.0 < ct <= 1.0:
                quality += 0.2
        except (TypeError, ValueError):
            pass
    if nonconformity is not None:
        try:
            nc = float(nonconformity)
            if nc == nc:  # finite
                quality += 0.1
        except (TypeError, ValueError):
            pass

    quality = max(0.0, min(1.0, quality))
    return uncertainty, quality
