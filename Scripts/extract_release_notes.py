"""Build bilingual GitHub Release notes from CHANGELOG.md + CHANGELOG.zh-CN.md.

Usage (from repo root):

    python Scripts/extract_release_notes.py
    python Scripts/extract_release_notes.py --version 0.1.3
    python Scripts/extract_release_notes.py --version 0.1.3 --out build/generated/release_notes.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.app_info import GITHUB_REPO_URL
from src.core.changelog import load_raw, parse_versions, version_ids


def _read_version(root: Path) -> str:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not version:
        raise SystemExit("VERSION is empty")
    return version


def _body_without_heading(block: str) -> str:
    lines = block.splitlines()
    if lines and lines[0].startswith("## "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _block_for(version: str, locale: str) -> str:
    versions = parse_versions(load_raw(locale))
    for ver, content in versions:
        if ver == version:
            return _body_without_heading(content)
    known = ", ".join(ver for ver, _ in versions) or "(none)"
    raise SystemExit(
        f"version {version} not found in {locale} changelog; have {known}"
    )


def _previous_version(version: str) -> str | None:
    ids = version_ids(load_raw("en"))
    try:
        index = ids.index(version)
    except ValueError:
        return None
    if index + 1 < len(ids):
        return ids[index + 1]
    return None


def render_notes(version: str) -> str:
    en_ids = version_ids(load_raw("en"))
    zh_ids = version_ids(load_raw("zh_CN"))
    if en_ids != zh_ids:
        raise SystemExit(
            f"changelog version mismatch: en={en_ids} zh_CN={zh_ids}"
        )
    if version not in en_ids:
        raise SystemExit(
            f"version {version} not in CHANGELOG.md; have {', '.join(en_ids) or '(none)'}"
        )

    english = _block_for(version, "en")
    chinese = _block_for(version, "zh_CN")
    lines = [
        f"# IGP Performance Monitor {version}",
        "",
        "## English",
        "",
        english,
        "",
        "## 简体中文",
        "",
        chinese,
    ]
    previous = _previous_version(version)
    if previous:
        lines.extend([
            "",
            "---",
            "",
            "Compare with the previous release: "
            f"{GITHUB_REPO_URL}/compare/v{previous}...v{version}",
        ])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write bilingual GitHub Release notes from the changelog files",
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--version", default=None, help="X.Y.Z (default: VERSION file)")
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Write here instead of stdout (directories are created)",
    )
    args = parser.parse_args()

    # load_raw() reads resource_root(), which is the repo in unfrozen runs.
    version = args.version or _read_version(args.root)
    text = render_notes(version)
    if args.out is None:
        sys.stdout.write(text)
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
