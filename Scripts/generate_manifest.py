"""Generate app_manifest.json for a GitHub Release.

Usage (from repo root, after Scripts\\build.bat):

    python Scripts\\generate_manifest.py
    python Scripts\\generate_manifest.py --no-previous
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.app_info import APP_EXE_NAME, AUTO_UPDATER_EXE_NAME
from src.core.release_manifest import (
    build_manifest,
    fetch_previous_manifest,
    snapshot_current_as_previous,
    write_manifest,
)


def _read_version(root: Path) -> str:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not version:
        raise SystemExit("VERSION is empty")
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description="Write dist/app_manifest.json")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--no-previous", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    root: Path = args.root
    version = _read_version(root)
    dist = root / "dist"
    main_exe = dist / APP_EXE_NAME
    updater_exe = dist / AUTO_UPDATER_EXE_NAME
    installer_candidates = sorted(dist.glob(f"IGPPerformanceMonitor-Setup-{version}.exe"))
    installer_exe = installer_candidates[0] if installer_candidates else None

    previous = None
    if not args.no_previous:
        latest = fetch_previous_manifest()
        if latest and str(latest.get("version", "")) != version:
            previous = snapshot_current_as_previous(latest)

    manifest = build_manifest(
        version=version,
        main_exe=main_exe,
        updater_exe=updater_exe,
        installer_exe=installer_exe,
        previous=previous,
    )
    output = args.output or (dist / "app_manifest.json")
    write_manifest(output, manifest)
    print(f"Wrote {output}")
    print(f"  version={manifest['version']}")
    print(f"  main={manifest['mainExeSha256']}")
    print(f"  updater={manifest['updaterExeSha256']}")
    print(f"  previous={manifest['previous']['version'] if manifest.get('previous') else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
