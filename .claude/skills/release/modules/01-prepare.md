# 01 · Prepare: version + changelog

## Key files

- `VERSION` — semver single source
- `CHANGELOG.md` — English (canonical); Help → Changelog in `en`
- `CHANGELOG.zh-CN.md` — Simplified Chinese; Help → Changelog in `zh_CN`
- `Scripts/extract_release_notes.py` — bilingual GitHub Release body
- `src/core/app_info.py` — reads `VERSION` (do not edit the version there)
- `src/core/changelog.py` — locale path + `## X.Y.Z` parser

## Responsibilities

Pick the next version, write `VERSION`, and write **detailed, bilingual,
user-facing** changelog blocks. Those two files are the source of the GitHub
Release body. Auto-generated compare links are not a changelog.

## Steps

### 1. Preconditions

```bat
git status
python Scripts/check.py
python -m src.tests
```

Working tree should be releasable. The static gate and contract checks must pass. If not, stop and fix.

### 2. Show current state

Read `VERSION`, `CHANGELOG.md`, and `CHANGELOG.zh-CN.md`.

**Default bump is patch (`+0.0.1`).** `0.1.2` → `0.1.3`. Use a different number only when the user named one (`release 0.2.0`). Do not ask. Do not promote to minor/major from the commit list on your own.

### 3. Write VERSION

```bat
echo 0.2.5> VERSION
```

No extra whitespace. This file is the only version source.

### 4. Changelog (English **and** Simplified Chinese)

```bat
git describe --tags --abbrev=0
git log <last-tag>..HEAD --no-merges --format="%h %s%n%b"
```

Read the commit **bodies**, not only the subjects. Insert a `## X.Y.Z` block
under the intro of **both** files, newest first. The two files must list the
**same versions** in the same order.

#### What "detailed" means

GitHub's `generate_release_notes: true` produced only:

`Full Changelog: https://github.com/…/compare/v0.1.2...v0.1.3`

That is not acceptable. Neither is a four-bullet dump of commit subjects
("system info layout, a quieter console, and a smaller test loop").

Write so a user who never opened the repo can decide whether to update:

- One or two sentences of context under the heading (`Released YYYY-MM-DD.`
  plus what this release is for).
- Then `### Added` / `### Changed` / `### Fixed` as needed. Chinese headings
  are `### 新增` / `### 变更` / `### 修复`.
- Each bullet is a user-visible change with **where it shows up** (menu path,
  widget, overlay, installer asset) and **what was wrong or missing before**
  when that is the point. "Stopping a capture now hides overlays, because the
  follow timer kept calling show() and left the last FPS frozen" is the bar.
  "Fix overlay teardown" is not.
- `### For contributors` / `### 面向贡献者` is optional and short: test-loop
  or release-tooling only. Do not hide a user-visible fix there.

Forbidden as the whole entry:

- Commit subjects copied in order
- Internal refactors with no user effect, unless collapsed into one tooling line
- Relying on the compare URL to "do the writing"

#### Shape (keep the `## X.Y.Z` heading exact)

English (`CHANGELOG.md`):

```markdown
## 0.1.4

Released 2026-09-20.

One or two sentences of context.

### Added

- Help → … does X. Before, Y.

### Changed

- …

### Fixed

- …

### For contributors

- …
```

Chinese (`CHANGELOG.zh-CN.md`) uses the same `## 0.1.4` heading (the dialog
splits on semver H2s) and translates every user-facing bullet. Do not leave
the Chinese file as a shorter summary of the English one.

### 5. Preview the GitHub body

```bat
python Scripts/extract_release_notes.py --version X.Y.Z
```

Skim stdout. It must contain both `## English` and `## 简体中文` sections with
the bullets you just wrote, not a lone compare link. CI runs the same command
and publishes that file as the Release body (`generate_release_notes: false`).

### 6. Continue

Show the new VERSION and both changelog blocks, then go to phase 2 without waiting.

## Pitfalls

- **Only edit `VERSION` for the number.** Never hand-edit `APP_BUILD`.
- **`parse_version()` is tuple compare.** Do not string-compare semver.
- **Do not skip tests.**
- **Do not use GitHub auto-notes as the body.** `release.yml` sets
  `body_path` + `generate_release_notes: false` on purpose. Re-enabling
  auto-notes reintroduces the empty `Full Changelog: vA...vB` Release.
- **Headings are `## X.Y.Z` only.** Extra `##` lines become fake versions in
  Help → Changelog. Intro text stays under `# Changelog` / `# 更新记录`.
- **Both locale files are bundled.** New resource → `build.bat` `--add-data`,
  `IGPPerformanceMonitor.spec`, and `installer.iss`.
- **English and Chinese version lists must match.** `extract_release_notes.py`
  and the `ui` self-check fail on drift.

## Checklist

- [ ] `VERSION` is clean `X.Y.Z`
- [ ] `CHANGELOG.md` and `CHANGELOG.zh-CN.md` both have a detailed `## X.Y.Z` block
- [ ] Every user-visible change since the last tag is in both files, with context
- [ ] `python Scripts/extract_release_notes.py --version X.Y.Z` prints bilingual notes
- [ ] Static gate and contract checks passed
