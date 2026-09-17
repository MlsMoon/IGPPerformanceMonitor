---
name: test-after-changes
description: |
  How to verify a change. Default is cheap and local: a static script, then
  only the self-check areas the diff selects, judged by you. A subagent is the
  exception, not the loop. Ask the planner when unsure. Triggers: "test after
  changes", "写完代码测试", "测试一下", "selfcheck", before commit
---

# Verifying a change

Do **not** habitually spawn a subagent, and do **not** run every `-t` area.
Ask the planner, then do what it says.

```bat
python -m src.selfcheck plan
```

It reads `git status` / `git diff` (or the paths you pass) and prints the
areas, whether contract checks are due, and **whether a subagent is warranted**.
Follow that output. If you already know the change is a one-line comment,
`python Scripts/check.py` is enough and you can skip the planner.

> How to **write** a check, and how coverage grows → `test-design`.

## Decision (this is the rule)

The agent who made the change runs the commands and reads the report. A
subagent is a **second pair of eyes on artefacts**, not a test runner, and
only in the cases below. The planner encodes the same rules; if you and the
planner disagree, trust the planner.

| Situation | What to run | Who judges |
|---|---|---|
| Docs / skills / changelog / comments only | nothing (or `check.py` if a Script changed) | — |
| Any `src/` or `Scripts/*.py` | `python Scripts/check.py` | you (exit code) |
| Planner lists areas | those `-t` areas only | **you**, in this turn |
| Planner lists contracts | `python -m src.tests` | you (exit code) |
| Visual files + you are about to commit | `-t ui`, then a subagent to **read** the PNGs | subagent |
| Report has a SUSPECT you cannot defend | do not mark it fine; subagent reads the report | subagent |
| User said "测试一下" / "verify this" **and** the change is visual, wide, or already suspect | planner `--user-asked` | subagent if the planner says yes |
| You changed `src/selfcheck/` itself | every non-admin area, then a subagent dogfoods the report | subagent |
| Capture / metrics / CSV / sampler | `Scripts\selfcheck.bat capture` (admin). **Never** a subagent — it cannot pass UAC | you, reading `temp/selfcheck/report.txt` |
| Same session, you already opened these PNGs | do not spawn a subagent to look again | — |

**Never spawn a subagent to re-run `check.py` or `-t`.** Those are cheap and
you already have the tree. If you do spawn one, its job is *read
`temp/selfcheck/report.txt` and the PNGs; do not fix; do not re-run*.

### Why this is the default

A subagent does not have the change in context unless you write a long prompt,
costs a full turn, and cannot elevate. The last time one was launched "because
that is the workflow", it re-ran work the parent had just done. Parent-first
is faster and usually more accurate. The cases in the table are the ones
where a *fresh* reader looking at a picture or a fill-rate column catches
something the author will rationalize.

## Commands the planner will name

```bat
python Scripts/check.py                        :: always, if src/ or Scripts/*.py moved
python -m src.main -t ui                       :: window + four PNGs
python -m src.main -t update                   :: localhost download / verify / cancel
Scripts\selfcheck.bat capture -a App.exe -s 8  :: real PresentMon (admin)
python -m src.tests                            :: i18n / CSV / manifest contracts
```

`-a` is `--process-name`, `-s` is `--timed`. Transcript: `temp/selfcheck/report.txt`.
PNGs: `temp/selfcheck/shots/{dark,light}-{1280x800,1920x1080}.png`.

Capture needs admin. `selfcheck.bat` elevates in a **separate** console — poll
for `report.txt`. Unelevated `python -m src.main -t capture` exits non-zero on
purpose (a lost run must not look like a pass).

### Reading a report

- `ERROR` — broken. Fix it. Sets the exit code.
- `SUSPECT` — looks wrong, no threshold. **Judge it.** If you cannot explain
  it in one sentence, that is the `--suspect` case, not a pass.
- Facts — compare to what you meant to change.
- PNGs (ui area) — open all four at native resolution if the change is visual
  or the planner told you to. A downscaled preview hides clipping.

## Done when

- You ran what the planner named (not more, not less)
- `check.py` is green when it ran
- Named areas have no `ERROR`
- Every `SUSPECT` is explained or fixed
- You opened the PNGs yourself **or** a subagent did, in the cases that require it
- You did **not** spawn a subagent unless the planner said `subagent: yes`
