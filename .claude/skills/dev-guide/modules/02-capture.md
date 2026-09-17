# 02 · Capture core

## Key files

- `src/core/presentmon.py` — `PresentMonWrapper(QThread)`; spawn PresentMon, read stdout, `_enrich_frame`
- `src/core/csv_parser.py` — `CsvParser`; column map from `metrics_schema`, `_compute_fps`
- `src/core/metrics_schema.py` — single source for CSV/FrameData fields
- `src/core/metrics_sampler.py` — `SystemMetricsSampler(QThread)`; ~500ms system + per-process
- `src/core/system_metrics.py` — psutil/NVML; `LOGICAL_CORES`, `process_memory_mb`, `sample_system`

## Responsibilities

PresentMon emits frames → `_enrich_frame` stamps system/process fields from sampler `_latest`. The sampler writes DataStore snapshots and `_latest` on a fixed ~500ms cadence.

## Pitfalls (high-frequency)

- **`psutil.cpu_percent(interval=None)` at frame rate returns 0.** Frame gaps are often below the ~15.6ms Windows clock. **Never** sample CPU inside `_enrich_frame`. `SystemMetricsSampler` owns that (~500ms). This once made TotalCPU% ~88% zeros and AppCPU% ~91% NA.
- **`Process.cpu_percent()` is per-core** (one full core = 100%, can exceed 100% on multi-core). `app_cpu_percent` must `÷ LOGICAL_CORES` (Task Manager total share). Also store `app_cpu_cores = raw/100`.
- **Memory:** `process_memory_mb()` = USS (private working set, Task Manager "Memory"), fallback RSS. Do **not** use `memory_info().private` (commit size, 2–3× larger).
- **NVML total vs per-process are different APIs.** Instant AppGPU% can exceed TotalGPU% (~4%, up to +27). Expected, not a bug.
- **Per-process VRAM is the Windows GPU perf counter, not NVML.** NVML process lists are empty under WDDM (empty App VRAM chart, all-NA `AppVramMB`). Use `sample_all_process_vram_mb()` via win32pdh `\GPU Process Memory(*)\Local Usage` (same source as Task Manager), `{pid: resident MB}` summed across adapters. Call **once per sampler tick**, then `vram_map.get(pid)`. Use **Local Usage**, never Dedicated Usage (commit space; can report more than the card). `sample_process_gpu` is GPU% only; its `vram_mb` stays `None`. Do not mix with system `gpu_vram_used_mb`.
- **`_enrich_frame` stamps only.** Read `sampler.latest_system` / `latest_per_process(pid)`. No psutil/NVML in the frame loop.
- **Dynamic PIDs:** `configure` seeds handles from `process_ids` + `process_names`; each tick `_refresh_dynamic_pids()`; wrapper `track_pid(pid)` only registers — sampling stays on the sampler thread.
- **New session must clear `_latest`.** `configure` is a session boundary. Otherwise the first frames inherit the previous session's CPU/GPU/RAM/VRAM.
- **PresentMon 2.4.1 names are short** (`CPUBusy` / `GPUTime` / `Runtime`). Aliases live on `metrics_schema.CSV_COLUMNS`.
- **NVML `-1` means unavailable**; sampler normalizes to `None`.
- **Missing = `None`. Never truthiness-coerce.** `if x else None` / `x or None` drops a real `0.0`. Use `is not None` / `< 0 → None`.
- **Displays:** `EnumDisplayDevices` + `EnumDisplaySettings`; primary first; fallback single display. Do not read primary only.
- **Per-core CPU + GPU power/temp** are **snapshot-only** (not stamped onto FrameData, not in CSV). Power is mW÷1000. Missing backend → `None`.

## Checklist

- [ ] CPU sample → `÷ LOGICAL_CORES` + `app_cpu_cores`; per-core via `percpu=True`
- [ ] Memory → USS (`process_memory_mb`)
- [ ] Cadence still in the sampler (~500ms), not `_enrich_frame`
- [ ] Dynamic PIDs still discovered; wrapper still registers real frame PIDs
- [ ] Per-process VRAM → `Local Usage` perf counter; no truthiness drop of `0.0`; run `verify-metrics`
- [ ] Snapshot-only fields stay off FrameData/CSV
- [ ] PresentMon/CSV columns start in `metrics_schema.CSV_COLUMNS`

---
last_updated: 2026-09-17
