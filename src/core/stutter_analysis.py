"""Offline frame pacing / stutter analysis helpers."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median

from src.core.csv_importer import group_frames_by_app
from src.models import FrameData

FIXED_33_MS = 33.3
FIXED_50_MS = 50.0
DYNAMIC_MULTIPLIER = 2.0
DYNAMIC_MIN_BASELINE_FRAMES = 30
DYNAMIC_WINDOW_FRAMES = 120


@dataclass(frozen=True)
class StutterEvent:
    app: str
    time_s: float
    frame_time_ms: float
    fps: float | None
    kind: str
    severity: float


@dataclass(frozen=True)
class StutterSummary:
    app: str
    frame_count: int
    duration_s: float
    avg_fps: float | None
    p001_low_fps: float | None
    p01_low_fps: float | None
    p05_low_fps: float | None
    avg_frame_time_ms: float | None
    median_frame_time_ms: float | None
    max_frame_time_ms: float | None
    fixed_33_count: int
    fixed_50_count: int
    dynamic_spike_count: int
    worst_time_s: float | None


@dataclass(frozen=True)
class StutterAnalysisResult:
    summaries: list[StutterSummary]
    events: list[StutterEvent]


def analyze_stutter(frames: list[FrameData]) -> StutterAnalysisResult:
    """Analyze frame pacing for each app in *frames*."""
    summaries: list[StutterSummary] = []
    events: list[StutterEvent] = []

    for app, app_frames in group_frames_by_app(frames).items():
        summary, app_events = _analyze_app(app, app_frames)
        summaries.append(summary)
        events.extend(app_events)

    summaries.sort(key=lambda s: (
        -(s.fixed_50_count + s.dynamic_spike_count),
        -(s.max_frame_time_ms or 0.0),
        s.app.lower(),
    ))
    events.sort(key=lambda e: (-e.severity, e.time_s, e.app.lower()))
    return StutterAnalysisResult(summaries=summaries, events=events)


def frame_time_ms(frame: FrameData) -> float | None:
    """Return frame time from PresentMon or derive it from FPS."""
    if frame.ms_between_presents is not None and frame.ms_between_presents > 0:
        return float(frame.ms_between_presents)
    if frame.fps is not None and frame.fps > 0:
        return 1000.0 / float(frame.fps)
    return None


def elapsed_frame_series(frames: list[FrameData]) -> list[tuple[float, FrameData, float]]:
    """Return ``(elapsed_s, frame, frame_time_ms)`` for analyzable frames."""
    elapsed = 0.0
    series: list[tuple[float, FrameData, float]] = []
    for frame in frames:
        ft = frame_time_ms(frame)
        dt = ft if ft is not None and ft > 0 else 16.667
        elapsed += dt / 1000.0
        if ft is not None and ft > 0:
            series.append((elapsed, frame, ft))
    return series


def _analyze_app(app: str, frames: list[FrameData]) -> tuple[StutterSummary, list[StutterEvent]]:
    series = elapsed_frame_series(frames)
    frame_times = [ft for _elapsed, _frame, ft in series]
    fps_values = [_fps_from_frame(frame, ft) for _elapsed, frame, ft in series]
    fps_values = [v for v in fps_values if v is not None and v > 0]

    events: list[StutterEvent] = []
    fixed_33_count = fixed_50_count = dynamic_spike_count = 0
    previous: list[float] = []

    for elapsed, frame, ft in series:
        kinds: list[str] = []
        if ft > FIXED_33_MS:
            fixed_33_count += 1
            kinds.append(">33.3ms")
        if ft > FIXED_50_MS:
            fixed_50_count += 1
            kinds.append(">50ms")
        baseline = _rolling_median(previous)
        if baseline is not None and ft > max(FIXED_33_MS, baseline * DYNAMIC_MULTIPLIER):
            dynamic_spike_count += 1
            kinds.append(">2x median")
        if kinds:
            events.append(StutterEvent(
                app=app,
                time_s=elapsed,
                frame_time_ms=ft,
                fps=_fps_from_frame(frame, ft),
                kind="+".join(kinds),
                severity=_severity(ft, baseline),
            ))
        previous.append(ft)
        if len(previous) > DYNAMIC_WINDOW_FRAMES:
            previous.pop(0)

    max_ft = max(frame_times) if frame_times else None
    worst_time = None
    if max_ft is not None:
        for elapsed, _frame, ft in series:
            if ft == max_ft:
                worst_time = elapsed
                break

    summary = StutterSummary(
        app=app,
        frame_count=len(series),
        duration_s=round(series[-1][0], 3) if series else 0.0,
        avg_fps=round(mean(fps_values), 1) if fps_values else None,
        p001_low_fps=_round_or_none(_percentile(fps_values, 0.001)),
        p01_low_fps=_round_or_none(_percentile(fps_values, 0.01)),
        p05_low_fps=_round_or_none(_percentile(fps_values, 0.05)),
        avg_frame_time_ms=round(mean(frame_times), 2) if frame_times else None,
        median_frame_time_ms=round(median(frame_times), 2) if frame_times else None,
        max_frame_time_ms=round(max_ft, 2) if max_ft is not None else None,
        fixed_33_count=fixed_33_count,
        fixed_50_count=fixed_50_count,
        dynamic_spike_count=dynamic_spike_count,
        worst_time_s=round(worst_time, 3) if worst_time is not None else None,
    )
    return summary, events


def _rolling_median(values: list[float]) -> float | None:
    if len(values) < DYNAMIC_MIN_BASELINE_FRAMES:
        return None
    return median(values[-DYNAMIC_WINDOW_FRAMES:])


def _fps_from_frame(frame: FrameData, ft: float) -> float | None:
    if frame.fps is not None and frame.fps > 0:
        return float(frame.fps)
    if ft > 0:
        return 1000.0 / ft
    return None


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    idx = min(len(sorted_values) - 1, max(0, int(len(sorted_values) * pct)))
    return sorted_values[idx]


def _round_or_none(value: float | None, digits: int = 1) -> float | None:
    return round(value, digits) if value is not None else None


def _severity(frame_time: float, baseline: float | None) -> float:
    baseline_ratio = frame_time / baseline if baseline and baseline > 0 else 0.0
    return max(frame_time / FIXED_33_MS, baseline_ratio)
