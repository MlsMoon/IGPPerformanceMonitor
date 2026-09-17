"""Outlier filtering utilities for time-series performance data."""


def median_adaptive_filter(
    data: list[tuple[float, float]],
    window: int = 15,
    multiplier: float = 5.0,
) -> list[tuple[float, float]]:
    """Filter outliers using a rolling-median adaptive window.

    For each point, checks whether it falls within
    [window_median / multiplier, window_median * multiplier].
    Handles variable refresh rates naturally.

    Args:
        data: list of (time, value) pairs.
        window: number of preceding points to compute median from.
        multiplier: keep values within median * [1/multiplier, multiplier].

    Returns:
        Filtered list (order preserved).
    """
    if len(data) < window:
        return list(data)

    result: list[tuple[float, float]] = []
    for i in range(len(data)):
        start = max(0, i - window + 1)
        chunk = data[start:i + 1]
        vals = sorted(v for _, v in chunk)
        median = vals[len(vals) // 2]
        lower = median / multiplier
        upper = median * multiplier
        if lower <= data[i][1] <= upper:
            result.append(data[i])
    return result


def iqr_filter_series(
    data: list[tuple[float, float]],
    multiplier: float = 3.0,
    min_window: int = 10,
) -> list[tuple[float, float]]:
    """Filter outliers via Inter-Quartile Range on the value dimension.

    Bounds: [Q1 - m*IQR, Q3 + m*IQR].  For small datasets (<30 points)
    a wider multiplier (5.0) is used to avoid false positives.

    Args:
        data: list of (time, value) pairs.
        multiplier: IQR multiplier (3.0 = extreme outliers).
        min_window: minimum points required before filtering.

    Returns:
        Filtered list (order preserved).
    """
    if len(data) < max(4, min_window):
        return list(data)

    values = [v for _, v in data]
    n = len(values)
    sorted_vals = sorted(values)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[(3 * n) // 4]
    iqr = q3 - q1
    if iqr == 0:
        return list(data)

    effective_m = multiplier if n >= 30 else 5.0
    lower = q1 - effective_m * iqr
    upper = q3 + effective_m * iqr
    return [(t, v) for (t, v) in data if lower <= v <= upper]
