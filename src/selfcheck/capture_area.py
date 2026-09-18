"""Capture self-check: run PresentMon for real and report how full every column came out.

This is the area that catches the recurring bug in this codebase — a metric
that still exists, still exports, and is silently empty or zero for every frame.
The fill rate per column is the signal; what counts as an acceptable rate
depends on the machine and the target, so it is reported, not asserted.

Needs admin, like every real capture.
"""

from __future__ import annotations

import logging

from src.core.capture_session import CaptureSession
from src.core.metrics_schema import CSV_COLUMNS, frame_to_row
from src.core.system_metrics import gpu_available
from src.models import SessionConfig, frame_series_key
from src.selfcheck.report import Report
from src.selfcheck.spec import Area

AREA = Area(
    name="capture",
    needs_admin=True,
    judge="numbers",
    touches=(
        "src/core/presentmon.py",
        "src/core/capture_session.py",
        "src/core/metrics_sampler.py",
        "src/core/system_metrics.py",
        "src/core/csv_parser.py",
        "src/core/csv_importer.py",
        "src/core/data_store.py",
        "src/core/metrics_schema.py",
        "src/core/filters.py",
        "src/core/stutter_analysis.py",
        "src/models.py",
        "src/config.py",
    ),
)


def run(report: Report, out_dir: str, app: list[str] | None = None,
        seconds: int = 8, **_kwargs) -> None:
    logging.getLogger().setLevel(logging.WARNING)  # keep the report readable

    process_names = list(app or [])
    config = SessionConfig(
        process_names=process_names,
        timed_seconds=max(1, seconds),
    )

    report.section("capture")
    report.fact("target", ", ".join(process_names) or "all processes")
    report.fact("seconds", seconds)
    report.fact("GPU metrics available", gpu_available())

    session = CaptureSession()
    with report.step("run_blocking"):
        try:
            session.run_blocking(config)
        except KeyboardInterrupt:
            pass
        finally:
            session.stop()

    store = session.data_store
    frames = store.get_all_frames()
    report.fact("frames captured", len(frames))
    if not frames:
        report.error(
            "no frames — PresentMon produced nothing. Either the target is not "
            "presenting, or the capture pipeline is broken. Check temp/igp_debug.log")
        return

    by_app: dict[str, int] = {}
    by_app_pids: dict[str, set[int]] = {}
    for frame in frames:
        key = frame_series_key(frame)
        by_app[key] = by_app.get(key, 0) + 1
        app = frame.application or "unknown"
        by_app_pids.setdefault(app, set()).add(frame.process_id)
    report.section("frames per instance")
    for name, count in sorted(by_app.items(), key=lambda kv: -kv[1])[:8]:
        report.fact(name, count)

    report.section("instance identity")
    store_keys = set(store.get_process_names())
    report.fact("series keys", len(store_keys))
    if store_keys != set(by_app):
        report.error("DataStore series keys do not match captured frame PIDs")
    for app, pids in sorted(by_app_pids.items()):
        report.fact(f"{app} distinct PIDs", len(pids))
        if len(pids) > 1:
            split = sum(1 for k in by_app if k == app or k.startswith(app + "|"))
            if split < len(pids):
                report.error(
                    f"{app} has {len(pids)} PIDs but only {split} series keys")

    _describe_columns(report, frames)
    _describe_stats(report, store, frames)


def _describe_columns(report, frames) -> None:
    """Fill rate for every exported column, straight off the schema.

    Walking CSV_COLUMNS rather than a hand-written list is what makes a newly
    added metric show up here automatically instead of being forgotten.
    """
    report.section("column fill rate (non-empty / total)")
    total = len(frames)
    empty: list[str] = []
    constant: list[str] = []

    for column in CSV_COLUMNS:
        if column.field_name is None:
            continue
        values = [getattr(frame, column.field_name) for frame in frames]
        present = [v for v in values if v is not None]
        rate = len(present) / total if total else 0.0
        distinct = len({repr(v) for v in present})
        report.fact(column.export_name, f"{len(present):>6}/{total}  {rate:6.1%}  distinct={distinct}")
        if not present:
            empty.append(column.export_name)
        elif distinct == 1 and total > 20:
            constant.append(f"{column.export_name}={present[0]!r}")

    if empty:
        report.suspect(f"always empty: {', '.join(empty)}")
    if constant:
        report.suspect(f"never varied: {', '.join(constant)}")

    with report.step("frame_to_row over every frame"):
        widths = {len(frame_to_row(frame)) for frame in frames}
        report.fact("row widths produced", widths)
        if len(widths) != 1:
            report.error(f"export rows have inconsistent widths: {widths}")


def _describe_stats(report, store, frames) -> None:
    report.section("computed stats")
    with report.step("compute_stats"):
        stats = store.compute_stats()
        if not stats:
            report.suspect("compute_stats returned nothing for a non-empty capture")
        else:
            report.fact(
                stats.process_name or "(all)",
                f"avg_fps={stats.avg_fps} frames={stats.frame_count}",
            )
        for key in store.get_process_names()[:4]:
            one = store.compute_stats(key)
            if one is not None:
                report.fact(key, f"avg_fps={one.avg_fps} frames={one.frame_count}")
    with report.step("history"):
        report.fact("elapsed seconds", round(store.get_elapsed_seconds(), 2))
        report.fact("frame count", store.get_frame_count())
