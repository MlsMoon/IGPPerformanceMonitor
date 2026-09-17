---
name: test-after-changes
description: |
  Standard post-change tests (static + real headless capture). After any src/
  edit: (1) py_compile / import / offscreen smoke (2) headless capture of a
  running app via capture_debug.bat (self-elevates, writes temp/). Avoids
  `python -m src.main --headless` from a non-admin agent (UAC relaunch drops
  output). Triggers: "test after changes", "headless test", before commit
---

# Test After Changes

Run these three steps after `src/` changes, before commit. They catch syntax/import errors, UI ctor/callback crashes, and a broken headless pipeline.

> How to **write** tests → `test-design`. How to **run/verify** → this skill.

## Step A — Static (no admin)

### A1. py_compile

```bat
python -m py_compile <each changed .py>
```

Compile `src/tests/` too if you edited tests.

### A2. Quick import (optional, small diffs)

```bat
python -c "from <module> import ..."
```

### A3. Offscreen suite

```bat
python -m src.tests
```

| File | Covers | Guards |
|---|---|---|
| `test_models` | FrameData / SystemInfo / ProcessStats + format helpers | default-field / format crashes |
| `test_i18n` | en + zh_CN **all keys**, identical key sets | added a key on one side only |
| `test_data_store` | frames / snapshots / stats / history / multi-app / clear | add_frame / stats drift |
| `test_csv` | real PresentMon golden + export/import + schema sentinels | column/field mismatch |
| `test_filters` | IQR + median-adaptive | silent filter breakage |
| `test_system_metrics` | gpu_available / process names / system info | WMI/NVML fallback |
| `test_theme` | Theme fields / palette / QSS / toggle | new color without a field |
| `test_ui_*` | MainWindow / overlay / process panel / analysis | ctor / callback crashes |
| `test_release_manifest` | GitHub URLs, SHA256, no-BOM JSON, previous block | broken update contract |
| `test_app_update_service` | required fields, validate | incomplete manifest |

If you change a public API, update the matching `src/tests/` file.

The suite points `APPDATA` at a throwaway directory (`src/tests/__init__.py`) before anything imports `app_config`, because the UI tests build a real `MainWindow` and call real slots that persist theme, chart visibility and splitter state. Without it the suite silently rewrites your own settings — it flipped a dev machine to the light theme once. Any new harness that drives the UI (screenshot scripts included) must do the same, or it will do the same damage.

## Step B — Headless capture (admin, `capture_debug.bat`)

Do **not** run `python -m src.main --headless` from a non-admin agent.

1. Pick a **rendering** process:

```bat
python -c "import psutil; names=sorted({p.info['name'] for p in psutil.process_iter(['name']) if p.info['name'] and p.info['name'].endswith('.exe')}); print(names[:25])"
```

2. Run (UAC prompt — user must accept):

```bat
Scripts\capture_debug.bat --process-name <App.exe> --timed 8
```

3. Validate the newest CSV with a schema-driven loop over `CSV_COLUMNS` (see the previous Chinese skill's Python snippet, now in `verify-metrics`). Every export column is reported. `gpu_available()` requires non-NA `AppGPU%` and `AppVramMB`.

Zero frames → the process is not presenting; retry or `--all-processes`.

## Step C — Field changes

If you changed FrameData / SystemSnapshot / PerProcessSnapshot / sampling / CSV columns, also run **`verify-metrics`**.

## Not covered (expected)

- Cross-process PresentMon + sampler threads (Step B)
- Platform GPU% / VRAM (skip on machines without a GPU)
- Network (GitHub update check — unit tests cover the contract, not live Releases)
- Visual color checks

## Done when

- Step A all green
- Step B: latest `temp/igpmon-*.csv` has rows; no export column is all-NA when the source exists; GPU box has non-NA AppGPU%/AppVramMB
- Field changes → `verify-metrics` also passed

## Permissions

Headless needs admin. `capture_debug.bat` self-elevates. Agents cannot bypass UAC; they read `temp/` afterwards.
