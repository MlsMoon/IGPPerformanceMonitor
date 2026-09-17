"""Test: filters — iqr_filter_series and median_adaptive_filter correctness."""

from src.core.filters import iqr_filter_series, median_adaptive_filter


def run():
    # --- iqr_filter_series: outlier should be removed ---
    # Signal with natural variance around 100 + one spike at 500.
    # (Flat data has IQR=0, so multiplier*IQR=0 → nothing filtered.)
    data = [(float(i), 100.0 + (i % 5) * 2.0) for i in range(50)]
    data[25] = (25.0, 500.0)  # spike
    filtered = iqr_filter_series(data, multiplier=3.0, min_window=1)
    assert len(filtered) < len(data), f"outlier not filtered ({len(filtered)} == {len(data)})"
    for _, y in filtered:
        assert y < 200.0, f"outlier survived: y={y}"

    # Clean same-valued data should pass through unchanged
    flat = [(float(i), 50.0) for i in range(20)]
    flat_f = iqr_filter_series(flat)
    assert len(flat_f) == len(flat), "flat data should not be filtered"

    # --- median_adaptive_filter ---
    # Uses multiplicative bounds [median/mult, median*mult], so a spike
    # at 500 with median ~102 needs multiplier < ~4.9 to be caught.
    filtered_m = median_adaptive_filter(data, window=11, multiplier=3.0)
    assert len(filtered_m) < len(data), "median_adaptive should filter spike"
    for _, y in filtered_m:
        assert y < 200.0, f"median_adaptive outlier survived: y={y}"
