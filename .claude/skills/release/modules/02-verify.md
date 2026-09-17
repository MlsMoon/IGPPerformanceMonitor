# 02 · Verify: tests + headless

## Key files

- `src/tests/` — offscreen suite
- `Scripts/capture_debug.bat` — self-elevating headless
- `temp/` — capture output

## Responsibilities

Confirm tests pass and the capture pipeline still writes real frames when this release touches metrics.

## Steps

### 1. Offscreen (required, no admin)

```bat
python -m src.tests
```

All must PASS (skips allowed). Fail → stop the release.

### 2. Headless (best-effort)

Skip and record why if **either**:

- Not admin (`net session` fails) — do not wait on UAC in a fully automatic run
- This release does **not** touch the data pipeline (FrameData / snapshots / sampler / CSV / stats)

If admin **and** pipeline changes, follow `test-after-changes` Step B:

1. Pick a rendering process
2. `Scripts\capture_debug.bat --process-name <App.exe> --timed 8`
3. Confirm `temp/igpmon-*.csv` has rows and enriched columns are not all NA

### 3. Continue to phase 3

No confirmation gate.

## Pitfalls

- Headless must use `capture_debug.bat`. Bare `python -m src.main --headless` relaunches elevated and the agent loses stdout.
- Zero frames usually means the process is not presenting. Try another GUI app or `--all-processes`.
- All-NA enriched columns → NVML/psutil/perf-counter wiring.

## Checklist

- [ ] `python -m src.tests` all PASSED
- [ ] If pipeline changed and admin available: CSV rows > 0, enriched columns not all NA
