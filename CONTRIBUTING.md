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

```bat
python -m src.tests
```

The suite forces `QT_QPA_PLATFORM=offscreen`. Prefer real capture data via `load_real_frames()`; see `test-design`.

## Pull requests

- Keep the change focused; do not mix refactors with feature work
- Add or update `src/tests/` when public APIs change
- UI strings go through `tr(key)` in **both** `src/i18n/en.py` and `src/i18n/zh_CN.py`
- Do not add secrets, OSS upload scripts, or hardcoded credentials
- Source comments, project skills, changelog, and commit messages stay in English. Do not add Chinese comments. `src/i18n/zh_CN.py` is the only Chinese file (UI strings).
- Self-update assets are published only as **GitHub Release** files (`app_manifest.json`, portable EXE, updater, installer)
- Open pull requests against **`develop`**. Do not force-push `develop` or `release`.

## Release

Maintainers follow `.claude/skills/release/SKILL.md`: bump `VERSION` on `develop`, fast-forward `release`, annotated tag `vX.Y.Z` on `release`. GitHub Actions builds the EXEs + installer and publishes the Release.
