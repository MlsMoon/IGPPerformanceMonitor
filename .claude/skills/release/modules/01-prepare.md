# 01 · Prepare: version + changelog

## Key files

- `VERSION` — semver single source
- `CHANGELOG.md` — Help → Changelog
- `src/core/app_info.py` — reads `VERSION` (do not edit the version there)

## Responsibilities

Pick the next version, write `VERSION`, add a user-facing changelog block.

## Steps

### 1. Preconditions

```bat
git status
python Scripts/check.py
python -m src.tests
```

Working tree should be releasable. The static gate and contract checks must pass. If not, stop and fix.

### 2. Show current state

Read `VERSION` and `CHANGELOG.md`. Choose the next semver (patch/minor/major from the commits since the last tag).

### 3. Write VERSION

```bat
echo 0.2.5> VERSION
```

No extra whitespace. This file is the only version source.

### 4. Changelog

```bat
git describe --tags --abbrev=0
git log <last-tag>..HEAD --oneline --no-merges
```

Group as features / fixes / other. Insert `## X.Y.Z` under `# Changelog`. Write for users, not "refactor QSS helper". Internal-only work can be one "tooling" line.

### 5. Continue

Show the new VERSION and changelog block, then go to phase 2 without waiting.

## Pitfalls

- **Only edit `VERSION` for the number.** Never hand-edit `APP_BUILD`.
- **`parse_version()` is tuple compare.** Do not string-compare semver.
- **Do not skip tests.**

## Checklist

- [ ] `VERSION` is clean `X.Y.Z`
- [ ] Changelog covers user-visible work since the last tag
- [ ] Offscreen tests passed
