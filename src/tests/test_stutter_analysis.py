"""Test: stutter_analysis — controlled frame pacing edge cases."""

from src.core.stutter_analysis import analyze_stutter, elapsed_frame_series
from src.tests._factory import make_frame


def _frames(frame_times: list[float], app: str = "Game.exe"):
    # Controlled frame times are required to hit exact 33ms/50ms/spike thresholds.
    return [
        make_frame(
            application=app,
            process_id=100,
            ms_between_presents=ft,
            fps=1000.0 / ft,
        )
        for ft in frame_times
    ]


def run():
    stable = _frames([16.667] * 90)
    result = analyze_stutter(stable)
    assert len(result.summaries) == 1
    summary = result.summaries[0]
    assert summary.fixed_33_count == 0
    assert summary.fixed_50_count == 0
    assert summary.dynamic_spike_count == 0
    assert not result.events

    spiky = _frames([16.667] * 40 + [40.0, 60.0, 16.667])
    result = analyze_stutter(spiky)
    summary = result.summaries[0]
    assert summary.fixed_33_count == 2
    assert summary.fixed_50_count == 1
    assert summary.dynamic_spike_count == 2
    assert any(">33.3ms" in e.kind for e in result.events)
    assert any(">50ms" in e.kind for e in result.events)
    assert any(">2x median" in e.kind for e in result.events)

    # Controlled fallback case: no PresentMon frame time, derive from FPS.
    derived = [
        make_frame(ms_between_presents=None, fps=50.0),
        make_frame(ms_between_presents=None, fps=None),
    ]
    series = elapsed_frame_series(derived)
    assert len(series) == 1
    assert abs(series[0][2] - 20.0) < 0.001
