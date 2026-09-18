# 03 · Commit + tag + push

## Key files

- `VERSION` / `CHANGELOG.md` / `CHANGELOG.zh-CN.md`
- `.claude/skills/release/` (if updated)

## Responsibilities

Commit the release, create an **annotated** tag, push branch + tag. That tag is what starts GitHub Actions.

## Steps

### 1. Commit

```bat
git add VERSION CHANGELOG.md CHANGELOG.zh-CN.md
git commit -m "Release X.Y.Z"
```

Include release-related skill/doc edits in the same commit if they are part of this ship.

### 2. Tag

```bat
git tag -a "vX.Y.Z" -m "Release X.Y.Z"
```

**Annotated only.** `git describe` and humans ignore lightweight tags.

### 3. Push (authorized by the release trigger)

```bat
git checkout release
git merge --ff-only develop
git push origin release
git tag -a "vX.Y.Z" -m "Release X.Y.Z"
git push origin vX.Y.Z
```

Ship from `release`. Push the branch first, then the annotated tag. Retry transient GitHub network errors.

## Pitfalls

- Tag is `v` + semver (`v0.1.0`). CI checks `github.ref_name == v$(VERSION)`.
- Tags are created on `release`, not `develop`.
- Do not tag if phase 2 tests failed.
- To undo an **unpublished** tag: `git tag -d vX.Y.Z` and `git push origin :refs/tags/vX.Y.Z`. Never recycle a tag that already has a GitHub Release.

## Checklist

- [ ] Commit message `Release X.Y.Z`
- [ ] Annotated tag `-a` with `v` prefix
- [ ] Branch and tag pushed
