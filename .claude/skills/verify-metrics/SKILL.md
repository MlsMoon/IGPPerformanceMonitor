---
name: verify-metrics
description: |
  Verify the monitoring metrics data pipeline end-to-end using headless capture. Use whenever you
  change ANY monitoring data: FrameData / SystemSnapshot / PerProcessSnapshot fields,
  SystemMetricsSampler, csv_export columns, csv_parser mappings, or any display/stats logic.
  Catches the recurring "I changed the metric but forgot downstream consumer X" bug (overlay crash,
  stale chart semantics, CSV column drift, missing i18n). Triggers: "verify metrics",
  "metrics pipeline", "headless test", after changing monitoring data fields/sampling.
---

# Verify Metrics Pipeline (headless)

When you change any monitoring metric (field, sampling formula, CSV column, display), run this
before committing. It prevents the classic "changed the metric, forgot X" regressions.

## The pipeline (a change must be consistent across ALL stages)

```
sample (SystemMetricsSampler / psutil / NVML)
  -> FrameData / SystemSnapshot / PerProcessSnapshot fields  (src/models.py)
  -> presentmon._enrich_frame stamps frame                   (src/core/presentmon.py)
  -> DataStore.add_frame / add_system_snapshot / add_per_process_snapshot + compute_stats
  -> consumers:
       overlay_window.py · monitor_view.py · chart_base.py
       csv_export.py (CSV_EXPORT_HEADER_V2 + _frame_to_row)
       csv_analysis_dialog.py
  -> csv_parser.py COLUMN_MAP_V2 (import roundtrip)
  -> i18n en.py / zh_CN.py
```

If you change semantics (e.g. `app_cpu_percent` is now total-share ÷ logical cores, NOT per-core),
EVERY consumer must reflect it. Same for memory (USS vs private), GPU, etc.

## Step 1 — Static consistency sweep (no admin)

For each field you touched, grep the whole `src/` and confirm it appears with the SAME semantics
in every stage above. Common omissions:

- added a field but forgot CSV column + parser mapping
- changed semantics but a chart/stat still assumes the old one
- used `tr(key)` in a module that doesn't `from src.i18n import tr` (overlay crashed this way)
- forgot `is not None` guard after switching a field to Optional
- used a **truthiness coercion** (`if x else None` / `x or None`) on a metric — it silently nulls a real `0.0` (the App VRAM bug). Normalize with `is not None`.
- per-process GPU/VRAM looks wired but is all-NA: NVML per-process VRAM is **empty on Windows WDDM** — use the Windows `GPU Process Memory\Local Usage` perf counter (`sample_all_process_vram_mb`), not NVML's `GetGraphicsRunningProcesses`.

## Step 2 — Headless capture (needs Admin / PresentMon)

Do **not** run bare `python -m src.main --headless` from a non-admin agent (UAC relaunch drops output). Prefer:

```
Scripts\capture_debug.bat --process-name <App.exe> --timed 10
```

Output: `temp/igpmon-<App>-<ts>.csv` (system header + frame rows + stats).
Use `--timed 0` for continuous until Ctrl+C; `-o path` for a custom output when running the module directly **already elevated**.

## Step 3 — Validate exported CSV columns

Schema-driven: check **every** `CSV_COLUMNS` export name. A hardcoded list once omitted `AppVramMB` and the empty-chart bug shipped.

If `gpu_available()`, `AppGPU%` and `AppVramMB` must have non-NA values (or the target is not using the GPU — pick a rendering app).

Touched columns must match live-view semantics (`AppCPU%` ~ Task Manager total-share, `AppCPUCores` = cores used, `AppMemoryMB` ~ USS, `AppVramMB` ~ Task Manager per-process GPU memory via the Windows perf counter).

## Step 4 — Import roundtrip

`csv_importer.import_file` on the same CSV. Count non-None `fps`, `app_cpu_percent`, `app_cpu_cores`, `app_memory_mb`, `total_cpu_percent`, `gpu_vram_percent`.

## Step 5 — UI does not throw (offscreen, no admin)

Construct `CsvAnalysisDialog` and `OverlayWindow` from the imported file / a stamped `FrameData`. `_refresh_display()` must not raise.

## Definition of done

- `python -m py_compile` on all changed files
- headless CSV: every exported column reported; GPU box → `AppGPU%` / `AppVramMB` non-NA
- import roundtrip preserves them
- overlay + CsvAnalysisDialog + MonitorView construct/refresh without exceptions
- semantics consistent across sampler → export → import → views (Step 1 sweep)
