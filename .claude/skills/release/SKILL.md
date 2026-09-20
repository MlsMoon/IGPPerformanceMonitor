---
name: release
description: |
  Ship IGP Performance Monitor: bump VERSION, changelog, verify tests, commit,
  annotated tag vX.Y.Z, push. GitHub Actions builds EXEs + installer and
  publishes a GitHub Release (app_manifest.json for in-app updates).
  Fully automatic after the trigger. Triggers: "release", "ship", "release X.Y.Z"
---

# Release — IGP Performance Monitor

Four phases, **in order, without pausing for confirmation**. Report each step. On failure, record why and continue any later step that is still possible. End with a pass/fail list.

## Flow

| Phase | What | Who | Doc |
|---|---|---|---|
| 1. Prepare | Version + CHANGELOG | Agent | `modules/01-prepare.md` |
| 2. Verify | Static + `-t` self-checks (required) + capture (best-effort) | Agent | `modules/02-verify.md` |
| 3. Publish git | commit + annotated tag `vX.Y.Z` + push | Agent | `modules/03-commit-tag.md` |
| 4. GitHub Release | Actions builds and uploads assets | GitHub Actions; agent watches | `modules/04-github-release.md` |

The trigger words authorize the git push. **CI is the only binary publisher.** Do not upload to object storage. Do not invent credentials.

## Branches

| Branch | Role |
|---|---|
| `develop` | **The only development branch.** Default integration line. Daily work, PRs, and agent edits land here. |
| `release` | Ship line only. Fast-forward from `develop`, then cut annotated tags (`vX.Y.Z`). No feature or fix commits. |

Both branches are **protected** (no force-push, no delete). Do not recreate `main` / `master`.

If HEAD is `release` and the task is not “ship this version”, `git checkout develop` first. After a tag, switch back to `develop`. Never commit product work on `release` and leave `develop` behind.

## Language

Project-owned skills, `CLAUDE.md`, source comments, and commit messages are **English**. Do not add Chinese comments or skill prose.

User-facing changelog is bilingual: `CHANGELOG.md` (English, canonical) and
`CHANGELOG.zh-CN.md` (Simplified Chinese). Write both in the same detail —
the Chinese file is not a shorter summary. Other Chinese user copy lives in
`src/i18n/locales/zh_CN.json` and `docs/zh-CN/` (`docs/zh-TW/` is Traditional).

## Version

If the user names a version (`release 0.2.0`), use that. **If they do not, bump the patch: `X.Y.Z` → `X.Y.(Z+1)`** (a 0.0.1 increment). Do not ask. Do not infer minor/major from the commit list unless they said so.

## Rules

- Changelog is bilingual and detailed (`CHANGELOG.md` + `CHANGELOG.zh-CN.md`; see `modules/01-prepare.md`). GitHub Release body is `Scripts/extract_release_notes.py`, **never** `generate_release_notes` / `--generate-notes`.
- Do not stop to ask "continue?" between phases.
- Headless capture is best-effort (needs admin). Skip if not admin **and** the change is not on the metrics pipeline. Pipeline changes must use `Scripts\capture_debug.bat`.
- Tag format is `v` + `VERSION` (example `v0.2.5`). Annotated (`-a`). Lightweight tags are rejected by `git describe` and by CI.
- After push, watch `.github/workflows/release.yml`. Confirm the Release has portable EXE, updater, Setup EXE, and `app_manifest.json`.
- If Actions fails, fix and push a new tag only after moving VERSION (do not recycle a published tag).

## Maintenance

When the release path changes (new artifact, tag rule, installer):

1. Update `modules/0N-*.md`
2. Sync this table if phase order changes
3. Record VERSION / changelog / CI / icon / secret pitfalls in the matching note
