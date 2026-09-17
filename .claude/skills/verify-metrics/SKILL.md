---
name: verify-metrics
description: |
  Verify the monitoring data pipeline after changing ANY metric: FrameData /
  SystemSnapshot / PerProcessSnapshot fields, SystemMetricsSampler, CSV columns,
  csv_parser mappings, display/stats logic. The mechanical half is
  `-t capture`; this skill is the reasoning half — the consumer sweep that no
  script can do. Triggers: "verify metrics", "metrics pipeline", after changing
  monitoring fields/sampling
---

# Verify the metrics pipeline

A metric change is rarely wrong in the place you changed it. It is wrong in the
fifth consumer you forgot. The capture self-check will tell you a column is
empty; it cannot tell you a chart still means the old thing.

## 1. Consumer sweep (the part you have to think about)

A field must carry the **same semantics** through every stage:

```
sample (SystemMetricsSampler / psutil / NVML)
  -> FrameData / SystemSnapshot / PerProcessSnapshot   (src/models.py)
  -> presentmon._enrich_frame stamps the frame          (src/core/presentmon.py)
  -> DataStore.add_frame / add_*_snapshot / compute_stats
  -> consumers: overlay_window · monitor_view · chart_base
                csv_export (CSV_COLUMNS + frame_to_row)
                csv_analysis_dialog
  -> csv_parser COLUMN_MAP_V2 (import roundtrip)
  -> i18n en.py / zh_CN.py
```

Grep each field you touched across `src/` and confirm every stage agrees. If
you changed what a number *means* (say `app_cpu_percent` became total-share ÷
logical cores rather than per-core), every consumer has to reflect it.

Recurring omissions:

- Added a field, forgot the CSV column or the parser mapping.
- Changed semantics, but a chart or stat still assumes the old one.
- Called `tr(key)` in a module that never imported `tr` — this crashed the
  overlay once.
- Made a field Optional but left a consumer without an `is not None` guard.
- **Truthiness coercion** (`x or None`, `if x else None`) on a metric, which
  silently nulls a real `0.0`. This was the App VRAM bug. Normalize with
  `is not None`.
- Per-process GPU/VRAM wired but all-NA: NVML per-process VRAM is **empty on
  Windows WDDM**. Use the `GPU Process Memory\Local Usage` perf counter
  (`sample_all_process_vram_mb`), not NVML's `GetGraphicsRunningProcesses`.

Do not spawn a subagent for this skill. Capture needs admin; a subagent
cannot pass UAC. You read `temp/selfcheck/report.txt` yourself.

## 2. Capture self-check (the part the machine does)

```bat
Scripts\selfcheck.bat capture -a <RenderingApp.exe> -s 10
```

Self-elevates (PresentMon needs admin) and tees to
`temp/selfcheck/report.txt`. It walks `CSV_COLUMNS` — the single source, so a
column you just added appears automatically — and reports per column:

- **fill rate**, non-empty / total
- **distinct values**, which is what catches a field that is technically
  populated but frozen at one number

Then read it:

- A column at 0% that the old build populated is your regression.
- A column at 0% on a machine without that sensor is expected. `SUSPECT` is a
  question, not a verdict.
- `distinct=1` over hundreds of frames means the sampler stamped a constant.
- If `gpu_available()` is true, `AppGPU%` and `AppVramMB` should be non-empty —
  unless the target is not actually rendering. Pick an app that is.

Target a **rendering** app. `dwm.exe` presents but tells you nothing about
per-process GPU attribution.

## 3. Consumers still build

```bat
python -m src.main -t ui
```

Builds the real window from `temp/real_capture.csv` and drives the real
refresh paths, so a consumer that now throws on your field shows up as an
`ERROR`. Delete `temp/real_capture.csv` first if you want it regenerated with
the new field.

## 4. Schema contract

```bat
python -m src.tests
```

`test_csv` checks `CSV_COLUMNS` against `FrameData` and round-trips real frames
through the real exporter and importer. A renamed field that only got renamed
on one side fails here.

## Done when

- Every stage in the sweep agrees on what the field means
- `-t capture`: your column has a plausible fill rate and more than one distinct
  value; nothing else regressed to 0%
- `-t ui`: no `ERROR`
- `python -m src.tests`: passes
