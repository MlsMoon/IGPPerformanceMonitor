# 04 · GitHub Release (CI)

## Key files

- `.github/workflows/release.yml`
- `Scripts/build.bat` / `Scripts/build_installer.bat` / `Scripts/generate_manifest.py`
- `Scripts/installer.iss`
- `src/core/release_manifest.py`

## Responsibilities

After the tag exists, **GitHub Actions** builds and publishes. The agent watches and verifies; it does not upload binaries from a laptop unless Actions is down and the maintainer explicitly asks.

## Required assets (every Release)

| File | Role |
|---|---|
| `IGPPerformanceMonitor.exe` | Portable + in-app update payload |
| `auto_updater.exe` | Swapper downloaded by `AppUpdateService` |
| `IGPPerformanceMonitor-Setup-X.Y.Z.exe` | Inno Setup installer |
| `app_manifest.json` | Client contract (`releases/latest/download/app_manifest.json`) |

## Agent steps

1. `gh run watch` / `gh run list --workflow=release.yml` for the tag push
2. When green, open `https://github.com/MlsMoon/IGPPerformanceMonitor/releases/tag/vX.Y.Z`
3. Confirm all four assets exist
4. Fetch the latest manifest and check:
   - valid JSON, no UTF-8 BOM
   - `version` == `VERSION`
   - `mainExeUrl` / `updaterExeUrl` use `/releases/download/vX.Y.Z/`
   - SHA256 fields are 64-char hex
   - `previous` is the prior current, or `null` on the first GitHub Release

```bat
gh release view vX.Y.Z
curl -sL -A IGPPerformanceMonitor https://github.com/MlsMoon/IGPPerformanceMonitor/releases/latest/download/app_manifest.json
```

## Local emergency build (only if CI cannot run)

```bat
Scripts\build.bat --no-pause
Scripts\build_installer.bat
python Scripts\generate_manifest.py
gh release create vX.Y.Z dist\IGPPerformanceMonitor.exe dist\auto_updater.exe dist\IGPPerformanceMonitor-Setup-X.Y.Z.exe dist\app_manifest.json --title "IGP Performance Monitor X.Y.Z" --generate-notes
```

Still no object-storage upload. Still no keys in the repo.

## Pitfalls

- Inno Setup must be installed (`choco install innosetup` on CI).
- `build.bat` pauses unless `CI=true` or `--no-pause`.
- Manifest URLs are written **before** upload but must already point at the tag that is about to exist.
- Fetching `previous` uses the *current* latest release; after publish, "latest" becomes this version — generate the file **before** creating the Release.
- GitHub requires a User-Agent on downloads.
- Empty SHA256 must fail the job, not publish a broken client.

## Checklist

- [ ] Actions run succeeded
- [ ] Four assets present
- [ ] Manifest JSON valid, no BOM, hashes filled
- [ ] In-app latest URL returns this version
