# 03 · Storage and models

## Key files

- `src/models.py` — `FrameData` / `SystemInfo` / snapshots / `ProcessStats` / `SessionConfig`
- `src/core/data_store.py` — thread-safe store, histories, `compute_stats`
- `src/core/metrics_schema.py` — CSV field schema
- `src/core/filters.py` — `median_adaptive_filter`, `iqr_filter_series`

## Responsibilities

Store frames and histories thread-safely for UI and export.

## Pitfalls

- **Missing is `None`.** Enriched fields (including GPU) never use a `-1` sentinel. `_compute_fps` returns `None` when empty. Consumers use `is not None` — keep real 0, write NA when missing.
- **Per-process mem/cpu/gpu history is frame-based** (key=`frame_series_key` = `Application|PID`, written in `add_frame`). Two `Unity.exe` must not share a curve. Do **not** key off `per_process_snapshots[proc.name()]` — PresentMon `application` and psutil `name()` can differ, and live curves vanish. CSV still stores the raw `Application` column.
- **Pretty labels** (`DataStore.set_process_labels` / `display_name`) are UI-only. Idle configured keys come from `SessionConfig.process_ids` as `exe|pid`.
- **FPS history** is written when `fps is not None and fps > 0`.
- **System snapshots come from the sampler** (`add_system_snapshot`). Total CPU/GPU/VRAM charts read `get_system_snapshots`.
- **Snapshot-only fields** (`per_core_cpu_percent`, `gpu_power_w`, `gpu_temp_c`, `gpu_power_limit_w`) stay off FrameData and CSV.
- **`display_outputs`** is `["3840x2160@59Hz", ...]`; `display_resolution` / `display_refresh_hz` remain primary for old CSV.
- **`app_cpu_cores` and `app_vram_mb`** have frame-based histories (`get_cpu_cores_history` / `get_app_vram_history`). `compute_stats.avg_app_vram_mb` uses `app_vram_mb`, **not** system `gpu_vram_used_mb`.
- **Configured apps vs apps that presented:** `get_monitored_apps()` is user config; `get_process_names()` is apps with ≥1 frame. Idle apps stay in the stats list (dimmed). `start_session()` / `clear()` reset `_monitored_apps`.
- **`add_frame` does not create snapshots.**
- **All reads/writes take `self._lock`.**
- **Trim:** frame-driven histories trim by **time window** (`_history_keep_s`), not a fixed count. Count trim (old 5000) emptied the front of high-FPS charts. `_max_history_points` is only a runaway-FPS cap. System snapshots still count-trim (`_max_snapshots=5000`). `compute_stats` / CSV read `_frames`, not trimmed histories.

## Checklist

- [ ] New/changed FrameData field → `metrics_schema` then 02/03/05/i18n; run `verify-metrics`
- [ ] Per-process history still keyed by `frame_series_key` (exe + PID)
- [ ] Missing-value consumers use `is not None`
- [ ] Stats ignore `None`
- [ ] Configured-app lists use `get_monitored_apps()`
- [ ] Frame history trim is time-windowed; stats/CSV still use `_frames`

---
last_updated: 2026-09-18
