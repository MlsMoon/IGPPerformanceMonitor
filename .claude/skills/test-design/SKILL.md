---
name: test-design
description: |
  How to write tests: prefer real captured data, keep the suite small but
  complete, drive coverage from schema. Read before creating or editing
  src/tests/ or inventing fixtures. Default to load_real_frames(). make_frame
  is an escape hatch (controlled values only, justify at the call site).
  How to run tests is test-after-changes. Triggers: "add test", "test fixture",
  "test design", before creating/editing src/tests/
---

# Test Design — small, complete, real pipeline

This project uses a custom `run()`-based runner under `src/tests/`. Core rule: **do not fake data when real capture exists.**

## Rules

### 0. Prefer real captured data

Default loaders in `src/tests/_factory.py`: `load_real_frames()` / `load_real_system_info()` / `load_real_frames_by_app()` read **`temp/real_capture.csv`** (gitignored). First miss auto-generates a headless `--all-processes --timed` capture (admin: inline / non-admin: UAC / failure: `SkipTest`, not fail).

Use `make_*` **only** when the test needs a controlled value real data cannot provide, and write a one-line reason at the call site. PID tracking that uses `os.getpid()` is not a fabricated-data exception.

### 1. Drive the real pipeline

Inputs should come from production code: `load_real_frames()` → `metrics_schema.frame_to_row` + real writer → `csv_importer.import_file`. Compare original vs imported relatively. Do not hand-write CSV strings or assert magic numbers like `1.2917`.

### 2. One real file, never committed

`temp/real_capture.csv` is machine-specific. Do not add capture dumps to git.

### 3. `make_*` is an escape hatch

Keep builders in `_factory.py`. If real data works, do not use them.

### 4. Schema-driven coverage

Walk the single source so new fields are auto-covered:

- CSV: `metrics_schema.CSV_COLUMNS`
- Theme: Theme fields
- i18n: every key in both locales (identical key sets)
- Update manifest: `REQUIRED_MANIFEST_FIELDS`

### 5. Few files, full coverage

Merge overlapping tests. Do not keep a parser test and a roundtrip test that invent different schemas.

### 6. Environment tolerance

The runner sets `QT_QPA_PLATFORM=offscreen`. `SkipTest` is a skip, not a fail. Guard platform/GPU/display asserts.

## Forbidden

- Using `make_frame()` when `load_real_frames()` would do
- Hard-coded CSV type/value checks or exact floats from a live capture
- Committing real captures
- Hand-written CSV strings (except a tiny golden PresentMon sample already in-tree)
- Copy-pasted `FrameData(magic numbers)` across files
- Cherry-picking five i18n keys
- Fake "roundtrips" that do not use the exporter schema
- Assuming a fixed core count / GPU / display (guard or use real defaults)

## Adding a test

1. Prefer `load_real_*`. `make_*` needs a reason comment.
2. Prefer schema iteration over enumerations.
3. New file `src/tests/test_<x>.py` with top-level `def run()`, registered in `__init__.py` `NON_QT` or `QT`.
4. Prove it with `python -m src.tests`.

Exception: `test_release_manifest` / `test_app_update_service` use tiny temp bytes because they test hashing and JSON, not capture semantics.
