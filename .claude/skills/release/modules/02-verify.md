# 02 · Verify: static + self-check + headless

## Key files

- `Scripts/check.py` — compile / import / lint
- `src/selfcheck/` — `-t` areas (`ui`, `capture`, `update`)
- `src/tests/` — three contract checks only (i18n / CSV schema / manifest)
- `Scripts/selfcheck.bat` — self-elevating capture area
- `temp/selfcheck/` — reports and screenshots

## Responsibilities

Confirm the static gate is green, the self-check areas the change touches report no ERROR, and the capture pipeline still writes real frames when this release touches metrics.

## Steps

### 1. Static + self-check (required)

```bat
python Scripts/check.py
python -m src.main -t ui
python -m src.main -t update
python -m src.tests
```

`check.py` and the contract checks must be green. Fail → stop the release.

The `ui` / `update` reports must have no `ERROR`. `SUSPECT` lines and the four PNGs under `temp/selfcheck/shots/` are judgement calls — open them. Do not treat exit 0 as "the window looks fine".

### 2. Headless / capture area (best-effort)

Skip and record why if **either**:

- Not admin (`net session` fails) — do not wait on UAC in a fully automatic run
- This release does **not** touch the data pipeline (FrameData / snapshots / sampler / CSV / stats)

If admin **and** pipeline changes:

```bat
Scripts\selfcheck.bat capture -a <App.exe> -s 8
```

Read `temp/selfcheck/report.txt`. A column that used to fill and is now 0% is a regression. Confirm `temp/igpmon-*.csv` (or the report's frame count) has rows.

### 3. Continue to phase 3

No confirmation gate.

## Pitfalls

- Do not run `python -m src.main -t capture` or `--headless` from a non-admin agent. Both relaunch elevated and the output does not come back. Use `Scripts\selfcheck.bat` / `Scripts\capture_debug.bat`.
- Zero frames usually means the process is not presenting. Try another GUI app or `--all-processes`.
- All-NA enriched columns → NVML/psutil/perf-counter wiring.

## Checklist

- [ ] `python Scripts/check.py` OK
- [ ] `-t ui` / `-t update`: no ERROR; screenshots opened
- [ ] `python -m src.tests` passed (skips allowed)
- [ ] If pipeline changed and admin available: capture report has frames, enriched columns not all empty
