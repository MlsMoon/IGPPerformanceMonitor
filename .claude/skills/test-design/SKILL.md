---
name: test-design
description: |
  Where a new check belongs, how coverage grows by itself, and when to extend
  an area after a miss. No fabricated data, no mocks. Read before adding any
  check or touching src/tests/ or src/selfcheck/. How to run them is
  test-after-changes. Triggers: "写测试", "add test", "测试设计", before
  editing src/tests/ or src/selfcheck/
---

# Designing a check

This project keeps very few tests on purpose. Verification is the app
exercising itself under `-t` and the author of the change reading the report.
A subagent is a second pair of eyes, not a place to put new assertions — see
`test-after-changes`.

Before adding anything, decide which of three places it belongs in. Then make
sure the **planner will find it next time** (an `AREA` declaration, not a
paragraph in a skill).

## Where does it go?

**A self-check area (`src/selfcheck/<name>_area.py`) — the default.**
Behaviour: a window that has to build, a capture that has to populate columns,
a download that has to cancel. Export ``AREA`` + ``run(report, out_dir, **kw)``.
That is enough: ``-t <name>``, ``-t all``, and ``python -m src.selfcheck plan``
discover the file. There is no central switch.

**A contract check (`src/tests/`) — rare, needs a reason.** Only exhaustive
comparisons against a single source of truth. Today: i18n key parity,
`CSV_COLUMNS` vs `FrameData` plus a real roundtrip, required manifest fields.
A fourth needs an argument for why an agent reading a report cannot do it.
Register the path prefixes in `src/selfcheck/plan.py` `_CONTRACTS` so the
planner selects it. Do not grow this list because a behaviour "felt important".

**Nowhere.** Compile / import errors are `Scripts/check.py`. A constructor
that must not throw is already covered by whichever area builds it.

## How coverage grows (do not maintain a table)

Three mechanisms. Prefer them over adding files.

1. **Schema walking, inside an area.** Iterate `CSV_COLUMNS`, every `*_qss`
   generator, every i18n key, changelog `## X.Y.Z` ids (English vs Chinese),
   `REQUIRED_MANIFEST_FIELDS`, `Theme` fields. A
   new column or stylesheet is covered the day it is added. A hand-written
   list of ten columns is a list that will be nine columns out of date.

2. **`AREA.touches` + discovery.** The planner selects areas by path prefix.
   A new widget under `src/ui/` is already in the `ui` area. A new package
   under `src/<pkg>/` that no area claims prints `UNCOVERED` — that is the
   expand signal. Either widen an existing `touches` tuple or add
   `<pkg>_area.py`. Do not add a `src/tests/test_<pkg>.py`.

3. **Self-iteration after a miss.** When a bug ships past a green report
   (or a human/subagent sees in a PNG something the area never mentioned):
   - add a `report.fact` / `report.suspect` / `report.error` to the area that
     should have seen it, walking a schema if you can
   - add a one-line pitfall here or in the matching `dev-guide` module
   - if the miss was "we always spawn a subagent" or "we never look at PNGs",
     fix `test-after-changes`, not the area
   Same loop as `dev-guide`: the skill cannot write itself, but the rule is
   that a miss updates the check, not that we pile on assertions.

`python -m src.selfcheck plan <new-path>` after you add a package. If it
says `UNCOVERED`, you are not done.

## `AREA` shape

```python
from src.selfcheck.spec import Area

AREA = Area(
    name="overlay",          # becomes -t overlay
    touches=("src/ui/views/overlay_window.py",),
    needs_qt=True,           # builds widgets
    needs_admin=False,       # PresentMon? then True
    judge="visual",          # parent | visual | numbers
)
```

`judge` is a hint for the planner, not a trigger by itself:

- `parent` — stdout is enough
- `visual` — PNGs are the point; still parent-first; subagent only on commit /
  user-asked / unexplained SUSPECT
- `numbers` — fill rates; parent judges against the machine; **never** a
  subagent (capture cannot elevate in one)

## Rules for the body of `run`

### No fabricated data, ever

No `make_frame()`, no mock. Frames come from `src.selfcheck.data` (real
`temp/real_capture.csv`). Network code gets a real `127.0.0.1` server. If
real data cannot be produced, skip — do not invent.

### Report, do not threshold

- `report.fact(...)` — default
- `report.error(...)` — provably broken, no context needed (exception,
  unbalanced QSS braces, download bytes differ, path-traversal guard failed)
- `report.suspect(...)` — looks wrong, machine-dependent. Never sets the exit
  code. Do not encode a fill-rate threshold you cannot defend.

### Photograph the object you describe

If the check is about how something looks: seed **that** widget, replay
`ms_between_presents` per app (imported `time_in_seconds` is 0;
`cpu_start_time` is milliseconds), `_spin` before every grab, native Qt
platform (offscreen has no fonts here). Grab both themes at two widths.

### Contain the blast radius

`report.step(name)` around each block. Sandbox `APPDATA` (`selfcheck._start_qt`)
before building a `MainWindow`.

**A path that starts the process** (first-run picker, last-window-closed,
UAC relaunch) must spawn `python -m src.main` or the packed EXE. `-t ui`
already has a QApp inside `exec_()`, so it cannot see the 0.1.5 "dialog OK
quits the app" bug. That is `-t startup`. In-process, still assert that
`LanguageDialog` OK stores a locale *code* — `QWidget.setProperty("locale")`
round-trips a `QLocale`, and that was 0.1.6.

### Prove a new check once

Break the thing on purpose, confirm the area says so, restore. A check never
seen failing is a check you do not know works.

## Forbidden

- Spawning a subagent as a substitute for reading the report
- `unittest.mock` / fabricated `FrameData`
- Hard-coded floats from a live capture; committing `temp/real_capture.csv`
- Growing `src/tests/` because a behaviour felt important
- A hardcoded "if you touch X run Y" table in a skill — that is `AREA.touches`
- Asserting a threshold no one can defend
