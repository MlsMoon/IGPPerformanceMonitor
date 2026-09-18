# Contributing

Thanks for helping with IGP Performance Monitor. This is a Windows-only desktop app (PyQt5 + Intel PresentMon).

## Before you change `src/`

1. Read [CLAUDE.md](CLAUDE.md) for architecture and pitfalls.
2. Open the matching module note under `.claude/skills/dev-guide/modules/`.
3. After coding, follow `.claude/skills/test-after-changes/SKILL.md`.
4. If you change metric fields or CSV columns, also run `verify-metrics`.

Project workflow skills are **English** and are the source of process rules (release, tests, GitHub Releases). Third-party PyQt reference skills stay as upstream English docs.

## Dev setup

```bat
pip install -r requirements.txt
Scripts\run_dev.bat
```

PresentMon needs Administrator (or membership in **Performance Log Users**). Every entry point self-elevates.

Headless capture (do **not** run `python -m src.main --headless` from a non-admin agent — UAC relaunch drops the output):

```bat
Scripts\capture_debug.bat --process-name Unity.exe --timed 8
```

## Tests

This project does not keep a large assertion suite. After a change:

```bat
python Scripts/check.py              :: compile + import + lint
python -m src.main -t ui             :: real window + PNGs in temp/selfcheck/shots/
python -m src.main -t update         :: real localhost download / verify / cancel
python -m src.tests                  :: three contract checks (i18n / CSV / manifest)
```

The `capture` area needs admin: `Scripts\selfcheck.bat capture -a App.exe -s 8`. Do not run `python -m src.main -t capture` from a non-admin shell (UAC relaunch drops the output).

Read the report. `ERROR` fails the run; `SUSPECT` and the screenshots are judgement calls. See `test-after-changes` and `test-design`. Do not add mocks or fabricated frames.

## Pull requests

- Keep the change focused; do not mix refactors with feature work
- Prefer a self-check area (`src/selfcheck/`) over a new file in `src/tests/`
- UI strings go through `tr(key)` in **both** `src/i18n/en.py` and `src/i18n/zh_CN.py`
- Do not add secrets, OSS upload scripts, or hardcoded credentials
- Source comments, project skills, and commit messages stay in English. Do not add Chinese comments. User-facing changelog is bilingual (`CHANGELOG.md` + `CHANGELOG.zh-CN.md`, same level of detail). Other Chinese copy is `src/i18n/zh_CN.py` and `docs/zh-CN/` / `docs/zh-TW/`.
- Self-update assets are published only as **GitHub Release** files (`app_manifest.json`, portable EXE, updater, installer)
- Open pull requests against **`develop`**. Do not force-push `develop` or `release`.

## Release

Maintainers follow `.claude/skills/release/SKILL.md`: bump `VERSION` on `develop`, fast-forward `release`, annotated tag `vX.Y.Z` on `release`. GitHub Actions builds the EXEs + installer and publishes the Release.
